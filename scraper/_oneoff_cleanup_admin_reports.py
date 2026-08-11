from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
from typing import Any, Callable, NamedTuple, TypeVar
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PREFIX = ("tmp", "admin-qa-cleanup")
DISCOVERY_SCHEMA = {"name": "admin-qa-cleanup-discovery", "version": 1}
FREEZE_SCHEMA = {"name": "admin-qa-cleanup-freeze", "version": 1}
REVIEW_SCHEMA = {"name": "admin-qa-cleanup-manual-review", "version": 1}
REPORT_PROJECTION = "*"
EVENT_PROJECTION = "*"
REPORT_REQUIRED_FIELDS = frozenset({"id", "event_id", "report_types", "status"})
PREDICATE_EVENT_FIELDS = frozenset(
    {
        "id",
        "is_active",
        "annotation_status",
        "source_name",
        "name_ja",
        "raw_title",
        "location_name",
        "location_address",
        "location_prefectures",
        "category",
        "start_date",
        "organizer",
        "business_hours",
        "performers",
        "performer",
        "parent_event_id",
        "description_zh",
        "name_zh",
        "location_name_zh",
        "location_address_zh",
        "business_hours_zh",
        "organizer_zh",
        "selection_reason",
        "event_form",
        "raw_description",
        "source_url",
        "created_at",
    }
)
REPORT_CLASSES = ("single_auto", "compound_auto", "manual", "empty")
REVIEW_REASONS = ("manual", "unknown", "empty", "mixed", "payload_token", "compound_auto")
KNOWN_MANUAL_REPORT_TYPES = frozenset(
    {
        "irrelevant",
        "wrongDetails",
        "wrongCategory",
        "wrongSelectionReason",
        "brokenLink",
        "auto_security_prompt_injection",
    }
)
MANUAL_METADATA_PREFIXES = ("securityHash:", "securitySeverity:")
MUTATION_METHODS = frozenset(
    {
        "insert",
        "update",
        "upsert",
        "delete",
        "rpc",
    }
)
CLIENT_READ_METHODS = frozenset({"table"})
QUERY_READ_METHODS = frozenset({"select", "eq", "in_", "order", "range", "execute"})
READ_ONLY_TABLES = frozenset({"event_reports", "events"})
_TIMESTAMP_DIRECTORY_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")
_REPOSITORY_HEAD_RE = re.compile(r"^[0-9a-f]{40}$")
_DecodedArtifact = TypeVar("_DecodedArtifact")


class AutoQaPolicy(NamedTuple):
    known_auto_qa_types: frozenset[str]
    classifier: Callable[[list[str] | None], str]
    payload_token_predicate: Callable[[str], bool]


def _load_auto_qa_policy() -> AutoQaPolicy:
    from auto_qa import KNOWN_AUTO_QA_TYPES, classify_report_types, is_payload_token

    return AutoQaPolicy(
        known_auto_qa_types=KNOWN_AUTO_QA_TYPES,
        classifier=classify_report_types,
        payload_token_predicate=is_payload_token,
    )


@dataclass(frozen=True, slots=True)
class ReadOnlyResult:
    data: list[dict[str, Any]] | None
    count: int | None


def _rebuild_json_value(value: Any) -> Any:
    value_type = type(value)
    if value is None or value_type in {str, bool, int}:
        return value
    if value_type is float:
        if not math.isfinite(value):
            raise RuntimeError("Supabase query execute returned non-finite JSON number")
        return value
    if value_type is list:
        return [_rebuild_json_value(item) for item in value]
    if value_type is dict:
        rebuilt: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise RuntimeError("Supabase query execute returned non-string JSON key")
            rebuilt[key] = _rebuild_json_value(item)
        return rebuilt
    raise RuntimeError(
        f"Supabase query execute returned non-JSON value: {value_type.__name__}"
    )


def _query_capability(target: Any) -> Any:
    def chain(name: str, *args: Any, **kwargs: Any) -> Any:
        try:
            attribute = getattr(target, name)
        except AttributeError as exc:
            raise RuntimeError(f"missing Supabase query read method: {name}") from exc
        if not callable(attribute):
            raise RuntimeError(f"Supabase query read method is not callable: {name}")
        return _query_capability(attribute(*args, **kwargs))

    class QueryCapability:
        __slots__ = ()

        def __getattribute__(self, name: str) -> Any:
            if name in QUERY_READ_METHODS:
                return object.__getattribute__(self, name)
            raise RuntimeError(f"blocked Supabase query access: {name}")

        def select(self, *args: Any, **kwargs: Any) -> Any:
            return chain("select", *args, **kwargs)

        def eq(self, *args: Any, **kwargs: Any) -> Any:
            return chain("eq", *args, **kwargs)

        def in_(self, *args: Any, **kwargs: Any) -> Any:
            return chain("in_", *args, **kwargs)

        def order(self, *args: Any, **kwargs: Any) -> Any:
            return chain("order", *args, **kwargs)

        def range(self, *args: Any, **kwargs: Any) -> Any:
            return chain("range", *args, **kwargs)

        def execute(self) -> ReadOnlyResult:
            try:
                attribute = getattr(target, "execute")
            except AttributeError as exc:
                raise RuntimeError("missing Supabase query read method: execute") from exc
            if not callable(attribute):
                raise RuntimeError("Supabase query read method is not callable: execute")
            response = attribute()
            missing = object()
            data = getattr(response, "data", missing)
            count = getattr(response, "count", missing)
            if data is missing or count is missing:
                raise RuntimeError("Supabase query execute returned malformed response")
            if data is not None and (
                type(data) is not list
                or any(type(row) is not dict for row in data)
            ):
                raise RuntimeError("Supabase query execute returned malformed data")
            if count is not None and (
                type(count) is not int or count < 0
            ):
                raise RuntimeError("Supabase query execute returned malformed count")
            try:
                rebuilt = None if data is None else _rebuild_json_value(data)
            except RuntimeError as exc:
                raise RuntimeError("Supabase query execute returned malformed data") from exc
            return ReadOnlyResult(data=rebuilt, count=count)

    return QueryCapability()


def ReadOnlyProxy(target: Any, *, surface: str = "client") -> Any:
    if surface == "query":
        return _query_capability(target)
    if surface != "client":
        raise ValueError(f"unsupported Supabase proxy surface: {surface}")

    def table(name: str) -> Any:
        if name not in READ_ONLY_TABLES:
            raise RuntimeError(f"blocked Supabase table access: {name}")
        try:
            attribute = getattr(target, "table")
        except AttributeError as exc:
            raise RuntimeError("missing Supabase client read method: table") from exc
        if not callable(attribute):
            raise RuntimeError("Supabase client read method is not callable: table")
        return _query_capability(attribute(name))

    class ClientCapability:
        __slots__ = ()

        def __getattribute__(self, name: str) -> Any:
            if name == "table":
                return object.__getattribute__(self, name)
            raise RuntimeError(f"blocked Supabase client access: {name}")

        def table(self, name: str) -> Any:
            return table(name)

    return ClientCapability()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _seal(payload: dict[str, Any]) -> dict[str, Any]:
    body = {key: deepcopy(value) for key, value in payload.items() if key != "digest_sha256"}
    return {**body, "digest_sha256": _digest(body)}


def _verify_digest(payload: dict[str, Any]) -> None:
    expected = payload.get("digest_sha256")
    body = {key: value for key, value in payload.items() if key != "digest_sha256"}
    if not isinstance(expected, str) or expected != _digest(body):
        raise RuntimeError("artifact digest mismatch")


def _full_uuid(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 36:
        raise RuntimeError(f"full UUID required for {field}: {value!r}")
    try:
        canonical = str(UUID(value))
    except ValueError as exc:
        raise RuntimeError(f"invalid UUID for {field}: {value!r}") from exc
    if value != canonical:
        raise RuntimeError(f"canonical full UUID required for {field}: {value!r}")
    return canonical


def _repository_head(value: Any) -> str:
    if not isinstance(value, str) or not _REPOSITORY_HEAD_RE.fullmatch(value):
        raise RuntimeError(f"full repository HEAD required: {value!r}")
    return value


def _required_fields(row: dict[str, Any], fields: frozenset[str], *, context: str) -> None:
    missing = sorted(fields - set(row))
    if missing:
        raise RuntimeError(f"{context} projection missing required fields: {missing}")


def _exact_count(response: Any, *, table: str, page: int) -> int:
    count = getattr(response, "count", None)
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise RuntimeError(f"{table} page {page} did not return a valid exact count")
    return count


def _response_rows(response: Any, *, table: str, page: int) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if data is None:
        return []
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise RuntimeError(f"{table} page {page} returned malformed rows")
    return [deepcopy(row) for row in data]


def fetch_pending_reports(
    client: Any,
    *,
    page_size: int = 500,
    projection: str | None = None,
) -> dict[str, Any]:
    if page_size < 1:
        raise ValueError("page_size must be positive")
    selected = projection or REPORT_PROJECTION
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    pages: list[dict[str, int]] = []
    expected_count: int | None = None
    offset = 0

    while True:
        page_number = len(pages) + 1
        end = offset + page_size - 1
        response = (
            client.table("event_reports")
            .select(selected, count="exact")
            .eq("status", "pending")
            .order("id")
            .range(offset, end)
            .execute()
        )
        count = _exact_count(response, table="event_reports", page=page_number)
        if expected_count is None:
            expected_count = count
        elif count != expected_count:
            raise RuntimeError(
                f"event_reports exact count drifted from {expected_count} to {count}"
            )
        batch = _response_rows(response, table="event_reports", page=page_number)
        if count != 0 or batch:
            pages.append(
                {
                    "page": page_number,
                    "start": offset,
                    "end": end,
                    "returned": len(batch),
                    "exact_count": count,
                }
            )

        for row in batch:
            _required_fields(row, REPORT_REQUIRED_FIELDS, context="event_reports")
            report_id = _full_uuid(row.get("id"), field="event_reports.id")
            _full_uuid(row.get("event_id"), field=f"event_reports[{report_id}].event_id")
            if row.get("status") != "pending":
                raise RuntimeError(f"non-pending report escaped the query filter: {report_id}")
            if report_id in seen:
                raise RuntimeError(f"duplicate report id across pages: {report_id}")
            if rows and report_id <= str(rows[-1]["id"]):
                raise RuntimeError("event_reports pagination order is not strictly increasing")
            seen.add(report_id)
            rows.append(row)

        if len(rows) == expected_count:
            break
        if len(rows) > expected_count:
            raise RuntimeError(
                f"event_reports fetched {len(rows)} rows above exact count {expected_count}"
            )
        if not batch or len(batch) < page_size:
            raise RuntimeError(
                f"event_reports pagination ended at {len(rows)} of {expected_count} rows"
            )
        offset += page_size

    return {
        "rows": rows,
        "query": {
            "table": "event_reports",
            "projection": selected,
            "filters": {"status": {"operator": "eq", "value": "pending"}},
            "order": [{"column": "id", "direction": "asc"}],
            "pagination": {
                "page_size": page_size,
                "pages": pages,
                "exact_count": expected_count,
                "fetched_count": len(rows),
                "complete": len(rows) == expected_count,
            },
        },
    }


def classify_pending_reports(
    reports: list[dict[str, Any]],
    *,
    policy: AutoQaPolicy | None = None,
    classifier: Callable[[list[str] | None], str] | None = None,
) -> list[dict[str, Any]]:
    resolved_policy = policy or _load_auto_qa_policy()
    classify = classifier or resolved_policy.classifier
    classified: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(reports, key=lambda item: str(item.get("id") or "")):
        _required_fields(row, REPORT_REQUIRED_FIELDS, context="event_reports")
        report_id = _full_uuid(row.get("id"), field="event_reports.id")
        event_id = _full_uuid(row.get("event_id"), field=f"event_reports[{report_id}].event_id")
        if report_id in seen:
            raise RuntimeError(f"duplicate report id during classification: {report_id}")
        seen.add(report_id)
        try:
            metadata = _classification_metadata(
                row.get("report_types"),
                policy=resolved_policy,
                classifier=classify,
            )
        except RuntimeError as exc:
            raise RuntimeError(f"invalid report classification metadata: {report_id}") from exc
        classified.append(
            {
                "report_id": report_id,
                "event_id": event_id,
                **metadata,
            }
        )
    return classified


def _classification_metadata(
    report_types: Any,
    *,
    policy: AutoQaPolicy,
    classifier: Callable[[list[str] | None], str],
) -> dict[str, Any]:
    if report_types is not None and not isinstance(report_types, list):
        raise RuntimeError("report_types must be a list or null")
    classification = classifier(report_types)
    if classification not in REPORT_CLASSES:
        raise RuntimeError(f"unsupported report classification: {classification!r}")
    usable_tokens = [
        token
        for token in (report_types or [])
        if isinstance(token, str) and token
    ]
    known_auto_types = sorted(
        {token for token in usable_tokens if token in policy.known_auto_qa_types}
    )
    payload_tokens = sorted(
        {token for token in usable_tokens if policy.payload_token_predicate(token)}
    )
    manual_tokens = sorted(
        {
            token
            for token in usable_tokens
            if token in KNOWN_MANUAL_REPORT_TYPES
            or token.startswith(MANUAL_METADATA_PREFIXES)
        }
    )
    unknown_tokens = sorted(
        {
            token
            for token in usable_tokens
            if token not in policy.known_auto_qa_types
            and token not in KNOWN_MANUAL_REPORT_TYPES
            and not token.startswith(MANUAL_METADATA_PREFIXES)
            and not policy.payload_token_predicate(token)
        }
    )
    reasons: list[str] = []
    if classification == "manual":
        reasons.append("manual")
    if unknown_tokens:
        reasons.append("unknown")
    if classification == "empty":
        reasons.append("empty")
    if known_auto_types and (manual_tokens or unknown_tokens or payload_tokens):
        reasons.append("mixed")
    if payload_tokens:
        reasons.append("payload_token")
    if classification == "compound_auto":
        reasons.append("compound_auto")
    return {
        "classification": classification,
        "review_reasons": [reason for reason in REVIEW_REASONS if reason in reasons],
        "known_auto_types": known_auto_types,
        "manual_tokens": manual_tokens,
        "unknown_tokens": unknown_tokens,
        "payload_tokens": payload_tokens,
        "predicate_resolution": "not_evaluated",
    }


def _require_exact_keys(value: Any, expected: set[str], *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise RuntimeError(f"{context} keys mismatch")
    return value


def _expected_pagination(row_count: int, page_size: int) -> dict[str, Any]:
    pages = []
    for page_number, start in enumerate(range(0, row_count, page_size), start=1):
        pages.append(
            {
                "page": page_number,
                "start": start,
                "end": start + page_size - 1,
                "returned": min(page_size, row_count - start),
                "exact_count": row_count,
            }
        )
    return {
        "page_size": page_size,
        "pages": pages,
        "exact_count": row_count,
        "fetched_count": row_count,
        "complete": True,
    }


def _verify_ledger_query(
    query: Any,
    *,
    table: str,
    projection: str,
    filters: dict[str, Any],
    row_count: int,
) -> None:
    query_map = _require_exact_keys(
        query,
        {"table", "projection", "filters", "order", "pagination"},
        context=f"{table} query",
    )
    pagination = _require_exact_keys(
        query_map["pagination"],
        {"page_size", "pages", "exact_count", "fetched_count", "complete"},
        context=f"{table} pagination",
    )
    page_size = pagination["page_size"]
    if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 1:
        raise RuntimeError(f"{table} page_size must be a positive integer")
    expected = {
        "table": table,
        "projection": projection,
        "filters": filters,
        "order": [{"column": "id", "direction": "asc"}],
        "pagination": _expected_pagination(row_count, page_size),
    }
    if query_map != expected:
        raise RuntimeError(f"{table} query contract mismatch")


def _fetch_referenced_events(
    client: Any,
    event_ids: list[str],
    *,
    page_size: int,
    projection: str | None = None,
) -> dict[str, Any]:
    selected = projection or EVENT_PROJECTION
    normalized_ids = sorted({_full_uuid(event_id, field="event_id") for event_id in event_ids})
    if not normalized_ids:
        return {
            "rows": [],
            "query": {
                "table": "events",
                "projection": selected,
                "filters": {"id": {"operator": "in", "values": []}},
                "order": [{"column": "id", "direction": "asc"}],
                "pagination": {
                    "page_size": page_size,
                    "pages": [],
                    "exact_count": 0,
                    "fetched_count": 0,
                    "complete": True,
                },
            },
        }

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    pages: list[dict[str, int]] = []
    expected_count: int | None = None
    offset = 0
    while True:
        page_number = len(pages) + 1
        end = offset + page_size - 1
        response = (
            client.table("events")
            .select(selected, count="exact")
            .in_("id", normalized_ids)
            .order("id")
            .range(offset, end)
            .execute()
        )
        count = _exact_count(response, table="events", page=page_number)
        if expected_count is None:
            expected_count = count
            if expected_count != len(normalized_ids):
                raise RuntimeError(
                    "referenced event count mismatch: "
                    f"expected {len(normalized_ids)}, exact count {expected_count}"
                )
        elif count != expected_count:
            raise RuntimeError(f"events exact count drifted from {expected_count} to {count}")
        batch = _response_rows(response, table="events", page=page_number)
        pages.append(
            {
                "page": page_number,
                "start": offset,
                "end": end,
                "returned": len(batch),
                "exact_count": count,
            }
        )
        for row in batch:
            _required_fields(row, PREDICATE_EVENT_FIELDS, context="events")
            event_id = _full_uuid(row.get("id"), field="events.id")
            if event_id in seen:
                raise RuntimeError(f"duplicate event id across pages: {event_id}")
            if rows and event_id <= str(rows[-1]["id"]):
                raise RuntimeError("events pagination order is not strictly increasing")
            seen.add(event_id)
            rows.append(row)
        if len(rows) == expected_count:
            break
        if len(rows) > expected_count:
            raise RuntimeError(f"events fetched {len(rows)} rows above exact count {expected_count}")
        if not batch or len(batch) < page_size:
            raise RuntimeError(f"events pagination ended at {len(rows)} of {expected_count} rows")
        offset += page_size

    missing = sorted(set(normalized_ids) - seen)
    if missing:
        raise RuntimeError(f"referenced events missing from complete scan: {missing}")
    return {
        "rows": rows,
        "query": {
            "table": "events",
            "projection": selected,
            "filters": {"id": {"operator": "in", "values": normalized_ids}},
            "order": [{"column": "id", "direction": "asc"}],
            "pagination": {
                "page_size": page_size,
                "pages": pages,
                "exact_count": expected_count,
                "fetched_count": len(rows),
                "complete": len(rows) == expected_count,
            },
        },
    }


def build_discovery_ledger(
    client: Any,
    *,
    repository_head: str,
    page_size: int = 500,
    policy: AutoQaPolicy | None = None,
    classifier: Callable[[list[str] | None], str] | None = None,
) -> dict[str, Any]:
    resolved_policy = policy or _load_auto_qa_policy()
    head = _repository_head(repository_head)
    report_scan = fetch_pending_reports(client, page_size=page_size)
    report_rows = report_scan["rows"]
    classifications = classify_pending_reports(
        report_rows,
        policy=resolved_policy,
        classifier=classifier,
    )
    classification_by_id = {row["report_id"]: row for row in classifications}
    event_ids = sorted({str(row["event_id"]) for row in report_rows})
    event_scan = _fetch_referenced_events(client, event_ids, page_size=page_size)

    report_entries = []
    for row in report_rows:
        report_id = str(row["id"])
        report_entries.append(
            {
                **deepcopy(classification_by_id[report_id]),
                "before_image": deepcopy(row),
            }
        )
    event_entries = [
        {"event_id": str(row["id"]), "before_image": deepcopy(row)}
        for row in event_scan["rows"]
    ]
    class_counts = Counter(row["classification"] for row in classifications)
    reason_counts = Counter(
        reason
        for row in classifications
        for reason in row["review_reasons"]
    )
    payload = {
        "schema": deepcopy(DISCOVERY_SCHEMA),
        "repository_head": head,
        "complete": True,
        "query": {
            "reports": deepcopy(report_scan["query"]),
            "events": deepcopy(event_scan["query"]),
        },
        "counts": {
            "pending_reports": len(report_entries),
            "unique_report_ids": len({row["report_id"] for row in report_entries}),
            "referenced_event_ids": len(event_ids),
            "fetched_events": len(event_entries),
            "classifications": {
                name: class_counts.get(name, 0) for name in REPORT_CLASSES
            },
            "review_reasons": {
                name: reason_counts.get(name, 0) for name in REVIEW_REASONS
            },
        },
        "contract": {
            "read_only": True,
            "complete_report_before_images": True,
            "complete_event_before_images": True,
            "classification_is_apply_allowlist": False,
            "known_auto_membership_proves_predicate_resolution": False,
            "predicate_resolution_evaluated": False,
        },
        "reports": report_entries,
        "events": event_entries,
    }
    ledger = _seal(payload)
    verify_discovery_ledger(
        ledger,
        expected_repository_head=head,
        policy=resolved_policy,
        classifier=classifier,
    )
    return ledger


def verify_discovery_ledger(
    ledger: dict[str, Any],
    *,
    expected_repository_head: str,
    policy: AutoQaPolicy | None = None,
    classifier: Callable[[list[str] | None], str] | None = None,
) -> None:
    resolved_policy = policy or _load_auto_qa_policy()
    classify = classifier or resolved_policy.classifier
    expected_head = _repository_head(expected_repository_head)
    _require_exact_keys(
        ledger,
        {
            "schema",
            "repository_head",
            "complete",
            "query",
            "counts",
            "contract",
            "reports",
            "events",
            "digest_sha256",
        },
        context="discovery ledger",
    )
    if ledger["schema"] != DISCOVERY_SCHEMA:
        raise RuntimeError("unsupported discovery ledger schema")
    _verify_digest(ledger)
    ledger_head = _repository_head(ledger["repository_head"])
    if ledger_head != expected_head:
        raise RuntimeError(
            f"discovery ledger repository HEAD mismatch: {ledger_head} != {expected_head}"
        )
    if ledger["complete"] is not True:
        raise RuntimeError("discovery ledger is incomplete")
    required_contract = {
        "read_only": True,
        "complete_report_before_images": True,
        "complete_event_before_images": True,
        "classification_is_apply_allowlist": False,
        "known_auto_membership_proves_predicate_resolution": False,
        "predicate_resolution_evaluated": False,
    }
    if ledger["contract"] != required_contract:
        raise RuntimeError("discovery ledger safety contract mismatch")

    reports = ledger["reports"]
    events = ledger["events"]
    if not isinstance(reports, list) or not isinstance(events, list):
        raise RuntimeError("discovery ledger rows are malformed")
    metadata_keys = {
        "classification",
        "review_reasons",
        "known_auto_types",
        "manual_tokens",
        "unknown_tokens",
        "payload_tokens",
        "predicate_resolution",
    }
    report_ids: set[str] = set()
    referenced_ids: set[str] = set()
    classifications: list[dict[str, Any]] = []
    previous_report_id: str | None = None
    for entry in reports:
        entry_map = _require_exact_keys(
            entry,
            {"report_id", "event_id", "before_image", *metadata_keys},
            context="report entry",
        )
        before = entry_map["before_image"]
        if not isinstance(before, dict):
            raise RuntimeError("report before-image is malformed")
        report_id = _full_uuid(entry_map["report_id"], field="report_id")
        event_id = _full_uuid(entry_map["event_id"], field=f"report[{report_id}].event_id")
        if previous_report_id is not None and report_id <= previous_report_id:
            raise RuntimeError("report entries are not canonically sorted")
        previous_report_id = report_id
        if report_id in report_ids:
            raise RuntimeError(f"duplicate report id in ledger: {report_id}")
        report_ids.add(report_id)
        referenced_ids.add(event_id)
        _required_fields(before, REPORT_REQUIRED_FIELDS, context="report before-image")
        if before.get("id") != report_id or before.get("event_id") != event_id:
            raise RuntimeError(f"report before-image identity mismatch: {report_id}")
        if before.get("status") != "pending":
            raise RuntimeError(f"report before-image is not pending: {report_id}")
        expected_metadata = _classification_metadata(
            before.get("report_types"),
            policy=resolved_policy,
            classifier=classify,
        )
        if {key: entry_map[key] for key in metadata_keys} != expected_metadata:
            raise RuntimeError(f"report classification metadata mismatch: {report_id}")
        classifications.append(expected_metadata)

    event_ids: set[str] = set()
    previous_event_id: str | None = None
    for entry in events:
        entry_map = _require_exact_keys(
            entry,
            {"event_id", "before_image"},
            context="event entry",
        )
        before = entry_map["before_image"]
        if not isinstance(before, dict):
            raise RuntimeError("event before-image is malformed")
        event_id = _full_uuid(entry_map["event_id"], field="event_id")
        if previous_event_id is not None and event_id <= previous_event_id:
            raise RuntimeError("event entries are not canonically sorted")
        previous_event_id = event_id
        if event_id in event_ids:
            raise RuntimeError(f"duplicate event id in ledger: {event_id}")
        event_ids.add(event_id)
        _required_fields(before, PREDICATE_EVENT_FIELDS, context="event before-image")
        if before.get("id") != event_id:
            raise RuntimeError(f"event before-image identity mismatch: {event_id}")
    if referenced_ids != event_ids:
        raise RuntimeError("referenced event before-images are incomplete")

    class_counts = Counter(row["classification"] for row in classifications)
    reason_counts = Counter(
        reason for row in classifications for reason in row["review_reasons"]
    )
    expected_counts = {
        "pending_reports": len(reports),
        "unique_report_ids": len(report_ids),
        "referenced_event_ids": len(referenced_ids),
        "fetched_events": len(events),
        "classifications": {name: class_counts.get(name, 0) for name in REPORT_CLASSES},
        "review_reasons": {name: reason_counts.get(name, 0) for name in REVIEW_REASONS},
    }
    if ledger["counts"] != expected_counts:
        raise RuntimeError("discovery ledger counts mismatch")

    query = _require_exact_keys(
        ledger["query"],
        {"reports", "events"},
        context="discovery query",
    )
    _verify_ledger_query(
        query["reports"],
        table="event_reports",
        projection=REPORT_PROJECTION,
        filters={"status": {"operator": "eq", "value": "pending"}},
        row_count=len(reports),
    )
    _verify_ledger_query(
        query["events"],
        table="events",
        projection=EVENT_PROJECTION,
        filters={"id": {"operator": "in", "values": sorted(referenced_ids)}},
        row_count=len(events),
    )


def _is_git_ignored(path: Path, *, root: Path) -> bool:
    relative = path.relative_to(root)
    result = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "-q", str(relative)],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _artifact_destination(path: Path) -> Path:
    root = ROOT.absolute()
    expanded = path.expanduser()
    absolute = expanded if expanded.is_absolute() else Path.cwd() / expanded
    try:
        relative = absolute.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"artifact must be inside worktree tmp/admin-qa-cleanup/: {absolute}") from exc
    parts = relative.parts
    if len(parts) != 4 or parts[:2] != ARTIFACT_PREFIX:
        raise RuntimeError(
            f"artifact must be tmp/admin-qa-cleanup/<timestamp>/<file>: {relative}"
        )
    if not _TIMESTAMP_DIRECTORY_RE.fullmatch(parts[2]):
        raise RuntimeError(f"artifact timestamp directory is invalid: {parts[2]}")
    filename = parts[3]
    separators = tuple(separator for separator in (os.sep, os.altsep) if separator)
    if (
        filename in {"", ".", ".."}
        or "\x00" in filename
        or Path(filename).name != filename
        or any(separator in filename for separator in separators)
    ):
        raise RuntimeError(f"artifact filename must be a single safe basename: {filename!r}")
    if not _is_git_ignored(absolute, root=root):
        raise RuntimeError(f"artifact path is not ignored by git: {relative}")
    return absolute


class DirectoryAnchor(NamedTuple):
    path: Path
    name: str | None
    descriptor: int
    identity: tuple[int, int]


def _identity(file_stat: os.stat_result) -> tuple[int, int]:
    return file_stat.st_dev, file_stat.st_ino


def _directory_open_flags() -> int:
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("artifact operations require O_DIRECTORY and O_NOFOLLOW")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _require_owned_directory(file_stat: os.stat_result, path: Path) -> None:
    if stat.S_ISLNK(file_stat.st_mode):
        raise RuntimeError(f"artifact directory symlink is forbidden: {path}")
    if not stat.S_ISDIR(file_stat.st_mode):
        raise RuntimeError(f"artifact parent must be a directory: {path}")
    if file_stat.st_uid != os.getuid():
        raise RuntimeError(f"artifact directory must be owned by current user: {path}")


def _open_directory_anchor(
    path: Path,
    *,
    name: str | None = None,
    parent_descriptor: int | None = None,
    create: bool = False,
) -> DirectoryAnchor:
    if parent_descriptor is None:
        before = os.lstat(path)
    else:
        if create:
            try:
                os.mkdir(name, mode=0o700, dir_fd=parent_descriptor)
            except FileExistsError:
                pass
        before = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    _require_owned_directory(before, path)
    if parent_descriptor is None:
        descriptor = os.open(path, _directory_open_flags())
    else:
        descriptor = os.open(name, _directory_open_flags(), dir_fd=parent_descriptor)
    try:
        opened = os.fstat(descriptor)
        _require_owned_directory(opened, path)
        if _identity(before) != _identity(opened):
            raise RuntimeError(f"artifact directory identity changed while opening: {path}")
        return DirectoryAnchor(path, name, descriptor, _identity(opened))
    except BaseException:
        os.close(descriptor)
        raise


def _verify_anchor_chain(anchors: list[DirectoryAnchor]) -> None:
    for index, anchor in enumerate(anchors):
        opened = os.fstat(anchor.descriptor)
        _require_owned_directory(opened, anchor.path)
        if _identity(opened) != anchor.identity:
            raise RuntimeError(f"artifact directory descriptor identity changed: {anchor.path}")
        if index == 0:
            visible = os.lstat(anchor.path)
        else:
            visible = os.stat(
                anchor.name,
                dir_fd=anchors[index - 1].descriptor,
                follow_symlinks=False,
            )
        _require_owned_directory(visible, anchor.path)
        if _identity(visible) != anchor.identity:
            raise RuntimeError(f"artifact directory path identity changed: {anchor.path}")


def _close_anchors(anchors: list[DirectoryAnchor]) -> None:
    for anchor in reversed(anchors):
        try:
            os.close(anchor.descriptor)
        except OSError:
            pass


def _open_artifact_parent(destination: Path, *, create: bool) -> list[DirectoryAnchor]:
    root = ROOT.absolute()
    relative = destination.relative_to(root)
    anchors: list[DirectoryAnchor] = []
    try:
        anchors.append(_open_directory_anchor(root))
        current = root
        for name in relative.parts[:3]:
            current = current / name
            anchors.append(
                _open_directory_anchor(
                    current,
                    name=name,
                    parent_descriptor=anchors[-1].descriptor,
                    create=create,
                )
            )
        _verify_anchor_chain(anchors)
        return anchors
    except BaseException:
        _close_anchors(anchors)
        raise


def _require_regular_mode(file_stat: os.stat_result, path: Path) -> None:
    if stat.S_ISLNK(file_stat.st_mode):
        raise RuntimeError(f"artifact symlink is forbidden: {path}")
    if not stat.S_ISREG(file_stat.st_mode):
        raise RuntimeError(f"artifact must be a regular file: {path}")
    mode = stat.S_IMODE(file_stat.st_mode)
    if mode != stat.S_IRUSR:
        raise RuntimeError(f"artifact mode must be exactly 0400, got {mode:04o}: {path}")
    if file_stat.st_uid != os.getuid():
        raise RuntimeError(f"artifact must be owned by current user: {path}")


def _lstat_at(directory_descriptor: int, name: str) -> os.stat_result:
    return os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)


def _read_anchored_artifact(
    directory_descriptor: int,
    name: str,
    path: Path,
    *,
    decoder: Callable[[bytes], _DecodedArtifact],
    post_decode_check: Callable[[], None] | None = None,
    expected_identity: tuple[int, int] | None = None,
) -> _DecodedArtifact:
    before = _lstat_at(directory_descriptor, name)
    _require_regular_mode(before, path)
    if expected_identity is not None and _identity(before) != expected_identity:
        raise RuntimeError(f"artifact identity changed before opening: {path}")
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(name, flags, dir_fd=directory_descriptor)
    handle = None
    try:
        opened = os.fstat(descriptor)
        _require_regular_mode(opened, path)
        opened_identity = _identity(opened)
        if _identity(before) != opened_identity:
            raise RuntimeError(f"artifact identity changed while opening: {path}")
        if expected_identity is not None and opened_identity != expected_identity:
            raise RuntimeError(f"artifact opened unexpected identity: {path}")
        handle = os.fdopen(descriptor, "rb", buffering=0)
        descriptor = -1
        content = handle.read()
        after_read = os.fstat(handle.fileno())
        _require_regular_mode(after_read, path)
        if _identity(after_read) != opened_identity:
            raise RuntimeError(f"artifact descriptor identity changed while reading: {path}")
        try:
            after_path = _lstat_at(directory_descriptor, name)
        except FileNotFoundError as exc:
            raise RuntimeError(f"artifact path disappeared while reading: {path}") from exc
        _require_regular_mode(after_path, path)
        if _identity(after_path) != opened_identity:
            raise RuntimeError(f"artifact path identity changed while reading: {path}")
        decoded = decoder(content)
        after_decode = os.fstat(handle.fileno())
        _require_regular_mode(after_decode, path)
        if _identity(after_decode) != opened_identity:
            raise RuntimeError(f"artifact descriptor identity changed while decoding: {path}")
        try:
            decoded_path = _lstat_at(directory_descriptor, name)
        except FileNotFoundError as exc:
            raise RuntimeError(f"artifact path disappeared while decoding: {path}") from exc
        _require_regular_mode(decoded_path, path)
        if _identity(decoded_path) != opened_identity:
            raise RuntimeError(f"artifact path identity changed while decoding: {path}")
        if post_decode_check is not None:
            post_decode_check()
        before_return = os.fstat(handle.fileno())
        _require_regular_mode(before_return, path)
        if _identity(before_return) != opened_identity:
            raise RuntimeError(f"artifact descriptor identity changed before return: {path}")
        try:
            return_path = _lstat_at(directory_descriptor, name)
        except FileNotFoundError as exc:
            raise RuntimeError(f"artifact path disappeared before return: {path}") from exc
        _require_regular_mode(return_path, path)
        if _identity(return_path) != opened_identity:
            raise RuntimeError(f"artifact path identity changed before return: {path}")
        handle.close()
        handle = None
        return decoded
    finally:
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        if descriptor >= 0:
            os.close(descriptor)


def _read_anchored_artifact_bytes(
    directory_descriptor: int,
    name: str,
    path: Path,
    *,
    expected_identity: tuple[int, int] | None = None,
) -> bytes:
    return _read_anchored_artifact(
        directory_descriptor,
        name,
        path,
        decoder=lambda content: content,
        expected_identity=expected_identity,
    )


def _read_secure_artifact(
    path: Path,
    *,
    decoder: Callable[[bytes], _DecodedArtifact],
) -> _DecodedArtifact:
    destination = _artifact_destination(path)
    anchors = _open_artifact_parent(destination, create=False)
    try:
        decoded = _read_anchored_artifact(
            anchors[-1].descriptor,
            destination.name,
            destination,
            decoder=decoder,
            post_decode_check=lambda: _verify_anchor_chain(anchors),
        )
        _verify_anchor_chain(anchors)
        return decoded
    finally:
        _close_anchors(anchors)


def _read_secure_artifact_bytes(path: Path) -> bytes:
    return _read_secure_artifact(path, decoder=lambda content: content)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-JSON numeric constant: {value}")


def _decode_artifact_bytes(content: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(
            content.decode("utf-8"),
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError("artifact JSON is invalid") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("artifact root must be an object")
    try:
        canonical = canonical_json_bytes(payload) + b"\n"
    except (TypeError, ValueError) as exc:
        raise RuntimeError("artifact JSON cannot be canonicalized") from exc
    if content != canonical:
        raise RuntimeError("artifact content is not canonical")
    _verify_digest(payload)
    return payload


def _open_staging_file(
    directory_descriptor: int,
    destination_name: str,
) -> tuple[str, int, tuple[int, int]]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    for _ in range(32):
        staging = f".{destination_name}.{secrets.token_hex(12)}.tmp"
        try:
            descriptor = os.open(
                staging,
                flags,
                stat.S_IRUSR,
                dir_fd=directory_descriptor,
            )
        except FileExistsError:
            continue
        opened = os.fstat(descriptor)
        return staging, descriptor, _identity(opened)
    raise RuntimeError(f"unable to create exclusive artifact staging file: {destination_name}")


def _unlink_owned_identity_links(
    directory_descriptor: int,
    identity: tuple[int, int] | None,
    *,
    preserve_names: frozenset[str] = frozenset(),
) -> list[str]:
    if identity is None:
        return []
    removed: list[str] = []
    for _ in range(64):
        try:
            names = os.listdir(directory_descriptor)
        except OSError as exc:
            raise RuntimeError(
                f"unable to enumerate anchored artifact directory: {exc}"
            ) from exc
        matches: list[str] = []
        for name in names:
            if name in preserve_names:
                continue
            try:
                current = _lstat_at(directory_descriptor, name)
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise RuntimeError(
                    f"unable to inspect anchored artifact cleanup entry: {name}"
                ) from exc
            if _identity(current) == identity:
                matches.append(name)
        if not matches:
            return removed
        progress = False
        for name in matches:
            try:
                current = _lstat_at(directory_descriptor, name)
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise RuntimeError(
                    f"unable to recheck anchored artifact cleanup entry: {name}"
                ) from exc
            if _identity(current) != identity:
                continue
            try:
                os.unlink(name, dir_fd=directory_descriptor)
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise RuntimeError(
                    f"unable to unlink owned artifact cleanup entry: {name}"
                ) from exc
            removed.append(name)
            progress = True
        if not progress:
            continue
    raise RuntimeError("owned artifact cleanup did not converge")


def _write_immutable_json(path: Path, payload: dict[str, Any]) -> Path:
    destination = _artifact_destination(path)
    anchors = _open_artifact_parent(destination, create=True)
    directory_descriptor = anchors[-1].descriptor
    content = canonical_json_bytes(payload) + b"\n"
    staging_name: str | None = None
    staging_identity: tuple[int, int] | None = None
    descriptor = -1
    handle = None
    publish_identity: tuple[int, int] | None = None
    try:
        try:
            _lstat_at(directory_descriptor, destination.name)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(f"artifact destination already exists: {destination}")
        staging_name, descriptor, staging_identity = _open_staging_file(
            directory_descriptor,
            destination.name,
        )
        os.fchmod(descriptor, stat.S_IRUSR)
        staged_open = os.fstat(descriptor)
        _require_regular_mode(staged_open, destination.with_name(staging_name))
        if _identity(staged_open) != staging_identity:
            raise RuntimeError(f"immutable artifact staging identity changed: {staging_name}")
        handle = os.fdopen(descriptor, "wb", buffering=0)
        descriptor = -1
        written = handle.write(content)
        if written != len(content):
            raise RuntimeError(
                f"immutable artifact short write: {written} of {len(content)} bytes"
            )
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        handle = None
        staged_content = _read_anchored_artifact_bytes(
            directory_descriptor,
            staging_name,
            destination.with_name(staging_name),
            expected_identity=staging_identity,
        )
        if staged_content != content:
            raise RuntimeError(f"immutable artifact staging read-back mismatch: {staging_name}")
        _decode_artifact_bytes(staged_content)
        staged = _lstat_at(directory_descriptor, staging_name)
        _require_regular_mode(staged, destination.with_name(staging_name))
        if _identity(staged) != staging_identity:
            raise RuntimeError(f"immutable artifact staging path identity changed: {staging_name}")
        publish_identity = staging_identity
        os.link(
            staging_name,
            destination.name,
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        published = _lstat_at(directory_descriptor, destination.name)
        _require_regular_mode(published, destination)
        if publish_identity != _identity(published):
            raise RuntimeError(f"immutable artifact publish identity mismatch: {destination}")
        if _read_anchored_artifact_bytes(
            directory_descriptor,
            destination.name,
            destination,
            expected_identity=publish_identity,
        ) != content:
            raise RuntimeError(f"immutable artifact final read-back mismatch: {destination}")
        _unlink_owned_identity_links(
            directory_descriptor,
            staging_identity,
            preserve_names=frozenset({destination.name}),
        )
        staging_name = None
        _verify_anchor_chain(anchors)
        visible_final = _lstat_at(directory_descriptor, destination.name)
        _require_regular_mode(visible_final, destination)
        if _identity(visible_final) != publish_identity:
            raise RuntimeError(f"immutable artifact final identity changed: {destination}")
        _verify_anchor_chain(anchors)
        return destination
    except BaseException as error:
        cleanup_errors: list[BaseException] = []
        if handle is not None:
            try:
                handle.close()
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        owned_identities = {
            identity
            for identity in (publish_identity, staging_identity)
            if identity is not None
        }
        for identity in owned_identities:
            try:
                _unlink_owned_identity_links(directory_descriptor, identity)
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        for cleanup_error in cleanup_errors:
            error.add_note(f"artifact cleanup failed: {cleanup_error!r}")
        raise
    finally:
        _close_anchors(anchors)


def freeze_discovery_ledger(
    first_scan: dict[str, Any],
    second_scan: dict[str, Any],
    destination: Path,
    *,
    frozen_at: str,
    expected_repository_head: str,
    policy: AutoQaPolicy | None = None,
    classifier: Callable[[list[str] | None], str] | None = None,
) -> Path:
    resolved_policy = policy or _load_auto_qa_policy()
    expected_head = _repository_head(expected_repository_head)
    verify_discovery_ledger(
        first_scan,
        expected_repository_head=expected_head,
        policy=resolved_policy,
        classifier=classifier,
    )
    verify_discovery_ledger(
        second_scan,
        expected_repository_head=expected_head,
        policy=resolved_policy,
        classifier=classifier,
    )
    if canonical_json_bytes(first_scan) != canonical_json_bytes(second_scan):
        raise RuntimeError("scan digest drift; no discovery artifact published")
    payload = _seal(
        {
            "schema": deepcopy(FREEZE_SCHEMA),
            "artifact_type": "two-scan-discovery-freeze",
            "frozen_at": frozen_at,
            "repository_head": expected_head,
            "scan": {
                "required_complete_scans": 2,
                "byte_identical": True,
                "digests_sha256": [
                    first_scan["digest_sha256"],
                    second_scan["digest_sha256"],
                ],
            },
            "query": deepcopy(first_scan["query"]),
            "counts": deepcopy(first_scan["counts"]),
            "discovery_ledger": deepcopy(first_scan),
        }
    )
    return _write_immutable_json(destination, payload)


def export_manual_review(
    ledger: dict[str, Any],
    destination: Path,
    *,
    exported_at: str,
    expected_repository_head: str,
    policy: AutoQaPolicy | None = None,
    classifier: Callable[[list[str] | None], str] | None = None,
) -> Path:
    expected_head = _repository_head(expected_repository_head)
    verify_discovery_ledger(
        ledger,
        expected_repository_head=expected_head,
        policy=policy,
        classifier=classifier,
    )
    event_by_id = {
        row["event_id"]: row["before_image"]
        for row in ledger["events"]
    }
    rows = []
    for report in ledger["reports"]:
        if not report["review_reasons"]:
            continue
        rows.append(
            {
                "report_id": report["report_id"],
                "event_id": report["event_id"],
                "classification": report["classification"],
                "review_reasons": deepcopy(report["review_reasons"]),
                "known_auto_types": deepcopy(report["known_auto_types"]),
                "manual_tokens": deepcopy(report["manual_tokens"]),
                "unknown_tokens": deepcopy(report["unknown_tokens"]),
                "payload_tokens": deepcopy(report["payload_tokens"]),
                "predicate_resolution": "not_evaluated",
                "report_before_image": deepcopy(report["before_image"]),
                "event_before_image": deepcopy(event_by_id[report["event_id"]]),
            }
        )
    reason_counts = Counter(reason for row in rows for reason in row["review_reasons"])
    payload = _seal(
        {
            "schema": deepcopy(REVIEW_SCHEMA),
            "artifact_type": "manual-review-export",
            "exported_at": exported_at,
            "repository_head": expected_head,
            "source_discovery_digest_sha256": ledger["digest_sha256"],
            "query": deepcopy(ledger["query"]),
            "source_counts": deepcopy(ledger["counts"]),
            "counts": {
                "rows": len(rows),
                "review_reasons": {
                    reason: reason_counts.get(reason, 0) for reason in REVIEW_REASONS
                },
            },
            "contract": {
                "read_only": True,
                "classification_is_apply_allowlist": False,
                "known_auto_membership_proves_predicate_resolution": False,
            },
            "rows": rows,
        }
    )
    return _write_immutable_json(destination, payload)


def load_artifact(path: Path) -> dict[str, Any]:
    return _read_secure_artifact(path, decoder=_decode_artifact_bytes)


def current_repository_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return _repository_head(result.stdout.strip())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _timestamp_directory() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_artifact_path(filename: str) -> Path:
    return ROOT.joinpath(*ARTIFACT_PREFIX, _timestamp_directory(), filename)


def _create_read_only_client() -> ReadOnlyProxy:
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv(Path(__file__).with_name(".env"), override=False)
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return ReadOnlyProxy(create_client(url, key))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only discovery and review tooling for pending Admin QA reports."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    discover = commands.add_parser("discover", help="print one complete read-only discovery scan")
    discover.add_argument("--page-size", type=int, default=500)
    freeze = commands.add_parser("freeze", help="publish only two byte-identical complete scans")
    freeze.add_argument("--page-size", type=int, default=500)
    freeze.add_argument("--output", type=Path)
    review = commands.add_parser("export-review", help="export review-only rows from a frozen ledger")
    review.add_argument("--ledger", type=Path, required=True)
    review.add_argument("--output", type=Path)
    return parser


def _ledger_from_artifact(
    payload: dict[str, Any],
    *,
    expected_repository_head: str,
    policy: AutoQaPolicy | None = None,
    classifier: Callable[[list[str] | None], str] | None = None,
) -> dict[str, Any]:
    expected_head = _repository_head(expected_repository_head)
    if payload.get("schema") == DISCOVERY_SCHEMA:
        ledger = payload
    elif payload.get("schema") == FREEZE_SCHEMA:
        artifact_head = _repository_head(payload.get("repository_head"))
        if artifact_head != expected_head:
            raise RuntimeError(
                f"freeze artifact repository HEAD mismatch: {artifact_head} != {expected_head}"
            )
        ledger = payload.get("discovery_ledger")
    else:
        raise RuntimeError("export-review requires a discovery or freeze artifact")
    if not isinstance(ledger, dict):
        raise RuntimeError("artifact does not contain a discovery ledger")
    verify_discovery_ledger(
        ledger,
        expected_repository_head=expected_head,
        policy=policy,
        classifier=classifier,
    )
    return ledger


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    policy = _load_auto_qa_policy()
    if args.command == "export-review":
        repository_head = current_repository_head()
        artifact = load_artifact(args.ledger)
        ledger = _ledger_from_artifact(
            artifact,
            expected_repository_head=repository_head,
            policy=policy,
        )
        output = args.output or _default_artifact_path("manual-review.json")
        written = export_manual_review(
            ledger,
            output,
            exported_at=_utc_now(),
            expected_repository_head=repository_head,
            policy=policy,
        )
        print(json.dumps({"artifact": str(written)}, sort_keys=True))
        return 0

    client = _create_read_only_client()
    repository_head = current_repository_head()
    if args.command == "discover":
        ledger = build_discovery_ledger(
            client,
            repository_head=repository_head,
            page_size=args.page_size,
            policy=policy,
        )
        sys.stdout.buffer.write(canonical_json_bytes(ledger) + b"\n")
        return 0

    first = build_discovery_ledger(
        client,
        repository_head=repository_head,
        page_size=args.page_size,
        policy=policy,
    )
    second = build_discovery_ledger(
        client,
        repository_head=repository_head,
        page_size=args.page_size,
        policy=policy,
    )
    output = args.output or _default_artifact_path("discovery-freeze.json")
    written = freeze_discovery_ledger(
        first,
        second,
        output,
        frozen_at=_utc_now(),
        expected_repository_head=repository_head,
        policy=policy,
    )
    print(
        json.dumps(
            {"artifact": str(written), "discovery_digest_sha256": first["digest_sha256"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
