"""
Scraper for 台湾フェスティバル™TOKYO (taiwanfes.org).

This is an annual festival held in Ueno Park, Tokyo.
Event details are published on the homepage in the footer widget (#text-7).

Strategy:
  1. Fetch the homepage with Playwright
  2. Extract the 開催詳細 widget (#text-7): title, venue, date string
  3. Parse dates: "6月25日～27日10時～21時、28日10時～19時" → start=Jun 25, end=Jun 28
  4. Year is extracted from the event title (e.g. "TOKYO2026" → 2026)
  5. source_id = "taiwanfes_{YYYY}" — one event per year, stable across runs
"""

import re
import logging
from datetime import datetime
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


def _parse_date_range(date_text: str, year: int) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse iregular date range text like:
      "6月25日～27日10時～21時、28日10時～19時"
      "7月9日（木）～12日（日）"
      "7月9日～12日"

    Returns (start_date, end_date) with the given year applied.
    """
    if not date_text:
        return None, None

    # Extract first month reference
    month_m = re.search(r'(\d{1,2})月', date_text)
    if not month_m:
        logger.warning("No month found in date text: %s", date_text)
        return None, None
    month = int(month_m.group(1))

    # Extract all day numbers in order
    day_nums = re.findall(r'(\d{1,2})日', date_text)
    if not day_nums:
        logger.warning("No day numbers found in date text: %s", date_text)
        return None, None

    start_day = int(day_nums[0])
    end_day = int(day_nums[-1])

    try:
        start_date = datetime(year, month, start_day)
        end_date = datetime(year, month, end_day)
    except ValueError as e:
        logger.warning("Invalid date from text %r: %s", date_text, e)
        return None, None

    return start_date, end_date


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
        # Locate the 開催詳細 footer widget by id
        widget = page.query_selector("#text-7")
        if not widget:
            # Fallback: find by heading text
            h2s = page.query_selector_all("h2")
            for h2 in h2s:
                if "開催詳細" in (h2.inner_text() or ""):
                    widget = h2.evaluate_handle(
                        'el => el.closest("section, div, article") || el.parentElement'
                    ).as_element()
                    break

        if not widget:
            logger.error("Could not find 開催詳細 widget on %s", HOMEPAGE_URL)
            return None

        paragraphs = widget.query_selector_all("p")
        if len(paragraphs) < 2:
            logger.error("Unexpected widget structure — fewer than 2 <p> elements")
            return None

        title = paragraphs[0].inner_text().strip()
        detail_text = paragraphs[1].inner_text().strip()

        # Extract year from title
        year = _extract_year_from_title(title)
        if not year:
            # Fallback: use current year
            year = datetime.now().year
            logger.warning("No year in title %r, falling back to %d", title, year)

        source_id = f"taiwanfes_{year}"

        # Parse venue and date from detail_text
        # Format: "会場：…\n日時：…"
        venue = VENUE  # default
        date_text = ""

        for line in detail_text.split("\n"):
            line = line.strip()
            if line.startswith("会場："):
                venue = line.replace("会場：", "").strip()
            elif line.startswith("日時："):
                date_text = line.replace("日時：", "").strip()

        start_date, end_date = _parse_date_range(date_text, year)
        if start_date is None:
            logger.error("Could not parse start_date from %r", date_text)
            return None

        # Build raw_description from widget text
        raw_description_parts = [f"開催日時: {start_date.strftime('%Y年%m月%d日')}"]
        if end_date and end_date != start_date:
            raw_description_parts[0] += f" ～ {end_date.strftime('%Y年%m月%d日')}"
        raw_description_parts.append("")
        raw_description_parts.append(detail_text)

        # Admission: check remaining paragraphs for price info
        price_info = None
        is_paid = True  # festival is paid by default
        for para in paragraphs[2:]:
            t = para.inner_text().strip()
            if "円" in t or "無料" in t or "入場" in t:
                price_info = t
                if "無料" in t and "円" not in t:
                    is_paid = False
                break

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=HOMEPAGE_URL,
            original_language="ja",
            name_ja=title,
            description_ja=detail_text or None,
            raw_title=title,
            raw_description="\n".join(raw_description_parts),
            start_date=start_date,
            end_date=end_date,
            location_name=venue,
            location_address="東京都台東区上野公園",
            is_paid=is_paid,
            price_info=price_info,
            category=["lifestyle_food", "performing_arts"],
        )
