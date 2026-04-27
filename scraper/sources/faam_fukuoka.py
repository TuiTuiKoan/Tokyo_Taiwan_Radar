"""
Scraper for 福岡アジア美術館 (Fukuoka Asian Art Museum).

Strategy:
  1. Fetch /exhibition/ listing page — parse c-list-exhibition-item cards
     Each card has title, date range, and exhibition URL
  2. Two-phase Taiwan filter:
     a. Check title from listing for 台湾 keywords (fast)
     b. If not found, fetch detail page and check full description (thorough)
  3. Parse date range from "YYYY.M.D (曜） 〜 YYYY.M.D (曜）" format
  4. source_id: "faam_{exhibition_id}" — numeric ID from URL path
  5. Location: 福岡アジア美術館, 福岡県福岡市博多区下川端町3-1 リバレインセンタービル7・8F
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://faam.city.fukuoka.lg.jp"
LISTING_URL = f"{BASE_URL}/exhibition/"

LOCATION_NAME = "福岡アジア美術館"
LOCATION_ADDRESS = "福岡県福岡市博多区下川端町3-1 リバレインセンタービル7・8F"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _parse_date_range(date_str: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse "2026.4.18 (土） 〜 2026.8.30 (日）" → (start, end)."""
    matches = re.findall(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", date_str)
    if not matches:
        return None, None
    try:
        start = datetime(int(matches[0][0]), int(matches[0][1]), int(matches[0][2]))
    except (ValueError, IndexError):
        start = None
    try:
        end = datetime(int(matches[1][0]), int(matches[1][1]), int(matches[1][2]), 23, 59, 59)
    except (ValueError, IndexError):
        end = None
    return start, end


def _parse_exhibition_id(url: str) -> Optional[str]:
    """Extract numeric exhibition ID from URL path."""
    m = re.search(r"/exhibition/(\d+)/", url)
    return m.group(1) if m else None


class FaamFukuokaScraper(BaseScraper):
    """Scrapes Taiwan-related exhibitions at 福岡アジア美術館."""

    SOURCE_NAME = "faam_fukuoka"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })

    def _get(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as exc:
            logger.warning("GET %s failed: %s", url, exc)
            return None

    def _scrape_detail(self, url: str) -> str:
        """Return full description text from detail page."""
        soup = self._get(url)
        if not soup:
            return ""
        # Main content area
        content_el = soup.select_one(
            "div.c-content-body, div.entry-content, main article, div.l-content"
        )
        if content_el:
            return content_el.get_text(separator="\n", strip=True)
        return soup.get_text(separator="\n", strip=True)

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        soup = self._get(LISTING_URL)
        if not soup:
            logger.error("Failed to fetch listing page: %s", LISTING_URL)
            return events

        items = soup.select("div.c-list-exhibition-item")
        logger.info("Found %d exhibition cards on listing page", len(items))

        for item in items:
            link_el = item.select_one("a.c-list-exhibition-item__inner")
            if not link_el:
                continue

            detail_url = link_el.get("href", "")
            if not detail_url:
                continue

            # Title
            title_el = item.select_one("h3.c-list-exhibition-item__title")
            title = title_el.get_text(strip=True) if title_el else ""

            # Date range
            date_el = item.select_one("span.c-list-exhibition-item__date")
            date_str = date_el.get_text(strip=True) if date_el else ""
            start_date, end_date = _parse_date_range(date_str)

            # Exhibition ID and source_id
            ex_id = _parse_exhibition_id(detail_url)
            if not ex_id:
                continue
            source_id = f"faam_{ex_id}"

            # Phase 1: check title
            if _is_taiwan(title):
                logger.debug("Taiwan hit in title: %s", title)
                description = ""
            else:
                # Phase 2: fetch detail page for full text check
                time.sleep(0.5)
                description = self._scrape_detail(detail_url)
                if not _is_taiwan(description):
                    logger.debug("Skipping non-Taiwan exhibition: %s", title)
                    continue

            # If we only hit via description, fetch description anyway
            if not description:
                time.sleep(0.5)
                description = self._scrape_detail(detail_url)

            # Build raw_description
            raw_desc = ""
            if date_str:
                raw_desc += f"会期: {date_str}\n\n"
            raw_desc += description

            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=detail_url,
                original_language="ja",
                name_ja=title,
                raw_title=title,
                raw_description=raw_desc,
                description_ja=description or None,
                category=["art"],
                start_date=start_date,
                end_date=end_date,
                location_name=LOCATION_NAME,
                location_address=LOCATION_ADDRESS,
            )
            events.append(event)
            logger.info("Found Taiwan exhibition: %s (%s)", title, date_str)

        logger.info("Total Taiwan exhibitions found: %d", len(events))
        return events
