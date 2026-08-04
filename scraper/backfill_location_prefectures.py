#!/usr/bin/env python3
"""
Backfill location_prefectures for parent + sub events.

Three passes (order matters):
  1. Multi-aggregation for parents — if sub-event addresses span ≥2 prefectures,
     write the sorted array to the parent.
  2. Single-row pass (default ON) — for any row (parent or sub) with
     location_prefectures IS NULL and a usable own address, write [pref].
     Use --no-single to skip this pass (legacy behavior).
  3. Sub-event parent-address fallback — for sub-events with NO own address
     but whose parent has a usable address, inherit prefecture from parent
     (writes location_prefectures only; does NOT modify location_address).

Run AFTER migration 012 has been applied in Supabase Dashboard. Dry-run is the
DEFAULT (no DB writes); pass --apply to persist:
    cd scraper && source ../.venv/bin/activate && python backfill_location_prefectures.py --apply [--no-single]

NOTE: automated callers (.github/workflows/scraper.yml) must pass --apply, or the
daily backfill becomes a no-op dry-run.
"""
import argparse
import os
import logging
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from supabase import create_client

from location_region import (
    _CITY_TO_PREF,
    _COUNTRY_PREFIX_RE,
    _EN_TO_PREF,
    _JP_PREF_RE,
    _LABEL_PREFIX_RE,
    _POSTAL_PREFIX_RE,
    _TW_ALIASES,
    _TW_START_RE,
    _TW_SUFFIX_RE,
    _normalize_address,
    extract_prefecture,
)
from publication_rules import is_pure_publication_in_db, partition_pure_publications

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def fetch_all_rows(
    sb,
    table: str,
    columns: str,
    *,
    apply_filters=None,
    order_col: str = "id",
    page_size: int = 1000,
    label: str = "",
) -> list[dict]:
    """Fetch ALL rows for a query, paginating past Supabase's ~1000-row cap.

    Supabase silently caps a single response at 1000 rows, so an unpaginated
    ``.execute()`` drops later events. This reads the exact count, then
    accumulates fixed-size pages via ``.range()`` ordered by ``order_col`` for
    stable slicing, logging per-page / exact / accumulated counts.

    ``apply_filters`` is an optional callable applied to BOTH the count-head
    request and each page request, e.g.
    ``lambda q: q.not_.is_("parent_event_id", "null")``.
    """
    tag = label or table

    count_q = sb.table(table).select(order_col, count="exact", head=True)
    if apply_filters:
        count_q = apply_filters(count_q)
    exact = count_q.execute().count
    logger.info("  [%s] exact count = %s", tag, exact)

    rows: list[dict] = []
    start = 0
    while True:
        page_q = sb.table(table).select(columns)
        if apply_filters:
            page_q = apply_filters(page_q)
        page = (
            page_q.order(order_col)
            .range(start, start + page_size - 1)
            .execute()
            .data
        ) or []
        rows.extend(page)
        logger.info(
            "  [%s] page @%d: +%d (accumulated %d)", tag, start, len(page), len(rows)
        )
        if len(page) < page_size:
            break
        start += page_size

    if exact is not None and len(rows) != exact:
        logger.warning("  [%s] accumulated %d != exact count %d", tag, len(rows), exact)
    return rows


def _verify_write(sb, event_id: str, expected: list[str]) -> None:
    """Re-read location_prefectures after a write; warn on mismatch (G2 step 7).

    This backfill only writes the events table (no field_corrections rows), so
    there is no FC row to re-read.
    """
    try:
        rb = (
            sb.table("events")
            .select("location_prefectures")
            .eq("id", event_id)
            .execute()
            .data
        )
        got = rb[0].get("location_prefectures") if rb else None
        if got != expected:
            logger.warning(
                "  read-back mismatch id=%s: wrote %s got %s", event_id, expected, got
            )
    except Exception as e:  # read-back must never abort the backfill
        logger.warning("  read-back failed id=%s: %s", event_id, e)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-single", action="store_true",
                        help="Skip single-row + sub-event passes; only do multi-aggregation for parents (legacy).")
    parser.add_argument("--include-single", action="store_true",
                        help="(deprecated, kept for compat) Single-row pass is now default ON.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Force dry-run (no DB writes). Dry-run is already the DEFAULT.")
    parser.add_argument("--apply", action="store_true",
                        help="Persist changes to Supabase. Without --apply this is a dry-run.")
    args = parser.parse_args()

    do_single = not args.no_single
    # Dry-run is the DEFAULT; writes require an explicit --apply. --dry-run still
    # forces dry-run and wins if both are given (safety-first).
    dry_run = args.dry_run or not args.apply
    if dry_run and not args.dry_run:
        logger.info("No --apply flag: DRY-RUN mode (no DB writes). Pass --apply to persist.")

    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    # Fetch ALL sub-events with location_address (including inactive — backfill
    # historical rows so reports & roadmap reflect total fill rate, not just active).
    logger.info("Fetching sub-events (aggregation pass)...")
    subs_data = fetch_all_rows(
        sb,
        "events",
        "parent_event_id,location_address,event_form",
        apply_filters=lambda q: q.not_.is_("parent_event_id", "null"),
        label="sub-agg",
    )
    subs_data, subs_publications = partition_pure_publications(subs_data)
    if subs_publications:
        logger.info("  [sub-agg] skipped %d pure publication rows", len(subs_publications))

    # Aggregate prefectures per parent
    parent_prefectures: dict[str, set[str]] = defaultdict(set)
    for s in subs_data:
        pid = s["parent_event_id"]
        pref = extract_prefecture(s["location_address"])
        if pref:
            parent_prefectures[pid].add(pref)

    # Fetch ALL parent events (parent_event_id IS NULL), regardless of is_active.
    # Filter `location_prefectures IS NULL` is enforced row-by-row below to keep
    # idempotency (we still want to emit `skipped_existing` counter for visibility).
    logger.info("Fetching parent events (all is_active states)...")
    parents = fetch_all_rows(
        sb,
        "events",
        "id,name_ja,location_address,location_prefectures,event_form",
        apply_filters=lambda q: q.is_("parent_event_id", "null"),
        label="parents",
    )
    parents, parent_publications = partition_pure_publications(parents)
    if parent_publications:
        logger.info("  [parents] skipped %d pure publication rows", len(parent_publications))

    scanned = len(parents)
    multi_updated = 0
    single_updated = 0
    skipped_existing = 0
    skipped_no_pref = 0

    # Build parent_id → location_address map for sub-event fallback (pass 3).
    parent_addr_map: dict[str, str | None] = {p["id"]: p.get("location_address") for p in parents}

    # ----- Pass 1: parents — multi-aggregation OR own-address single-row -----
    for p in parents:
        pid = p["id"]
        name = (p.get("name_ja") or pid)[:50]
        if p.get("location_prefectures"):
            skipped_existing += 1
            continue

        agg = parent_prefectures.get(pid, set())
        new_value: list[str] | None = None
        kind = ""
        if len(agg) >= 2:
            new_value = sorted(agg)
            kind = "multi"
        elif do_single:
            own_pref = extract_prefecture(p.get("location_address"))
            if own_pref:
                new_value = [own_pref]
                kind = "single"

        if not new_value:
            skipped_no_pref += 1
            continue

        if dry_run:
            logger.info("  [dry-run %s] PAR %s → %s", kind, name, new_value)
        else:
            if is_pure_publication_in_db(sb, pid):
                logger.warning("  SKIP pure publication (re-check): %s", pid[:8])
                continue
            try:
                sb.table("events").update({"location_prefectures": new_value}).eq("id", pid).execute()
                logger.info("  ✓ [%s] PAR %s → %s", kind, name, new_value)
                _verify_write(sb, pid, new_value)
            except Exception as e:
                logger.error("  ✗ %s: %s", pid, e)
                continue

        if kind == "multi":
            multi_updated += 1
        else:
            single_updated += 1

    # ----- Pass 2 + 3: sub-events — own address, or parent-address fallback -----
    sub_own_updated = 0
    sub_parent_fallback_updated = 0
    sub_skipped_existing = 0
    sub_skipped_no_pref = 0
    sub_scanned = 0

    if do_single:
        logger.info("Fetching sub-events (full rows for backfill)...")
        sub_rows = fetch_all_rows(
            sb,
            "events",
            "id,name_ja,parent_event_id,location_address,location_prefectures,event_form",
            apply_filters=lambda q: q.not_.is_("parent_event_id", "null"),
            label="sub-full",
        )
        sub_rows, sub_publications = partition_pure_publications(sub_rows)
        if sub_publications:
            logger.info("  [sub-full] skipped %d pure publication rows", len(sub_publications))
        sub_scanned = len(sub_rows)

        for s in sub_rows:
            sid = s["id"]
            name = (s.get("name_ja") or sid)[:50]
            if s.get("location_prefectures"):
                sub_skipped_existing += 1
                continue

            own_addr = s.get("location_address")
            pref = extract_prefecture(own_addr)
            kind = "sub-own"

            if not pref:
                # Parent-address fallback (do NOT modify location_address).
                parent_addr = parent_addr_map.get(s.get("parent_event_id"))
                pref = extract_prefecture(parent_addr)
                kind = "sub-parent" if pref else ""

            if not pref:
                sub_skipped_no_pref += 1
                continue

            new_value = [pref]
            if dry_run:
                logger.info("  [dry-run %s] SUB %s → %s", kind, name, new_value)
            else:
                if is_pure_publication_in_db(sb, sid):
                    logger.warning("  SKIP pure publication (re-check): %s", sid[:8])
                    continue
                try:
                    sb.table("events").update({"location_prefectures": new_value}).eq("id", sid).execute()
                    logger.info("  ✓ [%s] SUB %s → %s", kind, name, new_value)
                    _verify_write(sb, sid, new_value)
                except Exception as e:
                    logger.error("  ✗ %s: %s", sid, e)
                    continue

            if kind == "sub-own":
                sub_own_updated += 1
            else:
                sub_parent_fallback_updated += 1

    logger.info("=" * 60)
    logger.info("Scanned parents:               %d", scanned)
    logger.info("  Multi-city updated:          %d", multi_updated)
    logger.info("  Single-city updated:         %d", single_updated)
    logger.info("  Skipped (already set):       %d", skipped_existing)
    logger.info("  Skipped (no prefecture):     %d", skipped_no_pref)
    logger.info("Scanned sub-events:            %d", sub_scanned)
    logger.info("  Own-address updated:         %d", sub_own_updated)
    logger.info("  Parent-address updated:      %d", sub_parent_fallback_updated)
    logger.info("  Skipped (already set):       %d", sub_skipped_existing)
    logger.info("  Skipped (no prefecture):     %d", sub_skipped_no_pref)
    if dry_run:
        logger.info("(dry-run — no DB writes; pass --apply to persist)")


if __name__ == "__main__":
    # Smoke-test the extractor: Taiwan addresses must now match.
    assert extract_prefecture("桃園市中壢區") == "桃園"
    assert extract_prefecture("台北市信義區") == "台北"
    assert extract_prefecture("新北市板橋區") == "新北"
    assert extract_prefecture("台北") == "台北"
    assert extract_prefecture("福岡市博多区博多駅前1-1-1") == "福岡県"
    assert extract_prefecture("横浜市西区") == "神奈川県"
    assert extract_prefecture("東京都渋谷区") == "東京都"
    assert extract_prefecture("北海道札幌市中央区") == "北海道"
    assert extract_prefecture("大阪府大阪市北区") == "大阪府"
    assert extract_prefecture("〒310-0015　茨城県水戸市宮町1丁目7") == "茨城県"
    assert extract_prefecture("日本、〒106-0045 東京都港区麻布十番") == "東京都"
    assert extract_prefecture("港区麻布十番２丁目") == "東京都"
    assert extract_prefecture("渋谷区猿楽町17-10") == "東京都"
    assert extract_prefecture("〒338-8506 さいたま市中央区上峰3-15-1") == "埼玉県"
    assert extract_prefecture("高知市五台山4200-6") == "高知県"
    assert extract_prefecture("4-1-1 Miyoshi, Koto-ku, Tokyo 135-0022") == "東京都"
    assert extract_prefecture("津市本町1-1") == "三重県"
    assert extract_prefecture("那覇市首里") == "沖縄県"
    assert extract_prefecture("オンライン") is None
    main()
