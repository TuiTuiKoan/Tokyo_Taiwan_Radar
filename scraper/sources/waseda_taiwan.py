"""Scraper for 早稲田大学台湾研究所 (Waseda University Taiwan Research Institute).

Site: https://waseda-taiwan.com/
Type: WordPress REST API
Auth: None
Rate limit: None observed

Waseda Taiwan Research Institute holds lectures, symposia, and workshops at
Waseda Campus (東京都新宿区西早稲田), ~1–2 events per month.
ALL events are Taiwan-related — no keyword filter needed.

Not all posts are events; some are working papers, newsletters, or blog entries.
Event detection: post content contains 日時 / 開催日時 / 日 時 (with space).

Date label variants encountered on this site:
  '日時：YYYY年M月DD日（曜日）HH：MM～HH：MM'  (full-width colon/tilde)
  '日時：YYYY/M/DD（曜日）HH:MM〜HH:MM'
  '日 時：YYYY年M月DD日(曜日) HH:MM-HH:MM'  (space inside 日時)
  '開催日時：YYYY年M月DD日（曜日・祝）HH:MM〜HH:MM'

Venue label variants:
  '場所：VENUE', '場 所：VENUE', '会場：VENUE', '開催場所：VENUE'
"""

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "waseda_taiwan"
API_BASE = "https://waseda-taiwan.com/wp-json/wp/v2/posts"
PER_PAGE = 20
MAX_PAGES = 2          # 40 posts ≈ 4–6 months
LOOKBACK_DAYS = 90

JST = timezone(timedelta(hours=9))

# Labels that indicate a post is an event (not a paper/newsletter)
_EVENT_MARKERS = re.compile(
    r"(?:日\s*時|開催日時|開催日)[：:：]"
)

_STOP_LABELS = [
    "使用言語", "言語", "プログラム", "定員", "申込", "主催", "共催",
    "お問い合わせ", "連絡先", "備考", "講師", "コメンテーター",
    "司会", "報告者", "タイトル", "■", "●", "※", "http",
]


def _strip_html(raw_html: str) -> str:
    """Strip HTML tags, decode entities, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_after_label(text: str, label_re: str) -> Optional[str]:
    """Return text immediately after a label, stopping at the next stop word."""
    m = re.search(label_re + r"[\s：: ]+(.+)", text)
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
    """Parse a date string to timezone-aware datetime (JST).

    Handles:
      'YYYY年M月DD日（曜日）HH：MM～HH：MM'
      'YYYY年M月DD日（曜日・祝）HH:MM-HH:MM'
      'YYYY/M/DD（曜日）HH:MM〜HH:MM'
      'YYYY年M月DD日木曜日 午後HH時...'
    """
    raw = raw.strip()
    # Remove DOW annotations e.g.（土）（水・祝）(月) — replace with space to preserve adjacent digit spacing
    raw = re.sub(r"[（(][月火水木金土日・祝]+[）)]", " ", raw)
    # Remove time qualifiers like 午後
    raw = re.sub(r"午[前後]", "", raw)

    # YYYY年M月DD日
    m = re.search(r"(\d{4})年(\d+)月(\d+)日", raw)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        # YYYY/M/DD
        m = re.search(r"(\d{4})/(\d+)/(\d+)", raw)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            return None

    # Time: ASCII or full-width colon/tilde, format HH:MM or HH時
    tm = re.search(r"(\d{1,2})[：:](\d{2})", raw)
    if not tm:
        tm = re.search(r"(\d{1,2})時", raw)
        hour = int(tm.group(1)) if tm else 0
        minute = 0
    else:
        hour, minute = int(tm.group(1)), int(tm.group(2))

    try:
        return datetime(year, month, day, hour, minute, tzinfo=JST)
    except ValueError:
        logger.warning("Invalid date: %r", raw)
        return None


def _fetch_posts(page: int) -> list[dict]:
    """Fetch a page of posts from the Waseda Taiwan WP REST API."""
    params = {
        "per_page": PER_PAGE,
        "page": page,
        "_fields": "id,link,title,date,content",
        "orderby": "date",
        "order": "desc",
    }
    try:
        resp = requests.get(API_BASE, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("Waseda Taiwan API error (page %d): %s", page, exc)
        return []


class WasedaTaiwanScraper(BaseScraper):
    """Scraper for Waseda University Taiwan Research Institute events."""

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        cutoff = datetime.now(JST) - timedelta(days=LOOKBACK_DAYS)

        for page_num in range(1, MAX_PAGES + 1):
            posts = _fetch_posts(page_num)
            if not posts:
                break

            logger.info("Waseda Taiwan page %d: %d posts", page_num, len(posts))

            for post in posts:
                content_html = post.get("content", {}).get("rendered", "")
                content = _strip_html(content_html)

                # Skip non-event posts (working papers, newsletters, etc.)
                if not _EVENT_MARKERS.search(content):
                    continue

                post_id = post["id"]
                title = _strip_html(post.get("title", {}).get("rendered", ""))
                link: str = post.get("link", "")

                # Date extraction — try multiple label variants
                # Normalize: '日 時：' → captured by r'日\s*時[\s：:]+'
                date_raw = _extract_after_label(
                    content,
                    r"(?:開催日時|日\s*時)"
                )
                # Also try '開催日：' if above fails
                if not date_raw:
                    date_raw = _extract_after_label(content, r"開催日")

                start_date = _parse_date(date_raw) if date_raw else None

                if start_date and start_date < cutoff:
                    logger.debug("Skipping old Waseda event: %s (%s)", title, date_raw)
                    continue

                # If no date at all, skip (not a well-structured event post)
                if not start_date:
                    logger.debug("No date found in post %d: %s", post_id, title)
                    continue

                # Venue extraction — try multiple label variants
                venue_raw = (
                    _extract_after_label(content, r"(?:場\s*所|会\s*場|開催場所)")
                    or ""
                )
                # Take first part up to common delimiters
                venue = re.split(r"[（(]東京都|　|プログラム", venue_raw)[0].strip()[:120]
                # Include full address if it has prefecture prefix
                location_address = venue_raw.split()[0][:150] if venue_raw else None
                # If venue contains full address (東京都...) use it directly
                addr_m = re.search(r"(東京都[^\s]{5,60})", venue_raw)
                if addr_m:
                    location_address = addr_m.group(1).rstrip("）)）")
                elif venue:
                    location_address = venue

                raw_desc_parts = []
                if date_raw:
                    raw_desc_parts.append(f"開催日時: {date_raw}")
                if venue:
                    raw_desc_parts.append(f"会場: {venue_raw[:200] or venue}")
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
                    location_address=location_address or None,
                    is_paid=False,
                    raw_title=title,
                    raw_description=raw_description,
                ))
                logger.info("Waseda Taiwan: found event: %s", title)

        logger.info("waseda_taiwan: scraped %d events", len(events))
        return events
