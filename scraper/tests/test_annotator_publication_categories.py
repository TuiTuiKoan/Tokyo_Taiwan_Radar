"""Category post-processing for pure publication records (ndl-relevance-publication, 2026-10-23)."""

from annotator import _drop_format_only_books_media, _inject_keyword_categories


def test_books_media_dropped_when_a_subject_category_exists():
    assert _drop_format_only_books_media(["books_media", "history"]) == ["history"]
    assert _drop_format_only_books_media(["tourism", "books_media", "lifestyle_food"]) == ["tourism", "lifestyle_food"]


def test_books_media_kept_when_it_is_the_only_category():
    assert _drop_format_only_books_media(["books_media"]) == ["books_media"]


def test_categories_without_books_media_unchanged():
    assert _drop_format_only_books_media(["geopolitics", "academic"]) == ["geopolitics", "academic"]
    assert _drop_format_only_books_media([]) == []


def test_publication_skips_event_format_keyword_injection():
    text = "台湾の大学における研究会報告書 シンポジウム 講演録"
    event = _inject_keyword_categories(["academic"], text)
    publication = _inject_keyword_categories(["academic"], text, "publication")
    assert "lecture" in event
    assert "lecture" not in publication
    assert "report" not in publication
    assert "tv_program" not in publication


def test_publication_keeps_subject_keyword_injection():
    assert "geopolitics" in _inject_keyword_categories([], "台湾総統選の行方を読む", "publication")


def test_non_publication_record_type_behaves_as_before():
    text = "台湾映画上映とトーク"
    assert _inject_keyword_categories(["movie"], text, None) == _inject_keyword_categories(["movie"], text)
