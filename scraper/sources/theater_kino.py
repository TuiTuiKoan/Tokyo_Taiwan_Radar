"""
Scraper for シアターキノ (Theater Kino), Sapporo, Hokkaido.

Strategy:
  1. Fetch https://www.theaterkino.net/sakuhin.html — static HTML film listing
     Each film block: paragraph starting with "■" + title + "(YYYY年/国名/[言語/]分数)"
     Followed by a table with date range and details
  2. Extract country from the parenthetical: (YYYY年/台湾/...) → matches Taiwan
  3. Extract date range from table cell: "M/D(曜)⇒M/D(曜)" or "M/D(曜)〜M/D(曜)"
  4. source_id: "theater_kino_{slug}" where slug is ASCII-safe title hash
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.theaterkino.net"
LISTING_URL = f"{BASE_URL}/sakuhin.html"
LOCATION_NAME = "シアターキノ"
LOCATION_ADDRESS = "北海道札幌市中央区南3条西6丁目1番地 ゴトウビル地下2F"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _make_slug(title: str) -> str:
    """Create a short stable slug from film title."""
    return hashlib.md5(title.encode("utf-8")).hexdigest()[:10]


def _parse_dates(date_text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse date range from text like '4/3(金)⇒5/8(金)' or '6/13(土)～6/26(金)'."""
    current_year = datetime.now().year
    m = re.search(
        r"(\d{1,2})/(\d{1,2})[^⇒〜～\d]*[⇒〜～](\d{1,2})/(\d{1,2})",
        date_text,
    )
    if not m:
        # Try single date / open-ended: "M/D(曜)～ロードショー"
        m2 = re.search(r"(\d{1,2})/(\d{1,2})", date_text)
        if m2:
            try:
                start = datetime(current_year, int(m2.group(1)), int(m2.group(2)), tzinfo=timezone.utc)
                return start, None
            except ValueError:
                pass
        return None, None
    try:
        s_m, s_d = int(m.group(1)), int(m.group(2))
        e_m, e_d = int(m.group(3)), int(m.group(4))
        start = datetime(current_year, s_m, s_d, tzinfo=timezone.utc)
        end_year = current_year if e_m >= s_m else current_year + 1
        end = datetime(end_year, e_m, e_d, tzinfo=timezone.utc)
        return start, end
    except ValueError:
        return None, None


class TheaterKinoScraper(BaseScraper):
    """Scrapes Taiwan-related films from シアターキノ (Sapporo, Hokkaido)."""

    SOURCE_NAME = "theater_kino"

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

    def _parse_films(self, soup: BeautifulSoup) -> list[dict]:
        """Parse all film entries from sakuhin.html."""
        films = []

        # Each film is a block-level element (div/p) whose text starts with "■"
        # followed by zero or more sibling elements including a table with dates.
        content = soup.select_one("body") or soup

        # Iterate all elements looking for ones starting with ■
        for el in content.find_all(True):
            text = el.get_text(strip=True)
            if not text.startswith("■"):
                continue
            # Skip very short or duplicate parent/child elements
            title_line = text.split("\n")[0].strip()
            if len(title_line) < 4:
                continue

            # Extract title and country info from title_line
            # e.g. "■落下音　(2025年/ドイツ/155分)" or "■台湾映画タイトル　(2025年/台湾/100分)"
            m = re.match(r"■(.+?)　?\((\d{4}年/.+?)\)", title_line)
            if not m:
                # Try without year
                m = re.match(r"■(.+)", title_line)
                if not m:
                    continue
                title = m.group(1).strip()
                meta = ""
            else:
                title = m.group(1).strip()
                meta = m.group(2)

            # Check Taiwan in meta
            if not _is_taiwan(meta) and not _is_taiwan(title):
                continue

            # Find date from the surrounding context (sibling tables or text)
            # Try to find a table in the same parent element
            parent = el.parent
            date_text = ""
            if parent:
                for sibling in el.next_siblings:
                    if isinstance(sibling, Tag):
                        sib_text = sibling.get_text(" ", strip=True)
                        if re.search(r"\d+/\d+", sib_text):
                            date_text = sib_text
                            break
                    if date_text:
                        break

            start_date, end_date = _parse_dates(date_text)

            # Build description from full text of the block + next siblings
            desc_parts = [title_line]
            for sibling in el.next_siblings:
                if isinstance(sibling, Tag):
                    sib_text = sibling.get_text(" ", strip=True)
                    if sib_text:
                        desc_parts.append(sib_text)
                    # Stop at next film entry
                    if sib_text.startswith("■"):
                        break

            full_desc = "\n".join(desc_parts[:5])

            films.append({
                "title": title,
                "meta": meta,
                "date_text": date_text,
                "start_date": start_date,
                "end_date": end_date,
                "description": full_desc,
            })

        return films

    def scrape(self) -> list[Event]:
        soup = self._get(LISTING_URL)
        if not soup:
            logger.error("Failed to fetch シアターキノ listing")
            return []

        films = self._parse_films(soup)
        logger.info("Found %d Taiwan film(s) in シアターキノ listing", len(films))

        events: list[Event] = []
        seen_titles: set[str] = set()

        for film in films:
            title = film["title"]
            if title in seen_titles:
                continue
            seen_titles.add(title)

            source_id = f"theater_kino_{_make_slug(title)}"
            raw_desc = film["description"]
            if film["start_date"]:
                start = film["start_date"]
                end = film["end_date"]
                period = start.strftime('%Y年%m月%d日')
                if end and end != start:
                    period += f"〜{end.strftime('%Y年%m月%d日')}"
                raw_desc = f"上映期間: {period}\n\n" + raw_desc

            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=LISTING_URL,
                original_language="ja",
                name_ja=title,
                raw_title=title,
                raw_description=raw_desc or title,
                description_ja=film["description"] or None,
                category=["movie"],
                start_date=film["start_date"],
                end_date=film["end_date"],
                location_name=LOCATION_NAME,
                location_address=LOCATION_ADDRESS,
            )
            events.append(event)
            logger.info("Found Taiwan film: %s (%s)", title, film["date_text"])

        return events
