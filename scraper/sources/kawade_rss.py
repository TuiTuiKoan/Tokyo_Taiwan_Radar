"""
Scraper for Taiwan-related books and events via 河出書房新社 RDF/RSS 1.0 feed.

Strategy:
  1. Fetch https://www.kawade.co.jp/np/rss/index.rdf (RDF/RSS 1.0)
  2. Taiwan relevance filter on title + description (client-side)
  3. Items with 【イベント】 prefix → category includes "lecture"
  4. start_date = end_date = dc:date (発売日 / イベント日) UTC midnight
  5. source_id: kawade_{md5(link)[:12]}
"""

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import requests

from .base import BaseScraper, Event, dedup_events

logger = logging.getLogger(__name__)

SOURCE_NAME = "kawade_rss"
RSS_URL = "https://www.kawade.co.jp/np/rss/index.rdf"

NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rss": "http://purl.org/rss/1.0/",
    "dc":  "http://purl.org/dc/elements/1.1/",
}

# Expand namespace URIs for direct findall when prefix lookup fails
_NS_RSS  = "http://purl.org/rss/1.0/"
_NS_DC   = "http://purl.org/dc/elements/1.1/"

TAIWAN_KEYWORDS = [
    "台湾", "臺灣", "Taiwan", "台北", "台南", "台中", "高雄",
    "客家", "原住民", "原住民族", "閩南", "ホーロー", "台語",
    "minnan", "hakka",
]

PUBLISHER_HOMEPAGE = "https://www.kawade.co.jp/"
_PHYSICAL_EVENT_RE = re.compile(
    r"【イベント】|トーク|講演|講座|セミナー|ワークショップ|サイン(?:会)?|署名|"
    r"お渡し会|出版記念|刊行記念|発売記念|book\s*launch|会場|定員|申込|参加",
    re.IGNORECASE,
)
_WORKSHOP_RE = re.compile(r"ワークショップ|workshop", re.IGNORECASE)
_LECTURE_RE = re.compile(r"トーク|講演|講座|セミナー|lecture|talk", re.IGNORECASE)
_DATE_RANGE_RE = re.compile(
    r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日"
    r"(?:[^\d]{0,12}(?:[〜～~\-]|から)\s*(?:(20\d{2})年\s*)?"
    r"(?:(\d{1,2})月\s*)?(\d{1,2})日)?"
)
_TIME_RE = re.compile(
    r"(?<!\d)((?:[01]?\d|2[0-3]):[0-5]\d)"
    r"(?:\s*[〜～~\-]\s*((?:[01]?\d|2[0-3]):[0-5]\d))?"
)


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _strip_null(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return s.replace("\x00", "")


def _parse_dc_date(value: str) -> Optional[datetime]:
    """Parse ISO 8601 date like '2024-03-15' or '2024-03-15T00:00:00+09:00' → UTC midnight."""
    value = value.strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        try:
            return datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass
    return None


def _el_text(item: ET.Element, ns_uri: str, local: str) -> str:
    """Find a child element by Clark notation {ns_uri}local and return its text."""
    el = item.find(f"{{{ns_uri}}}{local}")
    if el is None:
        return ""
    return (el.text or "").strip().replace("\x00", "")


def _classify_event_form(title: str, description: str) -> list[str]:
    text = f"{title}\n{description}"
    if not _PHYSICAL_EVENT_RE.search(text):
        return ["publication"]
    if _WORKSHOP_RE.search(text):
        return ["workshop"]
    if _LECTURE_RE.search(text):
        return ["lecture"]
    return ["networking"]


def _extract_event_dates(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    match = _DATE_RANGE_RE.search(text)
    if not match:
        return None, None
    year, month, day = (int(match.group(index)) for index in (1, 2, 3))
    try:
        start = datetime(year, month, day, tzinfo=timezone.utc)
        end = start
        if match.group(6):
            end_year = int(match.group(4) or year)
            end_month = int(match.group(5) or month)
            end = datetime(end_year, end_month, int(match.group(6)), tzinfo=timezone.utc)
        return start, end
    except ValueError:
        return None, None


def _extract_labeled_value(text: str, labels: tuple[str, ...]) -> Optional[str]:
    for label in labels:
        match = re.search(rf"(?:^|\n)\s*{re.escape(label)}\s*[:：]\s*([^\n]+)", text)
        if match:
            return match.group(1).strip() or None
    return None


def _extract_business_hours(text: str) -> Optional[str]:
    matches = []
    for match in _TIME_RE.finditer(text):
        value = match.group(1)
        if match.group(2):
            value = f"{value}〜{match.group(2)}"
        if value not in matches:
            matches.append(value)
    return "\n".join(matches) or None


class KawadeRssScraper(BaseScraper):
    SOURCE_NAME = "kawade_rss"

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        try:
            resp = requests.get(
                RSS_URL,
                headers={"User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"},
                timeout=20,
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as exc:
            logger.warning("kawade_rss: fetch failed: %s", exc)
            return []

        # RDF/RSS 1.0: <item> elements are direct children of <rdf:RDF>
        # They may be in the rss: namespace (http://purl.org/rss/1.0/)
        items = root.findall(f"{{{_NS_RSS}}}item")
        if not items:
            # Some feeds omit the namespace on <item> — try unqualified fallback
            items = root.findall("item")
        logger.debug("kawade_rss: found %d items", len(items))

        for item in items:
            title   = _el_text(item, _NS_RSS, "title")
            link    = _el_text(item, _NS_RSS, "link")
            desc    = _el_text(item, _NS_RSS, "description")
            dc_date = _el_text(item, _NS_DC,  "date")

            # Taiwan filter
            if not _is_taiwan(f"{title} {desc}"):
                continue

            if not link:
                continue

            source_id = f"kawade_{hashlib.md5(link.encode()).hexdigest()[:12]}"

            start_dt: Optional[datetime] = _parse_dc_date(dc_date) if dc_date else None

            event_form = _classify_event_form(title, desc)
            is_physical = event_form != ["publication"]
            category = ["books_media"]
            if is_physical and event_form[0] in {"lecture", "workshop"}:
                category.append(event_form[0])
            explicit_start, explicit_end = _extract_event_dates(f"{title}\n{desc}")
            if is_physical:
                start_dt = explicit_start or start_dt
                end_dt = explicit_end or start_dt
            else:
                end_dt = start_dt
            location_name = _extract_labeled_value(desc, ("会場", "場所")) if is_physical else None
            location_address = _extract_labeled_value(desc, ("住所", "所在地")) if is_physical else None
            business_hours = _extract_business_hours(desc) if is_physical else None

            events.append(Event(
                source_name=SOURCE_NAME,
                source_id=source_id,
                source_url=_strip_null(link),
                original_language="ja",
                name_ja=_strip_null(title) or None,
                raw_title=_strip_null(title) or None,
                raw_description=_strip_null(desc) or None,
                start_date=start_dt,
                end_date=end_dt,
                location_name=location_name,
                location_address=location_address,
                location_prefectures=[],
                category=category,
                event_form=event_form,
                name_ja_locked=True,
                organizer="河出書房新社",
                organizer_url=PUBLISHER_HOMEPAGE,
                business_hours=business_hours,
            ))

        result = dedup_events(events)
        logger.info("kawade_rss: %d events after dedup", len(result))
        return result
