"""
Scraper for Connpass — Japanese tech/community event platform.

Requires the CONNPASS_API_KEY environment variable (Connpass API v2).
If the key is absent the scraper logs a warning and returns no events —
the daily pipeline continues without interruption.

How to obtain a key:
  https://connpass.com/about/api/

API docs: https://connpass.com/about/api/v2/

Strategy:
  1. GET https://connpass.com/api/v2/events/ for each Taiwan keyword
     with prefecture=tokyo to pre-filter server-side
  2. Paginate using start= until results are exhausted (max MAX_PAGES per keyword)
  3. Deduplicate across keyword passes by platform event ID
  4. source_id = "connpass_{id}" (stable — uses platform's numeric event ID)
"""

import logging
import os
import re
from datetime import datetime
from typing import Optional

import requests

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

API_BASE = "https://connpass.com/api/v2"

# Multiple keyword passes — each is an AND condition within the title/description/address
SEARCH_KEYWORDS = ["台湾", "Taiwan", "台灣"]

COUNT = 100   # max per request (Connpass cap)
MAX_PAGES = 5  # safety ceiling per keyword


def _parse_dt(iso: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime string to a naive datetime."""
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


class ConnpassScraper(BaseScraper):
    """Scrapes Taiwan-related Tokyo events from Connpass via API v2.

    Silently skips (returns []) if CONNPASS_API_KEY is not set.
    """

    SOURCE_NAME = "connpass"

    def __init__(self) -> None:
        self._api_key = os.environ.get("CONNPASS_API_KEY", "")
        self._session = requests.Session()
        if self._api_key:
            self._session.headers.update(
                {
                    "X-API-Key": self._api_key,
                    "Accept": "application/json",
                }
            )

    def scrape(self) -> list[Event]:
        if not self._api_key:
            logger.warning(
                "CONNPASS_API_KEY not set — skipping Connpass scraper. "
                "Obtain a key at https://connpass.com/about/api/ and add to scraper/.env"
            )
            return []

        seen_ids: set[int] = set()
        events: list[Event] = []

        for keyword in SEARCH_KEYWORDS:
            for page_num in range(1, MAX_PAGES + 1):
                start_pos = (page_num - 1) * COUNT + 1
                params = {
                    "keyword": keyword,
                    "prefecture": "tokyo",
                    "count": COUNT,
                    "start": start_pos,
                    "order": 2,  # 開催日時順
                }
                try:
                    resp = self._session.get(
                        f"{API_BASE}/events/", params=params, timeout=15
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    logger.warning(
                        "Connpass API error (keyword=%s start=%d): %s",
                        keyword, start_pos, exc,
                    )
                    break

                page_events = data.get("events", [])
                if not page_events:
                    break

                for e in page_events:
                    eid = e.get("id")
                    if not eid or eid in seen_ids:
                        continue
                    seen_ids.add(eid)

                    start_dt = _parse_dt(e.get("started_at"))
                    end_dt = _parse_dt(e.get("ended_at"))

                    if not start_dt:
                        logger.warning(
                            "Connpass event id=%s has no started_at; skipping", eid
                        )
                        continue

                    title = (e.get("title") or "").strip()
                    catch = (e.get("catch") or "").strip()
                    desc_text = _strip_html(e.get("description"))

                    # Build raw_description per convention
                    date_prefix = f"開催日時: {start_dt.strftime('%Y年%m月%d日')}\n\n"
                    raw_description = date_prefix
                    if catch:
                        raw_description += f"{catch}\n\n"
                    raw_description += desc_text

                    source_url = (
                        e.get("url") or f"https://connpass.com/event/{eid}/"
                    )

                    events.append(
                        Event(
                            source_name=self.SOURCE_NAME,
                            source_id=f"connpass_{eid}",
                            source_url=source_url,
                            original_language="ja",
                            name_ja=title,
                            raw_title=title,
                            raw_description=raw_description,
                            start_date=start_dt,
                            end_date=end_dt,
                            location_name=e.get("place") or None,
                            location_address=e.get("address") or None,
                        )
                    )

                if data.get("results_returned", 0) < COUNT:
                    break  # Last page for this keyword

        logger.info("Connpass: %d Taiwan Tokyo events found", len(events))
        return events
