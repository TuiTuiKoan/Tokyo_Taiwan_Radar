"""
Backfill location_name / location_address for events whose current address is a
generic prefecture label ("東京", "東京都") rather than a real venue.

Currently targets:
  - iwafu events where location_address IN ('東京', '東京都')

Strategy:
  - Visits each event's source_url with Playwright
  - Extracts 場所：<venue> pattern from the main page text
  - Updates ONLY location_name and location_address — never touches name/description/translations

Usage:
  python backfill_locations.py            # apply changes to DB
  python backfill_locations.py --dry-run  # preview only, no DB writes
"""

import argparse
import logging
import os
import re
import time
from typing import Optional

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from supabase import create_client

load_dotenv(".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Exact values stored in DB that indicate a generic/prefecture-level address
# iwafu stores "東 京" (with a full-width space) when no real venue was found
_GENERIC_ADDRESSES = {"東京", "東京都", "東\u3000京", "東 京", "Tokyo", "tokyo"}

# Sources to backfill and their detection rules
_SOURCES = [
    "iwafu",
    "koryu",
]


def _extract_iwafu_location(main_text: str) -> Optional[str]:
    """Extract 場所：<venue> from iwafu detail page text."""
    m = re.search(
        r'場所[：:]\s*(.+?)(?:\n|交通手段|Q&A|https?://|$)', main_text, re.DOTALL
    )
    if m:
        return m.group(1).strip()
    return None


def _fetch_main_text(page, url: str) -> str:
    """Navigate to url and return main element inner_text."""
    try:
        page.goto(url, wait_until="networkidle", timeout=30_000)
    except PWTimeout:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    main_el = page.query_selector("main")
    return main_el.inner_text() if main_el else ""


def run(dry_run: bool) -> None:
    load_dotenv(".env")
    sb = create_client(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    )

    # Fetch target events — use broad select + client-side filter
    # because iwafu stores "東 京" (with extra space) which may vary
    res = (
        sb.table("events")
        .select("id,source_name,source_url,location_name,location_address")
        .eq("is_active", True)
        .in_("source_name", _SOURCES)
        .execute()
    )
    candidates = [
        r for r in (res.data or [])
        if (r.get("location_address") or "").replace("\u3000", " ").replace("　", " ").strip()
        in {"東京", "東京都", "東 京", "Tokyo", "tokyo"}
    ]

    logger.info(
        "Found %d events with generic address (%s) to backfill",
        len(candidates),
        ", ".join(_GENERIC_ADDRESSES),
    )

    if not candidates:
        logger.info("Nothing to do.")
        return

    updates: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for event in candidates:
            eid = event["id"]
            url = event["source_url"]
            source = event["source_name"]

            logger.info("Processing %s %s …", source, url[-40:])
            try:
                main_text = _fetch_main_text(page, url)
            except Exception as exc:
                logger.warning("  Failed to load %s: %s", url, exc)
                time.sleep(1.5)
                continue

            new_location: Optional[str] = None

            if source == "iwafu":
                new_location = _extract_iwafu_location(main_text)
            elif source == "koryu":
                # koryu: look for 会場 section
                m = re.search(r'会\s*場\s*\n?\s*(.{5,120})', main_text)
                if m:
                    new_location = m.group(1).strip().split("\n")[0].strip()[:120]

            if new_location:
                logger.info("  → %s", new_location)
                updates.append(
                    {
                        "id": eid,
                        "source_name": source,
                        "old_address": event.get("location_address"),
                        "new_location": new_location,
                    }
                )
            else:
                logger.info("  → No venue found, skipping")

            time.sleep(1.5)

        browser.close()

    logger.info(
        "Backfill summary: %d/%d events with new venue data", len(updates), len(candidates)
    )

    for u in updates:
        logger.info(
            "  [%s] %s  %r → %r",
            u["source_name"],
            u["id"][:8],
            u["old_address"],
            u["new_location"],
        )

    if dry_run:
        logger.info("DRY RUN — no DB changes made.")
        return

    # Apply updates
    applied = 0
    for u in updates:
        try:
            sb.table("events").update(
                {
                    "location_name": u["new_location"],
                    "location_address": u["new_location"],
                }
            ).eq("id", u["id"]).execute()
            applied += 1
        except Exception as exc:
            logger.error("  Failed to update %s: %s", u["id"][:8], exc)

    logger.info("Applied %d location updates to DB.", applied)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill location fields for generic-address events")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
