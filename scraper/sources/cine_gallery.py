"""
Scraper for シネ・ギャラリー (Cine Gallery), Shizuoka.

Strategy:
  1. Fetch https://www.cine-gallery.jp (static HTML, requests + BeautifulSoup)
  2. Parse article.article-entry cards; extract URL from div.desc h2 a[href]
     (NOT a.blog-img which points to the same URL for all cards)
  3. Fetch each detail page for raw_description
  4. Taiwan filter: raw_title or detail text contains 台湾/台灣/Taiwan keywords
  5. start_date: extracted from raw_title via regex YYYY/M/D → UTC datetime
  6. source_id: cine_gallery_{slug} from cinema/YYYY/event/{slug}/
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from movie_title_lookup import lookup_movie_titles

logger = logging.getLogger(__name__)

BASE_URL = "https://www.cine-gallery.jp"

LOCATION_NAME = "静岡シネ・ギャラリー"
LOCATION_ADDRESS = "静岡県静岡市葵区御幸町11-14 サールナートホール3階"
LOCATION_PREFECTURES = ["静岡県"]

TAIWAN_KEYWORDS = {"台湾", "台灣", "Taiwan", "taiwan"}

_DATE_RE = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")
_SLUG_RE = re.compile(r"cinema/\d+/event/([^/]+)/")
_DATE_PREFIX_RE = re.compile(r"^\d{4}/\d{1,2}/\d{1,2}[（(][月火水木金土日][）)]\s*")


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _parse_date(text: str) -> Optional[datetime]:
    """Extract first YYYY/M/D from text and return as UTC datetime."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(y, mo, d, tzinfo=timezone.utc)
    except ValueError:
        return None


def _extract_slug(url: str) -> Optional[str]:
    """Extract event slug from URL like cinema/2026/event/physisnohamon/..."""
    m = _SLUG_RE.search(url)
    return m.group(1) if m else None


def _build_absolute_url(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return BASE_URL + href
    return BASE_URL + "/" + href


class CineGalleryScraper(BaseScraper):
    """Scrapes Taiwan-related events at 静岡シネ・ギャラリー."""

    SOURCE_NAME = "cine_gallery"
    source_name = "cine_gallery"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })

    def _get(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as exc:
            logger.warning("GET %s failed: %s", url, exc)
            return None

    def _fetch_detail_text(self, url: str) -> str:
        """Fetch detail page and return plain text (up to 4000 chars)."""
        soup = self._get(url)
        if not soup:
            return ""
        body = soup.find("body")
        if body:
            return body.get_text(" ", strip=True)[:4000]
        return ""

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        seen_ids: set[str] = set()

        soup = self._get(BASE_URL)
        if not soup:
            logger.error("Failed to fetch listing page: %s", BASE_URL)
            return events

        cards = soup.select("article.article-entry")
        logger.info("cine_gallery: found %d cards on listing page", len(cards))

        for card in cards:
            try:
                # Use div.desc h2 a for URL and title (a.blog-img points to same URL for all)
                link_el = card.select_one("div.desc h2 a")
                if not link_el:
                    continue

                href = link_el.get("href", "").strip()
                if not href:
                    continue

                source_url = _build_absolute_url(href)
                slug = _extract_slug(href)
                if not slug:
                    logger.debug("cine_gallery: could not extract slug from href: %s", href)
                    continue

                source_id = f"cine_gallery_{slug}"
                if source_id in seen_ids:
                    continue

                raw_title = link_el.get_text(strip=True)
                if not raw_title:
                    continue

                # Parse start_date from raw_title (e.g. "2026/5/23（土）...")
                start_date = _parse_date(raw_title)
                if not start_date:
                    logger.debug("cine_gallery: no date in title: %s", raw_title)
                    continue

                # Fetch detail page
                time.sleep(0.5)
                detail_text = self._fetch_detail_text(source_url)

                # Taiwan keyword filter
                combined = raw_title + " " + detail_text
                if not _is_taiwan(combined):
                    logger.debug("cine_gallery: skipping non-Taiwan event: %s", raw_title)
                    continue

                # Build raw_description with date header
                date_header = (
                    f"開催日時: {start_date.year}年{start_date.month}月{start_date.day}日"
                )
                raw_description = f"{date_header}\n\n{detail_text}".replace("\x00", "")

                # Clean name_ja: strip date + weekday prefix
                name_ja = _DATE_PREFIX_RE.sub("", raw_title).strip() or raw_title

                # Movie title lookup — always unpack as 3-tuple
                name_zh, name_en, official_url = lookup_movie_titles(name_ja)

                seen_ids.add(source_id)
                events.append(Event(
                    source_name=self.SOURCE_NAME,
                    source_id=source_id,
                    source_url=source_url,
                    original_language="ja",
                    raw_title=raw_title,
                    raw_description=raw_description,
                    name_ja=name_ja,
                    name_zh=name_zh,
                    name_en=name_en,
                    category=["movie"],
                    start_date=start_date,
                    end_date=None,
                    location_name=LOCATION_NAME,
                    location_address=LOCATION_ADDRESS,
                    location_prefectures=LOCATION_PREFECTURES,
                    official_url=official_url,
                ))
                logger.info("cine_gallery: Taiwan event found: %s", name_ja)

            except Exception as exc:
                logger.warning("cine_gallery: failed to parse card: %s", exc)
                continue

        logger.info("cine_gallery: %d Taiwan events found", len(events))
        return events

