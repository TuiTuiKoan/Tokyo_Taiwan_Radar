"""Scraper for 東京大学東洋文化研究所 (Tobunken) seminar announcements.

Source URL : https://www.ioc.u-tokyo.ac.jp/seminar/index.php
Detail URL : https://www.ioc.u-tokyo.ac.jp/news/news.php?id={id_param}
Platform   : Static HTML — DL/DT/DD listing, no pagination (all 1500+ entries in one page)
Source name: tobunken
Source ID  : tobunken_{id_param}

Relevance filter: Topics related to Taiwan, maritime history (海洋史), exchange history
(交流史), material history (物質史), and adjacent maritime/East-Asian themes.
Taiwan is NOT always the primary keyword — that is intentional.
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "tobunken"
LISTING_URL = "https://www.ioc.u-tokyo.ac.jp/seminar/index.php"
BASE_URL = "https://www.ioc.u-tokyo.ac.jp"
INSTITUTE_ADDRESS = "東京都文京区本郷7-3-1 東京大学東洋文化研究所"

LOOKBACK_DAYS = 365  # academic seminars often announced months ahead; low yield (~3–5/year)
_JST = timezone(timedelta(hours=9))
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Relevance keywords — match in event title (listing page)
# ---------------------------------------------------------------------------
_TAIWAN_KEYWORDS = [
    "台湾", "Taiwan", "臺灣", "台湾史", "台湾海峡",
]
_MARITIME_KEYWORDS = [
    "海洋史", "交流史", "物質史",
    "海域", "南シナ海", "東シナ海", "海上", "海峡",
    "東南アジア", "琉球",
]
_ALL_KEYWORDS = _TAIWAN_KEYWORDS + _MARITIME_KEYWORDS


def _is_relevant(title: str) -> bool:
    """Return True if the title contains at least one relevance keyword."""
    return any(kw in title for kw in _ALL_KEYWORDS)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------
def _parse_listing_date(date_str: str) -> datetime | None:
    """Parse listing DT text like '2026.04.20' or '2026.03.26 - 2026.03.27'.
    Returns JST datetime for the first (start) date."""
    m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", date_str.strip())
    if not m:
        return None
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=_JST)


def _parse_detail_date(box: BeautifulSoup) -> datetime | None:
    """Extract start date from detail page #contentsbox.

    Tries, in order:
    1. '当日期間：YYYYMMDD' in footer text (most reliable)
    2. '日時：' or '場所：' sibling text in <p><strong> block
    """
    text = box.get_text(separator="\n", strip=True)

    # Strategy 1: 当日期間：YYYYMMDD
    m = re.search(r"当日期間[：:]\s*(\d{4})(\d{2})(\d{2})", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=_JST)
        except ValueError:
            pass

    # Strategy 2: 日時：YYYY年M月DD日
    m = re.search(
        r"日時[：:]\s*(?:(?:全角数字|２０\d{2})|(\d{4}))?"
        r"(?:(\d{4}))?年(\d{1,2})月(\d{1,2})日",
        text,
    )
    if m:
        # Groups can shift depending on alternation; parse directly
        pass

    # Simpler fallback: just find YYYY年M月DD日 pattern anywhere near 日時
    m = re.search(r"日時[：:][^\n]*?(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if not m:
        # Try full-width year digit
        m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        try:
            yr, mo, dy = int(m.group(-3)), int(m.group(-2)), int(m.group(-1))
            return datetime(yr, mo, dy, tzinfo=_JST)
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# Venue helpers
# ---------------------------------------------------------------------------
def _extract_venue(box: BeautifulSoup) -> tuple[str | None, str | None]:
    """Return (location_name, location_address) from detail page."""
    for strong in box.find_all("strong"):
        label = strong.get_text(strip=True)
        if re.match(r"(?:場所|会場)[：:]", label):
            p = strong.parent
            if p and p.name == "p":
                full = p.get_text(separator="\n", strip=True)
                # Remove the label itself
                venue = re.sub(r"^(?:場所|会場)[：:]\s*", "", full).split("\n")[0].strip()
                if not venue:
                    continue
                # Strip online suffix — handles: オンライン, Zoom, Teams, Google Meet, hybrid「& Zoom」
                venue = re.split(
                    r"(?:およびオンライン|及びオンライン|オンラインのみ"
                    r"|\s*[&＆]\s*(?:Zoom|Teams|Google Meet|Google\s*Meet))",
                    venue,
                )[0].strip()
                # Strip orphaned open bracket left by the split (e.g. 「会議室（ハイブリッド」→「会議室」)
                venue = re.sub(r"[（(]\s*$", "", venue).strip()
                if not venue:
                    return "オンライン", None

                # location_address: hardcode institute address when venue is there
                if "東洋文化研究所" in venue:
                    return venue, INSTITUTE_ADDRESS
                return venue, None
    return None, None


# ---------------------------------------------------------------------------
# Scraper class
# ---------------------------------------------------------------------------
class TobunkenScraper(BaseScraper):
    """Scrapes 東文研 seminar announcements filtered by Taiwan/maritime keywords."""

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        try:
            resp = requests.get(
                LISTING_URL,
                timeout=20,
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("tobunken: listing fetch failed: %s", exc)
            return []

        soup = BeautifulSoup(resp.content, "html.parser")
        dts = soup.find_all("dt")
        dds = soup.find_all("dd")

        if len(dts) != len(dds):
            logger.warning(
                "tobunken: DT/DD count mismatch: %d vs %d", len(dts), len(dds)
            )

        cutoff = datetime.now(_JST) - timedelta(days=LOOKBACK_DAYS)
        candidates: list[tuple[datetime, str, str]] = []  # (date, title, detail_url)

        for dt, dd in zip(dts, dds):
            date_str = dt.get_text(strip=True)
            event_date = _parse_listing_date(date_str)
            if not event_date:
                continue
            if event_date < cutoff:
                continue

            title = dd.get_text(separator=" ", strip=True)
            # Strip trailing (登録日：...) annotation that appears in listing
            title = re.sub(r"[（(]登録日[：:][^）)]+[）)]", "", title).strip()

            if not _is_relevant(title):
                continue

            a = dd.find("a", href=True)
            if not a:
                continue
            href = a["href"].strip()
            if not href.startswith("http"):
                href = BASE_URL + href

            candidates.append((event_date, title, href))

        logger.info("tobunken: %d candidates after title filter", len(candidates))
        events: list[Event] = []

        for event_date, listing_title, detail_url in candidates:
            try:
                time.sleep(0.3)  # polite crawl
                dresp = requests.get(
                    detail_url,
                    timeout=20,
                    headers={"User-Agent": _USER_AGENT},
                )
                dresp.raise_for_status()
            except Exception as exc:
                logger.warning("tobunken: detail fetch failed %s: %s", detail_url, exc)
                continue

            dsoup = BeautifulSoup(dresp.content, "html.parser")
            box = dsoup.find("div", id="contentsbox")
            if not box:
                logger.warning("tobunken: no #contentsbox at %s", detail_url)
                continue

            # Title from h2 (preferred) — listing title as fallback
            h2 = box.find("h2")
            title = (h2.get_text(strip=True) if h2 else listing_title)

            # Date — try detail page first (more complete), fall back to listing date
            start_date = _parse_detail_date(box) or event_date

            location_name, location_address = _extract_venue(box)

            # Full text for raw_description
            body_text = box.get_text(separator="\n", strip=True)
            # Strip footer metadata lines
            body_text = re.split(r"登録種別[：:]", body_text)[0].strip()

            date_header = (
                f"開催日時: {start_date.year}年"
                f"{start_date.month}月{start_date.day}日"
            )
            raw_description = f"{date_header}\n\n{body_text}"

            # source_id from URL query param
            id_m = re.search(r"[?&]id=([A-Za-z0-9]+)", detail_url)
            source_id = f"tobunken_{id_m.group(1)}" if id_m else f"tobunken_{hash(detail_url)}"

            events.append(
                Event(
                    source_name=SOURCE_NAME,
                    source_id=source_id,
                    source_url=detail_url,
                    original_language="ja",
                    name_ja=title,
                    raw_title=title,
                    raw_description=raw_description,
                    category=["academic", "taiwan_japan"],
                    start_date=start_date,
                    location_name=location_name,
                    location_address=location_address,
                    is_paid=False,
                )
            )

        logger.info("tobunken: scraped %d events", len(events))
        return events
