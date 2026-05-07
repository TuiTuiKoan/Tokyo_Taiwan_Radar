"""
Scraper for OttO Extended Place (大宮, Saitama).

Strategy:
  1. Fetch https://otto-extended.com/cinema — static SSR page with film listings
     Sections: 上映中の作品 (Now Showing), 上映予定の作品 (Coming Soon)
     Each film: a[href*='/cinema/'] with alphanumeric slug ID
  2. For each unique film detail page, check full text for Taiwan keywords
  3. source_id: "otto_{slug}" — from /cinema/RMnPEswS → slug=RMnPEswS
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://otto-extended.com"
LISTING_URL = f"{BASE_URL}/cinema"
LOCATION_NAME = "OttO Extended Place"
LOCATION_ADDRESS = "埼玉県さいたま市大宮区宮町1-60 2F"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]

# Exclude non-film informational pages
EXCLUDED_SLUGS = {"archive", "cinema10", "uUIzw9_g"}


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _parse_slug(href: str) -> Optional[str]:
    path = urlparse(href).path  # e.g. /cinema/RMnPEswS
    parts = path.rstrip("/").split("/")
    return parts[-1] if parts and len(parts) >= 2 else None


class OttoScraper(BaseScraper):
    """Scrapes Taiwan-related films from OttO Extended Place (大宮, Saitama)."""

    SOURCE_NAME = "otto"

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
        """Return {slug: detail_url} for all current and upcoming films."""
        soup = self._get(LISTING_URL)
        if not soup:
            return {}

        links: dict[str, str] = {}
        for a in soup.select("a[href*='/cinema/']"):
            href = a.get("href", "")
            slug = _parse_slug(href)
            if not slug or slug in EXCLUDED_SLUGS or slug in links:
                continue
            # Skip navigation/footer links that are just "cinema" listing
            if href.rstrip("/").endswith("/cinema"):
                continue
            full = BASE_URL + href if href.startswith("/") else href
            links[slug] = full
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

        # Date range: "MM/DD(曜)～MM/DD(曜)" or "YYYY/MM/DD〜"
        m = re.search(r"(\d{1,2})/(\d{1,2})[^〜～]*[〜～](\d{1,2})/(\d{1,2})", full_text)
        if m:
            result["date_text"] = m.group(0)

        # Description: main content paragraphs
        content = soup.select_one("main") or soup.select_one("article") or soup
        paras = [p.get_text(strip=True) for p in content.select("p") if len(p.get_text(strip=True)) > 20]
        result["description"] = "\n".join(paras[:5])

        return result

    def _parse_date_from_listing(self, soup: BeautifulSoup, slug: str) -> Optional[datetime]:
        """Try to find dates for a film from the schedule section of listing page."""
        # Look for the film title in schedule sections
        full_text = soup.get_text(" ", strip=True)
        # Find the film's position in schedule and extract nearby date patterns
        return None

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        film_links = self._collect_film_links()
        logger.info("Collected %d unique film links from OttO listing", len(film_links))

        for slug, detail_url in film_links.items():
            time.sleep(0.5)
            detail = self._scrape_detail(detail_url)

            if not _is_taiwan(detail["full_text"]):
                logger.debug("Skipping non-Taiwan film: %s", detail["title"])
                continue

            source_id = f"otto_{slug}"
            title = detail["title"]

            # Parse start date from date text if available
            start_date: Optional[datetime] = None
            if detail["date_text"]:
                m = re.match(r"(\d{1,2})/(\d{1,2})", detail["date_text"])
                if m:
                    year = datetime.now().year
                    try:
                        start_date = datetime(year, int(m.group(1)), int(m.group(2)))
                    except ValueError:
                        pass

            raw_desc = detail["description"]
            if start_date:
                raw_desc = f"上映開始: {start_date.strftime('%Y年%m月%d日')}\n\n" + raw_desc

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
                end_date=None,
                location_name=LOCATION_NAME,
                location_address=LOCATION_ADDRESS,
            )
            events.append(event)
            logger.info("Found Taiwan film: %s", title)

        logger.info("Total Taiwan films found: %d", len(events))
        return events
