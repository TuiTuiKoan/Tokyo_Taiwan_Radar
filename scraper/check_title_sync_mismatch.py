#!/usr/bin/env python3
"""Detect events where name_ja was shortened but name_zh/name_en still reflect the old title.

This script is intentionally heuristic and outputs candidates for manual review.

Checks include:
1) subtitle marker mismatch:
   raw_title has subtitle markers, name_ja does not, but name_zh/name_en still do.
2) field_corrections drift:
   name_ja correction exists without matching name_zh/name_en corrections.

Exit code:
- 0: no findings, or findings exist but --fail-on-findings is not set
- 1: findings exist and --fail-on-findings is set
- 2: runtime/config error
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


@dataclass
class Finding:
    event_id: str
    source_name: str
    annotation_status: str | None
    updated_at: str | None
    reasons: list[str]
    raw_title: str
    name_ja: str
    name_zh: str
    name_en: str
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check title sync mismatch candidates")
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

    q = sb.table("events").select(
        "id,source_name,source_url,raw_title,name_ja,name_zh,name_en,annotation_status,updated_at,is_active"
    ).eq("is_active", True)

    if args.event_id:
        q = q.eq("id", args.event_id)
    else:
        q = q.gte("updated_at", since_iso)

    events = q.execute().data or []

    findings: list[Finding] = []

    for e in events:
        raw = (e.get("raw_title") or "").strip()
        ja = (e.get("name_ja") or "").strip()
        zh = (e.get("name_zh") or "").strip()
        en = (e.get("name_en") or "").strip()

        # If zh/en are missing entirely, this is a different class of issue.
        if not zh or not en:
            continue

        reasons: list[str] = []

        if raw and ja and _norm(raw) != _norm(ja):
            if _has_sep(raw) and (not _has_sep(ja)) and (_has_sep(zh) or _has_sep(en)):
                reasons.append("subtitle_marker_mismatch")

            # Length-based signal: JA got much shorter while zh/en look long.
            raw_len = len(_norm(raw))
            ja_len = len(_norm(ja))
            zh_len = len(_norm(zh))
            en_len = len(_norm(en))
            if (
                _has_sep(raw)
                and (_has_sep(zh) or _has_sep(en))
                and raw_len >= 12
                and ja_len <= int(raw_len * 0.75)
                and (zh_len >= ja_len + 6 or en_len >= ja_len + 6)
            ):
                reasons.append("title_shortened_without_zh_en_resync")

        # Field-correction drift check for edited titles.
        try:
            fc_rows = (
                sb.table("field_corrections")
                .select("field_name,created_at")
                .eq("event_id", e["id"])
                .in_("field_name", ["name_ja", "name_zh", "name_en"])
                .execute()
                .data
                or []
            )
        except Exception:
            fc_rows = []

        if fc_rows:
            ja_latest = _latest_dt(fc_rows, "name_ja")
            zh_latest = _latest_dt(fc_rows, "name_zh")
            en_latest = _latest_dt(fc_rows, "name_en")

            if ja_latest and not zh_latest and not en_latest:
                reasons.append("name_ja_fc_without_name_zh_en_fc")
            elif ja_latest and ((zh_latest and ja_latest > zh_latest) or (en_latest and ja_latest > en_latest)):
                reasons.append("name_ja_fc_newer_than_name_zh_en_fc")

        if reasons:
            findings.append(
                Finding(
                    event_id=e["id"],
                    source_name=e.get("source_name") or "",
                    annotation_status=e.get("annotation_status"),
                    updated_at=e.get("updated_at"),
                    reasons=sorted(set(reasons)),
                    raw_title=raw,
                    name_ja=ja,
                    name_zh=zh,
                    name_en=en,
                    source_url=e.get("source_url"),
                )
            )

    findings.sort(key=lambda x: (x.updated_at or ""), reverse=True)

    print(f"window_since: {since_iso}")
    print(f"events_scanned: {len(events)}")
    print(f"findings: {len(findings)}")

    for i, f in enumerate(findings[: args.limit], start=1):
        print(f"\n[{i}] {f.event_id} | {f.source_name} | {f.annotation_status} | {f.updated_at}")
        print("  reasons:", ", ".join(f.reasons))
        print("  raw:", f.raw_title[:160])
        print("  ja :", f.name_ja[:160])
        print("  zh :", f.name_zh[:160])
        print("  en :", f.name_en[:160])

    if args.output_json:
        os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as wf:
            json.dump([asdict(x) for x in findings], wf, ensure_ascii=False, indent=2)
        print(f"\njson_written: {args.output_json}")

    if findings and args.fail_on_findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
