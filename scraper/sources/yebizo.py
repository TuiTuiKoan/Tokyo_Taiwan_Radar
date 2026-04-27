"""
Scraper for 恵比寿映像祭 (Yebisu International Festival for Art & Alternative Visions).

Hosted annually at Tokyo Photographic Art Museum (TOP Museum, Yebisu Garden Place).
Usually held in February.  2026 theme: "あなたの音に｜日花聲音" — curated with strong
Taiwan connection (curator 邱于瑄, artist 張恩滿, etc.)

URL: https://www.yebizo.com/jp/archives/program

Strategy:
  1. Fetch /jp/archives/program — lists all programs via .program_archive div
  2. Parse each program link → extract artist, dates, venue from link text
  3. Pre-filter: artist name matches foreign East Asian pattern (CJK + katakana reading)
     OR link text mentions 台湾/台灣
  4. For pre-filtered candidates: fetch detail page → verify 台湾/台灣 in body text
  5. Create one Event per confirmed Taiwan-related program
  6. source_id: yebizo_{program_id}  (numeric ID from /jp/program/NNNN URL)
"""

import re
import time
import logging
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.yebizo.com"
PROGRAM_LIST_URL = f"{BASE_URL}/jp/archives/program"
SOURCE_NAME = "yebizo"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}

# Program ID from URL /jp/program/682
_PROG_ID_RE = re.compile(r"/jp/program/(\d+)")

# Date extraction
_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")

# Foreign East Asian artist: 2+ CJK chars followed by katakana reading in （）
# e.g. 張恩滿（チャン・エンマン）, 邱于瑄（チュウ・ユシュエン）
_FOREIGN_ARTIST_RE = re.compile(r"[\u4e00-\u9fff]{2,}（[ァ-ヴ・ー]{3,}）")

# Taiwan keywords to look for in page content
_TAIWAN_RE = re.compile(r"台[湾灣]|台湾原住民|台灣|タイワン")

# Location address for TOP Museum
_TOPMUSEUM_ADDRESS = "東京都目黒区三田1-13-3 恵比寿ガーデンプレイス内"


def _parse_date(year: int, month: int, day: int) -> Optional[datetime]:
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _extract_dates(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Extract start and optional end date from text like '2026年2月6日 - 2026年2月23日'."""
    matches = _DATE_RE.findall(text)
    dates = [_parse_date(int(y), int(m), int(d)) for y, m, d in matches]
    dates = [d for d in dates if d is not None]
    start = dates[0] if dates else None
    end = dates[1] if len(dates) > 1 else None
    return start, end


_TIME_RE = re.compile(r"^\d{1,2}:\d{2}")


def _extract_artist_and_venue(link_text: str) -> tuple[str, str]:
    """Extract artist name and venue from pipe-separated link text.

    Format: type(s)|[subtype]|price|artist|date_range|[time_range]|venue[|artist_repeat]
    The artist is the segment immediately before the first date segment.
    The venue is the first segment after the date (and optional time) segments
    that does not look like a time string.
    """
    parts = [p.strip() for p in link_text.split("|") if p.strip()]
    date_idx = next(
        (i for i, p in enumerate(parts) if _DATE_RE.search(p)),
        -1,
    )
    artist = parts[date_idx - 1] if date_idx > 0 else ""

    # Skip consecutive date/time segments after date_idx to find venue
    venue = "東京都写真美術館"
    for i in range(date_idx + 1, len(parts)):
        seg = parts[i]
        # Skip segments that are date or time-range
        if _DATE_RE.search(seg) or _TIME_RE.match(seg):
            continue
        # First non-date/time segment after the date is the venue
        venue = seg
        break

    return artist, venue


class YebizoScraper(BaseScraper):
    SOURCE_NAME = SOURCE_NAME

    def _fetch(self, url: str, retries: int = 2) -> Optional[str]:
        for attempt in range(retries + 1):
            try:
                r = requests.get(url, headers=_HEADERS, timeout=15)
                r.raise_for_status()
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text
            except Exception as exc:
                logger.warning("Fetch error (%d/%d) %s: %s", attempt + 1, retries + 1, url, exc)
                if attempt < retries:
                    time.sleep(1.5)
        return None

    def _check_taiwan(self, detail_url: str) -> tuple[bool, str, str]:
        """Fetch detail page; return (is_taiwan, title, description_body).

        Extracts:
        - Title: h1.single_article__ttl
        - Description: <p> elements inside main content
        """
        html = self._fetch(detail_url)
        if not html:
            return False, "", ""

        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title_el = soup.select_one("h1.single_article__ttl")
        title = title_el.get_text(strip=True) if title_el else ""

        # Extract description from paragraphs in main content
        main = soup.select_one("main") or soup
        paragraphs = [
            p.get_text(separator=" ", strip=True)
            for p in main.find_all("p")
            if len(p.get_text(strip=True)) > 20
        ]
        body = "\n\n".join(paragraphs)

        is_taiwan = bool(_TAIWAN_RE.search(body)) or bool(_TAIWAN_RE.search(title))
        return is_taiwan, title, body

    def scrape(self) -> list[Event]:
        html = self._fetch(PROGRAM_LIST_URL)
        if not html:
            logger.error("YebizoScraper: failed to fetch program listing")
            return []

        soup = BeautifulSoup(html, "html.parser")
        program_links = soup.find_all("a", href=_PROG_ID_RE)
        logger.info("YebizoScraper: found %d programs on listing", len(program_links))

        # Build candidate list with pre-filtering
        candidates: list[dict] = []
        seen_ids: set[str] = set()
        for a in program_links:
            href = a.get("href", "")
            prog_id_m = _PROG_ID_RE.search(href)
            if not prog_id_m:
                continue
            prog_id = prog_id_m.group(1)
            if prog_id in seen_ids:
                continue
            seen_ids.add(prog_id)

            full_url = BASE_URL + href if href.startswith("/") else href
            link_text = a.get_text(separator="|", strip=True)
            artist, venue = _extract_artist_and_venue(link_text)

            # Pre-filter: foreign East Asian artist OR Taiwan keyword in listing text
            is_foreign = bool(_FOREIGN_ARTIST_RE.search(link_text))
            has_taiwan = bool(_TAIWAN_RE.search(link_text))
            if not is_foreign and not has_taiwan:
                continue

            start_date, end_date = _extract_dates(link_text)
            candidates.append({
                "prog_id": prog_id,
                "url": full_url,
                "link_text": link_text,
                "artist": artist,
                "venue": venue,
                "start_date": start_date,
                "end_date": end_date,
            })

        logger.info("YebizoScraper: %d Taiwan-candidate programs (pre-filter)", len(candidates))

        events: list[Event] = []
        for prog in candidates:
            time.sleep(0.8)
            is_taiwan, detail_title, detail_body = self._check_taiwan(prog["url"])
            if not is_taiwan:
                logger.debug(
                    "YebizoScraper: skipping non-Taiwan program %s: %s",
                    prog["prog_id"],
                    prog["artist"],
                )
                continue

            raw_title = detail_title or prog["artist"]
            start = prog["start_date"]
            raw_description = (
                f"開催日時: {start.strftime('%Y年%m月%d日') if start else '未定'}\n\n"
                + detail_body[:3000]
            )

            source_id = f"yebizo_{prog['prog_id']}"
            # Determine if paid/free from link text
            is_paid: Optional[bool] = None
            if "有料" in prog["link_text"]:
                is_paid = True
            elif "無料" in prog["link_text"]:
                is_paid = False

            events.append(
                Event(
                    source_name=SOURCE_NAME,
                    source_id=source_id,
                    source_url=prog["url"],
                    original_language="ja",
                    name_ja=raw_title,
                    raw_title=raw_title,
                    raw_description=raw_description,
                    start_date=start,
                    end_date=prog["end_date"],
                    location_name=prog["venue"],
                    location_address=_TOPMUSEUM_ADDRESS,
                    is_paid=is_paid,
                    category=["art"],
                )
            )
            logger.info(
                "YebizoScraper: event %s | %s | %s",
                start.date() if start else "?",
                raw_title[:60],
                prog["url"],
            )

        logger.info("YebizoScraper: %d events total", len(events))
        return events
