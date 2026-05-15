"""Scraper for 京都シネマ (Kyoto)

URL: https://www.kyotocinema.jp/
Structure: WordPress site. Homepage shows schedule with movie links.
Individual movie pages at /movie/{id}/ have synopsis text that includes
country info in format "YYYY/国/N分/監督：.../出演：...".

source_name : kyoto_cinema
source_id   : kyoto_cinema_{movie_id}
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

_HOME_URL = "https://www.kyotocinema.jp/"
_MOVIE_URL = "https://www.kyotocinema.jp/movie/{id}/"
_UA = "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "台灣", "金馬", "金马", "台北", "台中"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _get_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = _UA
    return s


class KyotoCinemaScraper(BaseScraper):
    source_name = "kyoto_cinema"

    def scrape(self) -> list[Event]:
        session = _get_session()
        try:
            resp = session.get(_HOME_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("%s: homepage failed: %s", self.source_name, exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Collect unique movie IDs from homepage schedule links /movie/{id}/
        movie_ids: dict[str, datetime | None] = {}  # id → earliest start_date
        seen: set[str] = set()

        # Parse schedule: date headers are in ul.main-movie-date-list > li
        # Movie cards are in li.main-movie-content-once
        # Group them by looking at the schedule structure
        for card in soup.find_all("li", class_="main-movie-content-once"):
            link = card.find("a", href=re.compile(r"/movie/\d+/"))
            if not link:
                continue
            m = re.search(r"/movie/(\d+)/", link["href"])
            if not m:
                continue
            mid = m.group(1)
            if mid not in seen:
                seen.add(mid)
                # Try to find start date: look for date in enclosing schedule block
                start_date = _extract_date_from_schedule_block(card)
                movie_ids[mid] = start_date

        # Also collect any movie links we might have missed
        for a in soup.find_all("a", href=re.compile(r"kyotocinema\.jp/movie/\d+/")):
            m = re.search(r"/movie/(\d+)/", a["href"])
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                movie_ids[m.group(1)] = None

        events: list[Event] = []
        for mid, start_date in movie_ids.items():
            url = _MOVIE_URL.format(id=mid)
            time.sleep(0.5)
            try:
                resp2 = session.get(url, timeout=20)
                resp2.raise_for_status()
            except Exception as exc:
                logger.debug("%s: movie %s failed: %s", self.source_name, mid, exc)
                continue

            soup2 = BeautifulSoup(resp2.text, "html.parser")
            page_text = soup2.get_text(" ", strip=True)

            # Extract title from page title
            title = ""
            title_tag = soup2.find("title")
            if title_tag:
                title = title_tag.get_text().split("|")[0].strip()
            if not title:
                continue

            if not _is_taiwan(title + " " + page_text):
                continue

            # Extract description: look for main content paragraphs
            description = ""
            main = soup2.find("article") or soup2.find("div", id="content") or soup2.find("div", class_="entry-content")
            if main:
                paras = main.find_all("p")
                description = " ".join(p.get_text(" ", strip=True) for p in paras if len(p.get_text(strip=True)) > 20)[:1000]

            # end_date from "終映日：M/D" pattern
            end_date = None
            em = re.search(r"終映日[：:](\d{1,2})[/月](\d{1,2})", page_text)
            if em:
                try:
                    now = datetime.now(timezone.utc)
                    month, day = int(em.group(1)), int(em.group(2))
                    year = now.year if month >= now.month else now.year + 1
                    end_date = datetime(year, month, day, tzinfo=timezone.utc)
                except ValueError:
                    pass

            raw_desc = description
            if start_date and end_date and end_date != start_date:
                raw_desc = (
                    f"上映期間: {start_date.strftime('%Y年%m月%d日')}"
                    f"〜{end_date.strftime('%Y年%m月%d日')}\n\n" + raw_desc
                )
            elif start_date:
                raw_desc = f"上映期間: {start_date.strftime('%Y年%m月%d日')}\n\n" + raw_desc
            events.append(Event(
                source_name=self.source_name,
                source_id=f"kyoto_cinema_{mid}",
                source_url=url,
                original_language="ja",
                name_ja=title,
                start_date=start_date,
                end_date=end_date,
                location_name="京都シネマ",
                location_address="京都市下京区烏丸通四条下ル四条COCON烏丸3F",
                location_url=_HOME_URL,
                is_paid=True,
                raw_title=title,
                raw_description=raw_desc,
                organizer="京都シネマ",
                organizer_type=["commercial_brand"],
                event_form=["screening"],
            ))

        logger.info("%s: %d Taiwan events found", self.source_name, len(events))
        return events


def _extract_date_from_schedule_block(card) -> datetime | None:
    """Try to extract the first showing date from a movie schedule card."""
    # Walk up to find date list siblings
    parent = card.parent
    if parent:
        date_ul = parent.find_previous_sibling("ul", class_=re.compile("date"))
        if not date_ul:
            date_ul = parent.find("ul", class_=re.compile("date"))
        if date_ul:
            first_li = date_ul.find("li")
            if first_li:
                text = first_li.get_text(strip=True)
                m = re.search(r"(\d+)\.(\d+)", text)
                if m:
                    try:
                        now = datetime.now(timezone.utc)
                        month, day = int(m.group(1)), int(m.group(2))
                        year = now.year if month >= now.month else now.year + 1
                        return datetime(year, month, day, tzinfo=timezone.utc)
                    except ValueError:
                        pass
    return None
