"""Scraper for ユナイテッドシネマ (multiple venues)

Covers three venues (Tsukuba / Toyohashi / Kashihara) that share the
same Shift_JIS HTML structure on unitedcinemas.jp.

Listing URL  : https://www.unitedcinemas.jp/<branch>/film.php
Encoding     : Shift_JIS
Card selector: ul.movieList li
Date format  : YYYY/MM/DD（曜）公開  (in <em> inside <h3>)
Title        : <strong><a href="film.php?movie=N">タイトル</a></strong>
Source ID    : united_cinemas_{branch}_{movie_id}

Taiwan keyword filter applied on title + cast text.
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

SOURCE_NAME = "united_cinemas"

_JST = timezone(timedelta(hours=9))

_VENUES = [
    {
        "branch": "tsukuba",
        "listing_url": "https://www.unitedcinemas.jp/tsukuba/film.php",
        "location_name": "ユナイテッドシネマつくば",
        "location_address": "茨城県つくば市",
        "location_url": "https://www.unitedcinemas.jp/tsukuba/",
        "prefecture": "茨城",
    },
    {
        "branch": "toyohashi",
        "listing_url": "https://www.unitedcinemas.jp/toyohashi/film.php",
        "location_name": "ユナイテッドシネマ豊橋",
        "location_address": "愛知県豊橋市",
        "location_url": "https://www.unitedcinemas.jp/toyohashi/",
        "prefecture": "愛知",
    },
    {
        "branch": "kashihara",
        "listing_url": "https://www.unitedcinemas.jp/kashihara/film.php",
        "location_name": "ユナイテッドシネマ橿原",
        "location_address": "奈良県橿原市",
        "location_url": "https://www.unitedcinemas.jp/kashihara/",
        "prefecture": "奈良",
    },
]

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "台灣", "金馬", "金马"]

_BASE_URL = "https://www.unitedcinemas.jp"
_UA = "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"
_DATE_RE = re.compile(r"(\d{4})/(\d{2})/(\d{2})[（(]")


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _parse_date(text: str):
    """Parse 'YYYY/MM/DD（曜）公開' → datetime (UTC midnight)."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        tzinfo=timezone.utc)
    except ValueError:
        return None


class UnitedCinemasScraper(BaseScraper):
    source_name = SOURCE_NAME

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        for venue in _VENUES:
            try:
                venue_events = self._scrape_venue(venue)
                events.extend(venue_events)
                logger.info("united_cinemas[%s]: %d events", venue["branch"], len(venue_events))
            except Exception as exc:
                logger.warning("united_cinemas[%s]: failed: %s", venue["branch"], exc)
            time.sleep(1)
        return events

    def _scrape_venue(self, venue: dict) -> list[Event]:
        resp = requests.get(
            venue["listing_url"],
            headers={"User-Agent": _UA},
            timeout=20,
        )
        resp.raise_for_status()
        html = resp.content.decode("shift_jis", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        events: list[Event] = []
        movie_list = soup.select_one("ul.movieList")
        if not movie_list:
            logger.warning("united_cinemas[%s]: ul.movieList not found", venue["branch"])
            return events

        for li in movie_list.select("li"):
            h3 = li.select_one("h3")
            if not h3:
                continue

            # Title
            title_a = h3.select_one("strong a")
            if not title_a:
                continue
            title = title_a.get_text(strip=True)

            # Director + cast
            dl_text = li.get_text(" ", strip=True)

            # Taiwan filter
            if not _is_taiwan(title + dl_text):
                continue

            # Source URL and movie ID
            href = title_a.get("href", "")
            if href.startswith("/"):
                source_url = _BASE_URL + href.split("&")[0]
            else:
                source_url = href.split("&")[0]
            movie_id_m = re.search(r"movie=(\d+)", href)
            if not movie_id_m:
                continue
            movie_id = movie_id_m.group(1)
            source_id = f"united_cinemas_{venue['branch']}_{movie_id}"

            # Date — from <em>YYYY/MM/DD（曜）公開</em>
            em = h3.select_one("em")
            date_text = em.get_text(strip=True) if em else ""
            start_date = _parse_date(date_text)

            # English title / subtitle
            en_title_span = h3.select("span")
            name_en = en_title_span[0].get_text(strip=True) if en_title_span else None
            if name_en and len(name_en) > 80:
                name_en = None

            raw_desc = dl_text[:500]

            events.append(Event(
                source_name=SOURCE_NAME,
                source_id=source_id,
                source_url=source_url,
                original_language="ja",
                name_ja=title,
                name_en=name_en or None,
                start_date=start_date,
                location_name=venue["location_name"],
                location_address=venue["location_address"],
                location_url=venue["location_url"],
                is_paid=True,
                raw_title=title,
                raw_description=raw_desc,
                organizer=venue["location_name"],
                organizer_type=["commercial_brand"],
                event_form=["screening"],
            ))

        return events
