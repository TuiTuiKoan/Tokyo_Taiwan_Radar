"""
Weekly health report for Tokyo Taiwan Radar.
Queries scraper_runs and events tables for the past 7 days,
writes a markdown snapshot to docs/weekly_review/,
and optionally sends a LINE notification.

Usage:
    python weekly_report.py [--dry-run] [--no-line]
"""
import argparse
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

WEEKLY_OPENAI_USD_WARN = 5.0
WEEKLY_DEEPL_CHARS_WARN = 100_000
MONTHLY_BUDGET_USD = 20.0

AUTO_QA_TYPES = ("auto_qa_simplified_zh", "auto_qa_missing_address", "auto_qa_untranslated")
AUTO_QA_LABELS = {
    "auto_qa_simplified_zh": "簡繁混雜",
    "auto_qa_missing_address": "地址缺失",
    "auto_qa_untranslated": "翻譯缺失",
}
DEFAULT_SITE_URL = "https://tokyotaiwanradar.com"


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
    # Try with `success` column (Migration 014); fall back if column doesn't exist yet.
    try:
        runs_res = (
            sb.table("scraper_runs")
            .select("source, events_processed, cost_usd, success, ran_at, openai_tokens_in, openai_tokens_out, deepl_chars")
            .gte("ran_at", since.isoformat())
            .execute()
        )
    except Exception:
        runs_res = (
            sb.table("scraper_runs")
            .select("source, events_processed, cost_usd, ran_at, openai_tokens_in, openai_tokens_out, deepl_chars")
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

    # Budget guardrails: weekly OpenAI/DeepL totals + month-to-date cost
    weekly_openai_cost = round(sum(float(r.get("cost_usd", 0) or 0) for r in runs), 6)
    deepl_chars = sum(int(r.get("deepl_chars", 0) or 0) for r in runs)

    month_start = datetime.now(JST).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        month_runs_res = (
            sb.table("scraper_runs")
            .select("cost_usd")
            .gte("ran_at", month_start.isoformat())
            .execute()
        )
        month_cost = round(
            sum(float(r.get("cost_usd", 0) or 0) for r in (month_runs_res.data or [])), 6
        )
    except Exception:
        month_cost = 0.0
    ratio = month_cost / MONTHLY_BUDGET_USD if MONTHLY_BUDGET_USD > 0 else 0
    budget_status = "alert" if ratio > 1.0 else ("warn" if ratio > 0.8 else "ok")

    # Auto-QA anomalies opened in the past 7 days (still pending)
    auto_qa_counts: dict[str, int] = {t: 0 for t in AUTO_QA_TYPES}
    auto_qa_total = 0
    auto_qa_pending_total = 0
    try:
        qa_res = (
            sb.table("event_reports")
            .select("report_types, status, created_at")
            .gte("created_at", since.isoformat())
            .execute()
        )
        for row in qa_res.data or []:
            types = row.get("report_types") or []
            for t in types:
                if t in AUTO_QA_TYPES:
                    auto_qa_counts[t] = auto_qa_counts.get(t, 0) + 1
                    auto_qa_total += 1
                    if row.get("status") == "pending":
                        auto_qa_pending_total += 1
                    break  # only count each row once
    except Exception as exc:
        logger.warning("auto_qa report query failed: %s", exc)

    return {
        "period_start": since.astimezone(JST).strftime("%Y-%m-%d"),
        "new_events": new_events,
        "pending_annotation": pending,
        "total_cost_usd": round(total_cost, 6),
        "total_runs": len(runs),
        "weekly_openai_cost_usd": weekly_openai_cost,
        "weekly_deepl_chars": deepl_chars,
        "month_to_date_cost_usd": month_cost,
        "monthly_budget_usd": MONTHLY_BUDGET_USD,
        "budget_status": budget_status,
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
        "auto_qa": {
            "total": auto_qa_total,
            "pending": auto_qa_pending_total,
            "by_type": auto_qa_counts,
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
    budget_emoji = {"alert": " 🚨", "warn": " ⚠", "ok": ""}[report["budget_status"]]
    pct = (
        int(report["month_to_date_cost_usd"] / report["monthly_budget_usd"] * 100)
        if report["monthly_budget_usd"]
        else 0
    )
    lines.append("")
    lines.append(
        f"💰 本月迄今: ${report['month_to_date_cost_usd']:.2f} / "
        f"${report['monthly_budget_usd']:.2f} ({pct}%){budget_emoji}"
    )
    lines.append(f"📈 OpenAI 本週: ${report['weekly_openai_cost_usd']:.4f}")
    deepl_warn = " ⚠" if report["weekly_deepl_chars"] > WEEKLY_DEEPL_CHARS_WARN else ""
    lines.append(f"🌐 DeepL 本週: {report['weekly_deepl_chars']:,} 字元{deepl_warn}")

    # Auto-QA anomalies — show only when there are findings
    qa = report.get("auto_qa") or {}
    if qa.get("total", 0) > 0:
        site_url = os.environ.get("NEXT_PUBLIC_SITE_URL") or DEFAULT_SITE_URL
        lines.append("")
        lines.append(f"🔍 自動 QA 偵測（本週 {qa['total']} 件，待處理 {qa.get('pending', 0)}）:")
        for t, n in (qa.get("by_type") or {}).items():
            if n > 0:
                label = AUTO_QA_LABELS.get(t, t)
                lines.append(f"  ⚠ {label}: {n} 件")
        lines.append(f"  → {site_url}/zh/admin/reports")
    return "\n".join(lines)


def _analyze_git_commits(repo_root: Path) -> dict:
    """Count commits and new files from the past 7 days via git log."""
    def _git(*args: str) -> str:
        r = subprocess.run(list(args), cwd=repo_root, capture_output=True, text=True, timeout=20)
        return r.stdout.strip()

    raw = _git("git", "log", "--since=7 days ago", "--pretty=format:%s", "--no-merges")
    msgs = [line for line in raw.split("\n") if line]

    by_type: dict[str, int] = {}
    for msg in msgs:
        m = re.match(r"^(\w+)[\(\:!]", msg)
        t = m.group(1) if m else "other"
        by_type[t] = by_type.get(t, 0) + 1

    raw_src = _git("git", "log", "--since=7 days ago", "--diff-filter=A",
                   "--name-only", "--pretty=format:", "--", "scraper/sources/")
    new_scrapers = sorted(set(
        p.split("/")[-1] for p in raw_src.split("\n")
        if p.endswith(".py") and "base.py" not in p and "__" not in p
    ))

    raw_mig = _git("git", "log", "--since=7 days ago", "--diff-filter=A",
                   "--name-only", "--pretty=format:", "--", "supabase/migrations/")
    new_migrations = sorted(set(
        p.split("/")[-1] for p in raw_mig.split("\n") if p.endswith(".sql")
    ))

    return {
        "total_commits": len(msgs),
        "by_type": by_type,
        "new_scrapers": new_scrapers,
        "new_migrations": new_migrations,
    }


def format_markdown_report(report: dict) -> str:
    """Format the report as a markdown document for docs/weekly_review/."""
    period = report["period_start"]
    lines = [
        f"# 週報 — {period}",
        "",
        f"| 指標 | 值 |",
        f"|---|---|",
        f"| 本週新增事件 | {report['new_events']} 件 |",
        f"| 待標注 | {report['pending_annotation']} 件 |",
        f"| 本週總費用 | ${report['total_cost_usd']:.4f} |",
        f"| OpenAI 本週 | ${report['weekly_openai_cost_usd']:.4f} |",
        f"| DeepL 本週 | {report['weekly_deepl_chars']:,} 字元 |",
        f"| 本月迄今 | ${report['month_to_date_cost_usd']:.2f} / ${report['monthly_budget_usd']:.2f} |",
        f"| 預算狀態 | {report['budget_status']} |",
        f"| 執行次數 | {report['total_runs']} 次 |",
        "",
    ]

    # Source status table
    healthy, watch, broken = [], [], []
    for src, d in report["by_source"].items():
        rate = d["success_rate"]
        ev = d["total_events"]
        row = f"| `{src}` | {d['runs']}x | {int(rate*100)}% | {ev} |"
        if rate == 1.0 and ev > 0:
            healthy.append(row)
        elif rate == 0 or ev == 0:
            broken.append(row)
        else:
            watch.append(row)

    hdr = "| 來源 | 執行 | 成功率 | 事件數 |\n|---|---|---|---|"

    if healthy:
        lines += ["## 🟢 健康", "", hdr] + healthy + [""]
    if watch:
        lines += ["## 🟡 待觀察", "", hdr] + watch + [""]
    if broken:
        lines += ["## 🔴 需修復", "", hdr] + broken + [""]

    # Auto-QA
    qa = report.get("auto_qa") or {}
    if qa.get("total", 0) > 0:
        lines += [
            "## 🔍 自動 QA",
            "",
            f"本週偵測 {qa['total']} 件，待處理 {qa.get('pending', 0)} 件",
            "",
        ]
        for t, n in (qa.get("by_type") or {}).items():
            if n > 0:
                label = AUTO_QA_LABELS.get(t, t)
                lines.append(f"- {label}: {n} 件")
        lines.append("")

    # Git commits section
    git = report.get("git") or {}
    if git.get("total_commits", 0) > 0:
        lines += ["## 📦 本週推送摘要", ""]
        lines.append(f"**Commits**：{git['total_commits']} 個")
        lines.append("")
        by_type = git.get("by_type") or {}
        if by_type:
            lines += ["| 類型 | 數量 |", "|---|---|"] + [
                f"| `{t}` | {n} |"
                for t, n in sorted(by_type.items(), key=lambda x: -x[1])
            ]
            lines.append("")
        new_scrapers = git.get("new_scrapers") or []
        if new_scrapers:
            lines.append(f"**新增爬蟲**（{len(new_scrapers)}）：" +
                         "、".join(f"`{s}`" for s in new_scrapers))
            lines.append("")
        new_migrations = git.get("new_migrations") or []
        if new_migrations:
            lines.append(f"**新 Migration**（{len(new_migrations)}）：" +
                         "、".join(f"`{m}`" for m in new_migrations))
            lines.append("")

    lines.append(f"*自動產生於 {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')}*")
    return "\n".join(lines)


def _write_report_file(report: dict) -> Path:
    """Write markdown report to docs/weekly_review/YYYY-MM-DD.md."""
    docs_dir = Path(__file__).parent.parent / "docs" / "weekly_review"
    docs_dir.mkdir(parents=True, exist_ok=True)
    filename = docs_dir / f"{report['period_start']}.md"
    filename.write_text(format_markdown_report(report), encoding="utf-8")
    logger.info("Weekly report written to %s", filename)
    return filename


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-line", action="store_true", help="Skip LINE notification")
    args = parser.parse_args()

    sb = _supabase_client()
    since = datetime.now(JST) - timedelta(days=7)
    report = generate_report(sb, since)

    # Enrich with git commit analysis
    repo_root = Path(__file__).parent.parent
    try:
        report["git"] = _analyze_git_commits(repo_root)
        logger.info("git analysis: %d commits", report["git"]["total_commits"])
    except Exception as exc:
        logger.warning("git analysis failed: %s", exc)
        report["git"] = {}

    print(json.dumps(report, ensure_ascii=False, indent=2))

    # Always write the markdown file (CI reads it for git commit)
    if not args.dry_run:
        _write_report_file(report)

    message = format_line_message(report)
    if args.dry_run:
        logger.info("[DRY RUN] LINE message:\n%s", message)
        logger.info("[DRY RUN] markdown:\n%s", format_markdown_report(report))
    elif not args.no_line:
        _send_line(message)


if __name__ == "__main__":
    main()
