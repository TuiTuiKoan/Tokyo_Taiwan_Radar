"""Authoritative organizer registry — deterministic organizer_type lookup.

Mirrors ``venue_registry.py``'s lazy-load + module-level cache design, scoped to
``organizers`` rows flagged ``is_authoritative = true``. Wave 2 batch-4 wires the
annotator to consult this registry so verified entity types take precedence over
event-topic LLM inference. LLM output must never write back into the registry.

Graceful degradation
--------------------
The ``is_authoritative`` column ships in migration 095. On any database where
095 has not been applied yet (e.g. the daily CI run that fires before the
migration lands) the load query fails on the missing column. Instead of crashing
the annotation pipeline we log at ``debug`` level and return an **empty registry**
— every lookup returns ``None``, a silent no-op. This mirrors
``database._populate_entity_fks``'s migration-050 backwards-compat pattern
(``except Exception: logger.debug(...)``): never raise.

Duplicate fail-closed
---------------------
If the same canonical name (canonical-vs-canonical) or the same alias
(alias-vs-alias) maps to more than one authoritative entity, the key is
ambiguous. It is added to a reject set and logged at ``error`` level; every
lookup for that key returns ``None`` rather than picking an arbitrary row.
"""

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

# Module-level lazy singletons (mirror venue_registry._CACHE). ``_CANONICAL`` is
# both the canonical_name_ja map and the loaded-sentinel: ``None`` means "not yet
# built". ``_ALIASES`` maps alias -> entity. ``_REJECTED`` holds ambiguous keys
# that fail closed. After a graceful load failure all three are set to empty
# containers (not None), so the failing query is not retried on every lookup.
_CANONICAL: dict[str, dict[str, Any]] | None = None
_ALIASES: dict[str, dict[str, Any]] = {}
_REJECTED: set[str] = set()


def _register(dest: dict[str, dict[str, Any]], rejected: set[str], key: str, row: dict[str, Any]) -> None:
    """Insert ``key -> row`` into ``dest``, flagging same-tier duplicates.

    If ``key`` already maps to a *different* authoritative entity within the same
    tier, the key is ambiguous: record it in ``rejected`` (logging once) and do
    not overwrite. Rejected keys are purged from every map after the build.
    """
    existing = dest.get(key)
    if existing is not None and existing.get("id") != row.get("id"):
        if key not in rejected:
            logger.error(
                "organizer_registry: key %r maps to multiple authoritative organizers "
                "(%s, %s); rejecting key (lookup will return None).",
                key,
                existing.get("id"),
                row.get("id"),
            )
        rejected.add(key)
        return
    dest[key] = row


def _build_cache() -> None:
    global _CANONICAL, _ALIASES, _REJECTED

    sb = _get_client()
    try:
        rows = (
            sb.table("organizers")
            .select("id,canonical_name_ja,aliases,organizer_type")
            .eq("is_authoritative", True)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        # is_authoritative ships in migration 095. Before it is applied the
        # column does not exist and this query raises. Fail closed to an empty
        # registry — never raise, so the annotation pipeline keeps running.
        logger.debug(
            "organizer_registry: authoritative load failed "
            "(organizers.is_authoritative may not be migrated yet); "
            "returning empty registry. error=%s",
            exc,
        )
        _CANONICAL, _ALIASES, _REJECTED = {}, {}, set()
        return

    canonical: dict[str, dict[str, Any]] = {}
    aliases: dict[str, dict[str, Any]] = {}
    rejected: set[str] = set()

    for row in rows:
        canonical_name = (row.get("canonical_name_ja") or "").strip()
        if canonical_name:
            _register(canonical, rejected, canonical_name, row)
        for alias in row.get("aliases") or []:
            key = (alias or "").strip()
            if key:
                _register(aliases, rejected, key, row)

    # Purge every rejected key from both tiers so a later same-entity duplicate
    # cannot resurrect an ambiguous key.
    for key in rejected:
        canonical.pop(key, None)
        aliases.pop(key, None)

    _CANONICAL, _ALIASES, _REJECTED = canonical, aliases, rejected
    logger.info(
        "organizer_registry loaded: %d authoritative organizers, "
        "%d canonical keys, %d alias keys, %d rejected",
        len(rows),
        len(canonical),
        len(aliases),
        len(rejected),
    )


def lookup_organizer(name: str | None) -> dict[str, Any] | None:
    """Return the authoritative organizer entity for ``name``, or ``None``.

    Resolution order: canonical_name_ja exact match first, then alias exact
    match. A key that maps to multiple authoritative entities (duplicate
    canonical or duplicate alias) is in the reject set and returns ``None``
    (fail closed). Unknown names and an empty/unmigrated registry return
    ``None``.
    """
    global _CANONICAL
    if _CANONICAL is None:
        _build_cache()
    if not name:
        return None
    key = name.strip()
    if not key:
        return None
    if key in _REJECTED:
        return None
    hit = _CANONICAL.get(key) if _CANONICAL else None
    if hit is not None:
        return hit
    return _ALIASES.get(key)


def reset_cache() -> None:
    """Reset the module-level cache so the next lookup rebuilds it.

    Test aid — production code loads once per process.
    """
    global _CANONICAL, _ALIASES, _REJECTED
    _CANONICAL = None
    _ALIASES = {}
    _REJECTED = set()
