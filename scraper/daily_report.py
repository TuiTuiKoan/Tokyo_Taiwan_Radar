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
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

JST = timezone(timedelta(hours=9))
SITE_URL = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://tokyotaiwanradar.com")
ACTIONS_URL = "https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/actions"
RUNS_DIR = Path(__file__).parent / "auto_scraper" / "runs"

COST_DAILY_WARN  = 0.50   # ⚠ show in report section
COST_DAILY_ALERT = 1.00   # 🔴 also send LINE push
COST_MONTH_ALERT = 15.00  # 🔴 also send LINE push
COST_SOURCE_SPIKE = 1.50  # 🚨 any single source today

PERSISTENT_ZERO_DAYS = 30  # 連續 N 天 0 件 → 在 report 中標記需調查

_TAIWAN_KW = [
    "台灣", "台湾", "Taiwan", "臺灣",
    "台北", "台中", "台南", "高雄", "花蓮",
]


def _load_run_artifacts(source_id: int) -> dict:
    """Load meta.json, spec.json, and sample events from dry_run.txt for a given source_id.
    Returns a dict with keys: meta, spec, sample_titles. Empty dict on any error.
    """
    run_dir = RUNS_DIR / str(source_id)
    if not run_dir.is_dir():
        return {}
    try:
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    try:
        spec = json.loads((run_dir / "spec.json").read_text(encoding="utf-8"))
    except Exception:
        spec = {}
    # Extract first 3 event titles from SAMPLE_EVENTS in dry_run.txt
    sample_titles: list[str] = []
    try:
        dry = (run_dir / "dry_run.txt").read_text(encoding="utf-8")
        m = re.search(r"^SAMPLE_EVENTS=(.+)$", dry, re.MULTILINE)
        if m:
            events = json.loads(m.group(1))
            for ev in events[:3]:
                title = (
                    ev.get("name_ja")
                    or ev.get("name_zh")
                    or ev.get("name_en")
                    or ev.get("raw_title")
                    or ""
                )
                if title:
                    sample_titles.append(title)
    except Exception:
        pass
    return {"meta": meta, "spec": spec, "sample_titles": sample_titles}


_WIP_DATE_RE = re.compile(r"最後更新[:：]\s*(\d{4}-\d{2}-\d{2})")


def _read_wip_items(
    cutoff_date: "datetime | None" = None,
) -> tuple[list[tuple[str, list[str]]], list[tuple[str, list[str]]]]:
    """Read .github/wip.md.

    Returns (active_items, recently_completed_items).
    Each item is (title, detail_lines).
    recently_completed = ✅ items whose 最後更新 date >= cutoff_date (default: yesterday JST).
    """
    wip_path = Path(__file__).parent.parent / ".github" / "wip.md"
    if not wip_path.exists():
        return [], []

    if cutoff_date is None:
        cutoff_date = datetime.now(JST) - timedelta(hours=26)

    active: list[tuple[str, list[str]]] = []
    completed: list[tuple[str, list[str]]] = []

    current_title: str | None = None
    current_completed: bool = False
    current_lines: list[str] = []

    def _flush() -> None:
        if current_title is None:
            return
        if current_completed:
            # Include only if updated within the reporting window
            for line in current_lines:
                m = _WIP_DATE_RE.search(line)
                if m:
                    try:
                        item_date = datetime.strptime(m.group(1), "%Y-%m-%d").replace(
                            tzinfo=JST
                        )
                        if item_date >= cutoff_date:
                            completed.append((current_title, current_lines))
                    except ValueError:
                        pass
                    break
        else:
            active.append((current_title, current_lines))

    for raw in wip_path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("## "):
            _flush()
            title = raw[3:].strip()
            if title.startswith("✅"):
                current_title = title[1:].strip()  # strip ✅ prefix for display
                current_completed = True
            else:
                current_title = title
                current_completed = False
            current_lines = []
        elif current_title and raw.strip() and not raw.startswith("#"):
            if raw.strip() != "---":
                current_lines.append(raw.strip())

    _flush()
    return active, completed


def _supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def check_cost_anomalies(sb, today_runs: list, window_start_30d: str) -> dict:
    """
    Analyse cost anomalies from today's scraper_runs rows and the past 30 days.

    Args:
        sb: Supabase client
        today_runs: rows from scraper_runs for the past 25h (already fetched)
        window_start_30d: ISO timestamp for 30 days ago

    Returns dict with:
        today_cost       float
        month_cost       float
        today_warn       bool  (> COST_DAILY_WARN)
        today_alert      bool  (> COST_DAILY_ALERT)
        month_alert      bool  (> COST_MONTH_ALERT)
        spike_sources    list[tuple[str, float]]  sources exceeding COST_SOURCE_SPIKE
        top3_today       list[tuple[str, float]]
        any_alert        bool  (today_alert or month_alert or spike_sources)
    """
    today_cost = sum(r.get("cost_usd") or 0.0 for r in today_runs)

    try:
        month_rows = (
            sb.table("scraper_runs")
            .select("cost_usd")
            .gte("ran_at", window_start_30d)
            .execute()
            .data
            or []
        )
        month_cost = sum(r.get("cost_usd") or 0.0 for r in month_rows)
    except Exception:
        month_cost = 0.0

    by_source: dict[str, float] = {}
    for r in today_runs:
        src = r.get("source") or "unknown"
        by_source[src] = by_source.get(src, 0.0) + (r.get("cost_usd") or 0.0)

    spike_sources = [(s, c) for s, c in by_source.items() if c > COST_SOURCE_SPIKE]
    top3 = sorted(by_source.items(), key=lambda x: -x[1])[:3]

    today_warn  = today_cost > COST_DAILY_WARN
    today_alert = today_cost > COST_DAILY_ALERT
    month_alert = month_cost > COST_MONTH_ALERT
    any_alert   = today_alert or month_alert or bool(spike_sources)

    return {
        "today_cost":    today_cost,
        "month_cost":    month_cost,
        "today_warn":    today_warn,
        "today_alert":   today_alert,
        "month_alert":   month_alert,
        "spike_sources": spike_sources,
        "top3_today":    top3,
        "any_alert":     any_alert,
    }


def check_persistent_zero_sources(sb, window_start_30d: str) -> list[tuple[str, int, str]]:
    """
    Find scraper sources that have been running for PERSISTENT_ZERO_DAYS+ days
    without ever producing a single event.

    Returns list of (source_name, run_count, first_run_date) sorted by first_run.
    Excludes researcher/* and meta-sources.
    """
    META_PREFIXES = ("researcher/", "annotator", "merger", "backfill", "enrich")
    try:
        rows = (
            sb.table("scraper_runs")
            .select("source,events_processed,ran_at")
            .gte("ran_at", window_start_30d)
            .execute()
            .data
            or []
        )
    except Exception:
        return []

    by_source: dict[str, dict] = {}
    for r in rows:
        src = r.get("source") or "unknown"
        if any(src.startswith(p) for p in META_PREFIXES):
            continue
        if src not in by_source:
            by_source[src] = {"count": 0, "events": 0, "first": r["ran_at"][:10]}
        by_source[src]["count"] += 1
        by_source[src]["events"] += r.get("events_processed") or 0
        if r["ran_at"][:10] < by_source[src]["first"]:
            by_source[src]["first"] = r["ran_at"][:10]

    result = []
    for src, d in by_source.items():
        if d["events"] == 0 and d["count"] >= PERSISTENT_ZERO_DAYS:
            result.append((src, d["count"], d["first"]))
    return sorted(result, key=lambda x: x[2])


def generate_report() -> tuple[str, dict]:
    now_jst = datetime.now(JST)
    report_date = now_jst.strftime("%Y-%m-%d")
    window_start = (now_jst - timedelta(hours=25)).isoformat()
    window_start_30d = (now_jst - timedelta(days=30)).isoformat()

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
    cost_check = check_cost_anomalies(sb, runs, window_start_30d)
    persistent_zeros = check_persistent_zero_sources(sb, window_start_30d)

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

    # ── pending auto-generated PRs ──────────────────────────────────────────────
    pending_prs = (
        sb.table("research_sources")
        .select("id,name,scraping_feasibility,auto_scraper_pr_url")
        .not_.is_("auto_scraper_pr_url", "null")
        .neq("status", "implemented")
        .order("id")
        .execute()
        .data
        or []
    )

    # ── auto-generate success but no PR yet (needs human review) ────────────────
    review_queue = (
        sb.table("research_sources")
        .select("id,name,scraping_feasibility")
        .eq("auto_scraper_status", "success")
        .is_("auto_scraper_pr_url", "null")
        .order("id")
        .execute()
        .data
        or []
    )

    # ── auto-registered stub rows (name == scraper_source_name, need proper name/url) ──
    stub_rows = (
        sb.table("research_sources")
        .select("id,name,scraper_source_name,url")
        .eq("status", "implemented")
        .execute()
        .data
        or []
    )
    stub_rows = [
        r for r in stub_rows
        if r.get("scraper_source_name") and r.get("name") == r.get("scraper_source_name")
    ]

    # ── build report text ─────────────────────────────────────────────────────
    sep = "─" * 44
    lines: list[str] = []

    lines.append(f"📅 Tokyo Taiwan Radar 開發日報 {report_date} (JST)")
    lines.append("=" * 48)
    lines.append("")

    # Section 1: pending items
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

    # WIP: in-progress and recently completed items
    wip_active, wip_done = _read_wip_items()
    if wip_active:
        has_pending = True
        lines.append(f"  🚧 開發中項目：{len(wip_active)} 件")
        for title, details in wip_active:
            lines.append(f"    [{title}]")
            for d in details[:3]:  # max 3 detail lines per item
                lines.append(f"      {d}")

    if wip_done:
        has_pending = True
        lines.append(f"  ✅ 昨日完成：{len(wip_done)} 件")
        for title, details in wip_done:
            lines.append(f"    [{title}]")
            for d in details[:2]:
                lines.append(f"      {d}")

    if stub_rows:
        has_pending = True
        lines.append(f"  📝 自動補建的來源待補充 name/url：{len(stub_rows)} 件")
        for r in stub_rows:
            lines.append(f"    - id={r['id']}  scraper_source_name={r['scraper_source_name']}  url={r.get('url') or '（空）'}")
        lines.append("    → 在 scraper/ 目錄執行：python update_source.py --id <id> --name '來源名稱' --url 'https://...'")
        lines.append("      或：python - <<'PY'")
        lines.append("      # 範例：填入 id=XX 的 name 和 url")
        lines.append("      import os; from dotenv import load_dotenv; from supabase import create_client")
        lines.append("      load_dotenv('.env'); sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])")
        lines.append("      sb.table('research_sources').update({'name': '正式名稱', 'url': 'https://...'}).eq('id', XX).execute()")
        lines.append("      PY")

    if not has_pending:
        lines.append("  ✓ 無待處理事項")
    lines.append("")

    # Section 2: auto-generate 完成待人工建立 PR
    lines.append(f"── 🔎 待人工建立 PR（auto-generate 成功）{sep[:8]}")
    if review_queue:
        for item in review_queue:
            src_id = item["id"]
            name = item.get("name", "?")
            feas = item.get("scraping_feasibility") or "?"
            arts = _load_run_artifacts(src_id)
            meta = arts.get("meta", {})
            spec = arts.get("spec", {})
            titles = arts.get("sample_titles", [])

            events_found = meta.get("events_found", "?")
            cost = meta.get("cost_usd", 0.0)

            # source_id stability: pattern contains \d+ or [a-z0-9]+ → stable
            id_pattern = spec.get("source_id_url_pattern", "")
            id_stable = "✓" if re.search(r"\\d\+|[a-z]\+", id_pattern) else "⚠"

            # Taiwan keyword check on sample titles
            tw_hits = sum(1 for t in titles if any(kw in t for kw in _TAIWAN_KW))
            tw_flag = "✓" if tw_hits > 0 else f"⚠ 0/{len(titles)} 筆含台灣關鍵字"

            lines.append(f"  [{name}] (id={src_id}, {feas})")
            lines.append(f"    events_found  : {events_found}   cost: ${cost:.3f}")
            lines.append(f"    source_id 穩定: {id_stable}  ({id_pattern})")
            lines.append(f"    台灣關聯       : {tw_flag}")
            if titles:
                lines.append("    sample events :")
                for t in titles:
                    tw_mark = "+" if any(kw in t for kw in _TAIWAN_KW) else " "
                    lines.append(f"      [{tw_mark}] {t[:60]}")
            lines.append(f"    → runs/{src_id}/generated.py  確認後手動建立 PR")
            lines.append("")
        lines.append("  手動建立 PR:")
        lines.append("    cp scraper/auto_scraper/runs/<id>/generated.py scraper/sources/<name>.py")
        lines.append("    # 加入 main.py SCRAPERS → git commit → gh pr create")
    else:
        lines.append("  （無待建立項目）")
    lines.append("")

    # Section 3: PR review（已有 PR URL，等待 merge）
    lines.append(f"── 待 merge PR（auto-generated scrapers）{sep[:9]}")
    if pending_prs:
        for i, pr in enumerate(pending_prs, 1):
            feas = pr.get("scraping_feasibility") or "?"
            pr_url = pr.get("auto_scraper_pr_url", "")
            pr_num = pr_url.split("/")[-1] if pr_url else "?"
            lines.append(f"  {i}. [{pr.get('name', '?')}] ({feas}) → PR #{pr_num}")
            lines.append(f"     {pr_url}")
        lines.append("  → https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/pulls")
        lines.append("  ※ approve → merge 後次回 cron 自動上線")
    else:
        lines.append("  （無待 merge PR）")
    lines.append("")

    # Section 3: git commits
    lines.append(f"── 昨日提交 {sep[:32]}")
    if git_commits:
        for line in git_commits.splitlines()[:20]:
            lines.append(f"  {line}")
    else:
        lines.append("  （無提交）")
    lines.append("")

    # Section 4: security note
    lines.append(f"── 安全日誌 {sep[:33]}")
    lines.append("  請至 GitHub Actions 確認昨日爬蟲 log：")
    lines.append(f"  {ACTIONS_URL}")
    lines.append("  可疑 pattern：rm | curl | wget | eval | exec | __import__")
    lines.append("")

    # Section 5: scraper runs
    lines.append(f"── 爬蟲結果（過去 25 小時）{sep[:22]}")
    if runs:
        lines.append(f"  新增/更新事件  ：{total_events} 件")
        lines.append(f"  標注完成       ：{annotated_count} 件")
        _cost_flag = ""
        if cost_check["today_alert"]:
            _cost_flag = f"  ← 🔴 ALERT（>{COST_DAILY_ALERT}）"
        elif cost_check["today_warn"]:
            _cost_flag = f"  ← ⚠ warn（>{COST_DAILY_WARN}）"
        lines.append(f"  OpenAI 費用    ：${total_cost:.4f}{_cost_flag}")
        _month_flag = ""
        if cost_check["month_alert"]:
            _month_flag = f"  ← 🔴 ALERT（>{COST_MONTH_ALERT}）"
        lines.append(f"  30 天累計費用  ：${cost_check['month_cost']:.2f}{_month_flag}")
        if cost_check["spike_sources"]:
            for src, c in cost_check["spike_sources"]:
                lines.append(f"  🚨 單一來源 spike：{src}  ${c:.4f}（>{COST_SOURCE_SPIKE}）")
        if scraper_sources:
            lines.append("  來源明細：")
            for src, n in sorted(scraper_sources.items()):
                flag = " ⚠" if n == 0 else ""
                lines.append(f"    {src}: {n} 件{flag}")
        if zero_sources:
            lines.append(f"  ⚠ 以下來源 0 件（請確認）：{', '.join(zero_sources)}")
        if persistent_zeros:
            lines.append("")
            lines.append(f"  🔴 持續 {PERSISTENT_ZERO_DAYS} 天無事件（需調查）：")
            for src, cnt, first in persistent_zeros:
                lines.append(f"    {src}: {cnt} 次執行, 首次 {first}, 迄今 0 件")
    else:
        lines.append("  （無爬蟲記錄 — 可能今日未執行）")
    lines.append("")

    lines.append("=" * 48)
    lines.append(f"  生成時間：{now_jst.strftime('%Y-%m-%d %H:%M')} JST")

    return "\n".join(lines), cost_check


def send_cost_alert_if_needed(cost_check: dict, report_date: str) -> None:
    """Send a LINE push if any cost threshold is exceeded. No-op if LINE creds not set."""
    if not cost_check.get("any_alert"):
        return

    try:
        from line_notify import send_line_message
    except ImportError:
        return

    lines = [f"💰 OpenAI 成本告警（{report_date}）", ""]

    today_icon = "🔴" if cost_check["today_alert"] else "⚠️"
    lines.append(
        f"{today_icon} 今日：${cost_check['today_cost']:.4f}"
        f"  (warn=${COST_DAILY_WARN}, alert=${COST_DAILY_ALERT})"
    )

    month_icon = "🔴" if cost_check["month_alert"] else "✅"
    lines.append(
        f"{month_icon} 30 天：${cost_check['month_cost']:.2f}"
        f"  (alert=${COST_MONTH_ALERT})"
    )

    if cost_check["spike_sources"]:
        lines.append("")
        lines.append(f"🚨 Source spike（單源 >${COST_SOURCE_SPIKE}）：")
        for src, c in cost_check["spike_sources"]:
            lines.append(f"  {src}: ${c:.4f}")

    if cost_check["top3_today"]:
        lines.append("")
        lines.append("Top 3 sources today:")
        for src, c in cost_check["top3_today"]:
            if c > 0:
                lines.append(f"  {src}: ${c:.4f}")

    send_line_message("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily dev report")
    parser.add_argument("--dry-run", action="store_true", help="Print report to stdout only")
    args = parser.parse_args()

    report, cost_check = generate_report()
    print(report)

    if not args.dry_run:
        out_path = "/tmp/report_body.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n✓ Report written to {out_path}", file=sys.stderr)
        # Send LINE cost alert if any threshold exceeded
        now_jst = datetime.now(JST)
        send_cost_alert_if_needed(cost_check, now_jst.strftime("%Y-%m-%d"))


if __name__ == "__main__":
    main()
