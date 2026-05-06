"""
Scraper for Taiwan-related events in Japan via Google News RSS feeds.

Strategy:
  1. Fetch 4 Google News RSS queries covering Taiwan events/festivals/films/lectures
  2. Filter by Taiwan keywords (title + description)
  3. Skip Yahoo!ニュース aggregations (title ends with "- Yahoo!ニュース") —
     these are always duplicates of original-source articles, and their
     Google News redirect URLs expire faster.
  4. Decode the Google News redirect URL to the original article URL using
     googlenewsdecoder (lightweight HTTP call to Google News API), then fetch
     the full article body for richer annotation (location, dates, etc.).
     Falls back to RSS snippet if decode or fetch fails.
  5. Extract start_date from article text (or RSS snippet as fallback)
  6. Skip items older than 21 days
  7. source_id: gnews_{md5(gnews_link)[:12]} — kept stable (gnews URL, not
     real article URL) so existing DB events are updated rather than duplicated

Note on source_url: set to the real article URL (e.g. prtimes.jp/...) when
resolvable.  Falls back to the Google News redirect URL on failure.
Admin events list now shows the actual publisher domain in the source link.
"""

import hashlib
import logging
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Optional

import requests
from bs4 import BeautifulSoup
from googlenewsdecoder import new_decoderv1

from .base import BaseScraper, Event, dedup_events

_DECODE_SLEEP = 1.0          # polite delay between Google News decode calls
_ARTICLE_FETCH_TIMEOUT = 10
_ARTICLE_FETCH_SLEEP = 0.5   # polite delay between article fetches
_ARTICLE_MAX_CHARS = 4000

_ARTICLE_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_ARTICLE_HEADERS = {
    "User-Agent": _ARTICLE_UA,
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

logger = logging.getLogger(__name__)

QUERIES = [
    "台湾 展覧会 イベント 日本",
    "台湾 フェスティバル 祭り",
    "台湾映画 上映会",
    "台湾 講演 シンポジウム",
]
BASE_RSS = "https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]

# Google News redirect URLs typically expire within 2–3 weeks
_STALE_DAYS = 21


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(self._chunks).strip()


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


def _decode_gnews_url(gnews_url: str) -> Optional[str]:
    """Resolve a Google News redirect URL to the original article URL.

    Uses googlenewsdecoder which makes a lightweight call to the Google News
    API to retrieve the canonical article URL.  The RSS <description> hrefs
    are also Google News URLs, so we decode from the <link> element URL.
    Returns None if decoding fails (network error, unsupported format, etc.).
    """
    try:
        result = new_decoderv1(gnews_url, interval=0)
        if result and result.get("status") and result.get("decoded_url"):
            decoded = result["decoded_url"]
            if decoded and "google.com" not in decoded:
                return decoded
    except Exception as exc:
        logger.debug("google_news_rss: URL decode failed %s: %s", gnews_url[:60], exc)
    return None


def _fetch_article_text(url: str) -> Optional[str]:
    """Fetch plain text from original article URL.

    Tries several CSS selectors to isolate the article body.
    Returns up to _ARTICLE_MAX_CHARS of plain text, or None on any failure.
    Anti-bot 403/429 responses are silently ignored (fallback to RSS snippet).
    """
    try:
        resp = requests.get(
            url,
            headers=_ARTICLE_HEADERS,
            timeout=_ARTICLE_FETCH_TIMEOUT,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            logger.debug("google_news_rss: article fetch %s → %d", url, resp.status_code)
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        for sel in [
            "article",
            "main",
            '[role="main"]',
            ".article-body",
            ".post-content",
            ".entry-content",
            ".news-article",
            ".article__body",
            "#article",
            "#content",
        ]:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 80:
                return el.get_text(" ", strip=True)[:_ARTICLE_MAX_CHARS]
        body = soup.find("body")
        if body:
            return body.get_text(" ", strip=True)[:_ARTICLE_MAX_CHARS]
    except Exception as exc:
        logger.debug("google_news_rss: article fetch failed %s: %s", url, exc)
    return None


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _is_yahoo_aggregation(title: str) -> bool:
    """Return True for Yahoo!ニュース aggregation titles.

    These titles follow the pattern "元の記事タイトル (元ソース名) - Yahoo!ニュース"
    or "元の記事タイトル - Yahoo!ニュース".  They are always duplicates of the
    original-source article, so we skip them to avoid redundancy.
    """
    return title.rstrip().endswith("- Yahoo!ニュース")


def _clean_title_for_dedup(title: str) -> str:
    """Strip trailing '- Source Name' / '｜Source Name' suffix from RSS titles.

    Google News RSS titles look like:
      "台湾屋台祭in海老名2026｜レッツエンジョイ東京 - レッツエンジョイ東京"
      "海老名に台湾がやってくる『台湾屋台祭in海老名2026』を開催！ - newscast.jp"

    Stripping the suffix gives a shorter string for fuzzy dedup.  The
    annotator normalises name_ja further; this only improves in-scraper
    dedup before the event reaches the DB.
    """
    # Strip " - Source" or "｜Source" at the end
    cleaned = re.sub(r'\s*[-|｜]\s*\S[^\n]*$', '', title).strip()
    return cleaned or title


def _extract_start_date(description_plain: str, pub_date: datetime) -> Optional[datetime]:
    """Extract start_date from description text.

    Returns None when no date pattern is found — callers must not fall back to
    pub_date, because that is the article *publish* date, not the event date.
    """
    # Pattern 1: YYYY年MM月DD日
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", description_plain)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # Pattern 2: YYYY/MM/DD
    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", description_plain)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # Pattern 3: MM月DD日 — use pubDate year; adjust for Dec→Jan wrap
    m = re.search(r"(\d{1,2})月(\d{1,2})日", description_plain)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = pub_date.year
        if month < pub_date.month - 6:
            year = pub_date.year + 1
        elif month > pub_date.month + 6:
            year = pub_date.year - 1
        try:
            return datetime(year, month, day)
        except ValueError:
            pass

    # No date found — return None rather than the article publish date.
    # pub_date is the date the news article was written, not when the event occurs.
    return None


def _parse_pub_date(pubdate_str: str) -> Optional[datetime]:
    """Parse RSS pubDate string into a naive datetime."""
    try:
        return parsedate_to_datetime(pubdate_str).replace(tzinfo=None)
    except Exception:
        return None


class GoogleNewsRssScraper(BaseScraper):
    SOURCE_NAME = "google_news_rss"

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        now = datetime.now()
        cutoff = now - timedelta(days=_STALE_DAYS)

        for query in QUERIES:
            url = BASE_RSS.format(q=urllib.parse.quote(query))
            try:
                resp = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=15,
                )
                resp.raise_for_status()
                root = ET.fromstring(resp.content)
                channel = root.find("channel")
                if channel is None:
                    logger.warning("google_news_rss: no <channel> in feed for query '%s'", query)
                    time.sleep(1.5)
                    continue

                for item in channel.findall("item"):
                    title_el = item.find("title")
                    item_title = title_el.text.strip() if title_el is not None and title_el.text else ""

                    desc_el = item.find("description")
                    description_html = desc_el.text if desc_el is not None and desc_el.text else ""
                    description_plain = _strip_html(description_html)

                    # Taiwan filter
                    if not _is_taiwan(item_title + " " + description_plain):
                        continue

                    # Skip Yahoo!ニュース aggregations — always duplicates,
                    # and their Google News redirect URLs expire faster
                    if _is_yahoo_aggregation(item_title):
                        logger.debug("google_news_rss: skipping Yahoo aggregation: %s", item_title)
                        continue

                    # pubDate
                    pubdate_el = item.find("pubDate")
                    pub_date = _parse_pub_date(pubdate_el.text) if pubdate_el is not None and pubdate_el.text else now
                    if pub_date is None:
                        pub_date = now

                    # Skip stale items (redirect URLs likely expired)
                    if pub_date < cutoff:
                        continue

                    # Article URL (Google News redirect — works in real browsers)
                    link_el = item.find("link")
                    article_url = link_el.text.strip() if link_el is not None and link_el.text else ""
                    if not article_url:
                        continue

                    # source_id: keep stable gnews-URL-based hash so existing
                    # DB events are updated (not duplicated) on next upsert
                    source_id = f"gnews_{hashlib.md5(article_url.encode()).hexdigest()[:12]}"

                    # Resolve original article URL via googlenewsdecoder
                    original_url = _decode_gnews_url(article_url)
                    time.sleep(_DECODE_SLEEP)
                    article_text: Optional[str] = None
                    if original_url:
                        article_text = _fetch_article_text(original_url)
                        time.sleep(_ARTICLE_FETCH_SLEEP)

                    # source_url: real article URL when available; falls back to
                    # Google News redirect (works in browsers, expires in ~21 days)
                    final_source_url = original_url if original_url else article_url

                    # start_date: only extract when article body is available.
                    # Using RSS snippet as fallback produces unreliable dates
                    # (snippet too short; annotator guesses from sparse text).
                    start_date = _extract_start_date(article_text, pub_date) if article_text else None

                    # raw_description: article body text with publisher domain label.
                    # Always prepend the RSS publish date so GPT has a year anchor
                    # when the event text only mentions a month/day (e.g. "4月に熊本で上映").
                    pub_year_hint = (
                        f"（記事配信日: {pub_date.year}年{pub_date.month}月{pub_date.day}日）\n\n"
                    )
                    if article_text and original_url:
                        domain = urllib.parse.urlparse(original_url).netloc
                        raw_desc = f"開催情報（{domain}）:\n\n{pub_year_hint}{article_text}"
                    else:
                        raw_desc = f"開催情報（Google News）:\n\n{pub_year_hint}{description_plain}"

                    logger.debug(
                        "google_news_rss: %s → real_url=%s article_text=%d chars",
                        item_title[:40],
                        original_url or "(none)",
                        len(article_text) if article_text else 0,
                    )

                    events.append(Event(
                        source_name="google_news_rss",
                        source_id=source_id,
                        source_url=final_source_url,
                        original_language="ja",
                        name_ja=_clean_title_for_dedup(item_title),
                        raw_title=item_title,
                        raw_description=raw_desc,
                        start_date=start_date,
                        category=["report"],
                    ))

            except Exception as e:
                logger.warning("google_news_rss: query '%s' failed: %s", query, e)

            time.sleep(1.5)

        result = dedup_events(events)
        logger.info("google_news_rss: %d events after dedup", len(result))
        return result
