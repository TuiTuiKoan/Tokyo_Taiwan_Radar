"""
Scraper for Doorkeeper — Japanese community event platform.

Uses the public Doorkeeper REST API (no authentication required).
API docs: https://www.doorkeeper.jp/developers/api

Strategy:
  1. Call GET https://api.doorkeeper.jp/events?q={keyword}&locale=ja for each keyword
  2. Paginate until empty page (max MAX_PAGES per keyword)
  3. Deduplicate by event ID across all keyword queries
  4. Accept all Japan locations (no geographic filter)
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


_ONLINE_RE = re.compile(
    r'(?:online|オンライン|ライブ配信|配信のみ|[Zz][Oo][Oo][Mm])',
)


def _normalize_location_name(venue: Optional[str]) -> Optional[str]:
    """Return 'オンライン' if venue contains an online marker; else the raw value."""
    if venue and _ONLINE_RE.search(venue):
        return 'オンライン'
    return venue or None


def _normalize_location_address(venue: Optional[str], address: Optional[str]) -> Optional[str]:
    """Return None for online events; else the raw address."""
    if venue and _ONLINE_RE.search(venue):
        return None
    return address or None


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
                    location_name=_normalize_location_name(venue),
                    location_address=_normalize_location_address(venue, address),
                )
            )

        logger.info(
            "Doorkeeper: %d Taiwan events (Japan-wide)", len(events)
        )
        return events
