"""
Scraper for eplus.jp (イープラス) — major Japanese ticket platform.

Strategy:
  1. Load search page: https://eplus.jp/sf/search/?keyword=台湾
  2. Click 「もっと見る」 if present to reveal all results
  3. Parse each a[href*='/sf/detail/'] card for: date, title, venue, prefecture, start_time
  4. source_id = "eplus_{event_code}-{session_code}" derived from the detail URL path
  5. Accept all Japan-wide results; let annotator.py filter Taiwan relevance

Coverage: concerts, traditional performing arts (国光劇団), orchestras,
          rock/indie bands from Taiwan.
"""

import logging
import re
from datetime import datetime
from typing import Optional

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://eplus.jp"
SEARCH_URL = f"{BASE_URL}/sf/search/?keyword=%E5%8F%B0%E6%B9%BE"  # 台湾

# How long to wait for JS after clicking load-more
_LOAD_MORE_WAIT_MS = 3000

# Regex patterns
_DATE_RE = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")
_TIME_RE = re.compile(r"開演[：:]\s*(\d{1,2}):(\d{2})")


def _parse_card(link_el) -> Optional[dict]:
    """Extract structured data from a single event card <a> element."""
    href = link_el.get_attribute("href") or ""
    if "/sf/detail/" not in href:
        return None

    # source_id: take path segment after /sf/detail/, strip query params
    code = href.split("/sf/detail/")[1].split("?")[0]

    card_text = link_el.inner_text()
    lines = [l.strip() for l in card_text.splitlines() if l.strip()]

    date_str = ""
    title = ""
    venue_full = ""  # e.g. "東京国際フォーラム ホールC（東京都）"
    time_str = ""

    for line in lines:
        if not date_str and _DATE_RE.match(line):
            date_str = line
        elif line.startswith("開演") or line.startswith("開場"):
            time_str = line
        elif "（" in line and "）" in line and re.search(r"[都道府県]）", line):
            venue_full = line
        elif line not in ("先着", "抽選", "受付終了", "予定枚数終了", "受付中",
                          "受付待ち", "一般", "", "オンライン"):
            # Skip secondary date strings (e.g. "2026/5/17(日)" in multi-day events)
            if not title and not _DATE_RE.match(line):
                title = line

    if not date_str or not title:
        return None

    # Parse start datetime
    dm = _DATE_RE.match(date_str)
    year, month, day = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
    tm = _TIME_RE.search(time_str)
    if tm:
        start_dt = datetime(year, month, day, int(tm.group(1)), int(tm.group(2)))
    else:
        start_dt = datetime(year, month, day)

    # Extract venue name and prefecture from "会場名（都道府県）"
    venue_m = re.match(r"(.+?)（(.+?)）", venue_full)
    location_name = venue_m.group(1).strip() if venue_m else venue_full or None
    prefecture = venue_m.group(2).strip() if venue_m else None

    source_url = f"{BASE_URL}/sf/detail/{code}"

    return {
        "code": code,
        "title": title,
        "start_dt": start_dt,
        "location_name": location_name,
        "location_address": prefecture,  # prefecture as address fallback
        "source_url": source_url,
        "card_text": card_text,
        "time_str": time_str,
    }


class EplusScraper(BaseScraper):
    """Scrapes Taiwan-related events from eplus.jp via Playwright."""

    SOURCE_NAME = "eplus"

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        seen_codes: set[str] = set()

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0 Safari/537.36"
                )
            )

            try:
                page.goto(SEARCH_URL, wait_until="networkidle", timeout=30000)
            except PWTimeout:
                page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30000)

            # Click 「もっと見る」 if present to load all results
            more_btn = page.query_selector("button:has-text('もっと見る')")
            if more_btn:
                more_btn.click()
                page.wait_for_timeout(_LOAD_MORE_WAIT_MS)
                logger.info("eplus: clicked 'もっと見る' — loading all results")

            link_els = page.query_selector_all("a[href*='/sf/detail/']")
            logger.info("eplus: found %d event cards", len(link_els))

            for el in link_els:
                data = _parse_card(el)
                if data is None:
                    continue

                code = data["code"]
                if code in seen_codes:
                    continue
                seen_codes.add(code)

                start_dt: datetime = data["start_dt"]
                date_prefix = f"開催日時: {start_dt.strftime('%Y年%m月%d日')}\n\n"
                raw_description = date_prefix + data["card_text"]

                events.append(
                    Event(
                        source_name=self.SOURCE_NAME,
                        source_id=f"eplus_{code}",
                        source_url=data["source_url"],
                        original_language="ja",
                        name_ja=data["title"],
                        raw_title=data["title"],
                        raw_description=raw_description,
                        start_date=start_dt,
                        end_date=start_dt,
                        location_name=data["location_name"],
                        location_address=data["location_address"],
                        category=["performing_arts"],
                        is_paid=True,
                    )
                )

            browser.close()

        logger.info("eplus: %d events scraped (Japan-wide)", len(events))
        return events
