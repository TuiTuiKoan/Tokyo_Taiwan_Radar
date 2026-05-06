"""
pull_all.py — External stats orchestrator.

Runs all three pullers in sequence:
  1. JNTO 訪日外客統計 (monthly, per year)
  2. MOJ ISA 在留外国人統計 (biannual: June + December)
  3. e-Stat 人口推計 都道府県別 (annual)

Usage:
    python pull_all.py [--dry-run] [--source jnto|moj|population] [--year YYYY]
    python pull_all.py --dry-run           # Run all, no DB writes
    python pull_all.py --source jnto       # JNTO only (latest year)
    python pull_all.py --source moj        # MOJ only (latest period)
    python pull_all.py --source population # Population only (latest year)
"""
from __future__ import annotations

import argparse
import datetime
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
from supabase import create_client

from external_stats.jnto_visitors import JntoVisitorsPuller
from external_stats.moj_residents import MojResidentsPuller
from external_stats.estat_population import EstatPopulationPuller

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).parent.parent / ".env")


def _supabase_client():
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def run_jnto(sb, dry_run: bool, year: int | None = None) -> None:
    """Pull JNTO 訪日外客月別データ（台灣）for the given year (default: current year)."""
    target_year = year or datetime.date.today().year
    logger.info("=== JNTO: year %d ===", target_year)
    puller = JntoVisitorsPuller(sb, dry_run=dry_run)
    try:
        raw = puller.fetch(year=target_year)
        records = puller.parse(raw, year=target_year)
        puller.upsert(puller._table_name(), records)
        logger.info("JNTO: %d records", len(records))
    except Exception as exc:
        logger.error("JNTO failed for year %d: %s", target_year, exc)
        raise


def run_moj(sb, dry_run: bool, year: int | None = None) -> None:
    """Pull MOJ ISA 在留台湾人都道府県別 for the latest available period."""
    puller = MojResidentsPuller(sb, dry_run=dry_run)
    today = datetime.date.today()
    target_year = year or today.year

    # MOJ publishes June-end data ~September, December-end data ~March
    # Try December first, then June
    periods_to_try: list[tuple[int, int]]
    if today.month >= 9:
        # After September: December of previous year and June of previous year are published
        periods_to_try = [
            (target_year - 1, 12),
            (target_year - 1, 6),
        ]
    else:
        # January–August: December from 2 years ago and June of previous year
        periods_to_try = [
            (target_year - 1, 6),
            (target_year - 2, 12),
        ]

    logger.info("=== MOJ ISA: trying periods %s ===", periods_to_try)
    total = 0
    for y, p in periods_to_try:
        try:
            raw = puller.fetch(year=y, period=p)
            records = puller.parse(raw, year=y, period=p)
            puller.upsert(puller._table_name(), records)
            total += len(records)
            logger.info("MOJ: %d records for %d-%02d", len(records), y, p)
        except Exception as exc:
            logger.warning("MOJ: skipping %d-%02d: %s", y, p, exc)
    if total == 0:
        raise RuntimeError("MOJ: no data could be fetched")


def run_population(sb, dry_run: bool, year: int | None = None) -> None:
    """Pull e-Stat 人口推計 for the latest available year (default: current year or prev)."""
    app_id = os.environ["ESTAT_APP_ID"]
    puller = EstatPopulationPuller(sb, dry_run=dry_run)

    from external_stats.estat_population import _discover_time_codes
    time_codes = _discover_time_codes(app_id)
    available_years = sorted(time_codes.keys())

    if year:
        target_year = year
    else:
        # Use latest available year
        target_year = available_years[-1] if available_years else datetime.date.today().year - 1

    logger.info("=== Population: year %d (available: %s) ===", target_year, available_years)
    try:
        raw = puller.fetch(app_id=app_id, year=target_year)
        records = puller.parse(raw, year=target_year)
        puller.upsert(puller._table_name(), records)
        logger.info("Population: %d records for year %d", len(records), target_year)
    except Exception as exc:
        logger.error("Population failed for year %d: %s", target_year, exc)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull all external stats into Supabase")
    parser.add_argument(
        "--source",
        choices=["jnto", "moj", "population"],
        help="Run only one source (default: all)",
    )
    parser.add_argument("--year", type=int, help="Target year override")
    parser.add_argument("--dry-run", action="store_true", help="Skip DB writes")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    sb = _supabase_client()

    errors: list[str] = []

    sources_to_run: list[str]
    if args.source:
        sources_to_run = [args.source]
    else:
        sources_to_run = ["jnto", "moj", "population"]

    for source in sources_to_run:
        try:
            if source == "jnto":
                run_jnto(sb, dry_run=args.dry_run, year=args.year)
            elif source == "moj":
                run_moj(sb, dry_run=args.dry_run, year=args.year)
            elif source == "population":
                run_population(sb, dry_run=args.dry_run, year=args.year)
        except Exception as exc:
            logger.error("Source %s failed: %s", source, exc)
            errors.append(f"{source}: {exc}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
