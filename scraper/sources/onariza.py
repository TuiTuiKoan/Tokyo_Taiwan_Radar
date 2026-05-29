"""
Scraper for 御成座（おなり座）, Odate, Akita — WordPress-based arthouse cinema.

Strategy:
  1. Fetch /category/movie/ for all film post URLs
  2. Deduplicate URLs (film appears multiple times in listing)
  3. For each film detail page, check for Taiwan keywords in full text
  4. Extract: title (h1), date (YYYY-M-D), description
  5. source_id: onariza_{slug} from URL
"""

import hashlib
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

BASE_URL = "http://onariza.oodate.or.jp"
LISTING_URL = f"{BASE_URL}/category/movie/"
LOCATION_NAME = "御成座（おなり座）"
LOCATION_ADDRESS = "秋田県大館市"

TAIWAN_KEYWORDS = ["台湾", "台灣", "Taiwan", "taiwan", "臺灣"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in TAIWAN_KEYWORDS)


def _slug_from_url(url: str) -> str:
    # /movie/kiri-no-gotoku.html → kiri-no-gotoku
    m = re.search(r"/movie/([^/]+)\.html?$", url)
    if m:
        slug = m.group(1)
        # Use first 20 chars to keep source_id manageable
        return f"onariza_{slug[:40]}"
    digest = hashlib.md5(url.encode()).hexdigest()[:10]
    return f"onariza_{digest}"


def _parse_date(text: str) -> Optional[datetime]:
    """Parse 'YYYY-M-D' from page text."""
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


_WEEKDAY_JP_FROM_INT = "月火水木金土日"
_ONARIZA_TOKEN_RE = re.compile(
    r"(\d{1,2})月(\d{1,2})日（[月火水木金土日]）|[～〜]|休映|(\d{1,2}:\d{2})"
)


def _extract_schedule_from_detail(
    soup: BeautifulSoup, current_year: int
) -> tuple[Optional[str], Optional[datetime], Optional[datetime]]:
    """Parse the 上映スケジュール block from an onariza detail page.

    The page renders schedule as a flat text run, e.g.:
        "上映スケジュール 6月5日（金）～ 6月6日（土）13:00 6月7日（日）～ 6月9日（火）10:00
         6月10日（水）休映 6月11日（木）13:00 ... 6月20日（土）15:30"

    Tokenize: a date may stand alone with a time, be followed by ～ to form a
    range whose times apply to every day in between, or be marked 休映 (skip).

    Returns (business_hours, start_date, end_date). All three are None if no
    schedule entries can be extracted.
    """
    text = soup.get_text(" ", strip=True)
    block = re.search(r"上映スケジュール([\s\S]+?)(?:tweet|関連記事|トップページ|$)", text)
    if not block:
        return None, None, None
    sched_text = block.group(1)

    all_entries: list[tuple[int, int, str, str]] = []  # (year, month, day, time)
    cur_dates: list[tuple[int, int]] = []
    expecting_end = False
    just_emitted_time = False

    for tk in _ONARIZA_TOKEN_RE.finditer(sched_text):
        tok = tk.group(0)
        if tk.group(1):  # date
            mon, day = int(tk.group(1)), int(tk.group(2))
            if just_emitted_time and not expecting_end:
                cur_dates = []
                just_emitted_time = False
            if expecting_end and cur_dates:
                sm, sd = cur_dates[-1]
                cur_dates = cur_dates[:-1]
                try:
                    d1 = datetime(current_year, sm, sd)
                    d2 = datetime(current_year, mon, day)
                except ValueError:
                    expecting_end = False
                    continue
                if d2 < d1:
                    try:
                        d2 = datetime(current_year + 1, mon, day)
                    except ValueError:
                        expecting_end = False
                        continue
                cur = d1
                while cur <= d2:
                    cur_dates.append((cur.month, cur.day))
                    cur = cur + timedelta(days=1)
                expecting_end = False
            else:
                cur_dates.append((mon, day))
        elif tok in ("～", "〜"):
            expecting_end = True
        elif tok == "休映":
            cur_dates = []
            expecting_end = False
            just_emitted_time = False
        elif tk.group(3):  # time
            time_str = tk.group(3)
            # Determine year for each date with simple rollover heuristic
            for (mon, day) in cur_dates:
                year = current_year
                if all_entries:
                    prev_year, prev_mon, _, _ = all_entries[-1]
                    if mon < prev_mon - 1:
                        year = prev_year + 1
                    else:
                        year = prev_year
                all_entries.append((year, mon, day, time_str))
            just_emitted_time = True

    if not all_entries:
        return None, None, None

    bh_lines: list[str] = []
    for y, mon, day, t in all_entries:
        try:
            wd_int = datetime(y, mon, day).weekday()
            wd_jp = _WEEKDAY_JP_FROM_INT[wd_int]
            bh_lines.append(f"{mon}/{day}（{wd_jp}）{t}")
        except ValueError:
            bh_lines.append(f"{mon}/{day} {t}")
    business_hours = "\n".join(bh_lines)

    fy, fm, fd, _ = all_entries[0]
    ly, lm, ld, _ = all_entries[-1]
    try:
        start_date = datetime(fy, fm, fd, tzinfo=timezone.utc)
    except ValueError:
        start_date = None
    try:
        end_date = datetime(ly, lm, ld, tzinfo=timezone.utc)
    except ValueError:
        end_date = None
    return business_hours, start_date, end_date


class OnarizaScraper(BaseScraper):
    """Scrapes Taiwan-related films from 御成座 (Odate, Akita)."""

    SOURCE_NAME = "onariza"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; TokyoTaiwanRadar/1.0; "
                "+https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar)"
            )
        })

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self._session.get(url, timeout=20)
            resp.raise_for_status()
            return BeautifulSoup(resp.content, "html.parser")
        except Exception as exc:
            logger.warning("GET %s failed: %s", url, exc)
            return None

    def _collect_film_urls(self) -> list[str]:
        """Return unique film detail URLs from /category/movie/."""
        seen: set[str] = set()
        results: list[str] = []
        soup = self._get_soup(LISTING_URL)
        if not soup:
            return results
        for a in soup.select("a[href*='/movie/']"):
            href = a.get("href", "")
            if "category" in href or not href.endswith(".html"):
                continue
            full_url = urljoin(BASE_URL, href)
            if full_url not in seen:
                seen.add(full_url)
                results.append(full_url)
        return results

    def _scrape_detail(self, url: str) -> Optional[Event]:
        soup = self._get_soup(url)
        if not soup:
            return None

        full_text = soup.get_text(" ", strip=True)
        if not _is_taiwan(full_text):
            return None

        # Title: page <title> is "フィルム名 | 御成座..." — split reliably
        page_title = soup.title.text if soup.title else ""
        title = page_title.split("|")[0].strip()
        if not title:
            # Fallback: h2 or h1 inside main content area
            content_area = soup.select_one(".entry-content, .post-content, #content, main")
            h = (content_area or soup).select_one("h2, h1")
            title = h.get_text(strip=True) if h else ""

        current_year = datetime.now(timezone.utc).year
        business_hours, sched_start, sched_end = _extract_schedule_from_detail(
            soup, current_year
        )
        # Prefer schedule-derived start date.  Fall back to _parse_date only when
        # the schedule isn't published yet AND the date is in the future — this
        # avoids storing the WordPress post publication date (which appears in the
        # page text as "YYYY-M-D 上映") as start_date, which would then be locked
        # in forever by the movie-extend MIN logic.
        if sched_start:
            start_date = sched_start
        else:
            fallback = _parse_date(full_text)
            today = datetime.now(timezone.utc).replace(tzinfo=None).date()
            if fallback and fallback.date() >= today:
                start_date = fallback
            else:
                start_date = None  # will be set on next scrape when schedule is available
        end_date = sched_end

        # Description: main content paragraphs
        content = soup.select_one(".entry-content, .post-content, article")
        if content:
            paras = [p.get_text(strip=True) for p in content.select("p") if len(p.get_text(strip=True)) > 20]
            desc = "\n".join(paras[:5])
        else:
            desc = full_text[:500]

        # Include full schedule in raw_description so the annotator
        # SINGLE-DAY RULE does not overwrite end_date.
        if business_hours:
            desc = (desc or "") + "\n\n上映スケジュール:\n" + business_hours

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=_slug_from_url(url),
            source_url=url,
            original_language="ja",
            name_ja=title,
            raw_title=title,
            raw_description=desc,
            description_ja=desc or None,
            category=["movie"],
            event_form=["screening"],
            start_date=start_date,
            end_date=end_date,
            business_hours=business_hours,
            location_name=LOCATION_NAME,
            location_address=LOCATION_ADDRESS,
        )

    def scrape(self) -> list[Event]:
        film_urls = self._collect_film_urls()
        logger.info("Onariza: found %d unique films", len(film_urls))

        events: list[Event] = []
        for url in film_urls:
            time.sleep(0.3)
            ev = self._scrape_detail(url)
            if ev:
                events.append(ev)
                logger.info("Onariza Taiwan film: %s", ev.name_ja)

        logger.info("Onariza total Taiwan events: %d", len(events))
        return events
