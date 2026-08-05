"""Deterministic lookup for authoritative venue records."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.append(str(_THIS_DIR))

from database import _get_client

logger = logging.getLogger(__name__)
_CANONICAL: dict[str, dict[str, Any]] | None = None
_ALIASES: dict[str, dict[str, Any]] = {}
_AMBIGUOUS: set[str] = set()


def _register(
    index: dict[str, dict[str, Any]],
    ambiguous: set[str],
    key: str,
    row: dict[str, Any],
    tier: str,
) -> None:
    existing = index.get(key)
    if existing is not None and existing.get("id") != row.get("id"):
        ambiguous.add(key)
        logger.error(
            "venue_registry: %s key %r maps to multiple authoritative venues "
            "(%s, %s); rejecting key.",
            tier,
            key,
            existing.get("id"),
            row.get("id"),
        )
        return
    index[key] = row


def _build_cache() -> None:
    global _CANONICAL, _ALIASES, _AMBIGUOUS

    try:
        sb = _get_client()
        rows = (
            sb.table("venues")
            .select(
                "id,canonical_name_ja,canonical_name_zh,canonical_name_en,"
                "address,prefecture,prefectures,city,homepage,aliases,"
                "is_authoritative,is_multi_venue,business_hours"
            )
            .eq("is_authoritative", True)
            .execute()
            .data
            or []
        )

        canonical: dict[str, dict[str, Any]] = {}
        aliases: dict[str, dict[str, Any]] = {}
        ambiguous: set[str] = set()
        for row in rows:
            canonical_name = (row.get("canonical_name_ja") or "").strip()
            if canonical_name:
                _register(canonical, ambiguous, canonical_name, row, "canonical")
            for alias in row.get("aliases") or []:
                key = (alias or "").strip()
                if key:
                    _register(aliases, ambiguous, key, row, "alias")

        for key in canonical.keys() & aliases.keys():
            if canonical[key].get("id") != aliases[key].get("id"):
                ambiguous.add(key)
                logger.error(
                    "venue_registry: cross-tier key %r maps to authoritative venues "
                    "(%s canonical, %s alias); rejecting key.",
                    key,
                    canonical[key].get("id"),
                    aliases[key].get("id"),
                )
            else:
                aliases.pop(key)

        for key in ambiguous:
            canonical.pop(key, None)
            aliases.pop(key, None)
    except Exception as exc:
        logger.warning(
            "venue_registry: authoritative load failed; caching empty registry. error=%s",
            exc,
        )
        _CANONICAL, _ALIASES, _AMBIGUOUS = {}, {}, set()
        return

    _CANONICAL, _ALIASES, _AMBIGUOUS = canonical, aliases, ambiguous

    logger.info(
        "venue_registry loaded: %d authoritative venues, %d canonical keys, "
        "%d alias keys, %d ambiguous keys",
        len(rows),
        len(canonical),
        len(aliases),
        len(ambiguous),
    )


def lookup_venue(name: str | None) -> dict[str, Any] | None:
    global _CANONICAL
    if _CANONICAL is None:
        _build_cache()
    if not name:
        return None
    key = name.strip()
    if not key or key in _AMBIGUOUS:
        return None
    hit = _CANONICAL.get(key) if _CANONICAL else None
    return hit if hit is not None else _ALIASES.get(key)


def _reset_cache_for_tests() -> None:
    global _CANONICAL, _ALIASES, _AMBIGUOUS
    _CANONICAL = None
    _ALIASES = {}
    _AMBIGUOUS = set()
