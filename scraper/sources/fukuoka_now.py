"""Scraper for Fukuoka Now events (fukuoka-now.com/en/event/).

Fukuoka Now is the leading English-language media outlet for Fukuoka City.
Its event calendar covers cultural events, festivals, exhibitions and more —
and has confirmed annual Taiwan-themed events (台湾祭 in 福岡, 10th anniversary
in 2026, held at Fukuoka City Hall Fureai Hiroba every winter/spring).

Platform:  WordPress — server-rendered HTML (no Playwright needed)
Auth:      None
robots.txt: Only /wp-admin/ disallowed — scraping permitted
Rate limit: None observed; 1 s delay between detail pages is sufficient

Strategy:
  1. Paginate https://www.fukuoka-now.com/en/event/page/{N}/
     (page 1 = /en/event/, pages 2+ = /en/event/page/{N}/)
  2. Parse event cards: li.c-page-sub__guide-item
     - title, start_date/end_date (ISO via time[datetime]), tags, short desc, URL
  3. Taiwan filter on title + tags + short description
     (keywords: 台湾, Taiwan, Taiwanese, 臺灣)
  4. For Taiwan matches: fetch detail page for full description + venue
  5. Dedup key: slug from URL path  → source_id = "fukuoka_now_{slug}"

Pagination: 10 events per page; maximum 10 pages as safety cap.
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "fukuoka_now"
BASE_URL = "https://www.fukuoka-now.com"
LIST_URL = f"{BASE_URL}/en/event/"

JST = timezone(timedelta(hours=9))

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "Taiwanese", "臺灣"]
_PAGE_DELAY = 1.0   # seconds between detail page requests
_MAX_PAGES = 10     # safety cap

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html",
}


def _is_taiwan(text: str) -> bool:
    """Return True if any Taiwan keyword appears in text (case-sensitive)."""
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _slug_from_url(url: str) -> str:
    """Extract slug from event URL: .../en/event/taiwan-matsuri-2026/ → taiwan-matsuri-2026"""
    return url.rstrip("/").split("/")[-1]


def _parse_date(dt_str: str) -> Optional[datetime]:
    """Parse ISO date string (YYYY-MM-DD) to timezone-aware datetime (JST midnight)."""
    try:
        d = datetime.strptime(dt_str, "%Y-%m-%d")
        return d.replace(tzinfo=JST)
    except (ValueError, TypeError):
        logger.warning("fukuoka_now: cannot parse date %r", dt_str)
        return None


class FukuokaNowScraper(BaseScraper):
    """Scrapes Taiwan-related events from Fukuoka Now (fukuoka-now.com/en/event/)."""

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        for page_num in range(1, _MAX_PAGES + 1):
            if page_num == 1:
                url = LIST_URL
            else:
                url = f"{BASE_URL}/en/event/page/{page_num}/"

            soup = self._fetch(url)
            if soup is None:
                break

            cards = soup.select("li.c-page-sub__guide-item")
            if not cards:
                logger.debug("fukuoka_now: no cards on page %d — stopping", page_num)
                break

            for card in cards:
                event = self._parse_card(card)
                if event:
                    events.append(event)

            logger.info("fukuoka_now: page %d — %d cards, %d Taiwan so far",
                        page_num, len(cards), len(events))

        logger.info("fukuoka_now: total Taiwan events found: %d", len(events))
        return events

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch URL and return BeautifulSoup, or None on error/404."""
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=20)
        except requests.RequestException as exc:
            logger.warning("fukuoka_now: request error for %s: %s", url, exc)
            return None

        if resp.status_code == 404:
            return None
        if not resp.ok:
            logger.warning("fukuoka_now: HTTP %d for %s", resp.status_code, url)
            return None

        return BeautifulSoup(resp.text, "html.parser")

    def _parse_card(self, card) -> Optional[Event]:
        """Parse a list-page card and return an Event if Taiwan-related."""
        a_el = card.select_one("a[href]")
        if not a_el:
            return None
        detail_url = a_el["href"]
        if not detail_url.startswith("http"):
            detail_url = BASE_URL + detail_url

        # Title from listing card
        title_el = card.select_one(".c-page-sub__guide-title")
        card_title = title_el.get_text(strip=True) if title_el else ""

        # Tags  (e.g. "#Culture", "#Taiwan")
        tags = [t.get_text(strip=True).lstrip("#")
                for t in card.select(".c-page-sub__guide-category li span")]

        # Short description on the card
        desc_el = card.select_one(".c-page-sub__guide-description")
        card_desc = desc_el.get_text(strip=True) if desc_el else ""

        # Fast Taiwan filter: title + tags + card description
        combined = f"{card_title} {' '.join(tags)} {card_desc}"
        if not _is_taiwan(combined):
            return None

        # Start / end dates from listing card
        start_date = self._extract_date(card, ".c-event-date__start")
        end_date = self._extract_date(card, ".c-event-date__end") or start_date

        slug = _slug_from_url(detail_url)
        source_id = f"fukuoka_now_{slug}"

        # Fetch detail page for full description and venue
        time.sleep(_PAGE_DELAY)
        detail_soup = self._fetch(detail_url)

        if detail_soup:
            full_title, full_desc, venue, start_date_det, end_date_det = (
                self._parse_detail(detail_soup)
            )
            # Prefer detail page dates (more reliable) if available
            if start_date_det:
                start_date = start_date_det
            if end_date_det:
                end_date = end_date_det
            elif start_date_det:
                end_date = start_date_det
        else:
            full_title = card_title
            full_desc = card_desc
            venue = None

        if start_date is None:
            logger.warning("fukuoka_now: no start_date for %s — skipping", detail_url)
            return None

        # Prepend date stamp to raw_description per scraper conventions
        date_str = start_date.strftime("%Y年%-m月%-d日")
        raw_description = f"開催日時: {date_str}\n\n{full_desc}"

        # Infer categories from tags and title
        categories = _infer_categories(tags, full_title, full_desc)

        return Event(
            source_name=SOURCE_NAME,
            source_id=source_id,
            source_url=detail_url,
            original_language="en",
            raw_title=full_title or card_title,
            raw_description=raw_description,
            start_date=start_date,
            end_date=end_date,
            location_name=venue,
            location_address=venue,
            category=categories,
            is_active=True,
        )

    def _extract_date(self, soup, selector: str) -> Optional[datetime]:
        """Extract ISO date from time[datetime] within a CSS-selector context."""
        container = soup.select_one(selector)
        if not container:
            return None
        time_el = container.select_one("time[datetime]")
        if not time_el:
            return None
        return _parse_date(time_el.get("datetime", ""))

    def _parse_detail(self, soup: BeautifulSoup) -> tuple[
        str, str, Optional[str], Optional[datetime], Optional[datetime]
    ]:
        """
        Extract (title, description, venue, start_date, end_date) from a detail page.

        Detail page structure:
          article.c-page-sub__content
            .c-page-sub__content-title           ← title
            .c-event-date-detail__start time[datetime]  ← start date
            .c-event-date-detail__end time[datetime]    ← end date
            .c-content-main p                    ← description paragraphs
        """
        # Title
        title_el = soup.select_one(".c-page-sub__content-title")
        title = title_el.get_text(strip=True) if title_el else ""

        # Dates from detail page
        start_date = None
        end_date = None
        start_time_el = soup.select_one(".c-event-date-detail__start time[datetime]")
        if start_time_el:
            start_date = _parse_date(start_time_el.get("datetime", ""))
        end_time_el = soup.select_one(".c-event-date-detail__end time[datetime]")
        if end_time_el:
            end_date = _parse_date(end_time_el.get("datetime", ""))

        # Description: join all paragraphs in .c-content-main
        main_el = soup.select_one(".c-content-main")
        if main_el:
            paras = [p.get_text(strip=True) for p in main_el.find_all("p") if p.get_text(strip=True)]
            full_desc = "\n\n".join(paras)
        else:
            full_desc = ""

        # Venue: look for "Fukuoka City Hall" or address-like text in description
        venue = _extract_venue(full_desc, soup)

        return title, full_desc, venue, start_date, end_date


# ---------------------------------------------------------------------------
# Category inference
# ---------------------------------------------------------------------------

_TAG_TO_CATEGORY: dict[str, str] = {
    "Culture": "art",
    "Festival": "senses",
    "Food": "lifestyle_food",
    "Shopping": "retail",
    "Music": "performing_arts",
    "Art": "art",
    "Exhibition": "art",
    "Film": "movie",
    "Movie": "movie",
    "Lecture": "lecture",
    "Academic": "academic",
    "Nature": "nature",
    "Tourism": "tourism",
    "Theater": "performing_arts",
    "Dance": "performing_arts",
    "Community": "taiwan_japan",
}

_TITLE_CATEGORY_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"映画|film|movie|cinema", re.IGNORECASE), "movie"),
    (re.compile(r"concert|音楽|music|live", re.IGNORECASE), "performing_arts"),
    (re.compile(r"展覧|exhibition|exhibit|gallery|art", re.IGNORECASE), "art"),
    (re.compile(r"matsuri|festival|fes|祭", re.IGNORECASE), "senses"),
    (re.compile(r"food|restaurant|noodle|dish|cuisine|夜市|night market", re.IGNORECASE), "lifestyle_food"),
    (re.compile(r"lecture|seminar|talk|session|学術|研究", re.IGNORECASE), "lecture"),
    (re.compile(r"台湾|Taiwan|Taiwanese", re.IGNORECASE), "taiwan_japan"),
]


def _infer_categories(tags: list[str], title: str, desc: str) -> list[str]:
    """Infer canonical category list from tags and title/description text."""
    cats: set[str] = set()

    # Map tags to canonical categories
    for tag in tags:
        tag_clean = tag.lstrip("#").strip()
        if tag_clean in _TAG_TO_CATEGORY:
            cats.add(_TAG_TO_CATEGORY[tag_clean])

    # Title/description hints
    combined = f"{title} {desc}"
    for pattern, cat in _TITLE_CATEGORY_HINTS:
        if pattern.search(combined):
            cats.add(cat)

    # All Taiwan events should have taiwan_japan
    cats.add("taiwan_japan")

    return sorted(cats)


# ---------------------------------------------------------------------------
# Venue extraction
# ---------------------------------------------------------------------------

# Patterns for common Fukuoka venues mentioned in descriptions
_VENUE_PATTERNS = [
    re.compile(r"(Fukuoka City Hall [^\.,\n]+)"),
    re.compile(r"(Canal City [^\.,\n]+)"),
    re.compile(r"([^\.,\n]*(Tenjin|Hakata|Fukuoka)[^\.,\n]{0,60})"),
    # Japanese address patterns
    re.compile(r"(\d[\-\d]+ [^\.,\n]+(?:区|市)[^\.,\n]{0,60})"),
]

# Bullet-point patterns in Fukuoka Now event descriptions
# e.g. "• Jan. 30, 2026 (Fri.) ~ Feb. 23, 2026 (Mon., Holiday)"
# venue usually follows "• Free entry" or appears as "Fukuoka City Hall Fureai Hiroba"
_BULLET_VENUE_RE = re.compile(
    r"(?:^|\n)•[^\n]*\n([^\n•]{10,100})\n",
    re.MULTILINE,
)

_INLINE_VENUE_RE = re.compile(
    r"(?:venue|location|place|会場)[:\s]*([^\n\.]{5,120})",
    re.IGNORECASE,
)


def _extract_venue(desc: str, soup: BeautifulSoup) -> Optional[str]:
    """
    Try to extract venue name from description text or detail page.

    Fukuoka Now event descriptions list logistics as bullet points:
      • Jan. 30, 2026 (Fri.) ~ Feb. 23, 2026 ...
      • Weekdays: 12:00~21:30 ...
      • Free entry
      • Fukuoka City Hall Fureai Hiroba
        1-8-1 Tenjin, Chuo-ku, Fukuoka

    We capture the address-like line after "Free entry" or similar.
    """
    # Try inline venue/location label
    m = _INLINE_VENUE_RE.search(desc)
    if m:
        return m.group(1).strip()

    # Try bullet-point extraction: look for lines matching known Fukuoka venue keywords
    for line in desc.split("\n"):
        line = line.strip()
        if any(kw in line for kw in ["City Hall", "Fureai", "Tenjin", "Canal", "ACROS",
                                       "Nakasu", "Hakata", "博多", "天神", "中洲"]):
            return line[:120]

    return None
