import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared scraper utilities
# ---------------------------------------------------------------------------

_REF_FETCH_HEADERS = {"User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"}

# ---------------------------------------------------------------------------
# URL extraction helpers for aggregator / thin-pointer sources
# ---------------------------------------------------------------------------

_FIRST_PARTY_SIGNAL_RE = re.compile(
    r'(?:🔗|詳細|申込|公式|詳細・申込)[^\n]*?(https?://[^\s\u3000\u300d\uff09\)「」\n]+)',
    re.IGNORECASE,
)
_URL_BARE_RE = re.compile(r'https?://[^\s\u3000\u300d\uff09\)「」\n]+')
_SIGNUP_HOSTS: frozenset[str] = frozenset({
    "peatix.com", "forms.gle", "google.com", "docs.google.com", "linktr.ee",
    "bit.ly", "t.co",
})


def fetch_ref_text(ref_url: str, max_chars: int = 3000, verify_ssl: bool = True) -> Optional[str]:
    """Fetch an external reference page and return its plain-text body.

    Use this when a scraper encounters a **thin pointer article** — a page
    that provides only a short summary + an external URL, with no usable
    event date, venue, or description of its own.  Appending the fetched
    text to raw_description gives the annotator's GPT enough context to
    extract correct dates, categories, and descriptions.

    verify_ssl: set to False for .edu.tw/.gov.tw domains that commonly use
        self-signed or SKI-deficient certificates. Use tw_insecure_domain()
        to detect such domains automatically.

    Returns None on any network error or if the fetched content is too
    short (< 200 chars) to be useful.

    Selector priority: main > article > body (returns first with ≥200 chars).
    """
    try:
        import urllib3
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        resp = requests.get(ref_url, headers=_REF_FETCH_HEADERS, timeout=15, verify=verify_ssl)
        resp.raise_for_status()
    except Exception as exc:
        logger.debug("fetch_ref_text: failed %s: %s", ref_url[:80], exc)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    for selector in ["main", "article", "body"]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(" ", strip=True)
            if len(text) > 200:
                return text[:max_chars]
    return None


def extract_first_party_url(body: str, exclude_hosts: tuple[str, ...] = ("note.com",)) -> Optional[str]:
    """From a text body, extract the first URL that looks like a first-party
    official/detail page.

    Prioritises URLs near signal words (🔗 詳細 / 申込 / 公式).
    Excludes the source host (e.g. note.com) and pure signup-platform hosts
    (peatix, forms.gle, google, linktr.ee …).

    Returns None if no suitable URL is found.
    """

    def _is_valid(url: str) -> bool:
        try:
            host = urlparse(url).netloc.lower().lstrip("www.")
        except Exception:
            return False
        if any(host == h or host.endswith("." + h) for h in exclude_hosts):
            return False
        if host in _SIGNUP_HOSTS:
            return False
        return bool(host)

    # Priority: near signal words
    for m in _FIRST_PARTY_SIGNAL_RE.finditer(body):
        url = m.group(1).rstrip("。、）》」")
        if _is_valid(url):
            return url
    # Fallback: any bare URL
    for m in _URL_BARE_RE.finditer(body):
        url = m.group(0).rstrip("。、）》」")
        if _is_valid(url):
            return url
    return None


def tw_insecure_domain(url: str) -> bool:
    """Return True for Taiwan gov/edu domains that commonly have self-signed certs.

    These domains often fail requests' default verify=True due to missing Subject
    Key Identifier (SKI) in their TLS certificates. Pass the result as
    ``verify_ssl=not tw_insecure_domain(url)`` to fetch_ref_text().
    """
    host = urlparse(url).netloc.lower()
    return host.endswith(".edu.tw") or host.endswith(".gov.tw")


@dataclass
class Event:
    """Represents a single scraped event before it is saved to the database."""

    source_name: str          # e.g. "taiwan_cultural_center"
    source_id: str            # unique ID within that source (used for dedup)
    source_url: str           # direct link to the original event page
    original_language: str    # "ja" | "zh" | "en"

    name_ja: Optional[str] = None
    name_zh: Optional[str] = None
    name_en: Optional[str] = None

    description_ja: Optional[str] = None
    description_zh: Optional[str] = None
    description_en: Optional[str] = None

    # Values from canonical list: movie, performing_arts, senses, retail, nature,
    # tech, tourism, lifestyle_food, books_media, gender, geopolitics, art, lecture,
    # taiwan_japan, business, academic, competition, report
    category: list[str] = field(default_factory=list)

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    location_name: Optional[str] = None
    location_address: Optional[str] = None
    location_url: Optional[str] = None   # official website of the venue
    location_prefectures: list[str] = field(default_factory=list)
    business_hours: Optional[str] = None

    is_paid: Optional[bool] = None
    price_info: Optional[str] = None
    is_active: bool = True
    parent_event_id: Optional[str] = None

    # Raw layer — original scraped text before AI annotation
    raw_title: Optional[str] = None
    raw_description: Optional[str] = None

    # Set to source_url by official-organiser scrapers; None for aggregators/ticketing.
    # Requires migration 018_official_url.sql to be applied before it is written to DB.
    official_url: Optional[str] = None

    # When True, the annotator preserves name_ja exactly as set by the scraper and
    # does NOT overwrite it with a GPT-generated title. Use for events where name_ja
    # is extracted from a definitive structured source field (e.g. academic 題目:,
    # paper titles, film titles from official programmes). Translations (name_zh,
    # name_en, description_*, category) are still generated normally.
    # Requires migration 034_name_ja_locked.sql.
    name_ja_locked: bool = False

    # Tier 1 consulting-grade fields (migration 035).
    # Scrapers may set these directly when the source provides authoritative values
    # (e.g. taiwan_cultural_center.py knows organizer = "台湾文化センター").
    # Otherwise leave as defaults; the annotator will fill them via GPT extraction.
    organizer: Optional[str] = None
    co_organizers: list[str] = field(default_factory=list)
    sponsors: list[str] = field(default_factory=list)
    organizer_type: list[str] = field(default_factory=list)
    event_form: list[str] = field(default_factory=list)
    primary_language: Optional[str] = None
    has_japanese_support: Optional[bool] = None
    has_english_support: Optional[bool] = None
    has_chinese_support: Optional[bool] = None

    # Tier 2 schema.org Event JSON-LD fields (migration 037).
    organizer_url: Optional[str] = None
    organizer_zh: Optional[str] = None
    organizer_en: Optional[str] = None
    price_amount: Optional[float] = None
    price_currency: Optional[str] = "JPY"
    event_status: Optional[str] = "scheduled"
    performer: Optional[str] = None
    performers: list[str] = field(default_factory=list)
    director: Optional[str] = None
    performer_zh: Optional[str] = None
    performer_en: Optional[str] = None
    performer_url: Optional[str] = None  # performer's official page (Instagram, YouTube, etc.)
    performer_urls: list[str] = field(default_factory=list)  # per-performer URLs, parallel index to performers[]
    director_zh: Optional[str] = None
    director_en: Optional[str] = None
    performers_zh: list[str] = field(default_factory=list)
    performers_en: list[str] = field(default_factory=list)
    image_url: Optional[str] = None  # poster/OGP image URL


def dedup_events(events: list[Event]) -> list[Event]:
    """Remove duplicate events from a single scraper's output.

    Dedup key: (normalized name_ja, start_date.date()).
    Keeps the first occurrence (earliest in the list).
    Annotator-generated sub-events (source_id contains '_sub') are excluded
    from dedup — they are handled separately by the annotator pipeline.
    """
    seen: set[tuple] = set()
    result: list[Event] = []
    for event in events:
        # Sub-events created by annotator are not present at scrape time,
        # but guard against any scraper that generates _sub IDs directly.
        if "_sub" in event.source_id:
            result.append(event)
            continue
        name = (event.name_ja or "").strip().lower()
        date = event.start_date.date() if event.start_date else None
        key = (name, date)
        if name and key in seen:
            logger.warning(
                "Dropping in-source duplicate: %s (%s) — keeping first occurrence",
                event.name_ja,
                event.source_id,
            )
            continue
        if name:
            seen.add(key)
        result.append(event)
    return result


def is_jpro_placeholder_date(dt: Optional[datetime]) -> bool:
    """True if dt is the JPRO 近刊情報 year-end placeholder (MM-DD = 12-31).

    JPRO registers forthcoming books with 12/31 of the registration year when
    the publisher has not yet fixed a release date. NDL Search and 版元ドットコム
    (hanmoto) both inherit this placeholder. Callers should treat it as
    'date undecided' (set start_date/end_date to None) rather than a real date.
    """
    return dt is not None and dt.month == 12 and dt.day == 31


class BaseScraper(ABC):
    """All source scrapers must implement this interface."""

    @abstractmethod
    def scrape(self) -> list[Event]:
        """Scrape the source and return a list of structured Event objects."""
        ...

    def explore(self, url: str) -> dict:
        """Interactive exploration hook for Chrome MCP agents (local dev only).

        Override in a subclass to return a dict of discovered selectors and
        sample data for a given URL.  Not called by the production pipeline.
        Raises NotImplementedError by default so agents know to implement it.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement explore(). "
            "Use a Chrome MCP agent to navigate the page interactively, "
            "then implement this method with the discovered selectors."
        )
