"""One-off: retire event reports and the 'report' category (spec no-event-reports).

The user decided on 2026-11-22 that Tokyo Taiwan Radar no longer lists event
reports (活動報導), that the ones already listed come down, and that the
'report' tag goes away. This script does the existing-data half:

  1. every event whose category contains 'report' (active or not) loses it;
  2. the 【レポート】 / 【活動報導】 / [Report] name prefixes are removed;
  3. active rows whose raw_title is a recap (event_report.is_event_report) are
     deactivated, together with their active child events;
  4. field_corrections locks on category / names and the category_corrections
     few-shot table are rewritten the same way, so human locks and the
     feedback prompt cannot bring 'report' back.

Modes
  (default)            dry run: read-only, writes the plan JSON and a markdown
                       review list under scraper/reports/
  --apply PLAN.json    apply exactly that plan (production write: human gate).
                       Each event update is guarded by the row's updated_at at
                       planning time; a row that changed since is skipped.
  --deactivate-ids a,b add these event ids (full UUIDs) to the deactivation set
                       when planning, e.g. after reviewing the "review" list.

Usage
  cd scraper
  python _oneoff_retire_event_reports.py
  python _oneoff_retire_event_reports.py --deactivate-ids <uuid>,<uuid>
  python _oneoff_retire_event_reports.py --apply reports/retire_event_reports_<ts>.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from event_report import EVENT_REPORT_REASON, is_event_report, strip_report_prefix
from publication_rules import is_pure_publication_record

logger = logging.getLogger("retire_event_reports")

RETIRED = "report"
EVENT_URL = "https://tokyotaiwanradar.com/ja/events/{id}"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
DEACTIVATED_BY_PASS = "admin_manual"
NAME_FIELDS = ("name_ja", "name_zh", "name_en")
EVENT_FIELDS = (
    "id,source_name,raw_title,name_ja,name_zh,name_en,category,event_form,"
    "is_active,parent_event_id,updated_at"
)
# Sources whose items are never event reports (broadcasts, bibliographic records).
NEVER_REPORT_SOURCES = {"gguide_tv", "ndl_opensearch", "hanmoto", "kawade_rss"}
# News-type sources: an item that is not caught by the title rule still needs a
# human look, because their articles often recap a past event in the body.
REVIEW_SOURCES = {"google_news_rss", "nhk_rss", "tiff_jp", "prtimes", "note_creators"}


# ---------------------------------------------------------------------------
# Planning (pure, unit-tested)
# ---------------------------------------------------------------------------

def _strip(values: Any) -> list[str]:
    return [v for v in (values or []) if v != RETIRED]


def is_recap_row(row: dict) -> bool:
    if (row.get("source_name") or "") in NEVER_REPORT_SOURCES:
        return False
    if is_pure_publication_record(row):
        return False
    # raw_title, never name_ja: names may already carry the injected prefix.
    return is_event_report(row.get("raw_title"), row.get("event_form"))


def plan_events(rows: list[dict], children: list[dict], extra_ids: set[str]) -> dict:
    """Build the per-event plan.

    rows      — events whose category contains 'report'
    children  — active events whose parent_event_id is one of rows' ids
    extra_ids — ids the user chose to deactivate after review
    """
    updates: list[dict] = []
    buckets: dict[str, list[dict]] = {"deactivate": [], "review": [], "empty_category": [], "tag_only": []}
    deactivated: set[str] = set()

    for row in rows:
        patch: dict[str, Any] = {}
        new_cat = _strip(row.get("category"))
        if new_cat != list(row.get("category") or []):
            patch["category"] = new_cat
        for field in NAME_FIELDS:
            new_name = strip_report_prefix(row.get(field))
            if new_name != row.get(field):
                patch[field] = new_name

        bucket = "tag_only"
        if row.get("is_active") and (row["id"] in extra_ids or is_recap_row(row)):
            patch.update(is_active=False, deactivated_reason=EVENT_REPORT_REASON,
                         deactivated_by_pass=DEACTIVATED_BY_PASS)
            deactivated.add(row["id"])
            bucket = "deactivate"
        elif row.get("is_active") and not new_cat:
            bucket = "empty_category"
        elif row.get("is_active") and (row.get("source_name") or "") in REVIEW_SOURCES:
            bucket = "review"
        if row.get("is_active"):
            buckets[bucket].append(row)
        if patch:
            updates.append({"id": row["id"], "updated_at": row.get("updated_at"), "patch": patch})

    for child in children:
        if child.get("is_active") and child.get("parent_event_id") in deactivated and child["id"] not in deactivated:
            updates.append({
                "id": child["id"], "updated_at": child.get("updated_at"),
                "patch": {"is_active": False, "deactivated_reason": EVENT_REPORT_REASON,
                          "deactivated_by_pass": DEACTIVATED_BY_PASS},
            })
            deactivated.add(child["id"])
            buckets["deactivate"].append(child)

    return {"updates": updates, "buckets": buckets}


def plan_field_corrections(fc_rows: list[dict]) -> list[dict]:
    """Rewrite FC locks that still hold 'report' or an injected name prefix."""
    out = []
    for fc in fc_rows:
        value = fc.get("corrected_value")
        if not isinstance(value, str):
            continue
        new_value = value
        if fc.get("field_name") == "category":
            try:
                parsed = json.loads(value)
            except ValueError:
                continue
            if isinstance(parsed, list) and RETIRED in parsed:
                new_value = json.dumps(_strip(parsed), ensure_ascii=False)
        elif fc.get("field_name") in NAME_FIELDS:
            new_value = strip_report_prefix(value)
        if new_value != value:
            out.append({"id": fc["id"], "corrected_value": new_value})
    return out


def plan_category_corrections(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        patch = {}
        for key in ("ai_category", "corrected_category"):
            if RETIRED in (row.get(key) or []):
                patch[key] = _strip(row.get(key))
        if patch:
            out.append({"id": row["id"], "patch": patch})
    return out


def render_markdown(plan: dict, generated_at: str) -> str:
    b = plan["events"]["buckets"]
    lines = [
        f"# 活動報導下架 dry-run（{generated_at}）",
        "",
        f"- 要更新的活動列：{len(plan['events']['updates'])}",
        f"- field_corrections 改寫：{len(plan['field_corrections'])}",
        f"- category_corrections 改寫：{len(plan['category_corrections'])}",
        "",
    ]
    titles = {
        "deactivate": "停用（活動報導，含子活動）",
        "review": "待覆核：新聞型來源、標題看不出是報導（只拿掉標籤；要停用就用 --deactivate-ids 重跑）",
        "empty_category": "拿掉標籤後分類變空（保留上架；下次重新標註會補分類）",
        "tag_only": "只拿掉標籤（保留上架）",
    }
    for key in ("deactivate", "review", "empty_category", "tag_only"):
        rows = b[key]
        lines += [f"## {titles[key]}（{len(rows)}）", ""]
        for r in rows:
            title = (r.get("raw_title") or r.get("name_ja") or "").replace("\n", " ")[:80]
            lines.append(f"- [{r['id'][:8]}]({EVENT_URL.format(id=r['id'])}) `{r.get('source_name')}` {title}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def _client():
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv(Path(__file__).resolve().parent / ".env")
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def build_plan(sb, extra_ids: set[str]) -> dict:
    from db_paging import fetch_all

    rows = fetch_all(lambda: sb.table("events").select(EVENT_FIELDS).contains("category", [RETIRED]).order("id"))
    ids = [r["id"] for r in rows]
    extra_rows = []
    missing = extra_ids - set(ids)
    if missing:
        extra_rows = sb.table("events").select(EVENT_FIELDS).in_("id", sorted(missing)).execute().data or []
    children: list[dict] = []
    all_ids = ids + [r["id"] for r in extra_rows]
    for i in range(0, len(all_ids), 100):
        chunk = all_ids[i:i + 100]
        children += sb.table("events").select(EVENT_FIELDS).in_("parent_event_id", chunk).eq("is_active", True).execute().data or []
    fc_rows: list[dict] = []
    for i in range(0, len(all_ids), 100):
        chunk = all_ids[i:i + 100]
        fc_rows += (
            sb.table("field_corrections").select("id,event_id,field_name,corrected_value")
            .in_("event_id", chunk).in_("field_name", ["category", *NAME_FIELDS]).execute().data or []
        )
    cc_rows = fetch_all(lambda: sb.table("category_corrections").select("id,ai_category,corrected_category").order("id"))
    return {
        "schema": "retire-event-reports.v1",
        "events": plan_events(rows + extra_rows, children, extra_ids),
        "field_corrections": plan_field_corrections(fc_rows),
        "category_corrections": plan_category_corrections(cc_rows),
    }


def apply_plan(sb, plan: dict) -> dict:
    stats = {"events": 0, "events_skipped_changed": 0, "field_corrections": 0, "category_corrections": 0}
    for u in plan["events"]["updates"]:
        q = sb.table("events").update(u["patch"]).eq("id", u["id"])
        if u.get("updated_at"):
            q = q.eq("updated_at", u["updated_at"])
        res = q.execute()
        if res.data:
            stats["events"] += 1
        else:
            stats["events_skipped_changed"] += 1
            logger.warning("skipped %s: row changed since the plan was made", u["id"])
    for fc in plan["field_corrections"]:
        sb.table("field_corrections").update({"corrected_value": fc["corrected_value"]}).eq("id", fc["id"]).execute()
        stats["field_corrections"] += 1
    for cc in plan["category_corrections"]:
        sb.table("category_corrections").update(cc["patch"]).eq("id", cc["id"]).execute()
        stats["category_corrections"] += 1
    return stats


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", metavar="PLAN_JSON", help="apply this plan file (production write)")
    ap.add_argument("--deactivate-ids", default="", help="comma-separated event UUIDs to deactivate as well")
    args = ap.parse_args(argv)
    sb = _client()

    if args.apply:
        plan = json.loads(Path(args.apply).read_text(encoding="utf-8"))
        if plan.get("schema") != "retire-event-reports.v1":
            logger.error("not a retire-event-reports plan: %s", args.apply)
            return 2
        stats = apply_plan(sb, plan)
        logger.info("applied: %s", stats)
        return 1 if stats["events_skipped_changed"] else 0

    extra = {x.strip() for x in args.deactivate_ids.split(",") if x.strip()}
    plan = build_plan(sb, extra)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    REPORTS_DIR.mkdir(exist_ok=True)
    plan_path = REPORTS_DIR / f"retire_event_reports_{ts}.json"
    md_path = REPORTS_DIR / f"retire_event_reports_{ts}.md"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    md_path.write_text(render_markdown(plan, ts), encoding="utf-8")
    b = plan["events"]["buckets"]
    logger.info(
        "DRY RUN — deactivate=%d review=%d empty_category=%d tag_only=%d fc=%d cc=%d",
        len(b["deactivate"]), len(b["review"]), len(b["empty_category"]), len(b["tag_only"]),
        len(plan["field_corrections"]), len(plan["category_corrections"]),
    )
    logger.info("plan: %s", plan_path)
    logger.info("review list: %s", md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
