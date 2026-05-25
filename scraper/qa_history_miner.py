"""
qa_history_miner.py — Mine 90-day event_reports + field_corrections_audit
history to seed `.github/skills/scraper-expert/cases.jsonl` with R-class
exemplars and detector statistics.

Output schema (JSONL, one object per row):
{
  "r_class": "R-SCR-PERF-MULTI",
  "report_type": "auto_qa_performer_multi_value_pollution",
  "first_seen": "2026-05-12T...",
  "last_seen": "2026-05-25T...",
  "total_seen": 14,                  # all reports of this type within window
  "evidence_statuses": {              # split by resolution
      "confirmed": 11,
      "dismissed": 2,
      "pending": 1
  },
  "confidence_basis": "11 confirmed / 2 dismissed in last 90d",
  "example_admin_notes": ["…", "…"],   # up to 5 confirmed
  "false_positive_notes": ["…"]        # up to 3 dismissed (anti-examples)
}

Dismissed reports are kept SEPARATELY — they are evidence the detector
fired on a false positive and must not be learned as a confirmed
root-cause example.

Usage:
    python qa_history_miner.py --dry-run
    python qa_history_miner.py            # writes cases.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

load_dotenv(dotenv_path=SCRIPT_DIR / ".env")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OUT_PATH = REPO_ROOT / ".github" / "skills" / "scraper-expert" / "cases.jsonl"

# Heuristic mapping report_type → R-class (mirrors qa_heartbeat.ROUTING semantics).
REPORT_TYPE_TO_R_CLASS: dict[str, str] = {
    "auto_qa_simplified_zh": "R-ANN-SC",
    "auto_simplified_chinese": "R-ANN-SC",
    "auto_qa_performer_ai_translation_marker": "R-ANN-AI-MARKER",
    "auto_qa_performer_multi_value_pollution": "R-SCR-PERF-MULTI",
    "auto_qa_performer_zh_equals_katakana": "R-ENRICH-MISS",
    "auto_qa_missing_address": "R-SCR-ADDR-MISS",
    "auto_qa_missing_hours": "R-SCR-HOURS-MISS",
    "auto_qa_same_work_duplicate": "R-MERGE-WORK-DUP",
}


def _supabase_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _fetch_reports(sb, since_iso: str) -> list[dict]:
    """Pull all auto_qa reports created in the window. Paged via .range()."""
    rows: list[dict] = []
    batch = 1000
    start = 0
    while True:
        res = (
            sb.table("event_reports")
            .select("id,event_id,report_types,status,admin_notes,created_at,confirmed_at")
            .gte("created_at", since_iso)
            .order("created_at", desc=False)
            .range(start, start + batch - 1)
            .execute()
        )
        page = res.data or []
        rows.extend(page)
        if len(page) < batch:
            break
        start += batch
    return rows


def mine(window_days: int = 90, dry_run: bool = False) -> dict:
    sb = _supabase_client()
    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    logger.info("Mining event_reports since %s", since)

    reports = _fetch_reports(sb, since)
    logger.info("Fetched %d reports in last %d days", len(reports), window_days)

    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in reports:
        for t in r.get("report_types") or []:
            if not t.startswith("auto_"):
                continue
            by_type[t].append(r)

    cases: list[dict] = []
    for report_type, group in sorted(by_type.items()):
        r_class = REPORT_TYPE_TO_R_CLASS.get(report_type, "R-UNCLASSIFIED")
        statuses: dict[str, int] = {"confirmed": 0, "dismissed": 0, "pending": 0, "other": 0}
        confirmed_notes: list[str] = []
        dismissed_notes: list[str] = []
        first_seen: str | None = None
        last_seen: str | None = None
        for r in group:
            st = r.get("status") or "other"
            statuses[st if st in statuses else "other"] += 1
            ts = r.get("created_at")
            if ts:
                first_seen = ts if first_seen is None or ts < first_seen else first_seen
                last_seen = ts if last_seen is None or ts > last_seen else last_seen
            note = (r.get("admin_notes") or "").strip()
            if not note:
                continue
            if st == "confirmed" and len(confirmed_notes) < 5:
                confirmed_notes.append(note[:240])
            elif st == "dismissed" and len(dismissed_notes) < 3:
                dismissed_notes.append(note[:240])

        confidence_basis = (
            f"{statuses['confirmed']} confirmed / "
            f"{statuses['dismissed']} dismissed / "
            f"{statuses['pending']} pending in last {window_days}d"
        )

        cases.append({
            "r_class": r_class,
            "report_type": report_type,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "total_seen": len(group),
            "evidence_statuses": statuses,
            "confidence_basis": confidence_basis,
            "example_admin_notes": confirmed_notes,
            "false_positive_notes": dismissed_notes,
        })

    cases.sort(key=lambda c: c["total_seen"], reverse=True)

    if dry_run:
        for c in cases:
            logger.info(
                "  %s (%s) total=%d %s",
                c["r_class"], c["report_type"], c["total_seen"], c["confidence_basis"],
            )
        return {"cases": len(cases), "written": False}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    logger.info("Wrote %d cases → %s", len(cases), OUT_PATH)
    return {"cases": len(cases), "written": True, "path": str(OUT_PATH)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine QA history → cases.jsonl")
    parser.add_argument("--window-days", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    mine(window_days=args.window_days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
