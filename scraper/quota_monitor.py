"""
quota_monitor.py — Daily quota monitoring for Supabase DB size and GH Actions minutes.

Checks:
  1. Supabase DB total size (free tier limit: 500 MB)
  2. GitHub Actions minutes used in past 30 days (free tier limit: 2000 min/month)

Writes snapshots to quota_snapshots table.
Sends LINE alert when any resource exceeds WARN_PCT (80%).

Usage:
  python quota_monitor.py           # Alert only when >80%
  python quota_monitor.py --always  # Always send LINE report
"""

import argparse
import logging
import math
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
SUPABASE_FREE_LIMIT_BYTES = 500 * 1024 * 1024  # 500 MB
GH_ACTIONS_FREE_LIMIT_MIN = 2000               # 2000 min / month
WARN_PCT = 80
ALERT_PCT = 90


# ---------------------------------------------------------------------------
# Supabase DB check
# ---------------------------------------------------------------------------

def check_supabase_db(sb) -> dict:
    """Return DB size info by calling the db_size_summary RPC."""
    try:
        result = sb.rpc("db_size_summary").execute()
        data = result.data
        total_bytes = data.get("total_bytes", 0)
        tables = data.get("tables") or []
        pct = total_bytes / SUPABASE_FREE_LIMIT_BYTES * 100
        return {
            "ok": True,
            "total_bytes": total_bytes,
            "total_mb": total_bytes / (1024 * 1024),
            "limit_bytes": SUPABASE_FREE_LIMIT_BYTES,
            "limit_mb": SUPABASE_FREE_LIMIT_BYTES / (1024 * 1024),
            "pct": pct,
            "tables": tables,
        }
    except Exception as exc:
        logger.warning("check_supabase_db failed: %s", exc)
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# GitHub Actions minutes check
# ---------------------------------------------------------------------------

def check_gh_actions_minutes(repo: str, token: str) -> dict:
    """Sum run_duration_ms for all runs in the past 30 days, return minutes used."""
    if not token:
        logger.warning("GITHUB_TOKEN not set — skipping GH Actions check")
        return {"ok": False, "error": "GITHUB_TOKEN not set"}

    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{repo}/actions/runs"
    params = {"created": f">={since}", "per_page": 100, "page": 1}

    total_ms = 0
    run_count = 0

    try:
        while True:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code != 200:
                logger.warning("GH API error %d: %s", resp.status_code, resp.text[:200])
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
            body = resp.json()
            runs = body.get("workflow_runs", [])
            if not runs:
                break
            for run in runs:
                total_ms += run.get("run_duration_ms") or 0
            run_count += len(runs)
            # Check if there's a next page
            link = resp.headers.get("Link", "")
            if 'rel="next"' not in link:
                break
            params["page"] += 1

        total_min = math.ceil(total_ms / 60_000)
        pct = total_min / GH_ACTIONS_FREE_LIMIT_MIN * 100
        return {
            "ok": True,
            "minutes_30d": total_min,
            "limit_min": GH_ACTIONS_FREE_LIMIT_MIN,
            "pct": pct,
            "run_count": run_count,
        }
    except Exception as exc:
        logger.warning("check_gh_actions_minutes failed: %s", exc)
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Snapshot recording
# ---------------------------------------------------------------------------

def record_snapshot(sb, resource: str, metric: str, value: float,
                    limit_value: float | None = None, details: dict | None = None) -> None:
    try:
        sb.table("quota_snapshots").insert({
            "resource": resource,
            "metric": metric,
            "value": value,
            "limit_value": limit_value,
            "details": details,
        }).execute()
    except Exception as exc:
        logger.warning("record_snapshot failed (%s/%s): %s", resource, metric, exc)


# ---------------------------------------------------------------------------
# LINE message
# ---------------------------------------------------------------------------

def _emoji(pct: float) -> str:
    if pct >= ALERT_PCT:
        return "🔴"
    if pct >= WARN_PCT:
        return "⚠️"
    return "✅"


def build_line_message(db_check: dict, gh_check: dict, today: str) -> str:
    lines = [f"📊 配額監控（{today}）", ""]

    # Supabase DB
    if db_check.get("ok"):
        pct = db_check["pct"]
        lines.append(
            f"{_emoji(pct)} Supabase DB: "
            f"{db_check['total_mb']:.0f} MB / {db_check['limit_mb']:.0f} MB "
            f"({pct:.1f}%)"
        )
        tables = db_check.get("tables") or []
        if tables:
            lines.append("  Top 5 tables:")
            for t in tables[:5]:
                mb = t["bytes"] / (1024 * 1024)
                lines.append(f"    {t['table']}: {mb:.1f} MB")
    else:
        lines.append(f"❓ Supabase DB: 取得失敗 ({db_check.get('error', '')})")

    # GH Actions
    if gh_check.get("ok"):
        pct = gh_check["pct"]
        lines.append(
            f"{_emoji(pct)} GH Actions: "
            f"{gh_check['minutes_30d']} min / {gh_check['limit_min']} min "
            f"({pct:.1f}%, 30 天累計, {gh_check['run_count']} runs)"
        )
    else:
        lines.append(f"❓ GH Actions: 取得失敗 ({gh_check.get('error', '')})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(always: bool = False) -> None:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    github_token = os.environ.get("GITHUB_TOKEN")
    gh_repo = os.environ.get("GH_REPO", "TuiTuiKoan/Tokyo_Taiwan_Radar")
    line_token = os.environ.get("LINE_CHANNEL_TOKEN")
    line_user = os.environ.get("LINE_USER_ID")

    if not supabase_url or not supabase_key:
        logger.error("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
        sys.exit(1)

    sb = create_client(supabase_url, supabase_key)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # --- Run checks ---
    logger.info("Checking Supabase DB size...")
    db_check = check_supabase_db(sb)
    logger.info("DB: %s", db_check)

    logger.info("Checking GH Actions minutes...")
    gh_check = check_gh_actions_minutes(gh_repo, github_token)
    logger.info("GH: %s", gh_check)

    # --- Record snapshots ---
    if db_check.get("ok"):
        record_snapshot(sb, "supabase_db", "total_bytes",
                        db_check["total_bytes"], SUPABASE_FREE_LIMIT_BYTES,
                        {"tables": db_check.get("tables", [])[:10]})
        record_snapshot(sb, "supabase_db", "pct_used",
                        db_check["pct"], 100.0)

    if gh_check.get("ok"):
        record_snapshot(sb, "gh_actions_minutes", "minutes_30d",
                        gh_check["minutes_30d"], GH_ACTIONS_FREE_LIMIT_MIN,
                        {"run_count": gh_check["run_count"]})
        record_snapshot(sb, "gh_actions_minutes", "pct_used",
                        gh_check["pct"], 100.0)

    # --- Decide whether to notify ---
    db_pct  = db_check.get("pct", 0) if db_check.get("ok") else 0
    gh_pct  = gh_check.get("pct", 0) if gh_check.get("ok") else 0
    should_notify = always or db_pct >= WARN_PCT or gh_pct >= WARN_PCT

    if not should_notify:
        logger.info("All quotas below %d%% — skipping LINE notification", WARN_PCT)
        return

    msg = build_line_message(db_check, gh_check, today)
    print(msg)

    if not line_token or not line_user:
        logger.warning("LINE credentials not set — printed to stdout only")
        return

    from line_notify import send_line_message
    ok = send_line_message(msg)
    if ok:
        logger.info("LINE notification sent")
    else:
        logger.error("LINE notification failed")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--always", action="store_true",
                        help="Send LINE report even when below threshold")
    args = parser.parse_args()
    main(always=args.always)
