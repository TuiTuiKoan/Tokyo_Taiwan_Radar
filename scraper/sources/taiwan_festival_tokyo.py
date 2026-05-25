"""
Scraper for 台湾フェスティバル™TOKYO (taiwanfes.org).

This is an annual festival held in Ueno Park, Tokyo.

Strategy (in priority order):
  1. Fetch the homepage with Playwright
  2. PRIMARY: parse the body article (`section.p-entry__body`) containing the
     `《開催日時》YYYY年M月D日（曜）～D日（曜）HH:MM～HH:MM` block.
     This is where the organiser posts the canonical updated information.
  3. FALLBACK: parse the footer widget (`#text-7` 開催詳細) which carries a
     shorter `日時：…` line. The organiser sometimes forgets to update this
     widget after the main article is refreshed, so it is only a backup.
  4. Title comes from the widget (stable) or from the page <title>.
  5. source_id = "taiwanfes_{YYYY}" — one event per year, stable across runs.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

HOMEPAGE_URL = "https://taiwanfes.org/"
SOURCE_NAME = "taiwan_festival_tokyo"
VENUE = "上野恩賜公園・噴水広場"


def _extract_year_from_title(title: str) -> Optional[int]:
    """Extract 4-digit year from title string like '台湾フェスティバル™TOKYO2026'."""
    m = re.search(r'(20\d{2})', title)
    return int(m.group(1)) if m else None


def _parse_date_range(
    date_text: str, fallback_year: int
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse irregular date range text.

    Supported formats:
      "2026年7月9日（木）～12日（日）10:00～21:00（最終日19:00まで）"  # body article
      "2026年7月9日～8月12日"                                        # cross-month with year
      "6月25日～27日10時～21時、28日10時～19時"                      # widget fallback
      "7月9日（木）～12日（日）"                                     # widget fallback

    Returns naive datetimes (caller wraps in UTC).
    """
    if not date_text:
        return None, None

    # Priority: explicit year in text (body article format)
    m = re.search(
        r'(20\d{2})年(\d{1,2})月(\d{1,2})日'
        r'[^～]*?～'
        r'(?:(\d{1,2})月)?(\d{1,2})日',
        date_text,
    )
    if m:
        year = int(m.group(1))
        start_month = int(m.group(2))
        start_day = int(m.group(3))
        end_month = int(m.group(4)) if m.group(4) else start_month
        end_day = int(m.group(5))
        try:
            return datetime(year, start_month, start_day), datetime(year, end_month, end_day)
        except ValueError as e:
            logger.warning("Invalid date with year from %r: %s", date_text, e)
            return None, None

    # Fallback: legacy widget format (no year in text → use fallback_year)
    month_m = re.search(r'(\d{1,2})月', date_text)
    if not month_m:
        logger.warning("No month found in date text: %s", date_text)
        return None, None
    month = int(month_m.group(1))

    day_nums = re.findall(r'(\d{1,2})日', date_text)
    if not day_nums:
        logger.warning("No day numbers found in date text: %s", date_text)
        return None, None

    start_day = int(day_nums[0])
    end_day = int(day_nums[-1])

    try:
        return (
            datetime(fallback_year, month, start_day),
            datetime(fallback_year, month, end_day),
        )
    except ValueError as e:
        logger.warning("Invalid date from text %r: %s", date_text, e)
        return None, None


def _parse_body_article(page) -> Optional[dict]:
    """
    Parse the canonical event info from the homepage body article.

    Returns dict with keys: date_text, venue, price_info, is_paid, detail_text.
    Returns None if the article cannot be found.
    """
    sections = page.query_selector_all("section.p-entry__body, section.p-cb__item")
    target_text: Optional[str] = None
    for sec in sections:
        try:
            txt = sec.inner_text() or ""
        except Exception:
            continue
        if "《開催日時》" in txt:
            target_text = txt
            break

    if not target_text:
        return None

    # Date: between 《開催日時》 and next 《…》 or end of line
    date_m = re.search(r'《開催日時》\s*([^\n《]+)', target_text)
    date_text = date_m.group(1).strip() if date_m else ""

    # Venue: between 《開催場所》 and end of line
    venue_m = re.search(r'《開催場所》\s*([^\n《]+)', target_text)
    venue = venue_m.group(1).strip() if venue_m else VENUE

    # Price block: between 《SDGs体験参加費》 (or 《入場料》/《参加費》) and 《主催》
    price_m = re.search(
        r'《(?:SDGs体験参加費|入場料|参加費)》\s*(.+?)(?=《(?:主[\s　]*催|主催)》)',
        target_text,
        flags=re.DOTALL,
    )
    price_info: Optional[str] = None
    is_paid = True
    if price_m:
        price_info = re.sub(r'\n{2,}', '\n', price_m.group(1).strip())
        if "無料" in price_info and "円" not in price_info:
            is_paid = False

    if not date_text:
        return None

    return {
        "date_text": date_text,
        "venue": venue,
        "price_info": price_info,
        "is_paid": is_paid,
        "detail_text": target_text.strip(),
    }


def _parse_widget(page) -> Optional[dict]:
    """
    Parse the footer 開催詳細 widget (#text-7) as fallback.

    Returns dict with keys: title, date_text, venue, price_info, is_paid, detail_text.
    Returns None if the widget is missing or malformed.
    """
    widget = page.query_selector("#text-7")
    if not widget:
        h2s = page.query_selector_all("h2")
        for h2 in h2s:
            if "開催詳細" in (h2.inner_text() or ""):
                widget = h2.evaluate_handle(
                    'el => el.closest("section, div, article") || el.parentElement'
                ).as_element()
                break

    if not widget:
        return None

    paragraphs = widget.query_selector_all("p")
    if len(paragraphs) < 2:
        return None

    title = paragraphs[0].inner_text().strip()
    detail_text = paragraphs[1].inner_text().strip()

    venue = VENUE
    date_text = ""
    for line in detail_text.split("\n"):
        line = line.strip()
        if line.startswith("会場："):
            venue = line.replace("会場：", "").strip()
        elif line.startswith("日時："):
            date_text = line.replace("日時：", "").strip()

    price_info: Optional[str] = None
    is_paid = True
    for para in paragraphs[2:]:
        t = para.inner_text().strip()
        if "円" in t or "無料" in t or "入場" in t:
            price_info = t
            if "無料" in t and "円" not in t:
                is_paid = False
            break

    return {
        "title": title,
        "date_text": date_text,
        "venue": venue,
        "price_info": price_info,
        "is_paid": is_paid,
        "detail_text": detail_text,
    }


class TaiwanFestivalTokyoScraper(BaseScraper):
    """Scrapes the annual 台湾フェスティバル™TOKYO event from taiwanfes.org."""

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
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

            try:
                page.goto(HOMEPAGE_URL, wait_until="networkidle", timeout=30_000)
            except PWTimeout:
                page.goto(HOMEPAGE_URL, wait_until="domcontentloaded", timeout=30_000)

            event = self._parse_event(page)
            browser.close()

        return [event] if event else []

    def _parse_event(self, page) -> Optional[Event]:
        widget = _parse_widget(page)
        body = _parse_body_article(page)

        # Title source: widget first (stable across years), then page <title>.
        title: Optional[str] = None
        if widget and widget.get("title"):
            title = widget["title"]
        if not title:
            try:
                title = (page.title() or "").strip() or None
            except Exception:
                title = None
        if not title:
            logger.error("Could not determine event title on %s", HOMEPAGE_URL)
            return None

        year = _extract_year_from_title(title) or datetime.now().year
        source_id = f"taiwanfes_{year}"

        # Prefer body article (canonical, updated). Fall back to widget.
        chosen = body or widget
        if chosen is None:
            logger.error("Could not find event details on %s", HOMEPAGE_URL)
            return None

        # If both succeed and dates disagree, warn — body wins.
        if body and widget and body.get("date_text") and widget.get("date_text"):
            if body["date_text"] != widget["date_text"]:
                logger.warning(
                    "body article vs widget date mismatch: body=%r widget=%r — using body",
                    body["date_text"],
                    widget["date_text"],
                )

        date_text = chosen.get("date_text") or ""
        start_date, end_date = _parse_date_range(date_text, year)
        if start_date is None:
            logger.error("Could not parse start_date from %r", date_text)
            return None

        # Wrap to UTC midnight (Scraper Date Timezone Guard)
        start_date = datetime(
            start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc
        )
        if end_date:
            end_date = datetime(
                end_date.year, end_date.month, end_date.day, tzinfo=timezone.utc
            )

        venue = chosen.get("venue") or VENUE
        detail_text = chosen.get("detail_text") or ""
        price_info = chosen.get("price_info")
        is_paid = chosen.get("is_paid", True)

        # Build raw_description
        header = f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
        if end_date and end_date != start_date:
            header += f" ～ {end_date.strftime('%Y年%m月%d日')}"
        raw_description = f"{header}\n\n{detail_text}"

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=HOMEPAGE_URL,
            official_url=HOMEPAGE_URL,
            original_language="ja",
            name_ja=title,
            description_ja=detail_text or None,
            raw_title=title,
            raw_description=raw_description,
            start_date=start_date,
            end_date=end_date,
            location_name=venue,
            location_address="東京都台東区上野公園",
            is_paid=is_paid,
            price_info=price_info,
            category=["lifestyle_food", "performing_arts"],
        )
