"""Scraper for Rights Cube (rightscube.co.jp/movies/)

Rights Cube is a Japanese distributor/rights holder that handles Asian and
world cinema releases.  Only movies with Taiwanese origin are scraped.

Platform   : WordPress static HTML — no JS rendering required
Source name: rightscube
Source ID  : rightscube_{slug}             (parent — national release overview)
             rightscube_{slug}_{venue_key} (child — per-venue theatrical run)

Taiwan relevance filter:
  Applied to h1 title + full page text.
  Keywords: ["台湾", "Taiwan", "臺灣"]

Venue key derivation from theater URL (deterministic, stable):
  SNS hosts (x.com, twitter.com): use URL path component (last segment)
  Platform CDN hosts (jimdofree.com, thebase.in): use subdomain
  Standard domains: domain name minus TLD
  Result is lowercased; non-alphanumeric chars replaced by hyphens.

Examples:
  https://x.com/theater_talpa    → theater-talpa
  https://www.ks-cinema.com/     → ks-cinema
  https://www.jackandbetty.net/  → jackandbetty
  https://cinemakobe.jimdofree.com/ → cinemakobe
  https://www.theater-seven.com/ → theater-seven
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from sources.base import BaseScraper, Event
from movie_title_lookup import lookup_movie_titles

logger = logging.getLogger(__name__)

SOURCE_NAME = "rightscube"
_BASE_URL = "https://rightscube.co.jp"
_MOVIES_URL = f"{_BASE_URL}/movies/"

_JST = timezone(timedelta(hours=9))
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0 Safari/537.36"
)

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]

# Platform CDN hosts: use subdomain as venue key
_CDN_HOST_SUFFIXES = (".jimdofree.com", ".jimdosite.com", ".thebase.in", ".stores.jp")
# SNS hosts: use URL path component as venue key
_SNS_HOSTS = frozenset({"x.com", "twitter.com", "instagram.com", "facebook.com", "lin.ee"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_taiwan_relevant(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _normalize_bold_math(text: str) -> str:
    """Convert Mathematical Sans-Serif Bold uppercase letters (U+1D5D4–U+1D5ED)
    to plain ASCII uppercase.  Needed because rightscube uses 𝗧𝗛𝗘𝗔𝗧𝗘𝗥 in headings.
    """
    result = []
    for c in text:
        cp = ord(c)
        if 0x1D5D4 <= cp <= 0x1D5ED:   # Bold uppercase A-Z
            result.append(chr(cp - 0x1D5D4 + ord("A")))
        elif 0x1D5EE <= cp <= 0x1D607:  # Bold lowercase a-z
            result.append(chr(cp - 0x1D5EE + ord("a")))
        else:
            result.append(c)
    return "".join(result)


def _venue_key(theater_url: str) -> str:
    """Derive a stable, deterministic ASCII key from a theater's website URL.

    This key is used as the suffix in source_id for venue child events.
    Must remain stable across scraper runs to avoid duplicate records.
    """
    try:
        p = urlparse(theater_url)
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]

        if host in _SNS_HOSTS:
            # Use last non-empty path segment
            path_part = p.path.strip("/").split("/")[-1]
            key = path_part.replace("?", "").split("?")[0]
        elif any(host.endswith(s) for s in _CDN_HOST_SUFFIXES):
            # Use subdomain (e.g. "cinemakobe" from cinemakobe.jimdofree.com)
            key = host.split(".")[0]
        else:
            # Use domain name minus TLD
            key = host.rsplit(".", 1)[0]

        # Normalize: lowercase, replace non-alphanumeric sequences with hyphens
        key = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
        return key or "venue"
    except Exception:
        return "venue"


def _infer_year(month: int, today: datetime) -> int:
    """Infer the year for a date given only month.
    If the month is more than 3 months in the past, assume next year.
    """
    if month < today.month - 3:
        return today.year + 1
    return today.year


def _parse_venue_dates(date_text: str, today: datetime) -> tuple[datetime | None, datetime | None]:
    """Parse venue date text from rightscube THEATER section.

    Examples:
      "4/25(土)～"          → (2026-04-25, None)  — open-ended run
      "5/17(日)・5/24(日)"  → (2026-05-17, 2026-05-24)  — specific dates only
      "6/13(土)～"          → (2026-06-13, None)

    Returns (start_date, end_date).  end_date is None for open-ended runs.
    """
    if not date_text:
        return None, None

    # Remove day-of-week markers: （土）(日) etc.
    clean = re.sub(r"[（(][月火水木金土日祝・休]+[）)]", "", date_text).strip()

    # Find all M/D patterns
    all_dates_found = re.findall(r"(\d{1,2})/(\d{1,2})", clean)
    if not all_dates_found:
        return None, None

    dates: list[datetime] = []
    for mth_s, day_s in all_dates_found:
        mth, day = int(mth_s), int(day_s)
        yr = _infer_year(mth, today)
        try:
            dates.append(datetime(yr, mth, day, tzinfo=timezone.utc))
        except ValueError:
            pass

    if not dates:
        return None, None

    start = min(dates)
    # Open-ended: text ends with ～ (or ends after clean)
    is_open = bool(re.search(r"[～~]\s*$", clean))
    end = None if is_open else (max(dates) if len(dates) > 1 else start)

    return start, end


def _fetch(url: str, session: requests.Session, delay: float = 1.5) -> BeautifulSoup | None:
    if delay > 0:
        time.sleep(delay)
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            return BeautifulSoup(resp.text, "html.parser")
        logger.warning("HTTP %s for %s", resp.status_code, url)
    except requests.RequestException as e:
        logger.warning("Request error for %s: %s", url, e)
    return None


# ---------------------------------------------------------------------------
# Scraper class
# ---------------------------------------------------------------------------

class RightscubeScraper(BaseScraper):
    """Scraper for Taiwan films distributed by Rights Cube (rightscube.co.jp)."""

    SOURCE_NAME = SOURCE_NAME

    def scrape(self) -> list[Event]:
        session = requests.Session()
        session.headers["User-Agent"] = _USER_AGENT

        # Step 1: collect all movie detail URLs from the listing page
        movie_urls = self._collect_movie_urls(session)
        logger.info("[rightscube] Found %d movie pages", len(movie_urls))

        events: list[Event] = []
        for url in movie_urls:
            try:
                page_events = self._scrape_movie(url, session)
                if page_events:
                    logger.info("[rightscube] %d events from %s", len(page_events), url)
                events.extend(page_events)
            except Exception as exc:
                logger.error("[rightscube] Error scraping %s: %s", url, exc, exc_info=True)

        return events

    # ------------------------------------------------------------------
    # Listing page
    # ------------------------------------------------------------------

    def _collect_movie_urls(self, session: requests.Session) -> list[str]:
        """Collect all movie detail URLs from the /movies/ catalog listing and
        the homepage (which features special theatrical releases not in the
        regular product catalog).

        WordPress pagination uses /movies/page/N/ URLs; we follow those too.
        """
        urls: list[str] = []
        seen: set[str] = set()
        pattern = re.compile(r"https://rightscube\.co\.jp/movies/([^/]+)/?$")
        page_pattern = re.compile(r"https://rightscube\.co\.jp/movies/page/\d+/?$")

        def _harvest(soup: BeautifulSoup) -> None:
            for a in soup.select("a[href]"):
                href = str(a.get("href", "")).rstrip("/") + "/"
                m = pattern.match(href)
                if m and href != _MOVIES_URL and href not in seen:
                    seen.add(href)
                    urls.append(href)

        # 1. Homepage — contains featured theatrical releases (e.g. taiwan-filmake)
        homepage = _fetch(_BASE_URL, session, delay=0)
        if homepage:
            _harvest(homepage)

        # 2. Product catalog with pagination
        next_url: str | None = _MOVIES_URL
        page_count = 0
        while next_url and page_count < 20:
            soup = _fetch(next_url, session, delay=0 if page_count == 0 else 1.0)
            if not soup:
                break
            page_count += 1
            _harvest(soup)

            next_url = None
            for a in soup.select("a.next, a[rel='next'], a.page-numbers.next"):
                href = str(a.get("href", ""))
                if href and page_pattern.match(href.rstrip("/") + "/"):
                    next_url = href
                    break

        return urls

    # ------------------------------------------------------------------
    # Movie detail page
    # ------------------------------------------------------------------

    def _scrape_movie(self, url: str, session: requests.Session) -> list[Event]:
        """Scrape one movie page.  Returns parent + venue child events, or [] if
        the movie is not Taiwan-relevant.
        """
        soup = _fetch(url, session)
        if not soup:
            return []

        slug = unquote(url.rstrip("/").rsplit("/", 1)[-1])

        # Title
        h1 = soup.find("h1")
        if not h1:
            return []
        title = h1.get_text(strip=True)
        # Strip special-formatting prefix like【特集上映】
        title_clean = re.sub(r"^【[^】]+】\s*", "", title).strip()

        # Taiwan relevance: check full page text
        page_text = soup.get_text(" ", strip=True)
        if not _is_taiwan_relevant(page_text):
            return []

        logger.info("[rightscube] Taiwan-relevant: %s", title_clean[:60])

        # Parse sections
        intro_text = self._section_text(soup, "INTRODUCTION", "INTRO")
        cast_text = self._section_text(soup, "CAST", "STAFF")
        theater_venues = self._parse_theater_section(soup)

        # Skip movies without any confirmed venues (DVD-only releases)
        if not theater_venues:
            logger.debug("[rightscube] No THEATER venues found, skipping: %s", title_clean[:50])
            return []

        # Earliest venue start → parent start_date
        all_starts = [v["start_date"] for v in theater_venues if v.get("start_date")]
        parent_start = min(all_starts) if all_starts else None

        # raw_description for parent
        raw_parts = []
        if parent_start:
            raw_parts.append(f"開催日時: {parent_start.strftime('%Y年%m月%d日')}\n")
        raw_parts.append(title_clean)
        if intro_text:
            raw_parts.append(intro_text[:1500])
        if cast_text:
            raw_parts.append(cast_text[:800])
        raw_desc = "\n\n".join(raw_parts)

        parent_source_id = f"rightscube_{slug}"

        name_zh, name_en = lookup_movie_titles(title_clean)

        parent = Event(
            source_name=SOURCE_NAME,
            source_id=parent_source_id,
            source_url=url,
            official_url=url,
            original_language="ja",
            name_ja=title_clean,
            name_zh=name_zh,
            name_en=name_en,
            raw_title=title,
            raw_description=raw_desc,
            start_date=parent_start,
            category=["movie"],
            is_paid=True,
            name_ja_locked=True,
        )
        events: list[Event] = [parent]

        today = datetime.now(tz=_JST)

        for venue in theater_venues:
            venue_key_str = venue["venue_key"]
            child_source_id = f"rightscube_{slug}_{venue_key_str}"

            # Look up parent UUID from DB (None on first run; set on subsequent runs)
            parent_uuid: str | None = None
            try:
                from database import get_event_id_by_source as _get_parent_uuid
                parent_uuid = _get_parent_uuid(SOURCE_NAME, parent_source_id)
            except Exception:
                pass

            theater_name = venue.get("theater_name", "")
            theater_url = venue.get("theater_url", url)
            region = venue.get("region", "")
            city = venue.get("city", "")
            bh_text = venue.get("business_hours_text", "")
            start = venue.get("start_date")
            end = venue.get("end_date")

            # name_ja: movie title + venue in parentheses
            venue_label = f"{city}{theater_name}" if city else theater_name
            child_name_ja = f"{title_clean}（{venue_label}）"

            # raw_description for child
            v_raw_parts: list[str] = []
            if start:
                v_raw_parts.append(f"開催日時: {start.strftime('%Y年%m月%d日')}\n")
            v_raw_parts.append(child_name_ja)
            detail_lines = [f"会場：{theater_name}"]
            if region or city:
                detail_lines.append(f"地域：{region} {city}".strip())
            if bh_text:
                detail_lines.append(f"上映期間：{bh_text}")
            v_raw_parts.append("\n".join(detail_lines))
            v_raw_desc = "\n\n".join(v_raw_parts)

            child = Event(
                source_name=SOURCE_NAME,
                source_id=child_source_id,
                source_url=url,
                official_url=theater_url,
                original_language="ja",
                name_ja=child_name_ja,
                raw_title=child_name_ja,
                raw_description=v_raw_desc,
                start_date=start,
                end_date=end,
                business_hours=bh_text or None,
                category=["movie"],
                is_paid=True,
                parent_event_id=parent_uuid,
                name_ja_locked=True,
            )
            events.append(child)

        return events

    # ------------------------------------------------------------------
    # Section text extraction
    # ------------------------------------------------------------------

    def _section_text(self, soup: BeautifulSoup, *keywords: str) -> str:
        """Return concatenated text of all sibling elements after a heading
        whose text contains any of *keywords*, stopping at the next heading.
        Handles both ASCII and Unicode bold Math headings (𝗧𝗛𝗘𝗔𝗧𝗘𝗥 etc.).
        """
        for h in soup.find_all(re.compile(r"^h[1-6]$")):
            normalized = _normalize_bold_math(h.get_text(strip=True)).upper()
            if any(kw.upper() in normalized for kw in keywords):
                parts: list[str] = []
                for sib in h.find_next_siblings():
                    if isinstance(sib, Tag) and re.match(r"^h[1-6]$", sib.name):
                        break
                    parts.append(sib.get_text(" ", strip=True))
                return " ".join(p for p in parts if p)
        return ""

    # ------------------------------------------------------------------
    # THEATER section parser
    # ------------------------------------------------------------------

    def _parse_theater_section(self, soup: BeautifulSoup) -> list[dict]:
        """Parse the THEATER / THEATRE section and return a list of venue dicts.

        Each dict has keys:
          region, city, theater_name, theater_url, venue_key,
          start_date, end_date, business_hours_text
        """
        # Find the THEATER heading
        theater_heading: Tag | None = None
        for h in soup.find_all(re.compile(r"^h[1-6]$")):
            normalized = _normalize_bold_math(h.get_text(strip=True)).upper()
            if "THEATER" in normalized or "THEATRE" in normalized:
                theater_heading = h
                break
        if not theater_heading:
            return []

        # Collect section elements until next same-or-higher heading
        heading_level = int(theater_heading.name[1])
        section_els: list[Tag] = []
        for sib in theater_heading.find_next_siblings():
            if isinstance(sib, Tag) and re.match(r"^h[1-6]$", sib.name):
                if int(sib.name[1]) <= heading_level:
                    break
            section_els.append(sib)

        # Rebuild as a unified soup to flatten BR structure
        combined_html = "".join(str(el) for el in section_els)
        combined = BeautifulSoup(combined_html, "html.parser")

        today = datetime.now(tz=_JST)
        venues: list[dict] = []
        current_region = ""

        # Walk all <a> elements in the section — each is one venue.
        # HTML structure observed on rightscube:
        #   <p><strong>——北海道——</strong></p>
        #   <p><strong>札幌</strong><br/><span><a href="…">シアターtalpa</a></span>｜5/17(日)・5/24(日)</p>
        for a_tag in combined.find_all("a", href=True):
            theater_name = a_tag.get_text(strip=True)
            theater_url = str(a_tag["href"])

            if not theater_name or not theater_url.startswith("http"):
                continue

            # --- Region: nearest preceding <p><strong>——XX——</strong></p> ---
            p_parent = a_tag.find_parent("p")
            if p_parent:
                for prev_p in p_parent.find_all_previous("p"):
                    strong = prev_p.find("strong")
                    if strong:
                        m = re.match(r"[—\-－]{2,}([^—\-－]+?)[—\-－]{2,}", strong.get_text(strip=True))
                        if m:
                            current_region = m.group(1).strip()
                            break

            # --- City: <strong> tag inside the same <p>, before the <br> ---
            city = ""
            if p_parent:
                strong_tags = p_parent.find_all("strong")
                for s in strong_tags:
                    txt = s.get_text(strip=True)
                    # Exclude region markers
                    if txt and not re.match(r"[—\-－]{2,}", txt):
                        city = txt
                        break

            # --- Date text: text node after the <span> that wraps <a> ---
            date_text = ""
            # The <a> is typically inside a <span>; the date follows the <span>
            a_container = a_tag.parent  # usually <span>
            next_node = a_container.next_sibling if a_container.name != "a" else a_tag.next_sibling
            if isinstance(next_node, NavigableString):
                raw = str(next_node).strip()
                if "｜" in raw:
                    date_text = raw.split("｜", 1)[1].strip()
                elif re.search(r"\d/\d", raw):
                    date_text = raw

            start, end = _parse_venue_dates(date_text, today)

            venues.append({
                "region": current_region,
                "city": city,
                "theater_name": theater_name,
                "theater_url": theater_url,
                "venue_key": _venue_key(theater_url),
                "start_date": start,
                "end_date": end,
                "business_hours_text": date_text,
            })

        return venues
