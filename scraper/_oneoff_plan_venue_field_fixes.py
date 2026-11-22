"""Build the read-only plan that fixes fields of existing authoritative venues (#733).

The plan holds only ``venue_update`` actions and is consumed by the existing
engine in ``_oneoff_repair_authoritative_venues.py`` (preview, ``--capture``,
``--apply``, ``--rollback``), as ``_oneoff_plan_tiff_venue_inserts.py`` does for
#341. It never touches events: the engine's event and field-correction actions,
and the R1 rollback gap that came with them, are not used.

Each fix names the fields to set and the aliases to remove, with the official
page the value comes from. Re-check those pages before ``--apply``; the values
were last confirmed on CHECKED_ON.

Usage (from the repository root, at a commit already on origin/main):
  python scraper/_oneoff_plan_venue_field_fixes.py \\
      --plan-output tmp/venue-field-fixes/plan.json
  python scraper/_oneoff_repair_authoritative_venues.py --plan tmp/venue-field-fixes/plan.json
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import _oneoff_repair_authoritative_venues as repair
from _oneoff_plan_tiff_venue_inserts import (
    _TIMESTAMP_RE,
    _venue_keys,
    capture_timestamp,
    current_repository_sha,
    fetch_all_venues,
)

CHECKED_ON = "2026-08-06"

# Fields this planner may change. Everything else on the row stays as captured.
FIXABLE_FIELDS = frozenset({"address", "homepage", "aliases", "latitude", "longitude"})

VENUE_FIELD_FIXES: tuple[dict[str, Any], ...] = (
    {
        "id": "10a9aa7a-f8e1-4721-9fd8-77af830b74d2",
        "canonical_name_ja": "八丁座",
        "set": {"homepage": "https://johakyu.co.jp/"},
        "remove_aliases": ["サロンシネマ", "サロンシネマ1・2"],
        "evidence": "https://johakyu.co.jp/information.html",
        "reason": "サロンシネマ is another cinema; the shared aliases made both keys ambiguous (#482)",
    },
    {
        "id": "29fef1e9-67d1-457f-81a2-17b1d80437f8",
        "canonical_name_ja": "サロンシネマ",
        "set": {
            "address": "広島県広島市中区八丁堀16-10 広島東映プラザビル8階",
            "homepage": "https://johakyu.co.jp/",
        },
        "evidence": "https://johakyu.co.jp/information.html",
        "reason": "the cinema's current building",
    },
    {
        "id": "e2f5fd1f-f92c-4e61-9f5f-383ac84c5d8b",
        "canonical_name_ja": "センチュリーシネマ",
        "set": {
            "address": "愛知県名古屋市中区栄3-29-1 名古屋パルコ東館8F",
            "homepage": "https://eiga.starcat.co.jp/theater/century/",
        },
        "evidence": "https://eiga.starcat.co.jp/theater/century/",
        "reason": "the stored address is another building; the homepage was a ticket schedule page",
    },
    {
        "id": "4e010225-f963-4556-a439-2bc4a35afb12",
        "canonical_name_ja": "台北駐日経済文化代表処 台湾文化センター",
        "set": {"homepage": "https://jp.taiwan.culture.tw/"},
        "add_aliases": ["台湾駐日本代表処台湾文化センター"],
        "evidence": "https://jp.taiwan.culture.tw/",
        "reason": "the centre's own site; the office's newer name as an alias (#370 r046)",
    },
)


def _after_row(before: dict[str, Any], fix: dict[str, Any]) -> dict[str, Any]:
    after = deepcopy(before)
    unknown = set(fix.get("set", {})) - FIXABLE_FIELDS
    if unknown:
        raise RuntimeError(f"STOP: {fix['canonical_name_ja']} sets fields outside the plan: {sorted(unknown)}")
    after.update(deepcopy(fix.get("set", {})))
    aliases = [a for a in before.get("aliases") or [] if a not in set(fix.get("remove_aliases", []))]
    for alias in fix.get("add_aliases", []):
        if alias not in aliases:
            aliases.append(alias)
    after["aliases"] = aliases
    # Coordinates belong to the old address once it changes.
    if after.get("address") != before.get("address"):
        after["latitude"] = None
        after["longitude"] = None
    return after


def _check_keys(live: list[dict[str, Any]], replaced: dict[str, dict[str, Any]]) -> None:
    """Stop if any name or alias would be held by two authoritative venues after the fix."""
    holders: dict[str, set[str]] = {}
    for row in live:
        row = replaced.get(str(row["id"]), row)
        if not row.get("is_authoritative"):
            continue
        for key in _venue_keys(row):
            holders.setdefault(key, set()).add(str(row["id"]))
    for venue_id, row in replaced.items():
        for key in _venue_keys(row):
            if len(holders.get(key, ())) > 1:
                raise RuntimeError(
                    f"STOP: {row['canonical_name_ja']} key {key!r} would be shared with "
                    f"{sorted(holders[key] - {venue_id})}"
                )


def fetch_references(sb: Any, venue_ids: list[str]) -> list[dict[str, Any]]:
    """Events pointing at the venues, with what decides whether a venue fix reaches them."""
    events = (
        sb.table("events")
        .select("id, venue_id, annotation_status, is_active")
        .in_("venue_id", venue_ids)
        .order("id")
        .execute()
        .data
        or []
    )
    ids = [e["id"] for e in events]
    locked: set[str] = set()
    for start in range(0, len(ids), 100):
        rows = (
            sb.table("field_corrections")
            .select("event_id")
            .in_("event_id", ids[start:start + 100])
            .eq("field_name", "location_address")
            .execute()
            .data
            or []
        )
        locked.update(str(r["event_id"]) for r in rows)
    return [{**e, "address_locked": str(e["id"]) in locked} for e in events]


def event_impact(references: list[dict[str, Any]], venue_id: str) -> dict[str, int]:
    """How the venue's events will see the fix (plan-critique-2 B1).

    reviewed events are never annotated again; a locked address is skipped by
    annotator and enrich_addresses; the rest pick the fix up when annotator next
    passes through the authoritative-venue path.
    """
    mine = [e for e in references if e.get("venue_id") == venue_id]
    return {
        "events": len(mine),
        "reviewed": sum(1 for e in mine if e.get("annotation_status") == "reviewed"),
        "address_locked": sum(
            1 for e in mine if e.get("annotation_status") != "reviewed" and e["address_locked"]
        ),
        "will_update": sum(
            1 for e in mine if e.get("annotation_status") != "reviewed" and not e["address_locked"]
        ),
    }


def build_venue_fix_plan(
    live_venues: list[dict[str, Any]],
    references: list[dict[str, Any]],
    *,
    captured_at: str,
    repository_sha: str,
    project_ref: str,
    fixes: tuple[dict[str, Any], ...] = VENUE_FIELD_FIXES,
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
    by_id = {str(row["id"]): row for row in live_venues}

    afters: dict[str, dict[str, Any]] = {}
    for fix in fixes:
        before = by_id.get(fix["id"])
        if before is None:
            raise RuntimeError(f"STOP: venue {fix['id']} ({fix['canonical_name_ja']}) does not exist")
        if before.get("canonical_name_ja") != fix["canonical_name_ja"]:
            raise RuntimeError(
                f"STOP: venue {fix['id']} is now {before.get('canonical_name_ja')!r}, "
                f"not {fix['canonical_name_ja']!r}"
            )
        if not before.get("is_authoritative") or before.get("is_multi_venue"):
            raise RuntimeError(f"STOP: {fix['canonical_name_ja']} is not a single authoritative venue")
        afters[fix["id"]] = _after_row(before, fix)
    _check_keys(live_venues, afters)

    actions, skips, impact = [], [], {}
    for fix in fixes:
        before, after = by_id[fix["id"]], afters[fix["id"]]
        refs = sorted(str(e["id"]) for e in references if e.get("venue_id") == fix["id"])
        action = repair._venue_update_action(before, after, before_references=refs, after_references=refs)
        action["evidence"].update({
            "source": "official_page_checked_by_hand",
            "classification": "authoritative_venue_field_fix",
            "official_page": fix["evidence"],
            "checked_on": CHECKED_ON,
            "reason": fix["reason"],
        })
        action["eligibility"]["reason"] = "authoritative_venue_field_fix"
        if action["eligibility"]["status"] == "eligible":
            actions.append(action)
        else:
            skips.append({"id": fix["id"], "reason": "exact_desired_venue_state"})
        impact[fix["canonical_name_ja"]] = event_impact(references, fix["id"])

    return {
        "project_ref": project_ref,
        "repository_sha": repository_sha,
        "captured_at": captured_at,
        "actions": actions,
        "conflicts": [],
        "skips": skips,
        "event_impact": impact,
    }


def run_cli(
    argv: list[str] | None = None,
    *,
    client_factory: Callable[..., Any] = repair.get_supabase,
    project_ref_getter: Callable[[], str] = repair.runtime_project_ref,
    repository_sha_getter: Callable[[], str] = current_repository_sha,
    repo_sha_verifier: Callable[[str], bool] = repair.verify_repo_sha_on_origin_main,
    now: datetime | None = None,
) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Build the read-only authoritative venue field fix plan")
    parser.add_argument("--plan-output", type=Path, required=True)
    args = parser.parse_args(argv)

    output = repair.assert_ignored_tmp_path(args.plan_output)
    repository_sha = repository_sha_getter()
    if not repo_sha_verifier(repository_sha):
        raise RuntimeError(f"STOP: HEAD {repository_sha} is not on origin/main")
    sb = client_factory(read_only=True)
    if not isinstance(sb, repair.ReadOnlyProxy):
        sb = repair.ReadOnlyProxy(sb)
    references = fetch_references(sb, [fix["id"] for fix in VENUE_FIELD_FIXES])
    plan = build_venue_fix_plan(
        fetch_all_venues(sb),
        references,
        captured_at=capture_timestamp(now),
        repository_sha=repository_sha,
        project_ref=project_ref_getter(),
    )
    impact = plan.pop("event_impact")
    written = repair.write_immutable_json(output, plan)
    return {
        "mode": "plan-read-only",
        "plan": str(written),
        "project_ref": plan["project_ref"],
        "repository_sha": repository_sha,
        "captured_at": plan["captured_at"],
        "updates": [action["evidence"]["canonical_name_ja"] for action in plan["actions"]],
        "skips": plan["skips"],
        "event_impact": impact,
        "mutations": 0,
    }


def main() -> None:
    print(json.dumps(run_cli(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
