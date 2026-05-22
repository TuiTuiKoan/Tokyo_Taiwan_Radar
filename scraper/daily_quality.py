"""
daily_quality.py — Compute daily_quality_metrics.

For each of the last RECOMPUTE_DAYS days, count:
  events_upserted   — parent events with DATE(scraped_at) = day
  events_active     — same as above + is_active = true
  exclusion_hits    — source_exclusion_hits with DATE(matched_at) = day
  irrelevant_reports — event_reports.report_types contains 'irrelevant'
                       AND linked event's scraped_at::date = day
  precision_rate    — 1 - irrelevant_reports / max(events_upserted, 1)

Upsert each row into daily_quality_metrics (PRIMARY KEY metric_date).

Outputs JSON summary on stdout for CI consumption.
LINE alert when precision_rate < 0.85 on the most recent computed day.

Usage:
  python daily_quality.py                # default: last 14 days
  python daily_quality.py --backfill 30  # recompute last 30 days
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

logger = logging.getLogger(__name__)

UTC = timezone.utc
RECOMPUTE_DAYS = 14
LOW_PRECISION_THRESHOLD = 0.85


def _get_sb():
    load_dotenv()
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _count_events_for_day(sb, day: date, *, only_active: bool) -> int:
    """Count parent events whose scraped_at::date = day."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=UTC).isoformat()
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UTC).isoformat()
    q = (
        sb.table("events")
        .select("id", count="exact", head=True)
        .gte("scraped_at", start)
        .lt("scraped_at", end)
        .is_("parent_event_id", "null")
    )
    if only_active:
        q = q.eq("is_active", True)
    try:
        resp = q.execute()
        return resp.count or 0
    except Exception as exc:
        logger.warning("count events for %s failed: %s", day, exc)
        return 0


def _count_exclusion_hits(sb, day: date) -> int:
    start = datetime.combine(day, datetime.min.time(), tzinfo=UTC).isoformat()
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UTC).isoformat()
    try:
        resp = (
            sb.table("source_exclusion_hits")
            .select("id", count="exact", head=True)
            .gte("matched_at", start)
            .lt("matched_at", end)
            .execute()
        )
        return resp.count or 0
    except Exception as exc:
        logger.debug("exclusion_hits for %s skipped: %s", day, exc)
        return 0


def _count_irrelevant_for_day(sb, day: date) -> int:
    """Count event_reports with 'irrelevant' linked to events scraped on `day`."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=UTC).isoformat()
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UTC).isoformat()
    try:
        ev_resp = (
            sb.table("events")
            .select("id")
            .gte("scraped_at", start)
            .lt("scraped_at", end)
            .is_("parent_event_id", "null")
            .execute()
        )
        ids = [r["id"] for r in ev_resp.data or []]
        if not ids:
            return 0
        # Chunk to stay within URL limits
        total = 0
        CHUNK = 200
        for i in range(0, len(ids), CHUNK):
            chunk = ids[i : i + CHUNK]
            rep_resp = (
                sb.table("event_reports")
                .select("id, report_types")
                .in_("event_id", chunk)
                .execute()
            )
            for row in rep_resp.data or []:
                if "irrelevant" in (row.get("report_types") or []):
                    total += 1
        return total
    except Exception as exc:
        logger.warning("irrelevant count for %s failed: %s", day, exc)
        return 0


def _count_fc_override_attempts(sb, day: date) -> int:
    """Count field_corrections rows whose override_attempted_at falls on `day`.

    Migration 060 added override_attempted_at. The annotator B1 guard writes
    this timestamp every time enrich tries to overwrite an FC-locked value.
    Used as a baseline metric — no LINE alert until 30d baseline is collected.
    """
    start = datetime.combine(day, datetime.min.time(), tzinfo=UTC).isoformat()
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UTC).isoformat()
    try:
        resp = (
            sb.table("field_corrections")
            .select("id", count="exact", head=True)
            .gte("override_attempted_at", start)
            .lt("override_attempted_at", end)
            .execute()
        )
        return resp.count or 0
    except Exception as exc:
        logger.debug("fc_override_attempts for %s skipped: %s", day, exc)
        return 0


def compute_day(sb, day: date) -> dict:
    events_upserted = _count_events_for_day(sb, day, only_active=False)
    events_active   = _count_events_for_day(sb, day, only_active=True)
    excl_hits       = _count_exclusion_hits(sb, day)
    irrelevant      = _count_irrelevant_for_day(sb, day)
    fc_overrides    = _count_fc_override_attempts(sb, day)
    precision = None
    if events_upserted > 0:
        precision = round(1.0 - (irrelevant / events_upserted), 4)
    return {
        "metric_date":          day.isoformat(),
        "events_upserted":      events_upserted,
        "events_active":        events_active,
        "exclusion_hits":       excl_hits,
        "irrelevant_reports":   irrelevant,
        "precision_rate":       precision,
        "fc_override_attempts": fc_overrides,
        "computed_at":          datetime.now(tz=UTC).isoformat(),
    }


def run(days: int) -> dict:
    sb = _get_sb()
    today = datetime.now(tz=UTC).date()
    rows = []
    for offset in range(days):
        d = today - timedelta(days=offset)
        rows.append(compute_day(sb, d))

    if rows:
        try:
            sb.table("daily_quality_metrics").upsert(rows, on_conflict="metric_date").execute()
        except Exception as exc:
            logger.error("upsert daily_quality_metrics failed: %s", exc)

    latest = rows[0] if rows else None
    summary = {
        "days_computed": len(rows),
        "latest": latest,
        "alert": None,
    }
    if latest and latest.get("precision_rate") is not None and latest["events_upserted"] >= 5:
        if latest["precision_rate"] < LOW_PRECISION_THRESHOLD:
            summary["alert"] = (
                f"\u26a0\ufe0f precision_rate {latest['precision_rate']:.2%} on "
                f"{latest['metric_date']} (events={latest['events_upserted']}, "
                f"irrelevant={latest['irrelevant_reports']})"
            )
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", type=int, default=RECOMPUTE_DAYS,
                    help=f"Number of days to recompute (default {RECOMPUTE_DAYS})")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    summary = run(args.backfill)
    print(json.dumps(summary, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
