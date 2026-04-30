"""Scraper for 東京都現代美術館 (MOT — Museum of Contemporary Art Tokyo).

Strategy:
  1. Fetch all exhibitions via JSON API:
       GET https://www.mot-art-museum.jp/json/exhibitions/exhibitions.json
     Returns a list of ~250+ records including future and past exhibitions.
  2. Filter to exhibitions where `end >= today - LOOKBACK_DAYS`.
  3. For efficiency, only visit individual pages for `type == "exhibitions"`
     (special exhibitions) and JSON entries whose title contains a Taiwan keyword.
     Collection shows (`type == "collections"`) are skipped unless title matches.
  4. On each individual page, check body text for Taiwan keywords.
     If found, extract description, venue, and organizer from <main>/<dl>.
  5. Build one Event per Taiwan-relevant exhibition.

source_name : mot
source_id   : mot_{id}          (JSON integer id — stable across runs)
source_url  : https://www.mot-art-museum.jp{permalink}

Taiwan relevance rationale:
  MOT hosts ~1–2 Taiwan-related special exhibitions per year, co-organised with
  Taiwanese institutions (e.g. 台南市美術館, 国立台湾美術館, 台湾文化部).
  The JSON title alone rarely contains "台湾"; relevance must be verified on the
  individual page (organizer list, body text).

Date format: JSON `start` / `end` fields are integer YYYYMMDD.
  e.g. 20260905 → datetime(2026, 9, 5)

No Playwright needed — JSON API + static HTML individual pages.
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

_JSON_URL = "https://www.mot-art-museum.jp/json/exhibitions/exhibitions.json"
_BASE_URL = "https://www.mot-art-museum.jp"

_JST = timezone(timedelta(hours=9))
_LOOKBACK_DAYS = 30   # include exhibitions that ended up to 30 days ago

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "台灣", "台南", "台北", "高雄", "TAIWAN"]

# Selectors for the <dl> info table on individual pages
_DL_LABELS = {
    "会期": "period",
    "会場": "venue",
    "主催": "organizer",
}

MOT_ADDRESS = "〒135-0022 東京都江東区三好4-1-1"
MOT_LOCATION = "東京都現代美術館"


def _contains_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _parse_yyyymmdd(raw) -> datetime | None:
    """Parse integer or string YYYYMMDD → JST datetime."""
    s = str(raw).strip()
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), tzinfo=_JST)
    except ValueError:
        return None


def _parse_dl(soup: BeautifulSoup) -> dict[str, str]:
    """Extract key→value from <dl> info table on individual exhibition page.

    The table looks like:
        <dl>
          <dt>会期</dt><dd>2026年9月5日（土）～12月13日（日）</dd>
          <dt>会場</dt><dd>東京都現代美術館 企画展示室 1F/3F</dd>
          <dt>主催</dt><dd>東京都現代美術館（公益財団法人…）、台南市美術館</dd>
          ...
        </dl>
    """
    result: dict[str, str] = {}
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            key = dt.get_text(strip=True)
            if key in _DL_LABELS:
                result[key] = dd.get_text(" ", strip=True)
    return result


def _extract_description(main_soup: BeautifulSoup, dl_info: dict[str, str]) -> str:
    """Extract exhibition description text from <main>."""
    if not main_soup:
        return ""
    lines = [l.strip() for l in main_soup.get_text("\n").splitlines() if l.strip()]
    # Skip until after the title line (first non-empty), collect body text
    # Typical structure: [title, body paragraphs..., "基本情報", DL data, nav links]
    desc_lines: list[str] = []
    in_body = False
    for line in lines:
        if line == "基本情報":
            break
        if in_body:
            desc_lines.append(line)
        else:
            # First non-trivial line is the title; start collecting after that
            in_body = True
    # Limit to 600 chars
    return "\n".join(desc_lines)[:600].strip()


class MotScraper(BaseScraper):
    """Scrapes Taiwan-related exhibition events from 東京都現代美術館 (MOT)."""

    SOURCE_NAME = "mot"

    def scrape(self) -> list[Event]:
        today = datetime.now(_JST)
        cutoff = today - timedelta(days=_LOOKBACK_DAYS)
        events: list[Event] = []

        exhibitions = self._fetch_json()
        if not exhibitions:
            logger.warning("MOT: could not fetch exhibitions JSON")
            return []

        logger.info("MOT: %d exhibitions in JSON, filtering candidates…", len(exhibitions))

        for ex in exhibitions:
            end_date = _parse_yyyymmdd(ex.get("end", ""))
            if end_date and end_date < cutoff:
                continue  # ended too long ago

            start_date = _parse_yyyymmdd(ex.get("start", ""))
            permalink = ex.get("permalink", "")
            if not permalink:
                continue

            ex_type = ex.get("type", "")
            json_title = ex.get("title", "")
            json_crown = ex.get("crownName", "")

            # Fast-track: JSON title already contains a Taiwan keyword
            title_has_taiwan = _contains_taiwan(json_title) or _contains_taiwan(json_crown)

            # Only fetch individual page for special exhibitions (type==exhibitions)
            # or when title already hints at Taiwan
            if ex_type != "exhibitions" and not title_has_taiwan:
                continue

            event = self._process_exhibition(ex, start_date, end_date)
            if event:
                events.append(event)
            time.sleep(0.4)

        logger.info("MotScraper: %d Taiwan exhibitions found", len(events))
        return events

    # ------------------------------------------------------------------
    def _process_exhibition(
        self,
        ex: dict,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> Event | None:
        permalink = ex["permalink"]
        url = _BASE_URL + permalink
        wp_id = ex["id"]
        json_title = ex.get("title", "")
        another_date = ex.get("anotherDate", "")

        try:
            r = requests.get(url, headers=_HEADERS, timeout=15)
            r.raise_for_status()
        except Exception as exc:
            logger.warning("MOT: failed to fetch %s: %s", url, exc)
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        main = soup.find("main")
        page_text = (main or soup).get_text("\n")

        # Taiwan relevance check on full page text
        if not _contains_taiwan(page_text):
            return None

        dl_info = _parse_dl(soup)
        organizer = dl_info.get("主催", "")
        venue_raw = dl_info.get("会場", MOT_LOCATION)
        venue = venue_raw.split("\n")[0].strip() or MOT_LOCATION

        description = _extract_description(main, dl_info)

        # Build raw_description with date prefix for annotator
        date_prefix = ""
        if start_date:
            date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n\n"
        raw_desc = f"{date_prefix}{page_text[:800]}".strip()

        event = Event(
            source_name=self.SOURCE_NAME,
            source_id=f"mot_{wp_id}",
            source_url=url,
            original_language="ja",
            name_ja=json_title or None,
            description_ja=description or None,
            raw_title=json_title,
            raw_description=raw_desc or None,
            start_date=start_date,
            end_date=end_date,
            location_name=venue,
            location_address=MOT_ADDRESS,
            is_paid=True,
            category=["art"],
        )

        logger.info(
            "  ✓ mot_%d [%s] %s (%s–%s) organizer=%s",
            wp_id,
            permalink.strip("/").split("/")[-1],
            json_title[:50],
            start_date.strftime("%Y-%m-%d") if start_date else "?",
            end_date.strftime("%Y-%m-%d") if end_date else "?",
            organizer[:40],
        )
        return event

    # ------------------------------------------------------------------
    def _fetch_json(self) -> list[dict]:
        try:
            r = requests.get(_JSON_URL, headers=_HEADERS, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.warning("MOT: JSON fetch error: %s", exc)
            return []
