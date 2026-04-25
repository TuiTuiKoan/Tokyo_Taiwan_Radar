"""Scraper for 公益財団法人 国家基本問題研究所 (JINF) — Japan Institute for National Fundamentals.

Site: https://jinf.jp/meeting
Type: Static HTML, single page listing upcoming events
Auth: None (public list)
Rate limit: None observed

Upcoming lectures and symposia are listed as `<div class="meetingbox">` elements.
Each box contains: title in `<strong class="title">`, 【開催日】 date, 【場　所】 venue,
【登壇者】 speakers, and a registration link `/meeting/form?id=NNNN`.

Taiwan filter: 台湾/Taiwan/臺灣 anywhere in the box text (title or speakers).
"""

import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from playwright.sync_api import Page, sync_playwright

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "jinf"
MEETING_URL = "https://jinf.jp/meeting"

JST = timezone(timedelta(hours=9))
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse 'YYYY-MM-DD' to timezone-aware datetime (JST, midnight)."""
    date_str = date_str.strip()
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if not m:
        return None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(year, month, day, 0, 0, tzinfo=JST)
    except ValueError:
        logger.warning("Failed to parse date: %r", date_str)
        return None


def _extract_field(text: str, label: str) -> str:
    """Extract value after a 【label】 marker up to the next 【 or end of string."""
    pattern = rf'【{re.escape(label)}】\s*(.*?)(?=【|$)'
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return ""
    return m.group(1).strip()


class JinfScraper(BaseScraper):
    """Scraper for JINF upcoming lectures and symposia."""

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page: Page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )

            logger.info("Fetching %s", MEETING_URL)
            page.goto(MEETING_URL, wait_until="domcontentloaded", timeout=30000)

            boxes = page.query_selector_all("div.meetingbox")
            logger.info("Found %d meetingbox elements", len(boxes))

            for box in boxes:
                box_html = box.inner_html()
                box_text = box.inner_text()

                if not _is_taiwan(box_text):
                    continue

                # Title is in <strong class="title">
                title_el = box.query_selector("strong.title")
                title = title_el.inner_text().strip() if title_el else ""

                # Date
                date_raw = _extract_field(box_text, "開催日")
                # Also handle 【場　所】 (wide space)
                if not date_raw:
                    m = re.search(r'【開催日】\s*(\S+)', box_text)
                    date_raw = m.group(1) if m else ""
                start_date = _parse_date(date_raw)

                # Venue
                venue_raw = _extract_field(box_text, "場　所")
                if not venue_raw:
                    venue_raw = _extract_field(box_text, "場所")
                # Filter http lines from venue
                venue_lines = [ln.strip() for ln in venue_raw.splitlines() if ln.strip() and not ln.strip().startswith("http")]
                location_name = venue_lines[0] if venue_lines else None
                location_address = None  # JINF doesn't provide full addresses on this page

                # Registration link → source URL + source_id
                form_link_el = box.query_selector("a[href*='/meeting/form']")
                form_href = form_link_el.get_attribute("href") if form_link_el else None
                if form_href:
                    if form_href.startswith("/"):
                        source_url = f"https://jinf.jp{form_href}"
                    else:
                        source_url = form_href
                    form_id_m = re.search(r'id=(\d+)', form_href)
                    source_id = f"{SOURCE_NAME}_{form_id_m.group(1)}" if form_id_m else f"{SOURCE_NAME}_{re.sub(r'\\W+', '_', title)[:40]}"
                else:
                    source_url = MEETING_URL
                    source_id = f"{SOURCE_NAME}_{re.sub(r'W+', '_', title)[:40]}"

                # Speakers block (everything after 【登壇者】)
                speakers_raw = _extract_field(box_text, "登壇者")

                raw_desc_parts = [f"開催日時: {date_raw}"]
                if venue_raw:
                    raw_desc_parts.append(f"会場: {venue_raw}")
                if speakers_raw:
                    raw_desc_parts.append(f"登壇者:\n{speakers_raw}")
                raw_description = "\n\n".join(raw_desc_parts)

                events.append(Event(
                    source_name=SOURCE_NAME,
                    source_id=source_id,
                    source_url=source_url,
                    original_language="ja",
                    name_ja=title,
                    category=["geopolitics", "taiwan_japan"],
                    start_date=start_date,
                    location_name=location_name,
                    location_address=location_address,
                    is_paid=False,
                    raw_title=title,
                    raw_description=raw_description,
                ))
                logger.info("Found Taiwan event: %s", title)

            browser.close()

        logger.info("jinf: scraped %d events", len(events))
        return events
