"""
Scraper for 台北駐大阪経済文化弁事処 (Taipei Economic and Cultural Office in Osaka).

URL: https://www.roc-taiwan.org/jposa_ja/

Strategy:
  1. Consume WordPress RSS feeds for 政務 and 文教 categories (paginated).
  2. Filter titles using event-type keywords to exclude pure diplomatic visit reports.
  3. Fetch the detail page (static HTML, no Playwright needed) to extract
     event date and venue from the body text.
  4. Fallback to RSS pubDate when the body contains no extractable date.

Source ID format: jposa_ja_{post_id}
  where post_id is the numeric ID from /jposa_ja/post/NNNNN.html

Geographic scope:
  The Osaka office's jurisdiction covers Kansai + Chūbu + Hokuriku + Chūgoku + Shikoku.
  All events within this geographic area are in scope (All-Japan coverage).

Low-yield note:
  Most posts are diplomatic visit reports. Cultural event posts occur irregularly,
  roughly 1–3 per month. LOOKBACK_DAYS = 180 ensures we catch all of them.
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_NAME = "jposa_ja"
_BASE_URL = "https://www.roc-taiwan.org"
_OFFICE_LOCATION = "大阪市北区中之島2丁目3番18号 中之島フェスティバルタワー"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA, "Accept-Language": "ja,en;q=0.9"}

# RSS feeds to consume — 政務 (activities) + 文教 (culture/education)
_FEED_URLS = [
    _BASE_URL + "/jposa_ja/category/%e6%94%bf%e5%8b%99/feed/",   # 政務
    _BASE_URL + "/jposa_ja/category/%e6%96%87%e6%95%99/feed/",   # 文教
]

_MAX_PAGES = 20          # 10 items/page × 20 pages = up to 200 items per feed
LOOKBACK_DAYS = 180      # Irregular publishing; extend window to avoid gaps
_DELAY = 0.3             # Polite delay between detail page requests

# ---------------------------------------------------------------------------
# Keyword filters
# ---------------------------------------------------------------------------

# Title must contain at least one of these to be considered an event
_EVENT_KW = re.compile(
    r"上映会?|展示会?|展覧会|公演|コンサート|フェスティバル|フェスタ|フェス(?!ン)|"
    r"イベント|講演会?|セミナー|映画会?|音楽祭|文化祭|フォーラム|シンポジウム|"
    r"台湾祭|台湾フェス|台湾映画|台湾コンサート|体験|交流会|博覧会|式典|"
    r"文化行事|コンクール|コンテスト|ワークショップ|授賞式|発表会|展示|台湾フード"
)

# Skip posts that are purely diplomatic/administrative (not public events)
_SKIP_KW = re.compile(
    r"の表敬訪問を受ける$|の訪問を受ける$|と面会$|による表敬訪問$|"
    r"を受けた$|一行を歓迎$|への表敬訪問$|"
    r"(?:申請|募集|応募|申込|お知らせ)(?:要項|期間|方法)$"
)

# ---------------------------------------------------------------------------
# Date / Venue extraction
# ---------------------------------------------------------------------------

# Full-year kanji date: 2026年4月11日
_DATE_FULL = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
# Month-day only (no year): 4月11日
_DATE_MD = re.compile(r"(\d{1,2})月(\d{1,2})日[（(]?[月火水木金土日祝・]?[）)]?")
# Labeled date section
_DATE_LABEL = re.compile(
    r"(?:日時|開催日時|日程|開催日|上映日時)[：:]\s*(.{5,80})",
    re.MULTILINE,
)
# Venue label
_VENUE_LABEL = re.compile(
    r"(?:開催場所|会場|場所|開催地|会場名)[：:]\s*([^\n。]{3,60})",
    re.MULTILINE,
)
# Post ID from URL
_POST_ID_RE = re.compile(r"/post/(\d+)\.html")


def _parse_rfc2822(date_str: str) -> Optional[datetime]:
    """Parse an RFC 2822 pubDate string to a naive JST datetime."""
    try:
        dt = parsedate_to_datetime(date_str)
        # Convert to JST (UTC+9) naive datetime
        jst = timezone(timedelta(hours=9))
        return dt.astimezone(jst).replace(tzinfo=None)
    except Exception:
        return None


def _extract_date_from_body(body_text: str, pub_dt: Optional[datetime]) -> Optional[datetime]:
    """Extract event date from the post body text.

    Priority:
      1. Labeled date field (日時：/ 開催日時：)
      2. Full-year kanji date (2026年4月11日) in body
      3. Month-day only (4月11日) → year inferred from pub_dt
      4. fallback: pub_dt (publish date ≈ event date for same-day recap posts)
    """
    # 1. Labeled field
    m = _DATE_LABEL.search(body_text)
    if m:
        date_str = m.group(1)
        fm = _DATE_FULL.search(date_str)
        if fm:
            try:
                return datetime(int(fm.group(1)), int(fm.group(2)), int(fm.group(3)))
            except ValueError:
                pass
        md = _DATE_MD.search(date_str)
        if md and pub_dt:
            month, day = int(md.group(1)), int(md.group(2))
            for year in (pub_dt.year, pub_dt.year + 1, pub_dt.year - 1):
                try:
                    candidate = datetime(year, month, day)
                    if abs((candidate - pub_dt).days) <= 365:
                        return candidate
                except ValueError:
                    continue

    # 2. Full-year date in body
    all_full = list(_DATE_FULL.finditer(body_text))
    if all_full:
        for m2 in all_full:
            try:
                candidate = datetime(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
                # Must be plausible event date: within ±30 days of pubDate
                if pub_dt and abs((candidate - pub_dt).days) <= 30:
                    return candidate
                elif not pub_dt:
                    return candidate
            except ValueError:
                continue
        # If nothing within 30 days, take the first
        try:
            m3 = all_full[0]
            return datetime(int(m3.group(1)), int(m3.group(2)), int(m3.group(3)))
        except ValueError:
            pass

    # 3. Month-day in body (requires pub_dt for year inference)
    if pub_dt:
        all_md = list(_DATE_MD.finditer(body_text))
        for md2 in all_md:
            month, day = int(md2.group(1)), int(md2.group(2))
            for year in (pub_dt.year, pub_dt.year + 1, pub_dt.year - 1):
                try:
                    candidate = datetime(year, month, day)
                    if abs((candidate - pub_dt).days) <= 30:
                        return candidate
                except ValueError:
                    continue

    # 4. Fallback: publish date
    return pub_dt


def _extract_venue_from_body(body_text: str) -> Optional[str]:
    """Extract venue/location from labeled field in post body."""
    m = _VENUE_LABEL.search(body_text)
    if m:
        venue = m.group(1).strip()
        venue = re.split(r"[。\n]", venue)[0].strip()
        if venue:
            return venue
    return None


def _fetch_detail(url: str, session: requests.Session) -> str:
    """Fetch a post detail page and return the main body text.

    Returns "" on failure.
    """
    try:
        resp = session.get(url, headers=_HEADERS, timeout=20)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        # Content is in a [class*='content'] div
        body_el = (
            soup.select_one("[class*='content']")
            or soup.select_one("article")
            or soup.select_one("main")
        )
        if not body_el:
            return ""
        return body_el.get_text(separator="\n", strip=True)
    except Exception as exc:
        logger.debug("Detail fetch error for %s: %s", url, exc)
        return ""


def _parse_rss_items(rss_text: str) -> list[dict]:
    """Extract items from RSS XML text using regex (avoids lxml dependency)."""
    items = []
    for raw in re.findall(r"<item>(.*?)</item>", rss_text, re.DOTALL):
        # title
        tm = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", raw) or \
             re.search(r"<title>(.*?)</title>", raw)
        title = (tm.group(1).strip() if tm else "")
        # link — skip the atom:link element
        lm = re.search(r"<link>(https?://[^<]+)</link>", raw)
        link = lm.group(1).strip() if lm else ""
        if not link:
            # fallback: guid
            gm = re.search(r"<guid[^>]*>(https?://[^<]+)</guid>", raw)
            link = gm.group(1).strip() if gm else ""
        # pubDate
        pm = re.search(r"<pubDate>(.*?)</pubDate>", raw)
        pub_str = pm.group(1).strip() if pm else ""
        # content:encoded
        cm = re.search(r"<content:encoded><!\[CDATA\[(.*?)\]\]></content:encoded>",
                        raw, re.DOTALL)
        content_html = cm.group(1) if cm else ""

        if title and link:
            items.append({
                "title": title,
                "link": link,
                "pub_str": pub_str,
                "content_html": content_html,
            })
    return items


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


class JposaJaScraper(BaseScraper):
    """Scrapes cultural event posts from 台北駐大阪経済文化弁事処 (Osaka TECO)."""

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        session = requests.Session()
        cutoff = datetime.now() - timedelta(days=LOOKBACK_DAYS)
        seen_ids: set[str] = set()
        events: list[Event] = []

        for feed_url in _FEED_URLS:
            for page in range(1, _MAX_PAGES + 1):
                url = f"{feed_url}?paged={page}"
                try:
                    resp = session.get(url, headers=_HEADERS, timeout=20)
                    resp.raise_for_status()
                except Exception as exc:
                    logger.warning("RSS fetch error [%s p%d]: %s", feed_url, page, exc)
                    break

                items = _parse_rss_items(resp.text)
                if not items:
                    break

                hit_cutoff = False
                for item in items:
                    pub_dt = _parse_rfc2822(item["pub_str"])
                    if pub_dt and pub_dt < cutoff:
                        hit_cutoff = True
                        break

                    title = item["title"]

                    # Must have an event-type keyword
                    if not _EVENT_KW.search(title):
                        continue
                    # Skip pure diplomatic/admin posts
                    if _SKIP_KW.search(title):
                        continue

                    # Extract post ID from URL
                    link = item["link"]
                    pid_m = _POST_ID_RE.search(link)
                    if not pid_m:
                        continue
                    post_id = pid_m.group(1)
                    source_id = f"jposa_ja_{post_id}"
                    if source_id in seen_ids:
                        continue
                    seen_ids.add(source_id)

                    # Try body text from content:encoded first, else detail page
                    if item["content_html"]:
                        soup = BeautifulSoup(item["content_html"], "html.parser")
                        body_text = soup.get_text(separator="\n", strip=True)
                    else:
                        body_text = _fetch_detail(link, session)
                        time.sleep(_DELAY)

                    if not body_text:
                        body_text = title

                    start_date = _extract_date_from_body(body_text, pub_dt)
                    venue = _extract_venue_from_body(body_text)

                    # Prepend date info to raw_description
                    if start_date:
                        date_prefix = (
                            f"開催日時: {start_date.year}年"
                            f"{start_date.month:02d}月{start_date.day:02d}日\n\n"
                        )
                        raw_desc = date_prefix + body_text[:3000]
                    else:
                        raw_desc = body_text[:3000]

                    events.append(
                        Event(
                            source_name=SOURCE_NAME,
                            source_id=source_id,
                            source_url=link,
                            original_language="ja",
                            raw_title=title,
                            raw_description=raw_desc,
                            start_date=start_date,
                            end_date=start_date,
                            location_name=venue,
                            location_address=venue,
                            is_active=True,
                        )
                    )

                if hit_cutoff:
                    break
                if len(items) < 10:
                    break

                time.sleep(_DELAY)

        # Dedup across feeds
        seen_final: set[str] = set()
        deduped: list[Event] = []
        for ev in events:
            if ev.source_id not in seen_final:
                seen_final.add(ev.source_id)
                deduped.append(ev)

        logger.info("JposaJaScraper: %d events found", len(deduped))
        return deduped
