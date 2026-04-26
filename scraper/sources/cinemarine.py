"""Scraper for 横浜シネマリン (Yokohama Cinemarine)

Source URL: https://cinemarine.co.jp/
Platform  : WordPress static HTML — no JS rendering required
Source name: cinemarine
Source ID : cinemarine_{slug}  (URL path segment of the film detail page)

Strategy:
  1. Fetch /coming-soon/ and /movie-now/ listing pages (deduplicated)
  2. Each film entry in the listing page has:
       <h2>6/27(土)～</h2>
       <h3><a href="/slug/">Title</a></h3>
       <div class="content_block" id="custom_post_widget-{id}">...</div>
  3. Apply Taiwan keyword filter on the content_block text (country info,
     e.g. "2024年／台湾・香港・フランス") to avoid false positives from
     sidebar navigation that lists all films.
  4. Extract title from <h3> link text, URL from href.
  5. Parse screening date range from <h2> text.
  6. Fetch the individual film page for full description.

Taiwan keyword filter:
  ["台湾", "Taiwan", "臺灣", "金馬"]
  Applied only to the content_block text (country/distributor line),
  NOT the full listing page text (which would catch sidebar entries).

Date formats in <h2>:
  "6/27(土)～"               → start only (open-ended run)
  "4/25(土)－5/8(金)"        → range with 全角ダッシュ U+FF0D
  "5/23(土)～6/5(金)"        → range with 波ダッシュ

Venue (fixed):
  横浜シネマリン
  神奈川県横浜市中区花咲町1丁目1番地 横浜ニューテアトルビル
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "cine_marine"

_BASE_URL = "https://cinemarine.co.jp"
_LISTING_URLS = [
    "https://cinemarine.co.jp/coming-soon/",
    "https://cinemarine.co.jp/movie-now/",
]

_JST = timezone(timedelta(hours=9))

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

_VENUE_NAME = "横浜シネマリン"
_VENUE_ADDRESS = "神奈川県横浜市中区花咲町1丁目1番地 横浜ニューテアトルビル"

# Taiwan relevance keywords — checked against content_block text only
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "金馬"]

# Date patterns in <h2> heading
# "6/27(土)～"              → start only
# "4/25(土)－5/8(金)"       → range (全角ダッシュ)
# "5/23(土)～6/5(金)"       → range (波ダッシュ / 全角チルダ)
_DATE_RANGE_RE = re.compile(
    r"(\d{1,2})/(\d{1,2})"        # start month/day
    r"[^0-9\n]*?"                  # day-of-week etc.
    r"(?:－|〜|～|~)"              # separator (全角 or half-width)
    r"(\d{1,2})/(\d{1,2})"        # end month/day
)
_DATE_START_RE = re.compile(r"(\d{1,2})/(\d{1,2})")


def _is_taiwan_relevant(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _infer_year(month: int, today: datetime) -> int:
    """Infer screening year from month number."""
    if month < today.month - 3:
        return today.year + 1
    return today.year


def _parse_date(month: int, day: int, today: datetime) -> datetime:
    year = _infer_year(month, today)
    return datetime(year, month, day, tzinfo=_JST)


def _parse_date_range(h2_text: str, today: datetime):
    """Return (start_date, end_date) parsed from the <h2> date heading.

    Examples:
      "6/27(土)～"          → (2026-06-27, None)
      "4/25(土)－5/8(金)"   → (2026-04-25, 2026-05-08)
      "5/23(土)～6/5(金)"   → (2026-05-23, 2026-06-05)
    """
    m = _DATE_RANGE_RE.search(h2_text)
    if m:
        sm, sd, em, ed = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        start = _parse_date(sm, sd, today)
        end = _parse_date(em, ed, today)
        return start, end

    m2 = _DATE_START_RE.search(h2_text)
    if m2:
        sm, sd = int(m2.group(1)), int(m2.group(2))
        return _parse_date(sm, sd, today), None

    return None, None


class CineMarineScraper(BaseScraper):
    """Scraper for 横浜シネマリン."""

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": _USER_AGENT,
            "Accept-Language": "ja,en;q=0.9",
        })
        self._today = datetime.now(_JST)

    def scrape(self) -> list[Event]:
        events: dict[str, Event] = {}  # slug → Event (dedup across listing pages)

        for listing_url in _LISTING_URLS:
            page_events = self._scrape_listing(listing_url)
            for ev in page_events:
                slug = ev.source_id.replace(f"{SOURCE_NAME}_", "")
                if slug not in events:
                    events[slug] = ev

        result = list(events.values())
        logger.info(f"[{SOURCE_NAME}] {len(result)} Taiwan events found")
        return result

    def _scrape_listing(self, listing_url: str) -> list[Event]:
        """Scrape one listing page and return Taiwan film events."""
        try:
            resp = self._session.get(listing_url, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[{SOURCE_NAME}] Failed to fetch {listing_url}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        entry = soup.select_one(".entry-content")
        if not entry:
            logger.warning(f"[{SOURCE_NAME}] No .entry-content found at {listing_url}")
            return []

        events = []
        # Walk children: when we see h2 followed by h3>a, collect the pair
        children = list(entry.children)
        i = 0
        while i < len(children):
            node = children[i]
            if not hasattr(node, "name"):
                i += 1
                continue

            if node.name == "h2":
                date_text = node.get_text(strip=True)
                # Look ahead for h3 with a link
                j = i + 1
                while j < len(children) and (not hasattr(children[j], "name") or children[j].name not in ("h2", "h3")):
                    j += 1

                if j < len(children) and hasattr(children[j], "name") and children[j].name == "h3":
                    h3 = children[j]
                    a_tag = h3.find("a", href=True)
                    if a_tag:
                        film_url = a_tag.get("href", "")
                        title = a_tag.get_text(strip=True)

                        # Find the content_block div that follows the h3
                        k = j + 1
                        while k < len(children) and (not hasattr(children[k], "name") or children[k].name not in ("div", "h2", "h3")):
                            k += 1

                        content_text = ""
                        if k < len(children) and hasattr(children[k], "name") and children[k].name == "div":
                            content_block = children[k]
                            content_text = content_block.get_text(separator="\n", strip=True)

                        # Taiwan filter on content_block text
                        if _is_taiwan_relevant(content_text):
                            ev = self._build_event(title, film_url, date_text, content_text)
                            if ev:
                                events.append(ev)
                        i = k + 1
                        continue

            i += 1

        return events

    def _build_event(self, title: str, film_url: str, date_text: str, content_text: str) -> Event | None:
        """Build an Event from listing page data, optionally fetching film page for description."""
        # Extract slug from URL
        slug = film_url.rstrip("/").split("/")[-1]
        if not slug:
            return None

        source_id = f"{SOURCE_NAME}_{slug}"

        # Parse date
        start_date, end_date = _parse_date_range(date_text, self._today)
        if start_date is None:
            logger.warning(f"[{SOURCE_NAME}] Could not parse date from '{date_text}' for {title}")

        # Fetch film page for full description
        raw_description = content_text
        try:
            time.sleep(0.3)
            resp = self._session.get(film_url, timeout=15)
            if resp.ok:
                film_soup = BeautifulSoup(resp.text, "html.parser")
                # Remove sidebar/widget content
                for el in film_soup.select(".widget, aside, nav, header, footer, .sidebar"):
                    el.decompose()
                entry_content = film_soup.select_one(".entry-content")
                if entry_content:
                    raw_description = entry_content.get_text(separator="\n", strip=True)
        except requests.RequestException as e:
            logger.debug(f"[{SOURCE_NAME}] Could not fetch film page {film_url}: {e}")

        # Prepend 開催日時 prefix when start_date is populated
        if start_date:
            date_prefix = f"開催日時: {start_date.year}年{start_date.month:02d}月{start_date.day:02d}日\n\n"
            raw_description = date_prefix + raw_description

        return Event(
            source_name=SOURCE_NAME,
            source_id=source_id,
            source_url=film_url,
            original_language="ja",
            name_ja=title,
            raw_title=title,
            raw_description=raw_description,
            category=["movie"],
            start_date=start_date,
            end_date=end_date,
            location_name=_VENUE_NAME,
            location_address=_VENUE_ADDRESS,
            is_paid=True,
        )
