"""
Scraper for 台湾原住民族との交流会 (FTIP Japan).

Source: WordPress RSS feed at /category/event/feed
All posts are Taiwan-related; no keyword filter needed.
source_id: ftip_{post_id} from GUID (?p=NNN)
URL: link.next_sibling from RSS (e.g., https://www.ftip-japan.org/717)
Date: extracted from title or content, fallback to pubDate.
"""

import logging
import re
import time
import warnings
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

RSS_URL = "https://www.ftip-japan.org/category/event/feed"
LOCATION_NAME = "台湾原住民族との交流会"
LOCATION_ADDRESS = "東京都"  # Organization is nationwide

# Date patterns for extracting event dates from text
DATE_PATTERNS = [
    # YYYY年M月D日
    re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日"),
    # YYYY/M/D
    re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})"),
    # M/D(曜) — use pubDate year for year inference
    re.compile(r"(\d{1,2})/(\d{1,2})[（\(][日月火水木金土]"),
    # M月D日 — use pubDate year
    re.compile(r"(\d{1,2})月(\d{1,2})日"),
]


def _extract_date_from_text(text: str, pub_date: datetime) -> Optional[datetime]:
    """Try to extract the earliest future-ish date from text."""
    # Full date first (most reliable)
    m = DATE_PATTERNS[0].search(text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = DATE_PATTERNS[1].search(text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # M/D pattern — derive year from pubDate
    year = pub_date.year
    m = DATE_PATTERNS[2].search(text)
    if m:
        mo, day = int(m.group(1)), int(m.group(2))
        try:
            candidate = datetime(year, mo, day)
            # If candidate is more than 3 months before pubDate, try next year
            if (pub_date - candidate).days > 90:
                candidate = datetime(year + 1, mo, day)
            return candidate
        except ValueError:
            pass

    # M月D日 pattern
    m = DATE_PATTERNS[3].search(text)
    if m:
        mo, day = int(m.group(1)), int(m.group(2))
        try:
            candidate = datetime(year, mo, day)
            if (pub_date - candidate).days > 90:
                candidate = datetime(year + 1, mo, day)
            return candidate
        except ValueError:
            pass

    return None


def _parse_pub_date(pub_date_str: str) -> Optional[datetime]:
    try:
        dt = parsedate_to_datetime(pub_date_str)
        return dt.replace(tzinfo=None)
    except Exception:
        return None


def _extract_post_id(guid: str) -> Optional[str]:
    m = re.search(r"\?p=(\d+)", guid)
    return m.group(1) if m else None


class FtipScraper(BaseScraper):
    """Scrapes events from 台湾原住民族との交流会 RSS feed."""

    SOURCE_NAME = "ftip"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        try:
            resp = self._session.get(RSS_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Failed to fetch FTIP RSS: %s", exc)
            return events

        soup = BeautifulSoup(resp.content, "html.parser")
        items = soup.find_all("item")
        logger.info("FTIP RSS: %d items", len(items))

        # Extract per-item link URLs from raw text (BS4 drops <link> in HTML mode)
        raw_text = resp.text
        link_urls = re.findall(r"<link>(https?://[^<]+)</link>", raw_text)
        # First URL is the channel link; items start from index 1
        item_urls = link_urls[1:]

        for idx, item in enumerate(items):
            title_el = item.find("title")
            pub_el = item.find("pubdate")
            guid_el = item.find("guid")
            content_el = item.find("content:encoded") or item.find("description")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            pub_date_str = pub_el.get_text(strip=True) if pub_el else ""
            guid_text = guid_el.get_text(strip=True) if guid_el else ""
            content_html = content_el.get_text() if content_el else ""
            content_text = BeautifulSoup(content_html, "html.parser").get_text(" ", strip=True)

            post_id = _extract_post_id(guid_text)
            source_id = f"ftip_{post_id}" if post_id else f"ftip_{idx}"

            # URL
            source_url = item_urls[idx] if idx < len(item_urls) else f"https://www.ftip-japan.org/{post_id or idx}"
            source_url = source_url.strip()

            pub_date = _parse_pub_date(pub_date_str)
            fallback_dt = pub_date or datetime.now()

            # Extract event date from title first, then content
            search_text = title + " " + content_text
            start_date = _extract_date_from_text(search_text, fallback_dt)
            if start_date is None:
                start_date = pub_date

            raw_desc = content_text[:1000] if content_text else title

            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=source_url,
                original_language="ja",
                name_ja=title,
                raw_title=title,
                raw_description=raw_desc,
                description_ja=content_text[:500] if content_text else None,
                category=["art"],
                start_date=start_date,
                location_name=LOCATION_NAME,
                location_address=LOCATION_ADDRESS,
            )
            events.append(event)
            logger.info("FTIP event: %s", title)

        logger.info("Total FTIP events: %d", len(events))
        return events
