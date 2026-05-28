"""One-off: reconcile active events with authoritative venues.

Usage:
    python _oneoff_fix_tcc_locations.py --dry-run
    python _oneoff_fix_tcc_locations.py
"""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from database import _get_client
from venue_registry import lookup_venue

logger = logging.getLogger(__name__)

LOCATION_UPDATE_FIELDS = (
    "location_name",
    "location_address",
    "location_prefectures",
    "location_name_zh",
    "location_name_en",
    "location_url",
    "venue_id",
)

_AUTHORITY_COLUMNS = (
    "is_authoritative",
    "is_multi_venue",
    "homepage",
    "prefectures",
)

_TCC_FALLBACK_NAMES = {
    "台湾文化センター",
    "台北駐日経済文化代表処 台湾文化センター",
    "台北駐日経済文化代表処台湾文化センター",
    "台湾文化中心",
}

_TCC_FALLBACK_VENUE: dict[str, Any] = {
    "id": None,
    "canonical_name_ja": "台北駐日経済文化代表処 台湾文化センター",
    "canonical_name_zh": "台北駐日經濟文化代表處 台灣文化中心",
    "canonical_name_en": "Taiwan Cultural Center, Taipei Economic and Cultural Representative Office in Japan",
    "address": "東京都港区虎ノ門1-1-12 虎ノ門ビル2階",
    "prefecture": "東京都",
    "prefectures": ["東京都"],
    "homepage": "https://www.taiwanembassy.org/jp_ja/post/84095.html",
    "is_multi_venue": False,
}


@dataclass
class Result:
    scanned: int = 0
    matched: int = 0
    updated: int = 0
    skipped_locked: int = 0
    skipped_same: int = 0


def _is_missing_authority_column_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return ("column" in msg or "schema cache" in msg) and "venues" in msg and any(c in msg for c in _AUTHORITY_COLUMNS)


def _has_venues_authority_columns(sb) -> bool:
    try:
        (
            sb.table("venues")
            .select("is_authoritative,is_multi_venue,homepage,prefectures")
            .limit(1)
            .execute()
        )
        return True
    except Exception as exc:
        if not _is_missing_authority_column_error(exc):
            raise
        logger.warning(
            "venues authority migration not applied, skip registry mode and keep TCC fallback mode enabled. error=%s",
            exc,
        )
        print("[WARN] migration 未套用，跳過 registry 模式（compatibility fallback）")
        return False


def _lookup_tcc_fallback(name: str | None) -> dict[str, Any] | None:
    key = (name or "").strip()
    if key in _TCC_FALLBACK_NAMES:
        return dict(_TCC_FALLBACK_VENUE)
    return None


def _fetch_active_events(sb) -> list[dict[str, Any]]:
    return (
        sb.table("events")
        .select(
            "id,location_name,location_address,location_prefectures,"
            "location_name_zh,location_name_en,location_url,venue_id"
        )
        .eq("is_active", True)
        .execute()
        .data
        or []
    )


def _get_locked_fields(sb, event_id: str) -> set[str]:
    rows = (
        sb.table("field_corrections")
        .select("field_name")
        .eq("event_id", event_id)
        .in_("field_name", list(LOCATION_UPDATE_FIELDS))
        .execute()
        .data
        or []
    )
    return {r.get("field_name") for r in rows if r.get("field_name")}


def _build_updates(event: dict[str, Any], venue: dict[str, Any], locked: set[str]) -> dict[str, Any]:
    candidate = {
        "location_name": venue.get("canonical_name_ja"),
        "location_address": None if venue.get("is_multi_venue") else venue.get("address"),
        "location_prefectures": venue.get("prefectures") or (
            [venue.get("prefecture")] if venue.get("prefecture") else None
        ),
        "location_name_zh": venue.get("canonical_name_zh"),
        "location_name_en": venue.get("canonical_name_en"),
        "location_url": venue.get("homepage"),
        "venue_id": venue.get("id"),
    }

    updates: dict[str, Any] = {}
    for key, val in candidate.items():
        if key in locked:
            continue
        if val is None and key != "location_address":
            continue
        if event.get(key) == val:
            continue
        updates[key] = val
    return updates


def run(dry_run: bool) -> Result:
    sb = _get_client()
    result = Result()
    registry_enabled = _has_venues_authority_columns(sb)

    events = _fetch_active_events(sb)
    result.scanned = len(events)

    for event in events:
        loc_name = event.get("location_name")
        venue = lookup_venue(loc_name) if registry_enabled else _lookup_tcc_fallback(loc_name)
        if not venue:
            continue
        result.matched += 1

        locked = _get_locked_fields(sb, event["id"])
        if locked:
            result.skipped_locked += 1
            print(f"[SKIP locked] {event['id'][:8]} fields={sorted(locked)}")
            continue

        updates = _build_updates(event, venue, locked)
        if not updates:
            result.skipped_same += 1
            continue

        if dry_run:
            print(f"[DRY-RUN] {event['id'][:8]} keys={sorted(updates.keys())}")
            result.updated += 1
            continue

        sb.table("events").update(updates).eq("id", event["id"]).execute()
        print(f"[APPLY] {event['id'][:8]} keys={sorted(updates.keys())}")
        result.updated += 1

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile active events with authoritative venues")
    parser.add_argument("--dry-run", action="store_true", help="Show updates without writing DB")
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

    res = run(args.dry_run)
    mode = "DRY-RUN" if args.dry_run else "APPLY"
    print(
        f"[{mode}] done | scanned={res.scanned} matched={res.matched} updated={res.updated} "
        f"skipped_locked={res.skipped_locked} skipped_same={res.skipped_same}"
    )


if __name__ == "__main__":
    main()
