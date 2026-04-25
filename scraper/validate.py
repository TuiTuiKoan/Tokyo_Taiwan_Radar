"""
Scraper run validator.

Queries the most recent scraper_runs entries and flags anomalies:
  - events_processed == 0  → WARNING
  - events_processed < 50% of 7-day average for that source → WARNING

Exit codes:
  0 = all OK
  2 = one or more WARNINGs (CI marks validate job as failed, but notify still runs)

Writes warnings JSON to /tmp/warnings.json for CI capture.

Usage:
    python validate.py
"""

import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _fetch_latest_per_source(sb) -> dict[str, int]:
    """Return {source: events_processed} for the most recent run of each source."""
    rows = (
        sb.table("scraper_runs")
        .select("source, events_processed, ran_at")
        .order("ran_at", desc=True)
        .limit(200)
        .execute()
        .data
    )

    seen: dict[str, int] = {}
    for row in rows:
        src = row["source"]
        if src not in seen:
            seen[src] = row["events_processed"]
    return seen


def _fetch_7day_avg(sb) -> dict[str, float]:
    """Return {source: avg(events_processed)} over the past 7 days."""
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat()
    rows = (
        sb.table("scraper_runs")
        .select("source, events_processed")
        .gte("ran_at", cutoff)
        .execute()
        .data
    )

    buckets: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        buckets[row["source"]].append(row["events_processed"])

    return {src: sum(vals) / len(vals) for src, vals in buckets.items()}


def main() -> None:
    sb = _supabase_client()

    latest = _fetch_latest_per_source(sb)
    avg7d = _fetch_7day_avg(sb)

    warnings: list[str] = []

    for source, n in sorted(latest.items()):
        if n == 0:
            warnings.append(f"{source}: 0 筆 (可能失效)")
            logger.warning("WARNING — %s: 0 events_processed", source)
        else:
            avg = avg7d.get(source, 0.0)
            if avg >= 2 and n < avg * 0.5:
                warnings.append(f"{source}: {n} 筆 (上週均值 {avg:.1f} 筆)")
                logger.warning(
                    "WARNING — %s: %d < 50%% of 7d avg %.1f", source, n, avg
                )

    output = {"warnings": warnings, "sources": dict(sorted(latest.items()))}

    try:
        with open("/tmp/warnings.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False)
        logger.info("Wrote /tmp/warnings.json (%d warning(s))", len(warnings))
    except OSError as e:
        logger.error("Could not write /tmp/warnings.json: %s", e)

    if warnings:
        sys.exit(2)


if __name__ == "__main__":
    main()
