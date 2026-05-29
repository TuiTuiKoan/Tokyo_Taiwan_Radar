"""
Scraper for ミッドランドシネマ 名古屋空港 (Midland Cinema Nagoya Airport).

Strategy:
  1. Fetch /movie/show (now showing) and /movie/schedule (upcoming)
  2. Find all a[href*='/movie_detail/'] — each is a unique film
  3. Fetch each detail page — check '制作国' field for 台湾/Taiwan
     OR check full text for Taiwan keywords
  4. source_id: "midland_cinema_{id}" — from URL /movie_detail/86785
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.midland-cinema.jp"
LISTING_URLS = [
    f"{BASE_URL}/movie/show",
    f"{BASE_URL}/movie/schedule",
]
LOCATION_NAME = "ミッドランドシネマ 名古屋空港"
LOCATION_ADDRESS = "愛知県西春日井郡豊山町豊場南長廻間1 エアポートウォーク名古屋2F"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _parse_movie_id(href: str) -> Optional[str]:
    m = re.search(r"/movie_detail/(\d+)", href)
    return m.group(1) if m else None


class MidlandCinemaScraper(BaseScraper):
    """Scrapes Taiwan-related films from ミッドランドシネマ 名古屋空港."""

    SOURCE_NAME = "midland_cinema"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.verify = False  # midland-cinema.jp has SSL cert chain issues
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

    def _collect_detail_links(self) -> dict[str, str]:
        """Return {movie_id: detail_url} for all films across listing pages."""
        links: dict[str, str] = {}
        for listing_url in LISTING_URLS:
            soup = self._get(listing_url)
            if not soup:
                logger.warning("Failed to fetch listing: %s", listing_url)
                continue
            for a in soup.select("a[href*='/movie_detail/']"):
                href = a.get("href", "")
                mid = _parse_movie_id(href)
                if mid and mid not in links:
                    full = BASE_URL + href if href.startswith("/") else href
                    links[mid] = full
        return links

    def _scrape_detail(self, url: str) -> dict:
        result = {"title": "", "country": "", "description": "", "date_text": ""}
        soup = self._get(url)
        if not soup:
            return result

        # Title from h2 or page heading
        h2 = soup.find("h2")
        if h2:
            result["title"] = h2.get_text(strip=True)
            # Strip date suffix like " 5月8日公開予定" or "5月29日公開予定" (with or without space)
            result["title"] = re.sub(r"\s*\d+月\d+日.*", "", result["title"]).strip()

        # Country: look for th "制作国" sibling td
        for th in soup.find_all("th"):
            if "制作国" in th.get_text():
                td = th.find_next_sibling("td")
                if td:
                    result["country"] = td.get_text(strip=True)
                break

        # Date: capture range (X月X日〜X月X日), end-only (X月X日まで), or start (X月X日公開予定)
        full_text = soup.get_text(" ", strip=True)
        m_range = re.search(r"\d+月\d+日[〜～~]\d+月\d+日", full_text)
        m_made = re.search(r"\d+月\d+日まで", full_text)
        m_open = re.search(r"(\d+月\d+日)公開予定", full_text)
        if m_range:
            result["date_text"] = m_range.group(0)
        elif m_made:
            result["date_text"] = m_made.group(0)
        elif m_open:
            result["date_text"] = m_open.group(1)

        # Description from story section
        story_el = soup.find("h3", string=re.compile("ストーリー|解説|あらすじ"))
        if story_el:
            paras = []
            for sib in story_el.find_all_next(["p", "h3"]):
                if sib.name == "h3":
                    break
                txt = sib.get_text(strip=True)
                if txt:
                    paras.append(txt)
            result["description"] = "\n".join(paras[:5])

        if not result["description"]:
            # Fallback: first few paragraphs
            paras = [p.get_text(strip=True) for p in soup.select("p") if len(p.get_text(strip=True)) > 20]
            result["description"] = "\n".join(paras[:4])

        return result

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        detail_links = self._collect_detail_links()
        logger.info("Collected %d unique film detail links", len(detail_links))

        for movie_id, detail_url in detail_links.items():
            time.sleep(0.5)
            detail = self._scrape_detail(detail_url)

            full_text = ""
            if detail["country"]:
                full_text = detail["country"]
            full_text += " " + detail["description"] + " " + detail["title"]

            if not _is_taiwan(full_text):
                logger.debug("Skipping non-Taiwan film: %s (country=%s)", detail["title"], detail["country"])
                continue

            source_id = f"midland_cinema_{movie_id}"
            title = detail["title"]

            # Parse start date + end date from date_text
            now = datetime.now(timezone.utc)
            start_date: Optional[datetime] = None
            if detail["date_text"]:
                m = re.match(r"(\d+)月(\d+)日", detail["date_text"])
                if m:
                    mon, day = int(m.group(1)), int(m.group(2))
                    year = now.year
                    if mon < now.month:
                        year += 1
                    try:
                        start_date = datetime(year, mon, day, tzinfo=timezone.utc)
                    except ValueError:
                        pass

            end_date: Optional[datetime] = None
            if detail["date_text"]:
                em = re.search(r"[〜～~](\d+)月(\d+)日|(\d+)月(\d+)日まで", detail["date_text"])
                if em:
                    e_mon = int(em.group(1) or em.group(3))
                    e_day = int(em.group(2) or em.group(4))
                    e_year = now.year
                    if e_mon < now.month:
                        e_year += 1
                    try:
                        end_date = datetime(e_year, e_mon, e_day, tzinfo=timezone.utc)
                    except ValueError:
                        pass

            raw_desc = detail["description"]
            if start_date:
                raw_desc = f"公開予定: {start_date.strftime('%Y年%m月%d日')}\n\n" + raw_desc

            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=detail_url,
                original_language="ja",
                name_ja=title,
                raw_title=title,
                raw_description=raw_desc,
                description_ja=detail["description"] or None,
                category=["movie"],
                start_date=start_date,
                end_date=end_date,
                location_name=LOCATION_NAME,
                location_address=LOCATION_ADDRESS,
            )
            events.append(event)
            logger.info("Found Taiwan film: %s (country=%s)", title, detail["country"])

        logger.info("Total Taiwan films found: %d", len(events))
        return events
