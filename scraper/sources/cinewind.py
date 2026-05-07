"""
Scraper for 新潟・市民映画館 シネ・ウインド (Cine Wind), Niigata.

Strategy:
  1. Fetch /movie/?show=now (now showing) and first page of /movie/?show=soon (upcoming)
  2. Find all a[href*='/movie/'] links (h2 headings = film titles)
  3. For each unique detail page, check full text for Taiwan keywords
  4. Extract title, date range from detail page ('上映期間2026/MM/DD～MM/DD')
  5. source_id: "cinewind_{id}" — from URL /movie/65551/ → id=65551
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.cinewind.com"
LISTING_URLS = [
    f"{BASE_URL}/movie/?show=now",
    f"{BASE_URL}/movie/?show=soon",  # first page only
]
LOCATION_NAME = "シネ・ウインド"
LOCATION_ADDRESS = "新潟県新潟市中央区八千代2-1-1 万代シテイ第2駐車場ビル1F"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _parse_movie_id(href: str) -> Optional[str]:
    path = urlparse(href).path  # e.g. "/movie/65551/"
    parts = path.rstrip("/").split("/")
    return parts[-1] if parts else None


def _parse_dates(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse '上映期間2026/5/2～5/15' or '2026/5/2～5/15' → (start, end)."""
    # Try full-year format: YYYY/M/D～M/D
    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})[～~](\d{1,2})/(\d{1,2})", text)
    if m:
        y = int(m.group(1))
        try:
            start = datetime(y, int(m.group(2)), int(m.group(3)))
            end_m, end_d = int(m.group(4)), int(m.group(5))
            end = datetime(y if end_m >= int(m.group(2)) else y + 1, end_m, end_d)
            return start, end
        except ValueError:
            pass
    return None, None


class CinewindScraper(BaseScraper):
    """Scrapes Taiwan-related films from シネ・ウインド (Niigata)."""

    SOURCE_NAME = "cinewind"

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

    def _collect_film_links(self) -> dict[str, str]:
        """Return {movie_id: detail_url} for all films in now/upcoming listings."""
        links: dict[str, str] = {}
        for listing_url in LISTING_URLS:
            soup = self._get(listing_url)
            if not soup:
                continue
            for a in soup.select("a[href*='/movie/']"):
                href = a.get("href", "")
                # Exclude navigation links like /movie/?show=...
                if not re.search(r"/movie/[^/?]", href):
                    continue
                full = urljoin(BASE_URL, href)
                mid = _parse_movie_id(full)
                if mid and mid not in links:
                    links[mid] = full
        return links

    def _scrape_detail(self, url: str) -> dict:
        result = {"title": "", "description": "", "full_text": "", "date_text": ""}
        soup = self._get(url)
        if not soup:
            return result

        h1 = soup.find("h1") or soup.find("h2")
        if h1:
            result["title"] = h1.get_text(strip=True)

        full_text = soup.get_text(" ", strip=True)
        result["full_text"] = full_text

        # Date: "上映期間2026/5/2～5/15"
        m = re.search(r"上映期間(\d{4}/\d{1,2}/\d{1,2}[^。\s]*)", full_text)
        if m:
            result["date_text"] = m.group(1)

        # Description from main content
        content = soup.select_one(".entry-content") or soup.select_one("article") or soup.select_one("main")
        if content:
            paras = [p.get_text(strip=True) for p in content.select("p") if len(p.get_text(strip=True)) > 20]
            result["description"] = "\n".join(paras[:5])

        return result

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        film_links = self._collect_film_links()
        logger.info("Collected %d unique film links", len(film_links))

        for movie_id, detail_url in film_links.items():
            time.sleep(0.5)
            detail = self._scrape_detail(detail_url)

            if not _is_taiwan(detail["full_text"]):
                logger.debug("Skipping non-Taiwan film: %s", detail["title"])
                continue

            source_id = f"cinewind_{movie_id}"
            title = detail["title"]
            start_date, end_date = _parse_dates(detail["date_text"])

            raw_desc = detail["description"]
            if start_date:
                raw_desc = (
                    f"上映期間: {start_date.strftime('%Y年%m月%d日')}"
                    + (f"〜{end_date.strftime('%Y年%m月%d日')}" if end_date else "")
                    + "\n\n" + raw_desc
                )

            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=detail_url,
                original_language="ja",
                name_ja=title,
                raw_title=title,
                raw_description=raw_desc,
                description_ja=detail["description"] or None,
                category=["movie"],
                start_date=start_date,
                end_date=end_date,
                location_name=LOCATION_NAME,
                location_address=LOCATION_ADDRESS,
            )
            events.append(event)
            logger.info("Found Taiwan film: %s", title)

        logger.info("Total Taiwan films found: %d", len(events))
        return events
