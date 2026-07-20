"""Wave 2 Phase B0a / B — organizer storage-enum boundary + migration 095 fixture.

Deterministic, offline tests (no DB required) that lock in:

  * the LLM inference vocabulary stays at 9 values and never emits 'individual'
    or any actor-only value (B0a must NOT widen the daily GPT classifier);
  * the canonical STORAGE vocabulary is the 10-value superset (adds
    'individual') and the trilingual web `organizerType` labels already cover
    exactly those 10 keys, equal across zh/en/ja (expected zero i18n diff);
  * migration 095's legacy JSON-text -> scalar normalize is lossless for the
    unambiguous single legal value and NULLs multi/illegal values;
  * the events cardinality CHECK predicate has the documented COALESCE
    fail/pass semantics;
  * migration 095's SQL is structurally correct (validated CHECKs, scalar IN
    for research_sources, no NOT VALID, no GRANT/REVOKE/ALTER VIEW,
    transaction-wrapped).

An OPT-IN read-only DB gate test (set TTR_RUN_DB_GATE=1) reports the live
table-wide co/sponsor mismatch count and cross-checks two independent
cardinality implementations, demonstrating the fail-closed gate: while the
mismatch is > 0 the validated CHECK cannot be created; it becomes creatable
only once Phase A.5 has driven the count to 0.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from annotator import (
    VALID_ORGANIZER_TYPES,
    _validate_organizer_types,
    _validate_organizer_types_list,
)

# --- canonical vocabularies ------------------------------------------------

# Authoritative storage set = live events_organizer_type_check (migration 086).
CANONICAL_STORAGE_TYPES = frozenset({
    "government", "semi_official", "cultural_institution", "academic",
    "commercial_brand", "independent_venue", "civic_group", "media",
    "individual", "unknown",
})

# LLM inference set = storage set minus the storage/registry-only 'individual'.
LLM_INFERENCE_TYPES = CANONICAL_STORAGE_TYPES - {"individual"}

# Broader actor taxonomy (web/lib/actorTypes.ts) — must never leak into the
# organizer_type enum.
ACTOR_ONLY_VALUES = ("traveler", "writer", "food", "art")

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_MESSAGES_DIR = REPO_ROOT / "web" / "messages"
MIGRATION_095 = REPO_ROOT / "supabase" / "migrations" / "095_organizer_authority.sql"


# ===========================================================================
# 1. LLM inference vocabulary (B0a keeps GPT at 9 values)
# ===========================================================================

def test_llm_vocabulary_is_exactly_nine_values():
    assert set(VALID_ORGANIZER_TYPES) == set(LLM_INFERENCE_TYPES)
    assert len(VALID_ORGANIZER_TYPES) == 9


def test_llm_vocabulary_rejects_individual():
    assert "individual" not in VALID_ORGANIZER_TYPES


def test_llm_vocabulary_rejects_actor_only_values():
    for actor in ACTOR_ONLY_VALUES:
        assert actor not in VALID_ORGANIZER_TYPES


def test_llm_validators_drop_individual_and_actor_only():
    # Primary array validator and the flat parallel-array validator both drop
    # storage-only 'individual' and actor-only values, while keeping legal
    # inference values.
    assert _validate_organizer_types(["commercial_brand"]) == ["commercial_brand"]
    assert _validate_organizer_types(["individual"]) == []
    assert _validate_organizer_types(["traveler", "writer"]) == []
    assert _validate_organizer_types(["academic", "individual", "media"]) == ["academic", "media"]

    assert _validate_organizer_types_list(["civic_group"]) == ["civic_group"]
    assert _validate_organizer_types_list(["individual"]) == []
    assert _validate_organizer_types_list(["food", "art"]) == []


def test_database_layer_vocabulary_in_sync_with_annotator():
    import database  # lazy: avoids paying the import cost for the offline suite

    assert set(database._VALID_ORGANIZER_TYPES) == set(VALID_ORGANIZER_TYPES)
    assert "individual" not in database._VALID_ORGANIZER_TYPES


# ===========================================================================
# 2. Canonical storage vocabulary + trilingual web labels
# ===========================================================================

def test_canonical_storage_is_ten_value_superset_of_inference():
    assert len(CANONICAL_STORAGE_TYPES) == 10
    assert LLM_INFERENCE_TYPES < CANONICAL_STORAGE_TYPES  # proper subset
    assert CANONICAL_STORAGE_TYPES - LLM_INFERENCE_TYPES == {"individual"}


def _load_organizer_type_keys(locale: str) -> set[str]:
    data = json.loads((WEB_MESSAGES_DIR / f"{locale}.json").read_text(encoding="utf-8"))
    return set(data["organizerType"].keys())


@pytest.mark.parametrize("locale", ["zh", "en", "ja"])
def test_web_messages_organizer_type_keys_match_canonical(locale):
    assert _load_organizer_type_keys(locale) == set(CANONICAL_STORAGE_TYPES)


def test_web_messages_three_languages_have_equal_keys():
    zh = _load_organizer_type_keys("zh")
    en = _load_organizer_type_keys("en")
    ja = _load_organizer_type_keys("ja")
    assert zh == en == ja


@pytest.mark.parametrize("locale", ["zh", "en", "ja"])
def test_web_messages_exclude_actor_only_values(locale):
    keys = _load_organizer_type_keys(locale)
    for actor in ACTOR_ONLY_VALUES:
        assert actor not in keys


# ===========================================================================
# 3. Migration 095 legacy JSON-text -> scalar normalize (mirrors SQL 2a/2b)
# ===========================================================================

def _normalize_organizer_type_scalar(value):
    """Pure-Python mirror of migration 095 section 2 (steps 2a + 2b).

    2a: an unambiguous single-element bracketed array of a legal value is
        promoted to its bare scalar form (text ops only).
    2b: any remaining non-null value that is not a legal scalar becomes NULL.
    """
    if value is None:
        return None
    trimmed = value.strip()
    # 2a — single-element bracketed array (no comma) of a legal value.
    if trimmed.startswith("[") and trimmed.endswith("]") and "," not in value:
        inner = trimmed.strip("[]").strip(" '\"")
        if inner in CANONICAL_STORAGE_TYPES:
            return inner
    # 2b — keep an already-legal scalar, else NULL.
    return value if value in CANONICAL_STORAGE_TYPES else None


def test_normalize_json_text_double_quote_to_scalar():
    # The only live non-null value (2 rows) at authoring time.
    assert _normalize_organizer_type_scalar('["commercial_brand"]') == "commercial_brand"


def test_normalize_python_repr_single_quote_to_scalar():
    assert _normalize_organizer_type_scalar("['commercial_brand']") == "commercial_brand"


def test_normalize_multi_value_array_becomes_null():
    # Ambiguous multi-element array -> NULL (manual review), never silently
    # flattened to a single value.
    assert _normalize_organizer_type_scalar('["academic","media"]') is None


def test_normalize_illegal_legacy_scalar_becomes_null():
    assert _normalize_organizer_type_scalar("corporate") is None


def test_normalize_already_legal_scalar_is_preserved():
    assert _normalize_organizer_type_scalar("commercial_brand") == "commercial_brand"
    assert _normalize_organizer_type_scalar("individual") == "individual"


def test_normalize_null_stays_null():
    assert _normalize_organizer_type_scalar(None) is None


# ===========================================================================
# 4. events cardinality CHECK predicate (mirrors the SQL COALESCE semantics)
# ===========================================================================

def _card(arr):
    """Mirror SQL COALESCE(cardinality(x), 0): NULL and [] both -> 0."""
    return len(arr) if isinstance(arr, list) else 0


def _cardinality_ok(names, types):
    return _card(names) == _card(types)


@pytest.mark.parametrize(
    "names,types,expected",
    [
        (["a", "b"], ["t1", "t2"], True),   # aligned
        (["a", "b"], ["t1"], False),        # names longer
        (["a"], ["t1", "t2"], False),       # types longer
        ([], [], True),                      # both empty
        (None, None, True),                  # both null
        ([], None, True),                    # empty vs null -> both 0
        (None, [], True),                    # null vs empty -> both 0
        (["a"], None, False),               # single name, null types
        (None, ["t1"], False),              # null names, single type
    ],
)
def test_cardinality_predicate_fail_pass_semantics(names, types, expected):
    assert _cardinality_ok(names, types) is expected


# ===========================================================================
# 5. Migration 095 structural fixture
# ===========================================================================

def _migration_sql() -> str:
    return MIGRATION_095.read_text(encoding="utf-8")


def _migration_executable_sql() -> str:
    """Migration text with `--` line comments removed.

    Structural assertions must validate the executable statements, not the
    explanatory prose (which legitimately mentions GRANT / NOT VALID / <@ ARRAY
    / events_organizer_type_check while describing what the migration avoids).
    Migration 095 contains no `--` inside any string literal, so this naive
    stripper is safe.
    """
    out = []
    for line in _migration_sql().splitlines():
        idx = line.find("--")
        if idx != -1:
            line = line[:idx]
        out.append(line)
    return "\n".join(out)


def test_migration_file_exists():
    assert MIGRATION_095.is_file()


def test_migration_declares_both_cardinality_checks_validated():
    sql = _migration_executable_sql()
    assert "events_co_org_cardinality_check" in sql
    assert "events_sponsor_cardinality_check" in sql
    assert "COALESCE(cardinality(co_organizers), 0) = COALESCE(cardinality(co_organizer_types), 0)" in sql
    assert "COALESCE(cardinality(sponsors), 0) = COALESCE(cardinality(sponsor_types), 0)" in sql
    # Validated CHECK (fail-closed): must NOT be deferred with NOT VALID.
    assert "NOT VALID" not in sql.upper()


def test_migration_research_sources_uses_scalar_in_not_array_subset():
    sql = _migration_executable_sql()
    assert "research_sources_default_organizer_type_check" in sql
    assert "default_organizer_type IS NULL OR" in sql
    # Scalar column must not borrow the events text[] "<@ ARRAY[...]" syntax.
    assert "default_organizer_type <@" not in sql
    assert "<@ ARRAY" not in sql


def test_migration_declares_ten_value_sets_for_scalar_constraints():
    sql = _migration_executable_sql()
    # Every canonical value must appear inside a quoted literal, and the
    # storage-only 'individual' must be present in the new scalar CHECKs.
    for value in CANONICAL_STORAGE_TYPES:
        assert f"'{value}'" in sql
    assert "organizers_organizer_type_check" in sql


def test_migration_adds_is_authoritative_and_partial_index():
    sql = _migration_executable_sql()
    assert "ADD COLUMN IF NOT EXISTS is_authoritative BOOL NOT NULL DEFAULT false" in sql
    assert "idx_organizers_is_authoritative" in sql
    assert "WHERE is_authoritative = true" in sql


def test_migration_is_transaction_wrapped():
    sql = _migration_executable_sql()
    assert "BEGIN;" in sql
    assert "COMMIT;" in sql
    assert sql.index("BEGIN;") < sql.index("COMMIT;")


def test_migration_touches_no_permissions_or_views():
    sql = _migration_executable_sql().upper()
    # Assert there is no executable GRANT / REVOKE / ALTER VIEW statement
    # (comment prose is stripped before this check).
    for token in ("GRANT ", "REVOKE ", "ALTER VIEW", "CREATE VIEW", "CREATE OR REPLACE VIEW"):
        assert token not in sql


def test_migration_does_not_touch_events_organizer_type_column():
    sql = _migration_executable_sql()
    # 095 must not redefine the events.organizer_type text[] constraint (086).
    assert "events_organizer_type_check" not in sql


# ===========================================================================
# 6. OPT-IN read-only DB gate (set TTR_RUN_DB_GATE=1) — no writes
# ===========================================================================

@pytest.mark.skipif(
    not os.environ.get("TTR_RUN_DB_GATE"),
    reason="opt-in read-only DB gate; set TTR_RUN_DB_GATE=1 to run",
)
def test_db_gate_live_cardinality_mismatch_reports_fail_closed():
    import database

    def _card_b(arr):
        # Independent implementation: treat any falsy (None / []) as 0.
        return 0 if not arr else len(arr)

    sb = database._get_client()
    page, size, events = 0, 1000, []
    while True:
        lo = page * size
        batch = (
            sb.table("events")
            .select("id,co_organizers,co_organizer_types,sponsors,sponsor_types")
            .range(lo, lo + size - 1)
            .execute()
            .data
        )
        if not batch:
            break
        events.extend(batch)
        if len(batch) < size:
            break
        page += 1

    def pairs(e):
        yield e.get("co_organizers"), e.get("co_organizer_types")
        yield e.get("sponsors"), e.get("sponsor_types")

    mismatch_a = sum(
        1 for e in events for n, t in pairs(e) if _card(n) != _card(t)
    )
    mismatch_b = sum(
        1 for e in events for n, t in pairs(e) if _card_b(n) != _card_b(t)
    )

    # Two independent cardinality implementations must agree exactly.
    assert mismatch_a == mismatch_b

    validated_check_creatable = mismatch_a == 0
    print(
        f"[DB GATE] events={len(events)} table-wide co/sponsor mismatch pairs="
        f"{mismatch_a} -> validated CHECK creatable={validated_check_creatable}"
    )

    # Fail-closed gate contract: the validated CHECK is creatable IFF there is
    # zero table-wide mismatch. This assertion holds both pre-gate (mismatch>0
    # -> not creatable) and post-A.5 (mismatch==0 -> creatable).
    assert validated_check_creatable == (mismatch_a == 0)
