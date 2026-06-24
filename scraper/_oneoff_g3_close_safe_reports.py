"""_oneoff_g3_close_safe_reports.py — G3.0: stale / structural safe-close.

Reuses the G1 classifier (CONFIRM / DISMISS / LEAVE) but writes its OWN G3
rollback snapshot (tmp/g3_close_safe_reports_YYYYMMDD.json) and [G3] admin_notes
so it NEVER overwrites the G1 rollback snapshot (tmp/g1_closed_ids.json).

Multi-type assertion (R3-G1): classify_report() only returns CONFIRM/DISMISS when
EVERY auto type on the report row is closeable AND there is no human report type;
any unresolved/human type forces LEAVE (the row stays pending with no change).

Scope (STRICT): writes ONLY event_reports.status / admin_notes / confirmed_at.
NEVER touches the events table.

Usage:
    python _oneoff_g3_close_safe_reports.py            # dry-run (default)
    python _oneoff_g3_close_safe_reports.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv

from _oneoff_g1_close_safe_reports import (
    ACTIVITY_PLATFORMS,
    _fetch_all_pending,
    _fetch_events,
    _supabase_client,
    classify_report,
)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

_TODAY = datetime.now(timezone.utc).strftime("%Y%m%d")
_ROLLBACK_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tmp", f"g3_close_safe_reports_{_TODAY}.json"
)
_NOTE_DATE = "2026-06-25"


def _append_note(existing: str | None, reason: str) -> str:
    prev = (existing or "").strip()
    note = f"[G3] auto-close: {reason} {_NOTE_DATE}"
    return f"{prev}\n{note}" if prev else note


def run(apply_changes: bool = False) -> dict:
    sb = _supabase_client()

    exact = (
        sb.table("event_reports").select("id", count="exact", head=True)
        .eq("status", "pending").execute()
    )
    pending = _fetch_all_pending(sb)
    print(f"pending count(exact) = {exact.count}")
    print(f"pending scanned      = {len(pending)}")
    if exact.count != len(pending):
        raise RuntimeError(
            f"pagination incomplete: exact={exact.count} scanned={len(pending)}"
        )

    ids = sorted({r["event_id"] for r in pending if r.get("event_id")})
    events = _fetch_events(sb, ids)
    print(f"events fetched       = {len(events)} (of {len(ids)} unique ids)\n")

    classified: list[dict] = []
    for r in pending:
        c = classify_report(r, events)
        event = events.get(r.get("event_id")) or {}
        classified.append({
            "report_id": r["id"],
            "event_id": r.get("event_id"),
            "source_name": event.get("source_name"),
            "report_types": r.get("report_types") or [],
            **c,
        })

    buckets: dict[str, list[dict]] = defaultdict(list)
    for c in classified:
        buckets[c["decision"]].append(c)
    n_confirm = len(buckets["CONFIRM"])
    n_dismiss = len(buckets["DISMISS"])
    n_leave = len(buckets["LEAVE"])
    closeable = n_confirm + n_dismiss

    print("=" * 72)
    print(f"CONFIRM (stale-resolved) : {n_confirm}")
    print(f"DISMISS                  : {n_dismiss}")
    print(f"LEAVE                    : {n_leave}")
    print(f"closeable (CONFIRM+DISMISS) = {closeable}")
    print(f"total = {n_confirm + n_dismiss + n_leave} (must equal {len(pending)})")
    print("=" * 72)

    for label in ("CONFIRM", "DISMISS"):
        print(f"\n--- {label} list (report_id | event_id | source | types | status | reason) ---")
        for c in sorted(buckets[label], key=lambda x: x["source_name"] or ""):
            print(
                f"  {c['report_id'][:8]} | {c['event_id'][:8]} | {(c['source_name'] or '?'):20s} "
                f"| {','.join(t.replace('auto_qa_', '') for t in c['report_types'])} "
                f"| {c['status']} | {c['reason']}"
            )

    print("\n--- DISMISS by source ---")
    for s, n in Counter(c["source_name"] for c in buckets["DISMISS"]).most_common():
        print(f"  {(s or '?'):24s}: {n}")

    # GATE(b): activity-platform venue reports must NEVER be dismissed.
    plat_venue = [c for c in classified if c["source_name"] in ACTIVITY_PLATFORMS and c["has_venue"]]
    plat_dismissed = [c for c in plat_venue if c["decision"] == "DISMISS"]
    print(f"\n--- GATE(b): activity-platform venue reports = {len(plat_venue)}; "
          f"dismissed = {len(plat_dismissed)} (must be 0) ---")
    if plat_dismissed:
        print("  ❌ GATE(b) VIOLATION")

    # GATE(c): human report types must NEVER be auto-processed.
    human_processed = [c for c in classified if c["has_human"] and c["decision"] != "LEAVE"]
    print(f"--- GATE(c): human reports with type, auto-processed = {len(human_processed)} (must be 0) ---")
    if human_processed:
        print("  ❌ GATE(c) VIOLATION")

    summary = {
        "pending": len(pending), "confirm": n_confirm, "dismiss": n_dismiss,
        "leave": n_leave, "closeable": closeable,
        "gate_b_ok": not plat_dismissed, "gate_c_ok": not human_processed,
    }

    if not apply_changes:
        print("\nDRY-RUN — no rows updated.")
        return summary

    if plat_dismissed or human_processed:
        raise RuntimeError(
            "SAFETY GATE failed (activity-platform venue dismissed or human "
            "report auto-processed) — refusing to --apply."
        )

    rollback = [
        {"report_id": c["report_id"], "prev_status": "pending",
         "new_status": c["status"], "reason": c["reason"]}
        for c in classified if c["decision"] in ("CONFIRM", "DISMISS")
    ]
    os.makedirs(os.path.dirname(_ROLLBACK_PATH), exist_ok=True)
    with open(_ROLLBACK_PATH, "w", encoding="utf-8") as fh:
        json.dump(rollback, fh, ensure_ascii=False, indent=2)
    print(f"\nrollback snapshot ({len(rollback)} rows) → {os.path.normpath(_ROLLBACK_PATH)}")

    now_iso = datetime.now(timezone.utc).isoformat()
    applied = {"confirmed": 0, "dismissed": 0}
    for c in classified:
        if c["decision"] not in ("CONFIRM", "DISMISS"):
            continue
        existing = (
            sb.table("event_reports").select("admin_notes").eq("id", c["report_id"]).single().execute()
        ).data or {}
        update = {"status": c["status"], "admin_notes": _append_note(existing.get("admin_notes"), c["reason"])}
        if c["status"] == "confirmed":
            update["confirmed_at"] = now_iso
        (
            sb.table("event_reports").update(update)
            .eq("id", c["report_id"]).eq("status", "pending").execute()
        )
        applied["confirmed" if c["status"] == "confirmed" else "dismissed"] += 1

    print(f"applied: confirmed={applied['confirmed']} dismissed={applied['dismissed']}")
    summary["applied"] = applied
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="G3.0 — stale/structural safe-close")
    parser.add_argument("--apply", action="store_true", help="write status updates")
    args = parser.parse_args()
    run(apply_changes=args.apply)


if __name__ == "__main__":
    main()
