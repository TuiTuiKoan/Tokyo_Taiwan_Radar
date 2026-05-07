"""
Scraper for シネマディクト 奈良屋劇場 (Cinemadict / Narayagekijo), Aomori.

Strategy:
  1. Fetch homepage (https://www.cinemadict.com) — parse weekly schedule sections
     '今週' and '来週'; each film block has a '作品詳細' link to /films/{slug}/
  2. Fetch each unique detail page — check full page text for Taiwan keywords
  3. Extract start/end dates from '上映期間：YYYY/MM/DD 〜 YYYY/MM/DD' on listing
  4. source_id: "cinemadict_{slug}" — slug from URL path /films/{slug}/
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.cinemadict.com"
LISTING_URL = BASE_URL  # homepage has weekly schedule
LOCATION_NAME = "シネマディクト 奈良屋劇場"
LOCATION_ADDRESS = "青森県青森市古川1丁目21-18 NARAYAビル3F"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _slug_from_url(url: str) -> str:
    """Extract and URL-decode the film slug from /films/{slug}/"""
    path = urlparse(url).path  # e.g. "/films/%e3%82%b5%e3%83%88..."
    slug = path.rstrip("/").split("/")[-1]
    return unquote(slug)


def _parse_dates(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse '上映期間：2026/04/25 〜 2026/05/08' → (start, end) datetimes."""
    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})\s*[〜~]\s*(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if not m:
        return None, None
    try:
        start = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        end = datetime(int(m.group(4)), int(m.group(5)), int(m.group(6)))
        return start, end
    except ValueError:
        return None, None


class CinemadictScraper(BaseScraper):
    """Scrapes Taiwan-related films from シネマディクト 奈良屋劇場 (Aomori)."""

    SOURCE_NAME = "cinemadict"

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

    def _collect_schedule_entries(self) -> list[dict]:
        """Parse the homepage schedule sections for film entries.

        Returns list of {title, detail_url, date_text} dicts.
        """
        soup = self._get(LISTING_URL)
        if not soup:
            return []

        entries: dict[str, dict] = {}  # url → entry

        # Find all film detail links — they follow /films/ pattern
        for a in soup.select("a[href*='/films/']"):
            href = a.get("href", "")
            if not href or href.endswith("/films/"):
                continue
            full_url = BASE_URL + href if href.startswith("/") else href
            if full_url in entries:
                continue

            # Try to find the date range text in the surrounding container
            # The structure is: film title, 上映期間 text, times, detail link
            parent = a.parent
            date_text = ""
            # Walk up a few levels to find the schedule block
            for _ in range(4):
                if parent is None:
                    break
                block_text = parent.get_text(" ", strip=True)
                if "上映期間" in block_text:
                    date_text = block_text
                    break
                parent = parent.parent

            title_text = a.get_text(strip=True)

            entries[full_url] = {
                "title": title_text if title_text and title_text != "作品詳細" else "",
                "detail_url": full_url,
                "date_text": date_text,
            }

        return list(entries.values())

    def _scrape_detail(self, url: str) -> dict:
        """Fetch detail page; return {title, description, full_text}."""
        result = {"title": "", "description": "", "full_text": ""}
        soup = self._get(url)
        if not soup:
            return result

        h1 = soup.find("h1") or soup.find("h2")
        if h1:
            result["title"] = h1.get_text(strip=True)

        # Description from entry-content or similar
        content_el = (
            soup.select_one(".entry-content")
            or soup.select_one("article")
            or soup.select_one("main")
        )
        if content_el:
            paras = [p.get_text(strip=True) for p in content_el.select("p") if p.get_text(strip=True)]
            result["description"] = "\n".join(paras[:6])

        result["full_text"] = soup.get_text(" ", strip=True)
        return result

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        schedule_entries = self._collect_schedule_entries()
        logger.info("Found %d film schedule entries", len(schedule_entries))

        for entry in schedule_entries:
            detail_url = entry["detail_url"]
            time.sleep(0.5)
            detail = self._scrape_detail(detail_url)

            if not _is_taiwan(detail["full_text"]):
                logger.debug("Skipping non-Taiwan film: %s", detail["title"] or entry["title"])
                continue

            slug = _slug_from_url(detail_url)
            source_id = f"cinemadict_{slug}"
            title = detail["title"] or entry["title"] or slug

            date_text = entry["date_text"]
            start_date, end_date = _parse_dates(date_text)

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
