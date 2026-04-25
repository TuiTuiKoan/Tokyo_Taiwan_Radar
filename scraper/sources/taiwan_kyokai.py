"""
Scraper for 一般財団法人台湾協会 (taiwan-kyokai.or.jp).

All content on this site is Taiwan-related; the scraper looks for event
announcements (pages that contain a 日時: / 日　時: field) and filters
for venues in the greater Tokyo area.

Strategy:
  1. Fetch https://taiwan-kyokai.or.jp/news/
  2. Collect all news-* links
  3. For each detail page: check for 日時 field → event; else skip
  4. Filter: venue must contain Tokyo area markers (OR no venue → keep if
     title contains event keywords)
  5. Extract start_date, end_date, venue, description
  6. source_id = "taiwan_kyokai_{slug}" from the URL slug (stable)
"""

import re
import logging
from datetime import datetime
from typing import Optional

from playwright.sync_api import sync_playwright

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://taiwan-kyokai.or.jp"
NEWS_URL = f"{BASE_URL}/news/"
SOURCE_NAME = "taiwan_kyokai"

# Tokyo area venue markers
_TOKYO_MARKERS = [
    "東京", "港区", "千代田区", "新宿区", "渋谷区", "中央区", "台東区",
    "文京区", "豊島区", "品川区", "目黒区", "江東区", "墨田区", "荒川区",
    "足立区", "葛飾区", "江戸川区", "北区", "板橋区", "練馬区", "杉並区",
    "世田谷区", "大田区", "中野区",
]

# Imperial year → Gregorian
_GENGO = {"令和": 2018, "平成": 1988, "昭和": 1925, "大正": 1911}


def _convert_gengo(year_str: str, era: str) -> Optional[int]:
    base = _GENGO.get(era)
    if base is None:
        return None
    try:
        return base + int(year_str)
    except ValueError:
        return None


def _parse_date(raw: str) -> Optional[datetime]:
    """
    Parse event date strings in multiple formats:
      - '2025年10月25日（土曜日）'
      - '令和8（2026）年４月12日（日）'
      - '2026年5月16日'
    Returns the first valid date found.
    """
    if not raw:
        return None

    # Normalize full-width digits → ASCII
    table = str.maketrans("０１２３４５６７８９", "0123456789")
    raw = raw.translate(table)

    # Pattern A: Western year first — '2025年10月25日'
    m = re.search(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', raw)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # Pattern B: Imperial era with Western year in parentheses —
    # '令和8（2026）年４月12日'
    m = re.search(r'(令和|平成|昭和)(\d+)[（(]\d{4}[）)]年(\d{1,2})月(\d{1,2})日', raw)
    if m:
        try:
            # Use the parenthesised western year if extractable
            wy_m = re.search(r'[（(](\d{4})[）)]', raw)
            year = int(wy_m.group(1)) if wy_m else _convert_gengo(m.group(2), m.group(1))
            return datetime(year, int(m.group(3)), int(m.group(4)))
        except (ValueError, TypeError):
            pass

    # Pattern C: Imperial era without Western year — '令和8年4月12日'
    m = re.search(r'(令和|平成|昭和)(\d+)年(\d{1,2})月(\d{1,2})日', raw)
    if m:
        year = _convert_gengo(m.group(2), m.group(1))
        if year:
            try:
                return datetime(year, int(m.group(3)), int(m.group(4)))
            except ValueError:
                pass

    logger.warning("Could not parse date: %r", raw)
    return None


def _extract_slug(url: str) -> Optional[str]:
    """Extract slug like 'news-260217' from URL."""
    m = re.search(r'/(news-[^/]+)/?$', url)
    return m.group(1) if m else None


def _is_tokyo_venue(text: str) -> bool:
    """Return True if venue or address line contains a Tokyo-area marker."""
    # Collect venue line(s): 場所：… or 場　所：… or 会場：…
    venue_m = re.search(
        r'(?:場\s*所|会場)\s*[：:]\s*([^\n]{3,80})',
        text,
    )
    # Collect address line: 住所：… or 住　所：…
    addr_m = re.search(
        r'(?:住\s*所)\s*[：:]\s*([^\n]{5,80})',
        text,
    )
    combined = " ".join(
        filter(None, [
            venue_m.group(1) if venue_m else "",
            addr_m.group(1) if addr_m else "",
        ])
    )
    if not combined.strip():
        return False
    return any(marker in combined for marker in _TOKYO_MARKERS)


def _extract_event_fields(text: str) -> dict:
    """Extract date, venue, time, price from a news detail page body text."""
    result: dict = {
        "start_date": None,
        "end_date": None,
        "location_name": None,
        "location_address": None,
        "is_paid": None,
        "price_info": None,
    }

    # --- Date (日時 / 日　時) ---
    date_m = re.search(
        r'(?:日\s*時)\s*[：:]\s*([^\n]{4,60})',
        text,
    )
    if date_m:
        raw_date = date_m.group(1)
        result["start_date"] = _parse_date(raw_date)

    # Also try standalone 時間: line
    if not result["start_date"]:
        time_m = re.search(r'時間\s*[：:]\s*([^\n]{4,50})', text)
        if time_m:
            result["start_date"] = _parse_date(time_m.group(1))

    # Priority 2: Event dates with day-of-week markers, e.g. "5月16日（土）".
    # These almost always denote actual event dates, not page publish dates.
    # Prefer them over the generic YYYY年MM月DD日 fallback, which may pick up
    # the page's publish date that appears at the top of the body text.
    if not result["start_date"]:
        dow_m = re.search(
            r'(\d{1,2})月(\d{1,2})日（[月火水木金土日][曜]?[日]?）',
            text,
        )
        if dow_m:
            # Infer year from nearest 20XX年 in text before this position,
            # or from anywhere in text as fallback.
            year_m = re.search(r'(20\d{2})年', text[: dow_m.start()])
            if not year_m:
                year_m = re.search(r'(20\d{2})年', text)
            if year_m:
                try:
                    result["start_date"] = datetime(
                        int(year_m.group(1)),
                        int(dow_m.group(1)),
                        int(dow_m.group(2)),
                    )
                except ValueError:
                    pass

    # Fallback: find any clear date in body (YYYY年MM月DD日)
    if not result["start_date"]:
        m = re.search(r'((?:20\d{2}|令和\d+[（(]\d{4}[）)])年\d{1,2}月\d{1,2}日)', text)
        if m:
            result["start_date"] = _parse_date(m.group(1))

    # --- Venue (場所 / 場　所 / 会場) ---
    venue_m = re.search(r'(?:場\s*所|会場)\s*[：:]\s*([^\n]{3,80})', text)
    if venue_m:
        result["location_name"] = venue_m.group(1).strip()

    # --- Address (住所 / 住　所) ---
    addr_m = re.search(r'(?:住\s*所)\s*[：:]\s*([^\n]{5,80})', text)
    if addr_m:
        result["location_address"] = addr_m.group(1).strip()

    # --- Paid? (会費 / 参加費) ---
    fee_m = re.search(r'(?:会費|参加費)\s*[：:]\s*([^\n]{2,60})', text)
    if fee_m:
        fee_text = fee_m.group(1).strip()
        result["price_info"] = fee_text
        result["is_paid"] = "無料" not in fee_text

    # Single-day rule: end_date must equal start_date when only start is found.
    # taiwan_kyokai events are single-day ceremonies/lectures with a time range
    # (e.g. "正午～午後２時30分") — there is never a multi-day range.
    if result["start_date"] and not result["end_date"]:
        result["end_date"] = result["start_date"]

    return result


class TaiwanKyokaiScraper(BaseScraper):
    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            # ── Step 1: collect news links ──────────────────────────────────
            page.goto(NEWS_URL, timeout=20000)
            page.wait_for_timeout(1500)

            anchors = page.query_selector_all('a[href*="news-"]')
            hrefs: list[str] = []
            seen: set[str] = set()
            for a in anchors:
                href = a.get_attribute("href") or ""
                if href and href not in seen and re.search(r'/news-[\w-]+/?$', href):
                    seen.add(href)
                    hrefs.append(href)

            logger.info("[%s] Found %d news pages", SOURCE_NAME, len(hrefs))

            # ── Step 2: visit each page ──────────────────────────────────────
            for href in hrefs:
                url = href if href.startswith("http") else BASE_URL + href
                slug = _extract_slug(url)
                if not slug:
                    continue

                try:
                    page.goto(url, timeout=20000)
                    page.wait_for_timeout(1000)
                except Exception as exc:
                    logger.warning("[%s] Could not load %s: %s", SOURCE_NAME, url, exc)
                    continue

                # Extract body text (strip nav / sidebar)
                raw_text = page.inner_text("body") or ""
                # Trim sidebar cruft after クイックリンク
                body_text = raw_text.split("クイックリンク")[0]

                # ── Extract title ───────────────────────────────────────────
                title_el = page.query_selector("h1, article h2, .entry-title")
                raw_title = title_el.inner_text().strip() if title_el else ""
                if not raw_title:
                    # Fallback: first non-empty line after navigation items
                    for line in body_text.splitlines():
                        line = line.strip()
                        if len(line) > 5 and line not in (
                            "一般財団法人台湾協会", "ホーム", "協会概要", "事業内容",
                            "新着情報", "お問合せ", "蔵書検索", "マイページ",
                            "内容をスキップ",
                        ):
                            raw_title = line
                            break

                # If raw_title is just a generic heading like「講演会のご案内」,
                # look for a more specific 講演内容: / タイトル: line in the body.
                _GENERIC_HEADINGS = frozenset([
                    "【講演会のご案内】", "講演会のご案内", "講演会のお知らせ",
                    "イベントのご案内", "セミナーのご案内",
                ])
                if raw_title in _GENERIC_HEADINGS or raw_title.strip("【】") in _GENERIC_HEADINGS:
                    lecture_m = re.search(
                        r'(?:講演(?:内容|テーマ)|タイトル)\s*[：:「]\s*「?([^」\n]{5,60})」?',
                        body_text,
                    )
                    if lecture_m:
                        raw_title = lecture_m.group(1).strip()

                # ── Check this page is an event (has 日時 / 日　時 field, or date+venue) ──
                has_date_field = bool(re.search(r'(?:日\s*時|時間)\s*[：:]', body_text))
                # Also accept pages where a clear date appears alongside a venue field
                has_venue_field = bool(re.search(r'(?:場\s*所|会場)\s*[：:]', body_text))
                has_explicit_date = bool(re.search(r'(?:20\d{2}|令和\d+)[（(]?\d*[）)]?年\d{1,2}月\d{1,2}日', body_text))
                if not (has_date_field or (has_venue_field and has_explicit_date)):
                    logger.debug("[%s] Skipping non-event page: %s", SOURCE_NAME, slug)
                    continue

                # ── Extract structured fields ────────────────────────────────
                fields = _extract_event_fields(body_text)
                start_date: Optional[datetime] = fields["start_date"]

                if not start_date:
                    logger.warning("[%s] No start_date on %s — skipping", SOURCE_NAME, slug)
                    continue

                # ── Venue filter: must be Tokyo area ────────────────────────
                # (filter removed — now accepts all Japan venues)

                # ── Build raw_description ────────────────────────────────────
                date_prefix = (
                    f"開催日時: {start_date.year}年"
                    f"{start_date.month}月{start_date.day}日\n\n"
                )
                raw_description = date_prefix + body_text.strip()

                events.append(
                    Event(
                        source_name=SOURCE_NAME,
                        source_id=f"taiwan_kyokai_{slug}",
                        source_url=url,
                        original_language="ja",
                        name_ja=raw_title,
                        raw_title=raw_title,
                        raw_description=raw_description,
                        category=["lecture"],
                        start_date=start_date,
                        end_date=fields["end_date"],
                        location_name=fields["location_name"],
                        location_address=fields["location_address"],
                        is_paid=fields["is_paid"],
                        price_info=fields["price_info"],
                    )
                )
                logger.info(
                    "[%s] ✓ %s | %s | %s",
                    SOURCE_NAME,
                    slug,
                    start_date.date(),
                    raw_title[:40],
                )

            browser.close()

        logger.info("[%s] Total events: %d", SOURCE_NAME, len(events))
        return events
