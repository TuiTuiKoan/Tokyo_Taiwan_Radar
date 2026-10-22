import person_name_lookup


def test_resolve_person_retries_without_misleading_origin(monkeypatch):
    calls = []

    def fake_wiki(en_name, origin=None, *, strict=False):
        calls.append((en_name, origin, strict))
        if en_name == "Edward Yang" and origin is None and strict:
            return "楊德昌"
        if en_name == "Edward Yang" and origin is not None and not strict:
            return "白紙運動"
        return None

    person_name_lookup._person_cache.clear()
    monkeypatch.setattr(
        person_name_lookup,
        "_lookup_person_en_and_origin",
        lambda person_url: ("Edward Yang", "中国／上海"),
    )
    monkeypatch.setattr(person_name_lookup, "_lookup_zh_via_wikipedia", fake_wiki)
    monkeypatch.setattr(person_name_lookup, "_lookup_zh_via_ja_wikipedia", lambda *args, **kwargs: None)

    assert person_name_lookup._resolve_person("https://eiga.com/person/1/", "エドワード・ヤン") == (
        "Edward Yang",
        "楊德昌",
    )
    assert calls == [
        ("Edward Yang", "中国／上海", True),
        ("Edward Yang", None, True),
    ]


def test_resolve_person_uses_role_aware_strict_fallback(monkeypatch):
    calls = []

    def fake_wiki(en_name, origin=None, *, strict=False):
        calls.append((en_name, origin, strict))
        if en_name == "Edward Yang film director" and strict:
            return "楊德昌"
        return None

    person_name_lookup._person_cache.clear()
    monkeypatch.setattr(
        person_name_lookup,
        "_lookup_person_en_and_origin",
        lambda person_url: ("Edward Yang", "中国／上海"),
    )
    monkeypatch.setattr(person_name_lookup, "_lookup_zh_via_wikipedia", fake_wiki)
    monkeypatch.setattr(person_name_lookup, "_lookup_zh_via_ja_wikipedia", lambda *args, **kwargs: None)

    assert person_name_lookup._resolve_person("https://eiga.com/person/2/", "エドワード・ヤン") == (
        "Edward Yang",
        "楊德昌",
    )
    assert calls == [
        ("Edward Yang", "中国／上海", True),
        ("Edward Yang", None, True),
        ("Edward Yang film director", None, True),
    ]


def test_resolve_person_does_not_accept_loose_cjk_false_positive(monkeypatch):
    def fake_wiki(en_name, origin=None, *, strict=False):
        if strict:
            return None
        return "白紙運動"

    person_name_lookup._person_cache.clear()
    monkeypatch.setattr(
        person_name_lookup,
        "_lookup_person_en_and_origin",
        lambda person_url: ("Edward Yang", "中国／上海"),
    )
    monkeypatch.setattr(person_name_lookup, "_lookup_zh_via_wikipedia", fake_wiki)
    monkeypatch.setattr(person_name_lookup, "_lookup_zh_via_ja_wikipedia", lambda *args, **kwargs: None)

    assert person_name_lookup._resolve_person("https://eiga.com/person/3/", "エドワード・ヤン") == (
        "Edward Yang",
        None,
    )

def _fake_ja_wiki(titles_by_query, langlinks=None):
    """Build a requests.get stand-in for the ja.wikipedia API."""
    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    calls = []

    def fake_get(url, params=None, **kwargs):
        calls.append(params)
        if params.get("list") == "search":
            title = titles_by_query.get(params["srsearch"])
            hits = [{"title": title}] if title else []
            return _Resp({"query": {"search": hits}})
        links = [{"*": langlinks}] if langlinks else []
        return _Resp({"query": {"pages": {"1": {"langlinks": links}}}})

    return fake_get, calls


def test_ja_wikipedia_strict_skips_non_katakana_stage_name(monkeypatch):
    # "9m88" is a singer's stage name; ja-wiki search lands on the aircraft
    # "Ju 88 (航空機)" whose zh langlink is "Ju 88轟炸機".
    fake_get, calls = _fake_ja_wiki({"9m88": "Ju 88 (航空機)"}, langlinks="Ju 88轟炸機")
    monkeypatch.setattr(person_name_lookup.requests, "get", fake_get)

    assert person_name_lookup._lookup_zh_via_ja_wikipedia("9m88", strict=True) is None
    assert calls == []


def test_ja_wikipedia_strict_rejects_latin_title_for_katakana_query(monkeypatch):
    fake_get, _ = _fake_ja_wiki({"ジュー・ハチハチ": "Ju 88 (航空機)"}, langlinks="Ju 88轟炸機")
    monkeypatch.setattr(person_name_lookup.requests, "get", fake_get)

    assert person_name_lookup._lookup_zh_via_ja_wikipedia("ジュー・ハチハチ", strict=True) is None


def test_ja_wikipedia_strict_still_returns_zh_langlink_for_katakana_person(monkeypatch):
    fake_get, _ = _fake_ja_wiki({"クー・チェンドン": "柯震東"}, langlinks="柯震東")
    monkeypatch.setattr(person_name_lookup.requests, "get", fake_get)

    assert person_name_lookup._lookup_zh_via_ja_wikipedia("クー・チェンドン", strict=True) == "柯震東"


def test_extract_katakana_names_keeps_fan_surname():
    # ケイトリン・ファン (方郁婷): "ファン" is a surname here, not "fan".
    assert person_name_lookup.extract_katakana_names("出演 ケイトリン・ファン") == ["ケイトリン・ファン"]


def test_extract_katakana_names_still_drops_fan_compounds_and_other_noise():
    text = "アニメファン・ミーティング ヒルトン・ホテル"
    assert person_name_lookup.extract_katakana_names(text) == []


def test_extract_katakana_names_fan_not_last_part_is_noise():
    assert person_name_lookup.extract_katakana_names("ファン・ミーティング") == []
