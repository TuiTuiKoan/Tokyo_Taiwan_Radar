"""One-off cleanup for publication-related pending QA reports.

Scope:
  - source_name in: ndl_opensearch, hanmoto, kawade_rss, eslite_spectrum
  - only pending event_reports
  - conservative handling for eslite_spectrum: only if explicitly matched

Default mode is dry-run. Use --apply to write status updates.
"""

from __future__ import annotations

import argparse
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

TARGET_SOURCES = {
    "ndl_opensearch",
    "hanmoto",
    "kawade_rss",
    "eslite_spectrum",
}

CONFIRM_TYPES = {
    "ndl_opensearch": {"auto_qa_missing_location_name"},
    "hanmoto": {"auto_qa_missing_location_name"},
    "kawade_rss": set(),
    "eslite_spectrum": set(),
}

DISMISS_TYPES = {
    "hanmoto": {"auto_qa_thin_content"},
}


def _supabase_client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _batch(seq: list[str], size: int) -> list[list[str]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def _append_note(existing: str | None, note: str) -> str:
    prev = (existing or "").strip()
    return f"{prev}\n[publication-batch] {note}" if prev else f"[publication-batch] {note}"


def _fetch_pending_reports(sb) -> list[dict]:
    rows = (
        sb.table("event_reports")
        .select("id,event_id,report_types,status,admin_notes,created_at")
        .eq("status", "pending")
        .execute()
    ).data or []

    event_ids = [row.get("event_id") for row in rows if row.get("event_id")]
    event_map: dict[str, dict] = {}
    for chunk in _batch(event_ids, 200):
        events = (
            sb.table("events")
            .select("id,source_name,name_ja,category,event_form")
            .in_("id", chunk)
            .execute()
        ).data or []
        for event in events:
            event_map[event["id"]] = event

    out: list[dict] = []
    for row in rows:
        event = event_map.get(row.get("event_id"))
        if not event:
            continue
        source_name = event.get("source_name")
        if source_name not in TARGET_SOURCES:
            continue
        out.append({"report": row, "event": event})
    return out


def _classify(item: dict) -> str:
    report = item["report"]
    event = item["event"]
    source_name = event.get("source_name")
    types = set(report.get("report_types") or [])

    if source_name in CONFIRM_TYPES and types & CONFIRM_TYPES[source_name]:
        return "confirmed"
    if source_name in DISMISS_TYPES and types & DISMISS_TYPES[source_name]:
        return "dismissed"
    return "manual"


def run(apply_changes: bool = False) -> dict:
    sb = _supabase_client()
    pending = _fetch_pending_reports(sb)

    buckets: dict[str, list[dict]] = defaultdict(list)
    for item in pending:
        buckets[_classify(item)].append(item)

    summary = {
        "pending_total": len(pending),
        "confirmed": len(buckets["confirmed"]),
        "dismissed": len(buckets["dismissed"]),
        "manual": len(buckets["manual"]),
        "by_source": Counter(item["event"]["source_name"] for item in pending),
        "by_type": Counter(t for item in pending for t in (item["report"].get("report_types") or [])),
    }

    print("Publication QA cleanup summary")
    print(f"pending_total={summary['pending_total']}")
    print(f"confirmed={summary['confirmed']}")
    print(f"dismissed={summary['dismissed']}")
    print(f"manual={summary['manual']}")
    print("by_source:")
    for source_name, count in summary["by_source"].most_common():
        print(f"  {source_name}: {count}")
    print("by_type:")
    for report_type, count in summary["by_type"].most_common():
        print(f"  {report_type}: {count}")

    if not apply_changes:
        print("dry-run only; no rows updated")
        return summary

    now_iso = datetime.now(timezone.utc).isoformat()
    for item in buckets["confirmed"]:
        report = item["report"]
        event = item["event"]
        note = _append_note(
            report.get("admin_notes"),
            f"confirmed by publication batch for {event.get('source_name')} / {','.join(report.get('report_types') or [])}",
        )
        sb.table("event_reports").update(
            {
                "status": "confirmed",
                "confirmed_at": now_iso,
                "admin_notes": note,
            }
        ).eq("id", report["id"]).eq("status", "pending").execute()

    for item in buckets["dismissed"]:
        report = item["report"]
        event = item["event"]
        note = _append_note(
            report.get("admin_notes"),
            f"dismissed by publication batch for {event.get('source_name')} / {','.join(report.get('report_types') or [])}",
        )
        sb.table("event_reports").update(
            {
                "status": "dismissed",
                "admin_notes": note,
            }
        ).eq("id", report["id"]).eq("status", "pending").execute()

    print("updates applied")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="One-off publication pending QA cleanup")
    parser.add_argument("--apply", action="store_true", help="Write status updates")
    args = parser.parse_args()
    run(apply_changes=args.apply)


if __name__ == "__main__":
    main()