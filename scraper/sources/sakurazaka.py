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
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from sources.base import Event
from sources._cinema_base import CinemaScraper
from sources._cinema_dates import parse_japanese_date, parse_month_day

logger = logging.getLogger(__name__)

_HOME_URL = "https://sakura-zaka.com/"
_UA = "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "台灣", "金馬", "金马", "台北", "台中"]


def _is_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _parse_expire(text: str) -> datetime | None:
    """Parse "2026年05月29日まで" → UTC datetime (delegated to shared helper)."""
    return parse_japanese_date(text)


def _parse_release(text: str) -> datetime | None:
    """Parse "05月08日(金)〜" → UTC datetime with rollover (delegated to shared helper)."""
    return parse_month_day(text, rollover=True)


def _extract_movie_id(url: str) -> str | None:
    m = re.search(r"movie_info-(\d+)", url)
    return m.group(1) if m else None


_SZ_WEEKDAY_JP = "月火水木金土日"
_SZ_TOKEN_RE = re.compile(
    r"(\d{1,2})/(\d{1,2})\([月火水木金土日]\)"          # date M/D(曜)
    r"|[〜～]"                                          # range
    r"|・"                                              # continuation
    r"|(\d{1,2}):(\d{2})（[〜～](\d{1,2}):(\d{2})）"     # time HH:MM（〜HH:MM）
    r"|(\d{1,2}):(\d{2})"                              # bare time
    r"|まで"                                            # explicit end marker
    r"|以降"                                            # open-ended marker
)


def _extract_schedule_from_detail(
    soup: BeautifulSoup, current_year: int
) -> tuple[str | None, datetime | None, datetime | None]:
    """Parse the 上映スケジュール section of a Sakurazaka movie_info page.

    Schedule rendering example::

        上映スケジュール 5/23(土)・5/24(日) 12:40（〜15:01） 21:50（〜24:11）
        5/25(月)〜5/29(金) 12:40（〜15:01） 20:10（〜22:31）
        5/30(土)以降も続映予定、上映時間調整中

    Returns (business_hours, start_date, end_date) all UTC midnight.
    If "以降も続映予定" / "以降" appears after a date, that date is treated
    as a soft start of the open-ended tail and ``end_date`` is set to
    ``tail_start + 14 days``.
    """
    text = soup.get_text(" ", strip=True)
    block = re.search(
        r"上映スケジュール([\s\S]+?)(?:〒|交通・アクセス|上映プログラム|$)", text
    )
    if not block:
        return None, None, None
    sched_text = block.group(1)

    all_entries: list[tuple[int, int, int, str]] = []  # (year, month, day, time)
    cur_dates: list[tuple[int, int]] = []
    expecting_end = False
    just_emitted_time = False
    open_ended_from: datetime | None = None
    last_seen_date: tuple[int, int] | None = None

    def _year_for(mon: int, day: int) -> int:
        if all_entries:
            py, pm, _, _ = all_entries[-1]
            return py + 1 if mon < pm - 1 else py
        return current_year

    for tk in _SZ_TOKEN_RE.finditer(sched_text):
        tok = tk.group(0)
        if tk.group(1):  # date
            mon, day = int(tk.group(1)), int(tk.group(2))
            last_seen_date = (mon, day)
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
        elif tok in ("〜", "～"):
            expecting_end = True
        elif tok == "・":
            pass
        elif tk.group(3) is not None:  # time with end "HH:MM（〜HH:MM）"
            time_str = f"{tk.group(3)}:{tk.group(4)}-{tk.group(5)}:{tk.group(6)}"
            for (mon, day) in cur_dates:
                all_entries.append((_year_for(mon, day), mon, day, time_str))
            just_emitted_time = True
        elif tk.group(7) is not None:  # bare time HH:MM
            time_str = f"{tk.group(7)}:{tk.group(8)}"
            for (mon, day) in cur_dates:
                all_entries.append((_year_for(mon, day), mon, day, time_str))
            just_emitted_time = True
        elif tok == "まで":
            # "○月○日まで" — last date in cur_dates is the explicit end
            if cur_dates:
                emon, eday = cur_dates[-1]
                try:
                    open_ended_from = datetime(_year_for(emon, eday), emon, eday)
                except ValueError:
                    open_ended_from = None
                cur_dates = []
        elif tok == "以降":
            # The date most recently parsed is the open-ended tail start
            if last_seen_date is not None:
                emon, eday = last_seen_date
                try:
                    open_ended_from = datetime(_year_for(emon, eday), emon, eday)
                except ValueError:
                    open_ended_from = None
            cur_dates = []

    if not all_entries and open_ended_from is None:
        return None, None, None

    bh_lines: list[str] = []
    for y, mon, day, t in all_entries:
        try:
            wd_jp = _SZ_WEEKDAY_JP[datetime(y, mon, day).weekday()]
            bh_lines.append(f"{mon}/{day}（{wd_jp}）{t}")
        except ValueError:
            bh_lines.append(f"{mon}/{day} {t}")
    business_hours = "\n".join(bh_lines) if bh_lines else None

    start_date: datetime | None = None
    end_date: datetime | None = None
    if all_entries:
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

    if open_ended_from is not None:
        tail_end = open_ended_from + timedelta(days=14)
        tail_end_utc = datetime(
            tail_end.year, tail_end.month, tail_end.day, tzinfo=timezone.utc
        )
        if end_date is None or tail_end_utc > end_date:
            end_date = tail_end_utc

    return business_hours, start_date, end_date


def _get_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = _UA
    return s


class SakurazakaScraper(CinemaScraper):
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
            if not self.is_taiwan_relevant(title):
                # Fetch individual page for country check
                time.sleep(0.5)
                try:
                    resp2 = session.get(detail_url, timeout=20)
                    resp2.raise_for_status()
                    soup2 = BeautifulSoup(resp2.text, "html.parser")
                    # Check 作品情報 in dl/dd
                    page_text = soup2.get_text(" ", strip=True)
                    if not self.is_taiwan_relevant(page_text):
                        continue
                    # Extract description
                    description = page_text[:500]
                except Exception:
                    continue
            else:
                description = title

            # Ensure we have the full detail page for Taiwan movies
            sched_hours: str | None = None
            sched_start: datetime | None = None
            sched_end: datetime | None = None
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
                current_year = datetime.now(timezone.utc).year
                sched_hours, sched_start, sched_end = _extract_schedule_from_detail(
                    soup3, current_year
                )
                if sched_end:
                    logger.info(
                        "%s schedule: %s — end %s, %d slots",
                        self.source_name,
                        title,
                        sched_end.date(),
                        len((sched_hours or "").splitlines()),
                    )
            except Exception:
                pass

            resolved_start = sched_start or info["start_date"]
            resolved_end = sched_end or info["end_date"]
            if sched_hours:
                description = (description or "") + "\n\n上映スケジュール:\n" + sched_hours

            events.append(Event(
                source_name=self.source_name,
                source_id=self.make_film_source_id("sakurazaka", title),
                source_url=detail_url,
                original_language="ja",
                name_ja=title,
                start_date=resolved_start,
                end_date=resolved_end,
                business_hours=sched_hours,
                location_name="桜坂劇場",
                location_address="沖縄県那覇市牧志3-6-10",
                location_url=_HOME_URL,
                is_paid=True,
                raw_title=title,
                raw_description=description,
                organizer="桜坂劇場",
                organizer_type=["commercial_brand"],
                event_form=["screening"],
                category=["movie"],
            ))

        logger.info("%s: %d Taiwan events found", self.source_name, len(events))
        return events
