"""Scraper for シネマート新宿 (Cinemart Shinjuku)

Source URL: https://www.cinemart.co.jp/theater/shinjuku/movie/
Tagline   : アジアをもっと好きになる (Asia-focused art cinema)
Platform  : Static HTML — no JS rendering required
Source name: cinemart_shinjuku
Source ID : cinemart_shinjuku_{6-digit-number}  (from URL)

Strategy:
  1. Fetch the movie listing page
  2. Collect all relative 6-digit links (e.g. 002491.html)
  3. Resolve to full URLs: /theater/shinjuku/movie/{number}.html
  4. Apply Taiwan keyword filter on listing link text (fast pre-filter)
  5. Fetch detail page; confirm Taiwan relevance on full page text
  6. Parse start_date from the first <p> of <main>:
       "5月8日(金)ロードショー"      → start_date=5/8, end_date=None
       "5月28日（木）1日限定上映"    → start_date=end_date=5/28
  7. Build raw_description from <p> elements inside <main>

Taiwan keyword filter:
  ["台湾", "Taiwan", "臺灣", "金馬"]
  Applied first to listing text (cheap), then to full detail page text.

Venue (fixed):
  シネマート新宿
  東京都新宿区新宿3丁目13番3号 新宿文化ビル6F・7F
"""

import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sources._cinema_base import CinemaScraper
from sources.base import Event
from movie_title_lookup import lookup_movie_titles

logger = logging.getLogger(__name__)

SOURCE_NAME = "cinemart_shinjuku"

_BASE_URL = "https://www.cinemart.co.jp"
_LISTING_URL = "https://www.cinemart.co.jp/theater/shinjuku/movie/"

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

_VENUE_NAME = "シネマート新宿"
_VENUE_ADDRESS = "東京都新宿区新宿3丁目13番3号 新宿文化ビル6F・7F"

# Taiwan relevance filter
_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "金馬"]

# Stop words — <p> elements containing these start the venue/sidebar section
_VENUE_STOP_WORDS = [
    "オープン時間", "先売り指定席", "次週タイムスケジュール",
    "新宿区新宿3丁目", "東京メトロ", "詳しくはこちら",
]

_SCHEDULE_URL = "https://cinemart.cineticket.jp/theater/shinjuku/schedule"
_TITLE_BRACKET_RE = re.compile(r"[【〈（(〔][^】〉）)〕]*[】〉）)〕]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_taiwan_relevant(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _infer_year(month: int, today: datetime) -> int:
    """Infer year from month only. If month < today.month - 3, assume next year."""
    if month < today.month - 3:
        return today.year + 1
    return today.year


def _parse_release_date(date_str: str, today: datetime) -> tuple[datetime | None, datetime | None]:
    """Parse the release date line from the first <p> in <main>.

    Examples:
      '5月8日(金)ロードショー'      → (2026-05-08, None)   — ongoing release
      '5月28日（木）1日限定上映'    → (2026-05-28, 2026-05-28) — single day
      '4月17日(金)より限定開催！'   → (2026-04-17, None)   — start known, end unknown

    Returns (start_date, end_date). Both may be None on parse failure.
    """
    # Remove day-of-week parentheticals
    clean = re.sub(r"[（(][月火水木金土日祝]+[）)]", "", date_str)
    # Remove time patterns
    clean = re.sub(r"\d{1,2}:\d{2}", "", clean)

    m = re.search(r"(\d{1,2})月(\d{1,2})日", clean)
    if not m:
        return None, None

    month, day = int(m.group(1)), int(m.group(2))
    year = _infer_year(month, today)
    try:
        start = datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None, None

    # 1日限定 = single day event
    if "1日限定" in date_str or "一日限定" in date_str:
        return start, start

    return start, None


# ---------------------------------------------------------------------------
# Schedule helpers
# ---------------------------------------------------------------------------

def _normalize_title(title: str) -> str:
    """Remove bracket modifiers (【4K上映】, 〈特別版〉, etc.) for fuzzy title matching."""
    return _TITLE_BRACKET_RE.sub("", title).strip()


def _parse_schedule_page(session) -> dict[str, dict]:
    """Scrape the weekly schedule page and return {normalized_title: {start_date, end_date, business_hours}}."""
    soup = _fetch(_SCHEDULE_URL, session)
    if not soup:
        return {}

    _WEEKDAY_JA = {0: "月", 1: "火", 2: "水", 3: "木", 4: "金", 5: "土", 6: "日"}
    result: dict[str, dict] = {}

    for panel in soup.select(".movie-panel"):
        try:
            title_el = panel.select_one(".title-jp")
            if not title_el:
                continue
            norm = _normalize_title(title_el.get_text(strip=True))
            if not norm:
                continue

            dates_map: dict[str, list[str]] = {}
            for sched in panel.select('[class*="movie-schedule"][data-date]'):
                try:
                    date_str = sched["data-date"]  # e.g. "20260501"
                    text = sched.get_text(separator="|", strip=True)
                    times = re.findall(r'\d{1,2}:\d{2}', text)
                    first_time = times[0] if times else None
                    if first_time is not None:
                        dates_map.setdefault(date_str, []).append(first_time)
                except Exception:
                    continue

            if not dates_map:
                continue

            # Merge into existing entry if this movie already seen (different hall/version)
            if norm in result:
                existing_map = result[norm]["_dates_map"]
                for ds, tlist in dates_map.items():
                    existing_map.setdefault(ds, []).extend(tlist)
                    existing_map[ds] = sorted(set(existing_map[ds]))
                dates_map = existing_map
            else:
                # De-dup times per day
                for ds in dates_map:
                    dates_map[ds] = sorted(set(dates_map[ds]))

            date_objs = [
                datetime(int(d[:4]), int(d[4:6]), int(d[6:]), tzinfo=timezone.utc)
                for d in sorted(dates_map)
            ]
            start_date = min(date_objs)
            end_date = max(date_objs)

            lines: list[str] = []
            for ds in sorted(dates_map):
                dt = datetime(int(ds[:4]), int(ds[4:6]), int(ds[6:]), tzinfo=timezone.utc)
                dow = _WEEKDAY_JA[dt.weekday()]
                month_day = f"{dt.month}/{dt.day}"
                times_str = "・".join(dates_map[ds])
                lines.append(f"{month_day}（{dow}）{times_str}")
            business_hours = "\n".join(lines)

            result[norm] = {
                "start_date": start_date,
                "end_date": end_date,
                "business_hours": business_hours,
                "_dates_map": dates_map,
            }
        except Exception:
            continue

    # Strip internal _dates_map key before returning
    for v in result.values():
        v.pop("_dates_map", None)

    return result


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _fetch(url: str, session) -> BeautifulSoup | None:
    try:
        resp = session.get(url, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return BeautifulSoup(resp.text, "html.parser")
        logger.warning("HTTP %s for %s", resp.status_code, url)
    except Exception as e:
        logger.warning("Request error for %s: %s", url, e)
    return None


# ---------------------------------------------------------------------------
# Listing page
# ---------------------------------------------------------------------------

def _get_movie_links(session) -> list[tuple[str, str]]:
    """Return list of (full_url, listing_text) pairs.

    Links on the listing page are relative 6-digit numbers like '002491.html'.
    """
    soup = _fetch(_LISTING_URL, session)
    if not soup:
        return []

    base_dir = _LISTING_URL  # links are relative to this dir
    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        # Only 6-digit .html links (e.g. 002491.html)
        if not re.match(r"^\d{6}\.html$", href):
            continue
        if href in seen:
            continue
        seen.add(href)
        full_url = urljoin(base_dir, href)
        link_text = a.get_text(strip=True)
        results.append((full_url, link_text))

    return results


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------

def _extract_movie_number(url: str) -> str:
    """Extract the 6-digit number from a movie URL.

    https://www.cinemart.co.jp/theater/shinjuku/movie/002491.html → '002491'
    """
    m = re.search(r"(\d{6})\.html", url)
    return m.group(1) if m else url.rsplit("/", 1)[-1].replace(".html", "")


def _scrape_detail(url: str, session, today: datetime) -> Event | None:
    """Scrape a movie detail page. Returns None if not Taiwan-relevant."""
    soup = _fetch(url, session)
    if not soup:
        return None

    main = soup.select_one("main")
    if not main:
        return None

    full_text = main.get_text(separator="\n", strip=True)

    # Taiwan relevance check
    if not _is_taiwan_relevant(full_text):
        return None

    # --- Title: first <h2> ---
    h2 = main.select_one("h2")
    title = h2.get_text(strip=True) if h2 else ""
    if not title:
        return None

    # --- Release date: first <p> ---
    start_date: datetime | None = None
    end_date: datetime | None = None
    first_p = main.select_one("p")
    if first_p:
        first_p_text = first_p.get_text(strip=True)
        start_date, end_date = _parse_release_date(first_p_text, today)

    # --- Description: collect <p> content, stop at venue/sidebar section ---
    desc_parts: list[str] = []
    # Skip the first <p> (release date line) and collect body text
    all_ps = main.select("p")
    for p in all_ps[1:]:
        text = p.get_text(strip=True)
        if not text:
            continue
        # Stop at venue info / sidebar
        if any(stop in text for stop in _VENUE_STOP_WORDS):
            break
        desc_parts.append(text)

    raw_desc = "\n".join(desc_parts)

    # Prepend event date per BaseScraper convention
    if start_date:
        date_str = start_date.strftime("%Y年%m月%d日")
        raw_desc = f"開催日時: {date_str}\n\n" + raw_desc

    # --- Official URL: look for "オフィシャルサイト" or "公式サイト" external link ---
    official_url: str | None = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if not href.startswith("http"):
            continue
        if "cinemart.co.jp" in href:
            continue
        if any(kw in text for kw in ["オフィシャルサイト", "公式サイト", "official site", "Official Site"]):
            official_url = href
            break

    movie_number = _extract_movie_number(url)

    name_zh, name_en, _ = lookup_movie_titles(title)
    return Event(
        source_name=SOURCE_NAME,
        source_id=f"cinemart_shinjuku_{movie_number}",
        source_url=url,
        original_language="ja",
        name_zh=name_zh,
        name_en=name_en,
        raw_title=title,
        raw_description=raw_desc or title,
        start_date=start_date,
        end_date=end_date,
        category=["movie"],
        location_name=_VENUE_NAME,
        location_address=_VENUE_ADDRESS,
        is_paid=True,
        official_url=official_url,
    )


# ---------------------------------------------------------------------------
# Scraper class
# ---------------------------------------------------------------------------

class CinemartShinjukuScraper(CinemaScraper):
    """Scraper for シネマート新宿 (Cinemart Shinjuku) Taiwan film screenings.

    Cinemart Shinjuku is an Asia-focused art cinema in Shinjuku (Shinjuku Bunka
    Building 6F/7F). It regularly screens Taiwan films. A Taiwan keyword filter
    is required as it also screens Korean and other Asian films.
    """

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        today = datetime.now(timezone.utc)
        session = self.make_session()
        session.headers.update({"User-Agent": _USER_AGENT})

        # Step 1: collect movie links from listing
        movie_links = _get_movie_links(session)
        logger.info("Cinemart Shinjuku: found %d movie pages", len(movie_links))

        events: list[Event] = []
        for url, listing_text in movie_links:
            # Fast pre-filter: check Taiwan keywords in listing text
            if not _is_taiwan_relevant(listing_text):
                continue

            time.sleep(0.5)
            event = _scrape_detail(url, session, today)
            if event:
                logger.info("  %s → %r", _extract_movie_number(url), event.raw_title)
                events.append(event)

        logger.info("Cinemart Shinjuku: total events=%d", len(events))

        # Phase 2: enrich events with weekly schedule data
        try:
            time.sleep(0.5)
            schedule_data = _parse_schedule_page(session)
            logger.info("Cinemart schedule: %d titles found", len(schedule_data))
            for event in events:
                norm = _normalize_title(event.raw_title)
                if norm in schedule_data:
                    sd = schedule_data[norm]
                    event.start_date = sd["start_date"]
                    event.end_date = sd["end_date"]
                    event.business_hours = sd["business_hours"]
                    logger.info("  schedule enriched: %s → %s~%s bh=%s",
                                norm,
                                sd["start_date"].strftime("%m/%d") if sd["start_date"] else None,
                                sd["end_date"].strftime("%m/%d") if sd["end_date"] else None,
                                bool(sd["business_hours"]))
                else:
                    # Not yet showing / not on schedule — clear end_date so frontend shows "—"
                    event.end_date = None
        except Exception as exc:
            logger.warning("Cinemart schedule enrichment failed: %s", exc)

        return events
