"""
Scraper for Uplink cinema locations (Kichijoji / 吉祥寺).

Static HTML site (WordPress). No Playwright required.

Strategy:
  1. Fetch /movie/ listing page — parse article.list_archive-item cards
  2. For each card, extract title and date text from listing
  3. Fetch detail page — check country in <span class="small">（YEAR／COUNTRY／...）
  4. Taiwan filter: country contains 台湾 or Taiwan
  5. source_id: "uplink_{location_key}_{post_id}" (numeric from URL)

Monitored locations:
  joji     — アップリンク吉祥寺  (東京都武蔵野市吉祥寺)
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from movie_title_lookup import lookup_movie_titles

logger = logging.getLogger(__name__)

# Location config: (listing_url, location_name, location_address, location_key)
LOCATIONS = [
    (
        "https://joji.uplink.co.jp/movie/",
        "アップリンク吉祥寺",
        "東京都武蔵野市吉祥寺本町1-5-1",
        "joji",
    ),
]

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _extract_post_id(url: str) -> Optional[str]:
    """Extract numeric post ID from URL like /movie/2026/31768"""
    m = re.search(r"/(\d+)/?$", url)
    return m.group(1) if m else None


def _parse_date_from_listing(date_text: str, fetch_year: int) -> Optional[datetime]:
    """
    Parse date from listing text like:
      "6月5日（金） 公開"
      "M月D日（曜）～M月D日（曜）【N週間限定上映】"
      "M月D日（曜）公開"
    Returns start_date as datetime.
    """
    m = re.search(r"(\d{1,2})月(\d{1,2})日", date_text)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    # Cross-year: if month < current month by more than 6, use next year
    today = datetime.now()
    year = fetch_year
    if month < today.month - 6:
        year = fetch_year + 1
    elif month > today.month + 6:
        year = fetch_year - 1
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _parse_end_date(date_text: str, start_year: int) -> Optional[datetime]:
    """Parse end date from "M月D日（曜）～M月D日（曜）" ranges."""
    matches = re.findall(r"(\d{1,2})月(\d{1,2})日", date_text)
    if len(matches) >= 2:
        try:
            return datetime(start_year, int(matches[1][0]), int(matches[1][1]), 23, 59, 59)
        except ValueError:
            pass
    return None


def _extract_country_from_detail(soup: BeautifulSoup) -> str:
    """
    Extract all production fields from the production info span, e.g.
    <span class="small">（2024年／台湾／カラー／94分／...）</span>
    or
    <span class="small">（2025年／134分／台湾／カラー）</span>
    Returns the full fields string (after year) for Taiwan keyword matching.
    """
    for span in soup.find_all("span", class_="small"):
        text = span.get_text(strip=True)
        # Pattern: （YEAR年／rest）  — capture ALL fields after year
        m = re.search(r"[（(]\d{4}年?／(.+?)[）)]", text)
        if m:
            return m.group(1)
    return ""


_CAL_DATE_RE = re.compile(r"(\d{1,2})\.(\d{2})([月火水木金土日])")
_CAL_TIME_RE = re.compile(r"(\d{1,2}:\d{2})[–—](\d{1,2}:\d{2})")
_WEEKDAY_JP = {"月": "（月）", "火": "（火）", "水": "（水）", "木": "（木）",
               "金": "（金）", "土": "（土）", "日": "（日）"}


def _extract_schedule_from_detail(
    soup: BeautifulSoup,
    fetch_year: int,
) -> tuple[Optional[str], Optional[datetime]]:
    """
    Parse the "スケジュールとチケット" section from an Uplink detail page.

    Each day is a ``div.list-calendar-wrap`` containing:
      - ``div.list-calendar-header`` → "05.25月"
      - ``div.list-calendar-information`` → "11:50—14:04"

    Returns:
        (business_hours, end_date) where
          business_hours: newline-joined "M/D（曜） HH:MM-HH:MM" lines, or None
          end_date:       UTC midnight of the last scheduled day, or None
    """
    entries: list[tuple[int, int, str, str]] = []  # (month, day, weekday_jp, time)

    for wrap in soup.select("div.list-calendar-wrap"):
        header = wrap.select_one("div.list-calendar-header")
        info = wrap.select_one("div.list-calendar-information")
        if not header or not info:
            continue
        dm = _CAL_DATE_RE.search(header.get_text(strip=True))
        tm = _CAL_TIME_RE.search(info.get_text(strip=True))
        if not dm or not tm:
            continue
        mon, day, wd = int(dm.group(1)), int(dm.group(2)), dm.group(3)
        time_str = f"{tm.group(1)}-{tm.group(2)}"
        entries.append((mon, day, _WEEKDAY_JP.get(wd, f"（{wd}）"), time_str))

    if not entries:
        return None, None

    bh_lines = [f"{mon}/{day}{wd} {t}" for mon, day, wd, t in entries]
    business_hours = "\n".join(bh_lines)

    last_mon, last_day, _, _ = entries[-1]
    try:
        end_date = datetime(fetch_year, last_mon, last_day, tzinfo=timezone.utc)
    except ValueError:
        end_date = None

    return business_hours, end_date



class UplinkCinemaScraper(BaseScraper):
    """Scrapes Taiwan movies from Uplink cinema locations."""

    SOURCE_NAME = "uplink_cinema"

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

    def _scrape_location(
        self,
        listing_url: str,
        location_name: str,
        location_address: str,
        location_key: str,
    ) -> list[Event]:
        events: list[Event] = []

        soup = self._get(listing_url)
        if not soup:
            logger.warning("Failed to fetch listing: %s", listing_url)
            return events

        items = soup.select("article.list_archive-item")
        logger.info("%s: found %d movie cards", location_key, len(items))

        fetch_year = datetime.now().year

        for item in items:
            link_el = item.select_one("a")
            if not link_el:
                continue

            detail_url = link_el.get("href", "")
            if not detail_url:
                continue

            title_el = item.select_one("h1.list_archive-heading")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            date_el = item.select_one("p.list_archive-text")
            date_text = date_el.get_text(strip=True) if date_el else ""

            start_date = _parse_date_from_listing(date_text, fetch_year)
            end_date = _parse_end_date(date_text, start_date.year if start_date else fetch_year)

            post_id = _extract_post_id(detail_url)
            if not post_id:
                continue
            source_id = f"uplink_{location_key}_{post_id}"

            # Fetch detail page to check country
            time.sleep(0.5)
            detail_soup = self._get(detail_url)
            if not detail_soup:
                logger.debug("Could not fetch detail: %s", detail_url)
                continue

            country = _extract_country_from_detail(detail_soup)
            if not _is_taiwan(country):
                # Fallback: check full description text for Taiwan keywords
                detail_text = detail_soup.get_text()
                if not _is_taiwan(detail_text):
                    logger.debug("Skipping non-Taiwan: %s (country=%s)", title, country)
                    continue

            # Extract description from detail page
            desc_el = detail_soup.select_one("div.l-wysiwyg, div.wysiwyg-wrap")
            description = desc_el.get_text(separator="\n", strip=True) if desc_el else ""

            # Extract weekly schedule → business_hours + end_date
            sched_hours, sched_end = _extract_schedule_from_detail(detail_soup, fetch_year)
            resolved_end = sched_end or end_date
            if sched_end:
                logger.info(
                    "Uplink schedule: %s — last day %s, %d time slots",
                    title, sched_end.date(), len((sched_hours or "").splitlines()),
                )

            name_zh, name_en, _ = lookup_movie_titles(title)
            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=detail_url,
                original_language="ja",
                name_ja=title,
                name_zh=name_zh,
                name_en=name_en,
                raw_title=title,
                raw_description=f"会場: {location_name}\n{date_text}\n\n{description}",
                description_ja=description or None,
                category=["movie"],
                start_date=start_date,
                end_date=resolved_end,
                business_hours=sched_hours,
                location_name=location_name,
                location_address=location_address,
                is_paid=True,
            )
            events.append(event)
            logger.info("Found Taiwan movie: %s (country=%s, %s)", title, country, date_text)

        return events

        return events

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        for listing_url, loc_name, loc_addr, loc_key in LOCATIONS:
            loc_events = self._scrape_location(listing_url, loc_name, loc_addr, loc_key)
            events.extend(loc_events)

        logger.info("Total Taiwan movies from Uplink: %d", len(events))
        return events
