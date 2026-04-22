"""
Scraper for Taiwan-related events on Peatix (peatix.com).

Peatix is Japan's largest event ticketing platform. This scraper searches
for Taiwan-related keywords and collects structured event data.
"""

import hashlib
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

SEARCH_URL = "https://peatix.com/search"

# Keywords that suggest a Taiwan-related event in Tokyo
TAIWAN_KEYWORDS = [
    "台湾",
    "Taiwan",
    "臺灣",
    "台灣",
    "台北",
    "高雄",
    "台中",
    "台南",
    "花蓮",
    "宜蘭",
    "台東",
    "金門",
    "澎湖",
    "蘭嶼",
    "綠島",
    "新竹",
    "苗栗",
    "彰化",
    "南投",
    "嘉義",
    "屏東",
    "宜蘭",
    "桃園",
    "台北市"
    "高雄市",
    "台中市",
    "台南市",
    "台湾映画",
    "台湾料理",
    "台湾文化",
    "台湾音楽",
    "台湾フェス",
    "台湾祭",
    "台湾展",
    "台日",
    "日台",
    "台湾語",
    "台湾夜市",
]

# Location filter — Tokyo metropolitan area
LOCATION_FILTER = "JP-13"  # Tokyo prefecture code in Peatix

# Only keep events whose start_date is within this window from today
DATE_LOOKBACK_DAYS = 90

# Events whose titles match any of these patterns are excluded — they contain
# 台北 only in a speaker bio / book title, not in the actual event content.
BLOCKED_TITLE_PATTERNS: frozenset[str] = frozenset([
    "Q-B-CONTINUED",
    "Soul Food Assassins",
    "人氣主題！🇹🇼台日交流",
])

# Events whose Peatix group/organizer name matches any of these patterns are excluded.
# Used for organizers who run social mixer events (聯誼/交流会) not suited for this radar.
BLOCKED_ORGANIZER_PATTERNS: frozenset[str] = frozenset([
    "台日交流会",
    "台日交流會",
    "日台交流会",
    "日台交流會",
    "アンダーバー東京国際交流",
    "UnderBar TOKYO",
])


def _safe_text(page: Page, selector: str) -> Optional[str]:
    try:
        el = page.query_selector(selector)
        return el.inner_text().strip() if el else None
    except Exception:
        return None


def _parse_peatix_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in (
        "%Y/%m/%d %H:%M",
        "%Y年%m月%d日 %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y/%m/%d",
        "%Y年%m月%d日",
        # English formats used by Peatix (e.g. "Mon, May 12, 2025")
        "%a, %b %d, %Y",
        "%b %d, %Y",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _extract_peatix_dates(page_text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Extract start and end dates from Peatix page text.

    Peatix renders date/time like:
        DATE AND TIME
        Mon, May 12, 2025
        1:00 PM - 2:00 PM GMT+09:00

    Or for archive/replay events with a long sale window:
        DATE AND TIME
        Fri, Apr 24, 2026 - Wed, Mar 31, 2027
    """
    _WEEKDAY = r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)'
    _DATE = r'(?:' + _WEEKDAY + r'),\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}'

    # First: try to match a date RANGE on one line: "Day, Mon DD, YYYY - Day, Mon DD, YYYY"
    range_match = re.search(
        r'(' + _DATE + r')\s*[-–]\s*(' + _DATE + r')',
        page_text
    )
    if range_match:
        start = _parse_peatix_date(range_match.group(1))
        end = _parse_peatix_date(range_match.group(2))
        if start and end:
            return start, end

    # Second: single date line, e.g. "Mon, May 12, 2025"
    date_match = re.search(
        r'(' + _DATE + r')',
        page_text
    )
    if not date_match:
        # Fallback: try Japanese date pattern
        jp_match = re.search(r'(\d{4}[年/]\d{1,2}[月/]\d{1,2}日?)', page_text)
        if jp_match:
            start = _parse_peatix_date(jp_match.group(1))
            return start, start
        return None, None

    date_str = date_match.group(1)  # e.g. "Mon, May 12, 2025"
    start = _parse_peatix_date(date_str)
    if not start:
        return None, None

    # Look for time range on the following lines: "1:00 PM - 2:00 PM"
    time_match = re.search(
        r'(\d{1,2}:\d{2}\s*[AP]M)\s*[-–]\s*(\d{1,2}:\d{2}\s*[AP]M)',
        page_text[date_match.start():date_match.start() + 200]
    )
    if time_match:
        try:
            start_time = datetime.strptime(
                f"{date_str} {time_match.group(1).replace(' ', '')}", "%a, %b %d, %Y %I:%M%p"
            )
            end_time = datetime.strptime(
                f"{date_str} {time_match.group(2).replace(' ', '')}", "%a, %b %d, %Y %I:%M%p"
            )
            return start_time, end_time
        except ValueError:
            pass

    # No time range found — same-day event, start = end
        # (Caller enforces end_date = start_date when end is still None)


class PeatixScraper(BaseScraper):
    """Scrapes Taiwan-related events from Peatix in Tokyo."""

    SOURCE_NAME = "peatix"

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        seen_urls: set[str] = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            cutoff = datetime.now() - timedelta(days=DATE_LOOKBACK_DAYS)

            for keyword in TAIWAN_KEYWORDS:
                links = self._search_events(page, keyword)
                for url in links:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    try:
                        event = self._scrape_detail(page, url)
                        if event:
                            if event.start_date and event.start_date < cutoff:
                                logger.debug(
                                    "Peatix: skipping old event %s (%s)",
                                    event.name_ja,
                                    event.start_date.date(),
                                )
                            else:
                                events.append(event)
                        time.sleep(1.5)
                    except Exception as exc:
                        logger.error("Peatix: failed to scrape %s: %s", url, exc)

            browser.close()

        logger.info("Peatix: collected %d events", len(events))
        return events

    def _search_events(self, page: Page, keyword: str) -> list[str]:
        """Search Peatix for keyword and return event detail URLs."""
        links: list[str] = []
        search_page = 1

        while search_page <= 20:  # Limit to 20 search result pages per keyword
            url = f"{SEARCH_URL}?q={keyword}&l={LOCATION_FILTER}&page={search_page}"
            logger.info("Peatix search: %s (page %d)", keyword, search_page)
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
            except PWTimeout:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # Peatix event cards typically have URLs like /event/XXXXXXX
            anchors = page.query_selector_all("a[href*='/event/']")
            page_links = []
            for a in anchors:
                href = a.get_attribute("href") or ""
                if not href or "peatix.com/event/" not in href and not href.startswith("/event/"):
                    continue
                full = href if href.startswith("http") else f"https://peatix.com{href}"
                # Strip query params for dedup
                full = full.split("?")[0]
                if full not in links:
                    page_links.append(full)

            if not page_links:
                break

            links.extend(page_links)
            search_page += 1
            time.sleep(1.0)

        return links

    def _scrape_detail(self, page: Page, url: str) -> Optional[Event]:
        """Extract structured data from a Peatix event detail page."""
        try:
            page.goto(url, wait_until="networkidle", timeout=30_000)
        except PWTimeout:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        # --- Check if this is actually Taiwan-related ---
        page_text = page.inner_text("body") or ""
        if not any(kw in page_text for kw in TAIWAN_KEYWORDS):
            logger.debug("Peatix: skipping non-Taiwan event %s", url)
            return None

        # False-positive guard: 台東区 is a Tokyo ward, not Taiwan.
        # Skip if the only Taiwan keyword hit is 台東 and the page also contains 台東区,
        # meaning 台東 appears solely as part of 台東区 with no other Taiwan signals.
        _TAIWAN_KW_NO_TAITO = [kw for kw in TAIWAN_KEYWORDS if kw != "台東"]
        if (
            "台東区" in page_text
            and not any(kw in page_text for kw in _TAIWAN_KW_NO_TAITO)
        ):
            logger.info("Peatix: only '\u53f0東区' (Tokyo ward) found, skipping: %s", url)
            return None

        # --- Title ---
        name_ja = (
            _safe_text(page, "h1.event-title")
            or _safe_text(page, "h1#title")
            or _safe_text(page, "h1")
        )
        if not name_ja:
            return None

        # Blocklist: skip events whose titles match known false-positive patterns.
        # We check name_ja (scraped title) so this fires before any translation.
        if any(pat in name_ja for pat in BLOCKED_TITLE_PATTERNS):
            logger.info("Peatix: blocked title pattern matched, skipping: %s", name_ja[:60])
            return None

        # Blocklist: skip events from organizers known to run social-mixer events.
        # Peatix shows the group name in a link to /group/; fall back to text selectors.
        organizer_name = (
            _safe_text(page, "a[href*='/group/']")
            or _safe_text(page, ".group-name")
            or _safe_text(page, "[class*='organizer']")
            or ""
        )
        if organizer_name and any(pat in organizer_name for pat in BLOCKED_ORGANIZER_PATTERNS):
            logger.info("Peatix: blocked organizer '%s', skipping: %s", organizer_name[:40], name_ja[:60])
            return None

        # --- Description ---
        description_ja = (
            _safe_text(page, ".event-description")
            or _safe_text(page, "#description")
            or _safe_text(page, ".description")
        )

        # --- Date ---
        # Extract dates from full page text using regex (more reliable than CSS selectors
        # since Peatix uses English-format dates in a structured section, not a stable class)
        start_date, end_date = _extract_peatix_dates(page_text)
        # Also try CSS selectors as a fallback for the raw text snippet
        date_text = (
            _safe_text(page, ".event-date-time")
            or _safe_text(page, ".date-time")
            or _safe_text(page, "[class*='date-time']")
        )
        if not start_date and date_text:
            start_date = _parse_peatix_date(date_text)
            end_date = start_date

        # Extract the DATE AND TIME block from page_text so the annotator sees it
        # even if the event description body does not contain the date.
        date_block = ""
        dt_match = re.search(
            r'DATE AND TIME\s*\n(.{5,120})',
            page_text
        )
        if dt_match:
            date_block = f"DATE AND TIME: {dt_match.group(1).strip()}\n\n"

        # --- Location ---
        location_name = (
            _safe_text(page, ".venue-name")
            or _safe_text(page, ".location")
            or _safe_text(page, "[class*='venue']")
        )
        location_address = (
            _safe_text(page, ".venue-address")
            or _safe_text(page, "[class*='address']")
        )

        # --- Price ---
        # Peatix shows "無料" or ticket prices
        price_text = _safe_text(page, ".ticket-price") or _safe_text(page, "[class*='price']")
        is_paid = False if "無料" in (price_text or "") else (True if price_text else None)

        source_id = hashlib.md5(url.encode()).hexdigest()[:16]

        # Detect language from title (Peatix events are mostly Japanese)
        original_language = "ja"

        # Prepend date text to raw_description so the AI annotator always sees the date
        # even when the description body doesn't contain it
        date_prefix = ""
        if start_date:
            date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
            if end_date and end_date != start_date:
                date_prefix += f"〜{end_date.strftime('%Y年%m月%d日')}"
            date_prefix += "\n\n"
        raw_desc_with_date = date_block + date_prefix + (description_ja or "")

        # Rule: single-day events must have end_date = start_date (never null)
        if start_date and end_date is None:
            end_date = start_date

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language=original_language,
            name_ja=name_ja,
            description_ja=description_ja,
            raw_title=name_ja,
            raw_description=raw_desc_with_date,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=location_address,
            is_paid=is_paid,
            price_info=price_text,
            category=["culture"],
        )
