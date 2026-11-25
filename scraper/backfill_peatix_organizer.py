"""Backfill organizer for existing Peatix events whose organizer is empty.

The daily scraper skips events that are already in the DB, and its Peatix
crawl only sees current search results, so past events never get a fixed
organizer. This script opens each event's own source_url and reads the
Peatix group name with the same extractor as sources/peatix.py.

Dry-run by default: it prints "event link -> organizer" and writes nothing.
Pass --live to write. Writes only organizer, only where organizer IS NULL,
and never for an event whose organizer is locked in field_corrections.

    cd scraper && python backfill_peatix_organizer.py            # dry-run
    cd scraper && python backfill_peatix_organizer.py --live
    cd scraper && python backfill_peatix_organizer.py --event-ids <uuid> <uuid>

Replaces the former _oneoff_fix_peatix_organizer.py (issue #603, #604).
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from typing import Any, Iterable

sys.path.insert(0, os.path.dirname(__file__))

logger = logging.getLogger(__name__)

EVENT_URL = "https://tokyotaiwanradar.com/ja/events/{id}"
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def parse_event_ids(values: Iterable[str] | None) -> list[str]:
    """Split comma/space separated IDs and reject anything that is not a UUID."""
    ids: list[str] = []
    for value in values or []:
        for part in re.split(r"[\s,]+", value.strip()):
            if not part:
                continue
            if not _UUID_RE.match(part.lower()):
                raise ValueError(f"not an event UUID: {part!r}")
            ids.append(part.lower())
    return ids


def select_targets(
    rows: list[dict[str, Any]],
    locked_event_ids: set[str],
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], str]]]:
    """Split candidate rows into (targets, skipped-with-reason)."""
    targets: list[dict[str, Any]] = []
    skipped: list[tuple[dict[str, Any], str]] = []
    for row in rows:
        if row.get("organizer"):
            skipped.append((row, "organizer already set"))
        elif row["id"] in locked_event_ids:
            skipped.append((row, "organizer locked in field_corrections"))
        elif "peatix.com" not in (row.get("source_url") or ""):
            skipped.append((row, "source_url is not a Peatix page"))
        else:
            targets.append(row)
    return targets, skipped


def is_blocked(organizer: str, blocked_patterns: Iterable[str]) -> bool:
    return any(pat in organizer for pat in blocked_patterns)


def _fetch_rows(sb, event_ids: list[str], include_inactive: bool) -> list[dict[str, Any]]:
    query = (
        sb.table("events")
        .select("id,source_url,raw_title,organizer,is_active")
        .eq("source_name", "peatix")
        .is_("organizer", "null")
    )
    if event_ids:
        query = query.in_("id", event_ids)
    elif not include_inactive:
        query = query.eq("is_active", True)
    return query.execute().data or []


def _fetch_locked(sb, event_ids: list[str]) -> set[str]:
    if not event_ids:
        return set()
    rows = (
        sb.table("field_corrections")
        .select("event_id")
        .eq("field_name", "organizer")
        .in_("event_id", event_ids)
        .execute()
        .data
        or []
    )
    return {r["event_id"] for r in rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="write to the DB (default: dry-run)")
    parser.add_argument("--event-ids", nargs="*", default=[], help="only these event UUIDs")
    parser.add_argument("--include-inactive", action="store_true", help="also past/inactive events")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    event_ids = parse_event_ids(args.event_ids)

    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    from playwright.sync_api import sync_playwright
    from supabase import create_client

    from observability import init_sentry
    from sources.peatix import BLOCKED_ORGANIZER_PATTERNS, extract_organizer_from_page

    init_sentry("backfill_peatix_organizer")

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    rows = _fetch_rows(sb, event_ids, args.include_inactive)
    targets, skipped = select_targets(rows, _fetch_locked(sb, [r["id"] for r in rows]))
    mode = "LIVE" if args.live else "DRY-RUN"
    logger.info("%s: %d candidate(s), %d target(s)", mode, len(rows), len(targets))
    for row, reason in skipped:
        logger.info("skip %s — %s", EVENT_URL.format(id=row["id"]), reason)

    found = updated = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(extra_http_headers=_HEADERS)
        for row in targets:
            link = EVENT_URL.format(id=row["id"])
            try:
                page = ctx.new_page()
                page.goto(row["source_url"], wait_until="networkidle", timeout=45000)
                organizer = extract_organizer_from_page(page)
                page.close()
            except Exception:  # one bad page must not stop the batch
                logger.exception("error %s", link)
                continue
            if not organizer:
                logger.warning("none  %s — no organizer on %s", link, row["source_url"])
                continue
            if is_blocked(organizer, BLOCKED_ORGANIZER_PATTERNS):
                logger.warning("block %s — %r matches BLOCKED_ORGANIZER_PATTERNS", link, organizer)
                continue
            found += 1
            print(f"{link} -> {organizer}")
            if args.live:
                res = (
                    sb.table("events")
                    .update({"organizer": organizer})
                    .eq("id", row["id"])
                    .is_("organizer", "null")
                    .execute()
                )
                updated += len(res.data or [])
        browser.close()

    logger.info("%s done: found=%d updated=%d", mode, found, updated)
    return 0


if __name__ == "__main__":
    sys.exit(main())
