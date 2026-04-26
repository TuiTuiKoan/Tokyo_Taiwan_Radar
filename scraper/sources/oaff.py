"""
Scraper for 大阪アジアン映画祭 (Osaka Asian Film Festival — OAFF).

Strategy:
  1. Fetch all "Programs" posts via WordPress REST API:
       GET https://oaff.jp/wp-json/wp/v2/posts?categories=8&per_page=100
     Paginate until no more results.
  2. Filter posts that are Taiwan-relevant:
       - slug matches the pattern *-tw[0-9]+ (dedicated Taiwan special section)
       - OR title/content contains 台湾 / taiwan
  3. Parse festival year from the slug (leading YYYY or trailing YYYY in slug).
  4. Extract first screening date from the post content.
  5. Only include events whose start_date >= today - LOOKBACK_DAYS.

source_name: oaff
source_id  : oaff_{wp_post_id}   — WordPress post ID is stable across runs
source_url : https://oaff.jp/programs/{slug}/

Taiwan filter rationale:
  OAFF runs a dedicated Taiwan section every year ("電影ルネッサンス" / "TAIWAN NIGHT").
  Slugs in the dedicated section follow the pattern {year_str}-tw{NN}.
  Taiwan films also appear in the competition section with no -tw slug; those
  are caught by the 台湾 keyword in the post content/title.

Date format in content (two variants):
  - Full-year: 2025年3月21日（金）18:50
  - Month-day:  3月15日（土）10:10／会場名  (year inferred from slug)
  - Month-day with spaces: 8月30日(土)   11:50   /会場名

No Playwright needed — WP REST API + static HTML detail pages.
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

_WP_API_URL = "https://oaff.jp/wp-json/wp/v2/posts"
_PROGRAMS_CATEGORY_ID = 8   # "Programs" category in WP
_BASE_URL = "https://oaff.jp"

_JST = timezone(timedelta(hours=9))
_LOOKBACK_DAYS = 45   # include events that ended up to 45 days ago

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

# Matches dedicated Taiwan section slugs: 2025-tw01, 2025expo-tw03, expo2025-tw02, etc.
_TW_SLUG_RE = re.compile(r"tw\d+", re.IGNORECASE)

# Title prefix "(NN) " added by OAFF CMS for programme numbering
_TITLE_NUM_RE = re.compile(r"^\(\d+\)\s+")

# Date patterns in post content
_DATE_FULL_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
_DATE_MD_RE = re.compile(
    r"(\d{1,2})月(\d{1,2})日\s*[（(][^）)]{0,6}[）)]\s*(\d{2}:\d{2})"
)
# 2024-era format: M/D(曜) HH:MM
_DATE_SLASH_RE = re.compile(
    r"(\d{1,2})/(\d{1,2})\s*[（(][^）)]{0,5}[）)]\s*(\d{2}:\d{2})"
)


def _infer_year(slug: str) -> int:
    """Extract festival year from a slug like '2025-tw01', '2025expo-tw01',
    'taiwan-night2025', '2025-co03'. Fallback to current year."""
    m = re.search(r"(\d{4})", slug)
    return int(m.group(1)) if m else datetime.now(_JST).year


def _parse_date(content_text: str, year: int) -> datetime | None:
    """Return the first screening date found in the content text."""
    # Pattern A: full YYYY年M月D日 (e.g. TAIWAN NIGHT)
    m = _DATE_FULL_RE.search(content_text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            tzinfo=_JST)
        except ValueError:
            pass

    # Pattern B / C: M月D日（曜）HH:MM  (year from slug context)
    m = _DATE_MD_RE.search(content_text)
    if m:
        try:
            return datetime(year, int(m.group(1)), int(m.group(2)),
                            tzinfo=_JST)
        except ValueError:
            pass

    # Pattern D: M/D(曜) HH:MM (2024-era format)
    m = _DATE_SLASH_RE.search(content_text)
    if m:
        try:
            return datetime(year, int(m.group(1)), int(m.group(2)),
                            tzinfo=_JST)
        except ValueError:
            pass

    return None


def _extract_venue(content_text: str) -> str | None:
    """Extract the first screening venue from scheduling lines such as:
       '3月15日（土）10:10／大阪中之島美術館1Fホール'
       '8月30日(土)   11:50   /大阪中之島美術館1Fホール'
       '3/4(月) 13:00　シネ・リーブル梅田 シネマ4'          (2024 format)
       '日時：...  会場：ABCホール'
    """
    # After a date/time token, venue follows the / or full-width space delimiter
    # Covers both M月D日 and M/D patterns
    m = re.search(
        r"\d{1,2}[月/]\d{1,2}[^\n]*\d{2}:\d{2}\s*[/／　\s]([^\n/／]{5,60})",
        content_text,
    )
    if m:
        venue = m.group(1).strip()
        venue = re.sub(r"\s*(チケット|ゲストあり|￥\d+)\s*$", "", venue).strip()
        if venue:
            return venue

    # TAIWAN NIGHT style: 会場：ABCホール
    m = re.search(r"会場[：:]\s*([^\n]{5,50})", content_text)
    if m:
        return m.group(1).strip()

    return None


def _extract_synopsis(content_text: str) -> str | None:
    """Return the synopsis (paragraph before the 上映予定 block)."""
    # Synopsis is typically the long paragraph after the premiere label
    # and before the 上映予定 section.
    lines = [l.strip() for l in content_text.splitlines() if l.strip()]

    # Locate 上映予定 — synopsis is before it
    idx_schedule = next(
        (i for i, l in enumerate(lines) if l.startswith("上映予定")), len(lines)
    )

    # Skip known non-synopsis tokens near the start
    _SKIP = re.compile(
        r"^(特集企画|コンペティション|スペシャル|インディ|特別|海外初上映|世界初上映"
        r"|日本初上映|アジア初上映|YouTube|予告編|TAIWAN|第\d+回|OAFF|大阪アジアン)",
        re.IGNORECASE,
    )
    synopsis_lines: list[str] = []
    for line in lines[:idx_schedule]:
        if _SKIP.match(line):
            continue
        if len(line) < 15:
            continue
        # Skip lines that look like metadata (year | country | runtime)
        if re.match(r"^\d{4}\s*$", line) or re.match(r"^[台湾|日本|韓国|香港|中国]", line):
            continue
        synopsis_lines.append(line)
        if len(synopsis_lines) >= 3:
            break

    return "\n".join(synopsis_lines) if synopsis_lines else None


class OaffScraper(BaseScraper):
    """Scrapes Taiwan-related film events from 大阪アジアン映画祭 (OAFF)."""

    SOURCE_NAME = "oaff"

    def scrape(self) -> list[Event]:
        cutoff = datetime.now(_JST) - timedelta(days=_LOOKBACK_DAYS)
        events: list[Event] = []
        page = 1

        while True:
            posts = self._fetch_posts(page)
            if not posts:
                break

            for post in posts:
                slug = post.get("slug", "")
                wp_id = post["id"]
                title_raw = BeautifulSoup(
                    post.get("title", {}).get("rendered", ""), "html.parser"
                ).get_text(strip=True)
                content_html = post.get("content", {}).get("rendered", "")
                content_text = BeautifulSoup(content_html, "html.parser").get_text(
                    "\n", strip=True
                )

                # Taiwan relevance filter
                if not self._is_taiwan(slug, title_raw, content_text):
                    continue

                year = _infer_year(slug)
                start_date = _parse_date(content_text, year)

                # Skip events older than cutoff
                if start_date and start_date < cutoff:
                    logger.debug("Skipping past event: %s (%s)", slug, start_date.date())
                    continue

                title = _TITLE_NUM_RE.sub("", title_raw).strip()
                synopsis = _extract_synopsis(content_text)
                venue = _extract_venue(content_text)

                date_prefix = ""
                if start_date:
                    date_prefix = f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n\n"

                raw_desc = f"{date_prefix}{content_text[:800]}" if content_text else date_prefix

                event = Event(
                    source_name=self.SOURCE_NAME,
                    source_id=f"oaff_{wp_id}",
                    source_url=f"{_BASE_URL}/programs/{slug}/",
                    original_language="ja",
                    name_ja=title or title_raw,
                    description_ja=synopsis,
                    raw_title=title_raw,
                    raw_description=raw_desc or None,
                    start_date=start_date,
                    location_name=venue or "大阪中之島美術館",
                    location_address="大阪府大阪市北区中之島4丁目3-1",
                    is_paid=True,
                    category=["movie"],
                )
                events.append(event)
                logger.info(
                    "  ✓ oaff_%d [%s] %s (%s)",
                    wp_id,
                    slug,
                    title[:50],
                    start_date.strftime("%Y-%m-%d") if start_date else "no-date",
                )
                time.sleep(0.3)

            if len(posts) < 100:
                break
            page += 1

        logger.info("OaffScraper: %d Taiwan events found", len(events))
        return events

    def _fetch_posts(self, page: int) -> list[dict]:
        """Fetch one page of Program posts from the WP REST API."""
        try:
            r = requests.get(
                _WP_API_URL,
                params={
                    "categories": _PROGRAMS_CATEGORY_ID,
                    "per_page": 100,
                    "page": page,
                    "orderby": "date",
                    "order": "desc",
                    "_fields": "id,slug,title,content,date,excerpt",
                },
                headers=_HEADERS,
                timeout=20,
            )
            if r.status_code == 400:
                # WordPress returns 400 when page exceeds total pages
                return []
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.warning("OAFF WP API error (page %d): %s", page, exc)
            return []

    @staticmethod
    def _is_taiwan(slug: str, title: str, content: str) -> bool:
        """Return True if this post is related to Taiwan."""
        if _TW_SLUG_RE.search(slug):
            return True
        combined = (title + " " + content[:500]).lower()
        return "台湾" in combined or "taiwan" in combined
