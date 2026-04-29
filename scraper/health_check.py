"""
Daily health check for Tokyo Taiwan Radar.

Queries scraper_runs for the past 24 hours and sends a LINE alert ONLY
when issues are detected. Silent on success — no noise on healthy days.

Checks performed:
  1. Sources that failed (success=False) in the last 24 h
  2. Sources that ran 0 events (possible selector break or empty response)
  3. Active sources not present in scraper_runs at all (silent failure)

The list of expected sources is derived from scraper_runs history (sources
seen in the past 7 days) to avoid hardcoding the SCRAPERS list here.

Usage:
    python health_check.py            # run live, alert on issues
    python health_check.py --dry-run  # print report without sending LINE
    python health_check.py --always   # send LINE even when healthy (for testing)
"""

import argparse
import logging
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# Sources that are NOT expected to run every day (skip from "missing" alerts)
# e.g. sources that run weekly, or are temporarily suspended
NON_DAILY_SOURCES: frozenset[str] = frozenset()


def _supabase_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def run_check(dry_run: bool = False, always_notify: bool = False) -> None:
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)
    today_jst = now.astimezone(JST).strftime("%Y/%m/%d")

    sb = _supabase_client()

    # ── 1. Fetch runs from the past 24 hours ──────────────────────────────
    runs_24h = (
        sb.table("scraper_runs")
        .select("source, events_processed, success, ran_at")
        .gte("ran_at", since_24h.isoformat())
        .execute()
    ).data or []

    # ── 2. Determine expected active sources (seen in past 7 days) ────────
    runs_7d = (
        sb.table("scraper_runs")
        .select("source")
        .gte("ran_at", since_7d.isoformat())
        .execute()
    ).data or []
    expected_sources: set[str] = {r["source"] for r in runs_7d} - NON_DAILY_SOURCES

    # ── 3. Classify today's runs ──────────────────────────────────────────
    ran_today: set[str] = set()
    failed: list[str] = []
    zero_events: list[str] = []

    for r in runs_24h:
        src = r["source"]
        ran_today.add(src)
        if not r.get("success", True):
            failed.append(src)
        elif r.get("events_processed", 0) == 0:
            zero_events.append(src)

    # Sources expected to run but absent from today's runs
    missing: list[str] = sorted(expected_sources - ran_today)

    # ── 4. Build report ───────────────────────────────────────────────────
    issues: list[str] = []

    if failed:
        issues.append("🔴 爬蟲失敗（scraper error）：")
        for src in sorted(failed):
            issues.append(f"  • {src}")

    if zero_events:
        issues.append("🟡 執行成功但 0 件活動（selector 可能壞掉）：")
        for src in sorted(zero_events):
            issues.append(f"  • {src}")

    if missing:
        issues.append("⚠️ 預期執行但今日未出現於 scraper_runs：")
        for src in missing:
            issues.append(f"  • {src}")

    has_issues = bool(issues)
    ran_count = len(ran_today)
    ok_count = ran_count - len(set(failed)) - len(set(zero_events))

    if has_issues or always_notify:
        header = (
            f"{'🚨 ' if has_issues else '✅ '}"
            f"爬蟲健康チェック — {today_jst}\n"
            f"過去24h: {ran_count} ソース実行 / {ok_count} 正常\n"
        )
        body = "\n".join(issues) if issues else "✅ すべて正常です"
        message = header + "\n" + body
    else:
        logger.info(
            "Health check PASSED: %d sources ran, all healthy — no LINE alert sent.",
            ran_count,
        )
        return

    if dry_run:
        print("\n--- LINE message preview ---")
        print(message)
        print("--- end ---\n")
    else:
        from line_notify import send_line_message
        send_line_message(message)
        logger.info("Health check alert sent via LINE.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily scraper health check")
    parser.add_argument("--dry-run", action="store_true", help="Print report without sending LINE")
    parser.add_argument("--always", action="store_true", help="Send LINE even when all healthy")
    args = parser.parse_args()
    run_check(dry_run=args.dry_run, always_notify=args.always)
