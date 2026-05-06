"""
Cross-source duplicate event merger.

After all scrapers have upserted their events, this module scans the DB for
events that appear on multiple platforms (e.g., the same festival listed on
both Peatix and iwafu) and merges them:

  1. Detect pairs with name_ja similarity > 85% AND same start_date.
  2. Keep the "primary" event (higher-authority source via SOURCE_PRIORITY).
  3. Record the secondary source URL in primary.secondary_source_urls.
  4. Combine both raw_descriptions; set annotation_status = "pending" so the
     annotator re-processes the primary with richer combined content.
     (Only on the FIRST merge — subsequent runs skip re-annotation.)
  5. Deactivate the secondary event (is_active = False).

Pass 2 — News-report matching:
  News sources (google_news_rss, prtimes, nhk_rss) publish article-style
  titles that cannot be matched by name similarity alone.  They are matched
  to official events by:
    a. news.start_date falls within [official.start_date - LOOKBACK, official.end_date]
       (LOOKBACK = 90 days to catch pre-event press releases published before
        the event start date)
    b. location_name tokens overlap (≥1 common token of ≥2 chars)
  News events are always secondary; the official event is always primary.

This module is idempotent: re-running it produces the same result because
it checks whether the secondary URL is already present in
primary.secondary_source_urls before triggering re-annotation.

Notes on re-run stability:
  - secondary_source_urls is NOT included in upsert rows, so it is preserved
    between scraper runs.
  - On each re-run the secondary event is re-upserted (is_active = True), then
    merger re-deactivates it. This is slightly wasteful but correct.

Usage (standalone):
    python merger.py [--dry-run]
"""

import logging
import os
import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Lower value = higher authority (wins as "primary" when two events are merged).
# When both sources have the same priority, the one encountered first (lower
# start_date, then earlier creation order) wins.
SOURCE_PRIORITY: dict[str, int] = {
    "taiwan_cultural_center": 1,
    "taiwan_kyokai": 2,
    "taioan_dokyokai": 3,
    "koryu": 4,
    "taiwan_festival_tokyo": 5,
    "taiwan_matsuri": 6,
    "taiwanbunkasai": 7,  # official organiser, outranks aggregators
    "peatix": 8,
    "connpass": 9,
    "doorkeeper": 10,
    "iwafu": 11,
    "arukikata": 12,
    "ide_jetro": 13,
    "walkerplus": 14,
}

# Minimum name similarity to consider two events duplicates.
_SIMILARITY_THRESHOLD = 0.85

# Sources that publish news/article titles rather than event names.
# They are matched via date-range + location-overlap (Pass 2), never by
# name similarity (Pass 1).
_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss", "walkerplus"})

# How many days BEFORE an official event's start_date a news article may be
# published and still be considered a match (pre-event press releases).
_PRESS_RELEASE_LOOKBACK_DAYS = 90


def _normalize(name: str) -> str:
    """Strip all whitespace and lowercase for similarity comparison."""
    # Normalize registered trademark symbol variants (e.g. iwafu uses ®, official uses (R))
    name = name.replace("®", "(r)").replace("Ⓡ", "(r)")
    # Unify dash variants so katakana prolonged sound mark (ー), full-width hyphen (－),
    # em dash (—), horizontal bar (―) and ASCII hyphen-minus all compare as equal.
    # Without this, "台南ランタン祭ー" (walkerplus, ー) ≠ "台南ランタン祭－" (prtimes, －).
    name = re.sub(r"[ー－—―]", "-", name)
    # Strip wrapping quotes/brackets at the very ends so "「台湾祭…－」" ≡ "台湾祭…－".
    name = re.sub(r"^[「『《\"'(（\[【]+", "", name)
    name = re.sub(r"[」』》\"')）\]】]+$", "", name)
    # Strip iwafu-style subtitle suffixes like "-台南ランタン祭-"
    # (after dash unification, all variants collapse to the ASCII hyphen-minus class).
    name = re.sub(r"-[^-]{2,}-\s*$", "", name)
    # Strip year suffix (e.g. "台湾祭2026", "台湾文化祭2025春", "台灣節™東京2026")
    # so that recurring annual events with different year suffixes still match.
    name = re.sub(r"20\d{2}[春夏秋冬]?\s*$", "", name)
    return re.sub(r"[\s\u3000\u00a0]+", "", name).lower()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _location_overlap(loc_a: str | None, loc_b: str | None) -> bool:
    """Return True if two location strings share ≥1 token of ≥2 chars,
    OR if one is a substring of the other (both ≥4 chars to avoid noise)."""
    if not loc_a or not loc_b:
        return False
    a = loc_a.strip()
    b = loc_b.strip()
    # Substring containment for longer strings (e.g. "イオン太田" ⊂ "イオンモール太田").
    # Min length 4 avoids false matches like "東京" ⊂ "東京都".
    if len(a) >= 4 and len(b) >= 4:
        if a in b or b in a:
            return True

    def _tokens(s: str) -> set:
        return {t for t in re.split(r'[\s\u3000、,（()）・]', s) if len(t) >= 2}

    return bool(_tokens(a) & _tokens(b))


def _richness_score(ev: dict) -> int:
    """Return a data-richness score (higher = richer).

    Used as a tiebreaker when two events have equal SOURCE_PRIORITY.
    Fields checked (1 point each unless noted):
      official_url     — direct event page link
      start_date       — has a date (not NULL)
      end_date         — multi-day event info
      location_address — street-level address (vs just city name)
      location_name    — venue name
      raw_description  — each 200 chars = 1 point (up to 5)
    """
    score = 0
    if ev.get("official_url"):
        score += 1
    if ev.get("start_date"):
        score += 1
    if ev.get("end_date"):
        score += 1
    if ev.get("location_address"):
        score += 1
    if ev.get("location_name"):
        score += 1
    desc_len = len(ev.get("raw_description") or "")
    score += min(desc_len // 200, 5)
    return score


def _deactivate_payload(reason: str, pass_id: str) -> dict:
    """Build the update payload for deactivating an event with audit fields.

    pass_id: 'merger_pass_0' | 'merger_pass_1' | 'merger_pass_2'
             | 'merger_pass_3' | 'orphan_cleanup' | 'admin_manual'
    """
    from datetime import datetime, timezone
    return {
        "is_active": False,
        "deactivated_at": datetime.now(timezone.utc).isoformat(),
        "deactivated_reason": reason,
        "deactivated_by_pass": pass_id,
    }


def _deactivate_as_merged(primary_id: str, reason: str, pass_id: str) -> dict:
    """Build the update payload for a secondary event being merged into primary_id.
    Extends _deactivate_payload with merged_into_event_id for admin UI badge tracking.
    """
    payload = _deactivate_payload(reason, pass_id)
    payload["merged_into_event_id"] = primary_id
    return payload


def _date_in_range(
    date_str: str | None, start_str: str | None, end_str: str | None,
    lookback_days: int = 0,
) -> bool:
    """Return True if date_str (YYYY-MM-DD) falls within [start_str - lookback_days, end_str]."""
    if not date_str or not start_str or not end_str:
        return False
    from datetime import date, timedelta
    try:
        d = date.fromisoformat(date_str[:10])
        s = date.fromisoformat(start_str[:10]) - timedelta(days=lookback_days)
        e = date.fromisoformat(end_str[:10])
        return s <= d <= e
    except ValueError:
        return False


def run_merger(dry_run: bool = False) -> int:
    """
    Detect and merge cross-source duplicate events in the DB.

    Returns the number of duplicate pairs handled (merged or already-merged).
    """
    from database import _get_client

    sb = _get_client()

    # ------------------------------------------------------------------
    # Pass 0 — Within-source Google News RSS dedup
    # Google News RSS returns multiple articles about the same event across
    # different queries or different days.  Each article gets a unique
    # source_id (URL hash), so the in-scraper dedup (by raw title) misses
    # them.  After annotation, name_ja is normalised — we can deduplicate
    # by name_ja similarity ≥ _SIMILARITY_THRESHOLD across all active
    # google_news_rss events (including start_date=NULL).
    # Primary: prefer non-NULL start_date, then longer raw_description.
    # Guards:
    #   - Same parent article (same base source_id hash): skip — sub-events
    #     from the same article represent distinct screenings.
    #   - Both events have non-null location AND they don't overlap: skip —
    #     same film at different venues should remain separate events.
    # ------------------------------------------------------------------
    gnews_res = (
        sb.table("events")
        .select(
            "id,source_name,source_id,source_url,name_ja,start_date,"
            "location_name,raw_description,secondary_source_urls,annotation_status"
        )
        .eq("is_active", True)
        .eq("source_name", "google_news_rss")
        .not_.is_("name_ja", None)
        .execute()
    )
    gnews_events = gnews_res.data or []
    logger.info("Merger Pass 0: %d active google_news_rss events", len(gnews_events))

    def _gnews_base_id(source_id: str | None) -> str:
        """Extract the base article ID before any _sub suffixes.
        e.g. 'gnews_abc123_sub1_sub2' → 'gnews_abc123'"""
        if not source_id:
            return ""
        return source_id.split("_sub")[0]

    pass0_handled: set[str] = set()
    pass0_count = 0

    for i in range(len(gnews_events)):
        ev_a = gnews_events[i]
        if ev_a["id"] in pass0_handled:
            continue
        for j in range(i + 1, len(gnews_events)):
            ev_b = gnews_events[j]
            if ev_b["id"] in pass0_handled:
                continue
            if _similarity(ev_a["name_ja"], ev_b["name_ja"]) < _SIMILARITY_THRESHOLD:
                continue

            # Guard: same parent article → skip UNLESS same location+date (true dup)
            if _gnews_base_id(ev_a.get("source_id")) == _gnews_base_id(ev_b.get("source_id")):
                # Same parent article. Only proceed if same venue AND same start_date
                # (e.g., two sub-events created for the same screening → true duplicate)
                same_location = (
                    ev_a.get("location_name") and ev_b.get("location_name")
                    and _location_overlap(ev_a["location_name"], ev_b["location_name"])
                )
                same_date = ev_a.get("start_date") and ev_b.get("start_date") and (
                    ev_a["start_date"][:10] == ev_b["start_date"][:10]
                )
                if not (same_location and same_date):
                    continue  # different screenings from same article, skip

            # Guard: both events have location AND locations don't overlap → different
            # venues for same work (e.g. same film at different cinemas), skip
            if (
                ev_a.get("location_name") and ev_b.get("location_name")
                and not _location_overlap(ev_a["location_name"], ev_b["location_name"])
            ):
                continue

            # Determine primary: prefer non-null start_date, then has location, then longer raw_description
            def _gnews_score(ev: dict) -> tuple:
                has_date = 0 if ev.get("start_date") else 1  # 0 = better
                no_location = 0 if ev.get("location_name") else 1  # prefer events WITH location
                desc_len = -(len(ev.get("raw_description") or ""))  # negative = longer is better
                return (has_date, no_location, desc_len)

            if _gnews_score(ev_a) <= _gnews_score(ev_b):
                primary, secondary = ev_a, ev_b
            else:
                primary, secondary = ev_b, ev_a

            secondary_url = secondary["source_url"]
            existing_urls = primary.get("secondary_source_urls") or []
            already_merged = secondary_url in existing_urls

            logger.info(
                "%s  [gnews] '%s'  ←  [gnews] '%s'  (within-source sim=%.2f)",
                "EXISTS" if already_merged else "MERGE ",
                (primary["name_ja"] or "")[:40],
                (secondary["name_ja"] or "")[:40],
                _similarity(ev_a["name_ja"], ev_b["name_ja"]),
            )

            if dry_run:
                pass0_count += 1
                pass0_handled.add(secondary["id"])
                continue

            new_urls = list(dict.fromkeys(existing_urls + [secondary_url]))
            upd: dict = {"secondary_source_urls": new_urls}
            if not already_merged:
                primary_desc = (primary.get("raw_description") or "").strip()
                secondary_desc = (secondary.get("raw_description") or "").strip()
                if secondary_desc and secondary_desc not in primary_desc:
                    upd["raw_description"] = (
                        primary_desc + f"\n\n---\n別来源補足 (gnews)\n{secondary_desc}"
                    )
                upd["annotation_status"] = "pending"

            try:
                sb.table("events").update(upd).eq("id", primary["id"]).execute()
                sb.table("events").update(
                    _deactivate_as_merged(
                        primary["id"],
                        f"merged into {primary['id']} (gnews within-source dedup)",
                        "merger_pass_0",
                    )
                ).eq("id", secondary["id"]).execute()
                pass0_count += 1
                pass0_handled.add(secondary["id"])
            except Exception as exc:
                logger.error(
                    "Merger Pass 0: failed to merge %s ← %s: %s",
                    primary["source_id"],
                    secondary["source_id"],
                    exc,
                )

    logger.info("Merger Pass 0: %d google_news_rss within-source pair(s) handled", pass0_count)

    # Fetch all active events that have a start_date and name_ja.
    # Note: gnews sub-events (source_id contains '_sub') ARE included here so
    # Pass 1/2 can match them against official sources by name+location/date.
    # Same-source within-article dedup is handled by Pass 0.
    res = (
        sb.table("events")
        .select(
            "id,source_name,source_id,source_url,official_url,name_ja,start_date,end_date,"
            "location_name,location_address,raw_description,secondary_source_urls,"
            "annotation_status,work_id,category"
        )
        .eq("is_active", True)
        .not_.is_("start_date", None)
        .not_.is_("name_ja", None)
        .execute()
    )
    events = res.data or []
    logger.info("Merger: loaded %d active events for Pass 1/2", len(events))

    # Group by start_date (YYYY-MM-DD prefix)
    date_groups: dict[str, list] = defaultdict(list)
    for ev in events:
        date_key = (ev["start_date"] or "")[:10]
        if date_key:
            date_groups[date_key].append(ev)

    # Track secondary IDs already handled in this run to avoid double-processing
    handled_secondary_ids: set[str] = set()
    merge_count = 0

    for date_key, group in sorted(date_groups.items()):
        if len(group) < 2:
            continue

        for i in range(len(group)):
            ev_a = group[i]
            if ev_a["id"] in handled_secondary_ids:
                continue

            for j in range(i + 1, len(group)):
                ev_b = group[j]
                if ev_b["id"] in handled_secondary_ids:
                    continue

                # Only cross-source (within-source dedup is handled by dedup_events)
                if ev_a["source_name"] == ev_b["source_name"]:
                    continue

                sim = _similarity(ev_a["name_ja"], ev_b["name_ja"])
                if sim < _SIMILARITY_THRESHOLD:
                    continue

                # ----- Works-entity skip conditions (added with migration 048) -----
                # 1. Both events have non-null work_id and they differ → different
                #    creative works that happen to share a similar title; never merge.
                wa = ev_a.get("work_id")
                wb = ev_b.get("work_id")
                if wa and wb and wa != wb:
                    logger.info(
                        "[Pass 1 SKIP] different work_id: %s ↔ %s",
                        ev_a["id"],
                        ev_b["id"],
                    )
                    continue

                # 2. Same-name movie/performing_arts at different venues → likely the
                #    same work shown at multiple cinemas/theaters. Skip merge; the
                #    Works entity (work_id) is the correct linkage layer instead.
                cats_a = set(ev_a.get("category") or [])
                cats_b = set(ev_b.get("category") or [])
                _WORK_CATS = {"movie", "performing_arts"}
                if (cats_a & _WORK_CATS or cats_b & _WORK_CATS) and not _location_overlap(
                    ev_a.get("location_name"), ev_b.get("location_name")
                ):
                    logger.info(
                        "[Pass 1 SKIP] same-name movie/performing_arts at different "
                        "venues — likely same work, different screening: "
                        "[%s @ %s] ↔ [%s @ %s]",
                        (ev_a.get("name_ja") or "")[:40],
                        (ev_a.get("location_name") or "?")[:30],
                        (ev_b.get("name_ja") or "")[:40],
                        (ev_b.get("location_name") or "?")[:30],
                    )
                    continue
                # -------------------------------------------------------------------

                # Determine primary / secondary by source priority.
                # Lower number = higher authority.  Equal priority →
                # use data-richness score as tiebreaker.
                pri_a = SOURCE_PRIORITY.get(ev_a["source_name"], 99)
                pri_b = SOURCE_PRIORITY.get(ev_b["source_name"], 99)
                if pri_a < pri_b:
                    primary, secondary = ev_a, ev_b
                elif pri_b < pri_a:
                    primary, secondary = ev_b, ev_a
                else:
                    # Equal priority — richer data wins
                    if _richness_score(ev_a) >= _richness_score(ev_b):
                        primary, secondary = ev_a, ev_b
                    else:
                        primary, secondary = ev_b, ev_a

                secondary_url = secondary["source_url"]
                existing_urls = primary.get("secondary_source_urls") or []
                already_merged = secondary_url in existing_urls

                logger.info(
                    "%s  [%s] '%s'  ←  [%s] '%s'  (sim=%.2f)",
                    "EXISTS" if already_merged else "MERGE ",
                    primary["source_name"],
                    (primary["name_ja"] or "")[:40],
                    secondary["source_name"],
                    (secondary["name_ja"] or "")[:40],
                    sim,
                )

                if dry_run:
                    merge_count += 1
                    handled_secondary_ids.add(secondary["id"])
                    continue

                # --- Build primary update ---
                new_secondary_urls = list(
                    dict.fromkeys(existing_urls + [secondary_url])
                )
                primary_update: dict = {"secondary_source_urls": new_secondary_urls}

                # Propagate official_url from secondary to primary if primary lacks it
                if not primary.get("official_url") and secondary.get("official_url"):
                    primary_update["official_url"] = secondary["official_url"]

                if not already_merged:
                    # First-time merge: combine raw_descriptions and trigger
                    # re-annotation so the AI can produce a richer summary.
                    primary_desc = (primary.get("raw_description") or "").strip()
                    secondary_desc = (secondary.get("raw_description") or "").strip()

                    if secondary_desc and secondary_desc not in primary_desc:
                        combined = (
                            primary_desc
                            + f"\n\n---\n別来源補足 ({secondary['source_name']})\n{secondary_desc}"
                        )
                        primary_update["raw_description"] = combined

                    # Re-queue for annotation only on new merges
                    primary_update["annotation_status"] = "pending"

                # Apply updates
                try:
                    sb.table("events").update(primary_update).eq("id", primary["id"]).execute()
                    sb.table("events").update(
                        _deactivate_as_merged(
                            primary["id"],
                            f"merged into {primary['id']} via Pass 1 name similarity {sim:.3f}",
                            "merger_pass_1",
                        )
                    ).eq("id", secondary["id"]).execute()
                    merge_count += 1
                    handled_secondary_ids.add(secondary["id"])
                except Exception as exc:
                    logger.error(
                        "Merger: failed to merge %s ← %s: %s",
                        primary["source_id"],
                        secondary["source_id"],
                        exc,
                    )

    logger.info("Merger: Pass 1 done (%d pairs)", merge_count)

    # ------------------------------------------------------------------
    # Pass 2: News-report matching
    # News sources post article-style titles that don't match event names
    # by similarity.  Match by:
    #   (a) news.start_date ∈ [official.start_date, official.end_date]
    #   (b) location_name token overlap (≥1 common token of ≥2 chars)
    # News events are ALWAYS secondary; official events are ALWAYS primary.
    #
    # Guard: skip news events that already have a work_id — those are
    # annotated film/work events that Pass 1 already handles by name
    # similarity.  Using date+location alone for work-linked events causes
    # false positives when multiple different films screen at the same venue.
    # ------------------------------------------------------------------
    news_events = [
        ev for ev in events
        if ev["source_name"] in _NEWS_SOURCES
        and ev["id"] not in handled_secondary_ids
    ]
    official_events = [
        ev for ev in events
        if ev["source_name"] not in _NEWS_SOURCES
        and ev["id"] not in handled_secondary_ids
    ]

    for news_ev in news_events:
        best_match = None
        best_priority = 100

        for official_ev in official_events:
            if official_ev["id"] in handled_secondary_ids:
                continue

            # (a) Date range check — include LOOKBACK days before event start
            # to catch pre-event press releases
            if not _date_in_range(
                news_ev.get("start_date"),
                official_ev.get("start_date"),
                official_ev.get("end_date") or official_ev.get("start_date"),
                lookback_days=_PRESS_RELEASE_LOOKBACK_DAYS,
            ):
                continue

            # (b) Location overlap check
            if not _location_overlap(
                news_ev.get("location_name"),
                official_ev.get("location_name"),
            ):
                continue

            # (c) Work-linked guard: if news event has a work_id (annotated film),
            # require name similarity ≥ threshold to prevent false positives when
            # multiple different films screen at the same venue on overlapping dates.
            if news_ev.get("work_id"):
                if _similarity(
                    news_ev.get("name_ja") or "",
                    official_ev.get("name_ja") or "",
                ) < _SIMILARITY_THRESHOLD:
                    continue

            pri = SOURCE_PRIORITY.get(official_ev["source_name"], 99)
            if pri < best_priority:
                best_priority = pri
                best_match = official_ev

        if not best_match:
            continue

        primary, secondary = best_match, news_ev
        secondary_url = secondary["source_url"]
        existing_urls = primary.get("secondary_source_urls") or []
        already_merged = secondary_url in existing_urls

        logger.info(
            "%s  [%s] '%s'  ←  [%s] '%s'  (news-match)",
            "EXISTS" if already_merged else "MERGE ",
            primary["source_name"],
            (primary["name_ja"] or "")[:40],
            secondary["source_name"],
            (secondary["name_ja"] or "")[:40],
        )

        if dry_run:
            merge_count += 1
            handled_secondary_ids.add(secondary["id"])
            continue

        new_secondary_urls = list(dict.fromkeys(existing_urls + [secondary_url]))
        primary_update: dict = {"secondary_source_urls": new_secondary_urls}

        if not primary.get("official_url") and secondary.get("official_url"):
            primary_update["official_url"] = secondary["official_url"]

        if not already_merged:
            primary_desc = (primary.get("raw_description") or "").strip()
            secondary_desc = (secondary.get("raw_description") or "").strip()

            if secondary_desc and secondary_desc not in primary_desc:
                combined = (
                    primary_desc
                    + f"\n\n---\n別来源補足 ({secondary['source_name']})\n{secondary_desc}"
                )
                primary_update["raw_description"] = combined

            primary_update["annotation_status"] = "pending"

        try:
            sb.table("events").update(primary_update).eq("id", primary["id"]).execute()
            sb.table("events").update(
                _deactivate_as_merged(
                    primary["id"],
                    f"news article merged into {primary['id']} via Pass 2 date+location",
                    "merger_pass_2",
                )
            ).eq("id", secondary["id"]).execute()
            merge_count += 1
            handled_secondary_ids.add(secondary["id"])
        except Exception as exc:
            logger.error(
                "Merger: failed to merge %s ← %s: %s",
                primary["source_id"],
                secondary["source_id"],
                exc,
            )

    logger.info("Merger: %d cross-source duplicate pair(s) handled (Pass 1+2)", merge_count)

    # ------------------------------------------------------------------
    # Pass 3 — Orphaned sub-event cleanup
    # After Pass 1/2 deactivate parent events, their sub-events become
    # "orphaned" (is_active=True but parent is_active=False).
    # For each orphan, find the matching sub under the surviving primary
    # parent and merge them.  If no match exists, deactivate the orphan.
    # ------------------------------------------------------------------
    sub_res = (
        sb.table("events")
        .select(
            "id,source_name,source_id,source_url,official_url,name_ja,"
            "start_date,end_date,location_name,location_address,raw_description,"
            "secondary_source_urls,annotation_status,parent_event_id,work_id"
        )
        .eq("is_active", True)
        .not_.is_("parent_event_id", None)
        .execute()
    )
    all_subs = sub_res.data or []

    # Build parent info map
    parent_ids = list({s["parent_event_id"] for s in all_subs})
    parent_map: dict = {}
    for i in range(0, len(parent_ids), 100):
        batch = parent_ids[i:i + 100]
        pres = (
            sb.table("events")
            .select("id,is_active,source_url,secondary_source_urls")
            .in_("id", batch)
            .execute()
        )
        for p in pres.data or []:
            parent_map[p["id"]] = p

    orphaned: list[tuple] = []
    for sub in all_subs:
        if sub["id"] in handled_secondary_ids:
            continue
        # Skip events linked to a work entity — they are preserved as historical
        # records regardless of parent status (Archive Work-Link Bypass Guard)
        if sub.get("work_id"):
            continue
        parent = parent_map.get(sub["parent_event_id"])
        if parent and not parent["is_active"]:
            orphaned.append((sub, parent))

    logger.info("Merger: %d orphaned sub-event(s) found (Pass 3)", len(orphaned))
    pass3_count = 0

    for orphaned_sub, inactive_parent in orphaned:
        if orphaned_sub["id"] in handled_secondary_ids:
            continue

        inactive_url = inactive_parent.get("source_url") or ""

        # Find the primary parent: the active event that absorbed inactive_parent
        primary_parent_res = (
            sb.table("events")
            .select("id")
            .contains("secondary_source_urls", [inactive_url])
            .execute()
        ) if inactive_url else type("R", (), {"data": []})()

        primary_parent_id = (
            primary_parent_res.data[0]["id"] if primary_parent_res.data else None
        )

        if primary_parent_id:
            subs_under_primary = [
                s for s in all_subs
                if s["parent_event_id"] == primary_parent_id
                and s["id"] != orphaned_sub["id"]
                and s["id"] not in handled_secondary_ids
            ]
            matching_sub = next(
                (
                    c for c in subs_under_primary
                    if _similarity(orphaned_sub["name_ja"], c["name_ja"]) >= _SIMILARITY_THRESHOLD
                    and (orphaned_sub["start_date"] or "")[:10] == (c["start_date"] or "")[:10]
                ),
                None,
            )
        else:
            matching_sub = None

        if matching_sub:
            # Determine primary / secondary by source priority; richness tiebreaker
            pri_o = SOURCE_PRIORITY.get(orphaned_sub["source_name"], 99)
            pri_m = SOURCE_PRIORITY.get(matching_sub["source_name"], 99)
            if pri_o < pri_m:
                primary_sub, secondary_sub = orphaned_sub, matching_sub
            elif pri_m < pri_o:
                primary_sub, secondary_sub = matching_sub, orphaned_sub
            else:
                # Equal priority — richer data wins
                if _richness_score(orphaned_sub) >= _richness_score(matching_sub):
                    primary_sub, secondary_sub = orphaned_sub, matching_sub
                else:
                    primary_sub, secondary_sub = matching_sub, orphaned_sub

            secondary_url = secondary_sub["source_url"]
            existing_urls = primary_sub.get("secondary_source_urls") or []
            already_merged = secondary_url in existing_urls

            logger.info(
                "%s  [%s] '%s'  ←  [%s] '%s'  (orphan-sub)",
                "EXISTS" if already_merged else "MERGE ",
                primary_sub["source_name"],
                (primary_sub["name_ja"] or "")[:40],
                secondary_sub["source_name"],
                (secondary_sub["name_ja"] or "")[:40],
            )

            if dry_run:
                pass3_count += 1
                handled_secondary_ids.add(secondary_sub["id"])
                continue

            new_urls = list(dict.fromkeys(existing_urls + [secondary_url]))
            sub_update: dict = {"secondary_source_urls": new_urls}
            if not already_merged:
                sub_update["annotation_status"] = "pending"

            try:
                sb.table("events").update(sub_update).eq("id", primary_sub["id"]).execute()
                sb.table("events").update(
                    _deactivate_as_merged(
                        primary_sub["id"],
                        f"sub-event merged into {primary_sub['id']} via Pass 3 (orphan reattach)",
                        "merger_pass_3",
                    )
                ).eq("id", secondary_sub["id"]).execute()
                pass3_count += 1
                handled_secondary_ids.add(secondary_sub["id"])
            except Exception as exc:
                logger.error(
                    "Merger Pass 3: failed to merge %s ← %s: %s",
                    primary_sub["source_id"],
                    secondary_sub["source_id"],
                    exc,
                )
        else:
            # No matching sub under primary parent — deactivate the orphan
            logger.info(
                "ORPHAN  [%s] '%s' — no match, deactivating",
                orphaned_sub["source_name"],
                (orphaned_sub["name_ja"] or "")[:40],
            )
            if not dry_run:
                try:
                    sb.table("events").update(
                        _deactivate_payload(
                            "orphan sub-event with no surviving primary parent match",
                            "orphan_cleanup",
                        )
                    ).eq("id", orphaned_sub["id"]).execute()
                    pass3_count += 1
                    handled_secondary_ids.add(orphaned_sub["id"])
                except Exception as exc:
                    logger.error(
                        "Merger Pass 3: failed to deactivate orphan %s: %s",
                        orphaned_sub["source_id"],
                        exc,
                    )
            else:
                pass3_count += 1
                handled_secondary_ids.add(orphaned_sub["id"])

    logger.info("Merger: %d orphaned sub-event(s) handled (Pass 3)", pass3_count)

    # ------------------------------------------------------------------
    # Pass 4 — Grandchild event flattening
    # ------------------------------------------------------------------
    pass4_count = _flatten_grandchild_events(sb, dry_run=dry_run)

    total = pass0_count + merge_count + pass3_count + pass4_count
    return total


def _flatten_grandchild_events(sb: Any, dry_run: bool = False) -> int:
    """
    Pass 4: Detect and fix grandchild events (events whose parent is itself a sub-event).

    For each grandchild:
    - If a sibling with the same location_name + start_date[:10] exists under the root
      → deactivate the grandchild (it's a duplicate).
    - Otherwise → re-parent the grandchild directly under the root event.

    Returns the number of grandchild events processed.
    """
    # Fetch all active sub-events
    all_subs_res = (
        sb.table("events")
        .select("id,source_id,source_name,parent_event_id,name_ja,start_date,location_name")
        .not_.is_("parent_event_id", "null")
        .eq("is_active", True)
        .execute()
    )
    all_subs = all_subs_res.data or []

    if not all_subs:
        return 0

    # Batch-fetch all parent events to check their own parent_event_id
    parent_ids = list({s["parent_event_id"] for s in all_subs})
    if not parent_ids:
        return 0

    parents_res = (
        sb.table("events")
        .select("id,parent_event_id")
        .in_("id", parent_ids)
        .execute()
    )
    parent_map = {p["id"]: p for p in (parents_res.data or [])}

    # Grandchildren = sub-events whose parent is also a sub-event
    grandchildren = [
        s for s in all_subs
        if (parent_map.get(s["parent_event_id"]) or {}).get("parent_event_id") is not None
    ]

    if not grandchildren:
        logger.info("Merger Pass 4: no grandchild events found")
        return 0

    logger.info("Merger Pass 4: found %d grandchild event(s)", len(grandchildren))

    count = 0
    for gc in grandchildren:
        parent = parent_map[gc["parent_event_id"]]
        root_id = parent["parent_event_id"]

        # Fetch root's direct children to check for duplicates
        siblings_res = (
            sb.table("events")
            .select("id,location_name,start_date")
            .eq("parent_event_id", root_id)
            .execute()
        )
        siblings = siblings_res.data or []

        gc_loc = (gc.get("location_name") or "").strip()
        gc_date = (gc.get("start_date") or "")[:10]

        is_duplicate = any(
            s["id"] != gc["id"]
            and (s.get("location_name") or "").strip() == gc_loc
            and (s.get("start_date") or "")[:10] == gc_date
            for s in siblings
        )

        if dry_run:
            action = "would deactivate (dup)" if is_duplicate else "would re-parent to root"
            logger.info(
                "Pass 4 [dry-run]: %s grandchild %s (%s) → root %s",
                action,
                gc["id"][:8],
                (gc.get("name_ja") or "")[:40],
                root_id[:8],
            )
        else:
            try:
                if is_duplicate:
                    sb.table("events").update(
                        _deactivate_payload(
                            f"grandchild duplicate of sibling under root {root_id} (Pass 4 flatten)",
                            "merger_pass_3",
                        )
                    ).eq("id", gc["id"]).execute()
                    logger.info(
                        "Pass 4: deactivated duplicate grandchild %s (%s)",
                        gc["id"][:8],
                        (gc.get("name_ja") or "")[:40],
                    )
                else:
                    sb.table("events").update({"parent_event_id": root_id}).eq("id", gc["id"]).execute()
                    logger.info(
                        "Pass 4: re-parented grandchild %s to root %s",
                        gc["id"][:8],
                        root_id[:8],
                    )
            except Exception as exc:
                logger.error("Pass 4: failed to process grandchild %s: %s", gc["id"][:8], exc)
        count += 1

    logger.info("Merger Pass 4: %d grandchild event(s) processed", count)
    return count


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    parser = argparse.ArgumentParser(description="Cross-source event merger")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect duplicates and log without writing to DB",
    )
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

    count = run_merger(dry_run=args.dry_run)
    action = "would be merged" if args.dry_run else "merged"
    print(f"Done: {count} pair(s)/orphan(s) {action} (Pass 0+1+2+3).")
