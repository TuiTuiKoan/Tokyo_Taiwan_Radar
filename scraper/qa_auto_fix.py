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

# Report types handled by the existing simplified-Chinese auto-fix path
# (events.run() + _fix_simplified_for_events). Closing these reports is safe
# because the SC→TC handler always runs to completion before confirming.
SIMPLIFIED_REPORT_TYPES = (
    "auto_qa_simplified_zh",
    "auto_simplified_chinese",
)

# Broader allow-list of QA report types that the qa_heartbeat orchestrator
# may auto-handle via HANDLER_MAP. Adding a report type here without also
# providing a handler is a no-op (and a bug — the heartbeat will skip it).
SAFE_REPORT_TYPES = SIMPLIFIED_REPORT_TYPES + (
    "auto_qa_performer_ai_translation_marker",
    "auto_qa_performer_multi_value_pollution",
)

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
    for report_type in SIMPLIFIED_REPORT_TYPES:
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
            for report_type in SIMPLIFIED_REPORT_TYPES:
                logger.info(
                    "[DRY] would confirm pending reports type=%s for %d event(s)",
                    report_type,
                    len(fixed_ids),
                )
        else:
            for report_type in SIMPLIFIED_REPORT_TYPES:
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


# ---------------------------------------------------------------------------
# qa_heartbeat integration — helpers + per-report handlers + audit-aware write.
#
# These are imported by `qa_heartbeat.py`. They are NOT called by the existing
# daily `run()` flow above, which keeps its simpler "fix all + close all"
# behaviour for the SC→TC path.
# ---------------------------------------------------------------------------

_PERFORMER_SEP_RE = re.compile(r"[、,，×／/]")
_PERFORMER_ROLE_SUFFIX_RE = re.compile(
    r"[（(](?:監督|主演|出演|演出|脚本|製作|ゲスト|ナレーター|MC|司会|プロデューサー|ディレクター)[)）]"
)
_AI_MARKER_ZH = "（AI翻譯）"
_AI_MARKER_EN = "(AI Translation)"


def _split_performer_str(raw: str) -> list[str]:
    """Mirror of `_oneoff_migrate_multi_performer._split_performer`.
    Kept local to avoid coupling qa_auto_fix to a one-off script."""
    parts = [p.strip() for p in _PERFORMER_SEP_RE.split(raw) if p.strip()]
    cleaned = [_PERFORMER_ROLE_SUFFIX_RE.sub("", p).strip() for p in parts]
    seen: set[str] = set()
    out: list[str] = []
    for p in cleaned:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _confirm_report(sb, report_id: str, note: str | None = None, *, dry_run: bool = False) -> None:
    """Mark a pending event_report as confirmed. Idempotent — safe to call
    multiple times for the same report id."""
    if not report_id:
        return
    if dry_run:
        logger.info("[DRY] would confirm report %s — %s", report_id[:8], note or "")
        return
    update: dict[str, Any] = {
        "status": "confirmed",
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    if note:
        update["admin_notes"] = note
    sb.table("event_reports").update(update).eq("id", report_id).eq("status", "pending").execute()


def _append_report_note(sb, report_id: str, note: str, *, dry_run: bool = False) -> None:
    """Append a line to the report's admin_notes — used when verification fails
    or the deterministic rule rejects an apparent false-positive."""
    if not report_id or not note:
        return
    if dry_run:
        logger.info("[DRY] would append note to report %s — %s", report_id[:8], note)
        return
    existing = (
        sb.table("event_reports")
        .select("admin_notes")
        .eq("id", report_id)
        .single()
        .execute()
    ).data or {}
    prev = (existing.get("admin_notes") or "").strip()
    merged = f"{prev}\n[heartbeat] {note}" if prev else f"[heartbeat] {note}"
    sb.table("event_reports").update({"admin_notes": merged}).eq("id", report_id).execute()


def _audit_start(
    sb,
    *,
    event_id: str,
    field_name: str,
    report_id: str | None,
    unlock_reason: str,
    r_class: str | None,
    model_used: str | None,
    confidence: float | None,
    event_before_value: Any,
    fc_before: dict | None,
    dry_run: bool,
) -> str | None:
    """Write the `started` audit row before mutating. Returns audit id."""
    payload: dict[str, Any] = {
        "event_id": event_id,
        "field_name": field_name,
        "report_id": report_id,
        "unlock_reason": unlock_reason,
        "r_class": r_class,
        "model_used": model_used,
        "confidence": confidence,
        "event_before_value_json": event_before_value,
        "operation_status": "started",
    }
    if fc_before:
        payload["fc_before_original_value"] = fc_before.get("original_value")
        payload["fc_before_corrected_value"] = fc_before.get("corrected_value")
        payload["fc_before_corrected_by"] = fc_before.get("corrected_by")
        payload["fc_before_report_id"] = fc_before.get("report_id")
    if dry_run:
        logger.info("[DRY] audit start %s.%s reason=%s", event_id[:8], field_name, unlock_reason)
        return None
    res = sb.table("field_corrections_audit").insert(payload).execute()
    rows = res.data or []
    return (rows[0].get("id") if rows else None)


def _audit_finalize(
    sb,
    audit_id: str | None,
    *,
    status: str,
    event_after_value: Any = None,
    error_message: str | None = None,
    dry_run: bool = False,
) -> None:
    if not audit_id or dry_run:
        return
    update: dict[str, Any] = {"operation_status": status}
    if status == "applied":
        update["verified_at"] = datetime.now(timezone.utc).isoformat()
        update["event_after_value_json"] = event_after_value
    if error_message:
        update["error_message"] = error_message[:500]
    sb.table("field_corrections_audit").update(update).eq("id", audit_id).execute()


def unlock_and_write(
    sb,
    *,
    event_id: str,
    field_name: str,
    new_value: Any,
    mode: str,
    unlock_reason: str,
    report_id: str | None = None,
    r_class: str | None = None,
    model_used: str | None = None,
    confidence: float | None = None,
    dry_run: bool = False,
) -> bool:
    """Apply a single-field correction with audit + post-write verification.

    mode:
      - "lock_clean":   write field + upsert FC corrected_value=new_value
      - "lock_empty":   write field (clear pollution) + FC corrected_value=NULL
      - "unlock_only":  delete FC row, leave field unchanged (then re-annotate later)
      - "review_only":  no DB write, only audit reasoning for human review

    Returns True on success, False if verification failed (audit row left at
    operation_status='verify_failed' for later inspection).
    """
    if mode not in {"lock_clean", "lock_empty", "unlock_only", "review_only"}:
        raise ValueError(f"unknown unlock_and_write mode: {mode}")

    # Snapshot current state
    ev = (
        sb.table("events")
        .select(f"id,{field_name}")
        .eq("id", event_id)
        .single()
        .execute()
    ).data or {}
    before_val = ev.get(field_name)

    fc_existing = (
        sb.table("field_corrections")
        .select("original_value,corrected_value,corrected_by,report_id")
        .eq("event_id", event_id)
        .eq("field_name", field_name)
        .limit(1)
        .execute()
    ).data or []
    fc_before = fc_existing[0] if fc_existing else None

    audit_id = _audit_start(
        sb,
        event_id=event_id,
        field_name=field_name,
        report_id=report_id,
        unlock_reason=unlock_reason,
        r_class=r_class,
        model_used=model_used,
        confidence=confidence,
        event_before_value=before_val,
        fc_before=fc_before,
        dry_run=dry_run,
    )

    if mode == "review_only":
        _audit_finalize(sb, audit_id, status="applied", event_after_value=before_val, dry_run=dry_run)
        return True

    if dry_run:
        logger.info(
            "[DRY] unlock_and_write mode=%s %s.%s — before=%r new=%r",
            mode, event_id[:8], field_name, before_val, new_value,
        )
        return True

    # field_corrections.corrected_value is TEXT NOT NULL — coerce non-text new_value
    # to JSON string; use "" as sentinel for lock_empty since None violates NOT NULL.
    def _fc_value(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (list, dict)):
            return json.dumps(v, ensure_ascii=False)
        return str(v)

    try:
        if mode == "unlock_only":
            sb.table("field_corrections").delete().eq("event_id", event_id).eq("field_name", field_name).execute()
        elif mode == "lock_clean":
            sb.table("events").update({field_name: new_value}).eq("id", event_id).execute()
            sb.table("field_corrections").upsert(
                {
                    "event_id": event_id,
                    "field_name": field_name,
                    "corrected_value": _fc_value(new_value),
                    "report_id": report_id,
                },
                on_conflict="event_id,field_name",
            ).execute()
        elif mode == "lock_empty":
            sb.table("events").update({field_name: None}).eq("id", event_id).execute()
            sb.table("field_corrections").upsert(
                {
                    "event_id": event_id,
                    "field_name": field_name,
                    "corrected_value": "",  # sentinel: locked-as-empty
                    "report_id": report_id,
                },
                on_conflict="event_id,field_name",
            ).execute()
    except Exception as exc:  # pragma: no cover — DB failure path
        _audit_finalize(sb, audit_id, status="verify_failed", error_message=f"write_error: {exc!r}")
        return False

    # Post-write verification: re-read and confirm the field reflects the change.
    verify = (
        sb.table("events")
        .select(field_name)
        .eq("id", event_id)
        .single()
        .execute()
    ).data or {}
    after_val = verify.get(field_name)
    expected = new_value if mode == "lock_clean" else (None if mode == "lock_empty" else before_val)
    if after_val != expected:
        _audit_finalize(
            sb, audit_id, status="verify_failed",
            error_message=f"post_write_mismatch: expected={expected!r} got={after_val!r}",
        )
        return False

    _audit_finalize(sb, audit_id, status="applied", event_after_value=after_val)
    return True


# --- Per-report-type handlers --------------------------------------------------


def handle_simplified_zh(sb, event_id: str, report: dict, *, dry_run: bool = False) -> bool:
    """Apply SC→TC fix to one event's zh fields. Confirms the report on success."""
    from annotator import _to_trad

    row = (
        sb.table("events")
        .select("id," + ",".join(FIX_FIELDS) + ",selection_reason")
        .eq("id", event_id)
        .single()
        .execute()
    ).data or {}
    if not row:
        return False

    any_applied = False
    for field in FIX_FIELDS:
        val = row.get(field) or ""
        if not val:
            continue
        converted = _to_trad(val)
        if converted == val:
            continue
        ok = unlock_and_write(
            sb,
            event_id=event_id,
            field_name=field,
            new_value=converted,
            mode="lock_clean",
            unlock_reason="auto_fix_simplified_zh",
            report_id=report.get("id"),
            r_class="R-ANN-SC",
            model_used="rule:_to_trad",
            confidence=0.99,
            dry_run=dry_run,
        )
        any_applied = any_applied or ok

    sr = row.get("selection_reason")
    if sr:
        try:
            sr_dict = json.loads(sr) if isinstance(sr, str) else sr
            zh_val = sr_dict.get("zh", "") if isinstance(sr_dict, dict) else ""
            if zh_val:
                converted_zh = _to_trad(zh_val)
                if converted_zh != zh_val:
                    sr_dict["zh"] = converted_zh
                    new_sr = json.dumps(sr_dict, ensure_ascii=False)
                    ok = unlock_and_write(
                        sb,
                        event_id=event_id,
                        field_name="selection_reason",
                        new_value=new_sr,
                        mode="lock_clean",
                        unlock_reason="auto_fix_simplified_zh_selection_reason",
                        report_id=report.get("id"),
                        r_class="R-ANN-SC",
                        model_used="rule:_to_trad",
                        confidence=0.99,
                        dry_run=dry_run,
                    )
                    any_applied = any_applied or ok
        except (ValueError, TypeError, AttributeError):
            pass

    if any_applied and report.get("id"):
        _confirm_report(sb, report["id"], note="auto-fixed SC→TC", dry_run=dry_run)
    return any_applied


def handle_performer_multi_value_split(sb, event_id: str, report: dict, *, dry_run: bool = False) -> bool:
    """Split polluted `performer` into `performers[]` and clear translation
    fields so `enrich_person_names` can rebuild cleanly."""
    row = (
        sb.table("events")
        .select(
            "id,performer,performers,performer_zh,performer_en,"
            "performers_zh,performers_en,annotation_status"
        )
        .eq("id", event_id)
        .single()
        .execute()
    ).data or {}
    if not row:
        return False

    if row.get("annotation_status") == "reviewed":
        _append_report_note(sb, report.get("id", ""), "skipped: annotation_status=reviewed", dry_run=dry_run)
        return False

    raw = row.get("performer") or ""
    if not _PERFORMER_SEP_RE.search(raw):
        # performer already cleared and performers[] populated → split was done elsewhere; confirm
        if not raw and (row.get("performers") or []):
            _confirm_report(
                sb, report.get("id", ""),
                note="auto-confirm: performer already split and cleared; performers[] populated",
                dry_run=dry_run,
            )
            return True
        # No separator and performers[] empty — genuine false positive
        _append_report_note(sb, report.get("id", ""), "skipped: performer has no separator", dry_run=dry_run)
        return False

    names = _split_performer_str(raw)
    if not names:
        _append_report_note(sb, report.get("id", ""), "skipped: split produced empty list", dry_run=dry_run)
        return False

    existing = row.get("performers") or []
    seen: set[str] = set(existing)
    merged: list[str] = list(existing)
    for n in names:
        if n not in seen:
            seen.add(n)
            merged.append(n)

    ok = True
    ok &= unlock_and_write(
        sb, event_id=event_id, field_name="performers", new_value=merged,
        mode="lock_clean", unlock_reason="auto_split_performer",
        report_id=report.get("id"), r_class="R-SCR-PERF-MULTI",
        model_used="rule:_split_performer_str", confidence=0.95, dry_run=dry_run,
    )
    for f in ("performer", "performer_zh", "performer_en", "performers_zh", "performers_en"):
        ok &= unlock_and_write(
            sb, event_id=event_id, field_name=f, new_value=None,
            mode="lock_empty", unlock_reason="auto_split_performer_clear_stale",
            report_id=report.get("id"), r_class="R-SCR-PERF-MULTI",
            model_used="rule:_split_performer_str", confidence=0.95, dry_run=dry_run,
        )

    if ok and report.get("id"):
        _confirm_report(
            sb, report["id"],
            note=f"auto-split performer→performers[{len(merged)}]; cleared stale translations",
            dry_run=dry_run,
        )
    return ok


def handle_performer_ai_translation_marker(sb, event_id: str, report: dict, *, dry_run: bool = False) -> bool:
    """Clear (AI翻譯)/(AI Translation) markers from performer_zh / performer_en.

    Deterministic rule: if the marker text appears in the matching language
    field, strip it. If after stripping the value equals the source `performer`
    katakana (lookup never found a real translation), set the field to NULL so
    the next enrich pass can retry.
    """
    row = (
        sb.table("events")
        .select("id,performer,performer_zh,performer_en")
        .eq("id", event_id)
        .single()
        .execute()
    ).data or {}
    if not row:
        return False

    performer_ja = (row.get("performer") or "").strip()
    any_applied = False

    pf_zh = row.get("performer_zh") or ""
    if _AI_MARKER_ZH in pf_zh:
        stripped = pf_zh.replace(_AI_MARKER_ZH, "").strip()
        if not stripped or stripped == performer_ja:
            ok = unlock_and_write(
                sb, event_id=event_id, field_name="performer_zh", new_value=None,
                mode="lock_empty", unlock_reason="auto_clear_ai_marker_unresolved",
                report_id=report.get("id"), r_class="R-ANN-AI-MARKER",
                model_used="rule:strip_ai_marker", confidence=0.90, dry_run=dry_run,
            )
        else:
            ok = unlock_and_write(
                sb, event_id=event_id, field_name="performer_zh", new_value=stripped,
                mode="lock_clean", unlock_reason="auto_strip_ai_marker",
                report_id=report.get("id"), r_class="R-ANN-AI-MARKER",
                model_used="rule:strip_ai_marker", confidence=0.90, dry_run=dry_run,
            )
        any_applied = any_applied or ok

    pf_en = row.get("performer_en") or ""
    if _AI_MARKER_EN in pf_en:
        stripped = pf_en.replace(_AI_MARKER_EN, "").strip()
        if not stripped or stripped == performer_ja:
            ok = unlock_and_write(
                sb, event_id=event_id, field_name="performer_en", new_value=None,
                mode="lock_empty", unlock_reason="auto_clear_ai_marker_unresolved",
                report_id=report.get("id"), r_class="R-ANN-AI-MARKER",
                model_used="rule:strip_ai_marker", confidence=0.90, dry_run=dry_run,
            )
        else:
            ok = unlock_and_write(
                sb, event_id=event_id, field_name="performer_en", new_value=stripped,
                mode="lock_clean", unlock_reason="auto_strip_ai_marker",
                report_id=report.get("id"), r_class="R-ANN-AI-MARKER",
                model_used="rule:strip_ai_marker", confidence=0.90, dry_run=dry_run,
            )
        any_applied = any_applied or ok

    if any_applied and report.get("id"):
        _confirm_report(sb, report["id"], note="auto-cleared AI translation marker", dry_run=dry_run)
    return any_applied


HANDLER_MAP: dict[str, Any] = {
    "auto_qa_simplified_zh": handle_simplified_zh,
    "auto_simplified_chinese": handle_simplified_zh,
    "auto_qa_performer_ai_translation_marker": handle_performer_ai_translation_marker,
    "auto_qa_performer_multi_value_pollution": handle_performer_multi_value_split,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe one-click QA auto-fix")
    parser.add_argument("--dry-run", action="store_true", help="Preview only; no DB writes, no LINE")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
