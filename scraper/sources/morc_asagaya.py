"""Scraper for Morc阿佐ヶ谷

Source URL: https://www.morc-asagaya.com/film_date/film_now/
Platform  : WordPress static HTML — no JS rendering required
Source name: morc_asagaya
Source ID : morc_asagaya_{slug}  (URL path segment after /film/)

Strategy:
  1. Fetch the "上映中" and "近日上映予定" listing pages
  2. Collect all /film/{slug}/ URLs (deduplicated)
  3. For each film page, check Taiwan keyword filter on full page text
  4. Extract title from <h1>, date from "上映日時" section, description from body
  5. Parse date range from "M/D(曜)〜M/D(曜)" or "M/D(曜)" patterns

Taiwan keyword filter:
  ["台湾", "Taiwan", "臺灣", "金馬", "台北", "台中", "高雄"]
  Applied to full page text AFTER removing section#tp_info (site-wide notice
  banner that appears on every page and would cause false positives).

Venue (fixed):
  Morc阿佐ヶ谷
  東京都杉並区阿佐谷北2丁目12番21号 あさがやドラマ館2F
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "morc_asagaya"

_BASE_URL = "https://www.morc-asagaya.com"
_LISTING_URLS = [
    "https://www.morc-asagaya.com/film_date/film_now/",
    "https://www.morc-asagaya.com/film_date/film_plan/",
]

_JST = timezone(timedelta(hours=9))

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

_VENUE_NAME = "Morc阿佐ヶ谷"
_VENUE_ADDRESS = "東京都杉並区阿佐谷北2丁目12番21号 あさがやドラマ館2F"

# Taiwan relevance keywords
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "金馬", "台北", "台中", "高雄"]

# Date patterns
# "4/24(金)〜4/30(木)" or "4/24(金)" or "4/24(金)〜終了日未定"
_DATE_RANGE_RE = re.compile(
    r"(\d{1,2})/(\d{1,2})[^〜\n]*?(?:〜|~)(\d{1,2})/(\d{1,2})"
)
_DATE_SINGLE_RE = re.compile(r"(\d{1,2})/(\d{1,2})[（(]")


def _is_taiwan_relevant(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _infer_year(month: int, today: datetime) -> int:
    """Infer year from month. If month is far behind today, assume next year."""
    if month < today.month - 3:
        return today.year + 1
    return today.year


def _parse_date(month: int, day: int, today: datetime) -> datetime:
    year = _infer_year(month, today)
    return datetime(year, month, day, tzinfo=_JST)


class MorcAsagayaScraper(BaseScraper):
    """Scraper for Morc阿佐ヶ谷 (阿佐谷アジア映画ミニシアター)."""

    SOURCE_NAME = SOURCE_NAME

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": _USER_AGENT,
            "Accept-Language": "ja,en;q=0.9",
        })

    def scrape(self) -> list[Event]:
        today = datetime.now(tz=_JST)
        film_urls = self._collect_film_urls()
        logger.info("morc_asagaya: found %d film URLs", len(film_urls))

        events: list[Event] = []
        for url in film_urls:
            time.sleep(0.5)
            try:
                event = self._scrape_film(url, today)
                if event:
                    events.append(event)
            except Exception:
                logger.exception("morc_asagaya: failed to scrape %s", url)
        logger.info("morc_asagaya: %d Taiwan events found", len(events))
        return events

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_film_urls(self) -> list[str]:
        seen: set[str] = set()
        urls: list[str] = []
        for listing_url in _LISTING_URLS:
            try:
                resp = self._session.get(listing_url, timeout=15)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    # Match /film/{slug}/ — exclude /film_date/ index pages
                    if re.search(r"/film/[^/]+/?$", href) and "film_date" not in href:
                        full = href if href.startswith("http") else urljoin(_BASE_URL, href)
                        if full not in seen:
                            seen.add(full)
                            urls.append(full)
            except Exception:
                logger.exception("morc_asagaya: failed to fetch listing %s", listing_url)
        return urls

    def _scrape_film(self, url: str, today: datetime) -> Event | None:
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove the site-wide info/notice section (#tp_info) that appears on
        # every page and contains Taiwan festival banners — this would otherwise
        # cause false positives for non-Taiwan films.
        for el in soup.select("#tp_info"):
            el.decompose()

        full_text = soup.get_text(separator="\n", strip=True)

        if not _is_taiwan_relevant(full_text):
            return None

        # Extract slug for stable source_id
        slug = urlparse(url).path.rstrip("/").split("/")[-1]
        source_id = f"morc_asagaya_{slug}"

        # Title
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else slug

        # Date: find "上映日時" label, then adjacent h2 or next sibling text
        start_date: datetime | None = None
        end_date: datetime | None = None
        date_text = self._extract_date_text(soup)
        if date_text:
            start_date, end_date = self._parse_date_range(date_text, today)

        if start_date is None:
            logger.warning("morc_asagaya: no start_date for %s", url)
            return None

        # Description — main body text (excluding nav/menu/sidebar)
        raw_desc = self._extract_description(soup)
        date_prefix = f"開催日時: {start_date.year}年{start_date.month}月{start_date.day}日\n\n"
        raw_description = date_prefix + (raw_desc or "")

        return Event(
            source_name=SOURCE_NAME,
            source_id=source_id,
            source_url=url,
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

    def _extract_date_text(self, soup: BeautifulSoup) -> str | None:
        """Find date text from 上映日時 label."""
        for tag in soup.find_all(string=lambda t: "上映日時" in str(t)):
            parent = tag.parent
            # Look in next sibling or parent's next sibling
            candidate = parent.find_next_sibling()
            if candidate:
                return candidate.get_text(separator=" ", strip=True)
            # Also try h2 after the label
            h2 = parent.find_next("h2")
            if h2:
                return h2.get_text(strip=True)
        # Fallback: look for h2 containing M/D pattern
        for h2 in soup.find_all("h2"):
            txt = h2.get_text(strip=True)
            if re.search(r"\d{1,2}/\d{1,2}", txt):
                return txt
        return None

    def _parse_date_range(
        self, text: str, today: datetime
    ) -> tuple[datetime | None, datetime | None]:
        """Parse 'M/D(曜)〜M/D(曜)' or single 'M/D(曜)' into start/end dates."""
        m = _DATE_RANGE_RE.search(text)
        if m:
            sm, sd, em, ed = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            start = _parse_date(sm, sd, today)
            end = _parse_date(em, ed, today)
            # If end < start (year boundary), add 1 year to end
            if end < start:
                end = end.replace(year=end.year + 1)
            return start, end
        m2 = _DATE_SINGLE_RE.search(text)
        if m2:
            sm, sd = int(m2.group(1)), int(m2.group(2))
            dt = _parse_date(sm, sd, today)
            return dt, dt
        return None, None

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract main body text, skipping nav/menu/footer/header."""
        # Remove navigation and header elements
        for tag in soup.find_all(["nav", "header", "footer"]):
            tag.decompose()
        for cls in ["navi", "menu", "access", "information-area", "goods-area"]:
            for el in soup.find_all(class_=re.compile(cls, re.I)):
                el.decompose()

        # Find main content area — look for article or specific content divs
        main = (
            soup.find("article")
            or soup.find(class_=re.compile(r"film.?detail|single.?content|entry.?content", re.I))
            or soup.find("main")
        )
        if main:
            return main.get_text(separator="\n", strip=True)
        return soup.get_text(separator="\n", strip=True)
