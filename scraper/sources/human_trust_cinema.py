"""
Scraper for ヒューマントラストシネマ有楽町 (Human Trust Cinema Yurakucho), Tokyo.

Uses TTCG (Tokyo Theatres Company) CMS — shared across TTCG group venues.

Strategy:
  1. Fetch /human_yurakucho/movie/ — parse mod-column-box cards
     Each card has data-date (start date) and a relative href to detail page
  2. Fetch each detail page — extract country from b.label-type-b, OGP description
  3. Taiwan filter: 制作国 contains 台湾/Taiwan OR title/description contains 台湾/台灣
  4. source_id: "human_yurakucho_{movie_id}" — extracted from URL path
  5. No end_date available on site; leave as None (currently showing)
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from movie_title_lookup import lookup_movie_titles

logger = logging.getLogger(__name__)

BASE_URL = "https://ttcg.jp"
LISTING_URL = f"{BASE_URL}/human_yurakucho/movie/"

LOCATION_NAME = "ヒューマントラストシネマ有楽町"
LOCATION_ADDRESS = "東京都千代田区有楽町1-2-2 東宝日比谷ビル別館B1"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(country: str, title: str, description: str) -> bool:
    combined = f"{country} {title} {description}"
    return any(kw in combined for kw in TAIWAN_KEYWORDS)


def _parse_movie_id(href: str) -> Optional[str]:
    """Extract numeric movie ID from /human_yurakucho/movie/1296000.html"""
    m = re.search(r"/movie/(\d+)\.html", href)
    return m.group(1) if m else None


class HumanTrustCinemaScraper(BaseScraper):
    """Scrapes Taiwan-related films currently showing at ヒューマントラストシネマ有楽町."""

    SOURCE_NAME = "human_trust_cinema"

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

    def _scrape_detail(self, url: str) -> dict:
        """Return dict with keys: country, description, title."""
        result = {"country": "", "description": "", "title": ""}
        soup = self._get(url)
        if not soup:
            return result

        # Country: b.label-type-b inside movie-overview
        country_el = soup.select_one("div.movie-overview b.label-type-b")
        if country_el:
            result["country"] = country_el.get_text(strip=True)

        # Title: h2.movie-title (without span.sub)
        title_el = soup.select_one("div.movie-overview h2.movie-title")
        if title_el:
            # Remove the sub span (e.g. English title)
            sub = title_el.find("span", class_="sub")
            if sub:
                sub.decompose()
            result["title"] = title_el.get_text(strip=True)

        # Description: OGP meta description
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            result["description"] = og_desc.get("content", "")

        return result

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        soup = self._get(LISTING_URL)
        if not soup:
            logger.error("Failed to fetch listing page: %s", LISTING_URL)
            return events

        boxes = soup.select("div.mod-column-box")
        logger.info("Found %d movie cards on listing page", len(boxes))

        for box in boxes:
            link_el = box.select_one("a[href]")
            if not link_el:
                continue

            href = link_el.get("href", "")
            movie_id = _parse_movie_id(href)
            if not movie_id:
                continue

            detail_url = BASE_URL + href if href.startswith("/") else href
            source_id = f"human_yurakucho_{movie_id}"

            # Start date from data-date attribute
            data_date = link_el.get("data-date", "")
            # data-date may also be on an inner element
            if not data_date:
                inner = link_el.find(attrs={"data-date": True})
                data_date = inner.get("data-date", "") if inner else ""
            start_date: Optional[datetime] = None
            if data_date:
                try:
                    start_date = datetime.fromisoformat(
                        data_date.replace("+09:00", "")
                    )
                except (ValueError, AttributeError):
                    pass

            # Title from listing card h2
            title_el = box.select_one("h2")
            title = title_el.get_text(strip=True) if title_el else ""

            time.sleep(0.5)
            detail = self._scrape_detail(detail_url)

            # Use detailed title if available and more precise
            if detail["title"]:
                title = detail["title"]

            # Taiwan filter
            if not _is_taiwan(detail["country"], title, detail["description"]):
                logger.debug(
                    "Skipping non-Taiwan film: %s (country=%s)",
                    title, detail["country"]
                )
                continue

            raw_desc = detail["description"]
            if start_date:
                raw_desc = (
                    f"上映開始: {start_date.strftime('%Y年%m月%d日')}\n\n"
                    + raw_desc
                )

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
                raw_description=raw_desc,
                description_ja=detail["description"] or None,
                category=["movie"],
                start_date=start_date,
                end_date=None,
                location_name=LOCATION_NAME,
                location_address=LOCATION_ADDRESS,
            )
            events.append(event)
            logger.info(
                "Found Taiwan film: %s (country=%s)", title, detail["country"]
            )

        logger.info("Total Taiwan films found: %d", len(events))
        return events
