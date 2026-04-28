"""
Scraper for 阪急うめだ本店 (Hankyu Umeda Honten) — event schedule.

Captures Taiwan-themed events from the weekly event calendar.
The page is static HTML; no Playwright required.

URL: https://www.hankyu-dept.co.jp/honten/event/
Rendering: static-html (requests + BeautifulSoup)

HTML structure (confirmed 2026-04-28):
  Weeks: <p id="week01" class="o-event-list__title"> — week header with date range
  Items: <article><div class="o-event" data-place="{code}"> … </div></article>
    - Title:  <p class="o-event__title">
    - Desc:   <p class="o-event__desc">
    - URL:    <div class="o-event"> > <a href="…">
    - Date+Venue: <div class="o-event__detail"> <p> ◎4月22日（水）～27日（月）\n◎9階 催場 </p>

source_id = hankyu_umeda_{slug}  where slug = last path segment of detail URL
            falls back to sha1(title+date_str)[:10] when no URL is present.
"""

import hashlib
import logging
import re
import time
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_NAME = "hankyu_umeda"
LISTING_URL = "https://www.hankyu-dept.co.jp/honten/event/"
BASE_URL = "https://www.hankyu-dept.co.jp"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.9",
}
_DELAY = 0.5  # seconds between requests

# Taiwan relevance: title OR description must match
_TAIWAN_RE = re.compile(r"台湾|台灣|Taiwan|taiwan|🇹🇼", re.IGNORECASE)

# Date extraction from "◎4月22日（水）～27日（月）" or "◎4月22日（水）～5月11日（月）"
# Captures: (start_month, start_day, end_month_or_None, end_day)
_DATE_SAME_MONTH = re.compile(
    r"◎\s*(\d{1,2})月(\d{1,2})日[^～〜]*[～〜]\s*(\d{1,2})日"
)
_DATE_DIFF_MONTH = re.compile(
    r"◎\s*(\d{1,2})月(\d{1,2})日[^～〜]*[～〜]\s*(\d{1,2})月(\d{1,2})日"
)
_DATE_SINGLE = re.compile(r"◎\s*(\d{1,2})月(\d{1,2})日")


def _infer_year(month: int, today: date) -> int:
    """Pick current year, rolling forward if the month is already past."""
    if month >= today.month:
        return today.year
    # If month < current month, it's likely next year
    # But within the 5-week window, it should still be this year or just crossed.
    # Use today to avoid skipping: if we're in Dec and month==1, it's next year.
    if today.month == 12 and month <= 3:
        return today.year + 1
    return today.year


def _parse_date_range(detail_text: str, today: date) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Extract start_date and end_date from the event detail block text.
    e.g. "◎4月22日（水）～27日（月）\n◎9階 催場"
    """
    # Try cross-month range first: ◎4月29日（水）～5月11日（月）
    m = _DATE_DIFF_MONTH.search(detail_text)
    if m:
        sm, sd, em, ed = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        year = _infer_year(sm, today)
        # end year: same year unless month wraps into next year
        end_year = year if em >= sm else year + 1
        try:
            start = datetime(year, sm, sd)
            end = datetime(end_year, em, ed)
            return start, end
        except ValueError:
            pass

    # Same-month range: ◎4月22日（水）～27日（月）
    m = _DATE_SAME_MONTH.search(detail_text)
    if m:
        sm, sd, ed = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year = _infer_year(sm, today)
        try:
            start = datetime(year, sm, sd)
            end = datetime(year, sm, ed)
            return start, end
        except ValueError:
            pass

    # Single day: ◎4月22日
    m = _DATE_SINGLE.search(detail_text)
    if m:
        sm, sd = int(m.group(1)), int(m.group(2))
        year = _infer_year(sm, today)
        try:
            dt = datetime(year, sm, sd)
            return dt, dt
        except ValueError:
            pass

    return None, None


def _build_source_id(detail_url: Optional[str], title: str, date_str: str) -> str:
    """Derive a stable source_id from the detail URL slug, or a hash fallback."""
    if detail_url:
        # e.g. https://website.hankyu-dept.co.jp/honten/h/taiwan_life/
        # Slug = "taiwan_life"
        slug = detail_url.rstrip("/").split("/")[-1]
        if slug and slug not in ("", "honten", "h"):
            return f"hankyu_umeda_{slug}"
    # Fallback: stable hash of title + raw date string
    raw = f"{title}|{date_str}"
    digest = hashlib.sha1(raw.encode()).hexdigest()[:10]
    return f"hankyu_umeda_{digest}"


class HankyuUmedaScraper(BaseScraper):
    """Scrapes Taiwan-related events from 阪急うめだ本店 weekly event schedule."""

    SOURCE_NAME = SOURCE_NAME

    def _get(self, url: str) -> BeautifulSoup:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.encoding = "utf-8"
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def scrape(self) -> list[Event]:
        today = date.today()
        logger.info("Fetching Hankyu Umeda event schedule: %s", LISTING_URL)
        time.sleep(_DELAY)

        try:
            soup = self._get(LISTING_URL)
        except Exception as exc:
            logger.error("Failed to fetch %s: %s", LISTING_URL, exc)
            return []

        events: list[Event] = []
        articles = soup.select("article div.o-event")
        logger.info("Found %d event items", len(articles))

        for div in articles:
            try:
                event = self._parse_event(div, today)
                if event:
                    events.append(event)
            except Exception as exc:
                logger.warning("Skipping event due to error: %s", exc, exc_info=True)

        logger.info(
            "Hankyu Umeda: %d total items → %d Taiwan-related", len(articles), len(events)
        )
        return events

    def _parse_event(self, div: Tag, today: date) -> Optional[Event]:
        """Parse a single <div class="o-event"> into an Event, or return None."""
        # --- Title ---
        title_el = div.select_one("p.o-event__title")
        title = title_el.get_text(" ", strip=True) if title_el else ""

        # --- Description ---
        desc_el = div.select_one("p.o-event__desc")
        desc = desc_el.get_text(strip=True) if desc_el else ""

        # --- Taiwan filter ---
        if not _TAIWAN_RE.search(title) and not _TAIWAN_RE.search(desc):
            return None

        # --- Detail URL ---
        link_el = div.select_one("a[href]")
        raw_url = link_el.get("href", "") if link_el else ""
        # Make absolute
        if raw_url and raw_url.startswith("/"):
            detail_url = BASE_URL + raw_url
        elif raw_url.startswith("http"):
            detail_url = raw_url
        else:
            detail_url = LISTING_URL

        # --- Date & Venue from detail block ---
        detail_el = div.select_one("div.o-event__detail")
        detail_text = detail_el.get_text("\n", strip=True) if detail_el else ""

        start_date, end_date = _parse_date_range(detail_text, today)

        # Extract raw date string for fallback source_id
        date_str_match = re.search(r"◎[^\n◎]{3,50}", detail_text)
        date_str = date_str_match.group(0).strip() if date_str_match else ""

        # --- Location ---
        # Venue is the second ◎ line: e.g. "◎9階 催場"
        venue_match = re.findall(r"◎\s*(.+)", detail_text)
        location_name: Optional[str] = None
        if len(venue_match) >= 2:
            location_name = venue_match[1].strip()
        elif len(venue_match) == 1:
            # If only one line, it might be "◎9階 催場" (no date)
            if not re.search(r"\d+月\d+日", venue_match[0]):
                location_name = venue_match[0].strip()

        full_location = f"阪急うめだ本店 {location_name}" if location_name else "阪急うめだ本店"

        # --- source_id ---
        source_id = _build_source_id(raw_url if raw_url.startswith("http") else None, title, date_str)

        # --- raw_description ---
        date_prefix = ""
        if start_date:
            date_prefix = f"開催日時: {start_date.year}年{start_date.month}月{start_date.day}日\n\n"
        raw_desc = f"{date_prefix}{desc}\n\n{detail_text}".strip()

        return Event(
            source_name=SOURCE_NAME,
            source_id=source_id,
            source_url=detail_url,
            original_language="ja",
            raw_title=title,
            raw_description=raw_desc,
            name_ja=title,
            start_date=start_date,
            end_date=end_date,
            location_name=full_location,
            location_address="大阪府大阪市北区角田町8-7 阪急うめだ本店",
            category=["lifestyle_food"],
            is_active=True,
        )
