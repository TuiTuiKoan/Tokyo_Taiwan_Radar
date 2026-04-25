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
    "peatix",
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
    """Navigate to url and return main element inner_text (falls back to full body)."""
    try:
        page.goto(url, wait_until="networkidle", timeout=30_000)
    except PWTimeout:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    main_el = page.query_selector("main")
    return main_el.inner_text() if main_el else page.inner_text("body")


def _fetch_body_text(page, url: str) -> str:
    """Navigate to url and return full body inner_text (for JS-heavy pages like Peatix)."""
    try:
        page.goto(url, wait_until="networkidle", timeout=30_000)
    except PWTimeout:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    return page.inner_text("body")


def _extract_peatix_location(page) -> tuple[Optional[str], Optional[str]]:
    """Extract (location_name, location_address) from an already-loaded Peatix page."""

    def _safe(selector: str) -> Optional[str]:
        el = page.query_selector(selector)
        txt = el.inner_text().strip() if el else ""
        return txt or None

    loc_name = (
        _safe(".venue-name")
        or _safe(".location")
        or _safe("[class*='venue']")
    )
    # Strip leading label separators GPT/Peatix sometimes includes
    if loc_name:
        loc_name = loc_name.lstrip("：；:; \u3000会場所").strip()
    loc_addr = (
        _safe(".venue-address")
        or _safe("[class*='address']")
    )

    # Regex fallback on full body text
    page_text = page.inner_text("body")
    if not loc_name:
        loc_m = re.search(r'LOCATION\s*\n(.{3,100})', page_text)
        if loc_m:
            loc_name = loc_m.group(1).strip()
    if not loc_addr:
        addr_m = re.search(r'(?:\u3012\d{3}-\d{4}[^\n]*|\u6771\u4eac\u90fd[^\s,\uff0c\n]{3,60})', page_text)
        if addr_m:
            loc_addr = addr_m.group(0).strip()

    return loc_name or None, loc_addr or None


def run(dry_run: bool) -> None:
    load_dotenv(".env")
    sb = create_client(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    )

    # Fetch target events in two passes:
    # 1. iwafu/koryu: events with generic addresses (e.g. '東京')
    # 2. peatix: events with NULL location_address
    res_generic = (
        sb.table("events")
        .select("id,source_name,source_url,location_name,location_address")
        .eq("is_active", True)
        .in_("source_name", ["iwafu", "koryu"])
        .execute()
    )
    generic_candidates = [
        r for r in (res_generic.data or [])
        if (r.get("location_address") or "").replace("\u3000", " ").replace("\u3000", " ").strip()
        in {"東京", "東京都", "東 京", "Tokyo", "tokyo"}
    ]

    res_peatix = (
        sb.table("events")
        .select("id,source_name,source_url,location_name,location_address")
        .eq("is_active", True)
        .eq("source_name", "peatix")
        .is_("location_address", "null")
        .execute()
    )
    peatix_candidates = res_peatix.data or []

    candidates = generic_candidates + peatix_candidates

    logger.info(
        "Found %d generic-address events (iwafu/koryu) + %d null-address peatix events to backfill",
        len(generic_candidates),
        len(peatix_candidates),
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
                if source == "peatix":
                    # Peatix is JS-heavy — navigate first, then extract from live page
                    try:
                        page.goto(url, wait_until="networkidle", timeout=30_000)
                    except PWTimeout:
                        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    new_name, new_addr = _extract_peatix_location(page)
                else:
                    main_text = _fetch_main_text(page, url)
                    new_name = None
                    new_addr = None
                    if source == "iwafu":
                        val = _extract_iwafu_location(main_text)
                        new_name = val
                        new_addr = val
                    elif source == "koryu":
                        m = re.search(r'会\s*場\s*\n?\s*(.{5,120})', main_text)
                        if m:
                            val = m.group(1).strip().split("\n")[0].strip()[:120]
                            new_name = val
                            new_addr = val
            except Exception as exc:
                logger.warning("  Failed to load %s: %s", url, exc)
                time.sleep(1.5)
                continue

            # Build the update payload:
            # - Always update location_address when a new value is found
            # - Only update location_name when existing is None (don't overwrite scraped names)
            payload: dict = {}
            if new_addr:
                payload["location_address"] = new_addr
            if new_name and not event.get("location_name"):
                payload["location_name"] = new_name

            if payload:
                logger.info(
                    "  → name=%r addr=%r",
                    payload.get("location_name", "(keep)"),
                    payload.get("location_address", "(keep)"),
                )
                updates.append(
                    {
                        "id": eid,
                        "source_name": source,
                        "old_address": event.get("location_address"),
                        "payload": payload,
                    }
                )
            else:
                logger.info("  → No venue found, skipping")

            time.sleep(1.5)

        browser.close()

    logger.info(
        "Backfill summary: %d/%d events with update data", len(updates), len(candidates)
    )

    for u in updates:
        logger.info(
            "  [%s] %s  old_addr=%r → %s",
            u["source_name"],
            u["id"][:8],
            u["old_address"],
            u["payload"],
        )

    if dry_run:
        logger.info("DRY RUN — no DB changes made.")
        return

    # Apply updates
    applied = 0
    for u in updates:
        try:
            sb.table("events").update(u["payload"]).eq("id", u["id"]).execute()
            applied += 1
        except Exception as exc:
            logger.error("  Failed to update %s: %s", u["id"][:8], exc)

    logger.info("Applied %d location updates to DB.", applied)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill location fields for generic-address events")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
