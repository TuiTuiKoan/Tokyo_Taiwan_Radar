"""
Scraper for シネスイッチ銀座 (Cine Switch Ginza), Tokyo.

Strategy:
  1. Fetch /movie_now — parse movie cards (title, URL, optional end_date from "M/D まで")
  2. Fetch each /movie_detail/{slug} — extract country, description, official site
  3. Taiwan filter: 制作国 contains 台湾/Taiwan OR title/description contains 台湾/台灣
  4. start_date: today (currently showing); end_date: parsed from "M/D まで" label
  5. source_id: URL slug — stable across runs
"""

import logging
import re
import time
from datetime import datetime, date
from typing import Optional
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://cineswitch.com"
LISTING_URL = f"{BASE_URL}/movie_now"

LOCATION_NAME = "シネスイッチ銀座"
LOCATION_ADDRESS = "東京都中央区銀座4-4-5 簱ビル"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(country: str, title: str, description: str) -> bool:
    combined = f"{country} {title} {description}"
    return any(kw in combined for kw in TAIWAN_KEYWORDS)


def _parse_end_date(label: str, today: date) -> Optional[datetime]:
    """Parse "4／30  まで" → datetime(today.year, 4, 30)."""
    m = re.search(r"(\d{1,2})／(\d{1,2})", label)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    year = today.year
    # If the resulting month/day is in the past, assume next year
    try:
        end = date(year, month, day)
        if end < today:
            end = date(year + 1, month, day)
        return datetime(end.year, end.month, end.day, 23, 59, 59)
    except ValueError:
        return None


class CineswitchGinzaScraper(BaseScraper):
    """Scrapes Taiwan-related films currently showing at シネスイッチ銀座."""

    SOURCE_NAME = "cineswitch_ginza"

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

    def _scrape_detail(self, url: str) -> dict:
        """Return dict with keys: country, description, official_url."""
        result = {"country": "", "description": "", "official_url": None}
        soup = self._get(url)
        if not soup:
            return result

        # 制作国 — inside a table row: <td>制作国</td><td>台湾</td>
        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) >= 2 and "制作国" in cells[0].get_text():
                result["country"] = cells[1].get_text(strip=True)
                break

        # Description — div.movie_commentary > p
        commentary = soup.select_one("div.movie_commentary")
        if commentary:
            result["description"] = commentary.get_text(separator="\n", strip=True)

        # Official site — info div with label "公式サイト"
        for info in soup.select("div.info"):
            name_el = info.select_one("div.info_name")
            data_el = info.select_one("div.info_data")
            if name_el and data_el and "公式サイト" in name_el.get_text():
                link = data_el.find("a")
                if link:
                    result["official_url"] = link.get("href")
                else:
                    result["official_url"] = data_el.get_text(strip=True) or None

        return result

    def scrape(self) -> list[Event]:
        today = datetime.now().date()
        events: list[Event] = []

        soup = self._get(LISTING_URL)
        if not soup:
            logger.error("Failed to fetch listing page: %s", LISTING_URL)
            return events

        articles = soup.select("article.poster_wrap")
        logger.info("Found %d movie cards on listing page", len(articles))

        for article in articles:
            # End date label (e.g. "4／30  まで" or "NEW")
            showing_el = article.select_one("p.showing")
            end_date_label = showing_el.get_text(strip=True) if showing_el else ""
            end_date = _parse_end_date(end_date_label, today)

            # Movie link and title
            link_el = article.select_one("div.p_img a")
            if not link_el:
                continue
            detail_url = link_el.get("href", "")
            if not detail_url:
                continue
            title = link_el.get("title") or link_el.get_text(strip=True)

            # source_id from URL slug
            slug = unquote(detail_url.rstrip("/").split("/")[-1])
            source_id = f"cineswitch_ginza_{slug}"

            # Fetch detail page
            time.sleep(0.5)
            detail = self._scrape_detail(detail_url)

            # Taiwan filter
            if not _is_taiwan(detail["country"], title, detail["description"]):
                logger.debug("Skipping non-Taiwan film: %s (country=%s)", title, detail["country"])
                continue

            start_date = datetime(today.year, today.month, today.day)

            raw_desc_parts = []
            if end_date:
                raw_desc_parts.append(
                    f"上映期間: {today.strftime('%Y年%m月%d日')} 〜 {end_date.strftime('%Y年%m月%d日')}\n"
                )
            raw_desc_parts.append(detail["description"])
            raw_description = "\n".join(raw_desc_parts)

            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=detail_url,
                original_language="ja",
                name_ja=title,
                raw_title=title,
                raw_description=raw_description,
                description_ja=detail["description"] or None,
                category=["movie"],
                start_date=start_date,
                end_date=end_date,
                location_name=LOCATION_NAME,
                location_address=LOCATION_ADDRESS,
                official_url=detail.get("official_url"),
            )
            events.append(event)
            logger.info("Found Taiwan film: %s (country=%s)", title, detail["country"])

        logger.info("Total Taiwan films found: %d", len(events))
        return events
