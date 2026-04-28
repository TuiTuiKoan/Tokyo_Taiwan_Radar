"""Scraper for 映画.com 台湾映画

Source URL: https://eiga.com/search/%E5%8F%B0%E6%B9%BE/movie/
Platform  : Static HTML — no JS required
Source name: eiga_com
Source ID : eiga_com_{movie_id}_{theater_id}

Strategy:
  1. Fetch paginated /search/台湾/movie/ results (up to _MAX_PAGES pages)
  2. Filter by pub_date: keep films released within last 90 days or next 180 days
  3. For each film, fetch /movie/{id}/theater/ to find all area links
  4. For each area page /movie-area/{id}/{pref}/{area}/,
     extract one Event per theater (div.movie-schedule block)
  5. source_id = eiga_com_{movie_id}_{theater_id}
     theater_id extracted from .more-schedule a[href] → /movie-theater/…/{theater_id}/
  6. start_date = movie's 劇場公開日 (pub_date)
     end_date = last td[data-date] observed in current week's schedule
  7. location_name = data-theater attribute; location_address = regex from page HTML
  8. Fallback: if no theater pages found, emit one movie-level event (no venue)

Listing page structure (ul.row.list-tile > li.col-s-3):
  <a href="/movie/{id}/"> — title from p.title, date from small.time

Detail page structure:
  h1.page-title      → Japanese title (name_ja)
  p.date-published   → 劇場公開日: YYYY年M月D日
  p.data             → "YYYY年製作／Xmin／G／台湾" + optional 原題または英題 line
                       原題または英題 is parsed into name_zh (CJK part) and name_en (ASCII part).
                       Example: "原題または英題：阿嬤的夢中情人 Forever Love"
                                → name_zh="阿嬤的夢中情人", name_en="Forever Love"
  p (no class, long) → synopsis

Area page structure (/movie-area/{id}/{pref}/{area}/):
  div.movie-schedule[data-theater][data-title]
    td[data-date="YYYYMMDD"]   → individual screening dates (current week)
  div.more-schedule a[href]    → /movie-theater/{id}/{pref}/{area}/{theater_id}/

Address extraction (area page HTML):
  regex r'(?:東京都|大阪府|...) [^\\s<>]{5,}' → first match

Taiwan relevance:
  All results from /search/台湾/movie/ have "台湾" in title — inherently relevant.
  Additionally, filter: pub_date within ±6 months of today.
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

# theater_id regex from more-schedule href
_THEATER_ID_RE = re.compile(r"/movie-theater/\d+/\d+/\d+/(\d+)/")

# Original title regex — captures 原題 or 原題または英題 line from p.data
_ORIG_TITLE_RE = re.compile(r"原題(?:または英題)?[：:]\s*([^\n]+)")


def _parse_original_title(data_text: str) -> tuple["str | None", "str | None"]:
    """Extract (name_zh, name_en) from p.data 原題 line.

    Handles patterns:
      '原題：阿嬤的夢中情人 Forever Love'  → ('阿嬤的夢中情人', 'Forever Love')
      '原題または英題：Forever Love'        → (None, 'Forever Love')
      '原題：阿嬤的夢中情人'                → ('阿嬤的夢中情人', None)
    """
    m = _ORIG_TITLE_RE.search(data_text)
    if not m:
        return None, None
    orig = m.group(1).strip()
    # Split on first transition: non-ASCII block (CJK/full-width) → space → ASCII
    split_m = re.match(r"^([^\x00-\x7f]+)\s+([A-Za-z].+)$", orig)
    if split_m:
        return split_m.group(1).strip(), split_m.group(2).strip()
    # Only one language
    if re.search(r"[\u4e00-\u9fff]", orig):
        return orig, None
    return None, orig


def _parse_date(text: str) -> datetime | None:
    m = _DATE_RE.search(text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=_JST)
    return None


def _yyyymmdd_to_date(s: str) -> datetime | None:
    """Convert 'YYYYMMDD' string to datetime."""
    if len(s) == 8 and s.isdigit():
        return datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), tzinfo=_JST)
    return None


class EigaComScraper(BaseScraper):
    """Scraper for 映画.com 台湾映画 search results — one event per theater."""

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
            if not new_found and candidates:
                break

        logger.info(f"[{SOURCE_NAME}] {len(candidates)} recent Taiwan film(s) found")

        events: list[Event] = []
        for title, path, pub_date in candidates:
            time.sleep(0.5)
            movie_events = self._scrape_movie(path, title, pub_date)
            events.extend(movie_events)

        logger.info(f"[{SOURCE_NAME}] {len(events)} theater events produced")
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

    def _scrape_movie(
        self, path: str, fallback_title: str, fallback_date: datetime
    ) -> list[Event]:
        """Fetch detail + theater pages; return one Event per theater (or fallback movie event)."""
        m = re.search(r"/movie/(\d+)/", path)
        if not m:
            return []
        movie_id = m.group(1)
        detail_url = f"{_BASE_URL}{path}"

        # --- Fetch movie detail ---
        title, pub_date, raw_description, name_zh, name_en = self._fetch_movie_detail(
            detail_url, fallback_title, fallback_date
        )

        # --- Discover theater area links ---
        area_urls = self._fetch_area_links(movie_id)
        if not area_urls:
            # Fallback: one movie-level event with no venue
            fallback_source_id = f"{SOURCE_NAME}_{movie_id}"
            logger.debug(f"[{SOURCE_NAME}] No theaters for movie {movie_id}; emitting fallback event")
            return [Event(
                source_name=SOURCE_NAME,
                source_id=fallback_source_id,
                source_url=detail_url,
                original_language="ja",
                name_ja=title,
                name_zh=name_zh,
                name_en=name_en,
                raw_title=title,
                raw_description=raw_description,
                category=["movie"],
                start_date=pub_date,
                end_date=None,
                location_name=None,
                location_address=None,
                is_paid=True,
            )]

        # --- Scrape each area page for per-theater events ---
        theater_events: list[Event] = []
        for area_url in area_urls:
            time.sleep(0.3)
            events = self._scrape_area_page(
                area_url, movie_id, title, raw_description, pub_date, name_zh, name_en
            )
            theater_events.extend(events)

        return theater_events

    def _fetch_movie_detail(
        self, url: str, fallback_title: str, fallback_date: datetime
    ) -> tuple[str, datetime, str, "str | None", "str | None"]:
        """Return (title, pub_date, raw_description, name_zh, name_en) from movie detail page."""
        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.debug(f"[{SOURCE_NAME}] Could not fetch {url}: {e}")
            return fallback_title, fallback_date, "", None, None

        soup = BeautifulSoup(resp.text, "html.parser")

        h1 = soup.select_one("h1.page-title")
        title = h1.get_text(strip=True) if h1 else fallback_title

        pub_strong = soup.select_one("p.date-published strong")
        pub_date = _parse_date(pub_strong.get_text(strip=True)) if pub_strong else fallback_date

        data_el = soup.select_one("p.data")
        data_text = data_el.get_text(separator="\n", strip=True) if data_el else ""

        # Extract 原題 / 原題または英題 — may include both zh + en titles separated by a space.
        # Example: "原題または英題：阿嬤的夢中情人 Forever Love" → name_zh='阿嬤的夢中情人', name_en='Forever Love'
        name_zh, name_en = _parse_original_title(data_text)

        synopsis = ""
        for p in soup.find_all("p"):
            if p.get("class"):
                continue
            t = p.get_text(strip=True)
            if len(t) > 80:
                synopsis = t
                break

        return title, pub_date, f"{data_text}\n\n{synopsis}".strip(), name_zh, name_en

    def _fetch_area_links(self, movie_id: str) -> list[str]:
        """Return all /movie-area/{id}/{pref}/{area}/ URLs for a movie."""
        theater_index_url = f"{_BASE_URL}/movie/{movie_id}/theater/"
        try:
            resp = self._session.get(theater_index_url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.debug(f"[{SOURCE_NAME}] Theater index not available for {movie_id}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        seen: set[str] = set()
        area_urls: list[str] = []
        pattern = re.compile(rf"/movie-area/{movie_id}/\d+/\d+/$")
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if pattern.match(href) and href not in seen:
                seen.add(href)
                area_urls.append(f"{_BASE_URL}{href}")
        logger.debug(f"[{SOURCE_NAME}] movie {movie_id}: {len(area_urls)} area(s) found")
        return area_urls

    def _scrape_area_page(
        self,
        url: str,
        movie_id: str,
        title: str,
        raw_description: str,
        pub_date: datetime,
        name_zh: "str | None" = None,
        name_en: "str | None" = None,
    ) -> list[Event]:
        """Return one Event per theater block on an area page."""
        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.debug(f"[{SOURCE_NAME}] Could not fetch area page {url}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        events: list[Event] = []
        schedule_divs = soup.select("div.movie-schedule")
        if not schedule_divs:
            return []

        for sched_div in schedule_divs:
            theater_name = sched_div.get("data-theater") or sched_div.get("data-title") or ""
            if not theater_name:
                continue

            dates = sorted(
                filter(None, (_yyyymmdd_to_date(td.get("data-date", "")) for td in sched_div.select("td[data-date]")))
            )
            if not dates:
                continue

            end_date = dates[-1]

            # Locate theater_id from the "all schedule" link in the more-schedule div
            # The div has 3 links: copy (/mail/), print (/print/), and all schedule (/{id}/)
            theater_id = "unknown"
            theater_page_path: str | None = None
            more_div = sched_div.find_next_sibling("div", class_="more-schedule")
            if more_div:
                # Prefer the "all schedule" arrow link (not mail/print)
                more_a = more_div.select_one("a.icon.arrow[href*='/movie-theater/']")
                if not more_a:
                    # Fallback: first movie-theater link that is not /mail/ or /print/
                    for ta in more_div.select("a[href*='/movie-theater/']"):
                        href = ta.get("href", "")
                        if not href.endswith("/mail/") and not href.endswith("/print/"):
                            more_a = ta
                            break
                if more_a:
                    theater_page_path = more_a.get("href", "")
                    tid_m = _THEATER_ID_RE.search(theater_page_path)
                    if tid_m:
                        theater_id = tid_m.group(1)

            source_id = f"{SOURCE_NAME}_{movie_id}_{theater_id}"

            # Fetch theater detail page for address
            location_address = None
            if theater_page_path and theater_id != "unknown":
                location_address = self._fetch_theater_address(theater_page_path)

            # Build raw_description with date prefix
            start = pub_date or dates[0]
            desc_prefix = f"開催日時: {start.year}年{start.month:02d}月{start.day:02d}日"
            if end_date and end_date != start:
                desc_prefix += f"〜{end_date.year}年{end_date.month:02d}月{end_date.day:02d}日"
            desc_prefix += "\n\n"

            events.append(Event(
                source_name=SOURCE_NAME,
                source_id=source_id,
                source_url=url,
                original_language="ja",
                name_ja=title,
                name_zh=name_zh,
                name_en=name_en,
                raw_title=title,
                raw_description=desc_prefix + raw_description,
                category=["movie"],
                start_date=pub_date or dates[0],
                end_date=end_date,
                location_name=theater_name,
                location_address=location_address,
                is_paid=True,
            ))

        logger.debug(f"[{SOURCE_NAME}] {url}: {len(events)} theater event(s)")
        return events

    def _fetch_theater_address(self, theater_path: str) -> str | None:
        """Fetch address from /movie-theater/…/{theater_id}/ page via theater-table."""
        url = f"{_BASE_URL}{theater_path}"
        try:
            time.sleep(0.3)
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        # <th scope="row">住所</th><td>東京都新宿区…</td>
        for th in soup.select("table.theater-table th"):
            if "住所" in th.get_text():
                td = th.find_next_sibling("td")
                if td:
                    # Remove child links (e.g. "映画館公式ページ") before extracting text
                    for a_tag in td.find_all("a"):
                        a_tag.decompose()
                    addr = td.get_text(separator=" ", strip=True)
                    return addr or None
        return None
