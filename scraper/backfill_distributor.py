"""Backfill distributor_ja for works records via eiga.com.

Queries all works where distributor_ja IS NULL, looks up each title_ja on
eiga.com to extract the Japanese theatrical distributor (配給会社), and
updates the works table.

Usage:
    cd scraper
    python backfill_distributor.py            # apply changes to DB
    python backfill_distributor.py --dry-run  # preview only, no DB writes
"""
import argparse
import logging
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from supabase import create_client

from movie_title_lookup import lookup_distributor_ja

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main(dry_run: bool) -> None:
    sb = create_client(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    )

    result = (
        sb.table("works")
        .select("id,title_ja,original_title,work_type")
        .is_("distributor_ja", "null")
        .execute()
    )
    works = result.data
    logger.info(f"Found {len(works)} works with distributor_ja=NULL")

    updated = 0
    skipped = 0
    for w in works:
        title_ja = w.get("title_ja") or w.get("original_title") or ""
        if not title_ja:
            logger.warning(f"  SKIP {w['id'][:8]} — no title_ja or original_title")
            skipped += 1
            continue

        distributor_ja, eiga_url = lookup_distributor_ja(title_ja)
        if not distributor_ja:
            logger.info(f"  NOT FOUND: {title_ja!r}")
            skipped += 1
            continue

        logger.info(f"  FOUND: {title_ja!r} → {distributor_ja!r}  ({eiga_url})")
        if not dry_run:
            sb.table("works").update({"distributor_ja": distributor_ja}).eq(
                "id", w["id"]
            ).execute()
        updated += 1

    mode = "DRY-RUN" if dry_run else "APPLIED"
    logger.info(f"\n=== {mode} SUMMARY ===")
    logger.info(f"  Updated : {updated}")
    logger.info(f"  Skipped : {skipped}")
    logger.info(f"  Total   : {len(works)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Backfill distributor_ja for works via eiga.com"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
