"""One-off: close stale auto_qa_missing_date reports on publication records.

NDL bibliographies supply only a publication year, so `_parse_issued_date("2026")`
normalises to 2026-01-01. The January placeholder heuristic in
`_check_missing_date` used to flag those as missing dates. The predicate now
exempts exact pure publications; this script closes the reports that predicate
change already invalidated.

Dry-run by default. `--apply` writes. Never touches the `events` table.
"""

from __future__ import annotations

import argparse
import os
from collections import Counter

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

from auto_qa import _check_missing_date, _is_exact_pure_publication, close_report_exactly_one

TARGET_TYPE = "auto_qa_missing_date"
DISMISS_NOTE = (
    "auto-closed: publication 年份日期（YYYY-01-01），非 Contentful 佔位符；"
    "_check_missing_date 已豁免 exact pure publication"
)


def _supabase_client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _fetch_pending(sb) -> list[dict]:
    rows: list[dict] = []
    off = 0
    while True:
        batch = (
            sb.table("event_reports")
            .select("id,event_id,report_types,status,created_at")
            .eq("status", "pending")
            .range(off, off + 999)
            .execute()
            .data
            or []
        )
        rows.extend(batch)
        if len(batch) < 1000:
            break
        off += 1000
    return [r for r in rows if TARGET_TYPE in (r.get("report_types") or [])]


def _fetch_events(sb, event_ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(event_ids), 200):
        chunk = event_ids[i : i + 200]
        rows = (
            sb.table("events")
            .select("id,source_name,start_date,event_form,is_active,annotation_status")
            .in_("id", chunk)
            .execute()
            .data
            or []
        )
        for row in rows:
            out[row["id"]] = row
    return out


def _classify(report: dict, event: dict | None) -> tuple[str, str]:
    types = [t for t in (report.get("report_types") or []) if isinstance(t, str) and t]
    if types != [TARGET_TYPE]:
        return "SKIP_MULTI_TYPE", f"report_types={types}"
    if event is None:
        return "SKIP_EVENT_MISSING", "event row not found"
    note = _check_missing_date(event)
    if note is not None:
        return "KEEP", f"predicate still fires: {note}"
    if _is_exact_pure_publication(event):
        return "DISMISS", "pure publication year-only date"
    return "DISMISS", "predicate no longer fires"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    args = parser.parse_args()
    dry_run = not args.apply

    sb = _supabase_client()
    reports = _fetch_pending(sb)
    events = _fetch_events(sb, sorted({r["event_id"] for r in reports if r.get("event_id")}))

    print(f"mode = {'DRY-RUN' if dry_run else 'APPLY'}")
    print(f"pending reports carrying {TARGET_TYPE}: {len(reports)}")
    print("-" * 100)

    tally: Counter[str] = Counter()
    to_dismiss: list[tuple[dict, str]] = []

    for report in sorted(reports, key=lambda r: (r.get("created_at") or "", r["id"])):
        event = events.get(report.get("event_id"))
        decision, reason = _classify(report, event)
        tally[decision] += 1
        src = (event or {}).get("source_name", "?")
        start = (event or {}).get("start_date")
        form = (event or {}).get("event_form")
        print(
            f"{decision:<18} event={report.get('event_id')} src={src} "
            f"start_date={start!r} event_form={form} :: {reason}"
        )
        if decision == "DISMISS":
            to_dismiss.append((report, reason))

    print("-" * 100)
    for decision, count in sorted(tally.items()):
        print(f"{decision}: {count}")

    if dry_run:
        print(f"\nDRY-RUN — no writes. Would dismiss {len(to_dismiss)} report(s). Re-run with --apply.")
        return

    ok_count = 0
    fail_count = 0
    for report, _reason in to_dismiss:
        ok, updated = close_report_exactly_one(
            sb, report["id"], status="dismissed", note=DISMISS_NOTE, dry_run=False
        )
        if ok:
            ok_count += 1
        else:
            fail_count += 1
            print(f"  FAILED report={report['id']} updated_rows={updated}")
    print(f"\nAPPLIED — dismissed={ok_count} failed={fail_count}")


if __name__ == "__main__":
    main()
