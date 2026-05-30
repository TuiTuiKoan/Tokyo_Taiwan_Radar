"""Thin wrapper over venues table for authoritative venue lookup."""

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
_CACHE: dict[str, dict[str, Any]] | None = None
_COMPATIBILITY_MODE = False


def _is_missing_authority_column_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    authority_cols = ("is_authoritative", "is_multi_venue", "homepage", "prefectures")
    return ("column" in msg or "schema cache" in msg) and "venues" in msg and any(c in msg for c in authority_cols)


def _ensure_defaults(row: dict[str, Any]) -> dict[str, Any]:
    patched = dict(row)
    patched.setdefault("is_authoritative", False)
    patched.setdefault("is_multi_venue", False)
    patched.setdefault("homepage", None)
    patched.setdefault("prefectures", None)
    patched.setdefault("business_hours", None)
    return patched


def _build_cache() -> dict[str, dict[str, Any]]:
    global _COMPATIBILITY_MODE

    sb = _get_client()
    _COMPATIBILITY_MODE = False
    try:
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
    except Exception as exc:
        if not _is_missing_authority_column_error(exc):
            raise
        _COMPATIBILITY_MODE = True
        logger.warning(
            "venues authority migration not applied; venue_registry entering compatibility mode "
            "(defaults: is_authoritative=False, is_multi_venue=False, homepage=None, prefectures=None). "
            "error=%s",
            exc,
        )
        rows = (
            sb.table("venues")
            .select(
                "id,canonical_name_ja,canonical_name_zh,canonical_name_en,"
                "address,prefecture,city,aliases"
            )
            .execute()
            .data
            or []
        )
        rows = [_ensure_defaults(r) for r in rows]

    cache: dict[str, dict[str, Any]] = {}
    for row in rows:
        canonical = (row.get("canonical_name_ja") or "").strip()
        if canonical:
            cache[canonical] = row
        for alias in row.get("aliases") or []:
            key = (alias or "").strip()
            if key:
                cache[key] = row

    logger.info(
        "venue_registry loaded: %d authoritative venues, %d lookup keys",
        len(rows),
        len(cache),
    )
    return cache


def lookup_venue(name: str | None) -> dict[str, Any] | None:
    global _CACHE
    if _CACHE is None:
        _CACHE = _build_cache()
    if not name:
        return None
    row = _CACHE.get(name.strip())
    if row is None and _COMPATIBILITY_MODE:
        return None
    return row
