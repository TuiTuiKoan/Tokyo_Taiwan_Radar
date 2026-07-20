"""Unit tests for organizer_registry + _populate_entity_fks organizer resolution.

Mocks the Supabase client so nothing depends on the live ``is_authoritative``
column (migration 095 is not applied in CI at test time).
"""

import logging
from types import SimpleNamespace

import pytest

import organizer_registry
from organizer_registry import lookup_organizer
from database import _populate_entity_fks


# --------------------------------------------------------------------------- #
# organizer_registry fakes                                                     #
# --------------------------------------------------------------------------- #
class _RegistrySelect:
    def __init__(self, rows, error):
        self._rows = rows
        self._error = error

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def execute(self):
        if self._error is not None:
            raise self._error
        return SimpleNamespace(data=[dict(r) for r in self._rows])


class _RegistryClient:
    def __init__(self, rows=None, error=None):
        self._rows = rows or []
        self._error = error

    def table(self, name):
        assert name == "organizers", name
        return _RegistrySelect(self._rows, self._error)


@pytest.fixture(autouse=True)
def _reset_registry():
    organizer_registry.reset_cache()
    yield
    organizer_registry.reset_cache()


def _install_registry(monkeypatch, rows=None, error=None):
    monkeypatch.setattr(
        organizer_registry,
        "_get_client",
        lambda: _RegistryClient(rows=rows, error=error),
    )


# --------------------------------------------------------------------------- #
# 1. canonical exact hit                                                       #
# --------------------------------------------------------------------------- #
def test_canonical_exact_hit(monkeypatch):
    _install_registry(monkeypatch, rows=[
        {"id": "org-1", "canonical_name_ja": "誠品生活",
         "aliases": ["誠品"], "organizer_type": "commercial_brand"},
    ])
    hit = lookup_organizer("誠品生活")
    assert hit is not None
    assert hit["id"] == "org-1"
    assert hit["organizer_type"] == "commercial_brand"


# --------------------------------------------------------------------------- #
# 2. alias exact hit                                                           #
# --------------------------------------------------------------------------- #
def test_alias_exact_hit(monkeypatch):
    _install_registry(monkeypatch, rows=[
        {"id": "org-1", "canonical_name_ja": "誠品生活",
         "aliases": ["誠品", "eslite"], "organizer_type": "commercial_brand"},
    ])
    hit = lookup_organizer("eslite")
    assert hit is not None
    assert hit["id"] == "org-1"
    assert hit["organizer_type"] == "commercial_brand"


# --------------------------------------------------------------------------- #
# 3. unknown name / empty input                                                #
# --------------------------------------------------------------------------- #
def test_unknown_name_returns_none(monkeypatch):
    _install_registry(monkeypatch, rows=[
        {"id": "org-1", "canonical_name_ja": "誠品生活",
         "aliases": ["誠品"], "organizer_type": "commercial_brand"},
    ])
    assert lookup_organizer("紀伊國屋書店") is None


def test_empty_and_whitespace_name_returns_none(monkeypatch):
    _install_registry(monkeypatch, rows=[
        {"id": "org-1", "canonical_name_ja": "誠品生活",
         "aliases": [], "organizer_type": "commercial_brand"},
    ])
    assert lookup_organizer(None) is None
    assert lookup_organizer("") is None
    assert lookup_organizer("   ") is None


# --------------------------------------------------------------------------- #
# 4. duplicate alias / duplicate canonical -> fail closed                      #
# --------------------------------------------------------------------------- #
def test_duplicate_alias_fail_closed(monkeypatch, caplog):
    _install_registry(monkeypatch, rows=[
        {"id": "org-1", "canonical_name_ja": "A社",
         "aliases": ["共用別名"], "organizer_type": "commercial_brand"},
        {"id": "org-2", "canonical_name_ja": "B社",
         "aliases": ["共用別名"], "organizer_type": "civic_group"},
    ])
    with caplog.at_level(logging.ERROR, logger="organizer_registry"):
        assert lookup_organizer("共用別名") is None
    # Unambiguous canonical names still resolve deterministically.
    assert lookup_organizer("A社")["id"] == "org-1"
    assert lookup_organizer("B社")["id"] == "org-2"
    assert "multiple authoritative organizers" in caplog.text


def test_duplicate_canonical_fail_closed(monkeypatch, caplog):
    _install_registry(monkeypatch, rows=[
        {"id": "org-1", "canonical_name_ja": "同名社",
         "aliases": [], "organizer_type": "commercial_brand"},
        {"id": "org-2", "canonical_name_ja": "同名社",
         "aliases": [], "organizer_type": "civic_group"},
    ])
    with caplog.at_level(logging.ERROR, logger="organizer_registry"):
        assert lookup_organizer("同名社") is None
    assert "multiple authoritative organizers" in caplog.text


def test_canonical_precedence_over_alias(monkeypatch):
    # "共用名" is org-1's canonical AND org-2's alias — canonical wins, not rejected.
    _install_registry(monkeypatch, rows=[
        {"id": "org-1", "canonical_name_ja": "共用名",
         "aliases": [], "organizer_type": "commercial_brand"},
        {"id": "org-2", "canonical_name_ja": "別名社",
         "aliases": ["共用名"], "organizer_type": "civic_group"},
    ])
    hit = lookup_organizer("共用名")
    assert hit is not None
    assert hit["id"] == "org-1"


# --------------------------------------------------------------------------- #
# 5. graceful degradation: load failure -> empty registry, never raise         #
# --------------------------------------------------------------------------- #
def test_graceful_load_failure_returns_empty(monkeypatch, caplog):
    _install_registry(monkeypatch, error=Exception(
        "column organizers.is_authoritative does not exist"))
    with caplog.at_level(logging.DEBUG, logger="organizer_registry"):
        # Must not raise, and every lookup must return None.
        assert lookup_organizer("誠品生活") is None
        assert lookup_organizer("誠品") is None
    assert "may not be migrated yet" in caplog.text


# --------------------------------------------------------------------------- #
# _populate_entity_fks fakes                                                    #
# --------------------------------------------------------------------------- #
class _OrgQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []

    def select(self, _cols):
        return self

    def in_(self, field, values):
        self.filters.append(("in", field, list(values)))
        return self

    def contains(self, field, value):
        self.filters.append(("contains", field, list(value)))
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def execute(self):
        return SimpleNamespace(data=self.client._resolve(self))


class _OrgClient:
    def __init__(self, organizers):
        self._organizers = organizers

    def table(self, name):
        return _OrgQuery(self, name)

    def _resolve(self, q):
        if q.table != "organizers":
            return []
        for kind, field, value in q.filters:
            if kind == "in" and field == "canonical_name_ja":
                wanted = set(value)
                return [dict(o) for o in self._organizers
                        if o.get("canonical_name_ja") in wanted]
            if kind == "contains" and field == "aliases":
                needle = value[0]
                return [dict(o) for o in self._organizers
                        if needle in (o.get("aliases") or [])]
        return []


# --------------------------------------------------------------------------- #
# 6. _populate_entity_fks organizer resolution                                 #
# --------------------------------------------------------------------------- #
def test_populate_fks_alias_single_hit_sets_id_and_keeps_raw_text():
    client = _OrgClient([
        {"id": "org-1", "canonical_name_ja": "誠品生活股份有限公司",
         "aliases": ["誠品"], "homepage": None},
    ])
    row = {"organizer": "誠品", "source_name": "src", "source_id": "1"}

    _populate_entity_fks(client, [row])

    assert row["organizer_id"] == "org-1"
    # Raw organizer text must NOT be overwritten with the canonical name.
    assert row["organizer"] == "誠品"


def test_populate_fks_alias_collision_fail_closed(caplog):
    client = _OrgClient([
        {"id": "org-1", "canonical_name_ja": "A社", "aliases": ["共用"], "homepage": None},
        {"id": "org-2", "canonical_name_ja": "B社", "aliases": ["共用"], "homepage": None},
    ])
    row = {"organizer": "共用", "source_name": "src", "source_id": "1"}

    with caplog.at_level(logging.WARNING, logger="database"):
        _populate_entity_fks(client, [row])

    # Ambiguous alias -> organizer_id left unset (fail closed), raw text intact.
    assert "organizer_id" not in row
    assert row["organizer"] == "共用"
    assert "fail closed" in caplog.text


def test_populate_fks_canonical_hit_preserves_raw_text():
    client = _OrgClient([
        {"id": "org-9", "canonical_name_ja": "誠品生活", "aliases": [], "homepage": None},
    ])
    row = {"organizer": "誠品生活", "source_name": "src", "source_id": "1"}

    _populate_entity_fks(client, [row])

    assert row["organizer_id"] == "org-9"
    assert row["organizer"] == "誠品生活"
