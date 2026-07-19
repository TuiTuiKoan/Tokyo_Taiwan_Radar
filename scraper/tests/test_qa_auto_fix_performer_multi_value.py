"""Regression: qa_auto_fix.run() must dispatch a SINGLE-TYPE performer
multi-value pollution report through the deterministic H0 single-type path.

Group G4b (scraper slice) wires the existing
``handle_performer_multi_value_split`` handler into the normal daily
``run()`` flow. Previously that handler was only reachable from
``qa_heartbeat``'s HANDLER_MAP, never from ``run()`` itself.

Eligibility reuses ``auto_qa.single_auto_type``: a report qualifies only when
its ``report_types`` is EXACTLY ONE known Auto-QA type
(``auto_qa_performer_multi_value_pollution``). Compound / multi-type / human /
payload-token rows are never auto-handled.

Every test drives the whole ``run()`` entrypoint (not the handler directly)
against a pure in-memory Supabase double — no network, ``send_line_message``
stubbed. The "reached from run()" and "empty FC serializes as ''" tests FAIL
before the wiring exists and PASS after; the compound-exclusion test guards the
single-type gate on both sides.
"""
from __future__ import annotations

import json

import qa_auto_fix

# Full report / event ids — uuid columns are always matched with .eq(), never
# .like(), so these are used verbatim by the fake below.
RID = "33333333-3333-4333-8333-333333333333"
EID = "44444444-4444-4444-8444-444444444444"


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    """One chained query against a single table of the in-memory double.

    Persists inserts / updates / upserts back into the shared table list so
    ``unlock_and_write``'s post-write verification re-read sees the mutation.
    Deliberately exposes NO ``.like()`` — uuid matches must use ``.eq()``.
    """

    def __init__(self, db, table):
        self._db = db
        self._table = table
        self._op = "select"
        self._patch = None
        self._payload = None
        self._on_conflict = None
        self._filters = []
        self._limit = None
        self._single = False
        self._negate_next = False

    def select(self, cols="*", *_a, **_k):
        self._op = "select"
        self._db.calls.append((self._table, "select", cols))
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, patch):
        self._op = "update"
        self._patch = patch
        return self

    def upsert(self, payload, on_conflict=None):
        self._op = "upsert"
        self._payload = payload
        self._on_conflict = on_conflict
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def in_(self, col, vals):
        self._filters.append(("in", col, vals))
        return self

    def contains(self, col, vals):
        self._filters.append(("contains", col, vals))
        return self

    @property
    def not_(self):
        self._negate_next = True
        return self

    def is_(self, col, val):
        self._filters.append(("is_not" if self._negate_next else "is", col, val))
        self._negate_next = False
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def single(self):
        self._single = True
        return self

    def _match(self, rows):
        out = list(rows)
        for kind, col, val in self._filters:
            if kind == "eq":
                out = [r for r in out if r.get(col) == val]
            elif kind == "in":
                out = [r for r in out if r.get(col) in val]
            elif kind == "contains":
                want = set(val)
                out = [r for r in out if want <= set(r.get(col) or [])]
            elif kind == "is":
                out = [r for r in out if r.get(col) is val]
            elif kind == "is_not":
                out = [r for r in out if r.get(col) is not val]
        if self._limit is not None:
            out = out[: self._limit]
        return out

    def execute(self):
        rows = self._db.tables.setdefault(self._table, [])

        if self._op == "insert":
            stored = dict(self._payload)
            stored.setdefault("id", f"ins-{len(self._db.inserts) + 1}")
            self._db.inserts.append((self._table, dict(self._payload)))
            rows.append(stored)
            return _Result([{"id": stored["id"]}])

        if self._op == "upsert":
            keys = [k.strip() for k in (self._on_conflict or "").split(",") if k.strip()]
            existing = None
            for r in rows:
                if keys and all(r.get(k) == self._payload.get(k) for k in keys):
                    existing = r
                    break
            if existing is not None:
                existing.update(self._payload)
                result_row = existing
            else:
                rows.append(dict(self._payload))
                result_row = rows[-1]
            self._db.upserts.append((self._table, dict(self._payload)))
            return _Result([dict(result_row)])

        if self._op == "delete":
            matched = self._match(rows)
            self._db.tables[self._table] = [r for r in rows if r not in matched]
            self._db.deletes.append((self._table, len(matched)))
            return _Result([dict(r) for r in matched])

        if self._op == "update":
            matched = self._match(rows)
            for r in matched:
                r.update(self._patch)
            self._db.updates.append((self._table, dict(self._patch), len(matched)))
            return _Result([dict(r) for r in matched])

        matched = self._match(rows)
        if self._single:
            return _Result(dict(matched[0]) if matched else None)
        return _Result([dict(r) for r in matched])


class FakeSupabase:
    def __init__(self, tables):
        self.tables = {n: [dict(r) for r in rows] for n, rows in tables.items()}
        self.calls: list = []
        self.inserts: list = []
        self.updates: list = []
        self.upserts: list = []
        self.deletes: list = []

    def table(self, name):
        return _Query(self, name)

    # --- inspectors -------------------------------------------------------
    def event(self, eid):
        return next((r for r in self.tables.get("events", []) if r.get("id") == eid), None)

    def report(self, rid):
        return next((r for r in self.tables.get("event_reports", []) if r.get("id") == rid), None)

    def field_corrections(self):
        return list(self.tables.get("field_corrections", []))


def _build_db(report_types):
    return FakeSupabase(
        {
            "events": [
                {
                    "id": EID,
                    "performer": "\u9673\u4e00\u3001\u6797\u4e8c",  # 陳一、林二
                    "performers": [],
                    "performer_zh": "\u9673\u4e00",  # 陳一
                    "performer_en": "Chen Yi",
                    "performers_zh": [],
                    "performers_en": [],
                    "annotation_status": "annotated",
                }
            ],
            "event_reports": [
                {
                    "id": RID,
                    "event_id": EID,
                    "report_types": report_types,
                    "status": "pending",
                }
            ],
            "field_corrections": [],
            "field_corrections_audit": [],
        }
    )


def _patch(monkeypatch, sb):
    monkeypatch.setattr(qa_auto_fix, "_supabase_client", lambda: sb)
    monkeypatch.setattr(qa_auto_fix, "send_line_message", lambda *a, **k: None)


def test_run_dispatches_single_type_performer_report(monkeypatch):
    """run() reaches the performer multi-value cleanup for a single-type report.

    Asserted via the run() entrypoint (not the handler directly): performer is
    split into performers[], the polluted scalar field is cleared, and the
    report is closed. FAILS before the wiring exists.
    """
    sb = _build_db(["auto_qa_performer_multi_value_pollution"])
    _patch(monkeypatch, sb)

    result = qa_auto_fix.run(dry_run=False)

    ev = sb.event(EID)
    assert ev["performers"] == ["\u9673\u4e00", "\u6797\u4e8c"]  # split applied
    assert ev["performer"] is None  # pollution cleared
    assert sb.report(RID)["status"] == "confirmed"  # report closed status-last

    perf = result["summary"]["performer_multi_value_split"]
    assert perf["pending_reports"] == 1
    assert perf["handled"] == 1


def test_run_skips_compound_performer_report(monkeypatch):
    """A compound / multi-type row carrying the performer type is NOT
    auto-handled by run(). Guards the single-type gate (passes before + after).
    """
    sb = _build_db(
        ["auto_qa_performer_multi_value_pollution", "auto_qa_missing_hours"]
    )
    _patch(monkeypatch, sb)

    qa_auto_fix.run(dry_run=False)

    ev = sb.event(EID)
    assert ev["performer"] == "\u9673\u4e00\u3001\u6797\u4e8c"  # untouched
    assert ev["performers"] == []
    assert sb.report(RID)["status"] == "pending"  # never confirmed


def test_run_performer_lock_empty_serializes_as_empty_string(monkeypatch):
    """Cleared translation fields lock as intentional-empty: corrected_value ==
    "" (never SQL NULL). The performers[] list itself locks with its JSON value.
    FAILS before the wiring exists (no field_corrections written).
    """
    sb = _build_db(["auto_qa_performer_multi_value_pollution"])
    _patch(monkeypatch, sb)

    qa_auto_fix.run(dry_run=False)

    fcs = {fc["field_name"]: fc for fc in sb.field_corrections()}
    for field in (
        "performer",
        "performer_zh",
        "performer_en",
        "performers_zh",
        "performers_en",
    ):
        assert field in fcs, f"missing field_correction for {field}"
        assert fcs[field]["corrected_value"] == ""

    # No field_correction ever carries a SQL NULL corrected_value.
    assert all(fc["corrected_value"] is not None for fc in sb.field_corrections())

    # performers[] locks with the JSON list, not the empty sentinel.
    assert json.loads(fcs["performers"]["corrected_value"]) == [
        "\u9673\u4e00",
        "\u6797\u4e8c",
    ]
