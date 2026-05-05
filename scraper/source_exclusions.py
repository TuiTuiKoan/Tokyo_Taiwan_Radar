"""
source_exclusions.py — Source-level pattern-based event filter

Loads active exclusion rules from `source_exclusions` table and checks
incoming events against them before upsert.  All DB errors are handled
gracefully — filter is silently skipped on failure so the scraper never
gets blocked by this feature.

Tables used:
  source_exclusions       — admin-defined rules (substring or regex)
  source_exclusion_hits   — per-event hit log (30-day rolling window)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

UTC = timezone.utc


def load_exclusions(sb, source_names: list[str]) -> dict[str, list[dict]]:
    """Return active rules indexed by source_name.

    Returns {} if the table does not exist or on any DB error.
    """
    if not source_names:
        return {}
    try:
        resp = (
            sb.table("source_exclusions")
            .select("id,source_name,pattern,pattern_type,match_field,expires_at,auto_disabled_at")
            .in_("source_name", source_names)
            .eq("is_active", True)
            .is_("auto_disabled_at", "null")
            .execute()
        )
        now_dt = datetime.now(tz=UTC)
        rules: dict[str, list[dict]] = {}
        for row in resp.data or []:
            expires_at = row.get("expires_at")
            if expires_at:
                try:
                    exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if exp_dt <= now_dt:
                        continue
                except ValueError:
                    pass
            rules.setdefault(row["source_name"], []).append(row)
        return rules
    except Exception as exc:
        logger.debug("source_exclusions load skipped: %s", exc)
        return {}


def event_matches_exclusion(event, rules: list[dict]) -> dict | None:
    """Return the first matching rule dict, or None if no match.

    Matching is case-insensitive for 'substring'; uses re.search for 'regex'.
    """
    raw_title = (getattr(event, "raw_title", None) or "").lower()
    raw_description = (getattr(event, "raw_description", None) or "").lower()

    for rule in rules:
        pattern = rule.get("pattern", "")
        pattern_type = rule.get("pattern_type", "substring")
        match_field = rule.get("match_field", "raw_title")

        if match_field == "raw_title":
            candidates = [raw_title]
        elif match_field == "raw_description":
            candidates = [raw_description]
        else:  # raw_title_or_description
            candidates = [raw_title, raw_description]

        if pattern_type == "regex":
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                if any(compiled.search(c) for c in candidates):
                    return rule
            except re.error:
                logger.warning("source_exclusions: invalid regex %r — skipping rule", pattern)
        else:  # substring
            pat_lower = pattern.lower()
            if any(pat_lower in c for c in candidates):
                return rule

    return None


def record_hits(sb, hits: list[dict]) -> None:
    """Batch-insert hit records into source_exclusion_hits.

    Each hit dict: {rule_id, raw_title, source_name}
    Also increments match_count and last_matched_at on matched rules.
    Failures are logged but never propagated.
    """
    if not hits:
        return
    now = datetime.now(tz=UTC).isoformat()
    rows = [
        {
            "rule_id": h["rule_id"],
            "raw_title": h.get("raw_title"),
            "source_name": h["source_name"],
            "matched_at": now,
        }
        for h in hits
    ]
    try:
        sb.table("source_exclusion_hits").insert(rows).execute()
    except Exception as exc:
        logger.warning("source_exclusion_hits insert failed: %s", exc)
        return

    # Best-effort: bump match_count + last_matched_at per rule
    rule_ids = list({h["rule_id"] for h in hits})
    for rule_id in rule_ids:
        try:
            # Supabase SDK doesn't support atomic increment; use rpc or re-read
            current = (
                sb.table("source_exclusions")
                .select("match_count")
                .eq("id", rule_id)
                .single()
                .execute()
            )
            new_count = (current.data.get("match_count") or 0) + sum(
                1 for h in hits if h["rule_id"] == rule_id
            )
            sb.table("source_exclusions").update(
                {"match_count": new_count, "last_matched_at": now}
            ).eq("id", rule_id).execute()
        except Exception as exc:
            logger.debug("source_exclusions bump failed for %s: %s", rule_id, exc)
