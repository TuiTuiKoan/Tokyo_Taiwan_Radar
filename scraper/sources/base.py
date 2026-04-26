from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


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
