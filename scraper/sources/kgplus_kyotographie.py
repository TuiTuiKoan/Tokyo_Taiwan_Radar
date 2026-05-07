"""Scraper for KG+ Kyotographie (https://kgplus.kyotographie.jp).

KG+ is a satellite programme of KYOTOGRAPHIE International Photography Festival,
held annually in Kyoto each April–May. It features 200+ exhibitions across venues
in Kyoto, ~4 of which are Taiwan-related each year.

Strategy:
  1. Detect the current festival year by querying /wp-json/wp/v2/types and finding
     the most recent `exhibitions_plus{YEAR}` Custom Post Type.
  2. Enumerate all exhibition slugs/links via WP REST API (per_page=100, paginated).
  3. For each exhibition, fetch its individual HTML page.
  4. Filter pages that contain Taiwan keywords (台湾 / Taiwan / 臺灣 / etc.).
  5. For matching pages, extract title, dates, venue, and description.

source_name : kgplus_kyotographie
source_id   : kgplus_{slug}   e.g. kgplus_makoto-lin

Date format on individual pages: "M.D Weekday–M.D Weekday" inside <p class="-openclose">
  e.g. "Open: 4.4 Sat.–5.3 Sun."  Year inferred from CPT name (festival year).

No Playwright needed — WP REST API (JSON) + static HTML individual pages.
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

_BASE_URL = "https://kgplus.kyotographie.jp"
_WP_API = f"{_BASE_URL}/wp-json/wp/v2"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣", "台南", "台北", "taiwanese", "Taiwanese"]

# Safety cap: stop enumerating if more than this many exhibitions are found
_MAX_EXHIBITIONS = 400

# Seconds between individual page requests (rate limiting)
_REQUEST_DELAY = 0.5


def _contains_taiwan(text: str) -> bool:
    return any(kw in text for kw in _TAIWAN_KEYWORDS)


def _parse_festival_dates(
    openclose_text: str, festival_year: int
) -> tuple[datetime | None, datetime | None]:
    """Parse date range from p.-openclose text.

    Input examples:
      "Open: 4.4 Sat.– 5.3 Sun. Closed: Mon. Tue."
      "Open: 4.18 Sat.–5.17 Sun."
      "Open: 5.1 Fri.–5.10 Sun."

    Returns (start_date, end_date) as UTC datetimes.
    Year is inferred from festival_year (the CPT name's embedded year).
    """
    # Match start and end: digits.digits ... dash ... digits.digits
    match = re.search(
        r"Open:\s*(\d{1,2})\.(\d{1,2})\b[^–—\-]*[–—\-]\s*(\d{1,2})\.(\d{1,2})",
        openclose_text,
    )
    if match:
        start_m, start_d = int(match.group(1)), int(match.group(2))
        end_m, end_d = int(match.group(3)), int(match.group(4))
        try:
            start = datetime(festival_year, start_m, start_d, tzinfo=timezone.utc)
            end = datetime(festival_year, end_m, end_d, tzinfo=timezone.utc)
            return start, end
        except ValueError:
            pass

    # Fallback: single date only
    match = re.search(r"Open:\s*(\d{1,2})\.(\d{1,2})", openclose_text)
    if match:
        m, d = int(match.group(1)), int(match.group(2))
        try:
            return datetime(festival_year, m, d, tzinfo=timezone.utc), None
        except ValueError:
            pass

    return None, None


class KgplusKyotographieScraper(BaseScraper):
    """Scrapes Taiwan-related exhibitions from KG+ Kyotographie (Kyoto)."""

    SOURCE_NAME = "kgplus_kyotographie"

    def scrape(self) -> list[Event]:
        # Step 1: Detect which CPT to use
        cpt_name = self._detect_cpt()
        if not cpt_name:
            logger.warning(
                "KG+: could not detect exhibitions CPT — returning empty (festival may be off-season or API unreachable)"
            )
            return []

        m = re.search(r"(\d{4})$", cpt_name)
        festival_year = int(m.group(1)) if m else datetime.now(timezone.utc).year
        logger.info("KG+: using CPT '%s' (festival year %d)", cpt_name, festival_year)

        # Step 2: Enumerate all exhibition slugs
        slugs_and_links = self._fetch_all_slugs(cpt_name)
        logger.info("KG+: %d exhibitions total to check for Taiwan relevance", len(slugs_and_links))

        # Step 3: Fetch each page and filter by Taiwan keywords
        events: list[Event] = []
        for slug, link in slugs_and_links:
            event = self._process_exhibition(slug, link, festival_year)
            if event:
                events.append(event)
                logger.info("KG+: Taiwan exhibition found: %s (%s)", slug, link)
            time.sleep(_REQUEST_DELAY)

        logger.info("KG+: %d Taiwan-related exhibitions found", len(events))
        return events

    # ------------------------------------------------------------------
    def _detect_cpt(self) -> str | None:
        """Return the most recent exhibitions_plus{YEAR} CPT name available in WP."""
        try:
            resp = requests.get(f"{_WP_API}/types", headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            types = resp.json()
        except Exception as exc:
            logger.error("KG+: failed to fetch WP types: %s", exc)
            return None

        year_cpts = [k for k in types if re.match(r"^exhibitions_plus\d{4}$", k)]
        if not year_cpts:
            logger.warning("KG+: no exhibitions_plus{YEAR} CPT found")
            return None

        # lexicographic max = most recent year
        return max(year_cpts)

    def _fetch_all_slugs(self, cpt_name: str) -> list[tuple[str, str]]:
        """Paginate WP REST API to collect all (slug, link) pairs."""
        results: list[tuple[str, str]] = []
        page = 1

        while len(results) < _MAX_EXHIBITIONS:
            url = f"{_WP_API}/{cpt_name}?per_page=100&page={page}&_fields=slug,link"
            try:
                resp = requests.get(url, headers=_HEADERS, timeout=20)
                # WP returns 400 when page exceeds total pages
                if resp.status_code == 400:
                    break
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.error("KG+: error fetching exhibition list page %d: %s", page, exc)
                break

            if not data:
                break

            for item in data:
                slug = item.get("slug", "")
                link = item.get("link", "")
                if slug and link:
                    results.append((slug, link))

            total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
            if page >= total_pages:
                break
            page += 1
            time.sleep(_REQUEST_DELAY)

        return results

    def _process_exhibition(
        self,
        slug: str,
        link: str,
        festival_year: int,
    ) -> Event | None:
        """Fetch individual exhibition page; return Event if Taiwan-related, else None."""
        try:
            resp = requests.get(link, headers=_HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.debug("KG+: failed to fetch %s: %s", link, exc)
            return None

        html = resp.text
        if not _contains_taiwan(html):
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Artist name (h1 with class "-name")
        h1 = soup.find("h1", class_="-name")
        artist = h1.get_text(strip=True) if h1 else ""

        # Exhibition subtitle (p with class "-l1")
        subtitle_el = soup.find("p", class_="-l1")
        subtitle = subtitle_el.get_text(strip=True) if subtitle_el else ""

        # Build display name
        if artist and subtitle:
            name_ja = f"{artist}「{subtitle}」"
        elif artist:
            name_ja = artist
        else:
            name_ja = subtitle or slug

        # Venue name
        venue_el = soup.find("h4", class_="-venue")
        location_name = venue_el.get_text(strip=True) if venue_el else None

        # Address (p with class "-access")
        access_el = soup.find("p", class_="-access")
        raw_access = access_el.get_text(" ", strip=True) if access_el else ""
        addr_match = re.search(r"(〒[\d\-]+\s*\S[^\s].*|[都道府県]\S+市\S+)", raw_access)
        location_address: str | None = addr_match.group(1).strip() if addr_match else None
        # Enforce location_name ≠ location_address rule
        if location_address and location_address == location_name:
            location_address = None

        # Dates (p with class "-openclose")
        openclose_el = soup.find("p", class_="-openclose")
        openclose_text = openclose_el.get_text(" ", strip=True) if openclose_el else ""
        start_date, end_date = _parse_festival_dates(openclose_text, festival_year)

        # Business hours (p with class "-hours")
        hours_el = soup.find("p", class_="-hours")
        business_hours = hours_el.get_text(strip=True) if hours_el else None

        # Admission (p with class "-fee")
        fee_el = soup.find("p", class_="-fee")
        price_info = fee_el.get_text(strip=True) if fee_el else None
        is_paid: bool | None = None
        if price_info:
            is_paid = "無料" not in price_info and "Free" not in price_info

        # Description: collect paragraphs from the page body
        description = self._extract_description(soup)

        if start_date:
            raw_description = (
                f"開催日時: {start_date.year}年{start_date.month}月{start_date.day}日\n\n"
                + description
            )
        else:
            raw_description = description

        return Event(
            source_name=self.SOURCE_NAME,
            source_id=f"kgplus_{slug}",
            source_url=link,
            original_language="ja",
            name_ja=name_ja,
            raw_title=name_ja,
            raw_description=raw_description,
            category=["art"],
            start_date=start_date,
            end_date=end_date,
            location_name=location_name,
            location_address=location_address,
            business_hours=business_hours,
            is_paid=is_paid,
            price_info=price_info,
        )

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str:
        """Extract exhibition description paragraphs, capped at 800 chars."""
        # Try the main section first, then fall back to <main>
        container = soup.select_one(".s-exhibition-main") or soup.find("main")
        if not container:
            return ""

        # Remove navigation / footer noise
        for noise_sel in [".gNav", ".gFooter", "nav", "footer"]:
            for el in container.select(noise_sel):
                el.decompose()

        paras = [
            p.get_text(strip=True)
            for p in container.find_all("p")
            if p.get_text(strip=True)
            # Skip the structured metadata paragraphs
            and not any(
                cls in (p.get("class") or [])
                for cls in ["-openclose", "-hours", "-fee", "-access", "-l1"]
            )
        ]
        return "\n".join(paras)[:800].strip()
