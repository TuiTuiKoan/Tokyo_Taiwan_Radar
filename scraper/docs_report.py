"""
docs_report.py — Deterministic weekly / monthly docs report generator.

This is an *orchestration wrapper*, not a third metric engine. It reuses:
  - report_window.resolve_report_window — single source of window truth.
  - daily_report.check_cost_anomalies + cost constants — cost math/thresholds.
  - monthly_health_check.collect_monthly_health_metrics — read-only A1-A4 +
    governance + researcher health (no LINE, no DB cleanup).

Every Supabase query bound, git-inventory bound, markdown metadata field, and
output path is derived from one resolved ReportWindow. No volatile field
(generated_at, commit SHA, execution-date MTD) is written into the committed
markdown, so primary + fallback / rerun executions produce byte-identical files
when the underlying data is unchanged.

Usage:
    python docs_report.py --mode weekly                 # scheduled: prev complete week
    python docs_report.py --mode weekly --date 2026-06-14
    python docs_report.py --mode monthly                # scheduled: prev complete month
    python docs_report.py --mode monthly --month 2026-06

Test-only flags: --now-jst, --output-root, --git-log-file, --dry-run.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

try:  # supabase is optional at import time so offline tests still run
    from supabase import create_client
except Exception:  # pragma: no cover
    create_client = None  # type: ignore[assignment]

import daily_report
from monthly_health_check import collect_monthly_health_metrics
from report_window import JST, ReportWindow, resolve_report_window

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Design Principle 6: report-only paths + bot/report commit scopes ─────────
EXCLUDED_PATH_PREFIXES = (
    "docs/weekly_review/",
    "docs/monthly_review/",
    "docs/evaluation/",
    "docs/skill_scan/",
)
EXCLUDED_SUBJECT_MARKERS = (
    "docs(weekly_review)",
    "docs(monthly_review)",
    "chore(evaluation): monthly annotator baseline",
    "chore(governance): monthly SKILL.md scan report",
)

_COMMIT_MARKER = "__COMMIT__"
_CONVENTIONAL_RE = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?!?:")
_KNOWN_TYPES = ("feat", "fix", "docs", "chore", "refactor", "style", "perf", "test", "ci", "build", "security")
_NEW_SCRAPER_RE = re.compile(r"^scraper/sources/(?!__init__\.py$|base\.py$)[^/]+\.py$")
_NEW_MIGRATION_RE = re.compile(r"^supabase/migrations/.+\.sql$")


# ─── Supabase ─────────────────────────────────────────────────────────────────

def _supabase_client():
    """Return a Supabase client, or None when env/deps are unavailable (offline)."""
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key or create_client is None:
        return None
    try:
        return create_client(url, key)
    except Exception as exc:  # pragma: no cover
        print(f"[docs_report] Supabase client unavailable: {exc}", file=sys.stderr)
        return None


# ─── Git inventory (fixed absolute bounds, path-aware filtering) ──────────────

@dataclass
class GitCommit:
    hash: str
    date: str
    subject: str
    paths: list[tuple[str, str]] = field(default_factory=list)  # (status, path)


def _git_log_raw(window: ReportWindow) -> str:
    """Run `git log` with fixed --since/--until from the window. '' on failure."""
    since = window.window_start.isoformat()
    until = (window.window_end_exclusive - timedelta(seconds=1)).isoformat()
    cmd = [
        "git", "-C", str(REPO_ROOT), "log", "--no-merges",
        f"--since={since}", f"--until={until}",
        f"--pretty=format:{_COMMIT_MARKER}%x09%H%x09%cI%x09%s",
        "--name-status",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return out.stdout
    except Exception as exc:  # pragma: no cover
        print(f"[docs_report] git log failed: {exc}", file=sys.stderr)
        return ""


def _parse_git_log(raw: str) -> list[GitCommit]:
    """Parse `__COMMIT__\\t<hash>\\t<date>\\t<subject>` + name-status blocks."""
    commits: list[GitCommit] = []
    current: GitCommit | None = None
    for line in raw.splitlines():
        if line.startswith(_COMMIT_MARKER):
            parts = line.split("\t", 3)
            current = GitCommit(
                hash=parts[1] if len(parts) > 1 else "",
                date=parts[2] if len(parts) > 2 else "",
                subject=parts[3] if len(parts) > 3 else "",
            )
            commits.append(current)
            continue
        if not line.strip() or current is None:
            continue
        cols = line.split("\t")
        status = cols[0].strip()
        path = cols[-1].strip()  # rename rows (R100 old new) → take destination path
        if path:
            current.paths.append((status, path))
    return commits


def _is_report_only(commit: GitCommit) -> bool:
    """True if the commit is an automatic report / report-only-path commit."""
    if any(marker in commit.subject for marker in EXCLUDED_SUBJECT_MARKERS):
        return True
    if commit.paths and all(
        any(path.startswith(pref) for pref in EXCLUDED_PATH_PREFIXES)
        for _status, path in commit.paths
    ):
        return True
    return False


def _commit_type(subject: str) -> str:
    m = _CONVENTIONAL_RE.match(subject)
    if m and m.group("type") in _KNOWN_TYPES:
        return m.group("type")
    return "other"


def collect_git_inventory(window: ReportWindow, git_log_file: str | None = None) -> dict:
    """Full-history, fixed-window git inventory with Principle-6 filtering."""
    if git_log_file:
        raw = Path(git_log_file).read_text(encoding="utf-8")
    else:
        raw = _git_log_raw(window)

    commits = _parse_git_log(raw)
    feature_commits = [c for c in commits if not _is_report_only(c)]

    by_type: dict[str, int] = {}
    new_scrapers: list[str] = []
    new_migrations: list[str] = []
    highlights: list[str] = []

    for c in feature_commits:
        by_type[_commit_type(c.subject)] = by_type.get(_commit_type(c.subject), 0) + 1
        for status, path in c.paths:
            if status.startswith("A") and _NEW_SCRAPER_RE.match(path):
                new_scrapers.append(path)
            elif status.startswith("A") and _NEW_MIGRATION_RE.match(path):
                new_migrations.append(path)
        if c.subject.startswith("feat") and len(highlights) < 8:
            short = c.hash[:7] if c.hash else "-------"
            highlights.append(f"{c.subject} ({short})")

    return {
        "commit_count": len(feature_commits),
        "by_type": dict(sorted(by_type.items())),
        "new_scrapers": sorted(set(new_scrapers)),
        "new_migrations": sorted(set(new_migrations)),
        "highlights": highlights,
    }


# ─── Weekly data collection (window-bounded, deterministic) ──────────────────

def collect_weekly_data(sb, window: ReportWindow) -> dict:
    data: dict = {"db_available": sb is not None}
    if sb is None:
        return data

    start_iso = window.window_start.isoformat()
    end_iso = window.window_end_exclusive.isoformat()

    runs = (
        sb.table("scraper_runs")
        .select("source,events_processed,cost_usd,success,deepl_chars,ran_at")
        .gte("ran_at", start_iso)
        .lt("ran_at", end_iso)
        .order("ran_at", desc=False)
        .execute()
        .data or []
    )

    by_source: dict[str, dict] = {}
    for r in runs:
        s = r.get("source") or "unknown"
        d = by_source.setdefault(s, {"count": 0, "success": 0, "events": 0, "cost": 0.0})
        d["count"] += 1
        if r.get("success", True):
            d["success"] += 1
        d["events"] += r.get("events_processed") or 0
        d["cost"] += float(r.get("cost_usd") or 0.0)

    deepl_chars = sum(int(r.get("deepl_chars") or 0) for r in runs)

    # Month-to-report-end window: JST month start containing (end - 1s) → end.
    mtre_start = (window.window_end_exclusive - timedelta(seconds=1)).astimezone(JST).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    # Reuse daily_report cost math for the window-bounded figures only:
    # today_cost / top3_today / spike_sources are all derived from ``runs``
    # (already bounded to the weekly window).
    cost_check = daily_report.check_cost_anomalies(sb, runs, mtre_start.isoformat())

    # Principle 9: month-to-report-end cost MUST be bounded by the report window
    # end, never "now". check_cost_anomalies' month_cost has no upper bound, so
    # compute MTRE explicitly to keep committed markdown deterministic per key.
    mtre_runs = (
        sb.table("scraper_runs").select("cost_usd")
        .gte("ran_at", mtre_start.isoformat()).lt("ran_at", end_iso)
        .execute().data or []
    )
    mtre_cost = sum(float(r.get("cost_usd") or 0.0) for r in mtre_runs)

    new_events = (
        sb.table("events").select("id", count="exact", head=True)
        .eq("is_active", True).is_("parent_event_id", "null")
        .gte("created_at", start_iso).lt("created_at", end_iso)
        .execute().count or 0
    )
    total_active = (
        sb.table("events").select("id", count="exact", head=True)
        .eq("is_active", True).execute().count or 0
    )
    pending = (
        sb.table("events").select("id", count="exact", head=True)
        .eq("is_active", True).eq("annotation_status", "pending").execute().count or 0
    )

    qa_rows = (
        sb.table("event_reports").select("report_types").eq("status", "pending").execute().data or []
    )
    qa_total = len(qa_rows)
    qa_auto: dict[str, int] = {}
    for r in qa_rows:
        for t in (r.get("report_types") or []):
            if t.startswith("auto_"):
                qa_auto[t] = qa_auto.get(t, 0) + 1

    data.update({
        "by_source": by_source,
        "deepl_chars": deepl_chars,
        "weekly_cost": cost_check["today_cost"],
        "mtre_cost": mtre_cost,
        "mtre_start": mtre_start.strftime("%Y-%m-%d"),
        "month_warn": mtre_cost > daily_report.COST_MONTH_WARN,
        "month_alert": mtre_cost > daily_report.COST_MONTH_ALERT,
        "top3_sources": cost_check["top3_today"],
        "spike_sources": cost_check["spike_sources"],
        "new_events": new_events,
        "total_active": total_active,
        "pending": pending,
        "qa_total": qa_total,
        "qa_auto": dict(sorted(qa_auto.items())),
    })
    return data


# ─── Monthly data collection (window-bounded, deterministic) ─────────────────

def collect_monthly_data(sb, window: ReportWindow) -> dict:
    data: dict = {"db_available": sb is not None}
    if sb is None:
        return data

    start_iso = window.window_start.isoformat()
    end_iso = window.window_end_exclusive.isoformat()

    data["metrics"] = collect_monthly_health_metrics(
        sb, window_start=window.window_start, window_end_exclusive=window.window_end_exclusive
    )

    new_events = (
        sb.table("events").select("id", count="exact", head=True)
        .eq("is_active", True).is_("parent_event_id", "null")
        .gte("created_at", start_iso).lt("created_at", end_iso)
        .execute().count or 0
    )
    month_runs = (
        sb.table("scraper_runs").select("cost_usd")
        .gte("ran_at", start_iso).lt("ran_at", end_iso).execute().data or []
    )
    data["new_events"] = new_events
    data["month_cost"] = sum(float(r.get("cost_usd") or 0.0) for r in month_runs)
    return data


# ─── Markdown rendering (deterministic; stable metadata only) ─────────────────

def _frontmatter(window: ReportWindow) -> str:
    return "\n".join([
        "---",
        f"report_key: {window.report_key}",
        f"report_type: {window.report_type}",
        f"window_start: {window.window_start.isoformat()}",
        f"window_end: {window.window_end_exclusive.isoformat()}",
        "---",
        "",
    ])


def _git_section(git: dict) -> list[str]:
    by_type = git["by_type"]
    type_str = " / ".join(f"{t} {n}" for t, n in by_type.items()) if by_type else "0"
    lines = [
        "## 📦 推送摘要（已過濾自動報告 commit）",
        "",
        f"- **Commits**：{git['commit_count']} 個（{type_str}）",
    ]
    if git["new_scrapers"]:
        names = ", ".join(Path(p).stem for p in git["new_scrapers"])
        lines.append(f"- **新增爬蟲**：{len(git['new_scrapers'])} 個（{names}）")
    else:
        lines.append("- **新增爬蟲**：0 個")
    if git["new_migrations"]:
        names = ", ".join(Path(p).name for p in git["new_migrations"])
        lines.append(f"- **新增 Migration**：{len(git['new_migrations'])} 個（{names}）")
    else:
        lines.append("- **新增 Migration**：0 個")
    if git["highlights"]:
        lines += ["", "**功能亮點**：", ""]
        for i, h in enumerate(git["highlights"], 1):
            lines.append(f"{i}. {h}")
    return lines


def build_weekly_markdown(window: ReportWindow, data: dict) -> str:
    git = data["git"]
    lines = [f"# 週報 — {window.display_window_start} ~ {window.display_window_end}", ""]

    if not data.get("db_available"):
        lines += [
            "> ⚠️ _本次執行無法連線 Supabase，DB 指標已略過；以下僅含 git 推送盤點。_",
            "",
        ]
    else:
        mtre_flag = ""
        if data["month_alert"]:
            mtre_flag = f"  🔴（> ${daily_report.COST_MONTH_ALERT}）"
        elif data["month_warn"]:
            mtre_flag = f"  ⚠️（> ${daily_report.COST_MONTH_WARN}）"
        lines += [
            "## 📊 數據摘要",
            "",
            "| 指標 | 值 |",
            "|---|---|",
            f"| 本週新增事件 | {data['new_events']} 件 |",
            f"| Active 事件總數 | {data['total_active']} 件 |",
            f"| 待標注 (pending) | {data['pending']} 件 |",
            f"| 本週費用 (OpenAI) | ${data['weekly_cost']:.4f} |",
            f"| DeepL 本週 | {data['deepl_chars']:,} 字元 |",
            f"| 月累計至本週（{data['mtre_start']}~） | ${data['mtre_cost']:.2f}{mtre_flag} |",
            f"| Auto-QA pending | {data['qa_total']} 件 |",
            "",
        ]

        by_source = data["by_source"]
        if by_source:
            lines += ["## 🛰️ 來源狀態（本週窗口）", "", "| 來源 | 執行 | 成功率 | 事件 | 費用 |", "|---|---|---|---|---|"]
            for src, d in sorted(by_source.items()):
                rate = d["success"] / d["count"] if d["count"] else 0.0
                flag = "🟢" if rate == 1.0 and d["events"] > 0 else ("🔴" if rate == 0 or d["events"] == 0 else "🟡")
                lines.append(f"| {flag} {src} | {d['count']}x | {rate:.0%} | {d['events']} | ${d['cost']:.4f} |")
            zeros = sorted(s for s, d in by_source.items() if d["events"] == 0)
            if zeros:
                lines += ["", f"⚠️ 本週 0 件來源（{len(zeros)}）：{', '.join(zeros)}"]
            lines.append("")

        if data["top3_sources"]:
            lines += ["## 💰 費用 Top 來源（本週窗口）", ""]
            for src, c in data["top3_sources"]:
                if c > 0:
                    lines.append(f"- {src}: ${c:.4f}")
            if data["spike_sources"]:
                lines.append("")
                for src, c in data["spike_sources"]:
                    lines.append(f"- 🚨 spike：{src} ${c:.4f}（> ${daily_report.COST_SOURCE_SPIKE}）")
            lines.append("")

        if data["qa_auto"]:
            lines += ["## 🔍 Auto-QA pending 明細", ""]
            for t, n in data["qa_auto"].items():
                lines.append(f"- {t}: {n}")
            lines.append("")

    lines += _git_section(git)
    lines.append("")
    return _frontmatter(window) + "\n".join(lines).rstrip() + "\n"


def build_monthly_markdown(window: ReportWindow, data: dict) -> str:
    git = data["git"]
    lines = [
        f"# 月報 — {window.report_key}（{window.display_window_start} ~ {window.display_window_end}）",
        "",
    ]

    if not data.get("db_available"):
        lines += [
            "> ⚠️ _本次執行無法連線 Supabase，治理指標已略過；以下僅含 git 推送盤點。_",
            "",
        ]
    else:
        m = data["metrics"]
        reports = m["reports"]
        corr = m["corrections"]
        lines += [
            "## 🛡️ 治理健檢（本月窗口）",
            "",
            "| 指標 | 值 |",
            "|---|---|",
            f"| 本月新增事件 | {data['new_events']} 件 |",
            f"| 本月費用 (OpenAI) | ${data['month_cost']:.2f} |",
            f"| 報錯確認數 | {reports.get('total', 0)} 件 |",
            f"| ├ irrelevant | {reports.get('irrelevant', 0)} |",
            f"| ├ wrongCategory | {reports.get('wrongCategory', 0)} |",
            f"| ├ wrongDetails | {reports.get('wrongDetails', 0)} |",
            f"| └ wrongSelectionReason | {reports.get('wrongSelectionReason', 0)} |",
            f"| field_corrections | {corr.get('field_corrections', '?')} |",
            f"| category_corrections | {corr.get('category_corrections', '?')} |",
            f"| selection_reason_corrections | {corr.get('selection_reason_corrections', '?')} |",
            f"| AI 保護命中 (field_protect_hits) | {m['protect_hits'] if m['protect_hits'] >= 0 else '取得失敗'} |",
            f"| 封鎖規則命中 (exclusion_hits) | {m['exclusion_hits']} |",
            "",
        ]
        flags = m.get("integrity_flags") or []
        if flags:
            lines += ["### ⚠️ 閉環警訊", ""]
            for fl in flags:
                lines.append(f"- {fl}")
            lines.append("")
        else:
            lines += ["✅ 閉環完整：無斷鏈警訊", ""]

        a1 = m["a1_recurrence"]
        lines += [
            "## 📈 閉環效能指標（A1–A4，本月窗口）",
            "",
            f"**A1 重犯率**：{a1.get('recurrence_pairs', 'n/a')} 對 (source×field 修正 ≥2 次)",
            "",
        ]
        if a1.get("top_pairs"):
            lines += ["| source_name | field_name | count |", "|---|---|---|"]
            for p in a1["top_pairs"]:
                lines.append(f"| {p['source_name']} | {p['field_name']} | {p['count']} |")
            lines.append("")

        a2 = m["a2_protect_trend"]
        rate_str = f"{a2['rate']:.2%}" if a2.get("rate") is not None else "n/a"
        lines += [
            f"**A2 保護命中率**：{a2.get('hits', '?')} hits / {a2.get('annotated', '?')} annotated（{rate_str}）",
            "",
            "**A3 首次正確率**（24h 內被報錯比例，per source）：",
            "",
        ]
        a3_sources = m["a3_first_pass"].get("sources", [])
        if a3_sources:
            lines += ["| source_name | 新事件數 | 24h 內報錯 | 錯誤率 |", "|---|---|---|---|"]
            for s in a3_sources:
                lines.append(f"| {s['source_name']} | {s['total_new']} | {s['reported_within_24h']} | {s['error_rate']:.1%} |")
        else:
            lines.append("_No data_")
        lines += ["", "**A4 修復延遲**（field_correction − event 建立，中位數天，per source）：", ""]
        a4_sources = m["a4_repair_latency"].get("sources", [])
        if a4_sources:
            lines += ["| source_name | 修正次數 | 中位數（天） |", "|---|---|---|"]
            for s in a4_sources:
                lines.append(f"| {s['source_name']} | {s['n_corrections']} | {s['median_days']} |")
        else:
            lines.append("_No data_")
        lines.append("")

        r = m["researcher_health"]
        r_rate = f"{r['approval_rate']:.1%}" if r.get("approval_rate") is not None else "n/a"
        lines += [
            "## 🔬 Researcher 健康度（本月窗口）",
            "",
            f"- implemented {r.get('implemented', 0)} / not-viable {r.get('not_viable', 0)} / "
            f"candidate {r.get('candidate', 0)} / researched {r.get('researched', 0)}",
            f"- 通過率：{r_rate}（implemented / (implemented + not-viable)）",
            "",
        ]

    lines += _git_section(git)
    lines.append("")
    return _frontmatter(window) + "\n".join(lines).rstrip() + "\n"


# ─── Write (idempotent, deterministic) ───────────────────────────────────────

def write_report(window: ReportWindow, content: str, output_root: Path, dry_run: bool) -> tuple[Path, bool]:
    """Write the report. Returns (target_path, changed). Never creates a 2nd file."""
    target = output_root / window.output_relative_path
    if dry_run:
        return target, False
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.exists() else None
    if existing == content:
        return target, False
    target.write_text(content, encoding="utf-8")
    return target, True


def _emit_summary(window: ReportWindow, target: Path, changed: bool, exec_mtd: str | None) -> None:
    lines = [
        f"## 📝 docs_report ({window.report_type})",
        "",
        f"- report_key: `{window.report_key}`",
        f"- window: `{window.window_start.isoformat()}` ≤ t < `{window.window_end_exclusive.isoformat()}`",
        f"- output: `{target}`",
        f"- changed: {'yes' if changed else 'no (idempotent no-op)'}",
    ]
    if exec_mtd:
        lines.append(f"- execution-date MTD (stdout only, not committed): {exec_mtd}")
    block = "\n".join(lines)
    print(block)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as fh:
                fh.write(block + "\n")
        except Exception:  # pragma: no cover
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic weekly/monthly docs report generator")
    ap.add_argument("--mode", required=True, choices=["weekly", "monthly"])
    ap.add_argument("--date", help="Weekly week-ending Sunday key YYYY-MM-DD")
    ap.add_argument("--month", help="Monthly key YYYY-MM (overrides previous-complete-month default)")
    ap.add_argument("--output-root", help="Override docs output root (default: <repo>/docs)")
    ap.add_argument("--dry-run", action="store_true", help="Render + print preview without writing")
    ap.add_argument("--now-jst", help="Test-only reference time ISO8601 for scheduled defaults")
    ap.add_argument("--git-log-file", help="Test-only mocked git --name-status log fixture")
    args = ap.parse_args()

    window = resolve_report_window(args.mode, date=args.date, month=args.month, now_jst=args.now_jst)
    sb = _supabase_client()
    git_inv = collect_git_inventory(window, args.git_log_file)

    if args.mode == "weekly":
        data = collect_weekly_data(sb, window)
        data["git"] = git_inv
        content = build_weekly_markdown(window, data)
    else:
        data = collect_monthly_data(sb, window)
        data["git"] = git_inv
        content = build_monthly_markdown(window, data)

    output_root = Path(args.output_root) if args.output_root else REPO_ROOT / "docs"
    target, changed = write_report(window, content, output_root, args.dry_run)

    # Execution-date MTD is operational only — never written to committed markdown.
    exec_mtd = None
    if sb is not None and args.mode == "weekly" and not args.dry_run:
        try:
            from datetime import datetime
            now = datetime.now(tz=JST)
            mtd_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            mtd_runs = (
                sb.table("scraper_runs").select("cost_usd")
                .gte("ran_at", mtd_start.isoformat()).lt("ran_at", now.isoformat())
                .execute().data or []
            )
            exec_mtd = f"${sum(float(r.get('cost_usd') or 0.0) for r in mtd_runs):.2f} (as of {now.strftime('%Y-%m-%d')})"
        except Exception:
            exec_mtd = None

    if args.dry_run:
        print(f"[dry-run] target: {target}")
        print(f"[dry-run] window: {window.window_start.isoformat()} <= t < {window.window_end_exclusive.isoformat()}")
        print("=" * 60)
        print(content)
    else:
        _emit_summary(window, target, changed, exec_mtd)

    return 0


if __name__ == "__main__":
    sys.exit(main())
