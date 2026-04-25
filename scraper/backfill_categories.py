"""
Backfill new categories (taiwan_japan, business, academic) to existing events
using the keyword classifier. Does NOT call GPT — runs locally and is free.

Usage:
  python backfill_categories.py --dry-run   # preview changes
  python backfill_categories.py             # apply changes to DB
"""

import argparse
import logging
import os

from dotenv import load_dotenv
from supabase import create_client

from classifier import classify

load_dotenv(dotenv_path=".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NEW_CATEGORIES = {"taiwan_japan", "business", "academic"}


def main(dry_run: bool) -> None:
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    # Fetch all active events
    res = (
        sb.table("events")
        .select("id,name_ja,name_zh,name_en,description_ja,description_zh,description_en,category")
        .eq("is_active", True)
        .execute()
    )
    events = res.data
    logger.info("Fetched %d active events", len(events))

    updates: list[dict] = []

    for e in events:
        current = set(e.get("category") or [])
        classified = set(
            classify(
                e.get("name_ja"),
                e.get("name_zh"),
                e.get("name_en"),
                e.get("description_ja"),
                e.get("description_zh"),
                e.get("description_en"),
            )
        )
        # Only add new categories that classifier found AND that are in the NEW_CATEGORIES set
        to_add = (classified & NEW_CATEGORIES) - current
        if to_add:
            new_category = sorted(current | to_add)
            updates.append({"id": e["id"], "name_ja": e.get("name_ja", ""), "old": sorted(current), "new": new_category})

    logger.info("Events to update: %d", len(updates))
    for u in updates:
        logger.info("  [%s] %s", u["id"][:8], (u["name_ja"] or "")[:60])
        logger.info("    %s  →  %s", u["old"], u["new"])

    if dry_run:
        logger.info("DRY RUN — no changes written")
        return

    for u in updates:
        sb.table("events").update({"category": u["new"]}).eq("id", u["id"]).execute()
        logger.info("Updated %s", u["id"][:8])

    logger.info("Done. %d events updated.", len(updates))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
