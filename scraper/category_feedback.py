"""
Category feedback module — loads admin corrections from the database
and generates few-shot examples for the AI annotator prompt.

This creates a learning loop:
  1. AI annotates an event with category predictions
  2. Admin corrects the category in the admin UI
  3. Correction is saved to `category_corrections` table
  4. Next time the annotator runs, corrections are loaded as few-shot examples
  5. AI learns from past mistakes and improves accuracy
"""

import json
import logging
from typing import Optional

from supabase import Client

logger = logging.getLogger(__name__)

# Maximum number of few-shot examples to include in the prompt
MAX_EXAMPLES = 15


def load_corrections(sb: Client) -> list[dict]:
    """Load category corrections from the database, newest first."""
    try:
        result = (
            sb.table("category_corrections")
            .select("raw_title, ai_category, corrected_category")
            .order("created_at", desc=True)
            .limit(MAX_EXAMPLES)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.warning("Could not load category corrections: %s", e)
        return []


def build_feedback_prompt(corrections: list[dict]) -> str:
    """Build a few-shot section from admin corrections.

    Returns a string to be appended to the system prompt, or empty string
    if there are no corrections.
    """
    if not corrections:
        return ""

    lines = [
        "\n\nCATEGORY CORRECTION EXAMPLES (learn from these admin corrections):",
        "The following are real events where the AI's initial category was wrong.",
        "Use these examples to improve your category predictions:\n",
    ]

    for i, c in enumerate(corrections, 1):
        title = (c.get("raw_title") or "").strip()[:100]
        ai_cats = c.get("ai_category", [])
        correct_cats = c.get("corrected_category", [])
        lines.append(
            f"  {i}. \"{title}\"\n"
            f"     AI predicted: {json.dumps(ai_cats)}\n"
            f"     Correct answer: {json.dumps(correct_cats)}"
        )

    return "\n".join(lines)


def record_correction(
    sb: Client,
    event_id: str,
    raw_title: Optional[str],
    raw_description: Optional[str],
    ai_category: list[str],
    corrected_category: list[str],
    corrected_by: Optional[str] = None,
) -> None:
    """Save a category correction to the database."""
    row = {
        "event_id": event_id,
        "raw_title": raw_title,
        "raw_description": (raw_description or "")[:500],  # truncate long descriptions
        "ai_category": ai_category,
        "corrected_category": corrected_category,
    }
    if corrected_by:
        row["corrected_by"] = corrected_by

    try:
        sb.table("category_corrections").upsert(
            row, on_conflict="event_id"
        ).execute()
        logger.info("Saved category correction for event %s: %s -> %s",
                     event_id, ai_category, corrected_category)
    except Exception as e:
        logger.warning("Could not save category correction: %s", e)
