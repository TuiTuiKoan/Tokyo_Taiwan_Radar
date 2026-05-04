"""
enrich_addresses.py — Look up physical addresses for events with a venue name
but no location_address, using OpenAI gpt-4o-search-preview (real web search).

Usage:
    python enrich_addresses.py [--dry-run] [--source SOURCE_NAME]

Skips: gguide_tv (TV channels), events whose location_name contains オンライン.
"""

import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()


SKIP_SOURCES = {"gguide_tv"}
SKIP_VENUE_KEYWORDS = ["オンライン", "電視頻道", "online", "Online"]

SYSTEM_PROMPT = """\
You are a venue address lookup assistant.
Given a Japanese venue name, search the web and return the verified physical address in JSON.

Rules:
- Search the web for the venue's official address. Only use the result if it matches an
  authoritative source (official website, Google Maps, Tabelog, etc.).
- Address format: Japanese postal format (e.g., 東京都渋谷区神宮前1-14-30).
  For sub-venues (e.g. "○○S.C. 森のまち広場"), return the parent facility's address.
- Also provide Traditional Chinese and English translations of the address.
- If the venue is online-only, a TV channel, or you cannot find a reliable address,
  return null for all fields.
- DO NOT fabricate or guess addresses. Only return what you found via web search.

Return JSON only (no markdown code fences):
{
  "location_address": "<日本語住所 or null>",
  "location_address_zh": "<繁體中文住所 or null>",
  "location_address_en": "<English address or null>",
  "confidence": "high" | "medium" | "low"
}
"""


def lookup_address(client: OpenAI, venue_name: str) -> dict | None:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-search-preview",
            web_search_options={"search_context_size": "low"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Venue: {venue_name}"},
            ],
            # gpt-4o-search-preview does not support temperature or response_format
            max_tokens=400,
        )
        raw = response.choices[0].message.content or ""
        # Strip markdown code fences if present (search-preview may add them)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  [JSON parse error] {e} | raw={raw!r}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [OpenAI error] {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source", help="Limit to a specific source_name")
    args = parser.parse_args()

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    ai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    query = (
        sb.table("events")
        .select("id, name_ja, location_name, source_name")
        .eq("is_active", True)
        .is_("location_address", None)
        .not_.is_("location_name", None)
    )
    if args.source:
        query = query.eq("source_name", args.source)

    r = query.execute()
    candidates = [
        e for e in r.data
        if e["source_name"] not in SKIP_SOURCES
        and not any(kw in (e["location_name"] or "") for kw in SKIP_VENUE_KEYWORDS)
    ]

    print(f"Found {len(candidates)} events to enrich (dry_run={args.dry_run})")

    updated = 0
    skipped = 0

    for e in candidates:
        venue = e["location_name"]
        print(f"\n[{e['id'][:8]}] {e['source_name']} | venue={venue!r}")

        result = lookup_address(ai, venue)
        if not result:
            print("  → No result from OpenAI, skipping")
            skipped += 1
            continue

        conf = result.get("confidence", "low")
        addr_ja = result.get("location_address")

        if not addr_ja or conf == "low":
            print(f"  → Confidence={conf}, no address returned, skipping")
            skipped += 1
            continue

        print(f"  → {addr_ja} (conf={conf})")
        if result.get("location_address_zh"):
            print(f"     zh: {result['location_address_zh']}")
        if result.get("location_address_en"):
            print(f"     en: {result['location_address_en']}")

        if not args.dry_run:
            patch = {
                "location_address": addr_ja,
            }
            if result.get("location_address_zh"):
                patch["location_address_zh"] = result["location_address_zh"]
            if result.get("location_address_en"):
                patch["location_address_en"] = result["location_address_en"]
            sb.table("events").update(patch).eq("id", e["id"]).execute()
            updated += 1

        time.sleep(0.3)  # rate limit

    print(f"\nDone. updated={updated} skipped={skipped}")


if __name__ == "__main__":
    main()
