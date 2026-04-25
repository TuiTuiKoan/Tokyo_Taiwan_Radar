"""
Weekly health report for Tokyo Taiwan Radar.
Queries scraper_runs and events tables for the past 7 days,
sends a LINE notification, and exits.

Usage:
    python weekly_report.py [--dry-run]
"""
import argparse
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def _supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _send_line(message: str) -> None:
    import urllib.request
    token = os.environ.get("LINE_CHANNEL_TOKEN", "")
    user_id = os.environ.get("LINE_USER_ID", "")
    if not token or not user_id:
        logger.warning("LINE credentials not set — skipping notification")
        return
    payload = json.dumps({"to": user_id, "messages": [{"type": "text", "text": message}]}).encode()
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        logger.info("LINE push status: %d", resp.status)


def generate_report(sb, since: datetime) -> dict:
    # scraper_runs for the past 7 days
    runs_res = (
        sb.table("scraper_runs")
        .select("source, events_processed, cost_usd, success, ran_at")
        .gte("ran_at", since.isoformat())
        .execute()
    )
    runs = runs_res.data or []

    # Group by source
    by_source: dict[str, dict] = {}
    for r in runs:
        src = r["source"]
        if src not in by_source:
            by_source[src] = {"count": 0, "success": 0, "events": 0, "cost": 0.0}
        by_source[src]["count"] += 1
        if r.get("success", True):
            by_source[src]["success"] += 1
        by_source[src]["events"] += r.get("events_processed", 0)
        by_source[src]["cost"] += float(r.get("cost_usd", 0))

    # Events added this week
    events_res = (
        sb.table("events")
        .select("id", count="exact")
        .eq("is_active", True)
        .gte("created_at", since.isoformat())
        .execute()
    )
    new_events = events_res.count or 0

    pending_res = (
        sb.table("events")
        .select("id", count="exact")
        .eq("is_active", True)
        .eq("annotation_status", "pending")
        .execute()
    )
    pending = pending_res.count or 0

    ran_sources = set(by_source.keys())

    total_cost = sum(v["cost"] for v in by_source.values())
    total_events = sum(v["events"] for v in by_source.values())

    return {
        "period_start": since.astimezone(JST).strftime("%Y-%m-%d"),
        "new_events": new_events,
        "pending_annotation": pending,
        "total_cost_usd": round(total_cost, 6),
        "total_runs": len(runs),
        "by_source": {
            src: {
                "runs": d["count"],
                "success_rate": round(d["success"] / d["count"], 2) if d["count"] else 0,
                "total_events": d["events"],
                "avg_events": round(d["events"] / d["count"], 1) if d["count"] else 0,
                "total_cost_usd": round(d["cost"], 6),
            }
            for src, d in sorted(by_source.items())
        },
    }


def format_line_message(report: dict) -> str:
    lines = [
        f"📊 Tokyo Taiwan Radar 週報",
        f"📅 {report['period_start']} ～",
        "",
        f"🆕 本週新增事件: {report['new_events']} 件",
        f"⏳ 待標注: {report['pending_annotation']} 件",
        f"💰 本週費用: ${report['total_cost_usd']:.6f}",
        f"🔄 執行次數: {report['total_runs']} 次",
        "",
        "📋 各來源狀態:",
    ]
    for src, d in report["by_source"].items():
        rate = d["success_rate"]
        icon = "✅" if rate == 1.0 else ("⚠" if rate >= 0.5 else "❌")
        lines.append(
            f"  {icon} {src}: {d['total_events']} 件 "
            f"({d['runs']} 次, 成功率 {int(rate*100)}%)"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sb = _supabase_client()
    since = datetime.now(JST) - timedelta(days=7)
    report = generate_report(sb, since)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    message = format_line_message(report)
    if args.dry_run:
        logger.info("[DRY RUN] LINE message:\n%s", message)
    else:
        _send_line(message)


if __name__ == "__main__":
    main()
