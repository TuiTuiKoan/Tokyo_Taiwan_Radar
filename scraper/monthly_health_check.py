"""
monthly_health_check.py — Automated feedback-loop health check.

Runs the 4 SQL queries from docs/MONTHLY_FEEDBACK_LOOP_HEALTH_CHECK.md,
builds a structured LINE message, and sends it via line_notify.

Triggered by .github/workflows/monthly_health_check.yml on the 1st of
each month at 09:00 JST (00:00 UTC).

Can also be run manually:
  python monthly_health_check.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from supabase import create_client
from line_notify import send_line_message

logger = logging.getLogger(__name__)

UTC = timezone.utc
JST = timezone(timedelta(hours=9))


def _get_sb():
    load_dotenv()
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


# ─── Step 1: confirmed reports last 30d ──────────────────────────────────────

def _count_confirmed_reports(sb) -> dict:
    try:
        rows = (
            sb.table("event_reports")
            .select("report_types")
            .eq("status", "confirmed")
            .gte("confirmed_at", (datetime.now(tz=UTC) - timedelta(days=30)).isoformat())
            .execute()
            .data or []
        )
        counts = dict(irrelevant=0, wrongCategory=0, wrongDetails=0, wrongSelectionReason=0, total=0)
        for r in rows:
            types = r.get("report_types") or []
            counts["total"] += 1
            for t in types:
                if t in counts:
                    counts[t] += 1
        return counts
    except Exception as exc:
        logger.warning("count_confirmed_reports failed: %s", exc)
        return {}


# ─── Step 2: corrections tables last 30d ─────────────────────────────────────

def _count_corrections(sb) -> dict:
    cutoff = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
    result = {}
    for table in ("field_corrections", "category_corrections", "selection_reason_corrections"):
        try:
            resp = (
                sb.table(table)
                .select("id", count="exact", head=True)
                .gte("created_at", cutoff)
                .execute()
            )
            result[table] = resp.count or 0
        except Exception as exc:
            logger.warning("%s count failed: %s", table, exc)
            result[table] = None
    return result


# ─── Step 3: field_protect_hits from annotator scraper_runs (last 30d) ───────

def _count_protect_hits(sb) -> int:
    cutoff = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
    try:
        rows = (
            sb.table("scraper_runs")
            .select("notes")
            .eq("source", "annotator")
            .gte("ran_at", cutoff)
            .execute()
            .data or []
        )
        total = 0
        for r in rows:
            notes = r.get("notes") or ""
            m = re.search(r"field_protect_hits=(\d+)", notes)
            if m:
                total += int(m.group(1))
        return total
    except Exception as exc:
        logger.warning("protect_hits failed: %s", exc)
        return -1


# ─── Step 4: source_exclusion_hits last 30d ───────────────────────────────────

def _count_exclusion_hits(sb) -> int:
    cutoff = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
    try:
        resp = (
            sb.table("source_exclusion_hits")
            .select("id", count="exact", head=True)
            .gte("matched_at", cutoff)
            .execute()
        )
        return resp.count or 0
    except Exception as exc:
        logger.debug("exclusion_hits failed: %s", exc)
        return 0


# ─── Integrity signals ────────────────────────────────────────────────────────

def _integrity_flags(reports: dict, corrections: dict) -> list[str]:
    """Return list of warning strings if corrections don't match reports."""
    flags = []
    wrong_cat = reports.get("wrongCategory", 0)
    wrong_det = reports.get("wrongDetails", 0)
    wrong_sr = reports.get("wrongSelectionReason", 0)
    cat_corr = corrections.get("category_corrections")
    field_corr = corrections.get("field_corrections")
    sr_corr = corrections.get("selection_reason_corrections")

    if wrong_cat > 0 and cat_corr == 0:
        flags.append("❌ wrongCategory 有報錯但 category_corrections = 0（閉環斷鏈）")
    if wrong_det > 0 and field_corr == 0:
        flags.append("❌ wrongDetails 有報錯但 field_corrections = 0（閉環斷鏈）")
    if wrong_sr > 0 and sr_corr == 0:
        flags.append("❌ wrongSR 有報錯但 selection_reason_corrections = 0（閉環斷鏈）")
    return flags


# ─── Step 5: cleanup old records ─────────────────────────────────────────────

_CLEANUP_DAYS = 90  # Keep 90 days of aeo_visits and scraper_runs

def _cleanup_old_records(sb) -> dict:
    """Delete aeo_visits and scraper_runs records older than CLEANUP_DAYS days.

    Returns dict with row counts deleted per table.
    """
    cutoff = (datetime.now(tz=UTC) - timedelta(days=_CLEANUP_DAYS)).isoformat()
    result = {}
    for table in ("aeo_visits", "scraper_runs"):
        try:
            resp = (
                sb.table(table)
                .delete()
                .lt("created_at" if table == "aeo_visits" else "ran_at", cutoff)
                .execute()
            )
            deleted = len(resp.data) if resp.data else 0
            result[table] = deleted
            logger.info("cleanup %s: deleted %d rows older than %d days", table, deleted, _CLEANUP_DAYS)
        except Exception as exc:
            logger.warning("cleanup %s failed: %s", table, exc)
            result[table] = -1
    return result



def build_line_message(reports: dict, corrections: dict, protect_hits: int, excl_hits: int,
                       cleanup: dict | None = None) -> str:
    month = datetime.now(tz=JST).strftime("%Y-%m")
    lines = [
        f"📋 報錯閉環健檢 — {month}",
        "",
        "【步驟 1：報錯確認數（30 天）】",
        f"  irrelevant:            {reports.get('irrelevant', '?')}",
        f"  wrongCategory:         {reports.get('wrongCategory', '?')}",
        f"  wrongDetails:          {reports.get('wrongDetails', '?')}",
        f"  wrongSelectionReason:  {reports.get('wrongSelectionReason', '?')}",
        f"  合計:                  {reports.get('total', '?')}",
        "",
        "【步驟 2：corrections 落地數（30 天）】",
        f"  field_corrections:             {corrections.get('field_corrections', '?')}",
        f"  category_corrections:          {corrections.get('category_corrections', '?')}",
        f"  selection_reason_corrections:  {corrections.get('selection_reason_corrections', '?')}",
        "",
        "【步驟 3：AI 保護命中（30 天）】",
        f"  field_protect_hits: {protect_hits if protect_hits >= 0 else '取得失敗'}",
        "",
        "【步驟 4：封鎖規則命中（30 天）】",
        f"  source_exclusion_hits: {excl_hits}",
    ]

    flags = _integrity_flags(reports, corrections)
    if flags:
        lines.append("")
        lines.append("【⚠️ 閉環警訊】")
        for f in flags:
            lines.append(f"  {f}")
    else:
        lines.append("")
        lines.append("✅ 閉環完整：無斷鏈警訊")

    if protect_hits == 0:
        lines.append("⚠️ field_protect_hits = 0（annotator 可能未載入 corrections）")
    elif protect_hits > 0:
        lines.append(f"✅ 保護機制運作中（30 天累積 {protect_hits} 次命中）")

    if cleanup:
        lines.append("")
        lines.append("[步驟 5：90d 舊資料清理]")
        for table, cnt in cleanup.items():
            if cnt >= 0:
                lines.append(f"  {table}: 删除 {cnt} 筆")
            else:
                lines.append(f"  {table}: 清理失敗")

    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> dict:
    sb = _get_sb()
    reports = _count_confirmed_reports(sb)
    corrections = _count_corrections(sb)
    protect_hits = _count_protect_hits(sb)
    excl_hits = _count_exclusion_hits(sb)

    cleanup = None
    if not dry_run:
        cleanup = _cleanup_old_records(sb)

    msg = build_line_message(reports, corrections, protect_hits, excl_hits, cleanup)
    flags = _integrity_flags(reports, corrections)

    summary = {
        "month": datetime.now(tz=JST).strftime("%Y-%m"),
        "reports": reports,
        "corrections": corrections,
        "protect_hits_30d": protect_hits,
        "exclusion_hits_30d": excl_hits,
        "cleanup": cleanup,
        "integrity_flags": flags,
        "message_preview": msg[:200],
    }

    if dry_run:
        logger.info("[dry-run] LINE message:\n%s", msg)
    else:
        success = send_line_message(msg)
        if not success:
            logger.warning("LINE notification not sent (token not configured or request failed)")
        summary["line_sent"] = success

    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Monthly feedback-loop health check")
    ap.add_argument("--dry-run", action="store_true", help="Print message without sending LINE")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    summary = run(dry_run=args.dry_run)
    print(json.dumps(summary, default=str, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
