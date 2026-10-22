"""
eval_scraper_quality.py — Weekly per-source scraper quality report (#354, #327).

Read-only. Sections:
    1. Output health: runs and events per source over 7 / 28 days, days since the
       last non-zero run, and a status that knows which zeros are expected
       (source_expectations.json: seasonal, sporadic, or broken with an issue).
    2. Field completeness: share of active parent events created in the window
       with each quality_fields.TRACKED_FIELDS value filled. Pure publication
       records skip the fields the publication policy keeps empty.
    3. Correction rate: field_corrections per 100 events, human (corrected_by set)
       separately from script locks, which are most rows (#373). A report_id alone
       is not human: auto-QA reports carry one and qa_auto_fix settles them.
    4. DOM drift: scrape-time parsed_fields_median from scraper_runs.notes
       (written by main.py since #354). Alert when the last 3 runs are all more
       than 30% below the median of the earlier runs.
    5. Annotator fill: median filled fields of stored events minus the scrape-time
       median, i.e. how much the annotator adds on top of the scraper.

Usage:
    python eval_scraper_quality.py --output reports/scraper_quality_2026-10-25.md
    python eval_scraper_quality.py --output report.md --json-output report.json

Does NOT write to the database.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from quality_fields import TRACKED_FIELDS, applicable_fields, count_filled, is_filled  # noqa: E402

logger = logging.getLogger(__name__)

UTC = timezone.utc
JST = timezone(timedelta(hours=9))

EXPECTATIONS_PATH = Path(__file__).parent / "source_expectations.json"

RUN_LOOKBACK_DAYS = 120
EVENT_WINDOW_DAYS = 90
DRIFT_RECENT_RUNS = 3
DRIFT_DROP = 0.30
DRIFT_MIN_HISTORY = 3
MIN_EVENTS_FOR_RANKING = 10

# Rows in scraper_runs that are not scrapers (same idea as daily_report.py).
META_PREFIXES = ("researcher", "annotator", "merger", "backfill", "enrich", "geocode", "qa_", "auto_qa")

STATUS_LABEL = {
    "active": "🟢 有產出",
    "quiet": "🟡 本週 0，28 天內有",
    "off_season": "🔵 季節外",
    "quiet_expected": "🔵 零星來源，仍在預期內",
    "quiet_too_long": "🟠 零星來源，安靜過久",
    "known_broken": "🔴 已知故障",
    "failing": "🔴 最近一次執行失敗",
    "zero_unexplained": "🔴 28 天以上 0，原因未知",
    "no_runs": "⚫ 沒有執行紀錄",
}
NEEDS_ACTION = ("zero_unexplained", "quiet_too_long", "failing")


# ─── Pure logic ───────────────────────────────────────────────────────────────

def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_scraper_key(key: str) -> bool:
    return bool(key) and not any(key.startswith(p) for p in META_PREFIXES)


def classify_output(runs: list[dict], expectation: dict | None, now: datetime) -> dict:
    """Summarize one source's runs and give it a status.

    ``runs`` are scraper_runs rows (ran_at, events_processed, success) for the
    source within RUN_LOOKBACK_DAYS.
    """
    runs = sorted(runs, key=lambda r: r["ran_at"])
    expectation = expectation or {}

    def _since(days):
        cutoff = now - timedelta(days=days)
        return [r for r in runs if _parse_ts(r["ran_at"]) >= cutoff]

    last7, last28 = _since(7), _since(28)
    nonzero = [r for r in runs if (r.get("events_processed") or 0) > 0]
    last_nonzero = _parse_ts(nonzero[-1]["ran_at"]) if nonzero else None
    days_since = (now - last_nonzero).days if last_nonzero else None

    pattern = expectation.get("pattern")
    if not runs:
        status = "no_runs"
    elif pattern == "broken":
        status = "known_broken"
    elif runs[-1].get("success") is False:
        status = "failing"
    elif any((r.get("events_processed") or 0) > 0 for r in last7):
        status = "active"
    elif pattern == "seasonal" and now.astimezone(JST).month not in expectation.get("active_months", []):
        status = "off_season"
    elif pattern == "sporadic":
        quiet = days_since if days_since is not None else RUN_LOOKBACK_DAYS
        status = "quiet_expected" if quiet <= expectation.get("max_quiet_days", 0) else "quiet_too_long"
    elif any((r.get("events_processed") or 0) > 0 for r in last28):
        status = "quiet"
    else:
        status = "zero_unexplained"

    return {
        "runs_7d": len(last7),
        "events_7d": sum(r.get("events_processed") or 0 for r in last7),
        "events_28d": sum(r.get("events_processed") or 0 for r in last28),
        "last_nonzero": last_nonzero.date().isoformat() if last_nonzero else None,
        "days_since_nonzero": days_since,
        "status": status,
        "issue": expectation.get("issue"),
        "note": expectation.get("note"),
    }


_NOTE_RE = {
    "parsed": re.compile(r"parsed_fields_median=([0-9.]+)"),
    "sources": re.compile(r"event_sources=([^,\s]+)"),
}


def parse_run_notes(notes: str | None) -> dict:
    notes = notes or ""
    parsed = _NOTE_RE["parsed"].search(notes)
    sources = _NOTE_RE["sources"].search(notes)
    return {
        "parsed_fields_median": float(parsed.group(1)) if parsed else None,
        "event_sources": sources.group(1).split("|") if sources else [],
    }


def detect_drift(values: list[float]) -> dict | None:
    """Flag a sustained drop in scrape-time fields per event.

    Alert when each of the last DRIFT_RECENT_RUNS values is more than DRIFT_DROP
    below the median of the earlier ones. Returns None when there is not yet
    enough history (DRIFT_MIN_HISTORY earlier runs).
    """
    if len(values) < DRIFT_RECENT_RUNS + DRIFT_MIN_HISTORY:
        return None
    history, recent = values[:-DRIFT_RECENT_RUNS], values[-DRIFT_RECENT_RUNS:]
    baseline = median(history)
    if baseline <= 0:
        return {"baseline": baseline, "recent": recent, "alert": False}
    return {
        "baseline": baseline,
        "recent": recent,
        "alert": all(v < baseline * (1 - DRIFT_DROP) for v in recent),
    }


def map_event_sources(run_key: str, event_source_names: set[str], noted: list[str]) -> list[str]:
    """events.source_name values a run key writes.

    Prefer what main.py recorded in the run notes; fall back to the same name, then
    to the name with underscores removed (tokyo_art_beat → tokyoartbeat).
    """
    if noted:
        return sorted(noted)
    if run_key in event_source_names:
        return [run_key]
    squashed = run_key.replace("_", "")
    matches = sorted(n for n in event_source_names if n.replace("_", "") == squashed)
    return matches


def completeness(events: list[dict]) -> dict[str, dict]:
    """Per tracked field: filled / applicable over the given events."""
    out = {f: {"filled": 0, "applicable": 0} for f in TRACKED_FIELDS}
    for ev in events:
        for f in applicable_fields(ev):
            out[f]["applicable"] += 1
            if is_filled(ev.get(f)):
                out[f]["filled"] += 1
    return out


def completeness_score(table: dict[str, dict]) -> float | None:
    """Mean fill rate over fields that apply to at least one event."""
    rates = [v["filled"] / v["applicable"] for v in table.values() if v["applicable"]]
    return sum(rates) / len(rates) if rates else None


def is_human_correction(fc: dict) -> bool:
    """Only the admin UI sets corrected_by. Rows with just a report_id come from
    qa_auto_fix settling auto-QA reports (all 86 such rows in the 90 days to
    2026-10-22 were system reports)."""
    return bool(fc.get("corrected_by"))


def correction_rates(fc_rows: list[dict], source_by_event: dict[str, str], events_by_source: dict[str, int]) -> dict:
    counts: dict[str, dict] = defaultdict(lambda: {"human": 0, "script": 0})
    for fc in fc_rows:
        src = source_by_event.get(fc.get("event_id"))
        if not src:
            continue
        counts[src]["human" if is_human_correction(fc) else "script"] += 1
    out = {}
    for src, c in counts.items():
        n = events_by_source.get(src, 0)
        out[src] = {
            **c,
            "events": n,
            "human_per_100": round(c["human"] * 100 / n, 1) if n else None,
            "script_per_100": round(c["script"] * 100 / n, 1) if n else None,
        }
    return out


def build_rows(
    run_keys: list[str],
    runs_by_key: dict[str, list[dict]],
    events_by_name: dict[str, list[dict]],
    fc_rows: list[dict],
    source_by_event: dict[str, str],
    expectations: dict[str, dict],
    now: datetime,
) -> list[dict]:
    """One row per scraper run key with every metric the report shows."""
    event_names = set(events_by_name)
    rows = []
    for key in sorted(run_keys):
        runs = runs_by_key.get(key, [])
        notes = [parse_run_notes(r.get("notes")) for r in sorted(runs, key=lambda r: r["ran_at"])]
        noted_sources = next((n["event_sources"] for n in reversed(notes) if n["event_sources"]), [])
        names = map_event_sources(key, event_names, noted_sources)
        events = [e for n in names for e in events_by_name.get(n, [])]
        table = completeness(events)
        parsed = [n["parsed_fields_median"] for n in notes if n["parsed_fields_median"] is not None]
        stored_median = median(count_filled(e) for e in events) if events else None
        rows.append({
            "source": key,
            "event_sources": names,
            "output": classify_output(runs, expectations.get(key), now),
            "events_90d": len(events),
            "completeness": table,
            "completeness_score": completeness_score(table),
            "drift": detect_drift(parsed),
            "annotator_fill": (
                round(stored_median - median(parsed), 1) if parsed and stored_median is not None else None
            ),
        })

    rates = correction_rates(
        fc_rows, source_by_event, {n: len(evs) for n, evs in events_by_name.items()}
    )
    for row in rows:
        merged = {"human": 0, "script": 0, "events": 0}
        for n in row["event_sources"]:
            r = rates.get(n)
            if r:
                for k in merged:
                    merged[k] += r[k]
        n = row["events_90d"]
        row["corrections"] = {
            **merged,
            "human_per_100": round(merged["human"] * 100 / n, 1) if n else None,
            "script_per_100": round(merged["script"] * 100 / n, 1) if n else None,
        }
    return rows


def action_items(rows: list[dict]) -> list[dict]:
    """What needs a person this week, most urgent first."""
    items = []
    for r in rows:
        status = r["output"]["status"]
        if status in NEEDS_ACTION:
            items.append({"source": r["source"], "reason": STATUS_LABEL[status]})
        if r["drift"] and r["drift"]["alert"]:
            items.append({
                "source": r["source"],
                "reason": f"DOM drift：最近 3 次解析欄位 {r['drift']['recent']}，先前中位數 {r['drift']['baseline']:g}",
            })
    ranked = sorted(
        (r for r in rows if r["events_90d"] >= MIN_EVENTS_FOR_RANKING and r["completeness_score"] is not None),
        key=lambda r: r["completeness_score"],
    )
    for r in ranked[:3]:
        items.append({
            "source": r["source"],
            "reason": f"欄位完整度最低前 3（{r['completeness_score']:.0%}，{r['events_90d']} 筆）",
        })
    return items


# ─── Report ───────────────────────────────────────────────────────────────────

def _pct(filled: int, applicable: int) -> str:
    return f"{filled / applicable:.0%}" if applicable else "—"


def write_report(rows: list[dict], now: datetime, output: Path) -> None:
    status_counts = defaultdict(int)
    for r in rows:
        status_counts[r["output"]["status"]] += 1

    lines = [
        f"# Scraper 品質週報 — {now.astimezone(JST):%Y-%m-%d}",
        "",
        f"- 來源：{len(rows)} 個 scraper；產出看最近 7／28 天，欄位與修正看最近 {EVENT_WINDOW_DAYS} 天建立的有效母事件",
        "- 狀態："
        + "、".join(f"{STATUS_LABEL[s]} {status_counts[s]}" for s in STATUS_LABEL if status_counts[s]),
        "",
        "## 需要處理",
        "",
    ]
    items = action_items(rows)
    if items:
        lines += ["| source | 原因 |", "|---|---|"]
        lines += [f"| {i['source']} | {i['reason']} |" for i in items]
    else:
        lines.append("_本週沒有需要處理的來源。_")
    lines.append("")

    lines += [
        "## 1. 產出健康",
        "",
        "| source | 狀態 | 7 天執行 | 7 天產出 | 28 天產出 | 最後有產出 | 說明 |",
        "|---|---|---|---|---|---|---|",
    ]
    order = list(STATUS_LABEL)
    for r in sorted(rows, key=lambda r: (order.index(r["output"]["status"]), r["source"]), reverse=False):
        o = r["output"]
        if o["status"] == "active":
            continue
        note = o["note"] or ""
        if o["issue"]:
            note = f"#{o['issue']} {note}".strip()
        lines.append(
            f"| {r['source']} | {STATUS_LABEL[o['status']]} | {o['runs_7d']} | {o['events_7d']} | "
            f"{o['events_28d']} | {o['last_nonzero'] or '120 天內沒有'} | {note} |"
        )
    active = sorted(r["source"] for r in rows if r["output"]["status"] == "active")
    lines += ["", f"有產出的來源（{len(active)}）：{', '.join(active)}", ""]

    lines += [
        "## 2. 欄位完整度",
        "",
        f"只列 {EVENT_WINDOW_DAYS} 天內有 ≥ {MIN_EVENTS_FOR_RANKING} 筆事件的來源，依平均完整度由低到高。純出版紀錄不計地址、營業時間與場館名稱。",
        "",
        "| source | 事件 | 平均 | " + " | ".join(TRACKED_FIELDS) + " |",
        "|---|---|---|" + "---|" * len(TRACKED_FIELDS),
    ]
    ranked = sorted(
        (r for r in rows if r["events_90d"] >= MIN_EVENTS_FOR_RANKING and r["completeness_score"] is not None),
        key=lambda r: r["completeness_score"],
    )
    for r in ranked:
        cells = [_pct(r["completeness"][f]["filled"], r["completeness"][f]["applicable"]) for f in TRACKED_FIELDS]
        lines.append(f"| {r['source']} | {r['events_90d']} | {r['completeness_score']:.0%} | " + " | ".join(cells) + " |")
    lines.append("")

    lines += [
        "## 3. 修正率（每 100 筆事件）",
        "",
        "人工：`corrected_by` 有值（後台編輯）。腳本：annotator、qa_auto_fix、publication-policy 等自動寫入，只有 `report_id` 的列也屬此類，不代表錯誤（#373）。",
        "",
        "| source | 事件 | 人工 | 人工／100 | 腳本 | 腳本／100 |",
        "|---|---|---|---|---|---|",
    ]
    corr = sorted(
        (r for r in rows if r["corrections"]["human"] or r["corrections"]["script"]),
        key=lambda r: (-(r["corrections"]["human_per_100"] or 0), -(r["corrections"]["script"])),
    )
    for r in corr[:20]:
        c = r["corrections"]
        lines.append(
            f"| {r['source']} | {r['events_90d']} | {c['human']} | {c['human_per_100'] if c['human_per_100'] is not None else '—'} | "
            f"{c['script']} | {c['script_per_100'] if c['script_per_100'] is not None else '—'} |"
        )
    if not corr:
        lines.append("| — | | | | | |")
    lines.append("")

    with_parsed = [r for r in rows if r["drift"] is not None]
    lines += [
        "## 4. DOM drift",
        "",
        f"比較最近 {DRIFT_RECENT_RUNS} 次執行的解析欄位數中位數與先前的中位數，全部下降超過 {DRIFT_DROP:.0%} 才告警。",
        f"資料來自 main.py 寫入 `scraper_runs.notes` 的 `parsed_fields_median`；目前有足夠紀錄的來源：{len(with_parsed)} 個。",
        "",
    ]
    alerts = [r for r in with_parsed if r["drift"]["alert"]]
    if alerts:
        lines += ["| source | 先前中位數 | 最近 3 次 |", "|---|---|---|"]
        lines += [f"| {r['source']} | {r['drift']['baseline']:g} | {r['drift']['recent']} |" for r in alerts]
    else:
        lines.append("_沒有告警。_" if with_parsed else "_紀錄累積中：每個來源需要至少 6 次帶有欄位數的執行。_")
    lines.append("")

    fills = sorted((r for r in rows if r["annotator_fill"] is not None), key=lambda r: -r["annotator_fill"])
    lines += [
        "## 5. Annotator 補填",
        "",
        "已入庫事件的追蹤欄位中位數，減去 scraper 當下解析出的中位數。數字越大，代表 scraper 抽得越少、越依賴 annotator。",
        "",
    ]
    if fills:
        lines += ["| source | 補填欄位數 |", "|---|---|"]
        lines += [f"| {r['source']} | {r['annotator_fill']:+g} |" for r in fills[:15]]
    else:
        lines.append("_紀錄累積中：需要 main.py 寫入 `parsed_fields_median` 後的執行紀錄。_")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")


# ─── Data access (read-only) ─────────────────────────────────────────────────

_PAGE = 1000


def _fetch_all(make_query) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        batch = make_query().range(start, start + _PAGE - 1).execute().data or []
        rows += batch
        if len(batch) < _PAGE:
            return rows
        start += _PAGE


def _scraper_keys() -> list[str] | None:
    """Run keys of every registered scraper, or None if main.py cannot be imported."""
    try:
        import main  # noqa: PLC0415 — heavy import, only needed here

        return [main._scraper_key(s) for s in main.SCRAPERS]
    except Exception as exc:  # pragma: no cover - depends on the runtime environment
        logger.warning("Could not import main.SCRAPERS, falling back to scraper_runs keys: %s", exc)
        return None


def collect(sb, now: datetime) -> tuple[list[str], dict, dict, list[dict], dict]:
    run_since = (now - timedelta(days=RUN_LOOKBACK_DAYS)).isoformat()
    event_since = (now - timedelta(days=EVENT_WINDOW_DAYS)).isoformat()

    runs = _fetch_all(lambda: sb.table("scraper_runs")
                      .select("source,ran_at,events_processed,success,notes")
                      .gte("ran_at", run_since).order("ran_at"))
    runs_by_key: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        if is_scraper_key(r.get("source") or ""):
            runs_by_key[r["source"]].append(r)

    columns = ",".join(["id", "source_name", "event_form", *TRACKED_FIELDS])
    events = _fetch_all(lambda: sb.table("events").select(columns)
                        .gte("created_at", event_since).eq("is_active", True)
                        .is_("parent_event_id", "null").order("created_at"))
    events_by_name: dict[str, list[dict]] = defaultdict(list)
    source_by_event = {}
    for e in events:
        events_by_name[e["source_name"]].append(e)
        source_by_event[e["id"]] = e["source_name"]

    fc_rows = _fetch_all(lambda: sb.table("field_corrections")
                         .select("event_id,corrected_by,report_id")
                         .gte("created_at", event_since).order("created_at"))
    # Corrections count only against events created in the same window.
    fc_rows = [fc for fc in fc_rows if fc.get("event_id") in source_by_event]

    keys = _scraper_keys() or list(runs_by_key)
    return keys, runs_by_key, events_by_name, fc_rows, source_by_event


def main() -> int:
    ap = argparse.ArgumentParser(description="Weekly per-source scraper quality report")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--json-output", type=Path, default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from database import _get_client

    now = datetime.now(tz=UTC)
    keys, runs_by_key, events_by_name, fc_rows, source_by_event = collect(_get_client(), now)
    expectations = json.loads(EXPECTATIONS_PATH.read_text())["sources"]
    rows = build_rows(keys, runs_by_key, events_by_name, fc_rows, source_by_event, expectations, now)
    write_report(rows, now, args.output)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(
            {"generated_at": now.isoformat(), "rows": rows, "action_items": action_items(rows)},
            ensure_ascii=False, indent=2, default=str,
        ))
    logger.info("Report written: %s (%d sources)", args.output, len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
