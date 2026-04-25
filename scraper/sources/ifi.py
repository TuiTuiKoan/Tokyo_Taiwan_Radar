"""
Scraper for 東京大学未来ビジョン研究センター (IFI) — ifi.u-tokyo.ac.jp

IFI (Institute for Future Initiatives, The University of Tokyo) hosts academic
seminars and workshops. Taiwan-related events appear occasionally (~1–2/year),
typically joint seminars with National Taiwan University or Taiwan-Japan
comparative research events.

Strategy:
  1. Fetch https://ifi.u-tokyo.ac.jp/event/ (upcoming events — no pagination)
  2. For each card: check title for Taiwan keywords → skip non-Taiwan events
  3. Load detail page → extract dates, venue, description
  4. source_id = "ifi_{post_id}" (numeric WordPress post ID from /event/{id}/)

Taiwan keyword filter:
  ["台湾", "Taiwan", "臺灣"]
  Applied to card title + detail page full text.

Detail page structure:
  Labels on one line, values on the next line (inner_text):
    日程：  → YYYY年MM月DD日（曜日）
    時間：  → HH:MM-HH:MM
    会場：  → venue name / address
    主催：  → organizer(s)
"""

import re
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://ifi.u-tokyo.ac.jp"
LIST_URL = f"{BASE_URL}/event/"
SOURCE_NAME = "ifi"

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]
_PAGE_DELAY = 1.0

JST = timezone(timedelta(hours=9))


def _is_taiwan_related(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _parse_date(date_str: str, time_str: str = "") -> Optional[datetime]:
    """
    Parse IFI detail-page date/time into a JST-aware datetime.

    date_str examples:
      "2024年04月25日（木）"
      "2024年4月25日"
    time_str examples:
      "10:00-13:00"  → use start time
      "14:00-16:00"
      ""             → no time, use 00:00
    """
    if not date_str:
        return None
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))

    hour, minute = 0, 0
    if time_str:
        tm = re.match(r'(\d{1,2}):(\d{2})', time_str.strip())
        if tm:
            hour, minute = int(tm.group(1)), int(tm.group(2))

    try:
        return datetime(y, mo, d, hour, minute, tzinfo=JST)
    except ValueError:
        logger.warning("IFI: invalid date %s %s", date_str, time_str)
        return None


def _extract_info(body_text: str) -> dict[str, str]:
    """
    Extract structured info from the detail page inner_text.

    Labels appear on one line, values on the following non-empty line.
    Handles multi-line values for 会場 (venue can span two lines for hybrid events).
    """
    result: dict[str, str] = {}
    lines = [ln.strip() for ln in body_text.splitlines() if ln.strip()]
    # Remove trailing ： for matching
    known_keys = {"日程", "時間", "会場", "主催", "言語"}
    label_pattern = re.compile(r'^(日程|時間|会場|主催|言語)[：:]?$')

    i = 0
    while i < len(lines):
        lm = label_pattern.match(lines[i])
        if lm:
            key = lm.group(1)
            # Collect value: one or more non-label lines follow
            vals = []
            j = i + 1
            while j < len(lines) and not label_pattern.match(lines[j]):
                vals.append(lines[j])
                j += 1
                # Stop after 3 lines to avoid capturing unrelated content
                if len(vals) >= 3:
                    break
            if vals:
                result[key] = "\n".join(vals)
            i = j
        else:
            i += 1
    return result


class IfiScraper(BaseScraper):
    """Scrapes Taiwan-related events from 東京大学未来ビジョン研究センター (IFI)."""

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/124.0.0 Safari/537.36"
                )
            )

            # Collect upcoming event cards from the list page
            cards = self._collect_cards(page)
            logger.info("IFI: found %d upcoming events", len(cards))

            for url, card_title in cards:
                if not _is_taiwan_related(card_title):
                    continue
                time.sleep(_PAGE_DELAY)
                event = self._scrape_detail(page, url)
                if event:
                    events.append(event)

            browser.close()

        logger.info("IFI: %d Taiwan-related events", len(events))
        return events

    def _collect_cards(self, page) -> list[tuple[str, str]]:
        """Return list of (url, title) from the upcoming events list page."""
        results: list[tuple[str, str]] = []
        try:
            page.goto(LIST_URL, wait_until="domcontentloaded", timeout=30000)
        except PWTimeout:
            logger.warning("IFI: timeout loading list page")
            return results

        for card in page.query_selector_all("ul.module_card-04 li"):
            link = card.query_selector("a")
            if not link:
                continue
            href = link.get_attribute("href") or ""
            if not re.search(r'/event/\d+/', href):
                continue
            title_el = card.query_selector("p.title")
            title = title_el.inner_text().strip() if title_el else link.inner_text().strip()
            if href and title:
                results.append((href, title))

        return results

    def _scrape_detail(self, page, url: str) -> Optional[Event]:
        """Load an event detail page and return an Event."""
        id_m = re.search(r'/event/(\d+)/', url)
        if not id_m:
            logger.warning("IFI: cannot extract ID from %s", url)
            return None
        post_id = id_m.group(1)
        source_id = f"ifi_{post_id}"

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except PWTimeout:
            logger.warning("IFI: timeout on detail page %s", url)
            return None

        # Title: first h1 or h2 that is not a section header
        h_el = page.query_selector("h1.module_title-01") or page.query_selector("h2.module_title-01")
        if not h_el:
            # Fallback: breadcrumb last item
            bc = page.query_selector("ul.module_breadCrumb-01 li:last-child span")
            h_el = bc
        title = h_el.inner_text().strip() if h_el else ""

        if not title:
            logger.warning("IFI: no title found for %s", url)
            return None

        article = page.query_selector("article")
        body_text = article.inner_text() if article else page.inner_text("body")

        # Taiwan check on full body (title keyword check already done on card title,
        # but re-verify on detail to handle edge cases)
        if not _is_taiwan_related(title + " " + body_text):
            return None

        # Extract structured info
        info = _extract_info(body_text)

        start_date = _parse_date(info.get("日程", ""), info.get("時間", ""))
        if start_date is None:
            logger.warning("IFI: no start_date for %s (日程=%r)", source_id, info.get("日程"))
            return None
        end_date = start_date  # IFI events are single-day

        # Venue — may be multi-line for hybrid events (online + in-person)
        # Filter out lines that are URLs (map links etc.)
        venue_raw = info.get("会場", "")
        if venue_raw:
            venue_lines = [
                ln for ln in venue_raw.splitlines()
                if ln.strip() and not ln.strip().startswith("http")
            ]
            location_name = venue_lines[0].strip() if venue_lines else None
            location_address = "\n".join(venue_lines).strip() if venue_lines else None
        else:
            location_name = None
            location_address = None

        # Raw description
        date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n\n"
        raw_description = date_prefix + body_text.strip()

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            name_ja=title,
            raw_title=title,
            raw_description=raw_description,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=location_address,
            is_paid=False,  # IFI seminars are free / registration-required but free
        )
