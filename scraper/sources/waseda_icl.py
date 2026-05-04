"""Scraper for 早稲田大学比較法研究所 (Waseda Institute of Comparative Law).

Site: https://www.waseda.jp/folaw/icl/news/
Type: WordPress REST API (unlike waseda.jp/gsaps/, this subdirectory is NOT Cloudflare-blocked)
Auth: None
Rate limit: None observed

Strategy:
  1. Query WP REST API with search=台湾 (and Taiwan) — returns all matching posts
  2. Skip 開催報告 posts (title contains 開催されました / 【開催報告】) — event already passed
  3. Skip posts without a date label in content — not an event post
  4. Skip posts where title lacks Taiwan/日台 keyword — content-only mentions not strong enough
  5. Extract event date from 【開催日時】 / 【日　時】 labels
  6. Extract venue from 【開催会場名】 / 【場　所】 labels
  7. source_id = "waseda_icl_{wp_post_id}" (stable WP post ID)

Frequency: ~1–2 genuinely Taiwan-focused events per year (legal symposia, lectures).
Note: Some events are co-hosted with waseda-taiwan.com but posted separately — no overlap
with waseda_taiwan.py (different post IDs, different site).
"""

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "waseda_icl"
API_BASE = "https://www.waseda.jp/folaw/icl/wp-json/wp/v2/posts"
PER_PAGE = 50
MAX_PAGES = 3          # up to 150 posts — covers several years of Taiwan results
LOOKBACK_DAYS = 120    # look back 4 months

JST = timezone(timedelta(hours=9))

# Taiwan relevance: TITLE must contain these keywords
_TAIWAN_TITLE_RE = re.compile(r"台湾|日台|Taiwan|臺灣")

# Report posts (event already happened) — skip them
_REPORT_RE = re.compile(r"【開催報告】|開催されました|が開催されました")

# Event detection: content must have a date label inside 【】
_EVENT_DATE_LABEL_RE = re.compile(r"【[^】]*(?:開催日時|日\s*時)[^】]*】|(?:開催日時|日\s*時)[：:：]")

_STOP_LABELS = [
    "使用言語", "言語", "プログラム", "定員", "申込", "主催", "共催",
    "参加", "費用", "講師", "コメンテーター", "司会", "報告者",
    "世話人", "対象", "概要", "問い合わせ", "■", "●", "※", "http",
]

# Search terms — ordered by specificity; dedup by post ID across terms
_SEARCH_TERMS = ["台湾", "Taiwan"]


def _strip_html(raw_html: str) -> str:
    """Strip HTML tags, decode entities, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", raw_html or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_after_bracket_label(text: str, label_re: str) -> Optional[str]:
    """Extract value after a 【label】 marker, stopping at the next 【 or end.

    Handles:
      【開催日時】2026年1月9日15時〜17時 【開催会場名】…
      【日　時】 2025年3月8日（土）13:00～18:30 【場　所】…
    """
    m = re.search(
        r"【[^】]*(?:" + label_re + r")[^】]*】\s*(.+?)(?=\s*【|\Z)",
        text,
        re.DOTALL,
    )
    if not m:
        # Fallback: colon-style label outside brackets
        m = re.search(r"(?:" + label_re + r")[：:：\s]+(.+)", text)
    if not m:
        return None

    val = re.sub(r"\s+", " ", m.group(1)).strip()
    for stop in _STOP_LABELS:
        if len(stop) <= 2 and not stop[0].isalpha():
            stop_m = re.search(r"\s+" + re.escape(stop), val)
        else:
            stop_m = re.search(r"\s+" + re.escape(stop) + r"[\s：:]", val)
        if stop_m:
            val = val[: stop_m.start()]
    return val.strip()[:200] or None


def _parse_date(raw: str) -> Optional[datetime]:
    """Parse Japanese event date string to timezone-aware datetime (JST)."""
    if not raw:
        return None
    raw = raw.strip()
    # Remove DOW annotations e.g. （土）（水・祝）— replace with space to preserve digit spacing
    raw = re.sub(r"[（(][月火水木金土日・祝]+[）)]", " ", raw)
    raw = re.sub(r"午[前後]", "", raw)

    # YYYY年M月DD日
    m = re.search(r"(\d{4})年(\d+)月(\d+)日", raw)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.search(r"(\d{4})/(\d+)/(\d+)", raw)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            return None

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
        logger.warning("waseda_icl: invalid date parsed from %r", raw)
        return None


def _fetch_posts(page: int, search_term: str) -> tuple[list[dict], bool]:
    """Fetch one page of posts. Returns (posts, has_more_pages)."""
    params = {
        "per_page": PER_PAGE,
        "page": page,
        "search": search_term,
        "_fields": "id,link,title,date,content",
        "orderby": "date",
        "order": "desc",
    }
    try:
        resp = requests.get(API_BASE, params=params, timeout=20)
        resp.raise_for_status()
        posts = resp.json()
        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        return posts, page < total_pages
    except Exception as exc:
        logger.error("waseda_icl: API error (page=%d search=%r): %s", page, search_term, exc)
        return [], False


class WasedaIclScraper(BaseScraper):
    """Scraper for Waseda Institute of Comparative Law Taiwan-related events."""

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        seen_ids: set[int] = set()
        cutoff = datetime.now(JST) - timedelta(days=LOOKBACK_DAYS)

        for search_term in _SEARCH_TERMS:
            page = 1
            while page <= MAX_PAGES:
                posts, has_more = _fetch_posts(page, search_term)
                if not posts:
                    break

                logger.info(
                    "waseda_icl: '%s' page %d: %d posts", search_term, page, len(posts)
                )

                for post in posts:
                    post_id = post["id"]
                    if post_id in seen_ids:
                        continue
                    seen_ids.add(post_id)

                    title = _strip_html(post.get("title", {}).get("rendered", ""))
                    content = _strip_html(
                        post.get("content", {}).get("rendered", "")
                    )
                    link: str = post.get("link", "")

                    # Skip 開催報告 posts — event has already passed
                    if _REPORT_RE.search(title):
                        logger.debug(
                            "waseda_icl: skip report post [%d]: %s", post_id, title[:60]
                        )
                        continue

                    # Taiwan relevance: title must mention Taiwan/日台
                    if not _TAIWAN_TITLE_RE.search(title):
                        logger.debug(
                            "waseda_icl: skip non-Taiwan title [%d]: %s",
                            post_id,
                            title[:60],
                        )
                        continue

                    # Event detection: must have a date label
                    if not _EVENT_DATE_LABEL_RE.search(content):
                        logger.debug(
                            "waseda_icl: no date label in post [%d]: %s",
                            post_id,
                            title[:60],
                        )
                        continue

                    # Date extraction
                    date_raw = _extract_after_bracket_label(
                        content, r"開催日時|日\s*時"
                    )
                    start_date = _parse_date(date_raw) if date_raw else None
                    if not start_date:
                        logger.debug(
                            "waseda_icl: no date parsed in post [%d]: %s",
                            post_id,
                            title[:60],
                        )
                        continue

                    if start_date < cutoff:
                        logger.debug(
                            "waseda_icl: old event, skip [%d]: %s", post_id, title[:60]
                        )
                        continue

                    # Venue extraction
                    venue_raw = (
                        _extract_after_bracket_label(
                            content, r"開催会場名|場\s*所|会\s*場|開催場所"
                        )
                        or ""
                    )
                    # Take first segment (before full-width space or first parenthetical)
                    venue = re.split(r"[　\s]", venue_raw)[0].strip()[:120]
                    # Extract Tokyo address if present
                    addr_m = re.search(r"(東京都[^\s（(]{5,60})", venue_raw)
                    if addr_m:
                        location_address: Optional[str] = addr_m.group(1).rstrip("）)")
                    else:
                        location_address = venue or None

                    raw_parts: list[str] = []
                    if date_raw:
                        raw_parts.append(f"開催日時: {date_raw}")
                    if venue_raw:
                        raw_parts.append(f"会場: {venue_raw[:200]}")
                    raw_description = (
                        "\n\n".join(raw_parts) if raw_parts else content[:400]
                    )

                    events.append(
                        Event(
                            source_name=SOURCE_NAME,
                            source_id=f"{SOURCE_NAME}_{post_id}",
                            source_url=link,
                            original_language="ja",
                            name_ja=title,
                            category=["academic", "taiwan_japan"],
                            start_date=start_date,
                            location_name=venue or None,
                            location_address=location_address,
                            is_paid=False,
                            raw_title=title,
                            raw_description=raw_description,
                        )
                    )
                    logger.info(
                        "waseda_icl: found event [%d]: %s (%s)",
                        post_id,
                        title[:60],
                        start_date.date(),
                    )

                if not has_more:
                    break
                page += 1

        logger.info("waseda_icl: scraped %d events total", len(events))
        return events
