"""Scraper for Stranger（ストレンジャー）— 東京墨田区の微型戲院

Source URL  : https://stranger.jp/
Platform    : Eigaland JSON API — no auth required
Source name : stranger
Source ID   : stranger_{movieId}

Strategy:
  1. Loop through today + 0..89 days (90-day window)
  2. For each date call listByDomainAndDate API
  3. Filter entries whose movieDetail.countries contains "台湾" or "台灣"
  4. Track min_date / max_date per movieId across the entire window
  5. For each unique Taiwan movie call movie/detail API for full synopsis
  6. Build one Event per movieId (start_date = earliest showing, end_date = latest)

Venue (fixed):
  Stranger
  東京都墨田区菊川3丁目6-13
"""

import base64
import logging
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Optional

import requests

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "stranger"

_BASE_URL = "https://stranger.jp"
_LIST_API = "https://stranger.jp/api/website/show/listByDomainAndDate"
_DETAIL_API_TPL = "https://stranger.jp/api/website/movie/detail/{movie_id}"

_JST = timezone(timedelta(hours=9))

_VENUE_NAME = "Stranger"
_VENUE_ADDRESS = "東京都墨田区菊川3丁目6-13"

# Taiwan relevance — countries field values to match
_TAIWAN_COUNTRIES = {"台湾", "台灣"}

_WINDOW_DAYS = 90
_SLEEP = 0.3  # seconds between API calls


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _HTMLStripper(HTMLParser):
    """Strip HTML tags, collecting inner text."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._parts.append(text)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _decode_synopsis(b64_html: str) -> str:
    """Decode base64-encoded HTML synopsis to plain text.

    The Eigaland API encodes synopsis as base64(HTML). Returns "" on failure.
    """
    if not b64_html:
        return ""
    try:
        html = base64.b64decode(b64_html).decode("utf-8")
        stripper = _HTMLStripper()
        stripper.feed(html)
        return stripper.get_text()
    except Exception as exc:
        logger.debug("Stranger: failed to decode synopsis: %s", exc)
        return ""


def _is_taiwan_relevant(countries: list) -> bool:
    return bool(_TAIWAN_COUNTRIES.intersection(set(countries)))


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class StrangerScraper(BaseScraper):
    """Scraper for Stranger cinema — 東京墨田区菊川."""

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        today = datetime.now(tz=_JST).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # movie_id → {"min_date": datetime, "max_date": datetime, "summary": dict}
        taiwan_movies: dict[str, dict] = {}

        for i in range(_WINDOW_DAYS):
            date = today + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            shows = self._fetch_shows(date_str)
            if shows is None:
                continue

            for show in shows:
                md = show.get("movieDetail", {})
                movie_id = md.get("movieId", "")
                if not movie_id:
                    continue
                if not _is_taiwan_relevant(md.get("countries", [])):
                    continue

                if movie_id not in taiwan_movies:
                    taiwan_movies[movie_id] = {
                        "min_date": date,
                        "max_date": date,
                        "summary": md,
                    }
                else:
                    entry = taiwan_movies[movie_id]
                    if date < entry["min_date"]:
                        entry["min_date"] = date
                    if date > entry["max_date"]:
                        entry["max_date"] = date

        logger.info(
            "Stranger: found %d Taiwan movie(s) in %d-day window",
            len(taiwan_movies),
            _WINDOW_DAYS,
        )

        events: list[Event] = []
        for movie_id, entry in taiwan_movies.items():
            detail = self._fetch_detail(movie_id)
            events.append(self._build_event(movie_id, entry, detail))

        return events

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_shows(self, date_str: str) -> Optional[list]:
        """Fetch show list for a given date. Returns None on failure."""
        try:
            resp = requests.get(
                _LIST_API,
                params={"domain": "stranger.jp", "date": date_str},
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("Stranger: failed to fetch shows for %s: %s", date_str, exc)
            return None
        finally:
            time.sleep(_SLEEP)

    def _fetch_detail(self, movie_id: str) -> Optional[dict]:
        """Fetch full movie detail. Returns None on failure."""
        url = _DETAIL_API_TPL.format(movie_id=movie_id)
        try:
            resp = requests.get(
                url, params={"domain": "stranger.jp"}, timeout=20
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning(
                "Stranger: failed to fetch detail for %s: %s", movie_id, exc
            )
            return None
        finally:
            time.sleep(_SLEEP)

    def _build_event(
        self,
        movie_id: str,
        entry: dict,
        detail: Optional[dict],
    ) -> Event:
        """Construct an Event from API data."""
        # Prefer full detail; fall back to summary from list API
        data = detail if detail else entry["summary"]

        movie_name: str = (
            data.get("movieName", "") or entry["summary"].get("movieName", "")
        )
        directors: list[str] = data.get("directors", [])
        casts: list[str] = data.get("casts", [])
        official_page: str = data.get("officialPageUrl", "") or ""
        synopsis_b64: str = data.get("synopsis", "") or ""
        original_name: str = data.get("originalName", "") or ""
        slogan: str = data.get("slogan", "") or ""
        open_year: str = str(data.get("openYear", "") or "")
        running_time: int = int(data.get("durationMin", 0) or 0)

        # Convert JST-aware datetimes to UTC-midnight date strings to avoid
        # the JST+9 offset causing the date to shift back to the previous day
        # when stored as UTC in Supabase (e.g. JST 2026-05-08 00:00 → UTC 15:00 prev day).
        start_date = entry["min_date"].replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end_date = entry["max_date"].replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

        # Build raw_description — prepend date marker per scraper conventions
        synopsis_text = _decode_synopsis(synopsis_b64)
        desc_parts: list[str] = [
            f"開催日時: {start_date.strftime('%Y年%m月%d日')}\n"
        ]
        if slogan:
            desc_parts.append(slogan)
        if synopsis_text:
            desc_parts.append(synopsis_text)
        if directors:
            desc_parts.append(f"監督: {', '.join(directors)}")
        if casts:
            desc_parts.append(f"出演: {', '.join(casts)}")
        if original_name:
            desc_parts.append(f"原題: {original_name}")
        if open_year:
            desc_parts.append(f"製作年: {open_year}")
        if running_time:
            desc_parts.append(f"上映時間: {running_time}分")
        raw_description = "\n\n".join(desc_parts)

        return Event(
            source_name=SOURCE_NAME,
            source_id=f"stranger_{movie_id}",
            source_url=f"{_BASE_URL}/movie/{movie_id}",
            original_language="ja",
            raw_title=movie_name,
            raw_description=raw_description,
            start_date=start_date,
            end_date=end_date,
            category=["movie"],
            location_name=_VENUE_NAME,
            location_address=_VENUE_ADDRESS,
            is_paid=True,
            director=", ".join(directors) if directors else None,
            official_url=official_page if official_page else None,
            name_ja=movie_name,
            name_ja_locked=True,
        )
