#!/usr/bin/env python3
"""Detect events with multilingual field sync mismatches.

Checks for events where edits to the Japanese version of multilingual fields
(name, location_name, location_address, organizer) were not reflected in Chinese/English versions.

Heuristics:
1) subtitle_marker_mismatch: raw/ja has no separators, but zh/en still have them
2) field_edited_without_translation: ja_fc exists but zh_en_fc missing (newer_than)
3) length_mismatch: ja is much shorter than zh/en (suggests shortening without resync)

Exit codes:
- 0: no findings, or findings without --fail-on-findings
- 1: findings exist and --fail-on-findings is set
- 2: configuration error
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Iterable

from dotenv import load_dotenv
from supabase import create_client

SEP_RE = re.compile(r"[~〜―—]|\\s[-–—]\\s")
STRIP_RE = re.compile(r"[「」『』【】（）()\[\]\s]")

MULTILINGUAL_FIELDS = [
    ("name", "raw_title"),           # (base_field_name, raw_source_for_marker_check)
    ("location_name", None),
    ("location_address", None),
    ("organizer", None),
]


@dataclass
class FieldMismatch:
    field_name: str
    reasons: list[str]
    value_ja: str
    value_zh: str
    value_en: str


@dataclass
class Finding:
    event_id: str
    source_name: str
    annotation_status: str | None
    updated_at: str | None
    mismatches: list[FieldMismatch]
    source_url: str | None


def _norm(text: str | None) -> str:
    if not text:
        return ""
    return STRIP_RE.sub("", text)


def _has_sep(text: str | None) -> bool:
    return bool(text and SEP_RE.search(text))


def _iso_hours_ago(hours: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dt.isoformat()


def _to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _latest_dt(rows: Iterable[dict], field: str) -> datetime | None:
    vals = [_to_dt(r.get("created_at")) for r in rows if r.get("field_name") == field]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def _check_field_mismatch(
    field_name: str,
    ja: str,
    zh: str,
    en: str,
    raw_source: str | None,
    fc_rows: list[dict],
) -> FieldMismatch | None:
    """Check if a multilingual field has sync issues."""
    
    reasons: list[str] = []

    # Skip if zh or en missing
    if not zh or not en:
        return None

    # Heuristic 1: Subtitle marker mismatch
    # Raw has markers but ja doesn't, yet zh/en still do
    if raw_source and ja:
        if _has_sep(raw_source) and not _has_sep(ja) and (_has_sep(zh) or _has_sep(en)):
            reasons.append("subtitle_marker_mismatch")

    # Heuristic 2: Length mismatch
    # JA is much shorter than zh/en (suggests shortening without translation sync)
    if ja and zh and en:
        ja_len = len(_norm(ja))
        zh_len = len(_norm(zh))
        en_len = len(_norm(en))
        
        if (
            raw_source
            and _has_sep(raw_source)
            and (_has_sep(zh) or _has_sep(en))
            and len(_norm(raw_source)) >= 12
            and ja_len <= int(len(_norm(raw_source)) * 0.75)
            and (zh_len >= ja_len + 6 or en_len >= ja_len + 6)
        ):
            reasons.append("length_mismatch_ja_short")

    # Heuristic 3: Field-correction drift
    # Check if ja was corrected but zh/en weren't
    if fc_rows:
        ja_latest = _latest_dt(fc_rows, f"{field_name}_ja")
        zh_latest = _latest_dt(fc_rows, f"{field_name}_zh")
        en_latest = _latest_dt(fc_rows, f"{field_name}_en")

        if ja_latest and not zh_latest and not en_latest:
            reasons.append(f"{field_name}_ja_edited_without_zh_en")
        elif ja_latest and (
            (zh_latest and ja_latest > zh_latest) or (en_latest and ja_latest > en_latest)
        ):
            reasons.append(f"{field_name}_ja_edited_more_recently")

    if reasons:
        return FieldMismatch(
            field_name=field_name,
            reasons=sorted(set(reasons)),
            value_ja=ja,
            value_zh=zh,
            value_en=en,
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check multilingual field sync mismatches")
    parser.add_argument("--since-hours", type=int, default=36, help="Lookback window in hours")
    parser.add_argument("--limit", type=int, default=500, help="Max findings to print")
    parser.add_argument("--event-id", default="", help="Check only one event ID")
    parser.add_argument("--output-json", default="", help="Write findings to JSON file")
    parser.add_argument("--fail-on-findings", action="store_true", help="Exit 1 when findings exist")
    args = parser.parse_args()

    load_dotenv(".env")
    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing", file=sys.stderr)
        return 2

    sb = create_client(supabase_url, service_key)
    since_iso = _iso_hours_ago(args.since_hours)

    # Query events with all multilingual fields
    q = sb.table("events").select(
        "id,source_name,source_url,"
        "raw_title,"
        "name_ja,name_zh,name_en,"
        "location_name,location_name_zh,location_name_en,"
        "location_address,location_address_zh,location_address_en,"
        "organizer,organizer_zh,organizer_en,"
        "annotation_status,updated_at,is_active"
    ).eq("is_active", True)

    if args.event_id:
        q = q.eq("id", args.event_id)
    else:
        q = q.gte("updated_at", since_iso)

    events = q.execute().data or []

    # Fetch all field_corrections for these events
    event_ids = [e["id"] for e in events]
    all_fc: dict[str, list[dict]] = {}
    if event_ids:
        try:
            fc_data = (
                sb.table("field_corrections")
                .select("event_id,field_name,created_at")
                .in_("event_id", event_ids)
                .execute()
                .data
                or []
            )
            for row in fc_data:
                eid = row["event_id"]
                if eid not in all_fc:
                    all_fc[eid] = []
                all_fc[eid].append(row)
        except Exception:
            pass

    findings: list[Finding] = []

    for e in events:
        eid = e["id"]
        fc_rows = all_fc.get(eid, [])
        mismatches: list[FieldMismatch] = []

        for field_name, raw_field in MULTILINGUAL_FIELDS:
            ja_key = field_name if field_name == "name" else field_name
            zh_key = f"{field_name}_zh"
            en_key = f"{field_name}_en"

            ja = (e.get(ja_key) or "").strip()
            zh = (e.get(zh_key) or "").strip()
            en = (e.get(en_key) or "").strip()
            raw_source = (e.get(raw_field) or "").strip() if raw_field else None

            mismatch = _check_field_mismatch(field_name, ja, zh, en, raw_source, fc_rows)
            if mismatch:
                mismatches.append(mismatch)

        if mismatches:
            findings.append(
                Finding(
                    event_id=eid,
                    source_name=e.get("source_name") or "",
                    annotation_status=e.get("annotation_status"),
                    updated_at=e.get("updated_at"),
                    mismatches=mismatches,
                    source_url=e.get("source_url"),
                )
            )

    findings.sort(key=lambda x: (x.updated_at or ""), reverse=True)

    print(f"window_since: {since_iso}")
    print(f"events_scanned: {len(events)}")
    print(f"findings: {len(findings)}")

    for i, f in enumerate(findings[: args.limit], start=1):
        print(f"\n[{i}] {f.event_id} | {f.source_name} | {f.annotation_status} | {f.updated_at}")
        for mm in f.mismatches:
            print(f"  field: {mm.field_name}")
            print(f"    reasons: {', '.join(mm.reasons)}")
            print(f"    ja: {mm.value_ja[:100]}")
            print(f"    zh: {mm.value_zh[:100]}")
            print(f"    en: {mm.value_en[:100]}")

    if args.output_json:
        os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as wf:
            # Convert to dict for JSON serialization
            data = [
                {
                    **{k: v for k, v in asdict(f).items() if k != "mismatches"},
                    "mismatches": [asdict(mm) for mm in f.mismatches],
                }
                for f in findings
            ]
            json.dump(data, wf, ensure_ascii=False, indent=2)
        print(f"\njson_written: {args.output_json}")

    if findings and args.fail_on_findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
