"""
Scraper for Uplink cinema locations (Kichijoji / 吉祥寺).

Static HTML site (WordPress). No Playwright required.

Strategy:
  1. Fetch /movie/ listing page — parse article.list_archive-item cards
  2. For each card, extract title and date text from listing
  3. Fetch detail page — check country in <span class="small">（YEAR／COUNTRY／...）
  4. Taiwan filter: country contains 台湾 or Taiwan
  5. source_id: "uplink_{location_key}_{post_id}" (numeric from URL)

Monitored locations:
  joji     — アップリンク吉祥寺  (東京都武蔵野市吉祥寺)
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from movie_title_lookup import lookup_movie_titles

logger = logging.getLogger(__name__)

# Location config: (listing_url, location_name, location_address, location_key)
LOCATIONS = [
    (
        "https://joji.uplink.co.jp/movie/",
        "アップリンク吉祥寺",
        "東京都武蔵野市吉祥寺本町1-5-1",
        "joji",
    ),
]

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _extract_post_id(url: str) -> Optional[str]:
    """Extract numeric post ID from URL like /movie/2026/31768"""
    m = re.search(r"/(\d+)/?$", url)
    return m.group(1) if m else None


def _parse_date_from_listing(date_text: str, fetch_year: int) -> Optional[datetime]:
    """
    Parse date from listing text like:
      "6月5日（金） 公開"
      "M月D日（曜）～M月D日（曜）【N週間限定上映】"
      "M月D日（曜）公開"
    Returns start_date as datetime.
    """
    m = re.search(r"(\d{1,2})月(\d{1,2})日", date_text)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    # Cross-year: if month < current month by more than 6, use next year
    today = datetime.now()
    year = fetch_year
    if month < today.month - 6:
        year = fetch_year + 1
    elif month > today.month + 6:
        year = fetch_year - 1
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _parse_end_date(date_text: str, start_year: int) -> Optional[datetime]:
    """Parse end date from "M月D日（曜）～M月D日（曜）" ranges."""
    matches = re.findall(r"(\d{1,2})月(\d{1,2})日", date_text)
    if len(matches) >= 2:
        try:
            return datetime(start_year, int(matches[1][0]), int(matches[1][1]), 23, 59, 59)
        except ValueError:
            pass
    return None


def _extract_country_from_detail(soup: BeautifulSoup) -> str:
    """
    Extract all production fields from the production info span, e.g.
    <span class="small">（2024年／台湾／カラー／94分／...）</span>
    or
    <span class="small">（2025年／134分／台湾／カラー）</span>
    Returns the full fields string (after year) for Taiwan keyword matching.
    """
    for span in soup.find_all("span", class_="small"):
        text = span.get_text(strip=True)
        # Pattern: （YEAR年／rest）  — capture ALL fields after year
        m = re.search(r"[（(]\d{4}年?／(.+?)[）)]", text)
        if m:
            return m.group(1)
    return ""


class UplinkCinemaScraper(BaseScraper):
    """Scrapes Taiwan movies from Uplink cinema locations."""

    SOURCE_NAME = "uplink_cinema"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })

    def _get(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as exc:
            logger.warning("GET %s failed: %s", url, exc)
            return None

    def _scrape_location(
        self,
        listing_url: str,
        location_name: str,
        location_address: str,
        location_key: str,
    ) -> list[Event]:
        events: list[Event] = []

        soup = self._get(listing_url)
        if not soup:
            logger.warning("Failed to fetch listing: %s", listing_url)
            return events

        items = soup.select("article.list_archive-item")
        logger.info("%s: found %d movie cards", location_key, len(items))

        fetch_year = datetime.now().year

        for item in items:
            link_el = item.select_one("a")
            if not link_el:
                continue

            detail_url = link_el.get("href", "")
            if not detail_url:
                continue

            title_el = item.select_one("h1.list_archive-heading")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            date_el = item.select_one("p.list_archive-text")
            date_text = date_el.get_text(strip=True) if date_el else ""

            start_date = _parse_date_from_listing(date_text, fetch_year)
            end_date = _parse_end_date(date_text, start_date.year if start_date else fetch_year)

            post_id = _extract_post_id(detail_url)
            if not post_id:
                continue
            source_id = f"uplink_{location_key}_{post_id}"

            # Fetch detail page to check country
            time.sleep(0.5)
            detail_soup = self._get(detail_url)
            if not detail_soup:
                logger.debug("Could not fetch detail: %s", detail_url)
                continue

            country = _extract_country_from_detail(detail_soup)
            if not _is_taiwan(country):
                # Fallback: check full description text for Taiwan keywords
                detail_text = detail_soup.get_text()
                if not _is_taiwan(detail_text):
                    logger.debug("Skipping non-Taiwan: %s (country=%s)", title, country)
                    continue

            # Extract description from detail page
            desc_el = detail_soup.select_one("div.l-wysiwyg, div.wysiwyg-wrap")
            description = desc_el.get_text(separator="\n", strip=True) if desc_el else ""

            name_zh, name_en = lookup_movie_titles(title)
            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=detail_url,
                original_language="ja",
                name_ja=title,
                name_zh=name_zh,
                name_en=name_en,
                raw_title=title,
                raw_description=f"会場: {location_name}\n{date_text}\n\n{description}",
                description_ja=description or None,
                category=["movie"],
                start_date=start_date,
                end_date=end_date,
                location_name=location_name,
                location_address=location_address,
                is_paid=True,
            )
            events.append(event)
            logger.info("Found Taiwan movie: %s (country=%s, %s)", title, country, date_text)

        return events

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        for listing_url, loc_name, loc_addr, loc_key in LOCATIONS:
            loc_events = self._scrape_location(listing_url, loc_name, loc_addr, loc_key)
            events.extend(loc_events)

        logger.info("Total Taiwan movies from Uplink: %d", len(events))
        return events
