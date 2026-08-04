"""Digest-bound one-off for reviewed non-Japan scope events.

Snapshot mode is read-only. Apply mode accepts only the exact full UUIDs in an
immutable manifest and is never selected implicitly.
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
import tempfile
from typing import Any, Sequence
from uuid import UUID


SCHEMA_VERSION = "non-japan-scope-deactivation.v1"
TARGET_COUNT = 22
PAGE_SIZE = 500
DEACTIVATED_BY_PASS = "admin_manual"
STABLE_FIELDS = (
    "source_name",
    "raw_title",
    "location_address",
    "location_prefectures",
    "annotation_status",
)
BEFORE_IMAGE_FIELDS = (
    "id",
    "source_name",
    "raw_title",
    "location_address",
    "location_prefectures",
    "is_active",
    "annotation_status",
    "parent_event_id",
    "updated_at",
)
SNAPSHOT_QUERY_FIELDS = tuple(dict.fromkeys((*BEFORE_IMAGE_FIELDS, "raw_description")))
APPLY_QUERY_FIELDS = BEFORE_IMAGE_FIELDS
RELATION_QUERY_FIELDS = ("id", "parent_event_id", "is_active")


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


def script_path() -> Path:
    return Path(__file__).resolve()


def current_script_sha256() -> str:
    return hashlib.sha256(script_path().read_bytes()).hexdigest()


def current_git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=script_path().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


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


def before_image(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in BEFORE_IMAGE_FIELDS}


def inspect_relations(rows: list[dict[str, Any]], target_ids: set[str]) -> dict[str, Any]:
    target_parents = [
        {"id": row.get("id"), "parent_event_id": row.get("parent_event_id")}
        for row in rows
        if row.get("id") in target_ids and row.get("parent_event_id") is not None
    ]
    children = [
        {
            "id": row.get("id"),
            "parent_event_id": row.get("parent_event_id"),
            "is_active": row.get("is_active"),
        }
        for row in rows
        if row.get("parent_event_id") in target_ids
    ]
    return {
        "target_parents": target_parents,
        "active_children": [row for row in children if row["is_active"] is True],
        "inactive_children": [row for row in children if row["is_active"] is not True],
    }


def validate_target_state(
    resolved: list[tuple[TargetSpec, dict[str, Any]]], relations: dict[str, Any], *, stage: str
) -> list[str]:
    issues: list[str] = []
    inactive = [row["id"] for _spec, row in resolved if row.get("is_active") is not True]
    if inactive:
        issues.append(f"inactive target drift={inactive}")
    if relations["target_parents"]:
        issues.append(f"targets have parent_event_id={relations['target_parents']}")
    if relations["active_children"]:
        issues.append(f"active children point to targets={relations['active_children']}")
    if issues:
        raise RuntimeError(f"{stage} blocked; zero writes performed: " + "; ".join(issues))
    return [f"inactive_child={row['id']} parent={row['parent_event_id']}" for row in relations["inactive_children"]]


def build_manifest_from_rows(
    rows: list[dict[str, Any]], *, created_at_utc: str | None = None
) -> dict[str, Any]:
    resolved = resolve_target_rows(rows)
    captured_evidence = {
        spec.prefix: validate_evidence(row, spec) for spec, row in resolved
    }
    target_ids = {str(row["id"]) for _spec, row in resolved}
    relations = inspect_relations(rows, target_ids)
    warnings = validate_target_state(resolved, relations, stage="snapshot")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": created_at_utc or utc_now(),
        "operator": {
            "git_head": current_git_head(),
            "script_sha256": current_script_sha256(),
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
        "relations": {"inactive_children": relations["inactive_children"]},
        "warnings": warnings,
        "contract": {
            "digest": "SHA-256 of canonical UTF-8 JSON excluding top-level manifest_digest; sort_keys=true; separators=[',', ':']",
            "stable_fields": list(STABLE_FIELDS),
            "updated_at": "warning_only",
            "apply_requires_exact_digest": True,
            "apply_uses_manifest_full_uuids_only": True,
        },
    }
    return bind_manifest_digest(payload)


def build_snapshot(sb: Any, *, created_at_utc: str | None = None) -> dict[str, Any]:
    rows = fetch_all_event_rows(sb, SNAPSHOT_QUERY_FIELDS)
    return build_manifest_from_rows(rows, created_at_utc=created_at_utc)


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"output path already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
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


def validate_manifest_contract(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("unsupported manifest schema_version")
    if type(manifest.get("target_count")) is not int or manifest["target_count"] != TARGET_COUNT:
        raise RuntimeError(f"manifest target_count must equal {TARGET_COUNT}")
    targets = manifest.get("targets")
    if not isinstance(targets, list) or len(targets) != TARGET_COUNT:
        raise RuntimeError(f"manifest targets must contain exactly {TARGET_COUNT} rows")
    ids: list[str] = []
    target_fields = {"prefix", "category", "id", "before", "reason", "evidence"}
    before_fields = set(BEFORE_IMAGE_FIELDS)
    evidence_fields = {"field", "expected_substring", "observed_excerpt"}
    for target, spec in zip(targets, TARGET_SPECS, strict=True):
        if not isinstance(target, dict):
            raise RuntimeError("manifest target must be a JSON object")
        if set(target) != target_fields:
            raise RuntimeError(
                f"manifest target fields mismatch for {spec.prefix}: "
                f"missing={sorted(target_fields - set(target))} extra={sorted(set(target) - target_fields)}"
            )
        if target["prefix"] != spec.prefix:
            raise RuntimeError(f"manifest target prefix mismatch for {spec.prefix}")
        if target["category"] != spec.category:
            raise RuntimeError(f"manifest target category mismatch for {spec.prefix}")
        if target["reason"] != spec.reason:
            raise RuntimeError(f"manifest target reason mismatch for {spec.prefix}")
        event_id = target.get("id")
        if not isinstance(event_id, str):
            raise RuntimeError("manifest target id must be a full UUID string")
        try:
            canonical_id = str(UUID(event_id))
        except ValueError as exc:
            raise RuntimeError(f"invalid manifest target UUID: {event_id}") from exc
        if canonical_id != event_id or not event_id.startswith(spec.prefix):
            raise RuntimeError(f"manifest target UUID/prefix mismatch: {event_id}")
        before = target.get("before")
        if not isinstance(before, dict) or before.get("id") != event_id:
            raise RuntimeError(f"manifest before-image id mismatch: {event_id}")
        missing_fields = sorted(before_fields - set(before))
        if missing_fields:
            raise RuntimeError(f"manifest before-image missing fields for {event_id}: {missing_fields}")
        extra_fields = sorted(set(before) - before_fields)
        if extra_fields:
            raise RuntimeError(f"manifest before-image unexpected fields for {event_id}: {extra_fields}")
        if not isinstance(before["source_name"], str) or not before["source_name"]:
            raise RuntimeError(f"manifest before-image source_name invalid for {event_id}")
        for field in ("raw_title", "location_address", "annotation_status", "updated_at"):
            if before[field] is not None and not isinstance(before[field], str):
                raise RuntimeError(f"manifest before-image {field} invalid for {event_id}")
        prefectures = before["location_prefectures"]
        if prefectures is not None and (
            not isinstance(prefectures, list)
            or any(not isinstance(prefecture, str) for prefecture in prefectures)
        ):
            raise RuntimeError(f"manifest before-image location_prefectures invalid for {event_id}")
        if before["is_active"] is not True:
            raise RuntimeError(f"manifest before-image is_active must be true for {event_id}")
        parent_event_id = before["parent_event_id"]
        if parent_event_id is not None:
            if not isinstance(parent_event_id, str):
                raise RuntimeError(f"manifest before-image parent_event_id invalid for {event_id}")
            try:
                canonical_parent_id = str(UUID(parent_event_id))
            except ValueError as exc:
                raise RuntimeError(
                    f"manifest before-image parent_event_id invalid for {event_id}"
                ) from exc
            if canonical_parent_id != parent_event_id:
                raise RuntimeError(f"manifest before-image parent_event_id invalid for {event_id}")
        evidence_items = target["evidence"]
        if not isinstance(evidence_items, list) or len(evidence_items) != len(spec.evidence):
            raise RuntimeError(f"manifest evidence mismatch for {event_id}")
        for item, expected in zip(evidence_items, spec.evidence, strict=True):
            if not isinstance(item, dict) or set(item) != evidence_fields:
                raise RuntimeError(f"manifest evidence item malformed for {event_id}")
            if item["field"] != expected.field:
                raise RuntimeError(f"manifest evidence field mismatch for {event_id}")
            if item["expected_substring"] != expected.contains:
                raise RuntimeError(
                    f"manifest evidence expected_substring mismatch for {event_id}"
                )
            excerpt = item["observed_excerpt"]
            if not isinstance(excerpt, str) or not excerpt or expected.contains not in excerpt:
                raise RuntimeError(f"manifest evidence observed_excerpt invalid for {event_id}")
        ids.append(event_id)
    if len(set(ids)) != TARGET_COUNT:
        raise RuntimeError("manifest contains duplicate full UUIDs")
    operator = manifest.get("operator")
    if not isinstance(operator, dict):
        raise RuntimeError("manifest operator provenance missing")
    if not isinstance(operator.get("git_head"), str) or not operator["git_head"]:
        raise RuntimeError("manifest operator git_head missing")
    if not re.fullmatch(r"[0-9a-f]{64}", str(operator.get("script_sha256") or "")):
        raise RuntimeError("manifest operator script_sha256 invalid")
    if not hmac.compare_digest(operator["script_sha256"], current_script_sha256()):
        raise RuntimeError("current script SHA-256 does not match manifest provenance")
    return targets


def fetch_exact_manifest_rows(sb: Any, targets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    current: dict[str, dict[str, Any]] = {}
    columns = ",".join(APPLY_QUERY_FIELDS)
    problems: list[str] = []
    for target in targets:
        event_id = target["id"]
        rows = execute_rows(sb.table("events").select(columns).eq("id", event_id))
        if len(rows) != 1:
            problems.append(f"id={event_id} match_count={len(rows)}")
            continue
        current[event_id] = rows[0]
    if problems:
        raise RuntimeError("manifest exact-ID preflight failed; zero writes performed: " + "; ".join(problems))
    return current


def preflight_apply(sb: Any, targets: list[dict[str, Any]]) -> list[str]:
    current = fetch_exact_manifest_rows(sb, targets)
    issues: list[str] = []
    warnings: list[str] = []
    for target in targets:
        event_id = target["id"]
        before = target["before"]
        row = current[event_id]
        if row.get("is_active") is not True:
            issues.append(f"inactive target drift={event_id} current={row.get('is_active')!r}")
        for field in STABLE_FIELDS:
            if row.get(field) != before.get(field):
                issues.append(
                    f"stable drift={event_id} field={field} before={before.get(field)!r} current={row.get(field)!r}"
                )
        if row.get("updated_at") != before.get("updated_at"):
            warnings.append(
                f"updated_at_only_drift={event_id} before={before.get('updated_at')} current={row.get('updated_at')}"
            )
    relation_rows = fetch_all_event_rows(sb, RELATION_QUERY_FIELDS)
    target_ids = {target["id"] for target in targets}
    relations = inspect_relations(relation_rows, target_ids)
    if relations["target_parents"]:
        issues.append(f"targets have parent_event_id={relations['target_parents']}")
    if relations["active_children"]:
        issues.append(f"active children point to targets={relations['active_children']}")
    warnings.extend(
        f"inactive_child={row['id']} parent={row['parent_event_id']}"
        for row in relations["inactive_children"]
    )
    if issues:
        raise RuntimeError("apply preflight failed; zero writes performed: " + "; ".join(issues))
    return warnings


def journal_path_for(manifest_path: Path) -> Path:
    return manifest_path.with_name(manifest_path.name + ".apply-journal.jsonl")


class ApplyJournal:
    def __init__(self, path: Path):
        self.path = path
        self.handle: Any = None

    def __enter__(self) -> ApplyJournal:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.handle = os.fdopen(file_descriptor, "w", encoding="utf-8")
        return self

    def write(self, payload: dict[str, Any]) -> None:
        self.handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        self.handle.flush()
        os.fsync(self.handle.fileno())

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        if self.handle is not None:
            self.handle.flush()
            os.fsync(self.handle.fileno())
            self.handle.close()
        self.path.chmod(0o400)


def cas_deactivate(sb: Any, target: dict[str, Any], apply_timestamp: str) -> list[dict[str, Any]]:
    payload = {
        "is_active": False,
        "deactivated_reason": f"out_of_scope: {target['reason']} — not a Japan event",
        "deactivated_at": apply_timestamp,
        "deactivated_by_pass": DEACTIVATED_BY_PASS,
    }
    return execute_rows(
        sb.table("events")
        .update(payload)
        .eq("id", target["id"])
        .eq("is_active", True)
        .select("id")
    )


def apply_manifest(
    sb: Any,
    manifest: dict[str, Any],
    *,
    manifest_path: Path,
    expected_digest: str,
    apply_timestamp: str | None = None,
) -> dict[str, Any]:
    digest = verify_manifest_digest(manifest, expected_digest)
    targets = validate_manifest_contract(manifest)
    warnings = preflight_apply(sb, targets)
    journal_path = journal_path_for(manifest_path)
    timestamp = apply_timestamp or utc_now()
    applied_ids: list[str] = []
    with ApplyJournal(journal_path) as journal:
        journal.write(
            {
                "record_type": "header",
                "schema_version": SCHEMA_VERSION,
                "manifest_digest": digest,
                "apply_timestamp": timestamp,
                "target_count": TARGET_COUNT,
                "status_contract": "last status per id is authoritative",
            }
        )
        for target in targets:
            journal.write({"record_type": "target", "id": target["id"], "status": "unapplied"})
        for target in targets:
            event_id = target["id"]
            journal.write({"record_type": "target", "id": event_id, "status": "applying"})
            try:
                rows = cas_deactivate(sb, target, timestamp)
                if len(rows) != 1:
                    raise RuntimeError(f"CAS affected {len(rows)} rows for {event_id}")
            except Exception as exc:
                journal.write(
                    {
                        "record_type": "target",
                        "id": event_id,
                        "status": "error",
                        "error": str(exc),
                    }
                )
                raise
            journal.write({"record_type": "target", "id": event_id, "status": "applied"})
            applied_ids.append(event_id)
    return {
        "manifest_digest": digest,
        "journal_path": str(journal_path),
        "apply_timestamp": timestamp,
        "applied_ids": applied_ids,
        "warnings": warnings,
    }


def get_supabase() -> Any:
    from annotator import _get_supabase

    return _get_supabase()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or apply a digest-bound manifest for reviewed non-Japan scope events"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--snapshot", action="store_true", help="Create a read-only immutable manifest")
    mode.add_argument("--apply", action="store_true", help="Apply an exact digest-bound manifest")
    parser.add_argument("--out", type=Path, help="New immutable snapshot path")
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
        parser.error("--apply requires --manifest and --expect-digest")
    if args.out is not None:
        parser.error("--apply does not accept --out")


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_cli_args(parser, args)
    try:
        if args.snapshot:
            manifest = build_snapshot(get_supabase())
            write_manifest(args.out, manifest)
            print(f"snapshot_path={args.out}")
            print(f"target_count={manifest['target_count']}")
            print(f"manifest_digest={manifest['manifest_digest']}")
            print("read_only=true")
            return
        manifest = load_manifest(args.manifest)
        report = apply_manifest(
            get_supabase(),
            manifest,
            manifest_path=args.manifest,
            expected_digest=args.expect_digest,
        )
        print(f"applied_count={len(report['applied_ids'])}")
        print(f"journal_path={report['journal_path']}")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()