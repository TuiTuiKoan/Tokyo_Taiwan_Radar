"""Scraper for 上田映劇（長野県上田市）

Source URLs:
  https://www.uedaeigeki.com/category/now-showing/  (現在上映中)
  https://www.uedaeigeki.com/category/coming/        (今後の上映作品)

Platform  : WordPress static HTML — no JS rendering required
Source name: uedaeigeki
Source ID : uedaeigeki_{post_id}  (numeric ID from URL path)

Strategy:
  1. Fetch both listing pages → collect article.p-blog-list__item cards
  2. Extract title (p-blog-list__item-title) and detail URL from each card
  3. For each detail page:
     a. Extract start/end date from ［上映日程］ in p-entry__body
     b. Check full body text for Taiwan keywords
     c. Skip if no Taiwan content
  4. source_id: numeric ID from URL path

Date formats in title (for quick pre-filter before fetching detail):
  【5/15~28】 【5/1~14】 【順次公開】
Date in detail body:
  ［上映日程］2026年5月15日(金) 〜 28日(木)

Taiwan keyword filter (applied to full detail page text):
  ["台湾", "Taiwan", "臺灣", "台湾映画", "台湾作品"]
"""

import logging
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "uedaeigeki"
_BASE_URL = "https://www.uedaeigeki.com"
_LISTING_URLS = [
    "https://www.uedaeigeki.com/category/now-showing/",
    "https://www.uedaeigeki.com/category/coming/",
]
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]

_HEADERS = {
    "User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)",
}

# ［上映日程］2026年5月15日(金) 〜 28日(木)
_DATE_RE = re.compile(
    r"上映日程[^\d]*(\d{4})年(\d{1,2})月(\d{1,2})日"
    r"(?:[^\d～〜]*[～〜]\s*(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日)?"
)
# Title date hint: 【5/15~28】 or 【5/1~14】
_TITLE_DATE_RE = re.compile(r"【(\d{1,2})/(\d{1,2})[~〜～](\d{1,2})(?:/(\d{1,2}))?】")

_REQUEST_DELAY = 0.5  # seconds between requests


def _extract_post_id(url: str) -> str | None:
    """Extract numeric post ID from URL path like /coming/33301/."""
    m = re.search(r"/(\d{4,6})/?$", url)
    return m.group(1) if m else None


def _parse_date_from_body(body_text: str) -> tuple[datetime | None, datetime | None]:
    """Parse start/end dates from '上映日程' line in entry body."""
    m = _DATE_RE.search(body_text)
    if not m:
        return None, None

    sy, sm, sd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    start = datetime(sy, sm, sd)

    end = None
    if m.group(6):  # end day present
        ey = int(m.group(4)) if m.group(4) else sy
        em = int(m.group(5))
        ed = int(m.group(6))
        # If end month < start month, it wraps to next year
        if em < sm:
            ey += 1
        end = datetime(ey, em, ed)

    return start, end


def _is_taiwan_related(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


class UedaEigekiScraper(BaseScraper):
    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        seen_ids: set[str] = set()

        detail_links: list[str] = []
        for listing_url in _LISTING_URLS:
            links = self._collect_detail_links(listing_url)
            for link in links:
                if link not in detail_links:
                    detail_links.append(link)

        logger.info("uedaeigeki: %d detail pages to check", len(detail_links))

        for detail_url in detail_links:
            time.sleep(_REQUEST_DELAY)
            event = self._scrape_detail(detail_url)
            if event and event.source_id not in seen_ids:
                seen_ids.add(event.source_id)
                events.append(event)

        logger.info("uedaeigeki: total Taiwan films found: %d", len(events))
        return events

    def _collect_detail_links(self, listing_url: str) -> list[str]:
        try:
            resp = requests.get(listing_url, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
        except Exception as exc:
            logger.error("uedaeigeki: failed to fetch %s: %s", listing_url, exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.find_all("article", class_="p-blog-list__item")

        links = []
        for art in articles:
            a = art.find("a", href=True)
            if a and a["href"].startswith(_BASE_URL):
                links.append(a["href"])
        return links

    def _scrape_detail(self, url: str) -> Event | None:
        post_id = _extract_post_id(url)
        if not post_id:
            logger.debug("uedaeigeki: no post_id for %s", url)
            return None

        try:
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
        except Exception as exc:
            logger.warning("uedaeigeki: failed to fetch detail %s: %s", url, exc)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Title
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""
        # Strip date suffix from title: 【5/15~28】 and trailing *notes
        clean_title = re.sub(r"【[^】]*】.*$", "", title).strip()
        if not clean_title:
            clean_title = title

        # Entry body
        entry_body = soup.find(class_="p-entry__body")
        body_text = entry_body.get_text(separator="\n", strip=True) if entry_body else soup.get_text()

        if not _is_taiwan_related(body_text):
            return None

        logger.info("uedaeigeki: Taiwan film found: %s", clean_title)

        start_date, end_date = _parse_date_from_body(body_text)
        if not start_date:
            # Fallback: try to parse from title 【M/D~D】
            m = _TITLE_DATE_RE.search(title)
            if m:
                today = datetime.now()
                month = int(m.group(1))
                day = int(m.group(2))
                year = today.year if month >= today.month else today.year + 1
                start_date = datetime(year, month, day)

        raw_description = body_text
        if start_date:
            raw_description = f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n\n" + body_text

        return Event(
            source_name=SOURCE_NAME,
            source_id=f"uedaeigeki_{post_id}",
            source_url=url,
            original_language="ja",
            name_ja=clean_title,
            raw_title=title,
            raw_description=raw_description,
            start_date=start_date,
            end_date=end_date,
            category=["movie"],
        )
