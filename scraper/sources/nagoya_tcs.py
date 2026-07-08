"""Scraper for 名古屋大学 超域文化社会センター (TCS) topics.

Source URL : https://www.hum.nagoya-u.ac.jp/tcs/topics/
Platform   : Static HTML, single reverse-chronological archive page
Source name: nagoya_tcs

The page has no per-event permalink. Each event is represented by an ``h5``
heading followed by body elements until the next ``h5``.
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "nagoya_tcs"
LISTING_URL = "https://www.hum.nagoya-u.ac.jp/tcs/topics/"
BASE_URL = "https://www.hum.nagoya-u.ac.jp"
LOOKBACK_DAYS = 400
UTC = timezone.utc

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
        "+https://tokyotaiwanradar.com)"
    )
}

_TAIWAN_KEYWORDS = [
    "台湾", "臺灣", "Taiwan", "taiwan", "台大", "台湾大学", "臺灣大學",
    "李琴峰", "廖 克发", "廖克發", "ラウ・ケクフアット", "金馬", "TIDF",
    "台湾映画", "台日", "日台", "メイド・イン・タイワン",
]

_DATE_LABELS = ("日時", "開催日時", "開催日", "Date", "Period")
_FULL_RANGE_RE = re.compile(
    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*(?:日)?"
    r"\s*[〜~～\-—–∼]\s*(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*日"
)
_FULL_SINGLE_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_SLASH_RE = re.compile(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})")
_NO_YEAR_RE = re.compile(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_EN_MONTH_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2})(?:\s*[\-—–]\s*(\d{1,2}))?,\s*(\d{4})",
    re.IGNORECASE,
)
_EN_REVERSE_MONTH_RE = re.compile(
    r"(\d{1,2})(?:\s*[\-—–]\s*(\d{1,2}))?\s*"
    r"(?:\([A-Za-z]+\)\s*)?"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{4})",
    re.IGNORECASE,
)
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    return re.sub(r"\s+", " ", text).strip()


def _clean_lines(text: str) -> list[str]:
    lines = []
    for line in text.replace("\x00", "").splitlines():
        line = _clean_text(line)
        if line:
            lines.append(line)
    return lines


def _calendar_date(year: int, month: int, day: int) -> datetime | None:
    try:
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None


def _date_scope(text: str) -> str:
    lines = _clean_lines(text)
    scoped = [line for line in lines if any(label in line for label in _DATE_LABELS)]
    return "\n".join(scoped[:4]) if scoped else text[:1800]


def _parse_dates(text: str, inferred_year: int | None) -> tuple[datetime | None, datetime | None, int | None]:
    scope = _date_scope(text)

    m = _FULL_RANGE_RE.search(scope)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        start_day = int(m.group(3))
        end_month = int(m.group(4) or month)
        end_day = int(m.group(5))
        return (
            _calendar_date(year, month, start_day),
            _calendar_date(year, end_month, end_day),
            year,
        )

    m = _FULL_SINGLE_RE.search(scope)
    if m:
        year, month, day = map(int, m.groups())
        return _calendar_date(year, month, day), None, year

    m = _SLASH_RE.search(scope)
    if m:
        year, month, day = map(int, m.groups())
        return _calendar_date(year, month, day), None, year

    m = _EN_MONTH_RE.search(scope)
    if m:
        month = _MONTHS[m.group(1).lower()]
        start_day = int(m.group(2))
        end_day = int(m.group(3) or start_day)
        year = int(m.group(4))
        end_date = _calendar_date(year, month, end_day) if end_day != start_day else None
        return _calendar_date(year, month, start_day), end_date, year

    m = _EN_REVERSE_MONTH_RE.search(scope)
    if m:
        start_day = int(m.group(1))
        end_day = int(m.group(2) or start_day)
        month = _MONTHS[m.group(3).lower()]
        year = int(m.group(4))
        end_date = _calendar_date(year, month, end_day) if end_day != start_day else None
        return _calendar_date(year, month, start_day), end_date, year

    if inferred_year:
        m = _NO_YEAR_RE.search(scope)
        if m:
            month, day = map(int, m.groups())
            return _calendar_date(inferred_year, month, day), None, None

    return None, None, None


def _event_blocks(soup: BeautifulSoup) -> list[tuple[str, list[Tag]]]:
    section = soup.select_one("section#sub_contents")
    if not section:
        return []

    blocks: list[tuple[str, list[Tag]]] = []
    current_title: str | None = None
    current_elements: list[Tag] = []

    for child in section.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "h5":
            if current_title:
                blocks.append((current_title, current_elements))
            current_title = _clean_text(child.get_text(" ", strip=True))
            current_elements = []
            continue
        if current_title:
            current_elements.append(child)

    if current_title:
        blocks.append((current_title, current_elements))
    return [(title, elements) for title, elements in blocks if title]


def _block_text(title: str, elements: list[Tag]) -> str:
    parts = [title]
    for element in elements:
        text = element.get_text("\n", strip=True)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _is_relevant(title: str, body: str) -> bool:
    haystack = f"{title}\n{body}"
    haystack_lower = haystack.lower()
    return any(keyword.lower() in haystack_lower for keyword in _TAIWAN_KEYWORDS)


def _categories(title: str, body: str) -> list[str]:
    text = f"{title}\n{body}"
    categories = ["academic", "taiwan_japan"]
    if re.search(r"講演|セミナー|シンポジウム|研究発表|ワークショップ|フォーラム", text):
        categories.append("lecture")
    if re.search(r"映画|上映|監督|ドキュメンタリー|Cinema|Film", text, re.IGNORECASE):
        categories.append("movie")
    if re.search(r"文学|作家|李琴峰|書評|Book", text, re.IGNORECASE):
        categories.append("books_media")
    if re.search(r"ジェンダー|女性|フェミニズム|クィア|マイノリティ|Gender|Queer", text, re.IGNORECASE):
        categories.append("gender")
    return list(dict.fromkeys(categories))


def _extract_label(lines: list[str], labels: tuple[str, ...]) -> str | None:
    for line in lines:
        for label in labels:
            m = re.match(rf"^[•・\-\s]*{label}\s*[：:]\s*(.+)$", line, re.IGNORECASE)
            if m:
                return _clean_text(m.group(1))[:240]
    return None


def _extract_venue(lines: list[str], text: str) -> str | None:
    venue = _extract_label(lines, ("会場", "場所", "Venue"))
    if venue:
        venue = re.split(r"\s*(?:Venue|主催|Organized by|入場|Admission)[：:]", venue)[0]
        return _clean_text(venue) or None

    m = re.search(
        r"(名古屋大学[^。\n]{0,55}(?:館|ホール|講義室|教室|会議室|キャンパス)|"
        r"文系総合館[^。\n]{0,45}(?:ホール|会議室|カンファレンスホール)?)",
        text,
    )
    if m:
        return _clean_text(m.group(1))
    if "オンライン" in text or "Zoom" in text:
        return "オンライン"
    return None


def _extract_business_hours(text: str) -> str | None:
    scope = _date_scope(text)
    ranges = re.findall(
        r"\d{1,2}[：:]\d{2}\s*(?:[〜~～\-—–]\s*\d{1,2}[：:]\d{2})?",
        scope,
    )
    if not ranges:
        return None
    return " / ".join(_clean_text(item) for item in ranges[:4])


def _split_organizers(raw: str | None) -> tuple[str | None, list[str]]:
    if not raw:
        return "名古屋大学大学院人文学研究科附属超域文化社会センター", []
    raw = re.split(r"\s*(?:Organized by|科研費|Sponsored by)[：:]", raw)[0]
    parts = [_clean_text(part) for part in re.split(r"[／/、,]", raw) if _clean_text(part)]
    if not parts:
        return "名古屋大学大学院人文学研究科附属超域文化社会センター", []
    return parts[0][:120], parts[1:6]


def _extract_performer(lines: list[str]) -> str | None:
    return _extract_label(lines, ("講演者", "講師", "登壇者", "監督", "ゲスト", "報告者", "Speaker"))


def _image_url(elements: list[Tag]) -> str | None:
    for element in elements:
        image = element.find("img", src=True)
        if image:
            return urljoin(BASE_URL, image["src"])
    return None


def _source_id(title: str, start_date: datetime, elements: list[Tag]) -> str:
    key = _image_url(elements) or f"{title}|{start_date.date().isoformat()}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{SOURCE_NAME}_{digest}"


def _date_header(start_date: datetime, end_date: datetime | None) -> str:
    start = f"{start_date.year}年{start_date.month}月{start_date.day}日"
    if end_date and end_date.date() != start_date.date():
        end = f"{end_date.year}年{end_date.month}月{end_date.day}日"
        return f"開催日時: {start}〜{end}"
    return f"開催日時: {start}"


class NagoyaTcsScraper(BaseScraper):
    """Scrapes Taiwan-related TCS topics from Nagoya University."""

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
            resp = self._session.get(LISTING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("nagoya_tcs: listing fetch failed: %s", exc)
            return []

        soup = BeautifulSoup(resp.content, "html.parser")
        blocks = _event_blocks(soup)
        logger.info("nagoya_tcs: found %d topic blocks", len(blocks))

        cutoff = datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)
        inferred_year: int | None = None
        events: list[Event] = []

        for title, elements in blocks:
            text = _block_text(title, elements)
            start_date, end_date, explicit_year = _parse_dates(text, inferred_year)
            if explicit_year:
                inferred_year = explicit_year

            if not _is_relevant(title, text):
                continue
            if not start_date:
                logger.debug("nagoya_tcs: relevant block without event date skipped: %s", title)
                continue
            if start_date < cutoff:
                continue

            lines = _clean_lines(text)
            location_name = _extract_venue(lines, text)
            organizer_raw = _extract_label(lines, ("主催", "Organized by"))
            organizer, co_organizers = _split_organizers(organizer_raw)
            performer = _extract_performer(lines)
            business_hours = _extract_business_hours(text)
            raw_description = f"{_date_header(start_date, end_date)}\n\n{text}"

            events.append(
                Event(
                    source_name=SOURCE_NAME,
                    source_id=_source_id(title, start_date, elements),
                    source_url=LISTING_URL,
                    official_url=LISTING_URL,
                    original_language="ja",
                    name_ja=title,
                    name_ja_locked=True,
                    raw_title=title,
                    raw_description=raw_description,
                    description_ja=text[:1200],
                    category=_categories(title, text),
                    start_date=start_date,
                    end_date=end_date,
                    location_name=location_name,
                    business_hours=business_hours,
                    is_paid=False if re.search(r"入場無料|参加無料|Admission Free", text, re.IGNORECASE) else None,
                    image_url=_image_url(elements),
                    organizer=organizer,
                    co_organizers=co_organizers,
                    organizer_type=["academic"],
                    performer=performer,
                    event_form=["lecture"],
                    primary_language="ja",
                    has_japanese_support=True,
                )
            )
            logger.info("nagoya_tcs: found Taiwan event: %s", title)

        logger.info("nagoya_tcs: scraped %d events", len(events))
        return events