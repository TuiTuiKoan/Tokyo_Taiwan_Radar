"""Scraper for 早稲田大学エクステンションセンター（Waseda University Extension Center）.

Source: POST search to /course/search-list/ with search_str=台湾
URL:    https://www.wuext.waseda.jp/course/search-list/
Events: ~3-6 active Taiwan-related lectures per term, 4 terms/year
Venue:  早稲田校（新宿区）/ 中野校（中野区）/ オンライン / オンデマンド

Search returns ~11 rows; all rows are kept when either:
  - 台湾 appears in the course title, OR
  - 台湾 (or related keyword) appears in the detail page body (id="course")
Status 受付終了 and オンデマンド are included (as historical / archive records).

source_id: wuext_waseda_{internal_id}  (numeric ID from /course/detail/{id}/)
category:  ["lecture", "academic", "taiwan_japan"]
is_paid:   derived from 会員価格 on detail page (¥0 → False, else True)

Date parsing (from listing 日時 column):
  Format: "2026年度 夏期 07月04日～07月25日 土 13:00～16:30"
  Year from YYYY年度; start from first MM月DD日; end from second MM月DD日.
  Fallback for on-demand/missing dates: derived from term (春期/夏期/秋期/冬期).
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.wuext.waseda.jp/course/search-list/"
DETAIL_BASE = "https://www.wuext.waseda.jp/course/detail/"
SOURCE_NAME = "wuext_waseda"

_HEADERS = {
    "User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)",
}

# Taiwan-related keywords used to check detail page body
_TAIWAN_KEYWORDS = ("台湾", "台北", "台中", "高雄", "台南", "日台", "台日", "中華民国")

# Known campus addresses
_CAMPUS_ADDRESS: dict[str, tuple[str, str]] = {
    "早稲田校": ("早稲田大学 早稲田キャンパス", "東京都新宿区西早稲田1-6-1"),
    "中野校": ("早稲田大学 中野国際コミュニティプラザ", "東京都中野区中野4-11-1"),
    "八丁堀校": ("早稲田大学 エクステンションセンター 八丁堀校", "東京都中央区八丁堀2-4-1"),
    "本庄校": ("早稲田大学 本庄キャンパス", "埼玉県本庄市西富田410"),
}

# Regex: extract year, start/end month-day, and start time from listing 日時 string
# Example: "2026年度 夏期 07月04日～07月25日 土 13:00～16:30 全4回"
_YEAR_RE = re.compile(r"(\d{4})年度")
_DATE_RANGE_RE = re.compile(r"(\d{1,2})月(\d{1,2})日[～〜-](\d{1,2})月(\d{1,2})日")
_SINGLE_DATE_RE = re.compile(r"(\d{1,2})月(\d{1,2})日")
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})～(\d{1,2}):(\d{2})")

# Regex: extract internal ID from detail URL
_DETAIL_ID_RE = re.compile(r"/course/detail/(\d+)/")

# Regex: extract price from detail page
_PRICE_RE = re.compile(r"[\u00a5¥]\s*([\d,]+)")

# Regex: extract dates in (YYYY/MM/DD) or YYYY年MM月DD日 format from detail page body
# Example: "一般申込開始(2025/11/26)から学期終了翌月末(2026/04/30)まで"
_DETAIL_DATE_PARENS_RE = re.compile(r"\((\d{4})/(\d{1,2})/(\d{1,2})\)")
_DETAIL_DATE_KANJI_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def _extract_detail_dates(
    detail_soup: BeautifulSoup,
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Extract start/end dates from detail page body text.

    Looks for (YYYY/MM/DD) patterns (e.g. viewing period for on-demand courses).
    Returns (earliest_date, latest_date) or (None, None) if none found.
    """
    course_div = detail_soup.find(id="course")
    if not course_div:
        return None, None
    text = course_div.get_text(" ", strip=True)
    found: list[datetime] = []
    for m in _DETAIL_DATE_PARENS_RE.finditer(text):
        try:
            found.append(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc))
        except ValueError:
            pass
    if not found:
        for m in _DETAIL_DATE_KANJI_RE.finditer(text):
            try:
                found.append(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc))
            except ValueError:
                pass
    if not found:
        return None, None
    found.sort()
    return found[0], found[-1] if len(found) > 1 else None


def _parse_dates(date_str: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse start_date and end_date from listing 日時 column text.

    Returns (start_date, end_date) both with tzinfo=timezone.utc.
    Returns (None, None) if parsing fails.
    """
    year_m = _YEAR_RE.search(date_str)
    if not year_m:
        return None, None
    year = int(year_m.group(1))

    time_m = _TIME_RE.search(date_str)
    start_hour = int(time_m.group(1)) if time_m else 10
    start_min = int(time_m.group(2)) if time_m else 0

    range_m = _DATE_RANGE_RE.search(date_str)
    if range_m:
        sm, sd = int(range_m.group(1)), int(range_m.group(2))
        em, ed = int(range_m.group(3)), int(range_m.group(4))
        # Fiscal year: if month < 4, likely next calendar year
        sy = year if sm >= 4 else year + 1
        ey = year if em >= 4 else year + 1
        try:
            start = datetime(sy, sm, sd, start_hour, start_min, tzinfo=timezone.utc)
            end = datetime(ey, em, ed, tzinfo=timezone.utc)
            return start, end
        except ValueError:
            return None, None

    single_m = _SINGLE_DATE_RE.search(date_str)
    if single_m:
        sm, sd = int(single_m.group(1)), int(single_m.group(2))
        sy = year if sm >= 4 else year + 1
        try:
            start = datetime(sy, sm, sd, start_hour, start_min, tzinfo=timezone.utc)
            return start, start
        except ValueError:
            return None, None

    return None, None


# Term → (start_month, start_day) within fiscal year
# 冬期 falls in the *next* calendar year (fiscal year + 1)
_TERM_MONTH: dict[str, tuple[int, int, bool]] = {
    "年間": (4, 1, False),
    "春期": (4, 1, False),
    "夏期": (7, 1, False),
    "秋期": (10, 1, False),
    "冬期": (1, 1, True),   # True = use fiscal_year + 1
}


def _term_fallback_date(date_str: str) -> Optional[datetime]:
    """Derive an approximate start_date from fiscal year + term when no date range found."""
    year_m = _YEAR_RE.search(date_str)
    if not year_m:
        return None
    fiscal_year = int(year_m.group(1))
    for term, (month, day, next_year) in _TERM_MONTH.items():
        if term in date_str:
            cal_year = fiscal_year + 1 if next_year else fiscal_year
            try:
                return datetime(cal_year, month, day, tzinfo=timezone.utc)
            except ValueError:
                return None
    return None


def _is_taiwan_content(detail_soup: BeautifulSoup) -> bool:
    """Return True if the detail page body (id=course) contains Taiwan keywords."""
    course_div = detail_soup.find(id="course")
    if not course_div:
        return False
    text = course_div.get_text(" ", strip=True)
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _get_detail_price(soup: BeautifulSoup) -> Optional[str]:
    """Return price string from detail page, e.g. '¥12,000' or None."""
    # Find th/td pairs
    for th in soup.find_all("th"):
        label = th.get_text(strip=True)
        if "会員価格" in label or "受講料" in label:
            td = th.find_next_sibling("td")
            if td:
                return td.get_text(" ", strip=True)
    return None


def _extract_internal_id(url: str) -> Optional[str]:
    m = _DETAIL_ID_RE.search(url)
    return m.group(1) if m else None


class WuextWasedaScraper(BaseScraper):
    """早稲田大学エクステンションセンター 台湾関連講座スクレイパー."""

    @property
    def source_name(self) -> str:
        return SOURCE_NAME

    def scrape(self) -> list[Event]:
        try:
            resp = requests.post(
                SEARCH_URL,
                data={"state": "search-list", "page_index": "0", "search_str": "台湾"},
                headers=_HEADERS,
                allow_redirects=True,
                timeout=20,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("%s: fetch search page failed: %s", SOURCE_NAME, exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", {"summary": "検索結果"})
        if not table:
            logger.warning("%s: search result table not found", SOURCE_NAME)
            return []

        rows = table.find_all("tr")[1:]  # skip header row
        logger.info("%s: %d result rows found", SOURCE_NAME, len(rows))

        events: list[Event] = []
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue

            location_label = cols[0].get_text(strip=True)
            title_td = cols[1]
            link = title_td.find("a")
            detail_url = link["href"] if link else ""
            code_title_text = title_td.get_text(" ", strip=True)
            instructor = cols[2].get_text(strip=True)
            date_str = cols[3].get_text(" ", strip=True)
            status = cols[4].get_text(strip=True) if len(cols) > 4 else ""

            # Strip leading class code (6-digit number)
            title = re.sub(r"^\d{6}\s*", "", code_title_text).strip()

            internal_id = _extract_internal_id(detail_url)
            if not internal_id:
                logger.warning("%s: cannot extract internal ID from %s", SOURCE_NAME, detail_url)
                continue

            # --- Always fetch detail page (needed for price + Taiwan content check) ---
            detail_soup: Optional[BeautifulSoup] = None
            try:
                detail_resp = requests.get(detail_url, headers=_HEADERS, timeout=15)
                detail_resp.raise_for_status()
                detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
            except Exception as exc:
                logger.warning("%s: detail fetch failed for %s: %s", SOURCE_NAME, detail_url, exc)

            # Taiwan relevance check
            title_has_taiwan = any(kw in title for kw in _TAIWAN_KEYWORDS)
            content_has_taiwan = _is_taiwan_content(detail_soup) if detail_soup else False
            if not title_has_taiwan and not content_has_taiwan:
                logger.debug("%s: skip (no Taiwan content): %s", SOURCE_NAME, title[:50])
                continue

            source_id = f"{SOURCE_NAME}_{internal_id}"
            start_date, end_date = _parse_dates(date_str)
            if start_date is None and detail_soup:
                # Fallback A: extract dates from detail page body (e.g. on-demand viewing period)
                detail_start, detail_end = _extract_detail_dates(detail_soup)
                if detail_start:
                    start_date = detail_start
                    end_date = detail_end
                    logger.debug("%s: dates from detail page: %s ~ %s", SOURCE_NAME, start_date, end_date)
            if start_date is None:
                # Fallback B: derive from fiscal year + term (for on-demand / date-less rows)
                start_date = _term_fallback_date(date_str)
                end_date = None
            if start_date is None:
                logger.warning("%s: cannot parse date from '%s'", SOURCE_NAME, date_str[:60])
                continue

            # Venue / location
            if location_label == "オンライン":
                location_name = "オンライン"
                location_address = None
            elif location_label == "オンデマンド":
                location_name = "オンデマンド（録画配信）"
                location_address = None
            else:
                campus = _CAMPUS_ADDRESS.get(location_label)
                if campus:
                    location_name, location_address = campus
                else:
                    location_name = f"早稲田大学 {location_label}"
                    location_address = None

            # Price from detail page (already fetched above)
            is_paid: Optional[bool] = None
            price_info: Optional[str] = None
            if detail_soup:
                price_text = _get_detail_price(detail_soup)
                if price_text:
                    price_info = " ".join(price_text.replace("\xa5", "¥").split())
                    m = _PRICE_RE.search(price_text)
                    if m:
                        amount = int(m.group(1).replace(",", ""))
                        is_paid = amount > 0
                    else:
                        is_paid = "0" not in price_text

            # Build description
            desc_parts = [f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n"]
            if instructor:
                desc_parts.append(f"講師: {instructor}")
            if date_str:
                desc_parts.append(f"日時: {date_str}")
            if location_name:
                desc_parts.append(f"会場: {location_name}")
            if status:
                desc_parts.append(f"申込状況: {status}")
            if price_info:
                desc_parts.append(f"受講料: {price_info}")
            raw_description = "\n".join(desc_parts).replace("\x00", "")

            event = Event(
                source_name=SOURCE_NAME,
                source_id=source_id,
                source_url=detail_url,
                original_language="ja",
                name_ja=title.replace("\x00", ""),
                raw_title=title.replace("\x00", ""),
                raw_description=raw_description,
                category=["lecture", "academic", "taiwan_japan"],
                start_date=start_date,
                end_date=end_date if (end_date and end_date.date() != start_date.date()) else None,
                location_name=location_name,
                location_address=location_address,
                is_paid=is_paid,
                price_info=price_info,
                organizer="早稲田大学エクステンションセンター",
                organizer_type=["academic"],
            )
            events.append(event)
            logger.info(
                "%s: event [%s] %s (%s)",
                SOURCE_NAME,
                source_id,
                title[:50],
                start_date.date(),
            )

        logger.info("%s: total %d events", SOURCE_NAME, len(events))
        return events
