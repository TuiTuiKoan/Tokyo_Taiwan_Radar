"""
Scraper for Taiwan-related books via 版元ドットコム (hanmoto.com).

Strategy:
    1. Load the current search UI URL for keyword=台湾 sorted by release date desc
    2. Paginate by clicking page buttons in the JS search UI (20 per page, max 3 pages)
    3. Extract ISBN, title, release date, and publisher from .bd-booklist-item-book cards
    4. source_id: hanmoto_{isbn13} or hanmoto_{md5(detail_url)[:12]}
    5. start_date = end_date = 発売日 (UTC midnight)
    6. Stop once release dates fall outside the rolling 365-day window
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from .base import BaseScraper, Event, dedup_events, is_jpro_placeholder_date

logger = logging.getLogger(__name__)

SOURCE_NAME = "hanmoto"
BASE_URL = "https://www.hanmoto.com/bd/search/top?keyword=%E5%8F%B0%E6%B9%BE&sdate_desc=1"
_MAX_PAGES = 3
_PAGE_SIZE = 20
_CUTOFF_DAYS = 365

TAIWAN_KEYWORDS = [
    "台湾", "臺灣", "Taiwan", "台北", "台南", "台中", "高雄",
    "客家", "原住民", "原住民族", "閩南", "ホーロー", "台語",
    "minnan", "hakka",
]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _strip_null(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return s.replace("\x00", "")


def _parse_date(text: str) -> Optional[datetime]:
    """Parse '2024年03月15日' or '2024-03-15' to UTC midnight datetime."""
    text = text.strip()
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        try:
            return datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        try:
            return datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass
    return None


def _extract_isbn_from_href(href: str) -> Optional[str]:
    """Extract 13-digit ISBN from a URL path like /isbn/9784123456789."""
    m = re.search(r"/isbn/(\d{13})", href)
    if m:
        return m.group(1)
    return None


# CSS selector for book cards (confirmed 2026-06)
_CARD_SEL = ".bd-booklist-item-book"


class HanmotoScraper(BaseScraper):
    SOURCE_NAME = "hanmoto"

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=_CUTOFF_DAYS)).date()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page.set_extra_http_headers({"Accept-Language": "ja,en-US;q=0.9"})

            for page_num in range(1, _MAX_PAGES + 1):
                if page_num == 1:
                    try:
                        page.goto(BASE_URL, timeout=30000, wait_until="domcontentloaded")
                    except PWTimeout:
                        logger.warning("hanmoto: initial page timeout")
                        break
                    except Exception as exc:
                        logger.warning("hanmoto: initial navigation error: %s", exc)
                        break
                else:
                    btn = page.query_selector(f".page-item-page{page_num} button")
                    if btn is None:
                        logger.debug("hanmoto: no page-%d button, stopping", page_num)
                        break
                    btn.click()
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except PWTimeout:
                        pass  # proceed with whatever loaded

                try:
                    page.wait_for_selector(_CARD_SEL, timeout=10000)
                except PWTimeout:
                    logger.warning("hanmoto: no book cards on page %d", page_num)
                    break

                cards = page.query_selector_all(_CARD_SEL)
                if not cards:
                    break

                page_exhausted = False
                for card in cards:
                    try:
                        # Title
                        title_el = card.query_selector('[data-content-name="title"]')
                        title = title_el.inner_text().strip() if title_el is not None else ""
                        title = _strip_null(title) or ""

                        # Link and ISBN
                        link_el = card.query_selector('a[href*="/bd/isbn/"]')
                        href = link_el.get_attribute("href") if link_el is not None else ""
                        href = href or ""
                        if href and not href.startswith("http"):
                            href = f"https://www.hanmoto.com{href}"

                        isbn = _extract_isbn_from_href(href) or ""

                        # source_id
                        if isbn and len(isbn) == 13 and isbn.isdigit():
                            source_id = f"hanmoto_{isbn}"
                        elif href:
                            source_id = f"hanmoto_{hashlib.md5(href.encode()).hexdigest()[:12]}"
                        else:
                            continue

                        # Client-side Taiwan filter (title only; server already filtered)
                        if not _is_taiwan(title):
                            continue

                        # Publication date — find span containing '発売' + year pattern
                        date_text = ""
                        for span in card.query_selector_all("span"):
                            txt = span.inner_text()
                            if "発売" in txt and re.search(r"\d{4}年", txt):
                                date_text = txt
                                break
                        start_dt = _parse_date(date_text)

                        # Recency cutoff: since sorted by release date desc,
                        # stop pagination once we hit books older than _CUTOFF_DAYS
                        if start_dt is not None and start_dt.date() < cutoff_date:
                            page_exhausted = True
                            break

                        if is_jpro_placeholder_date(start_dt):
                            start_dt = None
                        # Publisher
                        pub_el = card.query_selector('[data-content-name="imprint"]')
                        publisher = pub_el.inner_text().strip() if pub_el is not None else None
                        publisher = _strip_null(publisher) or None

                        source_url = _strip_null(href) or BASE_URL

                        events.append(Event(
                            source_name=SOURCE_NAME,
                            source_id=source_id,
                            source_url=source_url,
                            original_language="ja",
                            name_ja=_strip_null(title) or None,
                            raw_title=_strip_null(title) or None,
                            raw_description=None,
                            start_date=start_dt,
                            end_date=start_dt,
                            location_name=None,
                            location_address=None,
                            location_prefectures=[],
                            category=["books_media"],
                            event_form=["other"],
                            name_ja_locked=True,
                            organizer=publisher,
                            organizer_type=["media"],
                        ))
                    except Exception as exc:
                        logger.debug("hanmoto: card parse error: %s", exc)
                        continue

                if page_exhausted or len(cards) < _PAGE_SIZE:
                    break

            browser.close()

        result = dedup_events(events)
        logger.info("hanmoto: %d events after dedup", len(result))
        return result
