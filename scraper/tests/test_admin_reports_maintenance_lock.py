"""Lock-atomicity regression tests for the Admin Reports #204 maintenance lock.

Exercises the compare-and-set (CAS) acquire/release primitives in
`_oneoff_admin_reports_maintenance.py` with a pure in-memory Supabase double
(no network). The double faithfully models the two behaviours the real lock
depends on:

  * A conditional UPDATE guarded by `.eq(...)` filters mutates ONLY the rows
    matching every filter, and returns those rows (so row-count == len(data)).
  * PostgREST JSON-path filters `value->>active` / `value->>window_id` compare
    the JSON member as text ('true' / 'false' / the string value), and an
    absent member never matches (fail-closed).

Together these let us prove: single-winner concurrent acquire, no takeover of
an active / malformed / stale-token row, and a window_id-scoped release.
"""
from __future__ import annotations

import pytest

import _oneoff_admin_reports_maintenance as maint

LOCK_KEY = maint.LOCK_KEY


# ---------------------------------------------------------------------------
# In-memory Supabase double (models conditional-update CAS + JSON-path filters)
# ---------------------------------------------------------------------------

class _Result:
    def __init__(self, data):
        self.data = data


def _json_text(v):
    """Model Postgres `->>` : JSON member rendered as text (or None if absent)."""
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return None
    return str(v)


class _Query:
    def __init__(self, db, table):
        self._db = db
        self._table = table
        self._op = "select"
        self._patch = None
        self._payload = None
        self._filters: list[tuple] = []

    def select(self, cols="*", *_a, **_k):
        self._op = "select"
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
        self._filters.append((col, val))
        return self

    def _match(self, rows):
        out = []
        for r in rows:
            ok = True
            for col, val in self._filters:
                if "->>" in col:
                    base, key = col.split("->>", 1)
                    key = key.strip("'\"")
                    actual = _json_text((r.get(base) or {}).get(key))
                else:
                    actual = r.get(col)
                if actual != val:
                    ok = False
                    break
            if ok:
                out.append(r)
        return out

    def execute(self):
        rows = self._db.tables.setdefault(self._table, [])
        if self._op == "insert":
            payload = dict(self._payload)
            rows.append(payload)
            self._db.inserts.append((self._table, payload))
            return _Result([dict(payload)])
        if self._op == "update":
            matched = self._match(rows)
            for r in matched:
                r.update(self._patch)
            self._db.updates.append((self._table, dict(self._patch), len(matched)))
            return _Result([dict(r) for r in matched])
        return _Result([dict(r) for r in self._match(rows)])


class FakeSupabase:
    def __init__(self, rows=None):
        self.tables = {"app_settings": [dict(r) for r in (rows or [])]}
        self.inserts: list[tuple] = []
        self.updates: list[tuple] = []

    def table(self, name):
        return _Query(self, name)

    # test-only inspector
    def row(self):
        rows = self.tables.get("app_settings", [])
        return next((r for r in rows if r.get("key") == LOCK_KEY), None)


def _seed(sb=None):
    sb = sb or FakeSupabase()
    maint.seed_inactive(sb)
    return sb


# ---------------------------------------------------------------------------
# seed-inactive
# ---------------------------------------------------------------------------

def test_seed_inactive_creates_row_when_absent():
    sb = FakeSupabase()
    maint.seed_inactive(sb)
    row = sb.row()
    assert row is not None
    assert row["value"] == {"active": False}
    assert row["updated_at"]  # a token was stamped


def test_seed_inactive_idempotent_when_present():
    sb = _seed()
    token_before = sb.row()["updated_at"]
    maint.seed_inactive(sb)  # second call must be a no-op
    assert len(sb.tables["app_settings"]) == 1
    assert sb.row()["updated_at"] == token_before
    assert sb.inserts == [("app_settings", {"key": LOCK_KEY, "value": {"active": False}, "updated_at": token_before})]


# ---------------------------------------------------------------------------
# acquire — happy path + fail-closed guards
# ---------------------------------------------------------------------------

def test_acquire_flips_inactive_to_active():
    sb = _seed()
    prior_token = sb.row()["updated_at"]
    audit = maint.acquire(sb, reason="cleanup", actor="op@host")

    assert audit["row_count"] == 1
    row = sb.row()
    assert row["value"]["active"] is True
    assert row["value"]["window_id"] == audit["window_id"]
    assert row["value"]["reason"] == "cleanup"
    assert row["value"]["actor"] == "op@host"
    assert row["updated_at"] != prior_token
    assert audit["new_token"] == row["updated_at"]
    assert audit["prior_token"] == prior_token


def test_acquire_refuses_when_absent():
    sb = FakeSupabase()
    with pytest.raises(RuntimeError, match="ABSENT"):
        maint.acquire(sb, reason="x", actor="op")


def test_acquire_refuses_when_already_active():
    sb = _seed()
    maint.acquire(sb, reason="first", actor="op")
    with pytest.raises(RuntimeError, match="not inactive"):
        maint.acquire(sb, reason="second", actor="op")
    # still exactly one active lock, owned by the first acquirer
    assert sb.row()["value"]["active"] is True


def test_acquire_refuses_when_value_malformed():
    sb = FakeSupabase([{"key": LOCK_KEY, "value": {}, "updated_at": "t0"}])
    with pytest.raises(RuntimeError, match="not inactive"):
        maint.acquire(sb, reason="x", actor="op")
    assert sb.row()["value"] == {}  # untouched


# ---------------------------------------------------------------------------
# CAS atomicity — concurrent acquire + stale token
# ---------------------------------------------------------------------------

def test_concurrent_acquire_single_winner():
    sb = _seed()
    # Racer B captures the token BEFORE anyone commits.
    stale_token = sb.row()["updated_at"]

    # Racer A acquires via the full path and wins.
    audit_a = maint.acquire(sb, reason="A", actor="A")
    assert audit_a["row_count"] == 1
    assert sb.row()["value"]["active"] is True

    # Racer B fires its conditional CAS on the SAME stale token. The row now
    # has active='true' AND a rewritten updated_at, so B matches ZERO rows.
    loser = maint._cas_acquire(
        sb,
        prior_token=stale_token,
        window_id="B",
        reason="B",
        actor="B",
        opened_at="B-open",
        new_token="B-token",
    )
    assert loser == []
    # B never overwrote A's lock.
    row = sb.row()
    assert row["value"]["window_id"] == audit_a["window_id"]
    assert row["updated_at"] == audit_a["new_token"]


def test_acquire_cas_stale_token_matches_zero_rows():
    sb = _seed()
    # Inactive row present, but the CAS token does not match updated_at.
    loser = maint._cas_acquire(
        sb,
        prior_token="does-not-match",
        window_id="W",
        reason="x",
        actor="op",
        opened_at="o",
        new_token="n",
    )
    assert loser == []
    assert sb.row()["value"]["active"] is False  # left inactive, untouched


# ---------------------------------------------------------------------------
# release — window_id scoped
# ---------------------------------------------------------------------------

def test_release_wrong_window_id_errors_and_keeps_lock():
    sb = _seed()
    audit = maint.acquire(sb, reason="cleanup", actor="op")
    with pytest.raises(RuntimeError, match="not held"):
        maint.release(sb, window_id="not-the-owner", actor="op")
    row = sb.row()
    assert row["value"]["active"] is True
    assert row["value"]["window_id"] == audit["window_id"]


def test_acquire_release_round_trip_flips_active():
    sb = _seed()
    seed_token = sb.row()["updated_at"]

    acq = maint.acquire(sb, reason="cleanup", actor="op")
    active_token = sb.row()["updated_at"]
    assert sb.row()["value"]["active"] is True
    assert active_token != seed_token

    rel = maint.release(sb, window_id=acq["window_id"], actor="op")
    row = sb.row()
    assert row["value"] == {"active": False}
    assert rel["row_count"] == 1
    assert row["updated_at"] != active_token  # fresh token stamped on release
    assert row["updated_at"] == rel["new_token"]

    # A released lock can be re-acquired with a brand-new window.
    acq2 = maint.acquire(sb, reason="again", actor="op")
    assert acq2["window_id"] != acq["window_id"]
    assert sb.row()["value"]["active"] is True
