"""
Main scraper orchestrator.

Runs all source scrapers, translates missing fields via DeepL,
then upserts everything to Supabase.

Usage:
    python main.py

Environment variables required (set in .env):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    DEEPL_API_KEY
"""

import logging
import os
import sys

from dotenv import load_dotenv

# Load .env file from the same directory as this script
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from sources.taiwan_cultural_center import TaiwanCulturalCenterScraper
from sources.peatix import PeatixScraper
from translator import fill_translations
from classifier import classify
from database import upsert_events, find_parent_event_id

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

    # Translate missing language fields
    logger.info("Running translations via DeepL...")
    for event in all_events:
        try:
            fill_translations(event)
        except Exception as exc:
            logger.error("Translation failed for event %s: %s", event.source_id, exc)

    # Auto-classify events (overwrites scraper-assigned categories)
    logger.info("Running semantic classifier...")
    for event in all_events:
        event.category = classify(
            event.name_ja, event.name_zh, event.name_en,
            event.description_ja, event.description_zh, event.description_en,
        )

    # Save to database (first pass — so parent events exist for linking)
    logger.info("Upserting to Supabase (pass 1)...")
    upsert_events(all_events)

    # Link report-type events to their parent events
    logger.info("Linking report events to parents...")
    reports_to_update = []
    for event in all_events:
        if "report" in event.category:
            parent_id = find_parent_event_id(event.name_ja, event.source_name)
            if parent_id:
                event.parent_event_id = parent_id
                # Set end_date to start_date to mark as ended
                if event.start_date:
                    event.end_date = event.start_date
                reports_to_update.append(event)
                logger.info(
                    "Linked report '%s' → parent %s",
                    event.source_id, parent_id
                )

    if reports_to_update:
        logger.info("Upserting %d linked reports (pass 2)...", len(reports_to_update))
        upsert_events(reports_to_update)

    logger.info("Done!")


if __name__ == "__main__":
    run()
