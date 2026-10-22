"""Fields that measure how much a scraper extracts (#354).

Shared by ``main.py``, which writes the scrape-time count into
``scraper_runs.notes``, and ``eval_scraper_quality.py``, which compares it with
the stored events. Keep the two in step by importing from here.
"""

from __future__ import annotations

from collections.abc import Mapping
from statistics import median
from typing import Any

from publication_rules import (
    PUBLICATION_NULL_FIELDS,
    PUBLICATION_VENUE_NAME_FIELDS,
    is_pure_publication_record,
)

# Fields a scraper can fill from the source page. Translations, AI annotations
# (category, selection_reason) and derived keys (venue_id, work_id) are left out.
TRACKED_FIELDS = (
    "start_date",
    "end_date",
    "location_name",
    "location_address",
    "business_hours",
    "price_info",
    "is_paid",
    "official_url",
    "organizer",
    "image_url",
    "performers",
)

# Pure publication records keep these intentionally empty (publication policy).
_PUBLICATION_SKIPPED = frozenset(PUBLICATION_NULL_FIELDS) | frozenset(PUBLICATION_VENUE_NAME_FIELDS)


def _value(record: Any, field: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(field)
    return getattr(record, field, None)


def is_filled(value: Any) -> bool:
    """None, blank strings and empty lists are empty; ``False`` is a real answer."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, frozenset)):
        return len(value) > 0
    return True


def applicable_fields(record: Any) -> tuple[str, ...]:
    """TRACKED_FIELDS minus the ones a pure publication keeps empty by policy."""
    if is_pure_publication_record(record):
        return tuple(f for f in TRACKED_FIELDS if f not in _PUBLICATION_SKIPPED)
    return TRACKED_FIELDS


def count_filled(record: Any) -> int:
    return sum(1 for f in applicable_fields(record) if is_filled(_value(record, f)))


def median_filled(records: list[Any]) -> float | None:
    """Median TRACKED_FIELDS filled per record, or None for an empty batch."""
    if not records:
        return None
    return float(median(count_filled(r) for r in records))


def run_notes(events: list[Any]) -> str:
    """Notes string main.py stores on each scraper_runs row.

    ``event_sources`` lists the distinct ``source_name`` values the run produced,
    because the run key (class name) and the events' source_name differ for some
    scrapers, e.g. ``tokyo_art_beat`` vs ``tokyoartbeat``.
    """
    med = median_filled(events)
    sources = sorted({str(_value(e, "source_name")) for e in events if _value(e, "source_name")})
    parts = [f"parsed_fields_median={med:g}" if med is not None else "parsed_fields_median=none"]
    if sources:
        parts.append(f"event_sources={'|'.join(sources)}")
    return ", ".join(parts)
