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
from datetime import date as _date
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
    "user_submission": 99,  # UGC has the lowest priority (absorbed by official scrapers if they collide)
}

# Minimum name similarity to consider two events duplicates.
_SIMILARITY_THRESHOLD = 0.85

# Sources that publish news/article titles rather than event names.
# They are matched via date-range + location-overlap (Pass 2), never by
# name similarity (Pass 1).
_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss", "walkerplus", "user_submission"})

# Sources enabled for within-source aggregator dedup (Pass 1.5).
_WITHIN_SOURCE_DEDUP_SOURCES = frozenset({"iwafu"})

# How many days BEFORE an official event's start_date a news article may be
# published and still be considered a match (pre-event press releases).
_PRESS_RELEASE_LOOKBACK_DAYS = 90


def _extract_isbn(source_id: str | None, source_url: str | None) -> str | None:
    """Extract standard 13-digit or 10-digit ISBN."""
    for text in [source_id, source_url]:
        if not text:
            continue
        # Look for 13-digit ISBN (978... or 979...)
        m13 = re.search(r"(97[89]\d{10})", text)
        if m13:
            return m13.group(1)
        # Look for 10-digit ISBN
        m10 = re.search(r"\b(\d{10})\b", text)
        if m10:
            return m10.group(1)
    return None


def _normalize(name: str) -> str:
    """Strip all whitespace and lowercase for similarity comparison."""
    # Normalize registered trademark symbol variants (e.g. iwafu uses ®, official uses (R))
    name = name.replace("®", "(r)").replace("Ⓡ", "(r)")
    # Unify dash variants so katakana prolonged sound mark (ー), full-width hyphen (－),
    # em dash (—), horizontal bar (―) and ASCII hyphen-minus all compare as equal.
    # Without this, "台南ランタン祭ー" (walkerplus, ー) ≠ "台南ランタン祭－" (prtimes, －).
    name = re.sub(r"[ー－—―]", "-", name)
    # Strip trailing 【organizer annotation】 e.g. "上映会【ＮＰＯ松本シネマセレクト】"
    # MUST run before the wrapping-bracket strip below (which would eat the trailing 】 first).
    name = re.sub(r"【[^】]*】\s*$", "", name)
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

    pass_id: 'merger_pass_0' | 'merger_pass_1' | 'merger_pass_1_5' | 'merger_pass_2'
             | 'merger_pass_3' | 'merger_pass_4' | 'merger_pass_5'
             | 'orphan_cleanup' | 'admin_manual'
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


# Same-work eligibility window: two events for the same work_id (or the same
# gnews film) count as the same run only when their start dates fall within this
# many days of each other.
_SAME_WORK_WINDOW_DAYS = 14

# Works metadata copied from a merged-away secondary onto the surviving primary
# (only when the primary field is empty). Order defines the reported sync order.
_WORKS_SYNC_FIELDS = [
    "work_id",
    "director",
    "release_year",
    "cast_summary",
    "description",
    "performer",
]


def same_work_eligible(
    date_a: str | None,
    date_b: str | None,
    loc_a: str | None,
    loc_b: str | None,
    *,
    require_location_overlap: bool,
    require_both_dates: bool = False,
    window_days: int = _SAME_WORK_WINDOW_DAYS,
) -> bool:
    """Shared same-work date/location eligibility predicate.

    Single source of truth for merger Pass 5 (merger mode) and Auto-QA
    same-work detection / reconciliation (detection mode):

    - Merger mode (``require_location_overlap=True``) requires the two venues to
      overlap and allows a one-sided/absent date (leaning on the location
      guard), mirroring the historical Pass 5 window+location check.
    - Detection mode (``require_location_overlap=False``,
      ``require_both_dates=True``) ignores location but demands both dates.

    Date rule: when both dates are present they must parse and fall within
    ``window_days`` of each other; an unparseable pair is never eligible
    (mirroring the historical ``continue``). When a date is missing,
    ``require_both_dates`` decides eligibility.
    """
    if date_a and date_b:
        try:
            diff = abs(
                (_date.fromisoformat(date_a[:10]) - _date.fromisoformat(date_b[:10])).days
            )
        except (ValueError, TypeError):
            return False
        if diff > window_days:
            return False
    elif require_both_dates:
        return False
    if require_location_overlap:
        return _location_overlap(loc_a, loc_b)
    return True


def apply_targeted_merge(
    sb: Any,
    primary: dict,
    secondary: dict,
    *,
    reason: str,
    pass_id: str,
    primary_update: dict | None = None,
    repair_children: bool = False,
    sync_works: bool = False,
    dry_run: bool = False,
) -> dict:
    """Deactivate ``secondary`` as merged into ``primary`` with full audit fields.

    The single targeted-merge primitive shared by every merger pass and future
    manifest tooling — never fork a second merge implementation.

    Guards (raise ``ValueError``): a falsy primary/secondary id, a self-merge, an
    inactive primary, or a cycle (primary already merged into the secondary).

    On apply (skipped entirely when ``dry_run``): optionally sync missing works
    metadata from the secondary, apply the caller's ``primary_update``,
    deactivate the secondary via :func:`_deactivate_as_merged`, and optionally
    re-parent the secondary's children onto the primary. Report status is never
    written here.

    Returns ``{"dry_run", "deactivated", "repaired_children", "synced_fields"}``.
    """
    primary_id = primary.get("id")
    secondary_id = secondary.get("id")
    if not primary_id:
        raise ValueError("apply_targeted_merge: primary id is required")
    if not secondary_id:
        raise ValueError("apply_targeted_merge: secondary id is required")
    if primary_id == secondary_id:
        raise ValueError(f"apply_targeted_merge: self-merge rejected ({primary_id})")
    if primary.get("is_active") is False:
        raise ValueError(
            f"apply_targeted_merge: inactive primary rejected ({primary_id})"
        )
    if primary.get("merged_into_event_id") == secondary_id:
        raise ValueError(
            f"apply_targeted_merge: cycle rejected ({primary_id} <-> {secondary_id})"
        )

    result: dict = {
        "dry_run": dry_run,
        "deactivated": False,
        "repaired_children": [],
        "synced_fields": [],
    }
    if dry_run:
        return result

    # 1. Sync works metadata from the secondary into any empty primary field.
    if sync_works:
        sync_update: dict = {}
        synced: list[str] = []
        for field in _WORKS_SYNC_FIELDS:
            if not primary.get(field) and secondary.get(field):
                sync_update[field] = secondary[field]
                synced.append(field)
        if sync_update:
            sb.table("events").update(sync_update).eq("id", primary_id).execute()
            for k, v in sync_update.items():
                primary[k] = v
        result["synced_fields"] = synced

    # 2. Apply the caller's primary update.
    if primary_update:
        sb.table("events").update(primary_update).eq("id", primary_id).execute()

    # 3. Deactivate the secondary as merged into the primary.
    sb.table("events").update(
        _deactivate_as_merged(primary_id, reason, pass_id)
    ).eq("id", secondary_id).execute()
    result["deactivated"] = True

    # 4. Re-parent the secondary's children onto the primary.
    if repair_children:
        children = (
            sb.table("events")
            .select("id")
            .eq("parent_event_id", secondary_id)
            .execute()
            .data
        ) or []
        repaired: list[str] = []
        for child in children:
            cid = child.get("id")
            if not cid:
                continue
            sb.table("events").update(
                {"parent_event_id": primary_id}
            ).eq("id", cid).execute()
            repaired.append(cid)
        result["repaired_children"] = repaired

    return result


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


# ---------------------------------------------------------------------------
# Pagination helpers
# PostgREST silently caps a single response at 1000 rows, so an un-paginated
# .execute() drops every event past the first 1000.  Each active-event scan and
# id-batched lookup in run_merger routes through these helpers.  Mirrors the G2
# backfill_location_prefectures.fetch_all_rows contract; merger stays
# self-contained (no cross-module import).
# ---------------------------------------------------------------------------
def _fetch_all_rows(
    sb: Any,
    table: str,
    columns: str,
    *,
    apply_filters=None,
    order_col: str = "id",
    page_size: int = 1000,
    label: str = "",
) -> list[dict]:
    """Return every row of a filtered query, paginating past the 1000-row cap
    via .range() windows.  Filters are applied to both the exact-count head
    query and every page."""
    tag = label or table
    count_q = sb.table(table).select(order_col, count="exact", head=True)
    if apply_filters:
        count_q = apply_filters(count_q)
    exact = count_q.execute().count
    logger.info("  [%s] exact count = %s", tag, exact)

    rows: list[dict] = []
    start = 0
    while True:
        page_q = sb.table(table).select(columns)
        if apply_filters:
            page_q = apply_filters(page_q)
        page = (
            page_q.order(order_col)
            .range(start, start + page_size - 1)
            .execute()
            .data
        ) or []
        rows.extend(page)
        logger.info(
            "  [%s] page @%d: +%d (accumulated %d)", tag, start, len(page), len(rows)
        )
        if len(page) < page_size:
            break
        start += page_size

    if exact is not None and len(rows) != exact:
        logger.warning(
            "  [%s] accumulated %d != exact count %d", tag, len(rows), exact
        )
    return rows


def _fetch_by_ids(
    sb: Any,
    table: str,
    ids,
    columns: str,
    *,
    chunk_size: int = 200,
    label: str = "",
) -> list[dict]:
    """Return rows for a list of ids, de-duplicated preserving first-seen order
    and chunked so a large .in_() lookup never caps at 1000."""
    tag = label or table
    unique_ids = list(dict.fromkeys(i for i in ids if i is not None))
    rows: list[dict] = []
    if not unique_ids:
        return rows
    for i in range(0, len(unique_ids), chunk_size):
        batch = unique_ids[i : i + chunk_size]
        page = sb.table(table).select(columns).in_("id", batch).execute().data or []
        rows.extend(page)
        logger.info(
            "  [%s] ids @%d: +%d (accumulated %d)", tag, i, len(page), len(rows)
        )
    return rows


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
    gnews_events = _fetch_all_rows(
        sb,
        "events",
        "id,source_name,source_id,source_url,name_ja,start_date,"
        "location_name,raw_description,secondary_source_urls,annotation_status",
        apply_filters=lambda q: (
            q.eq("is_active", True)
            .eq("source_name", "google_news_rss")
            .not_.is_("name_ja", None)
        ),
        label="pass0_gnews",
    )
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
                apply_targeted_merge(
                    sb, primary, secondary,
                    primary_update=upd,
                    reason=f"merged into {primary['id']} (gnews within-source dedup)",
                    pass_id="merger_pass_0",
                )
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

    # Fetch all active events that have a name_ja.
    # Note: gnews sub-events (source_id contains '_sub') ARE included here so
    # Pass 1/2 can match them against official sources by name+location/date.
    # Same-source within-article dedup is handled by Pass 0.
    # is_active is filtered with .neq(False) rather than .eq(True): identical in
    # Postgres (is_active is NOT NULL) but keeps the DB-side filter while the
    # scan paginates, and stays compatible with the pagination regression fake
    # (which treats a missing is_active key as active).
    events = _fetch_all_rows(
        sb,
        "events",
        "id,source_name,source_id,source_url,official_url,name_ja,start_date,end_date,"
        "location_name,location_address,raw_description,secondary_source_urls,"
        "annotation_status,work_id,category,parent_event_id,location_prefectures,"
        "image_url,performer,price_info,price_amount,event_form",
        apply_filters=lambda q: q.neq("is_active", False).not_.is_("name_ja", None),
        label="pass1_2_events",
    )
    logger.info("Merger: loaded %d active events for Pass 1/2", len(events))

    # Group by start_date (YYYY-MM-DD prefix)
    date_groups: dict[str, list] = defaultdict(list)
    for ev in events:
        start_date = ev.get("start_date")
        if start_date:
            date_key = start_date[:10]
            date_groups[date_key].append(ev)

    # Track secondary IDs already handled in this run to avoid double-processing
    handled_secondary_ids: set[str] = set()
    merge_count = 0

    # ------------------------------------------------------------------
    # Pass 1.1 — ISBN-based books cross-source dedup
    # For events in 'books_media' category, extract ISBN.
    # If standard ISBN matches, merge without date restrictions (up to 30 days gap or None).
    # Higher authority (e.g., ndl_opensearch) wins as Primary.
    # Propagate rich metadata from secondary to primary.
    # ------------------------------------------------------------------
    pass1_1_count = 0
    
    # Filter out books from events (matching category books_media, event_form publication, or source_name hanmoto)
    book_events = [
        ev for ev in events
        if "books_media" in (ev.get("category") or [])
        or "publication" in (ev.get("event_form") or [])
        or ev.get("source_name") == "hanmoto"
    ]
    
    # Sub priority for books authority (lower number = higher)
    # ndl_opensearch has highest priority. hanmoto is second, others next.
    BOOK_PRIORITY = {
        "ndl_opensearch": 1,
        "hanmoto": 2,
        "kawade_rss": 3,
        "eslite_spectrum": 4,
    }
    
    isbn_groups: dict[str, list[dict]] = defaultdict(list)
    for ev in book_events:
        isbn = _extract_isbn(ev.get("source_id"), ev.get("source_url"))
        if isbn:
            isbn_groups[isbn].append(ev)

    for isbn, group in sorted(isbn_groups.items()):
        if len(group) < 2:
            continue
            
        # Process pairs within this ISBN group
        for i in range(len(group)):
            ev_a = group[i]
            if ev_a["id"] in handled_secondary_ids:
                continue
                
            for j in range(i + 1, len(group)):
                ev_b = group[j]
                if ev_b["id"] in handled_secondary_ids:
                    continue
                
                # Check date compatibility: JPRO 12-31 is placeholder and can be ignored
                date_a_str = ev_a.get("start_date")
                date_b_str = ev_b.get("start_date")
                
                date_compatible = False
                if date_a_str is None or date_b_str is None:
                    date_compatible = True
                else:
                    try:
                        from datetime import datetime
                        # Parse with fallback to isolate YYYY-MM-DD
                        da_dt = datetime.fromisoformat(date_a_str.replace("Z", "+00:00"))
                        db_dt = datetime.fromisoformat(date_b_str.replace("Z", "+00:00"))
                        
                        # If a date is Dec 31, treat it as placeholder (None)
                        if (da_dt.month == 12 and da_dt.day == 31) or (db_dt.month == 12 and db_dt.day == 31):
                            date_compatible = True
                        else:
                            if abs((da_dt.date() - db_dt.date()).days) <= 30:
                                date_compatible = True
                    except Exception:
                        date_compatible = True
                
                if not date_compatible:
                    continue

                # Determine primary / secondary
                pri_a = BOOK_PRIORITY.get(ev_a["source_name"], 99)
                pri_b = BOOK_PRIORITY.get(ev_b["source_name"], 99)
                
                if pri_a < pri_b:
                    primary, secondary = ev_a, ev_b
                elif pri_b < pri_a:
                    primary, secondary = ev_b, ev_a
                else:
                    if _richness_score(ev_a) >= _richness_score(ev_b):
                        primary, secondary = ev_a, ev_b
                    else:
                        primary, secondary = ev_b, ev_a

                secondary_url = secondary["source_url"]
                existing_urls = primary.get("secondary_source_urls") or []
                already_merged = secondary_url in existing_urls

                logger.info(
                    "%s  [%s] '%s'  ←  [%s] '%s'  (ISBN Pass 1.1: %s)",
                    "EXISTS" if already_merged else "MERGE ",
                    primary["source_name"],
                    (primary["name_ja"] or "")[:40],
                    secondary["source_name"],
                    (secondary["name_ja"] or "")[:40],
                    isbn,
                )

                if dry_run:
                    pass1_1_count += 1
                    handled_secondary_ids.add(secondary["id"])
                    continue

                new_secondary_urls = list(dict.fromkeys(existing_urls + [secondary_url]))
                primary_update: dict = {"secondary_source_urls": new_secondary_urls}

                if not primary.get("official_url") and secondary.get("official_url"):
                    primary_update["official_url"] = secondary["official_url"]

                # Metadata propagation:
                # If primary lacks any key attribute, propagate from secondary.
                # Treat year-end (12-31) start_date as missing as well!
                for field in ["performer", "price_info", "price_amount", "image_url", "start_date", "end_date"]:
                    val_p = primary.get(field)
                    val_s = secondary.get(field)
                    
                    is_placeholder_a = False
                    if field in ("start_date", "end_date") and val_p:
                        try:
                            from datetime import datetime
                            dt_p = datetime.fromisoformat(val_p.replace("Z", "+00:00"))
                            is_placeholder_a = dt_p.month == 12 and dt_p.day == 31
                        except Exception:
                            is_placeholder_a = False
                    
                    if not val_p or is_placeholder_a:
                        if val_s:
                            primary_update[field] = val_s

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
                    apply_targeted_merge(
                        sb, primary, secondary,
                        primary_update=primary_update,
                        reason=f"merged into {primary['id']} via Pass 1.1 ISBN matching {isbn}",
                        pass_id="merger_pass_1_1",
                    )
                    pass1_1_count += 1
                    handled_secondary_ids.add(secondary["id"])
                    
                    # Store updated values locally
                    for k, v in primary_update.items():
                        primary[k] = v
                except Exception as exc:
                    logger.error(
                        "Merger Pass 1.1: failed to merge %s ← %s: %s",
                        primary["source_id"],
                        secondary["source_id"],
                        exc,
                    )

    logger.info("Merger: Pass 1.1 done (%d pairs)", pass1_1_count)

    # ------------------------------------------------------------------
    # Pass 1.5 — Within-source aggregator dedup (allowlist)
    # Some aggregators publish the same event under different page IDs.
    # This pass merges duplicates only within selected sources (e.g. iwafu).
    # ------------------------------------------------------------------
    pass1_5_count = 0

    def _annotation_rank(status: str | None) -> int:
        # Higher rank = preferred as primary
        order = {
            "reviewed": 3,
            "annotated": 2,
            "pending": 1,
        }
        return order.get((status or "").strip().lower(), 0)

    def _source_id_trailing_number(source_id: str | None) -> int:
        if not source_id:
            return -1
        m = re.search(r"(\d+)$", source_id)
        return int(m.group(1)) if m else -1

    def _prefecture_set(ev: dict) -> set[str]:
        vals = ev.get("location_prefectures")
        if not vals:
            return set()
        if isinstance(vals, list):
            return {str(v).strip() for v in vals if str(v).strip()}
        if isinstance(vals, str):
            return {v.strip() for v in vals.split(",") if v.strip()}
        return set()

    source_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in events:
        src = ev.get("source_name")
        if src in _WITHIN_SOURCE_DEDUP_SOURCES:
            source_groups[str(src)].append(ev)

    for source_name, group in sorted(source_groups.items()):
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

                source_id_a = ev_a.get("source_id") or ""
                source_id_b = ev_b.get("source_id") or ""

                # Skip sub-events and parent-linked rows.
                if "_sub" in source_id_a or "_sub" in source_id_b:
                    continue
                if ev_a.get("parent_event_id") is not None or ev_b.get("parent_event_id") is not None:
                    continue

                start_a = (ev_a.get("start_date") or "")[:10]
                start_b = (ev_b.get("start_date") or "")[:10]
                if start_a != start_b:
                    continue

                end_a = (ev_a.get("end_date") or "")[:10]
                end_b = (ev_b.get("end_date") or "")[:10]
                if bool(end_a) != bool(end_b):
                    continue
                if end_a and end_b and end_a != end_b:
                    continue

                wa = ev_a.get("work_id")
                wb = ev_b.get("work_id")
                if wa and wb and wa != wb:
                    continue

                pref_a = _prefecture_set(ev_a)
                pref_b = _prefecture_set(ev_b)
                if pref_a and pref_b and not (pref_a & pref_b):
                    continue

                name_a = ev_a.get("name_ja") or ""
                name_b = ev_b.get("name_ja") or ""
                norm_a = _normalize(name_a)
                norm_b = _normalize(name_b)
                sim = _similarity(name_a, name_b)

                short_norm, long_norm = sorted([norm_a, norm_b], key=len)
                substring_match = len(short_norm) >= 6 and short_norm in long_norm
                if sim < _SIMILARITY_THRESHOLD and not substring_match:
                    continue

                # Primary selection: richer first; then annotation status;
                # then larger source_id trailing number.
                score_a = _richness_score(ev_a)
                score_b = _richness_score(ev_b)
                if score_a > score_b:
                    primary, secondary = ev_a, ev_b
                elif score_b > score_a:
                    primary, secondary = ev_b, ev_a
                else:
                    rank_a = _annotation_rank(ev_a.get("annotation_status"))
                    rank_b = _annotation_rank(ev_b.get("annotation_status"))
                    if rank_a > rank_b:
                        primary, secondary = ev_a, ev_b
                    elif rank_b > rank_a:
                        primary, secondary = ev_b, ev_a
                    else:
                        id_num_a = _source_id_trailing_number(source_id_a)
                        id_num_b = _source_id_trailing_number(source_id_b)
                        if id_num_a >= id_num_b:
                            primary, secondary = ev_a, ev_b
                        else:
                            primary, secondary = ev_b, ev_a

                secondary_url = secondary["source_url"]
                existing_urls = primary.get("secondary_source_urls") or []
                already_merged = secondary_url in existing_urls

                logger.info(
                    "%s  [%s] '%s'  ←  [%s] '%s'  (within-source sim=%.2f substr=%s)",
                    "EXISTS" if already_merged else "MERGE ",
                    primary["source_name"],
                    (primary["name_ja"] or "")[:40],
                    secondary["source_name"],
                    (secondary["name_ja"] or "")[:40],
                    sim,
                    substring_match,
                )

                if dry_run:
                    pass1_5_count += 1
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
                        primary_update["raw_description"] = (
                            primary_desc
                            + f"\n\n---\n別来源補足 ({secondary['source_name']})\n{secondary_desc}"
                        )

                    # Keep reviewed as reviewed after merge.
                    if primary.get("annotation_status") != "reviewed":
                        primary_update["annotation_status"] = "pending"

                try:
                    apply_targeted_merge(
                        sb, primary, secondary,
                        primary_update=primary_update,
                        reason=f"merged into {primary['id']} via Pass 1.5 within-source dedup",
                        pass_id="merger_pass_1_5",
                    )
                    pass1_5_count += 1
                    handled_secondary_ids.add(secondary["id"])
                except Exception as exc:
                    logger.error(
                        "Merger Pass 1.5: failed to merge %s ← %s: %s",
                        primary["source_id"],
                        secondary["source_id"],
                        exc,
                    )

    logger.info("Merger: Pass 1.5 done (%d pairs)", pass1_5_count)

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
    all_subs = _fetch_all_rows(
        sb,
        "events",
        "id,source_name,source_id,source_url,official_url,name_ja,"
        "start_date,end_date,location_name,location_address,raw_description,"
        "secondary_source_urls,annotation_status,parent_event_id,work_id",
        apply_filters=lambda q: (
            q.eq("is_active", True).not_.is_("parent_event_id", None)
        ),
        label="pass3_orphan_subs",
    )

    # Build parent info map (chunked .in_() so a large id list never caps at 1000)
    parent_map: dict = {}
    for p in _fetch_by_ids(
        sb,
        "events",
        [s["parent_event_id"] for s in all_subs],
        "id,is_active,source_url,secondary_source_urls",
        label="pass3_parents",
    ):
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
    # Pass 5 — Same-work_id news-vs-news dedup
    # When two news-source events share the same work_id + overlapping
    # date (≤14 days) + overlapping location, they cover the same
    # screening from different articles.  Merge the lower-quality one
    # into the higher-quality one.
    #
    # This handles cases where name titles diverge too much for Pass 1
    # (name similarity << 0.85) and both events are in _NEWS_SOURCES
    # (so Pass 2's news→official loop never sees them together).
    # ------------------------------------------------------------------
    pass5_count = 0
    work_news_events = [
        ev for ev in events
        if ev["source_name"] in _NEWS_SOURCES
        and ev.get("work_id")
        and ev["id"] not in handled_secondary_ids
    ]

    # Group by work_id
    work_groups: dict[str, list] = defaultdict(list)
    for ev in work_news_events:
        work_groups[str(ev["work_id"])].append(ev)

    for work_id_key, group in work_groups.items():
        if len(group) < 2:
            continue
        for i, ev_a in enumerate(group):
            for j in range(i + 1, len(group)):
                ev_b = group[j]
                if ev_a["id"] in handled_secondary_ids or ev_b["id"] in handled_secondary_ids:
                    continue

                # Merger-mode same-work guard: start dates ≤ 14 days apart (a
                # one-sided/absent date is tolerated) AND overlapping venue
                # (prevents merging the same film at different cities).
                if not same_work_eligible(
                    ev_a.get("start_date"), ev_b.get("start_date"),
                    ev_a.get("location_name"), ev_b.get("location_name"),
                    require_location_overlap=True,
                ):
                    continue

                # Quality score: prefer has_date > has_location > longer description
                def _gnews_q(ev: dict) -> tuple:
                    has_date = 0 if ev.get("start_date") else 1
                    no_loc = 0 if ev.get("location_name") else 1
                    desc_len = -(len(ev.get("raw_description") or ""))
                    return (has_date, no_loc, desc_len)

                if _gnews_q(ev_a) <= _gnews_q(ev_b):
                    primary, secondary = ev_a, ev_b
                else:
                    primary, secondary = ev_b, ev_a

                secondary_url = secondary["source_url"]
                existing_urls = primary.get("secondary_source_urls") or []
                already_merged = secondary_url in existing_urls

                logger.info(
                    "%s  [gnews work=%s] '%s'  ←  [gnews] '%s'  (same-work Pass 5)",
                    "EXISTS" if already_merged else "MERGE ",
                    work_id_key[:8],
                    (primary["name_ja"] or "")[:40],
                    (secondary["name_ja"] or "")[:40],
                )

                if dry_run:
                    pass5_count += 1
                    handled_secondary_ids.add(secondary["id"])
                    continue

                new_urls = list(dict.fromkeys(existing_urls + [secondary_url]))
                upd5: dict = {"secondary_source_urls": new_urls}
                if not already_merged:
                    primary_desc = (primary.get("raw_description") or "").strip()
                    secondary_desc = (secondary.get("raw_description") or "").strip()
                    if secondary_desc and secondary_desc not in primary_desc:
                        upd5["raw_description"] = (
                            primary_desc
                            + f"\n\n---\n別来源補足 (gnews)\n{secondary_desc}"
                        )
                    upd5["annotation_status"] = "pending"

                try:
                    sb.table("events").update(upd5).eq("id", primary["id"]).execute()
                    sb.table("events").update(
                        _deactivate_as_merged(
                            primary["id"],
                            f"same-work_id gnews duplicate merged into {primary['id']} (Pass 5)",
                            "merger_pass_5",
                        )
                    ).eq("id", secondary["id"]).execute()
                    pass5_count += 1
                    handled_secondary_ids.add(secondary["id"])
                except Exception as exc:
                    logger.error(
                        "Merger Pass 5: failed to merge %s ← %s: %s",
                        primary.get("source_id"),
                        secondary.get("source_id"),
                        exc,
                    )

    logger.info("Merger Pass 5: %d same-work_id news-vs-news pair(s) handled", pass5_count)

    # ------------------------------------------------------------------
    # Pass 4 — Grandchild event flattening
    # ------------------------------------------------------------------
    pass4_count = _flatten_grandchild_events(sb, dry_run=dry_run)

    total = pass0_count + pass1_5_count + merge_count + pass3_count + pass4_count + pass5_count
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
    all_subs = _fetch_all_rows(
        sb,
        "events",
        "id,source_id,source_name,parent_event_id,name_ja,start_date,location_name",
        apply_filters=lambda q: (
            q.not_.is_("parent_event_id", "null").eq("is_active", True)
        ),
        label="pass4_subs",
    )

    if not all_subs:
        return 0

    # Batch-fetch all parent events (chunked .in_() so it never caps at 1000)
    parent_map = {
        p["id"]: p
        for p in _fetch_by_ids(
            sb,
            "events",
            [s["parent_event_id"] for s in all_subs],
            "id,parent_event_id",
            label="pass4_parents",
        )
    }
    if not parent_map:
        return 0

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
        siblings = _fetch_all_rows(
            sb,
            "events",
            "id,location_name,start_date",
            apply_filters=lambda q: q.eq("parent_event_id", root_id),
            label="pass4_root_siblings",
        )

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
                            "merger_pass_4",
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
    print(f"Done: {count} pair(s)/orphan(s) {action} (Pass 0+1+1.5+2+3+4+5).")
