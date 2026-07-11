from auto_qa import (
    _all_auto_report_types,
    _check_missing_hours,
    _check_missing_organizer,
    _check_missing_price,
    _resolve_report_disposition,
    _single_auto_report_type,
    detect,
)


def _base_event(**overrides):
    event = {
        "id": "ev-1",
        "source_name": "fixture_source",
        "name_ja": "書籍イベント",
        "raw_title": "書籍イベント",
        "category": ["books_media"],
        "event_form": ["lecture"],
        "location_name": "丸善丸の内本店",
        "location_address": "",
        "location_prefectures": [],
        "raw_description": "開場 19:00 / 参加費 1500円",
        "organizer": "出版社A",
        "official_url": "https://example.test/event",
        "created_at": "2024-01-10T00:00:00+00:00",
        "is_active": True,
        "annotation_status": "annotated",
    }
    event.update(overrides)
    return event


def _types(event):
    return {report_type for report_type, _note in detect(event)}


def test_detect_skips_venue_checks_only_for_exact_pure_publication():
    pure = _base_event(
        event_form=["publication"],
        location_name="",
        location_address="東京都千代田区1-1",
        location_prefectures=[],
    )
    physical = _base_event(
        event_form=["lecture"],
        location_name="",
        location_address="東京都千代田区1-1",
        location_prefectures=[],
    )

    pure_types = _types(pure)
    physical_types = _types(physical)

    assert "auto_qa_missing_location_name" not in pure_types
    assert "auto_qa_missing_prefectures" not in pure_types
    assert "auto_qa_missing_location_name" in physical_types
    assert "auto_qa_missing_prefectures" in physical_types


def test_detect_reports_missing_address_for_physical_books_media():
    physical = _base_event(event_form=["lecture"], location_name="丸善丸の内本店", location_address="")

    assert "auto_qa_missing_address" in _types(physical)


def test_detect_mixed_publication_form_is_not_treated_as_pure():
    mixed = _base_event(
        event_form=["publication", "lecture"],
        location_name="",
        location_address="東京都千代田区1-1",
        location_prefectures=[],
    )

    assert "auto_qa_missing_location_name" in _types(mixed)


def test_missing_hours_skips_only_exact_pure_publication():
    pure = _base_event(event_form=["publication"], business_hours=None, raw_description="開場 19:00")
    physical = _base_event(event_form=["lecture"], business_hours=None, raw_description="開場 19:00")

    assert _check_missing_hours(pure) is None
    assert "business_hours is null" in (_check_missing_hours(physical) or "")


def test_pure_missing_publisher_stays_pending():
    pure = _base_event(source_name="ndl_opensearch", event_form=["publication"], organizer=None)

    assert "organizer is null" in (_check_missing_organizer(pure) or "")


def test_missing_price_skips_only_exact_pure_publication():
    pure = _base_event(event_form=["publication"], raw_description="参加費 1500円")
    physical = _base_event(event_form=["lecture"], raw_description="参加費 1500円")
    mixed = _base_event(event_form=["publication", "lecture"], raw_description="参加費 1500円")

    assert _check_missing_price(pure) is None
    assert "price_keyword" in (_check_missing_price(physical) or "")
    assert "price_keyword" in (_check_missing_price(mixed) or "")


def test_single_auto_report_type_protects_manual_unknown_and_compound_rows():
    assert _single_auto_report_type(["auto_qa_missing_address"]) == "auto_qa_missing_address"
    assert _single_auto_report_type(["wrongCategory"]) is None
    assert _single_auto_report_type(["auto_qa_missing_address", "wrongCategory"]) is None
    assert _single_auto_report_type(["auto_qa_missing_address", "auto_qa_missing_title"]) is None
    assert _single_auto_report_type(["mystery_type"]) is None
    assert _single_auto_report_type(None) is None


def test_all_auto_report_types_accepts_compound_auto_and_rejects_mixed():
    assert _all_auto_report_types(["auto_qa_missing_address"]) == ["auto_qa_missing_address"]
    assert _all_auto_report_types(
        ["auto_qa_missing_address", "auto_qa_missing_title"]
    ) == ["auto_qa_missing_address", "auto_qa_missing_title"]
    assert _all_auto_report_types(["auto_qa_missing_address", "wrongCategory"]) is None
    assert _all_auto_report_types(["mystery_type"]) is None
    assert _all_auto_report_types(None) is None
    assert _all_auto_report_types([]) is None


def test_resolve_report_disposition_confirms_compound_row_only_when_all_resolved():
    # Both auto_qa_missing_title and auto_qa_missing_category resolved (fields present).
    resolved_event = _base_event(
        name_ja="書籍イベント",
        raw_title="書籍イベント",
        category=["books_media"],
    )
    disposition, reason = _resolve_report_disposition(
        resolved_event, ["auto_qa_missing_title", "auto_qa_missing_category"]
    )
    assert disposition == "confirm"
    assert reason == "issue resolved"


def test_resolve_report_disposition_keeps_compound_row_when_one_type_still_fires():
    # auto_qa_missing_organizer still fires (organizer is null) even though
    # auto_qa_missing_title is resolved — the whole compound row must stay pending.
    partially_resolved_event = _base_event(name_ja="書籍イベント", raw_title="書籍イベント", organizer=None)
    disposition, _reason = _resolve_report_disposition(
        partially_resolved_event, ["auto_qa_missing_title", "auto_qa_missing_organizer"]
    )
    assert disposition == "keep"


def test_resolve_report_disposition_dismisses_deleted_and_inactive_events():
    assert _resolve_report_disposition(None, ["auto_qa_missing_address"])[0] == "dismiss"
    inactive_event = _base_event(is_active=False)
    assert _resolve_report_disposition(inactive_event, ["auto_qa_missing_address"])[0] == "dismiss"


def test_resolve_report_disposition_confirms_admin_reviewed_events():
    reviewed_event = _base_event(annotation_status="reviewed")
    disposition, reason = _resolve_report_disposition(reviewed_event, ["auto_qa_missing_address"])
    assert disposition == "confirm"
    assert reason == "event reviewed by admin"