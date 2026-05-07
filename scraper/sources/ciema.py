"""
Scraper for シエマ (CIEMA), Saga City arthouse cinema.

Strategy:
  1. Parse two weekly schedule tables on homepage (this week + next week)
  2. Check film title in each table row for Taiwan keywords
  3. Also check special event h3 headings for Taiwan content
  4. Date: from h3 header before each table (YYYY.M.D(曜)～M.D(曜))
  5. source_id: ciema_{md5(title)[:10]}
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

LISTING_URL = "http://ciema.info"
LOCATION_NAME = "シエマ"
LOCATION_ADDRESS = "佐賀県佐賀市"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan", "臺灣"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _source_id(title: str) -> str:
    digest = hashlib.md5(title.encode("utf-8")).hexdigest()[:10]
    return f"ciema_{digest}"


def _parse_week_header(header_text: str) -> Optional[datetime]:
    """Parse '2026.5.8(金)～5.14(木)の上映スケジュール' → start date."""
    m = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", header_text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _parse_week_end(header_text: str, start: datetime) -> Optional[datetime]:
    """Parse end date like '5.14(木)' from header."""
    m = re.search(r"[～〜](\d{1,2})\.(\d{1,2})", header_text)
    if m and start:
        mo, day = int(m.group(1)), int(m.group(2))
        yr = start.year
        try:
            return datetime(yr, mo, day)
        except ValueError:
            pass
    return None


def _scrape_tables(soup: BeautifulSoup) -> list[Event]:
    events = []
    tables = soup.select("table")

    for table in tables:
        # Find the h3 header immediately before or near this table
        header_tag = table.find_previous("h3")
        week_text = header_tag.get_text(strip=True) if header_tag else ""
        start_date = _parse_week_header(week_text)
        end_date = _parse_week_end(week_text, start_date) if start_date else None

        for tr in table.select("tr"):
            cells = tr.select("td")
            if not cells:
                continue
            title_cell = cells[0]
            title = title_cell.get_text(strip=True)
            # Skip header rows and placeholder rows
            if not title or len(title) < 3 or not _is_taiwan(title):
                continue

            # Get schedule info from 3rd cell if present
            schedule_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""

            link = title_cell.select_one("a[href]")
            source_url = link.get("href") if link else LISTING_URL

            raw_desc = f"上映スケジュール: {schedule_text}\n{week_text}" if schedule_text else title

            event = Event(
                source_name="ciema",
                source_id=_source_id(title),
                source_url=source_url or LISTING_URL,
                original_language="ja",
                name_ja=title,
                raw_title=title,
                raw_description=raw_desc,
                description_ja=raw_desc,
                category=["art"],
                start_date=start_date,
                end_date=end_date,
                location_name=LOCATION_NAME,
                location_address=LOCATION_ADDRESS,
            )
            events.append(event)
            logger.info("ciema table event: %s", title)

    return events


def _scrape_events_section(soup: BeautifulSoup) -> list[Event]:
    """Scrape special event h3 headings with Taiwan keywords."""
    events = []
    for h3 in soup.select("h3"):
        text = h3.get_text(strip=True)
        if not _is_taiwan(text):
            continue

        # Get event link
        link = h3.select_one("a[href]")
        if not link:
            # Check next sibling for link
            sib = h3.find_next_sibling()
            if sib:
                link = sib.select_one("a[href]")

        source_url = link.get("href") if link else LISTING_URL

        # Parse date from h3 text
        start_date = None
        # Patterns: 5/16(土), 5月16日, M.D(曜)
        m = re.search(r"(\d{1,2})[/．](\d{1,2})[（\(][日月火水木金土]", text)
        if m:
            year = datetime.now().year
            mo, day = int(m.group(1)), int(m.group(2))
            try:
                candidate = datetime(year, mo, day)
                if candidate < datetime.now().replace(month=1, day=1):
                    candidate = datetime(year + 1, mo, day)
                start_date = candidate
            except ValueError:
                pass

        event = Event(
            source_name="ciema",
            source_id=_source_id(text),
            source_url=source_url or LISTING_URL,
            original_language="ja",
            name_ja=text,
            raw_title=text,
            raw_description=text,
            description_ja=text,
            category=["art"],
            start_date=start_date,
            location_name=LOCATION_NAME,
            location_address=LOCATION_ADDRESS,
        )
        events.append(event)
        logger.info("ciema event: %s", text)

    return events


class CiemaScraper(BaseScraper):
    """Scrapes Taiwan-related films/events from シエマ (Saga City)."""

    SOURCE_NAME = "ciema"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })

    def scrape(self) -> list[Event]:
        try:
            resp = self._session.get(LISTING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Failed to fetch ciema: %s", exc)
            return []

        soup = BeautifulSoup(resp.content, "html.parser")

        table_events = _scrape_tables(soup)
        event_section = _scrape_events_section(soup)

        # Deduplicate by source_id
        seen: set[str] = set()
        all_events: list[Event] = []
        for ev in table_events + event_section:
            if ev.source_id not in seen:
                seen.add(ev.source_id)
                all_events.append(ev)

        logger.info("ciema total events: %d", len(all_events))
        return all_events
