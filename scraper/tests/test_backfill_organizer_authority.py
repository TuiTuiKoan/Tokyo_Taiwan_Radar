"""Unit tests for ``backfill_organizer_authority`` (Wave 2 Phase D backfill).

The backfill delegates its type-mutation logic to
``annotator._apply_organizer_registry`` (single source of truth), so these
tests verify the *wiring*: field copy, four-case outcome flow-through,
organizer_id FK resolution, FC-skip accounting, and that the dry-run never
writes. The registry is faked (no DB, no migration 095 needed) by patching
``lookup_organizer`` in BOTH the annotator and backfill modules.
"""

from types import SimpleNamespace

import pytest

import annotator
import backfill_organizer_authority as backfill


# --------------------------------------------------------------------------- #
# Fake registry — patched into both modules so the primary type overlay        #
# (annotator) and the organizer_id FK (backfill) see the same entities.        #
# --------------------------------------------------------------------------- #
def _entity(name, org_type, ent_id=None):
    return {
        "id": ent_id or f"org-{name}",
        "canonical_name_ja": name,
        "aliases": [],
        "organizer_type": org_type,
    }


@pytest.fixture
def fake_registry(monkeypatch):
    """Install a name→entity map into both annotator and backfill lookups."""
    def _install(mapping):
        def _lookup(name):
            return mapping.get(name) if name else None
        monkeypatch.setattr(annotator, "lookup_organizer", _lookup)
        monkeypatch.setattr(backfill, "lookup_organizer", _lookup)
    return _install


# --------------------------------------------------------------------------- #
# Primary organizer_type — four cases (outcome flows through plan_event)        #
# --------------------------------------------------------------------------- #
def test_primary_case_a_empty_adopts_registry(fake_registry):
    fake_registry({"有隣堂": _entity("有隣堂", "commercial_brand", "org-y")})
    event = {"id": "e1", "organizer": "有隣堂", "organizer_type": ["unknown"],
             "organizer_id": "org-y"}
    p = backfill.plan_event(event, set())
    assert p["after"]["organizer_type"] == ["commercial_brand"]
    assert p["changed"] is True


def test_primary_case_b_already_contains_preserved(fake_registry):
    fake_registry({"某大学": _entity("某大学", "academic", "org-u")})
    event = {"id": "e2", "organizer": "某大学",
             "organizer_type": ["academic", "media"], "organizer_id": "org-u"}
    p = backfill.plan_event(event, set())
    # Preserved verbatim (no flatten / reorder), no org_id change.
    assert p["after"]["organizer_type"] == ["academic", "media"]
    assert p["org_id_change"] is None
    assert p["changed"] is False


def test_primary_case_c_single_conflict_registry_wins(fake_registry):
    fake_registry({"誠品書店": _entity("誠品書店", "commercial_brand", "org-e")})
    event = {"id": "e3", "organizer": "誠品書店",
             "organizer_type": ["independent_venue"], "organizer_id": "org-e"}
    p = backfill.plan_event(event, set())
    assert p["after"]["organizer_type"] == ["commercial_brand"]
    assert p["primary_conflict"] is False


def test_primary_case_d_multi_conflict_fail_closed(fake_registry):
    fake_registry({"複合団体": _entity("複合団体", "government", "org-g")})
    event = {"id": "e4", "organizer": "複合団体",
             "organizer_type": ["academic", "media"], "organizer_id": "org-g"}
    p = backfill.plan_event(event, set())
    # Fail closed: original multi-type array preserved, flagged for manual queue.
    assert p["after"]["organizer_type"] == ["academic", "media"]
    assert p["primary_conflict"] is True
    assert p["changed"] is False


# --------------------------------------------------------------------------- #
# Co-organizer / sponsor cardinality parity                                    #
# --------------------------------------------------------------------------- #
def test_sponsor_cardinality_parity(fake_registry):
    fake_registry({"A社": _entity("A社", "commercial_brand", "org-a")})
    event = {
        "id": "e5", "organizer": None, "organizer_id": None,
        "sponsors": ["A社", "B社", "C社"], "sponsor_types": [],
    }
    p = backfill.plan_event(event, set())
    after = p["after"]["sponsor_types"]
    assert len(after) == 3                       # parity with sponsors
    assert after[0] == "commercial_brand"        # registry-resolved index
    assert after[1] == "unknown" and after[2] == "unknown"
    assert p["unknowns"] == 2


def test_co_organizer_untouched_when_no_registry_hit(fake_registry):
    fake_registry({})  # empty registry
    event = {
        "id": "e6", "organizer": None, "organizer_id": None,
        "co_organizers": ["X会", "Y会"], "co_organizer_types": ["civic_group"],
    }
    p = backfill.plan_event(event, set())
    # No hit anywhere → full no-op (array left exactly as-is).
    assert p["after"]["co_organizer_types"] == ["civic_group"]
    assert p["changed"] is False


# --------------------------------------------------------------------------- #
# field_corrections protection (FC > registry)                                 #
# --------------------------------------------------------------------------- #
def test_fc_protected_primary_skipped_and_counted(fake_registry):
    fake_registry({"有隣堂": _entity("有隣堂", "commercial_brand", "org-y")})
    event = {"id": "e7", "organizer": "有隣堂",
             "organizer_type": ["academic"], "organizer_id": "org-y"}
    p = backfill.plan_event(event, {"organizer_type"})
    # FC lock → primary type untouched despite the registry hit.
    assert p["after"]["organizer_type"] == ["academic"]
    assert "organizer_type" in p["fc_skips"]


def test_fc_protected_organizer_id_not_set(fake_registry):
    fake_registry({"有隣堂": _entity("有隣堂", "commercial_brand", "org-y")})
    event = {"id": "e8", "organizer": "有隣堂",
             "organizer_type": ["commercial_brand"], "organizer_id": None}
    p = backfill.plan_event(event, {"organizer_id"})
    # organizer_id is FC-locked → no FK write even though the primary resolves.
    assert p["org_id_change"] is None
    assert "organizer_id" in p["fc_skips"]


# --------------------------------------------------------------------------- #
# organizer_id FK resolution                                                   #
# --------------------------------------------------------------------------- #
def test_organizer_id_set_when_registry_hit(fake_registry):
    fake_registry({"有隣堂": _entity("有隣堂", "commercial_brand", "org-yurindo")})
    event = {"id": "e9", "organizer": "有隣堂",
             "organizer_type": ["commercial_brand"], "organizer_id": None}
    p = backfill.plan_event(event, set())
    assert p["org_id_change"] == (None, "org-yurindo")
    assert p["_write"].get("organizer_id") == "org-yurindo"
    assert p["changed"] is True


def test_registry_empty_is_noop(fake_registry):
    fake_registry({})  # pre-095 empty registry
    event = {"id": "e10", "organizer": "有隣堂",
             "organizer_type": ["cultural_institution"], "organizer_id": "org-x",
             "co_organizers": ["Z会"], "co_organizer_types": ["civic_group"]}
    p = backfill.plan_event(event, set())
    assert p["changed"] is False
    assert p["registry_hit"] is False
    assert p["before"] == p["after"]


# --------------------------------------------------------------------------- #
# run() dry-run must never write                                               #
# --------------------------------------------------------------------------- #
class _EventsBuilder:
    def __init__(self, client):
        self.client = client
        self._update = None
        self._eq = {}
        self._range = (0, 999)

    def select(self, _cols):
        return self

    def eq(self, col, val):
        self._eq[col] = val
        return self

    def range(self, a, b):
        self._range = (a, b)
        return self

    def update(self, payload):
        self._update = payload
        return self

    def execute(self):
        if self._update is not None:
            self.client.updates.append((self._eq.get("id"), self._update))
            return SimpleNamespace(data=[])
        if self._range[0] == 0:
            return SimpleNamespace(data=[dict(e) for e in self.client.events])
        return SimpleNamespace(data=[])


class _FCBuilder:
    def __init__(self, client):
        self.client = client
        self._range = (0, 999)

    def select(self, _cols):
        return self

    def range(self, a, b):
        self._range = (a, b)
        return self

    def execute(self):
        if self._range[0] == 0:
            return SimpleNamespace(data=list(self.client.fc_rows))
        return SimpleNamespace(data=[])


class _FakeBackfillClient:
    def __init__(self, events, fc_rows=None):
        self.events = events
        self.fc_rows = fc_rows or []
        self.updates: list = []

    def table(self, name):
        if name == "events":
            return _EventsBuilder(self)
        if name == "field_corrections":
            return _FCBuilder(self)
        raise AssertionError(name)


def test_run_dry_run_writes_nothing(monkeypatch, fake_registry):
    fake_registry({"有隣堂": _entity("有隣堂", "commercial_brand", "org-y")})
    client = _FakeBackfillClient(
        events=[
            {"id": "e-1", "organizer": "有隣堂", "organizer_id": None,
             "organizer_type": ["unknown"], "co_organizers": None,
             "co_organizer_types": None, "sponsors": None, "sponsor_types": None},
            {"id": "e-2", "organizer": "無名", "organizer_id": None,
             "organizer_type": ["academic"], "co_organizers": None,
             "co_organizer_types": None, "sponsors": None, "sponsor_types": None},
        ],
    )
    monkeypatch.setattr(backfill, "_get_client", lambda: client)
    result = backfill.run(dry_run=True)
    # One event resolves and would change, but dry-run writes nothing.
    assert result["changed"] == 1
    assert result["registry_hits"] == 1
    assert client.updates == []


def test_run_dry_run_empty_registry_zero_coverage(monkeypatch, fake_registry):
    fake_registry({})  # pre-095: registry empty → zero coverage expected
    client = _FakeBackfillClient(
        events=[
            {"id": "e-1", "organizer": "有隣堂", "organizer_id": "org-x",
             "organizer_type": ["cultural_institution"], "co_organizers": None,
             "co_organizer_types": None, "sponsors": None, "sponsor_types": None},
        ],
    )
    monkeypatch.setattr(backfill, "_get_client", lambda: client)
    result = backfill.run(dry_run=True)
    assert result["events"] == 1
    assert result["changed"] == 0
    assert result["registry_hits"] == 0
    assert client.updates == []
