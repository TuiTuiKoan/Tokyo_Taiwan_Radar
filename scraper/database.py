"""
Supabase database client for upserting scraped events.

Uses the service role key (bypasses RLS) so the scraper can write freely.
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from supabase import create_client, Client

from publication_rules import (
    PUBLICATION_NULL_FIELDS,
    PUBLICATION_VENUE_NAME_FIELDS,
    is_pure_publication_record,
    validated_registry_homepage,
)
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
    "conference", "networking", "screening_with_talk", "tour", "competition",
    "tasting", "broadcast", "study_abroad", "publication", "other",
])
_VALID_PRIMARY_LANGUAGES = frozenset(["ja", "zh", "en", "mixed"])

# Tier 2 schema.org Event JSON-LD whitelists (migration 037).
_VALID_EVENT_STATUSES = frozenset({"scheduled", "cancelled", "postponed", "rescheduled"})
import re as _re_mod_db
_CURRENCY_RE_DB = _re_mod_db.compile(r'^[A-Z]{3}$')
_VENUE_SELECT_FIELDS = (
    "id,canonical_name_ja,canonical_name_zh,canonical_name_en,address,"
    "prefecture,prefectures,homepage,aliases,is_authoritative,"
    "is_multi_venue,business_hours"
)
_VENUE_PROPAGATED_FIELDS = (
    "venue_id",
    "location_name",
    "location_name_zh",
    "location_name_en",
    "location_address",
    "location_address_zh",
    "location_address_en",
    "location_prefectures",
    "location_url",
    "business_hours",
)


def _field_correction_value(field: str, value: Any) -> Any:
    if value == "" and field in {
        "venue_id",
        "location_address",
        "location_address_zh",
        "location_address_en",
        "location_url",
        "business_hours",
    }:
        return None
    if field == "location_prefectures" and isinstance(value, str):
        if not value:
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        return parsed
    return value


def _record_fc_override_attempt(client: Client, fc: dict[str, Any], attempted: Any) -> None:
    try:
        now_iso = datetime.now(UTC).isoformat()
        attempted_value = (
            json.dumps(attempted, ensure_ascii=False, sort_keys=True)
            if isinstance(attempted, (list, dict))
            else str(attempted)
        )
        update = {
            "last_override_attempted_at": now_iso,
            "override_attempted_value": attempted_value[:1000],
            "override_attempt_count": (fc.get("override_attempt_count") or 0) + 1,
        }
        if not fc.get("first_override_attempted_at"):
            update["first_override_attempted_at"] = now_iso
        client.table("field_corrections").update(update).eq("id", fc["id"]).execute()
        fc.update(update)
    except Exception as exc:
        logger.debug(
            "field_corrections venue override-log skipped for %s/%s: %s",
            fc.get("event_id"),
            fc.get("field_name"),
            exc,
        )


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


def _apply_pure_publication_policy(row: dict[str, Any]) -> bool:
    if not is_pure_publication_record(row):
        return False
    for field in PUBLICATION_NULL_FIELDS:
        row[field] = None
    for field in PUBLICATION_VENUE_NAME_FIELDS:
        row[field] = None
    row["location_url"] = None
    row.pop("venue_id", None)
    return True


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
        "location_prefectures": event.location_prefectures or None,
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
    if event.location_url is not None:
        row["location_url"] = event.location_url
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
    if event.performer_url is not None:
        row["performer_url"] = event.performer_url
    if event.performer_urls:
        row["performer_urls"] = event.performer_urls
    if event.director_zh is not None:
        row["director_zh"] = event.director_zh
    if event.director_en is not None:
        row["director_en"] = event.director_en
    if event.image_url is not None:
        row["image_url"] = event.image_url

    _apply_pure_publication_policy(row)

    return row


def _populate_entity_fks(client: Client, rows: list[dict]) -> None:
    """
    Mutate `rows` in-place from unique organizer and authoritative venue matches.

    Venue matches supply canonical names, physical address, prefectures, stable
    homepage, and fill-only business hours. Field corrections take precedence
    over every propagated venue field. Missing or ambiguous entities leave venue
    fields unchanged.

    Entity tables come from migration 050 (Tier 2 normalization). On older
    databases without the tables, the lookup query fails silently and the
    function becomes a no-op — keeping the upsert pipeline backwards-compatible.
    """
    if not rows:
        return
    organizer_strs = sorted({r["organizer"] for r in rows
                             if isinstance(r.get("organizer"), str) and r["organizer"].strip()})
    venue_strs = sorted({r["location_name"] for r in rows
                         if not is_pure_publication_record(r)
                         and isinstance(r.get("location_name"), str) and r["location_name"].strip()})

    org_lookup: dict[str, tuple[str, str | None, tuple[str, ...]]] = {}
    if organizer_strs:
        try:
            # Match on canonical_name_ja first.
            resp = (
                client.table("organizers")
                .select("id,canonical_name_ja,aliases,homepage")
                .in_("canonical_name_ja", organizer_strs)
                .execute()
            )
            for r in resp.data or []:
                aliases = tuple(a for a in (r.get("aliases") or []) if isinstance(a, str) and a.strip())
                org_lookup[r["canonical_name_ja"]] = (r["id"], r.get("homepage"), aliases)
            # Then alias hits — separate query per string (PostgREST `cs.{x}`).
            still_missing = [s for s in organizer_strs if s not in org_lookup]
            if still_missing:
                # `aliases @> ARRAY[…]` via `cs` filter on TEXT[] column.
                # One round-trip per string (small N expected — usually < 50/run).
                # No `.limit(1)`: an alias must resolve to exactly one organizer.
                # If it matches multiple rows the alias is ambiguous — fail closed
                # (leave organizer_id unset) instead of arbitrarily taking the
                # first row. Mirrors the organizer_registry duplicate-alias guard.
                for s in still_missing:
                    try:
                        ar = (
                            client.table("organizers")
                            .select("id,homepage,aliases")
                            .contains("aliases", [s])
                            .execute()
                        )
                        matches = ar.data or []
                        if len(matches) > 1:
                            logger.warning(
                                "organizer alias %r matched %d organizer rows; "
                                "leaving organizer_id unset (fail closed).",
                                s,
                                len(matches),
                            )
                            continue
                        if matches:
                            hit = matches[0]
                            aliases = tuple(
                                a
                                for a in (hit.get("aliases") or [])
                                if isinstance(a, str) and a.strip()
                            )
                            org_lookup[s] = (hit["id"], hit.get("homepage"), aliases)
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug("organizer entity lookup skipped (table may not exist yet): %s", exc)

    venue_lookup: dict[str, dict[str, Any]] = {}
    if venue_strs:
        try:
            candidates: dict[str, dict[str, dict[str, Any]]] = {
                name: {} for name in venue_strs
            }
            incomplete_candidates: set[str] = set()
            canonical_resp = (
                client.table("venues")
                .select(_VENUE_SELECT_FIELDS)
                .in_("canonical_name_ja", venue_strs)
                .eq("is_authoritative", True)
                .execute()
            )
            for hit in canonical_resp.data or []:
                canonical = hit.get("canonical_name_ja")
                if canonical in candidates:
                    candidates[canonical][hit["id"]] = hit

            for name in venue_strs:
                try:
                    alias_resp = (
                        client.table("venues")
                        .select(_VENUE_SELECT_FIELDS)
                        .contains("aliases", [name])
                        .eq("is_authoritative", True)
                        .execute()
                    )
                    for hit in alias_resp.data or []:
                        candidates[name][hit["id"]] = hit
                except Exception as exc:
                    incomplete_candidates.add(name)
                    logger.warning(
                        "venue alias lookup failed for %r; cannot prove a unique "
                        "authoritative match, leaving venue fields unset: %s",
                        name,
                        exc,
                    )

            for name, by_id in candidates.items():
                if name in incomplete_candidates:
                    continue
                if len(by_id) == 1:
                    venue_lookup[name] = next(iter(by_id.values()))
                elif len(by_id) > 1:
                    logger.warning(
                        "venue lookup %r is ambiguous across %d authoritative rows; "
                        "leaving venue fields unset (fail closed).",
                        name,
                        len(by_id),
                    )
        except Exception as exc:
            logger.debug("venue entity lookup skipped (table may not exist yet): %s", exc)

    protected_by_key: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    id_map: dict[tuple, str] = {}
    venue_candidates = [
        row for row in rows
        if not is_pure_publication_record(row)
        and isinstance(row.get("location_name"), str)
        and row.get("location_name") in venue_lookup
    ]
    if venue_candidates:
        from collections import defaultdict
        by_sn: dict[str, list[str]] = defaultdict(list)
        for row in venue_candidates:
            by_sn[row["source_name"]].append(row["source_id"])
        for sn, sids in by_sn.items():
            try:
                id_resp = (
                    client.table("events")
                    .select("id,source_name,source_id")
                    .eq("source_name", sn)
                    .in_("source_id", sids)
                    .execute()
                )
                for item in id_resp.data or []:
                    id_map[(item.get("source_name") or sn, item["source_id"])] = item["id"]
            except Exception as exc:
                logger.debug("venue FC event-id lookup failed for %s: %s", sn, exc)
        candidate_uuids = list(id_map.values())
        if candidate_uuids:
            try:
                fc_resp = (
                    client.table("field_corrections")
                    .select(
                        "id,event_id,field_name,corrected_value,override_attempt_count,"
                        "first_override_attempted_at"
                    )
                    .in_("event_id", candidate_uuids)
                    .in_("field_name", list(_VENUE_PROPAGATED_FIELDS))
                    .execute()
                )
                eid_to_key = {event_id: key for key, event_id in id_map.items()}
                for fc in fc_resp.data or []:
                    key = eid_to_key.get(fc.get("event_id"))
                    field = fc.get("field_name")
                    if key and field:
                        protected_by_key.setdefault(key, {})[field] = fc
            except Exception as exc:
                logger.debug("venue field_corrections lookup failed: %s", exc)

    # Mutate rows in-place.
    org_hits = 0
    venue_hits = 0
    bh_hits = 0
    for r in rows:
        org = r.get("organizer")
        if isinstance(org, str) and org in org_lookup:
            organizer_id, homepage, aliases = org_lookup[org]
            r["organizer_id"] = organizer_id
            if homepage and not r.get("organizer_url"):
                if is_pure_publication_record(r):
                    validated_homepage = validated_registry_homepage(
                        org,
                        homepage,
                        aliases=aliases,
                    )
                    if validated_homepage:
                        r["organizer_url"] = validated_homepage
                else:
                    r["organizer_url"] = homepage
            org_hits += 1
        if is_pure_publication_record(r):
            continue
        loc = r.get("location_name")
        if not isinstance(loc, str) or loc not in venue_lookup:
            continue
        venue = venue_lookup[loc]
        prefectures = venue.get("prefectures")
        if not prefectures and venue.get("prefecture"):
            prefectures = [venue["prefecture"]]
        proposed: dict[str, Any] = {
            "location_name": venue.get("canonical_name_ja"),
            "location_name_zh": venue.get("canonical_name_zh"),
            "location_name_en": venue.get("canonical_name_en"),
            "location_prefectures": prefectures,
        }
        if venue.get("is_multi_venue"):
            proposed.update({
                "venue_id": None,
                "location_address": None,
                "location_address_zh": None,
                "location_address_en": None,
                "location_url": None,
            })
        else:
            proposed.update({
                "venue_id": venue["id"],
                "location_address": venue.get("address"),
                "location_url": venue.get("homepage"),
            })
        if (
            not venue.get("is_multi_venue")
            and not r.get("business_hours")
            and venue.get("business_hours")
        ):
            proposed["business_hours"] = venue["business_hours"]

        key = (r.get("source_name"), r.get("source_id"))
        protected = protected_by_key.get(key, {})
        for field, value in proposed.items():
            fc = protected.get(field)
            if fc is not None:
                corrected = _field_correction_value(field, fc.get("corrected_value"))
                if value != corrected:
                    _record_fc_override_attempt(client, fc, value)
                r[field] = corrected
                continue
            r[field] = value
            if field == "business_hours":
                bh_hits += 1
        venue_hits += 1
    if org_hits or venue_hits:
        logger.info("Entity FK lookup: organizer_id matched %d row(s); venue_id matched %d row(s).",
                    org_hits, venue_hits)
    if bh_hits:
        logger.info("Venue business_hours propagated to %d row(s).", bh_hits)


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


def _auto_lock_location(client, eid_to_row: dict[str, dict[str, Any]]) -> None:
    """Auto-lock scraper-provided location fields so annotator cannot overwrite."""
    import json
    fc_records = []
    for eid, row in eid_to_row.items():
        if is_pure_publication_record(row) or not row.get("location_name"):
            continue
        for field, value in [
            ("location_name",        row.get("location_name")),
            ("location_address",     row.get("location_address")),
            ("location_prefectures", row.get("location_prefectures")),
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
        logger.info("Auto-locked location fields for %d new event(s).", len(eid_to_row))
    except Exception as exc:
        logger.warning("Auto-lock location FC failed (non-critical): %s", exc)


def _write_pure_publication_sentinels(
    client: Client,
    pure_rows: list[dict[str, Any]],
    upserted_rows: list[dict[str, Any]],
) -> None:
    if not pure_rows:
        return
    ids_by_key = {
        (row.get("source_name"), row.get("source_id")): row.get("id")
        for row in upserted_rows
        if row.get("id")
    }
    event_ids: list[str] = []
    for row in pure_rows:
        event_id = ids_by_key.get((row.get("source_name"), row.get("source_id")))
        if not event_id:
            raise RuntimeError("Pure publication upsert did not return an event UUID")
        event_ids.append(event_id)

    sentinel_rows = [
        {"event_id": event_id, "field_name": field, "corrected_value": ""}
        for event_id in event_ids
        for field in PUBLICATION_NULL_FIELDS
    ]
    client.table("field_corrections").upsert(
        sentinel_rows,
        on_conflict="event_id,field_name",
        ignore_duplicates=False,
    ).execute()

    event_result = (
        client.table("events")
        .select("id," + ",".join(PUBLICATION_NULL_FIELDS))
        .in_("id", event_ids)
        .execute()
    )
    events_by_id = {row["id"]: row for row in (event_result.data or [])}
    for event_id in event_ids:
        event_row = events_by_id.get(event_id)
        if event_row is None or any(event_row.get(field) is not None for field in PUBLICATION_NULL_FIELDS):
            raise RuntimeError(f"Pure publication NULL postcondition failed for {event_id}")

    fc_result = (
        client.table("field_corrections")
        .select("event_id,field_name,corrected_value")
        .in_("event_id", event_ids)
        .in_("field_name", list(PUBLICATION_NULL_FIELDS))
        .execute()
    )
    sentinels = {
        (row.get("event_id"), row.get("field_name")): row.get("corrected_value")
        for row in (fc_result.data or [])
    }
    for event_id in event_ids:
        for field in PUBLICATION_NULL_FIELDS:
            if sentinels.get((event_id, field)) != "":
                raise RuntimeError(f"Pure publication FC postcondition failed for {event_id}:{field}")


def _build_movie_extend_row(event: Event, existing_state: dict) -> dict | None:
    """
    Build a partial-update row for a movie event that already exists in DB.

    Preserves first-observed start_date (MIN) and extends end_date (MAX),
    refreshing only raw_description, business_hours, and dates. Other fields
    (name_*, description_*, category, location_*, etc.) are intentionally
    excluded — those are owned by the annotator and protected by
    field_corrections (P3.2 invariant).

    annotation_status is flipped to 'pending' when any translation-dependent
    source field changes (raw_description, business_hours, start_date, end_date),
    so the annotator re-runs with the latest schedule and date context.

    Returns None if nothing meaningful would change.
    """
    new_start = _dt_iso(event.start_date)
    new_end = _dt_iso(event.end_date)
    old_start = existing_state.get("start_date")
    old_end = existing_state.get("end_date")
    old_desc = (existing_state.get("raw_description") or "").strip()
    new_desc = (event.raw_description or "").strip()

    # Prefer the scraper's current start_date (new_start) over the stored one.
    # Rationale: the first scrape may have captured a publication date (before the
    # schedule was published), so MIN would permanently lock in that wrong date.
    # Trusting new_start means re-scrapes reflect the current schedule.
    # If new_start is None (schedule not yet available), fall back to old_start.
    merged_start = new_start or old_start

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
    if desc_changed or hours_changed or start_changed or end_changed:
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
            elif key in existing_movie_state:
                # Movie-extend: partial update only — preserves first-observed start_date,
                # extends end_date to cover ongoing run. Does NOT touch any P3.2-protected
                # fields (name_*, description_*, category, location_*, etc.) by construction.
                # NOTE: We use the DB row's category (stored in existing_movie_state, already
                # filtered to 'movie') — NOT e.category — because scrapers emit category=[]
                # before the annotator runs; checking e.category would always be False.
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
                .select("id,source_name,source_id")
                .in_("source_id", force_source_ids_list)
                .execute()
            )
            key_to_eid: dict[tuple[str, str], str] = {
                (row["source_name"], row["source_id"]): row["id"]
                for row in (id_map_res.data or [])
            }
            event_uuids = list(key_to_eid.values())

            if event_uuids:
                fc_res = (
                    client.table("field_corrections")
                    .select("event_id,field_name,corrected_value")
                    .in_("event_id", event_uuids)
                    .execute()
                )
                # Build: event_id → set of protected column names
                eid_protected: dict[str, set[str]] = {}
                for fc in (fc_res.data or []):
                    eid_protected.setdefault(fc["event_id"], set()).add(fc["field_name"])

                if eid_protected:
                    eid_to_key = {event_id: key for key, event_id in key_to_eid.items()}
                    key_protected: dict[tuple[str, str], set[str]] = {
                        eid_to_key[eid]: cols
                        for eid, cols in eid_protected.items()
                        if eid in eid_to_key
                    }
                    policy_conflicts = [
                        fc for fc in (fc_res.data or [])
                        if fc.get("field_name") in PUBLICATION_NULL_FIELDS
                        and fc.get("corrected_value") not in (None, "")
                        and any(
                            is_pure_publication_record(row)
                            and key_to_eid.get((row["source_name"], row["source_id"])) == fc.get("event_id")
                            for row in force_rows
                        )
                    ]
                    if policy_conflicts:
                        conflict = policy_conflicts[0]
                        raise RuntimeError(
                            "Pure publication policy conflicts with a non-empty field correction: "
                            f"{conflict['event_id']}:{conflict['field_name']}"
                        )
                    scrubbed = 0
                    for row in force_rows:
                        key = (row["source_name"], row["source_id"])
                        for col in key_protected.get(key, set()):
                            if col in row:
                                del row[col]
                                scrubbed += 1
                        _apply_pure_publication_policy(row)
                    if scrubbed:
                        logger.info(
                            "Stripped %d field_corrections-protected column(s) from %d force row(s).",
                            scrubbed, len(force_rows),
                        )
        except RuntimeError:
            raise
        except Exception as fc_exc:
            logger.debug("field_corrections check for force_rows skipped: %s", fc_exc)

    new_event_ids: list[str] = []
    if all_rows:
        try:
            resp = client.table("events").upsert(all_rows, on_conflict="source_name,source_id").execute()
            logger.info("Upserted %d events to Supabase.", len(all_rows))
            _write_pure_publication_sentinels(
                client,
                [row for row in all_rows if is_pure_publication_record(row)],
                list(resp.data or []),
            )
            # Collect IDs of newly-inserted events only (not force-updates)
            # Supabase returns the upserted rows — match source_id against new_rows
            new_source_ids = {r["source_id"] for r in new_rows}
            for row in (resp.data or []):
                if row.get("source_id") in new_source_ids and row.get("id"):
                    new_event_ids.append(row["id"])
            # ── Auto-lock scraper-provided location fields ────────────────────
            new_key_to_row = {
                (row["source_name"], row["source_id"]): row for row in new_rows
                if row.get("location_name") and not is_pure_publication_record(row)
            }
            if new_key_to_row:
                key_to_eid = {
                    (row["source_name"], row["source_id"]): row["id"]
                    for row in (resp.data or [])
                    if (row.get("source_name"), row.get("source_id")) in new_key_to_row
                    and row.get("id")
                }
                eid_to_row = {event_id: new_key_to_row[key] for key, event_id in key_to_eid.items()}
                _auto_lock_location(client, eid_to_row)
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

