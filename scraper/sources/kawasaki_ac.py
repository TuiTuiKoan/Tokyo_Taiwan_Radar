"""
Scraper for 川崎市アートセンター アルテリオ映像館 (Kawasaki Art Center Cinema), Kawasaki.

Strategy:
  1. Fetch /movie/theater/ — parse all a[href*="/movie/theater/detail/?id="] links
     (both 上映中 and 近日上映 sections)
  2. For each detail page, check full page text for Taiwan keywords (台湾/台灣/Taiwan)
  3. Extract title from h2 on detail page, dates from 上映日 or date range text
  4. source_id: "kawasaki_ac_{id_num}" — from "?id=002430" → "kawasaki_ac_002430"
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

BASE_URL = "https://kawasaki-ac.jp"
LISTING_URL = f"{BASE_URL}/movie/theater/"
LOCATION_NAME = "川崎市アートセンター アルテリオ映像館"
LOCATION_ADDRESS = "神奈川県川崎市麻生区万福寺6-7-1"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _parse_id(href: str) -> Optional[str]:
    m = re.search(r"[?&]id=(\w+)", href)
    return m.group(1) if m else None


def _parse_date_range(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse date range like '5.19～6.5' or '近日上映' relative to current year."""
    m = re.search(r"(\d+)\.(\d+)～(\d+)\.(\d+)", text)
    if not m:
        return None, None
    year = datetime.now().year
    sm, sd, em, ed = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    # Handle year rollover (Dec → Jan)
    start = datetime(year if sm >= 1 else year + 1, sm, sd)
    end = datetime(year if em >= sm else year + 1, em, ed)
    return start, end


class KawasakiAcScraper(BaseScraper):
    """Scrapes Taiwan-related films from 川崎市アートセンター アルテリオ映像館."""

    SOURCE_NAME = "kawasaki_ac"

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

    def _scrape_detail(self, url: str) -> dict:
        result = {"title": "", "description": "", "full_text": ""}
        soup = self._get(url)
        if not soup:
            return result

        h2 = soup.find("h2")
        if h2:
            result["title"] = h2.get_text(strip=True)

        # Description: p tags in main content
        paras = [p.get_text(strip=True) for p in soup.select("p") if p.get_text(strip=True)]
        result["description"] = "\n".join(paras[:8])

        result["full_text"] = soup.get_text(" ", strip=True)
        return result

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        soup = self._get(LISTING_URL)
        if not soup:
            logger.error("Failed to fetch listing page: %s", LISTING_URL)
            return events

        # Collect all detail links with associated date range text
        seen_ids: set[str] = set()
        cards: list[tuple[str, str, str]] = []  # (href, title, date_text)

        for link in soup.select("a[href*='/movie/theater/detail/']"):
            href = link.get("href", "")
            film_id = _parse_id(href)
            if not film_id or film_id in seen_ids:
                continue
            seen_ids.add(film_id)

            title = link.get_text(strip=True)

            # Date text: look in parent element for sibling text
            parent = link.parent
            date_text = ""
            if parent:
                date_text = parent.get_text(" ", strip=True)

            full_href = BASE_URL + href if href.startswith("/") else href
            cards.append((full_href, title, date_text))

        logger.info("Found %d unique film cards", len(cards))

        for detail_url, card_title, date_text in cards:
            time.sleep(0.5)
            detail = self._scrape_detail(detail_url)

            if not _is_taiwan(detail["full_text"]):
                logger.debug("Skipping non-Taiwan film: %s", detail["title"] or card_title)
                continue

            film_id = _parse_id(detail_url)
            source_id = f"kawasaki_ac_{film_id}"
            title = detail["title"] or card_title

            start_date, end_date = _parse_date_range(date_text)

            raw_desc = detail["description"]
            if start_date:
                raw_desc = (
                    f"上映期間: {start_date.strftime('%Y年%m月%d日')}"
                    + (f"〜{end_date.strftime('%Y年%m月%d日')}" if end_date else "")
                    + "\n\n" + raw_desc
                )

            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=detail_url,
                original_language="ja",
                name_ja=title,
                raw_title=title,
                raw_description=raw_desc,
                description_ja=detail["description"] or None,
                category=["movie"],
                start_date=start_date,
                end_date=end_date,
                location_name=LOCATION_NAME,
                location_address=LOCATION_ADDRESS,
            )
            events.append(event)
            logger.info("Found Taiwan film: %s", title)

        logger.info("Total Taiwan films found: %d", len(events))
        return events
