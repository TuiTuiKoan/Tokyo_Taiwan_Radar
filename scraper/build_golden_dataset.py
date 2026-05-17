"""
build_golden_dataset.py — Build and maintain the annotator golden test set.

Two modes:
  python build_golden_dataset.py --target 50 --interactive
      Fetch Tier 1 (field_corrections-backed) and Tier 2 (reviewed + spot check)
      cases from DB, run interactive spot check, and export:
        scraper/tests/golden/cases.jsonl
        scraper/tests/golden/manifest.json
        scraper/tests/golden/frozen_corrections.json

  python build_golden_dataset.py --rebuild-frozen-only
      Re-snapshot category_corrections and selection_reason_corrections from DB
      into frozen_corrections.json without touching cases.jsonl.

Measured fields (must match eval_annotator.py MEASURED_FIELDS):
  name_zh, name_en, description_zh, description_en,
  category, event_form, primary_language,
  is_paid, has_japanese_support, has_english_support, location_name
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
GOLDEN_DIR = Path(__file__).parent / "tests" / "golden"
CASES_PATH = GOLDEN_DIR / "cases.jsonl"
MANIFEST_PATH = GOLDEN_DIR / "manifest.json"
FROZEN_PATH = GOLDEN_DIR / "frozen_corrections.json"

# Fields evaluated by eval_annotator.py — must stay in sync
MEASURED_FIELDS = frozenset({
    "name_zh", "name_en", "description_zh", "description_en",
    "category", "event_form", "primary_language",
    "is_paid", "has_japanese_support", "has_english_support",
    "location_name",
})

# List fields (compared with set equality)
LIST_FIELDS = frozenset({"category", "event_form"})

# Tags we attach to cases
TAG_FC_BACKED = "fc_backed"
TAG_REVIEWED = "reviewed"


def _get_sb():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _sha256_json(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _load_frozen_corrections(sb) -> dict:
    """Fetch category_corrections and selection_reason_corrections from DB."""
    cat_corrs = []
    sr_corrs = []
    try:
        res = (
            sb.table("category_corrections")
            .select("raw_title,raw_description,ai_category,corrected_category")
            .order("created_at", desc=True)
            .limit(15)
            .execute()
        )
        cat_corrs = res.data or []
    except Exception as e:
        logger.warning("category_corrections fetch failed: %s", e)

    try:
        res = (
            sb.table("selection_reason_corrections")
            .select("raw_title,raw_description,ai_sr,corrected_sr")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        sr_corrs = res.data or []
    except Exception as e:
        logger.warning("selection_reason_corrections fetch failed: %s", e)

    snapshot_at = datetime.now(tz=JST).isoformat()
    data = {
        "snapshot_at": snapshot_at,
        "category_corrections": cat_corrs,
        "selection_reason_corrections": sr_corrs,
        "sha256": None,
    }
    data["sha256"] = _sha256_json(data)
    return data


def rebuild_frozen_only(sb) -> None:
    """Re-snapshot corrections tables and write frozen_corrections.json."""
    logger.info("Rebuilding frozen_corrections.json from DB ...")
    frozen = _load_frozen_corrections(sb)
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    FROZEN_PATH.write_text(json.dumps(frozen, ensure_ascii=False, indent=2))
    logger.info("Written: %s (sha256: %s...)", FROZEN_PATH, frozen["sha256"][:12])

    # Update manifest sha256 if manifest exists
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
        manifest["frozen_corrections_sha256"] = frozen["sha256"]
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        logger.info("Updated manifest frozen_corrections_sha256")


def _fetch_tier1_cases(sb) -> list[dict]:
    """Fetch events that have field_corrections for measured fields."""
    logger.info("Fetching Tier 1 cases (field_corrections-backed) ...")
    try:
        # Get field_corrections for measured fields only
        fc_rows = (
            sb.table("field_corrections")
            .select("event_id,field_name,corrected_value,created_at")
            .in_("field_name", list(MEASURED_FIELDS))
            .order("created_at", desc=True)
            .execute()
            .data or []
        )
    except Exception as e:
        logger.warning("field_corrections fetch failed: %s", e)
        return []

    # Group by event_id
    fc_by_event: dict[str, list[dict]] = {}
    for row in fc_rows:
        eid = row["event_id"]
        fc_by_event.setdefault(eid, []).append(row)

    if not fc_by_event:
        logger.warning("No field_corrections found for measured fields")
        return []

    # Fetch the events
    event_ids = list(fc_by_event.keys())
    # Batch fetch (max 200 at a time to avoid query size limits)
    events_by_id: dict[str, dict] = {}
    for i in range(0, len(event_ids), 200):
        batch = event_ids[i:i + 200]
        try:
            rows = (
                sb.table("events")
                .select("id,raw_title,raw_description,source_name," + ",".join(MEASURED_FIELDS))
                .in_("id", batch)
                .execute()
                .data or []
            )
            for e in rows:
                events_by_id[e["id"]] = e
        except Exception as ex:
            logger.warning("events batch fetch failed: %s", ex)

    # Build cases
    cases = []
    for event_id, fc_list in fc_by_event.items():
        event = events_by_id.get(event_id)
        if not event:
            continue
        if not event.get("raw_title") and not event.get("raw_description"):
            continue

        # Build expected dict — only fields in this event's fc_list
        expected: dict[str, dict | None] = {}
        for fc in fc_list:
            field_name = fc["field_name"]
            raw_val = fc.get("corrected_value") or ""
            # Parse list fields from JSON string
            if field_name in LIST_FIELDS:
                try:
                    value = json.loads(raw_val) if raw_val else None
                except json.JSONDecodeError:
                    value = [raw_val] if raw_val else None
            elif field_name in {"is_paid", "has_japanese_support", "has_english_support"}:
                # Boolean stored as "true"/"false" string or actual bool
                if isinstance(raw_val, bool):
                    value = raw_val
                elif raw_val.lower() == "true":
                    value = True
                elif raw_val.lower() == "false":
                    value = False
                else:
                    value = None
            else:
                value = raw_val if raw_val else None

            if value is not None:
                expected[field_name] = {"value": value, "tier": 1, "from_fc": True}

        # Skip if no usable expected fields
        if not expected:
            continue

        # Fill nulls for other measured fields (not tested)
        for f in MEASURED_FIELDS:
            if f not in expected:
                expected[f] = None

        case_id = event_id[:8]
        tags = [TAG_FC_BACKED]

        cases.append({
            "case_id": case_id,
            "event_id": event_id,
            "source_name": event.get("source_name", ""),
            "input": {
                "raw_title": event.get("raw_title") or "",
                "raw_description": event.get("raw_description") or "",
            },
            "expected": expected,
            "tags": tags,
        })

    logger.info("Tier 1: found %d candidate cases from field_corrections", len(cases))
    return cases


def _fetch_tier2_candidates(sb, exclude_ids: set[str], limit: int = 80) -> list[dict]:
    """Fetch reviewed events not already covered by Tier 1."""
    logger.info("Fetching Tier 2 candidates (reviewed events) ...")
    try:
        rows = (
            sb.table("events")
            .select("id,raw_title,raw_description,source_name," + ",".join(MEASURED_FIELDS))
            .eq("annotation_status", "reviewed")
            .eq("is_active", True)
            .is_("parent_event_id", "null")
            .limit(limit)
            .execute()
            .data or []
        )
    except Exception as e:
        logger.warning("reviewed events fetch failed: %s", e)
        return []

    return [r for r in rows if r["id"] not in exclude_ids]


def _display_case_for_spot_check(event: dict, candidate_fields: dict) -> None:
    """Print event summary and candidate expected values for user review."""
    print("\n" + "=" * 70)
    print(f"Event ID : {event['id']}")
    print(f"Source   : {event.get('source_name', '')}")
    print(f"Title    : {(event.get('raw_title') or '')[:100]}")
    desc = (event.get("raw_description") or "")[:300]
    print(f"Desc     : {desc}...")
    print("-" * 70)
    print("Candidate expected values (from current DB):")
    for field, val in candidate_fields.items():
        if val is not None:
            print(f"  {field:30s}: {json.dumps(val, ensure_ascii=False)[:80]}")
    print("-" * 70)


def _spot_check_interactive(event: dict) -> dict | None:
    """Interactive spot-check of a single reviewed event.

    Returns dict of confirmed expected fields, or None to skip this event.
    """
    candidate_fields = {
        f: event.get(f)
        for f in MEASURED_FIELDS
        if event.get(f) is not None
    }
    if not candidate_fields:
        return None

    _display_case_for_spot_check(event, candidate_fields)

    while True:
        answer = input("Include this case? [y=yes / n=no / s=skip / q=quit] ").strip().lower()
        if answer in ("q", "quit"):
            raise KeyboardInterrupt("User quit spot check")
        if answer in ("n", "no"):
            return None
        if answer in ("s", "skip"):
            return None
        if answer in ("y", "yes"):
            break
        print("Please enter y, n, s, or q")

    # Ask which fields to include
    confirmed: dict[str, dict] = {}
    print("\nFor each field, enter 'y' to include, 'n' to exclude (default: y):")
    for field, val in candidate_fields.items():
        short_val = json.dumps(val, ensure_ascii=False)[:60]
        answer = input(f"  {field:30s} = {short_val} [Y/n]: ").strip().lower()
        if answer in ("n", "no"):
            continue
        confirmed[field] = {"value": val, "tier": 2, "from_fc": False}

    return confirmed if confirmed else None


def _build_interactive(sb, target: int) -> list[dict]:
    """Run the full interactive golden set building pipeline."""
    tier1_cases = _fetch_tier1_cases(sb)
    tier1_ids = {c["event_id"] for c in tier1_cases}

    # Limit Tier 1 to target//2 to leave room for Tier 2
    tier1_budget = max(target // 2, len(tier1_cases))
    tier1_cases = tier1_cases[:tier1_budget]

    tier2_candidates = _fetch_tier2_candidates(sb, exclude_ids=tier1_ids, limit=target * 3)
    tier2_needed = max(0, target - len(tier1_cases))

    logger.info(
        "Building golden set: %d Tier 1 cases, need %d Tier 2 cases from %d candidates",
        len(tier1_cases), tier2_needed, len(tier2_candidates),
    )

    tier2_cases: list[dict] = []
    print(f"\n{'='*70}")
    print(f"INTERACTIVE SPOT CHECK — Tier 2 (reviewed events)")
    print(f"Target: {tier2_needed} additional cases (press q to stop early)")
    print(f"{'='*70}")

    for candidate in tier2_candidates:
        if len(tier2_cases) >= tier2_needed:
            break
        try:
            confirmed = _spot_check_interactive(candidate)
        except KeyboardInterrupt:
            print("\nSpot check stopped by user.")
            break

        if confirmed is None:
            continue

        # Fill nulls for other measured fields
        expected: dict[str, dict | None] = {}
        for f in MEASURED_FIELDS:
            expected[f] = confirmed.get(f)

        tier2_cases.append({
            "case_id": candidate["id"][:8],
            "event_id": candidate["id"],
            "source_name": candidate.get("source_name", ""),
            "input": {
                "raw_title": candidate.get("raw_title") or "",
                "raw_description": candidate.get("raw_description") or "",
            },
            "expected": expected,
            "tags": [TAG_REVIEWED],
        })

    all_cases = tier1_cases + tier2_cases
    logger.info("Final golden set: %d cases (%d T1, %d T2)", len(all_cases), len(tier1_cases), len(tier2_cases))
    return all_cases


def _write_cases(cases: list[dict], frozen: dict, target: int) -> None:
    """Write cases.jsonl, manifest.json, and frozen_corrections.json."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    # Write cases.jsonl (one JSON per line, no event_id in output)
    lines = []
    for c in cases:
        row = {k: v for k, v in c.items() if k != "event_id"}
        lines.append(json.dumps(row, ensure_ascii=False))
    CASES_PATH.write_text("\n".join(lines) + ("\n" if lines else ""))
    logger.info("Written %d cases to %s", len(lines), CASES_PATH)

    # Write frozen_corrections.json
    FROZEN_PATH.write_text(json.dumps(frozen, ensure_ascii=False, indent=2))
    logger.info("Written frozen_corrections.json (sha256: %s...)", frozen["sha256"][:12])

    # Write manifest.json
    manifest = {
        "version": 1,
        "created_at": datetime.now(tz=JST).isoformat(),
        "target_cases": target,
        "actual_cases": len(cases),
        "frozen_corrections_sha256": frozen["sha256"],
        "note": f"Generated by build_golden_dataset.py on {datetime.now(tz=JST).date()}",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    logger.info("Written manifest.json")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build annotator golden test set")
    ap.add_argument("--target", type=int, default=50, help="Target number of cases (default: 50)")
    ap.add_argument("--interactive", action="store_true", help="Run interactive Tier 2 spot check")
    ap.add_argument("--rebuild-frozen-only", action="store_true", help="Only rebuild frozen_corrections.json")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    sb = _get_sb()

    if args.rebuild_frozen_only:
        rebuild_frozen_only(sb)
        return 0

    if not args.interactive:
        ap.error("Please specify --interactive or --rebuild-frozen-only")

    # Build frozen corrections snapshot first
    frozen = _load_frozen_corrections(sb)

    try:
        cases = _build_interactive(sb, target=args.target)
    except KeyboardInterrupt:
        print("\nAborted.")
        return 1

    if not cases:
        logger.warning("No cases collected — golden set not written")
        return 1

    _write_cases(cases, frozen, target=args.target)
    print(f"\nGolden set ready: {len(cases)} cases in {CASES_PATH}")
    print(f"Next: python eval_annotator.py --sample 5 --output /tmp/test.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
