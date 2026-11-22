"""
plan_venue_address_backfill.py — Read-only planner for venue-level address work
(spec venue-ground-truth Phase D, step 4a). Writes nothing to the database.

It answers one question before any migration or write tool is built: how many
upcoming events could actually be fixed, and which data is blocking them.

Categories (all report-only):

  venue_backfill    a non-authoritative venue without an address whose same-name
                    events carry independent evidence for one street address
                    (enrich_addresses.build_sibling_map). Reports how many upcoming
                    events of that name could take the address: no address lock,
                    address still needing a fix.
  stale_auto_locks  events under an authoritative venue whose script lock holds an
                    address other than the venue's (plan-critique-2 B1).
  copy_locks        JSON-quoted script locks: copies or the old web-search fills.
  org_as_venue      venue names that are also the organizer of their events.

The venue_id of a non-authoritative venue comes from fuzzy clustering (#371), so
only events with the same name count, never events under the same venue_id.

Usage:
    python plan_venue_address_backfill.py --output /tmp/backfill.md --json-output /tmp/backfill.json
    python plan_venue_address_backfill.py --events-json e.json --venues-json v.json --locks-json l.json ...
"""

from __future__ import annotations

import argparse
import json
import os
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone

from address_quality import address_key, normalize_address
from audit_venue_addresses import SITE_EVENT_URL, _is_upcoming, _unquote
from enrich_addresses import build_sibling_map, needs_address
from publication_rules import is_pure_publication_record

EVENT_COLUMNS = (
    "id, source_name, location_name, location_address, location_address_zh, location_address_en, "
    "venue_id, event_form, created_at, start_date, end_date, raw_description, organizer, is_active"
)
VENUE_COLUMNS = "id, canonical_name_ja, address, is_authoritative, is_multi_venue"
LOCK_COLUMNS = "event_id, field_name, corrected_value, corrected_by, report_id, created_at"

# Do not build the write path (migration, propagation, apply) unless the backfill
# reaches at least this many upcoming events (plan-critique-2 M3).
MIN_UPCOMING_FOR_PHASE_4B = 4


def _name_key(name: str | None) -> str:
    return unicodedata.normalize("NFKC", name or "").strip()


def plan(events: list[dict], venues: list[dict], locks: list[dict], now: datetime) -> dict:
    """Pure: no I/O."""
    events = [e for e in events if e.get("is_active", True) and not is_pure_publication_record(e)]
    address_locks = {l["event_id"]: l for l in locks if l.get("field_name") == "location_address"}
    script_locks = {
        eid: l for eid, l in address_locks.items() if not l.get("corrected_by") and not l.get("report_id")
    }
    by_name: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        if e.get("location_name"):
            by_name[_name_key(e["location_name"])].append(e)

    # venue_backfill
    stubs = [
        v for v in venues
        if not v.get("is_authoritative") and not v.get("is_multi_venue") and not (v.get("address") or "").strip()
    ]
    authoritative_names: dict[str, str] = {}
    for v in venues:
        if v.get("is_authoritative"):
            for name in [v.get("canonical_name_ja"), *(v.get("aliases") or [])]:
                if _name_key(name):
                    authoritative_names[_name_key(name)] = v["canonical_name_ja"]
    backfill, duplicates = [], []
    for venue in stubs:
        if _name_key(venue.get("canonical_name_ja")) in authoritative_names:
            # A stub named like an authoritative venue is a duplicate (#371), not a
            # venue to give an address of its own.
            duplicates.append({
                "venue_id": venue["id"],
                "canonical_name_ja": venue["canonical_name_ja"],
                "authoritative": authoritative_names[_name_key(venue["canonical_name_ja"])],
            })
            continue
        same_name = by_name.get(_name_key(venue.get("canonical_name_ja")), [])
        if not same_name:
            continue
        consensus = build_sibling_map(
            [{**e, "location_name": venue["canonical_name_ja"]} for e in same_name if e.get("location_address")],
            address_locks,
        ).get(venue["canonical_name_ja"])
        if not consensus:
            continue
        reachable = [
            e for e in same_name
            if _is_upcoming(e, now) and e["id"] not in address_locks and needs_address(e.get("location_address"))
        ]
        backfill.append({
            "venue_id": venue["id"],
            "canonical_name_ja": venue["canonical_name_ja"],
            "address": consensus["location_address"],
            "same_name_events": len(same_name),
            "upcoming_reachable": len(reachable),
            "upcoming_reachable_events": [SITE_EVENT_URL.format(id=e["id"]) for e in reachable],
        })
    backfill.sort(key=lambda b: (-b["upcoming_reachable"], -b["same_name_events"], b["canonical_name_ja"]))

    # stale_auto_locks
    authoritative = {
        v["id"]: v for v in venues
        if v.get("is_authoritative") and not v.get("is_multi_venue") and (v.get("address") or "").strip()
    }
    stale = []
    for e in events:
        venue, lock = authoritative.get(e.get("venue_id")), script_locks.get(e["id"])
        if not venue or not lock:
            continue
        locked = _unquote(lock.get("corrected_value"))
        if locked in ("", "null"):
            continue  # a lock that keeps the address empty is a policy choice, not a stale copy
        if (address_key(locked) or normalize_address(locked)) == (
            address_key(venue["address"]) or normalize_address(venue["address"])
        ):
            continue
        stale.append({
            "event": SITE_EVENT_URL.format(id=e["id"]),
            "venue": venue["canonical_name_ja"],
            "locked": locked,
            "venue_address": venue["address"],
            "upcoming": _is_upcoming(e, now),
        })

    copy_locks = [
        {"event": SITE_EVENT_URL.format(id=eid), "value": _unquote(l.get("corrected_value"))}
        for eid, l in sorted(script_locks.items())
        if (l.get("corrected_value") or "").startswith('"')
    ]

    org_as_venue = sorted({
        e["location_name"] for e in events
        if e.get("organizer") and e.get("location_name")
        and _name_key(e["organizer"]) == _name_key(e["location_name"])
    })

    reachable_total = sum(b["upcoming_reachable"] for b in backfill)
    return {
        "generated_at": now.isoformat(),
        "venue_backfill": backfill,
        "venue_backfill_upcoming_reachable": reachable_total,
        "phase_4b_threshold": MIN_UPCOMING_FOR_PHASE_4B,
        "phase_4b_recommended": reachable_total >= MIN_UPCOMING_FOR_PHASE_4B,
        "duplicate_of_authoritative": duplicates,
        "stale_auto_locks": stale,
        "copy_locks": copy_locks,
        "org_as_venue": org_as_venue,
        "has_raw_text": any(e.get("raw_description") for e in events),
        "has_organizer": any(e.get("organizer") for e in events),
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# 場地層級地址回填：唯讀 planner",
        "",
        f"產生時間：{report['generated_at']}。只列出，不寫入。",
        "",
        "## venue_backfill",
        "",
        f"有獨立證據、可回填的殘樁場館 {len(report['venue_backfill'])} 個；"
        f"能修到的即將舉辦事件合計 {report['venue_backfill_upcoming_reachable']} 筆"
        f"（門檻 {report['phase_4b_threshold']} 筆；"
        f"{'達到，建議做 4b' if report['phase_4b_recommended'] else '未達，不做 4b'}）。",
    ]
    if not report["has_raw_text"]:
        lines.append("輸入沒有原文，「原文逐字出現」的證據沒有計入；實際數字只會更多。")
    if report["venue_backfill"]:
        lines += ["", "| 場館 | 回填地址 | 同名事件 | 能修到的即將舉辦事件 |", "|---|---|---|---|"]
        for b in report["venue_backfill"][:40]:
            lines.append(
                f"| {b['canonical_name_ja']} | {b['address']} | {b['same_name_events']} | {b['upcoming_reachable']} |"
            )
    if report["duplicate_of_authoritative"]:
        lines += [
            "",
            f"另有 {len(report['duplicate_of_authoritative'])} 個殘樁與權威場館同名或同別名，"
            "屬重複場館（#371），不回填：",
        ]
        lines += [
            f"- {d['canonical_name_ja']} → {d['authoritative']}" for d in report["duplicate_of_authoritative"][:20]
        ]
    stale = report["stale_auto_locks"]
    lines += [
        "",
        "## stale_auto_locks",
        "",
        f"掛在權威場館下、腳本鎖的地址與場館現址不同：{len(stale)} 筆"
        f"（即將舉辦 {sum(1 for s in stale if s['upcoming'])} 筆）。解鎖是 production 寫入，需使用者核准。",
    ]
    if stale:
        lines += ["", "| 活動 | 場館 | 鎖的值 | 場館現址 |", "|---|---|---|---|"]
        for s in stale[:40]:
            lines.append(f"| [活動頁]({s['event']}) | {s['venue']} | {s['locked']} | {s['venue_address']} |")
    lines += [
        "",
        "## copy_locks",
        "",
        f"帶 JSON 引號的腳本鎖（同名複製或舊版網搜）：{len(report['copy_locks'])} 筆。",
        "",
        "## org_as_venue",
        "",
    ]
    if report["has_organizer"]:
        lines.append(
            f"場地名與主辦單位相同：{len(report['org_as_venue'])} 個。只列給使用者判斷，不自動改。"
        )
        lines += [f"- {name}" for name in report["org_as_venue"][:40]]
    else:
        lines.append("輸入沒有主辦單位欄位，未計算。")
    lines.append("")
    return "\n".join(lines)


def _load_from_db() -> tuple[list[dict], list[dict], list[dict]]:
    from dotenv import load_dotenv
    from supabase import create_client

    from db_paging import fetch_all

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    events = fetch_all(lambda: (
        sb.table("events").select(EVENT_COLUMNS)
        .eq("is_active", True).is_("merged_into_event_id", None)
        .not_.is_("location_name", None).order("id")
    ))
    venues = fetch_all(lambda: sb.table("venues").select(VENUE_COLUMNS).order("id"))
    locks = fetch_all(lambda: (
        sb.table("field_corrections").select(LOCK_COLUMNS)
        .eq("field_name", "location_address").order("event_id")
    ))
    return events, venues, locks


def _read_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--events-json")
    parser.add_argument("--venues-json")
    parser.add_argument("--locks-json")
    parser.add_argument("--output", help="Markdown report (default: stdout)")
    parser.add_argument("--json-output")
    args = parser.parse_args()

    offline = [args.events_json, args.venues_json, args.locks_json]
    if any(offline) and not all(offline):
        parser.error("--events-json, --venues-json and --locks-json go together")
    if all(offline):
        events, venues, locks = (_read_json(p) for p in offline)
    else:
        events, venues, locks = _load_from_db()

    report = plan(events, venues, locks, datetime.now(timezone.utc))
    markdown = render_markdown(report)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(markdown)
    else:
        print(markdown)
    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
