"""Scraper for 映画.com 台湾映画

Source URL: https://eiga.com/search/%E5%8F%B0%E6%B9%BE/movie/
Platform  : Static HTML — no JS required
Source name: eiga_com
Source ID : eiga_com_{movie_id}

Strategy:
  1. Fetch paginated /search/台湾/movie/ results (up to _MAX_PAGES pages)
  2. Filter by pub_date: keep films released within last 90 days or next 180 days
  3. For each recent/upcoming film, fetch the detail page for description
  4. Source ID uses the numeric movie ID from the URL path

Listing page structure (ul.row.list-tile > li.col-s-3):
  <a href="/movie/{id}/"> — title from p.title, date from small.time

Detail page structure:
  h1.page-title     → Japanese title
  p.date-published  → 劇場公開日: YYYY年M月D日
  p.data            → "YYYY年製作／Xmin／G／台湾" (country info)
  p (no class, long) → synopsis

Taiwan relevance:
  All results from /search/台湾/movie/ have "台湾" in title — inherently relevant.
  Additionally, filter: pub_date within ±6 months of today.

Date field used: p.date-published strong → start_date, no end_date
Venue: None (film-wide release, no single Tokyo venue specified)
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "eiga_com"  # _scraper_key: EigaComScraper → eiga_com

_SEARCH_URL = "https://eiga.com/search/%E5%8F%B0%E6%B9%BE/movie/"
_BASE_URL = "https://eiga.com"
_MAX_PAGES = 5

_JST = timezone(timedelta(hours=9))

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

# Date window: include films released within last 90 days or up to 180 days ahead
_LOOKBACK_DAYS = 90
_LOOKAHEAD_DAYS = 180

_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def _parse_date(text: str) -> datetime | None:
    m = _DATE_RE.search(text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=_JST)
    return None


class EigaComScraper(BaseScraper):
    """Scraper for 映画.com 台湾映画 search results."""

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": _USER_AGENT,
            "Accept-Language": "ja,en;q=0.9",
        })
        self._today = datetime.now(_JST)

    def scrape(self) -> list[Event]:
        cutoff_past = self._today - timedelta(days=_LOOKBACK_DAYS)
        cutoff_future = self._today + timedelta(days=_LOOKAHEAD_DAYS)

        # Collect recent/upcoming candidates from listing pages
        candidates = []
        for page_num in range(1, _MAX_PAGES + 1):
            url = _SEARCH_URL if page_num == 1 else f"{_SEARCH_URL}{page_num}/"
            items = self._scrape_listing_page(url)
            if not items:
                break
            new_found = False
            for title, path, pub_date in items:
                if pub_date and cutoff_past <= pub_date <= cutoff_future:
                    candidates.append((title, path, pub_date))
                    new_found = True
            # If no new recent films on this page, stop paginating
            if not new_found and candidates:
                break

        logger.info(f"[{SOURCE_NAME}] {len(candidates)} recent Taiwan film(s) found")

        events = []
        for title, path, pub_date in candidates:
            time.sleep(0.5)
            ev = self._scrape_detail(path, title, pub_date)
            if ev:
                events.append(ev)

        logger.info(f"[{SOURCE_NAME}] {len(events)} events produced")
        return events

    def _scrape_listing_page(self, url: str) -> list[tuple]:
        """Return [(title, path, pub_date)] from one listing page."""
        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[{SOURCE_NAME}] Failed to fetch {url}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        items = []
        for li in soup.select("ul.row.list-tile li.col-s-3"):
            a = li.select_one("a[href]")
            title_el = li.select_one("p.title")
            date_el = li.select_one("small.time")
            if not (a and title_el and date_el):
                continue
            href = a.get("href", "")
            if not re.match(r"/movie/\d+/$", href):
                continue
            title = title_el.get_text(strip=True)
            pub_date = _parse_date(date_el.get_text(strip=True))
            items.append((title, href, pub_date))
        return items

    def _scrape_detail(self, path: str, fallback_title: str, fallback_date: datetime) -> Event | None:
        url = f"{_BASE_URL}{path}"
        m = re.search(r"/movie/(\d+)/", path)
        if not m:
            return None
        movie_id = m.group(1)
        source_id = f"{SOURCE_NAME}_{movie_id}"

        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.debug(f"[{SOURCE_NAME}] Could not fetch detail {url}: {e}")
            return self._build_event(source_id, url, fallback_title, "", fallback_date)

        soup = BeautifulSoup(resp.text, "html.parser")

        # Title
        h1 = soup.select_one("h1.page-title")
        title = h1.get_text(strip=True) if h1 else fallback_title

        # Publication date
        pub_strong = soup.select_one("p.date-published strong")
        pub_date = _parse_date(pub_strong.get_text(strip=True)) if pub_strong else fallback_date

        # p.data: "2013年製作／124分／G／台湾\n原題..."
        data_el = soup.select_one("p.data")
        data_text = data_el.get_text(separator="\n", strip=True) if data_el else ""

        # Synopsis: first long <p> without class
        synopsis = ""
        for p in soup.find_all("p"):
            if p.get("class"):
                continue
            t = p.get_text(strip=True)
            if len(t) > 80:
                synopsis = t
                break

        raw_description = ""
        if pub_date:
            raw_description = f"開催日時: {pub_date.year}年{pub_date.month:02d}月{pub_date.day:02d}日\n\n"
        raw_description += f"{data_text}\n\n{synopsis}".strip()

        return self._build_event(source_id, url, title, raw_description, pub_date)

    def _build_event(
        self, source_id: str, url: str, title: str, raw_description: str, pub_date: datetime
    ) -> Event:
        return Event(
            source_name=SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            name_ja=title,
            raw_title=title,
            raw_description=raw_description,
            category=["movie"],
            start_date=pub_date,
            end_date=None,
            location_name=None,
            location_address=None,
            is_paid=True,
        )
