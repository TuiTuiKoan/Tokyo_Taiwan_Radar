"""
Scraper for 山口情報芸術センター YCAM シネマ (YCAM Cinema), Yamaguchi.

Strategy:
  1. Fetch https://www.ycam.jp/cinema/{year}/ — list of cinema programs
     Each program is a thematic selection of 1–5 films with a date range
  2. For each program link a[href*='/cinema/{year}/'], check:
     a. Program title text for Taiwan keywords (fast pre-filter)
     b. If yes: fetch detail page for full description and film list
  3. Create one event per program that has Taiwan content
  4. source_id: "ycam_{slug}_{year}" — e.g. "ycam_life-in-taiwanese-society_2026"
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ycam.jp"
CURRENT_YEAR = datetime.now().year
LISTING_URLS = [
    f"{BASE_URL}/cinema/{CURRENT_YEAR}/",
    f"{BASE_URL}/cinema/{CURRENT_YEAR + 1}/",  # next year if programs listed early
]
LOCATION_NAME = "山口情報芸術センター YCAM"
LOCATION_ADDRESS = "山口県山口市中園町7-7"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _slug_from_url(url: str) -> str:
    path = urlparse(url).path  # e.g. /cinema/2026/life-in-taiwanese-society/
    return path.rstrip("/").split("/")[-1]


def _parse_ycam_dates(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse 'YYYY年M月D日（曜）〜M月D日（曜）' → (start, end)."""
    m = re.search(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日[^〜]*[〜~](\d{1,2})月(\d{1,2})日",
        text,
    )
    if not m:
        return None, None
    y = int(m.group(1))
    try:
        start = datetime(y, int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        end = datetime(y, int(m.group(4)), int(m.group(5)), tzinfo=timezone.utc)
        if end < start:
            end = datetime(y + 1, int(m.group(4)), int(m.group(5)), tzinfo=timezone.utc)
        return start, end
    except ValueError:
        return None, None


class YcamCinemaScraper(BaseScraper):
    """Scrapes Taiwan-related cinema programs from YCAM (Yamaguchi)."""

    SOURCE_NAME = "ycam_cinema"

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
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as exc:
            logger.warning("GET %s failed: %s", url, exc)
            return None

    def _collect_program_links(self) -> list[dict]:
        """Return list of {url, link_text} for all cinema programs."""
        programs: dict[str, dict] = {}
        for listing_url in LISTING_URLS:
            soup = self._get(listing_url)
            if not soup:
                continue
            for a in soup.select("a[href*='/cinema/']"):
                href = a.get("href", "")
                # Exclude nav/pagination links; keep only program detail links
                if not re.search(r"/cinema/\d{4}/\w", href):
                    continue
                full = BASE_URL + href if href.startswith("/") else href
                if full in programs:
                    continue
                programs[full] = {
                    "url": full,
                    "link_text": a.get_text(" ", strip=True),
                }
        return list(programs.values())

    def _scrape_detail(self, url: str) -> dict:
        result = {"title": "", "description": "", "full_text": "", "date_text": ""}
        soup = self._get(url)
        if not soup:
            return result

        h1 = soup.find("h1")
        if h1:
            result["title"] = h1.get_text(strip=True)

        full_text = soup.get_text(" ", strip=True)
        result["full_text"] = full_text

        # Date: "上映期間：YYYY年M月D日（曜）〜M月D日（曜）"
        m = re.search(r"上映期間[：:]\s*(\d{4}年\d+月\d+日[^〜]*[〜~]\d+月\d+日)", full_text)
        if m:
            result["date_text"] = m.group(1)
        else:
            # Also try from the basic info table
            m2 = re.search(r"(\d{4}年\d+月\d+日[^〜]*[〜~]\d+月\d+日)", full_text)
            if m2:
                result["date_text"] = m2.group(1)

        # Description: intro text before 上映作品 section
        content = soup.select_one("main") or soup.select_one("article") or soup
        paras = [p.get_text(strip=True) for p in content.select("p") if len(p.get_text(strip=True)) > 20]
        result["description"] = "\n".join(paras[:6])

        return result

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        programs = self._collect_program_links()
        logger.info("Found %d cinema program links", len(programs))

        for prog in programs:
            url = prog["url"]
            link_text = prog["link_text"]

            # Fast pre-filter: check link text for Taiwan keywords
            if not _is_taiwan(link_text):
                # Still need to fetch detail for full Taiwan check
                time.sleep(0.3)
                detail = self._scrape_detail(url)
                if not _is_taiwan(detail["full_text"]):
                    logger.debug("Skipping non-Taiwan program: %s", link_text[:40])
                    continue
            else:
                time.sleep(0.5)
                detail = self._scrape_detail(url)

            slug = _slug_from_url(url)
            year = re.search(r"/cinema/(\d{4})/", url)
            year_str = year.group(1) if year else str(CURRENT_YEAR)
            source_id = f"ycam_{slug}_{year_str}"
            title = detail["title"] or link_text.split()[0] if link_text else slug

            start_date, end_date = _parse_ycam_dates(detail["date_text"])
            if not start_date:
                # Try from link text
                start_date, end_date = _parse_ycam_dates(link_text)

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
            logger.info("Found Taiwan cinema program: %s", title)

        logger.info("Total Taiwan programs found: %d", len(events))
        return events
