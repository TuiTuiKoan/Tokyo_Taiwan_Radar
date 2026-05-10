"""
Scraper for シネプラザサントムーン (Cineplaza Suntomoon), Shimizu-cho, Shizuoka.

Strategy:
  1. Fetch /coming/ page (upcoming films)
  2. Iterate: h3.coming_date → date; ul.coming_list → one film per ul
  3. Film title from li.det span (first span)
  4. Check title for Taiwan keywords; if match, yield event
  5. source_id: cineplaza_{md5(title)[:10]}
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

LISTING_URL = "https://cineplaza.net/coming/"
BASE_URL = "https://cineplaza.net"
LOCATION_NAME = "シネプラザサントムーン"
LOCATION_ADDRESS = "静岡県駿東郡清水町"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan", "臺灣"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _source_id(title: str) -> str:
    digest = hashlib.md5(title.encode("utf-8")).hexdigest()[:10]
    return f"cineplaza_{digest}"


def _parse_date(header_text: str) -> Optional[datetime]:
    """Parse '2026年4月29日公開予定作品' → datetime."""
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", header_text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


class CineplazaScraper(BaseScraper):
    """Scrapes Taiwan-related upcoming films from シネプラザサントムーン."""

    SOURCE_NAME = "cineplaza"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        try:
            resp = self._session.get(LISTING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Failed to fetch Cineplaza: %s", exc)
            return events

        soup = BeautifulSoup(resp.content, "html.parser")

        # Walk through date headers and film lists
        current_date: Optional[datetime] = None
        for tag in soup.select("#inner > *"):
            if tag.name == "h3" and "coming_date" in (tag.get("class") or []):
                current_date = _parse_date(tag.get_text(strip=True))
            elif tag.name == "ul" and "coming_list" in (tag.get("class") or []):
                det = tag.select_one("li.det")
                if not det:
                    continue
                title_span = det.select_one("span")
                if not title_span:
                    continue
                title = title_span.get_text(strip=True)
                full_text = det.get_text(" ", strip=True)

                if not _is_taiwan(title) and not _is_taiwan(full_text):
                    continue

                # Get official site link (if any)
                btn = tag.select_one("li.btn_official a[href]")
                source_url = btn.get("href") if btn else LISTING_URL

                event = Event(
                    source_name=self.SOURCE_NAME,
                    source_id=_source_id(title),
                    source_url=source_url or LISTING_URL,
                    original_language="ja",
                    name_ja=title,
                    raw_title=title,
                    raw_description=full_text,
                    description_ja=full_text,
                    category=["art"],
                    start_date=current_date,
                    location_name=LOCATION_NAME,
                    location_address=LOCATION_ADDRESS,
                )
                events.append(event)
                logger.info("Cineplaza Taiwan event: %s", title)

        logger.info("Cineplaza total: %d Taiwan events", len(events))
        return events
