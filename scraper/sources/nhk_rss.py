"""
Scraper for Taiwan-related news via NHK RSS feeds.

Strategy:
  1. Fetch NHK news category RSS feeds (international + culture/science)
  2. Filter by Taiwan keywords (title + description)
  3. Extract start_date from description text; fallback to pubDate
  4. Skip items older than 90 days
  5. source_id: nhk_{md5(url)[:12]}
"""

import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Optional

import requests

from .base import BaseScraper, Event, dedup_events

logger = logging.getLogger(__name__)

NHK_FEEDS = [
    "https://www3.nhk.or.jp/rss/news/cat4.xml",  # international
    "https://www3.nhk.or.jp/rss/news/cat7.xml",  # culture/science
]

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]

_STALE_DAYS = 90


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


def _extract_start_date(description_plain: str, pub_date: datetime) -> datetime:
    """Extract start_date from description text. Fallback to pub_date."""
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

    # Fallback: use pubDate itself
    return pub_date


def _parse_pub_date(pubdate_str: str) -> Optional[datetime]:
    """Parse RSS pubDate string into a naive datetime."""
    try:
        return parsedate_to_datetime(pubdate_str).replace(tzinfo=None)
    except Exception:
        return None


class NhkRssScraper(BaseScraper):
    SOURCE_NAME = "nhk_rss"

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        now = datetime.now()
        cutoff = now - timedelta(days=_STALE_DAYS)

        for feed_url in NHK_FEEDS:
            try:
                resp = requests.get(
                    feed_url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=15,
                )
                resp.raise_for_status()
                root = ET.fromstring(resp.content)
                channel = root.find("channel")
                if channel is None:
                    logger.warning("nhk_rss: no <channel> in feed %s", feed_url)
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

                    # pubDate
                    pubdate_el = item.find("pubDate")
                    pub_date = _parse_pub_date(pubdate_el.text) if pubdate_el is not None and pubdate_el.text else now
                    if pub_date is None:
                        pub_date = now

                    # Skip stale items
                    if pub_date < cutoff:
                        continue

                    # Item link
                    link_el = item.find("link")
                    item_link = link_el.text.strip() if link_el is not None and link_el.text else ""
                    if not item_link:
                        # Try guid as fallback
                        guid_el = item.find("guid")
                        item_link = guid_el.text.strip() if guid_el is not None and guid_el.text else ""
                    if not item_link:
                        continue

                    source_id = f"nhk_{hashlib.md5(item_link.encode()).hexdigest()[:12]}"
                    start_date = _extract_start_date(description_plain, pub_date)

                    events.append(Event(
                        source_name="nhk_rss",
                        source_id=source_id,
                        source_url=item_link,
                        original_language="ja",
                        name_ja=item_title,
                        raw_title=item_title,
                        raw_description=f"NHKニュース:\n\n{description_plain}",
                        start_date=start_date,
                        category=["report", "books_media"],
                    ))

            except Exception as e:
                logger.warning("nhk_rss: feed %s failed: %s", feed_url, e)

        result = dedup_events(events)
        logger.info("nhk_rss: %d events after dedup", len(result))
        return result
