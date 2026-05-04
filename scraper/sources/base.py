from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared scraper utilities
# ---------------------------------------------------------------------------

_REF_FETCH_HEADERS = {"User-Agent": "TokyoTaiwanRadar/1.0 (+https://tokyotaiwanradar.com)"}


def fetch_ref_text(ref_url: str, max_chars: int = 3000) -> Optional[str]:
    """Fetch an external reference page and return its plain-text body.

    Use this when a scraper encounters a **thin pointer article** — a page
    that provides only a short summary + an external URL, with no usable
    event date, venue, or description of its own.  Appending the fetched
    text to raw_description gives the annotator's GPT enough context to
    extract correct dates, categories, and descriptions.

    Returns None on any network error or if the fetched content is too
    short (< 200 chars) to be useful.

    Selector priority: main > article > body (returns first with ≥200 chars).
    """
    try:
        resp = requests.get(ref_url, headers=_REF_FETCH_HEADERS, timeout=15)
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
    price_amount: Optional[float] = None
    price_currency: Optional[str] = "JPY"
    event_status: Optional[str] = "scheduled"
    performer: Optional[str] = None


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
