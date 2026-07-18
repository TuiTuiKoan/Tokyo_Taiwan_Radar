"""
error_recovery.py — Recover stuck annotation_status='error' events.

annotator.py sets annotation_status='error' when GPT JSON parsing fails
(annotator.py L2643), but the annotator main loop only queries 'pending'
events — so error events are never retried and pile up in the admin backlog.

This tool scans error events and classifies each one:

  HEAL     has field_corrections AND all CORE_FIELDS present
           → promote to 'reviewed' (status-only; never touches content fields)
  RETRY    no FC, or FC present but a CORE field missing, and retry_count < limit
           → reset to 'pending', increment annotation_retry_count
  ESCALATE retry_count >= limit
           → stay 'error', file a deduped event_report, collect for LINE summary

Phase 0 settles the previous round: events that reached 'annotated' with a
non-zero retry_count get retry_count reset to 0 (their reset → re-annotate
cycle succeeded). This keeps annotation_retry_count's lifecycle entirely inside
error_recovery — annotator.py needs ZERO changes.

Usage:
    python error_recovery.py [--dry-run] [--limit N] [--source NAME] [--report-only]
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timezone

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from line_notify import send_line_message  # noqa: E402
# Reuse H0's writer-safety primitives rather than re-implementing them: the
# exactly-one-row pending CAS close and the shared annotation_error_stuck
# resolution predicate both live in auto_qa (single source of truth).
from auto_qa import (  # noqa: E402
    _check_annotation_error_stuck,
    close_report_exactly_one,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETRY = 3
THIN_RETRY_LIMIT = 1  # thin-content sources fail structurally — escalate fast
THIN_CONTENT_SOURCES = frozenset({
    "google_news_rss", "note_creators", "prtimes", "nhk_rss", "walkerplus",
})
CORE_FIELDS = ("name_ja", "name_zh", "name_en", "start_date")
ESCALATE_REPORT_TYPE = "annotation_error_stuck"

# Sources with a known structural error cause — surfaced in the report.
SYSTEMIC_PUBLICATION = frozenset({"hanmoto", "ndl_opensearch"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _supabase_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _retry_limit(source_name: str) -> int:
    return THIN_RETRY_LIMIT if source_name in THIN_CONTENT_SOURCES else MAX_RETRY


def _core_complete(event: dict) -> bool:
    return all(event.get(f) for f in CORE_FIELDS)


def _classify(event: dict, has_fc: bool) -> str:
    """Return 'HEAL', 'RETRY', or 'ESCALATE' for one error event."""
    if has_fc and _core_complete(event):
        return "HEAL"
    retry_count = event.get("annotation_retry_count") or 0
    if retry_count >= _retry_limit(event.get("source_name") or ""):
        return "ESCALATE"
    return "RETRY"


def _age_days(updated_at: str | None) -> int:
    if not updated_at:
        return 0
    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        return max((datetime.now(timezone.utc) - ts).days, 0)
    except Exception:
        return 0


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2


def _recommendation(source_name: str) -> str:
    if source_name in SYSTEMIC_PUBLICATION:
        return "publication 模板問題（建議修 annotator publication 流程）"
    if source_name in THIN_CONTENT_SOURCES:
        return "薄內容（交 refetch_thin_events 處理）"
    return "個案人工檢查"


# ---------------------------------------------------------------------------
# Phase 0 — settle previous round
# ---------------------------------------------------------------------------

def _settle_previous_round(sb, dry_run: bool) -> int:
    """Reset annotation_retry_count=0 for events that reached 'annotated'.

    A non-zero retry_count on an annotated event means a prior RETRY reset
    succeeded — clear the counter so a future failure starts fresh.
    """
    rows = (
        sb.table("events")
        .select("id")
        .eq("annotation_status", "annotated")
        .gt("annotation_retry_count", 0)
        .execute()
        .data
        or []
    )
    healed = len(rows)
    if rows and not dry_run:
        ids = [r["id"] for r in rows]
        for i in range(0, len(ids), 200):
            chunk = ids[i:i + 200]
            sb.table("events").update({"annotation_retry_count": 0}).in_("id", chunk).execute()
    return healed


def _is_single_escalation_row(report_types) -> bool:
    """True only when report_types is exactly [ESCALATE_REPORT_TYPE].

    annotation_error_stuck is error_recovery's own escalation type, not a known
    Auto-QA type, so auto_qa.single_auto_type() never matches it. This mirrors
    H0's single-type eligibility for it directly: any compound / multi-type row
    — including one carrying a `field:` / `fieldEdit:` / `selectionReason:`
    payload token — is disqualified and left for manual review.
    """
    cleaned = [t for t in (report_types or []) if isinstance(t, str) and t]
    return cleaned == [ESCALATE_REPORT_TYPE]


def _settle_recovered_escalations(sb, dry_run: bool) -> int:
    """Close pending annotation_error_stuck reports whose event has recovered.

    The escalation half (_file_escalation_report) only ever INSERTs; this is its
    settlement counterpart. For each pending single-type escalation row it runs a
    status-last, all-or-compensate lifecycle:

      1. verify event recovery — annotation reached a verified-complete state
         (annotated/reviewed) via H0's shared _check_annotation_error_stuck
         predicate; otherwise the report is left pending.
      2. retry reset — annotation_retry_count -> 0 (skipped when already 0 to
         avoid a redundant write); if the write touches != 1 row the report is
         left pending and NOT closed.
      3. report confirmation — close_report_exactly_one(status='confirmed') with
         a full report_id + status='pending' CAS requiring EXACTLY ONE row.

    The report-status write is the FINAL Supabase write, so any earlier failure
    (recovery unverified, retry-reset raises / touches != 1 row, or the close CAS
    misses) leaves the report pending — there is no half-settled state. A retry
    reset that already succeeded is not rolled back: annotation_retry_count == 0
    on a recovered event is always correct, so keeping it breaks no invariant.
    Only single-type rows are eligible; compound / payload rows stay for manual
    review. Returns the number settled (would-settle count in dry-run).
    """
    reports = (
        sb.table("event_reports")
        .select("id, event_id, report_types")
        .ov("report_types", [ESCALATE_REPORT_TYPE])
        .eq("status", "pending")
        .execute()
        .data
        or []
    )
    settled = 0
    seen: set[str] = set()
    for rep in reports:
        rid = rep.get("id")
        eid = rep.get("event_id")
        if not rid or not eid or rid in seen:
            continue
        if not _is_single_escalation_row(rep.get("report_types")):
            continue  # compound / payload row — never auto-settle here

        rows = (
            sb.table("events")
            .select("id, annotation_status, annotation_retry_count")
            .eq("id", eid)
            .limit(1)
            .execute()
            .data
            or []
        )
        ev = rows[0] if rows else None
        # Step 1 — verify event recovery (shared type-specific resolution predicate)
        if ev is None or _check_annotation_error_stuck(ev) is not None:
            continue  # not recovered → leave report pending

        if dry_run:
            settled += 1
            seen.add(rid)
            continue

        try:
            # Step 2 — retry reset (idempotent; require exactly one updated row)
            if (ev.get("annotation_retry_count") or 0) != 0:
                rr = (
                    sb.table("events")
                    .update({"annotation_retry_count": 0})
                    .eq("id", eid)
                    .execute()
                )
                if len(rr.data or []) != 1:
                    logger.warning(
                        "  SETTLE %s retry-reset touched %d rows — report left pending",
                        eid[:8], len(rr.data or []),
                    )
                    continue
            # Step 3 — report confirmation LAST (full-id + pending CAS, exactly one)
            note = (
                "annotation 已恢復（annotated/reviewed），"
                "error_recovery 自動結案 annotation_error_stuck。"
            )
            ok, _n = close_report_exactly_one(sb, rid, status="confirmed", note=note)
        except Exception as exc:  # noqa: BLE001 — leave report pending on any failure
            logger.warning("  SETTLE %s aborted (%s) — report left pending", eid[:8], exc)
            continue

        if ok:
            settled += 1
            seen.add(rid)
            logger.info("  SETTLE %s → report %s confirmed (recovered)", eid[:8], rid[:8])
        else:
            logger.warning("  SETTLE %s report-close CAS miss — report left pending", eid[:8])
    return settled


# ---------------------------------------------------------------------------
# Phase 1 — escalation report row
# ---------------------------------------------------------------------------

def _file_escalation_report(sb, event_id: str, source_name: str, retry_count: int) -> bool:
    """Insert a deduped 'annotation_error_stuck' event_report. Returns True if written.

    Writer-safety (see auto_qa consumer matrix): this consumer only INSERTs a
    single-type escalation row and never transitions an existing report's
    status. Settling / closing these escalation rows is deferred to Round G3, so
    no pending-CAS close path is added here in H0.
    """
    existing = (
        sb.table("event_reports")
        .select("id")
        .eq("event_id", event_id)
        .ov("report_types", [ESCALATE_REPORT_TYPE])
        .eq("status", "pending")
        .execute()
        .data
        or []
    )
    if existing:
        logger.info("  ESCALATE dedup: %s already has pending %s", event_id[:8], ESCALATE_REPORT_TYPE)
        return False
    note = (
        f"標注重試 {retry_count} 次仍失敗（來源 {source_name}），"
        "需人工檢查 source_url 原始頁面或手動修正核心欄位。"
    )
    sb.table("event_reports").insert({
        "event_id": event_id,
        "report_types": [ESCALATE_REPORT_TYPE],
        "status": "pending",
        "admin_notes": note,
    }).execute()
    return True


# ---------------------------------------------------------------------------
# Phase 2 — report + LINE
# ---------------------------------------------------------------------------

def _systemic_sources(by_source_stats: dict) -> list[str]:
    return sorted(
        [s for s, st in by_source_stats.items() if st["escalate"] >= 3 or st["error"] >= 5],
        key=lambda s: by_source_stats[s]["error"],
        reverse=True,
    )


def _build_report(summary: dict, by_source_stats: dict) -> str:
    today = date.today().isoformat()
    lines = [
        f"# Error Recovery — {today}",
        "",
        f"- healed last round (上一輪 reset 後成功重標): {summary['healed_last_round']}",
        f"- settled (recovered escalations → confirmed): {summary['settled']}",
        f"- scanned (error events this run): {summary['scanned']}",
        f"- HEAL → reviewed: {summary['heal']}",
        f"- RETRY → pending: {summary['retry']}",
        f"- ESCALATE (stays error + report): {summary['escalate']}",
        "",
        "## By source",
        "",
        "| source | error | escalate | median stuck days | recommendation |",
        "|--------|-------|----------|-------------------|----------------|",
    ]
    for src in sorted(by_source_stats, key=lambda s: by_source_stats[s]["error"], reverse=True):
        st = by_source_stats[src]
        lines.append(
            f"| {src} | {st['error']} | {st['escalate']} | "
            f"{_median(st['ages']):.0f} | {_recommendation(src)} |"
        )
    lines += ["", "## Systemic sources (ESCALATE≥3 or error≥5)", ""]
    systemic = _systemic_sources(by_source_stats)
    if systemic:
        for src in systemic:
            st = by_source_stats[src]
            lines.append(
                f"- **{src}** — error={st['error']}, escalate={st['escalate']} "
                f"→ {_recommendation(src)}"
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _write_report(md: str) -> str:
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, f"error_recovery_{date.today().isoformat()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    logger.info("Report written: %s", path)
    return path


def _send_line_summary(summary: dict, by_source_stats: dict) -> None:
    systemic = _systemic_sources(by_source_stats)[:5]
    top = "、".join(f"{s}({by_source_stats[s]['error']})" for s in systemic) or "無"
    msg = (
        f"[Error Recovery] {date.today().isoformat()}\n"
        f"上一輪修復成功: {summary['healed_last_round']}\n"
        f"結案(恢復後): {summary['settled']}\n"
        f"本輪 error 掃描: {summary['scanned']}\n"
        f"HEAL→reviewed: {summary['heal']}\n"
        f"RETRY→pending: {summary['retry']}\n"
        f"ESCALATE(留 error): {summary['escalate']}\n"
        f"系統性來源: {top}"
    )
    send_line_message(msg)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(dry_run: bool = False, limit: int = 100, source: str | None = None,
        report_only: bool = False) -> dict:
    sb = _supabase_client()

    # Phase 0 — settle previous round (report_only still settles; dry_run does not write)
    healed_last_round = _settle_previous_round(sb, dry_run)
    logger.info("Phase 0 — healed last round: %d", healed_last_round)
    settled_reports = _settle_recovered_escalations(sb, dry_run)
    logger.info("Phase 0 — settled recovered escalations: %d", settled_reports)

    summary = {
        "scanned": 0, "heal": 0, "retry": 0, "escalate": 0,
        "healed_last_round": healed_last_round, "settled": settled_reports,
        "by_source": {},
    }

    # Phase 1 — scan + classify
    query = (
        sb.table("events")
        .select(
            "id, source_name, name_ja, name_zh, name_en, start_date, "
            "annotation_retry_count, updated_at"
        )
        .eq("annotation_status", "error")
        .eq("is_active", True)
        .order("updated_at", desc=False)
    )
    if source:
        query = query.eq("source_name", source)
    events = query.limit(limit).execute().data or []
    summary["scanned"] = len(events)

    by_source_stats: dict[str, dict] = {}
    writes_enabled = not (dry_run or report_only)

    for event in events:
        eid = event["id"]
        src = event.get("source_name") or "unknown"

        fc_rows = (
            sb.table("field_corrections")
            .select("field_name")
            .eq("event_id", eid)
            .execute()
            .data
            or []
        )
        has_fc = len(fc_rows) > 0
        decision = _classify(event, has_fc)

        st = by_source_stats.setdefault(src, {"error": 0, "escalate": 0, "ages": []})
        st["error"] += 1
        st["ages"].append(_age_days(event.get("updated_at")))
        summary["by_source"].setdefault(src, {"heal": 0, "retry": 0, "escalate": 0})

        if decision == "HEAL":
            summary["heal"] += 1
            summary["by_source"][src]["heal"] += 1
            if writes_enabled:
                sb.table("events").update(
                    {"annotation_status": "reviewed"}
                ).eq("id", eid).execute()
            logger.info("  HEAL %s (%s) → reviewed", eid[:8], src)
        elif decision == "RETRY":
            summary["retry"] += 1
            summary["by_source"][src]["retry"] += 1
            new_count = (event.get("annotation_retry_count") or 0) + 1
            if writes_enabled:
                sb.table("events").update({
                    "annotation_status": "pending",
                    "annotation_retry_count": new_count,
                }).eq("id", eid).execute()
            logger.info("  RETRY %s (%s) → pending (retry %d/%d)",
                        eid[:8], src, new_count, _retry_limit(src))
        else:  # ESCALATE
            summary["escalate"] += 1
            summary["by_source"][src]["escalate"] += 1
            st["escalate"] += 1
            retry_count = event.get("annotation_retry_count") or 0
            if writes_enabled:
                _file_escalation_report(sb, eid, src, retry_count)
            logger.info("  ESCALATE %s (%s) → stays error (retry %d)", eid[:8], src, retry_count)

    # Phase 2 — source analysis report
    report_md = _build_report(summary, by_source_stats)
    if dry_run:
        logger.info("DRY-RUN — report not written, LINE not sent:\n%s", report_md)
    else:
        _write_report(report_md)
        _send_line_summary(summary, by_source_stats)

    logger.info("error_recovery summary: %s", summary)
    return summary


if __name__ == "__main__":
    dry_run_flag = "--dry-run" in sys.argv
    report_only_flag = "--report-only" in sys.argv
    source_arg = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--source"), None)
    limit_str = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--limit"), None)
    limit_arg = int(limit_str) if limit_str else 100
    run(
        dry_run=dry_run_flag,
        limit=limit_arg,
        source=source_arg,
        report_only=report_only_flag,
    )
