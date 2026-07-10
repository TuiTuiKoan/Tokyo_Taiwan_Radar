"""
qa_triage.py — Daily QA triage for auto-fix vs human review.

Reads:
  - scraper_runs (last 24h + 7d)
  - event_reports with pending status

Outputs:
  - Classification buckets: auto-fixable / needs-human / info-only
  - Escalates 3-day consecutive zero-event sources to needs-human
  - LINE message (unless --dry-run)

Usage:
    python qa_triage.py
    python qa_triage.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from line_notify import send_line_message

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
SAFE_AUTO_FIX_TYPES = frozenset({"auto_qa_simplified_zh", "auto_simplified_chinese"})
NON_DAILY_SOURCES = frozenset({
    "weekly_broadcast",
    # Weekly-only scrapers (run on Monday UTC only)
    "oaff", "tokyo_filmex", "tiff", "tiff_jp",
    "ifi", "waseda_icl", "tuat_global",
    "tokyo_now", "fukuoka_now", "hankyu_umeda",
    "hankyu_hakata", "hankyu_kobe", "hanshin_umeda",
    "nagano_aioiza", "maruhiro", "whitestone_gallery",
    # Cinemas that rarely/never screen Taiwan films (0 events in 180d)
    "human_trust_cinema", "cineswitch_ginza", "cine_gallery",
    # Low-frequency venues / feeds (0 events in 180d; selectors confirmed OK)
    "morc_asagaya", "tokyo_city_i", "jposa_ja",
})
DATE_IN_TAB_URL_RE = re.compile(r"/(\d{4}-\d{2}-\d{2})$")


def _supabase_client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _fetch_runs(sb, since_24h: datetime, since_7d: datetime) -> tuple[list[dict], list[dict]]:
    runs_24h = (
        sb.table("scraper_runs")
        .select("source,events_processed,success,ran_at")
        .gte("ran_at", since_24h.isoformat())
        .execute()
    ).data or []
    runs_7d = (
        sb.table("scraper_runs")
        .select("source,events_processed,success,ran_at")
        .gte("ran_at", since_7d.isoformat())
        .execute()
    ).data or []
    return runs_24h, runs_7d


def _three_day_zero_streak_sources(runs_7d: list[dict], now_utc: datetime) -> set[str]:
    # Aggregate per source/day (JST): successful event counts for each day.
    per_source_day_events: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_source_day_success_runs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in runs_7d:
        ran_at = _parse_dt(row.get("ran_at"))
        if not ran_at:
            continue
        day_key = ran_at.astimezone(JST).date().isoformat()
        src = row.get("source") or "unknown"
        if row.get("success", True):
            per_source_day_success_runs[src][day_key] += 1
            per_source_day_events[src][day_key] += int(row.get("events_processed", 0) or 0)

    target_days = [
        (now_utc.astimezone(JST).date() - timedelta(days=i)).isoformat()
        for i in range(3)
    ]

    out: set[str] = set()
    for src, day_events in per_source_day_events.items():
        all_three_days_have_success_run = all(
            per_source_day_success_runs[src].get(day, 0) > 0 for day in target_days
        )
        all_three_days_zero_events = all(day_events.get(day, 0) == 0 for day in target_days)
        if all_three_days_have_success_run and all_three_days_zero_events:
            out.add(src)
    return out


def _fetch_pending_reports(sb) -> list[dict]:
    return (
        sb.table("event_reports")
        .select("id,event_id,report_types,admin_notes,created_at,status")
        .eq("status", "pending")
        .order("created_at", desc=True)
        .execute()
    ).data or []


def _fetch_tokyoartbeat_mismatch(sb) -> list[dict]:
    rows = (
        sb.table("events")
        .select("id,name_ja,start_date,source_url")
        .eq("source_name", "tokyoartbeat")
        .eq("is_active", True)
        .not_.is_("start_date", None)
        .execute()
    ).data or []

    mismatch: list[dict] = []
    for row in rows:
        m = DATE_IN_TAB_URL_RE.search(row.get("source_url") or "")
        if not m:
            continue
        url_date = m.group(1)
        db_date = (row.get("start_date") or "")[:10]
        if db_date and db_date != url_date:
            mismatch.append({
                "event_id": row["id"],
                "name_ja": row.get("name_ja") or "",
                "db_date": db_date,
                "url_date": url_date,
            })
    return mismatch


def _build_message(today_jst: str, triage: dict) -> str:
    lines: list[str] = []
    lines.append(f"🩺 QA 分診報告（{today_jst}）")
    lines.append("")

    auto_items: list[str] = triage["auto_fixable"]
    human_items: list[str] = triage["needs_human"]
    info_items: list[str] = triage["info_only"]

    lines.append(f"🤖 可自動修復: {len(auto_items)}")
    if auto_items:
        lines.extend(auto_items[:12])
        if len(auto_items) > 12:
            lines.append(f"  …（其餘 {len(auto_items) - 12} 筆）")

    lines.append("")
    lines.append(f"👤 需人工處理: {len(human_items)}")
    if human_items:
        lines.extend(human_items[:12])
        if len(human_items) > 12:
            lines.append(f"  …（其餘 {len(human_items) - 12} 筆）")

    lines.append("")
    lines.append(f"ℹ️ 資訊: {len(info_items)}")
    if info_items:
        lines.extend(info_items[:10])
        if len(info_items) > 10:
            lines.append(f"  …（其餘 {len(info_items) - 10} 筆）")

    lines.append("")
    lines.append("建議：可先手動觸發 QA Auto Fix workflow（dry_run=false）。")
    return "\n".join(lines)


def run(dry_run: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)
    today_jst = now.astimezone(JST).strftime("%Y/%m/%d")

    sb = _supabase_client()
    runs_24h, runs_7d = _fetch_runs(sb, since_24h, since_7d)
    pending_reports = _fetch_pending_reports(sb)
    tab_mismatch = _fetch_tokyoartbeat_mismatch(sb)

    triage = {
        "auto_fixable": [],
        "needs_human": [],
        "info_only": [],
    }

    streak3_zero = _three_day_zero_streak_sources(runs_7d, now)

    ran_sources_24h: set[str] = set()
    failed_sources: set[str] = set()
    zero_sources_24h: set[str] = set()
    for row in runs_24h:
        src = row.get("source") or "unknown"
        ran_sources_24h.add(src)
        if not row.get("success", True):
            failed_sources.add(src)
        elif int(row.get("events_processed", 0) or 0) == 0:
            zero_sources_24h.add(src)

    expected_sources_7d: set[str] = {
        (row.get("source") or "unknown") for row in runs_7d
    } - NON_DAILY_SOURCES
    missing_sources = sorted(expected_sources_7d - ran_sources_24h)

    for src in sorted(failed_sources):
        triage["needs_human"].append(f"- scraper failure: {src}")

    for src in sorted(zero_sources_24h):
        if src in streak3_zero:
            triage["needs_human"].append(f"- 連續 3 天 0-event（升級）: {src}")
        else:
            triage["info_only"].append(f"- 今日 0-event（觀察）: {src}")

    for src in missing_sources:
        triage["needs_human"].append(f"- 預期執行但 24h 未出現: {src}")

    for row in tab_mismatch:
        triage["auto_fixable"].append(
            f"- tokyoartbeat 日期可對齊: {row['event_id'][:8]} DB={row['db_date']} URL={row['url_date']}"
        )

    for row in pending_reports:
        types = row.get("report_types") or []
        event_id = (row.get("event_id") or "")[:8]
        if types and all(t in SAFE_AUTO_FIX_TYPES for t in types):
            triage["auto_fixable"].append(f"- pending report {event_id} types={','.join(types)}")
        else:
            triage["needs_human"].append(f"- pending report {event_id} types={','.join(types) or '?'}")

    summary = {
        "runs_24h": len(runs_24h),
        "runs_7d": len(runs_7d),
        "pending_reports": len(pending_reports),
        "tab_mismatch": len(tab_mismatch),
        "streak3_zero_sources": sorted(streak3_zero),
        "auto_fixable_count": len(triage["auto_fixable"]),
        "needs_human_count": len(triage["needs_human"]),
        "info_only_count": len(triage["info_only"]),
    }

    message = _build_message(today_jst, triage)

    logger.info("QA triage summary: %s", summary)
    if dry_run:
        print("\n--- QA TRIAGE (dry-run) LINE preview ---")
        print(message)
        print("--- end ---\n")
    else:
        send_line_message(message)
        logger.info("QA triage LINE message sent")

    return {"summary": summary, "triage": triage, "message": message}


def main() -> None:
    parser = argparse.ArgumentParser(description="QA triage (auto-fix vs human)")
    parser.add_argument("--dry-run", action="store_true", help="Print message only; no LINE push")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
