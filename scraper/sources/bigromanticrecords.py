"""Scraper for BIG ROMANTIC RECORDS — Japan×Taiwan indie music news & events.

BIG ROMANTIC RECORDS (bigromanticrecords.com) is a Tokyo-Taipei music label
and media site that publishes event news for touring Taiwanese indie artists
(DSPS, VOOID, Andr, MIZ, Sunset Rollercoaster, etc.) performing in Japan.

Strategy:
  1. Navigate to the event listing page with Playwright (JS rendering required)
  2. Collect all /single-post/ article links
  3. For each article: extract title, date, venue, and description
  4. Filter: keep only articles whose text contains Taiwan keywords
     (not all posts cover Taiwan — e.g. Thai artist YONLAPA is excluded)

Date format in articles:
  "Date：May 14, 2026 (Thu)"   → parsed with %B %d, %Y
  "Date: May 14, 2026 (Thu)"  → same
  Fallback: Japanese regex YYYY年MM月DD日

Dedup key: bigromanticrecords_{slug}
  e.g. /single-post/andr2026 → bigromanticrecords_andr2026
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

EVENT_LISTING_URL = "https://www.bigromanticrecords.com/event"
BASE_URL = "https://www.bigromanticrecords.com"

_TAIWAN_KEYWORDS = [
    "台湾", "Taiwan", "台灣", "臺灣",
    "台北", "高雄", "台中", "台南",
    "台日", "日台",
    # Known Taiwan artists frequently covered by this site
    "DSPS", "VOOID", "Andr", "André", "MIZ",
    "Sunset Rollercoaster", "日落飛車",
    "告五人", "魚丁糸", "大象體操", "Elephant Gym",
    "ØZI",
]

# Date separators vary: ：(full-width colon), : (regular colon), ｜(full-width bar),
# space, or newline (label and value may be on separate lines in static HTML).
# Pattern: "Date" <optional-whitespace> <optional-separator> <optional-whitespace> <value>
_DATE_EN_RE = re.compile(
    r"Date\s*[：:\uff5c]?\s*([A-Za-z]+ \d{1,2},?\s*\d{4})",
    re.DOTALL,
)
_DATE_DOT_RE = re.compile(
    r"Date\s*[：:\uff5c]?\s*(\d{4})\.(\d{1,2})\.(\d{1,2})",
    re.DOTALL,
)
_DATE_JA_RE = re.compile(r"(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})")
_VENUE_RE = re.compile(r"Venue\s*[：:\uff5c]?\s*(.+)")

# Slug clean: keep alphanumeric, hyphen, underscore
_SLUG_CLEAN_RE = re.compile(r"[^a-zA-Z0-9_\-]")


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _parse_date(text: str) -> Optional[datetime]:
    """Extract event date from article text.

    Priority order:
    1. English format:  "Date：May 14, 2026 (Thu)" or "Date May 26, 2026"
    2. ISO dot format:  "Date｜2026.05.08 (Fri)" or "Date：2026.05.08"
    3. Japanese/ISO:    「YYYY年MM月DD日」 or YYYY/MM/DD or YYYY-MM-DD
    """
    # 1. ISO dot format with explicit Date label (most reliable for this site)
    m_dot = _DATE_DOT_RE.search(text)
    if m_dot:
        try:
            return datetime(int(m_dot.group(1)), int(m_dot.group(2)), int(m_dot.group(3)))
        except ValueError:
            pass

    # 2. English format after Date label
    m_en = _DATE_EN_RE.search(text)
    if m_en:
        raw = m_en.group(1).rstrip(".,").strip()
        # Remove day-of-week suffix like " (Thu)"
        raw = re.sub(r"\s*\(.*?\)", "", raw).strip().rstrip(",").strip()
        for fmt in ("%B %d %Y", "%B %d, %Y", "%b %d %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue

    # 3. Fallback: first YYYY年MM月DD日 / YYYY/MM/DD / YYYY-MM-DD found
    m_ja = _DATE_JA_RE.search(text)
    if m_ja:
        try:
            return datetime(int(m_ja.group(1)), int(m_ja.group(2)), int(m_ja.group(3)))
        except ValueError:
            pass

    return None


def _extract_venue(text: str) -> Optional[str]:
    m = _VENUE_RE.search(text)
    if m:
        # Take first line only (stops at newline)
        venue = m.group(1).split("\n")[0].strip()
        # Some articles concatenate venue and address on one line, e.g.
        # "The Wall Live HouseAddress｜No.200, ..."
        # Split at "Address" label if present
        venue = re.split(r"Address[\s｜：:]", venue)[0].strip()
        return venue if venue else None
    return None


class BigRomanticRecordsScraper(BaseScraper):
    """Scrapes Taiwan-related live music event posts from bigromanticrecords.com."""

    SOURCE_NAME = "bigromanticrecords"

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

            article_urls = self._collect_article_urls(page)
            logger.info(
                "bigromanticrecords: found %d article(s) on listing page",
                len(article_urls),
            )

            for url in article_urls:
                try:
                    event = self._scrape_article(page, url)
                    if event:
                        events.append(event)
                    time.sleep(1.0)
                except Exception as exc:
                    logger.error(
                        "bigromanticrecords: failed to scrape %s: %s", url, exc
                    )

            browser.close()

        logger.info(
            "bigromanticrecords: collected %d Taiwan-related event(s)", len(events)
        )
        return events

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_article_urls(self, page: Page) -> list[str]:
        """Load the event listing and return all unique /single-post/ URLs."""
        try:
            page.goto(EVENT_LISTING_URL, wait_until="load", timeout=30_000)
        except PWTimeout:
            try:
                page.goto(
                    EVENT_LISTING_URL, wait_until="domcontentloaded", timeout=30_000
                )
            except Exception:
                logger.error("bigromanticrecords: failed to load listing page")
                return []

        # Wait for article links to appear (Squarespace renders them via JS)
        try:
            page.wait_for_selector("a[href*='/single-post/']", timeout=10_000)
        except PWTimeout:
            pass  # May have no posts — proceed anyway

        anchors = page.query_selector_all("a[href*='/single-post/']")
        seen: set[str] = set()
        urls: list[str] = []
        for a in anchors:
            href = a.get_attribute("href") or ""
            if "/single-post/" not in href:
                continue
            full = href if href.startswith("http") else f"{BASE_URL}{href}"
            full = full.split("?")[0].rstrip("/")  # strip query params and trailing slash
            if full not in seen:
                seen.add(full)
                urls.append(full)
        return urls

    def _scrape_article(self, page: Page, url: str) -> Optional[Event]:
        """Scrape a single event article and return an Event if Taiwan-related."""
        try:
            page.goto(url, wait_until="load", timeout=30_000)
        except PWTimeout:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            except Exception:
                return None

        # Let Squarespace JS render the article body
        try:
            page.wait_for_selector("h1", timeout=8_000)
        except PWTimeout:
            pass
        # Brief settle to avoid stale cross-page state
        page.wait_for_timeout(500)

        try:
            page_text = page.inner_text("body") or ""
        except Exception:
            page_text = ""

        # Taiwan keyword filter — skip articles with no Taiwan content
        if not _is_taiwan(page_text):
            logger.debug("bigromanticrecords: skipping non-Taiwan article %s", url)
            return None

        # --- Extract title ---
        # page.title() is most reliable on Squarespace/Wix (always reflects current page).
        # [data-hook='post-title'] / main h1 are secondary fallbacks.
        title = ""
        try:
            t = page.title().strip()
            # Reject the generic site title (site-level fallback when no article is loaded)
            if t and "BIG ROMANTIC RECORDS" not in t:
                title = t
        except Exception:
            pass

        if not title:
            for sel in ("[data-hook='post-title']", "main h1", "article h1"):
                try:
                    el = page.query_selector(sel)
                    if el:
                        t = el.inner_text().strip()
                        if t and "BIG ROMANTIC RECORDS" not in t:
                            title = t
                            break
                except Exception:
                    continue

        if not title:
            # Last resort: URL slug humanized
            slug = url.rstrip("/").split("/single-post/")[-1]
            title = slug.replace("-", " ").replace("_", " ")

        # --- Extract start date ---
        start_date = _parse_date(page_text)

        # --- Extract venue ---
        location_name = _extract_venue(page_text)

        # --- Build source_id from URL slug ---
        slug = url.rstrip("/").split("/single-post/")[-1]
        slug_clean = _SLUG_CLEAN_RE.sub("_", slug)[:80]
        source_id = f"bigromanticrecords_{slug_clean}"

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            name_ja=title,
            raw_title=title,
            raw_description=page_text.strip(),
            start_date=start_date,
            end_date=start_date,
            category=["performing_arts"],
            location_name=location_name,
        )
