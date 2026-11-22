import enrich_addresses as ea


def test_is_vague_flags_missing_and_area_only_addresses():
    assert ea.is_vague(None)
    assert ea.is_vague("  ")
    assert ea.is_vague("東京都")
    assert ea.is_vague("渋谷区")
    assert not ea.is_vague("東京都渋谷区神宮前1-14-30")


T0 = "2026-11-01T00:00:00+00:00"


def _sib(i, name, address, source, raw="", created=T0, **extra):
    return {"id": f"e{i}", "location_name": name, "location_address": address,
            "source_name": source, "created_at": created, "raw_description": raw, **extra}


def _autolock(value, created=T0, **extra):
    return {"corrected_value": value, "corrected_by": None, "report_id": None, "created_at": created, **extra}


def test_needs_address_uses_the_grader():
    assert ea.needs_address(None)
    assert ea.needs_address("東京都")
    assert ea.needs_address("東京都港区六本木")           # town level: is_vague() said specific
    assert not ea.needs_address("東京都渋谷区神宮前1-14-30")
    assert not ea.needs_address("台北市信義區信義路五段7號")  # outside Japan: left alone
    assert not ea.is_vague("東京都港区六本木")             # old rule kept for the audit


def test_sibling_vote_accepts_scraper_values_and_verbatim_text_only():
    addr = "東京都港区虎ノ門1-1-12"
    row = _sib(1, "A館", addr, "s1")
    assert ea.sibling_vote(row, _autolock(addr))
    assert ea.sibling_vote(row, _autolock("東京都港区虎ノ門１－１－１２ 2F"))                 # same key
    assert ea.sibling_vote(_sib(2, "A館", addr, "s1", raw=f"会場：{addr}（2階）"), None)       # verbatim
    assert not ea.sibling_vote(row, None)                                                     # no evidence
    assert not ea.sibling_vote(row, _autolock(f'"{addr}"'))                                    # copy lock
    assert not ea.sibling_vote(row, _autolock(addr, created="2026-11-01T00:05:00+00:00"))     # written later
    assert not ea.sibling_vote(row, _autolock(addr, corrected_by="admin"))                    # a person's fix
    assert not ea.sibling_vote(row, _autolock("東京都港区虎ノ門1-1-1"))                         # different key
    assert not ea.sibling_vote(_sib(3, "A館", "東京都港区", "s1"), _autolock("東京都港区"))      # not street
    two = "東京都港区六本木6-10-1 / 大阪府大阪市北区梅田1-1-3"
    assert not ea.sibling_vote(_sib(4, "A館", two, "s1", raw=two), None)                       # two places


def test_sibling_map_needs_two_independent_events_from_two_sources():
    addr = "東京都港区虎ノ門1-1-12 虎ノ門ビル2階"
    rows = [
        _sib(1, "A館", addr, "s1", location_address_zh="東京都港區虎之門1-1-12"),
        _sib(2, "A館", "東京都港区虎ノ門１－１－１２", "s2", location_address_en="1-1-12 Toranomon"),
        _sib(3, "A館", "東京都港区", "s3"),               # vague rows never vote or conflict
        _sib(4, "B館", addr, "s1"), _sib(5, "B館", addr, "s1"),   # one source only
        _sib(6, "C館", addr, "s1"), _sib(7, "C館", addr, "s2"),   # no evidence
    ]
    locks = {r["id"]: _autolock(r["location_address"]) for r in rows if r["id"] not in {"e6", "e7"}}
    result = ea.build_sibling_map(rows, locks)

    assert set(result) == {"A館"}
    assert result["A館"]["location_address"] in {addr, "東京都港区虎ノ門１－１－１２"}
    assert result["A館"]["location_address_zh"] == "東京都港區虎之門1-1-12"
    assert result["A館"]["location_address_en"] == "1-1-12 Toranomon"


def test_one_event_whose_own_text_has_the_address_is_enough():
    addr = "大阪府大阪市港区弁天1-2-3"
    rows = [_sib(1, "D館", addr, "s1", raw=f"会場：D館（{addr}）"), _sib(2, "D館", "大阪府大阪市港区", "s1")]
    assert ea.build_sibling_map(rows, {}) == {"D館": {"location_address": addr}}


def test_sibling_map_drops_names_with_conflicting_addresses():
    rows = [
        _sib(1, "チェーン店", "東京都港区虎ノ門1-1-12", "s1"),
        _sib(2, "チェーン店", "東京都港区虎ノ門1-1-12", "s2"),
        _sib(3, "チェーン店", "大阪府大阪市北区梅田2-2-2", "s3"),   # even a non-voting row conflicts
    ]
    locks = {"e1": _autolock("東京都港区虎ノ門1-1-12"), "e2": _autolock("東京都港区虎ノ門1-1-12")}
    assert ea.build_sibling_map(rows, locks) == {}


def test_registry_accepts_street_and_town_addresses(monkeypatch):
    registry = {
        "公園": {"address": "東京都渋谷区代々木神園町"},
        "県だけ": {"address": "京都府"},
    }
    monkeypatch.setattr(ea, "lookup_venue_for_location", lambda name: (registry.get(name), False))
    assert ea.registry_address("公園") == {"location_address": "東京都渋谷区代々木神園町"}
    assert ea.registry_address("県だけ") is None


def test_resolve_prefers_registry_then_sibling(monkeypatch):
    registry = {
        "公式館": {"address": "京都府京都市中京区烏丸通3-3"},
        "複数会場": {"address": "東京都千代田区丸の内4-4", "is_multi_venue": True},
        "住所なし館": {"address": "京都府"},
    }
    monkeypatch.setattr(ea, "lookup_venue_for_location", lambda name: (registry.get(name), False))
    siblings = {"住所なし館": {"location_address": "京都府京都市左京区5-5"}}

    assert ea.resolve({"location_name": "公式館"}, siblings) == (
        {"location_address": "京都府京都市中京区烏丸通3-3"}, "registry"
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
