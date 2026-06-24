"""_oneoff_g3_publication_organizer_reports.py — G3.1: publication organizer reports.

Clears the existing `auto_qa_missing_organizer` backlog for CORE publication
sources {ndl_opensearch, hanmoto}. The auto_qa.py refactor (same commit) stops
NEW such reports being created; this one-off resolves the pre-existing ones.

Per-report decision (CORE publication sources only):
  * BACKFILL  — a publisher is deterministically present VERBATIM in
                raw_description (NDL stores it as ``出版社: <name>``). Set
                events.organizer + FC-lock it, mark the report ``confirmed``.
  * CONFIRM_STALE — organizer is already set (report is stale) → ``confirmed``.
  * DISMISS   — no deterministic publisher in raw text (e.g. hanmoto book
                blurbs). Publications do not require an organizer → ``dismissed``
                with an explanatory admin_note.

NON-core sources (iwafu / peatix / go_taiwan / …) are LEFT UNTOUCHED — they are
G3.2's deterministic raw-hint backfill scope.

Guards:
  * Organizer Non-Hallucination — the written organizer MUST appear verbatim in
    raw_description; otherwise the row is DISMISSed, never fabricated.
  * Multi-type assertion (R3-G1) — a report row carrying any report_type other
    than auto_qa_missing_organizer is LEFT pending (SKIP_MULTI_TYPE).
  * Scope gate — only events.organizer (+ field_corrections lock) and
    event_reports.status/admin_notes/confirmed_at are written. Non-core sources
    are never written (asserted before --apply).

Usage:
    python _oneoff_g3_publication_organizer_reports.py            # dry-run
    python _oneoff_g3_publication_organizer_reports.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv

from _oneoff_g1_close_safe_reports import _fetch_all_pending, _supabase_client
from annotator import _lock_fields_via_corrections, _normalize_publication_publisher

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

_TODAY = datetime.now(timezone.utc).strftime("%Y%m%d")
_ROLLBACK_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tmp",
    f"g3_publication_organizer_reports_{_TODAY}.json",
)
_NOTE_DATE = "2026-06-25"

# Mirror auto_qa._CORE_PUBLICATION_SOURCES — sources whose organizer role is
# filled by the publisher, so a null organizer is not a real gap.
_CORE_PUBLICATION_SOURCES = frozenset({"ndl_opensearch", "hanmoto"})
_ORG_TYPE = "auto_qa_missing_organizer"

# NDL raw_description embeds the publisher as ``出版社: <name>`` followed by two
# spaces and an HTML tag. Capture the name verbatim.
_PUBLISHER_RE = re.compile(r"出版社[:：]\s*([^<\n]+?)(?:\s{2,}|<|\n|$)")

# Reject extraction noise that IS verbatim in raw but is NOT a publisher, so the
# row falls through to DISMISS instead of polluting events.organizer:
#   * a 4-digit run — a date / year / ISBN leaked into an empty 出版社 field
#     (e.g. "2026-03-31"); no JP/ZH publisher name carries a 4-digit run.
#   * a "姓, 名" comma-space — NDL records the AUTHOR in 出版社 for self-published
#     works (e.g. "中尾, 薫"); real publisher names never contain ", ".
#   * a " / " join — a location-polluted run-on (e.g. "<org> / <town>（<pref>）").
_PUBLISHER_REJECT_RE = re.compile(r"\d{4}|[,，]\s|\s[/／]\s")

_EVENT_COLUMNS = "id,source_name,event_form,category,organizer,raw_description"


def _extract_publisher(raw: str | None) -> str | None:
    """Return a clearly-obtained publisher verbatim from raw_description, or None.

    "明確取得" (plan §9.4): only a plausible institutional/company publisher is
    backfilled; date/author/location extraction noise is rejected so the report
    is DISMISSed (the safe fallback) rather than written into events.organizer.
    """
    if not raw:
        return None
    m = _PUBLISHER_RE.search(raw)
    if not m:
        return None
    pub = _normalize_publication_publisher(m.group(1))
    if not pub or pub not in raw:  # Non-Hallucination guard: verbatim in raw text
        return None
    if _PUBLISHER_REJECT_RE.search(pub):  # plausibility guard: reject extraction noise
        return None
    return pub


def _fetch_pub_events(sb, ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 200):
        chunk = ids[i : i + 200]
        for e in (
            sb.table("events").select(_EVENT_COLUMNS).in_("id", chunk).execute()
        ).data or []:
            out[e["id"]] = e
    return out


def _append_note(existing: str | None, reason: str) -> str:
    prev = (existing or "").strip()
    note = f"[G3] {reason} {_NOTE_DATE}"
    return f"{prev}\n{note}" if prev else note


def run(apply_changes: bool = False) -> dict:
    sb = _supabase_client()

    pending = _fetch_all_pending(sb)
    org_rows = [r for r in pending if _ORG_TYPE in (r.get("report_types") or [])]
    print(f"pending total           = {len(pending)}")
    print(f"missing_organizer rows  = {len(org_rows)}")

    ids = sorted({r["event_id"] for r in org_rows if r.get("event_id")})
    events = _fetch_pub_events(sb, ids)
    print(f"events fetched          = {len(events)} (of {len(ids)} unique ids)\n")

    classified: list[dict] = []
    for r in org_rows:
        types = r.get("report_types") or []
        ev = events.get(r.get("event_id")) or {}
        src = ev.get("source_name")
        decision = status = reason = None
        publisher = None

        if src not in _CORE_PUBLICATION_SOURCES:
            decision, status = "SKIP_OUT_OF_SCOPE", "pending"
            reason = f"non-core publication source ({src}) → G3.2 scope"
        elif any(t != _ORG_TYPE for t in types):
            decision, status = "SKIP_MULTI_TYPE", "pending"
            reason = f"multi-type row {types} → leave for review"
        elif ev.get("organizer"):
            decision, status = "CONFIRM_STALE", "confirmed"
            reason = "publication organizer backfill: organizer already set (stale report)"
        else:
            publisher = _extract_publisher(ev.get("raw_description"))
            if publisher:
                decision, status = "BACKFILL", "confirmed"
                reason = f"publication organizer backfill: organizer={publisher} (raw 出版社, FC-locked)"
            else:
                decision, status = "DISMISS", "dismissed"
                reason = (
                    "publication organizer QA skip: core publication source, "
                    "organizer not required / publisher unavailable"
                )

        classified.append({
            "report_id": r["id"],
            "event_id": r.get("event_id"),
            "source_name": src,
            "report_types": types,
            "decision": decision,
            "status": status,
            "reason": reason,
            "publisher": publisher,
        })

    buckets: dict[str, list[dict]] = defaultdict(list)
    for c in classified:
        buckets[c["decision"]].append(c)
    n_backfill = len(buckets["BACKFILL"])
    n_stale = len(buckets["CONFIRM_STALE"])
    n_dismiss = len(buckets["DISMISS"])
    n_oos = len(buckets["SKIP_OUT_OF_SCOPE"])
    n_multi = len(buckets["SKIP_MULTI_TYPE"])
    closeable = n_backfill + n_stale + n_dismiss

    print("=" * 72)
    print(f"BACKFILL (organizer set, confirmed) : {n_backfill}")
    print(f"CONFIRM_STALE (already set)         : {n_stale}")
    print(f"DISMISS (not required)              : {n_dismiss}")
    print(f"SKIP_OUT_OF_SCOPE (G3.2)            : {n_oos}")
    print(f"SKIP_MULTI_TYPE (leave)             : {n_multi}")
    print(f"closeable (BACKFILL+STALE+DISMISS)  = {closeable}")
    print(f"total = {len(classified)} (must equal {len(org_rows)})")
    print("=" * 72)

    print("\n--- BACKFILL list (report | event | source | organizer) ---")
    for c in sorted(buckets["BACKFILL"], key=lambda x: x["source_name"] or ""):
        print(f"  {c['report_id'][:8]} | {c['event_id'][:8]} | {(c['source_name'] or '?'):16s} | {c['publisher']}")

    print("\n--- DISMISS by source ---")
    for s, n in Counter(c["source_name"] for c in buckets["DISMISS"]).most_common():
        print(f"  {(s or '?'):20s}: {n}")

    print("\n--- SKIP_OUT_OF_SCOPE by source (G3.2 will handle) ---")
    for s, n in Counter(c["source_name"] for c in buckets["SKIP_OUT_OF_SCOPE"]).most_common():
        print(f"  {(s or '?'):20s}: {n}")

    # GATE: out-of-scope / multi-type rows must remain pending (no write).
    bad_scope = [c for c in classified if c["decision"].startswith("SKIP_") and c["status"] != "pending"]
    print(f"\n--- GATE: SKIP rows with non-pending status = {len(bad_scope)} (must be 0) ---")
    # GATE: a BACKFILL publisher MUST be verbatim in raw (re-assert post-classification).
    backfill_bad = [
        c for c in buckets["BACKFILL"]
        if not c["publisher"] or c["publisher"] not in (events.get(c["event_id"], {}).get("raw_description") or "")
    ]
    print(f"--- GATE: BACKFILL with non-verbatim organizer = {len(backfill_bad)} (must be 0) ---")

    summary = {
        "missing_organizer_rows": len(org_rows),
        "backfill": n_backfill, "confirm_stale": n_stale, "dismiss": n_dismiss,
        "out_of_scope": n_oos, "multi_type": n_multi, "closeable": closeable,
        "gate_scope_ok": not bad_scope, "gate_verbatim_ok": not backfill_bad,
    }

    if not apply_changes:
        print("\nDRY-RUN — no rows updated.")
        return summary

    if bad_scope or backfill_bad:
        raise RuntimeError(
            "SAFETY GATE failed (SKIP row marked closeable, or non-verbatim "
            "organizer) — refusing to --apply."
        )

    rollback = {
        "reports": [
            {"report_id": c["report_id"], "event_id": c["event_id"],
             "prev_status": "pending", "new_status": c["status"],
             "decision": c["decision"], "reason": c["reason"]}
            for c in classified if c["decision"] in ("BACKFILL", "CONFIRM_STALE", "DISMISS")
        ],
        "events": [
            {"event_id": c["event_id"], "field": "organizer",
             "prev": None, "new": c["publisher"]}
            for c in buckets["BACKFILL"]
        ],
    }
    os.makedirs(os.path.dirname(_ROLLBACK_PATH), exist_ok=True)
    with open(_ROLLBACK_PATH, "w", encoding="utf-8") as fh:
        json.dump(rollback, fh, ensure_ascii=False, indent=2)
    print(
        f"\nrollback snapshot (reports={len(rollback['reports'])} "
        f"events={len(rollback['events'])}) → {os.path.normpath(_ROLLBACK_PATH)}"
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    applied = {"backfilled": 0, "confirmed": 0, "dismissed": 0}
    for c in classified:
        if c["decision"] not in ("BACKFILL", "CONFIRM_STALE", "DISMISS"):
            continue
        # 1. events.organizer write (BACKFILL only), guarded null + FC lock.
        if c["decision"] == "BACKFILL":
            (
                sb.table("events").update({"organizer": c["publisher"]})
                .eq("id", c["event_id"]).is_("organizer", "null").execute()
            )
            _lock_fields_via_corrections(sb, c["event_id"], {"organizer": c["publisher"]})
            applied["backfilled"] += 1
        # 2. report status write (optimistic: only while still pending).
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

    print(
        f"applied: backfilled={applied['backfilled']} "
        f"confirmed={applied['confirmed']} dismissed={applied['dismissed']}"
    )
    summary["applied"] = applied
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="G3.1 — publication organizer reports")
    parser.add_argument("--apply", action="store_true", help="write organizer + report updates")
    args = parser.parse_args()
    run(apply_changes=args.apply)


if __name__ == "__main__":
    main()
