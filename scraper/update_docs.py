"""Auto-update /docs statistics blocks based on current DB + codebase state.

Replaces <!-- AUTO-UPDATE:START --> ... <!-- AUTO-UPDATE:END --> blocks in:
  - docs/ARCHITECTURE.md   → scraper count, active events, last run
  - docs/SCRAPER_PIPELINE.md → research_sources stats, auto_scraper stats

Usage:
    cd scraper && python update_docs.py           # update in-place
    cd scraper && python update_docs.py --dry-run # print only, no write
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

JST = timezone(timedelta(hours=9))
_REPO_ROOT = Path(__file__).parent.parent
_DOCS_DIR = _REPO_ROOT / "docs"
_MAIN_PY = Path(__file__).parent / "main.py"
_MIGRATIONS_DIR = _REPO_ROOT / "supabase" / "migrations"

AUTO_START = "<!-- AUTO-UPDATE:START -->"
AUTO_END = "<!-- AUTO-UPDATE:END -->"


# ---------------------------------------------------------------------------
# Codebase stats (no DB required)
# ---------------------------------------------------------------------------

def _count_scrapers() -> int:
    """Count registered scrapers in main.py SCRAPERS = [...] block."""
    text = _MAIN_PY.read_text(encoding="utf-8")
    m = re.search(r"SCRAPERS\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not m:
        return 0
    block = m.group(1)
    return sum(
        1 for line in block.splitlines()
        if "Scraper(" in line and not line.strip().startswith("#")
    )


def _migration_info() -> tuple[int, str]:
    """Return (count, latest_filename) for supabase/migrations/*.sql."""
    if not _MIGRATIONS_DIR.exists():
        return 0, "unknown"
    files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    return len(files), (files[-1].name if files else "unknown")


# ---------------------------------------------------------------------------
# DB stats
# ---------------------------------------------------------------------------

def _query_db_stats() -> dict:
    """Query Supabase for live system stats. Returns {} on any failure."""
    try:
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            print("[update_docs] SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — skipping DB stats", file=sys.stderr)
            return {}

        sb = create_client(url, key)
        now_jst = datetime.now(JST)
        today_str = now_jst.strftime("%Y-%m-%d")

        # Active events total
        active_res = (
            sb.table("events")
            .select("id", count="exact")
            .eq("is_active", True)
            .execute()
        )
        active_events = active_res.count or 0

        # Events scraped today (scraped_at >= today 00:00 JST)
        today_start_utc = now_jst.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        today_res = (
            sb.table("events")
            .select("id", count="exact")
            .eq("is_active", True)
            .gte("scraped_at", today_start_utc.isoformat())
            .execute()
        )
        events_today = today_res.count or 0

        # Latest scraper run (any source)
        run_res = (
            sb.table("scraper_runs")
            .select("ran_at,source")
            .order("ran_at", desc=True)
            .limit(1)
            .execute()
        )
        if run_res.data:
            ran_at = run_res.data[0].get("ran_at", "")
            src = run_res.data[0].get("source", "")
            if ran_at:
                dt = datetime.fromisoformat(ran_at.replace("Z", "+00:00")).astimezone(JST)
                last_run = f"{dt.strftime('%Y-%m-%d %H:%M')} JST ({src})"
            else:
                last_run = "—"
        else:
            last_run = "—"

        # research_sources counts by status
        src_res = sb.table("research_sources").select("status").execute()
        status_counts: dict[str, int] = {}
        for row in src_res.data or []:
            s = row.get("status") or "unknown"
            status_counts[s] = status_counts.get(s, 0) + 1

        # auto_scraper_status counts (all sources that have been attempted)
        auto_res = (
            sb.table("research_sources")
            .select("auto_scraper_status")
            .not_.is_("auto_scraper_status", "null")
            .execute()
        )
        auto_counts: dict[str, int] = {}
        for row in auto_res.data or []:
            s = row.get("auto_scraper_status") or "null"
            auto_counts[s] = auto_counts.get(s, 0) + 1

        return {
            "active_events": active_events,
            "events_today": events_today,
            "last_run": last_run,
            "status_counts": status_counts,
            "auto_counts": auto_counts,
        }

    except Exception as e:
        print(f"[update_docs] DB query failed: {e}", file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------

def _build_architecture_block(
    now_jst: datetime,
    scraper_count: int,
    migration_count: int,
    latest_migration: str,
    db: dict,
) -> str:
    active_events = db.get("active_events")
    events_today = db.get("events_today")
    last_run = db.get("last_run", "—")

    active_str = f"{active_events:,}" if isinstance(active_events, int) else "—"
    today_str = str(events_today) if isinstance(events_today, int) else "—"

    lines = [
        f"_最後更新：{now_jst.strftime('%Y-%m-%d %H:%M')} JST_",
        "",
        "### 爬蟲",
        f"登記中爬蟲：**{scraper_count} 個**（`scraper/main.py` SCRAPERS 清單）",
        "",
        "### 今日摘要",
        "",
        "| 指標 | 數值 |",
        "|------|------|",
        f"| 今日新增事件 | {today_str} |",
        f"| 活躍事件總計 | {active_str} |",
        f"| 最後爬取 | {last_run} |",
        "",
        "### 資料庫 Migrations",
        f"最新：`{latest_migration}`（共 {migration_count} 個）",
    ]
    return "\n".join(lines)


def _build_pipeline_block(now_jst: datetime, db: dict) -> str:
    status_counts = db.get("status_counts", {})
    auto_counts = db.get("auto_counts", {})

    STATUS_ORDER = ["candidate", "researched", "recommended", "not-viable", "implemented"]

    lines = [
        f"_最後更新：{now_jst.strftime('%Y-%m-%d %H:%M')} JST_",
        "",
        "### research_sources 管線統計",
        "",
        "| status | 數量 |",
        "|--------|------|",
    ]
    for s in STATUS_ORDER:
        lines.append(f"| `{s}` | {status_counts.get(s, 0)} |")
    for s, n in sorted(status_counts.items()):
        if s not in STATUS_ORDER:
            lines.append(f"| `{s}` | {n} |")

    if auto_counts:
        AUTO_ORDER = ["success", "sandbox-failed", "budget-exceeded", "llm-error", "spec-invalid", "null"]
        lines += [
            "",
            "### auto_scraper 代碼生成統計（已嘗試的來源）",
            "",
            "| auto_scraper_status | 數量 |",
            "|--------------------|------|",
        ]
        for s in AUTO_ORDER:
            if s in auto_counts:
                label = "未嘗試（NULL）" if s == "null" else s
                lines.append(f"| `{label}` | {auto_counts[s]} |")
        for s, n in sorted(auto_counts.items()):
            if s not in AUTO_ORDER:
                lines.append(f"| `{s}` | {n} |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Doc updater
# ---------------------------------------------------------------------------

def _replace_auto_block(content: str, new_block: str) -> str:
    pattern = re.compile(
        re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END),
        re.DOTALL,
    )
    replacement = f"{AUTO_START}\n{new_block}\n{AUTO_END}"
    return pattern.sub(replacement, content)


def run(dry_run: bool = False) -> int:
    now_jst = datetime.now(JST)
    scraper_count = _count_scrapers()
    migration_count, latest_migration = _migration_info()
    db = _query_db_stats()

    arch_block = _build_architecture_block(
        now_jst, scraper_count, migration_count, latest_migration, db
    )
    pipeline_block = _build_pipeline_block(now_jst, db)

    targets = [
        (_DOCS_DIR / "ARCHITECTURE.md", arch_block),
        (_DOCS_DIR / "SCRAPER_PIPELINE.md", pipeline_block),
    ]

    any_changed = False
    for path, block in targets:
        if not path.exists():
            print(f"[update_docs] {path.name}: not found, skipping", file=sys.stderr)
            continue

        content = path.read_text(encoding="utf-8")
        if AUTO_START not in content:
            print(f"[update_docs] {path.name}: no AUTO-UPDATE markers — skipping", file=sys.stderr)
            continue

        new_content = _replace_auto_block(content, block)
        if new_content == content:
            print(f"[update_docs] {path.name}: no changes")
        else:
            if dry_run:
                print(f"[update_docs] DRY-RUN {path.name} — new block:")
                print(block)
            else:
                path.write_text(new_content, encoding="utf-8")
                print(f"[update_docs] {path.name}: updated ✓")
            any_changed = True

    if not any_changed and not dry_run:
        print("[update_docs] All docs up to date")

    return 0


if __name__ == "__main__":
    sys.exit(run(dry_run="--dry-run" in sys.argv))
