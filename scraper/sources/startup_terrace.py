"""Scraper for Taiwan Startup Terrace (台湾新創競技場).

Taiwan Startup Terrace is a government-backed incubator (Ministry of Economic
Affairs) that organizes international outbound programs for Taiwanese startups,
with a strong focus on Japan-market expansion (GO Japan Mission, SusHi Tech
Tokyo, Fukuoka / Kumamoto programs, KGAP+, etc.).

URL: https://www.startupterrace.tw/en/News_Card2.aspx?n=1678&sms=11665

Strategy:
  1. Fetch the English news listing (PageSize=20, recent MAX_PAGES pages).
  2. Filter cards whose title contains Japan-related keywords (title-only check;
     avoids loading detail pages for irrelevant articles).
  3. For each matching card, fetch the detail page and extract the main content
     from ``.group.page-content``.
  4. start_date = publish date from listing card ``i.mark`` (PostDate).
     The annotator will extract the actual event date from the description body.
  5. Each matching news article → one Event.

Source ID format:
  startup_terrace_{s}   (e.g. startup_terrace_15274)
  where {s} is the news item ID from the URL query param ``s=NNN``.

Note on TLS:
  The site's certificate is missing the Subject Key Identifier extension.
  ``requests`` raises SSLError unless ``verify=False`` is passed.
  InsecureRequestWarning is suppressed at call sites.
"""

import logging
import re
import warnings
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE = "https://www.startupterrace.tw"
_LISTING_URL = _BASE + "/en/News_Card2.aspx?n=1678&sms=11665&PageSize=20&page={page}"
_DETAIL_URL = _BASE + "/en/News_Content.aspx?n=1678&s={sid}"

# Scan the most recent MAX_PAGES × 20 articles
MAX_PAGES = 5

# Articles whose titles do not match are skipped without fetching detail pages
_JAPAN_KW = re.compile(
    r"\bJapan\b|Tokyo|Osaka|Fukuoka|Kyoto|Nagoya|Sapporo"
    r"|SusHi Tech|GO Japan|KGAP|TechGALA Japan|日本|東京",
    re.IGNORECASE,
)

_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en,zh;q=0.9",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(url: str) -> requests.Response:
    """GET with SSL verification disabled (cert missing SKI extension)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return requests.get(url, headers=_HEADERS, timeout=15, verify=False)


def _parse_date(text: str) -> Optional[datetime]:
    """Parse YYYY-MM-DD string → datetime (date-only, midnight)."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _make_absolute(href: str) -> str:
    """Convert a relative href to an absolute URL."""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return f"{_BASE}/en/{href.lstrip('/')}"


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


class StartupTerraceScraper(BaseScraper):
    """Scraper for Taiwan Startup Terrace Japan-related programs."""

    source_name = "startup_terrace"

    def scrape(self) -> list[Event]:
        events: list[Event] = []
        seen_ids: set[str] = set()

        for page in range(1, MAX_PAGES + 1):
            url = _LISTING_URL.format(page=page)
            try:
                resp = _get(url)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("startup_terrace: listing page %d failed: %s", page, exc)
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(".area-figure")
            if not cards:
                logger.debug("startup_terrace: no cards on page %d, stopping", page)
                break

            for card in cards:
                event = self._parse_card(card, seen_ids)
                if event:
                    events.append(event)

        logger.info("startup_terrace: total events scraped = %d", len(events))
        return events

    def _parse_card(self, card, seen_ids: set[str]) -> Optional[Event]:
        """Extract one Event from a listing card, or None if not Japan-related."""
        a = card.select_one("a.div[href]")
        if not a:
            return None

        title = a.get("title", "").strip()
        # Filter by title first — avoids fetching irrelevant detail pages
        if not title or not _JAPAN_KW.search(title):
            return None

        # News ID from href: e.g. News_Content.aspx?n=1678&s=15274
        href = a.get("href", "")
        sid_m = re.search(r"s=(\d+)", href)
        if not sid_m:
            return None
        sid = sid_m.group(1)

        source_id = f"startup_terrace_{sid}"
        if source_id in seen_ids:
            return None
        seen_ids.add(source_id)

        # Publish date from listing card
        date_el = card.select_one("i.mark")
        date_str = date_el.get_text(strip=True) if date_el else ""
        start_date = _parse_date(date_str)

        detail_url = _make_absolute(href)
        raw_description = self._fetch_detail(detail_url)

        # Prepend publish date so the annotator can see when this was posted
        if start_date and raw_description:
            date_prefix = f"公開日: {start_date.strftime('%Y年%m月%d日')}\n\n"
            raw_description = date_prefix + raw_description

        logger.info("startup_terrace: added s=%s  %s", sid, title[:60])
        return Event(
            source_name=self.source_name,
            source_id=source_id,
            source_url=detail_url,
            original_language="en",
            name_en=title,
            raw_title=title,
            raw_description=raw_description,
            start_date=start_date,
            official_url=detail_url,
            organizer="Taiwan Startup Terrace",
            organizer_en="Taiwan Startup Terrace",
            organizer_zh="台湾新創競技場",
            organizer_url="https://www.startupterrace.tw",
            organizer_type=["government"],
            event_form=["mission"],
            category=["business", "tech"],
        )

    def _fetch_detail(self, url: str) -> Optional[str]:
        """Fetch detail page and return ``.group.page-content`` text."""
        try:
            resp = _get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            content_el = soup.select_one(".group.page-content")
            if content_el:
                return content_el.get_text("\n", strip=True)
        except Exception as exc:
            logger.warning("startup_terrace: detail page %s failed: %s", url, exc)
        return None
