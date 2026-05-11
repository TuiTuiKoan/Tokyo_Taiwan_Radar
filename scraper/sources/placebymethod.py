"""Scraper for (PLACE) by method (placebymethod.com).

A craft/design gallery in Shibuya, Tokyo.
Taiwan-related exhibitions appear roughly once per year.

Source URL  : https://placebymethod.com/pages/contact
Platform    : Shopify static HTML — no JS rendering required
source_name : placebymethod
source_id   : placebymethod_{slug}

Strategy:
  1. Fetch the exhibitions listing page (https://placebymethod.com/pages/contact)
  2. Collect all /pages/{slug} links (deduplicated, skip nav pages)
  3. For each link, fetch the individual page
  4. Filter by Taiwan keywords in the full page text
  5. For Taiwan-related pages, extract date/venue/description via regex
     on the "会期：YYYY年MM月DD日（曜）～MM月DD日（曜）" structured block
  6. Skip exhibitions whose end_date is older than LOOKBACK_DAYS

Venue (fixed):
  location_name    : (PLACE) by method
  location_address : 〒150-0011 東京都渋谷区東1-3-1 カミニート14号

Taiwan keywords: 台湾, 台灣, Taiwan, 台南, 台北, 高雄
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "placebymethod"

_LISTING_URL = "https://placebymethod.com/pages/contact"

# Navigation / non-exhibition pages to skip
_SKIP_SLUGS = {"about-us", "acces", "policy", "rental", "home", "contact"}

_TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "台南", "台北", "高雄"]

# Include exhibitions whose end_date is within this many days in the past
_LOOKBACK_DAYS = 365

_VENUE_NAME = "(PLACE) by method"
_VENUE_ADDRESS = "〒150-0011 東京都渋谷区東1-3-1 カミニート14号"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

_SLEEP_SEC = 1.2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_taiwan_relevant(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _slug_from_url(url: str) -> str:
    """'https://placebymethod.com/pages/broom-making-in-taiwan-...' → 'broom-making-in-taiwan-...'"""
    return url.rstrip("/").rsplit("/", 1)[-1]


def _parse_kigen(kigen_str: str) -> tuple[datetime | None, datetime | None]:
    """Parse 会期 string into (start_date, end_date) UTC datetimes.

    Handles formats:
      "2026年5月8日（金）～5月24日（日）"   ← most common
      "2026年5月8日～2026年5月24日"          ← both years explicit
      "2021年11月12日（金）～11月27日（土）"
    """
    # Pattern 1: YYYY年MM月DD日 ... ～ MM月DD日
    m1 = re.search(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日[^～〜]*[～〜](\d{1,2})月(\d{1,2})日",
        kigen_str,
    )
    if m1:
        year = int(m1.group(1))
        sm, sd = int(m1.group(2)), int(m1.group(3))
        em, ed = int(m1.group(4)), int(m1.group(5))
        # Year boundary: if end month < start month, end is next year
        ey = year + 1 if em < sm else year
        start = datetime(year, sm, sd, tzinfo=timezone.utc)
        end = datetime(ey, em, ed, tzinfo=timezone.utc)
        return start, end

    # Pattern 2: YYYY年MM月DD日～YYYY年MM月DD日
    m2 = re.search(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日[^～〜]*[～〜]\s*(\d{4})年(\d{1,2})月(\d{1,2})日",
        kigen_str,
    )
    if m2:
        start = datetime(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)), tzinfo=timezone.utc)
        end = datetime(int(m2.group(4)), int(m2.group(5)), int(m2.group(6)), tzinfo=timezone.utc)
        return start, end

    return None, None


def _extract_exhibition_urls(listing_html: str) -> list[str]:
    """Return deduplicated exhibition page URLs from the listing page.

    The Shopify listing page contains full absolute URLs in <a href>.
    """
    soup = BeautifulSoup(listing_html, "html.parser")
    seen: set[str] = set()
    result: list[str] = []
    for a in soup.find_all("a", href=re.compile(r"placebymethod\.com/pages/")):
        href: str = a["href"]
        slug = unquote(_slug_from_url(href))
        if slug in _SKIP_SLUGS:
            continue
        if href not in seen:
            seen.add(href)
            result.append(href)
    return result


def _parse_exhibition_page(url: str, html: str, today: datetime) -> Event | None:
    """Parse an individual exhibition page.

    Returns an Event if Taiwan-related and within the lookback window,
    otherwise returns None.
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main")
    if not main:
        return None

    full_text = main.get_text("\n", strip=True)
    if not _is_taiwan_relevant(full_text):
        return None

    # Title from h1; strip surrounding Japanese/ASCII curly quotes
    h1 = main.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    title = title.strip("\u201c\u201d\u300c\u300d\u2018\u2019\"'")

    # Date: try structured 会期 block first
    kigen_match = re.search(r"会期[：:]\s*(.+)", full_text)
    start_date, end_date = None, None
    if kigen_match:
        start_date, end_date = _parse_kigen(kigen_match.group(1))

    if start_date is None:
        logger.warning("placebymethod: could not parse 会期 for %s", url)
        return None

    # Lookback filter
    cutoff = today - timedelta(days=_LOOKBACK_DAYS)
    check_date = end_date if end_date else start_date
    if check_date < cutoff:
        logger.debug("placebymethod: skip old exhibition %s (%s)", url, check_date.date())
        return None

    # Business hours
    hours_match = re.search(r"時間[：:]\s*(.+)", full_text)
    business_hours = hours_match.group(1).strip() if hours_match else None

    # Raw description: content before the 会期 block (Japanese intro text)
    kigen_pos = full_text.find("会期")
    if kigen_pos > 0:
        desc_body = full_text[:kigen_pos].strip()
        # Remove title repetition at the very top
        if title and desc_body.startswith(title):
            desc_body = desc_body[len(title):].lstrip('\n "')
    else:
        desc_body = full_text[:600]

    date_str = start_date.strftime("%Y年%m月%d日")
    raw_description = f"開催日時: {date_str}\n\n{desc_body}"

    slug = unquote(_slug_from_url(url))
    source_id = f"placebymethod_{slug}"

    return Event(
        source_name=SOURCE_NAME,
        source_id=source_id,
        source_url=url,
        original_language="ja",
        name_ja=title,
        raw_title=title,
        raw_description=raw_description,
        start_date=start_date,
        end_date=end_date,
        business_hours=business_hours,
        location_name=_VENUE_NAME,
        location_address=_VENUE_ADDRESS,
        category=["art"],
        is_paid=False,
    )


# ---------------------------------------------------------------------------
# Scraper class
# ---------------------------------------------------------------------------


class PlacebymethodScraper(BaseScraper):
    source_name = SOURCE_NAME

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        today = datetime.now(tz=timezone.utc)

        # Step 1: Fetch exhibitions listing page
        try:
            resp = requests.get(_LISTING_URL, headers=_HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("placebymethod: listing fetch failed: %s", exc)
            return []

        urls = _extract_exhibition_urls(resp.text)
        logger.info("placebymethod: found %d exhibition URLs", len(urls))

        # Step 2: Visit each page and filter by Taiwan keywords
        for url in urls:
            time.sleep(_SLEEP_SEC)
            try:
                page_resp = requests.get(url, headers=_HEADERS, timeout=20)
                page_resp.raise_for_status()
            except Exception as exc:
                logger.warning("placebymethod: error fetching %s: %s", url, exc)
                continue

            event = _parse_exhibition_page(url, page_resp.text, today)
            if event is not None:
                events.append(event)
                logger.info("placebymethod: added '%s'", event.name_ja)

        logger.info("placebymethod: total Taiwan events: %d", len(events))
        return events
