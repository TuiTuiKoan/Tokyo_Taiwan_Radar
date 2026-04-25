"""
Scraper for アジア経済研究所 (IDE-JETRO) — ide.go.jp

アジア経済研究所 hosts regular lectures and symposia. About 1 in every
2–3 months concerns Taiwan (geopolitics, economy, academia).

Strategy
--------
1. Fetch one static HTML listing page: /Japanese/Event/Seminar.html
   (The /Sympo/ page mirrors the same data — overlap is 100%.)
2. Find all <li> containing <span class="date"> + <a href=".../YYMMDD.html">
3. Keep only items whose title contains "台湾"
4. Apply a lookback window: only events whose start_date is within
   LOOKBACK_DAYS in the past, or any future date.
5. Fetch each matching detail page for og:title and body description.
6. Build source_id = "ide-jetro_{YYMMDD}" from the href path.

Date formats on the listing page
---------------------------------
  Single : 2025.09.26 (金曜)
  Range  : 2025.11.25 (火曜)〜2026.03.13 (金曜) → start + end date
"""

import re
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

SOURCE_NAME = "ide_jetro"
BASE_URL = "https://www.ide.go.jp"
LISTING_URL = f"{BASE_URL}/Japanese/Event/Seminar.html"
HEADERS = {"User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyo-taiwan-radar.vercel.app)"}
LOOKBACK_DAYS = 180
REQUEST_DELAY = 1.0  # seconds between detail-page fetches

_HREF_RE = re.compile(r"/Japanese/Event/(?:Seminar|Sympo)/(\d{6})\.html")
_DATE_DOTTED_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})")


def _parse_date_dotted(s: str) -> Optional[datetime]:
    """Parse first 'YYYY.MM.DD' occurrence in string to datetime."""
    m = _DATE_DOTTED_RE.search(s)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _parse_dates(date_text: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse span.date text into (start_date, end_date).

    Handles:
      '2025.09.26 (金曜)'              → (2025-09-26, None)
      '2025.11.25 (火曜)〜2026.03.13'  → (2025-11-25, 2026-03-13)
    """
    # Find all dotted dates in order
    all_dates = _DATE_DOTTED_RE.findall(date_text)
    if len(all_dates) >= 2:
        start = _parse_date_dotted(date_text)
        # Find the second occurrence
        second_str = f"{all_dates[1][0]}.{all_dates[1][1]}.{all_dates[1][2]}"
        end = _parse_date_dotted(second_str)
        return start, end
    return _parse_date_dotted(date_text), None


def _fetch_detail(url: str) -> dict:
    """
    Fetch a detail page and return {title, description}.
    Returns an empty dict on any network / parse error.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Detail fetch failed %s: %s", url, exc)
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")

    # og:title gives the complete, clean title
    og_title_tag = soup.find("meta", {"property": "og:title"})
    title = og_title_tag.get("content", "") if og_title_tag else ""
    # Strip " - アジア経済研究所" site name suffix
    title = re.sub(r"\s*[-－]\s*アジア経済研究所.*$", "", title).strip()

    # Extract a description snippet from the main content area
    main = soup.find("div", id="maincolumn") or soup.find(
        "div", class_=re.compile(r"category-main|main-content")
    )
    description = ""
    if main:
        for el in main.find_all(["p"]):
            text = el.get_text(" ", strip=True)
            # Skip short labels and typical heading-like lines
            if len(text) > 60 and not re.match(
                r"^\s*(開催|日時|場所|講師|申込|参加|定員|受講|締切)", text
            ):
                description = text[:800]
                break

    return {"title": title, "description": description}


class IdeJetroScraper(BaseScraper):
    """Scraper for アジア経済研究所 (JETRO-IDE) academic lectures about Taiwan."""

    def scrape(self) -> list[Event]:
        cutoff = datetime.now() - timedelta(days=LOOKBACK_DAYS)
        events: list[Event] = []
        seen_ids: set[str] = set()

        try:
            resp = requests.get(LISTING_URL, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Failed to fetch IDE-JETRO listing: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        for li in soup.find_all("li"):
            span = li.find("span", class_="date")
            a = li.find("a", href=True)
            if not span or not a:
                continue

            href = a["href"]
            m = _HREF_RE.search(href)
            if not m:
                continue

            yymmdd = m.group(1)  # e.g. "250926"
            source_id = f"ide-jetro_{yymmdd}"

            if source_id in seen_ids:
                continue

            title_text = a.get_text(" ", strip=True)

            # Filter: must mention 台湾
            if "台湾" not in title_text:
                continue

            # Parse dates from span.date
            date_text = span.get_text(" ", strip=True)
            start_date, end_date = _parse_dates(date_text)

            # Lookback filter: skip events older than LOOKBACK_DAYS
            if start_date and start_date < cutoff:
                logger.debug("Skipping old event %s (%s)", source_id, start_date.date())
                continue

            detail_url = BASE_URL + href
            time.sleep(REQUEST_DELAY)
            detail = _fetch_detail(detail_url)

            name_ja = detail.get("title") or title_text

            # Build raw_description with date prepend per scraper convention
            if start_date:
                date_prefix = (
                    f"開催日時: {start_date.year}年{start_date.month}月{start_date.day}日\n\n"
                )
            else:
                date_prefix = f"開催日時: {date_text}\n\n"

            raw_desc_body = detail.get("description") or title_text
            raw_description = date_prefix + raw_desc_body

            # Members-only events (賛助会限定) — include but flag as paid
            is_paid: Optional[bool] = None
            if "賛助会限定" in title_text:
                is_paid = True

            location_name: Optional[str] = None
            if "オンライン" in title_text or "オンライン" in name_ja:
                location_name = "オンライン"

            seen_ids.add(source_id)
            events.append(
                Event(
                    source_name=SOURCE_NAME,
                    source_id=source_id,
                    source_url=detail_url,
                    original_language="ja",
                    name_ja=name_ja,
                    category=["lecture", "academic"],
                    start_date=start_date,
                    end_date=end_date,
                    location_name=location_name,
                    raw_title=title_text,
                    raw_description=raw_description,
                    is_paid=is_paid,
                )
            )
            logger.info("Found: %s  %s", source_id, start_date)

        logger.info("ide_jetro: %d Taiwan events found", len(events))
        return events
