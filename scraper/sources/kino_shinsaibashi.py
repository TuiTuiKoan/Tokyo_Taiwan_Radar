"""Scraper for kino cinéma 心斎橋 (Osaka)

URL: https://kinocinema.jp/shinsaibashi/movie/
Structure: Movie detail links at /shinsaibashi/movie/movie-detail/{id}.
Detail pages have title in h2.detail-main-visual__title and description
in "ABOUT THE MOVIE" section.

source_name : kino_shinsaibashi
source_id   : kino_shinsaibashi_{movie_id}
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

_BASE = "https://kinocinema.jp"
_LISTING_URL = "https://kinocinema.jp/shinsaibashi/movie/"
_UA = "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "台灣", "金馬", "金马", "台北", "台中"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _get_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = _UA
    s.verify = False  # kinocinema.jp has an incomplete certificate chain
    return s


class KinoCinemaShinsaibashiScraper(BaseScraper):
    source_name = "kino_cinema_shinsaibashi"

    def scrape(self) -> list[Event]:
        session = _get_session()
        try:
            resp = session.get(_LISTING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("%s: listing failed: %s", self.source_name, exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Collect unique movie IDs from /shinsaibashi/movie/movie-detail/{id}
        movie_ids: list[str] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            m = re.search(r"/shinsaibashi/movie/movie-detail/(\d+)", a["href"])
            if m and m.group(1) not in seen:
                movie_ids.append(m.group(1))
                seen.add(m.group(1))

        events: list[Event] = []
        for mid in movie_ids:
            url = f"{_BASE}/shinsaibashi/movie/movie-detail/{mid}"
            time.sleep(0.5)
            try:
                resp2 = session.get(url, timeout=20)
                resp2.raise_for_status()
            except Exception as exc:
                logger.debug("%s: %s failed: %s", self.source_name, mid, exc)
                continue

            soup2 = BeautifulSoup(resp2.text, "html.parser")

            # Title
            title_el = soup2.find(class_="detail-main-visual__title")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            # Description from "ABOUT THE MOVIE" section
            description = ""
            for tag in soup2.find_all(["section", "div"]):
                if "ABOUT" in (tag.get_text() or ""):
                    paras = tag.find_all("p")
                    description = " ".join(p.get_text(" ", strip=True) for p in paras if len(p.get_text(strip=True)) > 20)[:1000]
                    if description:
                        break

            if not _is_taiwan(title + " " + description):
                continue

            # start_date: earliest date from all schedule buttons
            # Recon (2026-05-30): buttons cover rolling 7-day booking window only,
            # NOT the full screening period — so end_date must NOT use max(buttons).
            start_date: datetime | None = None
            now = datetime.now(timezone.utc)
            schedule_btns = soup2.find_all(
                "button", attrs={"aria-label": re.compile(r"\d+月\d+日")}
            )
            btn_dates: list[datetime] = []
            for btn in schedule_btns:
                m_date = re.search(r"(\d+)月(\d+)日", btn.get("aria-label", ""))
                if m_date:
                    try:
                        month, day = int(m_date.group(1)), int(m_date.group(2))
                        year = now.year if month >= now.month else now.year + 1
                        btn_dates.append(datetime(year, month, day, tzinfo=timezone.utc))
                    except ValueError:
                        pass
            if btn_dates:
                start_date = min(btn_dates)

            # end_date: "※N/N(曜)で上映終了" note (only reliable source for end_date)
            end_date = None
            page_text = soup2.get_text(" ", strip=True)
            em = re.search(r"※(\d{1,2})[/月](\d{1,2})[^終]*終了", page_text)
            if em:
                try:
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

            events.append(Event(
                source_name=self.source_name,
                source_id=f"kino_cinema_shinsaibashi_{mid}",
                source_url=url,
                original_language="ja",
                name_ja=title,
                start_date=start_date,
                end_date=end_date,
                location_name="kino cinéma 心斎橋",
                location_address="大阪府大阪市中央区西心斎橋1丁目6-14 ビッグステップ4階",
                location_url="https://kinocinema.jp/shinsaibashi/",
                is_paid=True,
                raw_title=title,
                raw_description=raw_desc,
                organizer="kino cinéma",
                organizer_type=["commercial_brand"],
                event_form=["screening"],
            ))

        logger.info("%s: %d Taiwan events found", self.source_name, len(events))
        return events
