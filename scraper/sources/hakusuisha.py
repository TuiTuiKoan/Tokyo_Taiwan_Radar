"""Auto-generated scraper for hakusuisha (Layer B / auto_scraper).

DO NOT EDIT BY HAND — regenerate via scraper.auto_scraper.spec_to_code.
"""

import re
import time
import logging
from datetime import datetime
from typing import Optional
import requests as _requests

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.hakusuisha.co.jp"
SEARCH_URL = "https://www.hakusuisha.co.jp/news/nc2161.html"
SEARCH_KEYWORD = "%E5%8F%B0%E6%B9%BE"
MAX_PAGES = 5
CARD_SELECTOR = "div.sectionType1"
DETAIL_LINK_SELECTOR = "h3.titleType2 a[href*='/news/n']"
FIELD_SELECTORS = {"title": "h3.titleType2 a[href*='/news/n']", "date": "h3.titleType2 span.note"}
DATE_REGEX = re.compile("(\\d{4})\\.(\\d{2})\\.(\\d{2})")
SOURCE_ID_PREFIX = "hakusuisha_"
SOURCE_ID_URL_PATTERN = re.compile("/news/n(\\d+).html")

MAX_EVENTS = 200


def _parse_date(text):
    if not text:
        return None
    m = DATE_REGEX.search(text)
    if not m:
        return None
    raw = m.group(0)
    for fmt in ("%Y.%m.%d", "%Y/%m/%d", "%Y-%m-%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _extract_source_id(url):
    m = SOURCE_ID_URL_PATTERN.search(url or "")
    return f"{SOURCE_ID_PREFIX}{m.group(1)}" if m else None


def _safe_text(card, selector):
    if not selector:
        return None
    try:
        loc = card.locator(selector).first
        if loc.count() == 0:
            return None
        return (loc.inner_text(timeout=5000) or "").strip() or None
    except PWTimeout:
        return None
    except Exception as exc:
        logger.debug("selector %s failed: %s", selector, exc)
        return None


def _safe_attr(card, selector, attr):
    if not selector:
        return None
    try:
        loc = card.locator(selector).first
        if loc.count() == 0:
            return None
        return loc.get_attribute(attr, timeout=5000)
    except PWTimeout:
        return None
    except Exception as exc:
        logger.debug("attr %s on %s failed: %s", attr, selector, exc)
        return None


def _fetch_detail_text_fallback(url: str) -> str | None:
    """HTTP fallback for detail page body text when Playwright times out.

    Uses standard requests.get() which is sufficient for hakusuisha's
    static HTML pages. Returns up to 2000 chars of plain text.
    """
    try:
        resp = _requests.get(url, timeout=15, headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })
        resp.raise_for_status()
        # Force apparent encoding detection — hakusuisha serves UTF-8 but
        # requests defaults to ISO-8859-1 when no charset header is present.
        resp.encoding = resp.apparent_encoding or "utf-8"
        from html.parser import HTMLParser as _HTMLParser
        class _T(_HTMLParser):
            _SKIP = frozenset({"script", "style", "nav", "header", "footer"})
            def __init__(self) -> None:
                super().__init__()
                self._chunks: list[str] = []
                self._skip: int = 0
            def handle_starttag(self, tag: str, attrs: list) -> None:
                if tag in self._SKIP:
                    self._skip += 1
            def handle_endtag(self, tag: str) -> None:
                if tag in self._SKIP and self._skip > 0:
                    self._skip -= 1
            def handle_data(self, d: str) -> None:
                if self._skip == 0:
                    d = d.strip()
                    if d:
                        self._chunks.append(d)
        p = _T()
        p.feed(resp.text)
        text = "\n".join(p._chunks)
        return text[:4000] if text else None
    except Exception as exc:
        logger.debug("HTTP fallback failed for %s: %s", url, exc)
        return None


class HakusuishaScraper(BaseScraper):
    source_name = "hakusuisha"


    def scrape(self):
        events = []
        seen_ids = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            try:
                for page_num in range(1, MAX_PAGES + 1):
                    if len(events) >= MAX_EVENTS:
                        logger.info("Hit MAX_EVENTS cap (%d); stopping.", MAX_EVENTS)
                        break
                    url = f"{SEARCH_URL}?keyword={SEARCH_KEYWORD}&page={page_num}"
                    logger.info("Fetching listing page %d: %s", page_num, url)
                    try:
                        page.goto(url, timeout=30000)
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except PWTimeout:
                        logger.warning("Timeout loading %s; skipping page", url)
                        continue

                    cards = page.locator(CARD_SELECTOR)
                    count = cards.count()
                    if count == 0:
                        logger.info("No cards on page %d; end of pagination", page_num)
                        break

                    page_events = self._extract_cards(page, context, cards, count, seen_ids)
                    if not page_events:
                        logger.info("Page %d had cards but yielded 0 events; stopping", page_num)
                        break
                    events.extend(page_events)
                    if len(events) >= MAX_EVENTS:
                        events = events[:MAX_EVENTS]
                        break
            finally:
                context.close()
                browser.close()

        logger.info("%s: collected %d events", self.source_name, len(events))
        return events

    def _extract_cards(self, page, context, cards, count, seen_ids):
        out = []
        for i in range(count):
            card = cards.nth(i)
            try:
                title = _safe_text(card, FIELD_SELECTORS["title"])
                date_text = _safe_text(card, FIELD_SELECTORS["date"])
                description = None
                if "description" in FIELD_SELECTORS:
                    description = _safe_text(card, FIELD_SELECTORS["description"])
                location = None
                if "location" in FIELD_SELECTORS:
                    location = _safe_text(card, FIELD_SELECTORS["location"])

                detail_url = None
                if DETAIL_LINK_SELECTOR:
                    detail_url = _safe_attr(card, DETAIL_LINK_SELECTOR, "href")
                # Fallback: when detail_link_selector is empty, grab the first <a href>
                # inside the card. Most listing cards wrap the event in a single anchor.
                if not detail_url:
                    detail_url = _safe_attr(card, "a", "href")
                if detail_url and detail_url.startswith("/"):
                    detail_url = f"{BASE_URL}{detail_url}"
                elif detail_url and not detail_url.startswith("http"):
                    # Resolve relative paths (e.g. "../news/n123.html") against the listing page URL
                    from urllib.parse import urljoin
                    detail_url = urljoin(page.url, detail_url)

                source_url = detail_url or page.url
                source_id = _extract_source_id(source_url)
                if not source_id or source_id in seen_ids:
                    continue
                if not title or not date_text:
                    continue

                start_date = _parse_date(date_text)
                if not start_date:
                    continue

                full_description = description
                if detail_url:
                    _pw_success = False
                    try:
                        detail_page = context.new_page()
                        detail_page.goto(detail_url, timeout=30000)
                        detail_page.wait_for_load_state("networkidle", timeout=15000)
                        body_text = detail_page.locator("body").inner_text(timeout=5000)
                        if body_text:
                            full_description = body_text.strip()[:4000]
                            _pw_success = True
                        detail_page.close()
                    except PWTimeout:
                        logger.warning("Detail page timeout: %s — trying HTTP fallback", detail_url)
                        try:
                            detail_page.close()
                        except Exception:
                            pass
                    except Exception as exc:
                        logger.debug("Detail page failed %s: %s", detail_url, exc)
                        try:
                            detail_page.close()
                        except Exception:
                            pass
                    if not _pw_success and detail_url:
                        fallback_text = _fetch_detail_text_fallback(detail_url)
                        if fallback_text:
                            full_description = fallback_text
                            logger.debug("HTTP fallback succeeded for %s (%d chars)", detail_url, len(fallback_text))

                seen_ids.add(source_id)
                out.append(Event(
                    source_name=self.source_name,
                    source_id=source_id,
                    source_url=source_url,
                    original_language="ja",
                    name_ja=title,
                    description_ja=full_description,
                    start_date=start_date,
                    location_name=location,
                    raw_title=title,
                    raw_description=full_description,
                ))
            except Exception as exc:
                logger.warning("Failed to parse card %d: %s", i, exc)
                continue
        return out

