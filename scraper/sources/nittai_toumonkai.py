"""Scraper for 日台稲門会（早稲田大学日台同窓会）.

Source: WordPress 6.9.4 RSS feed at /category/event/feed
URL:    https://nittai-toumonkai.com/category/event/feed
Events: ~3–5/year — spring/autumn lectures, AGM, new-year lecture
Venue:  早稲田大学（新宿区早稲田）

All posts are Japan-Taiwan relations content; no keyword filter needed.
Skip only "講演録"（講演記録）posts which are past-event transcripts.

source_id: nittai_toumonkai_{wp_post_id} (from GUID ?p=NNN)
category:  ["lecture", "taiwan_japan"]
is_paid:   True (member/non-member pricing present in all events)

Date extraction priority:
  1. 開催日：（possibly fullwidth）YYYY年M月DD日
  2. Fullwidth-normalised YYYY年M月DD日 anywhere in body
  3. pubDate fallback

Fullwidth number handling: ２０２６年 → 2026年 via unicodedata.normalize or
a simple tr() mapping.
"""

import logging
import re
import unicodedata
import warnings
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

RSS_URL = "https://nittai-toumonkai.com/category/event/feed"
SOURCE_NAME = "nittai_toumonkai"

# Default venue (fallback when not extractable from post body)
DEFAULT_VENUE = "早稲田大学"
DEFAULT_ADDRESS = "東京都新宿区早稲田鶴巻町516-11"

# Skip posts that are transcripts / lecture records (not upcoming events)
_SKIP_RE = re.compile(r"講演録|期間限定|開催報告")

# Regex: post ID from GUID
_POST_ID_RE = re.compile(r"\?p=(\d+)")

# Regex: venue extraction — match 会場：/会場　but NOT 会場受付
# Terminates at newline, （, or end
_VENUE_RE = re.compile(
    r"会[　\s]*場(?!受付)[：:\s　]+([^\n。、:：（\(]{3,40}?)(?:\s*[\n（\(]|$)",
    re.MULTILINE,
)

# Regex: date label pattern (handles both halfwidth and fullwidth colons/spaces)
_DATE_LABEL_RE = re.compile(
    r"開催日[：:\s　]*([^\n]{5,30})",
)

# Regex: time extraction
_TIME_RE = re.compile(
    r"(\d{1,2})[：:](\d{2})"
)


def _fw_to_ascii(text: str) -> str:
    """Normalise fullwidth ASCII digits/punctuation to halfwidth.

    '２０２６年６月１３日' → '2026年6月13日'
    """
    return unicodedata.normalize("NFKC", text)


def _parse_pub_date(pub_date_str: str) -> Optional[datetime]:
    try:
        dt = parsedate_to_datetime(pub_date_str)
        return dt.replace(tzinfo=None)
    except Exception:
        return None


def _extract_post_id(guid: str) -> Optional[str]:
    m = _POST_ID_RE.search(guid)
    return m.group(1) if m else None


def _extract_date(content_text: str, pub_date: datetime) -> Optional[datetime]:
    """Extract event start_date from post body text.

    1. 開催日：YYYY年M月DD日 (may have fullwidth numerals)
    2. YYYY年M月DD日 anywhere, including spaced variant '2026 年 1 月 31 日'
       (produced when BS4 strips bold <strong> tags)
    3. Fallback: pub_date
    """
    normalised = _fw_to_ascii(content_text)

    # Regex tolerating optional spaces between digits and 年/月/日
    _DATE_SPACED = re.compile(
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
    )

    def _try_parse(dm, text_after: str) -> Optional[datetime]:
        try:
            y, mo, d = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
            if abs(y - pub_date.year) > 2:
                return None
            tm = _TIME_RE.search(text_after[:100])
            hour = int(tm.group(1)) if tm else 15
            minute = int(tm.group(2)) if tm else 0
            return datetime(y, mo, d, hour, minute)
        except ValueError:
            return None

    # Priority 1: 開催日 label
    m = _DATE_LABEL_RE.search(normalised)
    if m:
        snippet = m.group(1)
        dm = _DATE_SPACED.search(snippet)
        if dm:
            result = _try_parse(dm, snippet[dm.end():])
            if result:
                return result

    # Priority 2: 日時 label
    m2 = re.search(r"日[　\s]*時[：:\s　]*([^\n]{5,80})", normalised)
    if m2:
        snippet2 = m2.group(1)
        dm2 = _DATE_SPACED.search(snippet2)
        if dm2:
            result = _try_parse(dm2, snippet2[dm2.end():])
            if result:
                return result

    # Priority 3: any YYYY(spaced)年M月DD日 in full text
    dm3 = _DATE_SPACED.search(normalised)
    if dm3:
        result = _try_parse(dm3, normalised[dm3.end():])
        if result:
            return result

    return None


def _extract_venue(content_text: str) -> Optional[str]:
    """Extract venue name from 会場：... pattern."""
    normalised = _fw_to_ascii(content_text)
    m = _VENUE_RE.search(normalised)
    if not m:
        return None
    venue = m.group(1).strip()
    # Clean up trailing punctuation / number hints
    venue = re.sub(r"\s*(地下|〒|[\d\-]+階|から徒歩).*$", "", venue).strip()
    return venue[:60] if venue else None


def _extract_price_info(content_text: str) -> Optional[str]:
    """Extract price summary from 参加費 / 会費 label."""
    normalised = _fw_to_ascii(content_text)
    # Look for the clearest price-bearing line e.g.
    # "参加費：会員・会友・学生は無料、一般は1,000円"
    # "会費：会員・会友6,500円、一般7,500円、学生1,000円"
    for label in ("参加費", "会費"):
        m = re.search(
            rf"{label}[：:\s　]*([^\n]{{5,120}})",
            normalised,
        )
        if m:
            raw = m.group(1).strip()
            # Trim at paragraph break
            raw = re.split(r"[。\n■]", raw)[0].strip()
            if raw and len(raw) >= 5:
                return raw[:120]
    return None


class NittaiToumonkaiScraper(BaseScraper):
    """Scrapes events from 日台稲門会 WordPress RSS feed."""

    SOURCE_NAME = SOURCE_NAME

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
            logger.error("nittai_toumonkai: Failed to fetch RSS: %s", exc)
            return events

        soup = BeautifulSoup(resp.content, "html.parser")
        items = soup.find_all("item")
        logger.info("nittai_toumonkai RSS: %d items", len(items))

        # BS4 in HTML mode drops bare <link> elements — extract from raw text instead
        raw_text = resp.text
        link_urls = re.findall(r"<link>(https?://[^<]+)</link>", raw_text)
        # link_urls[0] = channel self-link; item links start at [1]
        item_urls = link_urls[1:]

        for idx, item in enumerate(items):
            title_el = item.find("title")
            pub_el = item.find("pubdate")
            guid_el = item.find("guid")
            content_el = item.find("content:encoded") or item.find("description")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)

            # Skip transcript/report posts
            if _SKIP_RE.search(title):
                logger.debug("nittai_toumonkai: skip report post: %s", title[:60])
                continue

            pub_date_str = pub_el.get_text(strip=True) if pub_el else ""
            guid_text = guid_el.get_text(strip=True) if guid_el else ""
            content_html = content_el.get_text() if content_el else ""
            content_text = BeautifulSoup(content_html, "html.parser").get_text(
                " ", strip=True
            )

            post_id = _extract_post_id(guid_text)
            source_id = f"{SOURCE_NAME}_{post_id}" if post_id else f"{SOURCE_NAME}_{idx}"

            source_url = (
                item_urls[idx].strip()
                if idx < len(item_urls)
                else f"https://nittai-toumonkai.com/?p={post_id or idx}"
            )

            pub_date = _parse_pub_date(pub_date_str) or datetime.now()

            # Event date from body; fallback to pubDate
            start_date = _extract_date(content_text, pub_date)
            if start_date is None:
                start_date = pub_date
                logger.debug(
                    "nittai_toumonkai: date not found, using pubDate for: %s",
                    title[:60],
                )

            # Venue extraction
            venue_name = _extract_venue(content_text)
            location_name = venue_name or DEFAULT_VENUE
            # Address only set if extractable; avoids hardcoding wrong address
            location_address: Optional[str] = None
            if not venue_name:
                location_address = DEFAULT_ADDRESS

            price_info = _extract_price_info(content_text)

            raw_desc = (content_text[:1000] if content_text else title)

            events.append(
                Event(
                    source_name=SOURCE_NAME,
                    source_id=source_id,
                    source_url=source_url,
                    original_language="ja",
                    name_ja=title,
                    raw_title=title,
                    raw_description=raw_desc,
                    category=["lecture", "taiwan_japan"],
                    start_date=start_date,
                    location_name=location_name,
                    location_address=location_address,
                    is_paid=True,
                    price_info=price_info,
                )
            )
            logger.info(
                "nittai_toumonkai: event [%s] %s (%s)",
                source_id,
                title[:60],
                start_date.date() if start_date else "no-date",
            )

        logger.info("nittai_toumonkai: total %d events", len(events))
        return events
