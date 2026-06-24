"""One-off: fix Taiwan Puppet Theatre Culture Month (台灣布袋戲文化月) locations.

The parent event 7446190c and its 5 sub-events were hard-set to the Taiwan
Cultural Center (台湾文化センター) by the TCC scraper default, even though the
real venues are at Waseda University (演劇博物館 / 小野記念講堂 / ワセダギャラリー).
field_corrections currently LOCK the wrong TCC values, so plain re-annotation
cannot fix them — this one-off must DELETE the stale FC rows first, UPDATE the
events table, then RE-LOCK the corrected values.

Query shape (per-event `.eq("event_id", ...)`) is reused from
_oneoff_fix_tcc_locations.py::_get_locked_fields, but the skip-locked behaviour
is intentionally NOT reused (these 6 events are exactly the ones whose FC locks
must be replaced).

FC write routing (Engineer SKILL.md §_lock_fields_via_corrections + Architect
SKILL.md §FC NOT NULL):
  - TEXT fields  -> annotator._lock_fields_via_corrections() (keeps _zh _to_trad guard)
  - location_prefectures (text[]) -> JSON-serialized corrected_value (database._auto_lock_location convention)
  - location_url / venue_id -> DELETE stale FC only, never re-lock (provenance guard)

Usage:
    ../.venv/bin/python _oneoff_fix_puppet_month_locations.py --dry-run
    ../.venv/bin/python _oneoff_fix_puppet_month_locations.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from dotenv import load_dotenv

from database import _get_client
from annotator import _lock_fields_via_corrections, _to_trad

# ──────────────────────────────────────────────────────────────────────────────
# Target data — 6 fixed UUIDs (1 parent + 5 sub-events)
# ──────────────────────────────────────────────────────────────────────────────

# Shared Waseda campus address (early-Waseda, Shinjuku).
_WASEDA_ADDR = {
    "location_address": "東京都新宿区西早稲田1丁目6-1",
    "location_address_zh": "東京都新宿區西早稻田1丁目6-1",
    "location_address_en": "1-6-1 Nishi-Waseda, Shinjuku, Tokyo",
}

# 小野記念講堂 localized name (shared by 4 sub-events).
_ONO_HALL = {
    "location_name": "小野記念講堂",
    "location_name_zh": "小野紀念講堂",
    "location_name_en": "Ono Memorial Auditorium",
}

# TEXT fields that get re-locked via _lock_fields_via_corrections().
PUPPET_TEXT_FC_FIELDS = (
    "location_name",
    "location_name_zh",
    "location_name_en",
    "location_address",
    "location_address_zh",
    "location_address_en",
    "business_hours",
    "business_hours_zh",
    "business_hours_en",
)

# All FC field_names whose stale TCC values must be deleted before re-write.
# location_url / venue_id are deleted but NOT re-locked.
FC_FIELDS_TO_CLEAR = (
    *PUPPET_TEXT_FC_FIELDS,
    "location_prefectures",
    "location_url",
    "venue_id",
)

EVENTS: list[dict[str, Any]] = [
    {
        "id": "7446190c-64ad-4273-adbe-48f14be1cb0b",
        "role": "parent",
        "text": {
            "location_name": "早稲田大学早稲田キャンパス（演劇博物館・小野記念講堂・ワセダギャラリー）",
            "location_name_zh": "早稻田大學早稻田校區（演劇博物館・小野紀念講堂・Waseda Gallery）",
            "location_name_en": "Waseda University Waseda Campus (Theatre Museum, Ono Memorial Auditorium, Waseda Gallery)",
            **_WASEDA_ADDR,
            "business_hours": "プログラムにより異なる",
            "business_hours_zh": "依各節目而異",
            "business_hours_en": "Varies by program",
        },
        "prefectures": ["東京都"],
        # Waseda Tsubouchi Museum exhibition page — official EVENT page (not a venue
        # homepage), so it goes to official_url, NOT location_url.
        "official_url": "https://enpaku.w.waseda.jp/ex/21525/",
    },
    {
        "id": "db7a2a69-096f-488c-ad11-b0b3a7fb9ba6",
        "role": "sub",
        "text": {
            "location_name": "早稲田大学坪内博士記念演劇博物館 1階 六世中村歌右衛門記念特別展示室",
            "location_name_zh": "早稻田大學坪內博士紀念演劇博物館 1樓 六世中村歌右衛門紀念特別展示室",
            "location_name_en": "Tsubouchi Memorial Theatre Museum, Waseda University — 1F Special Exhibition Room",
            **_WASEDA_ADDR,
            "business_hours": "10:00〜17:00（火・金曜日は19:00まで、7/15休館）",
            "business_hours_zh": "10:00〜17:00（週二・週五至19:00，7/15休館）",
            "business_hours_en": "10:00–17:00 (until 19:00 on Tue & Fri; closed 7/15)",
        },
        "prefectures": ["東京都"],
    },
    {
        "id": "8574a5a5-0cc5-40b4-b8c5-b8fa6cfbb910",
        "role": "sub",
        "text": {
            **_ONO_HALL,
            **_WASEDA_ADDR,
            "business_hours": "17:00〜20:15（16:30開場）",
            "business_hours_zh": "17:00〜20:15（16:30開場）",
            "business_hours_en": "17:00–20:15 (doors open 16:30)",
        },
        "prefectures": ["東京都"],
    },
    {
        "id": "d6f942dc-9ece-4de4-986e-cbbdd5e35d11",
        "role": "sub",
        "text": {
            **_ONO_HALL,
            **_WASEDA_ADDR,
            "business_hours": "15:00〜",
            "business_hours_zh": "15:00〜",
            "business_hours_en": "From 15:00",
        },
        "prefectures": ["東京都"],
    },
    {
        "id": "0c94d100-1137-4cf8-b119-1f6d11a82409",
        "role": "sub",
        "text": {
            **_ONO_HALL,
            **_WASEDA_ADDR,
            "business_hours": "18:00〜",
            "business_hours_zh": "18:00〜",
            "business_hours_en": "From 18:00",
        },
        "prefectures": ["東京都"],
    },
    {
        "id": "1194533e-e00c-4892-bc90-1293885ee019",
        "role": "sub",
        "text": {
            **_ONO_HALL,
            **_WASEDA_ADDR,
            "business_hours": "18:00〜",
            "business_hours_zh": "18:00〜",
            "business_hours_en": "From 18:00",
        },
        "prefectures": ["東京都"],
    },
]

_EVENT_SELECT = (
    "id,name_ja,parent_event_id,"
    "location_name,location_name_zh,location_name_en,"
    "location_address,location_address_zh,location_address_en,"
    "location_prefectures,business_hours,business_hours_zh,business_hours_en,"
    "location_url,venue_id,official_url"
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _db_value(field: str, value: Any) -> Any:
    """Mirror annotator's _zh traditionalisation so DB matches FC exactly."""
    if isinstance(value, str) and field.endswith("_zh"):
        return _to_trad(value)
    return value


def _build_db_update(spec: dict[str, Any]) -> dict[str, Any]:
    """Build the events-table update payload for one event."""
    upd: dict[str, Any] = {f: _db_value(f, v) for f, v in spec["text"].items()}
    upd["location_prefectures"] = list(spec["prefectures"])
    upd["location_url"] = None
    upd["venue_id"] = None
    if spec.get("official_url"):
        upd["official_url"] = spec["official_url"]
    return upd


def _expected_fc(spec: dict[str, Any]) -> dict[str, str]:
    """Expected field_corrections corrected_value strings after re-lock."""
    fc: dict[str, str] = {}
    for f, v in spec["text"].items():
        fc[f] = str(_to_trad(v)) if (isinstance(v, str) and f.endswith("_zh")) else str(v)
    fc["location_prefectures"] = json.dumps(list(spec["prefectures"]), ensure_ascii=False)
    return fc


def _fetch_event(sb, eid: str) -> dict[str, Any] | None:
    res = sb.table("events").select(_EVENT_SELECT).eq("id", eid).limit(1).execute()
    return res.data[0] if res.data else None


def _fetch_fc(sb, eid: str) -> dict[str, str]:
    rows = (
        sb.table("field_corrections")
        .select("field_name,corrected_value")
        .eq("event_id", eid)
        .in_("field_name", list(FC_FIELDS_TO_CLEAR))
        .execute()
        .data
        or []
    )
    return {r["field_name"]: r.get("corrected_value") for r in rows if r.get("field_name")}


def _verify(ev: dict[str, Any], fc: dict[str, str], spec: dict[str, Any]) -> list[str]:
    """Return list of mismatch messages; empty == OK."""
    errors: list[str] = []
    exp_db = _build_db_update(spec)
    exp_fc = _expected_fc(spec)

    for f, v in exp_db.items():
        if ev.get(f) != v:
            errors.append(f"events.{f}={ev.get(f)!r} != expected {v!r}")
    for f, v in exp_fc.items():
        if fc.get(f) != v:
            errors.append(f"FC.{f}={fc.get(f)!r} != expected {v!r}")
    # location_url / venue_id FC must be absent (deleted, never re-locked).
    for f in ("location_url", "venue_id"):
        if f in fc:
            errors.append(f"FC.{f} should be absent, got {fc.get(f)!r}")
    return errors


# ──────────────────────────────────────────────────────────────────────────────
# Dry-run / apply
# ──────────────────────────────────────────────────────────────────────────────
def _print_diff(sb, spec: dict[str, Any]) -> None:
    eid = spec["id"]
    ev = _fetch_event(sb, eid)
    if ev is None:
        print(f"[DRY-RUN][MISSING] {eid[:8]} not found in events")
        return
    fc = _fetch_fc(sb, eid)
    exp_db = _build_db_update(spec)
    print(f"\n[DRY-RUN] {eid[:8]} ({spec['role']}) {(ev.get('name_ja') or '')[:40]}")
    for f, new_v in exp_db.items():
        cur = ev.get(f)
        flag = "  " if cur == new_v else "→ "
        print(f"  {flag}{f}: {cur!r}  =>  {new_v!r}")
    cleared = [f for f in FC_FIELDS_TO_CLEAR if f in fc]
    print(f"   FC currently present (will delete): {cleared}")
    print(f"   FC to re-lock: TEXT={list(PUPPET_TEXT_FC_FIELDS)} + JSON=['location_prefectures']")


def _apply_one(sb, spec: dict[str, Any]) -> None:
    eid = spec["id"]
    # 0. Guard: event must exist.
    if _fetch_event(sb, eid) is None:
        raise RuntimeError(f"event {eid} not found — aborting before any write")
    # 1. DELETE stale FC for all managed field_names.
    sb.table("field_corrections").delete().eq("event_id", eid).in_(
        "field_name", list(FC_FIELDS_TO_CLEAR)
    ).execute()
    # 2. UPDATE events table.
    sb.table("events").update(_build_db_update(spec)).eq("id", eid).execute()
    # 3a. RE-LOCK TEXT fields via the chokepoint helper (keeps _zh _to_trad guard).
    _lock_fields_via_corrections(sb, eid, {f: spec["text"][f] for f in PUPPET_TEXT_FC_FIELDS})
    # 3b. RE-LOCK location_prefectures with JSON-serialized value (text[] convention).
    sb.table("field_corrections").upsert(
        {
            "event_id": eid,
            "field_name": "location_prefectures",
            "corrected_value": json.dumps(list(spec["prefectures"]), ensure_ascii=False),
            "corrected_by": None,
        },
        on_conflict="event_id,field_name",
    ).execute()
    # 4. RE-READ and verify; fail fast on any mismatch.
    ev = _fetch_event(sb, eid)
    fc = _fetch_fc(sb, eid)
    errors = _verify(ev or {}, fc, spec)
    if errors:
        raise RuntimeError(f"verification failed for {eid}:\n    " + "\n    ".join(errors))
    print(f"[APPLY][OK] {eid[:8]} ({spec['role']}) verified")


def run(dry_run: bool) -> None:
    sb = _get_client()
    if dry_run:
        for spec in EVENTS:
            _print_diff(sb, spec)
        print(f"\n[DRY-RUN] done | {len(EVENTS)} events (no DB writes)")
        return

    updated: list[str] = []
    try:
        for spec in EVENTS:
            _apply_one(sb, spec)
            updated.append(spec["id"][:8])
    except Exception as exc:  # fail fast — surface partial progress, do not swallow
        print(f"\n[APPLY][FAIL] {exc}")
        print(f"[APPLY] events successfully updated before failure: {updated}")
        sys.exit(1)
    print(f"\n[APPLY] done | {len(updated)} events updated & verified: {updated}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Print diff, write nothing")
    group.add_argument("--apply", action="store_true", help="Apply changes and verify")
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
