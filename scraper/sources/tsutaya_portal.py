"""
Scraper for 蔦屋書店ポータル — 全国蔦屋書店イベント横断検索.

Strategy:
  1. POST https://store.tsite.jp/portal/event/ with input_search_word=台湾,
     paging via input_page=N (12 items/page).
  2. Parse ul.eventlist li cards: title (span.title), date (span.date),
     store/genre (span.genre), detail href.
  3. Visit each detail page: extract precise date (div.date), full
     description (section div.article), and venue (span.place).
  4. Taiwan relevance check — keyword must appear in the title or within the
     first 500 chars of description to avoid artist-bio false positives.
  5. source_id = numeric ID extracted from the detail URL path,
     e.g. /umeda/event/shop/51599-1523431205.html → "51599-1523431205"
     This ID is stable across runs regardless of store slug.
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://store.tsite.jp"
PORTAL_URL = f"{BASE_URL}/portal/event/"
SOURCE_NAME = "tsutaya_portal"
MAX_PAGES = 10
REQUEST_DELAY = 0.5  # seconds between requests (polite crawl)

TAIWAN_KEYWORDS = ["台湾", "Taiwan", "台灣", "タイワン"]

# Extract the numeric event ID from URLs like /umeda/event/shop/51599-1523431205.html
_EVENT_ID_RE = re.compile(r"/event/[^/]+/(\d+-\d+)\.html$")

# Date patterns in detail page div.date: "梅田 蔦屋書店 ショールーム   2026年 06月06日(土)"
_DETAIL_DATE_RE = re.compile(r"(\d{4})年\s*(\d{1,2})月(\d{1,2})日")

# Date range in listing span.date: "2026.05.03(日) - 05.05(火)" or "2026. 05.05(火)"
_LIST_DATE_RE = re.compile(r"(\d{4})[.\s]+(\d{1,2})[./](\d{1,2})")
_LIST_END_DATE_RE = re.compile(r"-\s*(\d{1,2})[./](\d{1,2})")

_POST_FIELDS = {
    "input_search_date": "",
    "input_search_word": "台湾",
    "input_online_format": "",
    "input_ts_common_category_path": "",
    "input_ts_area": "",
    "input_order": "event",
}

_HEADERS = {
    "User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)",
    "Accept-Language": "ja,en;q=0.9",
    "Referer": PORTAL_URL,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_detail_date(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse date(s) from the detail page div.date text.

    The text may be a single date or a range:
      - "梅田 蔦屋書店 ショールーム   2026年 06月06日(土)"
      - "代官山T-SITE｜アート  2026年 04月25日(土) - 2026年 05月10日(日)"
    Returns (start_date, end_date); end_date == start_date when no range.
    """
    dates = _DETAIL_DATE_RE.findall(text)
    if not dates:
        return None, None
    try:
        start = datetime(int(dates[0][0]), int(dates[0][1]), int(dates[0][2]))
    except (ValueError, IndexError):
        return None, None
    if len(dates) >= 2:
        try:
            end = datetime(int(dates[1][0]), int(dates[1][1]), int(dates[1][2]))
        except (ValueError, IndexError):
            end = start
    else:
        end = start
    return start, end


def _parse_list_date(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse date from listing card span.date as fallback.

    Formats seen:
      " 2026.05.03(日) - 05.05(火)"   → start=2026-05-03, end=2026-05-05
      " 2026. 05.05(火)"              → start=2026-05-05, end=2026-05-05
    """
    m = _LIST_DATE_RE.search(text)
    if not m:
        return None, None
    try:
        year = int(m.group(1))
        start = datetime(year, int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None, None

    end_m = _LIST_END_DATE_RE.search(text, m.end())
    if end_m:
        try:
            end = datetime(year, int(end_m.group(1)), int(end_m.group(2)))
        except ValueError:
            end = start
    else:
        end = start
    return start, end


def _extract_source_id(href: str) -> Optional[str]:
    m = _EVENT_ID_RE.search(href)
    return m.group(1) if m else None


def _extract_store_name(genre_text: str) -> str:
    """Extract the store name from genre text like '高知 蔦屋書店｜テラス'.

    Returns everything before the first '｜' separator, trimmed.
    """
    return genre_text.split("｜")[0].strip()


def _is_taiwan_relevant(title: str, description: str) -> bool:
    """Return True only when a Taiwan keyword appears in the event title or
    within the first 500 characters of the description.

    Limiting the description window prevents false positives caused by artist
    biographies that mention past Taiwan exhibitions deep in the text (e.g.
    "ART TAIPEI出展" or "台湾などで活動" appearing at position 600+).
    The title is always checked in full.
    """
    if any(kw in (title or "") for kw in TAIWAN_KEYWORDS):
        return True
    desc_head = (description or "")[:500]
    return any(kw in desc_head for kw in TAIWAN_KEYWORDS)


def _fetch_detail(
    session: requests.Session, url: str
) -> tuple[Optional[datetime], Optional[datetime], Optional[str], Optional[str], Optional[str]]:
    """Fetch detail page and extract (start, end, venue, title, description).

    Returns (start_date, end_date, location_name, title, description).
    On error returns (None, None, None, None, None).
    """
    try:
        resp = session.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Detail fetch failed %s: %s", url, exc)
        return None, None, None, None, None

    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    # Title
    title_el = soup.select_one("article > header > h2.article_h")
    title = title_el.get_text(strip=True) if title_el else None

    # Date + venue (both inside div.date)
    date_el = soup.select_one("article > header > div.date")
    start_date, end_date, location_name = None, None, None
    if date_el:
        date_text = date_el.get_text(" ", strip=True)
        start_date, end_date = _parse_detail_date(date_text)
        # Venue is in span.place
        place_el = date_el.select_one("span.place")
        if place_el:
            location_name = place_el.get_text(strip=True)

    # Description
    desc_el = soup.select_one("section div.article")
    description = desc_el.get_text(" ", strip=True)[:2000] if desc_el else None

    return start_date, end_date, location_name, title, description


# ---------------------------------------------------------------------------
# Scraper class
# ---------------------------------------------------------------------------


class TsutayaPortalScraper(BaseScraper):
    source_name = SOURCE_NAME

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        seen_ids: set[str] = set()
        session = requests.Session()

        for page_num in range(1, MAX_PAGES + 1):
            logger.info("%s: fetching listing page %d", SOURCE_NAME, page_num)
            post_data = {**_POST_FIELDS, "input_page": str(page_num)}
            try:
                resp = session.post(PORTAL_URL, data=post_data, headers=_HEADERS, timeout=15)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("Listing page %d failed: %s", page_num, exc)
                break

            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            event_list = soup.select("ul.eventlist li")
            if not event_list:
                logger.info("No events on page %d; end of results", page_num)
                break

            page_events: list[Event] = []
            for li in event_list:
                a = li.find("a", href=True)
                if not a:
                    continue

                href = a["href"]
                if not href.startswith("/"):
                    continue

                detail_url = BASE_URL + href
                source_id = _extract_source_id(href)
                if not source_id or source_id in seen_ids:
                    continue
                seen_ids.add(source_id)

                # Card-level fields (used as fallback if detail fetch fails)
                genre_el = li.select_one("span.genre")
                title_el = li.select_one("span.title")
                date_el = li.select_one("span.date")

                card_title = title_el.get_text(strip=True) if title_el else None
                card_date_text = date_el.get_text(strip=True) if date_el else ""
                card_start, card_end = _parse_list_date(card_date_text)
                card_store = _extract_store_name(
                    genre_el.get_text(strip=True) if genre_el else ""
                )

                time.sleep(REQUEST_DELAY)
                det_start, det_end, location_name, det_title, description = _fetch_detail(
                    session, detail_url
                )

                title = det_title or card_title
                start_date = det_start or card_start
                end_date = det_end or card_end
                if not location_name:
                    location_name = card_store or None

                if not _is_taiwan_relevant(title or "", description or ""):
                    logger.debug("Skipping non-Taiwan event: %s", title)
                    continue

                event = Event(
                    source_name=SOURCE_NAME,
                    source_id=f"tsutaya_{source_id}",
                    source_url=detail_url,
                    original_language="ja",
                    name_ja=title,
                    raw_title=title,
                    raw_description=description,
                    description_ja=description,
                    start_date=start_date,
                    end_date=end_date,
                    location_name=location_name,
                )
                page_events.append(event)
                logger.info("  + %s (%s)", title, start_date)

            events.extend(page_events)
            if len(event_list) < 12:
                # Last page was partial — no more pages
                break

            time.sleep(REQUEST_DELAY)

        logger.info("%s: collected %d Taiwan events", SOURCE_NAME, len(events))
        return events
