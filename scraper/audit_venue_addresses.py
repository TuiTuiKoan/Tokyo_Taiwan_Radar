"""
audit_venue_addresses.py — Read-only report on how many events name a venue but
lack a street-level address, counted per source and per venue name.

Spec: docs/specs/active/venue-ground-truth/ (Phase A). Does NOT write to the database.

Usage:
    python audit_venue_addresses.py --output /tmp/venue_addresses.md
    python audit_venue_addresses.py --json-output /tmp/venue_addresses.json
    python audit_venue_addresses.py --events-json events.json --venues-json venues.json [--locks-json locks.json]
    python audit_venue_addresses.py --sample-output /tmp/sample.md   # for the human spot check

With --events-json / --venues-json the script reads exported rows instead of the
database, so it runs without credentials. The rows need the columns listed in
EVENT_COLUMNS and VENUE_COLUMNS.

Scope. An event is counted when it is active, not merged away, and names a venue.
Three groups are then reported apart, using the same predicates as auto_qa.py so the
numbers line up with the QA reports:

    in_scope      a physical venue is expected
    qa_excluded   sources auto_qa skips for venue QA (news, blog, TV feeds)
    no_venue      pure publications, and venue names that say online or TV

The registry section lists venues that could take an address from their events. That
list is an upper bound for spec Phase D, not a write plan: one event is enough to
appear in it, and it does not check where the event's address came from.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from address_quality import GRADES, NEEDS_FIX, NON_JAPAN, STREET, address_key, grade_address, normalize_address
from auto_qa import _NO_VENUE_QA_SOURCES, _is_online_or_tv
from enrich_addresses import is_vague
from publication_rules import is_pure_publication_record

EVENT_COLUMNS = (
    "id, source_name, location_name, location_address, venue_id, event_form, "
    "created_at, start_date, end_date"
)
VENUE_COLUMNS = "id, canonical_name_ja, address, is_authoritative, is_multi_venue"
LOCK_COLUMNS = "event_id, field_name, corrected_value, corrected_by, report_id, created_at"

IN_SCOPE = "in_scope"
QA_EXCLUDED = "qa_excluded"
NO_VENUE = "no_venue"

RECENT_DAYS = 60
SAMPLE_PER_GRADE = 30
SITE_EVENT_URL = "https://tokyotaiwanradar.com/ja/events/{id}"


def scope_of(event: dict) -> str:
    name = event.get("location_name") or ""
    if is_pure_publication_record(event) or _is_online_or_tv(name):
        return NO_VENUE
    if event.get("source_name") in _NO_VENUE_QA_SOURCES:
        return NO_VENUE if event.get("source_name") == "gguide_tv" else QA_EXCLUDED
    return IN_SCOPE


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _is_upcoming(event: dict, now: datetime) -> bool:
    last_day = _parse_ts(event.get("end_date")) or _parse_ts(event.get("start_date"))
    return bool(last_day and last_day >= now)


def _is_recent(event: dict, now: datetime) -> bool:
    created = _parse_ts(event.get("created_at"))
    return bool(created and created >= now - timedelta(days=RECENT_DAYS))


def _rate(street: int, total: int) -> float | None:
    return round(street / total, 4) if total else None


def _grade_counts(rows: list[dict]) -> dict:
    counts = Counter(r["_grade"] for r in rows)
    # Addresses outside Japan are not graded, so they stay out of the rate.
    gradable = len(rows) - counts.get(NON_JAPAN, 0)
    return {
        "total": len(rows),
        "grades": {g: counts.get(g, 0) for g in GRADES},
        "needs_fix": sum(counts.get(g, 0) for g in NEEDS_FIX),
        "street_rate": _rate(counts.get(STREET, 0), gradable),
    }


def _grade_samples(rows: list[dict]) -> dict[str, list[str]]:
    """Up to SAMPLE_PER_GRADE distinct addresses per grade, for a human spot check.

    The order is a hash of the address, so the sample is stable between runs and is
    not biased toward the most common or the alphabetically first values.
    """
    by_grade: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        address = (r.get("location_address") or "").strip()
        if address:
            by_grade[r["_grade"]].add(address)
    return {
        grade: sorted(values, key=lambda a: hashlib.sha256(a.encode("utf-8")).hexdigest())[:SAMPLE_PER_GRADE]
        for grade, values in sorted(by_grade.items())
    }


def _unquote(value: str | None) -> str:
    text = (value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        try:
            return str(json.loads(text))
        except ValueError:
            return text[1:-1]
    return text


def _lock_report(rows: list[dict], venues: list[dict], locks: list[dict] | None, now: datetime) -> dict | None:
    """Counts about field_corrections locks on location_address (plan-critique-2 B1, M2, M10)."""
    if locks is None:
        return None
    address_locks = {l["event_id"]: l for l in locks if l.get("field_name") == "location_address"}
    script = {eid: l for eid, l in address_locks.items() if not l.get("corrected_by") and not l.get("report_id")}
    authoritative = {
        v["id"]: v for v in venues
        if v.get("is_authoritative") and not v.get("is_multi_venue") and (v.get("address") or "").strip()
    }
    differs, differs_upcoming = [], 0
    for r in rows:
        venue, lock = authoritative.get(r.get("venue_id")), script.get(r["id"])
        if not venue or not lock:
            continue
        locked, current = _unquote(lock.get("corrected_value")), venue["address"]
        same = (address_key(locked) or normalize_address(locked)) == (address_key(current) or normalize_address(current))
        if not same:
            differs.append(SITE_EVENT_URL.format(id=r["id"]))
            differs_upcoming += r["_upcoming"]
    new_candidates = [
        r for r in rows
        if r["_scope"] != NO_VENUE and r["_upcoming"] and r["_grade"] in NEEDS_FIX
        and not is_vague(r.get("location_address"))
    ]
    mismatch = [
        r for r in rows
        if not (r.get("location_address") or "").strip()
        and _unquote(address_locks.get(r["id"], {}).get("corrected_value")) not in ("", "null")
    ]
    return {
        "quoted_event_addresses": sum(
            1 for r in rows if (r.get("location_address") or "").strip().startswith('"')
        ),
        "quoted_address_locks": sum(
            1 for l in address_locks.values() if (l.get("corrected_value") or "").startswith('"')
        ),
        "authoritative_lock_differs": len(differs),
        "authoritative_lock_differs_upcoming": differs_upcoming,
        "authoritative_lock_differs_examples": differs[:10],
        "event_blank_but_locked": len(mismatch),
        "enrich_new_candidates": len(new_candidates),
        "enrich_new_candidates_locked": sum(1 for r in new_candidates if r["id"] in address_locks),
    }


def audit(
    events: list[dict], venues: list[dict], now: datetime, locks: list[dict] | None = None,
) -> dict:
    """Return the full report as a plain dict. Pure: no I/O.

    `locks` is optional: the field_corrections rows of the events (LOCK_COLUMNS).
    """
    rows = []
    for event in events:
        name = (event.get("location_name") or "").strip()
        if not name:
            continue
        rows.append({
            **event,
            "_name": name,
            "_scope": scope_of(event),
            "_grade": grade_address(event.get("location_address"), name),
            "_upcoming": _is_upcoming(event, now),
            "_recent": _is_recent(event, now),
        })

    in_scope = [r for r in rows if r["_scope"] == IN_SCOPE]
    qa_excluded = [r for r in rows if r["_scope"] == QA_EXCLUDED]

    by_source: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["_scope"] != NO_VENUE:
            by_source[r["source_name"]].append(r)
    sources = sorted(
        (
            {
                "source": source,
                "scope": items[0]["_scope"],
                "missing": sum(1 for r in items if r["_grade"] in NEEDS_FIX),
                **_grade_counts(items),
            }
            for source, items in by_source.items()
        ),
        key=lambda s: (-s["missing"], s["source"]),
    )

    # One row per venue name: fixing the venue fixes every event under it.
    by_name: dict[str, list[dict]] = defaultdict(list)
    for r in in_scope:
        by_name[r["_name"]].append(r)
    venue_gaps = []
    for name, items in by_name.items():
        missing = [r for r in items if r["_grade"] in NEEDS_FIX]
        if not missing:
            continue
        street_addresses = sorted({
            normalize_address(r["location_address"]) for r in items if r["_grade"] == STREET
        })
        venue_gaps.append({
            "location_name": name,
            "missing_events": len(missing),
            "upcoming_missing": sum(1 for r in missing if r["_upcoming"]),
            "total_events": len(items),
            "grades": dict(Counter(r["_grade"] for r in missing)),
            "sibling_street_addresses": street_addresses,
            "example_event": SITE_EVENT_URL.format(id=missing[0]["id"]),
        })
    venue_gaps.sort(key=lambda v: (-v["upcoming_missing"], -v["missing_events"], v["location_name"]))

    # Registry venues with no address whose linked events already agree on one.
    by_venue_id: dict[str, list[dict]] = defaultdict(list)
    for r in in_scope:
        if r.get("venue_id"):
            by_venue_id[r["venue_id"]].append(r)
    backfill, conflicts, no_evidence = [], [], 0
    for venue in venues:
        if (venue.get("address") or "").strip() or venue.get("is_multi_venue"):
            continue
        linked = by_venue_id.get(venue["id"], [])
        addresses = Counter(
            normalize_address(r["location_address"]) for r in linked if r["_grade"] == STREET
        )
        entry = {
            "venue_id": venue["id"],
            "canonical_name_ja": venue.get("canonical_name_ja"),
            "is_authoritative": bool(venue.get("is_authoritative")),
            "linked_events": len(linked),
            "addresses": dict(addresses),
        }
        if len(addresses) == 1:
            backfill.append(entry)
        elif len(addresses) > 1:
            conflicts.append(entry)
        else:
            no_evidence += 1
    backfill.sort(key=lambda v: (-v["linked_events"], v["canonical_name_ja"] or ""))
    conflicts.sort(key=lambda v: (-v["linked_events"], v["canonical_name_ja"] or ""))

    return {
        "generated_at": now.isoformat(),
        "scopes": dict(Counter(r["_scope"] for r in rows)),
        "in_scope": {
            "all": _grade_counts(in_scope),
            "upcoming": _grade_counts([r for r in in_scope if r["_upcoming"]]),
            f"created_last_{RECENT_DAYS}_days": _grade_counts([r for r in in_scope if r["_recent"]]),
            "without_venue_id": sum(1 for r in in_scope if not r.get("venue_id")),
        },
        # Whether the sources auto_qa skips should need an address is the owner's call;
        # both denominators are reported so the target can be set either way.
        "qa_excluded": _grade_counts(qa_excluded),
        "in_scope_plus_qa_excluded": _grade_counts(in_scope + qa_excluded),
        # The owner chose this combined population as the target (2026-11-22, issue #708).
        "in_scope_plus_qa_excluded_upcoming": _grade_counts(
            [r for r in in_scope + qa_excluded if r["_upcoming"]]
        ),
        f"in_scope_plus_qa_excluded_created_last_{RECENT_DAYS}_days": _grade_counts(
            [r for r in in_scope + qa_excluded if r["_recent"]]
        ),
        # Events enrich_addresses.is_vague() calls specific but the grader does not:
        # the candidates added if enrich_addresses switches to the grader (Phase B).
        "not_vague_but_needs_fix": sum(
            1 for r in in_scope
            if r["_grade"] in NEEDS_FIX and not is_vague(r.get("location_address"))
        ),
        # Venue name says online or TV, yet the event carries a street address: hybrid
        # events that today's keyword rule drops from venue QA (issue #364).
        "online_named_with_street_address": sum(
            1 for r in rows
            if r["_grade"] == STREET and _is_online_or_tv(r["_name"])
            and not is_pure_publication_record(r)
        ),
        "grade_samples": _grade_samples(in_scope + qa_excluded),
        "locks": _lock_report(rows, venues, locks, now),
        "sources": sources,
        "venue_gaps": venue_gaps,
        "registry": {
            "venues": len(venues),
            "authoritative": sum(1 for v in venues if v.get("is_authoritative")),
            "without_address": sum(
                1 for v in venues
                if not (v.get("address") or "").strip() and not v.get("is_multi_venue")
            ),
            "authoritative_without_address": [
                {"canonical_name_ja": v.get("canonical_name_ja"), "is_multi_venue": bool(v.get("is_multi_venue"))}
                for v in venues
                if v.get("is_authoritative") and not (v.get("address") or "").strip()
            ],
            "backfill_candidates": backfill,
            "backfill_conflicts": conflicts,
            "without_address_and_without_evidence": no_evidence,
        },
    }


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def render_markdown(report: dict, top: int = 40) -> str:
    lines = [
        "# 場地地址稽核",
        "",
        f"產生時間：{report['generated_at']}。唯讀；等級定義見 `scraper/address_quality.py`。",
        "",
        "## 應有實體場地的事件",
        "",
        "| 母體 | 事件 | 街道級 | 待補 | 街道級比率 | 町名 | 僅行政區 | 空白 | 非地址 | 日本以外 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    blocks = [
        ("全部", report["in_scope"]["all"]),
        ("即將舉辦", report["in_scope"]["upcoming"]),
        (f"近 {RECENT_DAYS} 天新進", report["in_scope"][f"created_last_{RECENT_DAYS}_days"]),
        ("auto_qa 排除場地 QA 的來源", report["qa_excluded"]),
        ("全部＋上列排除來源", report["in_scope_plus_qa_excluded"]),
        ("即將舉辦＋排除來源", report["in_scope_plus_qa_excluded_upcoming"]),
        (f"近 {RECENT_DAYS} 天新進＋排除來源", report[f"in_scope_plus_qa_excluded_created_last_{RECENT_DAYS}_days"]),
    ]
    for label, block in blocks:
        g = block["grades"]
        lines.append(
            f"| {label} | {block['total']} | {g['street']} | "
            f"{block['needs_fix']} | {_pct(block['street_rate'])} | {g['town']} | {g['region']} | "
            f"{g['empty']} | {g['not_address']} | {g['non_japan']} |"
        )
    scopes = report["scopes"]
    lines += [
        "",
        "街道級比率的分母不含日本以外的地址（在台灣舉辦的活動屬於收錄範圍，本量尺不評其地址）。",
        "",
        f"- `venue_id` 為空：{report['in_scope']['without_venue_id']} 筆。",
        f"- 不需要場地（純出版、線上、電視）而未計入：{scopes.get(NO_VENUE, 0)} 筆。",
        f"- 場地名含線上或電視字樣、但地址是街道級（混合活動，#364）：{report['online_named_with_street_address']} 筆。",
        f"- `enrich_addresses.is_vague()` 視為具體、量尺判為待補：{report['not_vague_but_needs_fix']} 筆"
        "（`enrich_addresses` 改用量尺後會新增的候選）。",
        "",
        "## 各來源",
        "",
        "| 來源 | 範圍 | 事件 | 待補 | 街道級比率 |",
        "|---|---|---|---|---|",
    ]
    for s in report["sources"]:
        if s["missing"]:
            scope = "QA 範圍內" if s["scope"] == IN_SCOPE else "QA 排除"
            lines.append(
                f"| {s['source']} | {scope} | {s['total']} | {s['missing']} | {_pct(s['street_rate'])} |"
            )

    gaps = report["venue_gaps"]
    lines += [
        "",
        f"## 場地缺口（{len(gaps)} 個場地名，列出前 {min(top, len(gaps))} 個）",
        "",
        "依即將舉辦的缺地址事件數、再依缺地址事件數排序。",
        "",
        "| 場地名 | 缺地址事件 | 其中即將舉辦 | 同名事件已有的街道級地址 | 例 |",
        "|---|---|---|---|---|",
    ]
    for v in gaps[:top]:
        siblings = "；".join(v["sibling_street_addresses"][:2]) or "—"
        if len(v["sibling_street_addresses"]) > 2:
            siblings += f"（共 {len(v['sibling_street_addresses'])} 種）"
        name = v["location_name"].replace("|", "｜")
        lines.append(
            f"| {name} | {v['missing_events']} | {v['upcoming_missing']} | {siblings} | "
            f"[活動頁]({v['example_event']}) |"
        )

    reg = report["registry"]
    lines += [
        "",
        "## 場館登記簿",
        "",
        f"- 場館 {reg['venues']} 筆，權威 {reg['authoritative']} 筆，沒有地址 {reg['without_address']} 筆。",
        f"- 沒有地址、但旗下事件只出現一種街道級地址寫法：{len(reg['backfill_candidates'])} 筆"
        "（回填候選的上限；只有一筆事件也算，未查地址的出處）。",
        f"- 沒有地址、旗下事件有兩種以上街道級地址：{len(reg['backfill_conflicts'])} 筆（需人工判斷）。",
        f"- 沒有地址、旗下事件也沒有街道級地址：{reg['without_address_and_without_evidence']} 筆。",
    ]
    locks = report.get("locks")
    if locks:
        lines += [
            "",
            "## 鎖定欄位（field_corrections）",
            "",
            f"- 掛在權威場館下、地址被腳本鎖住、而且鎖的值與場館現址不同：{locks['authoritative_lock_differs']} 筆"
            f"（即將舉辦 {locks['authoritative_lock_differs_upcoming']} 筆）。場館修正流不到這些事件。",
            f"- 事件地址空白、但鎖定值非空：{locks['event_blank_but_locked']} 筆。",
            f"- 帶 JSON 引號的事件地址 {locks['quoted_event_addresses']} 筆；帶引號的地址鎖 {locks['quoted_address_locks']} 筆。",
            f"- `enrich_addresses` 改用量尺後新增的即將舉辦候選 {locks['enrich_new_candidates']} 筆，"
            f"其中 {locks['enrich_new_candidates_locked']} 筆有地址鎖、不會被處理。",
        ]
        lines.append("")
    missing_auth = reg["authoritative_without_address"]
    if missing_auth:
        names = "、".join(
            f"{v['canonical_name_ja']}{'（多會場）' if v['is_multi_venue'] else ''}" for v in missing_auth
        )
        lines.append(f"- 權威場館中沒有地址的 {len(missing_auth)} 筆：{names}。")
    lines.append("")
    return "\n".join(lines)


GRADE_LABELS = {
    "street": "street 街道級（合格）",
    "town": "town 町名",
    "region": "region 僅行政區",
    "not_address": "not_address 非地址",
    "non_japan": "non_japan 日本以外",
}


def render_sample(report: dict) -> str:
    """Stratified sample of graded addresses for the owner to spot check."""
    lines = [
        "# 地址量尺抽查樣本",
        "",
        f"產生時間：{report['generated_at']}。每個等級最多 {SAMPLE_PER_GRADE} 個不重複的地址，依雜湊排序抽取。",
        "",
        "看法：每一列的等級是否正確。最重要的是 street 這一段，不該出現沒有番地的地址。"
        "看到判錯的列，在 PR 留言貼上該列即可。",
        "",
    ]
    for grade, label in GRADE_LABELS.items():
        addresses = report["grade_samples"].get(grade, [])
        lines += [f"## {label}（{len(addresses)}）", ""]
        lines += [f"{i}. {a.replace(chr(10), ' ')[:120]}" for i, a in enumerate(addresses, 1)]
        lines.append("")
    return "\n".join(lines)


def _load_from_db() -> tuple[list[dict], list[dict], list[dict]]:
    from dotenv import load_dotenv
    from supabase import create_client

    from db_paging import fetch_all

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    events = fetch_all(lambda: (
        sb.table("events")
        .select(EVENT_COLUMNS)
        .eq("is_active", True)
        .is_("merged_into_event_id", None)
        .not_.is_("location_name", None)
        .order("id")
    ))
    venues = fetch_all(lambda: sb.table("venues").select(VENUE_COLUMNS).order("id"))
    locks = fetch_all(lambda: (
        sb.table("field_corrections")
        .select(LOCK_COLUMNS)
        .eq("field_name", "location_address")
        .order("event_id")
    ))
    return events, venues, locks


def _read_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--events-json", help="Read events from an exported JSON array instead of the database")
    parser.add_argument("--venues-json", help="Read venues from an exported JSON array instead of the database")
    parser.add_argument("--locks-json", help="Optional with --events-json: exported field_corrections rows")
    parser.add_argument("--output", help="Write the Markdown report here (default: stdout)")
    parser.add_argument("--json-output", help="Write the full report as JSON here")
    parser.add_argument("--sample-output", help="Write the stratified spot-check sample (Markdown) here")
    parser.add_argument("--top", type=int, default=40, help="Venue gaps to list in the Markdown report")
    args = parser.parse_args()

    if bool(args.events_json) != bool(args.venues_json):
        parser.error("--events-json and --venues-json must be given together")
    if args.events_json:
        events, venues = _read_json(args.events_json), _read_json(args.venues_json)
        locks = _read_json(args.locks_json) if args.locks_json else None
    else:
        events, venues, locks = _load_from_db()

    report = audit(events, venues, datetime.now(timezone.utc), locks)
    markdown = render_markdown(report, top=args.top)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(markdown)
    else:
        print(markdown)
    if args.sample_output:
        with open(args.sample_output, "w", encoding="utf-8") as f:
            f.write(render_sample(report))
    if args.json_output:
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
