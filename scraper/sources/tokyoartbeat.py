"""
Scraper for Tokyo Art Beat — events/exhibitions with Taiwan relevance.

Tokyo Art Beat (tokyoartbeat.com) is Tokyo's largest art event aggregator.
This scraper searches for "台湾" (Taiwan) and collects exhibitions and events
featuring Taiwanese artists or Taiwan-themed content.

Strategy:
  1. Load search results page: /events/search?query=台湾
  2. Collect all event detail URLs from the paginated results (up to MAX_PAGES)
  3. For each event page, extract structured data (title, dates, venue)
  4. Date extraction: the event URL itself contains the start date (YYYY-MM-DD)

Dedup key: tokyoartbeat_{url_slug}
  e.g. /events/-/Chen-Wei-Exhibition/ota-fine-arts-7chome/2026-04-21
  → tokyoartbeat_Chen-Wei-Exhibition_ota-fine-arts-7chome_2026-04-21

NOTE: tokyoartbeat.com requires JS (React rendering). Playwright is required.
The search results do NOT filter by Taiwan keyword on the server side —
all results are popular/recent events. We filter client-side by checking
that "台湾" appears on the event detail page.
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.tokyoartbeat.com"
SEARCH_URL = f"{BASE_URL}/events/search?query=%E5%8F%B0%E6%B9%BE"  # 台湾

MAX_PAGES = 5   # Each page shows ~30 events; 5 pages ≈ 150 events

TAIWAN_KEYWORDS = [
    "台湾", "Taiwan", "臺灣", "台灣",
    "台北", "台中", "台南", "高雄",
    "台日", "日台",
]

# Event URL pattern: /events/-/{slug}/{venue-slug}/{date}
_EVENT_URL_RE = re.compile(r"/events/-/[^/?#\s]+/[^/?#\s]+/(\d{4}-\d{2}-\d{2})")


def _parse_date_from_url(url: str) -> Optional[datetime]:
    """Extract YYYY-MM-DD from a Tokyo Art Beat event URL."""
    m = _EVENT_URL_RE.search(url)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            pass
    return None


def _safe_text(page: Page, selector: str, default: str = "") -> str:
    try:
        el = page.query_selector(selector)
        return el.inner_text().strip() if el else default
    except Exception:
        return default


class TokyoArtBeatScraper(BaseScraper):
    """Scrapes Taiwan-related art/exhibition events from Tokyo Art Beat."""

    SOURCE_NAME = "tokyoartbeat"

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

            event_urls = self._collect_event_urls(page)
            logger.info("tokyoartbeat: found %d candidate event URLs", len(event_urls))

            for url in event_urls:
                try:
                    event = self._scrape_event(page, url)
                    if event:
                        events.append(event)
                    time.sleep(1.2)
                except Exception as exc:
                    logger.error("tokyoartbeat: failed to scrape %s: %s", url, exc)

            browser.close()

        logger.info("tokyoartbeat: collected %d Taiwan-related events", len(events))
        return events

    def _collect_event_urls(self, page: Page) -> list[str]:
        """Load search result pages and collect event detail URLs."""
        seen: set[str] = set()
        urls: list[str] = []

        for pg in range(1, MAX_PAGES + 1):
            # Tokyo Art Beat paginates via ?page= or by clicking "next"
            # The search URL itself returns page 1; subsequent pages use &page=N
            if pg == 1:
                url = SEARCH_URL
            else:
                url = f"{SEARCH_URL}&page={pg}"

            logger.info("tokyoartbeat: loading search results page %d", pg)
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
            except PWTimeout:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                except Exception:
                    break

            time.sleep(1.5)

            # Collect all event anchors: href matches /events/-/.../.../YYYY-MM-DD
            anchors = page.query_selector_all("a[href*='/events/-/']")
            page_count = 0
            for a in anchors:
                href = a.get_attribute("href") or ""
                if not _EVENT_URL_RE.search(href):
                    continue
                full = href if href.startswith("http") else f"{BASE_URL}{href}"
                full = full.split("?")[0]
                if full not in seen:
                    seen.add(full)
                    urls.append(full)
                    page_count += 1

            if page_count == 0:
                logger.info("tokyoartbeat: no new events on page %d — stopping", pg)
                break

            time.sleep(1.0)

        return urls

    def _scrape_event(self, page: Page, url: str) -> Optional[Event]:
        """Fetch a Tokyo Art Beat event page and return an Event if Taiwan-related."""
        try:
            page.goto(url, wait_until="networkidle", timeout=30_000)
        except PWTimeout:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            except Exception:
                return None

        time.sleep(0.5)

        try:
            page_text = page.inner_text("body") or ""
        except Exception:
            page_text = ""

        # Taiwan relevance check: the search for 台湾 should return relevant results,
        # but the search API can return unrelated popular events. Validate here.
        if not any(kw in page_text for kw in TAIWAN_KEYWORDS):
            logger.debug("tokyoartbeat: skipping non-Taiwan event %s", url)
            return None

        # --- Extract title ---
        title = _safe_text(page, "h1")
        if not title:
            title = _safe_text(page, "h2")
        if not title:
            # Derive from URL slug
            slug_part = url.rstrip("/").split("/events/-/")[-1]
            title = slug_part.split("/")[0].replace("-", " ").title()

        # --- Extract dates ---
        # Primary: parse from URL (most reliable)
        start_date = _parse_date_from_url(url)

        # Try to find end date from page text patterns like "YYYY/MM/DD-YYYY/MM/DD"
        end_date = start_date
        range_m = re.search(
            r"(\d{4}[/．]\d{1,2}[/．]\d{1,2})\s*[–—〜～]\s*(\d{4}[/．]\d{1,2}[/．]\d{1,2})",
            page_text,
        )
        if range_m and start_date:
            for fmt in ("%Y/%m/%d", "%Y．%m．%d", "%Y/%m/%d", "%Y.%m.%d"):
                try:
                    end_date = datetime.strptime(
                        range_m.group(2).replace("．", "/"), fmt
                    )
                    break
                except ValueError:
                    pass

        # --- Extract venue / location ---
        # TAB detail pages typically have venue info in structured elements
        location_name = None
        location_address = None
        venue_el = page.query_selector("[class*='venue'], [class*='Venue'], [class*='place']")
        if venue_el:
            location_name = venue_el.inner_text().strip()

        # --- Build description ---
        description = page_text.strip()
        if start_date:
            date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
            if end_date and end_date != start_date:
                date_prefix += f"〜{end_date.strftime('%Y年%m月%d日')}"
            description = f"{date_prefix}\n\n{description}"

        # --- Build source_id from URL segments ---
        # e.g. /events/-/Chen-Wei-Exhibition/ota-fine-arts-7chome/2026-04-21
        # → tokyoartbeat_Chen-Wei-Exhibition_ota-fine-arts-7chome_2026-04-21
        slug_part = url.rstrip("/").split("/events/-/")[-1].replace("/", "_")
        source_id = f"tokyoartbeat_{slug_part}"[:120]

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            name_ja=title,
            raw_title=title,
            raw_description=description,
            start_date=start_date,
            end_date=end_date,
            category=["art"],
            location_name=location_name,
            location_address=location_address,
        )
