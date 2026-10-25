"""Build the read-only plan that inserts the four TIFF 2026 venues (issue #341).

The plan holds only ``venue_insert`` actions and is consumed by the existing
engine in ``_oneoff_repair_authoritative_venues.py`` (preview, ``--capture``,
``--apply``). It never builds the full 70-action repair from #339.

Usage (from the repository root, at a commit already on origin/main):
  python scraper/_oneoff_plan_tiff_venue_inserts.py \
      --plan-output tmp/tiff-venue-inserts/plan.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import _oneoff_repair_authoritative_venues as repair
from _oneoff_seed_authoritative_venues import SEED_DATA

TIFF_INSERT_VENUE_NAMES = (
    "ヒューリックホール東京",
    "TOHOシネマズ シャンテ",
    "TOHOシネマズ 日比谷 スクリーン12・13",
    "丸の内ピカデリー",
)
# PostgREST renders a whole-second timestamptz exactly like this, so the
# engine's exact read-back after insert can compare created_at/updated_at.
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$")
_PAGE_SIZE = 1000


def capture_timestamp(now: datetime | None = None) -> str:
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return moment.replace(microsecond=0).isoformat()


def fetch_all_venues(sb: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        page = (
            sb.table("venues")
            .select("*")
            .order("id")
            .range(start, start + _PAGE_SIZE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < _PAGE_SIZE:
            return rows
        start += _PAGE_SIZE


def _venue_keys(row: dict[str, Any]) -> list[str]:
    keys = [str(row.get("canonical_name_ja") or "").strip()]
    keys.extend(str(alias or "").strip() for alias in row.get("aliases") or [])
    return [key for key in keys if key]


def _insert_seeds() -> dict[str, dict[str, Any]]:
    seeds: dict[str, dict[str, Any]] = {}
    for row in SEED_DATA:
        name = row.get("canonical_name_ja")
        if name not in TIFF_INSERT_VENUE_NAMES:
            continue
        if name in seeds:
            raise RuntimeError(f"STOP: duplicate seed definition for {name}")
        if row.get("_expected_id"):
            raise RuntimeError(f"STOP: insert seed must not carry _expected_id: {name}")
        if row.get("is_authoritative") is not True or row.get("is_multi_venue") is not False:
            raise RuntimeError(f"STOP: insert seed must be a single authoritative venue: {name}")
        seeds[str(name)] = row
    missing = [name for name in TIFF_INSERT_VENUE_NAMES if name not in seeds]
    if missing:
        raise RuntimeError("STOP: missing seed definitions: " + ", ".join(missing))
    return seeds


def build_tiff_insert_plan(
    live_venues: list[dict[str, Any]],
    *,
    captured_at: str,
    repository_sha: str,
    project_ref: str,
    id_factory: Callable[[], Any] = uuid4,
) -> dict[str, Any]:
    if not _TIMESTAMP_RE.match(captured_at):
        raise RuntimeError(f"STOP: capture timestamp must be whole-second UTC: {captured_at}")
    if not live_venues:
        raise RuntimeError("STOP/INCONCLUSIVE: live venues snapshot is empty")
    for row in live_venues:
        if set(row) != repair.VENUE_REQUIRED_FIELDS:
            raise RuntimeError(
                "STOP: live venues columns differ from the engine contract: "
                f"extra={sorted(set(row) - repair.VENUE_REQUIRED_FIELDS)} "
                f"missing={sorted(repair.VENUE_REQUIRED_FIELDS - set(row))}"
            )

    existing_ids = {str(row.get("id")) for row in live_venues}
    existing_keys: dict[str, list[str]] = {}
    for row in live_venues:
        for key in _venue_keys(row):
            existing_keys.setdefault(key, []).append(str(row.get("id")))

    seeds = _insert_seeds()
    rows: list[dict[str, Any]] = []
    planned_keys: dict[str, str] = {}
    planned_ids: set[str] = set()
    for name in TIFF_INSERT_VENUE_NAMES:
        venue_id = str(id_factory())
        if not repair._valid_uuid(venue_id) or venue_id in planned_ids:
            raise RuntimeError(f"STOP: generated venue UUID is invalid or duplicate: {venue_id}")
        if venue_id in existing_ids:
            raise RuntimeError(f"STOP: generated venue UUID already exists: {venue_id}")
        planned_ids.add(venue_id)
        row = repair.new_venue_row(seeds[name], venue_id, captured_at=captured_at)
        for key in _venue_keys(row):
            if key in existing_keys:
                raise RuntimeError(
                    f"STOP: {name} key {key!r} already exists on venues "
                    f"{sorted(existing_keys[key])}"
                )
            if key in planned_keys and planned_keys[key] != name:
                raise RuntimeError(
                    f"STOP: key {key!r} collides between {planned_keys[key]} and {name}"
                )
            planned_keys[key] = name
        rows.append(row)

    return {
        "project_ref": project_ref,
        "repository_sha": repository_sha,
        "captured_at": captured_at,
        "actions": [
            repair._venue_insert_action(row, after_references=[]) for row in rows
        ],
        "conflicts": [],
        "skips": [],
    }


def current_repository_sha() -> str:
    result = subprocess.run(
        ["git", "-C", str(repair.ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def run_cli(
    argv: list[str] | None = None,
    *,
    client_factory: Callable[..., Any] = repair.get_supabase,
    project_ref_getter: Callable[[], str] = repair.runtime_project_ref,
    repository_sha_getter: Callable[[], str] = current_repository_sha,
    repo_sha_verifier: Callable[[str], bool] = repair.verify_repo_sha_on_origin_main,
    now: datetime | None = None,
) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Build the read-only TIFF venue insert plan")
    parser.add_argument("--plan-output", type=Path, required=True)
    args = parser.parse_args(argv)

    output = repair.assert_ignored_tmp_path(args.plan_output)
    repository_sha = repository_sha_getter()
    if not repo_sha_verifier(repository_sha):
        raise RuntimeError(f"STOP: HEAD {repository_sha} is not on origin/main")
    sb = client_factory(read_only=True)
    if not isinstance(sb, repair.ReadOnlyProxy):
        sb = repair.ReadOnlyProxy(sb)
    plan = build_tiff_insert_plan(
        fetch_all_venues(sb),
        captured_at=capture_timestamp(now),
        repository_sha=repository_sha,
        project_ref=project_ref_getter(),
    )
    written = repair.write_immutable_json(output, plan)
    return {
        "mode": "plan-read-only",
        "plan": str(written),
        "project_ref": plan["project_ref"],
        "repository_sha": repository_sha,
        "captured_at": plan["captured_at"],
        "venues": [
            {"id": action["id"], "canonical_name_ja": action["after"]["venue"]["canonical_name_ja"]}
            for action in plan["actions"]
        ],
        "mutations": 0,
    }


def main() -> None:
    print(json.dumps(run_cli(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
