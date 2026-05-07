"""Scraper for KBCシネマ1・2 (Fukuoka)

URL: https://kbc-cinema.com/pages/movies
Structure: Shopify-based listing with /pages/movies/{slug} links.
Individual movie pages have an "ABOUT THE MOVIE" section for Taiwan detection.

source_name : kbc_cinema
source_id   : kbc_cinema_{slug}
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import BaseScraper, Event

logger = logging.getLogger(__name__)

_BASE = "https://kbc-cinema.com"
_LISTING_URL = "https://kbc-cinema.com/pages/movies"
_UA = "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "台灣", "金馬", "金马", "台北", "台中"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _parse_kbc_date(date_str: str) -> datetime | None:
    """Parse "2026/05公開" → 2026-05-01."""
    m = re.search(r"(\d{4})/(\d{1,2})", date_str)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1, tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _get_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = _UA
    return s


class KbcCinemaScraper(BaseScraper):
    source_name = "kbc_cinema"

    def scrape(self) -> list[Event]:
        session = _get_session()
        try:
            resp = session.get(_LISTING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("%s: listing failed: %s", self.source_name, exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Collect unique movie slugs (both /pages/movies/ and /pages/special_program/)
        slugs: dict[str, str] = {}  # slug → full path
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = re.match(r"^(/pages/(?:movies|special_program)/([^#?/]+))$", href)
            if m:
                path, slug = m.group(1), m.group(2)
                if slug not in slugs:
                    slugs[slug] = path

        events: list[Event] = []
        for slug, path in slugs.items():
            url = _BASE + path
            time.sleep(0.5)
            try:
                resp2 = session.get(url, timeout=20)
                resp2.raise_for_status()
            except Exception as exc:
                logger.debug("%s: %s failed: %s", self.source_name, slug, exc)
                continue

            soup2 = BeautifulSoup(resp2.text, "html.parser")

            # Extract title
            title_el = soup2.find(class_="detail-main-visual__title")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                h2 = soup2.find("h2")
                title = h2.get_text(strip=True) if h2 else slug

            # Extract description (ABOUT THE MOVIE section)
            description = ""
            about_heading = soup2.find(
                lambda t: t.name in ("h2", "h3", "p")
                and "ABOUT" in (t.get_text() or ""),
            )
            if about_heading:
                # Get text from next sibling paragraphs
                sibling = about_heading.find_next_sibling(["p", "div"])
                if sibling:
                    description = sibling.get_text(" ", strip=True)
            if not description:
                # Fallback: all p tags after a certain point
                paras = soup2.find_all("p")
                description = " ".join(
                    p.get_text(" ", strip=True) for p in paras if len(p.get_text(strip=True)) > 30
                )[:1000]

            if not _is_taiwan(title + " " + description):
                continue

            # Extract start_date from "detail-main-visual__date" like "2026/05公開"
            date_el = soup2.find(class_="detail-main-visual__date")
            start_date = _parse_kbc_date(date_el.get_text() if date_el else "")

            # Extract end_date from schedule note like "06/30(火)終了予定" or "N月N日..."
            end_date = None
            page_text = soup2.get_text(" ", strip=True)
            em = re.search(r"(\d{1,2})[/月](\d{1,2})[^終]*終了", page_text)
            if em:
                try:
                    now = datetime.now(timezone.utc)
                    month, day = int(em.group(1)), int(em.group(2))
                    year = now.year if month >= now.month else now.year + 1
                    end_date = datetime(year, month, day, tzinfo=timezone.utc)
                except ValueError:
                    pass

            events.append(Event(
                source_name=self.source_name,
                source_id=f"kbc_cinema_{slug}",
                source_url=url,
                original_language="ja",
                name_ja=title,
                start_date=start_date,
                end_date=end_date,
                location_name="KBCシネマ1・2",
                location_address="福岡市中央区那の津1-3-21",
                location_url=_BASE,
                is_paid=True,
                raw_title=title,
                raw_description=description,
                organizer="KBCシネマ",
                organizer_type=["commercial_brand"],
                event_form=["screening"],
            ))

        logger.info("%s: %d Taiwan events found", self.source_name, len(events))
        return events
