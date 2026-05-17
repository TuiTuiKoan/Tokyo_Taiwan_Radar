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
from source_exclusions import load_exclusions, event_matches_exclusion, record_hits

logger = logging.getLogger(__name__)

_client: Client | None = None


# Tier 1 controlled vocabularies (mirror annotator.py — keep in sync).
_VALID_ORGANIZER_TYPES = frozenset([
    "government", "semi_official", "cultural_institution", "academic",
    "commercial_brand", "independent_venue", "civic_group", "media", "unknown",
])
_VALID_EVENT_FORMS = frozenset([
    "exhibition", "screening", "lecture", "performance", "market", "workshop",
    "conference", "networking", "screening_with_talk", "tour", "competition", "other",
])
_VALID_PRIMARY_LANGUAGES = frozenset(["ja", "zh", "en", "mixed"])

# Tier 2 schema.org Event JSON-LD whitelists (migration 037).
_VALID_EVENT_STATUSES = frozenset({"scheduled", "cancelled", "postponed", "rescheduled"})
import re as _re_mod_db
_CURRENCY_RE_DB = _re_mod_db.compile(r'^[A-Z]{3}$')


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
    row: dict[str, Any] = {
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
        "scraped_at": datetime.utcnow().isoformat() + "Z",
    }
    # Only include official_url when set — omitting preserves the existing DB value.
    # Requires migration 018_official_url.sql to be applied before writing.
    if event.official_url is not None:
        row["official_url"] = event.official_url
    # Only include name_ja_locked when True — omitting preserves the default (false).
    # Requires migration 034_name_ja_locked.sql to be applied before writing.
    if event.name_ja_locked:
        row["name_ja_locked"] = True

    # Tier 1 fields (migration 035). Only write keys the scraper explicitly set,
    # so omitted fields don't clobber annotator-filled values on re-upsert.
    if event.organizer is not None:
        row["organizer"] = event.organizer
    if event.co_organizers:
        row["co_organizers"] = [s for s in event.co_organizers if isinstance(s, str)]
    if event.sponsors:
        row["sponsors"] = [s for s in event.sponsors if isinstance(s, str)]
    if event.organizer_type:
        filtered = [v for v in event.organizer_type if v in _VALID_ORGANIZER_TYPES]
        if filtered:
            row["organizer_type"] = filtered
    if event.event_form:
        filtered = [v for v in event.event_form if v in _VALID_EVENT_FORMS]
        if filtered:
            row["event_form"] = filtered
    if event.primary_language is not None and event.primary_language in _VALID_PRIMARY_LANGUAGES:
        row["primary_language"] = event.primary_language
    if isinstance(event.has_japanese_support, bool):
        row["has_japanese_support"] = event.has_japanese_support
    if isinstance(event.has_english_support, bool):
        row["has_english_support"] = event.has_english_support

    # Tier 2 fields (migration 037). Whitelist event_status / price_currency;
    # organizer_url and price_amount pass through (annotator already filtered).
    if event.organizer_url is not None:
        row["organizer_url"] = event.organizer_url
    if event.organizer_zh is not None:
        row["organizer_zh"] = event.organizer_zh
    if event.organizer_en is not None:
        row["organizer_en"] = event.organizer_en
    if event.price_amount is not None:
        row["price_amount"] = event.price_amount
    if isinstance(event.price_currency, str) and _CURRENCY_RE_DB.match(event.price_currency):
        row["price_currency"] = event.price_currency
    if isinstance(event.event_status, str) and event.event_status in _VALID_EVENT_STATUSES:
        row["event_status"] = event.event_status
    if event.performer is not None:
        row["performer"] = event.performer
    if event.performers:
        row["performers"] = event.performers
    if event.performers_zh:
        row["performers_zh"] = event.performers_zh
    if event.performers_en:
        row["performers_en"] = event.performers_en
    if event.director is not None:
        row["director"] = event.director
    if event.performer_zh is not None:
        row["performer_zh"] = event.performer_zh
    if event.performer_en is not None:
        row["performer_en"] = event.performer_en
    if event.director_zh is not None:
        row["director_zh"] = event.director_zh
    if event.director_en is not None:
        row["director_en"] = event.director_en
    if event.image_url is not None:
        row["image_url"] = event.image_url

    return row


def _populate_entity_fks(client: Client, rows: list[dict]) -> None:
    """
    Mutate `rows` in-place: set `organizer_id` / `venue_id` when a matching
    `organizers` / `venues` entity already exists (either as canonical_name_ja
    or alias). Missing entity → leave FK unset; raw text columns (organizer,
    location_name) are unaffected.

    Entity tables come from migration 050 (Tier 2 normalization). On older
    databases without the tables, the lookup query fails silently and the
    function becomes a no-op — keeping the upsert pipeline backwards-compatible.
    """
    if not rows:
        return
    organizer_strs = sorted({r["organizer"] for r in rows
                             if isinstance(r.get("organizer"), str) and r["organizer"].strip()})
    venue_strs = sorted({r["location_name"] for r in rows
                         if isinstance(r.get("location_name"), str) and r["location_name"].strip()})

    org_lookup: dict[str, str] = {}
    if organizer_strs:
        try:
            # Match on canonical_name_ja first.
            resp = (
                client.table("organizers")
                .select("id,canonical_name_ja,aliases")
                .in_("canonical_name_ja", organizer_strs)
                .execute()
            )
            for r in resp.data or []:
                org_lookup[r["canonical_name_ja"]] = r["id"]
            # Then alias hits — separate query per string (PostgREST `cs.{x}`).
            still_missing = [s for s in organizer_strs if s not in org_lookup]
            if still_missing:
                # `aliases @> ARRAY[…]` via `cs` filter on TEXT[] column.
                # One round-trip per string (small N expected — usually < 50/run).
                for s in still_missing:
                    try:
                        ar = (
                            client.table("organizers")
                            .select("id")
                            .contains("aliases", [s])
                            .limit(1)
                            .execute()
                        )
                        if ar.data:
                            org_lookup[s] = ar.data[0]["id"]
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug("organizer entity lookup skipped (table may not exist yet): %s", exc)

    venue_lookup: dict[str, str] = {}
    if venue_strs:
        try:
            resp = (
                client.table("venues")
                .select("id,canonical_name_ja,aliases")
                .in_("canonical_name_ja", venue_strs)
                .execute()
            )
            for r in resp.data or []:
                venue_lookup[r["canonical_name_ja"]] = r["id"]
            still_missing = [s for s in venue_strs if s not in venue_lookup]
            if still_missing:
                for s in still_missing:
                    try:
                        ar = (
                            client.table("venues")
                            .select("id")
                            .contains("aliases", [s])
                            .limit(1)
                            .execute()
                        )
                        if ar.data:
                            venue_lookup[s] = ar.data[0]["id"]
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug("venue entity lookup skipped (table may not exist yet): %s", exc)

    # Mutate rows in-place.
    org_hits = 0
    venue_hits = 0
    for r in rows:
        org = r.get("organizer")
        if isinstance(org, str) and org in org_lookup:
            r["organizer_id"] = org_lookup[org]
            org_hits += 1
        loc = r.get("location_name")
        if isinstance(loc, str) and loc in venue_lookup:
            r["venue_id"] = venue_lookup[loc]
            venue_hits += 1
    if org_hits or venue_hits:
        logger.info("Entity FK lookup: organizer_id matched %d row(s); venue_id matched %d row(s).",
                    org_hits, venue_hits)


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


def get_event_id_by_source(source_name: str, source_id: str) -> str | None:
    """Look up event UUID by (source_name, source_id). Returns None if not found."""
    try:
        res = (
            _get_client()
            .table("events")
            .select("id")
            .eq("source_name", source_name)
            .eq("source_id", source_id)
            .limit(1)
            .execute()
        )
        return res.data[0]["id"] if res.data else None
    except Exception as exc:
        logger.warning("get_event_id_by_source(%s, %s) failed: %s", source_name, source_id, exc)
        return None


def _auto_lock_location(client, eid_to_event: dict) -> None:
    """Auto-lock scraper-provided location fields so annotator cannot overwrite."""
    import json
    fc_records = []
    for eid, event in eid_to_event.items():
        if not event.location_name:
            continue
        for field, value in [
            ("location_name",        event.location_name),
            ("location_address",     event.location_address),
            ("location_prefectures", event.location_prefectures),
        ]:
            if value is None or value == []:
                continue
            corrected = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
            fc_records.append({"event_id": eid, "field_name": field, "corrected_value": corrected})
    if not fc_records:
        return
    try:
        client.table("field_corrections").upsert(
            fc_records,
            on_conflict="event_id,field_name",
            ignore_duplicates=True,
        ).execute()
        logger.info("Auto-locked location fields for %d new event(s).", len(eid_to_event))
    except Exception as exc:
        logger.warning("Auto-lock location FC failed (non-critical): %s", exc)


def _build_movie_extend_row(event: Event, existing_state: dict) -> dict | None:
    """
    Build a partial-update row for a movie event that already exists in DB.

    Preserves first-observed start_date (MIN) and extends end_date (MAX),
    refreshing only raw_description, business_hours, and dates. Other fields
    (name_*, description_*, category, location_*, etc.) are intentionally
    excluded — those are owned by the annotator and protected by
    field_corrections (P3.2 invariant).

    annotation_status is flipped to 'pending' iff raw_description actually
    changed, so the annotator re-runs translation on the new schedule text.

    Returns None if nothing meaningful would change.
    """
    new_start = _dt_iso(event.start_date)
    new_end = _dt_iso(event.end_date)
    old_start = existing_state.get("start_date")
    old_end = existing_state.get("end_date")
    old_desc = (existing_state.get("raw_description") or "").strip()
    new_desc = (event.raw_description or "").strip()

    # MIN(existing, scraped) — prefer non-None; ISO 8601 strings sort chronologically.
    if old_start and new_start:
        merged_start = min(old_start, new_start)
    else:
        merged_start = old_start or new_start

    # MAX(existing, scraped)
    if old_end and new_end:
        merged_end = max(old_end, new_end)
    else:
        merged_end = old_end or new_end

    desc_changed = new_desc != old_desc
    start_changed = merged_start != old_start
    end_changed = merged_end != old_end
    hours_changed = (event.business_hours or "") != (existing_state.get("business_hours") or "")

    if not (desc_changed or start_changed or end_changed or hours_changed):
        return None

    row: dict[str, Any] = {
        "source_name": event.source_name,
        "source_id": event.source_id,
        "raw_description": event.raw_description,
        "business_hours": event.business_hours,
        "start_date": merged_start,
        "end_date": merged_end,
        "scraped_at": datetime.now().isoformat(),
    }
    if desc_changed:
        row["annotation_status"] = "pending"
    return row


def upsert_events(events: list[Event], force_keys: set[tuple[str, str]] | None = None) -> list[str]:
    """
    Insert or update events in the database.
    Uses (source_name, source_id) as the unique conflict key.

    Behaviour per event:
      1. Admin-deactivated (is_active=false) → always skip; never re-activate.
      2. Already in DB + force_rescrape=true in DB (or key in force_keys arg) →
         full overwrite of all fields; annotation_status reset to 'pending';
         force_rescrape reset to false.
      3. Already in DB, not forced → skip entirely (idempotent scraper).
      4. New event (not yet in DB) → insert normally.

    force_keys: optional set of (source_name, source_id) tuples that the caller
                (e.g. --rescrape-ids CLI flag) wants to force-overwrite this run,
                in addition to events with force_rescrape=true in the DB.

    Returns:
        List of UUIDs for newly-inserted events (not force-updates, not skipped).
        Used by callers to submit fresh URLs to IndexNow.
    """
    if not events:
        return []

    client = _get_client()
    force_keys = force_keys or set()

    # ── Pre-filter: source_exclusions pattern match ───────────────────────
    try:
        _source_names_for_excl = list({e.source_name for e in events})
        rules_by_source = load_exclusions(client, _source_names_for_excl)
        if rules_by_source:
            kept: list = []
            hit_records: list[dict] = []
            for e in events:
                rules = rules_by_source.get(e.source_name) or []
                matched = event_matches_exclusion(e, rules) if rules else None
                if matched:
                    hit_records.append({
                        "rule_id": matched["id"],
                        "raw_title": getattr(e, "raw_title", None),
                        "source_name": e.source_name,
                    })
                else:
                    kept.append(e)
            if hit_records:
                logger.info(
                    "source_exclusions filtered %d event(s) across %d rule(s)",
                    len(hit_records),
                    len({h["rule_id"] for h in hit_records}),
                )
                record_hits(client, hit_records)
                events = kept
    except Exception as exc:
        logger.warning("source_exclusions pre-filter failed (skipping): %s", exc)
    # ── End pre-filter ────────────────────────────────────────────────────

    # One query per source_name: fetch is_active, annotation_status, force_rescrape
    blocked_keys: set[tuple[str, str]] = set()    # admin-deactivated (is_active=false)
    reviewed_keys: set[tuple[str, str]] = set()   # human-reviewed — fully protected
    existing_keys: set[tuple[str, str]] = set()   # any row that already exists in DB
    db_force_keys: set[tuple[str, str]] = set()   # rows with force_rescrape=true in DB
    # Movie extend: for existing rows whose category contains 'movie', we need
    # the current start_date/end_date/raw_description/business_hours to compute
    # MIN(start)/MAX(end) and detect description changes.
    existing_movie_state: dict[tuple[str, str], dict] = {}

    source_names = list({e.source_name for e in events})
    try:
        for sn in source_names:
            resp = (
                client.table("events")
                .select(
                    "source_name,source_id,is_active,annotation_status,force_rescrape,"
                    "category,start_date,end_date,raw_description,business_hours"
                )
                .eq("source_name", sn)
                .execute()
            )
            for row in (resp.data or []):
                key = (row["source_name"], row["source_id"])
                existing_keys.add(key)
                if not row.get("is_active"):
                    blocked_keys.add(key)
                if row.get("annotation_status") == "reviewed":
                    reviewed_keys.add(key)
                if row.get("force_rescrape"):
                    db_force_keys.add(key)
                if "movie" in (row.get("category") or []):
                    existing_movie_state[key] = {
                        "start_date": row.get("start_date"),
                        "end_date": row.get("end_date"),
                        "raw_description": row.get("raw_description"),
                        "business_hours": row.get("business_hours"),
                    }
    except Exception as exc:
        logger.warning("Could not fetch existing events (skipping filter): %s", exc)

    all_force_keys = db_force_keys | force_keys

    # Classify incoming events
    new_rows: list[dict] = []       # brand-new events → insert
    force_rows: list[dict] = []     # forced re-scrape → full overwrite
    extend_rows: list[dict] = []    # movie-extend partial update (preserve first-seen start_date)

    for e in events:
        key = (e.source_name, e.source_id)
        if key in blocked_keys:
            continue  # never re-activate admin-deactivated events
        if key in reviewed_keys:
            continue  # human-reviewed events are fully protected — skip even if force_rescrape=true
        row = _event_to_row(e)
        if key in existing_keys:
            if key in all_force_keys:
                force_rows.append(row)
            elif key in existing_movie_state and "movie" in (e.category or []):
                # Movie-extend: partial update only — preserves first-observed start_date,
                # extends end_date to cover ongoing run. Does NOT touch any P3.2-protected
                # fields (name_*, description_*, category, location_*, etc.) by construction.
                extend_row = _build_movie_extend_row(e, existing_movie_state[key])
                if extend_row:
                    extend_rows.append(extend_row)
            # else: already in DB, not forced, not extendable → skip (idempotent)
        else:
            new_rows.append(row)

    skipped_deactivated = sum(
        1 for e in events if (e.source_name, e.source_id) in blocked_keys
    )
    skipped_reviewed = sum(
        1 for e in events if (e.source_name, e.source_id) in reviewed_keys
    )
    extended_keys = {(r["source_name"], r["source_id"]) for r in extend_rows}
    skipped_existing = sum(
        1 for e in events
        if (e.source_name, e.source_id) in existing_keys
        and (e.source_name, e.source_id) not in blocked_keys
        and (e.source_name, e.source_id) not in reviewed_keys
        and (e.source_name, e.source_id) not in all_force_keys
        and (e.source_name, e.source_id) not in extended_keys
    )

    if skipped_deactivated:
        logger.info("Skipped %d admin-deactivated event(s) — will not re-activate.", skipped_deactivated)
    if skipped_reviewed:
        logger.info("Skipped %d human-reviewed event(s) — fully protected from overwrite.", skipped_reviewed)
    if skipped_existing:
        logger.info(
            "Skipped %d already-scraped event(s) — use force_rescrape=true to overwrite.",
            skipped_existing,
        )
    if force_rows:
        logger.info("Force-re-scraping %d event(s) (force_rescrape=true).", len(force_rows))
    if extend_rows:
        logger.info("Movie-extending %d event(s) (preserve start, extend end).", len(extend_rows))
    if new_rows:
        logger.info("Inserting %d new event(s).", len(new_rows))

    all_rows = new_rows + force_rows
    if not all_rows and not extend_rows:
        return []

    # Tier 2: populate organizer_id / venue_id FKs from `organizers` / `venues`
    # entity tables (migration 050). Raw text columns are preserved — this only
    # adds FK references when an existing canonical/alias matches.
    _populate_entity_fks(client, all_rows)

    # P3.2: For force_rows, strip any fields that have a human correction in field_corrections.
    # reviewed events are already skipped above; this protects annotated events that have
    # had partial admin corrections from being overwritten on force-rescrape.
    if force_rows:
        try:
            # One batch query: get (source_id → event_id) for all force rows.
            force_source_ids_list = [r["source_id"] for r in force_rows]
            id_map_res = (
                client.table("events")
                .select("id,source_id")
                .in_("source_id", force_source_ids_list)
                .execute()
            )
            src_to_eid: dict[str, str] = {
                row["source_id"]: row["id"] for row in (id_map_res.data or [])
            }
            event_uuids = list(src_to_eid.values())

            if event_uuids:
                fc_res = (
                    client.table("field_corrections")
                    .select("event_id,field_name")
                    .in_("event_id", event_uuids)
                    .execute()
                )
                # Build: event_id → set of protected column names
                eid_protected: dict[str, set[str]] = {}
                for fc in (fc_res.data or []):
                    eid_protected.setdefault(fc["event_id"], set()).add(fc["field_name"])

                if eid_protected:
                    # Invert to source_id → set of protected columns
                    eid_to_src = {v: k for k, v in src_to_eid.items()}
                    src_protected: dict[str, set[str]] = {
                        eid_to_src[eid]: cols
                        for eid, cols in eid_protected.items()
                        if eid in eid_to_src
                    }
                    scrubbed = 0
                    for row in force_rows:
                        for col in src_protected.get(row["source_id"], set()):
                            if col in row:
                                del row[col]
                                scrubbed += 1
                    if scrubbed:
                        logger.info(
                            "Stripped %d field_corrections-protected column(s) from %d force row(s).",
                            scrubbed, len(force_rows),
                        )
        except Exception as fc_exc:
            logger.debug("field_corrections check for force_rows skipped: %s", fc_exc)

    new_event_ids: list[str] = []
    if all_rows:
        try:
            resp = client.table("events").upsert(all_rows, on_conflict="source_name,source_id").execute()
            logger.info("Upserted %d events to Supabase.", len(all_rows))
            # Collect IDs of newly-inserted events only (not force-updates)
            # Supabase returns the upserted rows — match source_id against new_rows
            new_source_ids = {r["source_id"] for r in new_rows}
            for row in (resp.data or []):
                if row.get("source_id") in new_source_ids and row.get("id"):
                    new_event_ids.append(row["id"])
            # ── Auto-lock scraper-provided location fields ────────────────────
            new_src_to_event = {
                e.source_id: e for e in events
                if (e.source_name, e.source_id) not in existing_keys
                and (e.source_name, e.source_id) not in blocked_keys
                and (e.source_name, e.source_id) not in reviewed_keys
                and e.location_name
            }
            if new_src_to_event:
                src_to_eid = {
                    row["source_id"]: row["id"]
                    for row in (resp.data or [])
                    if row.get("source_id") in new_src_to_event and row.get("id")
                }
                eid_to_event = {eid: new_src_to_event[src] for src, eid in src_to_eid.items()}
                _auto_lock_location(client, eid_to_event)
        except Exception as exc:
            logger.error("Failed to upsert events: %s", exc)
            raise

    # Movie-extend partial updates — separate pass after main upsert.
    # By construction these rows touch only raw_description, business_hours,
    # start_date, end_date, scraped_at, annotation_status — never any
    # field_corrections-protected column, so no P3.2 scrubbing is needed.
    # We use UPDATE (not upsert) because the row is guaranteed to exist and
    # the partial payload would otherwise violate NOT NULL constraints
    # (e.g. source_url) on insert-fallback.
    if extend_rows:
        try:
            for row in extend_rows:
                sn = row.pop("source_name")
                sid = row.pop("source_id")
                (
                    client.table("events")
                    .update(row)
                    .eq("source_name", sn)
                    .eq("source_id", sid)
                    .execute()
                )
            logger.info("Movie-extended %d event(s).", len(extend_rows))
        except Exception as exc:
            logger.error("Failed to apply movie-extend updates: %s", exc)
            raise

    # After upserting forced events: reset force_rescrape=false, annotation_status='pending'
    if force_rows:
        force_source_ids = [r["source_id"] for r in force_rows]
        try:
            (
                client.table("events")
                .update({"force_rescrape": False, "annotation_status": "pending"})
                .in_("source_id", force_source_ids)
                .execute()
            )
            logger.info(
                "Reset force_rescrape and annotation_status for %d event(s).",
                len(force_rows),
            )
        except Exception as exc:
            logger.warning("Could not reset force_rescrape flag: %s", exc)

    # Auto-clear force_rescrape for annotator-generated sub-events (_sub suffix).
    # Sub-events are produced by the annotator, not scrapers — their source_ids
    # (e.g. "abc123_sub1") never appear in scraper output, so they can never be
    # matched in force_rows above and would stay stuck indefinitely.
    # Instead we trigger re-annotation by resetting annotation_status='pending'.
    try:
        sub_cleanup = (
            client.table("events")
            .update({"force_rescrape": False, "annotation_status": "pending"})
            .in_("source_name", source_names)
            .eq("force_rescrape", True)
            .like("source_id", "%_sub%")
            .execute()
        )
        if sub_cleanup.data:
            logger.info(
                "Auto-cleared force_rescrape for %d annotator-generated sub-event(s) "
                "(re-annotation triggered instead of re-scrape).",
                len(sub_cleanup.data),
            )
    except Exception as exc:
        logger.warning("Could not auto-clear sub-event force_rescrape flags: %s", exc)

    return new_event_ids

