"""Scraper for 桜坂劇場 (Naha, Okinawa)

URL: https://sakura-zaka.com/
Structure: WordPress + custom CPT 'movie_info'.
  - 上映中作品: div.nowplay#sakurazaka > article > (p.expire, a[href*=movie_info])
  - 上映予定作品: article.grid-post > (p.releaseDate, a[href*=movie_info], p.grid-title)
  - Individual movie page: dl > dt[作品情報] + dd with "YYYY年/国/N分/rating"

source_name : sakurazaka
source_id   : sakurazaka_{movie_info_id}
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

_HOME_URL = "https://sakura-zaka.com/"
_UA = "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "台灣", "金馬", "金马", "台北", "台中"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _parse_expire(text: str) -> datetime | None:
    """Parse "2026年05月29日まで" → datetime."""
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _parse_release(text: str) -> datetime | None:
    """Parse "05月08日(金)〜" → datetime."""
    m = re.search(r"(\d{1,2})月(\d{1,2})日", text)
    if m:
        try:
            now = datetime.now(timezone.utc)
            month, day = int(m.group(1)), int(m.group(2))
            year = now.year if month >= now.month else now.year + 1
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _extract_movie_id(url: str) -> str | None:
    m = re.search(r"movie_info-(\d+)", url)
    return m.group(1) if m else None


def _get_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = _UA
    return s


class SakurazakaScraper(BaseScraper):
    source_name = "sakurazaka"

    def scrape(self) -> list[Event]:
        session = _get_session()
        try:
            resp = session.get(_HOME_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("%s: homepage failed: %s", self.source_name, exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        movies: dict[str, dict] = {}  # movie_id → {title, start_date, end_date, url}

        # 1. Now-showing section: div.nowplay
        nowplay = soup.find("div", id="sakurazaka")
        if nowplay:
            for article in nowplay.find_all("article"):
                a = article.find("a", href=re.compile(r"movie_info"))
                if not a:
                    continue
                mid = _extract_movie_id(a.get("href", ""))
                if not mid:
                    continue
                url = a["href"]
                if not url.startswith("http"):
                    url = "https://sakura-zaka.com/" + url.lstrip("/?")
                    url = a["href"] if a["href"].startswith("http") else "https://sakura-zaka.com" + a["href"]

                expire_p = article.find("p", class_="expire")
                end_date = _parse_expire(expire_p.get_text() if expire_p else "")

                title_p = a.find("p")
                title = re.sub(r"【[^】]+】", "", title_p.get_text(strip=True) if title_p else "").strip()

                if mid not in movies:
                    movies[mid] = {
                        "title": title,
                        "url": a["href"],
                        "start_date": None,  # currently showing
                        "end_date": end_date,
                    }

        # 2. Upcoming section: article.grid-post
        for article in soup.find_all("article", class_="grid-post"):
            a = article.find("a", href=re.compile(r"movie_info"))
            if not a:
                continue
            mid = _extract_movie_id(a.get("href", ""))
            if not mid or mid in movies:
                continue

            release_p = article.find("p", class_="releaseDate")
            start_date = _parse_release(release_p.get_text() if release_p else "")

            title_p = article.find("p", class_="grid-title")
            title = re.sub(r"【[^】]+】", "", title_p.get_text(strip=True) if title_p else "").strip()

            movies[mid] = {
                "title": title,
                "url": a["href"],
                "start_date": start_date,
                "end_date": None,
            }

        events: list[Event] = []
        for mid, info in movies.items():
            title = info["title"]
            detail_url = info["url"]

            # Quick title check first
            if not _is_taiwan(title):
                # Fetch individual page for country check
                time.sleep(0.5)
                try:
                    resp2 = session.get(detail_url, timeout=20)
                    resp2.raise_for_status()
                    soup2 = BeautifulSoup(resp2.text, "html.parser")
                    # Check 作品情報 in dl/dd
                    page_text = soup2.get_text(" ", strip=True)
                    if not _is_taiwan(page_text):
                        continue
                    # Extract description
                    description = page_text[:500]
                except Exception:
                    continue
            else:
                description = title

            # Ensure we have the full detail page for Taiwan movies
            try:
                resp3 = session.get(detail_url, timeout=20)
                resp3.raise_for_status()
                soup3 = BeautifulSoup(resp3.text, "html.parser")
                # Get actual title from page
                h1 = soup3.find("h1")
                if h1:
                    title = re.sub(r"【[^】]+】", "", h1.get_text(strip=True)).strip()
                # Get description
                dds = soup3.find_all("dd")
                description = " ".join(dd.get_text(" ", strip=True) for dd in dds)[:500]
            except Exception:
                pass

            events.append(Event(
                source_name=self.source_name,
                source_id=f"sakurazaka_{mid}",
                source_url=detail_url,
                original_language="ja",
                name_ja=title,
                start_date=info["start_date"],
                end_date=info["end_date"],
                location_name="桜坂劇場",
                location_address="沖縄県那覇市牧志3-6-10",
                location_url=_HOME_URL,
                is_paid=True,
                raw_title=title,
                raw_description=description,
                organizer="桜坂劇場",
                organizer_type=["commercial_brand"],
                event_form=["film_screening"],
            ))

        logger.info("%s: %d Taiwan events found", self.source_name, len(events))
        return events
