"""Scraper for LivePocket（ライブポケット）— Japanese e-ticket sales platform.

Source URL : https://livepocket.jp/event/search?word=台湾
Platform   : Static HTML (Hotwire/Turbo, but search results are server-rendered)
Auth       : None
robots.txt : No Disallow rules — open crawling
Source name: livepocket
Source ID  : livepocket_{slug}  (e.g. livepocket_8_kzj)

Strategy:
  1. Fetch paginated search results for keywords: 台湾, Taiwan, 臺灣
  2. For each event card (a.event-card[href^='/e/']):
       - Skip if status badge is '終了' (ended)
       - Skip if source_id already seen (dedup across keyword passes)
  3. Fetch detail page /e/{slug}:
       - Extract date, venue, performers, description via dl.event-detail-info
       - Apply Taiwan keyword filter on full page text
       - Skip /t/ tour pages (not individual events)
  4. Build Event from extracted fields

Taiwan keyword filter:
  ["台湾", "Taiwan", "臺灣"]
  Applied on full detail-page text after fetch.

Date formats:
  - Single day : "2026年6月9日(火)"
  - Date range : "2026年6月6日(土)〜2026年6月7日(日)"

Venue field format:
  "下北沢SHELTER (東京都)東京都世田谷区北沢２丁目６−１０  仙田商会仙田ビル B1..."
  Venue name = everything up to and including (都道府県)
  Address    = remainder after (都道府県)
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

SOURCE_NAME = "livepocket"
_BASE_URL = "https://livepocket.jp"
_SEARCH_KEYWORDS = ["台湾", "Taiwan", "臺灣"]
_MAX_PAGES = 10         # safety ceiling per keyword
_REQUEST_DELAY = 0.5    # seconds between requests

_JST = timezone(timedelta(hours=9))
_TODAY = None           # set per-run in scrape()

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

# Match "（東京都）", "（大阪府）", "（神奈川県）" etc.
_PREF_RE = re.compile(r"[（(][^）)]+[都道府県][）)]")

# Match date: "2026年6月9日(火)" or "2026年6月6日(土)"
_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_taiwan_relevant(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _parse_date(text: str) -> datetime | None:
    """Parse 'YYYY年M月D日(曜)' → datetime (JST). Returns None on failure."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=_JST)
    except ValueError:
        return None


def _parse_venue(raw: str) -> tuple[str | None, str | None]:
    """Split venue field into (location_name, location_address).

    Example:
      "下北沢SHELTER (東京都)東京都世田谷区北沢２丁目..."
      → ("下北沢SHELTER (東京都)", "東京都世田谷区北沢２丁目...")
    """
    m = _PREF_RE.search(raw)
    if not m:
        # No prefecture found — use full string as name only
        return raw.strip() or None, None
    split_pos = m.end()
    name = raw[:split_pos].strip()
    addr = raw[split_pos:].strip()
    # Remove trailing navigation boilerplate from address
    addr = re.sub(r"会場マップ・アクセス方法はこちら.*", "", addr).strip()
    return name or None, addr or None


def _get_dd_text(dl: BeautifulSoup, label: str) -> str | None:
    """Find <dt> matching label and return corresponding <dd> text.

    The dl.event-detail-info__list has the structure:
      <div class='event-detail-info__block'>
        <dt>...</dt>
        <dd>...</dd>
      </div>
    So we find the block div containing the matching dt and then get the dd.
    """
    for block in dl.select("div.event-detail-info__block"):
        dt = block.select_one("dt")
        if dt and label in dt.get_text():
            dd = block.select_one("dd")
            if dd:
                return dd.get_text(separator="\n", strip=True)
    return None


def _fetch(url: str, session: requests.Session) -> BeautifulSoup | None:
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        logger.warning("Fetch failed %s: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class LivepocketScraper(BaseScraper):
    """Scraper for LivePocket（ライブポケット）e-ticket platform."""

    @property
    def source_name(self) -> str:
        return SOURCE_NAME

    def scrape(self) -> list[Event]:
        global _TODAY
        _TODAY = datetime.now(_JST)

        session = requests.Session()
        session.headers.update({"User-Agent": _UA})

        events: list[Event] = []
        seen_slugs: set[str] = set()

        for keyword in _SEARCH_KEYWORDS:
            page = 1
            while page <= _MAX_PAGES:
                search_url = (
                    f"{_BASE_URL}/event/search"
                    f"?word={requests.utils.quote(keyword)}&page={page}"
                )
                logger.info("Fetching search page: %s", search_url)
                soup = _fetch(search_url, session)
                if soup is None:
                    break

                cards = soup.select("a.event-card[href]")
                if not cards:
                    logger.info("No cards on page %d for keyword '%s', stopping.", page, keyword)
                    break

                for card in cards:
                    href = card.get("href", "")
                    # Skip /t/ tour pages and non-event links
                    if not href.startswith("/e/"):
                        continue

                    slug = href[3:]  # strip leading "/e/"
                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)

                    # Skip ended events (status badge)
                    badge = card.select_one("span.event-card__tag")
                    if badge and badge.get_text(strip=True) == "終了":
                        continue

                    time.sleep(_REQUEST_DELAY)
                    detail_url = urljoin(_BASE_URL, href)
                    event = self._scrape_detail(slug, detail_url, session)
                    if event:
                        events.append(event)

                page += 1
                time.sleep(_REQUEST_DELAY)

        logger.info("livepocket: %d Taiwan events found.", len(events))
        return events

    # -----------------------------------------------------------------------

    def _scrape_detail(
        self, slug: str, url: str, session: requests.Session
    ) -> Event | None:
        soup = _fetch(url, session)
        if soup is None:
            return None

        page_text = soup.get_text()

        # Taiwan relevance check
        if not _is_taiwan_relevant(page_text):
            return None

        # ----- Title -----
        h1 = soup.select_one("h1.heading01")
        raw_title = h1.get_text(strip=True) if h1 else None
        if not raw_title:
            logger.warning("No title found at %s, skipping.", url)
            return None

        # ----- Detail info dl -----
        # There are two identical dl.event-detail-info__list blocks (desktop + mobile)
        # Use the first one
        dl = soup.select_one("dl.event-detail-info__list")

        # ----- Dates -----
        start_date: datetime | None = None
        end_date: datetime | None = None
        date_raw = _get_dd_text(dl, "開催日") if dl else None
        if date_raw:
            # Date range: "2026年6月6日(土)\n〜2026年6月7日(日)"
            dates = _DATE_RE.findall(date_raw)
            if dates:
                y, m, d = dates[0]
                try:
                    start_date = datetime(int(y), int(m), int(d), tzinfo=_JST)
                except ValueError:
                    pass
            if len(dates) >= 2:
                y2, m2, d2 = dates[1]
                try:
                    end_date = datetime(int(y2), int(m2), int(d2), tzinfo=_JST)
                except ValueError:
                    pass
            if start_date and not end_date:
                end_date = start_date  # single-day event

        if not start_date:
            logger.warning("No start_date at %s, skipping.", url)
            return None

        # ----- Venue -----
        venue_raw = _get_dd_text(dl, "会場") if dl else None
        location_name, location_address = _parse_venue(venue_raw) if venue_raw else (None, None)

        # ----- Performers -----
        performers_raw = _get_dd_text(dl, "出演者") if dl else None

        # ----- Price info -----
        ticket_body = soup.select_one("div.event-detail-ticket-body")
        price_info: str | None = None
        if ticket_body:
            raw_ticket_text = ticket_body.get_text(separator=" ", strip=True)
            # Extract price lines like "¥3,000（税込）" or "一般販売中¥3,000（税込）"
            price_matches = re.findall(r"[¥￥][\d,，]+[^\s　]{0,20}", raw_ticket_text)
            if price_matches:
                price_info = " / ".join(dict.fromkeys(price_matches))  # deduplicate
            is_paid = True
            if re.search(r"[¥￥]0\b|無料", raw_ticket_text):
                is_paid = False
        else:
            is_paid = None

        # ----- raw_description -----
        # Build from: title + date header + performers (if any) + detail content text
        desc_parts: list[str] = []
        if date_raw:
            # Prepend event date as required by BaseScraper contract
            date_line = date_raw.replace("\n", " ").strip()
            desc_parts.append(f"開催日時: {date_line}")
        if venue_raw:
            desc_parts.append(f"会場: {venue_raw.replace(chr(10), ' ').strip()}")
        if performers_raw:
            desc_parts.append(f"出演者: {performers_raw.replace(chr(10), '、').strip()}")

        # Main detail content
        content_div = soup.select_one("div.event-detail__content")
        if content_div:
            content_text = content_div.get_text(separator="\n", strip=True)
            # Remove navigation boilerplate at the start
            content_text = re.sub(
                r"^(?:概要|受付・チケット情報|お問い合わせ)\n?", "", content_text
            ).strip()
            if content_text:
                desc_parts.append(content_text)

        raw_description = "\n\n".join(desc_parts) if desc_parts else None

        source_id = f"{SOURCE_NAME}_{slug}"

        return Event(
            source_name=SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            original_language="ja",
            raw_title=raw_title,
            raw_description=raw_description,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=location_address,
            is_paid=is_paid if ticket_body else None,
            price_info=price_info,
            is_active=True,
            category=[],  # annotator will assign
        )
