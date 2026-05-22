"""
quota_monitor.py — Daily quota monitoring for Supabase DB, GH Actions, and Vercel.

Checks:
  1. Supabase DB total size (free tier limit: 500 MB)
  2. GitHub Actions minutes used in past 30 days (free tier limit: 2000 min/month)
  3. Vercel deployments in past 30 days (Hobby: 100/day, build 100h/month)

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
import re
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
VERCEL_HOBBY_BUILD_LIMIT_H = 100               # 100 hours / month
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
# Vercel deployments check
# ---------------------------------------------------------------------------

def check_vercel_deployments(token: str, project_id: str, team_id: str | None = None) -> dict:
    """Count deployments and total build time in the past 30 days via Vercel API."""
    if not token or not project_id:
        logger.warning("VERCEL_TOKEN or VERCEL_PROJECT_ID not set — skipping")
        return {"ok": False, "error": "VERCEL_TOKEN/PROJECT_ID not set"}

    since = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp() * 1000)
    headers = {"Authorization": f"Bearer {token}"}
    url = "https://api.vercel.com/v6/deployments"
    params: dict = {
        "projectId": project_id,
        "since": str(since),
        "limit": "100",
    }
    if team_id:
        params["teamId"] = team_id

    deploy_count = 0
    total_build_s = 0

    try:
        while True:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code != 200:
                logger.warning("Vercel API error %d: %s", resp.status_code, resp.text[:200])
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
            body = resp.json()
            deploys = body.get("deployments") or []
            if not deploys:
                break
            for d in deploys:
                deploy_count += 1
                building_at = d.get("buildingAt") or 0
                ready = d.get("ready") or 0
                if building_at and ready and ready > building_at:
                    total_build_s += (ready - building_at) / 1000
            # Pagination
            pagination = body.get("pagination") or {}
            next_ts = pagination.get("next")
            if not next_ts:
                break
            params["until"] = str(next_ts)

        build_hours = total_build_s / 3600
        build_pct = build_hours / VERCEL_HOBBY_BUILD_LIMIT_H * 100
        return {
            "ok": True,
            "deploy_count_30d": deploy_count,
            "build_hours_30d": round(build_hours, 2),
            "build_limit_h": VERCEL_HOBBY_BUILD_LIMIT_H,
            "build_pct": round(build_pct, 1),
            "avg_build_s": round(total_build_s / deploy_count) if deploy_count else 0,
        }
    except Exception as exc:
        logger.warning("check_vercel_deployments failed: %s", exc)
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


def build_line_message(db_check: dict, gh_check: dict, today: str,
                       vercel_check: dict | None = None) -> str:
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

    # Vercel
    if vercel_check is not None:
        if vercel_check.get("ok"):
            pct = vercel_check["build_pct"]
            lines.append(
                f"{_emoji(pct)} Vercel Build: "
                f"{vercel_check['build_hours_30d']:.1f}h / {vercel_check['build_limit_h']}h "
                f"({pct:.1f}%, {vercel_check['deploy_count_30d']} deploys, "
                f"avg {vercel_check['avg_build_s']}s)"
            )
        else:
            lines.append(f"❓ Vercel: 取得失敗 ({vercel_check.get('error', '')})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Budget guard (used by eval-annotator-stage2.yml)
# ---------------------------------------------------------------------------

def check_budget(budget_usd: float) -> int:
    """Pre-flight check: estimate 30d OpenAI annotator spend vs budget.

    Scans scraper_runs.notes for cost=$X.XXXX entries (source='annotator')
    in the past 30 days. If any cost data is logged AND the sum exceeds
    `budget_usd`, returns exit code 1 (skip eval). Otherwise returns 0.

    If no cost data is logged yet, returns 0 (graceful pass) — the Stage 2
    eval uses 14 frozen cases ≈ $0.001/run so this is mostly forward-compat.
    Plan v6 Phase 2.B: integrate with quota_monitor before Stage 2 cron.
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        logger.warning("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — skipping budget check")
        return 0

    sb = create_client(supabase_url, supabase_key)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        rows = (
            sb.table("scraper_runs")
            .select("notes")
            .eq("source", "annotator")
            .gte("ran_at", cutoff)
            .execute()
            .data or []
        )
    except Exception as exc:
        logger.warning("check_budget: scraper_runs fetch failed: %s — passing through", exc)
        return 0

    total = 0.0
    found_any = False
    pat = re.compile(r"cost=\$?([0-9]+\.[0-9]+)")
    for r in rows:
        notes = r.get("notes") or ""
        m = pat.search(notes)
        if m:
            found_any = True
            try:
                total += float(m.group(1))
            except ValueError:
                continue

    logger.info(
        "Budget check: 30d annotator spend ≈ $%.4f (budget $%.2f, cost_logs=%s)",
        total, budget_usd, "yes" if found_any else "none-yet",
    )
    if found_any and total > budget_usd:
        logger.error(
            "Budget exceeded: $%.4f > $%.2f — skipping Stage 2 eval",
            total, budget_usd,
        )
        # Best-effort LINE alert (no failure if creds missing).
        try:
            from line_notify import send_line_message
            send_line_message(
                f"⚠️ Stage 2 eval skipped: 30d annotator spend "
                f"${total:.4f} > budget ${budget_usd:.2f}"
            )
        except Exception:
            pass
        return 1
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(always: bool = False) -> None:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    github_token = os.environ.get("GITHUB_TOKEN")
    gh_repo = os.environ.get("GH_REPO", "TuiTuiKoan/Tokyo_Taiwan_Radar")
    vercel_token = os.environ.get("VERCEL_TOKEN")
    vercel_project_id = os.environ.get("VERCEL_PROJECT_ID")
    vercel_team_id = os.environ.get("VERCEL_TEAM_ID")
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

    logger.info("Checking Vercel deployments...")
    vercel_check = check_vercel_deployments(vercel_token, vercel_project_id, vercel_team_id)
    logger.info("Vercel: %s", vercel_check)

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

    if vercel_check.get("ok"):
        record_snapshot(sb, "vercel_build", "build_hours_30d",
                        vercel_check["build_hours_30d"],
                        VERCEL_HOBBY_BUILD_LIMIT_H,
                        {"deploy_count": vercel_check["deploy_count_30d"],
                         "avg_build_s": vercel_check["avg_build_s"]})
        record_snapshot(sb, "vercel_build", "pct_used",
                        vercel_check["build_pct"], 100.0)

    # --- Decide whether to notify ---
    db_pct  = db_check.get("pct", 0) if db_check.get("ok") else 0
    gh_pct  = gh_check.get("pct", 0) if gh_check.get("ok") else 0
    vc_pct  = vercel_check.get("build_pct", 0) if vercel_check.get("ok") else 0
    should_notify = always or db_pct >= WARN_PCT or gh_pct >= WARN_PCT or vc_pct >= WARN_PCT

    if not should_notify:
        logger.info("All quotas below %d%% — skipping LINE notification", WARN_PCT)
        return

    msg = build_line_message(db_check, gh_check, today, vercel_check)
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
    parser.add_argument("--check-budget", action="store_true",
                        help="Pre-flight budget guard. Exit 1 if estimated 30d "
                             "OpenAI annotator spend exceeds --budget-usd. "
                             "Used by eval-annotator-stage2.yml before running Stage 2.")
    parser.add_argument("--budget-usd", type=float, default=0.50,
                        help="USD budget cap for --check-budget (default 0.50).")
    args = parser.parse_args()

    if args.check_budget:
        sys.exit(check_budget(args.budget_usd))

    main(always=args.always)
