"""
Scraper for 川崎市アートセンター アルテリオ映像館 (Kawasaki Art Center Cinema), Kawasaki.

Strategy:
  1. Fetch /movie/theater/ — parse all a[href*="/movie/theater/detail/?id="] links
     (both 上映中 and 近日上映 sections)
  2. For each detail page, check full page text for Taiwan keywords (台湾/台灣/Taiwan)
  3. Extract title from h2 on detail page, dates from 上映日 or date range text
  4. source_id: "kawasaki_ac_{id_num}" — from "?id=002430" → "kawasaki_ac_002430"
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://kawasaki-ac.jp"
LISTING_URL = f"{BASE_URL}/movie/theater/"
LOCATION_NAME = "川崎市アートセンター アルテリオ映像館"
LOCATION_ADDRESS = "神奈川県川崎市麻生区万福寺6-7-1"
ORGANIZER_NAME = "川崎市アートセンター"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _parse_id(href: str) -> Optional[str]:
    m = re.search(r"[?&]id=(\w+)", href)
    return m.group(1) if m else None


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _safe_datetime(year: int, month: int, day: int) -> Optional[datetime]:
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _parse_date_range(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse flexible date formats from listing/detail text."""
    if not text:
        return None, None

    cleaned = re.sub(r"[（(][^）)]*[）)]", "", text)
    cleaned = cleaned.replace("〜", "～")
    cleaned = re.sub(r"※\s*休映日[^\n]*", "", cleaned)
    matches = list(
        re.finditer(
            r"(?:(?P<year>\d{4})\s*年\s*)?"
            r"(?P<month>\d{1,2})\s*(?:[/.]|月)\s*(?P<day>\d{1,2})\s*日?",
            cleaned,
        )
    )
    if not matches:
        return None, None

    tokens: list[datetime] = []
    inferred_year = datetime.now().year

    for m in matches:
        if m.group("year"):
            inferred_year = int(m.group("year"))
        month = int(m.group("month"))
        day = int(m.group("day"))

        if tokens and not m.group("year"):
            prev = tokens[-1]
            if prev.month == 12 and month == 1:
                inferred_year = prev.year + 1
            elif prev.month == 1 and month == 12:
                inferred_year = prev.year - 1
            else:
                inferred_year = prev.year

        dt = _safe_datetime(inferred_year, month, day)
        if dt:
            tokens.append(dt)

    if not tokens:
        return None, None

    start = tokens[0]
    end = tokens[-1]
    if len(tokens) == 1:
        end = start
    return start, end


def _extract_business_hours(text: str) -> Optional[str]:
    if not text:
        return None
    times = re.findall(r"(?:[01]?\d|2[0-3]):[0-5]\d", text)
    if not times:
        return None
    seen: list[str] = []
    for t in times:
        if t not in seen:
            seen.append(t)
    return "上映時間: " + " / ".join(seen)


def _extract_price_info(text: str) -> Optional[str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return None
    if not re.search(r"料金|一般|学生|シニア|高校生|円|無料|特別料金", cleaned):
        return None
    return cleaned


class KawasakiAcScraper(BaseScraper):
    """Scrapes Taiwan-related films from 川崎市アートセンター アルテリオ映像館."""

    SOURCE_NAME = "kawasaki_ac"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })
        retry = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _get(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as exc:
            logger.warning("GET %s failed: %s", url, exc)
            return None

    def _scrape_detail(self, url: str) -> dict:
        result = {
            "title": "",
            "description": "",
            "full_text": "",
            "work_info": "",
            "screening_date": "",
            "price_info": "",
            "official_url": "",
            "business_hours": "",
        }
        soup = self._get(url)
        if not soup:
            return result

        detail_root = soup.select_one("div.cont-inner.detail-inner") or soup.select_one("section.movie-theater")

        h2 = (detail_root.find("h2") if detail_root else None) or soup.find("h2")
        if h2:
            result["title"] = h2.get_text(strip=True)

        desc_parts: list[str] = []
        if detail_root:
            inner = detail_root.select_one("div.theater-inner")
            if inner:
                for p in inner.select("p"):
                    text = _clean_text(p.get_text(" ", strip=True))
                    if not text:
                        continue
                    if text.startswith("©"):
                        continue
                    desc_parts.append(text)

        table = detail_root.select_one("table.theater-detail") if detail_root else soup.select_one("table.theater-detail")
        if table:
            for tr in table.select("tr"):
                th = _clean_text((tr.find("th") or "").get_text(" ", strip=True) if tr.find("th") else "")
                td_node = tr.find("td")
                td_text = _clean_text(td_node.get_text(" ", strip=True) if td_node else "")
                if not td_text:
                    continue

                if "作品情報" in th:
                    result["work_info"] = td_text
                elif "上映日" in th:
                    result["screening_date"] = td_text
                elif "料金" in th:
                    result["price_info"] = td_text
                elif "公式サイト" in th:
                    link = td_node.find("a") if td_node else None
                    if link and link.get("href"):
                        result["official_url"] = link.get("href", "")

        result["description"] = "\n".join(desc_parts)
        result["full_text"] = _clean_text(detail_root.get_text(" ", strip=True) if detail_root else soup.get_text(" ", strip=True))

        if not result["price_info"]:
            result["price_info"] = _extract_price_info(result["screening_date"]) or _extract_price_info(result["work_info"])
        result["business_hours"] = _extract_business_hours(result["screening_date"]) or ""

        return result

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        soup = self._get(LISTING_URL)
        if not soup:
            logger.error("Failed to fetch listing page: %s", LISTING_URL)
            return events

        # Collect all detail links with associated date range text
        seen_ids: set[str] = set()
        cards: list[tuple[str, str, str]] = []  # (href, title, date_text)

        for link in soup.select("a[href*='/movie/theater/detail/']"):
            href = link.get("href", "")
            film_id = _parse_id(href)
            if not film_id or film_id in seen_ids:
                continue
            seen_ids.add(film_id)

            title = link.get_text(strip=True)

            # Date text: look in parent element for sibling text
            parent = link.parent
            date_text = ""
            if parent:
                date_text = parent.get_text(" ", strip=True)

            full_href = BASE_URL + href if href.startswith("/") else href
            cards.append((full_href, title, date_text))

        logger.info("Found %d unique film cards", len(cards))

        for detail_url, card_title, date_text in cards:
            time.sleep(0.5)
            detail = self._scrape_detail(detail_url)

            if not _is_taiwan(detail["full_text"]):
                logger.debug("Skipping non-Taiwan film: %s", detail["title"] or card_title)
                continue

            film_id = _parse_id(detail_url)
            source_id = f"kawasaki_ac_{film_id}"
            title = detail["title"] or card_title

            date_source = detail["screening_date"] or date_text
            start_date, end_date = _parse_date_range(date_source)

            raw_parts: list[str] = []
            if start_date:
                raw_parts.append(
                    f"開催日時: {start_date.strftime('%Y年%m月%d日')}"
                    + (f"〜{end_date.strftime('%Y年%m月%d日')}" if end_date else "")
                )
            if detail["description"]:
                raw_parts.append(f"作品紹介: {detail['description']}")
            if detail["work_info"]:
                raw_parts.append(f"作品情報: {detail['work_info']}")
            if detail["screening_date"]:
                raw_parts.append(f"上映日: {detail['screening_date']}")
            if detail["price_info"]:
                raw_parts.append(f"料金: {detail['price_info']}")
            if detail["official_url"]:
                raw_parts.append(f"公式サイト: {detail['official_url']}")

            raw_desc = "\n\n".join(raw_parts).strip() or detail["description"]

            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=detail_url,
                original_language="ja",
                name_ja=title,
                raw_title=title,
                raw_description=raw_desc,
                description_ja=detail["description"] or None,
                category=["movie"],
                start_date=start_date,
                end_date=end_date,
                location_name=LOCATION_NAME,
                location_address=LOCATION_ADDRESS,
                organizer=ORGANIZER_NAME,
                business_hours=detail["business_hours"] or None,
                is_paid=True if detail["price_info"] else None,
                price_info=detail["price_info"] or None,
                official_url=detail["official_url"] or None,
            )
            events.append(event)
            logger.info("Found Taiwan film: %s", title)

        logger.info("Total Taiwan films found: %d", len(events))
        return events
