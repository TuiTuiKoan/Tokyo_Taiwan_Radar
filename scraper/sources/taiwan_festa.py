"""
Scraper for 台湾フェスタ / 台湾祭 (taiwanfesta.com).

"台湾フェスタ" is a recurring Taiwan food-and-culture festival held at major
venues across Japan — Tokyo, Yokohama, Kyoto, Fukuoka, etc.

Strategy:
  1. Fetch the homepage (static HTML rendered by UIkit)
  2. Extract all .uk-card-default cards — each card is an event
  3. The card is wrapped in a parent <a href="./SLUG/"> element
  4. Title: .uk-card-title
  5. Dates: .card-text (format: "(YYYY/MM/DD 〜 YYYY/MM/DD)\n@場所名")
  6. Location: .card-text small (prefixed with @)
  7. source_id = "taiwanfesta_{slug}_{YYYYMMDD}" — slug + start date for stability

No Playwright needed — the site is server-rendered static HTML.
Playwright returns 403; requests with browser-like headers returns 200.

All events on this site are Taiwan festivals — no keyword filtering required.
"""

import re
import logging
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.taiwanfesta.com"
HOMEPAGE_URL = f"{BASE_URL}/"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}

# Match date pattern within card-text: "(YYYY/MM/DD 〜 YYYY/MM/DD)"
_DATE_RANGE_RE = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")


def _parse_dates(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Extract start and end dates from card text like '(2026/04/01 〜 2026/05/10)'."""
    matches = _DATE_RANGE_RE.findall(text)
    if not matches:
        return None, None
    try:
        start = datetime(int(matches[0][0]), int(matches[0][1]), int(matches[0][2]))
    except ValueError:
        return None, None
    end = start
    if len(matches) >= 2:
        try:
            end = datetime(int(matches[1][0]), int(matches[1][1]), int(matches[1][2]))
        except ValueError:
            pass
    return start, end


def _slug_from_href(href: str) -> Optional[str]:
    """Extract slug from relative href like './202408-yokohama/' → '202408-yokohama'."""
    # Remove leading ./ and trailing /
    slug = href.strip().lstrip("./").rstrip("/")
    if slug:
        return slug
    return None


class TaiwanFestaScraper(BaseScraper):
    """Scrapes 台湾フェスタ events across Japan from taiwanfesta.com."""

    SOURCE_NAME = "taiwan_festa"

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        _retry = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        self._session.mount("https://", HTTPAdapter(max_retries=_retry))
        self._session.mount("http://", HTTPAdapter(max_retries=_retry))

    def scrape(self) -> list[Event]:
        try:
            resp = self._session.get(HOMEPAGE_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("taiwan_festa: failed to fetch homepage: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".uk-card-default")
        logger.info("taiwan_festa: found %d cards on homepage", len(cards))

        events: list[Event] = []
        seen_ids: set[str] = set()

        for card in cards:
            try:
                event = self._parse_card(card)
                if event and event.source_id not in seen_ids:
                    seen_ids.add(event.source_id)
                    events.append(event)
            except Exception as exc:
                logger.warning("taiwan_festa: failed to parse card: %s", exc)

        logger.info("taiwan_festa: collected %d events", len(events))
        return events

    def _parse_card(self, card: BeautifulSoup) -> Optional[Event]:
        # Title
        title_el = card.select_one(".uk-card-title")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if not title:
            return None

        # Date + location from .card-text
        card_text_el = card.select_one(".card-text")
        card_text = card_text_el.get_text("\n", strip=True) if card_text_el else ""
        start_date, end_date = _parse_dates(card_text)

        # Location: small element inside .card-text, e.g. "@横浜赤レンガ倉庫"
        location = None
        location_el = card_text_el.select_one("small") if card_text_el else None
        if location_el:
            location = location_el.get_text(strip=True).lstrip("@").strip() or None

        # Source URL: parent <a> element
        parent_a = card.find_parent("a")
        href = parent_a.get("href", "") if parent_a else ""
        if not href:
            return None
        source_url = urljoin(HOMEPAGE_URL, href)

        # Source ID: slug + start date for uniqueness
        slug = _slug_from_href(href)
        if not slug:
            return None
        date_part = start_date.strftime("%Y%m%d") if start_date else "nodate"
        source_id = f"taiwanfesta_{slug}_{date_part}"

        # Build raw_description with event date prepended
        date_str = start_date.strftime("%Y年%m月%d日") if start_date else ""
        raw_desc_parts = []
        if date_str:
            raw_desc_parts.append(f"開催日時: {date_str}")
        if end_date and end_date != start_date:
            raw_desc_parts.append(f"終了日: {end_date.strftime('%Y年%m月%d日')}")
        if location:
            raw_desc_parts.append(f"会場: {location}")
        raw_desc_parts.append(title)
        raw_description = "\n".join(raw_desc_parts)

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=source_url,
            original_language="ja",
            name_ja=title,
            raw_title=title,
            raw_description=raw_description,
            category=["taiwan_japan", "lifestyle_food"],
            start_date=start_date,
            end_date=end_date,
            location_name=location,
            location_address=None,
        )
