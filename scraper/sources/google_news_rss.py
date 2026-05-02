"""
Scraper for Taiwan-related events in Japan via Google News RSS feeds.

Strategy:
  1. Fetch 4 Google News RSS queries covering Taiwan events/festivals/films/lectures
  2. Filter by Taiwan keywords (title + description)
  3. Skip Yahoo!ニュース aggregations (title ends with "- Yahoo!ニュース") —
     these are always duplicates of original-source articles, and their
     Google News redirect URLs expire faster.
  4. Extract start_date from description text (Japanese/slash date patterns)
  5. Skip items older than 21 days (Google News redirect URLs typically expire
     within 2–3 weeks; keeping them longer shows broken links to users)
  6. source_id: gnews_{md5(link)[:12]}

Note on source_url: Google News RSS <link> values are always
news.google.com/rss/articles/... redirect URLs.  These work in a real
browser (Google redirects to the original article) but cannot be resolved
server-side.  The 21-day TTL ensures stale events are pruned before the
redirect expires.
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

from .base import BaseScraper, Event, dedup_events

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

                    source_id = f"gnews_{hashlib.md5(article_url.encode()).hexdigest()[:12]}"
                    start_date = _extract_start_date(description_plain, pub_date)

                    events.append(Event(
                        source_name="google_news_rss",
                        source_id=source_id,
                        source_url=article_url,
                        original_language="ja",
                        name_ja=_clean_title_for_dedup(item_title),
                        raw_title=item_title,
                        raw_description=f"開催情報（Google News）:\n\n{description_plain}",
                        start_date=start_date,
                        category=["report"],
                    ))

            except Exception as e:
                logger.warning("google_news_rss: query '%s' failed: %s", query, e)

            time.sleep(1.5)

        result = dedup_events(events)
        logger.info("google_news_rss: %d events after dedup", len(result))
        return result
