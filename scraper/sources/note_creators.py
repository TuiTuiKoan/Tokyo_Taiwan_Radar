"""
Scraper for selected note.com creators posting Taiwan-related events in Japan.

Monitored creators:
  kuroshio2026   — 台湾・沖縄とともに〜黒潮ネット (event announcements)
  nichitaikouryu — ゆる〜くお茶べり日台交流会in東京 (weekly exchange event reports)

Strategy:
  1. Fetch RSS feed from https://note.com/{creator}/rss (no auth required)
  2. Parse XML items: title, description HTML, pubDate, link/guid
  3. Extract start_date from title using Japanese/slash date patterns:
       M月D日  →  e.g. "4月18日"
       M/D     →  e.g. "5/4"
     Year is inferred from pubDate's year (adjusts for Jan/Feb cross-year)
  4. Extract venue from title after ＠ or @ markers
  5. source_id: "note_{creator}_{note_id}" (note_id from URL path)
  6. All posts from these accounts are Taiwan-related by nature
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Optional

import requests

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

RSS_TEMPLATE = "https://note.com/{creator}/rss"

# creator → (location_name, location_address, default_category)
CREATOR_META: dict[str, tuple[str, str, list[str]]] = {
    "kuroshio2026": (
        "東京・文京区（主開催地）",
        "東京都文京区",
        ["taiwan_japan"],
    ),
    "nichitaikouryu": (
        "ゆる〜くお茶べり日台交流会in東京",
        "東京都新宿区大久保1-5-13 2階 CAFE ECLA",
        ["taiwan_japan"],
    ),
}

# Months for cross-year inference window
_CROSS_YEAR_MONTHS = frozenset([1, 2])


class _HTMLStripper(HTMLParser):
    """Minimal HTML → plain text converter."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(self._chunks).strip()


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


def _extract_note_id(url: str) -> Optional[str]:
    """Extract note article ID from URL, e.g. https://note.com/creator/n/n4f9a42875b82 → n4f9a42875b82"""
    m = re.search(r"/n/(n[a-z0-9]+)$", url.rstrip("/"))
    return m.group(1) if m else None


def _extract_venue(title: str) -> Optional[str]:
    """Extract venue hint after ＠ or @ in title."""
    m = re.search(r"[＠@]([^\s）)]+)", title)
    if m:
        # Strip surrounding punctuation
        venue = m.group(1).rstrip("）)」")
        return venue if venue else None
    return None


def _parse_date_from_title(title: str, pub_year: int, pub_month: int) -> Optional[datetime]:
    """
    Try to extract a date from the note title.

    Supports:
      M月D日  (Japanese)  e.g. "4月18日"
      M/D     (slash)     e.g. "5/4"
    """
    # Pattern 1: M月D日
    m = re.search(r"(\d{1,2})月(\d{1,2})日", title)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
    else:
        # Pattern 2: M/D — not followed by another digit (avoids year-like 2026/4/18)
        m2 = re.search(r"(?:^|[\s（(「])?(\d{1,2})/(\d{1,2})(?!\d)", title)
        if m2:
            month, day = int(m2.group(1)), int(m2.group(2))
        else:
            return None

    # Infer year: if event month is earlier than pubDate month by more than
    # 6 months, assume next year (handles Dec post → Jan event edge case).
    year = pub_year
    if month < pub_month - 6:
        year = pub_year + 1
    elif month > pub_month + 6:
        year = pub_year - 1

    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _parse_pubdate(pub_date_str: str) -> Optional[datetime]:
    """Parse RFC 2822 pubDate string to datetime."""
    try:
        dt = parsedate_to_datetime(pub_date_str)
        # Convert to naive local (JST) by dropping tzinfo — close enough for date extraction
        return dt.replace(tzinfo=None)
    except Exception:
        return None


class NoteCreatorsScraper(BaseScraper):
    """Scrapes Taiwan-related event posts from selected note.com creators."""

    SOURCE_NAME = "note_creators"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })

    def _fetch_rss(self, creator: str) -> list[ET.Element]:
        url = RSS_TEMPLATE.format(creator=creator)
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to fetch RSS for %s: %s", creator, exc)
            return []

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as exc:
            logger.warning("Failed to parse RSS for %s: %s", creator, exc)
            return []

        # Items are at rss/channel/item
        channel = root.find("channel")
        if channel is None:
            return []
        return channel.findall("item")

    def _parse_item(
        self,
        item: ET.Element,
        creator: str,
        location_name: str,
        location_address: str,
        category: list[str],
    ) -> Optional[Event]:
        title_el = item.find("title")
        link_el = item.find("link")
        guid_el = item.find("guid")
        desc_el = item.find("description")
        pub_el = item.find("pubDate")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        link = link_el.text.strip() if link_el is not None and link_el.text else ""
        guid = guid_el.text.strip() if guid_el is not None and guid_el.text else link
        raw_desc_html = desc_el.text if desc_el is not None and desc_el.text else ""
        pub_date_str = pub_el.text.strip() if pub_el is not None and pub_el.text else ""

        if not title or not guid:
            return None

        # Parse pubDate for year/month context
        pub_dt = _parse_pubdate(pub_date_str) if pub_date_str else None
        pub_year = pub_dt.year if pub_dt else datetime.now().year
        pub_month = pub_dt.month if pub_dt else datetime.now().month

        # source_id
        note_id = _extract_note_id(guid) or _extract_note_id(link)
        if not note_id:
            logger.debug("Cannot extract note_id from %s — skipping", guid)
            return None
        source_id = f"note_{creator}_{note_id}"
        source_url = link or guid

        # Dates
        start_date = _parse_date_from_title(title, pub_year, pub_month)
        if start_date is None:
            # Fallback: use pubDate as start_date
            start_date = pub_dt
            logger.debug(
                "No date in title for %s — falling back to pubDate", title
            )

        # Venue override from title
        venue = _extract_venue(title)
        effective_location_name = venue if venue else location_name
        effective_location_address = location_address if not venue else None

        # Description — strip HTML and drop boilerplate continuation link
        plain_desc = _strip_html(raw_desc_html) if raw_desc_html else ""
        # note.com RSS descriptions often end with just "続きをみる" (read more)
        if plain_desc.strip() in ("続きをみる", ""):
            plain_desc = ""

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=source_url,
            original_language="ja",
            name_ja=title,
            raw_title=title,
            raw_description=plain_desc,
            description_ja=plain_desc or None,
            category=list(category),
            start_date=start_date,
            location_name=effective_location_name,
            location_address=effective_location_address,
        )

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        for creator, (loc_name, loc_addr, cats) in CREATOR_META.items():
            items = self._fetch_rss(creator)
            logger.info("Creator %s: %d RSS items", creator, len(items))

            for item in items:
                event = self._parse_item(item, creator, loc_name, loc_addr, cats)
                if event is not None:
                    events.append(event)
                    logger.debug("Added: %s", event.name_ja)

        logger.info("Total note.com events: %d", len(events))
        return events
