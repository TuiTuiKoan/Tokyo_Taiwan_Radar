"""
Main scraper orchestrator.

Runs all source scrapers, saves raw data to Supabase,
then runs the AI annotator to extract structured fields.

Usage:
    python main.py                              # normal run (scrape + save + annotate)
    python main.py --dry-run                    # scrape all, print JSON, no DB/AI calls
    python main.py --dry-run --source peatix    # scrape one source, print JSON
    python main.py --dry-run --source taiwan_cultural_center

Environment variables required (set in .env):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    OPENAI_API_KEY
"""

import argparse
import dataclasses
import json
import logging
import os
import re
import sys
from datetime import datetime

from dotenv import load_dotenv

# Load .env file from the same directory as this script
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from sources.taiwan_cultural_center import TaiwanCulturalCenterScraper
from sources.peatix import PeatixScraper
from sources.taioan_dokyokai import TaioanDokyokaiScraper
from database import upsert_events
from annotator import annotate_pending_events

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# All active scrapers — add new sources here
# ---------------------------------------------------------------------------
SCRAPERS = [
    TaiwanCulturalCenterScraper(),
    PeatixScraper(),
    TaioanDokyokaiScraper(),
]


def _scraper_key(scraper) -> str:
    """Convert a scraper class name to its snake_case source key.

    e.g. TaiwanCulturalCenterScraper -> taiwan_cultural_center
         PeatixScraper                -> peatix
    """
    name = type(scraper).__name__
    name = re.sub(r"Scraper$", "", name)
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def run(dry_run: bool = False, source: str | None = None) -> None:
    active_scrapers = SCRAPERS

    if source:
        active_scrapers = [s for s in SCRAPERS if _scraper_key(s) == source]
        if not active_scrapers:
            available = ", ".join(_scraper_key(s) for s in SCRAPERS)
            logger.error("Unknown source %r. Available: %s", source, available)
            sys.exit(1)

    all_events = []

    for scraper in active_scrapers:
        source_label = type(scraper).__name__
        logger.info("=== Starting scraper: %s ===", source_label)
        try:
            events = scraper.scrape()
            logger.info("%s: scraped %d events", source_label, len(events))
            all_events.extend(events)
        except Exception as exc:
            logger.error("%s: scraper failed: %s", source_label, exc)

    logger.info("Total events scraped: %d", len(all_events))

    if dry_run:
        logger.info("DRY RUN — skipping DB write and AI annotation")
        print(json.dumps(
            [dataclasses.asdict(e) for e in all_events],
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        ))
        return

    # Save raw data to database (annotation_status = 'pending')
    logger.info("Upserting raw events to Supabase...")
    upsert_events(all_events)

    # Run AI annotator on pending events
    logger.info("Running AI annotator on pending events...")
    annotate_pending_events()

    logger.info("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tokyo Taiwan Radar scraper")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and print JSON output without writing to DB or calling OpenAI",
    )
    parser.add_argument(
        "--source",
        metavar="NAME",
        help="Only run the named scraper (e.g. peatix, taiwan_cultural_center)",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, source=args.source)
