"""
Scraper for 台湾文化祭 (taiwanbunkasai.com).

Single-page static HTML site announcing one upcoming event at a time.
The organizer holds events at KITTE (twice a year) and 中野 (once a year).
Only the next event is shown on the homepage.

Strategy:
  1. Fetch the homepage with requests
  2. Extract the 開催日 section: "2026年6月26日（金）・27日（土）・28日（日）"
  3. Extract the 会場 section
  4. source_id = "taiwanbunkasai_{YYYY}_{MM}" — stable per event-month
"""

import logging
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

HOMEPAGE_URL = "https://taiwanbunkasai.com/"
SOURCE_NAME = "taiwanbunkasai"

# Known venue → (location_name, location_address) mapping
# Verified: https://taiwanbunkasai.com/ (2026-04-26)
_VENUE_MAP = [
    ("中野",  "中野区役所・四季の森公園",     "東京都中野区中野4丁目8-1"),
    ("KITTE", "KITTE 丸の内",               "東京都千代田区丸の内2-7-2"),
    ("kitte", "KITTE 丸の内",               "東京都千代田区丸の内2-7-2"),
    ("丸の内", "KITTE 丸の内",              "東京都千代田区丸の内2-7-2"),
]
_START_DATE_RE = re.compile(
    r"(20\d{2})年(\d{1,2})月(\d{1,2})日"
)
# Last day number in the same month range: "27日" "28日"
_LAST_DAY_RE = re.compile(r"(\d{1,2})日[（(）) 　]*(?:$|・|,|、|\n)")

# Venue: line after "● 会場" or "●会場"
_VENUE_RE = re.compile(
    r"[●•]\s*会場\s*\n+(.+?)(?:\n[●•]|\Z)",
    re.DOTALL,
)


def _parse_dates(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse start and end date from page text."""
    m = _START_DATE_RE.search(text)
    if not m:
        return None, None

    year = int(m.group(1))
    month = int(m.group(2))
    start_day = int(m.group(3))
    start_date = datetime(year, month, start_day)

    # Find the last day number mentioned in the same event block
    # Look at the text segment up to 200 chars after the date match
    segment = text[m.start() : m.start() + 200]
    day_nums = [int(d) for d in re.findall(r"(\d{1,2})日", segment)]
    end_day = max(day_nums) if day_nums else start_day

    try:
        end_date = datetime(year, month, end_day)
    except ValueError:
        end_date = start_date

    return start_date, end_date


def _parse_venue(text: str) -> Optional[str]:
    """Extract venue name(s) from page text."""
    m = _VENUE_RE.search(text)
    if not m:
        # Fallback: look for 「…」quoted venue names
        quoted = re.findall(r"「(.+?)」", text)
        if quoted:
            return " / ".join(quoted[:2])
        return None

    raw = m.group(1).strip()
    # Clean up: remove form placeholders, map markers, etc.
    raw = re.sub(r"\s+", " ", raw)
    return raw[:200]


class TaiwanbunkasaiScraper(BaseScraper):
    """Scrapes the current upcoming event from 台湾文化祭 (taiwanbunkasai.com)."""

    SOURCE_NAME = SOURCE_NAME

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

    def scrape(self) -> list[Event]:
        try:
            resp = self._session.get(HOMEPAGE_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("TaiwanbunkasaiScraper: fetch failed — %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove nav / footer / social widgets to avoid noise
        for tag in soup.select("script, style, nav, footer, form"):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        start_date, end_date = _parse_dates(text)
        if not start_date:
            logger.warning(
                "TaiwanbunkasaiScraper: could not extract start_date from homepage"
            )
            return []

        venue_raw = _parse_venue(text)
        # Clean up 会場 text — remove trailing notes about map etc.
        if venue_raw:
            venue = re.sub(r"\s*(会場地図.*|×.*)", "", venue_raw).strip()
        else:
            venue = None

        # Resolve location_name / location_address from venue text
        location_name: Optional[str] = venue
        location_address: Optional[str] = None
        if venue:
            for keyword, lname, laddr in _VENUE_MAP:
                if keyword in venue:
                    location_name = lname
                    location_address = laddr
                    break

        # source_id: stable per event-year-month
        source_id = f"taiwanbunkasai_{start_date.year}_{start_date.month:02d}"

        # Build description: full page text trimmed to the event info block
        # Find the section between "出店概要" and "開催実績"
        block_m = re.search(r"出店概要(.+?)開催実績", text, re.DOTALL)
        event_block = block_m.group(1).strip() if block_m else text[:800]

        date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
        if end_date and end_date != start_date:
            date_prefix += f" 〜 {end_date.strftime('%Y年%m月%d日')}"
        raw_description = date_prefix + "\n\n" + event_block

        # Page title as raw_title; name_ja includes year for merger similarity with iwafu
        title_tag = soup.find("title")
        page_title = title_tag.get_text(strip=True) if title_tag else "台湾文化祭"
        name_ja = f"台湾文化祭{start_date.year}"

        logger.info(
            "TaiwanbunkasaiScraper: found event %s start=%s venue=%r",
            source_id,
            start_date.date(),
            venue,
        )

        return [
            Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=HOMEPAGE_URL,
                official_url=HOMEPAGE_URL,  # official organiser page
                original_language="ja",
                name_ja=name_ja,
                raw_title=page_title,
                raw_description=raw_description,
                start_date=start_date,
                end_date=end_date,
                location_name=location_name,
                location_address=location_address,
                is_paid=False,  # 入場無料 — verified on official site
                category=["lifestyle_food", "performing_arts", "senses"],
            )
        ]
