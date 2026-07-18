"""Regression: error_recovery.py must SETTLE recovered annotation_error_stuck reports.

error_recovery.py escalates stuck annotation errors by INSERTing a single-type
`annotation_error_stuck` event_report (H0 boundary: insert-only, never closes).
G3 adds the missing settlement half: once the underlying event recovers (its
annotation reaches a verified-complete `annotated`/`reviewed` state), the pending
escalation row must be closed.

Settlement contract exercised here (`_settle_recovered_escalations`):

  * Eligibility — a row is settled ONLY when BOTH hold:
      - the event is verified recovered via H0's type-specific resolution
        predicate (annotation_status in {annotated, reviewed}); AND
      - the report is single-type: report_types == ["annotation_error_stuck"].
    A compound / multi-type row (including one carrying a `field:` payload token)
    is NEVER auto-settled here — it stays pending for manual review.

  * Status-last lifecycle (all-or-compensate): verify event recovery → reset
    annotation_retry_count → close the report. The report-status write is the
    FINAL write (full report_id + status='pending' CAS requiring EXACTLY ONE
    updated row; 0-row or multi-row → failure). Any earlier failure (recovery
    not verified, retry-reset raises or touches != 1 row, or the close CAS
    misses) leaves the report PENDING — no half-settled state.

The doubles are pure in-memory Supabase stand-ins (no network). Every test FAILS
before the settlement code exists (`_settle_recovered_escalations` is absent /
`run()` has no "settled" summary key) and PASSES once G3 lands.
"""
from __future__ import annotations

import error_recovery


# ---------------------------------------------------------------------------
# In-memory Supabase double (persists updates; supports failure injection)
# ---------------------------------------------------------------------------

class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db, table):
        self._db = db
        self._table = table
        self._op = "select"
        self._patch = None
        self._payload = None
        self._filters: list[tuple] = []
        self._limit = None

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

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def ov(self, col, val):
        self._filters.append(("ov", col, val))
        return self

    def gt(self, col, val):
        self._filters.append(("gt", col, val))
        return self

    def in_(self, col, vals):
        self._filters.append(("in", col, vals))
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        self._limit = n
        return self

    # NOTE: no .like() on purpose — settlement must match a uuid with .eq only.
    # If any settlement path attempted .like() it would raise AttributeError and
    # fail the suite loudly (guards the "uuid never .like()" invariant).

    def _match(self, rows):
        out = list(rows)
        for kind, col, val in self._filters:
            if kind == "eq":
                out = [r for r in out if r.get(col) == val]
            elif kind == "ov":
                want = set(val)
                out = [r for r in out if want & set(r.get(col) or [])]
            elif kind == "gt":
                out = [r for r in out if (r.get(col) or 0) > val]
            elif kind == "in":
                out = [r for r in out if r.get(col) in val]
        if self._limit is not None:
            out = out[: self._limit]
        return out

    def execute(self):
        hook = self._db.hooks.get((self._table, self._op))
        if hook is not None:
            hook()  # may raise to simulate a DB / network failure mid-lifecycle
        rows = self._db.tables.setdefault(self._table, [])
        if self._op == "insert":
            self._db.inserts.append((self._table, self._payload))
            rows.append(dict(self._payload))
            return _Result([{"id": self._payload.get("id", "ins-1")}])
        if self._op == "update":
            override = self._db.update_rowcount.get(self._table)
            if override is not None:
                # Simulate a CAS mismatch: pretend `override` rows matched WITHOUT
                # mutating any stored row (models 0-row / multi-row failure so the
                # report row is provably left untouched = still pending).
                self._db.updates.append((self._table, dict(self._patch), override))
                return _Result([{"id": "phantom"} for _ in range(override)])
            matched = self._match(rows)
            for r in matched:
                r.update(self._patch)
            self._db.updates.append((self._table, dict(self._patch), len(matched)))
            return _Result([dict(r) for r in matched])
        return _Result([dict(r) for r in self._match(rows)])


class FakeSupabase:
    def __init__(self, tables):
        self.tables = {n: [dict(r) for r in rows] for n, rows in tables.items()}
        self.calls: list[tuple] = []
        self.inserts: list[tuple] = []
        self.updates: list[tuple] = []          # (table, patch, rowcount)
        self.hooks: dict[tuple, object] = {}     # (table, op) -> callable that may raise
        self.update_rowcount: dict[str, int] = {}  # table -> forced update rowcount

    def table(self, name):
        return _Query(self, name)

    # --- test-only inspectors -------------------------------------------------
    def report(self, rid):
        return next((r for r in self.tables.get("event_reports", []) if r.get("id") == rid), None)

    def event(self, eid):
        return next((r for r in self.tables.get("events", []) if r.get("id") == eid), None)

    def event_report_updates(self):
        return [u for u in self.updates if u[0] == "event_reports"]

    def event_updates(self):
        return [u for u in self.updates if u[0] == "events"]


RID = "11111111-1111-4111-8111-111111111111"
EID = "22222222-2222-4222-8222-222222222222"


def _raise(exc: Exception):
    def _hook():
        raise exc
    return _hook


def _db(*, status="annotated", retry_count=2, report_types=None, report_status="pending"):
    rtypes = report_types if report_types is not None else ["annotation_error_stuck"]
    return FakeSupabase(
        {
            "events": [
                {
                    "id": EID,
                    "annotation_status": status,
                    "annotation_retry_count": retry_count,
                    "is_active": True,
                }
            ],
            "event_reports": [
                {
                    "id": RID,
                    "event_id": EID,
                    "report_types": rtypes,
                    "status": report_status,
                    "admin_notes": None,
                    "confirmed_at": None,
                }
            ],
        }
    )


# ---------------------------------------------------------------------------
# Happy path — single-type + recovered event settles, status-last
# ---------------------------------------------------------------------------

def test_settles_single_type_report_when_event_annotated():
    sb = _db(status="annotated", retry_count=2)
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=False)

    assert settled == 1
    rep = sb.report(RID)
    assert rep["status"] == "confirmed"
    assert rep["confirmed_at"] is not None
    assert rep["admin_notes"]  # a settlement note was written
    # retry reset applied
    assert sb.event(EID)["annotation_retry_count"] == 0
    # status-last: the events (retry reset) write precedes the event_reports close
    assert [u[0] for u in sb.updates] == ["events", "event_reports"]


def test_settles_single_type_report_when_event_reviewed():
    sb = _db(status="reviewed", retry_count=1)
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=False)

    assert settled == 1
    assert sb.report(RID)["status"] == "confirmed"


def test_skips_retry_reset_when_counter_already_zero():
    """retry_count already 0 → no redundant events write, but report still closes."""
    sb = _db(status="annotated", retry_count=0)
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=False)

    assert settled == 1
    assert sb.report(RID)["status"] == "confirmed"
    assert sb.event_updates() == []            # retry-reset skipped (idempotent)
    assert len(sb.event_report_updates()) == 1  # close still happened


# ---------------------------------------------------------------------------
# Not recovered — event must be annotated/reviewed (H0 predicate)
# ---------------------------------------------------------------------------

def test_does_not_settle_when_event_still_error():
    sb = _db(status="error")
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=False)

    assert settled == 0
    assert sb.report(RID)["status"] == "pending"
    assert sb.updates == []  # no writes at all


def test_does_not_settle_when_event_pending():
    sb = _db(status="pending")
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=False)

    assert settled == 0
    assert sb.report(RID)["status"] == "pending"
    assert sb.updates == []


def test_does_not_settle_when_event_missing():
    sb = _db(status="annotated")
    sb.tables["events"] = []  # event row vanished
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=False)

    assert settled == 0
    assert sb.report(RID)["status"] == "pending"
    assert sb.updates == []


# ---------------------------------------------------------------------------
# Compound / payload rows are NEVER auto-settled here
# ---------------------------------------------------------------------------

def test_never_settles_compound_report_row():
    sb = _db(status="annotated", report_types=["annotation_error_stuck", "auto_qa_missing_date"])
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=False)

    assert settled == 0
    assert sb.report(RID)["status"] == "pending"
    assert sb.updates == []


def test_never_settles_row_with_payload_token():
    sb = _db(status="annotated", report_types=["annotation_error_stuck", "field:name_zh"])
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=False)

    assert settled == 0
    assert sb.report(RID)["status"] == "pending"
    assert sb.updates == []


# ---------------------------------------------------------------------------
# Report-close CAS must match EXACTLY ONE row (0-row / multi-row → pending)
# ---------------------------------------------------------------------------

def test_report_close_zero_row_leaves_pending():
    sb = _db(status="annotated", retry_count=2)
    sb.update_rowcount["event_reports"] = 0  # CAS matched no pending row
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=False)

    assert settled == 0
    assert sb.report(RID)["status"] == "pending"  # not settled


def test_report_close_multi_row_leaves_pending():
    sb = _db(status="annotated", retry_count=2)
    sb.update_rowcount["event_reports"] = 2  # CAS matched >1 row → failure
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=False)

    assert settled == 0
    assert sb.report(RID)["status"] == "pending"


# ---------------------------------------------------------------------------
# Partial lifecycle failure on retry-reset leaves the report PENDING (no close)
# ---------------------------------------------------------------------------

def test_retry_reset_exception_leaves_report_pending():
    sb = _db(status="annotated", retry_count=2)
    sb.hooks[("events", "update")] = _raise(RuntimeError("db down"))
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=False)

    assert settled == 0
    assert sb.report(RID)["status"] == "pending"
    assert sb.event_report_updates() == []  # close never attempted → no half-settle


def test_retry_reset_zero_row_leaves_report_pending():
    sb = _db(status="annotated", retry_count=2)
    sb.update_rowcount["events"] = 0  # retry-reset touched no row
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=False)

    assert settled == 0
    assert sb.report(RID)["status"] == "pending"
    assert sb.event_report_updates() == []


# ---------------------------------------------------------------------------
# Dry-run counts eligible rows but performs ZERO writes
# ---------------------------------------------------------------------------

def test_dry_run_counts_but_writes_nothing():
    sb = _db(status="annotated", retry_count=2)
    settled = error_recovery._settle_recovered_escalations(sb, dry_run=True)

    assert settled == 1              # would-settle count
    assert sb.updates == []          # no writes
    assert sb.inserts == []
    assert sb.report(RID)["status"] == "pending"
    assert sb.event(EID)["annotation_retry_count"] == 2  # untouched


# ---------------------------------------------------------------------------
# run() wires settlement into Phase 0 and surfaces the count in its summary
# ---------------------------------------------------------------------------

def test_run_surfaces_settled_count(monkeypatch):
    # Event already recovered (annotated) → Phase 1 finds 0 error events, and the
    # pending single-type escalation is eligible for settlement.
    sb = _db(status="annotated", retry_count=2)
    sb.tables["field_corrections"] = []
    monkeypatch.setattr(error_recovery, "_supabase_client", lambda: sb)

    summary = error_recovery.run(dry_run=True, limit=100)

    assert summary["settled"] == 1
    assert summary["scanned"] == 0
    assert sb.updates == []   # dry-run: nothing written
    assert sb.inserts == []
