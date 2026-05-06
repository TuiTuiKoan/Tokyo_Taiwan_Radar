#!/usr/bin/env python3
"""
Backfill `organizers` and `venues` entity tables (migration 050).

Algorithm:
  1. Pull distinct organizer (or location_name) strings from `events`.
  2. Cluster via `merger._normalize()` + SequenceMatcher ratio ≥ 0.92.
  3. Per cluster: create one entity row (canonical = longest variant; others → aliases).
  4. Backfill events.organizer_id (or venue_id) by matching events to clusters.

The original `events.organizer` / `events.location_name` columns are NEVER
deleted — they remain as audit trail. Entity tables augment, not replace.

Run AFTER migration 050 has been applied via Supabase Dashboard:
    cd scraper && source ../.venv/bin/activate && \
        python backfill_entities.py --type organizers --dry-run
    python backfill_entities.py --type organizers
    python backfill_entities.py --type venues --dry-run
    python backfill_entities.py --type venues
"""
from __future__ import annotations

import argparse
import logging
import os
from collections import defaultdict
from difflib import SequenceMatcher

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from supabase import create_client

from merger import _normalize  # reuse name normalization rules

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.92


def _cluster(strings: list[str]) -> list[list[str]]:
    """
    Greedy clustering: for each input string, attach to first existing cluster
    where SequenceMatcher.ratio() of normalized forms ≥ threshold; else open
    a new cluster. Order-preserving (longest-first input gives best canonical).
    """
    # Sort by length desc so the canonical anchor is the longest variant.
    ordered = sorted(set(s for s in strings if s and s.strip()), key=lambda s: (-len(s), s))
    clusters: list[list[str]] = []
    norms: list[str] = []
    for s in ordered:
        n = _normalize(s)
        if not n:
            continue
        attached = False
        for idx, anchor_n in enumerate(norms):
            if SequenceMatcher(None, n, anchor_n).ratio() >= SIMILARITY_THRESHOLD:
                clusters[idx].append(s)
                attached = True
                break
        if not attached:
            clusters.append([s])
            norms.append(n)
    return clusters


def _fetch_distinct_strings(sb, column: str) -> list[str]:
    """Pull distinct non-empty values from events.<column>."""
    # Supabase doesn't expose DISTINCT directly via PostgREST; pull all & uniq.
    resp = sb.table("events").select(f"id,{column}").execute()
    seen = set()
    out: list[str] = []
    for row in resp.data:
        v = (row.get(column) or "").strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _build_event_count_map(sb, column: str) -> dict[str, int]:
    """For reporting: how many events use each distinct string."""
    resp = sb.table("events").select(f"id,{column}").execute()
    counts: dict[str, int] = defaultdict(int)
    for row in resp.data:
        v = (row.get(column) or "").strip()
        if v:
            counts[v] += 1
    return counts


def backfill_organizers(sb, dry_run: bool) -> None:
    strings = _fetch_distinct_strings(sb, "organizer")
    counts = _build_event_count_map(sb, "organizer")
    logger.info("Found %d distinct organizer strings", len(strings))

    clusters = _cluster(strings)
    multi = [c for c in clusters if len(c) > 1]
    logger.info("Clustered into %d organizer groups (%d with ≥2 variants)",
                len(clusters), len(multi))

    # Print summary
    for c in sorted(multi, key=lambda c: -sum(counts.get(s, 0) for s in c))[:20]:
        canonical = c[0]
        events_total = sum(counts.get(s, 0) for s in c)
        logger.info("  %s [%d events, %d aliases]", canonical[:40], events_total, len(c) - 1)
        for alias in c[1:]:
            logger.info("    ↳ %s [%d events]", alias[:40], counts.get(alias, 0))

    if dry_run:
        logger.info("(dry-run — no DB writes)")
        return

    # Insert / upsert entity rows + backfill FKs
    inserted = 0
    updated_events = 0
    for c in clusters:
        canonical = c[0]
        aliases = c[1:]
        try:
            resp = (
                sb.table("organizers")
                .upsert(
                    {"canonical_name_ja": canonical, "aliases": aliases},
                    on_conflict="canonical_name_ja",
                )
                .execute()
            )
            entity_id = resp.data[0]["id"] if resp.data else None
        except Exception as exc:
            logger.error("  ✗ insert organizer %r: %s", canonical[:40], exc)
            continue
        if not entity_id:
            continue
        inserted += 1

        # Backfill organizer_id on every event whose organizer string is in the cluster.
        all_variants = [canonical] + aliases
        try:
            res = (
                sb.table("events")
                .update({"organizer_id": entity_id})
                .in_("organizer", all_variants)
                .execute()
            )
            updated_events += len(res.data or [])
        except Exception as exc:
            logger.error("  ✗ backfill organizer_id for cluster %r: %s", canonical[:40], exc)

    logger.info("Inserted/upserted %d organizer entities; updated %d events with organizer_id",
                inserted, updated_events)


def backfill_venues(sb, dry_run: bool) -> None:
    strings = _fetch_distinct_strings(sb, "location_name")
    counts = _build_event_count_map(sb, "location_name")
    logger.info("Found %d distinct location_name strings", len(strings))

    clusters = _cluster(strings)
    multi = [c for c in clusters if len(c) > 1]
    logger.info("Clustered into %d venue groups (%d with ≥2 variants)",
                len(clusters), len(multi))

    for c in sorted(multi, key=lambda c: -sum(counts.get(s, 0) for s in c))[:20]:
        canonical = c[0]
        events_total = sum(counts.get(s, 0) for s in c)
        logger.info("  %s [%d events, %d aliases]", canonical[:40], events_total, len(c) - 1)
        for alias in c[1:]:
            logger.info("    ↳ %s [%d events]", alias[:40], counts.get(alias, 0))

    if dry_run:
        logger.info("(dry-run — no DB writes)")
        return

    inserted = 0
    updated_events = 0
    for c in clusters:
        canonical = c[0]
        aliases = c[1:]
        try:
            resp = (
                sb.table("venues")
                .upsert(
                    {"canonical_name_ja": canonical, "aliases": aliases},
                    on_conflict="canonical_name_ja",
                )
                .execute()
            )
            entity_id = resp.data[0]["id"] if resp.data else None
        except Exception as exc:
            logger.error("  ✗ insert venue %r: %s", canonical[:40], exc)
            continue
        if not entity_id:
            continue
        inserted += 1

        all_variants = [canonical] + aliases
        try:
            res = (
                sb.table("events")
                .update({"venue_id": entity_id})
                .in_("location_name", all_variants)
                .execute()
            )
            updated_events += len(res.data or [])
        except Exception as exc:
            logger.error("  ✗ backfill venue_id for cluster %r: %s", canonical[:40], exc)

    logger.info("Inserted/upserted %d venue entities; updated %d events with venue_id",
                inserted, updated_events)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--type", choices=["organizers", "venues"], required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    if args.type == "organizers":
        backfill_organizers(sb, args.dry_run)
    else:
        backfill_venues(sb, args.dry_run)


if __name__ == "__main__":
    main()
