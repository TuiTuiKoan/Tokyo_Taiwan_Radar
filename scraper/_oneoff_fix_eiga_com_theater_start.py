#!/usr/bin/env python3
"""One-off (issue #537): correct start_date of existing eiga_com theater events
that inherited the film's 劇場公開日 although the theater started later.

Before #537 every theater event got start_date = 劇場公開日. After #537 the
scraper gives a later-run theater its own first screening date, but the DB keeps
the earliest start for eiga_com, so already-stored wrong dates would never move.

A stored start is treated as inherited (not observed) when the row was created
more than 7 days after it: the scraper first saw this theater long after that
date, so the date cannot come from this theater's schedule.

Usage (from scraper/):
    python _oneoff_fix_eiga_com_theater_start.py            # dry-run: print proposals
    python _oneoff_fix_eiga_com_theater_start.py --apply    # write (needs approval)

Needs SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY and network access to eiga.com.
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from database import _get_client, _normalize_legacy_jst_midnight, _parse_iso_utc  # noqa: E402
from sources.eiga_com import SOURCE_NAME, EigaComScraper  # noqa: E402

logger = logging.getLogger(__name__)

_INHERITED_GAP = timedelta(days=7)


def propose(row: dict, scraped_start: datetime | None) -> str | None:
    """Return the corrected start_date ISO string, or None to leave the row alone."""
    if scraped_start is None:
        return None
    db_start = _parse_iso_utc(_normalize_legacy_jst_midnight(row.get("start_date")) or "")
    created = _parse_iso_utc(row.get("created_at") or "")
    if db_start is None or created is None:
        return None
    if created <= db_start + _INHERITED_GAP:
        return None  # stored start was observed from this theater's schedule
    if scraped_start <= db_start:
        return None
    return scraped_start.astimezone(timezone.utc).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write corrections (default: dry-run)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    client = _get_client()
    rows = (
        client.table("events")
        .select("id,source_id,start_date,end_date,created_at,name_ja,location_name")
        .eq("source_name", SOURCE_NAME)
        .eq("is_active", True)
        .execute()
        .data
        or []
    )
    scraped = {ev.source_id: ev.start_date for ev in EigaComScraper().scrape()}

    proposals = []
    for row in rows:
        new_start = propose(row, scraped.get(row["source_id"]))
        if new_start:
            proposals.append((row, new_start))

    for row, new_start in proposals:
        print(
            f"https://tokyotaiwanradar.com/ja/events/{row['id']}  "
            f"{row.get('name_ja')} / {row.get('location_name')}  "
            f"{row['start_date']} → {new_start}"
        )
    print(f"\n{len(proposals)} correction(s) out of {len(rows)} active eiga_com row(s)")

    if not args.apply:
        print("dry-run: nothing written")
        return 0

    for row, new_start in proposals:
        client.table("events").update(
            {"start_date": new_start, "annotation_status": "pending"}
        ).eq("id", row["id"]).execute()
    print(f"applied {len(proposals)} correction(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
