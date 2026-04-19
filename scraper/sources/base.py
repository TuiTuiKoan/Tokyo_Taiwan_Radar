from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


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

    # List of categories from: movie, book, creator, shop, brand,
    # nature, tech, tourism, culture, literature
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


class BaseScraper(ABC):
    """All source scrapers must implement this interface."""

    @abstractmethod
    def scrape(self) -> list[Event]:
        """Scrape the source and return a list of structured Event objects."""
        ...
