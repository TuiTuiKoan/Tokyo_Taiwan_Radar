#!/usr/bin/env python3
"""
Phase A.5 — repair co_organizer / sponsor parallel type-array cardinality.

Finds every event (active + inactive) where
    COALESCE(cardinality(co_organizers), 0) != COALESCE(cardinality(co_organizer_types), 0)
  or
    COALESCE(cardinality(sponsors), 0)     != COALESCE(cardinality(sponsor_types), 0)
and proposes a cardinality-aligning repair. Default mode is DRY-RUN — it only
prints a manifest and writes JSON to --out; it does NOT touch the database
unless --apply is passed.

Scope is table-wide (not active-only) because the Phase B cardinality CHECK is
a validated table constraint: any inactive-event mismatch would block it too.

Repair contract (cardinality alignment ONLY — no entity-type refinement, no
LLM, no dependency on any not-yet-seeded registry):
  - names is NULL           -> type array set to NULL
  - names is []             -> type array set to []
  - names non-empty:
      per index i, keep the existing same-index type if it is one of the
      canonical 10 values; otherwise fill 'unknown'. Never shift a previous
      index's type into the next slot.
  - type array LONGER than names (orphan trailing types) -> flagged for MANUAL
      review; NOT auto-truncated (an orphan type may signal a dropped name).
  - if the role's type array is protected by a field_corrections row -> skipped
      and routed to the manual queue (FC keeps top priority).

Registry-based type refinement is intentionally deferred to Phase D.

Usage:
    python _oneoff_repair_organizer_type_arrays.py                # dry-run
    python _oneoff_repair_organizer_type_arrays.py --out .        # manifest to cwd
    python _oneoff_repair_organizer_type_arrays.py --apply        # (NOT this batch)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import database  # noqa: E402  (service-role client)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

CANONICAL_TYPES = frozenset([
    "government", "semi_official", "cultural_institution", "academic",
    "commercial_brand", "independent_venue", "civic_group", "media",
    "individual", "unknown",
])

# role -> (names_column, types_column). types_column is also the
# field_corrections.field_name that protects that array.
ROLES = (
    ("co", "co_organizers", "co_organizer_types"),
    ("sponsor", "sponsors", "sponsor_types"),
)
_FC_FIELDS = frozenset(tc for _, _, tc in ROLES)


def _card(x) -> int:
    """COALESCE(cardinality(x), 0) — None and [] both -> 0."""
    return len(x or [])


def _fetch_all_events(sb) -> list[dict[str, Any]]:
    """Fetch ALL events (active + inactive).

    The Phase B cardinality CHECK is table-wide, so pre-migration remediation
    must align every row regardless of is_active — inactive mismatches would
    otherwise block the validated constraint.
    """
    cols = (
        "id,is_active,source_url,co_organizers,co_organizer_types,"
        "sponsors,sponsor_types"
    )
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch = (
            sb.table("events").select(cols)
            .order("id")
            .range(offset, offset + 999)
            .execute()
            .data or []
        )
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return rows


def _load_fc_protected(sb) -> dict[str, dict[str, str]]:
    """event_id -> {field_name: corrected_value} for the two type arrays only."""
    out: dict[str, dict[str, str]] = {}
    offset = 0
    while True:
        rows = (
            sb.table("field_corrections")
            .select("event_id,field_name,corrected_value")
            .in_("field_name", list(_FC_FIELDS))
            .range(offset, offset + 999)
            .execute()
            .data or []
        )
        if not rows:
            break
        for r in rows:
            eid = r.get("event_id")
            fname = r.get("field_name")
            if eid and fname:
                out.setdefault(eid, {})[fname] = r.get("corrected_value") or ""
        if len(rows) < 1000:
            break
        offset += 1000
    return out


def _plan(names, types) -> tuple[Any, str, list[str]]:
    """Return (proposed_type_array, direction, per-index reasons)."""
    if names is None:
        return None, "names_null_clear", ["names is NULL -> type array set NULL"]
    if len(names) == 0:
        return [], "names_empty_clear", ["names is [] -> type array set []"]

    reasons: list[str] = []
    new: list[str] = []
    for i in range(len(names)):
        existing = types[i] if (types and i < len(types)) else None
        if existing in CANONICAL_TYPES:
            new.append(existing)
            reasons.append(f"[{i}] keep existing valid '{existing}'")
        else:
            new.append("unknown")
            reasons.append(
                f"[{i}] {'missing' if existing is None else f'invalid {existing!r}'} -> 'unknown'"
            )

    orphans = list((types or [])[len(names):])
    if orphans:
        return new, "types_longer_orphan", reasons + [
            f"ORPHAN types beyond names: {orphans} -> MANUAL review (not auto-truncated)"
        ]
    return new, "types_shorter_pad", reasons


def _apply_row(sb, eid: str, names_col: str, types_col: str, new_types) -> bool:
    """Apply one repair and read back; return True iff cardinality now aligns."""
    sb.table("events").update({types_col: new_types}).eq("id", eid).execute()
    rb = (
        sb.table("events").select(f"id,{names_col},{types_col}")
        .eq("id", eid).execute().data
    )
    if not rb:
        return False
    row = rb[0]
    return _card(row.get(names_col)) == _card(row.get(types_col))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--apply", action="store_true",
                        help="Apply auto-fixable repairs + read-back (NOT run this batch).")
    parser.add_argument("--out", default="/tmp",
                        help="Directory for the dry-run JSON manifest (default /tmp).")
    parser.add_argument("--limit", type=int, default=0,
                        help="Cap processed events (0 = all).")
    args = parser.parse_args()

    sb = database._get_client()
    logger.info("Fetching ALL events (paginated; table-wide scope)…")
    events = _fetch_all_events(sb)
    if args.limit:
        events = events[: args.limit]
    fc_map = _load_fc_protected(sb)
    logger.info("Events scanned: %d | events with co/sponsor-type FC: %d",
                len(events), len(fc_map))

    manifest: list[dict[str, Any]] = []
    for ev in events:
        eid = ev.get("id")
        for role, names_col, types_col in ROLES:
            names = ev.get(names_col)
            types = ev.get(types_col)
            if _card(names) == _card(types):
                continue  # aligned — nothing to do

            fc_val = fc_map.get(eid, {}).get(types_col)
            new_types, direction, reasons = _plan(names, types)
            if fc_val is not None:
                category = "fc_protected"
            elif direction == "types_longer_orphan":
                category = "manual_orphan"
            else:
                category = "auto"

            manifest.append({
                "event_id": eid,
                "is_active": bool(ev.get("is_active")),
                "role": role,
                "names": names,
                "current_types": types,
                "names_card": _card(names),
                "types_card": _card(types),
                "proposed_types": new_types,
                "direction": direction,
                "category": category,
                "fc_protected": fc_val is not None,
                "fc_value": fc_val,
                "source_url": ev.get("source_url"),
                "reasons": reasons,
            })

    # ---- distribution ----
    events_hit = {m["event_id"] for m in manifest}
    by_role = Counter(m["role"] for m in manifest)
    by_cat = Counter(m["category"] for m in manifest)
    by_dir = Counter(m["direction"] for m in manifest)
    by_active = Counter("active" if m["is_active"] else "inactive" for m in manifest)
    fc_pairs = sum(1 for m in manifest if m["fc_protected"])

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, f"organizer_type_array_repair_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({
            "generated_at": ts,
            "mode": "apply" if args.apply else "dry-run",
            "events_scanned": len(events),
            "mismatch_pairs": len(manifest),
            "mismatch_events": len(events_hit),
            "by_role": dict(by_role),
            "by_category": dict(by_cat),
            "by_direction": dict(by_dir),
            "by_active": dict(by_active),
            "fc_protected_pairs": fc_pairs,
            "rows": manifest,
        }, fh, ensure_ascii=False, indent=2)

    logger.info("=" * 72)
    logger.info("PARALLEL TYPE-ARRAY REPAIR  (%s)", "APPLY" if args.apply else "DRY-RUN")
    logger.info("  events scanned          : %d (table-wide: active + inactive)", len(events))
    logger.info("  mismatch (event,role)   : %d", len(manifest))
    logger.info("  distinct events         : %d", len(events_hit))
    logger.info("  by role                 : %s", dict(by_role))
    logger.info("  by category             : %s", dict(by_cat))
    logger.info("  by direction            : %s", dict(by_dir))
    logger.info("  by is_active            : %s", dict(by_active))
    logger.info("  FC-protected pairs      : %d", fc_pairs)
    logger.info("  JSON manifest           : %s", out_path)
    logger.info("-" * 72)
    for m in manifest[:40]:
        logger.info(
            "  %s %s %-7s %-18s names=%s(%d) types=%s(%d) -> %s  fc=%s",
            "A" if m["is_active"] else "I",
            m["event_id"][:8], m["role"], m["category"],
            m["names"], m["names_card"], m["current_types"], m["types_card"],
            m["proposed_types"], m["fc_protected"],
        )
    if len(manifest) > 40:
        logger.info("  … %d more (see JSON manifest)", len(manifest) - 40)

    if not args.apply:
        logger.info("-" * 72)
        logger.info("DRY-RUN — no database writes. Re-run with --apply after human "
                    "approval to fix 'auto' rows (manual_orphan / fc_protected are skipped).")
        return

    # ---- apply path (only 'auto' rows; read-back each) ----
    logger.info("-" * 72)
    logger.info("APPLYING auto-fixable repairs…")
    ok = fail = 0
    role_cols = {role: (nc, tc) for role, nc, tc in ROLES}
    for m in manifest:
        if m["category"] != "auto":
            continue
        names_col, types_col = role_cols[m["role"]]
        verified = _apply_row(sb, m["event_id"], names_col, types_col, m["proposed_types"])
        if verified:
            ok += 1
            logger.info("  db=✓ %s %s -> %s", m["event_id"][:8], m["role"], m["proposed_types"])
        else:
            fail += 1
            logger.warning("  db=✗ %s %s read-back mismatch", m["event_id"][:8], m["role"])
    logger.info("APPLY complete: ok=%d fail=%d (manual_orphan + fc_protected left for human review)",
                ok, fail)


if __name__ == "__main__":
    main()
