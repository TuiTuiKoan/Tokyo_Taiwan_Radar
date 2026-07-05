"""
Scraper for 阪急阪神百貨店 (Hankyu department stores) — weekly event schedules.

Multi-store generalisation of the former single-store ``hankyu_umeda`` scraper.
Covers the group's main催事 stores in one module; adding another verified store
is a one-line entry in ``_STORES``.

Enabled stores (2026-07):
  - hankyu_umeda  阪急うめだ本店  /honten/event/   (Osaka)
  - hankyu_hakata 博多阪急        /hakata/event/   (Fukuoka)
  - hankyu_kobe   神戸阪急        /kobe/event/     (Hyogo)

Rendering: static-html (requests + BeautifulSoup); no Playwright required.

HTML structure (identical across stores, confirmed 2026-07-04):
  article > div.o-event
    - Title:  p.o-event__title
    - Desc:   p.o-event__desc
    - URL:    a[href]  (often the website.hankyu-dept.co.jp subdomain)
    - Date+Venue: div.o-event__detail  e.g. "●7月8日（水）～13日（月）\n●8階 催場"
  Date marker differs per store: 梅田 uses "◎", 博多/神戸 use "●" → generalised to [◎●].

Two-layer Taiwan relevance filter:
  L1  title/desc contains 台湾 → collect (handles e.g. autumn 台湾ライフ fairs).
  L2  title/desc contains アジア/Asia but NOT 台湾, and a detail URL exists →
      fetch the detail page and look for Taiwan evidence in
      <meta name="description"> + Taiwan-bearing <img alt>.  Collected only if
      that evidence mentions Taiwan.  The evidence text is appended to
      raw_description so the annotator has context (the listing row itself only
      carries a date + venue).  This is why 博多 アジアンフェスティバル (title
      "Asian Festival", Taiwan content only inside images) is now captured.

source_id = {source_name}_{slug}  where slug = last path segment of detail URL;
            falls back to {source_name}_{sha1(title+date_str)[:10]} when absent.
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Store registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Store:
    source_name: str
    display_name: str
    event_url: str
    base_url: str
    location_address: str
    location_prefectures: tuple[str, ...]


_BASE_URL = "https://www.hankyu-dept.co.jp"

_STORES: dict[str, _Store] = {
    "hankyu_umeda": _Store(
        source_name="hankyu_umeda",
        display_name="阪急うめだ本店",
        event_url=f"{_BASE_URL}/honten/event/",
        base_url=_BASE_URL,
        location_address="大阪府大阪市北区角田町8-7 阪急うめだ本店",
        location_prefectures=("大阪府",),
    ),
    "hankyu_hakata": _Store(
        source_name="hankyu_hakata",
        display_name="博多阪急",
        event_url=f"{_BASE_URL}/hakata/event/",
        base_url=_BASE_URL,
        location_address="福岡県福岡市博多区博多駅中央街1-1 博多阪急",
        location_prefectures=("福岡県",),
    ),
    "hankyu_kobe": _Store(
        source_name="hankyu_kobe",
        display_name="神戸阪急",
        event_url=f"{_BASE_URL}/kobe/event/",
        base_url=_BASE_URL,
        location_address="兵庫県神戸市中央区小野柄通8-1-8 神戸阪急",
        location_prefectures=("兵庫県",),
    ),
}

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.9",
}
_DELAY = 0.5  # seconds between requests

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

# L1 — direct Taiwan relevance: title OR description must match.
_TAIWAN_RE = re.compile(r"台湾|台灣|Taiwan|taiwan|🇹🇼", re.IGNORECASE)
# L2 — pan-Asian candidates worth a detail-page evidence check.
_ASIA_RE = re.compile(r"アジア|Asian|Asia", re.IGNORECASE)

_EVIDENCE_MAX_CHARS = 2500

# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------

# Marker differs per store (◎ vs ●). Optional 前半/後半 prefix seen on 梅田 pages,
# e.g. "◎前半：7月1日（水）～6日（月）".
_MARK = r"[◎●]"
_PREFIX = r"(?:前半|後半)?[：:]?\s*"

# "●7月8日（水）～13日（月）" (same month) → (start_month, start_day, end_day)
_DATE_SAME_MONTH = re.compile(
    rf"{_MARK}\s*{_PREFIX}(\d{{1,2}})月(\d{{1,2}})日[^～〜]*[～〜]\s*(\d{{1,2}})日"
)
# "◎4月29日（水）～5月11日（月）" (cross month) → (sm, sd, em, ed)
_DATE_DIFF_MONTH = re.compile(
    rf"{_MARK}\s*{_PREFIX}(\d{{1,2}})月(\d{{1,2}})日[^～〜]*[～〜]\s*(\d{{1,2}})月(\d{{1,2}})日"
)
# "◎7月4日（土）" (single day)
_DATE_SINGLE = re.compile(rf"{_MARK}\s*{_PREFIX}(\d{{1,2}})月(\d{{1,2}})日")

_SLUG_STOPWORDS: frozenset[str] = frozenset(
    {"", "honten", "hakata", "kobe", "h", "event", "index.html"}
)


def _infer_year(month: int, today: date) -> int:
    """Pick current year, rolling forward if the month is already past."""
    if month >= today.month:
        return today.year
    if today.month == 12 and month <= 3:
        return today.year + 1
    return today.year


def _parse_date_range(
    detail_text: str, today: date
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Extract (start_date, end_date) from the event detail block text.

    Handles same-month / cross-month ranges and single days, with either
    ``◎`` or ``●`` markers and an optional 前半/後半 prefix. Dates are naive
    ``datetime(y, m, d)`` (== Supabase UTC midnight), matching prior behaviour.
    """
    # Cross-month range first: ◎4月29日（水）～5月11日（月）
    m = _DATE_DIFF_MONTH.search(detail_text)
    if m:
        sm, sd, em, ed = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        year = _infer_year(sm, today)
        end_year = year if em >= sm else year + 1
        try:
            return datetime(year, sm, sd), datetime(end_year, em, ed)
        except ValueError:
            pass

    # Same-month range: ●7月8日（水）～13日（月）
    m = _DATE_SAME_MONTH.search(detail_text)
    if m:
        sm, sd, ed = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year = _infer_year(sm, today)
        try:
            return datetime(year, sm, sd), datetime(year, sm, ed)
        except ValueError:
            pass

    # Single day: ◎7月4日
    m = _DATE_SINGLE.search(detail_text)
    if m:
        sm, sd = int(m.group(1)), int(m.group(2))
        year = _infer_year(sm, today)
        try:
            dt = datetime(year, sm, sd)
            return dt, dt
        except ValueError:
            pass

    return None, None


def _build_source_id(
    source_name: str, detail_url: Optional[str], has_detail: bool, title: str, date_str: str
) -> str:
    """Derive a stable source_id from the detail URL slug, or a hash fallback.

    All hankyu event links are absolute http URLs, so slug extraction from the
    resolved detail URL is identical to the legacy raw-href behaviour for 梅田
    (backward-compatible source_id), while also handling relative hrefs.
    """
    if has_detail and detail_url:
        clean = detail_url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
        slug = clean.split("/")[-1]
        if slug and slug not in _SLUG_STOPWORDS:
            return f"{source_name}_{slug}"
    raw = f"{title}|{date_str}"
    digest = hashlib.sha1(raw.encode()).hexdigest()[:10]
    return f"{source_name}_{digest}"


def _fetch_taiwan_detail_evidence(detail_url: str) -> tuple[bool, str]:
    """Fetch a detail page and look for Taiwan evidence (L2 filter).

    Collects the ``<meta name="description">`` (main activity description, placed
    first) plus every ``<img alt>`` that mentions Taiwan (order-preserving dedup).
    Returns ``(is_taiwan_related, evidence_text)``. On any network error returns
    ``(False, "")`` — a conservative skip so no Taiwan-less dirty data is created.
    """
    try:
        time.sleep(_DELAY)
        resp = requests.get(detail_url, headers=_HEADERS, timeout=15)
        resp.encoding = "utf-8"
        resp.raise_for_status()
    except Exception as exc:
        logger.debug("hankyu: detail fetch failed %s: %s", detail_url[:80], exc)
        return False, ""

    soup = BeautifulSoup(resp.text, "html.parser")

    parts: list[str] = []
    meta_el = soup.find("meta", attrs={"name": "description"})
    if meta_el and meta_el.get("content"):
        parts.append(meta_el["content"].strip())

    for img in soup.find_all("img", alt=True):
        alt = (img.get("alt") or "").strip()
        if alt and _TAIWAN_RE.search(alt):
            parts.append(alt)

    # Order-preserving dedup, then null-byte guard + length cap.
    evidence = "\n".join(dict.fromkeys(p for p in parts if p)).replace("\x00", "").strip()
    if len(evidence) > _EVIDENCE_MAX_CHARS:
        evidence = evidence[:_EVIDENCE_MAX_CHARS]

    return bool(_TAIWAN_RE.search(evidence)), evidence


class _HankyuBase(BaseScraper):
    """Shared scrape/parse logic for all Hankyu department stores.

    Concrete subclasses set ``SOURCE_NAME`` and ``_STORE_KEY``. The class name
    must snake_case to ``SOURCE_NAME`` (main._scraper_key), e.g.
    ``HankyuHakataScraper`` → ``hankyu_hakata``.
    """

    _STORE_KEY: str = ""

    @property
    def _store(self) -> _Store:
        return _STORES[self._STORE_KEY]

    def _get(self, url: str) -> BeautifulSoup:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.encoding = "utf-8"
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def scrape(self) -> list[Event]:
        store = self._store
        today = date.today()
        logger.info("Fetching %s event schedule: %s", store.display_name, store.event_url)
        time.sleep(_DELAY)

        try:
            soup = self._get(store.event_url)
        except Exception as exc:
            logger.error("Failed to fetch %s: %s", store.event_url, exc)
            return []

        events: list[Event] = []
        articles = soup.select("article div.o-event")
        logger.info("%s: found %d event items", store.source_name, len(articles))

        for div in articles:
            try:
                event = self._parse_event(div, today, store)
                if event:
                    events.append(event)
            except Exception as exc:
                logger.warning("Skipping event due to error: %s", exc, exc_info=True)

        logger.info(
            "%s: %d total items → %d Taiwan-related", store.source_name, len(articles), len(events)
        )
        return events

    def _parse_event(self, div: Tag, today: date, store: _Store) -> Optional[Event]:
        """Parse a single <div class="o-event"> into an Event, or return None."""
        title_el = div.select_one("p.o-event__title")
        title = title_el.get_text(" ", strip=True) if title_el else ""

        desc_el = div.select_one("p.o-event__desc")
        desc = desc_el.get_text(strip=True) if desc_el else ""

        # --- Detail URL ---
        link_el = div.select_one("a[href]")
        raw_url = link_el.get("href", "") if link_el else ""
        if raw_url.startswith("http"):
            detail_url = raw_url
            has_detail = True
        elif raw_url.startswith("/"):
            detail_url = store.base_url + raw_url
            has_detail = True
        else:
            detail_url = store.event_url
            has_detail = False

        # --- Two-layer Taiwan filter ---
        haystack = f"{title} {desc}"
        evidence_text = ""
        if _TAIWAN_RE.search(haystack):
            pass  # L1 hit — collect directly
        elif _ASIA_RE.search(haystack) and has_detail:
            is_taiwan, evidence_text = _fetch_taiwan_detail_evidence(detail_url)
            if not is_taiwan:
                return None  # L2 miss — pan-Asian event with no Taiwan content
        else:
            return None

        # --- Date & Venue from detail block ---
        detail_el = div.select_one("div.o-event__detail")
        detail_text = detail_el.get_text("\n", strip=True) if detail_el else ""

        start_date, end_date = _parse_date_range(detail_text, today)

        date_str_match = re.search(rf"{_MARK}[^\n◎●]{{3,50}}", detail_text)
        date_str = date_str_match.group(0).strip() if date_str_match else ""

        # Venue is the second marker line: e.g. "●8階 催場"
        marker_lines = re.findall(rf"{_MARK}\s*(.+)", detail_text)
        venue: Optional[str] = None
        if len(marker_lines) >= 2:
            venue = marker_lines[1].strip()
        elif len(marker_lines) == 1 and not re.search(r"\d+月\d+日", marker_lines[0]):
            venue = marker_lines[0].strip()

        location_name = f"{store.display_name} {venue}" if venue else store.display_name

        source_id = _build_source_id(store.source_name, detail_url, has_detail, title, date_str)

        # --- raw_description (+ L2 evidence appended for annotator context) ---
        date_prefix = ""
        if start_date:
            date_prefix = f"開催日時: {start_date.year}年{start_date.month}月{start_date.day}日\n\n"
        raw_desc = f"{date_prefix}{desc}\n\n{detail_text}".strip()
        if evidence_text:
            raw_desc = f"{raw_desc}\n\n{evidence_text}".strip()
        raw_desc = raw_desc.replace("\x00", "")

        return Event(
            source_name=store.source_name,
            source_id=source_id,
            source_url=detail_url,
            official_url=detail_url,  # Hankyu is an official department-store source
            original_language="ja",
            raw_title=title,
            raw_description=raw_desc,
            name_ja=title,
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=store.location_address,
            location_prefectures=list(store.location_prefectures),
            category=["lifestyle_food"],
            is_active=True,
        )


class HankyuUmedaScraper(_HankyuBase):
    """阪急うめだ本店 (Osaka) — weekly event schedule."""

    SOURCE_NAME = "hankyu_umeda"
    _STORE_KEY = "hankyu_umeda"


class HankyuHakataScraper(_HankyuBase):
    """博多阪急 (Fukuoka) — weekly event schedule."""

    SOURCE_NAME = "hankyu_hakata"
    _STORE_KEY = "hankyu_hakata"


class HankyuKobeScraper(_HankyuBase):
    """神戸阪急 (Hyogo) — weekly event schedule."""

    SOURCE_NAME = "hankyu_kobe"
    _STORE_KEY = "hankyu_kobe"
