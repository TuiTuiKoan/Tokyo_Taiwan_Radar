"""
Scraper for シアターエンヤ (Theater Enya), Karatsu, Saga.

Strategy:
  1. Fetch https://theater-enya.com/films — listing of current and upcoming films
     Each film is a link: a[href^='https://theater-enya.com/films/']
     Link text: "新作料金 G 上映時間：93分 湯徳章―私は誰なのか― 上映期間 5月9日（土）〜5月14日（木）"
  2. For each unique film detail page, check for Taiwan keywords
     Detail page text: "2024年製作／93分／G／台湾"
  3. Extract title from detail h2, dates from listing link text or detail page
  4. source_id: "theater_enya_{slug}" — slug from /films/{slug}
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

BASE_URL = "https://theater-enya.com"
LISTING_URL = f"{BASE_URL}/films"
LOCATION_NAME = "シアターエンヤ"
LOCATION_ADDRESS = "佐賀県唐津市呉服町1513-1"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]
# Month abbreviation pattern: 5月9日（土）
_DATE_PAT = re.compile(r"(\d+)月(\d+)日")


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _slug_from_url(url: str) -> str:
    return urlparse(url).path.rstrip("/").split("/")[-1]


def _parse_enya_dates(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse '上映期間 5月9日（土）〜5月14日（木）' → (start, end)."""
    m = re.search(r"上映期間\s+(\d+)月(\d+)日[^〜]*[〜~](\d+)月(\d+)日", text)
    if not m:
        return None, None
    year = datetime.now().year
    try:
        start = datetime(year, int(m.group(1)), int(m.group(2)))
        end = datetime(year, int(m.group(3)), int(m.group(4)))
        # Handle year rollover for December→January
        if end < start:
            end = datetime(year + 1, int(m.group(3)), int(m.group(4)))
        return start, end
    except ValueError:
        return None, None


class TheaterEnyaScraper(BaseScraper):
    """Scrapes Taiwan-related films from シアターエンヤ (Karatsu, Saga)."""

    SOURCE_NAME = "theater_enya"

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

    def _collect_listing(self) -> list[dict]:
        """Parse /films listing page → list of {url, link_text} dicts."""
        soup = self._get(LISTING_URL)
        if not soup:
            return []

        entries: dict[str, dict] = {}
        for a in soup.select(f"a[href^='{BASE_URL}/films/']"):
            href = a.get("href", "")
            slug = _slug_from_url(href)
            if not slug or slug == "films":
                continue
            if href in entries:
                continue
            entries[href] = {
                "url": href,
                "link_text": a.get_text(" ", strip=True),
            }
        return list(entries.values())

    def _scrape_detail(self, url: str) -> dict:
        result = {"title": "", "description": "", "full_text": "", "production_line": ""}
        soup = self._get(url)
        if not soup:
            return result

        h2 = soup.find("h2")
        if h2:
            result["title"] = h2.get_text(strip=True)

        # Look for production line like "2024年製作／93分／G／台湾"
        full_text = soup.get_text(" ", strip=True)
        m = re.search(r"\d{4}年製作[／/][^\n]{0,60}", full_text)
        if m:
            result["production_line"] = m.group(0)

        # Description from main paragraphs
        content = soup.select_one("main") or soup.select_one("article") or soup
        paras = [p.get_text(strip=True) for p in content.select("p") if len(p.get_text(strip=True)) > 15]
        result["description"] = "\n".join(paras[:6])

        result["full_text"] = full_text
        return result

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        listing = self._collect_listing()
        logger.info("Found %d film links on listing page", len(listing))

        for entry in listing:
            url = entry["url"]
            link_text = entry["link_text"]
            time.sleep(0.5)
            detail = self._scrape_detail(url)

            # Taiwan check: production line or full text
            check_text = detail["production_line"] + " " + detail["full_text"]
            if not _is_taiwan(check_text):
                logger.debug("Skipping non-Taiwan film: %s", detail["title"])
                continue

            slug = _slug_from_url(url)
            source_id = f"theater_enya_{slug}"
            title = detail["title"] or slug

            start_date, end_date = _parse_enya_dates(link_text)
            # Fallback: look in detail page full text
            if not start_date:
                start_date, end_date = _parse_enya_dates(detail["full_text"])

            raw_desc = detail["description"]
            if detail["production_line"]:
                raw_desc = detail["production_line"] + "\n\n" + raw_desc
            if start_date:
                raw_desc = (
                    f"上映期間: {start_date.strftime('%Y年%m月%d日')}"
                    + (f"〜{end_date.strftime('%Y年%m月%d日')}" if end_date else "")
                    + "\n\n" + raw_desc
                )

            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=url,
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
