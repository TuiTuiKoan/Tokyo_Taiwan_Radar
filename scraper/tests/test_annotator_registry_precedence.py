"""Registry-precedence tests for deterministic annotator overlays.

Every test monkeypatches registry and homepage lookups with controlled fakes, so
none depend on a live database, network access, or registry migrations.
"""

import copy
import inspect

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


def _venue_record() -> dict:
    return {
        "id": "venue-eslite",
        "canonical_name_ja": "誠品生活日本橋",
        "canonical_name_zh": "誠品生活日本橋",
        "canonical_name_en": "Eslite Spectrum Nihonbashi",
        "address": "東京都中央区日本橋室町3-2-1",
        "prefecture": "東京都",
        "prefectures": ["東京都"],
        "homepage": "https://www.eslitespectrum.jp/about/store/nihonbashi",
        "is_multi_venue": False,
        "business_hours": "平日 11:00～20:00、土日祝 10:00～20:00",
    }


def _patch_venue_services(
    monkeypatch,
    *,
    venue: dict | None,
    preserve_venue_label: bool = False,
    homepage: str | None = None,
) -> dict[str, list]:
    calls = {"lookup": [], "homepage": []}

    def fake_lookup(name):
        calls["lookup"].append(name)
        return venue, preserve_venue_label

    def fake_homepage(name, address=None):
        calls["homepage"].append((name, address))
        return homepage

    monkeypatch.setattr(annotator, "lookup_venue_for_location", fake_lookup)
    monkeypatch.setattr(annotator, "_search_venue_homepage", fake_homepage)
    return calls


def test_venue_ordinary_exact_alias_canonicalizes_names_and_metadata(monkeypatch):
    venue = _venue_record()
    calls = _patch_venue_services(monkeypatch, venue=venue)
    update_data = {"location_name": "誠品生活日本橋店"}

    result = annotator._apply_venue_registry({}, update_data, {})

    assert result == annotator.VenueRegistryResult(
        annotator.VenueRegistryOutcome.MATCHED,
        False,
        0,
    )
    assert update_data == {
        "location_name": venue["canonical_name_ja"],
        "location_name_zh": venue["canonical_name_zh"],
        "location_name_en": venue["canonical_name_en"],
        "location_address": venue["address"],
        "location_prefectures": venue["prefectures"],
        "location_url": venue["homepage"],
        "venue_id": venue["id"],
        "business_hours": venue["business_hours"],
    }
    assert calls == {"lookup": ["誠品生活日本橋店"], "homepage": []}


def _assert_subspace_two_payloads(
    monkeypatch,
    *,
    names: tuple[str, str, str],
) -> None:
    venue = _venue_record()
    _patch_venue_services(
        monkeypatch,
        venue=venue,
        preserve_venue_label=True,
    )
    name_ja, name_zh, name_en = names
    update_data = {
        "location_name": name_ja,
        "location_name_zh": name_zh,
        "location_name_en": name_en,
    }
    annotation = {
        "location_name_zh": venue["canonical_name_zh"],
        "location_name_en": venue["canonical_name_en"],
    }

    result = annotator._apply_venue_registry({}, update_data, {})
    localized = annotator._build_localized_location_data(
        annotation,
        {},
        update_data,
        result.preserve_venue_label,
        False,
        False,
        {},
    )

    assert result.outcome is annotator.VenueRegistryOutcome.MATCHED
    assert result.preserve_venue_label is True
    assert (
        update_data["location_name"],
        update_data["location_name_zh"],
        update_data["location_name_en"],
    ) == names
    assert localized["location_name_zh"] == name_zh
    assert localized["location_name_en"] == name_en
    assert update_data["location_address"] == venue["address"]
    assert update_data["location_prefectures"] == venue["prefectures"]
    assert update_data["location_url"] == venue["homepage"]
    assert update_data["venue_id"] == venue["id"]


def test_venue_exact_subspace_alias_preserves_both_payloads(monkeypatch):
    _assert_subspace_two_payloads(
        monkeypatch,
        names=(
            "誠品生活日本橋 expo",
            "誠品生活日本橋 expo 展演空間",
            "Eslite Spectrum Nihonbashi expo",
        ),
    )


def test_venue_canonical_prefix_subspace_preserves_both_payloads(monkeypatch):
    _assert_subspace_two_payloads(
        monkeypatch,
        names=(
            "誠品生活日本橋 書籍レジ",
            "誠品生活日本橋 書籍櫃檯",
            "Eslite Spectrum Nihonbashi Book Counter",
        ),
    )


def test_venue_subspace_missing_locale_uses_gpt_not_parent_label(monkeypatch):
    venue = _venue_record()
    _patch_venue_services(
        monkeypatch,
        venue=venue,
        preserve_venue_label=True,
    )
    update_data = {
        "location_name": "誠品生活日本橋 各ショップ",
        "location_name_zh": "誠品生活日本橋 各店舖",
    }
    annotation = {"location_name_en": "Participating Eslite shops"}

    result = annotator._apply_venue_registry({}, update_data, {})
    localized = annotator._build_localized_location_data(
        annotation,
        {},
        update_data,
        result.preserve_venue_label,
        False,
        False,
        {},
    )

    assert "location_name_en" not in update_data
    assert localized["location_name_zh"] == "誠品生活日本橋 各店舖"
    assert localized["location_name_en"] == "Participating Eslite shops"
    assert localized["location_name_en"] != venue["canonical_name_en"]


def test_venue_empty_hours_inherit_authoritative_hours(monkeypatch):
    venue = _venue_record()
    _patch_venue_services(monkeypatch, venue=venue)
    update_data = {"location_name": venue["canonical_name_ja"]}

    result = annotator._apply_venue_registry({}, update_data, {})

    assert update_data["business_hours"] == venue["business_hours"]
    assert result.protected_assignment_attempts == 0


def test_venue_current_annotation_hours_are_preserved(monkeypatch):
    venue = _venue_record()
    _patch_venue_services(monkeypatch, venue=venue)
    update_data = {
        "location_name": venue["canonical_name_ja"],
        "business_hours": "8/22 12:00～20:00、8/23 12:00～19:00",
    }

    result = annotator._apply_venue_registry({}, update_data, {})

    assert update_data["business_hours"] == "8/22 12:00～20:00、8/23 12:00～19:00"
    assert result.protected_assignment_attempts == 0


def test_venue_stored_event_hours_are_preserved(monkeypatch):
    venue = _venue_record()
    _patch_venue_services(monkeypatch, venue=venue)
    event = {"business_hours": "8/30 14:00～16:00"}
    update_data = {"location_name": venue["canonical_name_ja"]}

    result = annotator._apply_venue_registry(event, update_data, {})

    assert "business_hours" not in update_data
    assert event["business_hours"] == "8/30 14:00～16:00"
    assert result.protected_assignment_attempts == 0


def test_venue_empty_fc_sentinel_blocks_hours_and_counts_one(monkeypatch):
    venue = _venue_record()
    _patch_venue_services(monkeypatch, venue=venue)
    update_data = {"location_name": venue["canonical_name_ja"]}

    result = annotator._apply_venue_registry(
        {},
        update_data,
        {"business_hours": ""},
    )

    assert "business_hours" not in update_data
    assert result.protected_assignment_attempts == 1


def test_venue_protected_location_candidates_count_exactly_two(monkeypatch):
    venue = _venue_record()
    _patch_venue_services(monkeypatch, venue=venue)
    update_data = {"location_name": venue["canonical_name_ja"]}

    result = annotator._apply_venue_registry(
        {},
        update_data,
        {"location_address": "", "venue_id": "locked"},
    )

    assert result.protected_assignment_attempts == 2
    assert "location_address" not in update_data
    assert "venue_id" not in update_data
    assert update_data["location_prefectures"] == venue["prefectures"]


def test_venue_protected_attempt_wiring_is_single():
    source = inspect.getsource(annotator.annotate_pending_events)

    assert source.count("field_protect_hits += venue_protected_attempts") == 1


def test_venue_pure_publication_bypasses_lookup_and_homepage(monkeypatch):
    calls = _patch_venue_services(monkeypatch, venue=_venue_record())
    update_data = {
        "event_form": ["publication"],
        "location_name": "誠品生活日本橋",
    }

    result = annotator._apply_venue_registry({}, update_data, {})

    assert result == annotator.VenueRegistryResult(
        annotator.VenueRegistryOutcome.BYPASSED,
        False,
        0,
    )
    assert calls == {"lookup": [], "homepage": []}


def test_venue_multi_city_bypasses_lookup_and_homepage(monkeypatch):
    calls = _patch_venue_services(monkeypatch, venue=_venue_record())
    update_data = {"location_name": "東京・大阪"}

    result = annotator._apply_venue_registry({}, update_data, {})

    assert result == annotator.VenueRegistryResult(
        annotator.VenueRegistryOutcome.BYPASSED,
        False,
        0,
    )
    assert calls == {"lookup": [], "homepage": []}


def test_venue_match_calls_lookup_once_and_never_searches_homepage(monkeypatch):
    venue = _venue_record()
    calls = _patch_venue_services(monkeypatch, venue=venue)
    update_data = {"location_name": venue["canonical_name_ja"]}

    result = annotator._apply_venue_registry({}, update_data, {})

    assert result.outcome is annotator.VenueRegistryOutcome.MATCHED
    assert calls == {"lookup": [venue["canonical_name_ja"]], "homepage": []}


def test_venue_miss_empty_urls_searches_once_and_applies_result(monkeypatch):
    homepage = "https://venue.example/official"
    calls = _patch_venue_services(
        monkeypatch,
        venue=None,
        homepage=homepage,
    )
    update_data = {
        "location_name": "未登録会場",
        "location_address": "東京都中央区1-1",
    }

    result = annotator._apply_venue_registry({}, update_data, {})

    assert result.outcome is annotator.VenueRegistryOutcome.MISS
    assert result.preserve_venue_label is False
    assert update_data["location_url"] == homepage
    assert calls == {
        "lookup": ["未登録会場"],
        "homepage": [("未登録会場", "東京都中央区1-1")],
    }


def test_venue_miss_assembled_url_skips_homepage_search(monkeypatch):
    calls = _patch_venue_services(
        monkeypatch,
        venue=None,
        homepage="https://unexpected.example/",
    )
    update_data = {
        "location_name": "未登録会場",
        "location_url": "https://assembled.example/",
    }

    result = annotator._apply_venue_registry({}, update_data, {})

    assert result.outcome is annotator.VenueRegistryOutcome.MISS
    assert update_data["location_url"] == "https://assembled.example/"
    assert calls == {"lookup": ["未登録会場"], "homepage": []}


def test_venue_miss_stored_url_skips_homepage_search(monkeypatch):
    calls = _patch_venue_services(
        monkeypatch,
        venue=None,
        homepage="https://unexpected.example/",
    )
    event = {"location_url": "https://stored.example/"}
    update_data = {"location_name": "未登録会場"}

    result = annotator._apply_venue_registry(event, update_data, {})

    assert result.outcome is annotator.VenueRegistryOutcome.MISS
    assert "location_url" not in update_data
    assert calls == {"lookup": ["未登録会場"], "homepage": []}
