"""
Scraper for こくちーずプロ (Kokuchpro) — Japan's largest free event/seminar platform.

Strategy:
  1. Fetch paginated search results for keyword "台湾" across three prefectures:
     東京都, 京都府, 大阪府.
     Listing URL pattern: https://www.kokuchpro.com/s/q-台湾/area-<AREA>/?page=N
  2. For each card extract: date from .value-title ISO attribute, venue from
     .event_place, title from .event_name, short desc from .event_description.
  3. Taiwan keyword check on title + short description (guard against false
     positives where 台湾 matches an unrelated field).
  4. Fetch detail page for events within DETAIL_CUTOFF_DAYS past + all future
     events → full description from .event_page_description.editor_html,
     full address from hCard .adr microformat.
     Older events use card-level data only (less important, keeps run fast).
  5. source_id = URL slug between /event/ and trailing slash.
"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://www.kokuchpro.com"
# Search URLs per prefecture (Taiwan keyword, area-scoped)
SEARCH_URLS = [
    "https://www.kokuchpro.com/s/q-%E5%8F%B0%E6%B9%BE/area-%E6%9D%B1%E4%BA%AC%E9%83%BD/",  # 東京都
    "https://www.kokuchpro.com/s/q-%E5%8F%B0%E6%B9%BE/area-%E4%BA%AC%E9%83%BD%E5%BA%9C/",  # 京都府
    "https://www.kokuchpro.com/s/q-%E5%8F%B0%E6%B9%BE/area-%E5%A4%A7%E9%98%AA%E5%BA%9C/",  # 大阪府
]
MAX_PAGES = 10          # safety ceiling per area
REQUEST_DELAY = 0.4     # seconds between requests (polite crawl)
DETAIL_CUTOFF_DAYS = 60  # fetch detail page only for events ≤ this many days ago

TAIWAN_KEYWORDS = ["台湾", "Taiwan", "台灣", "タイワン"]

_SLUG_RE = re.compile(r"/event/([^/]+)/")

# Regex for end date from text like "2026年5月31日(日) 00:00〜2026年7月5日(日) 22:59"
_END_DATE_RE = re.compile(r"〜(\d{4}年\d{1,2}月\d{1,2}日)")

_ONLINE_RE = re.compile(
    r"(?:online|オンライン|ライブ配信|[Zz][Oo][Oo][Mm]|Zoom|web配信)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_iso(iso: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime string (with timezone offset) to naive JST datetime."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
        return dt.replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def _parse_end_date_text(text: str, start_date: datetime) -> Optional[datetime]:
    """Try to extract end date from date-range text like '〜2026年7月5日(日)'."""
    m = _END_DATE_RE.search(text)
    if not m:
        return None
    raw = m.group(1)  # e.g. "2026年7月5日"
    try:
        raw = re.sub(r"[年月]", "-", raw).replace("日", "").strip()
        # raw is now "2026-7-5"
        parts = raw.split("-")
        return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def _is_taiwan_relevant(title: str, short_desc: str) -> bool:
    combined = title + " " + short_desc
    return any(kw in combined for kw in TAIWAN_KEYWORDS)


def _normalize_online(text: str) -> str:
    """Return 'オンライン' if the venue contains an online marker, else the text."""
    if _ONLINE_RE.search(text):
        return "オンライン"
    return text


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


class KokuchproScraper(BaseScraper):
    """Scrapes Taiwan-related events from こくちーずプロ — covers 東京都, 京都府, 大阪府."""

    SOURCE_NAME = "kokuchpro"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "ja,en;q=0.9",
            }
        )

    def scrape(self) -> list[Event]:
        cards = self._fetch_all_cards()
        logger.info("KokuchproScraper: %d Taiwan-relevant cards after keyword filter", len(cards))

        events: list[Event] = []
        cutoff = datetime.now() - timedelta(days=DETAIL_CUTOFF_DAYS)

        for card in cards:
            try:
                event = self._build_event(card, cutoff)
                if event:
                    events.append(event)
            except Exception as exc:
                logger.warning(
                    "KokuchproScraper: failed to process %s — %s",
                    card.get("url", "?"),
                    exc,
                )

        logger.info("KokuchproScraper: %d events", len(events))
        return events

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def _fetch_all_cards(self) -> list[dict]:
        all_cards: list[dict] = []
        seen_slugs: set[str] = set()

        for search_url in SEARCH_URLS:
            for page in range(1, MAX_PAGES + 1):
                url = search_url if page == 1 else f"{search_url}?page={page}"
                try:
                    resp = self._session.get(url, timeout=20)
                    resp.raise_for_status()
                except Exception as exc:
                    logger.warning("KokuchproScraper: listing page %d failed — %s", page, exc)
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                items = soup.select(".event_item")
                if not items:
                    break

                for item in items:
                    card = self._parse_card(item)
                    if card and card["slug"] not in seen_slugs:
                        seen_slugs.add(card["slug"])
                        all_cards.append(card)

                # Check if next page exists in pagination links
                next_exists = bool(
                    soup.select_one(f"a[href*='?page={page + 1}']")
                )
                if not next_exists:
                    break

                time.sleep(REQUEST_DELAY)

        logger.info("KokuchproScraper: collected %d unique cards from listing", len(all_cards))
        return all_cards

    def _parse_card(self, item) -> Optional[dict]:
        # Title + URL
        name_el = item.select_one("a.event_name")
        if not name_el:
            return None
        title = name_el.get_text(strip=True)
        url = name_el.get("href", "")
        if not url.startswith("http"):
            url = BASE_URL + url

        # Stable slug → source_id
        m = _SLUG_RE.search(url)
        if not m:
            return None
        slug = m.group(1)

        # ISO start datetime from value-title attribute
        vt = item.select_one(".value-title")
        date_iso = vt.get("title") if vt else None

        # dtstart raw text (for end-date range parsing)
        dtstart_el = item.select_one(".dtstart")
        date_text = dtstart_el.get_text(separator=" ", strip=True) if dtstart_el else ""

        # Venue from card
        place_el = item.select_one(".event_place")
        venue_card = place_el.get_text(strip=True) if place_el else None

        # Short description from card
        desc_el = item.select_one(".event_description.description")
        short_desc = desc_el.get_text(strip=True) if desc_el else ""

        # Taiwan keyword guard
        if not _is_taiwan_relevant(title, short_desc):
            return None

        return {
            "url": url,
            "slug": slug,
            "title": title,
            "date_iso": date_iso,
            "date_text": date_text,
            "venue_card": venue_card,
            "short_desc": short_desc,
        }

    # ------------------------------------------------------------------
    # Event building
    # ------------------------------------------------------------------

    def _build_event(self, card: dict, cutoff: datetime) -> Optional[Event]:
        start_date = _parse_iso(card["date_iso"])
        if not start_date:
            logger.warning(
                "KokuchproScraper: no start_date for %s — skipping", card["url"]
            )
            return None

        # End date: try to parse from text range, else = start_date
        end_date = _parse_end_date_text(card["date_text"], start_date) or start_date

        # Decide whether to fetch detail page
        fetch_detail = start_date >= cutoff
        full_desc: str = card["short_desc"]
        location_name: Optional[str] = card["venue_card"]
        location_address: Optional[str] = card["venue_card"]

        if fetch_detail:
            time.sleep(REQUEST_DELAY)
            detail_data = self._fetch_detail(card["url"])
            if detail_data:
                if detail_data["description"]:
                    full_desc = detail_data["description"]
                if detail_data["venue"]:
                    location_name = detail_data["venue"]
                if detail_data["address"]:
                    location_address = detail_data["address"]
                elif detail_data["venue"]:
                    location_address = detail_data["venue"]

        # Normalize online events
        if location_name:
            location_name = _normalize_online(location_name)
        if location_address:
            location_address = _normalize_online(location_address)

        # raw_description: prepend date hint per convention
        date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n\n"
        raw_description = date_prefix + full_desc

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=card["slug"],
            source_url=card["url"],
            original_language="ja",
            name_ja=card["title"],
            raw_title=card["title"],
            raw_description=raw_description,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=location_address,
        )

    def _fetch_detail(self, url: str) -> Optional[dict]:
        """Fetch event detail page and return description + address."""
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("KokuchproScraper: detail fetch failed for %s — %s", url, exc)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Full description from editor content div
        desc_el = soup.select_one(".event_page_description.editor_html")
        description = (
            desc_el.get_text(separator="\n", strip=True) if desc_el else None
        )

        # Venue name from hCard .fn.org microformat
        venue_el = soup.select_one(".fn.org")
        venue = venue_el.get_text(strip=True) if venue_el else None

        # Full address from hCard .adr microformat
        adr_el = soup.select_one(".adr")
        address = (
            adr_el.get_text(separator=" ", strip=True) if adr_el else None
        )

        return {
            "description": description,
            "venue": venue,
            "address": address,
        }
