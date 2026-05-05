#!/usr/bin/env python3
"""
backfill_merged_into_event_id.py
=================================
One-time backfill: for each primary event with secondary_source_urls,
find events whose source_url matches any of those secondary URLs and
set their merged_into_event_id to the primary event's id.

Run AFTER migration 049_merged_into_event_id.sql is applied.

Usage:
    cd scraper/
    python backfill_merged_into_event_id.py [--dry-run]
"""
import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def main(dry_run: bool) -> None:
    from dotenv import load_dotenv
    load_dotenv(".env")
    from database import _get_client

    sb = _get_client()

    # Fetch all primary events that have secondary_source_urls
    logger.info("Fetching primary events with secondary_source_urls...")
    primaries_res = (
        sb.table("events")
        .select("id,name_ja,secondary_source_urls")
        .not_.is_("secondary_source_urls", "null")
        .execute()
    )
    primaries = [
        p for p in (primaries_res.data or [])
        if p.get("secondary_source_urls")
    ]
    logger.info("Found %d primary events with secondary URLs", len(primaries))

    # Build a flat map: secondary_url -> primary_id
    url_to_primary: dict[str, str] = {}
    for p in primaries:
        for url in p["secondary_source_urls"]:
            url_to_primary[url] = p["id"]

    logger.info("Total secondary URLs to match: %d", len(url_to_primary))

    # Find events whose source_url matches any secondary URL
    # Fetch in batches to avoid URL query limits
    all_urls = list(url_to_primary.keys())
    matched: list[dict] = []
    batch_size = 50
    for i in range(0, len(all_urls), batch_size):
        batch = all_urls[i:i + batch_size]
        res = (
            sb.table("events")
            .select("id,source_url,name_ja,merged_into_event_id")
            .in_("source_url", batch)
            .execute()
        )
        matched.extend(res.data or [])

    logger.info("Found %d events matching a secondary URL", len(matched))

    updated = 0
    skipped = 0
    for ev in matched:
        primary_id = url_to_primary.get(ev["source_url"])
        if not primary_id:
            continue
        if ev.get("merged_into_event_id") == primary_id:
            skipped += 1
            continue
        logger.info(
            "%s [%s] '%s' → primary %s",
            "DRY-RUN" if dry_run else "UPDATE",
            ev["id"][:8],
            (ev.get("name_ja") or "")[:40],
            primary_id[:8],
        )
        if not dry_run:
            sb.table("events").update(
                {"merged_into_event_id": primary_id}
            ).eq("id", ev["id"]).execute()
        updated += 1

    logger.info(
        "Backfill complete: %d updated, %d already correct, %d dry-run=%s",
        updated, skipped, len(matched), dry_run
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill merged_into_event_id")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
