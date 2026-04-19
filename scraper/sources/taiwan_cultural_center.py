"""
Scraper for the Taiwan Cultural Center in Japan (jp.taiwan.culture.tw).

The site is a JavaScript-rendered dynamic page, so we use Playwright.
This scraper:
  1. Navigates to the activities list page
  2. Collects event links across multiple pages
  3. Visits each event detail page to extract structured data
"""

import re
import time
import hashlib
import logging
from datetime import datetime
from typing import Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://jp.taiwan.culture.tw"
# The activity list URL — if the page structure changes, update this path.
ACTIVITY_LIST_URL = f"{BASE_URL}/activi/type_list"


def _safe_text(page: Page, selector: str) -> Optional[str]:
    """Return inner text of the first matching element, or None."""
    try:
        el = page.query_selector(selector)
        return el.inner_text().strip() if el else None
    except Exception:
        return None


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    """Try several common date formats used on the site."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    logger.warning("Could not parse date: %s", raw)
    return None


def _extract_dates(text: Optional[str]) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse a date-range string like "2026/01/10 ～ 2026/03/20"
    into (start_date, end_date).
    """
    if not text:
        return None, None
    # Match two date-like tokens separated by common range indicators
    parts = re.split(r"[～~〜\-–—]", text)
    start = _parse_date(parts[0]) if len(parts) >= 1 else None
    end = _parse_date(parts[1]) if len(parts) >= 2 else None
    return start, end


def _is_paid(text: Optional[str]) -> Optional[bool]:
    if not text:
        return None
    lower = text.lower()
    if any(w in lower for w in ["無料", "free", "免費", "免费"]):
        return False
    if any(w in lower for w in ["有料", "入場料", "料金", "円", "¥", "yen", "paid", "費用"]):
        return True
    return None


class TaiwanCulturalCenterScraper(BaseScraper):
    """Scrapes events from the Taiwan Cultural Center Japan website."""

    SOURCE_NAME = "taiwan_cultural_center"

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

            event_links = self._collect_event_links(page)
            logger.info("Found %d event links", len(event_links))

            for url in event_links:
                try:
                    event = self._scrape_detail(page, url)
                    if event:
                        events.append(event)
                    time.sleep(1.5)  # Be polite to the server
                except Exception as exc:
                    logger.error("Failed to scrape %s: %s", url, exc)

            browser.close()
        return events

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_event_links(self, page: Page) -> list[str]:
        """Walk through paginated activity list and collect all detail URLs."""
        links: list[str] = []
        current_page = 1

        while True:
            url = f"{ACTIVITY_LIST_URL}?page={current_page}"
            logger.info("Fetching list page %d: %s", current_page, url)
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
            except PWTimeout:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # Collect all <a> tags that point to activity detail pages
            anchors = page.query_selector_all("a[href*='/activi/']")
            page_links = []
            for a in anchors:
                href = a.get_attribute("href") or ""
                # Skip the list page itself and pagination links
                if "/activi/type_list" in href or not href:
                    continue
                full = href if href.startswith("http") else f"{BASE_URL}{href}"
                if full not in links:
                    page_links.append(full)

            if not page_links:
                break  # No more events on this page

            links.extend(page_links)
            current_page += 1

            # Safety limit to avoid infinite loops
            if current_page > 20:
                logger.warning("Reached page limit (20), stopping pagination.")
                break

        return links

    def _scrape_detail(self, page: Page, url: str) -> Optional[Event]:
        """Visit a single event detail page and extract all fields."""
        try:
            page.goto(url, wait_until="networkidle", timeout=30_000)
        except PWTimeout:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        # --- Title ---
        # Try common heading selectors; adjust if the site structure changes
        name_ja = (
            _safe_text(page, "h1.title")
            or _safe_text(page, "h1")
            or _safe_text(page, ".event-title")
            or _safe_text(page, "h2.title")
        )
        if not name_ja:
            logger.warning("Could not find title at %s, skipping.", url)
            return None

        # --- Description ---
        description_ja = (
            _safe_text(page, ".content-body")
            or _safe_text(page, ".event-detail")
            or _safe_text(page, ".description")
            or _safe_text(page, "article")
        )

        # --- Date ---
        date_text = (
            _safe_text(page, ".date")
            or _safe_text(page, ".event-date")
            or _safe_text(page, "[class*='date']")
        )
        start_date, end_date = _extract_dates(date_text)

        # --- Location ---
        location_name = (
            _safe_text(page, ".venue")
            or _safe_text(page, ".location")
            or _safe_text(page, "[class*='venue']")
            or _safe_text(page, "[class*='place']")
        )

        # --- Price ---
        price_text = (
            _safe_text(page, ".fee")
            or _safe_text(page, ".price")
            or _safe_text(page, "[class*='fee']")
            or _safe_text(page, "[class*='price']")
        )
        is_paid = _is_paid(price_text)

        # --- Source ID: use URL path as stable identifier ---
        source_id = hashlib.md5(url.encode()).hexdigest()[:16]

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            name_ja=name_ja,
            description_ja=description_ja,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            is_paid=is_paid,
            price_info=price_text,
            category=["culture"],  # Default; can be refined with ML/keyword matching later
        )
