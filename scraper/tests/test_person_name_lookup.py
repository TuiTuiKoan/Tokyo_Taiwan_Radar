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