"""Scope-decision and event-report lifecycle tests for the annotator."""

from __future__ import annotations

import logging

import pytest

import annotator
from annotator import (
    SCOPE_REPORT_TYPE,
    SYSTEM_PROMPT,
    _build_scope_finding,
    _persist_scope_finding,
    _sanitize_scope_reason,
    _validate_scope_decision,
)


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, table):
        self._db = db
        self._table = table
        self._rows = list(db.tables.get(table, []))
        self._insert = None
        self._update = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self._rows = [row for row in self._rows if row.get(column) == value]
        return self

    def contains(self, column, values):
        expected = set(values)
        self._rows = [
            row for row in self._rows if expected <= set(row.get(column) or [])
        ]
        return self

    def order(self, column, desc=False):
        self._rows.sort(key=lambda row: row.get(column) or "", reverse=desc)
        return self

    def limit(self, count):
        self._rows = self._rows[:count]
        return self

    def insert(self, payload):
        self._insert = dict(payload)
        return self

    def update(self, payload):
        self._update = dict(payload)
        return self

    def execute(self):
        if self._insert is not None:
            if self._db.fail_insert:
                raise RuntimeError("insert failed")
            self._db.inserts.append(self._insert)
            self._db.tables.setdefault(self._table, []).append(self._insert)
            return _Result([dict(self._insert)])
        if self._update is not None:
            updated = []
            for row in self._rows:
                row.update(self._update)
                updated.append({"id": row.get("id")})
            self._db.updates.append(
                {"table": self._table, "payload": self._update, "rows": updated}
            )
            return _Result(updated)
        if self._db.fail_select:
            raise RuntimeError("select failed")
        return _Result([dict(row) for row in self._rows])


class _FakeSupabase:
    def __init__(self, reports=None, *, fail_insert=False, fail_select=False):
        self.tables = {"event_reports": list(reports or [])}
        self.fail_insert = fail_insert
        self.fail_select = fail_select
        self.inserts = []
        self.updates = []

    def table(self, name):
        return _Query(self, name)


def _event(*, address="台北市中山区楽群三路", updated_at="2026-08-03T00:00:00Z"):
    return {
        "id": "event-1",
        "location_address": address,
        "location_prefectures": ["台北"],
        "updated_at": updated_at,
    }


def _finding(
    decision="out_of_scope",
    *,
    address="台北市中山区楽群三路",
    reason="This event is for Taiwanese consumers.",
):
    return _build_scope_finding(
        _event(address=address),
        {},
        {"scope_decision": decision, "scope_reason": reason},
    )


def test_scope_finding_requires_semantic_and_location_gates():
    assert _finding()["should_queue"] is True
    assert _finding(address="東京都渋谷区神南1-1")["should_queue"] is False
    assert _finding(
        "in_scope",
        reason="This study tour is explicitly for Japanese participants.",
    )["should_queue"] is False
    assert _finding(
        "uncertain",
        address="香港MOM Livehouse",
        reason="The intended audience is unclear.",
    )["should_queue"] is True


def test_scope_prompt_emits_decision_without_active_mutation():
    assert "scope_decision" in SYSTEM_PROMPT
    assert "scope_reason" in SYSTEM_PROMPT
    assert "set is_active" not in SYSTEM_PROMPT


@pytest.mark.parametrize("value", [None, 7, {}, "outside", "OUT_OF_SCOPE"])
def test_invalid_scope_decision_fails_safe(value):
    assert _validate_scope_decision(value) == "uncertain"


def test_missing_scope_decision_queues_foreign_location_for_review():
    finding = _build_scope_finding(_event(), {}, {})

    assert finding["decision"] == "uncertain"
    assert finding["should_queue"] is True


def test_scope_reason_is_sanitized_and_bounded():
    assert _sanitize_scope_reason(42) is None
    assert _sanitize_scope_reason("  \x00  ") is None
    assert _sanitize_scope_reason("  hello\x00 world  ") == "hello world"
    assert len(_sanitize_scope_reason("x" * 500)) == 300


def test_effective_update_location_overrides_existing_db_location():
    finding = _build_scope_finding(
        _event(address="東京都渋谷区神南1-1"),
        {
            "location_address": "台北市信義區",
            "location_prefectures": ["台北"],
        },
        {
            "scope_decision": "out_of_scope",
            "scope_reason": "This event is for Taiwanese consumers.",
        },
    )
    assert finding["region"] == "taiwan"
    assert finding["effective_address"] == "台北市信義區"
    assert finding["should_queue"] is True


def test_pending_scope_report_is_not_duplicated():
    finding = _finding()
    db = _FakeSupabase([
        {
            "id": "report-1",
            "event_id": "event-1",
            "report_types": [SCOPE_REPORT_TYPE, f"scopeHash:{finding['fingerprint']}"],
            "status": "pending",
            "created_at": "2026-08-04T00:00:00Z",
            "confirmed_at": None,
        }
    ])

    persisted = _persist_scope_finding(db, _event(), finding, dry_run=False, in_run_seen=set())

    assert persisted is True
    assert db.inserts == []
    assert db.updates == []


def test_changed_pending_scope_report_is_refreshed_in_place():
    current = _finding()
    old = _finding(decision="uncertain", address="香港MOM Livehouse")
    db = _FakeSupabase([
        {
            "id": "report-1",
            "event_id": "event-1",
            "report_types": [SCOPE_REPORT_TYPE, f"scopeHash:{old['fingerprint']}"],
            "status": "pending",
            "created_at": "2026-08-04T00:00:00Z",
            "confirmed_at": None,
        }
    ])

    _persist_scope_finding(db, _event(), current, dry_run=False, in_run_seen=set())

    assert db.inserts == []
    assert len(db.updates) == 1
    assert db.updates[0]["rows"] == [{"id": "report-1"}]
    assert db.updates[0]["payload"] == {
        "report_types": current["report_types"],
        "admin_notes": current["admin_notes"],
    }


def test_scope_report_lookup_failure_skips_insert(caplog):
    db = _FakeSupabase(fail_select=True)
    caplog.set_level(logging.WARNING)

    persisted = _persist_scope_finding(db, _event(), _finding(), dry_run=False, in_run_seen=set())

    assert persisted is False
    assert db.inserts == []
    assert db.updates == []
    assert "queue skipped" in caplog.text


def test_same_run_scope_report_is_not_duplicated():
    db = _FakeSupabase()
    finding = _finding()
    in_run_seen = set()

    _persist_scope_finding(db, _event(), finding, dry_run=False, in_run_seen=in_run_seen)
    _persist_scope_finding(db, _event(), finding, dry_run=False, in_run_seen=in_run_seen)

    assert len(db.inserts) == 1


def test_new_scope_report_uses_deterministic_id():
    first = _FakeSupabase()
    second = _FakeSupabase()

    assert _persist_scope_finding(first, _event(), _finding(), dry_run=False, in_run_seen=set())
    assert _persist_scope_finding(second, _event(), _finding(), dry_run=False, in_run_seen=set())

    assert first.inserts[0]["id"] == second.inserts[0]["id"]


def test_cleared_finding_closes_pending_report():
    previous = _finding()
    cleared = _finding(
        decision="in_scope",
        reason="This exchange is explicitly for Japanese participants.",
    )
    db = _FakeSupabase([
        {
            "id": "report-1",
            "event_id": "event-1",
            "report_types": [SCOPE_REPORT_TYPE, f"scopeHash:{previous['fingerprint']}"],
            "status": "pending",
            "created_at": "2026-08-04T00:00:00Z",
            "confirmed_at": None,
        }
    ])

    persisted = _persist_scope_finding(db, _event(), cleared, dry_run=False, in_run_seen=set())

    assert persisted is True
    assert db.updates[0]["payload"]["status"] == "dismissed"
    assert db.updates[0]["rows"] == [{"id": "report-1"}]


def test_reason_change_refreshes_pending_scope_evidence():
    previous = _finding(reason="Old reason.")
    current = _finding(reason="New audience evidence.")
    assert previous["fingerprint"] != current["fingerprint"]
    db = _FakeSupabase([
        {
            "id": "report-1",
            "event_id": "event-1",
            "report_types": [SCOPE_REPORT_TYPE, f"scopeHash:{previous['fingerprint']}"],
            "status": "pending",
            "created_at": "2026-08-04T00:00:00Z",
            "confirmed_at": None,
        }
    ])

    assert _persist_scope_finding(db, _event(), current, dry_run=False, in_run_seen=set())
    assert db.updates[0]["payload"]["report_types"] == current["report_types"]


@pytest.mark.parametrize("status", ["confirmed", "dismissed"])
def test_resolved_unchanged_scope_report_is_not_reopened(status):
    finding = _finding()
    db = _FakeSupabase([
        {
            "id": "report-1",
            "event_id": "event-1",
            "report_types": [SCOPE_REPORT_TYPE, f"scopeHash:{finding['fingerprint']}"],
            "status": status,
            "created_at": "2026-08-04T00:00:00Z",
            "confirmed_at": "2026-08-04T00:00:00Z",
        }
    ])

    _persist_scope_finding(db, _event(), finding, dry_run=False, in_run_seen=set())

    assert db.inserts == []


def test_changed_event_reopens_resolved_scope_report_in_place():
    finding = _finding()
    db = _FakeSupabase([
        {
            "id": "report-1",
            "event_id": "event-1",
            "report_types": [SCOPE_REPORT_TYPE, f"scopeHash:{finding['fingerprint']}"],
            "status": "confirmed",
            "created_at": "2026-08-04T00:00:00Z",
            "confirmed_at": "2026-08-04T00:00:00Z",
        }
    ])

    _persist_scope_finding(
        db,
        _event(updated_at="2026-08-05T00:00:00Z"),
        finding,
        dry_run=False,
        in_run_seen=set(),
    )

    assert db.inserts == []
    assert db.updates[0]["payload"]["status"] == "pending"
    assert db.updates[0]["rows"] == [{"id": "report-1"}]


def test_dry_run_logs_payload_without_insert(caplog):
    db = _FakeSupabase()
    finding = _finding()
    caplog.set_level(logging.INFO)

    _persist_scope_finding(db, _event(), finding, dry_run=True, in_run_seen=set())

    assert db.inserts == []
    assert "would queue scope report" in caplog.text
    assert "scopeDecision:out_of_scope" in caplog.text


def test_insert_error_is_nonblocking(caplog):
    db = _FakeSupabase(fail_insert=True)
    caplog.set_level(logging.WARNING)

    persisted = _persist_scope_finding(db, _event(), _finding(), dry_run=False, in_run_seen=set())

    assert persisted is False
    assert db.inserts == []
    assert "failed to queue scope report" in caplog.text


def test_scope_persistence_failure_restores_pending_status(monkeypatch):
    db = _FakeSupabase()
    db.tables["events"] = [{"id": "event-1", "annotation_status": "annotated"}]
    monkeypatch.setattr(annotator, "_persist_scope_finding", lambda *_args, **_kwargs: False)

    persisted = annotator._persist_scope_finding_or_retry(
        db,
        _event(),
        {},
        {"scope_decision": "out_of_scope"},
        dry_run=False,
        in_run_seen=set(),
    )

    assert persisted is False
    assert db.tables["events"][0]["annotation_status"] == "pending"
    assert db.updates[-1]["payload"] == {"annotation_status": "pending"}
