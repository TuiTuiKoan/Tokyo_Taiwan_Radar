"""
Scrapers for TTCG (Tokyo Theatres Company Group) Kansai venues:
  - テアトル梅田 (T-Joy Umeda / Teatoru Umeda), Osaka
  - シネ・リーブル神戸 (Cine Libre Kobe), Kobe

Both use the same TTCG CMS as ヒューマントラストシネマ有楽町.
Strategy:
  1. Fetch /ttcg_umeda/movie/ or /cinelibre_kobe/movie/ — parse div.mod-column-box cards
  2. Fetch each detail page — extract country from b.label-type-b, OGP description
  3. Taiwan filter: 制作国 contains 台湾/Taiwan OR title/description contains 台湾/台灣
  4. source_id: "{venue_key}_{movie_id}"
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
TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(country: str, title: str, description: str) -> bool:
    combined = f"{country} {title} {description}"
    return any(kw in combined for kw in TAIWAN_KEYWORDS)


def _parse_movie_id(href: str) -> Optional[str]:
    m = re.search(r"/movie/(\d+)\.html", href)
    return m.group(1) if m else None


class _TtcgVenueScraper(BaseScraper):
    """Base scraper for a single TTCG venue."""

    SOURCE_NAME: str = ""       # overridden in concrete subclass
    VENUE_KEY: str = ""         # used in listing URL and source_id prefix
    LOCATION_NAME: str = ""
    LOCATION_ADDRESS: str = ""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })

    def _listing_url(self) -> str:
        return f"{BASE_URL}/{self.VENUE_KEY}/movie/"

    def _get(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as exc:
            logger.warning("GET %s failed: %s", url, exc)
            return None

    def _scrape_detail(self, url: str) -> dict:
        result = {"country": "", "description": "", "title": ""}
        soup = self._get(url)
        if not soup:
            return result

        country_el = soup.select_one("div.movie-overview b.label-type-b")
        if country_el:
            result["country"] = country_el.get_text(strip=True)

        title_el = soup.select_one("div.movie-overview h2.movie-title")
        if title_el:
            sub = title_el.find("span", class_="sub")
            if sub:
                sub.decompose()
            result["title"] = title_el.get_text(strip=True)

        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            result["description"] = og_desc.get("content", "")

        return result

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        listing_url = self._listing_url()

        soup = self._get(listing_url)
        if not soup:
            logger.error("Failed to fetch listing page: %s", listing_url)
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
            source_id = f"{self.VENUE_KEY}_{movie_id}"

            # Start date from data-date attribute
            data_date = link_el.get("data-date", "")
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

            title_el = box.select_one("h2")
            title = title_el.get_text(strip=True) if title_el else ""

            time.sleep(0.5)
            detail = self._scrape_detail(detail_url)

            if detail["title"]:
                title = detail["title"]

            if not _is_taiwan(detail["country"], title, detail["description"]):
                logger.debug("Skipping non-Taiwan film: %s", title)
                continue

            raw_desc = detail["description"]
            if start_date:
                raw_desc = (
                    f"上映開始: {start_date.strftime('%Y年%m月%d日')}\n\n" + raw_desc
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
                location_name=self.LOCATION_NAME,
                location_address=self.LOCATION_ADDRESS,
            )
            events.append(event)
            logger.info("Found Taiwan film: %s", title)

        logger.info("%s: %d Taiwan events found", self.VENUE_KEY, len(events))
        return events


class TtcgUmedaScraper(_TtcgVenueScraper):
    """テアトル梅田 (Teatoru Umeda), Osaka."""

    SOURCE_NAME = "ttcg_umeda"
    VENUE_KEY = "ttcg_umeda"
    LOCATION_NAME = "テアトル梅田"
    LOCATION_ADDRESS = "大阪府大阪市北区角田町2-1 梅田ロフト7F"


class CinelibreKobeScraper(_TtcgVenueScraper):
    """シネ・リーブル神戸 (Cine Libre Kobe), Kobe."""

    SOURCE_NAME = "cinelibre_kobe"
    VENUE_KEY = "cinelibre_kobe"
    LOCATION_NAME = "シネ・リーブル神戸"
    LOCATION_ADDRESS = "兵庫県神戸市中央区小野柄通7-1-1 神戸阪急ビル東館8F"
