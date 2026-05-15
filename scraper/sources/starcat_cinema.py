"""
Scraper for スターキャット 伏見ミリオン座 & センチュリーシネマ (Nagoya), by STARCAT Co.

Both venues share one website: https://eiga.starcat.co.jp/

Strategy:
  1. Fetch https://eiga.starcat.co.jp/schedule/ — all film cards
     Each card is: a[href*='/schedule/detail/?thumbnail=']
     Link text starts with theater name: '伏見ミリオン座 ' or 'センチュリーシネマ '
  2. Deduplicate by thumbnail ID; record theater name from link text prefix
  3. Fetch each detail page — check full text for Taiwan keywords (台湾/台灣/Taiwan)
     Detail pages have: title in h1 "(XX分)", date text, description, copyright
  4. source_id: "starcat_{thumbnail_id}"
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

BASE_URL = "https://eiga.starcat.co.jp"
LISTING_URL = f"{BASE_URL}/schedule/"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]

THEATER_LOCATIONS = {
    "伏見ミリオン座": {
        "name": "伏見ミリオン座",
        "address": "愛知県名古屋市中区栄1-12-12",
    },
    "センチュリーシネマ": {
        "name": "センチュリーシネマ",
        "address": "愛知県名古屋市中区栄3-15-13 スカイルビル地下2F",
    },
}
DEFAULT_LOCATION = {
    "name": "伏見ミリオン座・センチュリーシネマ",
    "address": "愛知県名古屋市",
}

# starcat-ticket.com schedule pages (weekly timetable with HH:MM slots)
TICKET_SCHEDULE_URLS = {
    "伏見ミリオン座": "https://www.starcat-ticket.com/fm/theater/million/schedule",
    "センチュリーシネマ": "https://www.starcat-ticket.com/cc/theater/century/schedule",
}

_WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _parse_thumbnail_id(href: str) -> Optional[str]:
    m = re.search(r"thumbnail=(\d+)", href)
    return m.group(1) if m else None


def _parse_theater(link_text: str) -> str:
    for theater in THEATER_LOCATIONS:
        if link_text.startswith(theater):
            return theater
    return ""


def _parse_date(text: str) -> Optional[datetime]:
    """Parse '2026年5月22日(金)より公開' or '上映中' → datetime or None."""
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _normalize_title(title: str) -> str:
    """Normalize title for fuzzy matching: collapse whitespace, strip."""
    return re.sub(r"\s+", " ", title).strip()


class StarcatCinemaScraper(BaseScraper):
    """Scrapes Taiwan-related films from 伏見ミリオン座 and センチュリーシネマ (Nagoya)."""

    SOURCE_NAME = "starcat_cinema"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })
        # Cache: theater → {normalized_title: business_hours_string}
        self._ticket_schedule_cache: dict[str, dict[str, str]] = {}

    def _get(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as exc:
            logger.warning("GET %s failed: %s", url, exc)
            return None

    def _build_ticket_schedule(self, theater: str) -> dict[str, str]:
        """Fetch weekly timetable from starcat-ticket.com for the given theater.

        Returns: {normalized_title: business_hours_string}
        where business_hours_string is multi-line, one day per line:
            "5/15(金): 12:05〜13:49\n5/16(土): 12:05〜13:49\n..."
        """
        if theater in self._ticket_schedule_cache:
            return self._ticket_schedule_cache[theater]

        ticket_url = TICKET_SCHEDULE_URLS.get(theater, "")
        if not ticket_url:
            return {}

        soup = self._get(ticket_url)
        if not soup:
            return {}

        # Step 1: title div → panel ID → film_id
        title_to_film_id: dict[str, str] = {}
        for title_div in soup.find_all("div", class_="schedule-title"):
            title_norm = _normalize_title(title_div.get_text(strip=True))
            if not title_norm or title_norm in title_to_film_id:
                continue
            anchor = title_div.find_parent("a")
            if not anchor:
                continue
            panel_target = (
                anchor.get("data-target") or anchor.get("href") or ""
            ).lstrip("#")
            m = re.match(r"schedule\d{8}(\d+)-\d+", panel_target)
            if m:
                title_to_film_id[title_norm] = m.group(1)

        # Step 2: film_id → {YYYYMMDD: [time_ranges]}
        result: dict[str, str] = {}
        for title_norm, film_id in title_to_film_id.items():
            film_panels = soup.find_all(
                "div", id=re.compile(rf"schedule\d{{8}}{re.escape(film_id)}-\d+")
            )
            day_slots: dict[str, list[str]] = {}
            for panel_div in film_panels:
                pm = re.match(
                    rf"schedule(\d{{8}}){re.escape(film_id)}-\d+",
                    panel_div.get("id", ""),
                )
                if not pm:
                    continue
                date_key = pm.group(1)
                time_matches = re.findall(
                    r"(\d+:\d+)\s*～\s*(\d+:\d+)",
                    panel_div.get_text(" ", strip=True),
                )
                for start_t, end_t in time_matches:
                    day_slots.setdefault(date_key, []).append(
                        f"{start_t}〜{end_t}"
                    )

            if not day_slots:
                continue

            lines = []
            for date_key in sorted(day_slots.keys()):
                try:
                    dt = datetime.strptime(date_key, "%Y%m%d")
                    wd = _WEEKDAYS[dt.weekday()]
                    label = f"{dt.month}/{dt.day}({wd})"
                except ValueError:
                    label = date_key
                slots = "、".join(day_slots[date_key])
                lines.append(f"{label}: {slots}")

            result[title_norm] = "\n".join(lines)

        self._ticket_schedule_cache[theater] = result
        logger.info(
            "Ticket schedule for %s: %d films parsed", theater, len(result)
        )
        return result

    def _lookup_business_hours(self, theater: str, title: str) -> Optional[str]:
        """Look up business_hours string for a film by fuzzy-matching its title."""
        schedule = self._build_ticket_schedule(theater)
        if not schedule:
            return None
        title_norm = _normalize_title(title)
        # Exact match first
        if title_norm in schedule:
            return schedule[title_norm]
        # Fuzzy: check if first 4 chars match
        prefix = title_norm[:4]
        for key, val in schedule.items():
            if prefix and prefix in key:
                return val
        return None
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as exc:
            logger.warning("GET %s failed: %s", url, exc)
            return None

    def _collect_listing(self) -> list[dict]:
        """Returns list of {thumbnail_id, detail_url, theater, link_text}."""
        soup = self._get(LISTING_URL)
        if not soup:
            return []

        entries: dict[str, dict] = {}
        for a in soup.select("a[href*='/schedule/detail/?thumbnail=']"):
            href = a.get("href", "")
            tid = _parse_thumbnail_id(href)
            if not tid or tid in entries:
                continue
            link_text = a.get_text(" ", strip=True)
            theater = _parse_theater(link_text)
            full_url = BASE_URL + href if href.startswith("/") else href
            entries[tid] = {
                "thumbnail_id": tid,
                "detail_url": full_url,
                "theater": theater,
                "link_text": link_text,
            }
        return list(entries.values())

    def _scrape_detail(self, url: str) -> dict:
        result = {"title": "", "description": "", "full_text": "", "date_text": "", "theater": ""}
        soup = self._get(url)
        if not soup:
            return result

        full_text = soup.get_text(" ", strip=True)
        result["full_text"] = full_text

        # Title from h1 — strip "(XX分)" suffix
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
            title = re.sub(r"\(\d+分.*?\)$", "", title).strip()
            result["title"] = title

        # Date text: "YYYY年M月D日(曜)より公開" or "上映中"
        m = re.search(r"\d{4}年\d+月\d+日[^よ]*より公開", full_text)
        if m:
            result["date_text"] = m.group(0)
        elif "上映中" in full_text:
            result["date_text"] = "上映中"

        # Theater: look in breadcrumb area at bottom
        # Breadcrumb typically: "上映作品 > {title} > {theater}"
        for theater in THEATER_LOCATIONS:
            if theater in full_text:
                result["theater"] = theater
                break

        # Description: main body paragraphs (excluding nav/footer)
        main = soup.select_one("main") or soup.select_one("article")
        if main:
            paras = [p.get_text(strip=True) for p in main.select("p") if len(p.get_text(strip=True)) > 20]
            result["description"] = "\n".join(paras[:5])
        if not result["description"]:
            # Fallback: look for divs with enough text
            paras = [p.get_text(strip=True) for p in soup.select("p") if len(p.get_text(strip=True)) > 40]
            result["description"] = "\n".join(paras[:4])

        return result

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        listing = self._collect_listing()
        logger.info("Found %d unique film cards on listing page", len(listing))

        for entry in listing:
            # Quick pre-filter: check listing link text for Taiwan keywords
            # to avoid fetching all detail pages (most won't be Taiwan films)
            link_text = entry["link_text"]
            if not _is_taiwan(link_text):
                # Need to fetch detail for full text check
                pass  # will check after fetching

            tid = entry["thumbnail_id"]
            detail_url = entry["detail_url"]
            theater = entry["theater"]

            time.sleep(0.5)
            detail = self._scrape_detail(detail_url)

            # Use theater from detail page if listing didn't have it
            if not theater and detail["theater"]:
                theater = detail["theater"]

            check_text = detail["full_text"]
            if not _is_taiwan(check_text):
                logger.debug("Skipping non-Taiwan film: %s", detail["title"])
                continue

            source_id = f"starcat_{tid}"
            title = detail["title"] or entry["link_text"].split()[1] if entry["link_text"] else f"film_{tid}"

            start_date = _parse_date(detail["date_text"])

            loc = THEATER_LOCATIONS.get(theater, DEFAULT_LOCATION)
            raw_desc = detail["description"]
            if detail["date_text"]:
                raw_desc = detail["date_text"] + "\n\n" + raw_desc

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
                end_date=None,
                location_name=loc["name"],
                location_address=loc["address"],
                business_hours=self._lookup_business_hours(theater, title),
            )
            events.append(event)
            logger.info("Found Taiwan film: %s (theater=%s)", title, theater)

        logger.info("Total Taiwan films found: %d", len(events))
        return events
