"""Scraper for 東京農工大学グローバルイノベーション研究院 (TUAT Global).

Site: https://www.tuat-global.jp/event/
Type: Static HTML, paginated (10 events/page)
Auth: None
Rate limit: polite (no observed limit)

Events are public seminars featuring foreign researchers, held at
TUAT campuses in 府中市 and 小金井市 (both in Tokyo).
Taiwan-related events are identified by 台湾/Taiwan/臺灣 in the title.
"""

import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from playwright.sync_api import Page, sync_playwright, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "tuat_global"
BASE_URL = "https://www.tuat-global.jp"
LIST_URL = "https://www.tuat-global.jp/event/"

# Only look at the first N pages (10 events each).
# Events are listed newest-first; 3 pages covers ~3 months of seminars.
MAX_PAGES = 3

# Events older than LOOKBACK_DAYS days are skipped.
LOOKBACK_DAYS = 60

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]

JST = timezone(timedelta(hours=9))


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _parse_date(raw: str) -> Optional[datetime]:
    """Parse '2026.4.15（14：00～15：30）' or '2026.3.2（10：00～12：00）'.

    Returns a timezone-aware datetime (JST) for the start time.
    Falls back to midnight JST when no time is given.
    """
    raw = raw.strip()
    # Remove Japanese weekday in parentheses e.g. （月）（火）etc.
    raw = re.sub(r'（[月火水木金土日]）', '', raw)
    # Extract date part: YYYY.M.D
    date_match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', raw)
    if not date_match:
        return None
    year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
    # Extract start time from 「HH：MM～HH：MM」or 「HH:MM～HH:MM」
    time_match = re.search(r'(\d{1,2})[：:](\d{2})[～~]', raw)
    hour, minute = 0, 0
    if time_match:
        hour, minute = int(time_match.group(1)), int(time_match.group(2))
    try:
        return datetime(year, month, day, hour, minute, tzinfo=JST)
    except ValueError:
        logger.warning("Failed to parse date: %r", raw)
        return None


def _extract_table_fields(table_el) -> dict:
    """Extract 名称/日時/会場 from a listing-page <table> element."""
    result: dict = {}
    rows = table_el.query_selector_all("tr")
    for row in rows:
        th = row.query_selector("th")
        td = row.query_selector("td")
        if not th or not td:
            continue
        label = th.inner_text().strip()
        if label == "名称":
            a = td.query_selector("a")
            if a:
                result["title"] = a.inner_text().strip()
                result["url"] = a.get_attribute("href") or ""
            else:
                result["title"] = td.inner_text().strip()
                result["url"] = ""
        elif label == "日時":
            result["date_raw"] = td.inner_text().strip()
        elif label == "会場":
            result["venue"] = td.inner_text().strip()
    return result


class TuatGlobalScraper(BaseScraper):
    """Scraper for TUAT Global Innovation Research Institute seminars."""

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        cutoff = datetime.now(JST) - timedelta(days=LOOKBACK_DAYS)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page: Page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )

            for page_num in range(1, MAX_PAGES + 1):
                url = LIST_URL if page_num == 1 else f"{LIST_URL}page/{page_num}/"
                logger.info("Fetching %s", url)
                try:
                    page.goto(url, wait_until="networkidle", timeout=45000)
                except PWTimeout:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)

                tables = page.query_selector_all("table")
                if not tables:
                    logger.info("No tables on page %d — stopping pagination", page_num)
                    break

                for table in tables:
                    fields = _extract_table_fields(table)
                    title = fields.get("title", "")
                    if not title:
                        continue
                    if not _is_taiwan(title):
                        continue

                    date_raw = fields.get("date_raw", "")
                    start_date = _parse_date(date_raw)
                    if start_date and start_date < cutoff:
                        logger.debug("Skipping old event: %s (%s)", title, date_raw)
                        continue

                    detail_url = fields.get("url", "")
                    if detail_url and not detail_url.startswith("http"):
                        detail_url = BASE_URL + detail_url

                    # source_id: extract numeric post ID from /event/NNNN/
                    post_id_match = re.search(r'/event/(\d+)/', detail_url)
                    post_id = post_id_match.group(1) if post_id_match else re.sub(r'\W+', '_', title)[:40]
                    source_id = f"{SOURCE_NAME}_{post_id}"

                    venue_raw = fields.get("venue", "")
                    # Venue may contain newlines (Zoom link etc.) — keep first non-empty line
                    venue_lines = [ln.strip() for ln in venue_raw.splitlines() if ln.strip()]
                    location_name = venue_lines[0] if venue_lines else None
                    # Filter out lines starting with http (map URLs etc.)
                    location_lines = [ln for ln in venue_lines if not ln.startswith("http")]
                    location_address = "\n".join(location_lines) if location_lines else None

                    raw_desc = f"開催日時: {date_raw}\n\n会場: {venue_raw}"

                    events.append(Event(
                        source_name=SOURCE_NAME,
                        source_id=source_id,
                        source_url=detail_url or url,
                        original_language="ja",
                        name_ja=title,
                        category=["academic", "taiwan_japan"],
                        start_date=start_date,
                        location_name=location_name,
                        location_address=location_address,
                        is_paid=False,
                        raw_title=title,
                        raw_description=raw_desc,
                    ))
                    logger.info("Found Taiwan event: %s", title)

            browser.close()

        logger.info("tuat_global: scraped %d events", len(events))
        return events
