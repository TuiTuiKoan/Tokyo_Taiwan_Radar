"""
Supabase database client for upserting scraped events.

Uses the service role key (bypasses RLS) so the scraper can write freely.
"""

import logging
import os
from datetime import datetime
from typing import Any

from supabase import create_client, Client

from sources.base import Event

logger = logging.getLogger(__name__)

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment."
            )
        _client = create_client(url, key)
    return _client


def _dt_iso(dt: datetime | None) -> str | None:
    """Convert datetime to ISO 8601 string for Supabase."""
    return dt.isoformat() if dt else None


def _event_to_row(event: Event) -> dict[str, Any]:
    """Convert an Event dataclass to a dict matching the Supabase `events` table schema."""
    return {
        "source_name": event.source_name,
        "source_id": event.source_id,
        "source_url": event.source_url,
        "original_language": event.original_language,
        "name_ja": event.name_ja,
        "name_zh": event.name_zh,
        "name_en": event.name_en,
        "description_ja": event.description_ja,
        "description_zh": event.description_zh,
        "description_en": event.description_en,
        "category": event.category,
        "start_date": _dt_iso(event.start_date),
        "end_date": _dt_iso(event.end_date),
        "location_name": event.location_name,
        "location_address": event.location_address,
        "business_hours": event.business_hours,
        "is_paid": event.is_paid,
        "price_info": event.price_info,
        "is_active": event.is_active,
        "parent_event_id": event.parent_event_id,
    }


def find_parent_event_id(name_ja: str | None, source_name: str) -> str | None:
    """
    Try to find a parent event in the database by fuzzy-matching the name.
    For a report like '映画「X」トークイベント レポート', we extract the
    core title (e.g. the text in 『...』 or 「...」 brackets) and search
    for events whose name contains that title.
    """
    import re
    if not name_ja:
        return None

    client = _get_client()

    # Strategy 1: Extract title from brackets like 『X』 or 「X」
    bracket_match = re.search(r'[『「](.+?)[』」]', name_ja)
    if bracket_match:
        title = bracket_match.group(1).strip()
        if len(title) >= 3:
            try:
                result = (
                    client.table("events")
                    .select("id,category")
                    .ilike("name_ja", f"%{title}%")
                    .eq("source_name", source_name)
                    .limit(10)
                    .execute()
                )
                for row in result.data:
                    if "report" in (row.get("category") or []):
                        continue
                    return row["id"]
            except Exception as exc:
                logger.warning("Parent lookup (bracket) failed for '%s': %s", title, exc)

    # Strategy 2: Strip report suffixes and search with shorter fragment
    # Use [\s\u3000]* between chars to handle stray whitespace (e.g. "トー クイベント")
    stripped = re.sub(
        r'[\s\u3000]*(ト[\s]*ー[\s]*ク[\s]*イ[\s]*ベ[\s]*ン[\s]*ト|トークイベント|イベント)?[\s\u3000]*(レ[\s]*ポ[\s]*ー[\s]*ト|レポート|レビュー|報告|まとめ|振り返り|記録|紀錄|recap|report|review).*$',
        '', name_ja, flags=re.IGNORECASE
    ).strip()

    if not stripped or len(stripped) < 4:
        return None

    # Use only the last meaningful segment (after the last dash/hyphen)
    segments = re.split(r'\s*[-\-－—]\s*', stripped)
    search_term = segments[-1].strip() if len(segments) > 1 else stripped
    if len(search_term) < 4:
        search_term = stripped

    try:
        result = (
            client.table("events")
            .select("id,category")
            .ilike("name_ja", f"%{search_term}%")
            .eq("source_name", source_name)
            .limit(10)
            .execute()
        )
        for row in result.data:
            if "report" in (row.get("category") or []):
                continue
            return row["id"]
    except Exception as exc:
        logger.warning("Parent lookup failed for '%s': %s", search_term, exc)

    return None


def upsert_events(events: list[Event]) -> None:
    """
    Insert or update events in the database.
    Uses (source_name, source_id) as the unique conflict key.
    """
    if not events:
        return

    client = _get_client()
    rows = [_event_to_row(e) for e in events]

    try:
        response = (
            client.table("events")
            .upsert(rows, on_conflict="source_name,source_id")
            .execute()
        )
        logger.info("Upserted %d events to Supabase.", len(rows))
    except Exception as exc:
        logger.error("Failed to upsert events: %s", exc)
        raise
