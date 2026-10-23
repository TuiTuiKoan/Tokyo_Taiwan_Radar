"""
Fill location_address for upcoming active events where it is NULL or empty.

Strategy:
  - authoritative venue registry first (no model call)
  - taiwan_cultural_center: hardcoded patch (known fixed address)
  - others: GPT-4o-mini extracts address/city from raw_description

GPT rules (conservative — no hallucination):
  - Return full address if one is stated in the text
  - Return only city/region if that's all that's mentioned
  - Return null if no location info found

Usage:
    cd scraper
    python enrich_location.py --dry-run   # preview without writing
    python enrich_location.py             # write to DB
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import llm_cache
from enrich_addresses import registry_address
from llm_client import finish, get_client
from supabase import create_client

from publication_rules import is_pure_publication_in_db, partition_pure_publications

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TCC_ADDRESS = "東京都港区虎ノ門1-1-12"

CACHE_STEP = "location_extract"
RETRY_AFTER_DAYS = 30
JST = timezone(timedelta(hours=9))


SYSTEM_PROMPT = """You are a data extraction assistant.

Given an event description (in Japanese or Chinese), extract the venue location.

Rules:
1. If a full address is explicitly stated (e.g., 東京都渋谷区... or 〒xxx-xxxx...), return it.
2. If only a city or region is mentioned (e.g., 東京, 台北, 横浜, 大阪), return just that city name.
3. If the event is clearly online/virtual (オンライン, Zoom, etc.), return "オンライン".
4. If no location information can be found, return null.
5. DO NOT invent, guess, or hallucinate addresses. When in doubt, return null.
6. LOCATION ADDRESS RULE — IDENTICAL CHECK: If the address you would return is the same
   text as the venue name (e.g., venue=「仙六屋カフェ」and address=「仙六屋カフェ」), return null.
   An address must be a geographic identifier (street, district, city) — not a venue name.
7. SUB-VENUE PARENT ADDRESS RULE: For sub-venues inside a larger facility
   (e.g., 「○○ビル2階 大会議室」「○○S.C. 広場」), return the address of the parent
   building/facility, not the sub-space name.

Respond with valid JSON only:
{"location_address": "..." or null}"""


def extract_location(client, raw_description: str) -> str | None:
    """Ask GPT-4o-mini to extract location from raw_description."""
    truncated = raw_description[:3000]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Event description:\n\n{truncated}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=200,
    )
    text = response.choices[0].message.content
    data = json.loads(text)
    return data.get("location_address")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    args = parser.parse_args()

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    ai = get_client("enrich.location")

    today = datetime.now(JST).date().isoformat()
    # Fetch upcoming active events with NULL or empty location_address
    res = (
        sb.table("events")
        .select(
            "id, source_name, name_ja, location_name, location_address, "
            "raw_description, event_form"
        )
        .eq("is_active", True)
        # Upcoming only: a finished event gains nothing from a new address (#360).
        .or_(f"end_date.gte.{today},and(end_date.is.null,start_date.gte.{today})")
        .execute()
    )
    all_events = res.data
    targets = [
        e for e in all_events
        if not e.get("location_address") or e["location_address"].strip() == ""
    ]
    targets, publications = partition_pure_publications(targets)
    if publications:
        logger.info("Skipped %d pure publication events (no venue by policy)", len(publications))

    logger.info("Found %d active events with NULL/empty location_address", len(targets))

    updated = 0

    # --- Registry first: an authoritative venue needs no model call (#360) ---
    remaining = []
    for event in targets:
        patch = registry_address((event.get("location_name") or "").strip()) if event.get("location_name") else None
        if not patch:
            remaining.append(event)
            continue
        logger.info("Registry: %s → %s", (event.get("name_ja") or event["id"])[:40], patch["location_address"])
        if not args.dry_run and not is_pure_publication_in_db(sb, event["id"]):
            sb.table("events").update(patch).eq("id", event["id"]).execute()
            updated += 1
    targets = remaining

    # Events the model already looked at, with no answer, are not sent again for a while.
    tried = llm_cache.seen(sb, CACHE_STEP, [e["id"] for e in targets], max_age_days=RETRY_AFTER_DAYS)
    if tried:
        logger.info("Skipped %d events tried within %d days", len(tried), RETRY_AFTER_DAYS)
        targets = [e for e in targets if e["id"] not in tried]

    logger.info("  GPT extraction for all: %d", len(targets))

    # --- All events: GPT extraction ---
    # For taiwan_cultural_center, fall back to TCC HQ address only when GPT returns null
    for i, event in enumerate(targets, 1):
        name = event.get("name_ja") or event.get("id")[:8]
        raw_desc = event.get("raw_description") or ""

        if not raw_desc.strip():
            # TCC fallback when no description
            if event.get("source_name") == "taiwan_cultural_center":
                addr = TCC_ADDRESS
                logger.info("[%d/%d] TCC fallback (no desc): %s → %s", i, len(targets), name[:40], addr)
                if not args.dry_run:
                    if is_pure_publication_in_db(sb, event["id"]):
                        logger.warning("  SKIP pure publication (re-check): %s", event["id"][:8])
                    else:
                        sb.table("events").update({"location_address": addr}).eq("id", event["id"]).execute()
                        updated += 1
            else:
                logger.info("[%d/%d] SKIP (no raw_description): %s", i, len(targets), name[:40])
            continue

        logger.info("[%d/%d] Extracting: %s", i, len(targets), name[:40])
        try:
            addr = extract_location(ai, raw_desc)
        except Exception as exc:
            logger.warning("  GPT error: %s", exc)
            # A failed call is not an answer: leave no mark so the next run retries it.
            time.sleep(0.5)
            continue

        # TCC fallback: if GPT returns null, use hardcoded HQ address
        if addr is None and event.get("source_name") == "taiwan_cultural_center":
            addr = TCC_ADDRESS
            logger.info("  → %s (TCC fallback)", addr)
        else:
            logger.info("  → %s", addr)

        if not args.dry_run:
            llm_cache.record(sb, CACHE_STEP, event["id"], "applied" if addr else "no_result")

        if addr and not args.dry_run:
            # Guard: skip if extracted address is identical to venue name
            venue = (event.get("location_name") or "").strip()
            if venue and addr.strip() == venue:
                logger.warning("  SKIP identical (address == venue name): %s", addr)
            elif is_pure_publication_in_db(sb, event["id"]):
                logger.warning("  SKIP pure publication (re-check): %s", event["id"][:8])
            else:
                sb.table("events").update({"location_address": addr}).eq("id", event["id"]).execute()
                updated += 1

        time.sleep(0.5)

    mode = "DRY RUN — no changes written" if args.dry_run else f"Done. Updated {updated} rows."
    logger.info(mode)


if __name__ == "__main__":
    main()
    finish()
