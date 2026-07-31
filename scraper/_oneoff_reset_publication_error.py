"""One-off exact-ID reset for pure publication rows stuck in annotation error.

Default mode is dry-run. Dry-run can discover candidates by source, or write a
snapshot for repeated full UUIDs. Apply only consumes that snapshot, performs
per-row status/retry CAS, and never calls annotation or report settlement.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import stat
import subprocess
from typing import Any
from uuid import UUID

from annotator import _get_supabase
from publication_rules import is_pure_publication_record

TARGET_SOURCES = ("ndl_opensearch", "hanmoto", "kawade_rss")
QUERY_CHUNK_SIZE = 200
MAX_EXACT_CANDIDATES = 19
SNAPSHOT_SCHEMA = "publication-error-reset.v1"
TARGET_FIELDS = frozenset({"annotation_status", "annotation_retry_count"})
VOLATILE_FIELDS = frozenset({"updated_at"})
REPORT_TYPE = "annotation_error_stuck"


def _chunked(seq: list[str], size: int) -> list[list[str]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _script_path() -> Path:
    return Path(__file__).resolve()


def current_script_sha256() -> str:
    return hashlib.sha256(_script_path().read_bytes()).hexdigest()


def current_git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_script_path().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def row_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("event_id") or ""), str(row.get("id") or ""), str(row.get("field_name") or ""))


def normalize_event_ids(event_ids: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in event_ids or []:
        value = raw.strip()
        if len(value) != 36:
            raise ValueError(f"full UUID required for --event-id: {raw}")
        try:
            canonical = str(UUID(value))
        except ValueError as exc:
            raise ValueError(f"invalid UUID for --event-id: {raw}") from exc
        if canonical in seen:
            raise ValueError(f"duplicate --event-id: {canonical}")
        seen.add(canonical)
        normalized.append(canonical)
    if len(normalized) > MAX_EXACT_CANDIDATES:
        raise RuntimeError("20 or more exact candidates require Architect review")
    return normalized


def stable_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in sorted(row) if key not in TARGET_FIELDS and key not in VOLATILE_FIELDS}


def _execute_rows(query) -> list[dict[str, Any]]:
    return query.execute().data or []


def _fetch_discovery_candidates(sb, sources: list[str], limit: int | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        chunk = _execute_rows(
            sb.table("events")
            .select("*")
            .in_("source_name", sources)
            .eq("annotation_status", "error")
            .eq("is_active", True)
            .order("created_at", desc=True)
            .range(offset, offset + QUERY_CHUNK_SIZE - 1)
        )
        rows.extend(chunk)
        if len(chunk) < QUERY_CHUNK_SIZE:
            break
        offset += QUERY_CHUNK_SIZE
    candidates = [row for row in rows if is_pure_publication_record(row)]
    if limit is not None:
        candidates = candidates[:limit]
    return candidates


def _fetch_events_by_ids(sb, event_ids: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in _chunked(event_ids, QUERY_CHUNK_SIZE):
        rows.extend(_execute_rows(sb.table("events").select("*").in_("id", chunk)))
    by_id = {row.get("id"): row for row in rows}
    missing = [event_id for event_id in event_ids if event_id not in by_id]
    if missing:
        raise RuntimeError("selected event ids missing: " + ", ".join(missing))
    if len(by_id) != len(event_ids):
        raise RuntimeError("selected event id count changed; zero writes performed")
    return [by_id[event_id] for event_id in event_ids]


def _fetch_related(sb, event_ids: list[str]) -> dict[str, Any]:
    field_corrections: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    for chunk in _chunked(event_ids, QUERY_CHUNK_SIZE):
        field_corrections.extend(_execute_rows(sb.table("field_corrections").select("*").in_("event_id", chunk)))
        report_rows = _execute_rows(
            sb.table("event_reports").select("*").in_("event_id", chunk).eq("status", "pending")
        )
        reports.extend(row for row in report_rows if REPORT_TYPE in (row.get("report_types") or []))
    field_corrections = sorted(field_corrections, key=row_sort_key)
    reports = sorted(reports, key=row_sort_key)
    return {
        "field_corrections": {
            "count": len(field_corrections),
            "sha256": sha256(field_corrections),
            "rows": field_corrections,
        },
        "annotation_error_stuck_reports": {
            "count": len(reports),
            "sha256": sha256(reports),
            "rows": reports,
            "id_status": [{"id": row.get("id"), "status": row.get("status")} for row in reports],
        },
    }


def _validate_snapshot_candidate(row: dict[str, Any]) -> None:
    event_id = row.get("id")
    if row.get("is_active") is not True:
        raise RuntimeError(f"selected event is not active: {event_id}")
    if not is_pure_publication_record(row):
        raise RuntimeError(f"selected event is not exact pure publication: {event_id}")
    if row.get("annotation_status") != "error":
        raise RuntimeError(f"selected event is not in annotation_status=error: {event_id}")


def _with_snapshot_hash(payload: dict[str, Any]) -> dict[str, Any]:
    unsigned = {key: value for key, value in payload.items() if key != "snapshot_sha256"}
    return {**unsigned, "snapshot_sha256": sha256(unsigned)}


def build_snapshot(sb, event_ids: list[str], *, generated_at: str | None = None) -> dict[str, Any]:
    normalized_ids = normalize_event_ids(event_ids)
    if not normalized_ids:
        raise RuntimeError("snapshot requires at least one --event-id")
    events = _fetch_events_by_ids(sb, normalized_ids)
    for row in events:
        _validate_snapshot_candidate(row)
    payload = {
        "schema": SNAPSHOT_SCHEMA,
        "generated_at": generated_at or _utc_now(),
        "operator": {
            "git_head": current_git_head(),
            "script_sha256": current_script_sha256(),
        },
        "event_ids": normalized_ids,
        "events_before": events,
        "related": _fetch_related(sb, normalized_ids),
        "contract": {
            "target_fields": sorted(TARGET_FIELDS),
            "volatile_audit_only_fields": sorted(VOLATILE_FIELDS),
            "stable_fields_are_dynamic_full_row_minus_target_and_volatile": True,
        },
    }
    return _with_snapshot_hash(payload)


def write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"snapshot path already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR)


def load_snapshot(path: Path) -> dict[str, Any]:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    expected = snapshot.get("snapshot_sha256")
    actual = sha256({key: value for key, value in snapshot.items() if key != "snapshot_sha256"})
    if expected != actual:
        raise RuntimeError("snapshot hash mismatch")
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise RuntimeError("unsupported snapshot schema")
    return snapshot


def _assert_operator_unchanged(snapshot: dict[str, Any]) -> None:
    operator = snapshot.get("operator") or {}
    if operator.get("git_head") != current_git_head():
        raise RuntimeError("git HEAD drift; zero writes performed")
    if operator.get("script_sha256") != current_script_sha256():
        raise RuntimeError("script SHA drift; zero writes performed")


def _snapshot_rows_by_id(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in snapshot.get("events_before") or []}


def _related_matches(snapshot: dict[str, Any], current_related: dict[str, Any]) -> bool:
    for name, expected in snapshot["related"].items():
        current = current_related.get(name) or {}
        if expected.get("count") != current.get("count") or expected.get("sha256") != current.get("sha256"):
            return False
    return True


def _classify_current_state(snapshot_row: dict[str, Any], current_row: dict[str, Any]) -> str:
    if stable_projection(snapshot_row) != stable_projection(current_row):
        return "stable_drift"
    if (
        current_row.get("annotation_status") == "error"
        and current_row.get("annotation_retry_count") == snapshot_row.get("annotation_retry_count")
    ):
        return "before"
    if current_row.get("annotation_status") == "pending" and current_row.get("annotation_retry_count") == 0:
        return "after"
    return "third_state"


def _apply_retry_filter(query, captured_retry: Any):
    if captured_retry is None and hasattr(query, "is_"):
        return query.is_("annotation_retry_count", "null")
    return query.eq("annotation_retry_count", captured_retry)


def _cas_reset_event(sb, event_id: str, captured_retry: Any) -> list[dict[str, Any]]:
    query = (
        sb.table("events")
        .update({"annotation_status": "pending", "annotation_retry_count": 0})
        .eq("id", event_id)
        .eq("annotation_status", "error")
    )
    return _execute_rows(_apply_retry_filter(query, captured_retry).select("id"))


def _require_after_state(event_id: str, snapshot_row: dict[str, Any], current_row: dict[str, Any]) -> None:
    if stable_projection(snapshot_row) != stable_projection(current_row):
        raise RuntimeError(f"stable field changed after reset for {event_id}")
    if current_row.get("annotation_status") != "pending" or current_row.get("annotation_retry_count") != 0:
        raise RuntimeError(f"logical read-back failed for {event_id}")


def _preflight_apply(sb, snapshot: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str], list[str]]:
    event_ids = list(snapshot["event_ids"])
    current_rows = _fetch_events_by_ids(sb, event_ids)
    current_by_id = {row["id"]: row for row in current_rows}
    snapshot_by_id = _snapshot_rows_by_id(snapshot)
    if set(current_by_id) != set(snapshot_by_id):
        raise RuntimeError("selected event ids changed; zero writes performed")
    current_related = _fetch_related(sb, event_ids)
    if not _related_matches(snapshot, current_related):
        raise RuntimeError("field_corrections or report invariant drift; zero writes performed")

    states: dict[str, str] = {}
    warnings: list[str] = []
    for event_id in event_ids:
        snapshot_row = snapshot_by_id[event_id]
        current_row = current_by_id[event_id]
        state = _classify_current_state(snapshot_row, current_row)
        if state == "stable_drift":
            raise RuntimeError("stable-field drift; zero writes performed; rerun dry-run with refreshed snapshot")
        if state == "third_state":
            raise RuntimeError(f"third status/retry state for {event_id}; zero writes performed")
        if snapshot_row.get("updated_at") != current_row.get("updated_at"):
            warnings.append(
                f"updated_at_only_drift={event_id} "
                f"snapshot={snapshot_row.get('updated_at')} "
                f"current={current_row.get('updated_at')}"
            )
        states[event_id] = state
    return current_by_id, states, warnings


def apply_snapshot(sb, snapshot: dict[str, Any]) -> dict[str, Any]:
    _assert_operator_unchanged(snapshot)
    event_ids = list(snapshot["event_ids"])
    snapshot_by_id = _snapshot_rows_by_id(snapshot)
    _current_by_id, states, warnings = _preflight_apply(sb, snapshot)

    applied_ids: list[str] = []
    noop_ids: list[str] = []
    for event_id in event_ids:
        snapshot_row = snapshot_by_id[event_id]
        if states[event_id] == "after":
            noop_ids.append(event_id)
            continue

        rows = _cas_reset_event(sb, event_id, snapshot_row.get("annotation_retry_count"))
        if len(rows) != 1:
            raise RuntimeError(f"CAS affected {len(rows)} rows for {event_id}")
        read_back = _fetch_events_by_ids(sb, [event_id])[0]
        _require_after_state(event_id, snapshot_row, read_back)
        if not _related_matches(snapshot, _fetch_related(sb, event_ids)):
            raise RuntimeError("field_corrections or report invariant changed after reset")
        applied_ids.append(event_id)

    return {
        "applied_ids": applied_ids,
        "noop_ids": noop_ids,
        "warnings": warnings,
        "report_state": snapshot["related"]["annotation_error_stuck_reports"]["id_status"],
    }


def _print_discovery(rows: list[dict[str, Any]]) -> None:
    by_source = Counter(row.get("source_name") or "<null>" for row in rows)
    print("publication_error_reset_discovery")
    print(f"candidate_total={len(rows)}")
    for source_name, count in sorted(by_source.items()):
        print(f"  {source_name}: {count}")
    for row in rows:
        print(f"  {row['id']} | {row.get('source_name')} | retry={row.get('annotation_retry_count')}")


def _print_apply_report(report: dict[str, Any]) -> None:
    print("publication_error_reset_apply")
    print(f"applied_total={len(report['applied_ids'])}")
    for event_id in report["applied_ids"]:
        print(f"  applied={event_id}")
    print(f"noop_total={len(report['noop_ids'])}")
    for event_id in report["noop_ids"]:
        print(f"  noop={event_id}")
    for warning in report["warnings"]:
        print(f"warning={warning}")
    print("reports_unchanged=true")


def run(
    *,
    apply_changes: bool,
    sources: list[str] | None = None,
    event_ids: list[str] | None = None,
    limit: int | None = None,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    normalized_ids = normalize_event_ids(event_ids)
    if apply_changes:
        if not normalized_ids:
            raise RuntimeError("apply requires repeated full --event-id values")
        if sources:
            raise RuntimeError("--source is discovery-only and cannot be used with --apply")
        if limit is not None:
            raise RuntimeError("--limit is discovery-only and cannot be used with --apply")
        if snapshot_path is None:
            raise RuntimeError("apply requires --snapshot-path")
        snapshot = load_snapshot(snapshot_path)
        if snapshot.get("event_ids") != normalized_ids:
            raise RuntimeError("--event-id values do not match snapshot")
        report = apply_snapshot(_get_supabase(), snapshot)
        _print_apply_report(report)
        return report

    sb = _get_supabase()
    if normalized_ids:
        if sources or limit is not None:
            raise RuntimeError("exact --event-id dry-run cannot be combined with --source or --limit")
        snapshot = build_snapshot(sb, normalized_ids)
        print("publication_error_reset_snapshot")
        print(f"selected_total={len(normalized_ids)}")
        print(f"snapshot_sha256={snapshot['snapshot_sha256']}")
        if snapshot_path is not None:
            write_snapshot(snapshot_path, snapshot)
            print(f"snapshot_path={snapshot_path}")
        print("dry_run_only=true")
        return snapshot

    rows = _fetch_discovery_candidates(sb, sources or list(TARGET_SOURCES), limit)
    _print_discovery(rows)
    if len(rows) > MAX_EXACT_CANDIDATES:
        print("size_gate=architect_review_required")
    print("dry_run_only=true")
    return {"candidates": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset exact pure publication error events to pending")
    parser.add_argument("--apply", action="store_true", help="Apply a verified snapshot with per-row CAS")
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted(TARGET_SOURCES),
        help="Discovery-only source filter",
    )
    parser.add_argument("--event-id", action="append", help="Full UUID. Repeat for each selected event")
    parser.add_argument("--limit", type=int, help="Discovery-only candidate limit")
    parser.add_argument("--snapshot-path", type=Path, help="Dry-run output or apply input snapshot path")
    args = parser.parse_args()
    run(
        apply_changes=args.apply,
        sources=args.source,
        event_ids=args.event_id,
        limit=args.limit,
        snapshot_path=args.snapshot_path,
    )


if __name__ == "__main__":
    main()