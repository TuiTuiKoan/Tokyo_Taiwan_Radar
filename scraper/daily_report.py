"""
Daily development report generator for Tokyo Taiwan Radar.

Queries Supabase for the past 25h of activity, combines with git log
passed via GIT_COMMITS env var, and writes plain-text report to
/tmp/report_body.txt.

Usage (called by GitHub Actions daily-dev-report.yml):
    GIT_COMMITS="..." python daily_report.py [--dry-run]

Local test:
    cd scraper && python daily_report.py --dry-run
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

JST = timezone(timedelta(hours=9))
SITE_URL = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://tokyo-taiwan-radar.vercel.app")
ACTIONS_URL = "https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/actions"


def _read_wip_items() -> list[tuple[str, list[str]]]:
    """Read .github/wip.md; return list of (title, detail_lines) for active (non-✅) items."""
    wip_path = Path(__file__).parent.parent / ".github" / "wip.md"
    if not wip_path.exists():
        return []

    items: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for raw in wip_path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("## "):
            if current_title is not None:
                items.append((current_title, current_lines))
            title = raw[3:].strip()
            # Skip completed items marked with ✅
            current_title = None if title.startswith("✅") else title
            current_lines = []
        elif current_title and raw.strip() and not raw.startswith("#"):
            # Skip horizontal rules
            if raw.strip() != "---":
                current_lines.append(raw.strip())

    if current_title is not None:
        items.append((current_title, current_lines))

    return items


def _supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def generate_report() -> str:
    now_jst = datetime.now(JST)
    report_date = now_jst.strftime("%Y-%m-%d")
    window_start = (now_jst - timedelta(hours=25)).isoformat()

    sb = _supabase_client()

    # ── git commits (passed from workflow via env) ──────────────────────────
    git_commits = os.environ.get("GIT_COMMITS", "").strip()

    # ── scraper runs ────────────────────────────────────────────────────────
    runs = (
        sb.table("scraper_runs")
        .select("source,events_processed,cost_usd,notes,ran_at")
        .gte("ran_at", window_start)
        .order("ran_at", desc=False)
        .execute()
        .data
        or []
    )

    total_events = sum(r.get("events_processed") or 0 for r in runs)
    total_cost = sum(r.get("cost_usd") or 0.0 for r in runs)

    # Per-source summary (exclude meta-sources)
    META_SOURCES = {"annotator", "merger", "backfill", "enrich"}
    source_summary: dict[str, int] = {}
    for r in runs:
        src = r.get("source", "unknown")
        n = r.get("events_processed") or 0
        source_summary[src] = source_summary.get(src, 0) + n

    scraper_sources = {k: v for k, v in source_summary.items() if k not in META_SOURCES}
    annotated_count = source_summary.get("annotator", 0)
    zero_sources = [src for src, n in scraper_sources.items() if n == 0]

    # ── annotation errors ────────────────────────────────────────────────────
    error_events = (
        sb.table("events")
        .select("id,raw_title,source_name")
        .eq("annotation_status", "error")
        .eq("is_active", True)
        .limit(5)
        .execute()
        .data
        or []
    )

    # ── pending event reports ────────────────────────────────────────────────
    pending_reports_res = (
        sb.table("event_reports")
        .select("id", count="exact")
        .eq("status", "pending")
        .execute()
    )
    pending_count = pending_reports_res.count or 0

    # ── auto scraper failures ────────────────────────────────────────────────
    auto_failed_res = (
        sb.table("research_sources")
        .select("id", count="exact")
        .eq("auto_scraper_status", "failed")
        .execute()
    )
    auto_failed_count = auto_failed_res.count or 0

    # ── build report text ────────────────────────────────────────────────────
    sep = "─" * 44
    lines: list[str] = []

    lines.append(f"📅 Tokyo Taiwan Radar 開發日報 {report_date} (JST)")
    lines.append("=" * 48)
    lines.append("")

    # Section 1: git commits
    lines.append(f"── 昨日提交 {sep[:32]}")
    if git_commits:
        for line in git_commits.splitlines()[:20]:
            lines.append(f"  {line}")
    else:
        lines.append("  （無提交）")
    lines.append("")

    # Section 2: scraper runs
    lines.append(f"── 爬蟲結果（過去 25 小時）{sep[:22]}")
    if runs:
        lines.append(f"  新增/更新事件  ：{total_events} 件")
        lines.append(f"  標注完成       ：{annotated_count} 件")
        lines.append(f"  OpenAI 費用    ：${total_cost:.4f}")
        if scraper_sources:
            lines.append("  來源明細：")
            for src, n in sorted(scraper_sources.items()):
                flag = " ⚠" if n == 0 else ""
                lines.append(f"    {src}: {n} 件{flag}")
        if zero_sources:
            lines.append(f"  ⚠ 以下來源 0 件（請確認）：{', '.join(zero_sources)}")
    else:
        lines.append("  （無爬蟲記錄 — 可能今日未執行）")
    lines.append("")

    # Section 3: pending items
    lines.append(f"── 待處理事項 {sep[:31]}")
    has_pending = False

    if error_events:
        has_pending = True
        lines.append(f"  ⚠ 標注錯誤事件：{len(error_events)} 件")
        for e in error_events:
            title = (e.get("raw_title") or "?")[:50]
            src = e.get("source_name", "?")
            lines.append(f"    - [{src}] {title}")
        lines.append(f"    → {SITE_URL}/zh/admin")

    if pending_count > 0:
        has_pending = True
        lines.append(f"  ⚠ 待審核問題回報：{pending_count} 件")
        lines.append(f"    → {SITE_URL}/zh/admin/reports")

    if auto_failed_count > 0:
        has_pending = True
        lines.append(f"  ⚠ auto_scraper 失敗來源：{auto_failed_count} 件")
        lines.append(f"    → {SITE_URL}/zh/admin/research")

    # WIP: in-progress development items
    wip_items = _read_wip_items()
    if wip_items:
        has_pending = True
        lines.append(f"  🚧 開發中項目：{len(wip_items)} 件")
        for title, details in wip_items:
            lines.append(f"    [{title}]")
            for d in details[:3]:  # max 3 detail lines per item
                lines.append(f"      {d}")

    if not has_pending:
        lines.append("  ✓ 無待處理事項")
    lines.append("")

    # Section 4: security note
    lines.append(f"── 安全日誌 {sep[:33]}")
    lines.append("  請至 GitHub Actions 確認昨日爬蟲 log：")
    lines.append(f"  {ACTIONS_URL}")
    lines.append("  可疑 pattern：rm | curl | wget | eval | exec | __import__")
    lines.append("")

    lines.append("=" * 48)
    lines.append(f"  生成時間：{now_jst.strftime('%Y-%m-%d %H:%M')} JST")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily dev report")
    parser.add_argument("--dry-run", action="store_true", help="Print report to stdout only")
    args = parser.parse_args()

    report = generate_report()
    print(report)

    if not args.dry_run:
        out_path = "/tmp/report_body.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n✓ Report written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
