"""
Scraper for Taiwan-related TV programs via 番組表Gガイド (bangumi.org).

Strategy:
  1. For each keyword in SEARCH_KEYWORDS:
     a. GET /search/?q=<kw>  — establishes session cookies
     b. GET /fetch_search_content/?q=<kw>&type=tv  — returns HTML program list fragment
     c. Parse li.block items → ebisId, title, genre, schedule string
  2. Deduplicate by ebisId across all keyword searches
  3. For each unique program, fetch /tv_events/{ebisId} for the description text
  4. Parse broadcast date/time from schedule string (e.g. "4月29日 水曜 12:00　テレ東")
  5. source_id: gguide_{ebisId}

robots.txt: User-agent: * Allow: /  (no authentication required)
Rendering: static HTML — no Playwright needed
"""

import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event, dedup_events

logger = logging.getLogger(__name__)

_BASE_URL = "https://bangumi.org"
_SEARCH_URL = _BASE_URL + "/search/?q={kw}"
_FETCH_URL = _BASE_URL + "/fetch_search_content/?q={kw}&type=tv"
_DETAIL_URL = _BASE_URL + "/tv_events/{ebis_id}"

# Gガイド検索キーワード — "台湾ドラマ" は "台湾" のサブセットなので省略
SEARCH_KEYWORDS = ["台湾", "テレサ・テン"]

# Programs that aired more than this many days ago are skipped
LOOKBACK_DAYS = 7

# Max chars from detail page to include in raw_description
_MAX_DETAIL_LEN = 2000

_TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan", "テレサ・テン", "鄧麗君", "Teresa Teng"]


def _is_taiwan_title(title: str) -> bool:
    """Return True if the title contains a Taiwan-related keyword."""
    return any(kw in title for kw in _TAIWAN_KEYWORDS)


def _parse_schedule(schedule_str: str, today: datetime) -> tuple[Optional[datetime], str]:
    """
    Parse schedule strings like '4月29日 水曜 12:00　テレ東' into (datetime, channel).

    Year is inferred: if the resulting date is more than LOOKBACK_DAYS in the past,
    try next year (handles Dec→Jan boundary when upcoming Jan broadcasts appear in Dec).
    Returns (None, channel) when the date cannot be parsed.
    """
    # Match: M月D日 <DOW> HH:MM <channel>
    m = re.search(
        r"(\d{1,2})月(\d{1,2})日\s+\S+?\s+(\d{1,2}):(\d{2})\s*(.+)",
        schedule_str.strip(),
    )
    if not m:
        return None, schedule_str.strip()

    month = int(m.group(1))
    day = int(m.group(2))
    hour = int(m.group(3))
    minute = int(m.group(4))
    channel = m.group(5).strip()

    # Handle hour ≥ 24 (late-night Japanese broadcast convention: 25:00 = 01:00 next day)
    day_offset = 0
    if hour >= 24:
        day_offset = hour // 24
        hour = hour % 24

    year = today.year
    try:
        candidate = datetime(year, month, day, hour, minute) + timedelta(days=day_offset)
    except ValueError:
        return None, channel

    # If candidate is stale by more than LOOKBACK_DAYS, try next year
    cutoff = today - timedelta(days=LOOKBACK_DAYS)
    if candidate < cutoff:
        try:
            candidate = datetime(year + 1, month, day, hour, minute) + timedelta(days=day_offset)
        except ValueError:
            return None, channel

    return candidate, channel


def _genre_to_category(genre: str) -> list[str]:
    """Map Gガイド genre label to project canonical category list."""
    if "ドラマ" in genre:
        return ["performing_arts"]
    if "映画" in genre:
        return ["performing_arts"]
    if "音楽" in genre:
        return ["performing_arts"]
    if "ドキュメンタリー" in genre or "教養" in genre or "報道" in genre:
        return ["report"]
    # バラエティ, スポーツ, and unknown genres
    return ["report"]


def _fetch_detail(session: requests.Session, ebis_id: str) -> str:
    """
    Fetch the program detail page and return cleaned description text.
    Returns empty string on any error.
    """
    url = _DETAIL_URL.format(ebis_id=ebis_id)
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("gguide_tv: detail page failed %s: %s", url, exc)
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    main = soup.find("main")
    if not main:
        return ""

    # Remove script/style noise
    for elem in main.select("script, style, nav"):
        elem.decompose()

    text = main.get_text(separator="\n", strip=True)
    return text[:_MAX_DETAIL_LEN]


class GguideTvScraper(BaseScraper):
    SOURCE_NAME = "gguide_tv"

    def scrape(self) -> list[Event]:
        today = datetime.now()
        cutoff = today - timedelta(days=LOOKBACK_DAYS)

        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})

        seen_ebis_ids: set[str] = set()
        events: list[Event] = []

        for keyword in SEARCH_KEYWORDS:
            kw_encoded = quote(keyword)
            search_url = _SEARCH_URL.format(kw=kw_encoded)
            fetch_url = _FETCH_URL.format(kw=kw_encoded)

            # Step 1: establish session cookie
            try:
                resp1 = session.get(search_url, timeout=15)
                resp1.raise_for_status()
            except Exception as exc:
                logger.warning("gguide_tv: search page failed for '%s': %s", keyword, exc)
                continue

            time.sleep(0.5)

            # Step 2: fetch program list fragment
            try:
                resp2 = session.get(
                    fetch_url,
                    headers={"Referer": search_url},
                    timeout=15,
                )
                resp2.raise_for_status()
            except Exception as exc:
                logger.warning("gguide_tv: fetch_search_content failed for '%s': %s", keyword, exc)
                continue

            soup = BeautifulSoup(resp2.text, "html.parser")
            items = soup.select("ul.list-style-1 li.block")
            logger.info("gguide_tv: '%s' → %d items", keyword, len(items))

            for item in items:
                # Extract ebisId from the data-content JSON attribute
                link_el = item.select_one("a.js-logging[data-content]")
                if link_el is None:
                    continue
                try:
                    data_content = json.loads(link_el.get("data-content", "{}"))
                    ebis_id: str = data_content.get("ebisId", "")
                except (json.JSONDecodeError, AttributeError):
                    continue

                if not ebis_id or ebis_id in seen_ebis_ids:
                    continue

                # Extract genre, title, schedule from <p> tags inside .box-2
                ps = item.select(".box-2 p")
                genre = ps[0].get_text(strip=True) if ps else ""
                raw_title = ps[1].get_text(strip=True) if len(ps) > 1 else ""
                schedule_raw = ps[2].get_text(strip=True) if len(ps) > 2 else ""

                # Remove broadcast accessibility emoji marks (🈑 = repeat, 🈞 = multi-language)
                title_clean = re.sub(r"[\U0001F200-\U0001F2FF🈑🈞🈓]", "", raw_title).strip()

                if not title_clean or not schedule_raw:
                    continue

                # For テレサ・テン keyword: only keep programs where テレサ・テン
                # appears as a primary subject (full name in title), not as a minor guest
                if keyword == "テレサ・テン" and "テレサ・テン" not in title_clean:
                    logger.debug(
                        "gguide_tv: skip '%s' (テレサ・テン not in title)", title_clean
                    )
                    continue

                # Parse broadcast date/time
                start_dt, channel = _parse_schedule(schedule_raw, today)
                if start_dt is None:
                    logger.debug(
                        "gguide_tv: could not parse schedule '%s' for '%s'",
                        schedule_raw,
                        title_clean,
                    )
                    continue

                # Skip stale broadcasts
                if start_dt < cutoff:
                    logger.debug(
                        "gguide_tv: skip stale %s (%s)", title_clean, start_dt.date()
                    )
                    continue

                seen_ebis_ids.add(ebis_id)

                # Fetch detail page for description
                time.sleep(0.3)
                detail_text = _fetch_detail(session, ebis_id)

                # Build raw_description — prepend 開催日時 per BaseScraper convention
                broadcast_date_str = (
                    f"{start_dt.year}年{start_dt.month}月{start_dt.day}日"
                )
                desc_parts = [
                    f"開催日時: {broadcast_date_str}\n",
                    f"放送: {channel}",
                    f"ジャンル: {genre}",
                ]
                if detail_text:
                    desc_parts.append(f"\n{detail_text}")
                raw_description = "\n".join(desc_parts)

                source_url = _DETAIL_URL.format(ebis_id=ebis_id)

                events.append(
                    Event(
                        source_name="gguide_tv",
                        source_id=f"gguide_{ebis_id}",
                        source_url=source_url,
                        original_language="ja",
                        name_ja=title_clean,
                        raw_title=title_clean,
                        raw_description=raw_description,
                        start_date=start_dt,
                        category=_genre_to_category(genre),
                    )
                )

                time.sleep(0.3)

        result = dedup_events(events)
        logger.info("gguide_tv: %d events after dedup", len(result))
        return result
