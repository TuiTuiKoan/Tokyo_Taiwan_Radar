"""Processed markers for LLM steps, stored in public.llm_cache (#363).

A step records one row per subject it sent to the model, so later runs skip it
instead of paying for the same answer again:

    if llm_cache.seen(sb, "cinemaclair_ocr", [image_sha]):
        continue
    ...
    llm_cache.record(sb, "cinemaclair_ocr", image_sha, "applied", {"image_url": ...})

seen() raises when the table cannot be read: a step that cannot tell what it
already sent would resend everything, which is the cost this table exists to
stop. record() only logs on failure; at worst that subject is sent once more.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

logger = logging.getLogger(__name__)

_CHUNK = 100


def seen(sb, step: str, keys: Iterable[str]) -> set[str]:
    """The subset of keys already recorded for this step."""
    keys = list(dict.fromkeys(k for k in keys if k))
    found: set[str] = set()
    for i in range(0, len(keys), _CHUNK):
        rows = (
            sb.table("llm_cache")
            .select("subject_key")
            .eq("step", step)
            .in_("subject_key", keys[i : i + _CHUNK])
            .execute()
            .data
            or []
        )
        found.update(r["subject_key"] for r in rows)
    return found


def record(sb, step: str, key: str, outcome: str, result: dict | None = None) -> None:
    try:
        sb.table("llm_cache").upsert(
            {
                "step": step,
                "subject_key": key,
                "outcome": outcome,
                "result": result,
                "attempted_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="step,subject_key",
        ).execute()
    except Exception as exc:
        logger.warning("llm_cache record failed for %s/%s: %s", step, key[:16], exc)
