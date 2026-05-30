"""
One-off script: re-scrape Peatix organizer for events with organizer=null.
Uses the same extraction logic as sources/peatix.py (lines 470-496).
Run: cd scraper && source ../.venv/bin/activate && python _oneoff_fix_peatix_organizer.py
"""
from __future__ import annotations
import re
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
from supabase import create_client
from playwright.sync_api import sync_playwright

# Import the blocked-organizer pattern list from peatix.py (module-level constant)
from sources.peatix import BLOCKED_ORGANIZER_PATTERNS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _extract_organizer(page) -> str:
    """Same logic as peatix.py lines 470-496."""
    organizer_name = ""
    for _el in page.query_selector_all("a[href*='peatix.com/group/']"):
        _href = _el.get_attribute("href") or ""
        if re.search(r"peatix\.com/group/\d+", _href):
            _txt = (_el.inner_text() or "").strip()
            _txt = re.sub(r"\s+", " ", _txt)
            if _txt and len(_txt) <= 100:
                organizer_name = _txt
                break
    if not organizer_name:
        for selector in [".group-name", "[class*='organizer']"]:
            _el = page.query_selector(selector)
            if _el:
                _txt = (_el.inner_text() or "").strip()
                _txt = re.sub(r"\s+", " ", _txt)
                if _txt and len(_txt) <= 100:
                    organizer_name = _txt
                    break
    return organizer_name


def main() -> None:
    rows = (
        sb.table("events")
        .select("id,source_url,raw_title,organizer")
        .eq("source_name", "peatix")
        .is_("organizer", "null")
        .eq("is_active", True)
        .execute()
        .data
    )
    logger.info("Found %d peatix events with organizer=null", len(rows))
    if not rows:
        logger.info("Nothing to do.")
        return

    updated = 0
    skipped = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(extra_http_headers=_HEADERS)

        for row in rows:
            event_id = row["id"]
            url = row["source_url"]
            raw_title = (row.get("raw_title") or "")[:60]
            logger.info("Processing %s — %s", event_id[:8], raw_title)

            try:
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                organizer = _extract_organizer(page)
                page.close()

                if not organizer:
                    logger.warning("  No organizer found — skipping")
                    skipped += 1
                    continue

                if any(pat in organizer for pat in BLOCKED_ORGANIZER_PATTERNS):
                    logger.warning("  Blocked organizer '%s' — skipping", organizer[:40])
                    skipped += 1
                    continue

                logger.info("  organizer = '%s'", organizer)
                sb.table("events").update({"organizer": organizer}).eq("id", event_id).execute()
                updated += 1

            except Exception as exc:
                logger.error("  Error processing %s: %s", event_id[:8], exc)
                skipped += 1

        browser.close()

    logger.info("Done. Updated=%d Skipped=%d", updated, skipped)


if __name__ == "__main__":
    main()
