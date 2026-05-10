"""
Scraper for 台湾光譜 Taiwan Prism (www.taiwanprism.com).

台湾光譜 is an annual 2-day cultural event held in Kyoto (紫明会館) that
showcases Taiwanese culture through talks, live music, and workshops.
It has been held on late August each year since 2025.

URL: https://www.taiwanprism.com
Programs page: https://www.taiwanprism.com/programs

Strategy:
  1. Fetch /programs (Wix site, but data is in SSR HTML — no Playwright needed).
  2. Parse each wixui-repeater__item to extract:
       - Program number + title (from the Wix repeater item text)
       - Date/time (e.g. 2025年8月30日（土）10:00~11:15)
       - Speakers / artists
       - Detail URL (/programs/programN)
  3. Also emit one "parent" event for the whole festival
     (covers both days, venue = 紫明会館 京都).

Source ID format:
  Parent event:  taiwan_prism_YYYY            (e.g. taiwan_prism_2025)
  Program N:     taiwan_prism_YYYY_programN   (e.g. taiwan_prism_2025_program1)

Geographic scope: Kyoto (in scope for All-Japan coverage).

Note on future editions:
  When a new edition is launched (e.g. 台湾光譜in京都2026), the site title
  changes and a new /programs page appears.  The YYYY is detected
  from the page <title> so new editions are picked up automatically.
"""

import logging
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_NAME = "taiwan_prism"
BASE_URL = "https://www.taiwanprism.com"
PROGRAMS_URL = f"{BASE_URL}/programs"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept-Language": "ja,zh-TW,en;q=0.8",
}

# Venue info (stable across editions)
_VENUE_NAME = "紫明会館"
_VENUE_ADDRESS = "京都府京都市北区小山南大野町１"

# Date/time pattern: 2025年8月30日（土）10:00~11:15
#   Also handles: 18:45-20:00 (hyphen instead of ~)
_DATE_TIME_RE = re.compile(
    r"(\d{4})年(\d{1,2})月(\d{1,2})日[（(][月火水木金土日祝][）)]"
    r"(\d{1,2}):(\d{2})[~〜\-ー](\d{1,2}):(\d{2})"
)

# Page title to extract edition year: "台湾光譜in京都2025"
_TITLE_YEAR_RE = re.compile(r"台湾光譜.*?(\d{4})")


def _fetch(url: str) -> Optional[BeautifulSoup]:
    """Fetch a page and return a BeautifulSoup object, or None on failure."""
    try:
        r = requests.get(url, headers=_HEADERS, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as exc:
        logger.warning("taiwan_prism: fetch failed %s: %s", url, exc)
        return None


def _parse_datetime(text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Extract start and end datetime from a date-time string like:
    「2025年8月30日（土）10:00~11:15」
    Returns (start, end) where both are datetime objects or None.
    """
    m = _DATE_TIME_RE.search(text)
    if not m:
        return None, None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    sh, sm = int(m.group(4)), int(m.group(5))
    eh, em = int(m.group(6)), int(m.group(7))
    try:
        start = datetime(year, month, day, sh, sm)
        end = datetime(year, month, day, eh, em)
        return start, end
    except ValueError:
        return None, None


def _parse_programs(soup: BeautifulSoup) -> list[dict]:
    """Parse program cards from /programs page.

    Returns a list of dicts with keys:
      number, title, datetime_text, start, end, speakers, detail_url
    """
    programs = []

    # Each card is a wixui-repeater__item
    cards = soup.select("div.wixui-repeater__item")
    if not cards:
        # Fallback: find by class fragment
        cards = soup.select("[class*='wixui-repeater__item']")

    for card in cards:
        text = card.get_text(separator="\n", strip=True)
        lines = [l for l in text.splitlines() if l.strip()]

        # Skip cards that don't have at least a date pattern
        if not _DATE_TIME_RE.search(text):
            continue

        start, end = _parse_datetime(text)
        if not start:
            continue

        # Program number + title: first non-empty line before the date line
        title_lines = []
        for line in lines:
            if _DATE_TIME_RE.search(line):
                break
            if line not in ("Read More", "続きを読む"):
                title_lines.append(line)
        full_title = "\n".join(title_lines).strip()

        # Extract program number (e.g. "プログラム1")
        prog_num_m = re.match(r"プログラム(\d+)", full_title)
        prog_num = int(prog_num_m.group(1)) if prog_num_m else None

        # Title text: everything after "プログラムN\n"
        title = re.sub(r"^プログラム\d+\s*", "", full_title).strip()
        # Remove surrounding 「」
        title = title.strip("「」")

        # Speakers: lines after the date line, before "Read More"
        after_date = False
        speaker_lines = []
        for line in lines:
            if _DATE_TIME_RE.search(line):
                after_date = True
                continue
            if after_date:
                if line in ("Read More", "続きを読む"):
                    break
                speaker_lines.append(line)
        speakers = "／".join(speaker_lines).strip()
        # Strip null bytes that can appear in scraped text and break Postgres
        speakers = speakers.replace("\x00", "")
        detail_url = (
            f"{BASE_URL}/programs/program{prog_num}"
            if prog_num
            else PROGRAMS_URL
        )

        # Anchor link in card (more reliable than guessing)
        a_tag = card.select_one("a[href*='/programs/program']")
        if a_tag:
            href = a_tag.get("href", "")
            if href.startswith("http"):
                detail_url = href
            elif href.startswith("/"):
                detail_url = BASE_URL + href

        programs.append({
            "number": prog_num,
            "title": title,
            "start": start,
            "end": end,
            "speakers": speakers,
            "detail_url": detail_url,
        })

    return programs


class TaiwanPrismScraper(BaseScraper):
    """Scraper for 台湾光譜 Taiwan Prism annual Kyoto cultural event."""

    source_name = SOURCE_NAME

    def scrape(self) -> list[Event]:
        soup = _fetch(PROGRAMS_URL)
        if soup is None:
            logger.error("taiwan_prism: could not fetch %s", PROGRAMS_URL)
            return []

        # Detect edition year from <title>
        title_tag = soup.find("title")
        page_title_text = title_tag.get_text(strip=True) if title_tag else ""
        year_m = _TITLE_YEAR_RE.search(page_title_text)
        edition_year = int(year_m.group(1)) if year_m else datetime.now().year
        event_title = f"台湾光譜in京都{edition_year}"

        logger.info("taiwan_prism: edition=%d, page_title=%r", edition_year, page_title_text)

        programs = _parse_programs(soup)
        if not programs:
            logger.warning("taiwan_prism: no programs found on %s", PROGRAMS_URL)
            return []

        logger.info("taiwan_prism: found %d programs", len(programs))

        # ----------------------------------------------------------------
        # Parent event: the whole 2-day festival
        # ----------------------------------------------------------------
        all_starts = [p["start"] for p in programs if p["start"]]
        all_ends = [p["end"] for p in programs if p["end"]]
        festival_start = min(all_starts) if all_starts else None
        festival_end = max(all_ends) if all_ends else None

        # Build description from program list
        program_lines = []
        for p in programs:
            num = p["number"] or "?"
            dt_str = p["start"].strftime("%m/%d %H:%M") if p["start"] else ""
            program_lines.append(
                f"プログラム{num}: {p['title']} [{dt_str}] {p['speakers']}"
            )
        description = (
            f"台湾文化を紹介する2日間のスペシャルイベント。"
            f"歴史家、文筆家、歌手、漫画家、美術作家、武術家など日台スペシャリストによるトーク・音楽ライブ・ワークショップ。"
            f"\n\n"
            + "\n".join(program_lines)
        )

        events: list[Event] = []

        parent = Event(
            source_name=SOURCE_NAME,
            source_id=f"taiwan_prism_{edition_year}",
            source_url=BASE_URL,
            original_language="ja",
            name_ja=event_title,
            raw_title=event_title,
            raw_description=description,
            description_ja=description,
            category=["performing_arts", "art", "lecture", "taiwan_japan"],
            start_date=festival_start,
            end_date=festival_end,
            location_name=_VENUE_NAME,
            location_address=_VENUE_ADDRESS,
            organizer="台湾光譜実行委員会",
            organizer_type=["civic_group"],
            event_form=["offline"],
            primary_language="ja",
            has_japanese_support=True,
            official_url=BASE_URL,
            name_ja_locked=True,
        )
        events.append(parent)

        # ----------------------------------------------------------------
        # Resolve parent UUID: look up existing DB record first, so that
        # sub-events can correctly set parent_event_id.
        # On first run the parent may not exist yet — in that case leave
        # parent_event_id=None; subsequent runs will resolve it correctly.
        # ----------------------------------------------------------------
        parent_uuid: Optional[str] = None
        try:
            from database import get_event_id_by_source as _get_parent_uuid
            parent_uuid = _get_parent_uuid(SOURCE_NAME, f"taiwan_prism_{edition_year}")
        except Exception as exc:
            logger.warning("taiwan_prism: could not resolve parent UUID: %s", exc)

        # ----------------------------------------------------------------
        # Sub-events: individual programs
        # ----------------------------------------------------------------
        for p in programs:
            num = p["number"] or "?"
            sub_title = f"台湾光譜{edition_year} プログラム{num}「{p['title']}」"
            sub_desc = f"登壇者: {p['speakers']}" if p["speakers"] else ""

            sub = Event(
                source_name=SOURCE_NAME,
                source_id=f"taiwan_prism_{edition_year}_program{num}",
                source_url=p["detail_url"],
                original_language="ja",
                name_ja=sub_title,
                raw_title=sub_title,
                raw_description=sub_desc,
                description_ja=sub_desc,
                category=["performing_arts", "taiwan_japan"],
                start_date=p["start"],
                end_date=p["end"],
                location_name=_VENUE_NAME,
                location_address=_VENUE_ADDRESS,
                organizer="台湾光譜実行委員会",
                organizer_type=["civic_group"],
                event_form=["offline"],
                primary_language="ja",
                has_japanese_support=True,
                official_url=p["detail_url"],
                parent_event_id=parent_uuid,  # None on first run; resolved on subsequent runs
                name_ja_locked=True,
            )
            events.append(sub)

        logger.info(
            "taiwan_prism: emitting 1 parent + %d sub-events for edition %d",
            len(programs),
            edition_year,
        )
        return events
