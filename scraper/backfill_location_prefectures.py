#!/usr/bin/env python3
"""
Backfill location_prefectures for multi-city parent events.

Reads sub-events' location_address, extracts prefecture names, and updates
the parent event's location_prefectures column.

Run AFTER migration 012 has been applied in Supabase Dashboard:
    cd scraper && source ../.venv/bin/activate && python backfill_location_prefectures.py
"""
import os
import re
import sys
import logging
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def extract_prefecture(address: str | None) -> str | None:
    """Extract prefecture name from a Japanese address string."""
    if not address:
        return None
    m = re.match(r"^(北海道|東京都|(?:大阪|京都)府|大阪市|京都市|[^\s都道府県]{2,4}[都道府県])", address)
    if not m:
        return None
    full = m.group(1)
    if full == "北海道":
        return "北海道"
    if full in ("大阪市", "大阪府"):
        return "大阪"
    if full in ("京都市", "京都府"):
        return "京都"
    return full.rstrip("都道府県")


def main() -> None:
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    # Fetch all active sub-events with location_address
    logger.info("Fetching sub-events...")
    subs = (
        sb.table("events")
        .select("parent_event_id,location_address")
        .not_.is_("parent_event_id", "null")
        .eq("is_active", True)
        .execute()
    )

    # Aggregate prefectures per parent
    parent_prefectures: dict[str, set[str]] = defaultdict(set)
    for s in subs.data:
        pid = s["parent_event_id"]
        pref = extract_prefecture(s["location_address"])
        if pref:
            parent_prefectures[pid].add(pref)

    # Only update parents with 2+ prefectures
    multi_city = {pid: sorted(prefs) for pid, prefs in parent_prefectures.items() if len(prefs) >= 2}
    logger.info("Found %d multi-city parent events", len(multi_city))

    updated = 0
    for pid, prefs in multi_city.items():
        try:
            sb.table("events").update({"location_prefectures": prefs}).eq("id", pid).execute()
            # Log the event name
            name_res = sb.table("events").select("name_ja").eq("id", pid).single().execute()
            name = name_res.data.get("name_ja", pid)[:50] if name_res.data else pid
            logger.info("  ✓ %s → %s", name, prefs)
            updated += 1
        except Exception as e:
            logger.error("  ✗ %s: %s", pid, e)

    logger.info("Backfill complete: %d/%d events updated", updated, len(multi_city))


if __name__ == "__main__":
    main()
