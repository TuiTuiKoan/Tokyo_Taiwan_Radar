"""
Create a backup snapshot from Supabase tables used by the scraper/admin flow.

Usage:
  python backup_snapshot.py --dry-run
  python backup_snapshot.py --output-dir /tmp/tt_backup_test
"""

import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

PAGE_SIZE = 1000
REQUIRED_TABLE_FILES = {
    "category_corrections": "category_corrections.json",
    "event_reports": "event_reports.json",
    "events": "events.json",
    "research_reports": "research_reports.json",
    "research_sources": "research_sources.json",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _utc_stamp() -> str:
    return _now_utc().strftime("%Y%m%dT%H%M%SZ")


def _supabase_client():
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _fetch_all_rows(sb, table_name: str, columns: str = "*") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0

    while True:
        end = start + PAGE_SIZE - 1
        result = (
            sb.table(table_name)
            .select(columns)
            .range(start, end)
            .execute()
        )
        batch = result.data or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE

    return rows


def _fetch_events_by_filter(sb, *, inactive_only: bool = False, updated_after: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0

    while True:
        end = start + PAGE_SIZE - 1
        query = sb.table("events").select("*")
        if inactive_only:
            query = query.eq("is_active", False)
        if updated_after:
            query = query.gte("updated_at", updated_after)

        result = query.range(start, end).execute()
        batch = result.data or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE

    return rows


def _fetch_events_snapshot_rows(sb) -> list[dict[str, Any]]:
    cutoff = (_now_utc() - timedelta(days=30)).isoformat()
    inactive_rows = _fetch_events_by_filter(sb, inactive_only=True)
    recent_rows = _fetch_events_by_filter(sb, updated_after=cutoff)

    merged: dict[str, dict[str, Any]] = {}
    for row in inactive_rows + recent_rows:
        row_id = row.get("id")
        if row_id:
            merged[row_id] = row
    return list(merged.values())


def _to_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, payload: Any) -> tuple[int, str]:
    data = _to_json_bytes(payload)
    path.write_bytes(data)
    return len(data), _sha256(data)


def _impact_summary(sb) -> dict[str, int]:
    target_events = _fetch_events_snapshot_rows(sb)
    target_event_ids = {e["id"] for e in target_events if e.get("id")}

    event_reports = _fetch_all_rows(sb, "event_reports", "id,event_id")
    category_corrections = _fetch_all_rows(sb, "category_corrections", "id,event_id")

    report_count = sum(1 for r in event_reports if r.get("event_id") in target_event_ids)
    correction_count = sum(1 for r in category_corrections if r.get("event_id") in target_event_ids)
    sub_event_count = sum(1 for e in target_events if e.get("parent_event_id") is not None)

    return {
        "events": len(target_events),
        "event_reports": report_count,
        "category_corrections": correction_count,
        "sub_events": sub_event_count,
    }


def _resolve_output_dir(output_dir: str | None) -> Path:
    if output_dir:
        return Path(output_dir).expanduser().resolve()
    return Path("/tmp") / f"tt_backup_snapshot_{_utc_stamp()}"


def _snapshot_metadata(table_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "generated_at": _now_utc().isoformat(),
        "tables": {
            table_name: {
                "row_count": len(rows),
                "file": REQUIRED_TABLE_FILES[table_name],
            }
            for table_name, rows in table_rows.items()
        },
    }


def run(dry_run: bool, output_dir: str | None) -> int:
    sb = _supabase_client()
    impact = _impact_summary(sb)

    print("Impact summary:")
    print(json.dumps(impact, ensure_ascii=False, indent=2))

    if dry_run:
        print("DRY RUN: no snapshot files written")
        return 0

    out_dir = _resolve_output_dir(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    table_rows = {
        "category_corrections": _fetch_all_rows(sb, "category_corrections"),
        "event_reports": _fetch_all_rows(sb, "event_reports"),
        "events": _fetch_events_snapshot_rows(sb),
        "research_reports": _fetch_all_rows(sb, "research_reports"),
        "research_sources": _fetch_all_rows(sb, "research_sources"),
    }

    checksums: dict[str, str] = {}
    file_sizes: dict[str, int] = {}

    for table_name, rows in table_rows.items():
        file_name = REQUIRED_TABLE_FILES[table_name]
        size, digest = _write_json(out_dir / file_name, rows)
        checksums[file_name] = digest
        file_sizes[file_name] = size

    metadata = _snapshot_metadata(table_rows)
    metadata["files"] = {
        file_name: {
            "sha256": checksums[file_name],
            "bytes": file_sizes[file_name],
        }
        for file_name in checksums
    }

    metadata_bytes, metadata_sha = _write_json(out_dir / "metadata.json", metadata)
    checksums["metadata.json"] = metadata_sha
    file_sizes["metadata.json"] = metadata_bytes

    checksums_payload = {
        "generated_at": _now_utc().isoformat(),
        "sha256": checksums,
    }
    _write_json(out_dir / "checksums.json", checksums_payload)

    print(f"Snapshot written to: {out_dir}")
    print(json.dumps({"files": file_sizes}, ensure_ascii=False, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Supabase backup snapshots")
    parser.add_argument("--dry-run", action="store_true", help="Only print impact summary")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Destination directory for snapshot files. Defaults to /tmp with UTC timestamp.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(run(dry_run=args.dry_run, output_dir=args.output_dir))