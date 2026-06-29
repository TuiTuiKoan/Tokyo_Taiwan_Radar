import movie_title_lookup


def test_movie_lookup_normalizes_4k_restore_suffix(monkeypatch):
    calls = []

    def fake_lookup(title):
        calls.append(title)
        if title == "海辺の一日":
            return "海灘的一天", "That Day, on the Beach", "https://example.com/movie"
        return None, None, None

    movie_title_lookup._cache.clear()
    monkeypatch.setattr(movie_title_lookup, "_lookup_movie_titles_exact", fake_lookup)

    assert movie_title_lookup.lookup_movie_titles("海辺の一日 4Kレストア") == (
        "海灘的一天 4K修復版",
        "That Day, on the Beach 4K Restoration",
        "https://example.com/movie",
    )
    assert movie_title_lookup.lookup_movie_titles_with_metadata("海辺の一日 4Kレストア") == (
        "海灘的一天 4K修復版",
        "That Day, on the Beach 4K Restoration",
        "https://example.com/movie",
        "suffix_normalized",
    )
    assert calls == ["海辺の一日 4Kレストア", "海辺の一日"]


def test_movie_lookup_normalizes_4k_restore_version_suffix(monkeypatch):
    calls = []

    def fake_lookup(title):
        calls.append(title)
        if title == "エドワード・ヤンの恋愛時代":
            return "獨立時代", "A Confucian Confusion", None
        return None, None, None

    movie_title_lookup._cache.clear()
    monkeypatch.setattr(movie_title_lookup, "_lookup_movie_titles_exact", fake_lookup)

    assert movie_title_lookup.lookup_movie_titles("エドワード・ヤンの恋愛時代 4Kレストア版") == (
        "獨立時代 4K修復版",
        "A Confucian Confusion 4K Restoration",
        None,
    )
    assert calls == [
        "エドワード・ヤンの恋愛時代 4Kレストア版",
        "エドワード・ヤンの恋愛時代",
    ]


def test_movie_lookup_keeps_exact_result_before_normalized_candidate(monkeypatch):
    calls = []

    def fake_lookup(title):
        calls.append(title)
        if title == "海辺の一日 4Kレストア":
            return "海灘的一天 4K修復版", "That Day, on the Beach 4K Restoration", None
        return "海灘的一天", "That Day, on the Beach", None

    movie_title_lookup._cache.clear()
    monkeypatch.setattr(movie_title_lookup, "_lookup_movie_titles_exact", fake_lookup)

    assert movie_title_lookup.lookup_movie_titles("海辺の一日 4Kレストア")[:2] == (
        "海灘的一天 4K修復版",
        "That Day, on the Beach 4K Restoration",
    )
    assert movie_title_lookup.lookup_movie_titles_with_metadata("海辺の一日 4Kレストア")[3] == "exact"
    assert calls == ["海辺の一日 4Kレストア"]