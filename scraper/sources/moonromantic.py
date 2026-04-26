"""
Scraper for 月見ル君想フ (MoonRomantic) — South Aoyama live music venue.

月見ル君想フ is a live house in Minami-Aoyama, Tokyo, known for regularly hosting
Taiwan indie music artists (often organized by BIG ROMANTIC ENTERTAINMENT).

Strategy:
  1. Scrape monthly schedule pages for current month + MONTHS_AHEAD future months
     URL: https://www.moonromantic.com/allevents/categories/YYYY-MM
  2. Collect event post links from each month's schedule page
  3. For each event, fetch the detail page (Playwright required — Wix JS rendering)
  4. Filter: keep only events whose title or body contains Taiwan keywords
  5. Extract: date from title prefix "YYYY.MM.DD |", description from body

Dedup key: moonromantic_{post_slug}
  e.g. /post/260510 → moonromantic_260510

NOTE: Most events at this venue are NOT Taiwan-related. The Taiwan keyword
filter is essential to avoid flooding the DB with unrelated JP indie events.
"""

import logging
import re
import time
from datetime import datetime, date
from typing import Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.moonromantic.com"
SCHEDULE_BASE = f"{BASE_URL}/allevents/categories"

LOCATION_NAME = "月見ル君想フ"
LOCATION_ADDRESS = "東京都港区南青山4-9-1 B1F"

# Scrape current month + this many future months
MONTHS_AHEAD = 3

TAIWAN_KEYWORDS = [
    "台湾", "Taiwan", "臺灣", "台灣",
    "台北", "高雄", "台中", "台南",
    "台日", "日台",
    # Known Taiwan music labels / promoters
    "BIG ROMANTIC",
    "大浪漫",
    # Frequently touring Taiwan artists
    "DSPS", "VOOID", "Andr", "Sunset Rollercoaster",
    "日落飛車", "告五人", "魚丁糸", "ØZI", "Elephant Gym",
    "大象體操",
]

_TITLE_DATE_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})")
_DOW_RE = re.compile(r"\((?:月|火|水|木|金|土|日)[・祝]?\)")

_POST_LINK_RE = re.compile(r"/post/[^/?#\s]+")


def _parse_title_date(title: str) -> Optional[datetime]:
    """Parse 'YYYY.MM.DD | Event Title' → datetime."""
    m = _TITLE_DATE_RE.match(title.strip())
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _month_url(year: int, month: int) -> str:
    """Return the schedule page URL for the given year/month."""
    return f"{SCHEDULE_BASE}/{year}-{month:02d}"


def _months_to_scrape() -> list[tuple[int, int]]:
    """Return list of (year, month) tuples: current month + MONTHS_AHEAD."""
    today = date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(MONTHS_AHEAD + 1):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _safe_text(page: Page, selector: str, default: str = "") -> str:
    try:
        el = page.query_selector(selector)
        return el.inner_text().strip() if el else default
    except Exception:
        return default


class MoonRomanticScraper(BaseScraper):
    """Scrapes Taiwan-related live music events from 月見ル君想フ."""

    SOURCE_NAME = "moonromantic"

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

            seen_urls: set[str] = set()

            for year, month in _months_to_scrape():
                url = _month_url(year, month)
                logger.info("moonromantic: scraping schedule page %s", url)
                post_links = self._collect_post_links(page, url)
                logger.info("moonromantic: found %d posts for %d-%02d", len(post_links), year, month)

                for post_url in post_links:
                    if post_url in seen_urls:
                        continue
                    seen_urls.add(post_url)
                    try:
                        event = self._scrape_post(page, post_url)
                        if event:
                            events.append(event)
                        time.sleep(1.0)
                    except Exception as exc:
                        logger.error("moonromantic: failed to scrape %s: %s", post_url, exc)

            browser.close()

        logger.info("moonromantic: collected %d Taiwan-related events", len(events))
        return events

    def _collect_post_links(self, page: Page, url: str) -> list[str]:
        """Load a monthly schedule page and collect all /post/ event URLs."""
        try:
            page.goto(url, wait_until="load", timeout=30_000)
        except PWTimeout:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            except Exception:
                return []

        # Let Wix JS render content
        try:
            page.wait_for_selector("a[href*='/post/']", timeout=8_000)
        except PWTimeout:
            pass  # page may have no posts — that's fine

        anchors = page.query_selector_all("a[href*='/post/']")
        links: list[str] = []
        seen: set[str] = set()
        for a in anchors:
            href = a.get_attribute("href") or ""
            if not href or "/post/" not in href:
                continue
            # Skip announcement/system posts
            if any(skip in href for skip in ["/post/announcement", "/post/_system"]):
                continue
            full = href if href.startswith("http") else f"{BASE_URL}{href}"
            # Normalize: strip query params
            full = full.split("?")[0]
            if full not in seen:
                seen.add(full)
                links.append(full)
        return links

    def _scrape_post(self, page: Page, url: str) -> Optional[Event]:
        """Scrape a single event post page and return an Event if Taiwan-related."""
        try:
            page.goto(url, wait_until="load", timeout=30_000)
        except PWTimeout:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            except Exception:
                return None

        # Let Wix JS render post body
        try:
            page.wait_for_selector("h1, [data-testid='richTextElement']", timeout=8_000)
        except PWTimeout:
            pass  # proceed with whatever rendered

        # --- Extract full page text for Taiwan keyword check ---
        try:
            page_text = page.inner_text("body") or ""
        except Exception:
            page_text = ""

        if not any(kw in page_text for kw in TAIWAN_KEYWORDS):
            logger.debug("moonromantic: skipping non-Taiwan post %s", url)
            return None

        # --- Extract title ---
        # Wix renders the post title in an <h1> or data-testid="richTextElement"
        title = _safe_text(page, "h1")
        if not title:
            title = _safe_text(page, "[data-testid='richTextElement'] h1")
        if not title:
            # Fall back: try to extract from page h2 or heading-like element
            for sel in ("h2", ".post-title", ".blog-post-title"):
                title = _safe_text(page, sel)
                if title:
                    break

        if not title:
            # Last resort: derive from URL slug
            slug = url.rstrip("/").split("/post/")[-1]
            title = slug

        # --- Extract date from title "YYYY.MM.DD | ..." ---
        start_date = _parse_title_date(title)

        # Fallback: search body text for date pattern
        if not start_date:
            body_date_m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", page_text)
            if body_date_m:
                try:
                    start_date = datetime(
                        int(body_date_m.group(1)),
                        int(body_date_m.group(2)),
                        int(body_date_m.group(3)),
                    )
                except ValueError:
                    pass

        # --- Extract description from body ---
        description = page_text.strip()
        if start_date:
            description = f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n\n{description}"

        # --- Build source_id from URL slug ---
        slug = url.rstrip("/").split("/post/")[-1]
        # URL-decode for slug (slugs can be URL-encoded Japanese)
        try:
            from urllib.parse import unquote
            slug = unquote(slug)
        except Exception:
            pass
        # Sanitize: keep only alphanumeric, hyphens, underscores; limit length
        slug_clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", slug)[:80]
        source_id = f"moonromantic_{slug_clean}"

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            name_ja=title,
            raw_title=title,
            raw_description=description,
            start_date=start_date,
            end_date=start_date,
            category=["performing_arts"],
            location_name=LOCATION_NAME,
            location_address=LOCATION_ADDRESS,
        )
