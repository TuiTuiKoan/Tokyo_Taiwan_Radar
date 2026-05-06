#!/usr/bin/env python3
"""
One-off cluster review tool — list candidate organizer/venue clusters with
member counts so a human can verify before committing to backfill_entities.py.

Usage:
    python _oneoff_review_organizer_clusters.py --type organizers
    python _oneoff_review_organizer_clusters.py --type venues
    python _oneoff_review_organizer_clusters.py --type organizers --threshold 0.85

Output: prints all clusters with ≥2 variants. Higher event count → higher
priority for human review (a wrong merge there hurts more rows).
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

from merger import _normalize

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _cluster_with_threshold(strings: list[str], threshold: float) -> list[list[str]]:
    ordered = sorted(set(s for s in strings if s and s.strip()), key=lambda s: (-len(s), s))
    clusters: list[list[str]] = []
    norms: list[str] = []
    for s in ordered:
        n = _normalize(s)
        if not n:
            continue
        attached = False
        for idx, anchor_n in enumerate(norms):
            if SequenceMatcher(None, n, anchor_n).ratio() >= threshold:
                clusters[idx].append(s)
                attached = True
                break
        if not attached:
            clusters.append([s])
            norms.append(n)
    return clusters


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--type", choices=["organizers", "venues"], required=True)
    parser.add_argument("--threshold", type=float, default=0.92,
                        help="Similarity threshold (default 0.92)")
    parser.add_argument("--show-all", action="store_true",
                        help="Show single-member clusters too (default: only ≥2 variants)")
    args = parser.parse_args()

    column = "organizer" if args.type == "organizers" else "location_name"

    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    resp = sb.table("events").select(f"id,{column}").execute()
    counts: dict[str, int] = defaultdict(int)
    for row in resp.data:
        v = (row.get(column) or "").strip()
        if v:
            counts[v] += 1

    strings = list(counts.keys())
    logger.info("Distinct %s strings: %d (across %d events)",
                column, len(strings), sum(counts.values()))

    clusters = _cluster_with_threshold(strings, args.threshold)
    multi = [c for c in clusters if len(c) > 1]
    logger.info("Clusters: total=%d, multi-variant=%d, threshold=%.2f",
                len(clusters), len(multi), args.threshold)
    logger.info("=" * 70)

    target_clusters = clusters if args.show_all else multi
    for c in sorted(target_clusters, key=lambda c: -sum(counts.get(s, 0) for s in c)):
        canonical = c[0]
        total = sum(counts.get(s, 0) for s in c)
        logger.info("\n[%d events] CANONICAL: %s", total, canonical)
        for alias in c[1:]:
            logger.info("    ↳ ALIAS [%d ev]: %s", counts.get(alias, 0), alias)


if __name__ == "__main__":
    main()
