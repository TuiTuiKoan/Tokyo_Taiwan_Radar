"""Scraper for 八丁座・サロンシネマ (johakyu.co.jp) — Hiroshima cinema chain.

Source URL: https://johakyu.co.jp/schedule.html
Platform  : Static HTML (custom CMS) — no JS rendering required for schedule
Source name: johakyu
Source ID : johakyu_{movie_image_id}  (e.g. johakyu_03082, from image filename)

Strategy:
  1. Fetch https://johakyu.co.jp/schedule.html
  2. Parse each .schedule-sec (八丁座 / サロンシネマ) separately
  3. For each .schedule-date-block, extract week range + movie list
  4. Collect unique movies; use first week appearance as start_date
  5. For each movie, fetch the external distributor page via fetch_ref_text()
     to check for Taiwan keyword relevance
  6. If relevant, emit an Event with week start_date and week end_date

Taiwan keyword filter:
  ["台湾", "Taiwan", "臺灣", "金馬", "台北", "台中", "高雄"]
  Applied to external distributor page text (via fetch_ref_text).
  Also applied to title directly for known Taiwan film title patterns.

Date format:
  week header: "5月8日(金)～5月14日(木)のスケジュール"

Venues:
  - 八丁座: 広島県広島市中区本通8-14 ｼﾃｨﾌﾟﾗｻﾞ本通 3F
  - サロンシネマ: 広島県広島市中区三川町9-16 三川町ビル地下1F
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event, fetch_ref_text
from movie_title_lookup import lookup_movie_titles

logger = logging.getLogger(__name__)

SOURCE_NAME = "johakyu"

_SCHEDULE_URL = "https://johakyu.co.jp/schedule.html"
_BASE_URL = "https://johakyu.co.jp"

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

# Taiwan relevance keywords
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "金馬", "台北", "台中", "高雄"]

# Week date range pattern: "5月8日(金)～5月14日(木)のスケジュール"
_WEEK_RE = re.compile(
    r"(\d{1,2})月(\d{1,2})日[^〜\n]*[〜～~]"
    r"(\d{1,2})月(\d{1,2})日"
)

# Movie image ID pattern: "movie_03082.jpg" → "03082"
_MOVIE_ID_RE = re.compile(r"movie_(\d+)\.(?:jpg|png|webp)", re.IGNORECASE)

# Theaters on the schedule page (in order of .schedule-sec)
_THEATERS = [
    {
        "name": "八丁座",
        "location_name": "八丁座",
        "location_address": "広島県広島市中区本通8-14 シティプラザ本通3F",
    },
    {
        "name": "サロンシネマ",
        "location_name": "サロンシネマ",
        "location_address": "広島県広島市中区三川町9-16 三川町ビル地下1F",
    },
]


def _is_taiwan_relevant(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _infer_year(month: int, today: datetime) -> int:
    if month < today.month - 3:
        return today.year + 1
    return today.year


def _parse_week_range(week_text: str, today: datetime) -> tuple[datetime | None, datetime | None]:
    """Parse 'X月Y日(曜)～X月Y日(曜)のスケジュール' into (start, end)."""
    m = _WEEK_RE.search(week_text)
    if not m:
        return None, None
    sm, sd, em, ed = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    year = _infer_year(sm, today)
    try:
        start = datetime(year, sm, sd, tzinfo=timezone.utc)
        # end month could be next month
        end_year = year if em >= sm else year + 1
        end = datetime(end_year, em, ed, tzinfo=timezone.utc)
        return start, end
    except ValueError:
        return None, None


class JohakyuScraper(BaseScraper):
    """Scraper for 八丁座・サロンシネマ (johakyu.co.jp)."""

    SOURCE_NAME = SOURCE_NAME

    def __init__(self) -> None:
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": _USER_AGENT,
            "Accept-Language": "ja,en;q=0.9",
        })
        _retry = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        self._session.mount("https://", HTTPAdapter(max_retries=_retry))
        self._session.mount("http://", HTTPAdapter(max_retries=_retry))

    def scrape(self) -> list[Event]:
        today = datetime.now(tz=timezone.utc)
        events: list[Event] = []
        seen_movie_ids: set[str] = set()

        try:
            resp = self._session.get(_SCHEDULE_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("johakyu: failed to fetch schedule: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        schedule_secs = soup.select(".schedule-sec")
        logger.info("johakyu: found %d schedule sections", len(schedule_secs))

        for sec_idx, sec in enumerate(schedule_secs):
            theater = _THEATERS[sec_idx] if sec_idx < len(_THEATERS) else _THEATERS[0]

            # Collect movie→(start_date, end_date, external_url, movie_id) per week block
            movie_dates: dict[str, tuple[datetime, datetime, str, str]] = {}

            for block in sec.select(".schedule-date-block"):
                week_el = block.select_one(".schedule-week")
                if not week_el:
                    continue
                week_text = week_el.get_text()
                start_date, end_date = _parse_week_range(week_text, today)
                if not start_date:
                    logger.debug("johakyu: could not parse week: %s", week_text)
                    continue

                for item in block.select(".schedule-movie-list__item"):
                    title_el = item.select_one("h3.schedule-movie__title a")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    ext_url = title_el.get("href", "")

                    # Get stable movie_id from image filename
                    img = item.select_one("img[src*='movie_']")
                    movie_id_m = _MOVIE_ID_RE.search(img["src"] if img else "")
                    movie_id = movie_id_m.group(1) if movie_id_m else re.sub(r"[^\w]", "_", title)[:40]

                    # Use earliest start_date if seen in multiple weeks
                    if movie_id not in movie_dates or start_date < movie_dates[movie_id][0]:
                        movie_dates[movie_id] = (start_date, end_date, ext_url, title)

            # Now check Taiwan relevance and emit events
            for movie_id, (start_date, end_date, ext_url, title) in movie_dates.items():
                compound_id = f"{theater['name']}_{movie_id}"
                if compound_id in seen_movie_ids:
                    continue
                seen_movie_ids.add(compound_id)

                # Check Taiwan relevance via external page or title
                is_relevant = _is_taiwan_relevant(title)
                if not is_relevant and ext_url:
                    ref_text = fetch_ref_text(ext_url)
                    if ref_text:
                        is_relevant = _is_taiwan_relevant(ref_text)
                    time.sleep(0.5)

                if not is_relevant:
                    continue

                # Try to get multilingual titles via movie_title_lookup
                name_zh, name_en, _ = lookup_movie_titles(title)
                time.sleep(0.3)

                source_id = f"johakyu_{movie_id}"
                raw_desc = f"開催日時: {start_date.year}年{start_date.month}月{start_date.day}日〜{end_date.year}年{end_date.month}月{end_date.day}日\n\n上映館: {theater['name']}"
                if ext_url:
                    raw_desc += f"\n作品紹介: {ext_url}"

                events.append(Event(
                    source_name=SOURCE_NAME,
                    source_id=source_id,
                    source_url=_SCHEDULE_URL,
                    original_language="ja",
                    raw_title=title,
                    raw_description=raw_desc,
                    name_ja=title,
                    name_zh=name_zh,
                    name_en=name_en,
                    category=["movie"],
                    start_date=start_date,
                    end_date=end_date,
                    location_name=theater["location_name"],
                    location_address=theater["location_address"],
                ))
                logger.info("johakyu: found Taiwan movie: %s [%s]", title, theater["name"])

        logger.info("johakyu: total events: %d", len(events))
        return events
