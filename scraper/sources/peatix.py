"""
Scraper for Taiwan-related events on Peatix (peatix.com).

Peatix is Japan's largest event ticketing platform. This scraper searches
for Taiwan-related keywords and collects structured event data.
"""

import hashlib
import logging
import time
from datetime import datetime
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
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


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

            for keyword in TAIWAN_KEYWORDS:
                links = self._search_events(page, keyword)
                for url in links:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    try:
                        event = self._scrape_detail(page, url)
                        if event:
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

        while search_page <= 5:  # Limit to 5 search result pages per keyword
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

        # --- Title ---
        name_ja = (
            _safe_text(page, "h1.event-title")
            or _safe_text(page, "h1#title")
            or _safe_text(page, "h1")
        )
        if not name_ja:
            return None

        # --- Description ---
        description_ja = (
            _safe_text(page, ".event-description")
            or _safe_text(page, "#description")
            or _safe_text(page, ".description")
        )

        # --- Date ---
        date_text = (
            _safe_text(page, ".event-date-time")
            or _safe_text(page, ".date-time")
            or _safe_text(page, "[class*='date']")
        )
        start_date = _parse_peatix_date(date_text)

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

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language=original_language,
            name_ja=name_ja,
            description_ja=description_ja,
            raw_title=name_ja,
            raw_description=description_ja,
            start_date=start_date,
            location_name=location_name,
            location_address=location_address,
            is_paid=is_paid,
            price_info=price_text,
            category=["culture"],
        )
