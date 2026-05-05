"""
Scraper for Walker+ (walkerplus.com) — nationwide Japanese event listing site
operated by KADOKAWA.

Strategy:
  1. Fetch paginated listings for three event categories:
       eg0117 (グルメ・フードフェス)  — highest Taiwan event density
       eg0118 (物産展・観光フェア)    — physical goods / tourism fairs
       eg0107 (美術展・博物展)        — art and museum exhibitions
  2. For each listing card, filter by Taiwan keywords in the event title.
  3. For Taiwan-relevant events, fetch the detail page to extract:
     start/end date, venue, location address, business hours, description.
  4. source_id = "walkerplus_" + area+event code from URL path
     (e.g. "walkerplus_ar0313e462812")

Robots.txt note:
  Crawl-delay: 3 applies only to ClaudeBot. General crawling is permitted.
  Prohibited paths: /release_list/, /release/, /press_list/, /press/
  Pagination URL pattern: /event_list/<category>/<page>.html (page ≥ 2)
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://www.walkerplus.com"

# (listing_url, default_category) pairs — scraped in order
CATEGORY_LISTINGS: list[tuple[str, list[str]]] = [
    (f"{BASE_URL}/event_list/eg0117/", ["lifestyle_food"]),  # グルメ・フードフェス
    (f"{BASE_URL}/event_list/eg0118/", ["retail"]),          # 物産展・観光フェア
    (f"{BASE_URL}/event_list/eg0107/", ["art"]),             # 美術展・博物展
]

MAX_PAGES = 5           # pages to scan per category (10 events/page → 50 events scanned)
REQUEST_DELAY = 1.0     # seconds between requests (polite crawl)

TAIWAN_KEYWORDS = ["台湾", "Taiwan", "台灣", "タイワン"]

# Extract area+event code from URL path: /event/ar0313e462812/ → ar0313e462812
_EVENT_CODE_RE = re.compile(r"/event/(ar\d+e\d+)/")

# Date range: "2026年4月4日(土)～5月31日(日)"  or  "2025年12月1日(月)～2026年3月31日(月)"
_DATE_RANGE_RE = re.compile(
    r"(\d{4})年(\d{1,2})月(\d{1,2})日[^\d～]*～[^\d]*(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日"
)
# Single date: "2026年5月3日(土)"
_DATE_SINGLE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")

# Disclaimer phrases to skip when collecting description paragraphs
_DISCLAIMER_RE = re.compile(
    r"掲載情報は|無断転載|自然災害|おでかけください|随時更新|変更となっている"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_taiwan_relevant(title: str) -> bool:
    return any(kw in title for kw in TAIWAN_KEYWORDS)


def _parse_date_text(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse a date range or single date string.

    Returns (start_date, end_date).  If only a single date is found,
    end_date equals start_date.  Returns (None, None) on failure.
    """
    # Try range pattern first
    m = _DATE_RANGE_RE.search(text)
    if m:
        start_year = int(m.group(1))
        start_month = int(m.group(2))
        start_day = int(m.group(3))
        # End year defaults to start year when omitted
        end_year = int(m.group(4)) if m.group(4) else start_year
        end_month = int(m.group(5))
        end_day = int(m.group(6))
        # Handle year wrap (e.g. Dec → Jan without explicit year)
        if m.group(4) is None and end_month < start_month:
            end_year = start_year + 1
        try:
            return (
                datetime(start_year, start_month, start_day),
                datetime(end_year, end_month, end_day),
            )
        except ValueError:
            pass

    # Fall back to single date
    m = _DATE_SINGLE_RE.search(text)
    if m:
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return dt, dt
        except ValueError:
            pass

    return None, None


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


class WalkerplusScraper(BaseScraper):
    """Scrapes Taiwan-related events from Walker+ — covers all of Japan."""

    SOURCE_NAME = "walkerplus"

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

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def scrape(self) -> list[Event]:
        all_events: list[Event] = []
        seen_ids: set[str] = set()
        for listing_url, default_category in CATEGORY_LISTINGS:
            events = self._scrape_category(listing_url, default_category, seen_ids)
            all_events.extend(events)
        logger.info("WalkerplusScraper: %d events total", len(all_events))
        return all_events

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def _scrape_category(
        self,
        listing_url: str,
        default_category: list[str],
        seen_ids: set[str],
    ) -> list[Event]:
        events: list[Event] = []

        for page in range(1, MAX_PAGES + 1):
            url = listing_url if page == 1 else f"{listing_url}{page}.html"
            try:
                resp = self._session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning(
                    "WalkerplusScraper: listing %s page %d failed — %s", listing_url, page, exc
                )
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("li.m-mainlist__item")
            if not cards:
                break

            has_event_cards = False
            for card in cards:
                links = card.select("a[href*='/event/ar']")
                if not links:
                    continue
                has_event_cards = True

                href = links[0].get("href", "")
                title = links[0].get_text(strip=True)

                if not _is_taiwan_relevant(title):
                    continue

                # Build absolute URL
                event_url = href if href.startswith("http") else BASE_URL + href

                # Extract stable source ID from URL
                m = _EVENT_CODE_RE.search(href)
                if not m:
                    continue
                source_id = f"walkerplus_{m.group(1)}"

                if source_id in seen_ids:
                    continue
                seen_ids.add(source_id)

                # Fallback data from listing card
                date_el = card.select_one(".m-mainlist-item-event__period")
                card_date_text = date_el.get_text(strip=True) if date_el else ""
                venue_el = card.select_one(".m-mainlist-item-event__place")
                card_venue = venue_el.get_text(strip=True) if venue_el else None

                time.sleep(REQUEST_DELAY)
                event = self._build_event(
                    event_url=event_url,
                    source_id=source_id,
                    title=title,
                    card_date_text=card_date_text,
                    card_venue=card_venue,
                    default_category=default_category,
                )
                if event:
                    events.append(event)

            if not has_event_cards:
                break

            time.sleep(REQUEST_DELAY)

        logger.info(
            "WalkerplusScraper: %d events from %s", len(events), listing_url
        )
        return events

    # ------------------------------------------------------------------
    # Detail page → Event
    # ------------------------------------------------------------------

    def _build_event(
        self,
        event_url: str,
        source_id: str,
        title: str,
        card_date_text: str,
        card_venue: Optional[str],
        default_category: list[str],
    ) -> Optional[Event]:
        """Fetch the event detail page and return a populated Event object."""
        try:
            resp = self._session.get(event_url, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(
                "WalkerplusScraper: detail fetch failed %s — %s", event_url, exc
            )
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # --- Title ---
        h1 = soup.select_one("h1.m-detailheader-heading__ttl")
        name_ja = h1.get_text(strip=True) if h1 else title

        # --- Date ---
        # p.m-detailheader__text holds the date range; span.m-detailheader__text is used for other fields
        date_el = soup.select_one("p.m-detailheader__text")
        start_date, end_date = _parse_date_text(date_el.get_text(strip=True)) if date_el else (None, None)
        if not start_date:
            start_date, end_date = _parse_date_text(card_date_text)
        if not start_date:
            logger.warning(
                "WalkerplusScraper: no start_date for %s — skipping", event_url
            )
            return None

        # --- Venue, location address, business hours ---
        location_name: Optional[str] = card_venue
        location_address: Optional[str] = None
        business_hours: Optional[str] = None

        for period_el in soup.select(".m-detailheader__period"):
            icon_el = period_el.select_one(".m-detailheader__icon")
            label = icon_el.get_text(strip=True) if icon_el else ""

            if "場所" in label:
                # Link order: [地域, 都道府県, 市区町村, 施設名]
                # Use all links under this block (not just m-detailheader-heading__link)
                loc_links = period_el.select("a")
                if len(loc_links) >= 2:
                    location_name = loc_links[-1].get_text(strip=True)
                    # Address = prefecture + ward/city (skip first region link and last venue link)
                    if len(loc_links) >= 3:
                        location_address = " ".join(
                            a.get_text(strip=True) for a in loc_links[1:-1]
                        )
                    else:
                        # Only 2 links: [prefecture, venue] — use prefecture as address
                        location_address = loc_links[0].get_text(strip=True)
                elif len(loc_links) == 1:
                    location_name = loc_links[0].get_text(strip=True)

            elif "開催時間" in label:
                text_el = period_el.select_one("span.m-detailheader__text")
                if text_el:
                    business_hours = text_el.get_text(strip=True)

        # Ensure location_address != location_name
        if location_address and location_name and location_address == location_name:
            location_address = None

        # --- Description ---
        # Collect <p> tags only from the event detail section (.m-detail__contents).
        # Avoids related-event widgets (.m-articleset--3 instances outside that container).
        raw_desc_parts: list[str] = []
        detail_contents = soup.select_one(".m-detail__contents")
        source_el = detail_contents or soup.select_one("main, #main, .l-main")
        if source_el:
            for p in source_el.select("p"):
                text = p.get_text(strip=True)
                if len(text) > 50 and not _DISCLAIMER_RE.search(text):
                    # Skip paragraphs inside promotional feature widgets
                    parent_classes = " ".join(p.parent.get("class", []))
                    if "featureset" in parent_classes:
                        continue
                    raw_desc_parts.append(text)

        date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
        if end_date and end_date != start_date:
            date_prefix += f"～{end_date.strftime('%Y年%m月%d日')}"
        raw_description = date_prefix + "\n\n" + "\n\n".join(raw_desc_parts)

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=event_url,
            original_language="ja",
            name_ja=name_ja,
            raw_title=name_ja,
            raw_description=raw_description,
            category=default_category,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=location_address,
            business_hours=business_hours,
        )
