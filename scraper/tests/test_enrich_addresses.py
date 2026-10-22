import enrich_addresses as ea


def test_is_vague_flags_missing_and_area_only_addresses():
    assert ea.is_vague(None)
    assert ea.is_vague("  ")
    assert ea.is_vague("東京都")
    assert ea.is_vague("渋谷区")
    assert not ea.is_vague("東京都渋谷区神宮前1-14-30")


def test_sibling_map_uses_the_one_address_events_agree_on():
    rows = [
        {"location_name": "A館", "location_address": "東京都港区1-1", "location_address_zh": None},
        {"location_name": "A館", "location_address": "東京都港区1-1", "location_address_zh": "東京都港區1-1",
         "location_address_en": "1-1 Minato"},
        {"location_name": "A館", "location_address": "東京都"},  # vague rows never vote
    ]
    assert ea.build_sibling_map(rows) == {
        "A館": {
            "location_address": "東京都港区1-1",
            "location_address_zh": "東京都港區1-1",
            "location_address_en": "1-1 Minato",
        }
    }


def test_sibling_map_drops_names_with_conflicting_addresses():
    rows = [
        {"location_name": "チェーン店", "location_address": "東京都港区1-1"},
        {"location_name": "チェーン店", "location_address": "大阪府大阪市北区2-2"},
    ]
    assert ea.build_sibling_map(rows) == {}


def test_resolve_prefers_registry_then_sibling(monkeypatch):
    registry = {
        "公式館": {"address": "京都府京都市中京区3-3"},
        "複数会場": {"address": "東京都千代田区4-4", "is_multi_venue": True},
        "住所なし館": {"address": "京都府"},
    }
    monkeypatch.setattr(ea, "lookup_venue_for_location", lambda name: (registry.get(name), False))
    siblings = {"住所なし館": {"location_address": "京都府京都市左京区5-5"}}

    assert ea.resolve({"location_name": "公式館"}, siblings) == (
        {"location_address": "京都府京都市中京区3-3"}, "registry"
    )
    assert ea.resolve({"location_name": "住所なし館"}, siblings) == (
        {"location_address": "京都府京都市左京区5-5"}, "sibling"
    )
    assert ea.resolve({"location_name": "複数会場"}, siblings) is None


def test_registry_lookup_also_tries_the_name_without_city_prefix(monkeypatch):
    seen = []

    def fake_lookup(name):
        seen.append(name)
        return ({"address": "東京都港区六本木6-6"}, False) if name == "EX THEATER ROPPONGI" else (None, False)

    monkeypatch.setattr(ea, "lookup_venue_for_location", fake_lookup)
    assert ea.registry_address("東京六本木｜EX THEATER ROPPONGI") == {"location_address": "東京都港区六本木6-6"}
    assert seen == ["東京六本木｜EX THEATER ROPPONGI", "EX THEATER ROPPONGI"]


def test_resolve_does_not_mutate_the_sibling_map(monkeypatch):
    monkeypatch.setattr(ea, "lookup_venue_for_location", lambda name: (None, False))
    siblings = {"B館": {"location_address": "福岡県福岡市中央区7-7"}}
    patch, _ = ea.resolve({"location_name": "B館"}, siblings)
    patch["location_address_zh"] = "x"
    assert siblings == {"B館": {"location_address": "福岡県福岡市中央区7-7"}}
