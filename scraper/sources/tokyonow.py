"""
Scraper for Tokyo Now (tokyonow.tokyo) — Japan's Tokyo event listing.

Uses the Tribe Events WP REST API (no Playwright needed).
Fetches all future events in pages of 50, filters by Taiwan keywords
in title or description, and returns matching events.

Strategy:
  1. GET /wp-json/tribe/events/v1/events?per_page=50&start_date=<today>&page=N
  2. Paginate through total_pages
  3. Filter: title or description contains Taiwan keyword
  4. source_id = "tokyonow_{event_id}" (numeric WordPress post ID — stable)

Taiwan keyword filter:
  ["台湾", "Taiwan", "臺灣"]
  Conservative: avoids 台東区 false positives while catching genuine events.
"""

import html as html_lib
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://tokyonow.tokyo"
API_URL = f"{BASE_URL}/wp-json/tribe/events/v1/events"
SOURCE_NAME = "tokyonow"

# Taiwan relevance keywords — title OR description must contain at least one
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]

# Request delay between pages (seconds)
_PAGE_DELAY = 1.0

JST = timezone(timedelta(hours=9))


def _strip_html(raw: str) -> str:
    """Strip HTML tags and normalise whitespace."""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html_lib.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_api_date(dt_str: str) -> Optional[datetime]:
    """Parse API date string '2026-02-06 11:00:00' as JST-aware datetime."""
    if not dt_str:
        return None
    try:
        naive = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return naive.replace(tzinfo=JST)
    except ValueError:
        logger.warning("Cannot parse date: %r", dt_str)
        return None


def _is_taiwan_related(title: str, description: str) -> bool:
    """Return True if title or description contains a Taiwan keyword."""
    combined = title + " " + description
    return any(kw in combined for kw in _TAIWAN_KEYWORDS)


class TokyoNowScraper(BaseScraper):
    """Scrapes Taiwan-related events from tokyonow.tokyo via Tribe Events REST API."""

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        today = datetime.now(JST).strftime("%Y-%m-%d")
        events: list[Event] = []

        # Fetch first page to get total_pages
        first = self._fetch_page(today, 1)
        if not first:
            return events

        total_pages = first.get("total_pages", 1)
        logger.info("TokyoNow: total_pages=%d, start_date=%s", total_pages, today)

        all_api_events = list(first.get("events", []))

        for page_num in range(2, total_pages + 1):
            time.sleep(_PAGE_DELAY)
            data = self._fetch_page(today, page_num)
            if not data:
                break
            all_api_events.extend(data.get("events", []))

        logger.info("TokyoNow: fetched %d total events", len(all_api_events))

        for ev in all_api_events:
            event = self._parse_event(ev)
            if event:
                events.append(event)

        logger.info("TokyoNow: %d Taiwan-related events", len(events))
        return events

    def _fetch_page(self, start_date: str, page: int) -> Optional[dict]:
        """Fetch a single page from the Tribe Events API."""
        try:
            resp = requests.get(
                API_URL,
                params={"per_page": 50, "start_date": start_date, "page": page},
                timeout=20,
                headers={"User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyo-taiwan-radar.vercel.app)"},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("TokyoNow: API fetch error page=%d: %s", page, exc)
            return None

    def _parse_event(self, ev: dict) -> Optional[Event]:
        """Parse a single Tribe Events API response object into an Event."""
        event_id = ev.get("id")
        if not event_id:
            return None

        title = _strip_html(ev.get("title", ""))
        desc_html = ev.get("description", "")
        desc_text = _strip_html(desc_html)

        # Taiwan relevance gate
        if not _is_taiwan_related(title, desc_text):
            return None

        source_id = f"tokyonow_{event_id}"
        source_url = ev.get("url", f"{BASE_URL}/event/{event_id}/")

        start_date = _parse_api_date(ev.get("start_date", ""))
        end_date = _parse_api_date(ev.get("end_date", ""))
        if start_date is None:
            logger.warning("TokyoNow: no start_date for event %s, skipping", source_id)
            return None
        if end_date is None:
            end_date = start_date

        # Venue
        venue_obj = ev.get("venue") or {}
        location_name = venue_obj.get("venue") or None
        location_address = venue_obj.get("address") or None

        # Cost
        cost_str = (ev.get("cost") or "").strip()
        is_paid: Optional[bool] = None
        if cost_str:
            if re.search(r"[¥￥0-9]", cost_str) and "無料" not in cost_str:
                is_paid = True
            elif "無料" in cost_str or cost_str == "0":
                is_paid = False
        else:
            cost_details = ev.get("cost_details", {})
            if cost_details.get("values"):
                is_paid = True

        # Build raw_description with date prefix
        date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
        if end_date and end_date.date() != start_date.date():
            date_prefix += f" ～ {end_date.strftime('%Y年%m月%d日')}"
        date_prefix += "\n\n"
        raw_description = date_prefix + desc_text

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=source_url,
            original_language="ja",
            name_ja=title or None,
            raw_title=title or None,
            raw_description=raw_description,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=location_address,
            is_paid=is_paid,
            price_info=cost_str or None,
        )
