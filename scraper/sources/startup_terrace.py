"""Scraper for Startup Terrace (startupterrace.tw).

Taiwan Startup Terrace organizes international outbound programs, including
Japan missions (SusHi Tech Tokyo, etc.). This scraper fetches the News Room
listing and filters for Japan-related articles.

Note: The listing does not support server-side keyword filtering;
      Japan relevance check is applied client-side on detail page text.
"""

import re
import logging
from datetime import datetime
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.startupterrace.tw"
# Listing URL — pagination appended as &page=N&PageSize=9
LISTING_URL = f"{BASE_URL}/en/News_Card2.aspx?n=1678&sms=11665"

CARD_SELECTOR = ".area-figure"
SOURCE_ID_PREFIX = "startup_terrace_"
SOURCE_ID_URL_PATTERN = re.compile(r"[?&]s=(\d+)")
DATE_REGEX = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

MAX_EVENTS = 50
MAX_PAGES = 3  # 9 cards/page x 3 = covers ~27 latest articles

# Japan-related keywords -- must appear in title or detail page body
_JAPAN_KW = [
    "Japan", "日本", "Tokyo", "東京", "SusHi Tech",
    "大阪", "Osaka", "福岡", "Fukuoka",
    "日台", "台日",
]


def _is_japan_relevant(title: str, body: str) -> bool:
    """True only if the article mentions Japan-related terms."""
    combined = (title or "") + " " + (body or "")[:3000]
    return any(kw in combined for kw in _JAPAN_KW)


def _parse_date(text: str) -> Optional[datetime]:
    if not text:
        return None
    m = DATE_REGEX.search(text)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _extract_source_id(url: str) -> Optional[str]:
    m = SOURCE_ID_URL_PATTERN.search(url or "")
    return f"{SOURCE_ID_PREFIX}{m.group(1)}" if m else None


def _make_absolute(href: str) -> str:
    """Convert relative href to absolute URL."""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return f"{BASE_URL}/en/{href.lstrip('/')}"


class StartupTerraceScraper(BaseScraper):
    source_name = "startup_terrace"

    def scrape(self):  # noqa: C901
        events: list[Event] = []
        seen_ids: set[str] = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            list_page = context.new_page()

            try:
                for page_num in range(1, MAX_PAGES + 1):
                    if len(events) >= MAX_EVENTS:
                        break

                    url = f"{LISTING_URL}&page={page_num}&PageSize=9"
                    logger.info("StartupTerrace: fetching listing page %d", page_num)
                    try:
                        list_page.goto(url, timeout=30000)
                        list_page.wait_for_load_state("domcontentloaded", timeout=15000)
                    except PWTimeout:
                        logger.warning("StartupTerrace: listing page %d timeout", page_num)
                        break

                    cards = list_page.locator(CARD_SELECTOR)
                    count = cards.count()
                    if count == 0:
                        logger.info("StartupTerrace: no cards on page %d; stopping", page_num)
                        break

                    logger.info("StartupTerrace: page %d -- %d cards", page_num, count)

                    for i in range(count):
                        if len(events) >= MAX_EVENTS:
                            break
                        card = cards.nth(i)
                        try:
                            # Title stored in the `title` attribute of a.div
                            a_el = card.locator("a.div").first
                            if a_el.count() == 0:
                                continue
                            title = a_el.get_attribute("title", timeout=3000)
                            href = a_el.get_attribute("href", timeout=3000)

                            # Date is the text of i.mark
                            date_el = card.locator("i.mark").first
                            date_text = (
                                date_el.inner_text(timeout=3000)
                                if date_el.count() > 0
                                else None
                            )

                            if not title or not date_text:
                                continue

                            start_date = _parse_date(date_text)
                            if not start_date:
                                continue

                            detail_url = _make_absolute(href)
                            source_id = _extract_source_id(detail_url)
                            if not source_id or source_id in seen_ids:
                                continue

                            # Fetch detail page for Japan relevance + description
                            body_text = ""
                            if detail_url:
                                try:
                                    detail_page = context.new_page()
                                    detail_page.goto(detail_url, timeout=25000)
                                    detail_page.wait_for_load_state(
                                        "domcontentloaded", timeout=10000
                                    )
                                    body_text = (
                                        detail_page.locator("body").inner_text(timeout=5000) or ""
                                    )
                                    body_text = body_text.strip()[:3000]
                                    detail_page.close()
                                except PWTimeout:
                                    logger.warning(
                                        "StartupTerrace: detail timeout %s", detail_url
                                    )
                                except Exception as exc:
                                    logger.debug(
                                        "StartupTerrace: detail failed %s: %s", detail_url, exc
                                    )

                            if not _is_japan_relevant(title, body_text):
                                logger.debug(
                                    "StartupTerrace: skip (not Japan-related): %s", title[:60]
                                )
                                continue

                            seen_ids.add(source_id)
                            events.append(
                                Event(
                                    source_name=self.source_name,
                                    source_id=source_id,
                                    source_url=detail_url or LISTING_URL,
                                    original_language="en",
                                    name_ja=title,
                                    raw_title=title,
                                    raw_description=body_text or None,
                                    start_date=start_date,
                                )
                            )
                        except Exception as exc:
                            logger.warning("StartupTerrace: card %d failed: %s", i, exc)
                            continue

            finally:
                context.close()
                browser.close()

        logger.info("startup_terrace: collected %d Japan-related events", len(events))
        return events
