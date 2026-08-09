"""
Scraper for 誠品生活日本橋 (eslite spectrum Nihonbashi).

eslite spectrum is a Taiwanese cultural bookstore/event space in Nihonbashi
COREDO Muromachi Terrace 2F, Tokyo. It hosts Taiwan-themed book launches,
art exhibitions, and cultural events.

Strategy:
  1. Fetch /news listing page (static HTML)
  2. Collect all /news/{uuid} article links with listing publish date and title
  3. For each article, evaluate Taiwan relevance from title + detail body
  4. Keep listing/detail publish date separate from physical event datetime

Dedup key: eslite_spectrum_{article_uuid}
"""

import logging
import os
import re
import time
from datetime import date, datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.eslitespectrum.jp"
NEWS_URL = f"{BASE_URL}/news"

LOCATION_NAME = "誠品生活日本橋"
LOCATION_ADDRESS = "東京都中央区日本橋室町3-2-1 COREDO室町テラス2F"

# Keywords checked against TITLE + MAIN CONTENT only (not page nav/footer).
TAIWAN_KEYWORDS = [
    "台湾", "Taiwan", "臺灣", "台灣",
    "台北", "高雄", "台中", "台南",
    "台日", "日台",
]

PUBLICATION_KEYWORDS = [
    "出版", "刊行", "新刊", "新書", "書籍", "書店", "book launch", "publication",
]

PHYSICAL_KEYWORDS = [
    "トーク", "講演", "講座", "セミナー", "ワークショップ", "workshop",
    "サイン", "signing", "会場", "参加", "登壇", "来場", "対談",
]

# Fixed lower bound, not a rolling window: the /news archive reaches back to 2019 and a
# rolling cutoff would keep re-excluding already-published events. Historical import is a
# separate task; this floor only blocks the one-off seven-year backfill.
_HISTORY_FLOOR = date(2026, 1, 1)

# Patterns in title that clearly indicate non-event administrative content.
# Retail promotions (福袋/キャンペーン/ノベルティ/ギフト) and trade previews (内覧会) are
# store merchandising, not dated public events. 誠品選書 is the monthly staff-pick book
# list, which the project already treats as non-event content.
# Deliberately NOT matched: bare オープン and 営業 — real events use them
# (「…この日限りの特別オープン！」, 「6周年記念24時間営業…書籍フェア」).
_SKIP_TITLE_RE = re.compile(
    r"会員募集|メンバーズカード|ワークショップカレンダー|ポイント|お知らせ|営業時間|定休日|リニューアル"
    r"|福袋|ノベルティ|キャンペーン|禮物節|(?:母の日|父の日)ギフト|内覧会|サービス開始|誠品選書"
)

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_ARTICLE_UUID_RE = re.compile(
    r"/news/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:[/?#]|$)",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"([01]?\d|2[0-3]):([0-5]\d)")

# Real listings write weekday tokens between the date and the range separator
# ("2026.7.18 Sat.ー8.31 Mon.") and use ー / ～ / − as the separator, so both have to
# be tolerated or the end date is silently dropped and the event looks one-day.
_WEEKDAY_SRC = (
    r"(?:\s*(?:"
    r"(?:Mon|Tues?|Wed|Thur?s?|Fri|Sat|Sun)(?:day)?\.?"
    r"|[（(][月火水木金土日][）)]"
    r"))?"
)
_RANGE_SEP_SRC = r"\s*(?:[〜～~ー－−–—‐-]|から)\s*"
_RANGE_DATE_RE = re.compile(
    r"(?P<sy>20\d{2})[./年-]\s*(?P<sm>\d{1,2})[./月-]\s*(?P<sd>\d{1,2})日?"
    + _WEEKDAY_SRC
    + r"(?:"
    + _RANGE_SEP_SRC
    + r"(?:(?P<ey>20\d{2})[./年-])?\s*(?:(?P<em>\d{1,2})[./月-])?\s*(?P<ed>\d{1,2})日?"
    + _WEEKDAY_SRC
    + r")?"
)
# A labelled top-level range is the event's own schedule and outranks everything
# else on the page.
_EVENT_RANGE_LABEL_RE = re.compile(
    r"(?:開催日時|開催期間|開催時間|開催日|イベント期間|会期|期間|日時)\s*[:：]?\s*"
)
# Page-publication metadata is never the event's schedule.
_PUBLISH_LABEL_RE = re.compile(
    r"ページ公開日|公開日|掲載日|更新日|投稿日|発行日|published", re.IGNORECASE
)
_BARE_ISO_LINE_RE = re.compile(r"^\s*20\d{2}-\d{2}-\d{2}\s*$")
_LOCATION_LABEL_RE = re.compile(r"(?:会場|開催場所|場所)\s*[:：]\s*([^\n]+)")
_ADDRESS_LABEL_RE = re.compile(r"(?:住所|所在地)\s*[:：]\s*([^\n]+)")
_PRICE_LABEL_RE = re.compile(r"(?:参加費|料金|費用|入場料)\s*[:：]\s*([^\n]+)")
_FREE_RE = re.compile(r"無料|free", re.IGNORECASE)

_MIGRATION_GATE_ENV = "ESLITE_ALLOW_UUID_IDENTITY"
# Open since the live identity remap completed on 2026-08-04T11:41:04Z with no duplicate
# source_id. The env override stays so the gate can be closed again without a code change.
_MIGRATION_GATE_DEFAULT = True


def _migration_gate_open() -> bool:
    raw = os.environ.get(_MIGRATION_GATE_ENV)
    if raw is None:
        return _MIGRATION_GATE_DEFAULT
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _extract_article_uuid(url: str) -> Optional[str]:
    match = _ARTICLE_UUID_RE.search(url)
    if not match:
        return None
    return match.group(1).lower()


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    match = _DATE_RE.search(raw)
    if not match:
        return None
    try:
        local = datetime.strptime(match.group(0), "%Y-%m-%d")
    except ValueError:
        return None
    return datetime(local.year, local.month, local.day, tzinfo=timezone.utc)


def _extract_business_hours(text: str) -> Optional[str]:
    times: list[str] = []
    for hour, minute in _TIME_RE.findall(text):
        token = f"{int(hour):02d}:{minute}"
        if token not in times:
            times.append(token)
    if len(times) >= 2:
        return f"{times[0]}〜{times[1]}"
    if len(times) == 1:
        return times[0]
    return None


def _parse_date_range(text: str) -> Optional[tuple[datetime, datetime]]:
    match = _RANGE_DATE_RE.search(text)
    if not match:
        return None
    try:
        start_date = datetime(
            int(match.group("sy")),
            int(match.group("sm")),
            int(match.group("sd")),
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None
    if not match.group("ed"):
        return start_date, start_date
    try:
        end_date = datetime(
            int(match.group("ey") or match.group("sy")),
            int(match.group("em") or match.group("sm")),
            int(match.group("ed")),
            tzinfo=timezone.utc,
        )
    except ValueError:
        end_date = start_date
    return start_date, end_date


def _extract_event_datetime_range(text: str) -> tuple[Optional[datetime], Optional[datetime], Optional[str]]:
    """Return (start, end, business_hours) for the event's own schedule.

    A labelled top-level range wins over page-publication dates and over nested
    item ranges. Without a labelled range, a single unambiguous range is used;
    several competing nested ranges yield a start with NO end, because an
    umbrella end that no line actually states must never be invented.
    """
    if not text:
        return None, None, None

    lines = text.splitlines()

    for line in lines:
        if _PUBLISH_LABEL_RE.search(line):
            continue
        label = _EVENT_RANGE_LABEL_RE.search(line)
        if not label:
            continue
        labelled = _parse_date_range(line[label.end():])
        if labelled:
            return labelled[0], labelled[1], _extract_business_hours(text)

    candidates: list[tuple[datetime, datetime]] = []
    for line in lines:
        if _PUBLISH_LABEL_RE.search(line) or _BARE_ISO_LINE_RE.match(line):
            continue
        parsed = _parse_date_range(line)
        if parsed and parsed not in candidates:
            candidates.append(parsed)

    if not candidates:
        return None, None, None
    if len(candidates) == 1:
        return candidates[0][0], candidates[0][1], _extract_business_hours(text)
    return min(start for start, _end in candidates), None, _extract_business_hours(text)


def _extract_labeled_value(text: str, pattern: re.Pattern[str]) -> Optional[str]:
    match = pattern.search(text)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _extract_price_info(text: str) -> Optional[str]:
    labeled = _extract_labeled_value(text, _PRICE_LABEL_RE)
    if labeled:
        return labeled
    for line in text.splitlines():
        stripped = line.strip()
        if "円" in stripped and len(stripped) <= 120:
            return stripped
    return None


def _classify_event_form(title: str, body: str) -> list[str]:
    text = f"{title}\n{body}"
    lowered = text.lower()
    if any(keyword.lower() in lowered for keyword in PHYSICAL_KEYWORDS):
        if "ワークショップ" in text or "workshop" in lowered:
            return ["workshop"]
        if any(token in text for token in ("トーク", "講演", "講座", "セミナー", "対談")):
            return ["lecture"]
        return ["networking"]
    if any(keyword.lower() in lowered for keyword in PUBLICATION_KEYWORDS):
        return ["publication"]
    return ["other"]


class EsliteSpectrumScraper(BaseScraper):
    """Scrapes Taiwan-related events from 誠品生活日本橋 (eslite spectrum Nihonbashi)."""

    SOURCE_NAME = "eslite_spectrum"

    def scrape(self) -> list[Event]:
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en;q=0.9",
        })

        article_items = self._collect_articles(session)
        logger.info("eslite_spectrum: found %d news items on listing page", len(article_items))

        events: list[Event] = []
        for item in article_items:
            try:
                event = self._scrape_detail(session, item)
                if event:
                    events.append(event)
                time.sleep(0.8)
            except Exception as exc:
                logger.error("eslite_spectrum: failed to scrape %s: %s", item["url"], exc)

        logger.info("eslite_spectrum: collected %d Taiwan-related events", len(events))
        return events

    def _collect_articles(self, session: requests.Session) -> list[dict]:
        """Fetch the /news listing and return [{url, article_uuid, published_at, list_title}]."""
        items: list[dict] = []
        seen_ids: set[str] = set()

        try:
            resp = session.get(NEWS_URL, timeout=15)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("eslite_spectrum: failed to fetch %s: %s", NEWS_URL, exc)
            return items

        soup = BeautifulSoup(resp.text, "html.parser")

        for anchor in soup.find_all("a", href=True):
            full_url = urljoin(BASE_URL, anchor.get("href", ""))
            article_uuid = _extract_article_uuid(full_url)
            if not article_uuid:
                continue
            if article_uuid in seen_ids:
                continue
            seen_ids.add(article_uuid)

            title_text = anchor.get_text(strip=True)
            if not title_text:
                parent = anchor.parent
                if parent:
                    for sibling in parent.find_all("a", href=True):
                        sibling_url = urljoin(BASE_URL, sibling.get("href", ""))
                        if _extract_article_uuid(sibling_url) != article_uuid:
                            continue
                        sibling_text = sibling.get_text(strip=True)
                        if sibling_text:
                            title_text = sibling_text
                            break

            parent = anchor.parent
            parent_text = parent.get_text(separator=" ", strip=True) if parent else ""
            published_at = None
            match = _DATE_RE.search(parent_text)
            if match:
                published_at = match.group(0)

            items.append({
                "url": full_url,
                "article_uuid": article_uuid,
                "published_at": published_at,
                "list_title": title_text,
            })

        return items

    def _scrape_detail(self, session: requests.Session, item: dict) -> Optional[Event]:
        """Fetch a detail page and return an Event if Taiwan-related."""
        url = item["url"]

        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("eslite_spectrum: GET %s failed: %s", url, exc)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        title_el = soup.find("h2") or soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else item["list_title"]
        if not title:
            title = item["list_title"]

        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"content|body|detail", re.I))
        )
        page_text = soup.get_text(separator="\n")
        description = main.get_text(separator="\n", strip=True) if main else page_text.strip()

        content_text = f"{title}\n{description}"
        if _SKIP_TITLE_RE.search(title):
            logger.debug("eslite_spectrum: skipping admin item %s (%s)", title, url)
            return None
        if not any(keyword in content_text for keyword in TAIWAN_KEYWORDS):
            logger.debug("eslite_spectrum: skipping non-Taiwan item %s (%s)", title, url)
            return None

        listing_published_date = _parse_date(item.get("published_at"))
        detail_published_date = None
        meta = soup.find("meta", attrs={"property": "article:published_time"}) or soup.find(
            "meta", attrs={"name": "article:published_time"}
        )
        if meta and meta.get("content"):
            detail_published_date = _parse_date(meta.get("content"))
        if detail_published_date is None:
            match = _DATE_RE.search(page_text)
            if match:
                detail_published_date = _parse_date(match.group(0))
        published_date = detail_published_date or listing_published_date

        event_form = _classify_event_form(title, description)
        price_info = _extract_price_info(description)
        is_paid = None
        if price_info:
            is_paid = not bool(_FREE_RE.search(price_info))

        if event_form == ["publication"]:
            start_date = published_date
            end_date = published_date
            business_hours = None
        else:
            event_start, event_end, event_hours = _extract_event_datetime_range(description)
            start_date = event_start or published_date
            end_date = event_end or start_date
            business_hours = event_hours

        if start_date and start_date.date() < _HISTORY_FLOOR:
            logger.debug(
                "eslite_spectrum: skipping pre-%s archive item %s (%s)",
                _HISTORY_FLOOR.isoformat(),
                title,
                url,
            )
            return None

        source_id = f"eslite_spectrum_{item['article_uuid']}"
        if not _migration_gate_open():
            logger.info(
                "eslite_spectrum: migration gate blocked UUID identity %s (unset %s to restore the default open gate)",
                source_id,
                _MIGRATION_GATE_ENV,
            )
            return None

        location_name = _extract_labeled_value(description, _LOCATION_LABEL_RE) or LOCATION_NAME
        location_address = _extract_labeled_value(description, _ADDRESS_LABEL_RE) or LOCATION_ADDRESS

        if published_date:
            description = f"ページ公開日: {published_date.strftime('%Y年%m月%d日')}\n\n{description}"
        if event_form != ["publication"] and start_date:
            description = f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n\n{description}"

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            name_ja=title,
            raw_title=title,
            raw_description=description,
            start_date=start_date,
            end_date=end_date,
            category=["books_media"],
            location_name=location_name,
            location_address=location_address,
            event_form=event_form,
            business_hours=business_hours,
            is_paid=is_paid,
            price_info=price_info,
        )
