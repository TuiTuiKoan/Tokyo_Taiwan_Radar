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
# The activity list URL
ACTIVITY_LIST_URL = f"{BASE_URL}/News3.aspx?n=365&sms=10657"


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
    # Strip day-of-week / holiday markers in brackets: （月・祝） or (火) → removed
    # Only strip brackets whose content starts with a non-digit (keeps e.g. (2026))
    raw = re.sub(r'[（(][^）)\d][^）)]*[）)]', '', raw).strip()
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
    # Only split on range indicators (not on hyphen, which is used in YYYY-MM-DD)
    parts = re.split(r"[～~〜]|(?<=\d)\s*[–—]\s*(?=\d)", text)
    start = _parse_date(parts[0]) if len(parts) >= 1 else None
    end = _parse_date(parts[1]) if len(parts) >= 2 else None
    return start, end


# Structured date labels that appear in event body text.
# Captures the rest of the line (up to 120 chars) so that date strings
# with parenthetical day-of-week markers like「2026年5月4日（月・祝）～5日（火・祝）」
# are captured in full and cleaned by _parse_date / _extract_event_dates_from_body.
_BODY_DATE_LABELS = re.compile(
    r"[■●▶◆◇・]?\s*"
    r"(?:日\s*時|開催日時|日時|会期|開催期間|期間|開催日|イベント日時)"
    r"\s*[：:]"
    r"\s*(.{5,120})",
    re.MULTILINE,
)

# Slash-style date in title: "M/DD(曜)" e.g. "3/17(火)"
_TITLE_SLASH_DATE = re.compile(r"(\d{1,2})/(\d{1,2})[（(][月火水木金土日祝・]+[）)]")

# Prose date in body: "MM月DD日(曜)" with no label, common in report articles
_PROSE_DATE = re.compile(r"(\d{1,2})月(\d{1,2})日[（(][月火水木金土日祝・]+[）)]")
# Tier 1.3: unlabeled kanji date range in body — "MM月DD日〜MM月DD日" (no day-of-week required)
# Also handles YYYY年MM月DD日〜 prefix if year is present
_PROSE_DATE_RANGE = re.compile(
    r'((?:\d{4}年)?\d{1,2}月\d{1,2}日)[^\d年]{0,6}[～~〜][^\d年]{0,6}'
    r'((?:\d{4}年)?\d{1,2}月\d{1,2}日)'
)
# Title keywords that mark an article as a report/recap
_REPORT_KEYWORDS = re.compile(r"レポート|レポ|報告|記録|アーカイブ|recap", re.IGNORECASE)

# Tier 1b: dot-separated date in labeled body section — e.g. "10.11 Sat" or "10.11 (Sat)"
# Matches M.DD or MM.DD followed by an English weekday abbreviation
_DOTDAY_DATE = re.compile(
    r'(\d{1,2}\.\d{2})\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)',
    re.IGNORECASE,
)
# Label prefix for Tier 1b — same set as Tier 1 body labels
_DOTDAY_LABEL_SECTION = re.compile(
    r'[■●▶◆◇・]?\s*'
    r'(?:日\s*時|開催日時|日時|会期|開催期間|期間|開催日|イベント日時)'
    r'\s*[：:]\s*(.{1,200})',
    re.MULTILINE | re.DOTALL,
)


def _extract_dotday_date_from_body(
    text: Optional[str], post_date: Optional[datetime]
) -> Optional[datetime]:
    """Tier 1b: detect M.DD Day format inside a labeled date section.

    Handles patterns like:
      日時：10.11 Sat 16:30～19:00（開 16:00）

    Year is inferred from post_date using the same ±180-day window as Tier 1.5.
    """
    if not text or not post_date:
        return None
    # Only search within a labeled date section
    sec_m = _DOTDAY_LABEL_SECTION.search(text)
    if not sec_m:
        return None
    section_text = sec_m.group(1)[:200]
    m = _DOTDAY_DATE.search(section_text)
    if not m:
        return None
    raw = m.group(1)  # e.g. "10.11"
    parts = raw.split('.')
    try:
        month, day = int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return None
    for year in (post_date.year, post_date.year + 1, post_date.year - 1):
        try:
            candidate = datetime(year, month, day)
        except ValueError:
            continue
        delta = abs((candidate - post_date).days)
        if delta <= 180:
            return candidate
    return None


def _extract_prose_date_range_from_body(
    text: Optional[str], post_date: Optional[datetime]
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Tier 1.3: find an unlabeled kanji date range like '11月28日〜12月14日'.

    No label or day-of-week marker required.  Year is inferred from post_date
    using the same ±365-day window as Tier 1.5.
    """
    if not text or not post_date:
        return None, None
    m = _PROSE_DATE_RANGE.search(text)
    if not m:
        return None, None

    def _infer(raw: str) -> Optional[datetime]:
        # raw is like "11月28日" or "2025年11月28日"
        raw = raw.strip()
        if re.match(r'\d{4}年', raw):
            return _parse_date(raw)
        month_m = re.match(r'(\d{1,2})月(\d{1,2})日', raw)
        if not month_m:
            return None
        month, day = int(month_m.group(1)), int(month_m.group(2))
        for year in (post_date.year, post_date.year + 1, post_date.year - 1):
            try:
                candidate = datetime(year, month, day)
            except ValueError:
                continue
            delta = (candidate - post_date).days
            if -365 <= delta <= 365:
                return candidate
        return None

    start = _infer(m.group(1))
    end = _infer(m.group(2))
    return start, end


def _extract_prose_date_from_body(
    text: Optional[str], post_date: Optional[datetime]
) -> Optional[datetime]:
    """Tier 1.5: find first kanji-style date in prose body (no label required).

    Matches '10月25日(土)' and infers the year from post_date.
    Used for report/recap articles where the event date appears in passing.
    """
    if not text or not post_date:
        return None
    m = _PROSE_DATE.search(text)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    for year in (post_date.year, post_date.year - 1, post_date.year + 1):
        try:
            candidate = datetime(year, month, day)
        except ValueError:
            continue
        # Accept dates up to 180 days before the publish date (reports lag events)
        delta = (post_date - candidate).days
        if 0 <= delta <= 180:
            return candidate
    return None


def _extract_event_dates_from_body(
    text: Optional[str],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Tier 1: look for structured event-date labels inside body text."""
    if not text:
        return None, None
    for m in _BODY_DATE_LABELS.finditer(text):
        raw = m.group(1).strip()
        # Strip day-of-week / holiday markers before range-splitting
        clean = re.sub(r'[（(][^）)\d][^）)]*[）)]', '', raw).strip()
        # Split on range separator
        parts = re.split(r'[～~〜]|(?<=\d)\s*[–—]\s*(?=\d)', clean, maxsplit=1)
        start_raw = parts[0].strip()
        end_raw = parts[1].strip() if len(parts) > 1 else None
        start = _parse_date(start_raw)
        if start and end_raw:
            # Handle abbreviated ends: "5日" → inject year+month; "3月5日" → inject year
            if not re.match(r'\d{4}', end_raw):
                if re.match(r'\d{1,2}月', end_raw):
                    end_raw = f"{start.year}年{end_raw}"
                elif re.match(r'\d{1,2}日', end_raw):
                    end_raw = f"{start.year}年{start.month}月{end_raw}"
            end = _parse_date(end_raw)
        else:
            end = None
        if start:
            return start, end
    return None, None


def _extract_date_from_title(
    title: Optional[str], post_date: Optional[datetime]
) -> Optional[datetime]:
    """Tier 2: parse a slash-style date like '3/17(火)' from the title."""
    if not title or not post_date:
        return None
    m = _TITLE_SLASH_DATE.search(title)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    year = post_date.year
    try:
        candidate = datetime(year, month, day)
    except ValueError:
        return None
    # If the candidate is more than 30 days before post_date, try next year
    if (post_date - candidate).days > 30:
        try:
            candidate = datetime(year + 1, month, day)
        except ValueError:
            return None
    return candidate


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
            url = f"{ACTIVITY_LIST_URL}&p={current_page}"
            logger.info("Fetching list page %d: %s", current_page, url)
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
            except PWTimeout:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # Collect all <a> tags that point to article detail pages
            anchors = page.query_selector_all("a[href*='News_Content']")
            page_links = []
            for a in anchors:
                href = a.get_attribute("href") or ""
                if not href:
                    continue
                full = href if href.startswith("http") else f"{BASE_URL}/{href}"
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
        name_ja = (
            _safe_text(page, ".simple-text.title")
            or _safe_text(page, ".group.page-content h2")
            or _safe_text(page, "h1")
        )
        if not name_ja:
            logger.warning("Could not find title at %s, skipping.", url)
            return None

        # --- Description ---
        description_ja = (
            _safe_text(page, ".essay")
            or _safe_text(page, ".area-essay")
            or _safe_text(page, ".group.page-content")
        )

        # --- Date ---
        # "日付：YYYY-MM-DD" at the page bottom is the PUBLISH date, not the event date.
        # We read it as post_date and use it only as a Tier-3 fallback.
        raw_post = _safe_text(page, ".list-text.detail")
        if raw_post:
            raw_post = raw_post.replace("日付：", "").replace("日付:", "").strip()
        post_date = _parse_date(raw_post)

        # Tier 1: structured label in body (日時:, 会期:, 開催日:, …)
        start_date, end_date = _extract_event_dates_from_body(description_ja)

        # Tier 1b: dot-separated date in labeled section e.g. "10.11 Sat"
        if start_date is None:
            start_date = _extract_dotday_date_from_body(description_ja, post_date)

        # Tier 1.3: unlabeled kanji date range e.g. "11月28日〜12月14日"
        if start_date is None:
            start_date, end_date = _extract_prose_date_range_from_body(description_ja, post_date)

        # Tier 1.5: prose date in body e.g. "10月25日(土)に開催された" (report articles)
        if start_date is None:
            start_date = _extract_prose_date_from_body(description_ja, post_date)

        # Tier 2: slash date in title (e.g. "3/17(火)")
        if start_date is None:
            start_date = _extract_date_from_title(name_ja, post_date)

        # Tier 3: fall back to publish date so start_date is never null
        if start_date is None:
            start_date = post_date

        # Rule: single-day events must have end_date = start_date (never null)
        if start_date and end_date is None:
            end_date = start_date

        # Prepend extracted event date to raw_description for annotator context
        date_prefix = ""
        if start_date:
            date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
            if end_date:
                date_prefix += f" ～ {end_date.strftime('%Y年%m月%d日')}"
            date_prefix += "\n"
        if date_prefix and description_ja:
            description_ja = date_prefix + description_ja

        # --- Location ---
        # Site does not expose a dedicated location field; default to the center
        location_name = "台北駐日経済文化代表処 台湾文化センター"

        # --- Price ---
        # Extract from description text if available
        price_text = None
        is_paid = _is_paid(description_ja)

        # --- Category ---
        categories = ["culture"]
        if name_ja and _REPORT_KEYWORDS.search(name_ja):
            categories.append("report")

        # --- Source ID: use URL path as stable identifier ---
        source_id = hashlib.md5(url.encode()).hexdigest()[:16]

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            name_ja=name_ja,
            description_ja=description_ja,
            raw_title=name_ja,
            raw_description=description_ja,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            is_paid=is_paid,
            price_info=price_text,
            category=categories,
        )
