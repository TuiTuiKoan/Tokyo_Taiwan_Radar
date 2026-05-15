"""Scraper for ＮＰＯ松本シネマセレクト (Matsumoto Cinema Select)

Source URL: https://teket.jp/1841/{event_id}
Platform  : teket.jp — static HTML, no JS required
Source name: matsumoto_cinema_select
Source ID : matsumoto_cinema_select_{teket_event_id}

Strategy:
  1. Fetch https://teket.jp/sitemap.xml (1 req)
  2. Extract all /1841/{id} URLs, sort by ID descending
  3. Process top MAX_EVENTS_TO_CHECK (=30) event pages
  4. From each page:
     a. Parse JSON-LD for name/dates/image
     b. Extract venue from page title (after "|")
     c. Extract address from OG description bracket
     d. Get full text (script/style removed) for Taiwan filter + raw_description
  5. Return Taiwan-relevant events only

Taiwan keyword filter:
  Applied to full page text (not JSON-LD description which is too short).
  frozenset(['台湾', '台灣'])

Notes on teket.jp:
  - The group API (/api/events?group_id=1841) returns ALL platform events
    (34,000+), not filtered by group. Use sitemap.xml as the only reliable
    group-scoped enumeration method.
  - JSON-LD location.name is always "その他のホール" (useless). Use page title
    suffix after "|" for the actual venue name.
  - Sitemap fetch takes 15–20 s; timeout=30 is required.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event
from movie_title_lookup import lookup_movie_titles

logger = logging.getLogger(__name__)

SOURCE_NAME = "matsumoto_cinema_select"

_SITEMAP_URL = "https://teket.jp/sitemap.xml"
_BASE_URL = "https://teket.jp"
_GROUP_ID = "1841"
MAX_EVENTS_TO_CHECK = 30

_TAIWAN_KWS: frozenset[str] = frozenset(["台湾", "台灣"])

_ORGANIZER = "ＮＰＯ松本シネマセレクト"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

# Pattern to extract numeric event ID from teket URL like /1841/69526
_EVENT_ID_RE = re.compile(rf"teket\.jp/{_GROUP_ID}/(\d+)")

# OG description pattern: contains bracketed venue+address then bracketed date
# e.g. "[会場名 住所][日時 ...]" — extract what's inside the first bracket
_BRACKET_RE = re.compile(r"\[([^\]]+)\]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_taiwan_relevant(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KWS)


def _parse_ld_date(date_str: str) -> Optional[datetime]:
    """Parse teket JSON-LD date string to UTC midnight datetime.

    Handles formats like:
      '2026/06/07'   → datetime(2026, 6, 7, tzinfo=utc)
      '2026/6/7(日)' → same (strips day-of-week suffix)
      '2026-06-07'   → same

    Returns None on any parse failure.
    """
    if not date_str:
        return None
    try:
        # Normalise separators and strip day-of-week parentheticals
        s = date_str.strip().replace("-", "/")
        # Remove (曜) suffix on day part e.g. "7(日)" → "7"
        s = re.sub(r"\([^)]*\)", "", s)
        parts = s.split("/")
        if len(parts) == 3:
            y, m, d = int(parts[0].strip()), int(parts[1].strip()), int(parts[2].strip())
            return datetime(y, m, d, tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass
    return None


def _extract_venue_from_title(title: str) -> Optional[str]:
    """Extract venue name from page title suffix after '|'.

    e.g. '功夫（カンフー）| まつもと市民芸術館 2階小ホール | teket'
    → 'まつもと市民芸術館 2階小ホール'
    """
    parts = [p.strip() for p in title.split("|")]
    # Expect: [event_name, venue_name, "teket"]
    if len(parts) >= 2:
        # Skip the last segment if it's the platform name
        for candidate in parts[1:]:
            if candidate.lower() not in ("teket", ""):
                return candidate
    return None


def _extract_address_from_og_desc(og_desc: str) -> Optional[str]:
    """Extract address from the first bracketed segment in OG description.

    teket OG description format: "[venue_name address][日時 ...]..."
    The first bracket typically contains "venue_name address".
    We return the text after the first space (dropping the venue name prefix).
    Falls back to the full first-bracket content if no space found.
    """
    if not og_desc:
        return None
    matches = _BRACKET_RE.findall(og_desc)
    if not matches:
        return None
    first = matches[0].strip()
    # Heuristic: address typically contains prefecture characters like 県/都/道/府
    # or specific address patterns. Return the whole first-bracket content.
    return first if first else None


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


class MatsumotoCinemaSelectScraper(BaseScraper):
    """Scraper for ＮＰＯ松本シネマセレクト events on teket.jp (group 1841)."""

    def scrape(self) -> list[Event]:
        event_ids = self._fetch_event_ids()
        if not event_ids:
            logger.warning("%s: no event IDs found from sitemap", SOURCE_NAME)
            return []

        events: list[Event] = []
        for eid in event_ids:
            try:
                event = self._scrape_event(eid)
                if event:
                    events.append(event)
            except Exception as exc:
                logger.warning("%s: failed to scrape event %s: %s", SOURCE_NAME, eid, exc)
            time.sleep(0.5)

        logger.info("%s: %d Taiwan-relevant event(s) found", SOURCE_NAME, len(events))
        return events

    # ------------------------------------------------------------------

    def _fetch_event_ids(self) -> list[str]:
        """Fetch sitemap.xml and return group-1841 event IDs sorted by ID desc."""
        try:
            resp = requests.get(_SITEMAP_URL, headers=_HEADERS, timeout=30)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("%s: sitemap fetch failed: %s", SOURCE_NAME, exc)
            return []

        ids: list[int] = []
        for m in _EVENT_ID_RE.finditer(resp.text):
            try:
                ids.append(int(m.group(1)))
            except ValueError:
                pass

        # Deduplicate and sort by ID descending (newest first)
        unique_ids = sorted(set(ids), reverse=True)
        top_ids = unique_ids[:MAX_EVENTS_TO_CHECK]
        logger.info(
            "%s: sitemap → %d group-1841 URL(s), checking top %d",
            SOURCE_NAME, len(unique_ids), len(top_ids),
        )
        return [str(i) for i in top_ids]

    def _scrape_event(self, event_id: str) -> Optional[Event]:
        url = f"{_BASE_URL}/{_GROUP_ID}/{event_id}"

        try:
            resp = requests.get(url, headers=_HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.debug("%s: fetch failed %s: %s", SOURCE_NAME, url, exc)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # ---- Full page text for Taiwan filter + raw_description ----
        # Remove script/style before extracting text
        for tag in soup(["script", "style"]):
            tag.decompose()
        full_text = soup.get_text(" ", strip=True)

        if not _is_taiwan_relevant(full_text):
            return None

        # ---- JSON-LD ----
        ld_data: dict = {}
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict) and data.get("@type") == "Event":
                    ld_data = data
                    break
            except (json.JSONDecodeError, AttributeError):
                pass

        raw_title: str = ld_data.get("name", "").strip()
        if not raw_title:
            # Fallback to OG title
            og_title = soup.find("meta", property="og:title")
            raw_title = (og_title.get("content", "") if og_title else "").strip()

        if not raw_title:
            logger.debug("%s: no title for event %s, skipping", SOURCE_NAME, event_id)
            return None

        start_date = _parse_ld_date(ld_data.get("startDate"))
        end_date = _parse_ld_date(ld_data.get("endDate"))
        image_url: Optional[str] = ld_data.get("image")

        # ---- Venue from page title ----
        title_tag = soup.find("title")
        page_title = title_tag.get_text(strip=True) if title_tag else ""
        location_name = _extract_venue_from_title(page_title)

        # ---- Address from OG description ----
        og_desc_tag = soup.find("meta", property="og:description")
        og_desc = og_desc_tag.get("content", "") if og_desc_tag else ""
        raw_address = _extract_address_from_og_desc(og_desc)

        # ---- Movie title lookup ----
        name_zh, name_en, official_url = lookup_movie_titles(raw_title)

        return Event(
            source_name=SOURCE_NAME,
            source_id=f"{SOURCE_NAME}_{event_id}",
            source_url=url,
            original_language="ja",
            name_ja=raw_title,
            name_zh=name_zh,
            name_en=name_en,
            raw_title=raw_title,
            raw_description=full_text[:3000],
            category=["movie"],
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=raw_address,
            location_url=official_url,
            organizer=_ORGANIZER,
            image_url=image_url,
            is_paid=True,
        )
