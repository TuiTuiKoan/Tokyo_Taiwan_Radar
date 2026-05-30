"""
Scraper for Taiwan-related books via 版元ドットコム (hanmoto.com).

Strategy:
  1. Search https://www.hanmoto.com/bd/search/keyword/台湾/sdate_desc
  2. Paginate via /order/desc/offset/{offset} (20 per page, max 3 pages = 60 items)
  3. Extract ISBN, title, publication date, publisher from book cards
  4. source_id: hanmoto_{isbn13} or hanmoto_{md5(detail_url)[:12]}
  5. start_date = end_date = 発売日 (UTC midnight)
  6. hanmoto already server-side filters by "台湾"; still apply client-side filter
     as a safety net against server-side regression
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from .base import BaseScraper, Event, dedup_events

logger = logging.getLogger(__name__)

SOURCE_NAME = "hanmoto"
BASE_URL = "https://www.hanmoto.com/bd/search/keyword/台湾/sdate_desc"
_MAX_PAGES = 3
_PAGE_SIZE = 20

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


# Candidate CSS selectors for book cards on hanmoto.com.
# The first selector that returns at least one element will be used.
_CARD_SELECTORS = [
    "div.booklist-item",
    "ul.bookList > li",
    "div.list-item",
    ".booklist .item",
]

# Candidate selectors for sub-fields within a card
_TITLE_SELECTORS  = ["h2", "h3", ".book-title", ".title", "a.ttl"]
_DATE_SELECTORS   = [".hdate", ".date", ".pubdate", "time", ".release"]
_PUB_SELECTORS    = [".publisher", ".pub", ".imprint", ".hanbaiten"]
_DESC_SELECTORS   = [".description", ".desc", ".catch", "p"]


def _first_text(card, selectors: list[str]) -> str:
    """Return inner_text from the first matching selector, or empty string."""
    for sel in selectors:
        el = card.query_selector(sel)
        if el is not None:
            txt = el.inner_text().strip()
            if txt:
                return txt
    return ""


class HanmotoScraper(BaseScraper):
    SOURCE_NAME = "hanmoto"

    def scrape(self) -> list[Event]:
        events: list[Event] = []
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

            for page_num in range(_MAX_PAGES):
                offset = page_num * _PAGE_SIZE
                if offset == 0:
                    url = BASE_URL
                else:
                    url = (
                        f"https://www.hanmoto.com/bd/search/keyword/台湾"
                        f"/order/desc/offset/{offset}"
                    )

                try:
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                except PWTimeout:
                    logger.warning("hanmoto: page timeout at offset %d", offset)
                    break
                except Exception as exc:
                    logger.warning("hanmoto: navigation error at offset %d: %s", offset, exc)
                    break

                # Detect card selector for this page
                cards = []
                for sel in _CARD_SELECTORS:
                    try:
                        page.wait_for_selector(sel, timeout=8000)
                        cards = page.query_selector_all(sel)
                        if cards:
                            logger.debug("hanmoto: using selector %r at offset %d", sel, offset)
                            break
                    except PWTimeout:
                        continue

                if not cards:
                    logger.warning(
                        "hanmoto: no book cards found at offset %d (page %d)",
                        offset, page_num + 1,
                    )
                    break

                for card in cards:
                    try:
                        title = _first_text(card, _TITLE_SELECTORS)
                        title = _strip_null(title) or ""

                        # Link / href
                        link_el = card.query_selector("a[href]")
                        href = link_el.get_attribute("href") if link_el is not None else ""
                        href = href or ""
                        if href and not href.startswith("http"):
                            href = f"https://www.hanmoto.com{href}"

                        # ISBN from data-isbn attribute or href path
                        isbn = card.get_attribute("data-isbn") or ""
                        if not (isbn and len(isbn) == 13 and isbn.isdigit()):
                            isbn = _extract_isbn_from_href(href) or ""

                        # source_id
                        if isbn and len(isbn) == 13 and isbn.isdigit():
                            source_id = f"hanmoto_{isbn}"
                        elif href:
                            source_id = f"hanmoto_{hashlib.md5(href.encode()).hexdigest()[:12]}"
                        else:
                            continue  # cannot build stable ID

                        # Client-side Taiwan filter
                        description = _first_text(card, _DESC_SELECTORS)
                        description = _strip_null(description) or ""
                        if not _is_taiwan(f"{title} {description}"):
                            continue

                        # Publication date
                        date_text = _first_text(card, _DATE_SELECTORS)
                        start_dt = _parse_date(date_text)

                        # Publisher (organizer per-book; organizer_type is always "media")
                        publisher = _first_text(card, _PUB_SELECTORS)
                        publisher = _strip_null(publisher) or None

                        source_url = _strip_null(href) or BASE_URL

                        events.append(Event(
                            source_name=SOURCE_NAME,
                            source_id=source_id,
                            source_url=source_url,
                            original_language="ja",
                            name_ja=_strip_null(title) or None,
                            raw_title=_strip_null(title) or None,
                            raw_description=_strip_null(description) or None,
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

                if len(cards) < _PAGE_SIZE:
                    break  # No more pages

            browser.close()

        result = dedup_events(events)
        logger.info("hanmoto: %d events after dedup", len(result))
        return result
