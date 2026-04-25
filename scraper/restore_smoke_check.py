"""
Smoke-check backup snapshot integrity before using it for restore.

Usage:
  python restore_smoke_check.py --input /tmp/tt_backup_test
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_FILES = {
    "category_corrections": "category_corrections.json",
    "event_reports": "event_reports.json",
    "events": "events.json",
    "research_reports": "research_reports.json",
    "research_sources": "research_sources.json",
}

REQUIRED_COLUMNS = {
    "category_corrections": {"id", "event_id", "created_at"},
    "event_reports": {"id", "event_id", "report_types", "created_at"},
    "events": {"id", "source_name", "source_id", "is_active", "updated_at"},
    "research_reports": {"id", "report_type", "content", "created_at"},
    "research_sources": {"id", "name", "url", "status", "created_at"},
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _validate_required_files(base_dir: Path, errors: list[str]) -> None:
    required = ["metadata.json", "checksums.json", *REQUIRED_FILES.values()]
    for file_name in required:
        if not (base_dir / file_name).exists():
            errors.append(f"Missing required file: {file_name}")


def _validate_checksums(base_dir: Path, checksums: dict[str, Any], errors: list[str]) -> None:
    expected = checksums.get("sha256")
    if not isinstance(expected, dict):
        errors.append("Invalid checksums.json: missing sha256 map")
        return

    for file_name, expected_hash in expected.items():
        file_path = base_dir / file_name
        if not file_path.exists():
            errors.append(f"checksums.json references missing file: {file_name}")
            continue
        actual = _sha256(file_path)
        if actual != expected_hash:
            errors.append(
                f"Checksum mismatch for {file_name}: expected {expected_hash}, got {actual}"
            )


def _validate_table_schema_and_counts(
    base_dir: Path,
    metadata: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    tables_meta = metadata.get("tables")
    if not isinstance(tables_meta, dict):
        errors.append("Invalid metadata.json: missing tables object")
        return

    for table_name, file_name in REQUIRED_FILES.items():
        file_path = base_dir / file_name
        if not file_path.exists():
            continue

        data = _load_json(file_path)
        if not isinstance(data, list):
            errors.append(f"{file_name} must contain a JSON array")
            continue

        table_meta = tables_meta.get(table_name)
        if not isinstance(table_meta, dict):
            errors.append(f"metadata.json missing table metadata for {table_name}")
            continue

        expected_count = table_meta.get("row_count")
        if expected_count != len(data):
            errors.append(
                f"Row count mismatch for {table_name}: metadata={expected_count}, actual={len(data)}"
            )

        if len(data) == 0:
            warnings.append(f"{table_name}: snapshot has 0 rows")
            continue

        sample = data[0]
        if not isinstance(sample, dict):
            errors.append(f"{table_name}: row is not a JSON object")
            continue

        missing_columns = sorted(REQUIRED_COLUMNS[table_name] - set(sample.keys()))
        if missing_columns:
            errors.append(f"{table_name}: missing required columns: {', '.join(missing_columns)}")

        if len(data) > 1_000_000:
            errors.append(f"{table_name}: row count too large for smoke-check ({len(data)})")


def run(input_dir: str) -> int:
    base_dir = Path(input_dir).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not base_dir.exists() or not base_dir.is_dir():
        print(f"ERROR: input directory does not exist: {base_dir}")
        return 2

    _validate_required_files(base_dir, errors)
    if errors:
        for msg in errors:
            print(f"ERROR: {msg}")
        return 2

    metadata = _load_json(base_dir / "metadata.json")
    checksums = _load_json(base_dir / "checksums.json")

    _validate_checksums(base_dir, checksums, errors)
    _validate_table_schema_and_counts(base_dir, metadata, errors, warnings)

    if warnings:
        for msg in warnings:
            print(f"WARN: {msg}")

    if errors:
        for msg in errors:
            print(f"ERROR: {msg}")
        return 2

    print("Restore smoke-check passed")
    print(f"Snapshot folder: {base_dir}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate backup snapshot integrity")
    parser.add_argument("--input", required=True, help="Snapshot directory path")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(run(args.input))