"""Offline contract tests for `qa_auto_fix.unlock_and_write` manifest modes.

No network, no Supabase client, no production data: every case runs against the
in-memory fake below.
"""

from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

import qa_auto_fix


def _array_literal(value: Any) -> str:
    if value is None:
        return "\x00none"
    items = [str(item).replace("\\", "\\\\").replace('"', '\\"') for item in value]
    return "{" + ",".join(f'"{item}"' for item in items) + "}"


class FakeQuery:
    def __init__(self, client: "FakeSupabase", table: str, op: str, payload=None, on_conflict=None):
        self.client = client
        self.table_name = table
        self.op = op
        self.payload = payload
        self.on_conflict = on_conflict
        self.columns = "*"
        self.returning: str | None = None
        self.filters: list[tuple[str, str, Any]] = []
        self._single = False
        self._limit: int | None = None
        self._range: tuple[int, int] | None = None
        self._count: str | None = None
        self._head = False

    def select(self, columns: str = "*", count: str | None = None, head: bool = False):
        if self.op == "select":
            self.columns = columns
        else:
            self.returning = columns
        self._count, self._head = count, head
        return self

    def eq(self, column: str, value: Any):
        self.filters.append(("eq", column, value))
        return self

    def is_(self, column: str, value: Any):
        self.filters.append(("is", column, value))
        return self

    def in_(self, column: str, values):
        self.filters.append(("in", column, list(values)))
        return self

    def order(self, column: str, desc: bool = False):
        self.filters.append(("order", column, desc))
        return self

    def range(self, start: int, end: int):
        self._range = (start, end)
        return self

    def limit(self, count: int):
        self._limit = count
        return self

    def single(self):
        self._single = True
        return self

    def _matches(self, row: dict[str, Any]) -> bool:
        for kind, column, value in self.filters:
            if kind == "order":
                continue
            actual = row.get(column)
            if kind == "eq":
                if isinstance(actual, (list, tuple)) or (
                    isinstance(value, str) and value.startswith("{") and value.endswith("}")
                ):
                    if _array_literal(actual) != value:
                        return False
                elif actual is None or str(actual) != str(value):
                    return False
            elif kind == "is":
                if str(value) == "null" and actual is not None:
                    return False
            elif kind == "in":
                if str(actual) not in {str(item) for item in value}:
                    return False
        return True

    def _selected(self) -> list[dict[str, Any]]:
        rows = [row for row in self.client.tables.get(self.table_name, []) if self._matches(row)]
        order_columns = [column for kind, column, _ in self.filters if kind == "order"]
        for column in reversed(order_columns):
            rows.sort(key=lambda row: str(row.get(column) or ""))
        if self._range:
            start, end = self._range
            rows = rows[start : end + 1]
        if self._limit is not None:
            rows = rows[: self._limit]
        return rows

    def _projected(self, rows: list[dict[str, Any]], columns: str | None) -> list[dict[str, Any]]:
        if not columns or columns == "*":
            return [deepcopy(row) for row in rows]
        wanted = [column.strip() for column in columns.split(",")]
        return [{column: row.get(column) for column in wanted} for row in rows]

    def execute(self):
        table = self.client.tables.setdefault(self.table_name, [])
        if self.op == "select":
            rows = self._projected(self._selected(), self.columns)
            if self._head:
                return SimpleNamespace(data=[], count=len(self._selected()))
            if self._single:
                return SimpleNamespace(data=rows[0] if rows else None, count=None)
            return SimpleNamespace(data=rows, count=None)

        if self.op == "update":
            targets = self._selected()
            for row in targets:
                row.update(deepcopy(self.payload))
            self.client.writes.append(
                (self.table_name, "update", deepcopy(self.payload), list(self.filters))
            )
            return SimpleNamespace(data=self._projected(targets, self.returning), count=None)

        if self.op == "delete":
            targets = self._selected()
            ids = {id(row) for row in targets}
            self.client.tables[self.table_name] = [row for row in table if id(row) not in ids]
            self.client.writes.append((self.table_name, "delete", None, list(self.filters)))
            return SimpleNamespace(data=self._projected(targets, self.returning), count=None)

        if self.op in {"insert", "upsert"}:
            payload = deepcopy(self.payload)
            row = None
            if self.op == "upsert" and self.on_conflict:
                keys = [key.strip() for key in self.on_conflict.split(",")]
                row = next(
                    (
                        item
                        for item in table
                        if all(str(item.get(key)) == str(payload.get(key)) for key in keys)
                    ),
                    None,
                )
            if row is None:
                payload.setdefault("id", f"{self.table_name}-{len(table) + 1}")
                table.append(payload)
                row = payload
            else:
                row.update(payload)
            self.client.writes.append((self.table_name, self.op, deepcopy(payload), []))
            return SimpleNamespace(data=[deepcopy(row)], count=None)

        raise AssertionError(f"unsupported op {self.op}")


class FakeSupabase:
    def __init__(self, tables: dict[str, list[dict[str, Any]]] | None = None):
        self.tables = {name: deepcopy(rows) for name, rows in (tables or {}).items()}
        self.writes: list[tuple[str, str, Any, list]] = []

    def table(self, name: str):
        self.tables.setdefault(name, [])
        return FakeTable(self, name)


class FakeTable:
    def __init__(self, client: FakeSupabase, name: str):
        self.client = client
        self.name = name

    def select(self, columns: str = "*", count: str | None = None, head: bool = False):
        return FakeQuery(self.client, self.name, "select").select(columns, count=count, head=head)

    def update(self, payload):
        return FakeQuery(self.client, self.name, "update", payload=payload)

    def delete(self):
        return FakeQuery(self.client, self.name, "delete")

    def insert(self, payload):
        return FakeQuery(self.client, self.name, "insert", payload=payload)

    def upsert(self, payload, on_conflict: str | None = None):
        return FakeQuery(self.client, self.name, "upsert", payload=payload, on_conflict=on_conflict)


DIGEST = "b" * 64
REASON = f"publication_manifest:fc-remove:{DIGEST}"
EVENT_ID = "11111111-1111-4111-8111-111111111111"
FC_ID = "22222222-2222-4222-8222-222222222222"


def _polluted_fc(**overrides):
    row = {
        "id": FC_ID,
        "event_id": EVENT_ID,
        "field_name": "location_name",
        "original_value": None,
        "corrected_value": "大阪城ホール",
        "corrected_by": None,
        "report_id": None,
        "created_at": "2026-06-26T04:00:00+00:00",
    }
    row.update(overrides)
    return row


def _client(fc_rows=None, event_overrides=None):
    event = {
        "id": EVENT_ID,
        "event_form": ["publication"],
        "location_name": "大阪城ホール",
        "location_address": "新刊のご購入は各販売チャネルでお願いします",
    }
    event.update(event_overrides or {})
    return FakeSupabase(
        {
            "events": [event],
            "field_corrections": list(fc_rows or []),
            "field_corrections_audit": [],
        }
    )


def _audits(client):
    return client.tables["field_corrections_audit"]


def _data_writes(client):
    """Writes to real data tables; audit rows are bookkeeping, not mutations."""
    return [write for write in client.writes if write[0] != "field_corrections_audit"]


OTHER_EVENT_ID = "55555555-5555-4555-8555-555555555555"
STORED_END = "2026-07-18T00:00:00+00:00"
REPAIRED_END = "2026-08-31T00:00:00+00:00"
END_REASON = f"publication_manifest:end-date:{DIGEST}"


def _lock_clean_client(fc_rows=None, event_overrides=None, cls=None, **cls_kwargs):
    """Client for lock_clean cases: one target event plus an untargeted twin.

    The twin shares the target's CAS value, so a write that is not scoped to the
    full event id would visibly touch two rows instead of exactly one.
    """
    event = {
        "id": EVENT_ID,
        "event_form": ["exhibition"],
        "end_date": STORED_END,
        "performers": None,
        "price_amount": None,
    }
    event.update(event_overrides or {})
    twin = {
        "id": OTHER_EVENT_ID,
        "event_form": ["exhibition"],
        "end_date": STORED_END,
        "performers": None,
        "price_amount": None,
    }
    tables = {
        "events": [event, twin],
        "field_corrections": list(fc_rows or []),
        "field_corrections_audit": [],
    }
    if cls is None:
        return FakeSupabase(tables)
    return cls(tables, **cls_kwargs)


class _DriftQuery(FakeQuery):
    """Select that reports a value other than the one actually stored."""

    def execute(self):
        result = super().execute()
        field = self.client.drift_field
        if isinstance(result.data, dict) and field in result.data:
            drifted = dict(result.data)
            drifted[field] = self.client.drift_value
            return SimpleNamespace(data=drifted, count=result.count)
        return result


class _VerifyDriftTable(FakeTable):
    def select(self, columns: str = "*", count: str | None = None, head: bool = False):
        if self.name == "events":
            self.client.event_select_count += 1
            # 1st = pre-mutation snapshot, 2nd = post-write verification read.
            if self.client.event_select_count >= 2:
                return _DriftQuery(self.client, self.name, "select").select(
                    columns, count=count, head=head
                )
        return super().select(columns, count=count, head=head)


class _VerifyDriftSupabase(FakeSupabase):
    """Stored rows keep the applied values, but verification reads a stale value."""

    def __init__(self, tables, *, field: str, drift_value: Any):
        super().__init__(tables)
        self.drift_field = field
        self.drift_value = drift_value
        self.event_select_count = 0

    def table(self, name: str):
        self.tables.setdefault(name, [])
        return _VerifyDriftTable(self, name)


def test_lock_clean_scalar_cas_writes_exactly_the_targeted_event():
    client = _lock_clean_client()

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="end_date",
        new_value=REPAIRED_END,
        mode="lock_clean",
        unlock_reason=END_REASON,
        expected_fc=None,
        expected_event_value=STORED_END,
    )

    assert ok is True
    rows = {row["id"]: row for row in client.tables["events"]}
    assert rows[EVENT_ID]["end_date"] == REPAIRED_END
    assert rows[OTHER_EVENT_ID]["end_date"] == STORED_END

    update = next(w for w in client.writes if w[0] == "events" and w[1] == "update")
    assert {column for _, column, _ in update[3]} == {"id", "end_date"}
    assert ("eq", "end_date", STORED_END) in update[3]


def test_lock_clean_scalar_correction_is_exact_text_not_repr():
    client = _lock_clean_client()

    qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="end_date",
        new_value=REPAIRED_END,
        mode="lock_clean",
        unlock_reason=END_REASON,
        expected_fc=None,
        expected_event_value=STORED_END,
    )

    corrections = client.tables["field_corrections"]
    assert len(corrections) == 1
    assert corrections[0]["field_name"] == "end_date"
    assert corrections[0]["corrected_value"] == str(REPAIRED_END)
    assert corrections[0]["corrected_value"] != repr(REPAIRED_END)


def test_lock_clean_non_string_scalar_correction_uses_str_not_json():
    client = _lock_clean_client()

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="price_amount",
        new_value=1800,
        mode="lock_clean",
        unlock_reason=f"publication_manifest:price:{DIGEST}",
        expected_fc=None,
        expected_event_value=None,
    )

    assert ok is True
    assert client.tables["field_corrections"][0]["corrected_value"] == "1800"


def test_lock_clean_list_correction_is_json_text_not_repr_or_comma_join():
    stored = ["旧名"]
    value = ["王小明", "李小華"]
    client = _lock_clean_client(event_overrides={"performers": stored})

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="performers",
        new_value=value,
        mode="lock_clean",
        unlock_reason=f"publication_manifest:performers:{DIGEST}",
        expected_fc=None,
        expected_event_value=stored,
    )

    assert ok is True
    assert client.tables["events"][0]["performers"] == value

    corrected = client.tables["field_corrections"][0]["corrected_value"]
    assert corrected == json.dumps(value, ensure_ascii=False)
    assert json.loads(corrected) == value
    assert corrected != repr(value)
    assert corrected != str(value)
    assert corrected != "、".join(value)
    assert corrected != ", ".join(value)

    update = next(w for w in client.writes if w[0] == "events" and w[1] == "update")
    assert ("eq", "performers", '{"旧名"}') in update[3]


def test_lock_clean_expected_absent_correction_rejects_before_touching_the_event():
    existing = _polluted_fc(field_name="end_date", corrected_value=STORED_END)
    client = _lock_clean_client([deepcopy(existing)])

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="end_date",
        new_value=REPAIRED_END,
        mode="lock_clean",
        unlock_reason=END_REASON,
        expected_fc=None,
        expected_event_value=STORED_END,
    )

    assert ok is False
    assert client.tables["events"][0]["end_date"] == STORED_END
    assert client.tables["field_corrections"] == [existing]
    assert _data_writes(client) == []

    failed = [row for row in _audits(client) if row["operation_status"] == "verify_failed"]
    assert len(failed) == 1
    assert "expected_fc_mismatch" in failed[0]["error_message"]


def test_lock_clean_event_value_drift_rejects_before_touching_the_event():
    client = _lock_clean_client(event_overrides={"end_date": "2026-09-30T00:00:00+00:00"})

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="end_date",
        new_value=REPAIRED_END,
        mode="lock_clean",
        unlock_reason=END_REASON,
        expected_fc=None,
        expected_event_value=STORED_END,
    )

    assert ok is False
    assert client.tables["events"][0]["end_date"] == "2026-09-30T00:00:00+00:00"
    assert client.tables["field_corrections"] == []
    assert _data_writes(client) == []

    failed = [row for row in _audits(client) if row["operation_status"] == "verify_failed"]
    assert len(failed) == 1
    assert "expected_event_value_mismatch" in failed[0]["error_message"]


def test_lock_clean_success_finalizes_one_applied_audit_with_the_after_value():
    client = _lock_clean_client()

    qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="end_date",
        new_value=REPAIRED_END,
        mode="lock_clean",
        unlock_reason=END_REASON,
        r_class="publication_policy",
        expected_fc=None,
        expected_event_value=STORED_END,
    )

    audits = _audits(client)
    assert len(audits) == 1
    assert audits[0]["operation_status"] == "applied"
    assert audits[0]["event_before_value_json"] == STORED_END
    assert audits[0]["event_after_value_json"] == REPAIRED_END
    assert audits[0]["verified_at"]
    assert audits[0]["unlock_reason"] == END_REASON
    assert DIGEST in audits[0]["unlock_reason"]


def test_lock_clean_false_does_not_mean_nothing_was_written():
    # unlock_and_write is NOT transactional: the event and field_correction writes
    # land first, and only the later verification read fails. A False return must
    # therefore never be read as "no write happened".
    client = _lock_clean_client(
        cls=_VerifyDriftSupabase,
        field="end_date",
        drift_value="2026-09-30T00:00:00+00:00",
    )

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="end_date",
        new_value=REPAIRED_END,
        mode="lock_clean",
        unlock_reason=END_REASON,
        expected_fc=None,
        expected_event_value=STORED_END,
    )

    assert ok is False
    # Both writes are already applied and observable despite the False return.
    assert client.tables["events"][0]["end_date"] == REPAIRED_END
    assert client.tables["field_corrections"][0]["corrected_value"] == REPAIRED_END
    assert [w[1] for w in _data_writes(client)] == ["update", "upsert"]

    failed = [row for row in _audits(client) if row["operation_status"] == "verify_failed"]
    assert len(failed) == 1
    assert "post_write_mismatch" in failed[0]["error_message"]
    assert failed[0].get("event_after_value_json") is None


def test_unlock_only_expected_fc_deletes_and_finalizes_one_anchored_audit():
    expected = _polluted_fc()
    client = _client([deepcopy(expected)])

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="location_name",
        new_value=None,
        mode="unlock_only",
        unlock_reason=REASON,
        r_class="publication_policy",
        expected_fc=expected,
    )

    assert ok is True
    assert client.tables["field_corrections"] == []
    assert client.tables["events"][0]["location_name"] == "大阪城ホール"

    applied = [row for row in _audits(client) if row["operation_status"] == "applied"]
    assert len(applied) == 1
    assert applied[0]["field_correction_id"] == FC_ID
    assert applied[0]["unlock_reason"] == REASON
    assert DIGEST in applied[0]["unlock_reason"]
    assert applied[0]["verified_at"]
    assert applied[0]["event_id"] == EVENT_ID
    assert applied[0]["field_name"] == "location_name"


def test_unlock_only_deletes_by_full_field_correction_identity():
    expected = _polluted_fc()
    client = _client([deepcopy(expected)])

    qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="location_name",
        new_value=None,
        mode="unlock_only",
        unlock_reason=REASON,
        expected_fc=expected,
    )

    deletes = [write for write in _data_writes(client) if write[1] == "delete"]
    assert len(deletes) == 1
    columns = {column for _, column, _ in deletes[0][3]}
    assert columns == {"id", "event_id", "field_name"}


@pytest.mark.parametrize(
    "drift",
    [
        {"corrected_value": "別の場所"},
        {"corrected_by": "99999999-9999-4999-8999-999999999999"},
        {"report_id": "33333333-3333-4333-8333-333333333333"},
        {"created_at": "2026-06-27T04:00:00+00:00"},
        {"original_value": "旧値"},
    ],
)
def test_unlock_only_rejects_complete_row_drift_before_deleting(drift):
    expected = _polluted_fc()
    live = _polluted_fc(**drift)
    client = _client([live])

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="location_name",
        new_value=None,
        mode="unlock_only",
        unlock_reason=REASON,
        expected_fc=expected,
    )

    assert ok is False
    assert client.tables["field_corrections"] == [live]
    assert _data_writes(client) == []
    failed = [row for row in _audits(client) if row["operation_status"] == "verify_failed"]
    assert len(failed) == 1
    assert "expected_fc_mismatch" in failed[0]["error_message"]


def test_unlock_only_rejects_missing_expected_row_and_never_raw_deletes():
    client = _client([])

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="location_name",
        new_value=None,
        mode="unlock_only",
        unlock_reason=REASON,
        expected_fc=_polluted_fc(),
    )

    assert ok is False
    assert _data_writes(client) == []


def test_unlock_only_expected_absent_rejects_an_unexpected_row():
    client = _client([_polluted_fc()])

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="location_name",
        new_value=None,
        mode="unlock_only",
        unlock_reason=REASON,
        expected_fc=None,
    )

    assert ok is False
    assert client.tables["field_corrections"] != []


def test_unlock_only_without_contract_keeps_legacy_behaviour():
    client = _client([_polluted_fc()])

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="location_name",
        new_value=None,
        mode="unlock_only",
        unlock_reason="auto_fix_legacy",
    )

    assert ok is True
    assert client.tables["field_corrections"] == []
    assert _audits(client)[0].get("field_correction_id") is None


def test_lock_empty_creates_exactly_one_sentinel_and_cas_clears_the_event():
    client = _client([])

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="location_address",
        new_value=None,
        mode="lock_empty",
        unlock_reason=f"publication_manifest:event-clear:{DIGEST}",
        expected_fc=None,
        expected_event_value="新刊のご購入は各販売チャネルでお願いします",
        expected_event_form=["publication"],
    )

    assert ok is True
    assert client.tables["events"][0]["location_address"] is None
    sentinels = client.tables["field_corrections"]
    assert len(sentinels) == 1
    assert sentinels[0]["corrected_value"] == ""
    update = next(write for write in client.writes if write[1] == "update" and write[0] == "events")
    assert {column for _, column, _ in update[3]} == {"id", "location_address", "event_form"}


def test_lock_empty_preserves_an_exact_sentinel_but_still_cas_clears_the_event():
    sentinel = {
        "id": "44444444-4444-4444-8444-444444444444",
        "event_id": EVENT_ID,
        "field_name": "location_address",
        "original_value": None,
        "corrected_value": "",
        "corrected_by": None,
        "report_id": None,
        "created_at": "2026-06-01T00:00:00+00:00",
    }
    client = _client([deepcopy(sentinel)])

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="location_address",
        new_value=None,
        mode="lock_empty",
        unlock_reason=f"publication_manifest:event-clear:{DIGEST}",
        expected_fc=sentinel,
        expected_event_value="新刊のご購入は各販売チャネルでお願いします",
        expected_event_form=["publication"],
    )

    assert ok is True
    assert client.tables["events"][0]["location_address"] is None
    assert client.tables["field_corrections"] == [sentinel]
    assert not [write for write in _data_writes(client) if write[1] == "upsert"]


def test_lock_empty_rejects_event_value_drift_before_writing():
    client = _client([], event_overrides={"location_address": "別の住所"})

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="location_address",
        new_value=None,
        mode="lock_empty",
        unlock_reason=f"publication_manifest:event-clear:{DIGEST}",
        expected_fc=None,
        expected_event_value="新刊のご購入は各販売チャネルでお願いします",
        expected_event_form=["publication"],
    )

    assert ok is False
    assert client.tables["events"][0]["location_address"] == "別の住所"
    assert _data_writes(client) == []


def test_lock_empty_rejects_mixed_event_form_before_writing():
    client = _client([], event_overrides={"event_form": ["publication", "lecture"]})

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="location_address",
        new_value=None,
        mode="lock_empty",
        unlock_reason=f"publication_manifest:event-clear:{DIGEST}",
        expected_fc=None,
        expected_event_value="新刊のご購入は各販売チャネルでお願いします",
        expected_event_form=["publication"],
    )

    assert ok is False
    assert _data_writes(client) == []


def test_legacy_lock_empty_without_cas_still_issues_an_id_only_update():
    client = _client([])

    ok = qa_auto_fix.unlock_and_write(
        client,
        event_id=EVENT_ID,
        field_name="location_address",
        new_value=None,
        mode="lock_empty",
        unlock_reason="auto_fix_legacy",
    )

    assert ok is True
    update = next(write for write in client.writes if write[1] == "update" and write[0] == "events")
    assert {column for _, column, _ in update[3]} == {"id"}


def test_pg_array_literal_and_cas_filter_use_null_semantics():
    assert qa_auto_fix.pg_array_literal(["publication"]) == '{"publication"}'
    assert qa_auto_fix.pg_array_literal([]) == "{}"

    recorded: list[tuple[str, str, Any]] = []

    class _Recorder:
        def eq(self, column, value):
            recorded.append(("eq", column, value))
            return self

        def is_(self, column, value):
            recorded.append(("is", column, value))
            return self

    query = _Recorder()
    qa_auto_fix.apply_cas_filter(query, "venue_id", None)
    qa_auto_fix.apply_cas_filter(query, "event_form", ["publication"])
    qa_auto_fix.apply_cas_filter(query, "location_name", "大阪城ホール")

    assert recorded == [
        ("is", "venue_id", "null"),
        ("eq", "event_form", '{"publication"}'),
        ("eq", "location_name", "大阪城ホール"),
    ]
