"""Scraper for Short Shorts Film Festival & Asia (SSFF)

Source URL: https://www.shortshorts.org/{year}/all-program/
Platform  : Static HTML (WordPress) — no JS required
Source name: ssff
Source ID : ssff_{year}_{slug}

Strategy:
  1. Detect current festival year (try current + 1 year, fall back to current, then previous)
  2. Fetch /{year}/all-program/ (static HTML, ~112KB with all films)
  3. Find all <a href> links matching /{year}/program/{slug}/ whose text contains 台湾
  4. For each Taiwan film, fetch the detail page
  5. Extract: Japanese title (breadcrumb last item), English title (h1),
     synopsis, country, director, screening date (table row), venue

All-program listing Taiwan detection:
  <a href="/2026/program/{slug}/"> ... {director} / 台湾 </a>
  → filter by 台湾 in link text

Detail page structure:
  <title> "English Title | 上映・配信作品 – SSFF 2026"
  nav ol li[-1]            → Japanese title (breadcrumb last item)
  h1                       → English title
  dl.info                  → 監督, 時間, 国, ジャンル, 年 (key-value pairs)
  section (long, no 上映)  → synopsis paragraph
  table > tbody > tr       → [会場 | 2026.06.08 [Mon] 13:00-14:50 | ticket]

Date format: "2026.06.08 [Mon] 13:00-14:50"
Venue: table row 1st cell link text (e.g. "WITH HARAJUKU HALL")

Source ID: ssff_{year}_{slug}
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "ssff"  # _scraper_key: SsffScraper → ssff

_BASE_URL = "https://www.shortshorts.org"

_JST = timezone(timedelta(hours=9))

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

_TAIWAN_KWS = ["台湾", "Taiwan", "臺灣"]

# Date format in screening table: "2026.06.08 [Mon] 13:00-14:50"
_SSFF_DATE_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})")

# SSFF festival typically runs late May – end of June
_FESTIVAL_FALLBACK_MONTH = 5
_FESTIVAL_FALLBACK_DAY = 25


def _parse_ssff_date(text: str) -> datetime | None:
    m = _SSFF_DATE_RE.search(text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=_JST)
    return None


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KWS)


class SsffScraper(BaseScraper):
    """Scraper for Short Shorts Film Festival & Asia."""

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": _USER_AGENT,
            "Accept-Language": "ja,en;q=0.9",
        })
        self._today = datetime.now(_JST)

    def scrape(self) -> list[Event]:
        year = self._detect_year()
        if not year:
            logger.warning(f"[{SOURCE_NAME}] Could not detect festival year")
            return []

        listing_url = f"{_BASE_URL}/{year}/all-program/"
        taiwan_links = self._get_taiwan_links(listing_url, year)
        logger.info(f"[{SOURCE_NAME}] {len(taiwan_links)} Taiwan film(s) found in SSFF {year}")

        events = []
        for slug, link_text, film_url in taiwan_links:
            time.sleep(0.3)
            ev = self._scrape_film(slug, link_text, film_url, year)
            if ev:
                events.append(ev)

        logger.info(f"[{SOURCE_NAME}] {len(events)} events produced")
        return events

    def _detect_year(self) -> int | None:
        """Try current year and ±1 to find an active all-program page."""
        current_year = self._today.year
        for year in [current_year, current_year + 1, current_year - 1]:
            url = f"{_BASE_URL}/{year}/all-program/"
            try:
                resp = self._session.get(url, timeout=10)
                if resp.ok and len(resp.text) > 10000:
                    logger.info(f"[{SOURCE_NAME}] Detected festival year: {year}")
                    return year
            except requests.RequestException:
                continue
        return None

    def _get_taiwan_links(self, listing_url: str, year: int) -> list[tuple]:
        """Return [(slug, link_text, film_url)] for Taiwan films."""
        try:
            resp = self._session.get(listing_url, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[{SOURCE_NAME}] Failed to fetch {listing_url}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        seen: set[str] = set()
        slug_re = re.compile(rf"https://www\.shortshorts\.org/{year}/program/([a-z0-9-]+)/?$")

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            m = slug_re.match(href)
            if not m:
                continue
            slug = m.group(1)
            if slug in seen:
                continue
            text = a.get_text(separator=" ", strip=True)
            if _is_taiwan(text):
                seen.add(slug)
                results.append((slug, text, href))
        return results

    def _scrape_film(
        self, slug: str, link_text: str, film_url: str, year: int
    ) -> Event | None:
        source_id = f"{SOURCE_NAME}_{year}_{slug}"

        try:
            resp = self._session.get(film_url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.debug(f"[{SOURCE_NAME}] Failed to fetch {film_url}: {e}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Japanese title: last item of breadcrumb (nav ol li)
        breadcrumb_items = soup.select("nav ol li")
        name_ja = breadcrumb_items[-1].get_text(strip=True) if breadcrumb_items else ""

        # English title: <h1> in article, or page <title> before " | "
        h1 = soup.select_one("article h1")
        if h1:
            name_en = h1.get_text(strip=True)
        elif soup.title:
            name_en = soup.title.get_text(strip=True).split(" | ")[0]
        else:
            name_en = ""

        if not name_ja:
            name_ja = name_en or link_text[:60]

        # Extract meta from dl.info (key-value: 監督, 国, ジャンル, 年, etc.)
        country = ""
        director = ""
        for dl in soup.select("dl.info"):
            items_text = dl.get_text(separator="\n", strip=True).split("\n")
            for i, item in enumerate(items_text):
                if item == "国" and i + 1 < len(items_text):
                    country = items_text[i + 1]
                elif item == "監督" and i + 1 < len(items_text):
                    director = items_text[i + 1]

        # Synopsis: first long paragraph in article sections (not the screening section)
        synopsis = ""
        for section in soup.select("article section"):
            section_text = section.get_text(separator="\n", strip=True)
            if "上映会場" in section_text or "チケット" in section_text[:30]:
                continue
            for p in section.find_all("p"):
                pt = p.get_text(strip=True)
                if len(pt) > 60:
                    synopsis = pt
                    break
            if synopsis:
                break

        # Screening date and venue from table
        start_date = None
        venue_name = None
        screening_rows = []
        for table in soup.select("article table"):
            for tr in table.select("tbody tr"):
                cells = [td.get_text(strip=True) for td in tr.select("td")]
                if len(cells) >= 2:
                    venue_text = cells[0]
                    date_text = cells[1]
                    d = _parse_ssff_date(date_text)
                    if d:
                        screening_rows.append((d, venue_text))

        if screening_rows:
            screening_rows.sort(key=lambda x: x[0])
            start_date, venue_name = screening_rows[0]

        # Fallback to festival start date
        if not start_date:
            logger.warning(f"[{SOURCE_NAME}] No screening date for {slug}, using fallback")
            start_date = datetime(year, _FESTIVAL_FALLBACK_MONTH, _FESTIVAL_FALLBACK_DAY, tzinfo=_JST)

        raw_description = (
            f"開催日時: {start_date.year}年{start_date.month:02d}月{start_date.day:02d}日\n\n"
        )
        if director:
            raw_description += f"監督: {director}\n"
        if country:
            raw_description += f"国: {country}\n"
        if synopsis:
            raw_description += f"\n{synopsis}"
        raw_description = raw_description.strip()

        return Event(
            source_name=SOURCE_NAME,
            source_id=source_id,
            source_url=film_url,
            original_language="ja",
            name_ja=name_ja,
            name_en=name_en or None,
            raw_title=name_ja,
            raw_description=raw_description,
            category=["movie"],
            start_date=start_date,
            end_date=None,
            location_name=venue_name,
            location_address=None,
            is_paid=True,
        )
