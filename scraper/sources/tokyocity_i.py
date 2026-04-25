"""
Scraper for 東京シティアイ (tokyocity-i.jp).

Tokyo City i is a tourist information center at KITTE B1F, Marunouchi, Tokyo.
It hosts a small number of regional PR events, some of which are Taiwan-themed
(台湾フェア, 台湾夜市, etc.) — typically 2–5 events per year.

Strategy:
  1. Fetch https://www.tokyocity-i.jp/event/ (paginated via /event/page/{N}/)
  2. Collect all active event links (not past events)
  3. For each card title: apply Taiwan keyword filter
  4. Load detail page → extract dates, venue, description from <table.normal-table>
  5. source_id = "tokyocity_i_{post_id}" (numeric WordPress post ID from URL)

Taiwan keyword filter:
  ["台湾", "Taiwan", "臺灣"]
  Applied to card title and detail page content.

Location: Always KITTE 地下1階 東京シティアイ — fixed venue used as fallback
when detail table has no 場所 row.
"""

import re
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.tokyocity-i.jp"
LIST_URL = f"{BASE_URL}/event/"
SOURCE_NAME = "tokyocity_i"

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]

# Fixed fallback venue (KITTE B1F is the only location Tokyo City i uses)
_DEFAULT_LOCATION_NAME = "東京シティアイ"
_DEFAULT_LOCATION_ADDRESS = "東京都千代田区丸の内2-7-2 KITTE地下1階"

JST = timezone(timedelta(hours=9))

# Page delay between detail page requests
_PAGE_DELAY = 1.0


def _is_taiwan_related(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _parse_date_cell(raw: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse 期間 cell content into (start_date, end_date).

    Formats handled:
      - "2026/4/12（日）"                     → single day
      - "2026/4/21（火）～ 5/6（水）"           → same-year range
      - "2026/4/21（火）～ 2026/5/6（水）"      → explicit-year range
      - "2026/4/21（火）～5/6（水）"            → range without spaces
    """
    raw = raw.strip()
    # Extract all date-like groups "YYYY/M/D" or "M/D" (possibly followed by （曜日）)
    date_pat = re.compile(r'(\d{4}/\d{1,2}/\d{1,2}|\d{1,2}/\d{1,2})(?:（[^）]*）)?')
    matches = date_pat.findall(raw)
    if not matches:
        return None, None

    def _to_dt(s: str, ref_year: int) -> Optional[datetime]:
        parts = s.split("/")
        if len(parts) == 3:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            y, m, d = ref_year, int(parts[0]), int(parts[1])
        else:
            return None
        try:
            return datetime(y, m, d, tzinfo=JST)
        except ValueError:
            return None

    first = _to_dt(matches[0], datetime.now(JST).year)
    ref_year = first.year if first else datetime.now(JST).year

    if len(matches) >= 2:
        end = _to_dt(matches[1], ref_year)
    else:
        end = first

    return first, end


def _extract_table(body_text: str) -> dict[str, str]:
    """
    Extract key/value rows from the normal-table in inner_text format.
    The table renders as: "期間\n2026/4/12（日）\n時間\n11:00～18:00\n..."
    We just search for known labels and capture the next non-empty line.
    """
    result: dict[str, str] = {}
    lines = [ln.strip() for ln in body_text.splitlines() if ln.strip()]
    known_keys = {"期間", "時間", "場所", "主催", "共催", "公式サイト", "お問い合わせ"}
    for i, line in enumerate(lines):
        if line in known_keys and i + 1 < len(lines):
            val = lines[i + 1]
            # Don't capture the next label as the value
            if val not in known_keys:
                result[line] = val
    return result


class TokyoCityIScraper(BaseScraper):
    """Scrapes Taiwan-related events from 東京シティアイ (tokyocity-i.jp)."""

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

            # Collect event URLs from all list pages
            event_links = self._collect_event_links(page)
            logger.info("TokyoCityI: found %d active events", len(event_links))

            for url, card_title in event_links:
                if not _is_taiwan_related(card_title):
                    continue
                time.sleep(_PAGE_DELAY)
                event = self._scrape_detail(page, url)
                if event:
                    events.append(event)

            browser.close()

        logger.info("TokyoCityI: %d Taiwan-related events", len(events))
        return events

    def _collect_event_links(self, page) -> list[tuple[str, str]]:
        """Return list of (url, card_title) for all active (non-past) events."""
        links: list[tuple[str, str]] = []
        pg = 1
        max_pages = 20  # safety limit

        while pg <= max_pages:
            url = LIST_URL if pg == 1 else f"{BASE_URL}/event/page/{pg}/"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except PWTimeout:
                logger.warning("TokyoCityI: timeout on list page %d", pg)
                break

            # Extract event links (skip past-event link and nav links)
            sections = page.query_selector_all("article section a[href*='/event/']")
            if not sections:
                break

            for a in sections:
                href = a.get_attribute("href") or ""
                # Skip ?exit=1 (past events link) and /event/ root links
                if "exit=1" in href or not re.search(r'/event/\d+/', href):
                    continue
                # Card title from <p> inside the link
                p_el = a.query_selector("p")
                title = p_el.inner_text().strip() if p_el else a.inner_text().strip()
                if href and title:
                    links.append((href, title))

            # Check if there is a next page
            next_link = page.query_selector(f"a[href*='/event/page/{pg + 1}/']")
            if not next_link:
                break
            pg += 1

        return links

    def _scrape_detail(self, page, url: str) -> Optional[Event]:
        """Load a detail page and extract the Event."""
        # Extract numeric post ID from URL: /event/10303/ → 10303
        id_m = re.search(r'/event/(\d+)/', url)
        if not id_m:
            logger.warning("TokyoCityI: cannot extract ID from %s", url)
            return None
        post_id = id_m.group(1)
        source_id = f"tokyocity_i_{post_id}"

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except PWTimeout:
            logger.warning("TokyoCityI: timeout on detail page %s", url)
            return None

        # Title: h2.cap-lv1
        h2 = page.query_selector("h2.cap-lv1")
        title = h2.inner_text().strip() if h2 else ""
        if not title:
            # fallback: last breadcrumb span
            bc_span = page.query_selector("ul.bread li:last-child span")
            title = bc_span.inner_text().strip() if bc_span else ""

        if not title:
            logger.warning("TokyoCityI: no title found for %s", url)
            return None

        # Taiwan check on full page content (catches cases where title alone doesn't match)
        article = page.query_selector("article")
        body_text = article.inner_text() if article else page.inner_text("body")

        if not _is_taiwan_related(title + " " + body_text):
            return None

        # Extract table fields
        table = _extract_table(body_text)

        # Dates
        kikan_raw = table.get("期間", "")
        jikan_raw = table.get("時間", "")
        start_date, end_date = _parse_date_cell(kikan_raw)

        if start_date is None:
            logger.warning("TokyoCityI: no start_date for %s (期間=%r)", source_id, kikan_raw)
            return None

        # Add time component if available (e.g. "11:00～18:00" → use start time)
        if jikan_raw:
            time_m = re.match(r'(\d{1,2}):(\d{2})', jikan_raw)
            if time_m:
                start_date = start_date.replace(
                    hour=int(time_m.group(1)),
                    minute=int(time_m.group(2)),
                )

        if end_date is None:
            end_date = start_date

        # Location
        basho = table.get("場所", "")
        location_name = basho or _DEFAULT_LOCATION_NAME
        location_address = _DEFAULT_LOCATION_ADDRESS

        # Raw description: date prefix + full article text
        date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
        if end_date.date() != start_date.date():
            date_prefix += f" ～ {end_date.strftime('%Y年%m月%d日')}"
        date_prefix += "\n\n"
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
            is_paid=False,  # Tokyo City i events are free admission
        )
