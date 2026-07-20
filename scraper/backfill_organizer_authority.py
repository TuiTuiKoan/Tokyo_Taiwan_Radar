#!/usr/bin/env python3
"""Backfill organizer authority — Wave 2 Phase D (registry backfill, dry-run first).

Re-resolves the organizer *type* fields of active events against the
authoritative organizer registry, reusing the exact same logic the daily
annotator applies (``annotator._apply_organizer_registry``) so there is a
single source of truth for the scalar→array four-case protection — no
duplicated logic, no drift.

Per event it also sets ``organizer_id`` when the primary organizer name
resolves to an authoritative entity (the annotator helper only refines types;
FK population lives in ``database._populate_entity_fks``, mirrored here).

⛔ SCOPE — this batch is CODE-ONLY: the default mode is ``--dry-run`` and NO
row is ever written unless ``--apply`` is passed. The real backfill is
production gate 2C; do NOT run ``--apply`` here.

Graceful degradation (migration 095 not yet applied)
----------------------------------------------------
The registry loads only ``organizers`` rows flagged ``is_authoritative``. That
column ships in migration 095; before it is applied ``lookup_organizer``
returns ``None`` for every name (empty registry), so every event is an exact
no-op and the dry-run reports zero coverage. That is the expected pre-gate
state — the backfill only has effect once gate 2C has seeded authoritative rows.

Authority order preserved
-------------------------
``FC > registry > source default > existing > LLM``. Fields locked by
``field_corrections`` are skipped and counted; they are never overwritten.

Four-case primary protection (delegated to the annotator helper)
----------------------------------------------------------------
(a) empty / all-unknown  → adopt registry type;
(b) already contains it  → preserve verbatim (no flatten/reorder);
(c) single conflict      → registry wins (counted);
(d) ≥2 valid, none match → fail closed, keep original array + manual queue.

Usage::

    python backfill_organizer_authority.py            # dry-run (default)
    python backfill_organizer_authority.py --apply    # gate 2C ONLY
"""

from __future__ import annotations

import argparse
import copy
import logging
import os
from typing import Any

from dotenv import load_dotenv

import annotator
from annotator import _apply_organizer_registry, _load_human_field_map
from database import _get_client
from organizer_registry import lookup_organizer, reset_cache

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Type fields refined by the registry (parallel to the name fields).
TYPE_FIELDS = ("organizer_type", "co_organizer_types", "sponsor_types")
# FC-protectable fields relevant to this backfill.
_FC_RELEVANT = TYPE_FIELDS + ("organizer_id", "organizer")

_EVENT_COLUMNS = (
    "id,organizer,organizer_id,organizer_type,"
    "co_organizers,co_organizer_types,sponsors,sponsor_types"
)


def fetch_active_events(sb: Any) -> list[dict[str, Any]]:
    """Return all active events (paginated; Supabase caps at 1000/call)."""
    out: list[dict[str, Any]] = []
    offset = 0
    while True:
        rows = (
            sb.table("events")
            .select(_EVENT_COLUMNS)
            .eq("is_active", True)
            .range(offset, offset + 999)
            .execute()
            .data
            or []
        )
        if not rows:
            break
        out.extend(rows)
        if len(rows) < 1000:
            break
        offset += 1000
    return out


def build_working_data(event: dict[str, Any]) -> dict[str, Any]:
    """Copy the organizer name + type fields into a mutable working dict.

    Deep-copies list values so mutation by the annotator helper never touches
    the source event row.
    """
    fields = (
        "organizer", "organizer_type",
        "co_organizers", "co_organizer_types",
        "sponsors", "sponsor_types",
    )
    return {f: copy.deepcopy(event.get(f)) for f in fields}


def _count_unknowns(data: dict[str, Any]) -> int:
    """Count ``unknown`` entries across the co/sponsor type arrays."""
    total = 0
    for field in ("co_organizer_types", "sponsor_types"):
        for t in data.get(field) or []:
            if t == "unknown":
                total += 1
    return total


def _detect_primary_conflict(
    event: dict[str, Any],
    before_type: list[str] | None,
    fc_fields: set[str],
    hit: dict[str, Any] | None,
) -> bool:
    """Report-only detection of the four-case (d) fail-closed manual-queue case.

    Mirrors — for counting only — the branch inside
    ``_apply_organizer_registry``: a registry hit whose scalar type conflicts
    with an existing multi-type (≥2 valid) array that does not contain it. The
    actual write decision is still owned by the annotator helper; this only
    classifies the outcome for the dry-run report.
    """
    if "organizer_type" in fc_fields or not hit:
        return False
    rtype = hit.get("organizer_type")
    if not (
        isinstance(rtype, str)
        and rtype in annotator.VALID_ORGANIZER_TYPES
        and rtype != "unknown"
    ):
        return False
    current = before_type or []
    valid = [
        t for t in current
        if isinstance(t, str) and t in annotator.VALID_ORGANIZER_TYPES and t != "unknown"
    ]
    return len(valid) >= 2 and rtype not in valid


def plan_event(event: dict[str, Any], fc_fields: set[str]) -> dict[str, Any]:
    """Compute the registry backfill plan for one event (no DB write).

    Delegates the type mutation to ``annotator._apply_organizer_registry`` and
    adds the ``organizer_id`` FK the annotator helper does not set.
    """
    data = build_working_data(event)
    before = {f: copy.deepcopy(data.get(f)) for f in TYPE_FIELDS}
    before_org_id = event.get("organizer_id")

    # Reuse the canonical four-case + per-index overlay logic (single source of
    # truth). FC-protected type fields are skipped inside the helper.
    _apply_organizer_registry(event, data, fc_fields)

    # organizer_id FK (registry primary hit) — not handled by the annotator.
    primary_name = data.get("organizer") or event.get("organizer")
    hit = lookup_organizer(primary_name) if primary_name else None
    org_id_change: tuple[Any, Any] | None = None
    if hit and "organizer_id" not in fc_fields:
        new_id = hit.get("id")
        if new_id and new_id != before_org_id:
            data["organizer_id"] = new_id
            org_id_change = (before_org_id, new_id)

    after = {f: copy.deepcopy(data.get(f)) for f in TYPE_FIELDS}
    type_changed = after != before
    changed = type_changed or org_id_change is not None

    fc_skips = sorted(f for f in _FC_RELEVANT if f in fc_fields)
    primary_conflict = _detect_primary_conflict(
        event, before.get("organizer_type"), fc_fields, hit
    )

    return {
        "event_id": event.get("id"),
        "changed": changed,
        "before": before,
        "after": after,
        "org_id_change": org_id_change,
        "fc_skips": fc_skips,
        "primary_conflict": primary_conflict,
        "unknowns": _count_unknowns(data),
        "registry_hit": bool(hit),
        "_write": {f: data.get(f) for f in TYPE_FIELDS if after[f] != before[f]}
        | ({"organizer_id": data.get("organizer_id")} if org_id_change else {}),
    }


def run(dry_run: bool = True, sample: int = 20) -> dict[str, Any]:
    sb = _get_client()
    # Rebuild the registry cache against the current DB (empty pre-095).
    reset_cache()

    events = fetch_active_events(sb)
    try:
        fc_map = _load_human_field_map(sb)
    except Exception as exc:
        logger.debug("field_corrections unavailable (pre-migration 038b?): %s", exc)
        fc_map = {}

    plans = [plan_event(ev, set(fc_map.get(ev.get("id"), {}).keys())) for ev in events]

    changed = [p for p in plans if p["changed"]]
    conflicts = [p for p in plans if p["primary_conflict"]]
    fc_skipped = [p for p in plans if p["fc_skips"]]
    total_unknowns = sum(p["unknowns"] for p in plans)
    registry_hits = sum(1 for p in plans if p["registry_hit"])

    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"=== backfill_organizer_authority [{mode}] — {len(events)} active events ===")
    if registry_hits == 0:
        print(
            "[REGISTRY] 0 authoritative hits → registry 為空（migration 095 未 apply "
            "或尚未 seed authoritative rows）。預期無覆蓋；pre-flight/結構正常。"
        )
    else:
        print(f"[REGISTRY] {registry_hits} event(s) matched an authoritative organizer.")

    print(
        f"[SUMMARY] changed={len(changed)} primary_conflicts(manual queue)={len(conflicts)} "
        f"fc_skipped_events={len(fc_skipped)} co/sponsor_unknowns={total_unknowns}"
    )

    for p in changed[:sample]:
        print(
            f"[CHANGE] {p['event_id']}\n"
            f"    before: {p['before']}\n"
            f"    after : {p['after']}"
            + (f"\n    organizer_id: {p['org_id_change'][0]} → {p['org_id_change'][1]}"
               if p["org_id_change"] else "")
            + (f"\n    fc_skips: {p['fc_skips']}" if p["fc_skips"] else "")
        )
    if conflicts:
        print(f"\n[MANUAL QUEUE] {len(conflicts)} primary multi-type conflict(s) (fail closed, no auto-flatten):")
        for p in conflicts[:sample]:
            print(f"    - {p['event_id']} existing={p['before']['organizer_type']}")

    applied = 0
    if not dry_run:
        for p in changed:
            payload = p["_write"]
            if not payload:
                continue
            sb.table("events").update(payload).eq("id", p["event_id"]).execute()
            applied += 1
        print(f"[APPLY] updated {applied} event row(s).")

    return {
        "events": len(events),
        "changed": len(changed),
        "primary_conflicts": len(conflicts),
        "fc_skipped_events": len(fc_skipped),
        "unknowns": total_unknowns,
        "registry_hits": registry_hits,
        "applied": applied,
        "plans": plans,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill organizer authority types/FK from the registry (dry-run default)."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write refined types/organizer_id to events (gate 2C ONLY).",
    )
    parser.add_argument(
        "--sample", type=int, default=20, help="Console sample rows (default 20)."
    )
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run(dry_run=not args.apply, sample=args.sample)


if __name__ == "__main__":
    main()
