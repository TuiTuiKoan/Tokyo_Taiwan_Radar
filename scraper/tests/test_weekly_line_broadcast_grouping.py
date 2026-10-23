"""LINE weekly broadcast: books are grouped by record type, not by the books_media category."""

from weekly_line_broadcast import _group_by_type


def _ids(group):
    return [e["id"] for e in group]


def test_pure_publication_without_books_media_goes_to_books():
    events = [{"id": "pub", "category": ["history"], "event_form": ["publication"]}]
    regular, film, books, online, tv = _group_by_type(events)
    assert _ids(books) == ["pub"]
    assert not regular and not film and not online and not tv


def test_pure_publication_about_film_goes_to_books_not_film():
    events = [{"id": "pub", "category": ["movie"], "event_form": ["publication"]}]
    _, film, books, _, _ = _group_by_type(events)
    assert _ids(books) == ["pub"]
    assert not film


def test_book_launch_event_keeps_books_media_grouping():
    events = [{"id": "talk", "category": ["books_media", "lecture"], "event_form": ["lecture"]}]
    regular, _, books, _, _ = _group_by_type(events)
    assert _ids(books) == ["talk"]
    assert not regular


def test_mixed_form_is_not_a_pure_publication():
    events = [{"id": "mixed", "category": ["history"], "event_form": ["publication", "lecture"]}]
    regular, _, books, _, _ = _group_by_type(events)
    assert _ids(regular) == ["mixed"]
    assert not books


def test_missing_event_form_falls_back_to_category():
    events = [
        {"id": "film", "category": ["movie"]},
        {"id": "plain", "category": ["history"]},
        {"id": "tv", "category": ["tv_program"], "source_name": "gguide_tv"},
        {"id": "online", "category": ["lecture"], "location_name": "オンライン"},
    ]
    regular, film, books, online, tv = _group_by_type(events)
    assert (_ids(regular), _ids(film), _ids(books), _ids(online), _ids(tv)) == (
        ["plain"], ["film"], [], ["online"], ["tv"],
    )
