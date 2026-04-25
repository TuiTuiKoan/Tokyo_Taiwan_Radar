"""
Outputs a one-line JSON summary of the most recent scraper run to stdout.
Used by scraper.yml to populate GITHUB_OUTPUT.

Output format (single line, no newlines):
  {"total": 42, "by_source": {"taiwan_cultural_center": 5, "peatix": 15, ...}, "run_at": "2026-04-25T09:00:00+09:00"}

Usage:
    python summarize_run.py
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def main() -> None:
    try:
        sb = _supabase_client()

        # Fetch the single most-recent row to find the reference timestamp
        latest_rows = (
            sb.table("scraper_runs")
            .select("ran_at")
            .order("ran_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if not latest_rows:
            print("{}")
            return

        latest_ts_str = latest_rows[0]["ran_at"]
        # Parse ISO timestamp; Supabase returns UTC strings like "2026-04-25T00:05:01+00:00"
        latest_ts = datetime.fromisoformat(latest_ts_str)
        window_start = latest_ts - timedelta(minutes=2)
        window_end = latest_ts + timedelta(minutes=2)

        rows = (
            sb.table("scraper_runs")
            .select("source, events_processed, ran_at")
            .gte("ran_at", window_start.isoformat())
            .lte("ran_at", window_end.isoformat())
            .execute()
            .data
        )

        by_source: dict[str, int] = {}
        for row in rows:
            src = row["source"]
            by_source[src] = by_source.get(src, 0) + row["events_processed"]

        total = sum(by_source.values())

        # Convert run_at to JST (UTC+9) for display
        jst = timezone(timedelta(hours=9))
        run_at_jst = latest_ts.astimezone(jst).isoformat(timespec="seconds")

        result = {
            "total": total,
            "by_source": dict(sorted(by_source.items(), key=lambda x: -x[1])),
            "run_at": run_at_jst,
        }
        print(json.dumps(result, ensure_ascii=False))

    except Exception as e:
        logger.error("summarize_run failed: %s", e)
        print("{}")


if __name__ == "__main__":
    main()
