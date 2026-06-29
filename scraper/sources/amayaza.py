"""
Scraper for あまや座 (Amayaza), Naka City, Ibaraki.

Strategy:
  1. Fetch WordPress category pages for current and upcoming films:
     - /category/上映中の作品/ → film posts with date ranges in title
     - /category/今後の上映作品/ → upcoming film posts
  2. Each post has title like 『映画名』　2026/4/25（土）〜5/8（金）
  3. Check post content for Taiwan keywords
  4. Extract dates from post title
  5. source_id: "amayaza_{post_id}" — from URL /2014/12/01/post-9452/ → 9452
"""

import logging
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from movie_title_lookup import lookup_movie_titles

logger = logging.getLogger(__name__)

BASE_URL = "https://amaya-za.com"
CATEGORY_URLS = [
    f"{BASE_URL}/category/%e4%b8%8a%e6%98%a0%e4%b8%ad%e3%81%ae%e4%bd%9c%e5%93%81/",   # 上映中の作品
    f"{BASE_URL}/category/%e4%bb%8a%e5%be%8c%e3%81%ae%e4%b8%8a%e6%98%a0%e4%bd%9c%e5%93%81/",  # 今後の上映作品
]
LOCATION_NAME = "あまや座"
LOCATION_ADDRESS = "茨城県那珂市瓜連1724-2"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan"]
_BUSINESS_HOURS_RE = re.compile(
    r"\b([01]?\d|2[0-3]):([0-5]\d)\s*[〜～\-－]\s*([01]?\d|2[0-3]):([0-5]\d)\b"
)


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _parse_post_id(url: str) -> Optional[str]:
    m = re.search(r"/post-(\d+)", url)
    return m.group(1) if m else None


def _parse_dates_from_title(title: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Parse title like '『花様年華4K』　2026/4/25（土）〜5/8（金）' → (start, end)."""
    m = re.search(
        r"(\d{4})/(\d{1,2})/(\d{1,2})[^〜～]*[〜～](\d{1,2})/(\d{1,2})",
        title,
    )
    if not m:
        return None, None
    y = int(m.group(1))
    try:
        start = datetime(y, int(m.group(2)), int(m.group(3)))
        end_m, end_d = int(m.group(4)), int(m.group(5))
        # Year rollover
        end_y = y if end_m >= int(m.group(2)) else y + 1
        end = datetime(end_y, end_m, end_d)
        return start, end
    except ValueError:
        return None, None


def _clean_detail_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title.replace("\u3000", " ")).strip()
    return re.sub(r"\s*(?:[|｜]|[-–—])\s*(?:あまや座|AMAYAZA|Amayaza).*$", "", title).strip()


def _extract_detail_title(soup: BeautifulSoup) -> str:
    meta = soup.select_one("meta[property='og:title'], meta[name='og:title']")
    if meta:
        title = _clean_detail_title(meta.get("content", ""))
        if title:
            return title

    page_title = soup.select_one("title")
    if page_title:
        title = _clean_detail_title(page_title.get_text(" ", strip=True))
        if title:
            return title

    for selector in ("article h1", "h1.entry-title", ".entry-title", "h1"):
        elem = soup.select_one(selector)
        if not elem:
            continue
        title = _clean_detail_title(elem.get_text(" ", strip=True))
        if title and title != LOCATION_NAME:
            return title
    return ""


def _select_post_title(listing_title: str, detail_title: str) -> str:
    return listing_title.strip() or _clean_detail_title(detail_title)


def _extract_film_title(post_title: str) -> str:
    """Extract clean film name from post title like '『花様年華4K』　2026/4/25...' """
    m = re.match(r"[『「]([^』」]+)[』」]", post_title)
    if m:
        return m.group(1)
    # Fall back to text before date
    m2 = re.match(r"([^　\s]+)", post_title)
    return m2.group(1).strip("『』「」") if m2 else post_title


def _extract_business_hours(text: str) -> Optional[str]:
    m = _BUSINESS_HOURS_RE.search(text)
    if not m:
        return None
    start_hour, start_minute, end_hour, end_minute = m.groups()
    return f"{int(start_hour):02d}:{start_minute}〜{int(end_hour):02d}:{end_minute}"


class AmayazaScraper(BaseScraper):
    """Scrapes Taiwan-related films from あまや座 (Naka City, Ibaraki)."""

    SOURCE_NAME = "amayaza"

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

    def _collect_film_posts(self) -> list[dict]:
        """Return list of {post_url, post_title} from WordPress category pages."""
        posts: dict[str, dict] = {}
        for cat_url in CATEGORY_URLS:
            soup = self._get(cat_url)
            if not soup:
                continue
            for a in soup.select("a[href*='/post-']"):
                href = a.get("href", "")
                post_title = a.get_text(" ", strip=True) or a.get("title", "").strip()
                if not post_title:
                    img = a.select_one("img[alt]")
                    post_title = img.get("alt", "").strip() if img else ""
                if not href:
                    continue
                if href in posts:
                    if not posts[href]["post_title"] and post_title:
                        posts[href]["post_title"] = post_title
                    continue
                posts[href] = {"post_url": href, "post_title": post_title}
        return list(posts.values())

    def _scrape_post(self, url: str) -> dict:
        result = {"full_text": "", "description": ""}
        soup = self._get(url)
        if not soup:
            return result

        result["full_text"] = soup.get_text(" ", strip=True)
        result["title"] = _extract_detail_title(soup)

        content = soup.select_one(".entry-content") or soup.select_one("article")
        if content:
            paras = [p.get_text(strip=True) for p in content.select("p") if len(p.get_text(strip=True)) > 20]
            result["description"] = "\n".join(paras[:5])

        return result

    def scrape(self) -> list[Event]:
        events: list[Event] = []

        film_posts = self._collect_film_posts()
        logger.info("Found %d film posts from category pages", len(film_posts))

        for post in film_posts:
            post_url = post["post_url"]
            listing_title = post["post_title"]

            time.sleep(0.5)
            detail = self._scrape_post(post_url)
            post_title = _select_post_title(listing_title, detail.get("title", ""))

            if not _is_taiwan(detail["full_text"]):
                logger.debug("Skipping non-Taiwan post: %s", post_title[:40])
                continue

            post_id = _parse_post_id(post_url)
            source_id = f"amayaza_{post_id}" if post_id else f"amayaza_{hash(post_url)}"

            film_title = _extract_film_title(post_title)
            start_date, end_date = _parse_dates_from_title(post_title)

            raw_desc = detail["description"]
            if start_date:
                raw_desc = (
                    f"上映期間: {start_date.strftime('%Y年%m月%d日')}"
                    + (f"〜{end_date.strftime('%Y年%m月%d日')}" if end_date else "")
                    + "\n\n" + raw_desc
                )
            business_hours = _extract_business_hours(raw_desc or detail["description"] or detail["full_text"] or post_title)
            name_zh, name_en = None, None
            if film_title:
                name_zh, name_en, _ = lookup_movie_titles(film_title)

            event = Event(
                source_name=self.SOURCE_NAME,
                source_id=source_id,
                source_url=post_url,
                original_language="ja",
                name_ja=film_title,
                name_zh=name_zh,
                name_en=name_en,
                raw_title=film_title,
                raw_description=raw_desc or post_title,
                description_ja=detail["description"] or None,
                category=["movie"],
                start_date=start_date,
                end_date=end_date,
                location_name=LOCATION_NAME,
                location_address=LOCATION_ADDRESS,
                business_hours=business_hours,
            )
            events.append(event)
            logger.info("Found Taiwan film: %s", film_title)

        logger.info("Total Taiwan films found: %d", len(events))
        return events
