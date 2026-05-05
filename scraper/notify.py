"""
Sends a LINE push message summarising the daily scraper run.

Reads from environment variables:
  SCRAPE_SUMMARY    — JSON string from summarize_run.py (may be empty "{}")
  VALIDATE_WARNINGS — JSON string from validate.py (may be empty "{}")

Usage:
    python notify.py
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta

from line_notify import send_line_message

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def _parse_env_json(var: str) -> dict:
    raw = os.environ.get(var, "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Could not parse %s as JSON", var)
        return {}


def build_message(summary: dict, validate: dict, annotate_outcome: str = "", backlog: dict | None = None, quality_alert: str = "") -> str:
    today = datetime.now(tz=JST).strftime("%Y-%m-%d")
    lines: list[str] = []

    if not summary or not summary.get("by_source"):
        lines.append("❌ 爬蟲執行失敗 — 請至 GitHub Actions 確認")
        lines.append(f"📅 {today} JST")
    else:
        lines.append("🕘 東京台灣雷達 — 今日爬蟲報告")
        lines.append(f"📅 {today} JST")
        lines.append("")
        total = summary.get("total", 0)
        lines.append(f"✅ 抓取完成：共 {total} 筆")
        by_source: dict[str, int] = summary.get("by_source", {})
        for src, n in sorted(by_source.items(), key=lambda x: -x[1]):
            lines.append(f"  • {src}: {n}")

    warnings: list[str] = validate.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append(f"⚠️ 警告 ({len(warnings)} 項)：")
        for w in warnings:
            lines.append(f"  • {w}")

    # Annotate failure alert — highest priority signal
    if annotate_outcome and annotate_outcome != "success":
        lines.append("")
        lines.append(f"🚨 Annotate 失敗（outcome={annotate_outcome}）")
        lines.append("  今日 pending backlog 未消化，請查 GitHub Actions log")

    # Backlog health alert
    if backlog and backlog.get("status") and backlog["status"] != "ok":
        status = backlog["status"]
        icon = "🔴" if status == "critical" else "🟡"
        lines.append("")
        lines.append(f"{icon} Backlog Health：{status.upper()}")
        lines.append(f"  active pending: {backlog.get('active_pending', '?')}")
        lines.append(f"  >7 天 pending: {backlog.get('old_pending_over_7d', '?')}")
        if backlog.get("subevent_pending", 0) > 0:
            lines.append(f"  ⚠️ sub-event pending: {backlog['subevent_pending']}")
        top = backlog.get("top_sources", [])[:3]
        if top:
            lines.append("  Top sources:")
            for t in top:
                lines.append(f"    • {t['source']}: {t['count']}")
        if backlog.get("exclusion_hits_today", 0) > 0:
            lines.append(f"  🚫 今日封鎖：{backlog['exclusion_hits_today']} 件")

    # Precision rate alert
    if quality_alert:
        lines.append("")
        lines.append(quality_alert)

    return "\n".join(lines)


def main() -> None:
    summary = _parse_env_json("SCRAPE_SUMMARY")
    validate = _parse_env_json("VALIDATE_WARNINGS")
    annotate_outcome = os.environ.get("ANNOTATE_OUTCOME", "").strip()
    backlog = _parse_env_json("BACKLOG_HEALTH")
    quality_alert = os.environ.get("QUALITY_ALERT", "").strip()

    msg = build_message(summary, validate, annotate_outcome, backlog, quality_alert)
    logger.info("Sending LINE notification (%d chars)", len(msg))

    success = send_line_message(msg)
    if not success:
        logger.warning("LINE notification not sent (token not configured or request failed)")


if __name__ == "__main__":
    main()
