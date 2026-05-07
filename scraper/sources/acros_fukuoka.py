"""
Scraper for アクロス福岡 (ACROS Fukuoka), Fukuoka.

Strategy:
  1. Fetch event listing pages: /events/?&page=N (10 events per page)
  2. Cards: ul#event_list li — each contains div.text h2 (title) + time (date range) + a[href]
  3. Pre-filter by Taiwan keywords in listing title → fetch detail page for matches
  4. source_id: "acros_fukuoka_{event_id}" from /events/15511.html → 15511
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

BASE_URL = "https://www.acros.or.jp"
LISTING_URL = f"{BASE_URL}/events/"
MAX_PAGES = 20  # 163 events / 10 per page ≈ 17 pages; cap at 20
LOCATION_NAME = "アクロス福岡"
LOCATION_ADDRESS = "福岡県福岡市中央区天神1丁目1番1号"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan", "臺灣"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _parse_date_range(time_text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse '2026年4月17日(金)～5月31日(日) 08:00～22:00' → (start, end)."""
    m = re.match(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日[^〜～]*[〜～](\d{1,2})月(\d{1,2})日",
        time_text,
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
    m2 = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", time_text)
    if m2:
        try:
            start = datetime(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
            return start, None
        except ValueError:
            pass
    return None, None


def _parse_event_id(href: str) -> Optional[str]:
    m = re.search(r"(?:^|/)(\d+)\.html", href)
    return m.group(1) if m else None


class AcrosFukuokaScraper(BaseScraper):
    """Scrapes Taiwan-related events from アクロス福岡 (Fukuoka)."""

    SOURCE_NAME = "acros_fukuoka"

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
            return BeautifulSoup(resp.content, "html.parser")
        except Exception as exc:
            logger.warning("GET %s failed: %s", url, exc)
            return None

    def _scrape_listing_page(self, page: int) -> list[dict]:
        """Return raw card dicts from one listing page."""
        url = f"{LISTING_URL}?&page={page}"
        soup = self._get(url)
        if not soup:
            return []
        cards = []
        for li in soup.select("ul#event_list li"):
            a = li.select_one("a[href]")
            if not a:
                continue
            href = a.get("href", "")
            event_id = _parse_event_id(href)
            if not event_id:
                continue
            detail_url = urljoin(LISTING_URL, href)
            title_el = li.select_one("div.text h2")
            time_el = li.select_one("div.text time")
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
            time_text = time_el.get_text(strip=True) if time_el else ""
            cards.append({
                "event_id": event_id,
                "detail_url": detail_url,
                "title": title,
                "time_text": time_text,
            })
        return cards

    def _scrape_detail(self, url: str) -> dict:
        result = {"full_text": "", "description": ""}
        soup = self._get(url)
        if not soup:
            return result
        result["full_text"] = soup.get_text(" ", strip=True)
        content = soup.select_one(".event_detail") or soup.select_one("main") or soup
        paras = [p.get_text(strip=True) for p in content.select("p") if len(p.get_text(strip=True)) > 20]
        result["description"] = "\n".join(paras[:5])
        return result

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        seen_ids: set[str] = set()

        for page in range(1, MAX_PAGES + 1):
            cards = self._scrape_listing_page(page)
            if not cards:
                logger.info("No cards on page %d — stopping", page)
                break

            for card in cards:
                event_id = card["event_id"]
                if event_id in seen_ids:
                    continue
                seen_ids.add(event_id)

                # Pre-filter: check title first
                if not _is_taiwan(card["title"]):
                    continue

                # Taiwan title found — fetch detail for description
                time.sleep(0.3)
                detail = self._scrape_detail(card["detail_url"])

                start_date, end_date = _parse_date_range(card["time_text"])
                raw_desc = detail["description"] or card["title"]
                if card["time_text"]:
                    raw_desc = f"日程: {card['time_text']}\n\n" + raw_desc

                event = Event(
                    source_name=self.SOURCE_NAME,
                    source_id=f"acros_fukuoka_{event_id}",
                    source_url=card["detail_url"],
                    original_language="ja",
                    name_ja=card["title"],
                    raw_title=card["title"],
                    raw_description=raw_desc,
                    description_ja=detail["description"] or None,
                    category=["art"],
                    start_date=start_date,
                    end_date=end_date,
                    location_name=LOCATION_NAME,
                    location_address=LOCATION_ADDRESS,
                )
                events.append(event)
                logger.info("Found Taiwan event: %s", card["title"])

        logger.info("Total Taiwan events: %d", len(events))
        return events
