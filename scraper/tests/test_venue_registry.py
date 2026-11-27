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

def _load(monkeypatch, rows):
    monkeypatch.setattr(venue_registry, "_get_client", lambda: _Client(rows))


def test_loose_match_ignores_width_spaces_and_middle_dots(monkeypatch):
    """#370 r042 and r048."""
    _load(monkeypatch, [
        _venue("clair", "シネマ・クレール 丸の内1・2"),
        _venue("united", "ユナイテッドシネマつくば", aliases=["ユナイテッド・シネマつくば"]),
    ])

    venue, preserve = venue_registry.lookup_venue_for_location("シネマ・クレール 丸の内１・２")
    assert venue["id"] == "clair" and preserve is False
    venue, preserve = venue_registry.lookup_venue_for_location("ユナイテッド・シネマ つくば")
    assert venue["id"] == "united" and preserve is False


def test_loose_match_never_resolves_a_clash_or_an_ambiguous_key(monkeypatch):
    _load(monkeypatch, [
        _venue("a", "シネマ・ノヴェチェント"),
        _venue("b", "シネマノヴェチェント"),          # same loose key as "a"
        _venue("c", "Ａ館", aliases=["共有名"]),
        _venue("d", "Ｂ館", aliases=["共有名"]),        # exact alias clash
    ])

    assert venue_registry.lookup_venue_for_location("シネマ ノヴェチェント") == (None, False)
    assert venue_registry.lookup_venue_for_location("共 有 名") == (None, False)
    # Exact names still resolve.
    assert venue_registry.lookup_venue_for_location("シネマノヴェチェント")[0]["id"] == "b"


def test_loose_match_is_whole_name_only(monkeypatch):
    """No prefix or suffix relaxation: r043, r044 and r047 stay unresolved."""
    _load(monkeypatch, [_venue("t", "東京芸術劇場"), _venue("s", "シネマート新宿")])

    assert venue_registry.lookup_venue_for_location("東京芸術劇場コンサートホール") == (None, False)
    assert venue_registry.lookup_venue_for_location("シネマート新宿スクリーン１") == (None, False)
    # The existing boundary rule is unchanged.
    venue, preserve = venue_registry.lookup_venue_for_location("東京芸術劇場 シアターイースト")
    assert venue["id"] == "t" and preserve is True


def test_loose_keys_do_not_hide_any_snapshot_venue(monkeypatch):
    """On the frozen registry snapshot, the loose index drops no exact key.

    Every canonical name and alias that the exact lookup resolves must still
    resolve to the same venue, and the loose fallback must add no new clash.
    """
    import json
    from pathlib import Path

    snapshot = json.loads((Path(__file__).parent / "golden" / "venue_registry_snapshot.json").read_text())
    rows = [{**_venue(v["id"], v["canonical_name_ja"], v.get("aliases") or []),
             "is_multi_venue": v.get("is_multi_venue", False)} for v in snapshot["venues"]]
    _load(monkeypatch, rows)

    names = {(v["canonical_name_ja"], v["id"]) for v in snapshot["venues"]}
    names |= {(a, v["id"]) for v in snapshot["venues"] for a in v.get("aliases") or []}
    venue_registry.lookup_venue("warm-up")
    ambiguous = set(venue_registry._AMBIGUOUS)
    for name, venue_id in names:
        if name.strip() in ambiguous:
            continue
        venue, _ = venue_registry.lookup_venue_for_location(name)
        assert venue is not None and venue["id"] == venue_id, name

    loose = venue_registry._loose_index()
    exact_keys = set(venue_registry._CANONICAL) | set(venue_registry._ALIASES)
    lost = {venue_registry._loose_key(k) for k in exact_keys} - set(loose)
    # Loose keys may only disappear because the exact lookup already rejected them.
    assert lost <= {venue_registry._loose_key(k) for k in ambiguous}
