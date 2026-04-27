"""
Scraper for 京都大学人文科学研究所 (Zinbun) public events.

Strategy:
  1. Fetch /symposium/index_event.html — contains all public events
  2. Parse <table class="c-table"> rows:
       td[0]: ISO 8601 date (YYYY-MM-DD)
       td[1]: category tag(s) (c-tagList)
       td[2]: title + optional link + optional venue note
  3. Taiwan filter: title text contains 台湾 or Taiwan
  4. Detect venue override from "※会場は {venue}" notes in the row;
     default to 京都大学人文科学研究所
  5. source_id: "zinbun_{url_slug}" from the detail page URL path,
     or "zinbun_{date}_{title_hash}" if no link present
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.zinbun.kyoto-u.ac.jp"
LISTING_URL = f"{BASE_URL}/symposium/index_event.html"

DEFAULT_LOCATION_NAME = "京都大学人文科学研究所"
DEFAULT_LOCATION_ADDRESS = "京都府京都市左京区吉田本町46"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _parse_iso_date(date_str: str) -> Optional[datetime]:
    """Parse YYYY-MM-DD string to datetime."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date_str.strip())
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _extract_venue_override(row_text: str) -> Optional[str]:
    """
    Detect lines like "※会場は 一橋講堂（東京都） です。"
    Returns the venue name string, or None if not found.
    """
    m = re.search(r"※\s*会場は[、\s]*(.+?)(?:\s+です|。|$)", row_text)
    if m:
        return m.group(1).strip()
    return None


def _url_slug(href: str) -> Optional[str]:
    """Extract slug from a relative path like /symposium/zinbun-academy-2026-04-30.html"""
    m = re.search(r"/symposium/([^/]+?)(?:\.html)?$", href)
    return m.group(1) if m else None


def _title_hash(title: str, date_str: str) -> str:
    raw = f"{date_str}_{title}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]


class ZinbunKyotoScraper(BaseScraper):
    """Scrapes Taiwan-related public events from 京都大学人文科学研究所."""

    SOURCE_NAME = "zinbun_kyoto"

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

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        soup = self._get(LISTING_URL)
        if not soup:
            logger.error("Failed to fetch listing page: %s", LISTING_URL)
            return events

        tables = soup.select("table.c-table")
        logger.info("Found %d event tables on listing page", len(tables))

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue

                # Cell 0: date
                date_str = cells[0].get_text(strip=True)
                start_date = _parse_iso_date(date_str)
                if not start_date:
                    continue

                # Cell 2: title, link, venue note
                title_cell = cells[2]
                title_el = title_cell.find("a")
                if title_el:
                    # Combine span texts (some have sub-headers) + main text
                    title = title_el.get_text(separator=" ", strip=True)
                    href = title_el.get("href", "")
                    detail_url = urljoin(BASE_URL, href) if href else ""
                else:
                    title = title_cell.get_text(separator=" ", strip=True)
                    detail_url = ""

                # Taiwan filter
                if not _is_taiwan(title):
                    continue

                # source_id
                slug = _url_slug(detail_url) if detail_url else None
                if slug:
                    source_id = f"zinbun_{slug}"
                else:
                    source_id = f"zinbun_{date_str}_{_title_hash(title, date_str)}"

                # Venue override detection
                row_text = title_cell.get_text(separator=" ", strip=True)
                venue_override = _extract_venue_override(row_text)
                if venue_override:
                    location_name = venue_override
                    location_address = None
                else:
                    location_name = DEFAULT_LOCATION_NAME
                    location_address = DEFAULT_LOCATION_ADDRESS

                # Category tag
                tag_text = cells[1].get_text(strip=True)

                event = Event(
                    source_name=self.SOURCE_NAME,
                    source_id=source_id,
                    source_url=detail_url or LISTING_URL,
                    original_language="ja",
                    name_ja=title,
                    raw_title=title,
                    raw_description=f"種別: {tag_text}\n会場: {location_name}\n\n{title}",
                    description_ja=title,
                    category=["academic"],
                    start_date=start_date,
                    location_name=location_name,
                    location_address=location_address,
                )
                events.append(event)
                logger.info("Found Taiwan event: %s (%s)", title, date_str)

        logger.info("Total Taiwan events found: %d", len(events))
        return events
