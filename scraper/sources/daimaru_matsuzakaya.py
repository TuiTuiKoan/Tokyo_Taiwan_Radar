"""
Scraper for 大丸・松坂屋 催事スケジュール (Taiwan-themed events).

Both brands share the same React/Vite SPA but expose a JSON API at:
  https://www.daimaru.co.jp/spa_assets/events/{slug}.json
  https://www.matsuzakaya.co.jp/spa_assets/events/{slug}.json

No Playwright required — requests-only.

JSON structure (confirmed 2026-04-28):
  [ { "largeEventHallName": "…",
      "eventHalls": [
        { "eventHallName": "11階 催事場",
          "events": [
            { "id": 1091,
              "eventName": "〈洪瑞珍〉台湾サンドイッチ",
              "eventStartDate": "202405220000",
              "eventEndDate":   "202406041700",
              "displayDate":    "5月22日(水)→6月4日(火)",
              "eventUrl":       "https://www.daimaru.co.jp/tokyo/…/",
              "comment1":       "最終日は17時閉場",
              "comment2":       "" }
          ]
        }
      ]
    }, … ]

source_id = daimaru_matsuzakaya_{slug}_{event_id}
  slug: store slug (e.g. "tokyo", "umedamise", "nagoya")
  event_id: JSON "id" field (integer, stable)

Taiwan events in all-time history (2026-04-28):
  daimaru/tokyo: 〈グランドカステラ〉台湾カステラ (2022), 〈洪瑞珍〉台湾サンドイッチ (2024)
  daimaru/umedamise: 〈台湾カステラ米米〉 (2021, 2022)
  No current events — all past.  0-event dry-runs are expected behaviour.

Blocked (403, not reachable even via Playwright):
  daimaru/fukuoka, matsuzakaya/takatsuki
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional

import requests

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_NAME = "daimaru_matsuzakaya"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*;q=0.9",
    "Accept-Language": "ja,en;q=0.9",
}
_DELAY = 0.3  # seconds between store fetches

# Taiwan relevance: eventName OR comment1/comment2 must match
_TAIWAN_RE = re.compile(r"台湾|台灣|Taiwan|taiwan|🇹🇼", re.IGNORECASE)

# Store map: (brand, slug, json_url, event_page_url, location_address)
_STORES = [
    # daimaru
    ("daimaru", "tokyo",        "https://www.daimaru.co.jp/spa_assets/events/tokyo.json",          "https://www.daimaru.co.jp/tokyo/event/",          "東京都千代田区丸の内1-9-1 大丸東京店"),
    ("daimaru", "shinsaibashi", "https://www.daimaru.co.jp/spa_assets/events/shinsaibashi.json",   "https://www.daimaru.co.jp/shinsaibashi/event/",   "大阪府大阪市中央区心斎橋筋1-7-1 大丸心斎橋店"),
    ("daimaru", "umedamise",    "https://www.daimaru.co.jp/spa_assets/events/umedamise.json",      "https://www.daimaru.co.jp/umedamise/event/",      "大阪府大阪市北区梅田3-1-1 大丸梅田店"),
    ("daimaru", "kobe",         "https://www.daimaru.co.jp/spa_assets/events/kobe.json",           "https://www.daimaru.co.jp/kobe/event/",           "兵庫県神戸市中央区明石町40 大丸神戸店"),
    ("daimaru", "kyoto",        "https://www.daimaru.co.jp/spa_assets/events/kyoto.json",          "https://www.daimaru.co.jp/kyoto/event/",          "京都府京都市下京区四条通高倉西入立売西町79 大丸京都店"),
    ("daimaru", "sapporo",      "https://www.daimaru.co.jp/spa_assets/events/sapporo.json",        "https://www.daimaru.co.jp/sapporo/event/",        "北海道札幌市中央区大通西4 大丸札幌店"),
    ("daimaru", "shimonoseki",  "https://www.daimaru.co.jp/spa_assets/events/shimonoseki.json",    "https://www.daimaru.co.jp/shimonoseki/event/",    "山口県下関市竹崎町4-4-10 大丸下関店"),
    # matsuzakaya
    ("matsuzakaya", "nagoya",   "https://www.matsuzakaya.co.jp/spa_assets/events/nagoya.json",     "https://www.matsuzakaya.co.jp/nagoya/event/",     "愛知県名古屋市中区栄3-16-1 松坂屋名古屋店"),
    ("matsuzakaya", "ueno",     "https://www.matsuzakaya.co.jp/spa_assets/events/ueno.json",       "https://www.matsuzakaya.co.jp/ueno/event/",       "東京都台東区上野3-29-5 松坂屋上野店"),
    ("matsuzakaya", "shizuoka", "https://www.matsuzakaya.co.jp/spa_assets/events/shizuoka.json",   "https://www.matsuzakaya.co.jp/shizuoka/event/",   "静岡県静岡市葵区呉服町1-7 松坂屋静岡店"),
    ("matsuzakaya", "shimonoseki", "https://www.matsuzakaya.co.jp/spa_assets/events/shimonoseki.json", "https://www.matsuzakaya.co.jp/shimonoseki/event/", "山口県下関市竹崎町4-4-10 松坂屋下関店"),
]

# Friendly store names for location_name
_STORE_NAMES = {
    ("daimaru",     "tokyo"):        "大丸東京店",
    ("daimaru",     "shinsaibashi"): "大丸心斎橋店",
    ("daimaru",     "umedamise"):    "大丸梅田店",
    ("daimaru",     "kobe"):         "大丸神戸店",
    ("daimaru",     "kyoto"):        "大丸京都店",
    ("daimaru",     "sapporo"):      "大丸札幌店",
    ("daimaru",     "shimonoseki"):  "大丸下関店",
    ("matsuzakaya", "nagoya"):       "松坂屋名古屋店",
    ("matsuzakaya", "ueno"):         "松坂屋上野店",
    ("matsuzakaya", "shizuoka"):     "松坂屋静岡店",
    ("matsuzakaya", "shimonoseki"):  "松坂屋下関店",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse 'YYYYMMDDHHII' → datetime, or None."""
    if not date_str or len(date_str) < 8:
        return None
    try:
        return datetime.strptime(date_str[:8], "%Y%m%d")
    except ValueError:
        return None


def _is_taiwan(ev: dict) -> bool:
    text = (
        (ev.get("eventName") or "")
        + (ev.get("comment1") or "")
        + (ev.get("comment2") or "")
    )
    return bool(_TAIWAN_RE.search(text))


def _build_source_id(slug: str, event_id: int) -> str:
    return f"daimaru_matsuzakaya_{slug}_{event_id}"


def _build_raw_description(ev: dict, hall_name: str) -> str:
    start = _parse_date(ev.get("eventStartDate"))
    end = _parse_date(ev.get("eventEndDate"))
    date_line = ""
    if start:
        date_line = f"開催日時: {start.year}年{start.month}月{start.day}日"
        if end and end != start:
            date_line += f"〜{end.year}年{end.month}月{end.day}日"
    parts = [date_line] if date_line else []
    if hall_name:
        parts.append(f"会場: {hall_name}")
    if ev.get("comment1"):
        parts.append(ev["comment1"])
    if ev.get("comment2"):
        parts.append(ev["comment2"])
    if ev.get("displayDate"):
        parts.append(f"期間表示: {ev['displayDate']}")
    return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class DaimaruMatsuzakayaScraper(BaseScraper):
    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        session = requests.Session()
        session.headers.update(_HEADERS)

        for brand, slug, json_url, page_url, address in _STORES:
            time.sleep(_DELAY)
            store_name = _STORE_NAMES[(brand, slug)]
            try:
                r = session.get(json_url, headers={"Referer": page_url}, timeout=15)
                r.raise_for_status()
                data = r.json()
            except Exception as exc:
                logger.warning("Failed to fetch %s/%s: %s", brand, slug, exc)
                continue

            store_events = self._parse_store(data, slug, store_name, address, page_url)
            logger.info("%s/%s: %d Taiwan events found", brand, slug, len(store_events))
            events.extend(store_events)

        logger.info("DaimaruMatsuzakayaScraper: total %d Taiwan events", len(events))
        return events

    def _parse_store(
        self,
        data: list,
        slug: str,
        store_name: str,
        address: str,
        page_url: str,
    ) -> list[Event]:
        events: list[Event] = []
        for hall_group in data:
            for hall in hall_group.get("eventHalls", []):
                hall_name = hall.get("eventHallName", "")
                full_hall = f"{store_name} {hall_name}".strip()
                for ev in hall.get("events", []):
                    if not _is_taiwan(ev):
                        continue
                    event = self._make_event(ev, slug, store_name, full_hall, address, page_url)
                    if event:
                        events.append(event)
        return events

    def _make_event(
        self,
        ev: dict,
        slug: str,
        store_name: str,
        hall_name: str,
        address: str,
        page_url: str,
    ) -> Optional[Event]:
        event_id = ev.get("id")
        if event_id is None:
            return None

        title = (ev.get("eventName") or "").strip()
        if not title:
            return None

        start_date = _parse_date(ev.get("eventStartDate"))
        end_date = _parse_date(ev.get("eventEndDate"))
        if start_date is None:
            logger.debug("Skipping event %s: no start_date", event_id)
            return None

        source_url = (ev.get("eventUrl") or "").strip() or page_url
        raw_desc = _build_raw_description(ev, hall_name)

        return Event(
            source_name=SOURCE_NAME,
            source_id=_build_source_id(slug, event_id),
            source_url=source_url,
            original_language="ja",
            raw_title=title,
            raw_description=raw_desc,
            name_ja=title,
            start_date=start_date,
            end_date=end_date,
            location_name=hall_name,
            location_address=address,
            category=["lifestyle_food"],
            is_paid=None,
            is_active=True,
        )
