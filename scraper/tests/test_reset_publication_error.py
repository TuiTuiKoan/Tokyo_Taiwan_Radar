from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import json
import stat

import pytest

import _oneoff_reset_publication_error as reset

E1 = "11111111-1111-4111-8111-111111111111"
E2 = "22222222-2222-4222-8222-222222222222"
E3 = "33333333-3333-4333-8333-333333333333"


@pytest.fixture(autouse=True)
def _fixed_operator(monkeypatch):
    monkeypatch.setattr(reset, "current_git_head", lambda: "test-head")
    monkeypatch.setattr(reset, "current_script_sha256", lambda: "test-script-sha")


def _event(event_id: str = E1, **overrides):
    row = {
        "id": event_id,
        "source_name": "ndl_opensearch",
        "source_id": f"source-{event_id}",
        "source_url": f"https://example.test/{event_id}",
        "official_url": None,
        "event_form": ["publication"],
        "category": ["books_media"],
        "is_active": True,
        "created_at": "2026-07-30T00:00:00+00:00",
        "updated_at": "2026-07-30T01:00:00+00:00",
        "name_ja": "Book",
        "name_zh": None,
        "name_en": "Book",
        "organizer": "Publisher",
        "location_name": None,
        "location_address": None,
        "business_hours": None,
        "location_prefectures": None,
        "record_links": [{"url": "https://example.test/link", "kind": "source"}],
        "metadata": {"nested": ["a", None, {"b": 1}]},
        "annotation_status": "error",
        "annotation_retry_count": 3,
    }
    row.update(overrides)
    return row


def _field_correction(event_id: str = E1, **overrides):
    row = {
        "id": f"fc-{event_id}",
        "event_id": event_id,
        "field_name": "location_address",
        "corrected_value": json.dumps(None),
        "created_at": "2026-07-30T02:00:00+00:00",
    }
    row.update(overrides)
    return row


def _report(event_id: str = E1, **overrides):
    row = {
        "id": f"report-{event_id}",
        "event_id": event_id,
        "status": "pending",
        "report_types": ["annotation_error_stuck"],
        "created_at": "2026-07-30T03:00:00+00:00",
    }
    row.update(overrides)
    return row


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.op = "select"
        self.patch = None
        self.filters = []
        self.start = None
        self.end = None

    def select(self, _columns="*", *_args, **_kwargs):
        return self

    def update(self, patch):
        self.op = "update"
        self.patch = dict(patch)
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, list(values)))
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def is_(self, column, value):
        self.filters.append(("is", column, value))
        return self

    def order(self, _column, **_kwargs):
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def _matches(self, row):
        for kind, column, value in self.filters:
            actual = row.get(column)
            if kind == "in" and actual not in value:
                return False
            if kind == "eq" and actual != value:
                return False
            if kind == "is" and not (value == "null" and actual is None):
                return False
        return True

    def execute(self):
        rows = self.client.tables.setdefault(self.table, [])
        if self.op == "update":
            matched = [row for row in rows if self._matches(row)]
            self.client.update_attempts.append((self.table, deepcopy(self.patch), list(self.filters), len(matched)))
            if self.client.override_update_result is not None:
                return _Result(deepcopy(self.client.override_update_result))
            for row in matched:
                row.update(self.patch)
            return _Result([{"id": row.get("id")} for row in matched])

        matched = [deepcopy(row) for row in rows if self._matches(row)]
        if self.start is not None and self.end is not None:
            matched = matched[self.start : self.end + 1]
        return _Result(matched)


class _Client:
    def __init__(self, *, events=None, field_corrections=None, event_reports=None):
        self.tables = {
            "events": [deepcopy(row) for row in (events or [])],
            "field_corrections": [deepcopy(row) for row in (field_corrections or [])],
            "event_reports": [deepcopy(row) for row in (event_reports or [])],
        }
        self.update_attempts = []
        self.override_update_result = None

    def table(self, name):
        return _Query(self, name)

    def event(self, event_id=E1):
        return next(row for row in self.tables["events"] if row["id"] == event_id)


def _snapshot(client: _Client, event_ids=None):
    return reset.build_snapshot(client, event_ids or [E1], generated_at="2026-07-31T00:00:00Z")


def test_dry_run_discovery_writes_nothing(monkeypatch, capsys):
    client = _Client(events=[_event(E1), _event(E2, event_form=["publication", "lecture"])])
    monkeypatch.setattr(reset, "_get_supabase", lambda: client)

    result = reset.run(apply_changes=False, sources=["ndl_opensearch"], event_ids=None, limit=None)

    assert [row["id"] for row in result["candidates"]] == [E1]
    assert client.update_attempts == []
    assert "dry_run_only=true" in capsys.readouterr().out


def test_apply_rejects_missing_ids_source_filters_and_limit(tmp_path):
    with pytest.raises(RuntimeError, match="apply requires repeated full"):
        reset.run(apply_changes=True, event_ids=None, snapshot_path=tmp_path / "s.json")
    with pytest.raises(RuntimeError, match="--source is discovery-only"):
        reset.run(apply_changes=True, sources=["ndl_opensearch"], event_ids=[E1], snapshot_path=tmp_path / "s.json")
    with pytest.raises(RuntimeError, match="--limit is discovery-only"):
        reset.run(apply_changes=True, event_ids=[E1], limit=1, snapshot_path=tmp_path / "s.json")


def test_uuid_prefix_invalid_duplicate_and_twenty_plus_rejected():
    with pytest.raises(ValueError, match="full UUID"):
        reset.normalize_event_ids([E1[:8]])
    with pytest.raises(ValueError, match="invalid UUID"):
        reset.normalize_event_ids(["zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"])
    with pytest.raises(ValueError, match="duplicate"):
        reset.normalize_event_ids([E1, E1.upper()])
    too_many = [f"{index:08d}-1111-4111-8111-111111111111" for index in range(20)]
    with pytest.raises(RuntimeError, match="20 or more"):
        reset.normalize_event_ids(too_many)


def test_snapshot_rejects_non_pure_mixed_inactive_and_non_error_rows():
    cases = [
        _event(E1, event_form=["publication", "lecture"]),
        _event(E1, is_active=False),
        _event(E1, annotation_status="pending"),
    ]
    for row in cases:
        with pytest.raises(RuntimeError):
            _snapshot(_Client(events=[row]))


def test_existing_intentional_null_fc_rows_are_accepted_and_unchanged():
    fc = _field_correction()
    report = _report()
    client = _Client(events=[_event()], field_corrections=[fc], event_reports=[report])
    before_fc = deepcopy(client.tables["field_corrections"])
    before_reports = deepcopy(client.tables["event_reports"])

    result = reset.apply_snapshot(client, _snapshot(client))

    assert result["applied_ids"] == [E1]
    assert client.event()["annotation_status"] == "pending"
    assert client.event()["annotation_retry_count"] == 0
    assert client.tables["field_corrections"] == before_fc
    assert client.tables["event_reports"] == before_reports


def test_no_annotation_function_is_imported_or_called():
    assert not hasattr(reset, "annotate_pending_events")


def test_snapshot_hash_rejects_tampering(tmp_path):
    client = _Client(events=[_event()])
    snapshot = _snapshot(client)
    path = tmp_path / "snapshot.json"
    reset.write_snapshot(path, snapshot)
    assert stat.S_IMODE(path.stat().st_mode) == stat.S_IRUSR
    assert reset.load_snapshot(path)["snapshot_sha256"] == snapshot["snapshot_sha256"]

    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    tampered = deepcopy(snapshot)
    tampered["event_ids"] = [E2]
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        reset.load_snapshot(path)


def test_all_rows_preflight_before_first_mutation_on_stable_drift():
    client = _Client(events=[_event(E1), _event(E2)])
    snapshot = _snapshot(client, [E1, E2])
    client.event(E2)["location_name"] = "changed after snapshot"

    with pytest.raises(RuntimeError, match="stable-field drift"):
        reset.apply_snapshot(client, snapshot)
    assert client.update_attempts == []


def test_stable_field_set_contains_every_full_row_column_except_target_and_updated_at():
    row = _event(extra_none=None, extra_list=[1, None], extra_object={"a": ["b"]})

    assert set(reset.stable_projection(row)) == set(row) - reset.TARGET_FIELDS - reset.VOLATILE_FIELDS


def test_null_list_and_object_stable_values_round_trip_without_string_coercion():
    client = _Client(events=[_event(extra_none=None, extra_list=[1, None], extra_object={"a": ["b"]})])
    snapshot = _snapshot(client)

    report = reset.apply_snapshot(client, snapshot)

    assert report["applied_ids"] == [E1]
    assert client.event()["extra_none"] is None
    assert client.event()["extra_list"] == [1, None]
    assert client.event()["extra_object"] == {"a": ["b"]}


def test_updated_at_only_drift_warns_and_continues():
    client = _Client(events=[_event()])
    snapshot = _snapshot(client)
    client.event()["updated_at"] = "2026-07-31T02:00:00+00:00"

    report = reset.apply_snapshot(client, snapshot)

    assert report["applied_ids"] == [E1]
    assert report["warnings"] == [
        f"updated_at_only_drift={E1} snapshot=2026-07-30T01:00:00+00:00 current=2026-07-31T02:00:00+00:00"
    ]


def test_after_state_is_idempotent_noop_and_crash_rerun_completes_remaining():
    client = _Client(events=[_event(E1), _event(E2)])
    snapshot = _snapshot(client, [E1, E2])
    client.event(E1).update({"annotation_status": "pending", "annotation_retry_count": 0})

    report = reset.apply_snapshot(client, snapshot)

    assert report["noop_ids"] == [E1]
    assert report["applied_ids"] == [E2]
    assert [attempt[2] for attempt in client.update_attempts][0] == [
        ("eq", "id", E2),
        ("eq", "annotation_status", "error"),
        ("eq", "annotation_retry_count", 3),
    ]


def test_third_status_retry_state_stops_before_writes():
    client = _Client(events=[_event()])
    snapshot = _snapshot(client)
    client.event()["annotation_retry_count"] = 4

    with pytest.raises(RuntimeError, match="third status/retry state"):
        reset.apply_snapshot(client, snapshot)
    assert client.update_attempts == []


def test_cas_includes_full_id_status_retry_excludes_updated_at_and_resets_retry():
    client = _Client(events=[_event()])

    reset.apply_snapshot(client, _snapshot(client))

    table, patch, filters, matched = client.update_attempts[0]
    assert table == "events"
    assert patch == {"annotation_status": "pending", "annotation_retry_count": 0}
    assert filters == [
        ("eq", "id", E1),
        ("eq", "annotation_status", "error"),
        ("eq", "annotation_retry_count", 3),
    ]
    assert all(field != "updated_at" for _kind, field, _value in filters)
    assert matched == 1
    assert client.event()["annotation_retry_count"] == 0


@pytest.mark.parametrize("override, expected", [([], "0"), ([{"id": E1}, {"id": E2}], "2")])
def test_cas_rejects_zero_or_multi_row_results(override, expected):
    client = _Client(events=[_event()])
    snapshot = _snapshot(client)
    client.override_update_result = override

    with pytest.raises(RuntimeError, match=f"CAS affected {expected} rows"):
        reset.apply_snapshot(client, snapshot)


def test_related_report_rows_remain_pending_and_readback_matches_after_state():
    client = _Client(events=[_event()], event_reports=[_report()])
    snapshot = _snapshot(client)

    report = reset.apply_snapshot(client, snapshot)

    assert report["report_state"] == [{"id": f"report-{E1}", "status": "pending"}]
    assert client.tables["event_reports"][0]["status"] == "pending"
    assert client.event()["annotation_status"] == "pending"
    assert client.event()["annotation_retry_count"] == 0
