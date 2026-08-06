from types import SimpleNamespace

from auto_qa import (
    _all_auto_report_types,
    _check_missing_date,
    _check_missing_hours,
    _check_missing_organizer,
    _check_missing_price,
    _detect_missing_date,
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


class _FakeQuery:
    """Minimal PostgREST stand-in that projects rows down to the selected columns."""

    def __init__(self, rows):
        self._rows = rows
        self.selected = ""

    def select(self, columns):
        self.selected = columns
        return self

    def eq(self, *_args):
        return self

    def in_(self, *_args):
        return self

    def gte(self, *_args):
        return self

    def execute(self):
        columns = [column.strip() for column in self.selected.split(",")]
        return SimpleNamespace(
            data=[{k: v for k, v in row.items() if k in columns} for row in self._rows]
        )


class _FakeSupabase:
    def __init__(self, rows):
        self.query = _FakeQuery(rows)

    def table(self, _name):
        return self.query


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


def test_january_placeholder_skips_only_exact_pure_publication():
    pure = _base_event(
        source_name="ndl_opensearch", event_form=["publication"], start_date="2026-01-01"
    )
    physical = _base_event(source_name="ndl_opensearch", event_form=["lecture"], start_date="2026-01-01")
    mixed = _base_event(
        source_name="ndl_opensearch", event_form=["publication", "lecture"], start_date="2026-01-01"
    )

    assert _check_missing_date(pure) is None
    assert "start_date missing/placeholder" in (_check_missing_date(physical) or "")
    assert "start_date missing/placeholder" in (_check_missing_date(mixed) or "")


def test_null_start_date_still_fires_for_pure_publication():
    pure = _base_event(source_name="ndl_opensearch", event_form=["publication"], start_date=None)

    assert "start_date missing/placeholder" in (_check_missing_date(pure) or "")


def test_publish_date_sources_january_behaviour_is_unchanged():
    for source in ("note_creators", "google_news_rss", "prtimes", "nhk_rss", "walkerplus"):
        feed = _base_event(source_name=source, event_form=["other"], start_date="2026-01-15")
        assert _check_missing_date(feed) is None, source
        assert "start_date missing/placeholder" in (
            _check_missing_date(_base_event(source_name=source, event_form=["other"], start_date=None)) or ""
        ), source


def test_non_january_pure_publication_is_not_flagged():
    pure = _base_event(
        source_name="ndl_opensearch", event_form=["publication"], start_date="2026-05-01"
    )

    assert _check_missing_date(pure) is None


def test_detect_missing_date_selects_event_form():
    # The January exemption reads event_form, so dropping it from the select
    # silently reinstates the false positives the predicate was fixed for.
    pure = _base_event(
        id="ev-pure", source_name="ndl_opensearch", event_form=["publication"], start_date="2026-01-01"
    )
    physical = _base_event(
        id="ev-physical", source_name="ndl_opensearch", event_form=["lecture"], start_date="2026-01-01"
    )
    sb = _FakeSupabase([pure, physical])

    reports = _detect_missing_date(sb)

    assert "event_form" in [column.strip() for column in sb.query.selected.split(",")]
    assert [report["event_id"] for report in reports] == ["ev-physical"]


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
    assert reason == "compound: every type resolved"


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


def test_resolve_report_disposition_runs_predicate_for_reviewed_events():
    # H0: the admin-reviewed shortcut was removed. A reviewed event runs the
    # type predicate like any other row — reconcile is the sole authority on
    # whether the flagged issue is actually resolved.
    still_missing = _base_event(annotation_status="reviewed", location_address="")
    disposition, reason = _resolve_report_disposition(still_missing, ["auto_qa_missing_address"])
    assert disposition == "keep"
    assert reason == "predicate still fires"

    resolved = _base_event(annotation_status="reviewed", location_address="東京都千代田区1-1")
    disposition, reason = _resolve_report_disposition(resolved, ["auto_qa_missing_address"])
    assert disposition == "confirm"
    assert reason == "issue resolved"