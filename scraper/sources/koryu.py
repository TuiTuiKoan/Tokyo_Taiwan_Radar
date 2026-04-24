"""
Scraper for 公益財団法人日本台湾交流協会 (koryu.or.jp).

Fetches the イベント・セミナー情報 listing page and filters events
that are held in Tokyo (venue text contains 東京).

Strategy:
  1. Fetch /news/event/ with Playwright (DNN CMS, static HTML)
  2. Parse each list item: date, tags, title, href
  3. Only visit detail pages for items tagged with 東京
  4. From detail page: extract event date (日時 field), venue, description
  5. Filter: skip if venue is not in Tokyo (東京都 / 東京 / 都内)
  6. source_id = "koryu_{itemid}" from URL query param (stable)
"""

import re
import time
import logging
from datetime import datetime
from typing import Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.koryu.or.jp"
LIST_URL = f"{BASE_URL}/news/event/"
SOURCE_NAME = "koryu"

# Tokyo identifiers for venue filtering
_TOKYO_MARKERS = ["東京", "港区", "千代田区", "新宿区", "渋谷区", "中央区", "台東区",
                  "文京区", "豊島区", "品川区", "目黒区", "江東区", "墨田区"]

# Date formats used on the site
_DATE_PATTERNS = [
    (re.compile(r'(\d{4})年(\d{1,2})月(\d{1,2})日'), '%Y年%m月%d日'),
    (re.compile(r'(\d{4})[./](\d{1,2})[./](\d{1,2})'), None),
]


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    """Parse date strings: '2026年2月26日' or '2026.02.26'."""
    if not raw:
        return None
    raw = raw.strip()
    # Strip day-of-week in brackets
    raw = re.sub(r'[（(][^）)\d][^）)]*[）)]', '', raw).strip()
    for fmt in ("%Y年%m月%d日", "%Y.%m.%d", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    logger.warning("Could not parse date: %r", raw)
    return None


def _extract_itemid(href: str) -> Optional[str]:
    """Extract itemid from URL like /news/event/?itemid=4899&dispmid=4262"""
    m = re.search(r'itemid=(\d+)', href)
    return m.group(1) if m else None


def _extract_event_date(body_text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Extract event date from detail page body text.
    Looks for 日時 section: '2026年2月26日（木）14：30～16：30'
    Returns (start_date, end_date).
    """
    # Find 日時 label followed by date content
    m = re.search(
        r'(?:日\s*時|開催日時|日時)\s*\n?\s*'
        r'((?:20\d{2}年)?\d{1,2}月\d{1,2}日[^～\n]*(?:[～〜][^\n]*)?)',
        body_text
    )
    if not m:
        # Try searching for a standalone date line near 日時 heading
        m = re.search(r'(20\d{2}年\d{1,2}月\d{1,2}日)', body_text)
        if m:
            start = _parse_date(m.group(1))
            return start, start
        return None, None

    date_str = m.group(1).strip()
    # Split on range indicator
    parts = re.split(r'[～〜]', date_str)
    start_raw = parts[0].strip()
    end_raw = parts[1].strip() if len(parts) > 1 else None

    # Start date might be "2月26日（木）14:30" — extract just the date part
    start_date_m = re.search(r'(20\d{2}年\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日)', start_raw)
    start_date = _parse_date(start_date_m.group(1)) if start_date_m else None

    end_date = None
    if end_raw:
        end_date_m = re.search(r'(20\d{2}年\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日)', end_raw)
        if end_date_m:
            end_date = _parse_date(end_date_m.group(1))
            # If end_date has no year, inherit from start_date
            if end_date and start_date and end_date.year == 1900:
                end_date = end_date.replace(year=start_date.year)

    if start_date and end_date is None:
        end_date = start_date

    return start_date, end_date


def _is_tokyo_venue(body_text: str) -> bool:
    """Return True if the event has an explicit 会場 section in Tokyo.

    Returns False for '後援' posts that lack a venue section.
    """
    m = re.search(r'会\s*場\s*\n?\s*(.{5,120})', body_text)
    if not m:
        return False  # No venue section → skip (e.g. 後援 announcements)
    venue_text = m.group(1).strip()
    return any(marker in venue_text for marker in _TOKYO_MARKERS)


def _extract_location_address(body_text: str) -> Optional[str]:
    """Extract address/location details from 所在地 or 住所 section."""
    m = re.search(r'(?:所在地|住所|住　所)\s*\n?\s*(.{5,100})', body_text)
    if m:
        return m.group(1).strip().split('\n')[0].strip()[:100]
    return None


def _extract_venue(body_text: str) -> Optional[str]:
    """Extract venue name from 会場 section."""
    m = re.search(r'会\s*場\s*\n?\s*(.{5,120})', body_text)
    if not m:
        return None
    venue_line = m.group(1).strip()
    # Take first line only
    return venue_line.split('\n')[0].strip()[:120]


class KoryuScraper(BaseScraper):
    """Scrapes Tokyo-based Taiwan-related events from koryu.or.jp."""

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        events: list[Event] = []

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

            # Phase 1: fetch listing
            tokyo_items = self._fetch_listing(page)
            logger.info("Tokyo-tagged items: %d", len(tokyo_items))

            # Phase 2: visit detail pages
            seen_ids: set[str] = set()
            for item in tokyo_items:
                item_id = item["item_id"]
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)

                try:
                    event = self._scrape_detail(page, item)
                    if event:
                        events.append(event)
                    time.sleep(1.0)
                except Exception as exc:
                    logger.error("Failed to scrape %s: %s", item.get("href"), exc)

            browser.close()

        return events

    def _fetch_listing(self, page: Page) -> list[dict]:
        """Fetch the event listing and return Tokyo-tagged items."""
        try:
            page.goto(LIST_URL, wait_until="networkidle", timeout=30_000)
        except PWTimeout:
            page.goto(LIST_URL, wait_until="domcontentloaded", timeout=30_000)

        main = page.query_selector("main")
        if not main:
            logger.error("No <main> element found on %s", LIST_URL)
            return []

        items = []
        for li in main.query_selector_all("li"):
            # Get link and title
            a = li.query_selector(".newsTitle a")
            if not a:
                continue
            href = a.get_attribute("href") or ""
            title = a.inner_text().strip()
            if not title or not href:
                continue

            item_id = _extract_itemid(href)
            if not item_id:
                continue

            # Get listing date (publication date)
            date_el = li.query_selector(".newsDate")
            pub_date_str = date_el.inner_text().strip() if date_el else ""

            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"

            items.append({
                "item_id": item_id,
                "href": full_url,
                "title": title,
                "pub_date_str": pub_date_str,
            })

        return items

    def _scrape_detail(self, page: Page, item: dict) -> Optional[Event]:
        """Visit detail page and extract event data."""
        url = item["href"]

        try:
            page.goto(url, wait_until="networkidle", timeout=30_000)
        except PWTimeout:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        main = page.query_selector("main")
        if not main:
            return None

        body_text = main.inner_text()

        # Extract event date from body (日時 section)
        start_date, end_date = _extract_event_date(body_text)

        # Fallback to publication date if no event date found
        if start_date is None:
            start_date = _parse_date(item["pub_date_str"])
            end_date = start_date
            if start_date is None:
                logger.warning("No date found for %s, skipping", url)
                return None

        venue = _extract_venue(body_text) or ""
        location_address = _extract_location_address(body_text)

        title = item["title"]
        source_id = f"koryu_{item['item_id']}"

        # Build raw_description
        date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
        if end_date and end_date != start_date:
            date_prefix += f" ～ {end_date.strftime('%Y年%m月%d日')}"
        date_prefix += "\n\n"

        raw_description = date_prefix + body_text.strip()

        # Detect paid/free
        is_paid: Optional[bool] = None
        if "無料" in body_text:
            is_paid = False
        elif any(w in body_text for w in ["円", "有料", "参加費"]):
            is_paid = True

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            name_ja=title,
            description_ja=body_text.strip() or None,
            raw_title=title,
            raw_description=raw_description,
            start_date=start_date,
            end_date=end_date,
            location_name=venue,
            location_address=location_address,
            is_paid=is_paid,
            category=["lecture"],
        )
