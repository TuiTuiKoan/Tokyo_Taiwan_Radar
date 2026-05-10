"""
Scraper for 御成座（おなり座）, Odate, Akita — WordPress-based arthouse cinema.

Strategy:
  1. Fetch /category/movie/ for all film post URLs
  2. Deduplicate URLs (film appears multiple times in listing)
  3. For each film detail page, check for Taiwan keywords in full text
  4. Extract: title (h1), date (YYYY-M-D), description
  5. source_id: onariza_{slug} from URL
"""

import hashlib
import logging
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "http://onariza.oodate.or.jp"
LISTING_URL = f"{BASE_URL}/category/movie/"
LOCATION_NAME = "御成座（おなり座）"
LOCATION_ADDRESS = "秋田県大館市"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan", "臺灣"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _slug_from_url(url: str) -> str:
    # /movie/kiri-no-gotoku.html → kiri-no-gotoku
    m = re.search(r"/movie/([^/]+)\.html?$", url)
    if m:
        slug = m.group(1)
        # Use first 20 chars to keep source_id manageable
        return f"onariza_{slug[:40]}"
    digest = hashlib.md5(url.encode()).hexdigest()[:10]
    return f"onariza_{digest}"


def _parse_date(text: str) -> Optional[datetime]:
    """Parse 'YYYY-M-D' from page text."""
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


class OnarizaScraper(BaseScraper):
    """Scrapes Taiwan-related films from 御成座 (Odate, Akita)."""

    SOURCE_NAME = "onariza"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.content, "html.parser")
        except Exception as exc:
            logger.warning("GET %s failed: %s", url, exc)
            return None

    def _collect_film_urls(self) -> list[str]:
        """Return unique film detail URLs from /category/movie/."""
        seen: set[str] = set()
        results: list[str] = []
        soup = self._get_soup(LISTING_URL)
        if not soup:
            return results
        for a in soup.select("a[href*='/movie/']"):
            href = a.get("href", "")
            if "category" in href or not href.endswith(".html"):
                continue
            full_url = urljoin(BASE_URL, href)
            if full_url not in seen:
                seen.add(full_url)
                results.append(full_url)
        return results

    def _scrape_detail(self, url: str) -> Optional[Event]:
        soup = self._get_soup(url)
        if not soup:
            return None

        full_text = soup.get_text(" ", strip=True)
        if not _is_taiwan(full_text):
            return None

        # Title: page <title> is "フィルム名 | 御成座..." — split reliably
        page_title = soup.title.text if soup.title else ""
        title = page_title.split("|")[0].strip()
        if not title:
            # Fallback: h2 or h1 inside main content area
            content_area = soup.select_one(".entry-content, .post-content, #content, main")
            h = (content_area or soup).select_one("h2, h1")
            title = h.get_text(strip=True) if h else ""

        start_date = _parse_date(full_text)

        # Description: main content paragraphs
        content = soup.select_one(".entry-content, .post-content, article")
        if content:
            paras = [p.get_text(strip=True) for p in content.select("p") if len(p.get_text(strip=True)) > 20]
            desc = "\n".join(paras[:5])
        else:
            desc = full_text[:500]

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=_slug_from_url(url),
            source_url=url,
            original_language="ja",
            name_ja=title,
            raw_title=title,
            raw_description=desc,
            description_ja=desc or None,
            category=["art"],
            start_date=start_date,
            location_name=LOCATION_NAME,
            location_address=LOCATION_ADDRESS,
        )

    def scrape(self) -> list[Event]:
        film_urls = self._collect_film_urls()
        logger.info("Onariza: found %d unique films", len(film_urls))

        events: list[Event] = []
        for url in film_urls:
            time.sleep(0.3)
            ev = self._scrape_detail(url)
            if ev:
                events.append(ev)
                logger.info("Onariza Taiwan film: %s", ev.name_ja)

        logger.info("Onariza total Taiwan events: %d", len(events))
        return events
