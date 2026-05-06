"""Scraper for 『日本と台湾を考える集い』 (tsudoi-jptw.jimdofree.com).

Osaka-based Taiwan lecture & community event series (第1回〜, 2012–).
Held in Osaka (主に難波・大阪市内), ~5–6 events/year. ALL events are Taiwan-related.

Site: Jimdo free-hosting. Static HTML, no JS rendering required.

Strategy:
  1. Fetch blog category page /ブログ/講演会/ — lists recent event posts
  2. For each post link (href matches /YYYY/MM/DD/…), fetch the detail page
  3. Skip 開催報告 posts: title contains "開催しました" / "開催いたしました"
  4. Extract date from 【日　時】 label in post body
  5. Fallback: parse event date from URL slug (first YYYY-M-D segment after publish date)
  6. Extract venue from 【会　場】 label
  7. source_id = "tsudoi_osaka_{YYYY}{MM}{DD}" (derived from event date — stable)

URL slug date pattern:
  /2025/11/18/2025-12-20-土-第82回-…/
   ^publish    ^event-date in slug

Report-vs-announcement heuristic:
  - Announcement title patterns: "開催します", "開催予定", "開催いたします", "を開催"
  - Report title patterns: "開催しました", "開催いたしました", "開催されました"
  - Posts without either: treat as announcement if 【日　時】 present with a future date

Venue: Osaka area (大阪市浪速区, 難波市民学習センター, etc.)
Default fallback: 難波市民学習センター（大阪市浪速区）
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "tsudoi_osaka"
BASE_URL = "https://tsudoi-jptw.jimdofree.com"
BLOG_CATEGORY_URL = f"{BASE_URL}/ブログ/講演会/"
LOOKBACK_DAYS = 90
PAGE_DELAY = 0.8

JST = timezone(timedelta(hours=9))

# Report (past event) posts — skip these
_REPORT_RE = re.compile(r"開催しました|開催いたしました|開催されました")

# URL date slug pattern: e.g. "2025-12-20-土-第82回-..."
# The slug after the publish date path contains the actual event date
_SLUG_DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/.+?(\d{4})-(\d{1,2})-(\d{1,2})")

# Default venue fallback
_DEFAULT_VENUE = "難波市民学習センター"
_DEFAULT_ADDRESS = "大阪市浪速区湊町１丁目4-1 OCATビル4階"


def _get_soup(url: str) -> Optional[BeautifulSoup]:
    UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.9"}, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as exc:
        logger.error("tsudoi_osaka: fetch error %s: %s", url, exc)
        return None


def _extract_main_content(soup: BeautifulSoup) -> str:
    """Return the main body text after the double navigation menus."""
    text = soup.get_text(separator="\n", strip=True)
    lines = [l for l in text.splitlines() if l.strip()]
    # Jimdo pages have nav menus duplicated; real content starts after second "お問合わせ"
    nav_count = 0
    start = 0
    for i, l in enumerate(lines):
        if l == "お問合わせ":
            nav_count += 1
            if nav_count >= 2:
                start = i + 1
                break
    return "\n".join(lines[start:])


_REIWA_OFFSET = 2018  # 令和N年 = 2018 + N


def _parse_date_from_label(content: str) -> Optional[datetime]:
    """Extract date from 【日　時】 or 【日時】 bracket label.

    Handles both Western year (2025年) and Reiwa era (令和7年) formats.
    """
    m = re.search(
        r"【日[　\s]*時】\s*(.+?)(?=【|\Z)",
        content,
        re.DOTALL,
    )
    if not m:
        return None
    raw = " ".join(m.group(1).split())
    # Remove DOW annotations e.g.（土）（水・祝）
    raw = re.sub(r"[（(][月火水木金土日・祝]+[）)]", " ", raw)
    # Try Western year first: YYYY年M月DD日
    dm = re.search(r"(\d{4})年(\d+)月(\d+)日", raw)
    if dm:
        year, month, day = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
    else:
        # Try Reiwa era: 令和N年M月DD日
        era_m = re.search(r"令和(\d+)年(\d+)月(\d+)日", raw)
        if not era_m:
            return None
        year = _REIWA_OFFSET + int(era_m.group(1))
        month, day = int(era_m.group(2)), int(era_m.group(3))
    # Time
    tm = re.search(r"(\d{1,2})[時：:](\d{2})", raw)
    if tm:
        hour, minute = int(tm.group(1)), int(tm.group(2))
    else:
        tm2 = re.search(r"(\d{1,2})時", raw)
        hour = int(tm2.group(1)) if tm2 else 13
        minute = 0
    try:
        return datetime(year, month, day, hour, minute, tzinfo=JST)
    except ValueError:
        logger.warning("tsudoi_osaka: invalid date in label: %r", raw)
        return None


def _parse_date_from_slug(url: str) -> Optional[datetime]:
    """Extract event date from URL slug pattern /YYYY/MM/DD/YYYY-M-D-曜-…/"""
    m = _SLUG_DATE_RE.search(url)
    if not m:
        return None
    year, month, day = int(m.group(4)), int(m.group(5)), int(m.group(6))
    try:
        return datetime(year, month, day, 13, 30, tzinfo=JST)
    except ValueError:
        return None


def _extract_venue(content: str) -> tuple[Optional[str], Optional[str]]:
    """Return (location_name, location_address) from 【会　場】 label."""
    m = re.search(
        r"【会[　\s]*場】\s*(.+?)(?=【|\Z)",
        content,
        re.DOTALL,
    )
    if not m:
        return None, None
    raw = " ".join(m.group(1).split()).strip()
    if not raw:
        return None, None
    # First line is the venue name, rest is address
    parts = re.split(r"[　\s]", raw, maxsplit=1)
    venue_name = parts[0].strip()[:100]
    # Try to extract address (大阪市... or 〒...)
    addr_m = re.search(r"(大阪[市府][^\s（(]{5,80}|〒\d{3}-\d{4}[^\s]{5,80})", raw)
    if addr_m:
        location_address: Optional[str] = addr_m.group(1).strip()[:150]
    elif len(parts) > 1:
        location_address = parts[1].strip()[:150]
    else:
        location_address = None
    return venue_name or None, location_address


def _get_post_links(soup: BeautifulSoup) -> list[str]:
    """Extract detail page URLs from the blog category listing, deduplicated."""
    links = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=re.compile(r"tsudoi-jptw\.jimdofree\.com/\d{4}/\d{2}/\d{2}/")):
        href = a.get("href", "")
        # Normalise: strip fragment, decode percent-encoding, ensure trailing slash
        href = unquote(href.split("#")[0]).rstrip("/") + "/"
        if href not in seen:
            seen.add(href)
            links.append(href)
    return links


class TsudoiOsakaScraper(BaseScraper):
    """Scraper for 日本と台湾を考える集い — Osaka-based bimonthly Taiwan lecture series."""

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        cutoff = datetime.now(JST) - timedelta(days=LOOKBACK_DAYS)

        soup = _get_soup(BLOG_CATEGORY_URL)
        if not soup:
            logger.error("tsudoi_osaka: failed to fetch blog category page")
            return events

        post_links = _get_post_links(soup)
        logger.info("tsudoi_osaka: found %d post links", len(post_links))

        for url in post_links:
            time.sleep(PAGE_DELAY)

            detail_soup = _get_soup(url)
            if not detail_soup:
                continue

            # Title from <h2> or <h1>
            title_el = detail_soup.select_one("h2, h1.j-main-title, h1")
            title = title_el.get_text(strip=True) if title_el else ""

            # Skip report posts (開催しました etc.)
            if _REPORT_RE.search(title):
                logger.debug("tsudoi_osaka: skip report post: %s", title[:60])
                continue

            content = _extract_main_content(detail_soup)

            # Date extraction: 【日　時】 label first, URL slug fallback
            start_date = _parse_date_from_label(content)
            date_source = "label"
            if not start_date:
                start_date = _parse_date_from_slug(url)
                date_source = "slug"
            if not start_date:
                logger.debug("tsudoi_osaka: no date found in: %s", url)
                continue

            if start_date < cutoff:
                logger.debug(
                    "tsudoi_osaka: old event (%s), skip: %s",
                    start_date.date(),
                    title[:50],
                )
                continue

            location_name, location_address = _extract_venue(content)
            if not location_name:
                location_name = _DEFAULT_VENUE
                location_address = location_address or _DEFAULT_ADDRESS

            # Build raw_description: prepend date, then full content
            date_label_m = re.search(r"【日[　\s]*時】.+?(?=【|\Z)", content, re.DOTALL)
            date_str = " ".join(date_label_m.group().split()) if date_label_m else str(start_date.date())
            raw_description = (
                f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n\n{content[:600]}"
            )

            source_id = f"{SOURCE_NAME}_{start_date.strftime('%Y%m%d')}"

            events.append(
                Event(
                    source_name=SOURCE_NAME,
                    source_id=source_id,
                    source_url=url,
                    original_language="ja",
                    name_ja=title,
                    category=["lecture", "taiwan_japan"],
                    start_date=start_date,
                    end_date=start_date,
                    location_name=location_name,
                    location_address=location_address,
                    is_paid=True,
                    price_info="参加費 1,000円（目安）",
                    raw_title=title,
                    raw_description=raw_description,
                )
            )
            logger.info(
                "tsudoi_osaka: found event [%s]: %s (%s via %s)",
                source_id,
                title[:60],
                start_date.date(),
                date_source,
            )

        logger.info("tsudoi_osaka: scraped %d events total", len(events))
        return events
