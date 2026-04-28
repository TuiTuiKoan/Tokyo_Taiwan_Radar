"""
Scraper for iwafu.com — Japanese event discovery platform.

Searches for Taiwan-related events across all of Japan（全日本）.

Strategy:
  1. Fetch paginated search results (keyword=台湾) with Playwright (JS rendering)
  2. Parse event cards: date range, title, description snippet, prefecture, location
  3. No prefecture filter — all regions (Tokyo, Osaka, Fukuoka, Sapporo, etc.) included
  4. Visit each detail page for full description
  5. source_id = "iwafu_{numeric_id}" (stable across runs)
"""

import re
import time
import logging
from datetime import datetime
from typing import Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.iwafu.com"
SEARCH_URL = f"{BASE_URL}/jp/events"
# URL-encoded 台湾
SEARCH_KEYWORD = "%E5%8F%B0%E6%B9%BE"
MAX_PAGES = 10

# Known prefecture names used on iwafu cards
_PREFECTURES = {
    "東京", "神奈川", "千葉", "埼玉", "大阪", "京都", "兵庫",
    "愛知", "福岡", "北海道", "宮城", "広島", "群馬", "栃木", "茨城",
    "静岡", "新潟", "石川", "長野", "岐阜", "三重", "奈良", "和歌山",
    "滋賀", "岡山", "熊本", "鹿児島", "沖縄",
}

# UI section markers that appear after the event description on iwafu detail pages.
# Ordered by typical appearance order on page — first match wins.
_NOISE_MARKERS = (
    "Q&A イベントについて",  # Q&A section (earliest noise marker)
    "近くの看板",             # PR / nearby-signs section
    "近くのイベント",          # nearby events section
    "地図検索に切り替えて",   # map search section
)

# Patterns that indicate a global/nationwide tour event that merely INCLUDES Taiwan
# as one stop — these are NOT Taiwan-themed cultural events.
# A hit on any of these patterns causes the event to be rejected.
_GLOBAL_TOUR_PATTERNS = re.compile(
    r"台湾など世界各地|台湾など.*各地|全国各地.*台湾|世界各地.*台湾|台湾.*世界各地"
    r"|全国[0-9０-９]+[都道府県施設箇所].*台湾|台湾.*全国[0-9０-９]",
    re.DOTALL,
)

# Title fragments whose presence in the event TITLE means the event should always
# be rejected, regardless of description content.
# Use this for known entertainment IP series that run global/nationwide tours
# and coincidentally mention Taiwan as one venue.
_BLOCKED_TITLE_PATTERNS = re.compile(
    r"リアル脱出ゲーム.*名探偵コナン|名探偵コナン.*リアル脱出ゲーム"
    r"|名探偵コナン.*脱出|脱出.*名探偵コナン",  # catch title variants even without リアル
)

# Entire IP series that are permanently blocked regardless of title wording.
# Add the series name when all events from an IP are confirmed non-Taiwan-themed.
# These are checked against both the card title AND the h1 title on the detail page.
_BLOCKED_SERIES = re.compile(
    r"名探偵コナン"  # All Conan events — confirmed global-tour non-Taiwan-themed
    r"|神韻",       # Shen Yun — US-based Falun Gong troupe, not Taiwan-themed
)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    """Parse date strings in iwafu YYYY.MM.DD format (and other common formats)."""
    if not raw:
        return None
    raw = raw.strip()
    # Strip bracketed day-of-week markers like （月）(火) — but keep digit-only brackets
    raw = re.sub(r'[（(][^）)\d][^）)]*[）)]', '', raw).strip()
    for fmt in ("%Y.%m.%d", "%Y/%m/%d", "%Y-%m-%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    logger.warning("Could not parse date: %s", raw)
    return None


def _parse_date_range(text: Optional[str]) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse iwafu date range string: '2026.06.26 ～ 2026.06.28' → (start, end)."""
    if not text:
        return None, None
    parts = re.split(r'[～~〜]', text)
    start = _parse_date(parts[0].strip()) if parts else None
    end = _parse_date(parts[1].strip()) if len(parts) > 1 else None
    return start, end


# ---------------------------------------------------------------------------
# Card text parsers
# (Card inner_text uses \n as separator)
# Structure: date_range \n title \n \n - desc... \n categories... \n prefecture \n stations
# ---------------------------------------------------------------------------

def _extract_event_id(url: str) -> Optional[str]:
    m = re.search(r'/events/(\d+)', url)
    return m.group(1) if m else None


def _extract_prefecture_from_card(lines: list[str]) -> str:
    """Find the prefecture label near the end of card text lines.

    The prefecture appears as a short standalone line (2-5 chars, no 駅, no dash prefix)
    in the last several lines of the card.
    """
    for line in reversed(lines[-8:] if len(lines) >= 8 else lines):
        line = line.strip()
        if not line:
            continue
        if "駅" in line:
            continue
        if line.startswith("-"):
            continue
        if line in _PREFECTURES:
            return line
    return ""


def _extract_title_from_card(lines: list[str]) -> str:
    """Extract event title — second non-empty, non-date, non-description line."""
    non_empty = [l.strip() for l in lines if l.strip() and not l.strip().startswith("-")]
    # First non-empty line is the date range (contains digits and ～)
    # Second non-empty line is the title
    if len(non_empty) >= 2:
        return non_empty[1]
    return non_empty[0] if non_empty else ""


def _extract_description_snippet(lines: list[str]) -> str:
    """Extract description bullet lines from card text."""
    bullets = [l.strip().lstrip("- ").strip() for l in lines if l.strip().startswith("-")]
    return "\n".join(bullets)


def _extract_station_hint(lines: list[str]) -> Optional[str]:
    """Find station name line (contains 駅) for location_name hint."""
    for line in reversed(lines[-5:] if len(lines) >= 5 else lines):
        if "駅" in line:
            return line.strip()
    return None


# ---------------------------------------------------------------------------
# Main scraper class
# ---------------------------------------------------------------------------

class IwafuScraper(BaseScraper):
    """Scrapes Taiwan-related events across all of Japan from iwafu.com."""

    SOURCE_NAME = "iwafu"

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

            # Phase 1: collect all event cards from paginated search results
            all_cards = self._collect_cards(page)
            logger.info("Total event cards found: %d", len(all_cards))

            cards = all_cards
            logger.info("Taiwan events: %d", len(cards))

            # Phase 3: visit detail pages for full descriptions
            seen_ids: set[str] = set()
            for card in cards:
                event_id = card["id"]
                if event_id in seen_ids:
                    continue
                seen_ids.add(event_id)
                try:
                    event = self._scrape_detail(page, card)
                    if event:
                        events.append(event)
                    time.sleep(1.5)
                except Exception as exc:
                    logger.error("Failed to scrape event %s: %s", card.get("url"), exc)

            browser.close()

        return events

    # ------------------------------------------------------------------
    # Card collection (search results pages)
    # ------------------------------------------------------------------

    def _collect_cards(self, page: Page) -> list[dict]:
        """Fetch all search result pages and extract event card info."""
        cards: list[dict] = []
        seen_ids: set[str] = set()
        current_page = 1

        while current_page <= MAX_PAGES:
            if current_page == 1:
                url = f"{SEARCH_URL}?keyword={SEARCH_KEYWORD}"
            else:
                url = f"{SEARCH_URL}?keyword={SEARCH_KEYWORD}&page={current_page}"

            logger.info("Fetching list page %d: %s", current_page, url)
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
            except PWTimeout:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            page_cards = self._parse_page_cards(page)
            new_cards = [c for c in page_cards if c["id"] not in seen_ids]

            if not new_cards:
                logger.info("No new events on page %d, stopping pagination.", current_page)
                break

            for c in new_cards:
                seen_ids.add(c["id"])
            cards.extend(new_cards)
            logger.info(
                "Page %d: %d new cards (total: %d)", current_page, len(new_cards), len(cards)
            )

            current_page += 1
            time.sleep(1.0)

        return cards

    def _parse_page_cards(self, page: Page) -> list[dict]:
        """Extract event info from all card links on the current page."""
        anchors = page.query_selector_all("a[href*='/jp/events/']")
        cards = []
        seen_hrefs: set[str] = set()

        for anchor in anchors:
            href = anchor.get_attribute("href") or ""
            if not re.search(r'/jp/events/\d+', href):
                continue
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            if full_url in seen_hrefs:
                continue
            seen_hrefs.add(full_url)

            event_id = _extract_event_id(full_url)
            if not event_id:
                continue

            card_text = anchor.inner_text() or ""
            lines = card_text.split("\n")

            # Date range: search for YYYY.MM.DD ～ YYYY.MM.DD pattern
            date_m = re.search(
                r'(\d{4}\.\d{2}\.\d{2})\s*[～~〜]\s*(\d{4}\.\d{2}\.\d{2})', card_text
            )
            if date_m:
                date_range_str = f"{date_m.group(1)} ～ {date_m.group(2)}"
            else:
                single_m = re.search(r'(\d{4}\.\d{2}\.\d{2})', card_text)
                date_range_str = single_m.group(0) if single_m else None

            title = _extract_title_from_card(lines)
            prefecture = _extract_prefecture_from_card(lines)
            description_snippet = _extract_description_snippet(lines)
            location_hint = _extract_station_hint(lines)

            cards.append({
                "id": event_id,
                "url": full_url,
                "title": title,
                "date_range_str": date_range_str,
                "prefecture": prefecture,
                "description_snippet": description_snippet,
                "location_hint": location_hint,
            })

        return cards

    # ------------------------------------------------------------------
    # Detail page scraping
    # ------------------------------------------------------------------

    def _scrape_detail(self, page: Page, card: dict) -> Optional[Event]:
        """Visit the event detail page and return a fully populated Event."""
        url = card["url"]
        event_id = card["id"]

        # Fast-reject: title-based block (check before expensive page load)
        card_title = card.get("title", "")
        if _BLOCKED_TITLE_PATTERNS.search(card_title) or _BLOCKED_SERIES.search(card_title):
            logger.info(
                "Skipping blocked-title event: %s — %s", event_id, card_title[:60]
            )
            return None

        try:
            page.goto(url, wait_until="networkidle", timeout=30_000)
        except PWTimeout:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        # --- Full description from main element ---
        main_el = page.query_selector("main")
        main_text = main_el.inner_text() if main_el else ""
        main_lines = [l.strip() for l in main_text.split("\n") if l.strip()]

        # main_lines layout:
        #   [0]  "Item N of M"
        #   [1]  "TOKYO 東京"
        #   [2]  "2026年6月26日（金）～ 6月28日（日）"
        #   [3]  "{TITLE}"
        #   [4+] description paragraphs

        # --- Title: h1 > card title fallback ---
        h1_el = page.query_selector("h1")
        h1_text = h1_el.inner_text().strip() if h1_el else ""
        title = h1_text or card.get("title") or ""

        if not title:
            logger.warning("No title found at %s, skipping.", url)
            return None

        # Second-pass title block on the actual h1 (card title may be truncated)
        if _BLOCKED_TITLE_PATTERNS.search(title) or _BLOCKED_SERIES.search(title):
            logger.info(
                "Skipping blocked-title event (h1 check): %s — %s", event_id, title[:60]
            )
            return None

        # --- Description: everything after the title in main_lines ---
        description = ""
        title_idx = None
        for i, line in enumerate(main_lines):
            if line == title:
                title_idx = i
                break
        if title_idx is not None and title_idx + 1 < len(main_lines):
            description = "\n".join(main_lines[title_idx + 1 :])
        elif main_text:
            description = main_text.strip()

        # Fall back to card description snippet if detail page gave nothing
        if not description:
            description = card.get("description_snippet", "")

        # Strip iwafu page UI noise (Q&A, PR ads, nearby events, map, tags)
        description = _strip_iwafu_noise(description)

        # Reject global/nationwide tour events that merely include Taiwan as one of
        # many stops — they are NOT Taiwan-themed (e.g. "全国各地をはじめ台湾など世界各地で開催")
        combined_text = f"{title}\n{description}"
        if _GLOBAL_TOUR_PATTERNS.search(combined_text):
            logger.info(
                "Skipping global-tour event (Taiwan is just one stop): %s — %s",
                event_id, title[:60],
            )
            return None

        # --- Dates: from card (YYYY.MM.DD format is reliable) ---
        start_date, end_date = _parse_date_range(card.get("date_range_str"))

        # Fallback: search for date pattern in detail page text
        if start_date is None and main_text:
            date_m = re.search(
                r'(\d{4}\.\d{2}\.\d{2})\s*[～~〜]\s*(\d{4}\.\d{2}\.\d{2})', main_text
            )
            if date_m:
                start_date = _parse_date(date_m.group(1))
                end_date = _parse_date(date_m.group(2))
            else:
                single_m = re.search(r'(\d{4}\.\d{2}\.\d{2})', main_text)
                if single_m:
                    start_date = _parse_date(single_m.group(1))

        # Single-day rule: end_date must never be None when start_date is known
        if start_date and end_date is None:
            end_date = start_date

        # --- Location ---
        # Primary: extract 場所：<venue> from detail page text (e.g. "場所：中野区役所…")
        place_m = re.search(
            r'場所[：:]\s*(.+?)(?:\n|交通手段|Q&A|https?://|$)', main_text, re.DOTALL
        )
        if place_m:
            place_val = place_m.group(1).strip()
            location_name = place_val
            location_address = place_val
        else:
            location_name = card.get("location_hint") or card.get("prefecture") or ""
            location_address = card.get("prefecture") or None

        # --- Is paid? ---
        combined = f"{title} {description}"
        is_paid = _detect_paid(combined)

        # --- raw_description: prepend date prefix for annotator ---
        date_prefix = ""
        if start_date:
            date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
            if end_date and end_date != start_date:
                date_prefix += f" ～ {end_date.strftime('%Y年%m月%d日')}"
            date_prefix += "\n\n"

        raw_description = description or card.get("description_snippet", "")
        if date_prefix:
            raw_description = date_prefix + raw_description

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=f"iwafu_{event_id}",
            source_url=url,
            original_language="ja",
            name_ja=title,
            description_ja=description or None,
            raw_title=title,
            raw_description=raw_description or None,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=location_address,
            is_paid=is_paid,
            category=[],
        )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _strip_iwafu_noise(text: str) -> str:
    """Truncate text at the first iwafu UI section marker (Q&A, nearby signs, etc.)."""
    if not text:
        return text
    for marker in _NOISE_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    return text.strip()


def _detect_paid(text: Optional[str]) -> Optional[bool]:
    if not text:
        return None
    if any(w in text for w in ["無料", "入場無料", "参加無料", "free"]):
        return False
    if any(w in text for w in ["有料", "入場料", "料金", "円", "¥", "費用"]):
        return True
    return None
