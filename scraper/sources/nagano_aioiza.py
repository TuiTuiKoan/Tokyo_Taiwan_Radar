"""Scraper for 長野相生座・ロキシー (Nagano)

URL: http://www.naganoaioiza.com/category/1578520.html (now showing)
URL: http://www.naganoaioiza.com/category/1231977.html (upcoming)
Structure: CMS blog with info-{slug} individual movie pages.
  - Individual pages have <p>YYYY年/国/N分/rating</p> for country info.

source_name : nagano_aioiza
source_id   : nagano_aioiza_{slug}
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

_BASE = "http://www.naganoaioiza.com"
_NOW_SHOWING_URL = f"{_BASE}/category/1578520.html"
_UPCOMING_URL = f"{_BASE}/category/1231977.html"
_UA = "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "台灣", "金馬", "金马", "台北", "台中"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _get_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = _UA
    return s


def _extract_movie_links(html: str) -> dict[str, str]:
    """Extract {slug: full_url} from page HTML."""
    result: dict[str, str] = {}
    for m in re.finditer(r'href="(http://www\.naganoaioiza\.com/(info-[^"]+))"', html):
        url, slug = m.group(1), m.group(2)
        if slug not in result:
            result[slug] = url
    return result


class NaganoAioizaScraper(BaseScraper):
    source_name = "nagano_aioiza"

    def scrape(self) -> list[Event]:
        session = _get_session()
        movies: dict[str, str] = {}  # slug → url

        for listing_url in [_NOW_SHOWING_URL, _UPCOMING_URL]:
            try:
                resp = session.get(listing_url, timeout=20)
                resp.raise_for_status()
                links = _extract_movie_links(resp.text)
                for slug, url in links.items():
                    if slug not in movies:
                        movies[slug] = url
            except Exception as exc:
                logger.warning("%s: listing %s failed: %s", self.source_name, listing_url, exc)

        events: list[Event] = []
        for slug, url in movies.items():
            time.sleep(0.5)
            try:
                resp2 = session.get(url, timeout=20)
                resp2.raise_for_status()
            except Exception as exc:
                logger.debug("%s: %s failed: %s", self.source_name, slug, exc)
                continue

            soup2 = BeautifulSoup(resp2.text, "html.parser")
            page_text = soup2.get_text(" ", strip=True)

            # Title from og:title or h1
            title = ""
            og = soup2.find("meta", property="og:title")
            if og:
                title = og.get("content", "").strip()
            if not title:
                h1 = soup2.find("h1")
                title = h1.get_text(strip=True) if h1 else slug

            if not _is_taiwan(title + " " + page_text):
                continue

            # Description: paragraphs containing country or cast info
            description = ""
            for p in soup2.find_all("p"):
                text = p.get_text(" ", strip=True)
                if re.search(r"\d{4}年.*分", text):  # "YYYY年/国/N分"
                    description = text
                    break

            # start_date: not easily determined; use today as fallback
            start_date = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            events.append(Event(
                source_name=self.source_name,
                source_id=f"nagano_aioiza_{slug.replace('info-', '')}",
                source_url=url,
                original_language="ja",
                name_ja=title,
                start_date=start_date,
                end_date=None,
                location_name="長野相生座・ロキシー",
                location_address="長野県長野市権堂町2255",
                location_url=_BASE,
                is_paid=True,
                raw_title=title,
                raw_description=description,
                organizer="長野相生座・ロキシー",
                organizer_type=["commercial_brand"],
                event_form=["screening"],
            ))

        logger.info("%s: %d Taiwan events found", self.source_name, len(events))
        return events
