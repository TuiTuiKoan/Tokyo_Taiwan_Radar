"""Scraper for 新文芸坐 (Shin-Bungeiza)

Source URL: https://www.shin-bungeiza.com/schedule
Platform  : Static HTML — no JS rendering required
Source name: shin_bungeiza
Source ID : shin_bungeiza_{slug}  (slugified movie title)

Strategy:
  1. Fetch the schedule page
  2. For each section.schedule-box-wrap, find the <h1> movie title
  3. Apply Taiwan relevance filter on the extended schedule content (nihon-date)
     - Positive signals: `・台/` in nihon-date (<small> national code)
     - Positive signal: link to `taiwanfilm.net` in nihon-date
     - Positive signal: Taiwan keywords in catch/description text
  4. Extract date range from schedule-date <p> element
  5. Date format: "<em>5/8</em>（金）～<em>14</em>（木）"
     → start=5/8, end=5/14 (same month as start)

Taiwan relevance filter:
  - `・台/` in <small> national code (most reliable: "2021・台/128分")
  - Link href containing `taiwanfilm.net`
  - General keywords: ["台湾", "Taiwan", "臺灣", "金馬"] in full section text

Venue (fixed):
  新文芸坐
  東京都豊島区東池袋1丁目43番5号
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

SOURCE_NAME = "shin_bungeiza"

_SCHEDULE_URL = "https://www.shin-bungeiza.com/schedule"
_JST = timezone(timedelta(hours=9))

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

_VENUE_NAME = "新文芸坐"
_VENUE_ADDRESS = "東京都豊島区東池袋1丁目43番5号"

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "金馬"]

# Date patterns in schedule-date element
# "5/8（金）～14（木）"   → start=M/D end=M/D2 (end day only, same month)
# "4/20（月）〜28（火）"  → same
# "5/29（金）～6/4（木）" → end has explicit month
_DATE_RANGE_RE = re.compile(
    r"(\d{1,2})/(\d{1,2})[^〜～\n]*?[〜～](\d{1,2})(?:/(\d{1,2}))?[^0-9\n]"
)
_DATE_SINGLE_RE = re.compile(r"(\d{1,2})/(\d{1,2})[（(]")


def _is_taiwan_relevant(section_soup: BeautifulSoup, section_text: str) -> bool:
    """Check Taiwan relevance from multiple signals."""
    # Signal 1: national code in <small> — "(2021・台/128分)"
    for small in section_soup.find_all("small"):
        if "・台/" in small.get_text() or "・台 /" in small.get_text():
            return True
    # Signal 2: link to taiwanfilm.net
    for a in section_soup.find_all("a", href=True):
        if "taiwanfilm.net" in a["href"]:
            return True
    # Signal 3: explicit Taiwan keywords in section text
    return any(kw in section_text for kw in _TAIWAN_KEYWORDS)


def _infer_year(month: int, today: datetime) -> int:
    if month < today.month - 3:
        return today.year + 1
    return today.year


def _slugify(title: str) -> str:
    """Create a stable slug from movie title for source_id."""
    title = title.strip().lower()
    title = re.sub(r"[^\w\u3040-\u30ff\u4e00-\u9fff]", "_", title)
    title = re.sub(r"_+", "_", title).strip("_")
    return title[:60]


class ShinBungeizaScraper(BaseScraper):
    """Scraper for 新文芸坐 (Ikebukuro art cinema with regular Taiwan special screenings)."""

    SOURCE_NAME = SOURCE_NAME

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": _USER_AGENT,
            "Accept-Language": "ja,en;q=0.9",
        })

    def scrape(self) -> list[Event]:
        today = datetime.now(tz=_JST)
        resp = self._session.get(_SCHEDULE_URL, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        events: list[Event] = []
        seen_ids: set[str] = set()

        # Each movie is in a section.schedule-box-wrap
        # The <h1> + <p class="schedule-date"> are in <div class="schedule-box-txt">
        # The full programme content incl. nihon-date is elsewhere in the same wrap

        for section in soup.find_all(class_="schedule-box-wrap"):
            try:
                event = self._parse_section(section, today, seen_ids)
                if event:
                    events.append(event)
                    seen_ids.add(event.source_id)
            except Exception:
                logger.exception("shin_bungeiza: failed to parse section")

        # Also scan all <h1> elements for movies NOT inside schedule-box-wrap
        # (some movies only appear in the daily schedule list, not in box-wrap)
        # These have nihon-date links for Taiwan detection
        events += self._parse_nihon_date_only(soup, today, seen_ids)

        logger.info("shin_bungeiza: %d Taiwan events found", len(events))
        return events

    # ------------------------------------------------------------------

    def _parse_section(
        self,
        section: BeautifulSoup,
        today: datetime,
        seen_ids: set[str],
    ) -> Event | None:
        section_text = section.get_text(separator="\n", strip=True)
        if not _is_taiwan_relevant(section, section_text):
            return None

        h1 = section.find("h1")
        if not h1:
            return None
        title = h1.get_text(strip=True)
        if not title:
            return None

        source_id = f"shin_bungeiza_{_slugify(title)}"
        if source_id in seen_ids:
            return None

        date_p = section.find(class_="schedule-date")
        date_text = date_p.get_text(separator=" ", strip=True) if date_p else ""
        start_date, end_date = self._parse_dates(date_text, today)
        if start_date is None:
            logger.warning("shin_bungeiza: no start_date for %s", title)
            return None

        date_prefix = f"開催日時: {start_date.year}年{start_date.month}月{start_date.day}日\n\n"
        raw_description = date_prefix + section_text

        return Event(
            source_name=SOURCE_NAME,
            source_id=source_id,
            source_url=_SCHEDULE_URL,
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

    def _parse_nihon_date_only(
        self,
        soup: BeautifulSoup,
        today: datetime,
        seen_ids: set[str],
    ) -> list[Event]:
        """Parse Taiwan films visible only through nihon-date links in the schedule grid.

        Structure in the DOM:
          <div class="schedule-content-txt">
            <p class="nihon-date"><a>タイトル</a><small>(2021・台/128分)…</small></p>
            <h2><em>5/8</em>（金）</h2>   ← first h2: start date with M/D
            <div class="schedule-program">…</div>
            <h2><em>9</em>（土）</h2>     ← subsequent h2: day only (same month)
            …
            <h2><em>14</em>（木）</h2>   ← last h2: end day
          </div>
        """
        events: list[Event] = []
        processed_titles: set[str] = set()

        for p in soup.find_all(class_="nihon-date"):
            p_text = p.get_text()
            if not _is_taiwan_relevant(p, p_text):
                continue
            # Get movie title from link text or plain text
            a = p.find("a")
            title = (a.get_text(strip=True) if a else p.get_text(strip=True))
            if not title or title in processed_titles:
                continue
            processed_titles.add(title)

            source_id = f"shin_bungeiza_{_slugify(title)}"
            if source_id in seen_ids:
                continue
            seen_ids.add(source_id)

            # Date: h2 elements AFTER p inside the same parent container
            parent = p.parent
            if parent is None:
                continue

            # Collect all h2s that follow the nihon-date p in the same parent
            h2_elements = []
            collecting = False
            for child in parent.children:
                if child is p:
                    collecting = True
                    continue
                if collecting and getattr(child, "name", None) == "h2":
                    h2_elements.append(child)

            if not h2_elements:
                logger.warning("shin_bungeiza: no h2 dates found for %s", title)
                continue

            # First h2: start date — should have M/D format in <em>
            start_h2_text = h2_elements[0].get_text(strip=True)
            start_date, _ = self._parse_dates(start_h2_text, today)
            if start_date is None:
                logger.warning("shin_bungeiza: no start_date for %s (h2=%s)", title, start_h2_text)
                continue

            # Last h2: end day — may be day-only (e.g. "14（木）" same month as start)
            end_h2_text = h2_elements[-1].get_text(strip=True)
            end_day_m = re.match(r"(\d{1,2})[（(]", end_h2_text)
            if end_day_m:
                end_day = int(end_day_m.group(1))
                try:
                    end_date: datetime | None = datetime(start_date.year, start_date.month, end_day, tzinfo=_JST)
                    # Handle month wrap (e.g. start 5/30, end day 6 → must be 6/6)
                    if end_date < start_date:
                        # Try adding a month
                        next_month = start_date.month % 12 + 1
                        next_year = start_date.year + (1 if start_date.month == 12 else 0)
                        end_date = datetime(next_year, next_month, end_day, tzinfo=_JST)
                except ValueError:
                    end_date = start_date
            else:
                end_date = start_date

            date_prefix = f"開催日時: {start_date.year}年{start_date.month}月{start_date.day}日\n\n"
            raw_description = date_prefix + p_text

            events.append(Event(
                source_name=SOURCE_NAME,
                source_id=source_id,
                source_url=_SCHEDULE_URL,
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
            ))
        return events

    def _parse_dates(
        self, text: str, today: datetime
    ) -> tuple[datetime | None, datetime | None]:
        """Parse date text into start/end datetimes.

        Formats handled:
          "5/8（金）～14（木）"      → start=5/8, end=5/14 (end day only)
          "5/29（金）～6/4（木）"    → start=5/29, end=6/4
          "5/8（金）"               → start=5/8, end=5/8
          "5 / 8 （金） ～ 14 （木）" (with spaces from get_text)
        """
        # Normalize: remove labels like "2本目割", "トーク", "オールナイト"
        text = re.sub(r"[ぁ-ん一-龥ァ-ン！-｟\s]+?(?=\d)", " ", text).strip()

        m = _DATE_RANGE_RE.search(text)
        if m:
            sm, sd = int(m.group(1)), int(m.group(2))
            # If group(4) is set → end has explicit month: M/D
            # If group(4) is None → end day only (same month as start)
            if m.group(4):
                em, ed = int(m.group(3)), int(m.group(4))
            else:
                em, ed = sm, int(m.group(3))
            year = _infer_year(sm, today)
            start = datetime(year, sm, sd, tzinfo=_JST)
            end_year = year if em >= sm else year + 1
            try:
                end = datetime(end_year, em, ed, tzinfo=_JST)
            except ValueError:
                end = start
            return start, end

        m2 = _DATE_SINGLE_RE.search(text)
        if m2:
            sm, sd = int(m2.group(1)), int(m2.group(2))
            year = _infer_year(sm, today)
            dt = datetime(year, sm, sd, tzinfo=_JST)
            return dt, dt

        return None, None
