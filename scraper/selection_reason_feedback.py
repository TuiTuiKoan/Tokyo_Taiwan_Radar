"""
selection_reason_feedback.py — P3.3

Few-shot selection_reason correction loader for annotator.py.
Mirrors the pattern of category_feedback.py.

Usage (annotator.py startup):
    from selection_reason_feedback import load_sr_corrections, build_sr_feedback_prompt
    sr_corrections = load_sr_corrections(sb)
    sr_feedback_prompt = build_sr_feedback_prompt(sr_corrections)
"""

from __future__ import annotations

from supabase import Client


def load_sr_corrections(sb: Client) -> list[dict]:
    """Load the most recent admin-corrected selection_reason examples.

    Returns up to 10 rows from selection_reason_corrections, ordered newest
    first.  Falls back to an empty list when the table doesn't exist yet
    (pre-migration 040) so annotator.py degrades gracefully.
    """
    try:
        res = (
            sb.table("selection_reason_corrections")
            .select("raw_title,raw_description,ai_sr,corrected_sr")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def build_sr_feedback_prompt(corrections: list[dict]) -> str:
    """Format correction examples as a few-shot addendum for SYSTEM_PROMPT.

    Each example shows the original GPT selection_reason next to the admin's
    correction, providing concrete guidance on quality expectations.
    Only includes language pairs where AI and corrected values actually differ.
    Returns an empty string when there are no corrections to show.
    """
    if not corrections:
        return ""

    lines: list[str] = [
        "",
        "",
        "--- SELECTION REASON CORRECTION EXAMPLES ---",
        "The following events had their selection_reason corrected by a human editor.",
        "Use these as guidance to write more accurate and informative selection reasons.",
        "",
    ]

    for c in corrections:
        title = (c.get("raw_title") or "").strip()[:80]
        desc = (c.get("raw_description") or "").strip()[:150]
        ai: dict = c.get("ai_sr") or {}
        corrected: dict = c.get("corrected_sr") or {}

        lines.append(f"Event: '{title}'")
        if desc:
            lines.append(f"  Context: \"{desc}...\"")

        for lang in ("ja", "zh", "en"):
            ai_val = (ai.get(lang) or "").strip()
            corr_val = (corrected.get(lang) or "").strip()
            if ai_val and corr_val and ai_val != corr_val:
                lines.append(f"  AI ({lang}):      '{ai_val}'")
                lines.append(f"  Corrected ({lang}): '{corr_val}'")

        lines.append("")

    return "\n".join(lines)
