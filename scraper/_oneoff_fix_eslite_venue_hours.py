"""Applied provenance for the Eslite Nihonbashi venue-hours repair.

The official store/access page states the general opening hours as weekdays
11:00-20:00 and weekends/public holidays 10:00-20:00. Event-specific schedules
remain untouched; this repair only fills the umbrella event and three child
activities whose hours are currently empty.

Manifest ``5742d0438ed9`` was applied from 2026-08-09T22:09:12.030295Z through
2026-08-09T22:09:31.152860Z. The verified post-state is one authoritative venue
row, four general-hours events, four preserved event-specific schedules, 12
field corrections, and 12 applied audit rows. The historical mutation and
verification functions remain for audit inspection; the ``--apply`` path is
permanently retired.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

from qa_auto_fix import unlock_and_write


VENUE_ID = "fd330e2a-e8e8-40fb-9fcb-d1af44d7be3a"
VENUE_NAME = "誠品生活日本橋"
OLD_VENUE_URL = "https://www.eslitespectrum.jp/"
VENUE_URL = (
    "https://www.eslitespectrum.jp/about/store/"
    "9cd1340f-26b6-4f55-9c33-d0487d7ac01d"
)

HOURS = {
    "business_hours": "平日 11:00～20:00、土日祝 10:00～20:00",
    "business_hours_zh": "平日 11:00～20:00、週六日及國定假日 10:00～20:00",
    "business_hours_en": (
        "Weekdays 11:00 AM–8:00 PM; weekends and public holidays "
        "10:00 AM–8:00 PM"
    ),
}

TARGET_EVENTS = {
    "074ec240-3463-4c42-8cab-2ea348b93f5c": {
        "name_ja": "夏日の奇幻旅程～夏休みのファンタジック・ジャーニー～",
        "location_name": "誠品生活日本橋(COREDO室町テラス2階)および 1階大屋根広場",
    },
    "dda72a62-ad44-4aa4-aa23-33c942b06a92": {
        "name_ja": "eslite Collection -夏日の奇幻旅程-",
        "location_name": "誠品生活日本橋 各ショップ",
    },
    "5e8767c4-d89b-44c2-a995-a617db66eb8f": {
        "name_ja": "普段使いの魔法道具マーケット『まいにち魔法』",
        "location_name": "誠品生活日本橋 expo",
    },
    "5a5e27fc-68bf-4152-9830-9b4ed9228ad2": {
        "name_ja": "eslite welcome weekend! 誠品会員限定抽選会",
        "location_name": "誠品生活日本橋 書籍レジ",
    },
}

PARENT_ID = "074ec240-3463-4c42-8cab-2ea348b93f5c"
EXPECTED_PARENT_LOCKS = {
    "business_hours": ("abc9e96f-b566-4365-8cb0-4d60168a3507", ""),
    "business_hours_zh": ("2b1b3ef5-dc4f-4229-bcf0-df01aba5993a", ""),
    "business_hours_en": ("cd11e7d3-0a30-40a4-95a5-416f10aee4a1", ""),
}


def _client():
    local_env = Path(__file__).with_name(".env")
    shared_env = Path(__file__).resolve().parents[2] / "scraper" / ".env"
    load_dotenv(local_env if local_env.exists() else shared_env, override=False)
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _assert_subset(label: str, actual: dict[str, Any], expected: dict[str, Any]) -> None:
    mismatches = [
        f"{field}: expected={value!r} actual={actual.get(field)!r}"
        for field, value in expected.items()
        if actual.get(field) != value
    ]
    if mismatches:
        raise RuntimeError(f"{label} drift:\n  " + "\n  ".join(mismatches))


def _preflight(sb) -> dict[str, Any]:
    venue = (
        sb.table("venues")
        .select("id,canonical_name_ja,homepage,is_authoritative,business_hours")
        .eq("id", VENUE_ID)
        .single()
        .execute()
        .data
    )
    _assert_subset(
        "venue",
        venue,
        {
            "id": VENUE_ID,
            "canonical_name_ja": VENUE_NAME,
            "homepage": OLD_VENUE_URL,
            "is_authoritative": True,
            "business_hours": None,
        },
    )

    rows = (
        sb.table("events")
        .select(
            "id,name_ja,location_name,business_hours,business_hours_zh,"
            "business_hours_en,is_active,annotation_status"
        )
        .in_("id", list(TARGET_EVENTS))
        .execute()
        .data
        or []
    )
    by_id = {row["id"]: row for row in rows}
    if set(by_id) != set(TARGET_EVENTS):
        raise RuntimeError(
            f"target event set drift: expected={sorted(TARGET_EVENTS)} actual={sorted(by_id)}"
        )
    for event_id, expected in TARGET_EVENTS.items():
        _assert_subset(
            f"event {event_id}",
            by_id[event_id],
            {
                **expected,
                "business_hours": None,
                "business_hours_zh": None,
                "business_hours_en": None,
                "is_active": True,
                "annotation_status": "annotated",
            },
        )

    lock_rows = (
        sb.table("field_corrections")
        .select("*")
        .in_("event_id", list(TARGET_EVENTS))
        .in_("field_name", list(HOURS))
        .execute()
        .data
        or []
    )
    locks = {
        (row["event_id"], row["field_name"]): row
        for row in lock_rows
    }
    if len(locks) != len(EXPECTED_PARENT_LOCKS):
        raise RuntimeError(f"target FC count drift: {lock_rows}")
    for field, (expected_id, expected_value) in EXPECTED_PARENT_LOCKS.items():
        lock = locks.get((PARENT_ID, field))
        if not lock:
            raise RuntimeError(f"missing expected parent FC: {field}")
        if lock.get("id") != expected_id or lock.get("corrected_value") != expected_value:
            raise RuntimeError(f"parent FC drift for {field}: {lock}")

    return {"venue": venue, "events": by_id, "locks": locks}


def _manifest_digest() -> str:
    manifest = {
        "venue_id": VENUE_ID,
        "venue_url": VENUE_URL,
        "hours": HOURS,
        "target_event_ids": sorted(TARGET_EVENTS),
    }
    return hashlib.sha256(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()[:12]


def _apply_venue(sb) -> None:
    rows = (
        sb.table("venues")
        .update({"homepage": VENUE_URL, "business_hours": HOURS["business_hours"]})
        .eq("id", VENUE_ID)
        .eq("canonical_name_ja", VENUE_NAME)
        .eq("homepage", OLD_VENUE_URL)
        .is_("business_hours", "null")
        .select("id")
        .execute()
        .data
        or []
    )
    if len(rows) != 1:
        raise RuntimeError(f"venue CAS row count: expected=1 actual={len(rows)}")


def _apply_events(sb, snapshot: dict[str, Any], reason: str) -> None:
    for event_id in TARGET_EVENTS:
        for field, value in HOURS.items():
            ok = unlock_and_write(
                sb,
                event_id=event_id,
                field_name=field,
                new_value=value,
                mode="lock_clean",
                unlock_reason=reason,
                r_class="R-ENRICH-MISS",
                model_used="rule:official_venue_access_page",
                confidence=1.0,
                expected_fc=snapshot["locks"].get((event_id, field)),
                expected_event_value=None,
            )
            if not ok:
                raise RuntimeError(f"guarded write failed: {event_id}.{field}")


def _verify(sb, reason: str) -> None:
    venue = (
        sb.table("venues")
        .select("id,canonical_name_ja,homepage,is_authoritative,business_hours")
        .eq("id", VENUE_ID)
        .single()
        .execute()
        .data
    )
    _assert_subset(
        "venue after",
        venue,
        {
            "homepage": VENUE_URL,
            "business_hours": HOURS["business_hours"],
            "is_authoritative": True,
        },
    )

    rows = (
        sb.table("events")
        .select("id,business_hours,business_hours_zh,business_hours_en")
        .in_("id", list(TARGET_EVENTS))
        .execute()
        .data
        or []
    )
    if len(rows) != len(TARGET_EVENTS):
        raise RuntimeError(f"event verify count mismatch: {len(rows)}")
    for row in rows:
        _assert_subset(f"event after {row['id']}", row, HOURS)

    locks = (
        sb.table("field_corrections")
        .select("event_id,field_name,corrected_value")
        .in_("event_id", list(TARGET_EVENTS))
        .in_("field_name", list(HOURS))
        .execute()
        .data
        or []
    )
    expected_locks = {
        (event_id, field, value)
        for event_id in TARGET_EVENTS
        for field, value in HOURS.items()
    }
    actual_locks = {
        (row["event_id"], row["field_name"], row["corrected_value"])
        for row in locks
    }
    if actual_locks != expected_locks:
        raise RuntimeError("field_corrections verification mismatch")

    audits = (
        sb.table("field_corrections_audit")
        .select("event_id,field_name,operation_status")
        .eq("unlock_reason", reason)
        .execute()
        .data
        or []
    )
    expected_audits = {
        (event_id, field, "applied")
        for event_id in TARGET_EVENTS
        for field in HOURS
    }
    actual_audits = {
        (row["event_id"], row["field_name"], row["operation_status"])
        for row in audits
    }
    if actual_audits != expected_audits:
        raise RuntimeError(f"audit verification mismatch: {audits}")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.apply:
        raise SystemExit(
            "--apply is permanently retired: Eslite venue-hours manifest "
            "5742d0438ed9 is already applied and verified"
        )

    sb = _client()
    snapshot = _preflight(sb)
    digest = _manifest_digest()
    reason = f"Eslite official access-page venue hours manifest={digest}"
    print(f"preflight PASS manifest={digest}")
    print(f"venue ground truth: {VENUE_ID}")
    print(f"hours-less target events: {len(TARGET_EVENTS)}")
    print("event-specific child schedules preserved: 4")

    if args.dry_run:
        print("DRY RUN: no writes")
        return 0

    _apply_venue(sb)
    _apply_events(sb, snapshot, reason)
    _verify(sb, reason)
    print("verification PASS: venue=1 events=4 FC=12 audits=12")
    for event_id in TARGET_EVENTS:
        print(f"  https://tokyotaiwanradar.com/ja/events/{event_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
