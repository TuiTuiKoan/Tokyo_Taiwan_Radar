"""
backlog_health.py — CI backlog health snapshot

Outputs a single-line JSON to stdout summarising the current annotation
backlog.  Designed to be called from scraper.yml as a dedicated step so
the result can be forwarded to notify.py for LINE alerting.

Output JSON fields:
  status            "ok" | "warn" | "critical"
  active_pending    int — is_active=True, annotation_status='pending'
  old_pending_over_7d  int — active pending created > 7 days ago
  subevent_pending  int — pending with parent_event_id IS NOT NULL (should be 0)
  top_sources       list[{source, count}] — top-5 active-pending sources

Thresholds:
  warn     : active_pending > 150  OR  old_pending_over_7d > 30
  critical : active_pending > 250  OR  old_pending_over_7d > 80
  ok       : neither

Usage:
    python backlog_health.py
    HEALTH=$(python backlog_health.py)
    echo "json=$HEALTH" >> $GITHUB_OUTPUT
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

UTC = timezone.utc

# ── Thresholds ────────────────────────────────────────────────────────────────
WARN_ACTIVE     = 150   # active pending > this → warn
WARN_OLD        = 30    # >7d pending    > this → warn
CRITICAL_ACTIVE = 250   # active pending > this → critical
CRITICAL_OLD    = 80    # >7d pending    > this → critical


def _supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def main() -> None:
    try:
        sb = _supabase_client()

        # 1. Active pending total
        active_pending: int = (
            sb.table("events")
            .select("id", count="exact")
            .eq("annotation_status", "pending")
            .eq("is_active", True)
            .execute()
            .count
        ) or 0

        # 2. Old active pending (>7 days)
        cutoff = (datetime.now(tz=UTC) - timedelta(days=7)).isoformat()
        old_pending: int = (
            sb.table("events")
            .select("id", count="exact")
            .eq("annotation_status", "pending")
            .eq("is_active", True)
            .lt("created_at", cutoff)
            .execute()
            .count
        ) or 0

        # 3. Sub-event pending (should always be 0 — flags a root-cause bug)
        subevent_pending: int = (
            sb.table("events")
            .select("id", count="exact")
            .eq("annotation_status", "pending")
            .not_.is_("parent_event_id", "null")
            .execute()
            .count
        ) or 0

        # 4. Top-5 sources contributing to active pending
        rows = (
            sb.table("events")
            .select("source_name")
            .eq("annotation_status", "pending")
            .eq("is_active", True)
            .limit(2000)
            .execute()
            .data
        ) or []
        top_sources = [
            {"source": src, "count": n}
            for src, n in Counter(r["source_name"] for r in rows).most_common(5)
        ]

        # 5. Exclusion hits in last 24 hours (graceful: table may not exist yet)
        exclusion_hits_today: int = 0
        try:
            cutoff_1d = (datetime.now(tz=UTC) - timedelta(hours=24)).isoformat()
            exclusion_hits_today = (
                sb.table("source_exclusion_hits")
                .select("id", count="exact")
                .gte("matched_at", cutoff_1d)
                .execute()
                .count
            ) or 0
        except Exception as exc:
            logger.debug("source_exclusion_hits query skipped (table may not exist): %s", exc)

        # 6. Derive health status
        if active_pending > CRITICAL_ACTIVE or old_pending > CRITICAL_OLD:
            status = "critical"
        elif active_pending > WARN_ACTIVE or old_pending > WARN_OLD:
            status = "warn"
        else:
            status = "ok"

        result = {
            "status": status,
            "active_pending": active_pending,
            "old_pending_over_7d": old_pending,
            "subevent_pending": subevent_pending,
            "top_sources": top_sources,
            "exclusion_hits_today": exclusion_hits_today,
        }

        # Cleanup: remove hits older than 30 days
        try:
            cutoff_30d = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
            sb.table("source_exclusion_hits").delete().lt("matched_at", cutoff_30d).execute()
        except Exception as exc:
            logger.debug("source_exclusion_hits cleanup failed: %s", exc)

        print(json.dumps(result, ensure_ascii=False))

    except Exception as exc:
        logger.error("backlog_health failed: %s", exc)
        # Fail-safe: output unknown status so notify.py can still handle it
        print(json.dumps({"status": "unknown", "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
