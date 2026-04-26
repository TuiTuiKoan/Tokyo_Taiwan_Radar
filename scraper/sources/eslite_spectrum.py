"""
Scraper for 誠品生活日本橋 (eslite spectrum Nihonbashi).

eslite spectrum is a Taiwanese cultural bookstore/event space in Nihonbashi
COREDO Muromachi Terrace 2F, Tokyo. It hosts Taiwan-themed book launches,
art exhibitions, and cultural events.

Strategy:
  1. Fetch /news listing page (static HTML)
  2. Collect all /news/catalog/{id} links with their published dates and titles
  3. For each item, check if title OR detail page body contains Taiwan keywords
  4. Extract structured event data from the detail page

Dedup key: eslite_spectrum_{catalog_id}
  e.g. /news/catalog/9 → eslite_spectrum_9
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.eslitespectrum.jp"
NEWS_URL = f"{BASE_URL}/news"

LOCATION_NAME = "誠品生活日本橋"
LOCATION_ADDRESS = "東京都中央区日本橋室町3-2-1 COREDO室町テラス2F"

# Keywords checked against TITLE + MAIN CONTENT only (not page nav/footer).
# "誠品" appears in every page's navigation — intentionally excluded here.
TAIWAN_KEYWORDS = [
    "台湾", "Taiwan", "臺灣", "台灣",
    "台北", "高雄", "台中", "台南",
    "台日", "日台",
]

# Patterns in title that clearly indicate non-event administrative content
_SKIP_TITLE_RE = re.compile(
    r"会員募集|メンバーズカード|ワークショップカレンダー|ポイント|お知らせ|営業時間|定休日|リニューアル"
)

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_CATALOG_ID_RE = re.compile(r"/news/catalog/(\d+)")


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    m = _DATE_RE.search(raw)
    if m:
        try:
            return datetime.strptime(m.group(0), "%Y-%m-%d")
        except ValueError:
            pass
    return None


class EsliteSpectrumScraper(BaseScraper):
    """Scrapes Taiwan-related events from 誠品生活日本橋 (eslite spectrum Nihonbashi)."""

    SOURCE_NAME = "eslite_spectrum"

    def scrape(self) -> list[Event]:
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en;q=0.9",
        })

        article_items = self._collect_articles(session)
        logger.info("eslite_spectrum: found %d news items on listing page", len(article_items))

        events: list[Event] = []
        for item in article_items:
            try:
                event = self._scrape_detail(session, item)
                if event:
                    events.append(event)
                time.sleep(0.8)
            except Exception as exc:
                logger.error("eslite_spectrum: failed to scrape %s: %s", item["url"], exc)

        logger.info("eslite_spectrum: collected %d Taiwan-related events", len(events))
        return events

    def _collect_articles(self, session: requests.Session) -> list[dict]:
        """Fetch the /news listing and return [{url, catalog_id, date_str, list_title}]."""
        items: list[dict] = []
        seen_ids: set[str] = set()

        try:
            resp = session.get(NEWS_URL, timeout=15)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("eslite_spectrum: failed to fetch %s: %s", NEWS_URL, exc)
            return items

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find all anchors linking to /news/catalog/N
        for a in soup.find_all("a", href=_CATALOG_ID_RE):
            href = a.get("href", "")
            m = _CATALOG_ID_RE.search(href)
            if not m:
                continue
            catalog_id = m.group(1)
            if catalog_id in seen_ids:
                continue
            seen_ids.add(catalog_id)

            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"

            # Extract title: use the link with non-empty text
            title_text = a.get_text(strip=True)
            if not title_text:
                # This is the image-link anchor; look for a sibling anchor with text
                parent = a.parent
                if parent:
                    for sibling in parent.find_all("a", href=_CATALOG_ID_RE):
                        sib_text = sibling.get_text(strip=True)
                        if sib_text:
                            title_text = sib_text
                            break

            # Extract date from surrounding text in the parent container
            parent = a.parent
            parent_text = parent.get_text(separator=" ", strip=True) if parent else ""
            date_str = ""
            dm = _DATE_RE.search(parent_text)
            if dm:
                date_str = dm.group(0)

            items.append({
                "url": full_url,
                "catalog_id": catalog_id,
                "date_str": date_str,
                "list_title": title_text,
            })

        return items

    def _scrape_detail(self, session: requests.Session, item: dict) -> Optional[Event]:
        """Fetch a detail page and return an Event if Taiwan-related."""
        url = item["url"]

        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("eslite_spectrum: GET %s failed: %s", url, exc)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # --- Extract title ---
        # Detail page has the title in an <h2> (or <h1> as fallback)
        title_el = soup.find("h2") or soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else item["list_title"]
        if not title:
            title = item["list_title"]

        # --- Extract date from detail page (more reliable than listing page) ---
        date_str = item["date_str"]
        # The detail page shows the date just above the h2: <YYYY-MM-DD>
        page_text = soup.get_text(separator="\n")
        dm = _DATE_RE.search(page_text)
        if dm:
            date_str = dm.group(0)

        # --- Extract description ---
        # Try main content area; fall back to full page text
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"content|body|detail", re.I))
        )
        description = main.get_text(separator="\n", strip=True) if main else page_text.strip()

        # --- Taiwan relevance check (against title + MAIN CONTENT only, not nav) ---
        # This avoids matching 誠品 which appears in every page's navigation.
        content_text = f"{title}\n{description}"
        if _SKIP_TITLE_RE.search(title):
            logger.debug("eslite_spectrum: skipping admin item %s (%s)", title, url)
            return None
        if not any(kw in content_text for kw in TAIWAN_KEYWORDS):
            logger.debug("eslite_spectrum: skipping non-Taiwan item %s (%s)", title, url)
            return None

        start_date = _parse_date(date_str)
        if start_date:
            description = f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n\n{description}"

        catalog_id = item["catalog_id"]

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=f"eslite_spectrum_{catalog_id}",
            source_url=url,
            original_language="ja",
            name_ja=title,
            raw_title=title,
            raw_description=description,
            start_date=start_date,
            end_date=start_date,
            category=["community"],
            location_name=LOCATION_NAME,
            location_address=LOCATION_ADDRESS,
        )
