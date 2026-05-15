"""Scraper for シネマ・クレール（岡山）

Source URL: http://www.cinemaclair.co.jp/a10261.html  (これからの上映予定)
Platform  : Static HTML — no JS rendering required
Source name: cinemaclair
Source ID : cinemaclair_{official_url_slug}  (domain from official site link)
            cinemaclair_{title_slug}          (fallback: normalized title)

Strategy:
  1. Fetch 「これからの上映予定」 listing page (a10261.html)
  2. Walk #content-body children:
     - <h3> → captures opening date context
     - <table> → one movie per table
  3. For each movie:
     a. Extract title from <span style="font-size: x-large;"><strong>
     b. Extract opening date from the last <h3> above the table
     c. Extract official URL from td[0] <a href>
     d. Filter: keep only if production country contains "台湾"
        OR text contains Taiwan keywords
  4. "上映中" (currently showing) → set start_date to today

Date format: "２０２６年５月２２日公開"  → YYYY年MM月DD日
             "上映中" → today
"""

import hashlib
import logging
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "cinemaclair"

_LISTING_URL = "http://www.cinemaclair.co.jp/a10261.html"
_BASE_URL = "http://www.cinemaclair.co.jp"

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]

# シネマ・クレール 固定ロケーション（丸の内1・2のみ）
_LOCATION_NAME    = "シネマ・クレール 丸の内１・２"
_LOCATION_ADDRESS = "岡山市北区丸の内１丁目５−１"
_LOCATION_PREF    = ["岡山県"]

_HEADERS = {
    "User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)",
}

# Full-width digit → ASCII digit
_FW_DIGIT = str.maketrans("０１２３４５６７８９", "0123456789")


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(_FW_DIGIT)


def _parse_opening_date(h3_text: str) -> datetime | None:
    """Parse "２０２６年５月２２日公開" → datetime(2026, 5, 22)."""
    text = _normalize(h3_text)
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if not m:
        return None
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _make_source_id(official_url: str, title: str) -> str:
    """Stable ID: prefer domain of official_url, fallback to title hash."""
    if official_url:
        try:
            domain = urlparse(official_url).netloc.replace("www.", "")
            slug = re.sub(r"[^a-z0-9]", "_", domain.lower()).strip("_")
            if slug:
                return f"cinemaclair_{slug}"
        except Exception:
            pass
    # Fallback: short MD5 of normalized title
    norm = _normalize(title).strip()
    h = hashlib.md5(norm.encode("utf-8")).hexdigest()[:10]
    return f"cinemaclair_{h}"


def _is_taiwan_related(table_text: str) -> bool:
    return any(kw in table_text for kw in _TAIWAN_KEYWORDS)


def _extract_title(info_td: Tag) -> str:
    """Extract title from x-large span or first strong after ■."""
    span = info_td.find("span", style=lambda s: s and "x-large" in s)
    if span:
        title = span.get_text(strip=True)
    else:
        strong = info_td.find("strong")
        title = strong.get_text(strip=True) if strong else info_td.get_text(strip=True)[:80]
    # Strip leading ■ and whitespace
    title = title.lstrip("■").strip()
    return title


def _extract_official_url(img_td: Tag) -> str:
    a = img_td.find("a", href=True)
    if a:
        href = a["href"]
        if href.startswith("http"):
            return href
    return ""


def _build_description(title: str, info_td: Tag, opening_date_str: str) -> str:
    """Build raw_description with date prepended per scraper convention."""
    body = info_td.get_text(separator="\n", strip=True)
    # Prepend date for annotator
    if opening_date_str and opening_date_str != "上映中":
        date_line = f"開催日時: {_normalize(opening_date_str)}\n\n"
    else:
        date_line = "開催日時: 上映中\n\n"
    return date_line + body


class CinemaClairScraper(BaseScraper):
    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        try:
            resp = requests.get(_LISTING_URL, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
        except Exception as exc:
            logger.error("cinemaclair: failed to fetch listing page: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        content = soup.find("div", id="content-body")
        if not content:
            logger.warning("cinemaclair: #content-body not found")
            return []

        events: list[Event] = []
        seen_ids: set[str] = set()
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        current_h3_text = "上映中"
        current_opening_date: datetime | None = None

        for child in content.children:
            if not isinstance(child, Tag):
                continue

            if child.name == "h3":
                current_h3_text = child.get_text(strip=True)
                current_opening_date = _parse_opening_date(current_h3_text)
                continue

            if child.name != "table":
                continue

            tds = child.find_all("td", recursive=False)
            # Some tables have nested structure — try all td
            if len(tds) < 2:
                tds = child.find_all("td")
            if len(tds) < 2:
                continue

            img_td = tds[0]
            info_td = tds[1]

            table_text = child.get_text()
            if not _is_taiwan_related(table_text):
                continue

            title = _extract_title(info_td)
            if not title:
                continue

            official_url = _extract_official_url(img_td)
            source_id = _make_source_id(official_url, title)
            if source_id in seen_ids:
                continue
            seen_ids.add(source_id)

            # Date: from h3 context, or today for 上映中
            if current_opening_date:
                start_date = current_opening_date
            else:
                start_date = today.replace(tzinfo=None)

            raw_description = _build_description(title, info_td, current_h3_text)

            event = Event(
                source_name=SOURCE_NAME,
                source_id=source_id,
                source_url=_LISTING_URL,
                original_language="ja",
                name_ja=title,
                raw_title=title,
                raw_description=raw_description,
                start_date=start_date,
                category=["movie"],
                event_form=["screening"],
                official_url=official_url or None,
                location_name=_LOCATION_NAME,
                location_address=_LOCATION_ADDRESS,
            )
            events.append(event)
            logger.info("cinemaclair: found Taiwan film: %s [%s]", title, current_h3_text)

        logger.info("cinemaclair: total Taiwan films found: %d", len(events))
        return events
