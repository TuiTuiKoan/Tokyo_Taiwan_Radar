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
from datetime import datetime, date as _date
import calendar as _calendar
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
    # Normalise full-width digits / spaces for month-only patterns below
    raw_norm = raw.replace('\u3000', ' ').replace('　', ' ')
    for fmt in ("%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(raw_norm, fmt)
        except ValueError:
            continue
    # Month-only: "2026年5月" or "2026 年5 月" → first day of that month
    m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(?:\([^)]*\)\s*)?$', raw_norm)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1)
        except ValueError:
            pass
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

# Multi-city detection uses full prefecture names (no short substring tokens)
# and requires venue-style context nearby to reduce false positives.
_MULTI_CITY_REGIONS = (
    "北海道",
    "東京都",
    "大阪府",
    "京都府",
    "神奈川県",
    "福岡県",
    "愛知県",
    "宮城県",
    "兵庫県",
    "沖縄県",
)

_PREFECTURE_SHORT_NAME = {
    "東京都": "東京",
    "大阪府": "大阪",
    "京都府": "京都",
    "北海道": "北海道",
    "神奈川県": "神奈川",
    "福岡県": "福岡",
    "宮城県": "仙台",
    "兵庫県": "神戸",
    "沖縄県": "沖縄",
    # "愛知県": user decision pending; fallback keeps full name
}

_VENUE_CONTEXT_RE = re.compile(r"会場[：:]|開催地")


def _short_name(prefecture_full: str) -> str:
    """Return a short city-like name for display; fallback to full name."""
    return _PREFECTURE_SHORT_NAME.get(prefecture_full, prefecture_full)


def _detect_multi_city_prefectures(text: str) -> list[str]:
    """Detect prefectures with strict venue-style context near token matches."""
    if not text:
        return []
    found: list[str] = []
    for pref in _MULTI_CITY_REGIONS:
        short = _short_name(pref)
        has_match = False
        for m in re.finditer(re.escape(pref), text):
            start = max(0, m.start() - 200)
            end = min(len(text), m.end() + 200)
            window = text[start:end]
            if _VENUE_CONTEXT_RE.search(window) or re.search(rf"[（(]\s*{re.escape(short)}\s*[）)]", window):
                has_match = True
                break
        if has_match:
            found.append(pref)
    return found


# ──────────────────────────────────────────────────────────────────────────────
# External-venue detection (additive override of the TCC default location).
#
# TCC articles expose no dedicated location field, so the scraper defaults to the
# centre itself. That default is correct for the majority of events (verified:
# of 21 active TCC parent events, 15 have no venue label and genuinely run at the
# centre). This detector is an override-on-signal helper (same shape as
# _detect_multi_city_prefectures): it returns an external venue ONLY when the
# body carries an explicit venue label or a known external hall, otherwise None
# so the TCC default is preserved.
# ──────────────────────────────────────────────────────────────────────────────

# Generic venue-context labels that introduce an explicit external venue name.
_EXPLICIT_VENUE_LABEL_RE = re.compile(
    r"(?:会\s*場|場\s*所|開催地|開催場所)\s*[：:]\s*(.+)"
)

# TCC self-references — these are the organiser / contact address, never an
# external venue. Must not trigger an override (root-cause fix step 5).
_TCC_SELF_NAMES = (
    "台湾文化センター",
    "台北駐日経済文化代表処",
    "台湾文化中心",
)

# Known external halls that reinforce detection (whitelist supplement only — the
# primary logic is the generic label extractor above, NOT a per-event hardcode).
_KNOWN_EXTERNAL_VENUES = (
    "早稲田大学坪内博士記念演劇博物館",
    "ワセダギャラリー",
    "小野記念講堂",
)

# Prefecture hints for known external halls (used when no full prefecture name
# is present in the venue string itself).
_KNOWN_EXTERNAL_VENUE_PREFECTURE = {
    "早稲田大学坪内博士記念演劇博物館": "東京都",
    "ワセダギャラリー": "東京都",
    "小野記念講堂": "東京都",
}


def _derive_venue_prefecture(name: str) -> Optional[str]:
    """Best-effort prefecture for an external venue name; None when unknown."""
    if name in _KNOWN_EXTERNAL_VENUE_PREFECTURE:
        return _KNOWN_EXTERNAL_VENUE_PREFECTURE[name]
    for pref in _MULTI_CITY_REGIONS:
        if pref in name:
            return pref
    return None


def _extract_explicit_location_from_body(text: str) -> tuple[Optional[str], Optional[str]]:
    """Return (venue_name, prefecture_or_None) for an explicit external venue.

    Override-on-signal: returns (None, None) when no external venue is present so
    the caller keeps the TCC default. Primary logic is the generic venue-label
    extractor; named halls are only a reinforcement whitelist. TCC self-names
    (organiser / contact) never count as an external venue.
    """
    if not text:
        return None, None

    # Primary: generic venue-context label extraction (会場：/場所：/開催地：…).
    for m in _EXPLICIT_VENUE_LABEL_RE.finditer(text):
        raw = m.group(1).strip()
        candidate = re.split(r"[\n\r。、，,（(／/｜|]", raw, maxsplit=1)[0]
        candidate = candidate.strip("　 ・-—–:：")
        if len(candidate) < 3:
            continue
        if any(self_name in candidate for self_name in _TCC_SELF_NAMES):
            continue  # organiser/contact line, not an external venue
        return candidate, _derive_venue_prefecture(candidate)

    # Reinforcement: known external halls mentioned anywhere in the body.
    for venue in _KNOWN_EXTERNAL_VENUES:
        if venue in text:
            return venue, _derive_venue_prefecture(venue)

    return None, None


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
            # Also handle month-only end: "10月" or "10 月" → inject year from start
            if not re.match(r'\d{4}', end_raw):
                if re.match(r'\d{1,2}\s*月\s*$', end_raw.strip()):
                    # Month-only end (no year, no day) — inject year from start
                    end_raw = f"{start.year}年{end_raw.strip()}"
                elif re.match(r'\d{1,2}月', end_raw):
                    end_raw = f"{start.year}年{end_raw}"
                elif re.match(r'\d{1,2}日', end_raw):
                    end_raw = f"{start.year}年{start.month}月{end_raw}"
            end = _parse_date(end_raw)
            # If end_raw was month-only, advance to last day of that month
            if end and end_raw and re.search(r'年\d{1,2}\s*月\s*$', end_raw.strip()):
                last_day = _calendar.monthrange(end.year, end.month)[1]
                end = datetime(end.year, end.month, last_day)
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
        # Site does not expose a dedicated location field; default to the center.
        # Verified address: jp.taiwan.culture.tw/cp.aspx?n=362 (2026-04-26)
        location_name = "台北駐日経済文化代表処 台湾文化センター"
        location_address: str | None = "東京都港区虎ノ門1-1-12 虎ノ門ビル2階"

        location_prefectures = ["東京都"]

        # If text clearly indicates multiple event cities, treat it as multi-city.
        _desc_check = (description_ja or "") + "\n" + (name_ja or "")
        _found_regions = _detect_multi_city_prefectures(_desc_check)
        if len(_found_regions) >= 2:
            location_name = "・".join(_short_name(r) for r in _found_regions)
            location_address = None
            location_prefectures = list(_found_regions)
        else:
            # Single explicit external venue (会場：… or a known external hall)
            # overrides the TCC default. TCC self-references (organiser/contact)
            # are ignored, and a no-signal result preserves the TCC default.
            _ext_venue, _ext_pref = _extract_explicit_location_from_body(_desc_check)
            if _ext_venue:
                location_name = _ext_venue
                location_address = None
                location_prefectures = [_ext_pref] if _ext_pref else None

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
            official_url=url,  # official organiser page
            original_language="ja",
            name_ja=name_ja,
            description_ja=description_ja,
            raw_title=name_ja,
            raw_description=description_ja,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=location_address,
            location_prefectures=location_prefectures,
            is_paid=is_paid,
            price_info=price_text,
            category=categories,
        )
