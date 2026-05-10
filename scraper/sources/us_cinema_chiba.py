"""
Scraper for USシネマ・千葉劇場 (US Cinema Chiba Gekijo), Chiba City.

Strategy:
  1. Fetch the next 7 days of schedule via ?date=YYYY-MM-DD
  2. For each day, extract h4.pull-left film titles
  3. Check each title for Taiwan keywords
  4. source_id: us_cinema_chiba_{md5(title+date)[:10]} (title is stable per film period)
     Use just title hash since the same film runs for weeks.
"""

import hashlib
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://uscinemas.jp/category/chibagekijo/"
LOCATION_NAME = "USシネマ・千葉劇場"
LOCATION_ADDRESS = "千葉県千葉市中央区富士見2丁目3-1"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan", "臺灣"]
SCAN_DAYS = 8  # Scan today + 7 future days


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _source_id(title: str) -> str:
    # Strip time/duration info to make ID stable
    clean = re.sub(r"\[.*?\]", "", title).strip()
    digest = hashlib.md5(clean.encode("utf-8")).hexdigest()[:10]
    return f"us_cinema_chiba_{digest}"


def _parse_date_from_nav(soup: BeautifulSoup) -> Optional[datetime]:
    """Parse the current display date from h3 or #box-title."""
    box = soup.select_one("#box-title, .box-title")
    if box:
        text = box.get_text(strip=True)
        m = re.search(r"(\d{2})月(\d{2})日", text)
        if m:
            year = datetime.now().year
            try:
                return datetime(year, int(m.group(1)), int(m.group(2)))
            except ValueError:
                pass
    # Fallback: h3 at top of schedule
    h3 = soup.select_one("h3:not(.scheduleh3)")
    if h3:
        text = h3.get_text(strip=True)
        m = re.search(r"(\d{2})月(\d{2})日", text)
        if m:
            year = datetime.now().year
            try:
                return datetime(year, int(m.group(1)), int(m.group(2)))
            except ValueError:
                pass
    return None


class UsCinemaChibaGekijoScraper(BaseScraper):
    """Scrapes Taiwan-related films from USシネマ・千葉劇場."""

    SOURCE_NAME = "us_cinema_chiba"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })

    def _fetch_day(self, date: datetime) -> list[tuple[str, datetime]]:
        """Fetch film titles for one day. Returns list of (title, date)."""
        date_str = date.strftime("%Y-%m-%d")
        url = f"{BASE_URL}?date={date_str}#Schedules"
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("USCinema fetch %s failed: %s", date_str, exc)
            return []

        soup = BeautifulSoup(resp.content, "html.parser")
        results = []
        for h4 in soup.select("h4.pull-left"):
            title = h4.get_text(strip=True)
            if title and _is_taiwan(title):
                results.append((title, date))
        return results

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        seen_ids: set[str] = set()

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(SCAN_DAYS):
            check_date = today + timedelta(days=i)
            matches = self._fetch_day(check_date)
            for title, date in matches:
                sid = _source_id(title)
                if sid in seen_ids:
                    continue
                seen_ids.add(sid)

                # Clean title (strip duration info like [本編:106分])
                clean_title = re.sub(r"\[.*?\]", "", title).strip()

                event = Event(
                    source_name=self.SOURCE_NAME,
                    source_id=sid,
                    source_url=BASE_URL,
                    original_language="ja",
                    name_ja=clean_title,
                    raw_title=title,
                    raw_description=clean_title,
                    category=["art"],
                    start_date=date,
                    location_name=LOCATION_NAME,
                    location_address=LOCATION_ADDRESS,
                )
                events.append(event)
                logger.info("USCinema Chiba: %s on %s", clean_title, check_date.date())

            time.sleep(0.3)

        logger.info("USCinema Chiba total: %d Taiwan events", len(events))
        return events
