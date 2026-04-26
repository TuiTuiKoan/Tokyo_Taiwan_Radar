"""Scraper for 台湾發祭 Taiwan Faasai

Source URL: https://taiwanfaasai.com/outline
Platform  : Static HTML (no JS rendering required)
Source name: taiwan_faasai
Source ID : taiwan_faasai_{year}  (e.g. taiwan_faasai_2026)

Strategy:
  1. Fetch https://taiwanfaasai.com/outline
  2. Extract event dates from text (multi-day format: 8月28日(金)～8月30日(日))
  3. Extract year from page title or heading (e.g. "台湾發祭 Taiwan Faasai 2026")
  4. Source ID is stable per year: taiwan_faasai_{year}

Date format on page:
  "2026年\n8月28日(金) ・29日(土)  ・30日(日)11:00 - 21:00（予定）"
  → start_date: 2026-08-28, end_date: 2026-08-30

Venue (fixed):
  上野恩賜公園 竹の台広場（噴水前広場）
  東京都台東区上野公園8番（竹の台広場）
"""

import logging
import re
import warnings
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "taiwan_faasai"

_OUTLINE_URL = "https://taiwanfaasai.com/outline"

_JST = timezone(timedelta(hours=9))

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

_VENUE_NAME = "上野恩賜公園 竹の台広場（噴水前広場）"
_VENUE_ADDRESS = "東京都台東区上野公園8番（竹の台広場）"

# Pattern: 8月28日(金) → month=8, day=28
_DATE_DAY_RE = re.compile(r"(\d{1,2})月(\d{1,2})日")
# Pattern: additional days "・29日(土) ・30日(日)" → day=29, day=30
_EXTRA_DAY_RE = re.compile(r"・(\d{1,2})日")
# Pattern: year in heading "台湾發祭 Taiwan Faasai 2026"
_YEAR_RE = re.compile(r"20\d{2}")


class TaiwanFaasaiScraper(BaseScraper):
    """Scraper for 台湾發祭 Taiwan Faasai (annual outdoor festival in Ueno)."""

    def scrape(self) -> list[Event]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                resp = requests.get(
                    _OUTLINE_URL,
                    headers={"User-Agent": _USER_AGENT, "Accept-Language": "ja,en;q=0.9"},
                    timeout=20,
                    verify=False,  # site has self-signed cert issues
                )
                resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[{SOURCE_NAME}] Failed to fetch {_OUTLINE_URL}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)

        year = self._extract_year(text)
        if not year:
            logger.warning(f"[{SOURCE_NAME}] Could not extract year from page")
            return []

        start_date, end_date = self._extract_dates(text, year)
        if not start_date:
            logger.warning(f"[{SOURCE_NAME}] Could not extract dates from page")
            return []

        source_id = f"{SOURCE_NAME}_{year}"

        # Build description from outline section
        raw_description = self._build_description(text, start_date, end_date, year)

        event = Event(
            source_name=SOURCE_NAME,
            source_id=source_id,
            source_url=_OUTLINE_URL,
            original_language="ja",
            name_ja=f"台湾發祭 Taiwan Faasai {year}",
            raw_title=f"台湾發祭 Taiwan Faasai {year}",
            raw_description=raw_description,
            category=["lifestyle_food"],
            start_date=start_date,
            end_date=end_date,
            location_name=_VENUE_NAME,
            location_address=_VENUE_ADDRESS,
            is_paid=False,
        )

        logger.info(f"[{SOURCE_NAME}] Found event: {event.name_ja} ({start_date.date()} – {end_date.date() if end_date else '?'})")
        return [event]

    def _extract_year(self, text: str) -> int | None:
        """Extract year from page text (e.g. '台湾發祭 Taiwan Faasai 2026')."""
        for m in _YEAR_RE.finditer(text):
            y = int(m.group())
            if 2024 <= y <= 2030:
                return y
        return None

    def _extract_dates(self, text: str, year: int):
        """Extract start_date and end_date from the outline page text.

        The page has:
          "2026年\n8月28日(金) ・29日(土) ・30日(日)11:00 - 21:00（予定）"

        Returns (start_date, end_date) as timezone-aware datetime objects.
        """
        # Find the primary date line: "8月28日(金)"
        m = _DATE_DAY_RE.search(text)
        if not m:
            return None, None

        start_month = int(m.group(1))
        start_day = int(m.group(2))
        start_date = datetime(year, start_month, start_day, tzinfo=_JST)

        # Find the last additional day in the same segment: "・30日(日)"
        # Search in text from start match onwards, up to a newline or end of day list
        segment_start = m.start()
        segment = text[segment_start: segment_start + 100]
        extra_days = _EXTRA_DAY_RE.findall(segment)

        end_date = None
        if extra_days:
            last_day = int(extra_days[-1])
            end_date = datetime(year, start_month, last_day, tzinfo=_JST)

        return start_date, end_date

    def _build_description(self, text: str, start_date: datetime, end_date: datetime | None, year: int) -> str:
        """Build a raw_description with 開催日時 prefix."""
        date_prefix = f"開催日時: {start_date.year}年{start_date.month:02d}月{start_date.day:02d}日"
        if end_date:
            date_prefix += f"～{end_date.year}年{end_date.month:02d}月{end_date.day:02d}日"
        date_prefix += "\n\n"

        # Extract the relevant section from the page text
        # Look for the 開催概要 / outline section
        section = ""
        lines = text.split("\n")
        in_section = False
        for line in lines:
            if "開催概要" in line or "名称" in line:
                in_section = True
            if in_section:
                section += line + "\n"
                if "問合せ" in line or "メールアドレス" in line:
                    break

        return date_prefix + (section.strip() if section else text[:800])
