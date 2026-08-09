from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import auto_qa
from auto_qa import (
    _all_auto_report_types,
    _check_missing_date,
    _check_missing_hours,
    _check_missing_organizer,
    _check_missing_performers,
    _check_missing_price,
    _detect_missing_date,
    _detect_missing_performers,
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


class _RecordingQuery:
    """PostgREST stand-in that records the projection and applies real filters."""

    def __init__(self, rows, recorder):
        self._rows = [dict(row) for row in rows]
        self._recorder = recorder
        self.selected = ""

    def select(self, columns):
        self.selected = columns
        self._recorder.append(columns)
        return self

    def eq(self, column, value):
        self._rows = [row for row in self._rows if row.get(column) == value]
        return self

    def in_(self, column, values):
        wanted = set(values)
        self._rows = [row for row in self._rows if row.get(column) in wanted]
        return self

    def is_(self, column, _value):
        self._rows = [row for row in self._rows if row.get(column) is None]
        return self

    def gte(self, column, value):
        self._rows = [row for row in self._rows if (row.get(column) or "") >= value]
        return self

    def range(self, start, end):
        self._rows = self._rows[start : end + 1]
        return self

    def execute(self):
        columns = [column.strip() for column in self.selected.split(",")]
        return SimpleNamespace(
            data=[{k: v for k, v in row.items() if k in columns} for row in self._rows]
        )


class _RecordingSupabase:
    def __init__(self, tables):
        self._tables = tables
        self.selects: dict[str, list[str]] = {}

    def table(self, name):
        return _RecordingQuery(
            self._tables.get(name, []), self.selects.setdefault(name, [])
        )


def _iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


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


def test_check_missing_date_fires_only_on_a_null_start_date():
    assert "start_date is null" in (_check_missing_date(_base_event(start_date=None)) or "")
    valid = (
        "2026-01-01",
        "2026-01-24",
        "2026-01-30",
        "2026-01-01T00:00:00+00:00",
        "2026-05-01",
    )
    for value in valid:
        assert _check_missing_date(_base_event(start_date=value)) is None, value


def test_check_missing_date_is_source_and_event_form_agnostic():
    sources = ("ndl_opensearch", "note_creators", "tokyoartbeat", "eslite_spectrum")
    forms = (["publication"], ["lecture"], ["publication", "lecture"], ["exhibition"])
    for source in sources:
        for form in forms:
            january = _base_event(source_name=source, event_form=form, start_date="2026-01-15")
            missing = _base_event(source_name=source, event_form=form, start_date=None)
            assert _check_missing_date(january) is None, (source, form)
            assert _check_missing_date(missing) is not None, (source, form)


def test_check_missing_date_applies_no_time_window():
    # The pure predicate is the reconcile authority and must not inherit the
    # detector's rolling candidate window.
    stale = _base_event(start_date=None, created_at="2019-01-01T00:00:00+00:00")
    fresh = _base_event(start_date=None, created_at=_iso(0))
    assert _check_missing_date(stale) is not None
    assert _check_missing_date(fresh) is not None
    assert _check_missing_date(_base_event(start_date="2026-01-30", created_at=_iso(0))) is None


def test_null_start_date_still_fires_for_pure_publication():
    pure = _base_event(source_name="ndl_opensearch", event_form=["publication"], start_date=None)

    assert "start_date is null" in (_check_missing_date(pure) or "")


def test_non_january_pure_publication_is_not_flagged():
    pure = _base_event(
        source_name="ndl_opensearch", event_form=["publication"], start_date="2026-05-01"
    )

    assert _check_missing_date(pure) is None


def test_detect_missing_date_only_reports_rows_inside_the_thirty_day_window():
    # The DETECTOR keeps its rolling candidate window even though the pure
    # predicate has none: an old null-date row must not create a new report.
    inside = _base_event(id="ev-inside", start_date=None, created_at=_iso(1))
    outside = _base_event(id="ev-outside", start_date=None, created_at=_iso(90))
    sb = _RecordingSupabase({"events": [inside, outside]})

    reports = _detect_missing_date(sb)

    assert [report["event_id"] for report in reports] == ["ev-inside"]
    assert reports[0]["report_type"] == "auto_qa_missing_date"


def test_detect_missing_date_ignores_january_rows_inside_the_window():
    january = _base_event(id="ev-january", start_date="2026-01-30", created_at=_iso(1))
    sb = _RecordingSupabase({"events": [january]})

    assert _detect_missing_date(sb) == []


def test_detect_missing_date_projection_carries_every_predicate_field():
    # Dropping any of these from the select makes the predicate read None and
    # silently changes its verdict.
    sb = _RecordingSupabase({"events": [_base_event(start_date=None, created_at=_iso(1))]})

    _detect_missing_date(sb)

    columns = {column.strip() for column in sb.selects["events"][0].split(",")}
    assert {"id", "start_date", "source_name"} <= columns


def test_detect_missing_performers_selects_only_null_arrays_inside_the_window():
    # Known asymmetry, preserved on purpose: the detector considers only
    # `performers IS NULL`, while the pure predicate treats [] as missing too.
    labelled = "\u8b1b\u5e2b\uff1a\u5c71\u7530\u592a\u90ce\u3055\u3093 \u306b\u3088\u308b\u8b1b\u6f14"
    null_inside = _base_event(
        id="ev-null-inside", performers=None, raw_description=labelled, created_at=_iso(1)
    )
    empty_inside = _base_event(
        id="ev-empty-inside", performers=[], raw_description=labelled, created_at=_iso(1)
    )
    null_outside = _base_event(
        id="ev-null-outside", performers=None, raw_description=labelled, created_at=_iso(90)
    )
    sb = _RecordingSupabase({"events": [null_inside, empty_inside, null_outside]})

    reports = _detect_missing_performers(sb)

    assert [report["event_id"] for report in reports] == ["ev-null-inside"]
    assert _check_missing_performers(empty_inside) is not None


def test_detect_missing_performers_projection_carries_every_predicate_field():
    sb = _RecordingSupabase({"events": [_base_event(performers=None, created_at=_iso(1))]})

    _detect_missing_performers(sb)

    columns = {column.strip() for column in sb.selects["events"][0].split(",")}
    required = {
        "id",
        "source_name",
        "raw_title",
        "raw_description",
        "event_form",
        "parent_event_id",
        "category",
        "performers",
    }
    assert required <= columns


def test_reconcile_projection_carries_every_predicate_field(monkeypatch):
    event = _base_event(id="e1", start_date=None, performers=None, parent_event_id=None)
    reports = [{
        "id": "r1",
        "event_id": "e1",
        "report_types": ["auto_qa_missing_date"],
        "admin_notes": None,
        "status": "pending",
    }]
    sb = _RecordingSupabase({"event_reports": reports, "events": [event]})
    monkeypatch.setattr(auto_qa, "_supabase_client", lambda: sb)

    summary = auto_qa.reconcile(dry_run=True)

    assert summary["scanned_pending"] == 1
    columns = {column.strip() for column in sb.selects["events"][0].split(",")}
    required = {
        "id",
        "is_active",
        "start_date",
        "source_name",
        "raw_title",
        "raw_description",
        "event_form",
        "parent_event_id",
        "category",
        "performers",
    }
    assert required <= columns


def test_missing_date_and_performer_predicates_never_mutate_their_input():
    event = _base_event(
        start_date=None,
        performers=None,
        event_form=["lecture"],
        raw_description="\u8b1b\u5e2b\uff1a\u5c71\u7530\u592a\u90ce\u3055\u3093 \u306b\u3088\u308b\u8b1b\u6f14",
    )
    before = deepcopy(event)

    _check_missing_date(event)
    _check_missing_performers(event)

    assert event == before


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