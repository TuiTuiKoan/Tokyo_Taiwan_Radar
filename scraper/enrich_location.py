"""
One-time script: fill location_address for active events where it is NULL or empty.

Strategy:
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

import argparse
import json
import logging
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI
from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TCC_ADDRESS = "東京都港区虎ノ門1-1-12"

SYSTEM_PROMPT = """You are a data extraction assistant.

Given an event description (in Japanese or Chinese), extract the venue location.

Rules:
1. If a full address is explicitly stated (e.g., 東京都渋谷区... or 〒xxx-xxxx...), return it.
2. If only a city or region is mentioned (e.g., 東京, 台北, 横浜, 大阪), return just that city name.
3. If the event is clearly online/virtual (オンライン, Zoom, etc.), return "オンライン".
4. If no location information can be found, return null.
5. DO NOT invent, guess, or hallucinate addresses. When in doubt, return null.

Respond with valid JSON only:
{"location_address": "..." or null}"""


def extract_location(client: OpenAI, raw_description: str) -> str | None:
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
    ai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Fetch all active events with NULL or empty location_address
    res = (
        sb.table("events")
        .select("id, source_name, name_ja, location_address, raw_description")
        .eq("is_active", True)
        .execute()
    )
    all_events = res.data
    targets = [
        e for e in all_events
        if not e.get("location_address") or e["location_address"].strip() == ""
    ]

    logger.info("Found %d active events with NULL/empty location_address", len(targets))

    logger.info("  GPT extraction for all: %d", len(targets))

    updated = 0

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
            addr = None

        # TCC fallback: if GPT returns null, use hardcoded HQ address
        if addr is None and event.get("source_name") == "taiwan_cultural_center":
            addr = TCC_ADDRESS
            logger.info("  → %s (TCC fallback)", addr)
        else:
            logger.info("  → %s", addr)

        if addr and not args.dry_run:
            sb.table("events").update({"location_address": addr}).eq("id", event["id"]).execute()
            updated += 1

        time.sleep(0.5)

    mode = "DRY RUN — no changes written" if args.dry_run else f"Done. Updated {updated} rows."
    logger.info(mode)


if __name__ == "__main__":
    main()
