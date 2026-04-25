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
    "peatix": 7,
    "connpass": 8,
    "doorkeeper": 9,
    "iwafu": 10,
    "arukikata": 11,
    "ide_jetro": 12,
}

# Minimum name similarity to consider two events duplicates.
_SIMILARITY_THRESHOLD = 0.85


def _normalize(name: str) -> str:
    """Strip all whitespace and lowercase for similarity comparison."""
    return re.sub(r"[\s\u3000\u00a0]+", "", name).lower()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def run_merger(dry_run: bool = False) -> int:
    """
    Detect and merge cross-source duplicate events in the DB.

    Returns the number of duplicate pairs handled (merged or already-merged).
    """
    from database import _get_client

    sb = _get_client()

    # Fetch all active, non-sub events that have a start_date and name_ja.
    # Sub-events (source_id contains '_sub') are excluded — they are child
    # events created by the annotator and should not be merged independently.
    res = (
        sb.table("events")
        .select(
            "id,source_name,source_id,source_url,name_ja,start_date,"
            "raw_description,secondary_source_urls,annotation_status"
        )
        .eq("is_active", True)
        .not_.is_("start_date", None)
        .not_.is_("name_ja", None)
        .execute()
    )
    events = [
        ev
        for ev in (res.data or [])
        if "_sub" not in (ev.get("source_id") or "")
    ]
    logger.info("Merger: loaded %d active non-sub events", len(events))

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

                # Determine primary / secondary by source priority.
                # Lower number = higher authority.
                pri_a = SOURCE_PRIORITY.get(ev_a["source_name"], 99)
                pri_b = SOURCE_PRIORITY.get(ev_b["source_name"], 99)
                if pri_a <= pri_b:
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
                    sb.table("events").update({"is_active": False}).eq("id", secondary["id"]).execute()
                    merge_count += 1
                    handled_secondary_ids.add(secondary["id"])
                except Exception as exc:
                    logger.error(
                        "Merger: failed to merge %s ← %s: %s",
                        primary["source_id"],
                        secondary["source_id"],
                        exc,
                    )

    logger.info("Merger: %d cross-source duplicate pair(s) handled", merge_count)
    return merge_count


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
    print(f"Done: {count} cross-source pair(s) {action}.")
