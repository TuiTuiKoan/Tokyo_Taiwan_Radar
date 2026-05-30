"""Auto-generated scraper for artistcafe (Layer B / auto_scraper).

DO NOT EDIT BY HAND — regenerate via scraper.auto_scraper.spec_to_code.
"""

import re
import time
import logging
from datetime import datetime
from typing import Optional

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://artistcafe.jp"
SEARCH_URL = "https://artistcafe.jp/event/"
# NOTE: artistcafe.jp ignores ?keyword= query params — the site returns all events
# regardless of the keyword.  Taiwan relevance is therefore enforced in-scraper
# by _is_taiwan() after visiting each detail page.
MAX_PAGES = 5

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "台灣", "臺灣"]
CARD_SELECTOR = "li.article-list"
DETAIL_LINK_SELECTOR = "a.text-article-list-title"
FIELD_SELECTORS = {"title": "a.text-article-list-title", "date": "p.text-article-list-date"}
# Detail page content selector — <article> excludes header/nav; fall back to body
DETAIL_CONTENT_SELECTOR = "article"
DATE_REGEX = re.compile("(\\d{4})\\.(\\d{1,2})\\.(\\d{1,2})")
SOURCE_ID_PREFIX = "artistcafe_"
SOURCE_ID_URL_PATTERN = re.compile("/event/(\\d+)")

MAX_EVENTS = 200


def _is_taiwan(text: str) -> bool:
    """Return True if text contains at least one Taiwan keyword."""
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


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



class ArtistcafeScraper(BaseScraper):
    source_name = "artistcafe"


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
                    url = f"{SEARCH_URL}?page={page_num}"
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
                    # Do NOT early-exit on empty results — Taiwan keywords may appear in
                    # the detail page body even when the listing title has no keywords.
                    # Only stop when the listing page itself has no cards (count == 0 above).
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
                    try:
                        detail_page = context.new_page()
                        detail_page.goto(detail_url, timeout=30000)
                        detail_page.wait_for_load_state("networkidle", timeout=15000)
                        # Prefer <article> to exclude nav/header; fall back to body
                        if detail_page.locator(DETAIL_CONTENT_SELECTOR).count() > 0:
                            body_text = detail_page.locator(DETAIL_CONTENT_SELECTOR).first.inner_text(timeout=5000)
                        else:
                            body_text = detail_page.locator("body").inner_text(timeout=5000)
                        if body_text:
                            full_description = body_text.strip()[:2000]
                        detail_page.close()
                    except PWTimeout:
                        logger.warning("Detail page timeout: %s", detail_url)
                    except Exception as exc:
                        logger.debug("Detail page failed %s: %s", detail_url, exc)

                # Taiwan relevance gate — skip events with no Taiwan keywords
                check_text = (title or "") + " " + (full_description or "")
                if not _is_taiwan(check_text):
                    logger.debug("Skipping non-Taiwan event: %s", (title or "")[:60])
                    continue

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

