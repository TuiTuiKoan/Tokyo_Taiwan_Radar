"""
Main scraper orchestrator.

Runs all source scrapers, saves raw data to Supabase,
then runs the AI annotator to extract structured fields.

Usage:
    python main.py

Environment variables required (set in .env):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    OPENAI_API_KEY
"""

import logging
import os
import sys

from dotenv import load_dotenv

# Load .env file from the same directory as this script
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from sources.taiwan_cultural_center import TaiwanCulturalCenterScraper
from sources.peatix import PeatixScraper
from database import upsert_events
from annotator import annotate_pending_events

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# All active scrapers — add new sources here
# ---------------------------------------------------------------------------
SCRAPERS = [
    TaiwanCulturalCenterScraper(),
    PeatixScraper(),
]


def run() -> None:
    all_events = []

    for scraper in SCRAPERS:
        source = type(scraper).__name__
        logger.info("=== Starting scraper: %s ===", source)
        try:
            events = scraper.scrape()
            logger.info("%s: scraped %d events", source, len(events))
            all_events.extend(events)
        except Exception as exc:
            logger.error("%s: scraper failed: %s", source, exc)

    logger.info("Total events scraped: %d", len(all_events))

    # Save raw data to database (annotation_status = 'pending')
    logger.info("Upserting raw events to Supabase...")
    upsert_events(all_events)

    # Run AI annotator on pending events
    logger.info("Running AI annotator on pending events...")
    annotate_pending_events()

    logger.info("Done!")


if __name__ == "__main__":
    run()
