"""Digest-bound one-off for reviewed non-Japan scope events (japan-scope-gate Phase 6b).

Every mode except --apply is read-only. --apply needs the approved digest, a
matching script and migration, a passing live validate and a typed confirmation
on a terminal; it then makes one call to public.apply_scope_cleanup (migration
103), which deactivates the whole set in a single database transaction.

  --snapshot          capture a v2 manifest; nothing is written unless the live
                      RPC validate passes
  --validate          re-check an existing manifest against live data
  --approval-package  print the approval package for a manifest (offline)
  --rollback-sql      write the CAS-protected rollback SQL (offline)
  --apply             deactivate the set (the only mode that writes)
  --readback          read-only check of the result after --apply
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Callable, Sequence
from uuid import UUID


SCHEMA_VERSION = "non-japan-scope-deactivation.v2"
RPC_SCHEMA_VERSION = 2
RPC_NAME = "apply_scope_cleanup"
PROJECT_REF = "cjtndektjjpvvjofdvzr"
TARGET_COUNT = 22
PAGE_SIZE = 500
DEACTIVATED_BY_PASS = "admin_manual"
EVENT_URL = "https://tokyotaiwanradar.com/ja/events/{event_id}"
MIGRATION_RELATIVE = "supabase/migrations/103_scope_cleanup_rpc.sql"
# Order matters only for readability; the RPC compares every one of these.
BEFORE_FIELDS = (
    "source_name",
    "raw_title",
    "location_address",
    "location_prefectures",
    "annotation_status",
    "parent_event_id",
    "is_active",
    "deactivated_at",
    "deactivated_reason",
    "deactivated_by_pass",
    "updated_at",
    "raw_description_sha256",
)
ROW_QUERY_FIELDS = (
    "id",
    "source_name",
    "raw_title",
    "raw_description",
    "location_address",
    "location_prefectures",
    "annotation_status",
    "parent_event_id",
    "is_active",
    "deactivated_at",
    "deactivated_reason",
    "deactivated_by_pass",
    "updated_at",
)
RELATION_QUERY_FIELDS = ("id", "parent_event_id", "is_active")
REFERENCE_TABLES = (
    ("pending_reports", "event_reports"),
    ("saved_events", "saved_events"),
    ("announcement_events", "announcement_events"),
)




@dataclass(frozen=True)
class EvidenceSpec:
    field: str
    contains: str


@dataclass(frozen=True)
class TargetSpec:
    prefix: str
    category: str
    reason: str
    evidence: tuple[EvidenceSpec, ...]


TARGET_SPECS = (
    TargetSpec(
        "3d74504d",
        "A1_japan_brand_ip_taiwan_b2c",
        "Taipei consumer exhibition charging NTD admission",
        (EvidenceSpec("raw_title", "炎上展"), EvidenceSpec("location_address", "台北市")),
    ),
    TargetSpec(
        "13a274f8",
        "A1_japan_brand_ip_taiwan_b2c",
        "Taipei IP merchandise pop-up and ticketed fan stage",
        (
            EvidenceSpec("raw_title", "漫画博覧会"),
            EvidenceSpec("raw_description", "台湾のアニメ・漫画・ゲームファン"),
        ),
    ),
    TargetSpec(
        "5f3866d0",
        "A1_japan_brand_ip_taiwan_b2c",
        "Taipei IP merchandise pop-up for local shoppers",
        (
            EvidenceSpec("raw_title", "POPUP STORE in Asia"),
            EvidenceSpec("raw_description", "オリジナルグッズの販売"),
        ),
    ),
    TargetSpec(
        "2af3196f",
        "A1_japan_brand_ip_taiwan_b2c",
        "Taipei IP merchandise pop-up for Taiwan fans",
        (
            EvidenceSpec("raw_title", "台北POPUP STORE"),
            EvidenceSpec("raw_description", "台湾のファン"),
        ),
    ),
    TargetSpec(
        "e74020ee",
        "A1_japan_brand_ip_taiwan_b2c",
        "Taiwan baseball collaboration and merchandise promotion",
        (
            EvidenceSpec("raw_title", "NIJISANJI野球日"),
            EvidenceSpec("raw_description", "オリジナルグッズ"),
        ),
    ),
    TargetSpec(
        "1b16388c",
        "A1_japan_brand_ip_taiwan_b2c",
        "Taipei tourism promotion aimed at Taiwan families",
        (
            EvidenceSpec("raw_title", "沖縄魅力祭り"),
            EvidenceSpec("raw_description", "台湾現地の皆様"),
        ),
    ),
    TargetSpec(
        "c97ed4eb",
        "A1_japan_brand_ip_taiwan_b2c",
        "Taipei character exhibition with local merchandise",
        (
            EvidenceSpec("raw_title", "ちびまる子ちゃん"),
            EvidenceSpec("raw_description", "台湾台北市松山文創園区"),
        ),
    ),
    TargetSpec(
        "a8b8603e",
        "A1_japan_brand_ip_taiwan_b2c",
        "Taiwan-market retail opening covered by a radio program",
        (
            EvidenceSpec("raw_title", "台湾人に人気の日本の雑貨チェーン"),
            EvidenceSpec("raw_description", "台湾市場進出"),
        ),
    ),
    TargetSpec(
        "318c760a",
        "A2_taiwan_trade_show_japan_pavilion_b2b",
        "Japan pavilion selling regional products at a Taipei food expo",
        (EvidenceSpec("raw_title", "台湾美食展"), EvidenceSpec("raw_description", "日本美食館")),
    ),
    TargetSpec(
        "29e24167",
        "A2_taiwan_trade_show_japan_pavilion_b2b",
        "Japan pavilion promoting municipalities and companies at a Taipei trade show",
        (
            EvidenceSpec("raw_title", "国際インテリアデザイン展示会"),
            EvidenceSpec("raw_description", "海外プロモーション"),
        ),
    ),
    TargetSpec(
        "ac50c469",
        "A3_taiwan_local_event_news",
        "retrospective report on an MSI anniversary exhibition in Taipei",
        (
            EvidenceSpec("raw_title", "MSI"),
            EvidenceSpec("raw_description", "40周年記念展示会"),
        ),
    ),
    TargetSpec(
        "2815aad9",
        "A3_taiwan_local_event_news",
        "Taipei research symposium lecture reported as Taiwan local news",
        (EvidenceSpec("raw_title", "中央研究院で講演"), EvidenceSpec("location_address", "台北市")),
    ),
    TargetSpec(
        "50144293",
        "A3_taiwan_local_event_news",
        "retrospective report on a Taiwan conservation symposium for local attendees",
        (
            EvidenceSpec("raw_title", "世界カワウソの日"),
            EvidenceSpec("raw_description", "台湾現地の方々に向けて講演"),
        ),
    ),
    TargetSpec(
        "9e1c9b0b",
        "A3_taiwan_local_event_news",
        "local music and market festival held in Pingtung, Taiwan",
        (EvidenceSpec("raw_title", "南國國際生活節"), EvidenceSpec("location_address", "屏東縣")),
    ),
    TargetSpec(
        "3f693869",
        "A4_japan_band_overseas_performance",
        "Japan band's release tour announcement limited to Taipei and Hong Kong",
        (
            EvidenceSpec("raw_title", "リリースツアー台北・香港公演"),
            EvidenceSpec("raw_description", "海外公演は9月16日（水）香港"),
        ),
    ),
    TargetSpec(
        "7c6c1e7f",
        "A4_japan_band_overseas_performance",
        "Japan band's Taipei concert",
        (EvidenceSpec("raw_title", "台北公演"), EvidenceSpec("raw_description", "THE WALL LIVE HOUSE")),
    ),
    TargetSpec(
        "fe47a25c",
        "A4_japan_band_overseas_performance",
        "Japan band's Taipei tour leg",
        (EvidenceSpec("raw_title", "台北公演"), EvidenceSpec("raw_description", "台北・香港公演")),
    ),
    TargetSpec(
        "a62ce9e1",
        "A4_japan_band_overseas_performance",
        "Japan band's Hong Kong concert",
        (EvidenceSpec("raw_title", "香港公演"), EvidenceSpec("raw_description", "MOM Livehouse")),
    ),
    TargetSpec(
        "47262b02",
        "A4_japan_band_overseas_performance",
        "Japan band's Hong Kong tour leg",
        (EvidenceSpec("raw_title", "香港公演"), EvidenceSpec("location_address", "香港")),
    ),
    TargetSpec(
        "256e9571",
        "A5_report_or_non_event",
        "retrospective award announcement, not a current participable event",
        (
            EvidenceSpec("raw_title", "最優秀チームワーク賞を獲得"),
            EvidenceSpec("raw_description", "活動の舞台"),
        ),
    ),
    TargetSpec(
        "dc03563f",
        "A5_report_or_non_event",
        "retrospective university report on a completed invited lecture",
        (
            EvidenceSpec("raw_title", "招待講演を行いました"),
            EvidenceSpec("raw_description", "2026年7月14日～16日"),
        ),
    ),
    TargetSpec(
        "f925a943",
        "A5_report_or_non_event",
        "news report about a planned ministerial trip to an APEC meeting in Shanghai",
        (EvidenceSpec("raw_title", "訪中調整"), EvidenceSpec("raw_description", "上海で開かれるAPEC")),
    ),
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def manifest_digest(manifest: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_digest"}
    return hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()


def bind_manifest_digest(payload: dict[str, Any]) -> dict[str, Any]:
    unsigned = {key: value for key, value in payload.items() if key != "manifest_digest"}
    return {**unsigned, "manifest_digest": manifest_digest(unsigned)}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def script_path() -> Path:
    return Path(__file__).resolve()


def migration_path() -> Path:
    return repo_root() / MIGRATION_RELATIVE


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_script_sha256() -> str:
    return file_sha256(script_path())


def current_migration_sha256() -> str:
    return file_sha256(migration_path())


def current_git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def assert_provenance_clean() -> None:
    """The script and the migration must be committed exactly as they will be applied."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", str(script_path()), str(migration_path())],
        cwd=repo_root(),
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise RuntimeError("script or migration has uncommitted changes: " + result.stdout.strip())


def assert_project_ref(supabase_url: str | None) -> None:
    host = re.sub(r"^https?://", "", supabase_url or "").split("/")[0]
    if host != f"{PROJECT_REF}.supabase.co":
        raise RuntimeError(f"SUPABASE_URL does not point at project {PROJECT_REF}")


def execute_rows(query: Any) -> list[dict[str, Any]]:
    return query.execute().data or []


def fetch_all_event_rows(sb: Any, fields: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    columns = ",".join(fields)
    while True:
        page = execute_rows(
            sb.table("events")
            .select(columns)
            .order("id")
            .range(offset, offset + PAGE_SIZE - 1)
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def resolve_target_rows(
    rows: list[dict[str, Any]], specs: Sequence[TargetSpec] = TARGET_SPECS
) -> list[tuple[TargetSpec, dict[str, Any]]]:
    resolved: list[tuple[TargetSpec, dict[str, Any]]] = []
    problems: list[str] = []
    seen_ids: set[str] = set()
    for spec in specs:
        matches = [row for row in rows if str(row.get("id") or "").startswith(spec.prefix)]
        if len(matches) != 1:
            ids = [str(row.get("id")) for row in matches]
            problems.append(f"prefix={spec.prefix} match_count={len(matches)} ids={ids}")
            continue
        event_id = str(matches[0].get("id") or "")
        try:
            canonical_id = str(UUID(event_id))
        except ValueError:
            problems.append(f"prefix={spec.prefix} invalid_full_uuid={event_id!r}")
            continue
        if canonical_id in seen_ids:
            problems.append(f"duplicate_full_uuid={canonical_id} prefix={spec.prefix}")
            continue
        seen_ids.add(canonical_id)
        resolved.append((spec, matches[0]))
    if problems:
        raise RuntimeError("target resolution failed: " + "; ".join(problems))
    if len(resolved) != TARGET_COUNT or len(seen_ids) != TARGET_COUNT:
        raise RuntimeError(
            f"target resolution count mismatch: resolved={len(resolved)} unique={len(seen_ids)} expected={TARGET_COUNT}"
        )
    return resolved


def evidence_excerpt(value: str, needle: str, radius: int = 100) -> str:
    index = value.find(needle)
    start = max(0, index - radius)
    end = min(len(value), index + len(needle) + radius)
    return " ".join(value[start:end].split())


def validate_evidence(row: dict[str, Any], spec: TargetSpec) -> list[dict[str, str]]:
    captured: list[dict[str, str]] = []
    for evidence in spec.evidence:
        value = row.get(evidence.field)
        if not isinstance(value, str) or evidence.contains not in value:
            raise RuntimeError(
                f"evidence contradiction for {spec.prefix}: field={evidence.field} "
                f"missing={evidence.contains!r}"
            )
        captured.append(
            {
                "field": evidence.field,
                "expected_substring": evidence.contains,
                "observed_excerpt": evidence_excerpt(value, evidence.contains),
            }
        )
    return captured


def raw_description_sha256(value: str | None) -> str | None:
    return None if value is None else hashlib.sha256(value.encode("utf-8")).hexdigest()


def before_image(row: dict[str, Any]) -> dict[str, Any]:
    image = {
        field: row.get(field)
        for field in BEFORE_FIELDS
        if field != "raw_description_sha256"
    }
    image["raw_description_sha256"] = raw_description_sha256(row.get("raw_description"))
    return {field: image[field] for field in BEFORE_FIELDS}


def reason_for(category: str, digest: str) -> str:
    return f"out_of_scope: {category} - scope cleanup {digest[:12]}"


def closed_family_problems(
    target_rows: list[dict[str, Any]], external_children: list[dict[str, Any]]
) -> list[str]:
    """Targets may only have parents inside the set; outside children must be inactive."""
    target_ids = {row["id"] for row in target_rows}
    problems = [
        f"target {row['id']} has parent {row['parent_event_id']} outside the set"
        for row in target_rows
        if row.get("parent_event_id") is not None and row["parent_event_id"] not in target_ids
    ]
    problems += [
        f"active child {row['id']} points to target {row['parent_event_id']}"
        for row in external_children
        if row.get("is_active") is True
    ]
    problems += [
        f"target {row['id']} is not active (is_active={row.get('is_active')!r})"
        for row in target_rows
        if row.get("is_active") is not True
    ]
    return problems


def fetch_rows_for_ids(sb: Any, ids: Sequence[str]) -> dict[str, dict[str, Any]]:
    rows = execute_rows(
        sb.table("events").select(",".join(ROW_QUERY_FIELDS)).in_("id", sorted(ids))
    )
    return {str(row["id"]): row for row in rows}


def fetch_external_children(sb: Any, target_ids: set[str]) -> list[dict[str, Any]]:
    rows = execute_rows(
        sb.table("events")
        .select(",".join(RELATION_QUERY_FIELDS))
        .in_("parent_event_id", sorted(target_ids))
    )
    return sorted(
        (row for row in rows if row.get("id") not in target_ids), key=lambda row: str(row["id"])
    )


def fetch_reference_counts(sb: Any, target_ids: Sequence[str]) -> dict[str, dict[str, int]]:
    counts = {event_id: {name: 0 for name, _table in REFERENCE_TABLES} for event_id in target_ids}
    for name, table in REFERENCE_TABLES:
        query = sb.table(table).select("event_id").in_("event_id", sorted(target_ids))
        if table == "event_reports":
            query = query.eq("status", "pending")
        for row in execute_rows(query):
            counts[str(row["event_id"])][name] += 1
    return counts


def build_manifest(
    resolved: list[tuple[TargetSpec, dict[str, Any]]],
    external_children: list[dict[str, Any]],
    reference_counts: dict[str, dict[str, int]],
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    target_rows = [row for _spec, row in resolved]
    problems = closed_family_problems(target_rows, external_children)
    if problems:
        raise RuntimeError("snapshot blocked; zero writes performed: " + "; ".join(problems))
    captured_evidence = {spec.prefix: validate_evidence(row, spec) for spec, row in resolved}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": created_at_utc or utc_now(),
        "project_ref": PROJECT_REF,
        "operator": {
            "git_head": current_git_head(),
            "script_sha256": current_script_sha256(),
            "migration_sha256": current_migration_sha256(),
        },
        "target_count": TARGET_COUNT,
        "targets": [
            {
                "prefix": spec.prefix,
                "category": spec.category,
                "id": row["id"],
                "before": before_image(row),
                "reason": spec.reason,
                "evidence": captured_evidence[spec.prefix],
            }
            for spec, row in resolved
        ],
        "external_children": [
            {"id": row["id"], "parent_event_id": row["parent_event_id"]} for row in external_children
        ],
        "reference_counts": reference_counts,
        "write_template": {
            "is_active": False,
            "deactivated_by_pass": DEACTIVATED_BY_PASS,
            "deactivated_reason": "out_of_scope: <category> - scope cleanup <first 12 of manifest_digest>",
        },
        "contract": {
            "digest": "SHA-256 of canonical UTF-8 JSON excluding top-level manifest_digest; sort_keys=true; separators=[',', ':']",
            "before_fields": list(BEFORE_FIELDS),
            "updated_at": "strict_equality_in_rpc",
            "apply_requires_exact_digest": True,
            "apply_requires_typed_confirmation_on_tty": True,
            "apply_uses_manifest_full_uuids_only": True,
        },
    }
    return bind_manifest_digest(payload)


def rpc_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RPC_SCHEMA_VERSION,
        "manifest_digest": manifest["manifest_digest"],
        "target_count": manifest["target_count"],
        "targets": [
            {"id": target["id"], "category": target["category"], "before": target["before"]}
            for target in manifest["targets"]
        ],
        "external_children": manifest["external_children"],
    }


def format_rpc_error(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    message = getattr(exc, "message", None) or str(exc)
    details = getattr(exc, "details", None)
    text = f"RPC error code={code} message={message}"
    if details:
        text += f" details={details}"
    return text


def call_rpc(sb: Any, mode: str, manifest: dict[str, Any]) -> dict[str, Any]:
    try:
        response = sb.rpc(RPC_NAME, {"p_mode": mode, "p_manifest": rpc_payload(manifest)}).execute()
    except Exception as exc:  # noqa: BLE001 - the transport raises many types
        raise RuntimeError(format_rpc_error(exc)) from exc
    data = response.data
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected RPC response: {data!r}")
    return data


def validate_live(sb: Any, manifest: dict[str, Any]) -> dict[str, Any]:
    result = call_rpc(sb, "validate", manifest)
    if result.get("ok") is not True:
        raise RuntimeError(
            "live validate failed; zero writes performed: "
            + json.dumps(result.get("problems"), ensure_ascii=False)
        )
    return result


def build_snapshot(sb: Any, *, created_at_utc: str | None = None) -> dict[str, Any]:
    id_rows = fetch_all_event_rows(sb, ("id",))
    ids = [str(row["id"]) for _spec, row in resolve_target_rows(id_rows)]
    rows = fetch_rows_for_ids(sb, ids)
    resolved = resolve_target_rows(list(rows.values()))
    target_ids = {str(row["id"]) for _spec, row in resolved}
    manifest = build_manifest(
        resolved,
        fetch_external_children(sb, target_ids),
        fetch_reference_counts(sb, sorted(target_ids)),
        created_at_utc=created_at_utc,
    )
    validate_live(sb, manifest)
    return manifest


def write_immutable(path: Path, text: str) -> None:
    if path.exists():
        raise RuntimeError(f"output path already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(0o400)
        os.link(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    directory_descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    write_immutable(path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("manifest must be a JSON object")
    return value


def verify_manifest_digest(manifest: dict[str, Any], expected_digest: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise RuntimeError("--expect-digest must be a lowercase SHA-256 hex digest")
    embedded = manifest.get("manifest_digest")
    computed = manifest_digest(manifest)
    if not isinstance(embedded, str) or not hmac.compare_digest(computed, embedded):
        raise RuntimeError("manifest embedded digest mismatch")
    if not hmac.compare_digest(computed, expected_digest):
        raise RuntimeError("manifest expected digest mismatch")
    return computed


def _uuid_or_raise(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"{label} must be a UUID string")
    try:
        canonical = str(UUID(value))
    except ValueError as exc:
        raise RuntimeError(f"{label} is not a UUID: {value!r}") from exc
    if canonical != value:
        raise RuntimeError(f"{label} is not canonical: {value!r}")
    return value


def _check_before(before: Any, event_id: str, ids: set[str]) -> None:
    if not isinstance(before, dict) or set(before) != set(BEFORE_FIELDS):
        raise RuntimeError(f"manifest before-image fields mismatch for {event_id}")
    if not isinstance(before["source_name"], str) or not before["source_name"]:
        raise RuntimeError(f"manifest before-image source_name invalid for {event_id}")
    for field in (
        "raw_title",
        "location_address",
        "annotation_status",
        "deactivated_at",
        "deactivated_reason",
        "deactivated_by_pass",
        "updated_at",
    ):
        if before[field] is not None and not isinstance(before[field], str):
            raise RuntimeError(f"manifest before-image {field} invalid for {event_id}")
    if not isinstance(before["updated_at"], str):
        raise RuntimeError(f"manifest before-image updated_at missing for {event_id}")
    prefectures = before["location_prefectures"]
    if prefectures is not None and (
        not isinstance(prefectures, list) or any(not isinstance(item, str) for item in prefectures)
    ):
        raise RuntimeError(f"manifest before-image location_prefectures invalid for {event_id}")
    if before["is_active"] is not True:
        raise RuntimeError(f"manifest before-image is_active must be true for {event_id}")
    if any(before[field] is not None for field in ("deactivated_at", "deactivated_reason", "deactivated_by_pass")):
        raise RuntimeError(f"manifest before-image must not be deactivated for {event_id}")
    digest = before["raw_description_sha256"]
    if digest is not None and not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
        raise RuntimeError(f"manifest before-image raw_description_sha256 invalid for {event_id}")
    parent = before["parent_event_id"]
    if parent is not None:
        _uuid_or_raise(parent, f"before-image parent_event_id of {event_id}")
        if parent not in ids:
            raise RuntimeError(f"manifest target {event_id} has a parent outside the set")


def validate_manifest_contract(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    expected_keys = {
        "schema_version", "created_at_utc", "project_ref", "operator", "target_count", "targets",
        "external_children", "reference_counts", "write_template", "contract", "manifest_digest",
    }
    if set(manifest) != expected_keys:
        raise RuntimeError(
            f"manifest keys mismatch: missing={sorted(expected_keys - set(manifest))} "
            f"extra={sorted(set(manifest) - expected_keys)}"
        )
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise RuntimeError("unsupported manifest schema_version")
    if manifest["project_ref"] != PROJECT_REF:
        raise RuntimeError("manifest project_ref mismatch")
    if type(manifest["target_count"]) is not int or manifest["target_count"] != TARGET_COUNT:
        raise RuntimeError(f"manifest target_count must equal {TARGET_COUNT}")
    targets = manifest["targets"]
    if not isinstance(targets, list) or len(targets) != TARGET_COUNT:
        raise RuntimeError(f"manifest targets must contain exactly {TARGET_COUNT} rows")
    target_fields = {"prefix", "category", "id", "before", "reason", "evidence"}
    evidence_fields = {"field", "expected_substring", "observed_excerpt"}
    ids: list[str] = []
    for target, spec in zip(targets, TARGET_SPECS, strict=True):
        if not isinstance(target, dict) or set(target) != target_fields:
            raise RuntimeError(f"manifest target fields mismatch for {spec.prefix}")
        if target["prefix"] != spec.prefix or target["category"] != spec.category or target["reason"] != spec.reason:
            raise RuntimeError(f"manifest target does not match the reviewed spec for {spec.prefix}")
        event_id = _uuid_or_raise(target["id"], f"target id for {spec.prefix}")
        if not event_id.startswith(spec.prefix):
            raise RuntimeError(f"manifest target UUID/prefix mismatch: {event_id}")
        ids.append(event_id)
        evidence_items = target["evidence"]
        if not isinstance(evidence_items, list) or len(evidence_items) != len(spec.evidence):
            raise RuntimeError(f"manifest evidence mismatch for {event_id}")
        for item, expected in zip(evidence_items, spec.evidence, strict=True):
            if not isinstance(item, dict) or set(item) != evidence_fields:
                raise RuntimeError(f"manifest evidence item malformed for {event_id}")
            if item["field"] != expected.field or item["expected_substring"] != expected.contains:
                raise RuntimeError(f"manifest evidence does not match the reviewed spec for {event_id}")
            excerpt = item["observed_excerpt"]
            if not isinstance(excerpt, str) or expected.contains not in excerpt:
                raise RuntimeError(f"manifest evidence observed_excerpt invalid for {event_id}")
    if len(set(ids)) != TARGET_COUNT:
        raise RuntimeError("manifest contains duplicate full UUIDs")
    id_set = set(ids)
    for target in targets:
        _check_before(target["before"], target["id"], id_set)
    children = manifest["external_children"]
    if not isinstance(children, list):
        raise RuntimeError("manifest external_children must be a list")
    for child in children:
        if not isinstance(child, dict) or set(child) != {"id", "parent_event_id"}:
            raise RuntimeError("manifest external_children entry malformed")
        _uuid_or_raise(child["id"], "external child id")
        if _uuid_or_raise(child["parent_event_id"], "external child parent") not in id_set:
            raise RuntimeError("manifest external child parent is not a target")
        if child["id"] in id_set:
            raise RuntimeError("manifest external child is also a target")
    counts = manifest["reference_counts"]
    if not isinstance(counts, dict) or set(counts) != id_set:
        raise RuntimeError("manifest reference_counts must cover exactly the targets")
    for event_id, entry in counts.items():
        if not isinstance(entry, dict) or set(entry) != {name for name, _table in REFERENCE_TABLES}:
            raise RuntimeError(f"manifest reference_counts malformed for {event_id}")
        if any(type(value) is not int or value < 0 for value in entry.values()):
            raise RuntimeError(f"manifest reference_counts invalid for {event_id}")
    operator = manifest["operator"]
    if not isinstance(operator, dict) or set(operator) != {"git_head", "script_sha256", "migration_sha256"}:
        raise RuntimeError("manifest operator provenance malformed")
    if not isinstance(operator["git_head"], str) or not operator["git_head"]:
        raise RuntimeError("manifest operator git_head missing")
    for key, current in (
        ("script_sha256", current_script_sha256),
        ("migration_sha256", current_migration_sha256),
    ):
        if not re.fullmatch(r"[0-9a-f]{64}", str(operator[key])):
            raise RuntimeError(f"manifest operator {key} invalid")
        if not hmac.compare_digest(operator[key], current()):
            raise RuntimeError(f"current {key.removesuffix('_sha256')} does not match manifest provenance")
    return targets


def verified_manifest(manifest: dict[str, Any], expected_digest: str) -> dict[str, Any]:
    verify_manifest_digest(manifest, expected_digest)
    validate_manifest_contract(manifest)
    return manifest


def confirm_on_terminal(manifest: dict[str, Any]) -> bool:
    digest12 = manifest["manifest_digest"][:12]
    print(f"About to deactivate {manifest['target_count']} events in project {PROJECT_REF}.")
    print(f"manifest_digest={manifest['manifest_digest']}")
    answer = input(f"Type the first 12 characters of the digest ({digest12}) to apply: ")
    return answer.strip() == digest12


def apply_manifest(
    sb: Any,
    manifest: dict[str, Any],
    *,
    manifest_path: Path,
    expected_digest: str,
    confirm: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    verified_manifest(manifest, expected_digest)
    validate_live(sb, manifest)
    if not confirm(manifest):
        raise RuntimeError("apply not confirmed; zero writes performed")
    result = call_rpc(sb, "apply", manifest)
    if result.get("status") not in ("applied", "noop"):
        raise RuntimeError(f"unexpected apply status: {result.get('status')!r}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    journal_path = manifest_path.with_name(f"{manifest_path.name}.apply-{stamp}.json")
    write_immutable(
        journal_path,
        json.dumps(
            {"manifest_digest": manifest["manifest_digest"], "recorded_at_utc": utc_now(), "result": result},
            ensure_ascii=False, indent=2, sort_keys=True,
        ) + "\n",
    )
    return {"status": result["status"], "applied_count": result.get("applied_count", 0),
            "journal_path": journal_path, "result": result}


def readback(sb: Any, manifest: dict[str, Any]) -> list[str]:
    """Read-only: every target is deactivated with this manifest's marker; no active child remains."""
    ids = [target["id"] for target in manifest["targets"]]
    rows = fetch_rows_for_ids(sb, ids)
    problems: list[str] = []
    stamps = set()
    for target in manifest["targets"]:
        row = rows.get(target["id"])
        if row is None:
            problems.append(f"{target['id']} is missing")
            continue
        expected = reason_for(target["category"], manifest["manifest_digest"])
        if row.get("is_active") is not False:
            problems.append(f"{target['id']} is still active")
        if row.get("deactivated_reason") != expected:
            problems.append(f"{target['id']} deactivated_reason={row.get('deactivated_reason')!r}")
        if row.get("deactivated_by_pass") != DEACTIVATED_BY_PASS:
            problems.append(f"{target['id']} deactivated_by_pass={row.get('deactivated_by_pass')!r}")
        if row.get("parent_event_id") != target["before"]["parent_event_id"]:
            problems.append(f"{target['id']} parent_event_id changed")
        stamps.add(row.get("deactivated_at"))
    if len(stamps) > 1:
        problems.append(f"deactivated_at differs across targets: {sorted(map(str, stamps))}")
    children = execute_rows(
        sb.table("events")
        .select(",".join(RELATION_QUERY_FIELDS))
        .in_("parent_event_id", sorted(ids))
        .eq("is_active", True)
    )
    problems += [f"active child {row['id']} points to {row['parent_event_id']}" for row in children]
    return problems


def sql_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return "'" + str(value).replace("'", "''") + "'"


def render_rollback_sql(manifest: dict[str, Any]) -> str:
    """CAS-protected rollback for the Dashboard; restores the four fields the RPC writes.

    updated_at cannot be restored (a trigger refreshes it). Rows whose marker was
    changed after the apply are not matched, and the transaction aborts.
    """
    digest = manifest["manifest_digest"]
    rows = []
    for target in manifest["targets"]:
        before = target["before"]
        rows.append(
            "    ({id}::uuid, {active}, {at}::timestamptz, {reason}, {by_pass}, {expect})".format(
                id=sql_literal(target["id"]),
                active=sql_literal(before["is_active"]),
                at=sql_literal(before["deactivated_at"]),
                reason=sql_literal(before["deactivated_reason"]),
                by_pass=sql_literal(before["deactivated_by_pass"]),
                expect=sql_literal(reason_for(target["category"], digest)),
            )
        )
    count = len(manifest["targets"])
    values = ",\n".join(rows)
    return f"""-- Rollback of japan-scope-gate cleanup, manifest_digest {digest}
-- Run in Supabase Dashboard -> SQL Editor as postgres. Aborts (changes nothing) unless
-- all {count} rows still carry this manifest's marker and one shared deactivated_at.
-- updated_at is not restored; the events_updated_at trigger refreshes it.
begin;
lock table public.events in share row exclusive mode;
do $$
declare n bigint;
begin
  if (select count(distinct e.deactivated_at) from public.events e
       where e.id in (select b.id from (values
{values}
       ) as b(id, is_active, deactivated_at, deactivated_reason, deactivated_by_pass, expect_reason))) <> 1 then
    raise exception 'rollback aborted: deactivated_at is not a single shared value';
  end if;
  update public.events e
     set is_active = b.is_active,
         deactivated_at = b.deactivated_at,
         deactivated_reason = b.deactivated_reason,
         deactivated_by_pass = b.deactivated_by_pass
    from (values
{values}
    ) as b(id, is_active, deactivated_at, deactivated_reason, deactivated_by_pass, expect_reason)
   where e.id = b.id
     and e.is_active is false
     and e.deactivated_by_pass = {sql_literal(DEACTIVATED_BY_PASS)}
     and e.deactivated_reason = b.expect_reason;
  get diagnostics n = row_count;
  if n <> {count} then
    raise exception 'rollback aborted: matched % rows, expected {count}', n;
  end if;
end $$;
commit;
"""


def render_approval_package(manifest: dict[str, Any]) -> str:
    digest = manifest["manifest_digest"]
    lines = [
        "# japan-scope-gate cleanup — approval package",
        "",
        f"- manifest_digest: `{digest}`",
        f"- captured: {manifest['created_at_utc']}  project: `{manifest['project_ref']}`",
        f"- git_head: `{manifest['operator']['git_head']}`",
        f"- script_sha256: `{manifest['operator']['script_sha256']}`",
        f"- migration_sha256: `{manifest['operator']['migration_sha256']}`",
        f"- rollback SQL sha256: `{hashlib.sha256(render_rollback_sql(manifest).encode('utf-8')).hexdigest()}`",
        "",
        f"## {manifest['target_count']} events that would be deactivated",
        "",
        "| # | category | event | source | pending reports | saved | announcements |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, target in enumerate(manifest["targets"], start=1):
        counts = manifest["reference_counts"][target["id"]]
        title = (target["before"]["raw_title"] or "").replace("|", "/")[:48]
        lines.append(
            f"| {index} | {target['category']} | [{title}]({EVENT_URL.format(event_id=target['id'])}) "
            f"`{target['id']}` | {target['before']['source_name']} | {counts['pending_reports']} | "
            f"{counts['saved_events']} | {counts['announcement_events']} |"
        )
    families: dict[str, list[str]] = {}
    for target in manifest["targets"]:
        parent = target["before"]["parent_event_id"]
        if parent is not None:
            families.setdefault(parent, []).append(target["id"])
    lines += ["", "## Families (parent -> children, all inside the set)", ""]
    lines += [f"- `{parent}` -> {', '.join(f'`{c}`' for c in children)}" for parent, children in sorted(families.items())] or ["- none"]
    lines += ["", "## Children outside the set (already inactive)", ""]
    lines += [f"- `{c['id']}` (parent `{c['parent_event_id']}`)" for c in manifest["external_children"]] or ["- none"]
    lines += ["", "## Evidence", ""]
    for target in manifest["targets"]:
        lines.append(f"- `{target['id']}` {target['reason']}")
        lines += [f"    - {e['field']} contains `{e['expected_substring']}`: ...{e['observed_excerpt']}..." for e in target["evidence"]]
    lines += [
        "",
        "## What an approval of this digest covers",
        "",
        f"- one call to `public.apply_scope_cleanup('apply', ...)` deactivating exactly the {manifest['target_count']} events above "
        f"(`is_active=false`, `deactivated_by_pass={DEACTIVATED_BY_PASS}`, reason `out_of_scope: <category> - scope cleanup {digest[:12]}`)",
        "- `parent_event_id` is not touched; the four children go with their parent",
        "- writer pause/drain/resume and the maintenance lock are separate steps listed in the runbook and must be named in the approval",
    ]
    return "\n".join(lines) + "\n"


def get_supabase() -> Any:
    from annotator import _get_supabase

    return _get_supabase()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Digest-bound cleanup for reviewed non-Japan scope events (only --apply writes)"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    for flag, text in (
        ("--snapshot", "Capture a v2 manifest (read-only; needs --out)"),
        ("--validate", "Re-check a manifest against live data (read-only)"),
        ("--approval-package", "Print the approval package (offline)"),
        ("--rollback-sql", "Write the rollback SQL (offline; needs --out)"),
        ("--apply", "Deactivate the set via the RPC; needs a terminal and typed confirmation"),
        ("--readback", "Read-only check after --apply"),
    ):
        mode.add_argument(flag, action="store_true", help=text)
    parser.add_argument("--out", type=Path, help="New immutable output path")
    parser.add_argument("--manifest", type=Path, help="Existing immutable manifest path")
    parser.add_argument("--expect-digest", help="Expected lowercase SHA-256 manifest digest")
    return parser


def validate_cli_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.snapshot:
        if args.out is None:
            parser.error("--snapshot requires --out")
        if args.manifest is not None or args.expect_digest is not None:
            parser.error("--snapshot accepts only --out")
        return
    if args.manifest is None or args.expect_digest is None:
        parser.error("this mode requires --manifest and --expect-digest")
    if args.rollback_sql and args.out is None:
        parser.error("--rollback-sql requires --out")
    if args.out is not None and not (args.rollback_sql or args.approval_package):
        parser.error("--out is only accepted by --snapshot, --rollback-sql and --approval-package")
    if args.apply and not sys.stdin.isatty():
        parser.error("--apply needs an interactive terminal for the typed confirmation")


def connect() -> Any:
    sb = get_supabase()
    assert_project_ref(os.environ.get("SUPABASE_URL"))
    return sb


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_cli_args(parser, args)
    try:
        if args.snapshot:
            assert_provenance_clean()
            manifest = build_snapshot(connect())
            write_manifest(args.out, manifest)
            print(f"snapshot_path={args.out}")
            print(f"target_count={manifest['target_count']}")
            print(f"manifest_digest={manifest['manifest_digest']}")
            print("read_only=true")
            return
        manifest = verified_manifest(load_manifest(args.manifest), args.expect_digest)
        if args.approval_package:
            text = render_approval_package(manifest)
            if args.out is not None:
                write_immutable(args.out, text)
                print(f"approval_package_path={args.out}")
            else:
                print(text, end="")
        elif args.rollback_sql:
            write_immutable(args.out, render_rollback_sql(manifest))
            print(f"rollback_sql_path={args.out}")
        elif args.validate:
            result = validate_live(connect(), manifest)
            print(f"validate=ok target_count={result['target_count']}")
        elif args.readback:
            problems = readback(connect(), manifest)
            for problem in problems:
                print(f"problem: {problem}")
            print(f"readback={'ok' if not problems else 'FAILED'}")
            if problems:
                parser.exit(1)
        else:
            report = apply_manifest(
                connect(),
                manifest,
                manifest_path=args.manifest,
                expected_digest=args.expect_digest,
                confirm=confirm_on_terminal,
            )
            print(f"status={report['status']}")
            print(f"applied_count={report['applied_count']}")
            print(f"journal_path={report['journal_path']}")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
