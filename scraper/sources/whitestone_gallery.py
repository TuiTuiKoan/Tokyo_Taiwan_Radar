"""Scraper for Whitestone Gallery Tokyo / Karuizawa

Source URL: https://www.whitestone-gallery.com/blogs/gallery-exhibitions/tagged/current
Platform  : Static HTML (Shopify blog, no JS required)
Source name: whitestone_gallery

Strategy:
  1. Fetch /tagged/current — paginate with ?page=N until no more cards
  2. Find each div.wsg-exhibition-card → extract title, location, date
  3. Filter for Japan locations: "Ginza", "Karuizawa", "Tokyo"
  4. For each Japan exhibition, fetch detail page and check for Taiwan keywords
  5. If Taiwan-related, create Event

Taiwan keywords: Taiwan, 台湾, 臺灣, Taiwanese
Date format: "2026.04.25 - 05.31"  or  "2026.05.08"
source_id: whitestone_gallery_{url-slug}

Japan venues:
  Ginza New Gallery: 東京都中央区銀座6丁目4-16
  Karuizawa Gallery: 長野県北佐久郡軽井沢町
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "whitestone_gallery"
BASE_URL = "https://www.whitestone-gallery.com"
LISTING_URL = f"{BASE_URL}/blogs/gallery-exhibitions/tagged/current"

_JST = timezone(timedelta(hours=9))
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0)",
    "Accept-Language": "en-US,en;q=0.9",
}

# Japan location keywords in the card location text
_JAPAN_KEYWORDS = ["Ginza", "Karuizawa", "Tokyo", "Japan"]

# Taiwan relevance keywords for detail page full text
_TAIWAN_KEYWORDS = ["Taiwan", "台湾", "臺灣", "Taiwanese"]

# Known Japan venue addresses
_VENUE_MAP = {
    "Ginza": "東京都中央区銀座6丁目4-16",
    "Karuizawa": "長野県北佐久郡軽井沢町",
    "Tokyo": "東京都",
}

# Date pattern: "2026.04.25 - 05.31" or "2026.04.25"
_DATE_RE = re.compile(
    r"(\d{4})\.(\d{1,2})\.(\d{1,2})"  # start: YYYY.M.D
    r"(?:\s*-\s*(?:(\d{4})\.)?(\d{1,2})\.(\d{1,2}))?"  # optional end: [YYYY.]M.D
)


def _is_taiwan_relevant(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _is_japan_location(location: str) -> bool:
    return any(kw in location for kw in _JAPAN_KEYWORDS)


def _parse_dates(date_str: str, today: datetime):
    """Parse "YYYY.MM.DD - MM.DD" or "YYYY.MM.DD" into (start_date, end_date)."""
    m = _DATE_RE.search(date_str)
    if not m:
        return None, None

    s_year, s_mon, s_day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        start = datetime(s_year, s_mon, s_day, tzinfo=_JST)
    except ValueError:
        return None, None

    end = None
    if m.group(5) is not None:
        e_year = int(m.group(4)) if m.group(4) else s_year
        e_mon = int(m.group(5))
        e_day = int(m.group(6))
        # Handle year rollover: if end month < start month, increment year
        if e_mon < s_mon:
            e_year += 1
        try:
            end = datetime(e_year, e_mon, e_day, tzinfo=_JST)
        except ValueError:
            end = None

    return start, end


def _venue_address(location: str) -> str:
    for kw, addr in _VENUE_MAP.items():
        if kw in location:
            return addr
    return "東京都"


class WhitestoneGalleryScraper(BaseScraper):
    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        today = datetime.now(_JST)

        page = 1
        while True:
            url = LISTING_URL if page == 1 else f"{LISTING_URL}?page={page}"
            try:
                resp = requests.get(url, headers=_HEADERS, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("WhitestoneGallery: failed to fetch %s: %s", url, exc)
                break

            soup = BeautifulSoup(resp.content, "html.parser")
            cards = soup.find_all("div", class_="wsg-exhibition-card")
            if not cards:
                break

            for card in cards:
                a = card.find("a", href=True)
                if not a:
                    continue

                href = a["href"]
                slug = href.rstrip("/").split("/")[-1]
                full_url = urljoin(BASE_URL, href)

                # Parse title, location, date from <a> text
                parts = [p.strip() for p in a.get_text(separator="|", strip=True).split("|") if p.strip()]
                if len(parts) < 2:
                    continue

                title = parts[0]
                location = parts[1] if len(parts) > 1 else ""
                date_str = parts[2] if len(parts) > 2 else ""

                # Skip non-Japan exhibitions
                if not _is_japan_location(location):
                    continue

                # Fetch detail page and check Taiwan relevance
                try:
                    time.sleep(0.5)
                    detail_resp = requests.get(full_url, headers=_HEADERS, timeout=20)
                    detail_resp.raise_for_status()
                except Exception as exc:
                    logger.warning("WhitestoneGallery: failed to fetch detail %s: %s", full_url, exc)
                    continue

                # Only check main content for Taiwan keywords (ignore footer country list)
                detail_soup = BeautifulSoup(detail_resp.content, "html.parser")
                desc_el = detail_soup.find("div", class_="rte") or detail_soup.find("article")
                main_text = desc_el.get_text(" ", strip=True) if desc_el else ""
                # Also include the page <title> and exhibition header
                header_el = detail_soup.find("h1") or detail_soup.find("h2")
                header_text = header_el.get_text(" ", strip=True) if header_el else title
                check_text = f"{header_text} {main_text}"

                if not _is_taiwan_relevant(check_text):
                    continue

                # Parse dates
                start_dt, end_dt = _parse_dates(date_str, today)
                if start_dt is None:
                    logger.warning("WhitestoneGallery: cannot parse date '%s' for %s", date_str, slug)
                    continue

                raw_desc = main_text[:1500] if main_text else title

                events.append(Event(
                    source_name=SOURCE_NAME,
                    source_id=f"whitestone_gallery_{slug}",
                    source_url=full_url,
                    original_language="en",
                    name_ja=title,
                    name_en=title,
                    start_date=start_dt,
                    end_date=end_dt,
                    location_name=location,
                    location_address=_venue_address(location),
                    raw_title=title,
                    raw_description=raw_desc,
                ))
                logger.info("WhitestoneGallery: found Taiwan exhibition: %s @ %s", title, location)

            # Check if there's a next page
            next_link = soup.find("a", class_=lambda c: c and "next" in (c or "").lower())
            if not next_link:
                break
            page += 1
            time.sleep(1.0)

        logger.info("WhitestoneGalleryScraper: scraped %d events", len(events))
        return events
