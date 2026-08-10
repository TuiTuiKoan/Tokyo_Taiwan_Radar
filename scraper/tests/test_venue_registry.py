import logging
from types import SimpleNamespace

import pytest

import venue_registry


class _Query:
    def __init__(self, client):
        self.client = client
        self.authoritative_only = False

    def select(self, *_):
        return self

    def eq(self, field, value):
        assert (field, value) == ("is_authoritative", True)
        self.authoritative_only = True
        return self

    def execute(self):
        self.client.calls += 1
        assert self.authoritative_only
        if self.client.error is not None:
            raise self.client.error
        return SimpleNamespace(data=[dict(row) for row in self.client.rows])


class _Client:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error
        self.calls = 0

    def table(self, name):
        assert name == "venues"
        return _Query(self)


@pytest.fixture(autouse=True)
def _reset_registry():
    venue_registry._reset_cache_for_tests()
    yield
    venue_registry._reset_cache_for_tests()


def _venue(venue_id, canonical, aliases=()):
    return {
        "id": venue_id,
        "canonical_name_ja": canonical,
        "canonical_name_zh": f"{canonical}-zh",
        "canonical_name_en": f"{canonical}-en",
        "address": "東京都千代田区1-1",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "city": "千代田区",
        "homepage": "https://venue.example/",
        "aliases": list(aliases),
        "is_authoritative": True,
        "is_multi_venue": False,
        "business_hours": None,
    }


def _install(monkeypatch, client):
    monkeypatch.setattr(venue_registry, "_get_client", lambda: client)


def test_canonical_alias_unknown_and_trimmed_lookup(monkeypatch):
    client = _Client([_venue("venue-1", "正規館", ["別名館"])])
    _install(monkeypatch, client)

    assert venue_registry.lookup_venue(" 正規館 ")["id"] == "venue-1"
    assert venue_registry.lookup_venue(" 別名館 ")["id"] == "venue-1"
    assert venue_registry.lookup_venue("未知館") is None
    assert venue_registry.lookup_venue(None) is None
    assert venue_registry.lookup_venue("   ") is None
    assert client.calls == 1


def test_same_row_canonical_alias_repetition_is_not_ambiguous(monkeypatch):
    _install(monkeypatch, _Client([_venue("venue-1", "正規館", ["正規館"])]))

    assert venue_registry.lookup_venue("正規館")["id"] == "venue-1"


def test_location_lookup_preserves_alias_and_canonical_subspace(monkeypatch):
    venue = _venue("venue-1", "正規館", ["正規館 イベントスペース"])
    venue["business_hours"] = "平日 11:00～20:00"
    _install(monkeypatch, _Client([venue]))

    canonical, preserve_canonical = venue_registry.lookup_venue_for_location("正規館")
    alias, preserve_alias = venue_registry.lookup_venue_for_location(
        "正規館 イベントスペース"
    )
    subspace, preserve_subspace = venue_registry.lookup_venue_for_location(
        "正規館 書籍レジ"
    )

    assert canonical["id"] == alias["id"] == subspace["id"] == "venue-1"
    assert subspace["business_hours"] == "平日 11:00～20:00"
    assert preserve_canonical is False
    assert preserve_alias is True
    assert preserve_subspace is True


def test_location_lookup_parent_match_is_boundary_guarded_and_canonical_only(monkeypatch):
    _install(monkeypatch, _Client([_venue("venue-1", "正規館", ["広い別名"])]))

    alias, preserve_alias = venue_registry.lookup_venue_for_location("広い別名")
    assert alias["id"] == "venue-1"
    assert preserve_alias is False
    assert venue_registry.lookup_venue_for_location("正規館別館") == (None, False)
    assert venue_registry.lookup_venue_for_location("広い別名 展示室") == (None, False)


@pytest.mark.parametrize(
    "rows,key",
    [
        ([_venue("venue-1", "同名館"), _venue("venue-2", "同名館")], "同名館"),
        ([_venue("venue-1", "A館", ["共通名"]), _venue("venue-2", "B館", ["共通名"])], "共通名"),
    ],
)
def test_same_tier_collisions_fail_closed(monkeypatch, caplog, rows, key):
    _install(monkeypatch, _Client(rows))

    with caplog.at_level(logging.ERROR, logger="venue_registry"):
        assert venue_registry.lookup_venue(key) is None

    assert "multiple authoritative venues" in caplog.text


@pytest.mark.parametrize(
    "rows",
    [
        [_venue("venue-1", "衝突名"), _venue("venue-2", "別館", ["衝突名"])],
        [_venue("venue-2", "別館", ["衝突名"]), _venue("venue-1", "衝突名")],
    ],
)
def test_cross_tier_collisions_fail_closed_regardless_of_row_order(monkeypatch, caplog, rows):
    _install(monkeypatch, _Client(rows))

    with caplog.at_level(logging.ERROR, logger="venue_registry"):
        assert venue_registry.lookup_venue("衝突名") is None

    assert "cross-tier" in caplog.text


def test_load_failure_caches_empty_registry(monkeypatch, caplog):
    client = _Client(error=RuntimeError("database unavailable"))
    _install(monkeypatch, client)

    with caplog.at_level(logging.WARNING, logger="venue_registry"):
        assert venue_registry.lookup_venue("正規館") is None

    client.error = None
    client.rows = [_venue("venue-1", "正規館")]
    assert venue_registry.lookup_venue("正規館") is None
    assert client.calls == 1
    assert "caching empty registry" in caplog.text


def test_empty_registry_is_cached(monkeypatch):
    client = _Client()
    _install(monkeypatch, client)

    assert venue_registry.lookup_venue("A館") is None
    assert venue_registry.lookup_venue("B館") is None
    assert client.calls == 1


def test_reset_reloads_registry(monkeypatch):
    client = _Client([_venue("venue-1", "旧館")])
    _install(monkeypatch, client)

    assert venue_registry.lookup_venue("旧館")["id"] == "venue-1"
    client.rows = [_venue("venue-2", "新館")]
    assert venue_registry.lookup_venue("新館") is None

    venue_registry._reset_cache_for_tests()

    assert venue_registry.lookup_venue("旧館") is None
    assert venue_registry.lookup_venue("新館")["id"] == "venue-2"
    assert client.calls == 2