"""Scraper for TRANSIT STORE Event Collection (transitmagazinestore.com).

TRANSIT is a Japanese travel magazine. Their Shopify store occasionally hosts
book-launch talk events with a Taiwan focus, e.g.:
  - TRANSIT66 台湾特集発売記念トークイベント (2024-12-12)
  - TRANSIT Travel Guide Taiwan 発売記念トークイベント (2026-05-16)

Strategy:
  1. Fetch Shopify JSON API: /collections/event/products.json (paginated, 20/page)
  2. Filter products with Taiwan-related keywords in title or body_html
  3. Parse event date from body_html (日程：YYYY年M月D日)
  4. Include upcoming events (any ticket available) or recently ended (≤60 days ago)

Dedup key: transit_store_{product.handle}
  e.g. event-taiwanguide → transit_store_event-taiwanguide
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

COLLECTION_URL = "https://transitmagazinestore.com/collections/event/products.json"
PRODUCT_BASE_URL = "https://transitmagazinestore.com/products"

TAIWAN_KEYWORDS = [
    "台湾", "Taiwan", "TAIWAN", "台灣",
    "台北", "高雄", "台中", "台南", "台日", "日台",
]

# Match 日程：(any non-digit chars)(YYYY年M月D日)
_DATE_RE = re.compile(r"日程[：:][^\d]*(\d{4})年(\d{1,2})月(\d{1,2})日")
# Fallback: first plausible YYYY年M月D日 in text
_DATE_FALLBACK_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")

_VENUE_RE = re.compile(r"会場[：:]\s*([^\n\r<]+)")
_ADDRESS_RE = re.compile(r"住所[：:]\s*([^\n\r<]+)")

JST = timezone(timedelta(hours=9))


def _is_taiwan_related(title: str, body_html: str) -> bool:
    text = title + body_html
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _html_to_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(separator="\n")


def _parse_event_date(body_html: str) -> tuple[Optional[datetime], Optional[str]]:
    """Return (start_date, date_label) parsed from body_html."""
    text = _html_to_text(body_html)

    m = _DATE_RE.search(text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            dt = datetime(year, month, day, tzinfo=JST)
            return dt, f"{year}年{month}月{day}日"
        except ValueError:
            pass

    # Fallback: first YYYY年M月D日 with a plausible year
    for m2 in _DATE_FALLBACK_RE.finditer(text):
        year, month, day = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        if 2020 <= year <= 2030:
            try:
                dt = datetime(year, month, day, tzinfo=JST)
                return dt, f"{year}年{month}月{day}日"
            except ValueError:
                continue

    return None, None


def _parse_venue(body_html: str) -> tuple[Optional[str], Optional[str]]:
    """Return (location_name, location_address) from body_html text."""
    text = _html_to_text(body_html)
    name = None
    address = None

    vm = _VENUE_RE.search(text)
    if vm:
        name = vm.group(1).strip()

    am = _ADDRESS_RE.search(text)
    if am:
        address = am.group(1).strip()

    return name, address


def _has_available_ticket(product: dict) -> bool:
    return any(v.get("available", False) for v in product.get("variants", []))


def _min_price(product: dict) -> Optional[str]:
    prices = []
    for v in product.get("variants", []):
        p = v.get("price", "")
        if isinstance(p, str) and p.isdigit():
            prices.append(int(p))
        elif isinstance(p, (int, float)):
            prices.append(int(p))
    if prices:
        return f"¥{min(prices):,}〜"
    return None


class TransitStoreScraper(BaseScraper):
    """Scrapes Taiwan-related talk events from TRANSIT STORE (Shopify)."""

    SOURCE_NAME = "transit_store"

    def scrape(self) -> list[Event]:
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        })

        products = self._fetch_all_products(session)
        logger.info("transit_store: fetched %d total products", len(products))

        now = datetime.now(tz=JST)
        cutoff = now - timedelta(days=60)

        events: list[Event] = []
        for product in products:
            title = product.get("title", "")
            body_html = product.get("body_html", "")
            handle = product.get("handle", "")
            product_id = product.get("id", "")

            if not _is_taiwan_related(title, body_html):
                continue

            source_id = f"transit_store_{handle}" if handle else f"transit_store_{product_id}"
            source_url = f"{PRODUCT_BASE_URL}/{handle}"

            start_date, date_label = _parse_event_date(body_html)
            has_ticket = _has_available_ticket(product)

            # Skip past events with no available tickets
            if not has_ticket:
                if start_date is None or start_date < cutoff:
                    logger.debug("transit_store: skipping old sold-out event %s", handle)
                    continue

            venue_name, venue_address = _parse_venue(body_html)

            body_text = _html_to_text(body_html).strip()
            if date_label:
                raw_description = f"開催日時: {date_label}\n\n{body_text}"
            else:
                raw_description = body_text

            price_info = _min_price(product)

            event = Event(
                source_name="transit_store",
                source_id=source_id,
                source_url=source_url,
                original_language="ja",
                raw_title=title,
                raw_description=raw_description,
                start_date=start_date,
                end_date=start_date,
                location_name=venue_name,
                location_address=venue_address,
                is_paid=bool(price_info),
                price_info=price_info,
                category=["lecture", "taiwan_japan"],
                is_active=has_ticket,
            )
            events.append(event)
            logger.info("transit_store: Taiwan event found → %s (%s)", title, handle)

        logger.info("transit_store: %d Taiwan events collected", len(events))
        return events

    def _fetch_all_products(self, session: requests.Session) -> list[dict]:
        products: list[dict] = []
        page = 1
        while True:
            url = f"{COLLECTION_URL}?limit=20&page={page}"
            try:
                resp = session.get(url, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.error("transit_store: failed to fetch page %d: %s", page, exc)
                break

            batch = data.get("products", [])
            if not batch:
                break
            products.extend(batch)
            if len(batch) < 20:
                break
            page += 1
            time.sleep(0.5)

        return products
