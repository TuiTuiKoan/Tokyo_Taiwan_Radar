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
from pathlib import Path
from statistics import median

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


# ─── A1 / A4 input: human field_corrections only (#373) ─────────────────────

def _fetch_human_corrections(
    sb, columns: str, start_iso: str, end_iso: str | None = None,
) -> tuple[list[dict], int | None]:
    """Human-written field_corrections in the window, plus the script-written count.

    Only the admin UI sets corrected_by. Annotator locks, qa_auto_fix, the
    publication-policy empty sentinel and one-off scripts leave it null; rows
    with only a report_id come from qa_auto_fix settling auto-QA reports. Same
    rule as eval_scraper_quality.is_human_correction. Script rows are counted,
    not ranked: in 2026-09 all 698 rows were script-written.
    """
    q = (
        sb.table("field_corrections")
        .select(columns)
        .gte("created_at", start_iso)
        .not_.is_("corrected_by", "null")
    )
    if end_iso:
        q = q.lt("created_at", end_iso)
    rows = q.execute().data or []

    try:
        cq = (
            sb.table("field_corrections")
            .select("id", count="exact", head=True)
            .gte("created_at", start_iso)
            .is_("corrected_by", "null")
        )
        if end_iso:
            cq = cq.lt("created_at", end_iso)
        script = cq.execute().count or 0
    except Exception as exc:
        logger.warning("script-written field_corrections count failed: %s", exc)
        script = None
    return rows, script


def _aggregate_recurrence(fc_rows: list[dict], source_by_event: dict[str, str]) -> dict:
    """(source_name, field_name) pairs corrected ≥ 2 times, top 10."""
    pair_counts: dict[tuple[str, str], int] = {}
    for row in fc_rows:
        source = source_by_event.get(row.get("event_id", ""), "unknown")
        field = row.get("field_name", "")
        if source and field:
            pair_counts[(source, field)] = pair_counts.get((source, field), 0) + 1

    recurring = {pair: cnt for pair, cnt in pair_counts.items() if cnt >= 2}
    top = sorted(recurring.items(), key=lambda x: -x[1])[:10]
    return {
        "recurrence_pairs": len(recurring),
        "top_pairs": [
            {"source_name": src, "field_name": fld, "count": cnt}
            for (src, fld), cnt in top
        ],
    }


def _aggregate_repair_latency(
    fc_rows: list[dict], event_created_at: dict[str, str], event_source: dict[str, str],
) -> dict:
    """Per source: median days from event creation to correction, slowest 5."""
    source_latencies: dict[str, list[float]] = {}
    for fc in fc_rows:
        eid = fc.get("event_id")
        if not eid or eid not in event_created_at:
            continue
        try:
            ev_dt = datetime.fromisoformat(event_created_at[eid].replace("Z", "+00:00"))
            fc_dt = datetime.fromisoformat(fc["created_at"].replace("Z", "+00:00"))
            days = max(0.0, (fc_dt - ev_dt).total_seconds() / 86400)
        except Exception:
            continue
        source_latencies.setdefault(event_source.get(eid, "unknown"), []).append(days)

    rows = [
        {"source_name": src, "n_corrections": len(lats), "median_days": round(median(lats), 1)}
        for src, lats in source_latencies.items() if lats
    ]
    rows.sort(key=lambda x: -x["median_days"])
    return {"sources": rows[:5]}


def script_corrections_note(metric: dict) -> str:
    """One line saying how many script-written corrections the metric left out."""
    n = metric.get("script_corrections")
    if n is None:
        return "只計人工修正（`corrected_by` 有值）；腳本寫入筆數取得失敗。"
    return f"只計人工修正（`corrected_by` 有值）；腳本寫入 {n} 筆不計入，那是 annotator 鎖定、qa_auto_fix 與出版政策的正常運作（#373）。"


# ─── A1: Recurrence rate (same source×field corrected ≥2 times in 90d) ──────

def _count_recurrence(sb) -> dict:
    """A1 — (source_name, field_name) pairs corrected by a human ≥ 2 times in last 90 days."""
    cutoff = (datetime.now(tz=UTC) - timedelta(days=90)).isoformat()
    try:
        fc_rows, script = _fetch_human_corrections(sb, "event_id,field_name,created_at", cutoff)
    except Exception as exc:
        logger.warning("_count_recurrence: field_corrections fetch failed: %s", exc)
        return {"recurrence_pairs": -1, "top_pairs": [], "script_corrections": None}

    if not fc_rows:
        return {"recurrence_pairs": 0, "top_pairs": [], "script_corrections": script}

    # Fetch source_name for each event_id (batch)
    event_ids = list({r["event_id"] for r in fc_rows if r.get("event_id")})
    source_by_event: dict[str, str] = {}
    for i in range(0, len(event_ids), 200):
        batch = event_ids[i:i + 200]
        try:
            rows = (
                sb.table("events")
                .select("id,source_name")
                .in_("id", batch)
                .execute()
                .data or []
            )
            for r in rows:
                source_by_event[r["id"]] = r.get("source_name", "unknown")
        except Exception as exc:
            logger.warning("_count_recurrence: events batch failed: %s", exc)

    return {**_aggregate_recurrence(fc_rows, source_by_event), "script_corrections": script}


# ─── A2: Protect hit trend (30/60/90 day windows) ────────────────────────────

def _parse_annotator_notes(notes: str) -> tuple[int, int]:
    """Return ``(field_protect_hits, annotated_events)`` from an annotator run note.

    ``annotated=`` is the explicit denominator; ``total=`` is the historical
    fallback (see ``_protect_hit_trend``). Missing tokens count as 0.
    """
    m_hits = re.search(r"field_protect_hits=(\d+)", notes)
    m_ann = re.search(r"(?<![a-z_])annotated=(\d+)", notes) \
        or re.search(r"(?<![a-z_])total=(\d+)", notes)
    return (
        int(m_hits.group(1)) if m_hits else 0,
        int(m_ann.group(1)) if m_ann else 0,
    )


def _fields_per_event(hits: int, annotated: int) -> float | None:
    """A2 — average number of protected fields per annotated event.

    ``field_protect_hits`` is counted per field: one event with five corrected
    fields adds five. Dividing by annotated events therefore gives a per-event
    average, not a percentage. Reporting it as a percentage produced the
    2026-09 "453.55%" reading (3515 fields / 775 events), see #324.
    """
    if not annotated or hits < 0:
        return None
    return round(hits / annotated, 2)


def _protect_hit_trend(sb) -> dict:
    """A2 — field_protect_hits / annotated_events ratio for 30/60/90 day windows.

    Denominator token provenance
    ----------------------------
    ``annotator.py`` writes the run summary into ``scraper_runs.notes`` as a flat
    ``key=value`` string. Two tokens can carry the number of events the annotator
    processed, and both must be accepted:

    * ``annotated=<n>`` — the explicit denominator. Added 2026-08-12.
    * ``total=<n>``     — the number of events in the batch. Present since the
      notes string was introduced, and the only denominator available on every
      historical row.

    Before 2026-08-12 only ``total=`` was ever written, while this function
    searched for ``annotated=`` alone. That token therefore never matched, the
    denominator was always ``0``, and ``rate_*`` was reported as ``n/a`` for two
    consecutive months even though ``field_protect_hits`` was being recorded
    correctly. The fallback below is what makes those historical rows usable; it
    is not a defensive nicety and must not be removed as one.

    ``total=`` is kept in the notes string as well, because other consumers read
    it. Rows written from now on carry both tokens, and ``annotated=`` wins when
    the two ever diverge.
    """
    now = datetime.now(tz=UTC)
    windows = [("30d", 30), ("60d", 60), ("90d", 90)]
    result: dict[str, int | float | None] = {}

    try:
        all_runs = (
            sb.table("scraper_runs")
            .select("notes,ran_at")
            .eq("source", "annotator")
            .gte("ran_at", (now - timedelta(days=90)).isoformat())
            .execute()
            .data or []
        )
    except Exception as exc:
        logger.warning("_protect_hit_trend: scraper_runs fetch failed: %s", exc)
        return {f"hit_{k}": -1 for k, _ in windows}

    for label, days in windows:
        cutoff = (now - timedelta(days=days)).isoformat()
        hits = 0
        annotated = 0
        for r in all_runs:
            if (r.get("ran_at") or "") < cutoff:
                continue
            run_hits, run_annotated = _parse_annotator_notes(r.get("notes") or "")
            hits += run_hits
            annotated += run_annotated
        result[f"hit_{label}"] = hits
        result[f"annotated_{label}"] = annotated
        result[f"fields_per_event_{label}"] = _fields_per_event(hits, annotated)

    return result


# ─── A3: First-pass accuracy (reported within 24h / new events, per source) ──

# A3 measures reader-submitted reports only. The public report form
# (web/app/actions/submit-report.ts) always sends a locale; auto_qa.py,
# annotator.py and error_recovery.py insert rows with locale = NULL. Counting
# both made every source auto-QA touched read "100% reported within 24h" (#324).
A3_MIN_NEW_EVENTS = 5
A3_WINDOW_SECONDS = 86400


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _aggregate_first_pass(
    events: list[dict],
    reports: list[dict],
    *,
    min_new_events: int = A3_MIN_NEW_EVENTS,
    limit: int = 10,
) -> dict:
    """Aggregate A3 from already-fetched events and their event_reports rows.

    An event counts as reported when a reader report (``locale`` set) arrives
    within 24h of the event's creation. System reports inside the same window
    are counted separately so the report can show both. Sources with fewer than
    ``min_new_events`` new events are left out of the ranking: one event with
    one report would otherwise sit at the top as 100%.
    """
    created_at_by_id = {e["id"]: e.get("created_at") for e in events}
    human: set[str] = set()
    system: set[str] = set()
    for rep in reports:
        eid = rep.get("event_id")
        ev_created = created_at_by_id.get(eid)
        rep_created = rep.get("created_at")
        if not (eid and ev_created and rep_created):
            continue
        try:
            delta = (_parse_ts(rep_created) - _parse_ts(ev_created)).total_seconds()
        except ValueError:
            continue
        if not 0 <= delta < A3_WINDOW_SECONDS:
            continue
        if rep.get("locale"):
            human.add(eid)
        else:
            system.add(eid)

    source_total: dict[str, int] = {}
    source_reported: dict[str, int] = {}
    for e in events:
        src = e.get("source_name") or "unknown"
        source_total[src] = source_total.get(src, 0) + 1
        if e["id"] in human:
            source_reported[src] = source_reported.get(src, 0) + 1

    rows = []
    for src, total in source_total.items():
        if total < min_new_events:
            continue
        reported = source_reported.get(src, 0)
        rows.append({
            "source_name": src,
            "total_new": total,
            "reported_within_24h": reported,
            "error_rate": round(reported / total, 4),
        })
    rows.sort(key=lambda x: (-x["error_rate"], -x["total_new"], x["source_name"]))
    return {
        "sources": rows[:limit],
        "events_total": len(events),
        "human_reported_24h": len(human),
        "system_reported_24h": len(system),
        "min_new_events": min_new_events,
    }


def a3_scope_note(a3: dict) -> str:
    """One-line scope note shared by the evaluation md and docs_report."""
    return (
        f"只計前台回報（locale 非空）；只排名新事件 ≥ {a3.get('min_new_events', A3_MIN_NEW_EVENTS)} 筆的來源。"
        f"同期 24h 內：讀者回報 {a3.get('human_reported_24h', '?')} 筆事件，"
        f"系統自動回報 {a3.get('system_reported_24h', '?')} 筆事件（不計入）。"
    )


def _fetch_reports_for(sb, event_ids: list[str], caller: str) -> list[dict]:
    reports: list[dict] = []
    for i in range(0, len(event_ids), 200):
        batch = event_ids[i:i + 200]
        try:
            reports += (
                sb.table("event_reports")
                .select("event_id,created_at,locale")
                .in_("event_id", batch)
                .execute()
                .data or []
            )
        except Exception as exc:
            logger.warning("%s: event_reports batch failed: %s", caller, exc)
    return reports


def _first_pass_accuracy(sb) -> dict:
    """A3 — per source: events reported by readers within 24h of creation (30d)."""
    cutoff = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
    try:
        events = (
            sb.table("events")
            .select("id,source_name,created_at")
            .gte("created_at", cutoff)
            .eq("is_active", True)
            .is_("parent_event_id", "null")
            .execute()
            .data or []
        )
    except Exception as exc:
        logger.warning("_first_pass_accuracy: events fetch failed: %s", exc)
        return {"sources": []}

    if not events:
        return {"sources": []}

    reports = _fetch_reports_for(sb, [e["id"] for e in events], "_first_pass_accuracy")
    return _aggregate_first_pass(events, reports)


# ─── A4: Repair latency (median days from event creation to field_correction) ─

def _repair_latency(sb) -> dict:
    """A4 — per source: median days from event creation to a human field_correction."""
    cutoff = (datetime.now(tz=UTC) - timedelta(days=180)).isoformat()
    try:
        fc_rows, script = _fetch_human_corrections(sb, "event_id,created_at", cutoff)
    except Exception as exc:
        logger.warning("_repair_latency: field_corrections fetch failed: %s", exc)
        return {"sources": [], "script_corrections": None}

    if not fc_rows:
        return {"sources": [], "script_corrections": script}

    event_ids = list({r["event_id"] for r in fc_rows if r.get("event_id")})
    event_created_at: dict[str, str] = {}
    event_source: dict[str, str] = {}
    for i in range(0, len(event_ids), 200):
        batch = event_ids[i:i + 200]
        try:
            rows = (
                sb.table("events")
                .select("id,created_at,source_name")
                .in_("id", batch)
                .execute()
                .data or []
            )
            for r in rows:
                event_created_at[r["id"]] = r["created_at"]
                event_source[r["id"]] = r.get("source_name", "unknown")
        except Exception as exc:
            logger.warning("_repair_latency: events batch failed: %s", exc)

    return {**_aggregate_repair_latency(fc_rows, event_created_at, event_source), "script_corrections": script}



def _researcher_health(sb) -> dict:
    """Researcher 健康度 — research_sources status counts (30d).

    Plan v6 Phase 5' (降級版): 不新建 eval_researcher.py / golden set，
    只在 monthly health check 中加 retrospective 統計。後續 30 天 baseline
    收齊後再考慮設 LINE 警報門檻。

    Actual status taxonomy in production:
      - implemented  — scraper merged & shipping events (success)
      - not-viable   — researcher proposed but rejected (no-go)
      - candidate    — pending researcher follow-up
      - researched   — investigation done, awaiting decision

    Approval rate = implemented / (implemented + not-viable).
    """
    cutoff = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
    counts = {"implemented": 0, "not_viable": 0, "candidate": 0, "researched": 0, "other": 0}
    try:
        rows = (
            sb.table("research_sources")
            .select("status")
            .gte("created_at", cutoff)
            .execute()
            .data or []
        )
    except Exception as exc:
        logger.warning("_researcher_health: research_sources fetch failed: %s", exc)
        return {**counts, "total": -1, "approval_rate": None}

    for r in rows:
        st = (r.get("status") or "").strip().lower()
        if st == "implemented":
            counts["implemented"] += 1
        elif st in ("not-viable", "not_viable", "rejected"):
            counts["not_viable"] += 1
        elif st in ("candidate", "pending"):
            counts["candidate"] += 1
        elif st == "researched":
            counts["researched"] += 1
        else:
            counts["other"] += 1

    total = sum(counts.values())
    denom = counts["implemented"] + counts["not_viable"]
    approval_rate = round(counts["implemented"] / denom, 4) if denom else None
    return {**counts, "total": total, "approval_rate": approval_rate}


# ─── Read-only window-bounded metric helper (for deterministic docs reports) ──

def collect_monthly_health_metrics(
    sb,
    *,
    window_start: datetime,
    window_end_exclusive: datetime,
) -> dict:
    """Read-only governance + A1-A4 + researcher metrics for an explicit window.

    Every time-windowed query below is bounded by the explicit
    ``[window_start, window_end_exclusive)`` arguments and never infers the
    current month from execution time. This helper performs NO side effects:
    no LINE send, no DB cleanup, no markdown write. It is the only path the
    deterministic docs reporter should use.

    Args:
        sb: Supabase client.
        window_start: Inclusive JST window start.
        window_end_exclusive: Exclusive JST window end.

    Returns:
        Dict with confirmed reports, corrections, protect hits, exclusion hits,
        integrity flags, A1-A4 metrics, and researcher health — all bounded to
        the window.
    """
    start_iso = window_start.isoformat()
    end_iso = window_end_exclusive.isoformat()

    # ── Confirmed reports (by confirmed_at) ──────────────────────────────────
    reports = dict(irrelevant=0, wrongCategory=0, wrongDetails=0, wrongSelectionReason=0, total=0)
    try:
        rows = (
            sb.table("event_reports")
            .select("report_types")
            .eq("status", "confirmed")
            .gte("confirmed_at", start_iso)
            .lt("confirmed_at", end_iso)
            .execute()
            .data or []
        )
        for r in rows:
            reports["total"] += 1
            for t in (r.get("report_types") or []):
                if t in reports:
                    reports[t] += 1
    except Exception as exc:
        logger.warning("collect_monthly_health_metrics: confirmed reports failed: %s", exc)

    # ── Corrections counts (by created_at) ───────────────────────────────────
    corrections: dict[str, int | None] = {}
    for table in ("field_corrections", "category_corrections", "selection_reason_corrections"):
        try:
            resp = (
                sb.table(table)
                .select("id", count="exact", head=True)
                .gte("created_at", start_iso)
                .lt("created_at", end_iso)
                .execute()
            )
            corrections[table] = resp.count or 0
        except Exception as exc:
            logger.warning("collect_monthly_health_metrics: %s count failed: %s", table, exc)
            corrections[table] = None

    # ── Protect hits + annotated (annotator scraper_runs notes, by ran_at) ───
    protect_hits = 0
    annotated_total = 0
    try:
        run_rows = (
            sb.table("scraper_runs")
            .select("notes,ran_at")
            .eq("source", "annotator")
            .gte("ran_at", start_iso)
            .lt("ran_at", end_iso)
            .execute()
            .data or []
        )
        for r in run_rows:
            run_hits, run_annotated = _parse_annotator_notes(r.get("notes") or "")
            protect_hits += run_hits
            annotated_total += run_annotated
    except Exception as exc:
        logger.warning("collect_monthly_health_metrics: protect_hits failed: %s", exc)
        protect_hits = -1

    a2 = {
        "hits": protect_hits,
        "annotated": annotated_total,
        "fields_per_event": _fields_per_event(protect_hits, annotated_total),
    }

    # ── Exclusion hits (by matched_at) ───────────────────────────────────────
    excl_hits = 0
    try:
        resp = (
            sb.table("source_exclusion_hits")
            .select("id", count="exact", head=True)
            .gte("matched_at", start_iso)
            .lt("matched_at", end_iso)
            .execute()
        )
        excl_hits = resp.count or 0
    except Exception as exc:
        logger.debug("collect_monthly_health_metrics: exclusion_hits failed: %s", exc)

    # ── Shared helper: source_name lookup for a set of event_ids ─────────────
    def _sources_for(event_ids: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for i in range(0, len(event_ids), 200):
            batch = event_ids[i:i + 200]
            try:
                rows = (
                    sb.table("events").select("id,source_name").in_("id", batch).execute().data or []
                )
                for r in rows:
                    out[r["id"]] = r.get("source_name", "unknown")
            except Exception as exc:
                logger.warning("collect_monthly_health_metrics: events source batch failed: %s", exc)
        return out

    # ── A1: recurrence (source×field corrected by a human ≥2 within window) ──
    a1 = {"recurrence_pairs": 0, "top_pairs": [], "script_corrections": None}
    try:
        fc_rows, script = _fetch_human_corrections(sb, "event_id,field_name,created_at", start_iso, end_iso)
        a1["script_corrections"] = script
        if fc_rows:
            source_by_event = _sources_for(list({r["event_id"] for r in fc_rows if r.get("event_id")}))
            a1 = {**_aggregate_recurrence(fc_rows, source_by_event), "script_corrections": script}
    except Exception as exc:
        logger.warning("collect_monthly_health_metrics: A1 recurrence failed: %s", exc)
        a1 = {"recurrence_pairs": -1, "top_pairs": [], "script_corrections": None}

    # ── A3: first-pass accuracy (events created within window) ───────────────
    a3 = {"sources": []}
    try:
        events = (
            sb.table("events")
            .select("id,source_name,created_at")
            .gte("created_at", start_iso)
            .lt("created_at", end_iso)
            .eq("is_active", True)
            .is_("parent_event_id", "null")
            .execute()
            .data or []
        )
        if events:
            reports = _fetch_reports_for(
                sb, [e["id"] for e in events], "collect_monthly_health_metrics: A3",
            )
            a3 = _aggregate_first_pass(events, reports)
    except Exception as exc:
        logger.warning("collect_monthly_health_metrics: A3 first-pass failed: %s", exc)

    # ── A4: repair latency (human field_corrections created within window) ───
    a4 = {"sources": [], "script_corrections": None}
    try:
        fc_rows, script = _fetch_human_corrections(sb, "event_id,created_at", start_iso, end_iso)
        a4["script_corrections"] = script
        if fc_rows:
            event_ids = list({r["event_id"] for r in fc_rows if r.get("event_id")})
            event_created_at: dict[str, str] = {}
            event_source: dict[str, str] = {}
            for i in range(0, len(event_ids), 200):
                batch = event_ids[i:i + 200]
                try:
                    rows = (
                        sb.table("events")
                        .select("id,created_at,source_name")
                        .in_("id", batch)
                        .execute()
                        .data or []
                    )
                    for r in rows:
                        event_created_at[r["id"]] = r["created_at"]
                        event_source[r["id"]] = r.get("source_name", "unknown")
                except Exception as exc:
                    logger.warning("collect_monthly_health_metrics: A4 events batch failed: %s", exc)
            a4 = {**_aggregate_repair_latency(fc_rows, event_created_at, event_source), "script_corrections": script}
    except Exception as exc:
        logger.warning("collect_monthly_health_metrics: A4 repair latency failed: %s", exc)

    # ── Researcher health (research_sources created within window) ───────────
    counts = {"implemented": 0, "not_viable": 0, "candidate": 0, "researched": 0, "other": 0}
    try:
        rs_rows = (
            sb.table("research_sources")
            .select("status")
            .gte("created_at", start_iso)
            .lt("created_at", end_iso)
            .execute()
            .data or []
        )
        for r in rs_rows:
            st = (r.get("status") or "").strip().lower()
            if st == "implemented":
                counts["implemented"] += 1
            elif st in ("not-viable", "not_viable", "rejected"):
                counts["not_viable"] += 1
            elif st in ("candidate", "pending"):
                counts["candidate"] += 1
            elif st == "researched":
                counts["researched"] += 1
            else:
                counts["other"] += 1
        rs_total = sum(counts.values())
        denom = counts["implemented"] + counts["not_viable"]
        researcher = {**counts, "total": rs_total, "approval_rate": round(counts["implemented"] / denom, 4) if denom else None}
    except Exception as exc:
        logger.warning("collect_monthly_health_metrics: researcher health failed: %s", exc)
        researcher = {**counts, "total": -1, "approval_rate": None}

    return {
        "window_start": start_iso,
        "window_end_exclusive": end_iso,
        "reports": reports,
        "corrections": corrections,
        "protect_hits": protect_hits,
        "exclusion_hits": excl_hits,
        "integrity_flags": _integrity_flags(reports, corrections),
        "a1_recurrence": a1,
        "a2_protect_trend": a2,
        "a3_first_pass": a3,
        "a4_repair_latency": a4,
        "researcher_health": researcher,
    }


def build_line_message(reports: dict, corrections: dict, protect_hits: int, excl_hits: int,
                       cleanup: dict | None = None,
                       a1: dict | None = None, a2: dict | None = None,
                       a3: dict | None = None, a4: dict | None = None,
                       researcher: dict | None = None) -> str:
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

    # A1–A4 evaluation metrics (appended as Step 6)
    if a1 is not None or a2 is not None or a3 is not None or a4 is not None:
        lines.append("")
        lines.append("【閉環效能指標（Evaluation A1–A4）】")

    if a1 is not None:
        n = a1.get("recurrence_pairs", -1)
        top = a1.get("top_pairs", [])
        if n >= 0:
            script = a1.get("script_corrections")
            script_str = f"，腳本寫入 {script} 筆不計" if script is not None else ""
            lines.append(f"  A1 重犯率 (90d): {n} 對 (source×field 人工修正 ≥2 次{script_str})")
            if top:
                lines.append(f"    最高: {top[0]['source_name']}/{top[0]['field_name']} ×{top[0]['count']}")
        else:
            lines.append("  A1 重犯率: 取得失敗")

    if a2 is not None:
        f30 = a2.get("fields_per_event_30d")
        h30 = a2.get("hit_30d", "?")
        h90 = a2.get("hit_90d", "?")
        per_event = f"{f30:.2f}" if f30 is not None else "n/a"
        lines.append(f"  A2 每筆受保護欄位數 (30d): {per_event}（{h30} 欄位次）| 90d: {h90} 欄位次")

    if a3 is not None:
        sources = a3.get("sources", [])
        if sources:
            top_src = sources[0]
            lines.append(
                f"  A3 讀者 24h 報錯 (30d): 最高 {top_src['source_name']} "
                f"{top_src['error_rate']:.1%} ({top_src['reported_within_24h']}/{top_src['total_new']})"
            )
        else:
            lines.append("  A3 讀者 24h 報錯: 無資料")

    if a4 is not None:
        sources = a4.get("sources", [])
        if sources:
            top_src = sources[0]
            lines.append(
                f"  A4 修復延遲 (180d): 最高 {top_src['source_name']} "
                f"中位數 {top_src['median_days']} 天 (n={top_src['n_corrections']})"
            )
        else:
            lines.append("  A4 修復延遲: 無人工修正")

    # Researcher 健康度（Plan v6 Phase 5'）
    if researcher is not None:
        lines.append("")
        lines.append("【Researcher 健康度（30d）】")
        rate = researcher.get("approval_rate")
        rate_str = f"{rate:.1%}" if rate is not None else "n/a"
        lines.append(
            f"  implemented {researcher.get('implemented', '?')} / "
            f"not-viable {researcher.get('not_viable', '?')} / "
            f"candidate {researcher.get('candidate', '?')} / "
            f"researched {researcher.get('researched', '?')}"
        )
        lines.append(f"  通過率: {rate_str}（implemented / (implemented+not-viable)）")

    return "\n".join(lines)


def _write_evaluation_md(
    a1: dict, a2: dict, a3: dict, a4: dict,
    protect_hits: int, corrections: dict,
    researcher: dict | None = None,
) -> Path:
    """Write detailed A1–A4 evaluation markdown to docs/evaluation/feedback_loop/.

    Kept under docs/evaluation/ (not docs/monthly_review/) so it never becomes a
    second canonical monthly-review main file. The canonical merged monthly
    review is produced by docs_report.py at docs/monthly_review/<YYYY-MM>.md.
    """
    month = datetime.now(tz=JST).strftime("%Y-%m")
    docs_dir = Path(__file__).resolve().parent.parent / "docs" / "evaluation" / "feedback_loop"
    docs_dir.mkdir(parents=True, exist_ok=True)
    out_path = docs_dir / f"{month}-evaluation.md"

    now_jst = datetime.now(tz=JST).strftime("%Y-%m-%d %H:%M JST")
    lines = [
        f"# 閉環效能指標 — {month}",
        f"_Generated: {now_jst}_",
        "",
        "## A1 — 重犯率（Recurrence Rate）",
        f"過去 90 天中，同一 source × field_name 被修正 ≥ 2 次的組合數：**{a1.get('recurrence_pairs', 'n/a')}**",
        script_corrections_note(a1),
        "",
    ]

    top_pairs = a1.get("top_pairs", [])
    if top_pairs:
        lines += ["| source_name | field_name | count |", "|---|---|---|"]
        for p in top_pairs:
            lines.append(f"| {p['source_name']} | {p['field_name']} | {p['count']} |")
    else:
        lines.append("_No recurring correction pairs found._")

    lines += [
        "",
        "## A2 — 每筆受保護欄位數（Protected Fields per Event）",
        "field_protect_hits 以欄位計數，一筆事件可貢獻多次，因此這是每筆平均值，不是百分比。",
        "",
        "| 期間 | 受保護欄位次 | Annotated Events | 每筆平均 |",
        "|---|---|---|---|",
    ]
    for period in ("30d", "60d", "90d"):
        hits = a2.get(f"hit_{period}", "?")
        annotated = a2.get(f"annotated_{period}", "?")
        per_event = a2.get(f"fields_per_event_{period}")
        per_event_str = f"{per_event:.2f}" if per_event is not None else "n/a"
        lines.append(f"| {period} | {hits} | {annotated} | {per_event_str} |")

    lines += [
        "",
        "## A3 — 首次正確率（First-Pass Accuracy）",
        "過去 30 天新事件中，24h 內被讀者從前台報錯的比例（per source）。",
        a3_scope_note(a3),
        "",
        "| source_name | 新事件數 | 24h 內報錯 | 錯誤率 |",
        "|---|---|---|---|",
    ]
    for s in a3.get("sources", []):
        lines.append(
            f"| {s['source_name']} | {s['total_new']} | {s['reported_within_24h']} | {s['error_rate']:.1%} |"
        )
    if not a3.get("sources"):
        lines.append("_No data_")

    lines += [
        "",
        "## A4 — 修復延遲（Repair Latency）",
        "過去 180 天 field_corrections.created_at − events.created_at 中位數（per source）：",
        script_corrections_note(a4),
        "",
        "| source_name | 修正次數 | 中位數（天） |",
        "|---|---|---|",
    ]
    for s in a4.get("sources", []):
        lines.append(f"| {s['source_name']} | {s['n_corrections']} | {s['median_days']} |")
    if not a4.get("sources"):
        lines.append("_No data_")

    lines += [
        "",
        "## 其他健檢指標（摘要）",
        f"- field_protect_hits (30d): {protect_hits if protect_hits >= 0 else 'n/a'}",
        f"- field_corrections (30d): {corrections.get('field_corrections', '?')}",
        f"- category_corrections (30d): {corrections.get('category_corrections', '?')}",
        f"- selection_reason_corrections (30d): {corrections.get('selection_reason_corrections', '?')}",
    ]

    # Researcher 健康度（Plan v6 Phase 5'）
    if researcher is not None:
        rate = researcher.get("approval_rate")
        rate_str = f"{rate:.1%}" if rate is not None else "n/a"
        lines += [
            "",
            "## Researcher 健康度（30d）",
            "過去 30 天 `research_sources` 各 status 計數（retrospective）：",
            "",
            "| status | count |",
            "|---|---|",
            f"| implemented | {researcher.get('implemented', 0)} |",
            f"| not-viable | {researcher.get('not_viable', 0)} |",
            f"| candidate | {researcher.get('candidate', 0)} |",
            f"| researched | {researcher.get('researched', 0)} |",
            f"| other | {researcher.get('other', 0)} |",
            f"| **total** | **{researcher.get('total', 0)}** |",
            "",
            f"通過率：**{rate_str}** （implemented / (implemented + not-viable)）",
            "",
            "_v6 降級版：先觀察 30–60 天 baseline 再考慮 LINE 警報門檻。_",
        ]

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Evaluation markdown written: %s", out_path)
    return out_path


# ─── Main ─────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> dict:
    sb = _get_sb()
    reports = _count_confirmed_reports(sb)
    corrections = _count_corrections(sb)
    protect_hits = _count_protect_hits(sb)
    excl_hits = _count_exclusion_hits(sb)

    # A1–A4 evaluation metrics
    a1 = _count_recurrence(sb)
    a2 = _protect_hit_trend(sb)
    a3 = _first_pass_accuracy(sb)
    a4 = _repair_latency(sb)

    # Researcher 健康度（Plan v6 Phase 5'）
    researcher = _researcher_health(sb)

    cleanup = None
    if not dry_run:
        cleanup = _cleanup_old_records(sb)

    msg = build_line_message(reports, corrections, protect_hits, excl_hits, cleanup, a1, a2, a3, a4, researcher)
    flags = _integrity_flags(reports, corrections)

    # Write evaluation markdown
    eval_md_path = None
    try:
        eval_md_path = str(_write_evaluation_md(a1, a2, a3, a4, protect_hits, corrections, researcher))
    except Exception as exc:
        logger.warning("Could not write evaluation md: %s", exc)

    summary = {
        "month": datetime.now(tz=JST).strftime("%Y-%m"),
        "reports": reports,
        "corrections": corrections,
        "protect_hits_30d": protect_hits,
        "exclusion_hits_30d": excl_hits,
        "cleanup": cleanup,
        "integrity_flags": flags,
        "a1_recurrence": a1,
        "a2_protect_trend": a2,
        "a3_first_pass": a3,
        "a4_repair_latency": a4,
        "researcher_health": researcher,
        "eval_md": eval_md_path,
        "message_preview": msg[:200],
    }

    if dry_run:
        logger.info("[dry-run] LINE message:\n%s", msg)
        logger.info("[dry-run] recurrence=%s protected_fields_per_event=%s first_pass=%s repair_latency=%s researcher=%s",
                    a1.get("recurrence_pairs"), a2.get("fields_per_event_30d"),
                    a3.get("sources", [])[:1], a4.get("sources", [])[:1],
                    researcher.get("approval_rate"))
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
