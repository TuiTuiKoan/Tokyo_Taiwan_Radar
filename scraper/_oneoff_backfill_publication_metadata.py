"""Immutable Wave 1 publication legacy-repair manifest CLI and contract."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Callable

from dotenv import load_dotenv

from auto_qa import _all_auto_report_types, _resolve_report_disposition
from enrich_poster import _is_placeholder_image_url
from publication_rules import (
    PUBLICATION_NULL_FIELDS,
    is_ndl_periodical_article,
    is_pure_publication_record,
    normalize_event_forms,
    normalize_publisher_name,
    validated_registry_homepage,
)
from qa_auto_fix import apply_cas_filter

SCHEMA_NAME = "tokyo-taiwan-radar/publication-legacy-repair"
SCHEMA_VERSION = 3
WAVE = "wave1"
PAGE_SIZE = 500
ROOT = Path(__file__).resolve().parents[1]
TABLES = ("events", "field_corrections", "event_reports", "organizers")

# Cleared alongside PUBLICATION_NULL_FIELDS on exact-pure rows, but deliberately
# NOT part of it: these six gain no empty-sentinel field_correction contract.
PUBLICATION_EXTENDED_CLEAR_FIELDS = (
    "location_name",
    "location_name_zh",
    "location_name_en",
    "location_url",
    "venue_id",
    "organizer_type",
)
PUBLICATION_TARGET_FIELDS = tuple(PUBLICATION_NULL_FIELDS) + PUBLICATION_EXTENDED_CLEAR_FIELDS

APPLY_PHASES = ("eslite-identity", "fc-remove", "event-clear")
# Phase boundaries are defined by side effect, never by abstract table purity.
PHASE_ALLOWED_FC_MODES = {
    "fc-remove": frozenset({"unlock_only"}),
    "event-clear": frozenset({"lock_empty"}),
    "eslite-identity": frozenset({"lock_clean", "lock_empty", "unlock_only"}),
}
CHECKPOINT_BEFORE = {
    "eslite-identity": "eslite-identity.before",
    "fc-remove": "fc-remove.before",
    "event-clear": "fc-remove.after",
}
CHECKPOINT_AFTER = {
    "eslite-identity": "eslite-identity.after",
    "fc-remove": "fc-remove.after",
    "event-clear": "event-clear.after",
}
CHECKPOINT_ALIASES = {"event-clear.before": "fc-remove.after"}
CLEANUP_CHECKPOINTS = ("fc-remove.before", "fc-remove.after", "event-clear.after")
ESLITE_CHECKPOINTS = ("eslite-identity.before", "eslite-identity.after")
# events.updated_at is maintained automatically; it is audit evidence, never a
# checkpoint identity field.
CHECKPOINT_VOLATILE_EVENT_FIELDS = ("updated_at",)
# A field correction the phase still has to create carries no id in the manifest
# because Postgres assigns it during the write. Its after-image is therefore
# matched on (event_id, field_name) plus these value/provenance columns only.
# `created_at` is deliberately absent: Postgres assigns it during the same write,
# so it can never be predicted by the manifest.
CHECKPOINT_NEW_ROW_MATCH_FIELDS = (
    "corrected_value",
    "original_value",
    "corrected_by",
    "report_id",
)
MANIFEST_DIGEST_PLACEHOLDER = "<manifest_digest>"

MANIFEST_SCOPE_CLEANUP = "cleanup"
MANIFEST_SCOPE_ESLITE = "eslite-identity"

ESLITE_TALK_ID = "50c83c11-ed64-481a-bb5a-caa3e9981943"
ESLITE_OLD_SOURCE_ID = "eslite_spectrum_9"
ESLITE_NEW_SOURCE_ID = "eslite_spectrum_f0039984-3181-450d-8b59-e024a8eea070"
ESLITE_ARTICLE_URL = "https://www.eslitespectrum.jp/news/f0039984-3181-450d-8b59-e024a8eea070"
ESLITE_PHYSICAL_FORMS = ["lecture"]
ESLITE_IDENTITY_FIELDS = ("event_form", "source_id", "source_url")
ESLITE_BUSINESS_HOURS = "13:00〜"
# Fixed Venue Authority Guard: a fixed venue is resolved from the authoritative
# registry, never from whatever the event row happens to carry. These mirror
# venues.fd330e2a-e8e8-40fb-9fcb-d1af44d7be3a (is_authoritative=true):
# homepage / canonical_name_zh / canonical_name_en.
ESLITE_VENUE_URL = "https://www.eslitespectrum.jp/"
ESLITE_VENUE_NAME_ZH = "誠品生活日本橋"
ESLITE_VENUE_NAME_EN = "Eslite Spectrum Nihonbashi"

PUBLICATION_PREFIXES = (
    "[新刊出版]",
    "【新刊出版】",
    "[New Release]",
    "[雑誌記事]",
    "【雑誌記事】",
    "[期刊專文]",
    "【期刊專文】",
    "[Periodical Article]",
    "[Periodical article]",
)
PERIODICAL_LABELS = {
    "name_ja": "[雑誌記事]",
    "name_zh": "[期刊專文]",
    "name_en": "[Periodical Article]",
}
TITLE_FIELDS = tuple(PERIODICAL_LABELS)
FAKE_PRICE_PLACEHOLDERS = frozenset(
    {
        "新刊のご購入は各販売チャネルでお願いします",
        "新書購買請洽各通路",
        "Please check each sales channel to purchase this new book.",
    }
)
PUBLICATION_LOCATION_MARKERS = (
    "新刊",
    "出版",
    "刊載",
    "掲載",
    "刊行",
    "雑誌",
    "期刊",
    "購入",
    "購買",
    "販売チャネル",
    "各通路",
)
PHYSICAL_LOCATION_RE = re.compile(
    r"(?:ホール|会館|劇場|シアター|ギャラリー|美術館|博物館|大学|キャンパス|書店|"
    r"本店|支店|イベントスペース|FORUM|フォーラム|スタジオ|サロン|ホテル|誠品生活|"
    r"(?:東京都|北海道|(?:京都|大阪)府|.{2,3}県).{0,20}(?:市|区|町|村|丁目))",
    re.IGNORECASE,
)
POSTER_POLLUTION_LOCATION = "大阪城ホール"
POSTER_POLLUTION_START_DATE = "2023-10-14T00:00:00+00:00"
POSTER_POLLUTION_ORGANIZER = "コミックマーケット準備会"
PUBLICATION_CHANNEL_LOCATION = "新刊のご購入は各販売チャネルでお願いします"
# Legacy producer literals retained as historical pollution detectors. They are
# never written back by this script.
PUBLICATION_PLACEHOLDER_VALUES = frozenset(
    {PUBLICATION_CHANNEL_LOCATION, *FAKE_PRICE_PLACEHOLDERS}
)
POSTER_POLLUTION_REPAIRS = {
    "0ca66140-4eb1-45a8-b3c4-9b61740705e4": {
        "source_name": "hanmoto",
        "source_id": "hanmoto_9784533174162",
        "clean_start_date": "2026-08-16T00:00:00+00:00",
        "date_evidence": "unpolluted_end_date",
    },
    "3995e531-4ebe-403a-ac4d-f1bc7119c5c9": {
        "source_name": "ndl_opensearch",
        "source_id": "ndl_9784816379222",
        "clean_start_date": "2026-09-14T00:00:00+00:00",
        "date_evidence": "same_isbn_source",
        "same_isbn_source_id": "hanmoto_9784816379222",
    },
    "3dd4c8c8-d433-4221-961a-3b3c9b58d05e": {
        "source_name": "hanmoto",
        "source_id": "hanmoto_9784868140771",
        "clean_start_date": "2026-03-13T00:00:00+00:00",
        "date_evidence": "unpolluted_end_date",
        "publisher": "金沢文圃閣",
    },
    "407b750a-5f6c-427c-8206-542a278deb04": {
        "source_name": "hanmoto",
        "source_id": "hanmoto_9784868140092",
        "clean_start_date": "2026-03-06T00:00:00+00:00",
        "date_evidence": "unpolluted_end_date",
    },
    "66aa80d7-7db2-41d4-882c-5ab759be4419": {
        "source_name": "hanmoto",
        "source_id": "hanmoto_9784868140764",
        "clean_start_date": "2026-03-13T00:00:00+00:00",
        "date_evidence": "unpolluted_end_date",
        "publisher": "金沢文圃閣",
    },
    "77d0177e-1709-4b09-9402-80c32a71e2b4": {
        "source_name": "hanmoto",
        "source_id": "hanmoto_9784843336175",
        "clean_start_date": "2026-04-03T00:00:00+00:00",
        "date_evidence": "unpolluted_end_date",
    },
    "c1be1d3b-3708-42ba-9fe7-1c081dfe6d35": {
        "source_name": "ndl_opensearch",
        "source_id": "ndl_9784562077014",
        "clean_start_date": "2026-08-17T00:00:00+00:00",
        "date_evidence": "unpolluted_end_date",
    },
    "c865cbda-b9d3-4bc9-b14c-289771ec1260": {
        "source_name": "hanmoto",
        "source_id": "hanmoto_9784533174155",
        "clean_start_date": "2026-08-16T00:00:00+00:00",
        "date_evidence": "unpolluted_end_date",
        "publisher": "JTBパブリッシング",
    },
}
SECRET_PATTERNS = (
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\b"),
)
WAVE2_BOUNDARY = {
    "status": "not_executed",
    "requires_separate_manifest": True,
    "wave1_dependency": False,
    "unresolved_homepage_is_valid": True,
    "providers": [
        {
            "name": "duckduckgo_html",
            "enabled": False,
            "network_allowed": False,
            "cost_unit": "query",
            "max_cost": 0,
            "required_evidence": [
                "query",
                "candidate_url",
                "page_title",
                "rejection_or_acceptance_reason",
            ],
        },
        {
            "name": "openai_search_preview",
            "enabled": False,
            "network_allowed": False,
            "cost_unit": "request",
            "max_cost": 0,
            "required_evidence": [
                "model",
                "query",
                "candidate_url",
                "citations",
                "validation_reason",
            ],
        },
    ],
}

_MUTATION_METHODS = {"delete", "insert", "rpc", "update", "upsert"}


class _ReadOnlyProxy:
    def __init__(self, target):
        self._target = target

    def __getattr__(self, name):
        if name in _MUTATION_METHODS:
            raise RuntimeError(f"dry-run read-only client blocked Supabase mutation: {name}")
        attribute = getattr(self._target, name)
        if not callable(attribute):
            return attribute

        def call(*args, **kwargs):
            result = attribute(*args, **kwargs)
            if result is self._target or hasattr(result, "execute"):
                return _ReadOnlyProxy(result)
            return result

        return call


def get_supabase(*, read_only: bool):
    env_file = Path(
        os.environ.get("PUBLICATION_MANIFEST_ENV_FILE")
        or Path(__file__).with_name(".env")
    ).expanduser()
    load_dotenv(env_file)
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    from supabase import create_client

    client = create_client(url, key)
    return _ReadOnlyProxy(client) if read_only else client


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_bytes(value: Any, *, indent: int | None = None) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=None if indent else (",", ":"),
        indent=indent,
    ).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(json_bytes(value)).hexdigest()


def row_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("id") or ""),
        str(row.get("event_id") or ""),
        str(row.get("field_name") or ""),
    )


def with_retry(fetch_fn: Callable[[], Any], *, label: str) -> Any:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return fetch_fn()
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1)
    raise RuntimeError(f"{label} failed after 3 attempts: {last_error}") from last_error


def fetch_table_exact(sb, table: str) -> tuple[list[dict[str, Any]], int]:
    result = with_retry(
        lambda: sb.table(table).select("id", count="exact", head=True).execute(),
        label=f"count {table}",
    )
    exact_count = result.count
    if exact_count is None:
        raise RuntimeError(f"{table} exact count was not returned")

    rows: list[dict[str, Any]] = []
    offset = 0
    while offset < exact_count:
        page = with_retry(
            lambda offset=offset: (
                sb.table(table)
                .select("*")
                .order("id")
                .range(offset, offset + PAGE_SIZE - 1)
                .execute()
            ),
            label=f"fetch {table} page at {offset}",
        )
        batch = list(page.data or [])
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
    if len(rows) != exact_count:
        raise RuntimeError(
            f"{table} exact/fetched mismatch: exact={exact_count} fetched={len(rows)}"
        )
    return sorted(rows, key=row_sort_key), exact_count


def read_database_state(sb) -> dict[str, Any]:
    tables: dict[str, list[dict[str, Any]]] = {}
    exact_counts: dict[str, int] = {}
    hashes: dict[str, str] = {}
    for table in TABLES:
        rows, exact_count = fetch_table_exact(sb, table)
        tables[table] = rows
        exact_counts[table] = exact_count
        hashes[table] = sha256(rows)
    base = {
        "exact_counts": exact_counts,
        "fetched_counts": {table: len(tables[table]) for table in TABLES},
        "table_hashes": hashes,
    }
    return {"tables": tables, "fingerprint": {**base, "sha256": sha256(base)}}


def contains_publication_form(event: dict[str, Any]) -> bool:
    return "publication" in normalize_event_forms(event.get("event_form"))


def strip_publication_prefix(value: str | None) -> str | None:
    if not value:
        return value
    result = value.strip()
    changed = True
    while changed:
        changed = False
        for prefix in PUBLICATION_PREFIXES:
            if result.casefold().startswith(prefix.casefold()):
                result = result[len(prefix) :].lstrip()
                changed = True
    return result


def periodical_title(value: str | None, label: str) -> str | None:
    base = strip_publication_prefix(value)
    return f"{label}{base}" if base else value


def is_fake_price(value: Any) -> bool:
    return isinstance(value, str) and value.strip() in FAKE_PRICE_PLACEHOLDERS


def location_conflict_reason(event: dict[str, Any]) -> str | None:
    value = str(event.get("location_name") or "").strip()
    if not value or any(marker in value for marker in PUBLICATION_LOCATION_MARKERS):
        return None
    if PHYSICAL_LOCATION_RE.search(value):
        return f"location_name has physical venue/address evidence: {value}"
    return None


def classification_evidence(event: dict[str, Any]) -> dict[str, Any]:
    forms = normalize_event_forms(event.get("event_form"))
    names = [event.get(field) for field in TITLE_FIELDS]
    return {
        "normalized_event_form": forms,
        "exact_pure_helper": is_pure_publication_record(event),
        "contains_publication_form": "publication" in forms,
        "source_evidence_only": event.get("source_name"),
        "books_media_category_evidence_only": "books_media" in (event.get("category") or []),
        "title_prefix_evidence_only": any(
            isinstance(name, str)
            and any(name.strip().casefold().startswith(prefix.casefold()) for prefix in PUBLICATION_PREFIXES)
            for name in names
        ),
        "active": event.get("is_active") is True,
        "location_conflict": location_conflict_reason(event),
        "ndl_periodical_source_evidence": is_ndl_periodical_article(event),
    }


def organizer_indexes(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("id"):
            by_id[str(row["id"])] = row
        names = [
            row.get("canonical_name_ja"),
            row.get("canonical_name_zh"),
            row.get("canonical_name_en"),
            *(row.get("aliases") or []),
        ]
        for name in names:
            normalized = normalize_publisher_name(name)
            if normalized:
                by_name.setdefault(normalized, row)
    return by_id, by_name


def publisher_plan(
    event: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    publisher = event.get("organizer")
    normalized = normalize_publisher_name(publisher)
    organizer = by_id.get(str(event.get("organizer_id") or "")) or by_name.get(normalized or "")
    aliases = organizer.get("aliases") or [] if organizer else []
    candidates = []
    if event.get("organizer_url"):
        candidates.append(("existing_event_organizer_url", event.get("organizer_url")))
    if organizer and organizer.get("homepage"):
        candidates.append(("validated_registry_homepage", organizer.get("homepage")))

    accepted = None
    provider = None
    rejected: list[dict[str, Any]] = []
    for candidate_provider, candidate_url in candidates:
        validated = validated_registry_homepage(publisher, candidate_url, aliases=aliases)
        if validated:
            accepted = validated
            provider = candidate_provider
            break
        rejected.append(
            {
                "provider": candidate_provider,
                "url": candidate_url,
                "reason": "strict-validator-rejected",
            }
        )
    status = (
        "unresolved_missing_publisher"
        if not publisher
        else "resolved"
        if accepted
        else "unresolved_homepage_allowed"
    )
    return {
        "publisher_name": publisher,
        "normalized_publisher": normalized,
        "status": status,
        "provider": provider,
        "accepted_homepage": accepted,
        "rejected_candidates": rejected,
        "organizer_before": deepcopy(organizer),
        "organizer_after": deepcopy(organizer),
        "network_search_performed": False,
    }


def event_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        field: {"before": before.get(field), "after": after.get(field)}
        for field in sorted(set(before) | set(after))
        if before.get(field) != after.get(field)
    }


def fc_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict, bool)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def decoded_fc_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def unlock_reason_template(apply_phase: str) -> str:
    """Digest placeholder form; expanded only after the canonical digest exists."""
    return f"publication_manifest:{apply_phase}:{MANIFEST_DIGEST_PLACEHOLDER}"


def expand_unlock_reason(template: str, manifest_digest: str) -> str:
    if MANIFEST_DIGEST_PLACEHOLDER not in str(template):
        raise RuntimeError(f"unlock reason template lacks digest placeholder: {template!r}")
    if not manifest_digest:
        raise RuntimeError("manifest digest is required to expand an unlock reason")
    return str(template).replace(MANIFEST_DIGEST_PLACEHOLDER, manifest_digest)


def is_target_field(field: Any) -> bool:
    return str(field) in PUBLICATION_TARGET_FIELDS


def is_empty_sentinel(row: dict[str, Any] | None) -> bool:
    return bool(row) and row.get("corrected_value") == ""


def is_human_correction(row: dict[str, Any]) -> bool:
    return row.get("corrected_by") is not None


def human_locked_target_fields(fc_rows: list[dict[str, Any]]) -> list[str]:
    return sorted(
        str(row.get("field_name"))
        for row in fc_rows
        if is_target_field(row.get("field_name")) and is_human_correction(row)
    )


def target_fc_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (deepcopy(row) for row in rows if is_target_field(row.get("field_name"))),
        key=row_sort_key,
    )


def checkpoint_event_row(event: dict[str, Any]) -> dict[str, Any]:
    row = deepcopy(event)
    for field in CHECKPOINT_VOLATILE_EVENT_FIELDS:
        row.pop(field, None)
    return row


def poster_pollution_evidence(
    event: dict[str, Any],
    fc_rows: list[dict[str, Any]],
    events_by_source_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[str]]:
    expected = POSTER_POLLUTION_REPAIRS.get(str(event.get("id")))
    if not expected:
        return None, []

    failures: list[str] = []
    if not is_pure_publication_record(event):
        failures.append("event_form is not exact pure publication")
    for field in ("source_name", "source_id"):
        if event.get(field) != expected[field]:
            failures.append(f"{field} does not match audited signature")
    if not _is_placeholder_image_url(event.get("image_url")):
        failures.append("image_url is not a canonical Hanmoto placeholder")
    if event.get("location_name") != POSTER_POLLUTION_LOCATION:
        failures.append("location_name does not match poster pollution")
    if event.get("start_date") != POSTER_POLLUTION_START_DATE:
        failures.append("start_date does not match poster pollution")

    fc_by_field = {str(row.get("field_name")): row for row in fc_rows}
    required_fc = {
        "location_name": POSTER_POLLUTION_LOCATION,
        "start_date": POSTER_POLLUTION_START_DATE,
    }
    if expected.get("publisher"):
        required_fc["organizer"] = POSTER_POLLUTION_ORGANIZER
        if event.get("organizer") != POSTER_POLLUTION_ORGANIZER:
            failures.append("organizer does not match poster pollution")
    for field, polluted_value in required_fc.items():
        row = fc_by_field.get(field)
        if not row:
            failures.append(f"missing {field} field-correction evidence")
            continue
        if decoded_fc_value(row.get("corrected_value")) != polluted_value:
            failures.append(f"{field} field-correction value does not match pollution")
        if row.get("original_value") is not None:
            failures.append(f"{field} field-correction original value is not null")

    start_fc = fc_by_field.get("start_date")
    location_fc = fc_by_field.get("location_name")
    same_batch_seconds = None
    if start_fc and location_fc:
        try:
            start_created = datetime.fromisoformat(str(start_fc["created_at"]).replace("Z", "+00:00"))
            location_created = datetime.fromisoformat(str(location_fc["created_at"]).replace("Z", "+00:00"))
            same_batch_seconds = abs((start_created - location_created).total_seconds())
            if same_batch_seconds > 5:
                failures.append("start/location FC timestamps are not from the same Vision batch")
        except (KeyError, TypeError, ValueError):
            failures.append("start/location FC batch timestamps are incomplete")

    date_evidence: dict[str, Any]
    clean_start_date = expected["clean_start_date"]
    if expected["date_evidence"] == "same_isbn_source":
        peer = events_by_source_id.get(str(expected["same_isbn_source_id"]))
        if not peer or peer.get("start_date") != clean_start_date or peer.get("end_date") != clean_start_date:
            failures.append("same-ISBN source date evidence is incomplete")
            date_evidence = {
                "type": "same_isbn_source",
                "source_id": expected["same_isbn_source_id"],
                "verified": False,
            }
        else:
            date_evidence = {
                "type": "same_isbn_source",
                "source_id": peer.get("source_id"),
                "event_id": peer.get("id"),
                "start_date": peer.get("start_date"),
                "end_date": peer.get("end_date"),
                "verified": True,
            }
    else:
        verified = event.get("end_date") == clean_start_date
        if not verified:
            failures.append("unpolluted end_date evidence is incomplete")
        date_evidence = {
            "type": "unpolluted_end_date",
            "end_date": event.get("end_date"),
            "verified": verified,
        }

    evidence = {
        "signature": "exact_uuid_source_placeholder_venue_date_fc_batch",
        "event_id": event.get("id"),
        "source_name": event.get("source_name"),
        "source_id": event.get("source_id"),
        "image_url": event.get("image_url"),
        "location_name": event.get("location_name"),
        "start_date": event.get("start_date"),
        "fc_fields": sorted(required_fc),
        "start_location_fc_batch_seconds": same_batch_seconds,
        "date_repair": date_evidence,
        "publisher_repair": {
            "value": expected.get("publisher"),
            "evidence": "audited source publisher by ISBN" if expected.get("publisher") else None,
        },
        "complete": not failures,
    }
    return evidence, failures


def plan_fc_actions(
    event_id: str,
    before_rows: list[dict[str, Any]],
    field_modes: dict[str, tuple[str, Any]],
    *,
    route_action: str = "pure_cleanup",
    apply_phase: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if apply_phase not in APPLY_PHASES:
        raise RuntimeError(f"unknown apply_phase: {apply_phase!r}")
    by_field = {str(row.get("field_name")): deepcopy(row) for row in before_rows}
    actions: list[dict[str, Any]] = []
    for field, (mode, value) in field_modes.items():
        if mode not in PHASE_ALLOWED_FC_MODES[apply_phase]:
            raise RuntimeError(f"mode {mode!r} is not permitted in apply_phase {apply_phase!r}")
        existing = by_field.get(field)
        if mode == "unlock_only":
            by_field.pop(field, None)
            after_row = None
        else:
            after_row = deepcopy(existing) if existing else {
                "id": None,
                "event_id": event_id,
                "field_name": field,
                "corrected_by": None,
                "original_value": None,
                "report_id": None,
            }
            after_row["corrected_value"] = "" if mode == "lock_empty" else fc_value(value)
            by_field[field] = after_row
        actions.append(
            {
                "field_name": field,
                "mode": mode,
                "new_value": value,
                "report_id": existing.get("report_id") if existing else None,
                "audit_contract": "qa_auto_fix.unlock_and_write",
                "route_action": route_action,
                "apply_phase": apply_phase,
                "expected_fc": deepcopy(existing),
                "expected_fc_after": deepcopy(after_row),
                "unlock_reason_template": unlock_reason_template(apply_phase),
            }
        )
    return (
        sorted(deepcopy(before_rows), key=row_sort_key),
        sorted(by_field.values(), key=row_sort_key),
        actions,
    )


def report_plans(reports: list[dict[str, Any]], event_after: dict[str, Any]) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for report in sorted(reports, key=row_sort_key):
        types = _all_auto_report_types(report.get("report_types"))
        if report.get("status") != "pending":
            disposition, reason = "unchanged", "report is not pending"
        elif not types:
            disposition, reason = "keep", "manual or unknown report type"
        else:
            disposition, reason = _resolve_report_disposition(event_after, types)
        plans.append(
            {
                "before": deepcopy(report),
                "after": deepcopy(report),
                "planned_disposition": disposition,
                "reason": reason,
                "execution": "external_auto_qa_reconcile_only",
                "script_will_write": False,
            }
        )
    return plans


def pure_plan(
    event: dict[str, Any],
    fc_rows: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    publisher: dict[str, Any],
    *,
    route_action: str = "pure_cleanup",
) -> dict[str, Any]:
    event_id = str(event["id"])
    after = deepcopy(event)
    for field in PUBLICATION_TARGET_FIELDS:
        after[field] = None

    fc_by_field = {str(row.get("field_name")): row for row in fc_rows}

    # fc-remove: every polluted target FC leaves through the audited unlock_only
    # contract. Exact empty sentinels are valid policy locks and are preserved.
    remove_modes: dict[str, tuple[str, Any]] = {
        field: ("unlock_only", None)
        for field in PUBLICATION_TARGET_FIELDS
        if fc_by_field.get(field) is not None and not is_empty_sentinel(fc_by_field[field])
    }
    fc_before, fc_after_fc_remove, remove_actions = plan_fc_actions(
        event_id,
        fc_rows,
        remove_modes,
        route_action=route_action,
        apply_phase="fc-remove",
    )

    # event-clear: canonical seven only. The six extended fields are cleared by
    # the value-level CAS patch below and gain no sentinel semantics.
    clear_modes: dict[str, tuple[str, Any]] = {
        field: ("lock_empty", None) for field in PUBLICATION_NULL_FIELDS
    }
    _, fc_after, clear_actions = plan_fc_actions(
        event_id,
        fc_after_fc_remove,
        clear_modes,
        route_action=route_action,
        apply_phase="event-clear",
    )

    extended_field_patch = {
        field: {"before": event.get(field), "after": None}
        for field in PUBLICATION_EXTENDED_CLEAR_FIELDS
    }

    periodical = is_ndl_periodical_article(event)
    title_fc = {
        str(row.get("field_name"))
        for row in fc_rows
        if row.get("field_name") in TITLE_FIELDS
    }
    title_findings = {}
    if periodical:
        for field, label in PERIODICAL_LABELS.items():
            if field in title_fc:
                continue
            repaired = periodical_title(event.get(field), label)
            if repaired and repaired != event.get(field):
                title_findings[field] = {"observed": event.get(field), "source_evidence": repaired}

    organizer = publisher.get("organizer_before")
    fake_price = is_fake_price(event.get("price_info"))
    read_only_findings = {
        "contract": "non-target findings never produce an executable action, "
                    "event change, or after-image delta",
        "price_info": {
            "observed": event.get("price_info"),
            "fake_placeholder_allowlist_match": fake_price,
            "executable": False,
        },
        "periodical_titles": {
            "source_metadata_confirmed": periodical,
            "candidates": title_findings,
            "executable": False,
        },
        "organizer_link": {
            "organizer_id": {
                "observed": event.get("organizer_id"),
                "registry_match": organizer.get("id") if organizer else None,
            },
            "organizer_url": {
                "observed": event.get("organizer_url"),
                "accepted_homepage": publisher.get("accepted_homepage"),
            },
            "executable": False,
        },
    }

    nonempty_policy_fc = sorted(
        str(row.get("field_name"))
        for row in fc_rows
        if row.get("field_name") in PUBLICATION_NULL_FIELDS
        and row.get("corrected_value") not in (None, "")
    )
    return {
        "included": True,
        "action_type": "pure_cleanup",
        "route_action": route_action,
        "apply_eligible": True,
        "excluded_reason": None,
        "conflicts": [
            {
                "type": "legacy_nonempty_policy_fc",
                "fields": nonempty_policy_fc,
                "resolution": "fc_remove_unlock_only_then_event_clear_lock_empty",
            }
        ] if nonempty_policy_fc else [],
        "event_before": deepcopy(event),
        "event_after": after,
        "event_changes": event_changes(event, after),
        "extended_field_patch": extended_field_patch,
        "identity_patch": {},
        "field_corrections_before": fc_before,
        "field_corrections_after_fc_remove": fc_after_fc_remove,
        "field_corrections_after": fc_after,
        "field_correction_actions": remove_actions + clear_actions,
        "reports": report_plans(reports, after),
        "publisher_resolution": {**publisher, "executable": False},
        "read_only_findings": read_only_findings,
        "periodical": {
            "source_metadata_confirmed": periodical,
            "title_fc_preserved": sorted(title_fc),
            "planned_title_repairs": {},
            "read_only_title_findings": title_findings,
            "executable": False,
        },
        "price_policy": {
            "action": "read_only_finding_fake_placeholder" if fake_price else "preserved",
            "fake_placeholder_allowlist_match": fake_price,
            "real_price_preserved": bool(event.get("price_info")) and not fake_price,
            "executable": False,
        },
    }


def poster_pollution_repair_plan(
    event: dict[str, Any],
    fc_rows: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    publisher: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Evidence and routing only.

    The poster cohort is repaired through the same thirteen-field cleanup as any
    other exact-pure row: the polluted `location_name` FC leaves via `fc-remove`
    and the venue fields are cleared in `event-clear`. The audited date,
    publisher, title, price, and organizer values are retained as read-only
    evidence and are never written, so PUBLICATION_CHANNEL_LOCATION is never
    reintroduced and no non-target `lock_clean` is emitted.
    """
    expected = POSTER_POLLUTION_REPAIRS[str(event["id"])]
    cleanup = pure_plan(
        event,
        fc_rows,
        reports,
        publisher,
        route_action="poster_placeholder_pollution_repair",
    )
    cleanup["pre_actions"] = []
    cleanup["poster_pollution_repair"] = {
        "status": "evidence_only",
        "executable_repair": False,
        "cleanup_scope": list(PUBLICATION_TARGET_FIELDS),
        "read_only_findings": {
            "polluted_location_name": POSTER_POLLUTION_LOCATION,
            "polluted_start_date": POSTER_POLLUTION_START_DATE,
            "audited_clean_start_date": expected["clean_start_date"],
            "audited_publisher": expected.get("publisher"),
            "executable": False,
        },
        "evidence": evidence,
    }
    return cleanup


def eslite_plan(
    event: dict[str, Any],
    fc_rows: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    publisher: dict[str, Any],
) -> dict[str, Any]:
    event_id = str(event["id"])
    after = deepcopy(event)
    after.update(
        {
            "source_id": ESLITE_NEW_SOURCE_ID,
            "source_url": ESLITE_ARTICLE_URL,
            "event_form": ESLITE_PHYSICAL_FORMS,
            "business_hours": ESLITE_BUSINESS_HOURS,
            "business_hours_zh": ESLITE_BUSINESS_HOURS,
            "business_hours_en": ESLITE_BUSINESS_HOURS,
            # Registry-resolved, never preserved: the live row carries the book
            # sales page, which is a purchase channel and not the venue.
            "location_url": ESLITE_VENUE_URL,
            # After the migration `event_form=['lecture']` makes the venue public,
            # so the localized names must hold the registry value; leaving them
            # NULL would fall the EN page back to Japanese.
            "location_name_zh": ESLITE_VENUE_NAME_ZH,
            "location_name_en": ESLITE_VENUE_NAME_EN,
        }
    )
    for field in TITLE_FIELDS:
        after[field] = strip_publication_prefix(after.get(field))

    # Step 1 of the fixed order: leave the exact-pure cohort before any lock.
    identity_patch = {
        field: {"before": event.get(field), "after": after.get(field)}
        for field in ESLITE_IDENTITY_FIELDS
    }

    modes: dict[str, tuple[str, Any]] = {
        "event_form": ("lock_clean", ESLITE_PHYSICAL_FORMS),
        "business_hours": ("lock_clean", ESLITE_BUSINESS_HOURS),
        "business_hours_zh": ("lock_clean", ESLITE_BUSINESS_HOURS),
        "business_hours_en": ("lock_clean", ESLITE_BUSINESS_HOURS),
        "location_url": ("lock_clean", ESLITE_VENUE_URL),
        "location_name_zh": ("lock_clean", ESLITE_VENUE_NAME_ZH),
        "location_name_en": ("lock_clean", ESLITE_VENUE_NAME_EN),
    }
    for field in TITLE_FIELDS:
        if after.get(field) != event.get(field):
            modes[field] = ("lock_clean", after.get(field))
    for field in ("location_name", "location_address", "location_prefectures", "price_info"):
        if after.get(field) not in (None, "", []):
            modes[field] = ("lock_clean", after.get(field))

    fc_before, fc_after_locks, lock_actions = plan_fc_actions(
        event_id,
        fc_rows,
        modes,
        route_action="eslite_physical_identity_migration",
        apply_phase="eslite-identity",
    )

    # Step 2 tail: the stale publication placeholder locks leave through the same
    # audited unlock_only contract while those event fields stay NULL.
    locked_fields = set(modes)
    stale_modes: dict[str, tuple[str, Any]] = {
        field: ("unlock_only", None)
        for field in PUBLICATION_TARGET_FIELDS
        if field not in locked_fields
        and any(
            str(row.get("field_name")) == field
            and not is_human_correction(row)
            and str(decoded_fc_value(row.get("corrected_value")) or "") in PUBLICATION_PLACEHOLDER_VALUES
            for row in fc_after_locks
        )
    }
    _, fc_after, stale_actions = plan_fc_actions(
        event_id,
        fc_after_locks,
        stale_modes,
        route_action="eslite_physical_identity_migration",
        apply_phase="eslite-identity",
    )
    return {
        "included": False,
        "action_type": "eslite_physical_identity_migration",
        "route_action": "eslite_physical_identity_migration",
        "apply_eligible": True,
        "excluded_reason": "physical Eslite Talk excluded from pure cleanup",
        "conflicts": [
            {
                "type": "classification_location_conflict",
                "reason": location_conflict_reason(event) or "known physical Eslite Talk",
            }
        ],
        "event_before": deepcopy(event),
        "event_after": after,
        "event_changes": event_changes(event, after),
        "extended_field_patch": {},
        "identity_patch": identity_patch,
        "field_corrections_before": fc_before,
        "field_corrections_after_fc_remove": fc_after_locks,
        "field_corrections_after": fc_after,
        "field_correction_actions": lock_actions + stale_actions,
        "reports": report_plans(reports, after),
        "publisher_resolution": {**publisher, "executable": False},
        "read_only_findings": {
            "contract": "eslite-identity is the sole named exception that may "
                        "combine event and field-correction writes",
        },
        "migration": {
            "apply_order": [
                "identity_cas_event_form_and_source_identity",
                "audited_physical_field_locks_and_fc_removals",
                "complete_after_checkpoint_verification",
            ],
            "live_remap_performed": False,
            "old_source_id": event.get("source_id"),
            "expected_old_source_id": ESLITE_OLD_SOURCE_ID,
            "new_source_id": ESLITE_NEW_SOURCE_ID,
            "article_url": ESLITE_ARTICLE_URL,
            "physical_forms": ESLITE_PHYSICAL_FORMS,
            # Strictly disjoint by construction: preserved_fields are read off the
            # event row, registry_resolved_fields come from the authoritative
            # `venues` registry. Treating an event value as registry-resolved is
            # exactly the confusion that put a book sales page in location_url.
            "preserved_fields": {
                field: event.get(field)
                for field in (
                    "start_date",
                    "end_date",
                    "location_name",
                    "location_address",
                    "location_prefectures",
                    "venue_id",
                    "price_info",
                )
            },
            "registry_resolved_fields": {
                "location_url": ESLITE_VENUE_URL,
                "location_name_zh": ESLITE_VENUE_NAME_ZH,
                "location_name_en": ESLITE_VENUE_NAME_EN,
            },
        },
        "periodical": {
            "source_metadata_confirmed": False,
            "title_fc_preserved": [],
            "planned_title_repairs": {},
            "read_only_title_findings": {},
            "executable": False,
        },
        "price_policy": {
            "action": "preserved_physical_price",
            "real_price_preserved": True,
            "executable": False,
        },
    }


def excluded_plan(
    event: dict[str, Any],
    fc_rows: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    publisher: dict[str, Any],
    *,
    reason: str,
    conflict_type: str,
) -> dict[str, Any]:
    rows = sorted(deepcopy(fc_rows), key=row_sort_key)
    return {
        "included": False,
        "action_type": "excluded",
        "route_action": "excluded",
        "apply_eligible": False,
        "excluded_reason": reason,
        "conflicts": [{"type": conflict_type, "reason": reason}],
        "event_before": deepcopy(event),
        "event_after": deepcopy(event),
        "event_changes": {},
        "extended_field_patch": {},
        "identity_patch": {},
        "field_corrections_before": rows,
        "field_corrections_after_fc_remove": deepcopy(rows),
        "field_corrections_after": deepcopy(rows),
        "field_correction_actions": [],
        "reports": report_plans(reports, event),
        "publisher_resolution": {**publisher, "executable": False},
        "read_only_findings": {"contract": "excluded candidates emit no executable action"},
        "periodical": {
            "source_metadata_confirmed": False,
            "title_fc_preserved": [],
            "planned_title_repairs": {},
            "read_only_title_findings": {},
            "executable": False,
        },
        "price_policy": {
            "action": "preserved_excluded",
            "real_price_preserved": True,
            "executable": False,
        },
    }


def build_summary(candidates: list[dict[str, Any]], fingerprint: dict[str, Any]) -> dict[str, Any]:
    actions = Counter(candidate["action_type"] for candidate in candidates)
    conflicts = Counter(
        conflict["type"]
        for candidate in candidates
        for conflict in candidate.get("conflicts", [])
    )
    pure = [candidate for candidate in candidates if candidate["action_type"] == "pure_cleanup"]
    return {
        "exact_counts": fingerprint["exact_counts"],
        "fetched_counts": fingerprint["fetched_counts"],
        "candidate_total": len(candidates),
        "included_pure": actions["pure_cleanup"],
        "poster_placeholder_pollution_evidence_rows": sum(
            candidate.get("poster_pollution_repair", {}).get("status") == "evidence_only"
            for candidate in candidates
        ),
        "excluded_human_field_correction": conflicts["human_field_correction"],
        "excluded_mixed": conflicts["mixed_event_form"],
        "excluded_location_conflict": conflicts["classification_location_conflict"],
        "unresolved_non_eslite_location_conflicts": sum(
            candidate["action_type"] != "eslite_physical_identity_migration"
            and any(
                conflict["type"] == "classification_location_conflict"
                for conflict in candidate.get("conflicts", [])
            )
            for candidate in candidates
        ),
        "eslite_migration_actions": actions["eslite_physical_identity_migration"],
        "inactive_mixed_exclusions": sum(
            candidate["action_type"] == "excluded"
            and candidate["classification"]["active"] is False
            and candidate["classification"]["contains_publication_form"]
            for candidate in candidates
        ),
        "fc_conflict_candidates": sum(
            any(conflict["type"] == "legacy_nonempty_policy_fc" for conflict in candidate["conflicts"])
            for candidate in pure
        ),
        "unresolved_publishers": sum(
            candidate["publisher_resolution"]["status"].startswith("unresolved")
            for candidate in pure
        ),
        "resolved_registry_or_existing_homepages": sum(
            candidate["publisher_resolution"]["status"] == "resolved"
            for candidate in pure
        ),
        "periodical_candidates": sum(
            candidate["periodical"]["source_metadata_confirmed"] for candidate in pure
        ),
        "periodical_title_read_only_findings": sum(
            bool(candidate["periodical"]["read_only_title_findings"]) for candidate in pure
        ),
        "fake_price_placeholders_read_only": sum(
            candidate["price_policy"].get("fake_placeholder_allowlist_match") is True
            for candidate in pure
        ),
        "real_prices_preserved": sum(
            candidate["price_policy"].get("real_price_preserved") is True
            for candidate in candidates
        ),
        "fc_remove_actions": sum(
            action["apply_phase"] == "fc-remove"
            for candidate in candidates
            for action in candidate["field_correction_actions"]
        ),
        "event_clear_actions": sum(
            action["apply_phase"] == "event-clear"
            for candidate in candidates
            for action in candidate["field_correction_actions"]
        ),
        "eslite_identity_actions": sum(
            action["apply_phase"] == "eslite-identity"
            for candidate in candidates
            for action in candidate["field_correction_actions"]
        ),
        "planned_null_fields": {
            field: sum(candidate["event_after"].get(field) is None for candidate in pure)
            for field in PUBLICATION_TARGET_FIELDS
        },
        "planned_empty_sentinels": {
            field: sum(
                any(
                    action["field_name"] == field and action["mode"] == "lock_empty"
                    for action in candidate["field_correction_actions"]
                )
                for candidate in pure
            )
            for field in PUBLICATION_NULL_FIELDS
        },
        "planned_extended_field_clears": {
            field: sum(
                (candidate.get("extended_field_patch", {}).get(field) or {}).get("before") is not None
                for candidate in pure
            )
            for field in PUBLICATION_EXTENDED_CLEAR_FIELDS
        },
    }


def assert_no_secret_material(payload: Any) -> None:
    text = json_bytes(payload).decode("utf-8")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise RuntimeError(f"secret-like material detected in output: {pattern.pattern}")
    for env_name in ("SUPABASE_SERVICE_ROLE_KEY", "OPENAI_API_KEY", "GITHUB_TOKEN"):
        value = os.environ.get(env_name)
        if value and len(value) >= 12 and value in text:
            raise RuntimeError(f"environment secret leaked into output: {env_name}")


def checkpoint_preserve_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every existing FC row the manifest promises to leave byte-identical."""
    rows: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        changed = {action["field_name"] for action in candidate["field_correction_actions"]}
        for row in candidate["field_corrections_before"]:
            row_id = row.get("id")
            if not row_id or str(row.get("field_name")) in changed:
                continue
            rows[str(row_id)] = deepcopy(row)
    return sorted(rows.values(), key=row_sort_key)


def executable_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        candidate
        for candidate in candidates
        if candidate["field_correction_actions"]
        or any(
            change.get("before") is not None
            for change in (candidate.get("extended_field_patch") or {}).values()
        )
        or candidate.get("identity_patch")
    ]


def _checkpoint_payload(
    name: str,
    *,
    events: list[dict[str, Any]],
    field_corrections: list[dict[str, Any]],
    preserve: list[dict[str, Any]],
    audits: list[dict[str, Any]],
) -> dict[str, Any]:
    body = {
        "checkpoint": name,
        "events": sorted((checkpoint_event_row(row) for row in events), key=row_sort_key),
        "target_field_corrections": sorted(deepcopy(field_corrections), key=row_sort_key),
        "preserve_field_corrections": sorted(deepcopy(preserve), key=row_sort_key),
        "audit_expectations": sorted(
            deepcopy(audits),
            key=lambda row: (str(row["field_correction_id"]), str(row["field_name"])),
        ),
        "volatile_event_fields_excluded": list(CHECKPOINT_VOLATILE_EVENT_FIELDS),
    }
    return {**body, "sha256": sha256(body)}


def build_checkpoints(candidates: list[dict[str, Any]], *, scope: str) -> dict[str, Any]:
    """Immutable per-phase before/after images.

    Unrelated rows in `events`, `field_corrections`, `event_reports`, or
    `organizers` may change freely: only these scoped images gate a phase apply.
    """
    executable = executable_candidates(candidates)
    preserve = checkpoint_preserve_rows(candidates)

    events_before: list[dict[str, Any]] = []
    events_after: list[dict[str, Any]] = []
    fc_before: list[dict[str, Any]] = []
    fc_after_fc_remove: list[dict[str, Any]] = []
    fc_after: list[dict[str, Any]] = []
    for candidate in executable:
        events_before.append(candidate["event_before"])
        events_after.append(candidate["event_after"])
        fc_before.extend(target_fc_rows(candidate["field_corrections_before"]))
        fc_after_fc_remove.extend(target_fc_rows(candidate["field_corrections_after_fc_remove"]))
        fc_after.extend(target_fc_rows(candidate["field_corrections_after"]))

    def _audits(phase: str) -> list[dict[str, Any]]:
        rows = []
        for candidate in executable:
            for action in candidate["field_correction_actions"]:
                if action["apply_phase"] != phase or action["mode"] != "unlock_only":
                    continue
                rows.append(
                    {
                        "field_correction_id": (action["expected_fc"] or {}).get("id"),
                        "event_id": candidate["event_id"],
                        "field_name": action["field_name"],
                        "operation_status": "applied",
                        "verified_at_required": True,
                        "unlock_reason_template": action["unlock_reason_template"],
                    }
                )
        return rows

    if scope == MANIFEST_SCOPE_ESLITE:
        return {
            "eslite-identity.before": _checkpoint_payload(
                "eslite-identity.before",
                events=events_before,
                field_corrections=fc_before,
                preserve=preserve,
                audits=[],
            ),
            "eslite-identity.after": _checkpoint_payload(
                "eslite-identity.after",
                events=events_after,
                field_corrections=fc_after,
                preserve=preserve,
                audits=_audits("eslite-identity"),
            ),
        }

    fc_remove_audits = _audits("fc-remove")
    return {
        "fc-remove.before": _checkpoint_payload(
            "fc-remove.before",
            events=events_before,
            field_corrections=fc_before,
            preserve=preserve,
            audits=[],
        ),
        # fc-remove must not mutate any event value, so its after-image keeps the
        # before event rows. This payload is also the event-clear before gate.
        "fc-remove.after": _checkpoint_payload(
            "fc-remove.after",
            events=events_before,
            field_corrections=fc_after_fc_remove,
            preserve=preserve,
            audits=fc_remove_audits,
        ),
        "event-clear.after": _checkpoint_payload(
            "event-clear.after",
            events=events_after,
            field_corrections=fc_after,
            preserve=preserve,
            audits=fc_remove_audits,
        ),
    }


def build_manifest(
    state: dict[str, Any],
    *,
    generated_at: str | None = None,
    scope: str = MANIFEST_SCOPE_CLEANUP,
) -> dict[str, Any]:
    if scope not in (MANIFEST_SCOPE_CLEANUP, MANIFEST_SCOPE_ESLITE):
        raise RuntimeError(f"unknown manifest scope: {scope!r}")
    tables = state["tables"]
    fingerprint = state["fingerprint"]
    fc_by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    reports_by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["field_corrections"]:
        if row.get("event_id"):
            fc_by_event[str(row["event_id"])].append(row)
    for row in tables["event_reports"]:
        if row.get("event_id"):
            reports_by_event[str(row["event_id"])].append(row)
    organizer_by_id, organizer_by_name = organizer_indexes(tables["organizers"])
    events_by_source_id = {
        str(event["source_id"]): event
        for event in tables["events"]
        if event.get("source_id")
    }

    events = sorted(
        (event for event in tables["events"] if contains_publication_form(event)),
        key=row_sort_key,
    )
    if scope == MANIFEST_SCOPE_ESLITE:
        events = [event for event in events if str(event["id"]) == ESLITE_TALK_ID]
    candidates: list[dict[str, Any]] = []
    for event in events:
        event_id = str(event["id"])
        classification = classification_evidence(event)
        publisher = publisher_plan(event, organizer_by_id, organizer_by_name)
        fc_rows = fc_by_event.get(event_id, [])
        reports = reports_by_event.get(event_id, [])
        poster_evidence, poster_failures = poster_pollution_evidence(
            event,
            fc_rows,
            events_by_source_id,
        )
        human_locked = human_locked_target_fields(fc_rows)
        if event_id == ESLITE_TALK_ID:
            plan = eslite_plan(event, fc_rows, reports, publisher)
        elif human_locked:
            plan = excluded_plan(
                event,
                fc_rows,
                reports,
                publisher,
                reason=(
                    "human field corrections are a hard cleanup exclusion: "
                    + ", ".join(human_locked)
                ),
                conflict_type="human_field_correction",
            )
        elif poster_evidence and poster_failures:
            plan = excluded_plan(
                event,
                fc_rows,
                reports,
                publisher,
                reason="poster pollution repair evidence incomplete: " + "; ".join(poster_failures),
                conflict_type="classification_location_conflict",
            )
            plan["poster_pollution_repair"] = {
                "status": "conflict",
                "evidence": poster_evidence,
                "failures": poster_failures,
            }
        elif poster_evidence:
            plan = poster_pollution_repair_plan(
                event,
                fc_rows,
                reports,
                publisher,
                poster_evidence,
            )
        elif not is_pure_publication_record(event):
            plan = excluded_plan(
                event,
                fc_rows,
                reports,
                publisher,
                reason="event_form contains publication but is not exact pure",
                conflict_type="mixed_event_form",
            )
        elif classification["location_conflict"]:
            plan = excluded_plan(
                event,
                fc_rows,
                reports,
                publisher,
                reason=classification["location_conflict"],
                conflict_type="classification_location_conflict",
            )
        else:
            plan = pure_plan(event, fc_rows, reports, publisher)
        candidates.append(
            {
                "event_id": event_id,
                "source_identity": {
                    "source_name": event.get("source_name"),
                    "source_id": event.get("source_id"),
                    "source_url": event.get("source_url"),
                    "official_url": event.get("official_url"),
                },
                "updated_at": event.get("updated_at"),
                "before_hash": sha256(event),
                "classification": classification,
                **plan,
            }
        )

    supported_phases = (
        [MANIFEST_SCOPE_ESLITE] if scope == MANIFEST_SCOPE_ESLITE else ["fc-remove", "event-clear"]
    )
    manifest: dict[str, Any] = {
        "schema": {"name": SCHEMA_NAME, "version": SCHEMA_VERSION},
        "wave": WAVE,
        "scope": scope,
        "generated_at": generated_at or now_iso(),
        "mode": "dry-run-read-only",
        "base_read_fingerprint": {**fingerprint, "role": "discovery_evidence_only"},
        "candidate_definition": (
            "event_form normalization contains publication; exact pure helper alone "
            "controls pure cleanup inclusion"
        ),
        "apply_contract": {
            "requires_flags": ["--apply", "--manifest PATH", "--apply-phase PHASE"],
            "supported_apply_phases": supported_phases,
            "apply_phase_is_the_sole_write_selector": True,
            "apply_eligible_is_generation_time_metadata_only": True,
            "route_action_is_provenance_only": True,
            "recompute_planned_changes": False,
            "full_batch_fingerprint_drift_gate_before_any_write": False,
            "base_read_fingerprint_role": "discovery_evidence_only",
            "scoped_checkpoint_gate_before_any_write": True,
            "checkpoint_aliases": dict(CHECKPOINT_ALIASES),
            "phase_effect_boundaries": {
                "fc-remove": {
                    "may_delete_field_corrections": True,
                    "may_append_audit": True,
                    "may_mutate_event_values": False,
                },
                "event-clear": {
                    "may_delete_field_corrections": False,
                    "may_clear_event_values": True,
                    "may_create_canonical_empty_sentinels": True,
                },
                "eslite-identity": {
                    "named_exception": True,
                    "may_mutate_event_values": True,
                    "may_delete_field_corrections": True,
                },
            },
            "executable_target_fields": list(PUBLICATION_TARGET_FIELDS),
            "non_target_findings_are_read_only": [
                "price_info",
                *TITLE_FIELDS,
                "organizer_id",
                "organizer_url",
                "start_date",
                "organizer",
            ],
            "unresolved_non_eslite_classification_conflicts_block_apply": True,
            "rollback_snapshot_tables": list(TABLES),
            "rollback_snapshot_required_before_any_write": True,
            "row_read_back_required": True,
            "candidate_ordering": [
                "manifest_order_by_event_id",
                "phase_selected_actions",
                "row_read_back",
            ],
            "event_clear_write_order": [
                "extended_field_value_cas_patch",
                "canonical_lock_empty_actions",
            ],
            "reports_are_not_written": True,
        },
        "checkpoints": build_checkpoints(candidates, scope=scope),
        "wave2_boundary": deepcopy(WAVE2_BOUNDARY),
        "candidates": candidates,
    }
    manifest["summary"] = build_summary(candidates, fingerprint)
    manifest["manifest_sha256"] = sha256(manifest)
    assert_no_secret_material(manifest)
    return manifest


def assert_ignored_output_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError(f"output must be inside worktree ignored tmp/: {resolved}") from exc
    result = subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "-q", str(relative)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"output path is not ignored by git: {relative}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def write_immutable_json(path: Path, payload: dict[str, Any]) -> None:
    assert_no_secret_material(payload)
    with path.open("xb") as handle:
        handle.write(json_bytes(payload, indent=2) + b"\n")
    path.chmod(0o444)
    if json.loads(path.read_text(encoding="utf-8")) != payload:
        raise RuntimeError(f"immutable JSON read-back mismatch: {path}")


def write_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    resolved = assert_ignored_output_path(path)
    write_immutable_json(resolved, manifest)
    return resolved


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    digest = payload.pop("manifest_sha256", None)
    if digest != sha256(payload):
        raise RuntimeError("manifest hash mismatch; immutable input was modified")
    payload["manifest_sha256"] = digest
    if payload.get("schema") != {"name": SCHEMA_NAME, "version": SCHEMA_VERSION}:
        raise RuntimeError("unsupported publication manifest schema/version")
    if payload.get("wave") != WAVE:
        raise RuntimeError("only Wave 1 manifests are accepted")
    return payload


def snapshot_payload(state: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    snapshot = {
        "schema": {"name": f"{SCHEMA_NAME}/rollback", "version": 1},
        "generated_at": now_iso(),
        "manifest_sha256": manifest["manifest_sha256"],
        "base_read_fingerprint": state["fingerprint"],
        "tables": deepcopy(state["tables"]),
        "rollback_contract": {
            "restore_order": ["organizers", "events", "field_corrections", "event_reports"],
            "delete_new_field_corrections_before_restore": True,
            "upsert_conflict_keys": {
                "events": ["id"],
                "field_corrections": ["event_id", "field_name"],
                "event_reports": ["id"],
                "organizers": ["id"],
            },
            "read_back_every_row": True,
        },
    }
    snapshot["snapshot_sha256"] = sha256(snapshot)
    return snapshot


def default_snapshot_path(manifest_path: Path, apply_phase: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return manifest_path.with_name(f"{manifest_path.stem}.rollback-{apply_phase}-{stamp}.json")


def audited_write(sb, **kwargs: Any) -> bool:
    from qa_auto_fix import unlock_and_write

    return unlock_and_write(sb, **kwargs)


def read_single_event(sb, event_id: str) -> dict[str, Any]:
    return sb.table("events").select("*").eq("id", event_id).single().execute().data or {}


def fetch_rows_in(
    sb,
    table: str,
    column: str,
    values: list[str],
    *,
    columns: str = "*",
) -> list[dict[str, Any]]:
    """Deterministic paginated `IN` fetch scoped to explicit full IDs."""
    unique = sorted({str(value) for value in values if value})
    rows: list[dict[str, Any]] = []
    for start in range(0, len(unique), PAGE_SIZE):
        chunk = unique[start : start + PAGE_SIZE]
        offset = 0
        while True:
            page = with_retry(
                lambda offset=offset, chunk=chunk: (
                    sb.table(table)
                    .select(columns)
                    .in_(column, chunk)
                    .order("id")
                    .range(offset, offset + PAGE_SIZE - 1)
                    .execute()
                ),
                label=f"fetch {table} by {column}",
            )
            batch = list(page.data or [])
            rows.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            offset += len(batch)
    return rows


def observe_checkpoint(sb, expected: dict[str, Any]) -> dict[str, Any]:
    event_ids = [str(row["id"]) for row in expected["events"]]
    preserve_ids = [
        str(row["id"]) for row in expected["preserve_field_corrections"] if row.get("id")
    ]
    events = [checkpoint_event_row(row) for row in fetch_rows_in(sb, "events", "id", event_ids)]
    target = [
        row
        for row in fetch_rows_in(sb, "field_corrections", "event_id", event_ids)
        if is_target_field(row.get("field_name"))
    ]
    preserve = (
        fetch_rows_in(sb, "field_corrections", "id", preserve_ids) if preserve_ids else []
    )
    return {
        "events": sorted(events, key=row_sort_key),
        "target_field_corrections": sorted(target, key=row_sort_key),
        "preserve_field_corrections": sorted(preserve, key=row_sort_key),
    }


def _row_label(row: dict[str, Any]) -> str:
    return str(row.get("id") or "") or json.dumps(row, ensure_ascii=False, sort_keys=True)


def _row_identity(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("event_id") or ""), str(row.get("field_name") or ""))


def _phase_created_row_matches(expected: dict[str, Any], observed: dict[str, Any]) -> bool:
    """Compare a not-yet-created field correction without its assigned id."""
    if not observed.get("id"):
        return False
    return all(
        expected.get(field) == observed.get(field)
        for field in CHECKPOINT_NEW_ROW_MATCH_FIELDS
    )


def structural_row_diff(
    expected: list[dict[str, Any]],
    observed: list[dict[str, Any]],
    *,
    allow_db_assigned_ids: bool = False,
) -> dict[str, Any]:
    """Pair rows by full id, then report what is missing, extra, or changed.

    `allow_db_assigned_ids` relaxes nothing for rows that already exist: every
    before-image row, preserve row, and `unlock_only` delete target still has to
    match on the complete field-correction id. It only lets an after-image pair a
    row the same phase creates (`id is None`) with its live counterpart by
    `(event_id, field_name)` plus every value/provenance column.
    """
    remaining = list(observed)
    missing: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []

    for row in expected:
        if allow_db_assigned_ids and not row.get("id"):
            pending.append(row)
            continue
        index = next(
            (
                position
                for position, other in enumerate(remaining)
                if _row_label(other) == _row_label(row)
            ),
            None,
        )
        if index is None:
            missing.append(row)
            continue
        if remaining.pop(index) != row:
            changed.append(row)

    for row in pending:
        matches = [
            position
            for position, other in enumerate(remaining)
            if _row_identity(other) == _row_identity(row)
        ]
        if len(matches) != 1:
            missing.append(row)
            continue
        if not _phase_created_row_matches(row, remaining.pop(matches[0])):
            changed.append(row)

    return {
        "missing": sorted(_row_label(row) for row in missing),
        "unexpected": sorted(_row_label(row) for row in remaining),
        "changed": sorted(_row_label(row) for row in changed),
    }


def verify_checkpoint_audits(
    sb,
    expected: dict[str, Any],
    manifest_digest: str,
    *,
    remediation: str = "zero writes performed",
) -> None:
    for row in expected.get("audit_expectations", []):
        reason = expand_unlock_reason(row["unlock_reason_template"], manifest_digest)
        audits = (
            sb.table("field_corrections_audit")
            .select("id,field_correction_id,event_id,field_name,operation_status,verified_at,unlock_reason")
            .eq("field_correction_id", row["field_correction_id"])
            .eq("unlock_reason", reason)
            .execute()
            .data
            or []
        )
        applied = [
            audit
            for audit in audits
            if audit.get("operation_status") == row["operation_status"]
            and audit.get("verified_at")
            and str(audit.get("event_id")) == str(row["event_id"])
            and str(audit.get("field_name")) == str(row["field_name"])
        ]
        if len(applied) != 1:
            raise RuntimeError(
                "STOP: audit anchor mismatch for field_correction_id="
                f"{row['field_correction_id']}: expected exactly 1 applied row, "
                f"got {len(applied)}; {remediation}"
            )


def checkpoint_stop_language(
    is_after_gate: bool,
    write_context: dict[str, Any] | None,
) -> tuple[str, str]:
    """Return `(drift_marker, remediation)` for a failed checkpoint gate.

    A before gate is the only place that may claim `zero writes performed`. An
    after gate runs once the phase has already written, so it always names the
    rollback snapshot and what was applied instead.
    """
    if not is_after_gate:
        return "", "zero writes performed"
    if not write_context:
        return " AFTER writes", "manual rollback verification required"
    return (
        " AFTER writes",
        f"rollback snapshot={write_context['rollback_snapshot']}; "
        f"applied_event_ids={write_context['applied_event_ids']}; "
        f"fc_created={write_context['fc_created']}; "
        f"fc_deleted={write_context['fc_deleted']}; "
        "manual rollback required",
    )


def verify_checkpoint(
    sb,
    manifest: dict[str, Any],
    checkpoint_name: str,
    *,
    is_after_gate: bool = False,
    write_context: dict[str, Any] | None = None,
) -> None:
    name = CHECKPOINT_ALIASES.get(checkpoint_name, checkpoint_name)
    marker, remediation = checkpoint_stop_language(is_after_gate, write_context)
    checkpoints = manifest.get("checkpoints") or {}
    if name not in checkpoints:
        raise RuntimeError(f"STOP: manifest has no {name} checkpoint; {remediation}")
    expected = checkpoints[name]
    body = {key: value for key, value in expected.items() if key != "sha256"}
    if sha256(body) != expected.get("sha256"):
        raise RuntimeError(f"STOP: {name} checkpoint digest mismatch; {remediation}")

    observed = observe_checkpoint(sb, expected)
    # Only this phase's own after-image can contain rows the phase creates, and
    # only in the target set. The caller states that explicitly: a `.after`
    # payload reused as the next phase's before gate (`event-clear`) is still a
    # before gate and stays id-exact, as do events and preserve rows.
    for key in ("events", "target_field_corrections", "preserve_field_corrections"):
        diff = structural_row_diff(
            expected[key],
            observed[key],
            allow_db_assigned_ids=is_after_gate and key == "target_field_corrections",
        )
        if any(diff.values()):
            raise RuntimeError(
                f"STOP: {name} {key} drift{marker}; {remediation}: {diff}"
            )
    verify_checkpoint_audits(
        sb, expected, manifest["manifest_sha256"], remediation=remediation
    )


def phase_snapshot_payload(
    sb,
    manifest: dict[str, Any],
    apply_phase: str,
) -> dict[str, Any]:
    expected = manifest["checkpoints"][CHECKPOINT_BEFORE[apply_phase]]
    snapshot = {
        "schema": {"name": f"{SCHEMA_NAME}/rollback", "version": 2},
        "generated_at": now_iso(),
        "manifest_sha256": manifest["manifest_sha256"],
        "apply_phase": apply_phase,
        "checkpoint": CHECKPOINT_BEFORE[apply_phase],
        "checkpoint_sha256": expected["sha256"],
        "observed": observe_checkpoint(sb, expected),
        "rollback_contract": {
            "restore_order": ["events", "field_corrections"],
            "delete_new_field_corrections_before_restore": True,
            "upsert_conflict_keys": {
                "events": ["id"],
                "field_corrections": ["event_id", "field_name"],
            },
            "read_back_every_row": True,
        },
    }
    snapshot["snapshot_sha256"] = sha256(snapshot)
    return snapshot


def phase_actions(candidate: dict[str, Any], apply_phase: str) -> list[dict[str, Any]]:
    return [
        action
        for action in candidate["field_correction_actions"]
        if action.get("apply_phase") == apply_phase
    ]


def phase_candidates(manifest: dict[str, Any], apply_phase: str) -> list[dict[str, Any]]:
    """Selected by apply_phase alone — never by `apply_eligible` or route_action."""
    selected = []
    for candidate in manifest["candidates"]:
        has_actions = bool(phase_actions(candidate, apply_phase))
        has_event_work = False
        if apply_phase == "event-clear":
            has_event_work = any(
                change.get("before") is not None
                for change in (candidate.get("extended_field_patch") or {}).values()
            )
        elif apply_phase == "eslite-identity":
            has_event_work = any(
                change.get("before") != change.get("after")
                for change in (candidate.get("identity_patch") or {}).values()
            )
        if has_actions or has_event_work:
            selected.append(candidate)
    return selected


def verify_candidate_read_back(sb, candidate: dict[str, Any], *, apply_phase: str) -> None:
    event_id = candidate["event_id"]
    event = read_single_event(sb, event_id)
    if apply_phase != "fc-remove":
        for field, change in candidate["event_changes"].items():
            if event.get(field) != change["after"]:
                raise RuntimeError(
                    f"event read-back mismatch {event_id}.{field}: "
                    f"expected={change['after']!r} actual={event.get(field)!r}"
                )
    else:
        for field, change in candidate["event_changes"].items():
            if event.get(field) != change["before"]:
                raise RuntimeError(
                    f"fc-remove must not mutate events; {event_id}.{field} changed: "
                    f"expected={change['before']!r} actual={event.get(field)!r}"
                )

    actions = {action["field_name"]: action for action in phase_actions(candidate, apply_phase)}
    if not actions:
        return
    rows = (
        sb.table("field_corrections")
        .select("*")
        .eq("event_id", event_id)
        .in_("field_name", sorted(actions))
        .execute()
        .data
        or []
    )
    by_field = {row.get("field_name"): row for row in rows}
    for field, action in actions.items():
        if action["mode"] == "unlock_only":
            if field in by_field:
                raise RuntimeError(
                    f"FC read-back mismatch {event_id}.{field}: expected absent, "
                    f"actual={by_field[field].get('corrected_value')!r}"
                )
            continue
        expected = "" if action["mode"] == "lock_empty" else fc_value(action["new_value"])
        actual = by_field.get(field, {}).get("corrected_value")
        if actual != expected:
            raise RuntimeError(
                f"FC read-back mismatch {event_id}.{field}: expected={expected!r} actual={actual!r}"
            )


def same_value(left: Any, right: Any) -> bool:
    if isinstance(left, (list, tuple)) or isinstance(right, (list, tuple)):
        return list(left or []) == list(right or [])
    return left == right


def classify_live_state(
    live: dict[str, Any],
    plan: dict[str, dict[str, Any]],
    *,
    label: str,
    event_id: str,
) -> str:
    """Exact before-state or exact after-state only; any third state stops."""
    if all(same_value(live.get(field), change["after"]) for field, change in plan.items()):
        return "after"
    if all(same_value(live.get(field), change["before"]) for field, change in plan.items()):
        return "before"
    raise RuntimeError(
        f"{label} found a third state for {event_id}: "
        + repr({field: live.get(field) for field in sorted(plan)})
    )


def execute_extended_field_cas(sb, candidate: dict[str, Any]) -> int:
    """Clear only the six extended fields under a value-level CAS predicate."""
    plan = candidate.get("extended_field_patch") or {}
    if not plan or all(change.get("before") is None for change in plan.values()):
        return 0
    event_id = candidate["event_id"]
    live = read_single_event(sb, event_id)
    if classify_live_state(live, plan, label="extended-field CAS", event_id=event_id) == "after":
        return 0
    patch = {field: plan[field]["after"] for field in PUBLICATION_EXTENDED_CLEAR_FIELDS}
    query = sb.table("events").update(patch).eq("id", event_id)
    query = apply_cas_filter(
        query,
        "event_form",
        normalize_event_forms(candidate["event_before"].get("event_form")),
    )
    for field in PUBLICATION_EXTENDED_CLEAR_FIELDS:
        query = apply_cas_filter(query, field, plan[field]["before"])
    rows = (query.select("id").execute()).data or []
    if len(rows) != 1:
        raise RuntimeError(
            f"extended-field CAS affected {len(rows)} row(s), expected exactly 1: {event_id}"
        )
    return 1


def execute_identity_patch(sb, candidate: dict[str, Any]) -> int:
    """Eslite step 1: leave the exact-pure cohort before any physical lock."""
    plan = candidate.get("identity_patch") or {}
    changed = {
        field: change
        for field, change in plan.items()
        if change.get("before") != change.get("after")
    }
    if not changed:
        return 0
    event_id = candidate["event_id"]
    live = read_single_event(sb, event_id)
    if classify_live_state(live, plan, label="identity CAS", event_id=event_id) == "after":
        return 0
    query = sb.table("events").update(
        {field: change["after"] for field, change in sorted(changed.items())}
    ).eq("id", event_id)
    for field, change in sorted(plan.items()):
        query = apply_cas_filter(query, field, change["before"])
    rows = (query.select("id").execute()).data or []
    if len(rows) != 1:
        raise RuntimeError(
            f"identity CAS affected {len(rows)} row(s), expected exactly 1: {event_id}"
        )
    return 1


def execute_candidate(
    sb,
    candidate: dict[str, Any],
    *,
    apply_phase: str,
    manifest_digest: str,
) -> dict[str, int]:
    if apply_phase not in APPLY_PHASES:
        raise RuntimeError(f"unknown apply_phase: {apply_phase!r}")
    event_id = candidate["event_id"]
    actions = phase_actions(candidate, apply_phase)
    allowed = PHASE_ALLOWED_FC_MODES[apply_phase]
    for action in actions:
        if action["mode"] not in allowed:
            raise RuntimeError(
                f"apply_phase {apply_phase!r} forbids mode {action['mode']!r}: "
                f"{event_id}.{action['field_name']}"
            )

    if apply_phase == "eslite-identity":
        execute_identity_patch(sb, candidate)
    elif apply_phase == "event-clear":
        execute_extended_field_cas(sb, candidate)

    before = candidate["event_before"]
    expected_form = (
        ESLITE_PHYSICAL_FORMS
        if apply_phase == "eslite-identity"
        else normalize_event_forms(before.get("event_form"))
    )
    counts = {"fc_created": 0, "fc_deleted": 0}
    for action in actions:
        kwargs: dict[str, Any] = {
            "event_id": event_id,
            "field_name": action["field_name"],
            "new_value": action["new_value"],
            "mode": action["mode"],
            "unlock_reason": expand_unlock_reason(
                action["unlock_reason_template"], manifest_digest
            ),
            "report_id": action.get("report_id"),
            "r_class": "publication_policy",
            "dry_run": False,
            "expected_fc": action["expected_fc"],
        }
        if action["mode"] != "unlock_only":
            # Identity fields were already moved by step 1 of the fixed order.
            identity = (candidate.get("identity_patch") or {}).get(action["field_name"])
            kwargs["expected_event_value"] = (
                identity["after"] if identity else before.get(action["field_name"])
            )
            kwargs["expected_event_form"] = expected_form
        ok = audited_write(sb, **kwargs)
        if not ok:
            raise RuntimeError(f"audited field write failed: {event_id}.{action['field_name']}")
        if action["mode"] == "unlock_only":
            counts["fc_deleted"] += 1
        elif not action["expected_fc"]:
            # An expected_fc row already exists, so only an absent one is created.
            counts["fc_created"] += 1

    verify_candidate_read_back(sb, candidate, apply_phase=apply_phase)
    return counts


def assert_cleanup_manifest_excludes_eslite(manifest: dict[str, Any]) -> None:
    """A cleanup manifest generated before the Eslite migration is unusable.

    Its `fc-remove.after` image carries the locks only `eslite-identity` creates,
    so the phase would write the pure cohort and only then fail its own gate.
    """
    if manifest.get("scope") != MANIFEST_SCOPE_CLEANUP:
        return
    stale = [
        candidate["event_id"]
        for candidate in manifest.get("candidates") or []
        if candidate.get("action_type") == "eslite_physical_identity_migration"
    ]
    if stale:
        raise RuntimeError(
            "STOP: cleanup manifest still contains eslite_physical_identity_migration "
            f"candidates {stale}; zero writes performed. Apply --scope eslite-identity "
            "first, read back the migrated rows, then regenerate the cleanup manifest."
        )


def apply_manifest(
    sb,
    manifest: dict[str, Any],
    *,
    manifest_path: Path,
    apply_phase: str,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    assert_ignored_output_path(manifest_path)
    if apply_phase not in APPLY_PHASES:
        raise RuntimeError(f"STOP: unknown apply_phase {apply_phase!r}; zero writes performed")
    supported = manifest.get("apply_contract", {}).get("supported_apply_phases") or []
    if apply_phase not in supported:
        raise RuntimeError(
            f"STOP: manifest does not support apply_phase={apply_phase}; zero writes performed"
        )
    assert_cleanup_manifest_excludes_eslite(manifest)
    unresolved_classification = [
        candidate["event_id"]
        for candidate in manifest["candidates"]
        if candidate["action_type"] != "eslite_physical_identity_migration"
        and any(
            conflict["type"] == "classification_location_conflict"
            for conflict in candidate.get("conflicts", [])
        )
    ]
    if unresolved_classification:
        raise RuntimeError(
            "STOP: unresolved classification/location conflicts in manifest; "
            f"zero writes performed: {unresolved_classification}"
        )

    # Scoped checkpoint gate. Unrelated whole-table drift is discovery evidence
    # only and never invalidates a phase.
    verify_checkpoint(sb, manifest, CHECKPOINT_BEFORE[apply_phase], is_after_gate=False)

    snapshot_target = assert_ignored_output_path(
        snapshot_path or default_snapshot_path(manifest_path, apply_phase)
    )
    write_immutable_json(snapshot_target, phase_snapshot_payload(sb, manifest, apply_phase))
    digest = manifest["manifest_sha256"]
    applied: list[str] = []
    fc_created = 0
    fc_deleted = 0
    try:
        for candidate in phase_candidates(manifest, apply_phase):
            counts = execute_candidate(
                sb, candidate, apply_phase=apply_phase, manifest_digest=digest
            )
            applied.append(candidate["event_id"])
            fc_created += counts["fc_created"]
            fc_deleted += counts["fc_deleted"]
    except Exception as exc:
        raise RuntimeError(
            f"apply stopped after {len(applied)} row(s); rollback snapshot={snapshot_target}; "
            f"applied_event_ids={applied}; error={exc}"
        ) from exc
    verify_checkpoint(
        sb,
        manifest,
        CHECKPOINT_AFTER[apply_phase],
        is_after_gate=True,
        write_context={
            "rollback_snapshot": str(snapshot_target),
            "applied_event_ids": applied,
            "fc_created": fc_created,
            "fc_deleted": fc_deleted,
        },
    )
    return {
        "apply_phase": apply_phase,
        "applied_total": len(applied),
        "applied_event_ids": applied,
        "rollback_snapshot": str(snapshot_target),
        "reports_written": 0,
        "wave2_provider_calls": 0,
    }


def default_manifest_path(scope: str = MANIFEST_SCOPE_CLEANUP) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = "wave1-eslite-manifest" if scope == MANIFEST_SCOPE_ESLITE else "wave1-manifest"
    return ROOT / "tmp" / "publication-policy" / f"{prefix}-{stamp}.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publication Wave 1 immutable manifest")
    parser.add_argument("--manifest-output", type=Path, help="Ignored JSON path for dry-run output")
    parser.add_argument(
        "--scope",
        choices=(MANIFEST_SCOPE_CLEANUP, MANIFEST_SCOPE_ESLITE),
        default=MANIFEST_SCOPE_CLEANUP,
        help="Dry-run manifest scope; eslite-identity emits the pre-cleanup manifest",
    )
    parser.add_argument("--apply", action="store_true", help="Apply one immutable manifest")
    parser.add_argument("--manifest", type=Path, help="Existing immutable manifest accepted by --apply")
    parser.add_argument(
        "--apply-phase",
        choices=APPLY_PHASES,
        help="Sole write selector; required with --apply --manifest",
    )
    parser.add_argument("--rollback-snapshot", type=Path, help="Ignored snapshot path for future apply")
    args = parser.parse_args(argv)
    if args.apply and not args.manifest:
        parser.error("--apply requires --manifest PATH")
    if not args.apply and args.manifest:
        parser.error("--manifest is only accepted with --apply")
    if args.apply and args.manifest_output:
        parser.error("--manifest-output cannot be combined with --apply")
    if not args.apply and args.rollback_snapshot:
        parser.error("--rollback-snapshot is only accepted with --apply")
    if args.apply and args.manifest and not args.apply_phase:
        parser.error("--apply --manifest requires --apply-phase PHASE")
    if not args.apply and args.apply_phase:
        parser.error("--apply-phase is only accepted with --apply --manifest")
    if not args.apply and args.scope not in (MANIFEST_SCOPE_CLEANUP, MANIFEST_SCOPE_ESLITE):
        parser.error("--scope must be cleanup or eslite-identity")
    return args


def main() -> None:
    args = parse_args()
    sb = get_supabase(read_only=not args.apply)
    if args.apply:
        manifest_path = args.manifest.expanduser().resolve()
        result = apply_manifest(
            sb,
            load_manifest(manifest_path),
            manifest_path=manifest_path,
            apply_phase=args.apply_phase,
            snapshot_path=args.rollback_snapshot,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    state = read_database_state(sb)
    manifest = build_manifest(state, scope=args.scope)
    output = write_manifest(
        args.manifest_output or default_manifest_path(args.scope), manifest
    )
    print(json.dumps({"manifest": str(output), "summary": manifest["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
