"""
qa_auto_fix.py — Safe one-click QA auto fixes.

Scope (safe only):
  1) Simplified->Traditional fix for auto_qa findings
     - applies to zh text fields + selection_reason.zh
     - locks updated fields in field_corrections
     - closes matched pending event_reports as confirmed
  2) tokyoartbeat date-sync
     - aligns events.start_date with date in source_url (.../YYYY-MM-DD)
     - locks start_date in field_corrections

Usage:
    python qa_auto_fix.py
    python qa_auto_fix.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv

from annotator import _lock_fields_via_corrections, _to_trad
from line_notify import send_line_message

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
SAFE_REPORT_TYPES = ("auto_qa_simplified_zh", "auto_simplified_chinese")
FIX_FIELDS = (
    "name_zh",
    "description_zh",
    "location_name_zh",
    "location_address_zh",
    "business_hours_zh",
    "organizer_zh",
)
DATE_IN_TAB_URL_RE = re.compile(r"/(\d{4}-\d{2}-\d{2})$")


def _supabase_client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _pending_simplified_report_event_ids(sb) -> set[str]:
    event_ids: set[str] = set()
    for report_type in SAFE_REPORT_TYPES:
        rows = (
            sb.table("event_reports")
            .select("event_id")
            .eq("status", "pending")
            .contains("report_types", [report_type])
            .execute()
        ).data or []
        for row in rows:
            eid = row.get("event_id")
            if eid:
                event_ids.add(eid)
    return event_ids


def _fix_simplified_for_events(sb, event_ids: set[str], dry_run: bool) -> dict:
    if not event_ids:
        return {
            "pending_events": 0,
            "scanned": 0,
            "fixed_events": 0,
            "closed_reports": 0,
            "fixed_fields": 0,
        }

    rows: list[dict] = []
    event_id_list = sorted(event_ids)
    for i in range(0, len(event_id_list), 200):
        chunk = event_id_list[i : i + 200]
        chunk_rows = (
            sb.table("events")
            .select("id," + ",".join(FIX_FIELDS) + ",selection_reason")
            .in_("id", chunk)
            .eq("is_active", True)
            .execute()
        ).data or []
        rows.extend(chunk_rows)

    fixed_events = 0
    fixed_fields = 0
    fixed_ids: list[str] = []

    for row in rows:
        update: dict[str, Any] = {}

        for field in FIX_FIELDS:
            val = row.get(field) or ""
            if not val:
                continue
            converted = _to_trad(val)
            if converted != val:
                update[field] = converted

        sr = row.get("selection_reason")
        if sr:
            try:
                sr_dict = json.loads(sr) if isinstance(sr, str) else sr
                zh_val = sr_dict.get("zh", "") if isinstance(sr_dict, dict) else ""
                if zh_val:
                    converted_zh = _to_trad(zh_val)
                    if converted_zh != zh_val:
                        sr_dict["zh"] = converted_zh
                        update["selection_reason"] = json.dumps(sr_dict, ensure_ascii=False)
            except (ValueError, TypeError, AttributeError):
                pass

        if not update:
            continue

        if dry_run:
            logger.info("[DRY] simplified fix %s fields=%s", row["id"][:8], list(update.keys()))
        else:
            sb.table("events").update(update).eq("id", row["id"]).execute()
            _lock_fields_via_corrections(sb, row["id"], update)

        fixed_events += 1
        fixed_fields += len(update)
        fixed_ids.append(row["id"])

    closed_reports = 0
    if fixed_ids:
        now_iso = datetime.now(timezone.utc).isoformat()
        if dry_run:
            for report_type in SAFE_REPORT_TYPES:
                logger.info(
                    "[DRY] would confirm pending reports type=%s for %d event(s)",
                    report_type,
                    len(fixed_ids),
                )
        else:
            for report_type in SAFE_REPORT_TYPES:
                res = (
                    sb.table("event_reports")
                    .update({"status": "confirmed", "confirmed_at": now_iso})
                    .eq("status", "pending")
                    .contains("report_types", [report_type])
                    .in_("event_id", fixed_ids)
                    .execute()
                )
                closed_reports += len(res.data or [])

    return {
        "pending_events": len(event_ids),
        "scanned": len(rows),
        "fixed_events": fixed_events,
        "closed_reports": closed_reports,
        "fixed_fields": fixed_fields,
    }


def _tokyoartbeat_mismatches(sb) -> list[dict]:
    rows = (
        sb.table("events")
        .select("id,name_ja,start_date,source_url")
        .eq("source_name", "tokyoartbeat")
        .eq("is_active", True)
        .not_.is_("start_date", None)
        .execute()
    ).data or []

    mismatch: list[dict] = []
    for row in rows:
        m = DATE_IN_TAB_URL_RE.search(row.get("source_url") or "")
        if not m:
            continue
        url_date = m.group(1)
        db_date = (row.get("start_date") or "")[:10]
        if db_date and db_date != url_date:
            mismatch.append(
                {
                    "id": row["id"],
                    "name_ja": row.get("name_ja") or "",
                    "db_date": db_date,
                    "url_date": url_date,
                }
            )
    return mismatch


def _fix_tokyoartbeat_dates(sb, dry_run: bool) -> dict:
    mismatch = _tokyoartbeat_mismatches(sb)
    fixed = 0

    for row in mismatch:
        event_id = row["id"]
        target_date = row["url_date"]
        if dry_run:
            logger.info(
                "[DRY] tokyoartbeat date-sync %s %s -> %s",
                event_id[:8],
                row["db_date"],
                target_date,
            )
        else:
            sb.table("events").update({"start_date": target_date}).eq("id", event_id).execute()
            _lock_fields_via_corrections(sb, event_id, {"start_date": target_date})
        fixed += 1

    return {
        "mismatch": len(mismatch),
        "fixed": fixed,
    }


def _build_message(today_jst: str, summary: dict) -> str:
    simp = summary["simplified_fix"]
    tab = summary["tokyoartbeat_date_sync"]

    lines = [
        f"🛠️ QA Auto Fix（{today_jst}）",
        "",
        "A) 簡轉繁修復（auto_qa）",
        f"- pending events: {simp['pending_events']}",
        f"- scanned events: {simp['scanned']}",
        f"- fixed events: {simp['fixed_events']}",
        f"- fixed fields: {simp['fixed_fields']}",
        f"- confirmed reports: {simp['closed_reports']}",
        "",
        "B) tokyoartbeat date-sync",
        f"- mismatch found: {tab['mismatch']}",
        f"- fixed: {tab['fixed']}",
    ]
    return "\n".join(lines)


def run(dry_run: bool = False) -> dict:
    sb = _supabase_client()
    today_jst = datetime.now(timezone.utc).astimezone(JST).strftime("%Y/%m/%d")

    pending_event_ids = _pending_simplified_report_event_ids(sb)
    simplified_summary = _fix_simplified_for_events(sb, pending_event_ids, dry_run=dry_run)
    tab_summary = _fix_tokyoartbeat_dates(sb, dry_run=dry_run)

    summary = {
        "simplified_fix": simplified_summary,
        "tokyoartbeat_date_sync": tab_summary,
    }
    message = _build_message(today_jst, summary)

    logger.info("QA auto-fix summary: %s", summary)
    if dry_run:
        print("\n--- QA AUTO FIX (dry-run) LINE preview ---")
        print(message)
        print("--- end ---\n")
    else:
        send_line_message(message)
        logger.info("QA auto-fix LINE message sent")

    return {"summary": summary, "message": message}


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe one-click QA auto-fix")
    parser.add_argument("--dry-run", action="store_true", help="Preview only; no DB writes, no LINE")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
