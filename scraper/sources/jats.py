"""Scraper for 日本台湾学会 (JATS) — Japan Association for Taiwan Studies.

Site: https://jats.gr.jp/
Type: WordPress REST API
Auth: None
Rate limit: None observed

JATS is an academic society specialising in Taiwan studies, based in Tokyo
(東京大学東洋文化研究所). It holds 定例研究会（関東）monthly and an annual
学術大会. ALL events are Taiwan-related — no keyword filter needed.

Two types of posts share category 6 (taikai-tokyo):
  1. Announcement posts  — URL pattern /taikai-tokyo/kantoNNN/  → SKIP (just says "blog に掲載")
  2. Structured detail posts — URL pattern /taikai/tokyoNNN     → SCRAPE

Strategy: query cat 6 posts (newest first), filter to detail posts only.
"""

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "jats"
API_BASE = "https://jats.gr.jp/wp-json/wp/v2/posts"
# Category 6 = 定例研究会(東京); category 13 = 学術大会
CATEGORIES = "6"
PER_PAGE = 20
MAX_PAGES = 2          # 40 posts ≈ 6–10 months of meetings
LOOKBACK_DAYS = 90

JST = timezone(timedelta(hours=9))

# Only structured detail posts have this URL pattern
_DETAIL_URL_RE = re.compile(r"/taikai/tokyo\d+$")

_STOP_LABELS = [
    "プログラム", "■", "●", "※", "言語", "使用言語", "定員", "申込",
    "主催", "共催", "お問い合わせ", "連絡先", "備考", "お知らせ",
    "http",
]


def _strip_html(raw_html: str) -> str:
    """Strip HTML tags, decode entities, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_after_label(text: str, label_re: str) -> Optional[str]:
    """Return text immediately after a label, stopping at the next stop word."""
    m = re.search(label_re + r"\s+(.+)", text)
    if not m:
        return None
    val = m.group(1)
    for stop in _STOP_LABELS:
        # Single special characters stop just after a space
        if len(stop) <= 2 and not stop[0].isalpha():
            stop_m = re.search(r"\s+" + re.escape(stop), val)
        else:
            stop_m = re.search(r"\s+" + re.escape(stop) + r"[\s：:]", val)
        if stop_m:
            val = val[: stop_m.start()]
    return val.strip()[:200]


def _parse_date(raw: str) -> Optional[datetime]:
    """Parse Japanese date string to timezone-aware datetime (JST).

    Handles formats:
      '2026年4月25日（土）10:30-16:00' (ASCII colon, hyphen)
      '2026年3月8日（日）13:00-17:45 （JST）'
    """
    raw = raw.strip()
    # Remove day-of-week annotations e.g.（土）（日・祝）
    raw = re.sub(r"（[月火水木金土日・祝）]+）", "", raw)
    # Remove （JST） annotation
    raw = raw.replace("（JST）", "").strip()

    m = re.search(r"(\d{4})年(\d+)月(\d+)日", raw)
    if not m:
        return None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))

    # Time: HH:MM (ASCII or full-width colon)
    tm = re.search(r"(\d{1,2})[：:](\d{2})", raw)
    hour, minute = (int(tm.group(1)), int(tm.group(2))) if tm else (0, 0)

    try:
        return datetime(year, month, day, hour, minute, tzinfo=JST)
    except ValueError:
        logger.warning("Invalid date components: %s", raw)
        return None


def _fetch_posts(page: int) -> list[dict]:
    """Fetch a page of posts from the JATS WP REST API."""
    params = {
        "per_page": PER_PAGE,
        "page": page,
        "categories": CATEGORIES,
        "_fields": "id,link,title,date,content",
        "orderby": "date",
        "order": "desc",
    }
    try:
        resp = requests.get(API_BASE, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("JATS API error (page %d): %s", page, exc)
        return []


class JatsScraper(BaseScraper):
    """Scraper for JATS 定例研究会（関東）structured detail posts."""

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        cutoff = datetime.now(JST) - timedelta(days=LOOKBACK_DAYS)

        for page_num in range(1, MAX_PAGES + 1):
            posts = _fetch_posts(page_num)
            if not posts:
                break

            logger.info("JATS page %d: %d posts", page_num, len(posts))

            for post in posts:
                # Only process structured detail posts (/taikai/tokyoNNN)
                link: str = post.get("link", "")
                if not _DETAIL_URL_RE.search(link):
                    continue

                post_id = post["id"]
                title_html = post.get("title", {}).get("rendered", "")
                title = _strip_html(title_html)

                content_html = post.get("content", {}).get("rendered", "")
                content = _strip_html(content_html)

                # Date: "日時 YYYY年M月DD日（曜日）HH:MM-HH:MM"
                date_raw_m = re.search(r"日時\s+(\d{4}年\d+月\d+日.{0,60}?)(?:\s+(?:場所|プログラム|■|●|$))", content)
                if not date_raw_m:
                    # Fallback: looser search
                    date_raw_m = re.search(r"日時\s+(.{10,60})", content)
                date_raw = date_raw_m.group(1).strip() if date_raw_m else ""
                start_date = _parse_date(date_raw) if date_raw else None

                if start_date and start_date < cutoff:
                    logger.debug("Skipping old JATS event: %s (%s)", title, date_raw)
                    continue

                # Venue: "場所 VENUE プログラム"
                venue_raw = _extract_after_label(content, r"場所") or ""
                # Take only first sentence / line
                venue = venue_raw.split("　")[0].strip()[:120]

                raw_desc_parts = []
                if date_raw:
                    raw_desc_parts.append(f"開催日時: {date_raw}")
                if venue:
                    raw_desc_parts.append(f"会場: {venue}")
                # Include presentation titles / content summary
                program_m = re.search(r"プログラム\s+(.{20,400})", content)
                if program_m:
                    raw_desc_parts.append(f"プログラム:\n{program_m.group(1)[:400]}")
                raw_description = "\n\n".join(raw_desc_parts) if raw_desc_parts else content[:400]

                events.append(Event(
                    source_name=SOURCE_NAME,
                    source_id=f"{SOURCE_NAME}_{post_id}",
                    source_url=link,
                    original_language="ja",
                    name_ja=title,
                    category=["academic", "taiwan_japan"],
                    start_date=start_date,
                    location_name=venue or None,
                    location_address=venue or None,
                    is_paid=False,
                    raw_title=title,
                    raw_description=raw_description,
                ))
                logger.info("JATS: found event: %s", title)

        logger.info("jats: scraped %d events", len(events))
        return events
