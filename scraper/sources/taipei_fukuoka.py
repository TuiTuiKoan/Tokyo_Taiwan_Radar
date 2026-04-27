"""
Scraper for 台北駐福岡経済文化弁事処 (Fukuoka Branch, Taipei Economic and Cultural
Office in Osaka).  Covers cultural events in Kyushu and western Japan.

URL: https://www.roc-taiwan.org/jpfuk_ja/

Strategy:
  1. Fetch the main page and collect the latest local post links from .news-item
  2. For each post: fetch detail page, extract title (h2.fz-A) and body (.page-content)
  3. Filter: keep posts whose body contains 日時: / 開催日時: markers (event announcements)
  4. Extract start_date from body text using 日時:... patterns; fall back to title date
  5. source_id: taipei_fukuoka_{post_id}  (post_id = numeric segment of /post/NNNNN.html)
"""

import re
import time
import logging
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.roc-taiwan.org"
LIST_URL = f"{BASE_URL}/jpfuk_ja/"
SOURCE_NAME = "taipei_fukuoka"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}

# Pattern to identify local Fukuoka post URLs
_POST_RE = re.compile(r"/jpfuk_ja/post/(\d+)\.html")

# Date label patterns in body text (日時：, 開催日時：, 開催日：)
_DATE_LABEL_RE = re.compile(
    r"(?:日\s*時|開催日時?|開催日)\s*[：:]\s*(.{4,100})",
    re.MULTILINE,
)

# Date extraction patterns
_YEAR_MONTH_DAY_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
_MONTH_DAY_RE = re.compile(r"(\d{1,2})月\s*(\d{1,2})日")

# Title date patterns like "4・25開催", "4‧2防府市", "5/6「..."
_TITLE_DATE_RE = re.compile(r"(\d{1,2})[・‧/．](\d{1,2})")

# Publish date in body text: 発信日時：YYYY-MM-DD
_PUBDATE_RE = re.compile(r"発信日時[：:]\s*(\d{4})-(\d{2})-(\d{2})")

# Body event markers that confirm the post describes a public event
_EVENT_BODY_MARKERS = (
    "日時：", "日時:", "開催日時：", "開催日時:", "開催日：", "開催日:",
)

# Title keywords that indicate an event announcement
_EVENT_TITLE_KEYWORDS = (
    "お知らせ", "開催", "シンポジウム", "コンサート", "上映", "映画", "展覧",
    "公演", "講演", "セミナー", "ワークショップ", "写真展", "展示会",
    "ライブ", "ライヴ", "音楽", "KANO", "フェスティバル",
)

# Location extraction from body
_VENUE_RE = re.compile(r"(?:場\s*所|会場|開催場所)\s*[：:]\s*([^\n]{3,80})")


def _parse_date(raw: str, fallback_year: Optional[int] = None) -> Optional[datetime]:
    """Parse a date string. Tries YYYY年MM月DD日 first, then MM月DD日 + fallback_year."""
    if not raw:
        return None
    # Normalize full-width digits
    raw = raw.translate(str.maketrans("０１２３４５６７８９", "0123456789"))

    m = _YEAR_MONTH_DAY_RE.search(raw)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    if fallback_year:
        md = _MONTH_DAY_RE.search(raw)
        if md:
            try:
                return datetime(fallback_year, int(md.group(1)), int(md.group(2)))
            except ValueError:
                pass

    return None


def _extract_start_date(body_text: str, title: str, fallback_year: Optional[int]) -> Optional[datetime]:
    """Extract event start date.

    Priority:
    1. 日時: / 開催日時: label in body → date on same line
    2. Any YYYY年MM月DD日 pattern in body
    3. MM/DD or M・D pattern in title (no-year, uses fallback_year)
    """
    # 1. Explicit date label
    m = _DATE_LABEL_RE.search(body_text)
    if m:
        d = _parse_date(m.group(1), fallback_year)
        if d:
            return d

    # 2. Any full date in body
    ym = _YEAR_MONTH_DAY_RE.search(body_text)
    if ym:
        try:
            return datetime(int(ym.group(1)), int(ym.group(2)), int(ym.group(3)))
        except ValueError:
            pass

    # 3. Title pattern like "4・25開催" or "5/6「KANO"
    if fallback_year:
        t = _TITLE_DATE_RE.search(title)
        if t:
            try:
                return datetime(fallback_year, int(t.group(1)), int(t.group(2)))
            except ValueError:
                pass

    return None


def _get_publish_year(body_text: str, publish_date_str: str) -> Optional[int]:
    """Extract year from 発信日時：YYYY-MM-DD or listing .date element."""
    m = _PUBDATE_RE.search(body_text)
    if m:
        return int(m.group(1))
    if publish_date_str and len(publish_date_str) >= 4:
        try:
            return int(publish_date_str[:4])
        except ValueError:
            pass
    return None


def _extract_venue(body_text: str) -> Optional[str]:
    m = _VENUE_RE.search(body_text)
    return m.group(1).strip() if m else None


def _extract_post_id(href: str) -> Optional[str]:
    m = _POST_RE.search(href)
    return m.group(1) if m else None


class TaipeiFukuokaScraper(BaseScraper):
    SOURCE_NAME = SOURCE_NAME

    def _fetch(self, url: str, retries: int = 2) -> Optional[str]:
        for attempt in range(retries + 1):
            try:
                r = requests.get(url, headers=_HEADERS, timeout=15)
                r.raise_for_status()
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text
            except Exception as exc:
                logger.warning("Fetch error (%d/%d) %s: %s", attempt + 1, retries + 1, url, exc)
                if attempt < retries:
                    time.sleep(1.5)
        return None

    def scrape(self) -> list[Event]:
        html = self._fetch(LIST_URL)
        if not html:
            logger.error("TaipeiFukuokaScraper: failed to fetch main page")
            return []

        soup = BeautifulSoup(html, "html.parser")

        # Collect local post links from .news-item
        post_items: list[dict] = []
        for item in soup.select(".news-item"):
            link = item.select_one(".text-holder a")
            date_el = item.select_one(".date")
            if not link:
                continue
            href = link.get("href", "")
            # Only process local Fukuoka posts (skip external Taiwan Today links)
            if not _POST_RE.search(href):
                continue
            post_id = _extract_post_id(href)
            if not post_id:
                continue
            full_url = BASE_URL + href if href.startswith("/") else href
            post_items.append({
                "post_id": post_id,
                "url": full_url,
                "title": link.get_text(strip=True),
                "publish_date": date_el.get_text(strip=True) if date_el else "",
            })

        logger.info("TaipeiFukuokaScraper: %d posts to process", len(post_items))

        events: list[Event] = []
        for item in post_items:
            time.sleep(0.8)
            detail_html = self._fetch(item["url"])
            if not detail_html:
                continue

            detail_soup = BeautifulSoup(detail_html, "html.parser")

            # Extract title
            title_el = detail_soup.select_one("h2.fz-A")
            raw_title = title_el.get_text(strip=True) if title_el else item["title"]

            # Extract body
            body_el = detail_soup.select_one(".page-content")
            raw_body = body_el.get_text(separator="\n", strip=True) if body_el else ""

            # Filter: must be an event post
            has_date_label = any(m in raw_body for m in _EVENT_BODY_MARKERS)
            has_event_title = any(kw in raw_title for kw in _EVENT_TITLE_KEYWORDS)
            if not has_date_label and not has_event_title:
                logger.debug("TaipeiFukuoka: skipping non-event: %s", raw_title[:60])
                continue

            # Infer year for month-only date strings
            pub_year = _get_publish_year(raw_body, item["publish_date"])

            # Extract start_date
            start_date = _extract_start_date(raw_body, raw_title, pub_year)
            if not start_date:
                logger.warning(
                    "TaipeiFukuoka: no start_date for %s — skipping", raw_title[:60]
                )
                continue

            # Extract venue
            venue = _extract_venue(raw_body) or "九州・西日本"

            raw_description = f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n\n{raw_body}"
            source_id = f"taipei_fukuoka_{item['post_id']}"

            events.append(
                Event(
                    source_name=SOURCE_NAME,
                    source_id=source_id,
                    source_url=item["url"],
                    original_language="ja",
                    name_ja=raw_title,
                    raw_title=raw_title,
                    raw_description=raw_description,
                    start_date=start_date,
                    location_name=venue,
                    category=["taiwan_japan"],
                )
            )
            logger.info(
                "TaipeiFukuoka: event %s | %s | %s",
                start_date.date(),
                raw_title[:60],
                item["url"],
            )

        logger.info("TaipeiFukuokaScraper: %d events total", len(events))
        return events
