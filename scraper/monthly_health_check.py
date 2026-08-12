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


# ─── A1: Recurrence rate (same source×field corrected ≥2 times in 90d) ──────

def _count_recurrence(sb) -> dict:
    """A1 — (source_name, field_name) pairs corrected ≥ 2 times in last 90 days."""
    cutoff = (datetime.now(tz=UTC) - timedelta(days=90)).isoformat()
    try:
        fc_rows = (
            sb.table("field_corrections")
            .select("event_id,field_name,created_at")
            .gte("created_at", cutoff)
            .execute()
            .data or []
        )
    except Exception as exc:
        logger.warning("_count_recurrence: field_corrections fetch failed: %s", exc)
        return {"recurrence_pairs": -1, "top_pairs": []}

    if not fc_rows:
        return {"recurrence_pairs": 0, "top_pairs": []}

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

    # Count (source_name, field_name) occurrences
    pair_counts: dict[tuple[str, str], int] = {}
    for row in fc_rows:
        eid = row.get("event_id", "")
        source = source_by_event.get(eid, "unknown")
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


# ─── A2: Protect hit trend (30/60/90 day windows) ────────────────────────────

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
            notes = r.get("notes") or ""
            m_hits = re.search(r"field_protect_hits=(\d+)", notes)
            # Explicit denominator first, batch size as the historical fallback.
            m_ann = re.search(r"(?<![a-z_])annotated=(\d+)", notes) \
                or re.search(r"(?<![a-z_])total=(\d+)", notes)
            if m_hits:
                hits += int(m_hits.group(1))
            if m_ann:
                annotated += int(m_ann.group(1))
        result[f"hit_{label}"] = hits
        result[f"annotated_{label}"] = annotated
        result[f"rate_{label}"] = round(hits / annotated, 4) if annotated else None

    return result


# ─── A3: First-pass accuracy (reported within 24h / new events, per source) ──

def _first_pass_accuracy(sb) -> dict:
    """A3 — per source: events reported via event_reports within 24h of creation."""
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

    event_ids = [e["id"] for e in events]
    created_at_by_id = {e["id"]: e["created_at"] for e in events}

    # Fetch event_reports for those events
    reports_within_24h: dict[str, bool] = {}
    for i in range(0, len(event_ids), 200):
        batch = event_ids[i:i + 200]
        try:
            reps = (
                sb.table("event_reports")
                .select("event_id,created_at")
                .in_("event_id", batch)
                .execute()
                .data or []
            )
            for rep in reps:
                eid = rep.get("event_id")
                if not eid:
                    continue
                ev_created = created_at_by_id.get(eid)
                rep_created = rep.get("created_at")
                if ev_created and rep_created:
                    try:
                        ev_dt = datetime.fromisoformat(ev_created.replace("Z", "+00:00"))
                        rep_dt = datetime.fromisoformat(rep_created.replace("Z", "+00:00"))
                        if (rep_dt - ev_dt).total_seconds() < 86400:
                            reports_within_24h[eid] = True
                    except Exception:
                        pass
        except Exception as exc:
            logger.warning("_first_pass_accuracy: event_reports batch failed: %s", exc)

    # Aggregate per source
    source_total: dict[str, int] = {}
    source_reported: dict[str, int] = {}
    source_by_source: dict[str, str] = {}
    for e in events:
        src = e.get("source_name", "unknown")
        eid = e["id"]
        source_total[src] = source_total.get(src, 0) + 1
        if eid in reports_within_24h:
            source_reported[src] = source_reported.get(src, 0) + 1

    rows = []
    for src, total in source_total.items():
        reported = source_reported.get(src, 0)
        rate = reported / total if total else 0.0
        rows.append({"source_name": src, "total_new": total, "reported_within_24h": reported, "error_rate": round(rate, 4)})

    rows.sort(key=lambda x: -x["error_rate"])
    return {"sources": rows[:10]}


# ─── A4: Repair latency (median days from event creation to field_correction) ─

def _repair_latency(sb) -> dict:
    """A4 — per source: median days from event creation to field_corrections."""
    cutoff = (datetime.now(tz=UTC) - timedelta(days=180)).isoformat()
    try:
        fc_rows = (
            sb.table("field_corrections")
            .select("event_id,created_at")
            .gte("created_at", cutoff)
            .execute()
            .data or []
        )
    except Exception as exc:
        logger.warning("_repair_latency: field_corrections fetch failed: %s", exc)
        return {"sources": []}

    if not fc_rows:
        return {"sources": []}

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

    # Compute latency in days per source
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
        src = event_source.get(eid, "unknown")
        source_latencies.setdefault(src, []).append(days)

    rows = []
    for src, lats in source_latencies.items():
        if not lats:
            continue
        med = median(lats)
        rows.append({"source_name": src, "n_corrections": len(lats), "median_days": round(med, 1)})

    rows.sort(key=lambda x: -x["median_days"])
    return {"sources": rows[:5]}



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
            notes = r.get("notes") or ""
            m_hits = re.search(r"field_protect_hits=(\d+)", notes)
            m_ann = re.search(r"annotated=(\d+)", notes)
            if m_hits:
                protect_hits += int(m_hits.group(1))
            if m_ann:
                annotated_total += int(m_ann.group(1))
    except Exception as exc:
        logger.warning("collect_monthly_health_metrics: protect_hits failed: %s", exc)
        protect_hits = -1

    a2 = {
        "hits": protect_hits,
        "annotated": annotated_total,
        "rate": round(protect_hits / annotated_total, 4) if annotated_total and protect_hits >= 0 else None,
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

    # ── A1: recurrence (source×field corrected ≥2 within window) ─────────────
    a1 = {"recurrence_pairs": 0, "top_pairs": []}
    try:
        fc_rows = (
            sb.table("field_corrections")
            .select("event_id,field_name,created_at")
            .gte("created_at", start_iso)
            .lt("created_at", end_iso)
            .execute()
            .data or []
        )
        if fc_rows:
            source_by_event = _sources_for(list({r["event_id"] for r in fc_rows if r.get("event_id")}))
            pair_counts: dict[tuple[str, str], int] = {}
            for row in fc_rows:
                source = source_by_event.get(row.get("event_id", ""), "unknown")
                field = row.get("field_name", "")
                if source and field:
                    pair_counts[(source, field)] = pair_counts.get((source, field), 0) + 1
            recurring = {p: c for p, c in pair_counts.items() if c >= 2}
            top = sorted(recurring.items(), key=lambda x: -x[1])[:10]
            a1 = {
                "recurrence_pairs": len(recurring),
                "top_pairs": [
                    {"source_name": src, "field_name": fld, "count": cnt}
                    for (src, fld), cnt in top
                ],
            }
    except Exception as exc:
        logger.warning("collect_monthly_health_metrics: A1 recurrence failed: %s", exc)
        a1 = {"recurrence_pairs": -1, "top_pairs": []}

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
            created_at_by_id = {e["id"]: e["created_at"] for e in events}
            event_ids = [e["id"] for e in events]
            reports_within_24h: dict[str, bool] = {}
            for i in range(0, len(event_ids), 200):
                batch = event_ids[i:i + 200]
                try:
                    reps = (
                        sb.table("event_reports")
                        .select("event_id,created_at")
                        .in_("event_id", batch)
                        .execute()
                        .data or []
                    )
                    for rep in reps:
                        eid = rep.get("event_id")
                        ev_created = created_at_by_id.get(eid)
                        rep_created = rep.get("created_at")
                        if eid and ev_created and rep_created:
                            try:
                                ev_dt = datetime.fromisoformat(ev_created.replace("Z", "+00:00"))
                                rep_dt = datetime.fromisoformat(rep_created.replace("Z", "+00:00"))
                                if 0 <= (rep_dt - ev_dt).total_seconds() < 86400:
                                    reports_within_24h[eid] = True
                            except Exception:
                                pass
                except Exception as exc:
                    logger.warning("collect_monthly_health_metrics: A3 reports batch failed: %s", exc)
            source_total: dict[str, int] = {}
            source_reported: dict[str, int] = {}
            for e in events:
                src = e.get("source_name", "unknown")
                source_total[src] = source_total.get(src, 0) + 1
                if e["id"] in reports_within_24h:
                    source_reported[src] = source_reported.get(src, 0) + 1
            rows = []
            for src, total in source_total.items():
                reported = source_reported.get(src, 0)
                rows.append({
                    "source_name": src,
                    "total_new": total,
                    "reported_within_24h": reported,
                    "error_rate": round(reported / total, 4) if total else 0.0,
                })
            rows.sort(key=lambda x: -x["error_rate"])
            a3 = {"sources": rows[:10]}
    except Exception as exc:
        logger.warning("collect_monthly_health_metrics: A3 first-pass failed: %s", exc)

    # ── A4: repair latency (field_corrections created within window) ─────────
    a4 = {"sources": []}
    try:
        fc_rows = (
            sb.table("field_corrections")
            .select("event_id,created_at")
            .gte("created_at", start_iso)
            .lt("created_at", end_iso)
            .execute()
            .data or []
        )
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
            rows = []
            for src, lats in source_latencies.items():
                if lats:
                    rows.append({"source_name": src, "n_corrections": len(lats), "median_days": round(median(lats), 1)})
            rows.sort(key=lambda x: -x["median_days"])
            a4 = {"sources": rows[:5]}
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
            lines.append(f"  A1 重犯率 (90d): {n} 對 (source×field 修正 ≥2 次)")
            if top:
                lines.append(f"    最高: {top[0]['source_name']}/{top[0]['field_name']} ×{top[0]['count']}")
        else:
            lines.append("  A1 重犯率: 取得失敗")

    if a2 is not None:
        r30 = a2.get("rate_30d")
        h30 = a2.get("hit_30d", "?")
        h90 = a2.get("hit_90d", "?")
        rate_str = f"{r30:.2%}" if r30 is not None else "n/a"
        lines.append(f"  A2 保護命中率 (30d): {h30} hits ({rate_str}) | 90d: {h90} hits")

    if a3 is not None:
        sources = a3.get("sources", [])
        if sources:
            top_src = sources[0]
            lines.append(
                f"  A3 首次正確率 (30d): 最高錯誤率 {top_src['source_name']} "
                f"{top_src['error_rate']:.1%} ({top_src['reported_within_24h']}/{top_src['total_new']})"
            )
        else:
            lines.append("  A3 首次正確率: 無資料")

    if a4 is not None:
        sources = a4.get("sources", [])
        if sources:
            top_src = sources[0]
            lines.append(
                f"  A4 修復延遲 (180d): 最高 {top_src['source_name']} "
                f"中位數 {top_src['median_days']} 天 (n={top_src['n_corrections']})"
            )
        else:
            lines.append("  A4 修復延遲: 無資料")

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
        "## A2 — 保護命中率趨勢（Protect Hit Rate Trend）",
        "| 期間 | Protect Hits | Annotated Events | 命中率 |",
        "|---|---|---|---|",
    ]
    for period in ("30d", "60d", "90d"):
        hits = a2.get(f"hit_{period}", "?")
        annotated = a2.get(f"annotated_{period}", "?")
        rate = a2.get(f"rate_{period}")
        rate_str = f"{rate:.2%}" if rate is not None else "n/a"
        lines.append(f"| {period} | {hits} | {annotated} | {rate_str} |")

    lines += [
        "",
        "## A3 — 首次正確率（First-Pass Accuracy）",
        "過去 30 天新事件中，24h 內被 event_reports 報錯的比例（per source）：",
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
        logger.info("[dry-run] recurrence=%s protect_hit_rate=%s first_pass=%s repair_latency=%s researcher=%s",
                    a1.get("recurrence_pairs"), a2.get("rate_30d"),
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
