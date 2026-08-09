"""Restore a publication-repair phase snapshot written by the manifest executor.

The executor writes an immutable snapshot and declares a `rollback_contract`, but
ships no way to act on it, so recovery was a manual procedure. This is that
procedure as code, for the Step B3R rehearsal and for PN-3a/PN-3b recovery.

It honours the snapshot's own declared contract rather than a hardcoded one:
delete the field corrections the phase created, restore each table in the
declared order using the declared conflict keys, then read back every row.

Deletion is scoped to publication target fields on the snapshot's own events, so
a field correction the phase never touched is never removed.

    # dry-run against a rehearsal target (refuses the production project ref)
    PUBLICATION_MANIFEST_ENV_FILE=/path/to/rehearsal.env \
      python _oneoff_restore_publication_snapshot.py --snapshot SNAP.json --target rehearsal

    # execute
    PUBLICATION_MANIFEST_ENV_FILE=/path/to/rehearsal.env \
      python _oneoff_restore_publication_snapshot.py --snapshot SNAP.json --target rehearsal --apply
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _oneoff_backfill_publication_metadata import (
    CHECKPOINT_VOLATILE_EVENT_FIELDS,
    assert_non_production_target,
    fetch_rows_in,
    get_supabase,
    is_target_field,
    now_iso,
    row_sort_key,
    sha256,
)

RESTORE_TABLES = ("events", "field_corrections")
OBSERVED_FC_KEYS = ("target_field_corrections", "preserve_field_corrections")


def load_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    digest = payload.pop("snapshot_sha256", None)
    if digest != sha256(payload):
        raise RuntimeError("snapshot digest mismatch; the immutable snapshot was modified")
    payload["snapshot_sha256"] = digest
    contract = payload.get("rollback_contract") or {}
    missing = [
        key
        for key in ("restore_order", "upsert_conflict_keys", "read_back_every_row")
        if key not in contract
    ]
    if missing:
        raise RuntimeError(f"snapshot declares no usable rollback contract: missing {missing}")
    return payload


def snapshot_rows(snapshot: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    observed = snapshot.get("observed") or {}
    field_corrections: dict[str, dict[str, Any]] = {}
    for key in OBSERVED_FC_KEYS:
        for row in observed.get(key) or []:
            field_corrections[str(row.get("id"))] = deepcopy(row)
    return {
        "events": sorted(deepcopy(observed.get("events") or []), key=row_sort_key),
        "field_corrections": sorted(field_corrections.values(), key=row_sort_key),
    }


def phase_created_field_corrections(
    sb, rows: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Target-field corrections that exist now but were absent at snapshot time."""
    event_ids = [str(row["id"]) for row in rows["events"]]
    if not event_ids:
        return []
    known = {str(row.get("id")) for row in rows["field_corrections"]}
    live = fetch_rows_in(sb, "field_corrections", "event_id", event_ids)
    return sorted(
        (
            deepcopy(row)
            for row in live
            if is_target_field(row.get("field_name")) and str(row.get("id")) not in known
        ),
        key=row_sort_key,
    )


def _conflict_key(row: dict[str, Any], columns: list[str]) -> tuple[str, ...]:
    return tuple(str(row.get(column)) for column in columns)


def read_back_mismatches(
    sb, table: str, rows: list[dict[str, Any]], conflict_columns: list[str]
) -> list[dict[str, Any]]:
    if not rows:
        return []
    column = conflict_columns[0]
    live = fetch_rows_in(sb, table, column, [str(row.get(column)) for row in rows])
    by_key = {_conflict_key(row, conflict_columns): row for row in live}
    mismatches = []
    for expected in rows:
        actual = by_key.get(_conflict_key(expected, conflict_columns))
        if actual is None:
            mismatches.append({"table": table, "row": expected, "reason": "missing after restore"})
            continue
        differing = sorted(
            field
            for field, value in expected.items()
            if field not in CHECKPOINT_VOLATILE_EVENT_FIELDS and actual.get(field) != value
        )
        if differing:
            mismatches.append({"table": table, "row": expected, "reason": f"fields differ: {differing}"})
    return mismatches


def restore(sb, snapshot: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    contract = snapshot["rollback_contract"]
    conflict_keys = contract["upsert_conflict_keys"]
    order = [table for table in contract["restore_order"] if table in RESTORE_TABLES]
    unsupported = [table for table in contract["restore_order"] if table not in RESTORE_TABLES]
    if unsupported:
        raise RuntimeError(f"snapshot restore_order names unsupported tables: {unsupported}")

    rows = snapshot_rows(snapshot)
    phase_created = phase_created_field_corrections(sb, rows)
    result: dict[str, Any] = {
        "generated_at": now_iso(),
        "snapshot_sha256": snapshot["snapshot_sha256"],
        "apply_phase": snapshot.get("apply_phase"),
        "checkpoint": snapshot.get("checkpoint"),
        "mode": "apply" if apply else "dry-run",
        "restore_order": order,
        "planned_deletes": [str(row.get("id")) for row in phase_created],
        "planned_restores": {table: len(rows[table]) for table in order},
        "deleted": 0,
        "restored": {table: 0 for table in order},
        "read_back_mismatches": [],
    }
    if not apply:
        return result

    if contract.get("delete_new_field_corrections_before_restore"):
        for row in phase_created:
            sb.table("field_corrections").delete().eq("id", str(row["id"])).execute()
            result["deleted"] += 1

    for table in order:
        columns = list(conflict_keys[table])
        for row in rows[table]:
            sb.table(table).upsert(deepcopy(row), on_conflict=",".join(columns)).execute()
            result["restored"][table] += 1

    if contract.get("read_back_every_row"):
        for table in order:
            result["read_back_mismatches"].extend(
                read_back_mismatches(sb, table, rows[table], list(conflict_keys[table]))
            )
    if result["read_back_mismatches"]:
        raise RuntimeError(
            f"restore read-back failed for {len(result['read_back_mismatches'])} row(s): "
            f"{result['read_back_mismatches']}"
        )
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore a publication phase snapshot")
    parser.add_argument("--snapshot", type=Path, required=True, help="Immutable phase snapshot")
    parser.add_argument(
        "--target",
        choices=("rehearsal", "production"),
        required=True,
        help="rehearsal refuses the production project ref; production is an explicit choice",
    )
    parser.add_argument("--apply", action="store_true", help="Execute the restore")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    snapshot = load_snapshot(args.snapshot)
    sb = get_supabase(read_only=not args.apply)
    if args.target == "rehearsal":
        assert_non_production_target()
    print(json.dumps(restore(sb, snapshot, apply=args.apply), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
