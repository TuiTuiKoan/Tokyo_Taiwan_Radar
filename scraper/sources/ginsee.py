"""Scraper for ginsee.jp — OYAMA Cinema ROBLE & 宇都宮ヒカリ座

Both theaters share the same JSON API:
  GET /api/theaters/{code}/showing-movies
  → { "movies": [ { "code", "title", "alt", "startDate", "endDate", ... }, ... ] }

startDate / endDate: "YYYY-MM-DD" (ISO date, no timezone info)
Detail page: /roble/movie-guide/?c={code}&b=0

Source names : ginsee_roble (ROBLE) / ginsee_hikariza (ヒカリ座)
Source ID    : ginsee_roble_{code} / ginsee_hikariza_{code}
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

_API_URL = "https://www.ginsee.jp/api{version}/theaters/{code}/showing-movies"
_DETAIL_URL = "https://www.ginsee.jp/{theater}/movie-guide/?c={code}&b=0"
_UA = "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "台灣", "金馬", "金马"]

_THEATERS = [
    {
        "api_code": "roble",
        "api_version": "",        # /api/theaters/...
        "theater": "roble",
        "source_name": "ginsee_roble",
        "location_name": "OYAMA Cinema ROBLE",
        "location_address": "栃木県小山市",
        "location_url": "https://www.ginsee.jp/roble/",
        "prefecture": "栃木",
    },
    {
        "api_code": "hikariza",
        "api_version": "2",       # /api2/theaters/...
        "theater": "hikariza",
        "source_name": "ginsee_hikariza",
        "location_name": "宇都宮ヒカリ座",
        "location_address": "栃木県宇都宮市",
        "location_url": "https://www.ginsee.jp/hikariza/",
        "prefecture": "栃木",
    },
]


def _is_taiwan(title: str, alt: str = "") -> bool:
    combined = title + " " + (alt or "")
    return any(kw in combined for kw in _TAIWAN_KEYWORDS)


def _parse_date(date_str: str | None):
    if not date_str:
        return None
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class _GinseeTheaterScraper(BaseScraper):
    def __init__(self, theater: dict):
        self._theater = theater

    @property
    def source_name(self):
        return self._theater["source_name"]

    def scrape(self) -> list[Event]:
        url = _API_URL.format(code=self._theater["api_code"], version=self._theater["api_version"])
        try:
            resp = requests.get(url, headers={"User-Agent": _UA}, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("%s: API request failed: %s", self.source_name, exc)
            return []

        movies = data.get("movies", [])
        events: list[Event] = []

        for movie in movies:
            title = movie.get("title", "") or ""
            alt = movie.get("alt", "") or ""
            if not _is_taiwan(title, alt):
                continue

            code = movie.get("code")
            if not code:
                continue

            source_id = f"{self.source_name}_{code}"
            source_url = _DETAIL_URL.format(
                theater=self._theater["theater"], code=code
            )
            start_date = _parse_date(movie.get("startDate"))
            end_date = _parse_date(movie.get("endDate"))

            events.append(Event(
                source_name=self.source_name,
                source_id=source_id,
                source_url=source_url,
                original_language="ja",
                name_ja=title,
                name_en=alt or None,
                start_date=start_date,
                end_date=end_date,
                location_name=self._theater["location_name"],
                location_address=self._theater["location_address"],
                location_url=self._theater["location_url"],
                is_paid=True,
                raw_title=title,
                organizer=self._theater["location_name"],
                organizer_type=["commercial_brand"],
                event_form=["screening"],
            ))

        logger.info("%s: %d Taiwan events found", self.source_name, len(events))
        return events


class GinseeRobleScraper(_GinseeTheaterScraper):
    source_name = "ginsee_roble"

    def __init__(self):
        super().__init__(_THEATERS[0])


class GinseeHikarizaScraper(_GinseeTheaterScraper):
    source_name = "ginsee_hikariza"

    def __init__(self):
        super().__init__(_THEATERS[1])
