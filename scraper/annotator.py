"""
AI-powered event annotator using OpenAI GPT-4o-mini.

Processes events with annotation_status='pending' in the database:
  1. Sends raw_title + raw_description to GPT-4o-mini
  2. Extracts structured fields (dates, location, pricing, categories)
  3. Translates name + description into ja/zh/en
  4. Detects sub-events and creates child rows
  5. Updates the event row with annotation_status='annotated'

Usage:
    python annotator.py          # Annotate all pending events
    python annotator.py --all    # Re-annotate ALL events
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid categories (must match web/lib/types.ts)
# ---------------------------------------------------------------------------
VALID_CATEGORIES = [
    "movie", "music", "senses", "retail", "nature",
    "tech", "tourism", "culture", "gender", "geopolitics", "report",
]

# ---------------------------------------------------------------------------
# GPT System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an expert event data analyst specializing in Taiwan-related cultural events in Japan.

Given the raw title and description of an event (usually in Japanese), extract structured data and translate into three languages.

CRITICAL DATE EXTRACTION RULES:
1. You MUST extract dates from ALL parts of the text: title, body, headers, and footers.
2. Look for date patterns like: 2025年10月8日, 10/8, 10月8日, 2025-10-08, etc.
3. If the event spans multiple days (e.g., "10/8 and 10/10"), start_date = first date, end_date = last date.
4. If only one date is mentioned, use it as BOTH start_date AND end_date.
5. end_date MUST NOT be null if any date can be found anywhere in the text. Try harder to find dates.
6. If the title contains a date like "（10/8・10/10）", extract those dates even if the body is vague.
7. When the year is not explicitly stated, infer it from context. If unclear, assume the nearest future occurrence.
8. For ongoing exhibitions/screenings with a date range (e.g., "4月5日〜6月30日"), use the full range.

OTHER RULES:
1. If the description mentions multiple separate events/sessions with different dates (e.g., a film screening series with individual dates), list them as sub_events.
2. Categories must be from this list: movie, music, senses, retail, nature, tech, tourism, culture, gender, geopolitics, report
   - "senses" = art, exhibitions, literature, books, photography, design, workshops, creative experiences
   - "report" = event reports/recaps (only if the text IS a report about a past event, not an upcoming event)
   - An event can have multiple categories
3. Translate the event name and a concise summary description into all three languages (ja, zh, en).
4. The description should be a clean, concise summary (2-4 sentences), NOT a copy of the raw text.
5. Extract location, address, business hours, and pricing from the text if available.
6. For pricing: is_paid=false if free/無料/免費, is_paid=true if there's a fee, null if unknown.

Respond with valid JSON matching this schema:
{
  "name_ja": "Japanese event name",
  "name_zh": "Traditional Chinese event name",
  "name_en": "English event name",
  "description_ja": "Japanese summary (2-4 sentences)",
  "description_zh": "Traditional Chinese summary (2-4 sentences)",
  "description_en": "English summary (2-4 sentences)",
  "category": ["culture"],
  "start_date": "2026-01-15T00:00:00" or null,
  "end_date": "2026-01-15T00:00:00" or null,
  "location_name": "venue name" or null,
  "location_address": "full address" or null,
  "business_hours": "opening hours" or null,
  "is_paid": false or true or null,
  "price_info": "price details" or null,
  "sub_events": [
    {
      "name_ja": "sub-event name in Japanese",
      "name_zh": "sub-event name in Chinese",
      "name_en": "sub-event name in English",
      "description_ja": "brief description",
      "description_zh": "brief description",
      "description_en": "brief description",
      "start_date": "2026-02-01T00:00:00",
      "end_date": "2026-02-01T00:00:00",
      "category": ["movie"],
      "location_name": "venue" or null,
      "location_address": "address" or null,
      "business_hours": "hours" or null,
      "is_paid": false or true or null,
      "price_info": "price" or null
    }
  ]
}"""


def _get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _get_openai() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required")
    return OpenAI(api_key=api_key)


def _annotate_one(client: OpenAI, raw_title: str, raw_description: str) -> dict:
    """Send raw event data to GPT-4o-mini and return structured annotation."""
    user_content = f"Raw Title: {raw_title or '(no title)'}\n\nRaw Description:\n{raw_description or '(no description)'}"

    # Truncate very long descriptions to stay within token limits
    if len(user_content) > 12000:
        user_content = user_content[:12000] + "\n\n[... truncated ...]"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=4000,
    )

    text = response.choices[0].message.content
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Retry once with higher token budget
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=6000,
        )
        return json.loads(response.choices[0].message.content)


def _validate_categories(cats: list) -> list[str]:
    """Filter to only valid category strings."""
    return [c for c in cats if isinstance(c, str) and c in VALID_CATEGORIES] or ["culture"]


def annotate_pending_events(re_annotate_all: bool = False) -> None:
    """Fetch pending events from DB, annotate with AI, and update."""
    sb = _get_supabase()
    ai = _get_openai()

    # Fetch events to annotate
    query = sb.table("events").select("*")
    if re_annotate_all:
        query = query.eq("is_active", True)
    else:
        query = query.eq("annotation_status", "pending")

    result = query.order("created_at", desc=True).execute()
    events = result.data

    if not events:
        logger.info("No pending events to annotate.")
        return

    logger.info("Found %d events to annotate", len(events))

    for i, event in enumerate(events, 1):
        eid = event["id"]
        raw_title = event.get("raw_title") or event.get("name_ja") or ""
        raw_desc = event.get("raw_description") or event.get("description_ja") or ""

        logger.info("[%d/%d] Annotating: %s", i, len(events), raw_title[:60])

        try:
            annotation = _annotate_one(ai, raw_title, raw_desc)

            # Validate and sanitize
            categories = _validate_categories(annotation.get("category", []))

            update_data: dict[str, Any] = {
                "name_ja": annotation.get("name_ja") or raw_title,
                "name_zh": annotation.get("name_zh"),
                "name_en": annotation.get("name_en"),
                "description_ja": annotation.get("description_ja"),
                "description_zh": annotation.get("description_zh"),
                "description_en": annotation.get("description_en"),
                "category": categories,
                "start_date": annotation.get("start_date"),
                "end_date": annotation.get("end_date"),
                "location_name": annotation.get("location_name") or event.get("location_name"),
                "location_address": annotation.get("location_address") or event.get("location_address"),
                "business_hours": annotation.get("business_hours") or event.get("business_hours"),
                "is_paid": annotation.get("is_paid") if annotation.get("is_paid") is not None else event.get("is_paid"),
                "price_info": annotation.get("price_info") or event.get("price_info"),
                "annotation_status": "annotated",
                "annotated_at": datetime.utcnow().isoformat(),
            }

            # Ensure end_date is not null when start_date exists
            if update_data["start_date"] and not update_data["end_date"]:
                update_data["end_date"] = update_data["start_date"]

            sb.table("events").update(update_data).eq("id", eid).execute()
            logger.info("  ✓ annotated (categories: %s)", categories)

            # Handle sub-events
            sub_events = annotation.get("sub_events", [])
            for j, sub in enumerate(sub_events):
                sub_cats = _validate_categories(sub.get("category", categories))
                sub_start = sub.get("start_date")
                sub_end = sub.get("end_date") or sub_start

                sub_row = {
                    "source_name": event["source_name"],
                    "source_id": f"{event['source_id']}_sub{j+1}",
                    "source_url": event["source_url"],
                    "original_language": event.get("original_language", "ja"),
                    "name_ja": sub.get("name_ja", ""),
                    "name_zh": sub.get("name_zh"),
                    "name_en": sub.get("name_en"),
                    "description_ja": sub.get("description_ja"),
                    "description_zh": sub.get("description_zh"),
                    "description_en": sub.get("description_en"),
                    "category": sub_cats,
                    "start_date": sub_start,
                    "end_date": sub_end,
                    "location_name": sub.get("location_name") or update_data["location_name"],
                    "location_address": sub.get("location_address") or update_data["location_address"],
                    "business_hours": sub.get("business_hours") or update_data["business_hours"],
                    "is_paid": sub.get("is_paid") if sub.get("is_paid") is not None else update_data["is_paid"],
                    "price_info": sub.get("price_info") or update_data["price_info"],
                    "is_active": True,
                    "parent_event_id": eid,
                    "raw_title": sub.get("name_ja", ""),
                    "raw_description": sub.get("description_ja"),
                    "annotation_status": "annotated",
                    "annotated_at": datetime.utcnow().isoformat(),
                }

                sb.table("events").upsert(
                    sub_row, on_conflict="source_name,source_id"
                ).execute()
                logger.info("  + sub-event %d: %s", j + 1, sub.get("name_ja", "")[:50])

        except Exception as exc:
            logger.error("  ✗ annotation failed: %s", exc)
            sb.table("events").update({
                "annotation_status": "error",
            }).eq("id", eid).execute()

        # Rate limiting — avoid hitting OpenAI too fast
        time.sleep(0.5)

    logger.info("Annotation complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    re_all = "--all" in sys.argv
    annotate_pending_events(re_annotate_all=re_all)
