"""Scraper for the annual Taiwan Expo Japan event."""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

HOMEPAGE_URL = "https://jp.twexpojapan.com/"
SOURCE_NAME = "taiwan_expo_japan"
VENUE_NAME = "東京新宿住友ビル三角広場"
ORGANIZER = "経済部国際貿易署"
ORGANIZER_URL = "https://www.trade.gov.tw/english/"

_HEADERS = {
    "User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.7",
}
_TITLE_RE = re.compile(r"(?:台湾エキスポ|Taiwan\s*Expo).*?(20\d{2})", re.IGNORECASE)
_DATE_RANGE_RE = re.compile(
    r"(?P<year>20\d{2})\s*(?:[./]|年)\s*"
    r"(?P<start_month>\d{1,2})\s*(?:[./]|月)\s*"
    r"(?P<start_day>\d{1,2})\s*日?\s*"
    r"[〜~～\-－–—]\s*"
    r"(?:(?P<end_year>20\d{2})\s*(?:[./]|年)\s*)?"
    r"(?:(?P<end_month>\d{1,2})\s*(?:[./]|月)\s*)?"
    r"(?P<end_day>\d{1,2})\s*日?"
)
_ADDRESS_RE = re.compile(
    r"(?:〒?\s*\d{3}-\d{4}.*(?:東京都|Tokyo)|"
    r"\d+\s+Chome-\d+-\d+\s+Nishishinjuku.*Tokyo\s+\d{3}-\d{4})",
    re.IGNORECASE,
)
_ABOUT_HEADING = "Taiwan Expo について"
_SCHEDULE_HEADING = "イベントスケジュール"
_PAST_RESULTS_RE = re.compile(r"(20\d{2})年\s*開催実績")


def _clean_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value.replace("\x00", "")).strip()


def _page_lines(soup: BeautifulSoup) -> list[str]:
    for element in soup.select("script, style, noscript"):
        element.decompose()
    lines: list[str] = []
    for raw_line in soup.get_text("\n", strip=True).splitlines():
        line = re.sub(r"\s+", " ", _clean_text(raw_line)).strip()
        if line and (not lines or line != lines[-1]):
            lines.append(line)
    return lines


def _parse_date_range(
    text: str,
    expected_year: int,
) -> tuple[datetime | None, datetime | None]:
    normalized = _clean_text(text)
    for match in _DATE_RANGE_RE.finditer(normalized):
        year = int(match.group("year"))
        if year != expected_year:
            continue
        end_year = int(match.group("end_year") or year)
        start_month = int(match.group("start_month"))
        end_month = int(match.group("end_month") or start_month)
        try:
            start_date = datetime(
                year,
                start_month,
                int(match.group("start_day")),
                tzinfo=timezone.utc,
            )
            end_date = datetime(
                end_year,
                end_month,
                int(match.group("end_day")),
                tzinfo=timezone.utc,
            )
        except ValueError:
            continue
        if end_date < start_date:
            continue
        return start_date, end_date
    return None, None


def _extract_description(lines: list[str], event_year: int) -> str | None:
    try:
        start_index = next(
            index for index, line in enumerate(lines) if _ABOUT_HEADING in line
        )
    except StopIteration:
        return None

    end_index: int | None = None
    for index in range(start_index + 1, len(lines)):
        line = lines[index]
        if _SCHEDULE_HEADING in line:
            end_index = index
            break
        past_results = _PAST_RESULTS_RE.search(line)
        if past_results and int(past_results.group(1)) != event_year:
            end_index = index
            break
    if end_index is None:
        return None

    description_lines = lines[start_index + 1 : end_index]
    description = "\n".join(description_lines).strip()
    return description or None


def _extract_location(lines: list[str]) -> tuple[str | None, str | None]:
    try:
        venue_index = next(
            index for index, line in enumerate(lines) if VENUE_NAME in line
        )
    except StopIteration:
        return None, None

    window_start = max(0, venue_index - 8)
    window_end = min(len(lines), venue_index + 9)
    address = next(
        (line for line in lines[window_start:window_end] if _ADDRESS_RE.search(line)),
        None,
    )
    return VENUE_NAME, address


def _parse_event_html(html: str) -> Event | None:
    soup = BeautifulSoup(html.replace("\x00", ""), "html.parser")
    title = _clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    title_match = _TITLE_RE.search(title)
    if not title_match:
        logger.error("taiwan_expo_japan: official title or year not found")
        return None

    event_year = int(title_match.group(1))
    lines = _page_lines(soup)
    page_text = " ".join(lines)
    start_date, end_date = _parse_date_range(page_text, event_year)
    if start_date is None or end_date is None:
        logger.error(
            "taiwan_expo_japan: complete date range for title year %d not found",
            event_year,
        )
        return None

    description = _extract_description(lines, event_year)
    if not description:
        logger.error("taiwan_expo_japan: main description boundaries not found")
        return None

    location_name, location_address = _extract_location(lines)
    if not location_name:
        logger.error("taiwan_expo_japan: official venue not found")
        return None

    date_prefix = (
        f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
        f"〜{end_date.strftime('%Y年%m月%d日')}"
    )
    details = [date_prefix, f"会場: {location_name}"]
    if location_address:
        details.append(f"住所: {location_address}")
    details.append(f"主催: {ORGANIZER}")
    raw_description = "\n".join(details) + "\n\n" + description

    return Event(
        source_name=SOURCE_NAME,
        source_id=f"taiwan_expo_japan_{event_year}",
        source_url=HOMEPAGE_URL,
        official_url=HOMEPAGE_URL,
        original_language="ja",
        name_ja=title,
        name_ja_locked=True,
        description_ja=description,
        raw_title=title,
        raw_description=raw_description,
        category=["taiwan_japan", "business", "tech", "lifestyle_food"],
        start_date=start_date,
        end_date=end_date,
        location_name=location_name,
        location_address=location_address,
        organizer=ORGANIZER,
        organizer_url=ORGANIZER_URL,
    )


class TaiwanExpoJapanScraper(BaseScraper):
    """Scrape one canonical event for each annual Taiwan Expo Japan edition."""

    SOURCE_NAME = SOURCE_NAME

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        retry = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def scrape(self) -> list[Event]:
        try:
            response = self._session.get(HOMEPAGE_URL, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("taiwan_expo_japan: homepage fetch failed: %s", exc)
            return []

        event = _parse_event_html(response.text)
        return [event] if event else []