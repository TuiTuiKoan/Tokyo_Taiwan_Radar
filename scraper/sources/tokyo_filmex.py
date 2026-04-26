"""Scraper for 東京フィルメックス (Tokyo Filmex)

Source URL: https://filmex.jp/program/{cat}/
Platform  : Static HTML — no JS required (requires User-Agent or returns 403)
Source name: tokyo_filmex
Source ID : tokyo_filmex_{year}_{cat}{num}  e.g. tokyo_filmex_2025_fc2

Program categories scraped:
  fc  — フィルメックス・コンペティション
  ss  — 特別招待作品
  mj  — メイド・イン・ジャパン

Strategy:
  1. Fetch /program/fc/ to detect festival year (from page title)
  2. If festival_year < today.year → festival is over → return []
  3. For each category, parse listing entries (div.imgL_wrap02)
  4. Taiwan filter: first bare <p> tag starts with "台湾"
  5. Follow detail link (ul.nav03.type04 li.next a[href]) → fc2.html etc.
  6. Extract: title, synopsis, screening date+venue from detail page
  7. source_id = tokyo_filmex_{year}_{cat}{num}

Listing structure (per film):
  div.imgL_wrap02 > div.textWrap.areaLink
    p.text01                  → Japanese title / English title ("女の子 / Girl")
    p (no class)              → "台湾 / 2025 / 125分 / 監督：…" (country first)
    ul.nav03.type04 li.next a → relative href e.g. "fc2.html"

Detail page (filmex.jp/program/{cat}/{id}.html):
  h1 (inside main article)   → "女の子" or combined "女の子 / Girl"
  p.screenlist ul li         → "11月23日（日）\n15:20 -\n朝日 …"
  section / div with text    → synopsis

Date format: "11月23日（日）" → month, day in festival year
Venue abbreviations:
  朝日 → 有楽町朝日ホール
  HTC  → ヒューマントラストシネマ有楽町

Note: 2026 program is typically published around October each year.
Until then, festival_year < today.year and this scraper returns [].
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "tokyo_filmex"  # _scraper_key: TokyoFilmexScraper → tokyo_filmex

_BASE_URL = "https://filmex.jp"

_JST = timezone(timedelta(hours=9))

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

# Program category pages to scrape
_CATEGORIES = ["fc", "ss", "mj"]

# Venue abbreviation → full name
_VENUE_MAP = {
    "朝日": "有楽町朝日ホール",
    "HTC": "ヒューマントラストシネマ有楽町",
}

# Match "MM月DD日（曜）" in screening text
_DATE_RE = re.compile(r"(\d{1,2})月(\d{1,2})日（\w+）")

# Match year in page title like "東京フィルメックス2025"
_YEAR_RE = re.compile(r"(\d{4})")


def _parse_filmex_date(text: str, year: int) -> datetime | None:
    m = _DATE_RE.search(text)
    if m:
        return datetime(year, int(m.group(1)), int(m.group(2)), tzinfo=_JST)
    return None


def _expand_venue(short_name: str) -> str:
    for abbr, full in _VENUE_MAP.items():
        if abbr in short_name:
            return full
    return short_name


class TokyoFilmexScraper(BaseScraper):
    """Scraper for 東京フィルメックス program pages."""

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": _USER_AGENT,
            "Accept-Language": "ja,en;q=0.9",
        })
        self._today = datetime.now(_JST)

    def scrape(self) -> list[Event]:
        festival_year = self._detect_year()
        if not festival_year:
            logger.warning(f"[{SOURCE_NAME}] Could not detect festival year")
            return []

        # If the festival already ended, skip (program will not be updated)
        if festival_year < self._today.year:
            logger.info(
                f"[{SOURCE_NAME}] Festival year {festival_year} < {self._today.year}: "
                "skipping (past festival, no new events)"
            )
            return []

        events = []
        for cat in _CATEGORIES:
            cat_events = self._scrape_category(cat, festival_year)
            events.extend(cat_events)
            if cat_events:
                time.sleep(0.5)

        logger.info(f"[{SOURCE_NAME}] {len(events)} events produced for {festival_year}")
        return events

    def _detect_year(self) -> int | None:
        """Detect festival year from /program/fc/ page title."""
        url = f"{_BASE_URL}/program/fc/"
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[{SOURCE_NAME}] Could not fetch {url}: {e}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""
        years = _YEAR_RE.findall(title)
        if years:
            return int(years[0])

        # Fallback: look in h1 or first heading
        for h in soup.find_all(["h1", "h2"]):
            m_years = _YEAR_RE.findall(h.get_text())
            if m_years:
                return int(m_years[0])

        return None

    def _scrape_category(self, cat: str, year: int) -> list[Event]:
        url = f"{_BASE_URL}/program/{cat}/"
        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[{SOURCE_NAME}] Failed to fetch {url}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        events = []

        for block in soup.select("div.imgL_wrap02"):
            text_wrap = block.select_one("div.textWrap.areaLink")
            if not text_wrap:
                continue

            # Title from p.text01
            title_el = text_wrap.select_one("p.text01")
            if not title_el:
                continue
            title_text = title_el.get_text(strip=True)

            # Country line: first <p> without class
            country_line = ""
            for p in text_wrap.find_all("p"):
                if p.get("class"):
                    continue
                country_line = p.get_text(strip=True)
                break

            # Taiwan filter
            if not country_line.startswith("台湾"):
                continue

            # Detail page link
            detail_a = text_wrap.select_one("ul.nav03.type04 li.next a[href]")
            if not detail_a:
                continue
            rel_href = detail_a.get("href", "")
            # Extract numeric ID from "fc2.html" → "2" (or "ss3.html" → "3")
            id_m = re.search(r"[a-z]+(\d+)\.html", rel_href)
            film_num = id_m.group(1) if id_m else rel_href.replace(".html", "")
            source_id = f"{SOURCE_NAME}_{year}_{cat}{film_num}"
            detail_url = f"{_BASE_URL}/program/{cat}/{rel_href}"

            time.sleep(0.3)
            ev = self._scrape_detail(source_id, detail_url, title_text, country_line, year)
            if ev:
                events.append(ev)

        return events

    def _scrape_detail(
        self, source_id: str, url: str, listing_title: str, country_line: str, year: int
    ) -> Event | None:
        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.debug(f"[{SOURCE_NAME}] Could not fetch detail {url}: {e}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Determine Japanese and English title from listing_title
        # Format: "女の子 / Girl" or "女の子"
        title_parts = [t.strip() for t in listing_title.split(" / ") if t.strip()]
        name_ja = title_parts[0] if title_parts else listing_title
        name_en = title_parts[1] if len(title_parts) > 1 else None

        # Director from country line: "台湾 / 2025 / 125分 /\n監督：スー・チー"
        director = ""
        for line in country_line.replace("\u3000", " ").splitlines():
            if "監督" in line:
                director = re.sub(r"監督[：:]?", "", line).strip()
                break

        # Synopsis: look for the main description paragraph
        synopsis = ""
        for el in soup.select("div.textWrap p, article p, main p"):
            pt = el.get_text(strip=True)
            # Skip very short texts and venue/ticket info
            if len(pt) < 80:
                continue
            if any(kw in pt for kw in ["チケット", "上映", "劇場名"]):
                continue
            synopsis = pt
            break

        # Screening dates and venues from screening list
        # Pattern: each li contains "MM月DD日（曜）\nHH:MM -\n朝日 …" or similar
        start_date = None
        venue_name = None

        # Try structured screening list
        for container in soup.select("p.screenlist, ul.screenlist, div.screenlist"):
            for li in container.find_all("li"):
                text = li.get_text(separator="\n", strip=True)
                d = _parse_filmex_date(text, year)
                if d and start_date is None:
                    start_date = d
                    # Venue: look for known abbreviations
                    for abbr in _VENUE_MAP:
                        if abbr in text:
                            venue_name = _VENUE_MAP[abbr]
                            break
                    if not venue_name:
                        # Use first non-date/non-time line as venue
                        for line in text.splitlines():
                            if _DATE_RE.search(line) or re.search(r"\d+:\d+", line):
                                continue
                            line = line.strip()
                            if line:
                                venue_name = _expand_venue(line.split("（")[0].strip())
                                break
                if start_date:
                    break
            if start_date:
                break

        # Fallback: scan all text nodes for date pattern
        if not start_date:
            body_text = soup.get_text(separator="\n")
            for line in body_text.splitlines():
                d = _parse_filmex_date(line, year)
                if d:
                    start_date = d
                    for abbr, full in _VENUE_MAP.items():
                        if abbr in line:
                            venue_name = full
                            break
                    break

        if not start_date:
            logger.warning(f"[{SOURCE_NAME}] No date found for {source_id}")
            return None

        raw_description = (
            f"開催日時: {start_date.year}年{start_date.month:02d}月{start_date.day:02d}日\n\n"
        )
        raw_description += country_line
        if director:
            raw_description += f"\n監督: {director}"
        if synopsis:
            raw_description += f"\n\n{synopsis}"
        raw_description = raw_description.strip()

        return Event(
            source_name=SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            name_ja=name_ja,
            name_en=name_en,
            raw_title=listing_title,
            raw_description=raw_description,
            category=["movie"],
            start_date=start_date,
            end_date=None,
            location_name=venue_name,
            location_address=None,
            is_paid=True,
        )
