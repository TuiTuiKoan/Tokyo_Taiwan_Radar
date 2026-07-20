"""Unit tests for ``seed_authoritative_organizers`` (Wave 2 Phase D seed).

Every DB interaction is mocked, so nothing depends on a live database or on
migration 095's ``organizers.is_authoritative`` column. The dry-run path is
asserted to never write.
"""

from types import SimpleNamespace

import pytest

import seed_authoritative_organizers as seed


# --------------------------------------------------------------------------- #
# Fake Supabase client                                                         #
# --------------------------------------------------------------------------- #
class _OrgBuilder:
    """One-shot query builder for the ``organizers`` table."""

    def __init__(self, client):
        self.client = client
        self._cols = None
        self._eq = {}

    def select(self, cols):
        self._cols = cols
        return self

    def eq(self, col, val):
        self._eq[col] = val
        return self

    def limit(self, _n):
        return self

    def execute(self):
        # Schema probe: is_authoritative is absent pre-migration 095.
        if self.client.schema_missing and self._cols and "is_authoritative" in self._cols:
            raise RuntimeError("column organizers.is_authoritative does not exist")
        canonical = self._eq.get("canonical_name_ja")
        if canonical is not None:
            row = self.client.existing.get(canonical)
            return SimpleNamespace(data=[dict(row)] if row else [])
        return SimpleNamespace(data=[])

    def upsert(self, payload, on_conflict=None):
        self.client.upserts.append((payload, on_conflict))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=[]))


class _FakeClient:
    def __init__(self, existing=None, schema_missing=True):
        self.existing = existing or {}
        self.schema_missing = schema_missing
        self.upserts: list = []

    def table(self, name):
        assert name == "organizers", name
        return _OrgBuilder(self)


@pytest.fixture
def _patch_client(monkeypatch):
    def _install(client):
        monkeypatch.setattr(seed, "_get_client", lambda: client)
    return _install


# --------------------------------------------------------------------------- #
# 1. Pre-flight: alias / canonical collision (pure)                            #
# --------------------------------------------------------------------------- #
def test_alias_collision_detected():
    entries = [
        {"canonical_name_ja": "A社", "aliases": ["共用"], "organizer_type": "commercial_brand"},
        {"canonical_name_ja": "B社", "aliases": ["共用"], "organizer_type": "commercial_brand"},
    ]
    collisions = seed.check_alias_collisions(entries)
    assert "共用" in collisions
    assert collisions["共用"] == ["A社", "B社"]


def test_canonical_as_other_alias_is_collision():
    entries = [
        {"canonical_name_ja": "有隣堂", "aliases": [], "organizer_type": "commercial_brand"},
        {"canonical_name_ja": "株式会社有隣堂", "aliases": ["有隣堂"], "organizer_type": "commercial_brand"},
    ]
    collisions = seed.check_alias_collisions(entries)
    assert "有隣堂" in collisions


def test_no_collision_in_core_seed():
    # The shipped core list must itself be collision-free.
    assert seed.check_alias_collisions(seed.SEED_DATA) == {}


# --------------------------------------------------------------------------- #
# 2. Seed type validity (pure)                                                 #
# --------------------------------------------------------------------------- #
def test_core_seed_types_all_canonical():
    assert seed.validate_seed_types(seed.SEED_DATA) == []


def test_illegal_seed_type_flagged():
    bad = seed.validate_seed_types(
        [{"canonical_name_ja": "X", "organizer_type": "traveler"}]
    )
    assert bad == ["X"]


# --------------------------------------------------------------------------- #
# 3. evaluate_entry: existing type conflict → rejected                         #
# --------------------------------------------------------------------------- #
def test_existing_type_conflict_rejects(_patch_client):
    client = _FakeClient(
        existing={"紀伊國屋書店": {
            "id": "org-1", "canonical_name_ja": "紀伊國屋書店",
            "aliases": ["紀伊国屋書店"], "organizer_type": "cultural_institution",
        }},
        schema_missing=False,
    )
    _patch_client(client)
    entry = next(e for e in seed.SEED_DATA if e["canonical_name_ja"] == "紀伊國屋書店")
    plan = seed.evaluate_entry(client, entry, set())
    assert plan["type_conflict"] == "cultural_institution"
    assert plan["rejected"] is True
    assert plan["action"] == "update"


def test_matching_existing_type_not_conflict(_patch_client):
    client = _FakeClient(
        existing={"誠品書店": {
            "id": "org-2", "canonical_name_ja": "誠品書店",
            "aliases": [], "organizer_type": "commercial_brand",
        }},
        schema_missing=False,
    )
    _patch_client(client)
    entry = next(e for e in seed.SEED_DATA if e["canonical_name_ja"] == "誠品書店")
    plan = seed.evaluate_entry(client, entry, set())
    assert plan["type_conflict"] is None
    assert plan["rejected"] is False


def test_insert_action_when_not_present(_patch_client):
    client = _FakeClient(existing={}, schema_missing=False)
    _patch_client(client)
    entry = seed.SEED_DATA[0]
    plan = seed.evaluate_entry(client, entry, set())
    assert plan["action"] == "insert"
    assert plan["before"]["exists"] is False


# --------------------------------------------------------------------------- #
# 4. Schema compatibility: missing is_authoritative flagged, never crashes     #
# --------------------------------------------------------------------------- #
def test_schema_missing_flagged_not_ready():
    client = _FakeClient(schema_missing=True)
    assert seed.check_schema_ready(client) is False


def test_schema_ready_when_present():
    client = _FakeClient(schema_missing=False)
    assert seed.check_schema_ready(client) is True


def test_dry_run_graceful_when_schema_missing(_patch_client, capsys):
    client = _FakeClient(existing={}, schema_missing=True)
    _patch_client(client)
    result = seed.run(dry_run=True)
    assert result["schema_ready"] is False
    # Full plan still produced for every core entry despite the missing column.
    assert len(result["plans"]) == len(seed.SEED_DATA)
    out = capsys.readouterr().out
    assert "需先 apply migration 095" in out


# --------------------------------------------------------------------------- #
# 5. Dry-run must never write                                                  #
# --------------------------------------------------------------------------- #
def test_dry_run_writes_nothing(_patch_client):
    client = _FakeClient(existing={}, schema_missing=False)
    _patch_client(client)
    seed.run(dry_run=True)
    assert client.upserts == []


def test_dry_run_all_core_seedable_when_no_conflict(_patch_client):
    client = _FakeClient(existing={}, schema_missing=False)
    _patch_client(client)
    result = seed.run(dry_run=True)
    assert result["seedable"] == len(seed.SEED_DATA)
    assert result["rejected"] == 0
    assert client.upserts == []


# --------------------------------------------------------------------------- #
# 6. Manifest candidate discovery (human review only)                         #
# --------------------------------------------------------------------------- #
def test_load_manifest_candidates_filters_a1(tmp_path):
    import json
    manifest = {
        "entities": [
            {"canonical": "髙島屋", "aliases": ["高島屋"], "cohorts": ["A1"],
             "keyword_signals": {"dept": ["髙島屋"]}, "event_count": 5,
             "distinct_meaningful_types": ["commercial_brand"]},
            {"canonical": "ある市民の会", "aliases": [], "cohorts": ["A2"],
             "keyword_signals": {}, "event_count": 2,
             "distinct_meaningful_types": ["civic_group"]},
            # Already in the core seed list → excluded.
            {"canonical": "紀伊國屋書店", "aliases": [], "cohorts": ["A1"],
             "keyword_signals": {"bookstore": ["紀伊國屋書店"]}, "event_count": 3,
             "distinct_meaningful_types": ["commercial_brand"]},
        ]
    }
    p = tmp_path / "audit.json"
    p.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    cands = seed.load_manifest_candidates(str(p))
    names = {c["canonical"] for c in cands}
    assert "髙島屋" in names          # A1 dept candidate surfaced
    assert "ある市民の会" not in names  # A2 non-retail excluded
    assert "紀伊國屋書店" not in names  # already seeded → excluded
