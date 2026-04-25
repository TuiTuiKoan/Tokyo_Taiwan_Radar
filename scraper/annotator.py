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

from category_feedback import load_corrections, build_feedback_prompt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid categories (must match web/lib/types.ts)
# ---------------------------------------------------------------------------
VALID_CATEGORIES = [
    "movie", "performing_arts", "senses", "retail", "nature",
    "tech", "tourism", "lifestyle_food", "books_media", "gender", "geopolitics",
    "art", "lecture", "taiwan_japan", "business", "academic", "competition",
    "indigenous", "history", "urban", "workshop", "report",
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
4. SINGLE-DAY RULE: If only one date is mentioned — or if you judge the event to be a single-day occurrence — set end_date = start_date exactly. NEVER leave end_date null when start_date is known.
5. end_date MUST NOT be null if any date can be found anywhere in the text. Try harder to find dates.
6. If the title contains a date like "（10/8・10/10）", extract those dates even if the body is vague.
7. When the year is not explicitly stated, infer it from context. If unclear, assume the nearest future occurrence.
8. For ongoing exhibitions/screenings with a date range (e.g., "4月5日〜6月30日"), use the full range.
9. JUDGMENT: Use your reasoning to decide if an event is single-day vs multi-day. A concert, one-time screening, or one-time talk = single day (end_date = start_date). An exhibition, festival, or course = may span many days.

OTHER RULES:
1. If the description mentions multiple separate events/sessions with different dates (e.g., a film screening series with individual dates), list them as sub_events.
2. Categories must be from this list: movie, performing_arts, senses, retail, nature, tech, tourism, lifestyle_food, books_media, gender, geopolitics, art, lecture, taiwan_japan, business, academic, competition, indigenous, history, urban, workshop, report
   - "taiwan_japan" = Taiwan-Japan bilateral relations, diplomacy, civil exchange, friendship events between Taiwan and Japan
   - "business" = business, investment, commerce, startups, corporate events, trade, entrepreneurship
   - "competition" = contests, competitions, awards, championships, public calls for entries (コンテスト, 大会, 選手権, 公募, コンクール)
   - "academic" = academic research, seminars, symposiums, papers, university events, scholarly conferences
   - "indigenous" = events related to Taiwan's indigenous peoples (原住民族), tribal culture, indigenous arts or languages (アミ族, パイワン族, タイヤル族, etc.)
   - "history" = historical events, exhibitions on history, cultural heritage, archives, museums, war memory, historical figures
   - "workshop" = hands-on workshops, experience classes, craft workshops, cooking classes, pottery, weaving, tea ceremony, atelier sessions (体験, ワークショップ, 手作り, クラフト)
   - "movie" = film screenings, movie events, documentary showings, film festivals. IMPORTANT: any event with 上映, 映画, film, screening, cinema in its title or description MUST include "movie" as a category, even if it also involves talks or other elements.
   - "performing_arts" = music, concerts, live performances, dance, theater, stage shows, opera (but NOT film screenings)
   - "senses" = art, exhibitions, photography, design, workshops, creative experiences (but NOT film screenings or book events)
   - "lifestyle_food" = food, cooking, tea, restaurants, cafes, lifestyle events, daily life culture
   - "books_media" = books, literature, publishing, authors, readings, book launch events, media, journalism
   - "report" = event reports/recaps (only if the text IS a report about a past event, not an upcoming event)
   - An event can have multiple categories
3. Translate the event name and a concise summary description into all three languages (ja, zh, en).
4. The description should be a clean, concise summary (2-4 sentences), NOT a copy of the raw text.
5. Extract location, address, business hours, and pricing from the text if available.
6. LOCATION ADDRESS RULE: If the raw location_address looks like a venue/shop name (no street number, 丁目, 番地, or postal code 〒), use your knowledge to provide the real Japanese address (都道府県＋区＋丁目番地). Example: "青山・月見ル君想フ" → "東京都港区南青山3-10-33". If you genuinely don't know the address, keep it as-is. NEVER fabricate an address — only fill in if you are confident.
7. For pricing: is_paid=false if free/無料/免費, is_paid=true if there's a fee, null if unknown.

Respond with valid JSON matching this schema:
{
  "name_ja": "Japanese event name",
  "name_zh": "Traditional Chinese event name",
  "name_en": "English event name",
  "description_ja": "Japanese summary (2-4 sentences)",
  "description_zh": "Traditional Chinese summary (2-4 sentences)",
  "description_en": "English summary (2-4 sentences)",
  "category": ["senses"],
  "start_date": "2026-01-15T00:00:00" or null,
  "end_date": "2026-01-15T00:00:00" or null,
  "location_name": "venue name in Japanese (original)" or null,
  "location_name_zh": "venue name in Traditional Chinese" or null,
  "location_name_en": "venue name in English" or null,
  "location_address": "full address (original Japanese format)" or null,
  "location_address_zh": "address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is" or null,
  "location_address_en": "address in English (romanized city/area names; keep street number as-is)" or null,
  "business_hours": "opening hours in Japanese (original)" or null,
  "business_hours_zh": "opening hours in Traditional Chinese" or null,
  "business_hours_en": "opening hours in English" or null,
  "is_paid": false or true or null,
  "price_info": "price details" or null,
  "selection_reason": {
    "ja": "1-2文の日本語で、このイベントが台湿関連である理由と選定理由",
    "zh": "1-2句繁體中文，說明此活動與台灣的關聯及收錄原因",
    "en": "1-2 sentences in English explaining why this event is Taiwan-related and was selected"
  },
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


def _annotate_one(client: OpenAI, raw_title: str, raw_description: str, feedback_prompt: str = "") -> dict:
    """Send raw event data to GPT-4o-mini and return structured annotation."""
    system_content = SYSTEM_PROMPT + feedback_prompt
    user_content = f"Raw Title: {raw_title or '(no title)'}\n\nRaw Description:\n{raw_description or '(no description)'}"

    # Truncate very long descriptions to stay within token limits
    if len(user_content) > 12000:
        user_content = user_content[:12000] + "\n\n[... truncated ...]"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=4000,
    )

    usage = response.usage  # may be None in rare cases
    text = response.choices[0].message.content
    try:
        return json.loads(text), usage
    except json.JSONDecodeError:
        # Retry once with higher token budget
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=6000,
        )
        usage = response.usage
        return json.loads(response.choices[0].message.content), usage


def _validate_categories(cats: list) -> list[str]:
    """Filter to only valid category strings."""
    return [c for c in cats if isinstance(c, str) and c in VALID_CATEGORIES] or ["senses"]


_LECTURE_KEYWORDS = frozenset(["座談", "講座", "座談会", "座談會"])


def _inject_keyword_categories(categories: list[str], text: str) -> list[str]:
    """Add 'lecture' tag if the text contains lecture-related keywords."""
    if "lecture" not in categories and any(kw in text for kw in _LECTURE_KEYWORDS):
        return categories + ["lecture"]
    return categories


def annotate_pending_events(re_annotate_all: bool = False) -> None:
    """Fetch pending events from DB, annotate with AI, and update."""
    sb = _get_supabase()
    ai = _get_openai()
    annotation_start = time.time()

    # Load category feedback from admin corrections (for few-shot examples in AI prompt)
    corrections = load_corrections(sb)
    feedback_prompt = build_feedback_prompt(corrections)
    if corrections:
        logger.info("Loaded %d category corrections as few-shot examples", len(corrections))

    # Load full event_id → corrected_category map so the annotator can
    # apply human corrections directly and skip AI category prediction.
    # This ensures re-annotation never overwrites manually corrected categories.
    all_corrections_res = sb.table("category_corrections").select("event_id,corrected_category").execute()
    human_category_map: dict[str, list[str]] = {
        r["event_id"]: r["corrected_category"]
        for r in (all_corrections_res.data or [])
        if r.get("corrected_category")
    }
    if human_category_map:
        logger.info("Loaded %d human-corrected category overrides", len(human_category_map))

    # Fetch events to annotate
    # Always filter is_active=True so soft-deleted events are never re-processed.
    query = sb.table("events").select("*").eq("is_active", True)
    if re_annotate_all:
        pass  # annotate all active events regardless of status
    else:
        query = query.eq("annotation_status", "pending")

    result = query.order("created_at", desc=True).execute()
    events = result.data

    if not events:
        logger.info("No pending events to annotate.")
        return

    logger.info("Found %d events to annotate", len(events))

    # Accumulate usage for scraper_runs logging
    total_tokens_in = 0
    total_tokens_out = 0
    events_ok = 0

    for i, event in enumerate(events, 1):
        eid = event["id"]
        raw_title = event.get("raw_title") or event.get("name_ja") or ""
        raw_desc = event.get("raw_description") or event.get("description_ja") or ""

        logger.info("[%d/%d] Annotating: %s", i, len(events), raw_title[:60])

        try:
            annotation, usage = _annotate_one(ai, raw_title, raw_desc, feedback_prompt)
            if usage:
                total_tokens_in += usage.prompt_tokens or 0
                total_tokens_out += usage.completion_tokens or 0

            # Validate and sanitize
            categories = _validate_categories(annotation.get("category", []))
            categories = _inject_keyword_categories(categories, raw_title + " " + raw_desc)

            # Override with human-corrected category if one exists — this takes
            # priority over AI prediction and keyword injection.
            if eid in human_category_map:
                human_cats = human_category_map[eid]
                if human_cats != categories:
                    logger.info("  → Applying human-corrected category: %s (AI predicted: %s)",
                                human_cats, categories)
                categories = human_cats

            # Helper: convert empty-string GPT outputs to None so that
            # the web fallback chain (ja→zh→en) works correctly.
            def _str(val: Any) -> str | None:
                return val if isinstance(val, str) and val.strip() else None

            # Helper: clean location strings — GPT sometimes includes the label
            # separator (e.g. "会場：" → "：台北…"). Strip any leading ：；:; chars.
            def _loc(val: Any) -> str | None:
                s = _str(val)
                if s:
                    s = s.lstrip("：；:; \u3000")
                return s or None

            update_data: dict[str, Any] = {
                "name_ja": _str(annotation.get("name_ja")) or raw_title,
                "name_zh": _str(annotation.get("name_zh")),
                "name_en": _str(annotation.get("name_en")),
                "description_ja": _str(annotation.get("description_ja")),
                "description_zh": _str(annotation.get("description_zh")),
                "description_en": _str(annotation.get("description_en")),
                "category": categories,
                # Preserve scraper-set dates when GPT returns null — GPT may fail to
                # extract dates from long descriptions, but the scraper already found
                # and prepended them in 開催日時: format.
                "start_date": annotation.get("start_date") or event.get("start_date"),
                "end_date": annotation.get("end_date") or event.get("end_date"),
                "location_name": _loc(annotation.get("location_name")) or _loc(event.get("location_name")),
                "location_address": _loc(annotation.get("location_address")) or _loc(event.get("location_address")),
                "business_hours": annotation.get("business_hours") or event.get("business_hours"),
                "is_paid": annotation.get("is_paid") if annotation.get("is_paid") is not None else event.get("is_paid"),
                "price_info": annotation.get("price_info") or event.get("price_info"),
                "annotation_status": "annotated",
                "annotated_at": datetime.utcnow().isoformat(),
            }

            # Localized location/hours fields added in migration 010.
            # Kept separate so the primary update above never fails on old DB schemas.
            localized_location_data: dict[str, Any] = {
                "location_name_zh": _loc(annotation.get("location_name_zh")),
                "location_name_en": _loc(annotation.get("location_name_en")),
                "location_address_zh": _loc(annotation.get("location_address_zh")),
                "location_address_en": _loc(annotation.get("location_address_en")),
                "business_hours_zh": _str(annotation.get("business_hours_zh")),
                "business_hours_en": _str(annotation.get("business_hours_en")),
            }
            # Only send non-null values
            localized_location_data = {k: v for k, v in localized_location_data.items() if v is not None}

            # Ensure end_date is not null when start_date exists
            if update_data["start_date"] and not update_data["end_date"]:
                update_data["end_date"] = update_data["start_date"]

            # Try to include selection_reason (column may not exist yet)
            selection_reason = annotation.get("selection_reason")
            if selection_reason:
                # If AI returned a multilingual dict, JSON-encode it
                if isinstance(selection_reason, dict):
                    selection_reason = json.dumps(selection_reason, ensure_ascii=False)
                update_data["selection_reason"] = selection_reason

            sb.table("events").update(update_data).eq("id", eid).execute()
            events_ok += 1
            logger.info("  ✓ annotated (categories: %s)", categories)

            # Apply localized location/hours fields separately — columns were added
            # in migration 010 and may not exist on older DB schemas.
            if localized_location_data:
                try:
                    sb.table("events").update(localized_location_data).eq("id", eid).execute()
                except Exception as loc_err:
                    logger.warning("  ⚠ localized location update skipped (run migration 010): %s", loc_err)

            # Handle sub-events
            sub_events = annotation.get("sub_events", [])
            for j, sub in enumerate(sub_events):
                sub_cats = _validate_categories(sub.get("category", categories))
                sub_cats = _inject_keyword_categories(sub_cats, sub.get("name_ja", "") + " " + (sub.get("description_ja") or ""))
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

                # Also try localized location fields for sub-events (migration 010)
                sub_loc = {k: v for k, v in {
                    "location_name_zh": _loc(sub.get("location_name_zh")) or localized_location_data.get("location_name_zh"),
                    "location_name_en": _loc(sub.get("location_name_en")) or localized_location_data.get("location_name_en"),
                    "location_address_zh": _loc(sub.get("location_address_zh")) or localized_location_data.get("location_address_zh"),
                    "location_address_en": _loc(sub.get("location_address_en")) or localized_location_data.get("location_address_en"),
                    "business_hours_zh": _str(sub.get("business_hours_zh")) or localized_location_data.get("business_hours_zh"),
                    "business_hours_en": _str(sub.get("business_hours_en")) or localized_location_data.get("business_hours_en"),
                }.items() if v is not None}
                if sub_loc:
                    try:
                        # Get the upserted sub-event id
                        sub_result = sb.table("events").select("id").eq("source_name", event["source_name"]).eq("source_id", f"{event['source_id']}_sub{j+1}").single().execute()
                        if sub_result.data:
                            sb.table("events").update(sub_loc).eq("id", sub_result.data["id"]).execute()
                    except Exception:
                        pass  # migration 010 not applied yet, skip silently

                logger.info("  + sub-event %d: %s", j + 1, sub.get("name_ja", "")[:50])

        except Exception as exc:
            logger.error("  ✗ annotation failed: %s", exc)
            sb.table("events").update({
                "annotation_status": "error",
            }).eq("id", eid).execute()

        # Rate limiting — avoid hitting OpenAI too fast
        time.sleep(0.5)

    # -------------------------------------------------------------------
    # Write scraper_runs record
    # GPT-4o-mini pricing: $0.15 / 1M input tokens, $0.60 / 1M output tokens
    # -------------------------------------------------------------------
    cost = (total_tokens_in * 0.15 + total_tokens_out * 0.60) / 1_000_000
    try:
        sb.table("scraper_runs").insert({
            "source": "annotator",
            "events_processed": events_ok,
            "openai_tokens_in": total_tokens_in,
            "openai_tokens_out": total_tokens_out,
            "cost_usd": round(cost, 6),
            "duration_seconds": int(time.time() - annotation_start),
            "notes": f"re_annotate_all={re_annotate_all}, total={len(events)}",
        }).execute()
        logger.info(
            "scraper_runs logged: %d events, %d in / %d out tokens, $%.6f",
            events_ok, total_tokens_in, total_tokens_out, cost,
        )
    except Exception as exc:
        logger.warning("Could not write scraper_runs (table may not exist yet): %s", exc)

    logger.info("Annotation complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    re_all = "--all" in sys.argv
    annotate_pending_events(re_annotate_all=re_all)
