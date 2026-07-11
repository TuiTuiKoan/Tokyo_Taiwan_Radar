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

SCHEMA_NAME = "tokyo-taiwan-radar/publication-legacy-repair"
SCHEMA_VERSION = 2
WAVE = "wave1"
PAGE_SIZE = 500
ROOT = Path(__file__).resolve().parents[1]
TABLES = ("events", "field_corrections", "event_reports", "organizers")

ESLITE_TALK_ID = "50c83c11-ed64-481a-bb5a-caa3e9981943"
ESLITE_OLD_SOURCE_ID = "eslite_spectrum_9"
ESLITE_NEW_SOURCE_ID = "eslite_spectrum_f0039984-3181-450d-8b59-e024a8eea070"
ESLITE_ARTICLE_URL = "https://www.eslitespectrum.jp/news/f0039984-3181-450d-8b59-e024a8eea070"
ESLITE_PHYSICAL_FORMS = ["lecture"]

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
    phase: str = "pure_cleanup",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_field = {str(row.get("field_name")): deepcopy(row) for row in before_rows}
    actions: list[dict[str, Any]] = []
    for field, (mode, value) in field_modes.items():
        existing = by_field.get(field)
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
                "phase": phase,
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
) -> dict[str, Any]:
    after = deepcopy(event)
    for field in PUBLICATION_NULL_FIELDS:
        after[field] = None
    after["location_url"] = None
    modes: dict[str, tuple[str, Any]] = {
        field: ("lock_empty", None) for field in PUBLICATION_NULL_FIELDS
    }

    price_action = "preserved"
    if is_fake_price(event.get("price_info")):
        after["price_info"] = None
        modes["price_info"] = ("lock_empty", None)
        price_action = "cleared_explicit_fake_placeholder"

    title_fc = {
        str(row.get("field_name"))
        for row in fc_rows
        if row.get("field_name") in TITLE_FIELDS
    }
    periodical = is_ndl_periodical_article(event)
    title_repairs: dict[str, str] = {}
    if periodical:
        for field, label in PERIODICAL_LABELS.items():
            if field in title_fc:
                continue
            repaired = periodical_title(after.get(field), label)
            if repaired and repaired != after.get(field):
                after[field] = repaired
                modes[field] = ("lock_clean", repaired)
                title_repairs[field] = "source_evidence_repaired"

    organizer = publisher.get("organizer_before")
    if organizer:
        after["organizer_id"] = organizer.get("id")
    if publisher.get("accepted_homepage"):
        after["organizer_url"] = publisher["accepted_homepage"]

    fc_before, fc_after, actions = plan_fc_actions(str(event["id"]), fc_rows, modes)
    nonempty_policy_fc = sorted(
        str(row.get("field_name"))
        for row in fc_rows
        if row.get("field_name") in PUBLICATION_NULL_FIELDS
        and row.get("corrected_value") not in (None, "")
    )
    return {
        "included": True,
        "action_type": "pure_cleanup",
        "apply_eligible": True,
        "excluded_reason": None,
        "conflicts": [
            {
                "type": "legacy_nonempty_policy_fc",
                "fields": nonempty_policy_fc,
                "resolution": "unlock_and_write_lock_empty",
            }
        ] if nonempty_policy_fc else [],
        "event_before": deepcopy(event),
        "event_after": after,
        "event_changes": event_changes(event, after),
        "field_corrections_before": fc_before,
        "field_corrections_after": fc_after,
        "field_correction_actions": actions,
        "reports": report_plans(reports, after),
        "publisher_resolution": publisher,
        "periodical": {
            "source_metadata_confirmed": periodical,
            "title_fc_preserved": sorted(title_fc),
            "planned_title_repairs": title_repairs,
        },
        "price_policy": {
            "action": price_action,
            "fake_placeholder_allowlist_match": is_fake_price(event.get("price_info")),
            "real_price_preserved": bool(event.get("price_info")) and not is_fake_price(event.get("price_info")),
        },
    }

def poster_pollution_repair_plan(
    event: dict[str, Any],
    fc_rows: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    publisher: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    expected = POSTER_POLLUTION_REPAIRS[str(event["id"])]
    repaired = deepcopy(event)
    repaired["location_name"] = PUBLICATION_CHANNEL_LOCATION
    repaired["start_date"] = expected["clean_start_date"]
    repair_modes: dict[str, tuple[str, Any]] = {
        "location_name": ("lock_clean", PUBLICATION_CHANNEL_LOCATION),
        "start_date": ("lock_clean", expected["clean_start_date"]),
    }
    if expected.get("publisher"):
        repaired["organizer"] = expected["publisher"]
        repair_modes["organizer"] = ("lock_clean", expected["publisher"])

    fc_before, fc_after_repair, repair_actions = plan_fc_actions(
        str(event["id"]),
        fc_rows,
        repair_modes,
        phase="poster_placeholder_pollution_repair",
    )
    cleanup = pure_plan(repaired, fc_after_repair, reports, publisher)
    cleanup["event_before"] = deepcopy(event)
    cleanup["event_changes"] = event_changes(event, cleanup["event_after"])
    cleanup["field_corrections_before"] = fc_before
    cleanup["field_correction_actions"] = repair_actions + cleanup["field_correction_actions"]
    cleanup["pre_actions"] = [
        {
            "action_type": "poster_placeholder_pollution_repair",
            "ordering": "before_pure_cleanup",
            "event_changes": event_changes(event, repaired),
            "field_correction_actions": repair_actions,
            "evidence": evidence,
        }
    ]
    cleanup["poster_pollution_repair"] = {
        "status": "planned",
        "location_name": PUBLICATION_CHANNEL_LOCATION,
        "start_date": expected["clean_start_date"],
        "organizer": expected.get("publisher"),
        "evidence": evidence,
    }
    return cleanup


def eslite_plan(
    event: dict[str, Any],
    fc_rows: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    publisher: dict[str, Any],
) -> dict[str, Any]:
    after = deepcopy(event)
    after.update(
        {
            "source_id": ESLITE_NEW_SOURCE_ID,
            "source_url": ESLITE_ARTICLE_URL,
            "event_form": ESLITE_PHYSICAL_FORMS,
            "business_hours": "13:00〜",
            "business_hours_zh": "13:00〜",
            "business_hours_en": "13:00〜",
        }
    )
    for field in TITLE_FIELDS:
        after[field] = strip_publication_prefix(after.get(field))

    modes: dict[str, tuple[str, Any]] = {
        "event_form": ("lock_clean", ESLITE_PHYSICAL_FORMS),
        "business_hours": ("lock_clean", "13:00〜"),
        "business_hours_zh": ("lock_clean", "13:00〜"),
        "business_hours_en": ("lock_clean", "13:00〜"),
    }
    for field in TITLE_FIELDS:
        if after.get(field) != event.get(field):
            modes[field] = ("lock_clean", after.get(field))
    for field in ("location_name", "location_address", "location_prefectures", "price_info"):
        if after.get(field) not in (None, "", []):
            modes[field] = ("lock_clean", after.get(field))
    fc_before, fc_after, actions = plan_fc_actions(str(event["id"]), fc_rows, modes)
    return {
        "included": False,
        "action_type": "eslite_physical_identity_migration",
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
        "field_corrections_before": fc_before,
        "field_corrections_after": fc_after,
        "field_correction_actions": actions,
        "reports": report_plans(reports, after),
        "publisher_resolution": publisher,
        "migration": {
            "live_remap_performed": False,
            "old_source_id": event.get("source_id"),
            "expected_old_source_id": ESLITE_OLD_SOURCE_ID,
            "new_source_id": ESLITE_NEW_SOURCE_ID,
            "article_url": ESLITE_ARTICLE_URL,
            "physical_forms": ESLITE_PHYSICAL_FORMS,
            "preserved_fields": {
                field: event.get(field)
                for field in (
                    "start_date",
                    "end_date",
                    "location_name",
                    "location_address",
                    "location_prefectures",
                    "location_url",
                    "venue_id",
                    "price_info",
                )
            },
        },
        "periodical": {
            "source_metadata_confirmed": False,
            "title_fc_preserved": [],
            "planned_title_repairs": {},
        },
        "price_policy": {"action": "preserved_physical_price", "real_price_preserved": True},
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
    return {
        "included": False,
        "action_type": "excluded",
        "apply_eligible": False,
        "excluded_reason": reason,
        "conflicts": [{"type": conflict_type, "reason": reason}],
        "event_before": deepcopy(event),
        "event_after": deepcopy(event),
        "event_changes": {},
        "field_corrections_before": sorted(deepcopy(fc_rows), key=row_sort_key),
        "field_corrections_after": sorted(deepcopy(fc_rows), key=row_sort_key),
        "field_correction_actions": [],
        "reports": report_plans(reports, event),
        "publisher_resolution": publisher,
        "periodical": {
            "source_metadata_confirmed": False,
            "title_fc_preserved": [],
            "planned_title_repairs": {},
        },
        "price_policy": {"action": "preserved_excluded", "real_price_preserved": True},
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
        "poster_placeholder_pollution_repair_actions": sum(
            any(
                action.get("action_type") == "poster_placeholder_pollution_repair"
                for action in candidate.get("pre_actions", [])
            )
            for candidate in candidates
        ),
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
        "periodical_title_repairs": sum(
            bool(candidate["periodical"]["planned_title_repairs"]) for candidate in pure
        ),
        "fake_price_placeholders_to_clear": sum(
            candidate["price_policy"].get("action") == "cleared_explicit_fake_placeholder"
            for candidate in pure
        ),
        "real_prices_preserved": sum(
            candidate["price_policy"].get("real_price_preserved") is True
            for candidate in candidates
        ),
        "planned_null_fields": {
            field: sum(candidate["event_after"].get(field) is None for candidate in pure)
            for field in PUBLICATION_NULL_FIELDS
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


def build_manifest(state: dict[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
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
        if event_id == ESLITE_TALK_ID:
            plan = eslite_plan(event, fc_rows, reports, publisher)
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
            repaired = deepcopy(event)
            repaired["organizer"] = POSTER_POLLUTION_REPAIRS[event_id].get("publisher") or event.get("organizer")
            repaired_publisher = publisher_plan(repaired, organizer_by_id, organizer_by_name)
            plan = poster_pollution_repair_plan(
                event,
                fc_rows,
                reports,
                repaired_publisher,
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

    manifest: dict[str, Any] = {
        "schema": {"name": SCHEMA_NAME, "version": SCHEMA_VERSION},
        "wave": WAVE,
        "generated_at": generated_at or now_iso(),
        "mode": "dry-run-read-only",
        "base_read_fingerprint": fingerprint,
        "candidate_definition": (
            "event_form normalization contains publication; exact pure helper alone "
            "controls pure cleanup inclusion"
        ),
        "apply_contract": {
            "requires_flags": ["--apply", "--manifest PATH"],
            "recompute_planned_changes": False,
            "full_batch_fingerprint_drift_gate_before_any_write": True,
            "unresolved_non_eslite_classification_conflicts_block_apply": True,
            "rollback_snapshot_tables": list(TABLES),
            "rollback_snapshot_required_before_any_write": True,
            "row_read_back_required": True,
            "candidate_ordering": [
                "poster_placeholder_pollution_repair",
                "pure_cleanup",
                "row_read_back",
            ],
            "reports_are_not_written": True,
        },
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


def default_snapshot_path(manifest_path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return manifest_path.with_name(f"{manifest_path.stem}.rollback-{stamp}.json")


def audited_write(sb, **kwargs: Any) -> bool:
    from qa_auto_fix import unlock_and_write

    return unlock_and_write(sb, **kwargs)


def read_single_event(sb, event_id: str) -> dict[str, Any]:
    return sb.table("events").select("*").eq("id", event_id).single().execute().data or {}


def verify_candidate_read_back(sb, candidate: dict[str, Any]) -> None:
    event_id = candidate["event_id"]
    event = read_single_event(sb, event_id)
    for field, change in candidate["event_changes"].items():
        if event.get(field) != change["after"]:
            raise RuntimeError(
                f"event read-back mismatch {event_id}.{field}: "
                f"expected={change['after']!r} actual={event.get(field)!r}"
            )
    actions = {action["field_name"]: action for action in candidate["field_correction_actions"]}
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
        expected = "" if action["mode"] == "lock_empty" else fc_value(action["new_value"])
        actual = by_field.get(field, {}).get("corrected_value")
        if actual != expected:
            raise RuntimeError(
                f"FC read-back mismatch {event_id}.{field}: expected={expected!r} actual={actual!r}"
            )


def execute_candidate(sb, candidate: dict[str, Any]) -> None:
    event_id = candidate["event_id"]
    audited_fields = {action["field_name"] for action in candidate["field_correction_actions"]}
    for action in candidate["field_correction_actions"]:
        ok = audited_write(
            sb,
            event_id=event_id,
            field_name=action["field_name"],
            new_value=action["new_value"],
            mode=action["mode"],
            unlock_reason=f"publication_manifest_{action.get('phase', candidate['action_type'])}",
            report_id=action.get("report_id"),
            r_class="publication_policy",
            dry_run=False,
        )
        if not ok:
            raise RuntimeError(f"audited field write failed: {event_id}.{action['field_name']}")
    patch = {
        field: change["after"]
        for field, change in candidate["event_changes"].items()
        if field not in audited_fields
    }
    if patch:
        result = sb.table("events").update(patch).eq("id", event_id).select("id").execute()
        if len(result.data or []) != 1:
            raise RuntimeError(f"event update affected unexpected row count: {event_id}")
    verify_candidate_read_back(sb, candidate)


def apply_manifest(
    sb,
    manifest: dict[str, Any],
    *,
    manifest_path: Path,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    assert_ignored_output_path(manifest_path)
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
    current = read_database_state(sb)
    if current["fingerprint"] != manifest["base_read_fingerprint"]:
        raise RuntimeError("STOP: database drift detected before writes; zero writes performed")

    snapshot_target = assert_ignored_output_path(snapshot_path or default_snapshot_path(manifest_path))
    write_immutable_json(snapshot_target, snapshot_payload(current, manifest))
    applied: list[str] = []
    try:
        eligible = sorted(
            (candidate for candidate in manifest["candidates"] if candidate.get("apply_eligible")),
            key=lambda candidate: candidate["action_type"] != "eslite_physical_identity_migration",
        )
        for candidate in eligible:
            execute_candidate(sb, candidate)
            applied.append(candidate["event_id"])
    except Exception as exc:
        raise RuntimeError(
            f"apply stopped after {len(applied)} row(s); rollback snapshot={snapshot_target}; "
            f"applied_event_ids={applied}; error={exc}"
        ) from exc
    return {
        "applied_total": len(applied),
        "applied_event_ids": applied,
        "rollback_snapshot": str(snapshot_target),
        "reports_written": 0,
        "wave2_provider_calls": 0,
    }


def default_manifest_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT / "tmp" / "publication-policy" / f"wave1-manifest-{stamp}.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publication Wave 1 immutable manifest")
    parser.add_argument("--manifest-output", type=Path, help="Ignored JSON path for dry-run output")
    parser.add_argument("--apply", action="store_true", help="Apply one immutable manifest")
    parser.add_argument("--manifest", type=Path, help="Existing immutable manifest accepted by --apply")
    parser.add_argument("--rollback-snapshot", type=Path, help="Ignored snapshot path for future apply")
    args = parser.parse_args()
    if args.apply and not args.manifest:
        parser.error("--apply requires --manifest PATH")
    if not args.apply and args.manifest:
        parser.error("--manifest is only accepted with --apply")
    if args.apply and args.manifest_output:
        parser.error("--manifest-output cannot be combined with --apply")
    if not args.apply and args.rollback_snapshot:
        parser.error("--rollback-snapshot is only accepted with --apply")
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
            snapshot_path=args.rollback_snapshot,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    state = read_database_state(sb)
    manifest = build_manifest(state)
    output = write_manifest(args.manifest_output or default_manifest_path(), manifest)
    print(json.dumps({"manifest": str(output), "summary": manifest["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
