"""
Scraper for 丸広百貨店 (maruhiro.co.jp) event calendar (Taiwan-themed events).

All event data is on the list pages — detail pages contain only a JPEG image.
No JSON API or Playwright needed; requests + BeautifulSoup only.

List page structure:
  https://www.maruhiro.co.jp/top/events         (page 1)
  https://www.maruhiro.co.jp/top/events/page:N  (pages 2..N)

Each page renders up to ~15 cards:
  <div class="card card-child" data-url="/events/view/15625">
    <h3 class="card-title p-t">
      <a href="/events/view/15625">台湾フェア</a>
    </h3>
    <p class="card-text m-a-0">
      ●2026年4月29日(水・祝)～2026年5月4日(月・祝)まで
      ●5階催場〈最終日は午後5時閉場〉　開催店舗: 川越店
    </p>
  </div>

source_id = maruhiro_{event_id}
  event_id: integer from data-url="/events/view/{id}" — stable across runs.

Stores confirmed 2026-04-29:
  川越店, 飯能店, 入間店, まるひろ上尾SC, まるひろ南浦和SC
  (Plus satellite stores with no dedicated event page — mapped to "川越店" as fallback)

Historical Taiwan events:
  - 台湾フェア (川越店, 2026-04-29〜2026-05-04) — confirmed
  - Seasonal pattern: GW (Apr/May) and autumn (Sep/Oct)
"""

import logging
import re
import time
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_NAME = "maruhiro"
BASE_URL = "https://www.maruhiro.co.jp"
LIST_URL = f"{BASE_URL}/top/events"
_MAX_PAGES = 20  # safety cap
_DELAY = 0.4  # seconds between page fetches

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "ja,en;q=0.9",
}

_TAIWAN_RE = re.compile(r"台湾|台灣|Taiwan|taiwan|🇹🇼", re.IGNORECASE)

# Date patterns in p.card-text:
#   ●2026年4月29日(水・祝)～2026年5月4日(月・祝)まで
#   ●2026年4月29日(水・祝)から
_DATE_RANGE_RE = re.compile(
    r"●(\d{4})年(\d{1,2})月(\d{1,2})日[^～\n]*～(\d{4})年(\d{1,2})月(\d{1,2})日"
)
_DATE_FROM_RE = re.compile(
    r"●(\d{4})年(\d{1,2})月(\d{1,2})日[^～\n]*から"
)

# Store name → (location_name, location_address)
_STORE_ADDRESS: dict[str, tuple[str, str]] = {
    "川越店":    ("まるひろ川越店",    "埼玉県川越市新富町2-6-1"),
    "飯能店":    ("まるひろ飯能店",    "埼玉県飯能市栄町24-4"),
    "入間店":    ("まるひろ入間店",    "埼玉県入間市豊岡1-6-12"),
    "上尾SC":   ("まるひろ上尾SC",   "埼玉県上尾市宮本町1-1"),
    "南浦和SC":  ("まるひろ南浦和SC",  "埼玉県さいたま市南区南本町1-7-4"),
}
# Fallback for satellite stores that host events
_DEFAULT_LOCATION = ("まるひろ川越店", "埼玉県川越市新富町2-6-1")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_dates(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Extract (start_date, end_date) from the card-text paragraph.

    Returns (None, None) when no date pattern is found (skip these cards).
    dedup_events in base.py calls .date() on start_date, so datetime is required.
    """
    m = _DATE_RANGE_RE.search(text)
    if m:
        sy, sm, sd, ey, em, ed = (int(x) for x in m.groups())
        return datetime(sy, sm, sd), datetime(ey, em, ed)

    m = _DATE_FROM_RE.search(text)
    if m:
        sy, sm, sd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(sy, sm, sd), None

    return None, None


def _parse_store(text: str) -> tuple[str, str]:
    """Extract (location_name, location_address) from card text.

    Looks for '開催店舗: {name}' and resolves via _STORE_ADDRESS.
    """
    m = re.search(r"開催店舗[:：]\s*(.+?)(?:\s*\.|$)", text.replace("\n", " "))
    if m:
        raw = m.group(1).strip()
        # Check each key as a substring (e.g. "南浦和SC" inside "まるひろ南浦和SC")
        for key, val in _STORE_ADDRESS.items():
            if key in raw:
                return val
    return _DEFAULT_LOCATION


def _build_raw_description(
    title: str,
    start: date,
    end: Optional[date],
    floor_info: str,
    store_text: str,
) -> str:
    """Build raw_description prepended with 開催日時 line."""
    date_str = f"{start.year}年{start.month}月{start.day}日"
    if end and end != start:
        date_str += f"〜{end.year}年{end.month}月{end.day}日"
    parts = [f"開催日時: {date_str}"]
    if floor_info:
        parts.append(floor_info)
    if store_text:
        parts.append(store_text)
    return "\n\n".join(parts)


def _get_max_page(soup: BeautifulSoup) -> int:
    """Parse pagination links to find the last page number."""
    max_pg = 1
    for a in soup.find_all("a", href=True):
        m = re.search(r"/top/events/page:(\d+)", a["href"])
        if m:
            n = int(m.group(1))
            if n > max_pg:
                max_pg = n
    return max_pg


def _extract_floor_info(card_text: str) -> str:
    """Extract floor/location hints like '5階催場〈最終日は午後5時閉場〉'."""
    # Lines starting with ● that are NOT the date line
    lines = [l.strip() for l in card_text.replace("●", "\n●").split("\n") if l.strip()]
    floor_parts = []
    for line in lines:
        if line.startswith("●") and not re.search(r"\d{4}年", line) and "開催店舗" not in line:
            floor_parts.append(line.lstrip("●").strip())
    return "　".join(floor_parts)


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


class MaruhiroScraper(BaseScraper):
    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        session = requests.Session()
        session.headers.update(_HEADERS)

        # Fetch page 1 and determine total pages
        soup = self._fetch_page(session, LIST_URL)
        if soup is None:
            return []

        max_page = min(_get_max_page(soup), _MAX_PAGES)
        logger.info("MaruhiroScraper: %d pages to scan", max_page)

        seen_ids: set[str] = set()
        events: list[Event] = []

        pages_soups = [(1, soup)] + [
            (pg, self._fetch_page(session, f"{LIST_URL}/page:{pg}"))
            for pg in range(2, max_page + 1)
        ]

        for pg, page_soup in pages_soups:
            if page_soup is None:
                continue
            page_events = self._parse_page(page_soup, seen_ids)
            logger.debug("Page %d: %d Taiwan events", pg, len(page_events))
            events.extend(page_events)

        logger.info("MaruhiroScraper: %d total Taiwan events", len(events))
        return events

    def _fetch_page(self, session: requests.Session, url: str) -> Optional[BeautifulSoup]:
        time.sleep(_DELAY)
        try:
            r = session.get(url, timeout=15)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
            return None

    def _parse_page(
        self, soup: BeautifulSoup, seen_ids: set[str]
    ) -> list[Event]:
        events: list[Event] = []
        for card in soup.select("div.card.card-child"):
            event = self._parse_card(card, seen_ids)
            if event:
                events.append(event)
        return events

    def _parse_card(
        self, card: BeautifulSoup, seen_ids: set[str]
    ) -> Optional[Event]:
        # --- event_id ---
        data_url = card.get("data-url", "")
        m = re.search(r"/events/view/(\d+)$", data_url)
        if not m:
            return None
        event_id = m.group(1)
        source_id = f"maruhiro_{event_id}"
        if source_id in seen_ids:
            return None
        seen_ids.add(source_id)

        # --- title ---
        title_a = card.select_one("h3 a")
        if not title_a:
            return None
        title = title_a.get_text(strip=True)
        if not title:
            return None

        # --- Taiwan filter ---
        if not _TAIWAN_RE.search(title):
            return None

        # --- date ---
        card_text_el = card.select_one("p.card-text")
        card_text = card_text_el.get_text(separator=" ", strip=True) if card_text_el else ""
        start_date, end_date = _parse_dates(card_text)
        if start_date is None:
            logger.debug("Skipping maruhiro_%s '%s': no date", event_id, title)
            return None

        # --- location ---
        location_name, location_address = _parse_store(card_text)

        # --- floor/extra info ---
        floor_info = _extract_floor_info(card_text)

        # --- raw_description ---
        raw_desc = _build_raw_description(
            title, start_date, end_date, floor_info, card_text
        )

        source_url = f"{BASE_URL}{data_url}"

        return Event(
            source_name=SOURCE_NAME,
            source_id=source_id,
            source_url=source_url,
            original_language="ja",
            raw_title=title,
            raw_description=raw_desc,
            name_ja=title,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=location_address,
            category=["lifestyle_food"],
            is_paid=None,
            is_active=True,
        )
