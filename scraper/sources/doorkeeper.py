"""
Scraper for Doorkeeper — Japanese community event platform.

Uses the public Doorkeeper REST API (no authentication required).
API docs: https://www.doorkeeper.jp/developers/api

Strategy:
  1. Call GET https://api.doorkeeper.jp/events?q={keyword}&locale=ja for each keyword
  2. Paginate until empty page (max MAX_PAGES per keyword)
  3. Deduplicate by event ID across all keyword queries
  4. Filter to Tokyo area by address / venue_name
  5. source_id = "doorkeeper_{id}" (stable — uses platform's numeric event ID)
"""

import logging
import re
from datetime import datetime
from typing import Optional

import requests

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

API_BASE = "https://api.doorkeeper.jp"

# Multiple keyword passes to maximise recall
SEARCH_QUERIES = ["台湾", "Taiwan", "台灣"]

PER_PAGE = 100   # Doorkeeper's max per_page
MAX_PAGES = 5

# Tokyo markers — only use strings that uniquely identify Tokyo to avoid false
# positives from same-name wards in other prefectures (e.g. 神戸市中央区).
_TOKYO_MARKERS = {
    "東京都",
    "東京",          # catches "東京都", "東京23区", "東京都新宿区" etc.
    "新宿区", "千代田区", "港区", "渋谷区", "豊島区", "台東区",
    "品川区", "目黒区", "世田谷区", "中野区", "杉並区", "練馬区",
    "板橋区", "北区", "荒川区", "足立区", "葛飾区", "江戸川区",
    "江東区", "墨田区", "文京区", "大田区",
}


def _is_tokyo(address: Optional[str], venue: Optional[str] = None) -> bool:
    """Return True if address or venue contains a known Tokyo marker."""
    combined = (address or "") + " " + (venue or "")
    return any(m in combined for m in _TOKYO_MARKERS)


def _parse_dt(iso: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime string to a naive datetime (UTC preserved)."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def _strip_html(html: Optional[str]) -> str:
    """Remove HTML tags and return plain text."""
    if not html:
        return ""
    return re.sub(r"<[^>]+>", "", html).strip()


class DoorkeeperScraper(BaseScraper):
    """Scrapes Taiwan-related Tokyo events from Doorkeeper via public API."""

    SOURCE_NAME = "doorkeeper"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "TokyoTaiwanRadar/1.0 (+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)",
            }
        )

    def scrape(self) -> list[Event]:
        seen_ids: set[int] = set()
        raw_events: list[dict] = []

        for query in SEARCH_QUERIES:
            for page in range(1, MAX_PAGES + 1):
                params = {
                    "q": query,
                    "locale": "ja",
                    "per_page": PER_PAGE,
                    "page": page,
                }
                try:
                    resp = self._session.get(
                        f"{API_BASE}/events", params=params, timeout=15
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    logger.warning(
                        "Doorkeeper API error (query=%s page=%d): %s",
                        query, page, exc,
                    )
                    break

                if not data:
                    break  # No more results on this page

                new_items = 0
                for item in data:
                    e = item.get("event", {})
                    eid = e.get("id")
                    if eid and eid not in seen_ids:
                        seen_ids.add(eid)
                        raw_events.append(e)
                        new_items += 1

                if len(data) < PER_PAGE:
                    break  # Last page for this keyword

        logger.info(
            "Doorkeeper: fetched %d unique raw events across all queries", len(raw_events)
        )

        events: list[Event] = []
        for e in raw_events:
            address = e.get("address") or ""
            venue = e.get("venue_name") or ""

            if not _is_tokyo(address, venue):
                continue

            start = _parse_dt(e.get("starts_at"))
            end = _parse_dt(e.get("ends_at"))

            if not start:
                logger.warning(
                    "Doorkeeper event id=%s has no starts_at; skipping", e.get("id")
                )
                continue

            title = (e.get("title") or "").strip()
            desc_text = _strip_html(e.get("description"))
            event_id = e.get("id")
            source_url = e.get("public_url") or f"https://doorkeeper.jp/events/{event_id}"

            # Prepend date per scraper convention
            date_prefix = f"開催日時: {start.strftime('%Y年%m月%d日')}\n\n"
            raw_description = date_prefix + desc_text

            events.append(
                Event(
                    source_name=self.SOURCE_NAME,
                    source_id=f"doorkeeper_{event_id}",
                    source_url=source_url,
                    original_language="ja",
                    name_ja=title,
                    raw_title=title,
                    raw_description=raw_description,
                    start_date=start,
                    end_date=end,
                    location_name=venue or None,
                    location_address=address or None,
                )
            )

        logger.info(
            "Doorkeeper: %d Tokyo Taiwan events after location filter", len(events)
        )
        return events
