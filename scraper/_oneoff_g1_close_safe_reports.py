"""_oneoff_g1_close_safe_reports.py — G1: safely close stale auto_qa pending reports.

Scope (STRICT):
  - Reads ALL pending rows of `event_reports` (paginated via .range()).
  - Joins the corresponding `events` row.
  - Classifies each report as CONFIRM / DISMISS / LEAVE per the G1 rules.
  - On --apply, updates ONLY event_reports.status / confirmed_at / admin_notes.
    NEVER touches the `events` table.

Classification (report-level, see aggregation rule at bottom):
  CONFIRM (stale-resolved): the report's mapped event field now has a value.
  DISMISS (inactive):       event.is_active is False.
  DISMISS (structural no-venue, allow-list only): a venue-type report whose
    event is a structurally venue-less source (publication / broadcast / news /
    online / Taiwan-overseas address).
  LEAVE: everything else — including activity-platform (peatix/kokuchpro/...)
    venue gaps (NEVER auto-dismissed), human report types, and grey-area gaps.

Aggregation: a report is closed only when EVERY auto_qa type on it is closeable
(CONFIRM or DISMISS). Any LEAVE type, or any human report type, forces LEAVE.

Usage:
    python _oneoff_g1_close_safe_reports.py            # dry-run (default)
    python _oneoff_g1_close_safe_reports.py --apply     # write status updates
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv

from auto_qa import PLACEHOLDER_TITLE_RE, _TAIWAN_ADDR_RE

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

_ROLLBACK_PATH = os.path.join(os.path.dirname(__file__), "..", "tmp", "g1_closed_ids.json")
_DRYRUN_DUMP_PATH = os.path.join(os.path.dirname(__file__), "..", "tmp", "g1_dryrun_classification.json")

# Report types that map to an event field; if that field now has a value the
# report is stale-resolved → CONFIRM.
CONFIRM_FIELD = {
    "auto_qa_missing_organizer": "organizer",
    "auto_qa_missing_prefectures": "location_prefectures",
    "auto_qa_missing_date": "start_date",
    "auto_qa_missing_location_name": "location_name",
    "auto_qa_missing_address": "location_address",
    "auto_qa_missing_hours": "business_hours",
    "auto_qa_missing_performers": "performers",
    "auto_qa_missing_title": "name_ja",
    "auto_qa_missing_category": "category",
}

# Venue-type reports eligible for structural no-venue DISMISS.
VENUE_TYPES = frozenset({
    "auto_qa_missing_prefectures",
    "auto_qa_missing_address",
    "auto_qa_missing_location_name",
    "auto_qa_missing_hours",
})

ARRAY_FIELDS = frozenset({"location_prefectures", "performers", "category"})

# Structural no-venue allow-list (G1 — NARROWER than G4's _NO_VENUE_QA_SOURCES).
PUB_SOURCES = frozenset({"hanmoto", "ndl_opensearch"})
BROADCAST_SOURCES = frozenset({"gguide_tv"})
NEWS_SOURCES = frozenset({"google_news_rss", "nhk_rss"})
_ONLINE_RE = re.compile(r"オンライン|online|zoom|配信", re.IGNORECASE)

# Activity platforms: venue gaps here are data-extraction gaps, NOT structural —
# NEVER auto-dismissed (kept for explicit gate reporting only).
ACTIVITY_PLATFORMS = frozenset({"peatix", "kokuchpro", "doorkeeper", "connpass"})

EVENT_COLUMNS = (
    "id,source_name,is_active,location_name,location_address,location_prefectures,"
    "organizer,start_date,business_hours,performers,name_ja,category,event_form"
)


def _supabase_client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _fetch_all_pending(sb) -> list[dict]:
    rows, off, page = [], 0, 1000
    while True:
        batch = (
            sb.table("event_reports")
            .select("id,event_id,report_types,status,admin_notes,created_at")
            .eq("status", "pending")
            .range(off, off + page - 1)
            .execute()
        ).data or []
        rows += batch
        if len(batch) < page:
            break
        off += page
    return rows


def _fetch_events(sb, ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 200):
        chunk = ids[i : i + 200]
        for e in (
            sb.table("events").select(EVENT_COLUMNS).in_("id", chunk).execute()
        ).data or []:
            out[e["id"]] = e
    return out


def _is_human_type(t: str) -> bool:
    """Anything not an auto_qa_* type or annotation_error_stuck is a human report."""
    return not (t.startswith("auto_qa_") or t == "annotation_error_stuck")


def _has_value(field: str, event: dict) -> bool:
    v = event.get(field)
    if field in ARRAY_FIELDS:
        if isinstance(v, str):
            return v.strip() not in ("", "[]", "null")
        return bool(v)
    if field == "name_ja":
        s = (v or "").strip()
        return bool(s) and not PLACEHOLDER_TITLE_RE.match(s)
    if isinstance(v, str):
        return bool(v.strip())
    return v is not None


def _structural_no_venue(event: dict, report_type: str) -> tuple[bool, str]:
    src = event.get("source_name")
    cat = event.get("category") or []
    loc_name = event.get("location_name") or ""
    loc_addr = event.get("location_address") or ""
    if src in PUB_SOURCES or "books_media" in cat:
        return True, "publication"
    if src in BROADCAST_SOURCES:
        return True, "broadcast"
    if src in NEWS_SOURCES:
        return True, "news"
    if _ONLINE_RE.search(loc_name):
        return True, "online venue"
    if report_type == "auto_qa_missing_prefectures" and _TAIWAN_ADDR_RE.search(loc_addr):
        return True, "taiwan/overseas address"
    return False, ""


def _classify_auto_type(t: str, event: dict) -> tuple[str, str]:
    """Classify a single auto-type for an active event → (decision, reason)."""
    if t == "annotation_error_stuck":
        return "LEAVE", "annotation_error_stuck → error_recovery"
    if t not in CONFIRM_FIELD:
        return "LEAVE", f"{t} not auto-closeable by G1"
    field = CONFIRM_FIELD[t]
    if _has_value(field, event):
        return "CONFIRM", f"{t}: {field} now set"
    if t in VENUE_TYPES:
        ok, why = _structural_no_venue(event, t)
        if ok:
            return "DISMISS", f"{t}: structural no-venue ({why})"
    return "LEAVE", f"{t}: {field} still empty"


def classify_report(report: dict, events: dict[str, dict]) -> dict:
    """Return {decision: CONFIRM|DISMISS|LEAVE, status, reason, has_human, has_venue}."""
    types = report.get("report_types") or []
    has_human = any(_is_human_type(t) for t in types)
    venue_types = [t for t in types if t in VENUE_TYPES]
    event = events.get(report.get("event_id"))

    if has_human:
        return {"decision": "LEAVE", "status": "pending", "has_human": True,
                "has_venue": bool(venue_types),
                "reason": "contains human report type: "
                          + ",".join(t for t in types if _is_human_type(t))}

    if event is None:
        return {"decision": "LEAVE", "status": "pending", "has_human": False,
                "has_venue": bool(venue_types), "reason": "event not found"}

    # DISMISS (inactive) — applies to all auto types on a hidden event.
    if event.get("is_active") is False:
        return {"decision": "DISMISS", "status": "dismissed", "has_human": False,
                "has_venue": bool(venue_types), "reason": "event is_active=false"}

    per = [(_classify_auto_type(t, event)) for t in types]
    decisions = [d for d, _ in per]
    reasons = "; ".join(r for _, r in per)

    if per and all(d in ("CONFIRM", "DISMISS") for d in decisions):
        # Mixed within a single report is essentially nonexistent here; if any
        # type is genuinely resolved (CONFIRM) prefer confirmed, else dismissed.
        final = "CONFIRM" if "CONFIRM" in decisions else "DISMISS"
        return {"decision": final,
                "status": "confirmed" if final == "CONFIRM" else "dismissed",
                "has_human": False, "has_venue": bool(venue_types), "reason": reasons}

    return {"decision": "LEAVE", "status": "pending", "has_human": False,
            "has_venue": bool(venue_types), "reason": reasons}


def _append_note(existing: str | None, reason: str) -> str:
    prev = (existing or "").strip()
    note = f"[G1] auto-close: {reason} 2026-06-22"
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

    # --- full audit dump (read-only file) ---
    os.makedirs(os.path.dirname(_DRYRUN_DUMP_PATH), exist_ok=True)
    with open(_DRYRUN_DUMP_PATH, "w", encoding="utf-8") as fh:
        json.dump(classified, fh, ensure_ascii=False, indent=2, default=str)

    print("=" * 72)
    print(f"CONFIRM (stale-resolved) : {n_confirm}")
    print(f"DISMISS                  : {n_dismiss}")
    print(f"LEAVE                    : {n_leave}")
    print(f"closeable (CONFIRM+DISMISS) = {closeable}")
    print(f"total = {n_confirm + n_dismiss + n_leave} (must equal {len(pending)})")
    print("=" * 72)

    print("\n--- CONFIRM list (report_id | event_id | source | types | reason) ---")
    for c in sorted(buckets["CONFIRM"], key=lambda x: x["source_name"] or ""):
        print(f"  {c['report_id'][:8]} | {c['event_id'][:8]} | {c['source_name']:20s} "
              f"| {','.join(t.replace('auto_qa_', '') for t in c['report_types'])} | {c['reason']}")

    print("\n--- DISMISS list (report_id | event_id | source | types | reason) ---")
    for c in sorted(buckets["DISMISS"], key=lambda x: x["source_name"] or ""):
        print(f"  {c['report_id'][:8]} | {c['event_id'][:8]} | {c['source_name']:20s} "
              f"| {','.join(t.replace('auto_qa_', '') for t in c['report_types'])} | {c['reason']}")

    print("\n--- DISMISS by source ---")
    for s, n in Counter(c["source_name"] for c in buckets["DISMISS"]).most_common():
        print(f"  {s:24s}: {n}")

    print("\n--- LEAVE by reason (histogram) ---")
    leave_reason = Counter(c["reason"].split(";")[0].strip() for c in buckets["LEAVE"])
    for reason, n in leave_reason.most_common(25):
        print(f"  {n:4d}  {reason}")

    # --- GATE (b): peatix venue-type report dispositions ---
    peatix_venue = [c for c in classified
                    if c["source_name"] in ACTIVITY_PLATFORMS and c["has_venue"]]
    peatix_dismissed = [c for c in peatix_venue if c["decision"] == "DISMISS"]
    print("\n--- GATE(b): activity-platform venue-type report dispositions ---")
    print(f"  activity-platform venue reports: {len(peatix_venue)}")
    print(f"    CONFIRM: {sum(1 for c in peatix_venue if c['decision']=='CONFIRM')} "
          f"| DISMISS: {len(peatix_dismissed)} "
          f"| LEAVE: {sum(1 for c in peatix_venue if c['decision']=='LEAVE')}")
    for c in peatix_venue:
        print(f"    {c['report_id'][:8]} | {c['source_name']} | "
              f"{','.join(t.replace('auto_qa_','') for t in c['report_types'])} | "
              f"{c['decision']} | {c['reason']}")
    if peatix_dismissed:
        print("  ❌ GATE(b) VIOLATION: activity-platform venue report(s) DISMISSED")

    # --- GATE (c): no human report auto-processed ---
    human_processed = [c for c in classified
                       if c["has_human"] and c["decision"] != "LEAVE"]
    print("\n--- GATE(c): human report types ---")
    print(f"  reports with human types: {sum(1 for c in classified if c['has_human'])}")
    print(f"  human reports auto-processed (must be 0): {len(human_processed)}")
    if human_processed:
        print("  ❌ GATE(c) VIOLATION: human report(s) auto-processed")

    # --- GATE (a): closeable range ---
    gate_a = 60 <= closeable <= 150
    print(f"\n--- GATE(a): closeable in [60,150]? {closeable} → {'OK' if gate_a else 'OUT OF RANGE'}")
    print(f"\nfull classification dump → {os.path.normpath(_DRYRUN_DUMP_PATH)}")

    summary = {
        "pending": len(pending), "confirm": n_confirm, "dismiss": n_dismiss,
        "leave": n_leave, "closeable": closeable,
        "gate_a": gate_a, "gate_b_ok": not peatix_dismissed,
        "gate_c_ok": not human_processed,
    }

    if not apply_changes:
        print("\nDRY-RUN — no rows updated.")
        return summary

    # Hard safety invariants (never overridable): never dismiss an activity-
    # platform venue report; never auto-process a human report.
    if peatix_dismissed or human_processed:
        raise RuntimeError(
            "SAFETY GATE failed (activity-platform venue dismissed or human "
            "report auto-processed) — refusing to --apply."
        )
    # GATE(a) is a sanity band only; proceeding here is under explicit user
    # approval (composition verified: all DISMISS are structural no-venue).
    if not gate_a:
        print(f"\nWARNING: GATE(a) closeable={closeable} outside [60,150] — "
              "proceeding under explicit user approval (2026-06-22).")

    # rollback snapshot BEFORE any write
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
        note = _append_note_for(sb, c["report_id"], c["reason"])
        update = {"status": c["status"], "admin_notes": note}
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


def _append_note_for(sb, report_id: str, reason: str) -> str:
    existing = (
        sb.table("event_reports").select("admin_notes").eq("id", report_id).single().execute()
    ).data or {}
    return _append_note(existing.get("admin_notes"), reason)


def main() -> None:
    parser = argparse.ArgumentParser(description="G1 — safely close stale auto_qa pending reports")
    parser.add_argument("--apply", action="store_true", help="write status updates")
    args = parser.parse_args()
    run(apply_changes=args.apply)


if __name__ == "__main__":
    main()
