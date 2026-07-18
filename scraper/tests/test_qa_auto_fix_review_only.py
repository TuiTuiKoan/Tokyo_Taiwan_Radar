"""Regression: unlock_and_write(review_only) must not query a real events column.

qa_heartbeat._dispatch() routes every below-threshold / no-handler report through
qa_auto_fix.unlock_and_write(..., field_name="__review__", mode="review_only"),
where "__review__" is a SENTINEL, not a real events column. The pre-fix code ran
the snapshot select("id,__review__") unconditionally — before the review_only /
dry_run short-circuits — so PostgREST raised APIError 42703 (undefined_column)
and the whole `qa_heartbeat.py --dry-run` crashed at qa_auto_fix.py:517.

These tests use an in-memory Supabase double whose `events` table faithfully
rejects any select of a column outside its schema (reproducing 42703). They FAIL
against the pre-fix code (the sentinel select raises) and PASS once the reads are
guarded behind `if mode != "review_only":`. A control test confirms real write
modes still snapshot their column, including under dry_run, so the guard does not
over-skip the real write paths.
"""
from __future__ import annotations

from qa_auto_fix import unlock_and_write


class _FakeAPIError(Exception):
    """Mimics postgrest.exceptions.APIError for SQLSTATE 42703 (undefined_column)."""

    def __init__(self, message: str, code: str = "42703") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# Real events columns the double recognises. "__review__" is deliberately absent,
# so any select referencing it raises 42703 exactly like production PostgREST.
_EVENTS_COLUMNS = {"id", "name_zh", "description_zh", "start_date"}


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, table):
        self._db = db
        self._table = table
        self._rows = [dict(r) for r in db.tables.get(table, [])]
        self._single = False
        self._update = None
        self._insert = None
        self._select_cols = None

    def select(self, cols="*", *_a, **_k):
        self._select_cols = cols
        self._db.select_calls.append((self._table, cols))
        return self

    def insert(self, payload):
        self._insert = payload
        return self

    def update(self, patch):
        self._update = patch
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def single(self):
        self._single = True
        return self

    def execute(self):
        # Reproduce Postgres 42703 at execute time for an undefined events column.
        if (
            self._table == "events"
            and self._insert is None
            and self._update is None
            and self._select_cols not in (None, "*")
        ):
            requested = [c.strip() for c in str(self._select_cols).split(",") if c.strip()]
            for col in requested:
                if col not in _EVENTS_COLUMNS:
                    raise _FakeAPIError(f"column events.{col} does not exist")
        if self._insert is not None:
            self._db.inserts.append((self._table, self._insert))
            return _Result([{"id": "audit-1"}])  # emulate INSERT ... RETURNING id
        if self._update is not None:
            self._db.updates.append((self._table, self._update))
            updated = []
            for r in self._rows:
                r.update(self._update)
                updated.append(dict(r))
            return _Result(updated)
        if self._single:
            return _Result(dict(self._rows[0]) if self._rows else None)
        return _Result([dict(r) for r in self._rows])


class FakeSupabase:
    def __init__(self, tables):
        self.tables = {name: [dict(r) for r in rows] for name, rows in tables.items()}
        self.select_calls: list[tuple] = []
        self.inserts: list[tuple] = []
        self.updates: list[tuple] = []

    def table(self, name):
        return _Query(self, name)


def _fresh_db():
    return FakeSupabase(
        {
            "events": [{"id": "e1", "name_zh": "简体"}],
            "field_corrections": [],
            "field_corrections_audit": [],
        }
    )


def _events_selects(sb):
    return [(t, c) for (t, c) in sb.select_calls if t == "events"]


def test_review_only_sentinel_never_queries_events_column():
    """The __review__ sentinel must not reach an events column select (no 42703).

    Mirrors the exact qa_heartbeat._dispatch() below-threshold call. FAILS pre-fix
    (snapshot select("id,__review__") raises 42703); PASSES post-fix.
    """
    sb = _fresh_db()
    ok = unlock_and_write(
        sb,
        event_id="e1",
        field_name="__review__",
        new_value=None,
        mode="review_only",
        unlock_reason="heartbeat_review_only:missing_organizer:0.40:below_threshold",
        report_id="r1",
        r_class="missing_organizer",
        model_used="gpt-4o",
        confidence=0.40,
        dry_run=False,
    )
    assert ok is True
    # No events column query was issued at all — so the sentinel never hits 42703.
    assert _events_selects(sb) == [], f"unexpected events query: {_events_selects(sb)}"
    # review_only still leaves an audit trail: one audit insert + one finalize update.
    assert any(t == "field_corrections_audit" for (t, _) in sb.inserts)
    assert any(t == "field_corrections_audit" for (t, _) in sb.updates)


def test_review_only_dry_run_touches_no_db():
    """dry_run review_only short-circuits before any read or write."""
    sb = _fresh_db()
    ok = unlock_and_write(
        sb,
        event_id="e1",
        field_name="__review__",
        new_value=None,
        mode="review_only",
        unlock_reason="heartbeat_review_only:test",
        report_id="r1",
        dry_run=True,
    )
    assert ok is True
    assert _events_selects(sb) == []
    # dry_run: audit_start returns None without inserting; finalize is a no-op.
    assert sb.inserts == []
    assert sb.updates == []


def test_real_field_write_mode_still_snapshots_column():
    """Control: real write modes still read their events column (no over-skip).

    Passes both before and after the fix — guards against a future change that
    skips the snapshot for every dry_run instead of only the review_only sentinel.
    """
    sb = _fresh_db()
    ok = unlock_and_write(
        sb,
        event_id="e1",
        field_name="name_zh",
        new_value="繁體",
        mode="lock_clean",
        unlock_reason="test",
        report_id="r1",
        dry_run=True,
    )
    assert ok is True
    # The real column WAS snapshotted (existing behaviour preserved).
    assert ("events", "id,name_zh") in sb.select_calls
    # dry_run performs no write.
    assert sb.inserts == []
    assert sb.updates == []
