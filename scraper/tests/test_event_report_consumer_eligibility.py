"""Writer-safety eligibility matrix for every recurring event_reports consumer.

Asserts the checked-in consumer matrix in auto_qa.py: automated writers
(reconcile, qa_auto_fix, qa_heartbeat, refetch_thin_events) classify a
`report_types[]` array by TOKEN IDENTITY + membership in the known Auto-QA set,
never by list length alone. A payload token (`field:` / `fieldEdit:` /
`selectionReason:`) or any manual/unknown/human type anywhere in the array
disqualifies the whole row from every automatic write.

Every assertion here fails against the pre-H0 behaviour (report_types[0]-only
checks, `.contains` fan-out without an exact single-type gate, no pending CAS,
no sb-aware FC sentinel) and passes with the H0 code.
"""
from __future__ import annotations

import sys

import pytest

from auto_qa import (
    QA_TYPES,
    _check_performer_multi_value,
    _resolve_report_disposition,
    all_known_auto_types,
    classify_report_types,
    close_report_exactly_one,
    is_known_auto_type,
    is_payload_token,
    single_auto_type,
)

# Concrete tokens used across the matrix -----------------------------------
AUTO_A = "auto_qa_missing_address"
AUTO_B = "auto_qa_missing_title"
THIN = "auto_qa_thin_content"
SIMP = "auto_qa_simplified_zh"
SIMP2 = "auto_simplified_chinese"
PERFORMER_MULTI = "auto_qa_performer_multi_value_pollution"
LOCATION_URL = "auto_qa_location_url_is_event_url"
HUMAN = "wrongCategory"
UNKNOWN = "mystery_type"
PAYLOAD_TOKENS = ("field:price_info", "fieldEdit:name_ja", "selectionReason:foo")


# ---------------------------------------------------------------------------
# Minimal in-memory Supabase double — supports only the query-builder methods
# the H0 consumers actually call. No network.
# ---------------------------------------------------------------------------
class _Result:
    def __init__(self, data):
        self.data = data


class _Not:
    def __init__(self, query):
        self._q = query

    def is_(self, col, _val):
        self._q._rows = [r for r in self._q._rows if r.get(col) is not None]
        return self._q


class _Query:
    def __init__(self, db, table):
        self._db = db
        self._table = table
        self._rows = list(db.tables.get(table, []))
        self._single = False
        self._update = None

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def neq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) != val]
        return self

    def gte(self, col, val):
        self._rows = [r for r in self._rows if (r.get(col) or "") >= val]
        return self

    def contains(self, col, vals):
        want = set(vals)
        self._rows = [r for r in self._rows if want <= set(r.get(col) or [])]
        return self

    def ov(self, col, vals):
        want = set(vals)
        self._rows = [r for r in self._rows if want & set(r.get(col) or [])]
        return self

    def in_(self, col, vals):
        self._db.in_calls.append((self._table, col, list(vals)))
        want = set(vals)
        self._rows = [r for r in self._rows if r.get(col) in want]
        return self

    @property
    def not_(self):
        return _Not(self)

    def is_(self, col, _val):
        self._rows = [r for r in self._rows if r.get(col) is None]
        return self

    def order(self, col, desc=False):
        self._rows.sort(key=lambda r: r.get(col) or "", reverse=desc)
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def range(self, a, b):
        self._rows = self._rows[a : b + 1]
        return self

    def single(self):
        self._single = True
        return self

    def update(self, patch):
        self._update = patch
        return self

    def execute(self):
        if self._update is not None:
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
        # store real dict refs so update()-CAS mutations persist across queries
        self.tables = {name: list(rows) for name, rows in tables.items()}
        self.in_calls: list[tuple] = []

    def table(self, name):
        return _Query(self, name)


# ---------------------------------------------------------------------------
# 1. Pure token-prefix classification matrix
# ---------------------------------------------------------------------------
def test_classify_report_types_matrix():
    assert classify_report_types([AUTO_A]) == "single_auto"
    assert classify_report_types([AUTO_A, AUTO_B]) == "compound_auto"
    # reordered all-auto is still compound_auto (order independent)
    assert classify_report_types([AUTO_B, AUTO_A]) == "compound_auto"
    # auto + human, both orders → manual
    assert classify_report_types([AUTO_A, HUMAN]) == "manual"
    assert classify_report_types([HUMAN, AUTO_A]) == "manual"
    # any payload token anywhere → manual
    for pt in PAYLOAD_TOKENS:
        assert classify_report_types([pt]) == "manual"
        assert classify_report_types([AUTO_A, pt]) == "manual"
        assert classify_report_types([pt, AUTO_A]) == "manual"
    assert classify_report_types([UNKNOWN]) == "manual"
    # empty / non-usable tokens
    assert classify_report_types([]) == "empty"
    assert classify_report_types(None) == "empty"
    assert classify_report_types([""]) == "empty"
    assert classify_report_types([None]) == "empty"
    # empty/None tokens are stripped before length is judged
    assert classify_report_types([AUTO_A, ""]) == "single_auto"
    assert classify_report_types([AUTO_A, None]) == "single_auto"


def test_single_auto_type_matrix():
    assert single_auto_type([AUTO_A]) == AUTO_A
    assert single_auto_type([AUTO_A, ""]) == AUTO_A  # padding stripped
    assert single_auto_type([AUTO_A, AUTO_B]) is None  # compound
    assert single_auto_type([AUTO_A, HUMAN]) is None
    assert single_auto_type([HUMAN, AUTO_A]) is None
    for pt in PAYLOAD_TOKENS:
        assert single_auto_type([pt]) is None
        assert single_auto_type([AUTO_A, pt]) is None
    assert single_auto_type([UNKNOWN]) is None
    assert single_auto_type([]) is None
    assert single_auto_type(None) is None


def test_all_known_auto_types_matrix():
    assert all_known_auto_types([AUTO_A]) == [AUTO_A]
    assert all_known_auto_types([AUTO_A, AUTO_B]) == [AUTO_A, AUTO_B]
    # order is preserved, not sorted
    assert all_known_auto_types([AUTO_B, AUTO_A]) == [AUTO_B, AUTO_A]
    # padding stripped but real tokens kept
    assert all_known_auto_types([AUTO_A, ""]) == [AUTO_A]
    # any non-auto token disqualifies the whole row
    assert all_known_auto_types([AUTO_A, HUMAN]) is None
    assert all_known_auto_types([HUMAN, AUTO_A]) is None
    for pt in PAYLOAD_TOKENS:
        assert all_known_auto_types([AUTO_A, pt]) is None
    assert all_known_auto_types([UNKNOWN]) is None
    assert all_known_auto_types([]) is None
    assert all_known_auto_types(None) is None


def test_is_payload_token_and_is_known_auto_type():
    for pt in PAYLOAD_TOKENS:
        assert is_payload_token(pt) is True
        assert is_known_auto_type(pt) is False
    for auto in QA_TYPES:
        assert is_known_auto_type(auto) is True
        assert is_payload_token(auto) is False
    assert is_payload_token(HUMAN) is False
    assert is_payload_token("") is False
    assert is_payload_token(None) is False  # non-str guard
    assert is_known_auto_type(HUMAN) is False
    assert is_known_auto_type(UNKNOWN) is False
    assert is_known_auto_type("") is False
    assert is_known_auto_type(None) is False


# ---------------------------------------------------------------------------
# 2. Per-consumer eligibility gates (real consumer functions, fake client)
# ---------------------------------------------------------------------------
_ELIGIBILITY_ROWS = [
    {"id": "s1", "event_id": "e1", "report_types": [SIMP], "status": "pending",
     "created_at": "2024-01-01T00:00:00Z", "admin_notes": None},
    {"id": "s2", "event_id": "e2", "report_types": [SIMP2], "status": "pending",
     "created_at": "2024-01-02T00:00:00Z", "admin_notes": None},
    {"id": "h1", "event_id": "e3", "report_types": [PERFORMER_MULTI], "status": "pending",
     "created_at": "2024-01-03T00:00:00Z", "admin_notes": None},
    {"id": "h2", "event_id": "e4", "report_types": [LOCATION_URL], "status": "pending",
     "created_at": "2024-01-04T00:00:00Z", "admin_notes": None},
    # compound all-auto → excluded by single_auto_type gate
    {"id": "c1", "event_id": "e5", "report_types": [SIMP, AUTO_B], "status": "pending",
     "created_at": "2024-01-05T00:00:00Z", "admin_notes": None},
    # payload token alongside an auto type → excluded
    {"id": "p1", "event_id": "e6", "report_types": [SIMP, "field:name_zh"], "status": "pending",
     "created_at": "2024-01-06T00:00:00Z", "admin_notes": None},
    # manual/human → excluded
    {"id": "m1", "event_id": "e7", "report_types": [HUMAN], "status": "pending",
     "created_at": "2024-01-07T00:00:00Z", "admin_notes": None},
    # eligible single type but already resolved (non-pending) → excluded by status CAS
    {"id": "x1", "event_id": "e8", "report_types": [SIMP], "status": "confirmed",
     "created_at": "2024-01-08T00:00:00Z", "admin_notes": None},
]


def test_qa_auto_fix_pending_simplified_reports_single_type_only():
    from qa_auto_fix import _pending_simplified_reports

    sb = FakeSupabase({"event_reports": _ELIGIBILITY_ROWS})
    out = _pending_simplified_reports(sb)
    ids = {row["id"] for row in out}
    # only the two single-type simplified rows that are still pending
    assert ids == {"s1", "s2"}
    # compound / payload / manual / non-pending never leak through
    assert "c1" not in ids and "p1" not in ids
    assert "m1" not in ids and "x1" not in ids


def test_qa_heartbeat_fetch_pending_reports_single_type_only():
    from qa_heartbeat import _fetch_pending_reports

    sb = FakeSupabase({"event_reports": _ELIGIBILITY_ROWS})
    out = _fetch_pending_reports(sb, limit=50)
    ids = {row["id"] for row in out}
    # every SAFE single-type pending row qualifies (simplified + heartbeat types)
    assert {"s1", "s2", "h1", "h2"} <= ids
    # compound / payload / manual / non-pending are rejected
    assert "c1" not in ids and "p1" not in ids
    assert "m1" not in ids and "x1" not in ids


def test_refetch_thin_events_exact_single_type_gate(monkeypatch):
    pytest.importorskip("playwright.sync_api")
    import refetch_thin_events

    reports = [
        {"id": "t1", "event_id": "te1", "report_types": [THIN],
         "status": "pending", "admin_notes": None},
        # compound: thin + a second unresolved finding → excluded (exact-match)
        {"id": "tc", "event_id": "te2", "report_types": [THIN, "auto_qa_missing_date"],
         "status": "pending", "admin_notes": None},
        # payload token alongside thin → excluded
        {"id": "tp", "event_id": "te3", "report_types": [THIN, "field:raw_description"],
         "status": "pending", "admin_notes": None},
    ]
    events = [
        {"id": "te1", "source_name": "fixture_source", "source_url": "https://example.test/1",
         "raw_description": "short", "is_active": True, "annotation_status": "pending"},
        {"id": "te2", "source_name": "fixture_source", "source_url": "https://example.test/2",
         "raw_description": "short", "is_active": True, "annotation_status": "pending"},
        {"id": "te3", "source_name": "fixture_source", "source_url": "https://example.test/3",
         "raw_description": "short", "is_active": True, "annotation_status": "pending"},
    ]
    sb = FakeSupabase({"event_reports": reports, "events": events})
    monkeypatch.setattr(refetch_thin_events, "_supabase_client", lambda: sb)
    monkeypatch.setattr(sys, "argv", ["refetch_thin_events.py", "--dry-run", "--limit", "20"])

    refetch_thin_events.main()

    # The events batch fetch reflects exactly which reports passed the gate.
    events_id_queries = [ids for (table, col, ids) in sb.in_calls if table == "events" and col == "id"]
    assert events_id_queries, "events were never queried — gate rejected everything"
    assert events_id_queries[-1] == ["te1"]  # compound + payload excluded


# ---------------------------------------------------------------------------
# 3. reconcile disposition — all-auto compound vs single, deleted / inactive /
#    reviewed / missing events
# ---------------------------------------------------------------------------
def _base_event(**overrides):
    event = {
        "id": "ev-1",
        "source_name": "fixture_source",
        "name_ja": "書籍イベント",
        "raw_title": "書籍イベント",
        "category": ["books_media"],
        "event_form": ["lecture"],
        "location_name": "丸善丸の内本店",
        "location_address": "東京都千代田区1-1",
        "location_prefectures": ["東京都"],
        "raw_description": "開場 19:00 / 参加費 1500円",
        "organizer": "出版社A",
        "official_url": "https://example.test/event",
        "created_at": "2024-01-10T00:00:00+00:00",
        "is_active": True,
        "annotation_status": "annotated",
    }
    event.update(overrides)
    return event


def test_single_type_dismisses_deleted_and_inactive():
    assert _resolve_report_disposition(None, [AUTO_A])[0] == "dismiss"
    assert _resolve_report_disposition(_base_event(is_active=False), [AUTO_A])[0] == "dismiss"


def test_single_type_reviewed_event_runs_predicate_no_shortcut():
    # reviewed + issue resolved → confirm; reviewed + issue still fires → keep
    resolved = _base_event(annotation_status="reviewed", location_address="東京都千代田区1-1")
    assert _resolve_report_disposition(resolved, [AUTO_A]) == ("confirm", "issue resolved")
    still_missing = _base_event(annotation_status="reviewed", location_address="")
    assert _resolve_report_disposition(still_missing, [AUTO_A]) == ("keep", "predicate still fires")


def test_compound_never_dismisses_missing_or_inactive_event():
    types = [AUTO_B, "auto_qa_missing_organizer"]
    # deleted event → keep (never dismissed, cannot verify every type)
    assert _resolve_report_disposition(None, types)[0] == "keep"
    # inactive event with a still-firing type → keep (never dismissed like single)
    inactive_one_fires = _base_event(is_active=False, organizer=None)
    assert _resolve_report_disposition(inactive_one_fires, types)[0] == "keep"


def test_compound_confirms_only_when_every_type_resolves():
    types = [AUTO_B, "auto_qa_missing_organizer"]
    # both resolved (title present, organizer present) → confirm
    all_resolved = _base_event()
    assert _resolve_report_disposition(all_resolved, types) == (
        "confirm", "compound: every type resolved")
    # one type still fires (organizer null) → keep the whole row pending
    one_fires = _base_event(organizer=None)
    assert _resolve_report_disposition(one_fires, types) == (
        "keep", "compound: a type still fires")


def test_compound_reviewed_event_has_no_shortcut():
    types = [AUTO_B, "auto_qa_missing_organizer"]
    reviewed_resolved = _base_event(annotation_status="reviewed")
    assert _resolve_report_disposition(reviewed_resolved, types)[0] == "confirm"
    reviewed_one_fires = _base_event(annotation_status="reviewed", organizer=None)
    assert _resolve_report_disposition(reviewed_one_fires, types)[0] == "keep"


# ---------------------------------------------------------------------------
# 4. Reviewed-event FC fixtures — the sb-aware performer sentinel gate
# ---------------------------------------------------------------------------
def _fc_client(rows):
    return FakeSupabase({"field_corrections": rows})


def test_performer_no_fc_row_is_eligible_and_fires():
    ev = {"id": "ev-1", "performer": "王小明、李小華", "source_name": "cinema"}
    sb = _fc_client([])  # no correction on record
    note = _check_performer_multi_value(ev, sb=sb)
    assert note is not None  # unresolved → row remains actionable


def test_performer_empty_string_fc_is_intentional_empty_and_skips():
    ev = {"id": "ev-1", "performer": "王小明、李小華", "source_name": "cinema"}
    sb = _fc_client([
        {"event_id": "ev-1", "field_name": "performer", "corrected_value": ""},
    ])
    # empty-string FC is the lock-empty sentinel → treated as resolved, skip
    assert _check_performer_multi_value(ev, sb=sb) is None


def test_performer_nonempty_fc_with_clean_field_is_protected():
    # admin corrected the field to a clean single value → no separators remain
    ev = {"id": "ev-1", "performer": "王小明", "source_name": "cinema"}
    sb = _fc_client([
        {"event_id": "ev-1", "field_name": "performer", "corrected_value": "王小明"},
    ])
    assert _check_performer_multi_value(ev, sb=sb) is None


def test_performer_nonempty_fc_but_field_still_polluted_stays_manual():
    # a non-empty FC that is NOT the empty sentinel must not silently resolve a
    # field that is still polluted — the predicate keeps firing (manual review)
    ev = {"id": "ev-1", "performer": "王小明、李小華", "source_name": "cinema"}
    sb = _fc_client([
        {"event_id": "ev-1", "field_name": "performer", "corrected_value": "unrelated"},
    ])
    assert _check_performer_multi_value(ev, sb=sb) is not None


def test_performer_sentinel_skipped_when_sb_is_none():
    # sb=None path: caller pre-filters sentinels, so the predicate still fires
    ev = {"id": "ev-1", "performer": "王小明、李小華", "source_name": "cinema"}
    assert _check_performer_multi_value(ev, sb=None) is not None


# ---------------------------------------------------------------------------
# 5. close_report_exactly_one — pending CAS + exactly-one-row semantics
# ---------------------------------------------------------------------------
def _reports_client():
    return FakeSupabase({"event_reports": [
        {"id": "r1", "event_id": "e1", "status": "pending", "admin_notes": None},
        {"id": "r2", "event_id": "e2", "status": "pending", "admin_notes": None},
    ]})


def test_close_report_exactly_one_dry_run_is_no_write():
    sb = _reports_client()
    assert close_report_exactly_one(sb, "r1", status="confirmed", dry_run=True) == (True, 1)
    # dry-run must not mutate the row
    row = sb.table("event_reports").select("*").eq("id", "r1").single().execute().data
    assert row["status"] == "pending"


def test_close_report_exactly_one_rejects_bad_status():
    sb = _reports_client()
    with pytest.raises(ValueError):
        close_report_exactly_one(sb, "r1", status="pending")
    with pytest.raises(ValueError):
        close_report_exactly_one(sb, "r1", status="deleted")


def test_close_report_exactly_one_guards_empty_and_non_str_id():
    sb = _reports_client()
    assert close_report_exactly_one(sb, "", status="confirmed") == (False, 0)
    assert close_report_exactly_one(sb, None, status="confirmed") == (False, 0)  # type: ignore[arg-type]


def test_close_report_exactly_one_confirms_one_pending_row_then_is_idempotent():
    sb = _reports_client()
    ok, n = close_report_exactly_one(sb, "r1", status="confirmed", note="done")
    assert (ok, n) == (True, 1)
    row = sb.table("event_reports").select("*").eq("id", "r1").single().execute().data
    assert row["status"] == "confirmed" and row["admin_notes"] == "done"
    # second call finds no pending row → safe no-op (idempotent)
    assert close_report_exactly_one(sb, "r1", status="confirmed") == (False, 0)


def test_close_report_exactly_one_supports_dismiss():
    sb = _reports_client()
    assert close_report_exactly_one(sb, "r2", status="dismissed") == (True, 1)
    row = sb.table("event_reports").select("*").eq("id", "r2").single().execute().data
    assert row["status"] == "dismissed"
