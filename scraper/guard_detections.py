"""
guard_detections.py — Monthly counts of data symptoms named by architect Guards (#356).

`.github/skills/agents/architect/SKILL.md` holds 103 guards: 47 leave a symptom
in data, 41 are code-level and 15 are process rules (inventory in
docs/evaluation/guards/README.md). This module covers the data guards whose
symptom fits single-table PostgREST filters; the rest need joins, regex or
column-to-column comparison and are tracked separately.

Each detection counts rows with `count="exact", head=True`. The monthly run
writes docs/evaluation/guards/YYYY-MM.{md,json}; with two earlier months on
disk, a guard at 0 for three months in a row is listed as a pruning candidate,
and a guard whose count rose is listed for follow-up.

`proxy` detections count a weaker signal (a review list, not violations), so
they are reported but never proposed for pruning.

Usage:
    python guard_detections.py --out-dir ../docs/evaluation/guards [--month 2026-11]

Read-only.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logger = logging.getLogger(__name__)

UTC = timezone.utc
JST = timezone(timedelta(hours=9))

ZERO_MONTHS_FOR_PRUNING = 3

# filters: list of (op, column, value). op is one of eq, neq, is, not.is, ilike,
# not.ilike, like, gte, cs, not.cs, in, or. For "or", column is the PostgREST or
# expression and value is None. A value "now-<N>d" becomes an ISO timestamp.
DETECTIONS: list[dict] = [
    {"id": "merged_but_active", "guard": "Manual Merge Completeness Guard", "table": "events",
     "filters": [("not.is", "merged_into_event_id", "null"), ("eq", "is_active", True)]},
    {"id": "reviewed_missing_title_translation", "guard": "Reviewed Event Translation Guard", "table": "events",
     "filters": [("eq", "annotation_status", "reviewed"), ("or", "name_zh.is.null,name_en.is.null", None)]},
    {"id": "failed_run_without_notes_30d", "guard": "Scraper Failure Notes Guard", "table": "scraper_runs",
     "filters": [("eq", "success", False), ("is", "notes", "null"), ("gte", "ran_at", "now-30d")]},
    {"id": "online_with_physical_fields", "guard": "Pure-online / Hybrid planning guard", "table": "events",
     "filters": [("eq", "location_name", "オンライン"),
                 ("or", "venue_id.not.is.null,location_address.not.is.null,location_prefectures.not.is.null", None)]},
    {"id": "report_prefix_injected", "guard": "Report Prefix Injection Guard", "table": "events",
     "filters": [("like", "name_ja", "【レポート】*"),
                 ("not.in", "source_name", "(google_news_rss,nhk_rss,prtimes,walkerplus,note_creators)"),
                 *[("not.ilike", "raw_title", f"*{k}*") for k in (
                     "レポ", "報告", "活動記録", "開催記録", "鑑賞記録", "アーカイブ", "recap",
                     "行ってきた", "観てきた", "結果発表")]]},
    {"id": "name_ja_report_suffix_lost", "guard": "Annotator name_ja Suffix Omission Guard", "table": "events",
     "filters": [("ilike", "raw_title", "*レポート*"), ("not.ilike", "name_ja", "*レポート*")]},
    {"id": "official_url_eiga", "guard": "Movie Lookup Official URL Guard", "table": "events",
     "filters": [("ilike", "official_url", "*eiga.com*")]},
    {"id": "official_url_ticket", "guard": "Cinema Official URL Extraction", "table": "events",
     "filters": [("or", "official_url.ilike.*/ticket/*,official_url.ilike.*/purchase/*", None)]},
    {"id": "placeholder_cover_image", "guard": "Derived enrichment candidate audit", "table": "events",
     "filters": [("or", "image_url.ilike.*noimage*,image_url.ilike.*no-cover*", None)]},
    {"id": "tv_location_not_standard", "guard": "TV / Non-Physical Location Standard", "table": "events",
     "filters": [("eq", "source_name", "gguide_tv"), ("eq", "is_active", True),
                 ("or", "location_name.is.null,location_name.neq.電視頻道,location_address.not.is.null", None)]},
    {"id": "note_creators_with_organizer", "guard": "Blog/Creator Source Thin Content Guard", "table": "events",
     "filters": [("eq", "source_name", "note_creators"), ("eq", "is_active", True), ("not.is", "organizer", "null")]},
    {"id": "yebizo_location_not_venue", "guard": "Collection Attribution Guard", "table": "events",
     "filters": [("eq", "source_name", "yebizo"), ("eq", "is_active", True),
                 ("or", "location_name.is.null,location_name.neq.東京都写真美術館", None)]},
    {"id": "ks_cinema_active_sub1", "guard": "Cinema Series Sub-Event Sub_Events Guard", "table": "events",
     "filters": [("eq", "source_name", "ks_cinema"), ("like", "source_id", "*_sub1*"), ("eq", "is_active", True)]},
    {"id": "organizer_missing_translation", "guard": "Organizer Multilingual Fields Guard", "table": "events",
     "filters": [("eq", "is_active", True), ("not.is", "organizer", "null"),
                 ("or", "organizer_zh.is.null,organizer_en.is.null", None)]},
    {"id": "person_missing_translation", "guard": "Performer Multilingual Fields Guard", "table": "events",
     "filters": [("in", "annotation_status", "(annotated,reviewed)"), ("eq", "is_active", True),
                 ("or", "and(performer.not.is.null,or(performer_zh.is.null,performer_en.is.null)),"
                        "and(director.not.is.null,or(director_zh.is.null,director_en.is.null))", None)]},
    {"id": "inactive_person_missing_translation", "guard": "Known Person Map Guard", "table": "events",
     "filters": [("eq", "is_active", False), ("not.is", "performer", "null"),
                 ("or", "performer_zh.is.null,performer_en.is.null", None)]},
    {"id": "tcc_kanji_time_missing_hours", "guard": "Kanji Time Format business_hours Guard", "table": "events",
     "filters": [("eq", "source_name", "taiwan_cultural_center"), ("eq", "is_active", True),
                 ("is", "business_hours", "null"), ("like", "raw_description", "*時*分*")]},
    {"id": "museum_source_missing_organizer", "guard": "Venue = Organizer Default Guard", "table": "events",
     "filters": [("eq", "source_name", "tokyoartbeat"), ("eq", "is_active", True),
                 ("or", "organizer.is.null,event_form.is.null,event_form.eq.{}", None)]},
    {"id": "organizer_type_without_organizer", "guard": "organizer_type Batch Inference Guard", "table": "events",
     "filters": [("is", "organizer", "null"), ("not.is", "organizer_type", "null"),
                 ("neq", "organizer_type", "{}"), ("not.cs", "organizer_type", "{unknown}")]},
    {"id": "implemented_without_scraper_key", "guard": "Auto-Generate Promotion Checklist", "table": "research_sources",
     "filters": [("eq", "status", "implemented"), ("is", "scraper_source_name", "null")]},
    {"id": "lowsignal_rejected_above_threshold", "guard": "Auto-Research Low-Signal Policy Guard",
     "table": "research_sources",
     "filters": [("or", "status.eq.not-viable,auto_research_status.eq.not-viable", None),
                 ("gte", "auto_research_score", 0.30)]},
    # Proxies: review lists, not violations.
    {"id": "venue_name_without_address", "guard": "Address Regex Prefecture-Optional Guard", "table": "events",
     "proxy": True,
     "filters": [("eq", "is_active", True), ("not.is", "location_name", "null"), ("is", "location_address", "null"),
                 ("is", "location_prefectures", "null"), ("not.in", "location_name", "(オンライン,電視頻道)")]},
    {"id": "performer_null_with_guest_title", "guard": "Performer Null Guard", "table": "events", "proxy": True,
     "filters": [("eq", "annotation_status", "annotated"), ("eq", "is_active", True), ("is", "performer", "null"),
                 ("or", "raw_title.ilike.*氏を迎え*,raw_title.ilike.*さんを迎え*,raw_title.ilike.*講師*,"
                        "raw_title.ilike.*ゲスト*", None)]},
    {"id": "organizer_with_slash", "guard": "Joint Distributor Split Guard", "table": "events", "proxy": True,
     "filters": [("eq", "is_active", True), ("or", "organizer.like.*/*,organizer.like.*／*", None)]},
    {"id": "organizer_fk_unresolved", "guard": "Entity Normalization Guard", "table": "events", "proxy": True,
     "filters": [("eq", "is_active", True), ("not.is", "organizer", "null"), ("is", "organizer_id", "null")]},
    {"id": "reviewed_missing_hours", "guard": "reviewed 保護邊界 Guard", "table": "events", "proxy": True,
     "filters": [("eq", "annotation_status", "reviewed"), ("eq", "is_active", True), ("is", "business_hours", "null")]},
    {"id": "inactive_without_pass", "guard": "Database Safety Rules", "table": "events", "proxy": True,
     "filters": [("eq", "is_active", False), ("is", "merged_into_event_id", "null"), ("is", "deactivated_by_pass", "null")]},
    {"id": "missing_address_reports_dismissed", "guard": "auto_qa False Positive Guard", "table": "event_reports",
     "proxy": True,
     "filters": [("cs", "report_types", "{auto_qa_missing_address}"), ("eq", "status", "dismissed")]},
]


# ─── Query building ───────────────────────────────────────────────────────────

def resolve_value(value, now: datetime):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str) and value.startswith("now-") and value.endswith("d"):
        return (now - timedelta(days=int(value[4:-1]))).isoformat()
    return value


def apply_filters(query, filters: list[tuple], now: datetime):
    for op, column, value in filters:
        value = resolve_value(value, now)
        if op == "or":
            query = query.or_(column)
        elif op.startswith("not."):
            query = query.not_.filter(column, op[4:], value)
        elif op in ("eq", "neq", "gte", "lt", "like", "ilike", "is", "cs", "in"):
            query = query.filter(column, op, value)
        else:
            raise ValueError(f"unsupported op {op!r}")
    return query


def run_detections(sb, now: datetime, detections: list[dict] = DETECTIONS) -> list[dict]:
    results = []
    for d in detections:
        try:
            query = apply_filters(sb.table(d["table"]).select("*", count="exact", head=True), d["filters"], now)
            count = query.execute().count
            error = None
        except Exception as exc:  # one broken detection must not hide the others
            count, error = None, str(exc)[:200]
            logger.warning("detection %s failed: %s", d["id"], exc)
        results.append({"id": d["id"], "guard": d["guard"], "proxy": bool(d.get("proxy")),
                        "count": count, "error": error})
    return results


# ─── Trends ───────────────────────────────────────────────────────────────────

def load_history(out_dir: Path, month: str, n: int) -> list[dict]:
    """The ``n`` most recent monthly JSON files strictly before ``month``."""
    files = sorted(p for p in out_dir.glob("????-??.json") if p.stem < month)
    return [json.loads(p.read_text()) for p in files[-n:]]


def trends(results: list[dict], history: list[dict]) -> dict:
    """Pruning candidates (0 for ZERO_MONTHS_FOR_PRUNING months) and rising guards."""
    past = [{r["id"]: r["count"] for r in h["results"]} for h in history]
    prune, rising = [], []
    for r in results:
        if r["count"] is None:
            continue
        series = [p.get(r["id"]) for p in past] + [r["count"]]
        if (not r["proxy"] and len(series) >= ZERO_MONTHS_FOR_PRUNING
                and all(c == 0 for c in series[-ZERO_MONTHS_FOR_PRUNING:])):
            prune.append(r["id"])
        if past and past[-1].get(r["id"]) is not None and r["count"] > past[-1][r["id"]]:
            rising.append({"id": r["id"], "previous": past[-1][r["id"]], "current": r["count"]})
    return {"prune_candidates": prune, "rising": rising, "months_of_history": len(past)}


# ─── Report ───────────────────────────────────────────────────────────────────

def write_outputs(out_dir: Path, month: str, results: list[dict], trend: dict, now: datetime) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{month}.json").write_text(json.dumps(
        {"month": month, "generated_at": now.isoformat(), "results": results, "trends": trend},
        ensure_ascii=False, indent=2,
    ) + "\n")

    def _count(r):
        return "查詢失敗" if r["count"] is None else str(r["count"])

    lines = [
        f"# Guard Detection — {month}",
        "",
        f"架構師 SKILL 中可用單表查詢偵測的 data guard（#356）。產生時間 {now.astimezone(JST):%Y-%m-%d %H:%M} JST；"
        f"歷史月份 {trend['months_of_history']} 個。",
        "",
        "## 違規計數（目標為 0）",
        "",
        "| detection | guard | 數量 |",
        "|---|---|---|",
    ]
    lines += [f"| {r['id']} | {r['guard']} | {_count(r)} |" for r in results if not r["proxy"]]
    lines += [
        "",
        "## 代理指標（待審清單，不是違規數）",
        "",
        "| detection | guard | 數量 |",
        "|---|---|---|",
    ]
    lines += [f"| {r['id']} | {r['guard']} | {_count(r)} |" for r in results if r["proxy"]]
    lines += ["", "## 趨勢", ""]
    if trend["months_of_history"] < ZERO_MONTHS_FOR_PRUNING - 1:
        lines.append(f"_歷史不足：連續 {ZERO_MONTHS_FOR_PRUNING} 個月為 0 才列為精簡候選。_")
    else:
        lines.append(f"- 連續 {ZERO_MONTHS_FOR_PRUNING} 個月為 0（候選精簡）：{', '.join(trend['prune_candidates']) or '無'}")
    if trend["rising"]:
        lines.append("- 比上月增加：" + "、".join(f"{x['id']}（{x['previous']} → {x['current']}）" for x in trend["rising"]))
    errors = [r for r in results if r["error"]]
    if errors:
        lines += ["", "## 查詢失敗", ""] + [f"- {r['id']}：`{r['error']}`" for r in errors]
    path = out_dir / f"{month}.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="Monthly guard detection counts")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--month", default=None, help="YYYY-MM label (default: current month, JST)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from database import _get_client

    now = datetime.now(tz=UTC)
    month = args.month or now.astimezone(JST).strftime("%Y-%m")
    results = run_detections(_get_client(), now)
    trend = trends(results, load_history(args.out_dir, month, ZERO_MONTHS_FOR_PRUNING - 1))
    path = write_outputs(args.out_dir, month, results, trend, now)
    print(path.read_text())
    return 0 if all(r["error"] is None for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
