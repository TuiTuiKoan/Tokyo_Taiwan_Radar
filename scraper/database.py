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
        "raw_title": event.raw_title,
        "raw_description": event.raw_description,
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

    Admin-deactivated events (is_active = false) are never overwritten by the
    scraper — once an admin disables an event it stays disabled across runs.

    Already-annotated events (annotation_status = 'annotated') have their
    human-correctable fields protected: name_ja, location_name,
    location_address, and business_hours are NOT overwritten on subsequent
    scraper runs. Only raw_title, raw_description, start_date, end_date,
    source_url, is_paid, and price_info are updated.
    """
    if not events:
        return

    client = _get_client()

    # Fetch all (source_name, source_id) pairs that have been admin-deactivated
    # so we don't accidentally re-activate them on the next scraper run.
    blocked_keys: set[tuple[str, str]] = set()
    # Also track which keys are already annotated so we can protect their fields.
    annotated_keys: set[tuple[str, str]] = set()
    source_names = list({e.source_name for e in events})
    try:
        for sn in source_names:
            resp = (
                client.table("events")
                .select("source_name,source_id,is_active,annotation_status")
                .eq("source_name", sn)
                .execute()
            )
            for row in (resp.data or []):
                key = (row["source_name"], row["source_id"])
                if not row.get("is_active"):
                    blocked_keys.add(key)
                if row.get("annotation_status") == "annotated":
                    annotated_keys.add(key)
    except Exception as exc:
        logger.warning("Could not fetch deactivated/annotated events (skipping filter): %s", exc)

    rows = [_event_to_row(e) for e in events
            if (e.source_name, e.source_id) not in blocked_keys]

    skipped = len(events) - len(rows)
    if skipped:
        logger.info("Skipped %d admin-deactivated event(s) — will not re-activate.", skipped)

    if not rows:
        return

    # For already-annotated events, strip out the human-correctable fields so
    # the scraper doesn't overwrite manual corrections on every run.
    # Fields protected: name_ja, location_name, location_address, business_hours,
    #                   category (human corrections in category_corrections table).
    # Fields still updated: raw_title, raw_description, start_date, end_date,
    #                       source_url, is_paid, price_info.
    _PROTECTED_FIELDS = {"name_ja", "location_name", "location_address", "business_hours", "category"}
    protected_count = 0
    for r in rows:
        key = (r["source_name"], r["source_id"])
        if key in annotated_keys:
            for field in _PROTECTED_FIELDS:
                r.pop(field, None)
            protected_count += 1
    if protected_count:
        logger.info(
            "Protected human-correctable fields for %d annotated event(s).",
            protected_count,
        )

    rows = [_event_to_row(e) for e in events
            if (e.source_name, e.source_id) not in blocked_keys]

    skipped = len(events) - len(rows)
    if skipped:
        logger.info("Skipped %d admin-deactivated event(s) — will not re-activate.", skipped)

    if not rows:
        return

    # Preserve existing categories: if the incoming row has an empty category list
    # but the DB already has a non-empty category, keep the DB value.
    empty_cat_rows = [r for r in rows if not r.get("category")]
    if empty_cat_rows:
        try:
            existing_map: dict[tuple[str, str], list] = {}
            for sn in {r["source_name"] for r in empty_cat_rows}:
                resp = (
                    client.table("events")
                    .select("source_name,source_id,category")
                    .eq("source_name", sn)
                    .execute()
                )
                for row in (resp.data or []):
                    if row.get("category"):
                        existing_map[(row["source_name"], row["source_id"])] = row["category"]
            preserved = 0
            for r in rows:
                if not r.get("category"):
                    key = (r["source_name"], r["source_id"])
                    if key in existing_map:
                        r["category"] = existing_map[key]
                        preserved += 1
            if preserved:
                logger.info(
                    "Preserved existing category for %d event(s) (scraper returned empty list).",
                    preserved,
                )
        except Exception as exc:
            logger.warning("Could not preserve existing categories: %s", exc)

    try:
        client.table("events").upsert(rows, on_conflict="source_name,source_id").execute()
        logger.info("Upserted %d events to Supabase.", len(rows))
    except Exception as exc:
        logger.error("Failed to upsert events: %s", exc)
        raise


def archive_ended_events(dry_run: bool = False) -> int:
    """
    Auto-archive events whose end_date has passed.

    Sets is_active=False for events where:
      - is_active = True
      - end_date is NOT NULL
      - end_date < yesterday 00:00 UTC  (1-day grace period)

    Events with end_date IS NULL are never archived automatically.
    Returns the count of archived events.
    """
    from datetime import timezone, timedelta

    client = _get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00+00:00")

    try:
        result = (
            client.table("events")
            .select("id, name_ja, end_date, source_name")
            .eq("is_active", True)
            .not_.is_("end_date", "null")
            .lt("end_date", cutoff)
            .execute()
        )
    except Exception as exc:
        logger.error("[archive] Failed to query ended events: %s", exc)
        return 0

    ended = result.data or []
    if not ended:
        logger.info("[archive] No ended events to archive.")
        return 0

    if dry_run:
        logger.info("[archive] DRY RUN: would archive %d ended event(s).", len(ended))
        for ev in ended[:10]:
            logger.info(
                "  - [%s] %s (end: %s)",
                ev.get("source_name", "?"),
                (ev.get("name_ja") or ev["id"])[:60],
                ev.get("end_date", "?"),
            )
        return len(ended)

    ids = [ev["id"] for ev in ended]
    try:
        client.table("events").update({"is_active": False}).in_("id", ids).execute()
        logger.info("[archive] Archived %d ended event(s).", len(ended))
    except Exception as exc:
        logger.error("[archive] Failed to archive events: %s", exc)
        return 0

    return len(ended)
