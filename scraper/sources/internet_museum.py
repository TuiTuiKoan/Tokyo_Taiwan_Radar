"""
Scraper for アイエム（インターネットミュージアム）- museum.or.jp

Strategy:
  1. Fetch all 13 region schedule pages for 2026
  2. For each event block (.p-schedule_museum_event), check title for Taiwan keywords
  3. Skip past events (has class 'is-past')
  4. Parse dates from .p-schedule_museum_event_term
  5. source_id: internet_museum_{event_id} from /event/{ID}
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.museum.or.jp"
YEAR = 2026

# All region schedule pages
REGION_AREAS = [
    "area_hokkaido-touhoku",
    "area_kitakanto",
    "area_tokyo_ueno",
    "area_tokyo23east",
    "area_tokyo23west",
    "area_kanagawa-chiba-saitama",
    "area_koushinetsu",
    "area_toukai",
    "area_hokuriku",
    "area_keihanshin",
    "area_shiga-nara-wakayama",
    "area_chugoku-shikoku",
    "area_kyushu-okinawa",
]

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan", "臺灣", "台北", "台東"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _parse_dates(term_text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse '2026年3月14日（Sa）〜6月14日（Su）' → (start, end)."""
    m = re.match(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日[^〜～]*[〜～](\d{1,2})月(\d{1,2})日",
        term_text,
    )
    if m:
        y = int(m.group(1))
        try:
            start = datetime(y, int(m.group(2)), int(m.group(3)))
            end_m, end_d = int(m.group(4)), int(m.group(5))
            end_y = y if end_m >= int(m.group(2)) else y + 1
            end = datetime(end_y, end_m, end_d)
            return start, end
        except ValueError:
            pass
    # Single date fallback
    m2 = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", term_text)
    if m2:
        try:
            return datetime(int(m2.group(1)), int(m2.group(2)), int(m2.group(3))), None
        except ValueError:
            pass
    return None, None


def _event_id_from_href(href: str) -> Optional[str]:
    m = re.search(r"/event/(\d+)", href)
    return m.group(1) if m else None


class InternetMuseumScraper(BaseScraper):
    """Scrapes Taiwan-related exhibitions from アイエム（インターネットミュージアム）."""

    SOURCE_NAME = "internet_museum"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })

    def _scrape_region(self, area: str) -> list[Event]:
        url = f"{BASE_URL}/schedule/{YEAR}/{area}"
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("museum.or.jp %s failed: %s", area, exc)
            return []

        soup = BeautifulSoup(resp.content, "html.parser")
        events: list[Event] = []

        for block in soup.select(".p-schedule_museum_event"):
            # Skip past events
            if "is-past" in (block.get("class") or []):
                continue

            a = block.select_one(".p-schedule_museum_event_head_name")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")

            if not _is_taiwan(title):
                continue

            event_id = _event_id_from_href(href)
            source_id = f"internet_museum_{event_id}" if event_id else f"internet_museum_{hash(title) & 0xFFFFFF}"
            source_url = urljoin(BASE_URL, href)

            term_el = block.select_one(".p-schedule_museum_event_term")
            term_text = term_el.get_text(strip=True) if term_el else ""
            start_date, end_date = _parse_dates(term_text)

            # Location from museum name in the parent section
            museum_el = block.find_previous("h2")
            museum_name = museum_el.get_text(strip=True) if museum_el else ""

            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=source_url,
                original_language="ja",
                name_ja=title,
                raw_title=title,
                raw_description=f"{museum_name}\n{term_text}" if museum_name else term_text,
                description_ja=None,
                category=["art"],
                start_date=start_date,
                end_date=end_date,
                location_name=museum_name or "日本各地美術館",
                location_address="",
            )
            events.append(event)
            logger.info("Internet Museum Taiwan: %s (%s)", title, area)

        return events

    def scrape(self) -> list[Event]:
        all_events: list[Event] = []
        seen_ids: set[str] = set()

        for area in REGION_AREAS:
            region_events = self._scrape_region(area)
            for ev in region_events:
                if ev.source_id not in seen_ids:
                    seen_ids.add(ev.source_id)
                    all_events.append(ev)
            time.sleep(0.5)

        logger.info("Internet Museum total Taiwan: %d", len(all_events))
        return all_events
