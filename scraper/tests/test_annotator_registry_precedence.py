"""Registry-precedence tests for ``annotator._apply_organizer_registry``.

Every test monkeypatches ``annotator.lookup_organizer`` with a controlled fake,
so none of them depend on a live database or on migration 095's
``organizers.is_authoritative`` column. The final test pins the graceful-
degradation contract: when the registry is empty (every lookup → ``None``, the
real behaviour before migration 095 is applied) the helper is a field-for-field
no-op, even for GPT payloads whose parallel arrays have mismatched cardinality.
"""

import copy

import annotator


def _entity(organizer_type: str, name: str = "X") -> dict:
    return {
        "id": f"id-{name}-{organizer_type}",
        "canonical_name_ja": name,
        "aliases": [],
        "organizer_type": organizer_type,
    }


def _patch_lookup(monkeypatch, mapping: dict) -> None:
    """Patch annotator.lookup_organizer. mapping: {name: type}; misses → None."""

    def fake(name):
        if not name:
            return None
        t = mapping.get(name)
        return _entity(t, name) if t else None

    monkeypatch.setattr(annotator, "lookup_organizer", fake)


# --------------------------------------------------------------------------- #
# Primary organizer_type — scalar registry value → events.organizer_type[]     #
# --------------------------------------------------------------------------- #

def test_primary_case_a_empty_or_unknown_adopts_registry(monkeypatch):
    _patch_lookup(monkeypatch, {"誠品生活日本橋": "commercial_brand"})
    for current in (None, [], ["unknown"], ["unknown", "unknown"]):
        data = {"organizer": "誠品生活日本橋", "organizer_type": current}
        annotator._apply_organizer_registry({}, data)
        assert data["organizer_type"] == ["commercial_brand"]


def test_primary_case_b_already_contains_registry_preserved(monkeypatch):
    _patch_lookup(monkeypatch, {"某大学": "academic"})
    data = {"organizer": "某大学", "organizer_type": ["academic", "media"]}
    annotator._apply_organizer_registry({}, data)
    # Existing legal multi-type array containing the registry type is preserved
    # verbatim — no flatten, no reorder.
    assert data["organizer_type"] == ["academic", "media"]


def test_primary_case_c_single_conflict_registry_wins(monkeypatch):
    _patch_lookup(monkeypatch, {"有隣堂": "commercial_brand"})
    data = {"organizer": "有隣堂", "organizer_type": ["independent_venue"]}
    annotator._apply_organizer_registry({}, data)
    assert data["organizer_type"] == ["commercial_brand"]


def test_primary_case_d_multi_conflict_fail_closed(monkeypatch):
    _patch_lookup(monkeypatch, {"某団体": "government"})
    data = {"organizer": "某団体", "organizer_type": ["academic", "media"]}
    annotator._apply_organizer_registry({}, data)
    # >=2 legal types, none is the registry type → fail closed: keep the original
    # array untouched (no auto-flatten to the single scalar registry value).
    assert data["organizer_type"] == ["academic", "media"]


# --------------------------------------------------------------------------- #
# Co-organizer / Sponsor parallel arrays — per-index overlay, cardinality lock  #
# --------------------------------------------------------------------------- #

def test_co_hit_overrides_same_index_and_miss_preserves(monkeypatch):
    _patch_lookup(monkeypatch, {"紀伊國屋書店": "commercial_brand"})
    data = {
        "co_organizers": ["紀伊國屋書店", "地元の会"],
        "co_organizer_types": ["cultural_institution", "civic_group"],
    }
    annotator._apply_organizer_registry({}, data)
    # index0 registry hit overrides; index1 miss keeps existing legal value.
    assert data["co_organizer_types"] == ["commercial_brand", "civic_group"]


def test_sponsor_cardinality_maintained_when_types_shorter(monkeypatch):
    _patch_lookup(monkeypatch, {"A社": "commercial_brand"})
    data = {
        "sponsors": ["A社", "B団体", "C機構"],
        "sponsor_types": [],  # GPT returned mismatched (empty) types
    }
    annotator._apply_organizer_registry({}, data)
    assert data["sponsor_types"] == ["commercial_brand", "unknown", "unknown"]
    assert len(data["sponsor_types"]) == len(data["sponsors"])


def test_co_miss_preserves_valid_and_normalizes_invalid(monkeypatch):
    _patch_lookup(monkeypatch, {"A社": "commercial_brand"})
    data = {
        "co_organizers": ["A社", "既知団体", "不明"],
        "co_organizer_types": ["unknown", "civic_group", "bogus_value"],
    }
    annotator._apply_organizer_registry({}, data)
    # index0 hit; index1 miss keeps civic_group; index2 miss + invalid → unknown.
    assert data["co_organizer_types"] == ["commercial_brand", "civic_group", "unknown"]


# --------------------------------------------------------------------------- #
# Precedence: FC > registry, registry > existing unknown, raw names untouched   #
# --------------------------------------------------------------------------- #

def test_fc_protected_primary_type_not_touched(monkeypatch):
    _patch_lookup(monkeypatch, {"有隣堂": "commercial_brand"})
    data = {"organizer": "有隣堂", "organizer_type": ["independent_venue"]}
    # organizer_type is FC-locked → registry must skip it (FC restore wins later).
    annotator._apply_organizer_registry({}, data, {"organizer_type": '["independent_venue"]'})
    assert data["organizer_type"] == ["independent_venue"]


def test_fc_protected_co_types_not_touched(monkeypatch):
    _patch_lookup(monkeypatch, {"紀伊國屋書店": "commercial_brand"})
    data = {
        "co_organizers": ["紀伊國屋書店"],
        "co_organizer_types": ["cultural_institution"],
    }
    annotator._apply_organizer_registry({}, data, {"co_organizer_types": "x"})
    assert data["co_organizer_types"] == ["cultural_institution"]


def test_registry_never_overwrites_raw_name_text(monkeypatch):
    _patch_lookup(monkeypatch, {
        "有隣堂": "commercial_brand",
        "紀伊國屋書店": "commercial_brand",
        "A社": "government",
    })
    data = {
        "organizer": "有隣堂",
        "organizer_type": ["unknown"],
        "co_organizers": ["紀伊國屋書店"],
        "co_organizer_types": ["cultural_institution"],
        "sponsors": ["A社"],
        "sponsor_types": ["unknown"],
    }
    annotator._apply_organizer_registry({}, data)
    # Types are refined, but the raw name strings are never rewritten.
    assert data["organizer"] == "有隣堂"
    assert data["co_organizers"] == ["紀伊國屋書店"]
    assert data["sponsors"] == ["A社"]
    assert data["organizer_type"] == ["commercial_brand"]
    assert data["co_organizer_types"] == ["commercial_brand"]
    assert data["sponsor_types"] == ["government"]


# --------------------------------------------------------------------------- #
# Graceful equivalence — empty/unmigrated registry is a byte-for-byte no-op     #
# --------------------------------------------------------------------------- #

def test_graceful_noop_when_registry_empty(monkeypatch):
    monkeypatch.setattr(annotator, "lookup_organizer", lambda name: None)
    data = {
        "organizer": "誠品生活日本橋",
        "organizer_type": ["independent_venue"],
        "co_organizers": ["紀伊國屋書店", "地元の会"],
        # Deliberately mismatched cardinality (2 names, 1 type): the empty
        # registry must NOT "fix" it — that is A.5 / migration-095's job.
        "co_organizer_types": ["cultural_institution"],
        "sponsors": ["A社"],
        "sponsor_types": [],
    }
    before = copy.deepcopy(data)
    annotator._apply_organizer_registry({}, data)
    assert data == before
