"""Scraper for K's Cinema（新宿K'sシネマ）

Source URL: https://www.ks-cinema.com/movie/
Platform  : WordPress static HTML — no JS rendering required
Source name: ks_cinema
Source ID : ks_cinema_{url_slug}  (parent/single film)
           ks_cinema_{url_slug}_{film_index}  (sub-film within a series)

Strategy:
  1. Fetch nowshowing + comingsoon listing pages
  2. Collect all /movie/{slug}/ links
  3. For each page, check Taiwan keyword filter in title/content
  4. On Taiwan pages:
     a. Series (multiple <h3> sub-films) → parent event + one sub-event per film
     b. Single film (no <h3> sub-sections) → one event
  5. Parse start_date / end_date from 上映期間 table row

Date format: M/DD(曜) or M/DD(曜)・DD(曜) or M/DD(曜)～M/DD(曜)
  Year is inferred from today's date (no year in the strings).

Taiwan keyword filter:
  Applied to h1 title + full page text.
  ["台湾", "Taiwan", "臺灣"]

Venue (fixed):
  〒160-0022 東京都新宿区新宿3丁目35-13 3F
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "ks_cinema"

_BASE_URL = "https://www.ks-cinema.com"
_LISTING_URLS = [
    "https://www.ks-cinema.com/movie/list/nowshowing/",
    "https://www.ks-cinema.com/movie/list/comingsoon/",
]

_JST = timezone(timedelta(hours=9))

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

_VENUE_NAME = "K's cinema"
_VENUE_ADDRESS = "東京都新宿区新宿3丁目35-13 3F"

# Taiwan relevance filter — applied to title + full page text
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_taiwan_relevant(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _url_to_slug(url: str) -> str:
    """Extract the last path segment from a URL as the slug.
    https://www.ks-cinema.com/movie/taiwan-filmake/ → 'taiwan-filmake'
    """
    return url.rstrip("/").rsplit("/", 1)[-1]


def _infer_year(month: int, today: datetime) -> int:
    """Infer the year for a date given only month and day.

    If the month is more than 3 months in the past, assume next year.
    (Handles comingsoon spanning year boundary.)
    """
    if month < today.month - 3:
        return today.year + 1
    return today.year


def _parse_period(period_str: str, today: datetime) -> tuple[datetime | None, datetime | None]:
    """Parse '4/25(土)～5/8(金)' or '4/25(土)' into (start, end) datetimes.

    Returns (None, None) on parse failure.
    """
    # Clean parenthetical day-of-week markers
    clean = re.sub(r"[（(][月火水木金土日祝・休]+[）)]", "", period_str)
    clean = clean.strip()

    # Pattern: M/D or M/D～M/D
    m = re.search(r"(\d{1,2})/(\d{1,2})\s*(?:[～~]\s*(\d{1,2})/(\d{1,2}))?", clean)
    if not m:
        return None, None

    start_month, start_day = int(m.group(1)), int(m.group(2))
    start_year = _infer_year(start_month, today)
    try:
        start = datetime(start_year, start_month, start_day, tzinfo=_JST)
    except ValueError:
        return None, None

    if m.group(3) and m.group(4):
        end_month, end_day = int(m.group(3)), int(m.group(4))
        end_year = start_year if end_month >= start_month else start_year + 1
        try:
            end = datetime(end_year, end_month, end_day, tzinfo=_JST)
        except ValueError:
            end = start
    else:
        end = start

    return start, end


def _parse_schedule_first_last(schedule_str: str, today: datetime) -> tuple[datetime | None, datetime | None]:
    """Parse a film schedule line and return (first_date, last_date).

    Examples:
      '4/25(土)・26(日)12:30、4/27(月)～5/1(金)12:40、5/2(土)～8(金)10:00'
      '4/25(土)～5/1(金)15:15、5/2(土)～8(金)12:30'

    Strategy: single left-to-right pass, tracking the most recently seen month.
    This avoids the bug where bare day numbers (e.g. '26' in '4/25・26') would
    be attached to the *last* month found instead of the current context month.
    """
    # Clean day-of-week and time markers
    clean = re.sub(r"[（(][月火水木金土日祝・休]+[）)]", "", schedule_str)
    clean = re.sub(r"\d{1,2}:\d{2}", "", clean)  # strip HH:MM times

    dates: list[datetime] = []
    current_month: int | None = None

    # Single pass: alternate between M/D patterns and bare-day patterns
    # Token: either  M/D  (with optional separator before)  or  SEP + D
    token_re = re.compile(
        r"(\d{1,2})/(\d{1,2})"          # group 1+2: explicit M/D
        r"|[～~・、]\s*(\d{1,2})\b(?!/)" # group 3: bare day after separator
    )
    for m in token_re.finditer(clean):
        if m.group(1) and m.group(2):
            # Explicit M/D
            current_month = int(m.group(1))
            day = int(m.group(2))
        elif m.group(3) and current_month is not None:
            # Bare day — attach to most recently seen month
            day = int(m.group(3))
        else:
            continue

        if current_month is None:
            continue
        year = _infer_year(current_month, today)
        try:
            dates.append(datetime(year, current_month, day, tzinfo=_JST))
        except ValueError:
            pass

    if not dates:
        return None, None
    return min(dates), max(dates)


def _table_to_dict(table_el: BeautifulSoup) -> dict[str, str]:
    """Convert a <table> of <tr><td>key</td><td>value</td></tr> to a dict."""
    result: dict[str, str] = {}
    for row in table_el.select("tr"):
        cells = row.select("td, th")
        if len(cells) >= 2:
            k = cells[0].get_text(strip=True)
            v = cells[1].get_text(strip=True)
            if k:
                result[k] = v
    return result


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _fetch(url: str, session: requests.Session) -> BeautifulSoup | None:
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            return BeautifulSoup(resp.text, "html.parser")
        logger.warning("HTTP %s for %s", resp.status_code, url)
    except requests.RequestException as e:
        logger.warning("Request error for %s: %s", url, e)
    return None


# ---------------------------------------------------------------------------
# Listing page scraping
# ---------------------------------------------------------------------------

def _get_movie_links(listing_url: str, session: requests.Session) -> list[str]:
    """Return all /movie/{slug}/ URLs from a listing page."""
    soup = _fetch(listing_url, session)
    if not soup:
        return []
    links: list[str] = []
    seen: set[str] = set()
    for a in soup.select("a[href*='/movie/']"):
        href = a.get("href", "")
        if not href or "/movie/list/" in href:
            continue
        if href in ("https://www.ks-cinema.com/movie/", "https://www.ks-cinema.com/movie"):
            continue
        # Must match /movie/{slug}/ pattern (not /movie/list/)
        if re.match(r"https://www\.ks-cinema\.com/movie/[a-z0-9\-]+/?$", href):
            if href not in seen:
                seen.add(href)
                links.append(href)
    return links


# ---------------------------------------------------------------------------
# Detail page scraping
# ---------------------------------------------------------------------------

def _scrape_detail(url: str, session: requests.Session, today: datetime) -> list[Event]:
    """Scrape a movie detail page and return events.

    Returns [] if the page is not Taiwan-relevant.
    Returns 1 event for a single film page.
    Returns parent + N sub-events for a series page.
    """
    soup = _fetch(url, session)
    if not soup:
        return []

    # --- Title ---
    h1 = soup.find("h1")
    if not h1:
        return []
    title = h1.get_text(strip=True)

    # --- Content div ---
    box_base = h1.find_parent("div", class_="box-base")
    if not box_base:
        # Fallback: find content from body
        content_div = soup.find("body")
    else:
        # The content div is the unnamed div sibling of div.head
        head_div = box_base.find("div", class_="head")
        content_div = None
        if head_div:
            for sib in head_div.find_next_siblings("div"):
                if not sib.get("class"):
                    content_div = sib
                    break
        if not content_div:
            content_div = box_base

    full_text = (content_div or soup).get_text(separator="\n", strip=True)

    # --- Taiwan relevance check ---
    if not _is_taiwan_relevant(title + "\n" + full_text):
        return []

    # --- Period table (last table with 上映期間 key) ---
    period_table = None
    for t in reversed(soup.select("table")):
        d = _table_to_dict(t)
        if "上映期間" in d:
            period_table = d
            break

    overall_start: datetime | None = None
    overall_end: datetime | None = None
    price_info: str | None = None
    biko: str | None = None

    if period_table:
        overall_start, overall_end = _parse_period(period_table.get("上映期間", ""), today)
        price_info = period_table.get("当日料金")
        biko = period_table.get("備考")

    url_slug = _url_to_slug(url)

    # --- Check for sub-films (h3 elements in content) ---
    h3_elements = content_div.select("h3") if content_div else []
    # Filter out h3 elements from the sidebar (メニュー, お問い合わせ)
    film_h3s = [
        h for h in h3_elements
        if h.get_text(strip=True) not in ("メニュー", "お問い合わせ", "上映MOVIES", "Contact")
           and "menu" not in " ".join(h.get("class", [])).lower()
    ]

    events: list[Event] = []

    if len(film_h3s) >= 2:
        # === Series page: parent + sub-events ===

        # Collect intro text (before first h3)
        intro_parts: list[str] = []
        for el in content_div.children:
            if not hasattr(el, "name") or not el.name:
                continue
            if el.name == "h3":
                break
            if el.name == "p":
                t = el.get_text(strip=True)
                if t:
                    intro_parts.append(t)
        intro_text = "\n".join(intro_parts)

        # Build raw_description for parent
        parent_raw_desc = intro_text
        if overall_start:
            date_str = overall_start.strftime("%Y年%m月%d日")
            parent_raw_desc = f"開催日時: {date_str}\n\n" + parent_raw_desc

        parent_event = Event(
            source_name=SOURCE_NAME,
            source_id=f"ks_cinema_{url_slug}",
            source_url=url,
            original_language="ja",
            raw_title=title,
            raw_description=parent_raw_desc or title,
            start_date=overall_start,
            end_date=overall_end,
            category=["movie"],
            location_name=_VENUE_NAME,
            location_address=_VENUE_ADDRESS,
            is_paid=True,
            price_info=price_info,
        )
        events.append(parent_event)

        # --- Sub-events: parse each h3 section ---
        for idx, h3 in enumerate(film_h3s):
            film_title = h3.get_text(strip=True)

            # Gather siblings until next h3 or the period div
            schedule_text: str = ""
            desc_parts: list[str] = []
            film_table: dict[str, str] = {}

            node = h3.find_next_sibling()
            while node:
                if not hasattr(node, "name") or not node.name:
                    node = node.find_next_sibling()
                    continue
                if node.name == "h3":
                    break
                if node.name == "p":
                    text = node.get_text(strip=True)
                    if not schedule_text and re.search(r"\d+/\d+", text):
                        schedule_text = text
                    elif text:
                        desc_parts.append(text)
                elif node.name == "table":
                    film_table = _table_to_dict(node)
                elif node.name == "div":
                    # Period div or link div — stop
                    break
                node = node.find_next_sibling()

            # Parse dates from schedule line
            film_start, film_end = None, None
            if schedule_text:
                film_start, film_end = _parse_schedule_first_last(schedule_text, today)
            if film_start is None:
                film_start = overall_start
                film_end = overall_end

            # Build raw_description
            meta_parts: list[str] = []
            for k in ("監督", "出演", "プロデューサー", "作品情報"):
                if k in film_table:
                    meta_parts.append(f"{k}：{film_table[k]}")
            if schedule_text:
                meta_parts.insert(0, f"上映時間：{schedule_text}")

            raw_desc = "\n".join(desc_parts)
            if meta_parts:
                raw_desc = raw_desc + "\n\n" + "\n".join(meta_parts) if raw_desc else "\n".join(meta_parts)
            if film_start:
                date_str = film_start.strftime("%Y年%m月%d日")
                raw_desc = f"開催日時: {date_str}\n\n" + raw_desc

            sub_event = Event(
                source_name=SOURCE_NAME,
                source_id=f"ks_cinema_{url_slug}_{idx}",
                source_url=url,
                original_language="ja",
                raw_title=film_title,
                raw_description=raw_desc or film_title,
                start_date=film_start,
                end_date=film_end,
                category=["movie"],
                location_name=_VENUE_NAME,
                location_address=_VENUE_ADDRESS,
                is_paid=True,
                price_info=price_info,
                parent_event_id=f"ks_cinema_{url_slug}",
            )
            events.append(sub_event)

    else:
        # === Single film page ===

        # Collect all description text
        desc_parts: list[str] = []
        if content_div:
            for el in content_div.find_all(["p"]):
                text = el.get_text(strip=True)
                if text and not re.match(r"^\d{1,2}/\d{1,2}", text):  # skip pure schedule lines
                    desc_parts.append(text)

        raw_desc = "\n".join(desc_parts)
        if biko:
            raw_desc = raw_desc + "\n\n備考：" + biko if raw_desc else "備考：" + biko
        if overall_start:
            date_str = overall_start.strftime("%Y年%m月%d日")
            raw_desc = f"開催日時: {date_str}\n\n" + raw_desc

        event = Event(
            source_name=SOURCE_NAME,
            source_id=f"ks_cinema_{url_slug}",
            source_url=url,
            original_language="ja",
            raw_title=title,
            raw_description=raw_desc or title,
            start_date=overall_start,
            end_date=overall_end,
            category=["movie"],
            location_name=_VENUE_NAME,
            location_address=_VENUE_ADDRESS,
            is_paid=True,
            price_info=price_info,
        )
        events.append(event)

    return events


# ---------------------------------------------------------------------------
# Scraper class
# ---------------------------------------------------------------------------

class KsCinemaScraper(BaseScraper):
    """Scraper for K's Cinema（新宿K'sシネマ） Taiwan film screenings."""

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        today = datetime.now(_JST)
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        # Collect unique movie URLs from all listing pages
        all_urls: list[str] = []
        seen: set[str] = set()
        for listing_url in _LISTING_URLS:
            for url in _get_movie_links(listing_url, session):
                if url not in seen:
                    seen.add(url)
                    all_urls.append(url)
            time.sleep(0.5)

        logger.info("K's Cinema: found %d movie pages to check", len(all_urls))

        events: list[Event] = []
        for url in all_urls:
            time.sleep(0.5)
            page_events = _scrape_detail(url, session, today)
            if page_events:
                logger.info(
                    "  %s → %d event(s)", _url_to_slug(url), len(page_events)
                )
                events.extend(page_events)

        logger.info("K's Cinema: total events=%d", len(events))
        return events
