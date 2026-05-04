"""
backlog_health.py — CI backlog health snapshot.

Outputs a single-line JSON to stdout (same pattern as summarize_run.py).
Used by scraper.yml "Backlog health snapshot" step to:
  - write $GITHUB_OUTPUT json=<payload>
  - write $GITHUB_STEP_SUMMARY with a human-readable table
  - emit ::warning:: when status != ok

Status thresholds (based on current baseline, 2026-05-04):
  ok       : active_pending <= 150  AND  old_pending_over_7d <= 30
  warn     : active_pending 151–250 OR   old_pending_over_7d 31–80
  critical : active_pending > 250   OR   old_pending_over_7d > 80

Exit code:
  0 always — the step must not fail on its own; caller decides action.

Usage:
    python backlog_health.py
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

UTC = timezone.utc

# ── Thresholds ────────────────────────────────────────────────────────────────
WARN_ACTIVE     = 150   # active pending count
CRITICAL_ACTIVE = 250
WARN_OLD        = 30    # pending events older than 7 days
CRITICAL_OLD    = 80


def _supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _determine_status(active_pending: int, old_pending: int) -> str:
    if active_pending > CRITICAL_ACTIVE or old_pending > CRITICAL_OLD:
        return "critical"
    if active_pending > WARN_ACTIVE or old_pending > WARN_OLD:
        return "warn"
    return "ok"


def main() -> None:
    try:
        sb = _supabase_client()

        # 1. Total active pending (non-sub-events)
        active_res = (
            sb.table("events")
            .select("id", count="exact")
            .eq("annotation_status", "pending")
            .eq("is_active", True)
            .is_("parent_event_id", "null")
            .execute()
        )
        active_pending: int = active_res.count or 0

        # 2. Pending events older than 7 days (likely stuck)
        cutoff = (datetime.now(tz=UTC) - timedelta(days=7)).isoformat()
        old_res = (
            sb.table("events")
            .select("id", count="exact")
            .eq("annotation_status", "pending")
            .eq("is_active", True)
            .is_("parent_event_id", "null")
            .lt("created_at", cutoff)
            .execute()
        )
        old_pending: int = old_res.count or 0

        # 3. Sub-event pending (should be near-zero; flags annotator bugs)
        # Use .filter("parent_event_id", "not.is", "null") — not_() has quirks in this SDK version
        sub_rows = (
            sb.table("events")
            .select("id")
            .eq("annotation_status", "pending")
            .filter("parent_event_id", "not.is", "null")
            .limit(500)
            .execute()
        )
        subevent_pending: int = len(sub_rows.data or [])

        # 4. Top 5 sources contributing to active pending (for triage)
        rows = (
            sb.table("events")
            .select("source_name")
            .eq("annotation_status", "pending")
            .eq("is_active", True)
            .is_("parent_event_id", "null")
            .limit(2000)
            .execute()
        )
        top_sources = [
            {"source": src, "count": n}
            for src, n in Counter(r["source_name"] for r in (rows.data or [])).most_common(5)
        ]

        status = _determine_status(active_pending, old_pending)

        result = {
            "status": status,
            "active_pending": active_pending,
            "old_pending_over_7d": old_pending,
            "subevent_pending": subevent_pending,
            "top_sources": top_sources,
        }

        print(json.dumps(result, ensure_ascii=False))

    except Exception as exc:
        logger.error("backlog_health failed: %s", exc)
        # Graceful degradation — emit unknown status so notify doesn't crash
        print(json.dumps({"status": "unknown", "error": str(exc)}))


if __name__ == "__main__":
    main()
