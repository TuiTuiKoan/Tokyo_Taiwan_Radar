"""
auto_qa.py — Automated translation & address quality checks.

Scans recent events and inserts pending rows into `event_reports` so that
admins can review/fix anomalies via /admin/reports.

Detectors:
  1. auto_qa_simplified_zh   — Simplified Chinese chars in any *_zh field
                               (name_zh, description_zh, location_name_zh,
                                location_address_zh)
  2. auto_qa_missing_address — Has location_name but location_address is empty
                               (skips online / TV / pure-katakana venues)

Dedup: skips events that already have a pending event_report of the same
auto_qa type (no spam re-creation across runs).

Scope: only events with is_active=true and created_at within the last
QA_WINDOW_DAYS (default 14) — keeps the run cheap and focused on fresh data.

Usage:
    python auto_qa.py            # live run
    python auto_qa.py --dry-run  # report, no writes
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

QA_WINDOW_DAYS = 14

# Matches the char list maintained in copilot-instructions Step 5,
# extended with chars seen in real anomaly samples. Only chars that are
# unambiguously simplified-only (NOT valid in Traditional Chinese or
# Japanese) belong here, to avoid false positives.
SIMP_RE = re.compile(
    r"[东来这发会说时问门关对长进现与实变内还单层达诺厅络设联馆园乐欢艺师"
    r"丰个为产业亲见开闭难纪员体让历观书写报场属层听处声证识请赞动务区团圆"
    r"岛带帮当录张归态总职护扩续齐奖]"
)

ZH_FIELDS = ("name_zh", "description_zh", "location_name_zh", "location_address_zh")

ADDRESS_SKIP_KEYWORDS = (
    "オンライン", "online", "Online",
    "電視", "テレビ", "tv", "TV",
    "Zoom", "zoom", "YouTube", "youtube",
    "配信", "ライブ配信",
)

QA_TYPES = ("auto_qa_simplified_zh", "auto_qa_missing_address")


def _supabase_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)


def _has_simplified(text: str | None) -> bool:
    if not text:
        return False
    return bool(SIMP_RE.search(text))


def _is_online_or_tv(name: str | None) -> bool:
    if not name:
        return False
    return any(kw in name for kw in ADDRESS_SKIP_KEYWORDS)


def _existing_pending_types(sb, event_ids: list[str]) -> dict[str, set[str]]:
    """Map event_id → set of auto_qa report_types that already have a pending row."""
    if not event_ids:
        return {}
    out: dict[str, set[str]] = {}
    # Supabase JS-py: chunk to avoid 1000-row in() limit
    for i in range(0, len(event_ids), 200):
        chunk = event_ids[i : i + 200]
        res = (
            sb.table("event_reports")
            .select("event_id, report_types, status")
            .in_("event_id", chunk)
            .eq("status", "pending")
            .execute()
        )
        for row in res.data or []:
            existing = out.setdefault(row["event_id"], set())
            for t in row.get("report_types") or []:
                if t in QA_TYPES:
                    existing.add(t)
    return out


def detect(event: dict) -> list[tuple[str, str]]:
    """Return list of (report_type, admin_note) detected for one event."""
    findings: list[tuple[str, str]] = []

    # 1. Simplified Chinese in any *_zh field
    bad_fields = [f for f in ZH_FIELDS if _has_simplified(event.get(f))]
    if bad_fields:
        sample = next((event[f] for f in bad_fields if event.get(f)), "")
        findings.append((
            "auto_qa_simplified_zh",
            f"簡體字偵測 fields={','.join(bad_fields)} sample={sample[:80]}",
        ))

    # 2. Has location_name but no location_address (skip online / TV)
    loc_name = event.get("location_name") or ""
    loc_addr = event.get("location_address") or ""
    if (
        loc_name.strip()
        and not loc_addr.strip()
        and not _is_online_or_tv(loc_name)
        and event.get("source_name") != "gguide_tv"
    ):
        findings.append((
            "auto_qa_missing_address",
            f"地址缺失 venue={loc_name[:80]}",
        ))

    return findings


def run(dry_run: bool = False) -> dict:
    sb = _supabase_client()
    since = (datetime.now(timezone.utc) - timedelta(days=QA_WINDOW_DAYS)).isoformat()

    res = (
        sb.table("events")
        .select(
            "id, source_name, name_zh, description_zh, "
            "location_name, location_name_zh, location_address, location_address_zh"
        )
        .eq("is_active", True)
        .gte("created_at", since)
        .execute()
    )
    events = res.data or []
    logger.info("Scanning %d events (last %d days)", len(events), QA_WINDOW_DAYS)

    # Build candidate findings
    candidates: list[tuple[str, str, str]] = []  # (event_id, type, note)
    for ev in events:
        for t, note in detect(ev):
            candidates.append((ev["id"], t, note))

    # Dedup against existing pending auto_qa reports
    existing = _existing_pending_types(sb, list({c[0] for c in candidates}))
    new_rows: list[dict] = []
    skipped = 0
    for event_id, t, note in candidates:
        if t in existing.get(event_id, set()):
            skipped += 1
            continue
        new_rows.append({
            "event_id": event_id,
            "report_types": [t],
            "status": "pending",
            "admin_notes": note,
        })
        # Track in-memory so a second finding of same type/event in this run is also skipped
        existing.setdefault(event_id, set()).add(t)

    counts: dict[str, int] = {t: 0 for t in QA_TYPES}
    for r in new_rows:
        counts[r["report_types"][0]] = counts.get(r["report_types"][0], 0) + 1

    summary = {
        "scanned": len(events),
        "candidates": len(candidates),
        "skipped_existing": skipped,
        "inserted": len(new_rows),
        "by_type": counts,
    }

    if dry_run:
        logger.info("DRY RUN summary: %s", summary)
        for r in new_rows[:20]:
            logger.info("  + %s %s — %s", r["event_id"][:8], r["report_types"][0], r["admin_notes"])
        return summary

    if new_rows:
        # Insert in chunks of 100 to keep payloads small
        for i in range(0, len(new_rows), 100):
            sb.table("event_reports").insert(new_rows[i : i + 100]).execute()
    logger.info("auto_qa summary: %s", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
