from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
from typing import Any, Callable
from urllib.parse import urlparse
from uuid import UUID, uuid4

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "tokyo-taiwan-radar/authoritative-venue-repair"
SCHEMA_VERSION = 1
ACTION_ORDER = (
    "venue_update",
    "venue_insert",
    "event_fc",
    "venue_delete",
)
MUTATION_METHODS = frozenset({"delete", "insert", "rpc", "update", "upsert"})
ACTION_TYPES = frozenset(ACTION_ORDER)
ELIGIBILITY_STATUSES = frozenset({"eligible", "review_conflict", "skip"})
STATE_IMAGE_KEYS = frozenset(
    {"venue", "event", "field_corrections", "venue_references"}
)
FC_IMAGE_KEYS = frozenset({"event_id", "target_fields", "rows", "absent_fields"})
FC_REQUIRED_FIELDS = frozenset(
    {
        "id",
        "event_id",
        "field_name",
        "original_value",
        "corrected_value",
        "corrected_by",
        "report_id",
        "created_at",
    }
)
ACTION_REQUIRED_KEYS = frozenset(
    {
        "id",
        "type",
        "dependencies",
        "eligibility",
        "evidence",
        "before",
        "after",
        "apply_expected",
        "rollback_expected",
        "apply_operations",
        "rollback_operations",
        "conflicts",
        "skips",
        "already_applied",
        "volatile_event_fields",
    }
)


class ReadOnlyProxy:
    def __init__(self, target: Any):
        self._target = target

    def __getattr__(self, name: str) -> Any:
        if name in MUTATION_METHODS:
            raise RuntimeError(f"read-only client blocked Supabase mutation: {name}")
        attribute = getattr(self._target, name)
        if not callable(attribute):
            return attribute

        def call(*args: Any, **kwargs: Any) -> Any:
            result = attribute(*args, **kwargs)
            if result is None or isinstance(
                result,
                (bool, bytes, dict, float, int, list, set, str, tuple),
            ):
                return result
            return ReadOnlyProxy(result)

        return call


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def action_digest(action: dict[str, Any]) -> str:
    body = {key: value for key, value in action.items() if key != "digest"}
    return sha256_json(body)


def row_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("id") or ""),
        str(row.get("event_id") or ""),
        str(row.get("field_name") or ""),
    )


def fc_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def empty_fc_image(event_id: str | None = None) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "target_fields": [],
        "rows": [],
        "absent_fields": [],
    }


def empty_state_image() -> dict[str, Any]:
    return {
        "venue": None,
        "event": None,
        "field_corrections": empty_fc_image(),
        "venue_references": [],
    }


def _valid_uuid(value: Any) -> bool:
    try:
        return str(UUID(str(value))) == str(value)
    except (ValueError, TypeError, AttributeError):
        return False


def _validate_fc_image(image: Any, *, label: str) -> None:
    if not isinstance(image, dict) or set(image) != FC_IMAGE_KEYS:
        raise RuntimeError(f"{label} field_corrections image is incomplete")
    target_fields = image["target_fields"]
    absent_fields = image["absent_fields"]
    rows = image["rows"]
    if not isinstance(target_fields, list) or target_fields != sorted(set(target_fields)):
        raise RuntimeError(f"{label} target_fields must be sorted and unique")
    if not isinstance(absent_fields, list) or absent_fields != sorted(set(absent_fields)):
        raise RuntimeError(f"{label} absent_fields must be sorted and unique")
    if not isinstance(rows, list) or rows != sorted(rows, key=row_sort_key):
        raise RuntimeError(f"{label} field_correction rows must use fixed order")
    for row in rows:
        if not isinstance(row, dict) or not FC_REQUIRED_FIELDS.issubset(row):
            raise RuntimeError(f"{label} field_correction row is incomplete")
        if image["event_id"] is not None and row.get("event_id") != image["event_id"]:
            raise RuntimeError(f"{label} field_correction event_id mismatch")
    rows_by_target = {
        str(row["field_name"])
        for row in rows
        if str(row.get("field_name")) in target_fields
    }
    if rows_by_target & set(absent_fields):
        raise RuntimeError(f"{label} field_correction presence/absence overlap")
    if rows_by_target | set(absent_fields) != set(target_fields):
        raise RuntimeError(f"{label} lacks explicit target FC presence/absence")


def _validate_state_image(image: Any, *, label: str) -> None:
    if not isinstance(image, dict) or set(image) != STATE_IMAGE_KEYS:
        raise RuntimeError(f"{label} state image is incomplete")
    for entity in ("venue", "event"):
        row = image[entity]
        if row is not None and (not isinstance(row, dict) or not row.get("id")):
            raise RuntimeError(f"{label} {entity} row is incomplete")
    references = image["venue_references"]
    if not isinstance(references, list) or references != sorted(set(references)):
        raise RuntimeError(f"{label} venue references must be sorted and unique")
    _validate_fc_image(image["field_corrections"], label=label)


def _changed_event_fields(action: dict[str, Any]) -> set[str]:
    before = action["before"]["event"] or {}
    after = action["after"]["event"] or {}
    volatile = set(action["volatile_event_fields"])
    return {
        field
        for field in set(before) | set(after)
        if field not in volatile and before.get(field) != after.get(field)
    }


def _validate_operations(action: dict[str, Any], key: str) -> None:
    operations = action[key]
    if not isinstance(operations, list):
        raise RuntimeError(f"{action['id']} {key} must be a list")
    for operation in operations:
        required = {
            "field_name",
            "mode",
            "new_value",
            "expected_event_value",
            "expected_fc",
        }
        if not isinstance(operation, dict) or not required.issubset(operation):
            raise RuntimeError(f"{action['id']} {key} operation is incomplete")
        if operation["mode"] not in {"lock_clean", "lock_empty", "unlock_only"}:
            raise RuntimeError(f"{action['id']} {key} has unsupported helper mode")
        expected_fc = operation["expected_fc"]
        if expected_fc is not None and not FC_REQUIRED_FIELDS.issubset(expected_fc):
            raise RuntimeError(f"{action['id']} {key} expected_fc is incomplete")


def _review_conflicts(action: dict[str, Any]) -> list[dict[str, Any]]:
    if action["type"] != "event_fc":
        return []
    conflicts = [
        {
            "type": "human_field_correction",
            "field_name": row["field_name"],
            "field_correction_id": row["id"],
        }
        for row in action["before"]["field_corrections"]["rows"]
        if row.get("corrected_by") is not None
    ]
    before_event = action["before"]["event"] or {}
    after_event = action["after"]["event"] or {}
    before_submission = before_event.get("submission_url")
    if before_submission and before_submission != after_event.get("submission_url"):
        conflicts.append(
            {
                "type": "submission_url_conflict",
                "before": before_submission,
                "after": after_event.get("submission_url"),
            }
        )
    return conflicts


def validate_action(action: dict[str, Any], *, require_digest: bool) -> None:
    required = ACTION_REQUIRED_KEYS | ({"digest"} if require_digest else set())
    if not isinstance(action, dict) or not required.issubset(action):
        raise RuntimeError("manifest action is incomplete")
    if not _valid_uuid(action["id"]):
        raise RuntimeError(f"manifest action id is not a full UUID: {action.get('id')}")
    if action["type"] not in ACTION_TYPES:
        raise RuntimeError(f"unsupported manifest action type: {action['type']}")
    if not isinstance(action["dependencies"], list) or not all(
        _valid_uuid(value) for value in action["dependencies"]
    ):
        raise RuntimeError(f"{action['id']} dependencies must be full UUIDs")
    eligibility = action["eligibility"]
    if not isinstance(eligibility, dict) or eligibility.get("status") not in ELIGIBILITY_STATUSES:
        raise RuntimeError(f"{action['id']} eligibility is incomplete")
    if not isinstance(action["evidence"], dict) or action["evidence"].get("complete") is not True:
        raise RuntimeError(f"{action['id']} eligibility evidence is incomplete")
    if not isinstance(action["volatile_event_fields"], list):
        raise RuntimeError(f"{action['id']} volatile_event_fields must be a list")
    _validate_state_image(action["before"], label=f"{action['id']} before")
    _validate_state_image(action["after"], label=f"{action['id']} after")
    if action["apply_expected"] != action["before"]:
        raise RuntimeError(f"{action['id']} apply_expected must equal the complete before image")
    if action["rollback_expected"] != action["after"]:
        raise RuntimeError(f"{action['id']} rollback_expected must equal the complete after image")
    if action["type"] == "event_fc":
        before_event = action["before"]["event"]
        after_event = action["after"]["event"]
        if not before_event or not after_event or before_event.get("id") != after_event.get("id"):
            raise RuntimeError(f"{action['id']} event images are incomplete")
        if set(before_event) != set(after_event):
            raise RuntimeError(f"{action['id']} event before/after columns differ")
        target_fields = set(action["before"]["field_corrections"]["target_fields"])
        if target_fields != set(action["after"]["field_corrections"]["target_fields"]):
            raise RuntimeError(f"{action['id']} target FC fields differ across images")
        if not _changed_event_fields(action).issubset(target_fields):
            raise RuntimeError(f"{action['id']} event delta is outside target FC fields")
        unrelated_before = [
            row
            for row in action["before"]["field_corrections"]["rows"]
            if row["field_name"] not in target_fields
        ]
        unrelated_after = [
            row
            for row in action["after"]["field_corrections"]["rows"]
            if row["field_name"] not in target_fields
        ]
        if unrelated_before != unrelated_after:
            raise RuntimeError(f"{action['id']} unrelated field corrections are not preserved")
        _validate_operations(action, "apply_operations")
        _validate_operations(action, "rollback_operations")
    elif action["apply_operations"] or action["rollback_operations"]:
        raise RuntimeError(f"{action['id']} venue action cannot contain event helper operations")
    before_venue = action["before"]["venue"]
    after_venue = action["after"]["venue"]
    if action["type"] == "venue_update":
        if not before_venue or not after_venue or before_venue.get("id") != after_venue.get("id"):
            raise RuntimeError(f"{action['id']} venue update images are incomplete")
        if set(before_venue) != set(after_venue):
            raise RuntimeError(f"{action['id']} venue update columns differ")
    if action["type"] == "venue_insert" and (before_venue is not None or not after_venue):
        raise RuntimeError(f"{action['id']} venue insert absence/after image is incomplete")
    if action["type"] == "venue_delete" and (not before_venue or after_venue is not None):
        raise RuntimeError(f"{action['id']} venue delete before/absence image is incomplete")


def validate_manifest_structure(manifest: dict[str, Any], *, require_digests: bool) -> None:
    if not manifest.get("project_ref"):
        raise RuntimeError("manifest project ref is missing")
    repository_sha = str(manifest.get("repository_sha") or "")
    if len(repository_sha) != 40 or any(character not in "0123456789abcdef" for character in repository_sha):
        raise RuntimeError("manifest repository SHA must be an exact 40-character commit")
    if manifest.get("action_order") != list(ACTION_ORDER):
        raise RuntimeError("manifest action order mismatch")
    actions = manifest.get("actions")
    if not isinstance(actions, list):
        raise RuntimeError("manifest actions must be a list")
    ranks = [ACTION_ORDER.index(action.get("type")) for action in actions]
    if ranks != sorted(ranks):
        raise RuntimeError("manifest actions are not in fixed action order")
    known: set[str] = set()
    for action in actions:
        validate_action(action, require_digest=require_digests)
        if action["id"] in known:
            raise RuntimeError(f"duplicate manifest action id: {action['id']}")
        missing = set(action["dependencies"]) - known
        if missing:
            raise RuntimeError(f"{action['id']} dependencies do not precede action: {sorted(missing)}")
        known.add(action["id"])


def _prepare_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared = [deepcopy(action) for action in actions]
    prepared.sort(key=lambda action: ACTION_ORDER.index(action["type"]))
    for action in prepared:
        conflicts = _review_conflicts(action)
        if conflicts:
            combined = [*action.get("conflicts", []), *conflicts]
            unique = {
                canonical_json_bytes(conflict): conflict
                for conflict in combined
            }
            action["conflicts"] = sorted(
                unique.values(),
                key=lambda row: (str(row.get("type")), str(row.get("field_name") or "")),
            )
            action["eligibility"] = {
                **action["eligibility"],
                "status": "review_conflict",
            }
    return prepared


def seal_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    manifest = deepcopy(payload)
    manifest.setdefault("schema", {"name": SCHEMA_NAME, "version": SCHEMA_VERSION})
    manifest.setdefault("captured_at", datetime.now(timezone.utc).isoformat())
    manifest.setdefault("action_order", list(ACTION_ORDER))
    manifest.setdefault("actions", [])
    manifest.setdefault("conflicts", [])
    manifest.setdefault("skips", [])
    manifest.setdefault("already_applied", [])
    manifest["actions"] = _prepare_actions(manifest["actions"])
    validate_manifest_structure(manifest, require_digests=False)
    for action in manifest["actions"]:
        action["digest"] = action_digest(action)
    manifest.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = sha256_json(manifest)
    return manifest


def verify_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != {"name": SCHEMA_NAME, "version": SCHEMA_VERSION}:
        raise RuntimeError("unsupported authoritative venue repair manifest schema/version")
    if manifest.get("action_order") != list(ACTION_ORDER):
        raise RuntimeError("manifest action order mismatch")
    for action in manifest.get("actions") or []:
        if action.get("digest") != action_digest(action):
            raise RuntimeError(f"action digest mismatch: {action.get('id')}")
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if manifest.get("manifest_sha256") != sha256_json(body):
        raise RuntimeError("manifest SHA-256 mismatch; immutable input was modified")
    validate_manifest_structure(manifest, require_digests=True)


def project_ref_from_url(url: str) -> str:
    host = urlparse(url).hostname or ""
    if not host.endswith(".supabase.co") or "." not in host:
        raise RuntimeError(f"cannot derive Supabase project ref from URL: {url}")
    return host.split(".", 1)[0]


def verify_repo_sha_on_origin_main(repository_sha: str) -> bool:
    if len(repository_sha) != 40:
        return False
    commit = subprocess.run(
        ["git", "-C", str(ROOT), "cat-file", "-e", f"{repository_sha}^{{commit}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if commit.returncode != 0:
        return False
    ancestry = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", repository_sha, "origin/main"],
        check=False,
        capture_output=True,
        text=True,
    )
    return ancestry.returncode == 0


def verify_runtime_identity(
    manifest: dict[str, Any],
    *,
    project_ref: str,
    repo_sha_verifier: Callable[[str], bool] = verify_repo_sha_on_origin_main,
) -> None:
    if manifest.get("project_ref") != project_ref:
        raise RuntimeError(
            f"project ref mismatch: manifest={manifest.get('project_ref')} runtime={project_ref}"
        )
    if not repo_sha_verifier(str(manifest.get("repository_sha") or "")):
        raise RuntimeError("manifest repository SHA is not present in origin/main")


def _fetch_one(sb: Any, table: str, row_id: str) -> dict[str, Any] | None:
    rows = (
        sb.table(table)
        .select("*")
        .eq("id", row_id)
        .limit(2)
        .execute()
        .data
        or []
    )
    if len(rows) > 1:
        raise RuntimeError(f"multiple {table} rows for id={row_id}")
    return deepcopy(rows[0]) if rows else None


def _fetch_venue_by_name(sb: Any, canonical_name_ja: str) -> list[dict[str, Any]]:
    rows = (
        sb.table("venues")
        .select("*")
        .eq("canonical_name_ja", canonical_name_ja)
        .order("id")
        .execute()
        .data
        or []
    )
    return sorted((deepcopy(row) for row in rows), key=row_sort_key)


def _fetch_venue_references(sb: Any, venue_id: str) -> list[str]:
    rows = (
        sb.table("events")
        .select("id")
        .eq("venue_id", venue_id)
        .order("id")
        .execute()
        .data
        or []
    )
    return sorted(str(row["id"]) for row in rows)


def _fetch_event_fcs(sb: Any, event_id: str) -> list[dict[str, Any]]:
    rows = (
        sb.table("field_corrections")
        .select("*")
        .eq("event_id", event_id)
        .order("id")
        .execute()
        .data
        or []
    )
    return sorted((deepcopy(row) for row in rows), key=row_sort_key)


def _observed_fc_image(action: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    target_fields = action["before"]["field_corrections"]["target_fields"]
    present = {str(row.get("field_name")) for row in rows}
    event = action["before"]["event"] or action["after"]["event"] or {}
    return {
        "event_id": event.get("id"),
        "target_fields": list(target_fields),
        "rows": rows,
        "absent_fields": sorted(set(target_fields) - present),
    }


def observe_action(sb: Any, action: dict[str, Any]) -> dict[str, Any]:
    if action["type"] == "event_fc":
        event_id = str((action["before"]["event"] or action["after"]["event"])["id"])
        event = _fetch_one(sb, "events", event_id)
        rows = _fetch_event_fcs(sb, event_id)
        return {
            "venue": None,
            "event": event,
            "field_corrections": _observed_fc_image(action, rows),
            "venue_references": [],
        }
    venue = action["before"]["venue"] or action["after"]["venue"]
    venue_id = str(venue["id"])
    live = _fetch_one(sb, "venues", venue_id)
    return {
        "venue": live,
        "event": None,
        "field_corrections": empty_fc_image(),
        "venue_references": _fetch_venue_references(sb, venue_id),
    }


def _fc_row_matches(expected: dict[str, Any], actual: dict[str, Any], *, after: bool) -> bool:
    if not FC_REQUIRED_FIELDS.issubset(actual):
        return False
    if expected.get("id") is not None:
        return expected == actual
    if not after or not actual.get("id") or not actual.get("created_at"):
        return False
    for key, value in expected.items():
        if key in {"id", "created_at"} and value is None:
            continue
        if actual.get(key) != value:
            return False
    return True


def _fc_rows_match(
    expected: list[dict[str, Any]], actual: list[dict[str, Any]], *, after: bool
) -> bool:
    remaining = list(actual)
    for row in expected:
        matches = [
            index
            for index, candidate in enumerate(remaining)
            if (
                candidate.get("id") == row.get("id")
                if row.get("id") is not None
                else candidate.get("event_id") == row.get("event_id")
                and candidate.get("field_name") == row.get("field_name")
            )
        ]
        if len(matches) != 1 or not _fc_row_matches(row, remaining[matches[0]], after=after):
            return False
        remaining.pop(matches[0])
    return not remaining


def _row_matches(
    expected: dict[str, Any] | None,
    actual: dict[str, Any] | None,
    *,
    volatile_fields: list[str],
) -> bool:
    if expected is None or actual is None:
        return expected is actual
    if set(expected) != set(actual):
        return False
    volatile = set(volatile_fields)
    return all(expected.get(key) == actual.get(key) for key in expected if key not in volatile)


def state_image_matches(
    action: dict[str, Any], expected: dict[str, Any], actual: dict[str, Any], *, after: bool
) -> bool:
    expected_fc = expected["field_corrections"]
    actual_fc = actual["field_corrections"]
    return (
        _row_matches(expected["venue"], actual["venue"], volatile_fields=[])
        and _row_matches(
            expected["event"],
            actual["event"],
            volatile_fields=action["volatile_event_fields"],
        )
        and expected_fc["event_id"] == actual_fc["event_id"]
        and expected_fc["target_fields"] == actual_fc["target_fields"]
        and expected_fc["absent_fields"] == actual_fc["absent_fields"]
        and _fc_rows_match(expected_fc["rows"], actual_fc["rows"], after=after)
        and expected["venue_references"] == actual["venue_references"]
    )


def classify_action_state(sb: Any, action: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if action["type"] == "venue_insert":
        after_venue = action["after"]["venue"]
        by_id = _fetch_one(sb, "venues", str(after_venue["id"]))
        by_name = _fetch_venue_by_name(sb, str(after_venue["canonical_name_ja"]))
        references = _fetch_venue_references(sb, str(after_venue["id"]))
        observed = {
            "venue": by_id,
            "event": None,
            "field_corrections": empty_fc_image(),
            "venue_references": references,
        }
        if by_id is None and not by_name and state_image_matches(
            action, action["before"], observed, after=False
        ):
            return "before", observed
        if (
            by_id == after_venue
            and by_name == [after_venue]
            and state_image_matches(action, action["after"], observed, after=True)
        ):
            return "after", observed
        raise RuntimeError(
            f"STOP: venue insert ID/name absence found partial or third state: {action['id']}"
        )
    observed = observe_action(sb, action)
    if state_image_matches(action, action["before"], observed, after=False):
        return "before", observed
    if state_image_matches(action, action["after"], observed, after=True):
        return "after", observed
    raise RuntimeError(f"STOP: action found partial, third, or drifted state: {action['id']}")


def preflight_actions(sb: Any, manifest: dict[str, Any]) -> tuple[str, dict[str, dict[str, Any]]]:
    conflicts = [
        action["id"]
        for action in manifest["actions"]
        if action["eligibility"]["status"] == "review_conflict"
    ]
    if conflicts:
        raise RuntimeError(f"STOP: review_conflict actions block apply: {conflicts}")
    states: dict[str, str] = {}
    observations: dict[str, dict[str, Any]] = {}
    for action in manifest["actions"]:
        if action["eligibility"]["status"] == "skip":
            continue
        state, observed = classify_action_state(sb, action)
        states[action["id"]] = state
        observations[action["id"]] = observed
    unique_states = set(states.values())
    if len(unique_states) > 1:
        raise RuntimeError(f"STOP: manifest is partially applied; zero writes performed: {states}")
    return (next(iter(unique_states)) if unique_states else "after"), observations


def _capture_or_preview(
    sb: Any,
    plan: dict[str, Any],
    *,
    project_ref: str,
    repo_sha_verifier: Callable[[str], bool],
    captured_at: str | None,
    mode: str,
) -> dict[str, Any]:
    payload = {
        "schema": {"name": SCHEMA_NAME, "version": SCHEMA_VERSION},
        "captured_at": captured_at or datetime.now(timezone.utc).isoformat(),
        "project_ref": plan.get("project_ref"),
        "repository_sha": plan.get("repository_sha"),
        "action_order": list(ACTION_ORDER),
        "actions": plan.get("actions") or [],
        "conflicts": deepcopy(plan.get("conflicts") or []),
        "skips": deepcopy(plan.get("skips") or []),
        "already_applied": [],
        "capture_mode": mode,
    }
    prepared = seal_manifest(payload)
    verify_runtime_identity(
        prepared,
        project_ref=project_ref,
        repo_sha_verifier=repo_sha_verifier,
    )
    read_only = sb if isinstance(sb, ReadOnlyProxy) else ReadOnlyProxy(sb)
    already_applied = []
    for action in prepared["actions"]:
        state, _observed = classify_action_state(read_only, action)
        if state == "after":
            already_applied.append(
                {"action_id": action["id"], "reason": "exact_after_state"}
            )
    payload["actions"] = prepared["actions"]
    for action in payload["actions"]:
        action.pop("digest", None)
    payload["already_applied"] = already_applied
    action_conflicts = [
            {"action_id": action["id"], **conflict}
            for action in payload["actions"]
            for conflict in action["conflicts"]
        ]
    payload["conflicts"] = sorted(
        [*deepcopy(plan.get("conflicts") or []), *action_conflicts],
        key=lambda row: (str(row.get("action_id")), str(row.get("type"))),
    )
    action_skips = [
            {"action_id": action["id"], **skip}
            for action in payload["actions"]
            for skip in action["skips"]
        ]
    payload["skips"] = sorted(
        [*deepcopy(plan.get("skips") or []), *action_skips],
        key=lambda row: (str(row.get("action_id")), str(row.get("reason"))),
    )
    return seal_manifest(payload)


def preview_manifest(
    sb: Any,
    plan: dict[str, Any],
    *,
    project_ref: str,
    repo_sha_verifier: Callable[[str], bool] = verify_repo_sha_on_origin_main,
    captured_at: str | None = None,
) -> dict[str, Any]:
    return _capture_or_preview(
        sb,
        plan,
        project_ref=project_ref,
        repo_sha_verifier=repo_sha_verifier,
        captured_at=captured_at,
        mode="preview-read-only",
    )


def capture_manifest(
    sb: Any,
    plan: dict[str, Any],
    output_path: Path,
    *,
    project_ref: str,
    repo_sha_verifier: Callable[[str], bool] = verify_repo_sha_on_origin_main,
    captured_at: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    manifest = _capture_or_preview(
        sb,
        plan,
        project_ref=project_ref,
        repo_sha_verifier=repo_sha_verifier,
        captured_at=captured_at,
        mode="capture-read-only",
    )
    return write_immutable_json(output_path, manifest), manifest


class LocalJournal:
    def __init__(self, path: Path, *, mode: str, manifest_digest: str):
        self.path = assert_ignored_tmp_path(path)
        self.mode = mode
        self.manifest_digest = manifest_digest
        self.run_id = str(uuid4())
        self.sequence = 0
        self._handle = self.path.open("x", encoding="utf-8")
        self.append(
            "run_start",
            details={"mode": mode, "manifest_sha256": manifest_digest},
        )

    def append(
        self,
        event: str,
        *,
        action_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "sequence": self.sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "mode": self.mode,
            "manifest_sha256": self.manifest_digest,
            "event": event,
            "action_id": action_id,
            "details": deepcopy(details or {}),
        }
        self._handle.write(canonical_json_bytes(entry).decode("utf-8") + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self.sequence += 1

    def close(self, *, status: str, details: dict[str, Any] | None = None) -> None:
        if self._handle.closed:
            return
        self.append("run_final", details={"status": status, **(details or {})})
        self._handle.close()
        self.path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def default_journal_path(mode: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return ROOT / "tmp" / "authoritative-venue-repair" / f"{mode}-{stamp}-{uuid4()}.jsonl"


def audited_write(sb: Any, **kwargs: Any) -> bool:
    from qa_auto_fix import unlock_and_write

    return unlock_and_write(sb, **kwargs)


def _apply_full_row_filters(query: Any, row: dict[str, Any]) -> Any:
    from qa_auto_fix import apply_cas_filter

    for field in sorted(row):
        query = apply_cas_filter(query, field, row[field])
    return query


def _exact_mutation_row(rows: Any, expected: dict[str, Any], *, label: str) -> dict[str, Any]:
    result = list(rows or [])
    if len(result) != 1 or result[0] != expected:
        raise RuntimeError(
            f"{label} exact read-back mismatch: expected one full row, got={result!r}"
        )
    return deepcopy(result[0])


def _venue_insert(sb: Any, row: dict[str, Any]) -> dict[str, Any]:
    if _fetch_one(sb, "venues", str(row["id"])) is not None:
        raise RuntimeError(f"venue insert ID is no longer absent: {row['id']}")
    by_name = _fetch_venue_by_name(sb, str(row["canonical_name_ja"]))
    if by_name:
        raise RuntimeError(
            f"venue insert canonical name is no longer absent: {row['canonical_name_ja']}"
        )
    inserted = sb.table("venues").insert(deepcopy(row)).select("*").execute().data
    _exact_mutation_row(inserted, row, label="venue insert")
    read_back = _fetch_one(sb, "venues", str(row["id"]))
    if read_back != row:
        raise RuntimeError(f"venue insert read-back mismatch: {row['id']}")
    return read_back


def _venue_update(
    sb: Any,
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    if _fetch_one(sb, "venues", str(before["id"])) != before:
        raise RuntimeError(f"venue update full before CAS drift: {before['id']}")
    payload = {key: deepcopy(value) for key, value in after.items() if key != "id"}
    query = sb.table("venues").update(payload)
    query = _apply_full_row_filters(query, before)
    updated = query.select("*").execute().data
    _exact_mutation_row(updated, after, label="venue update")
    read_back = _fetch_one(sb, "venues", str(after["id"]))
    if read_back != after:
        raise RuntimeError(f"venue update read-back mismatch: {after['id']}")
    return read_back


def _venue_delete(sb: Any, row: dict[str, Any]) -> None:
    venue_id = str(row["id"])
    references = _fetch_venue_references(sb, venue_id)
    if references:
        raise RuntimeError(
            f"venue delete live-reference guard failed: {venue_id} refs={references}"
        )
    if _fetch_one(sb, "venues", venue_id) != row:
        raise RuntimeError(f"venue delete full before CAS drift: {venue_id}")
    query = sb.table("venues").delete()
    query = _apply_full_row_filters(query, row)
    deleted = query.select("*").execute().data
    _exact_mutation_row(deleted, row, label="venue delete")
    if _fetch_one(sb, "venues", venue_id) is not None:
        raise RuntimeError(f"venue delete read-back mismatch: {venue_id}")


def _target_fc(rows: list[dict[str, Any]], field_name: str) -> dict[str, Any] | None:
    matches = [row for row in rows if row.get("field_name") == field_name]
    if len(matches) > 1:
        raise RuntimeError(f"multiple field corrections for target field: {field_name}")
    return matches[0] if matches else None


def _operation_expected_fc_matches(expected: Any, actual: dict[str, Any] | None) -> bool:
    if expected is None:
        return actual is None
    if actual is None:
        return False
    return _fc_row_matches(expected, actual, after=expected.get("id") is None)


def execute_event_action(
    sb: Any,
    action: dict[str, Any],
    *,
    direction: str,
    manifest_digest: str,
    writer: Callable[..., bool] = audited_write,
) -> dict[str, Any]:
    operations_key = "apply_operations" if direction == "apply" else "rollback_operations"
    expected_image = action["after"] if direction == "apply" else action["before"]
    event_id = str((action["before"]["event"] or action["after"]["event"])["id"])
    for operation in action[operations_key]:
        field_name = str(operation["field_name"])
        event = _fetch_one(sb, "events", event_id)
        if event is None:
            raise RuntimeError(f"event helper target is missing: {event_id}")
        if event.get(field_name) != operation["expected_event_value"]:
            raise RuntimeError(
                f"event helper expected value drift: {event_id}.{field_name} "
                f"expected={operation['expected_event_value']!r} actual={event.get(field_name)!r}"
            )
        actual_fc = _target_fc(_fetch_event_fcs(sb, event_id), field_name)
        if not _operation_expected_fc_matches(operation["expected_fc"], actual_fc):
            raise RuntimeError(f"event helper expected FC drift: {event_id}.{field_name}")
        ok = writer(
            sb,
            event_id=event_id,
            field_name=field_name,
            new_value=deepcopy(operation["new_value"]),
            mode=operation["mode"],
            unlock_reason=(
                f"authoritative_venue_manifest:{direction}:{manifest_digest}:{action['id']}"
            ),
            report_id=operation.get("report_id"),
            r_class="authoritative_venue_repair",
            dry_run=False,
            expected_event_value=deepcopy(operation["expected_event_value"]),
            expected_fc=deepcopy(actual_fc),
        )
        if not ok:
            raise RuntimeError(f"unlock_and_write failed: {event_id}.{field_name}")
    observed = observe_action(sb, action)
    if not state_image_matches(
        action,
        expected_image,
        observed,
        after=direction == "apply",
    ):
        raise RuntimeError(f"event/FC exact read-back mismatch: {action['id']}")
    return observed


def execute_venue_action(
    sb: Any,
    action: dict[str, Any],
    *,
    direction: str,
) -> dict[str, Any]:
    before = action["before"]["venue"]
    after = action["after"]["venue"]
    if action["type"] == "venue_update":
        read_back = (
            _venue_update(sb, before, after)
            if direction == "apply"
            else _venue_update(sb, after, before)
        )
    elif action["type"] == "venue_insert":
        if direction == "apply":
            read_back = _venue_insert(sb, after)
        else:
            _venue_delete(sb, after)
            read_back = None
    elif action["type"] == "venue_delete":
        if direction == "apply":
            _venue_delete(sb, before)
            read_back = None
        else:
            read_back = _venue_insert(sb, before)
    else:
        raise RuntimeError(f"unsupported venue action: {action['type']}")
    observed = observe_action(sb, action)
    expected = action["after"] if direction == "apply" else action["before"]
    if direction == "rollback" and action["type"] == "venue_delete":
        expected = deepcopy(action["before"])
        expected["venue_references"] = deepcopy(action["after"]["venue_references"])
    if not state_image_matches(
        action,
        expected,
        observed,
        after=direction == "apply",
    ):
        raise RuntimeError(f"venue exact read-back mismatch: {action['id']}")
    return {"venue": read_back, "state": observed}


def verify_predelete_invariants(sb: Any, manifest: dict[str, Any]) -> None:
    for action in manifest["actions"]:
        if action["eligibility"]["status"] != "eligible":
            continue
        if action["type"] == "venue_delete":
            observed = observe_action(sb, action)
            transitional = deepcopy(action["before"])
            transitional["venue_references"] = deepcopy(action["after"]["venue_references"])
            if not state_image_matches(action, transitional, observed, after=False):
                raise RuntimeError(
                    f"pre-delete invariant mismatch: {action['id']}"
                )
            if observed["venue_references"]:
                raise RuntimeError(
                    f"pre-delete invariant still has live references: {action['id']}"
                )
            continue
        state, _observed = classify_action_state(sb, action)
        if state != "after":
            raise RuntimeError(f"post-action invariant is not exact after: {action['id']}")


def _run_action(
    sb: Any,
    action: dict[str, Any],
    *,
    direction: str,
    manifest_digest: str,
    journal: LocalJournal,
    writer: Callable[..., bool],
) -> None:
    journal.append(
        "action_start",
        action_id=action["id"],
        details={"type": action["type"], "direction": direction},
    )
    try:
        if action["type"] == "event_fc":
            read_back = execute_event_action(
                sb,
                action,
                direction=direction,
                manifest_digest=manifest_digest,
                writer=writer,
            )
        else:
            read_back = execute_venue_action(sb, action, direction=direction)
        journal.append(
            "action_read_back",
            action_id=action["id"],
            details={"state": read_back},
        )
        journal.append(
            "action_result",
            action_id=action["id"],
            details={"status": "applied" if direction == "apply" else "rolled_back"},
        )
    except Exception as exc:
        journal.append(
            "action_error",
            action_id=action["id"],
            details={"error": repr(exc)},
        )
        raise


def _run_manifest(
    sb: Any,
    manifest: dict[str, Any],
    *,
    mode: str,
    project_ref: str,
    journal_path: Path,
    repo_sha_verifier: Callable[[str], bool],
    writer: Callable[..., bool],
    invariant_verifier: Callable[[Any, dict[str, Any]], None],
) -> dict[str, Any]:
    journal = LocalJournal(
        journal_path,
        mode=mode,
        manifest_digest=str(manifest.get("manifest_sha256") or "unverified"),
    )
    mutation_count = 0
    completed: list[str] = []
    try:
        verify_manifest(manifest)
        verify_runtime_identity(
            manifest,
            project_ref=project_ref,
            repo_sha_verifier=repo_sha_verifier,
        )
        state, observations = preflight_actions(sb, manifest)
        journal.append(
            "preflight_result",
            details={"state": state, "observations": observations},
        )
        for action in manifest["actions"]:
            if action["eligibility"]["status"] == "skip":
                journal.append(
                    "action_result",
                    action_id=action["id"],
                    details={"status": "skipped", "reasons": action["skips"]},
                )
        expected_start = "before" if mode == "apply" else "after"
        already_done = "after" if mode == "apply" else "before"
        if state == already_done:
            for action in manifest["actions"]:
                if action["eligibility"]["status"] == "eligible":
                    journal.append(
                        "action_result",
                        action_id=action["id"],
                        details={"status": "already_applied" if mode == "apply" else "already_rolled_back"},
                    )
            journal.close(status="noop", details={"mutation_count": 0})
            return {
                "mode": mode,
                "status": "noop",
                "mutation_count": 0,
                "completed_action_ids": [],
                "journal": str(journal.path),
            }
        if state != expected_start:
            raise RuntimeError(f"STOP: {mode} requires exact {expected_start} state")

        eligible = [
            action
            for action in manifest["actions"]
            if action["eligibility"]["status"] == "eligible"
        ]
        eligible_ids = {action["id"] for action in eligible}
        invalid_dependencies = {
            action["id"]: sorted(set(action["dependencies"]) - eligible_ids)
            for action in eligible
            if set(action["dependencies"]) - eligible_ids
        }
        if invalid_dependencies:
            raise RuntimeError(
                f"eligible actions depend on non-eligible actions: {invalid_dependencies}"
            )
        if mode == "apply":
            phases = (
                [action for action in eligible if action["type"] in {"venue_update", "venue_insert"}],
                [action for action in eligible if action["type"] == "event_fc"],
            )
            for phase in phases:
                for action in phase:
                    missing = set(action["dependencies"]) - set(completed)
                    if missing:
                        raise RuntimeError(
                            f"action dependencies are incomplete: {action['id']} -> {sorted(missing)}"
                        )
                    _run_action(
                        sb,
                        action,
                        direction="apply",
                        manifest_digest=manifest["manifest_sha256"],
                        journal=journal,
                        writer=writer,
                    )
                    mutation_count += 1
                    completed.append(action["id"])
            journal.append("invariant_start")
            invariant_verifier(sb, manifest)
            journal.append("invariant_result", details={"status": "passed"})
            for action in eligible:
                if action["type"] != "venue_delete":
                    continue
                missing = set(action["dependencies"]) - set(completed)
                if missing:
                    raise RuntimeError(
                        f"action dependencies are incomplete: {action['id']} -> {sorted(missing)}"
                    )
                _run_action(
                    sb,
                    action,
                    direction="apply",
                    manifest_digest=manifest["manifest_sha256"],
                    journal=journal,
                    writer=writer,
                )
                mutation_count += 1
                completed.append(action["id"])
            final_state, final_observations = preflight_actions(sb, manifest)
            if final_state != "after":
                raise RuntimeError("final apply read-back is not exact after")
        else:
            for action in reversed(eligible):
                _run_action(
                    sb,
                    action,
                    direction="rollback",
                    manifest_digest=manifest["manifest_sha256"],
                    journal=journal,
                    writer=writer,
                )
                mutation_count += 1
                completed.append(action["id"])
            final_state, final_observations = preflight_actions(sb, manifest)
            if final_state != "before":
                raise RuntimeError("final rollback read-back is not exact before")
        journal.append(
            "final_read_back",
            details={"state": final_state, "observations": final_observations},
        )
        journal.close(status="completed", details={"mutation_count": mutation_count})
        return {
            "mode": mode,
            "status": "completed",
            "mutation_count": mutation_count,
            "completed_action_ids": completed,
            "journal": str(journal.path),
        }
    except Exception as exc:
        journal.append(
            "run_error",
            details={
                "error": repr(exc),
                "mutation_count": mutation_count,
                "completed_action_ids": completed,
                "automatic_rollback": False,
            },
        )
        journal.close(
            status="failed",
            details={
                "mutation_count": mutation_count,
                "completed_action_ids": completed,
                "automatic_rollback": False,
            },
        )
        raise RuntimeError(
            f"{mode} stopped; journal={journal.path}; mutation_count={mutation_count}; "
            f"automatic rollback disabled; error={exc}"
        ) from exc


def apply_manifest(
    sb: Any,
    manifest: dict[str, Any],
    *,
    project_ref: str,
    journal_path: Path | None = None,
    repo_sha_verifier: Callable[[str], bool] = verify_repo_sha_on_origin_main,
    writer: Callable[..., bool] = audited_write,
    invariant_verifier: Callable[[Any, dict[str, Any]], None] = verify_predelete_invariants,
) -> dict[str, Any]:
    return _run_manifest(
        sb,
        manifest,
        mode="apply",
        project_ref=project_ref,
        journal_path=journal_path or default_journal_path("apply"),
        repo_sha_verifier=repo_sha_verifier,
        writer=writer,
        invariant_verifier=invariant_verifier,
    )


def rollback_manifest(
    sb: Any,
    manifest: dict[str, Any],
    *,
    project_ref: str,
    journal_path: Path | None = None,
    repo_sha_verifier: Callable[[str], bool] = verify_repo_sha_on_origin_main,
    writer: Callable[..., bool] = audited_write,
) -> dict[str, Any]:
    return _run_manifest(
        sb,
        manifest,
        mode="rollback",
        project_ref=project_ref,
        journal_path=journal_path or default_journal_path("rollback"),
        repo_sha_verifier=repo_sha_verifier,
        writer=writer,
        invariant_verifier=verify_predelete_invariants,
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


def assert_ignored_tmp_path(path: Path, *, root: Path | None = None) -> Path:
    base = (root or ROOT).resolve()
    resolved = path.expanduser().resolve()
    try:
        relative = resolved.relative_to(base)
    except ValueError as exc:
        raise RuntimeError(f"artifact must be inside worktree tmp/: {resolved}") from exc
    if not relative.parts or relative.parts[0] != "tmp":
        raise RuntimeError(f"artifact must be inside worktree tmp/: {relative}")
    if not _is_git_ignored(resolved, root=base):
        raise RuntimeError(f"artifact path is not ignored by git: {relative}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def write_immutable_json(path: Path, payload: dict[str, Any]) -> Path:
    resolved = assert_ignored_tmp_path(path)
    with resolved.open("xb") as handle:
        handle.write(canonical_json_bytes(payload) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    resolved.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    if json.loads(resolved.read_text(encoding="utf-8")) != payload:
        raise RuntimeError(f"immutable JSON read-back mismatch: {resolved}")
    return resolved


def load_manifest(path: Path) -> dict[str, Any]:
    resolved = assert_ignored_tmp_path(path)
    manifest = json.loads(resolved.read_text(encoding="utf-8"))
    verify_manifest(manifest)
    return manifest


def get_supabase(*, read_only: bool) -> Any:
    env_file = Path(
        os.environ.get("AUTHORITATIVE_VENUE_REPAIR_ENV_FILE")
        or Path(__file__).with_name(".env")
    ).expanduser()
    load_dotenv(env_file)
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    from supabase import create_client

    client = create_client(url, key)
    return ReadOnlyProxy(client) if read_only else client


def runtime_project_ref() -> str:
    env_file = Path(
        os.environ.get("AUTHORITATIVE_VENUE_REPAIR_ENV_FILE")
        or Path(__file__).with_name(".env")
    ).expanduser()
    load_dotenv(env_file)
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL must be set")
    return project_ref_from_url(url)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Authoritative venue immutable repair engine")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--capture", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--rollback", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--journal-output", type=Path)
    args = parser.parse_args(argv)
    args.mode = "capture" if args.capture else "apply" if args.apply else "rollback" if args.rollback else "preview"
    if args.mode in {"preview", "capture"} and args.manifest:
        parser.error("--manifest is only accepted with --apply or --rollback")
    if args.mode in {"apply", "rollback"} and not args.manifest:
        parser.error(f"--{args.mode} requires --manifest PATH")
    if args.mode == "capture" and (not args.plan or not args.manifest_output):
        parser.error("--capture requires --plan PATH and --manifest-output PATH")
    if args.mode != "capture" and args.manifest_output:
        parser.error("--manifest-output is only accepted with --capture")
    if args.mode in {"apply", "rollback"} and args.plan:
        parser.error("--plan is only accepted with preview or --capture")
    if args.mode in {"preview", "capture"} and args.journal_output:
        parser.error("--journal-output is only accepted with --apply or --rollback")
    return args


def run_cli(
    argv: list[str] | None = None,
    *,
    client_factory: Callable[..., Any] | None = None,
    project_ref_getter: Callable[[], str] = runtime_project_ref,
    repo_sha_verifier: Callable[[str], bool] = verify_repo_sha_on_origin_main,
) -> dict[str, Any]:
    args = parse_args(argv)
    factory = client_factory or get_supabase
    read_only = args.mode in {"preview", "capture"}
    sb = factory(read_only=read_only)
    if read_only and not isinstance(sb, ReadOnlyProxy):
        sb = ReadOnlyProxy(sb)
    if args.mode == "preview" and not args.plan:
        return {
            "mode": "preview",
            "status": "no_plan",
            "read_only": True,
            "queries": 0,
            "mutations": 0,
        }
    project_ref = project_ref_getter()
    if args.mode in {"preview", "capture"}:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        if args.mode == "preview":
            manifest = preview_manifest(
                sb,
                plan,
                project_ref=project_ref,
                repo_sha_verifier=repo_sha_verifier,
            )
            return {
                "mode": "preview",
                "status": "validated",
                "manifest_sha256": manifest["manifest_sha256"],
                "actions": len(manifest["actions"]),
                "conflicts": len(manifest["conflicts"]),
                "already_applied": len(manifest["already_applied"]),
                "mutations": 0,
            }
        output, manifest = capture_manifest(
            sb,
            plan,
            args.manifest_output,
            project_ref=project_ref,
            repo_sha_verifier=repo_sha_verifier,
        )
        return {
            "mode": "capture",
            "status": "captured",
            "manifest": str(output),
            "manifest_sha256": manifest["manifest_sha256"],
            "actions": len(manifest["actions"]),
            "mutations": 0,
        }
    manifest = load_manifest(args.manifest)
    if args.mode == "apply":
        return apply_manifest(
            sb,
            manifest,
            project_ref=project_ref,
            journal_path=args.journal_output,
            repo_sha_verifier=repo_sha_verifier,
        )
    return rollback_manifest(
        sb,
        manifest,
        project_ref=project_ref,
        journal_path=args.journal_output,
        repo_sha_verifier=repo_sha_verifier,
    )


def main() -> None:
    print(json.dumps(run_cli(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
