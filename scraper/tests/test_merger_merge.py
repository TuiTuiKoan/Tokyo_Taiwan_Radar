"""Round G / LANE G3 regressions — shared same-work helper, targeted-merge
primitive, and guard preservation.

Fail-before defects:
  * No single ``same_work_eligible`` helper existed; the merger Pass 5 window /
    location check and ``auto_qa._detect_same_work_duplicate`` each open-coded
    the ±14-day rule, so they could drift apart.
  * No ``apply_targeted_merge`` primitive existed; every merge pass inlined the
    two-write (update-primary / deactivate-secondary) sequence, so the manual
    "completeness" contract (reject self-merge, reject inactive primary, reject
    cycle, deactivate + tag ``merged_into_event_id``, repair child links, sync
    works metadata) was unenforced and easy to get wrong.

Guard-preservation (pass before AND after — must never regress):
  * ``_normalize`` trademark / dash / bracket / subtitle / year stripping.
  * ``_similarity`` threshold behaviour.
  * Pass 1 "different work_id never merges" skip.

Run:
    python -m pytest scraper/tests/test_merger_merge.py -q
"""
from __future__ import annotations

import pytest

import merger


# ---------------------------------------------------------------------------
# Write-capable in-memory Supabase double (rows mutated by reference)
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _Query:
    def __init__(self, rows):
        self._rows = rows  # live reference into the store
        self._preds = []
        self._negate_is = False
        self._update = None
        self._count = None
        self._head = False
        self._order = None
        self._desc = False
        self._start = None
        self._end = None

    def select(self, *_cols, count=None, head=None):
        self._count = count
        self._head = bool(head)
        return self

    @property
    def not_(self):
        self._negate_is = True
        return self

    def is_(self, col, val):
        want_null = val is None or val == "null"
        neg = self._negate_is
        self._negate_is = False

        def pred(r):
            res = (r.get(col) is None) if want_null else (r.get(col) == val)
            return (not res) if neg else res

        self._preds.append(pred)
        return self

    def eq(self, col, val):
        self._preds.append(lambda r: r.get(col) == val)
        return self

    def neq(self, col, val):
        self._preds.append(lambda r: r.get(col) != val)
        return self

    def in_(self, col, vals):
        s = set(vals)
        self._preds.append(lambda r: r.get(col) in s)
        return self

    def order(self, col, desc=False):
        self._order = col
        self._desc = desc
        return self

    def range(self, start, end, foreign_table=None):
        self._start = start
        self._end = end
        return self

    def update(self, vals):
        self._update = vals
        return self

    def _match(self):
        return [r for r in self._rows if all(p(r) for p in self._preds)]

    def execute(self):
        rows = self._match()
        if self._update is not None:
            for r in rows:
                r.update(self._update)  # mutate store by reference
            return _Resp(list(rows))
        if self._order:
            rows = sorted(
                rows,
                key=lambda r: (r.get(self._order) is None, r.get(self._order)),
                reverse=self._desc,
            )
        count = len(rows) if self._count == "exact" else None
        if self._head:
            return _Resp([], count=count)
        if self._start is not None:
            rows = rows[self._start : self._end + 1]
        else:
            rows = rows[:1000]  # emulate PostgREST default cap
        return _Resp(list(rows), count=count)


class _Client:
    def __init__(self, rows_by_table):
        self._store = {k: list(v) for k, v in rows_by_table.items()}

    def table(self, name):
        return _Query(self._store.setdefault(name, []))

    def rows(self, name):
        return self._store[name]


# ---------------------------------------------------------------------------
# same_work_eligible — single source of truth
# ---------------------------------------------------------------------------

def test_same_work_helper_shared_by_merger_and_auto_qa():
    import auto_qa

    assert auto_qa.same_work_eligible is merger.same_work_eligible


def test_same_work_eligible_merger_mode_needs_location_overlap():
    fn = merger.same_work_eligible
    # Pass-5 mode: dates within 14d + overlapping venue → eligible.
    assert fn("2026-08-01", "2026-08-10", "渋谷ホール", "渋谷ホール",
              require_location_overlap=True) is True
    # Dates too far apart → never eligible.
    assert fn("2026-08-01", "2026-09-01", "渋谷ホール", "渋谷ホール",
              require_location_overlap=True) is False
    # Same window but no shared location → not eligible in merger mode.
    assert fn("2026-08-01", "2026-08-05", "渋谷ホール", "大阪城ホール",
              require_location_overlap=True) is False


def test_same_work_eligible_detection_mode_ignores_location():
    fn = merger.same_work_eligible
    # Auto-QA detection mode: location not required, but both dates required.
    assert fn("2026-08-01", "2026-08-05", "渋谷", "大阪",
              require_location_overlap=False, require_both_dates=True) is True
    assert fn("2026-08-01", None, "渋谷", "大阪",
              require_location_overlap=False, require_both_dates=True) is False
    assert fn("2026-08-01", "2026-08-20", "渋谷", "大阪",
              require_location_overlap=False, require_both_dates=True) is False


# ---------------------------------------------------------------------------
# Guard preservation (regression — pass before AND after G3)
# ---------------------------------------------------------------------------

def test_normalize_strips_year_bracket_and_subtitle():
    assert merger._normalize("台湾祭2026") == "台湾祭"
    assert merger._normalize("上映会【NPO松本】") == "上映会"
    assert merger._normalize("「台湾祭－台南ランタン祭－」") == "台湾祭"


def test_similarity_threshold_behaviour():
    # Recurring annual event: year-insensitive → identical after normalize.
    assert merger._similarity("台湾祭2026", "台湾祭2025") == pytest.approx(1.0)
    # Genuinely different names stay below the 0.85 merge threshold.
    assert merger._similarity("台湾フェスティバル™TOKYO", "台湾文化祭") < merger._SIMILARITY_THRESHOLD


def _make_pair(work_a, work_b):
    common = dict(
        start_date="2026-08-01",
        category=["art"],
        event_form=["exhibition"],
        name_ja="台湾フェス2026",
        is_active=True,
        location_name=None,
    )
    a = {**common, "id": "ev-a", "source_name": "peatix",
         "source_id": "peatix-a", "source_url": "https://peatix.com/a",
         "work_id": work_a}
    b = {**common, "id": "ev-b", "source_name": "connpass",
         "source_id": "connpass-b", "source_url": "https://connpass.com/b",
         "work_id": work_b}
    return [a, b]


def test_pass1_skips_different_work_id(monkeypatch):
    sb = _Client({"events": _make_pair("W1", "W2")})
    monkeypatch.setattr("database._get_client", lambda: sb)
    # Different creative works with a similar title must never merge.
    assert merger.run_merger(dry_run=True) == 0


def test_pass1_merges_same_work_id(monkeypatch):
    sb = _Client({"events": _make_pair("W1", "W1")})
    monkeypatch.setattr("database._get_client", lambda: sb)
    # Control: identical work_id + cross-source + high name similarity → merges.
    assert merger.run_merger(dry_run=True) == 1


# ---------------------------------------------------------------------------
# apply_targeted_merge — the shared merge primitive
# ---------------------------------------------------------------------------

def test_apply_targeted_merge_rejects_bad_pairs():
    sb = _Client({"events": []})
    active = {"id": "p", "is_active": True}
    with pytest.raises(ValueError):
        merger.apply_targeted_merge(sb, {"id": None}, {"id": "s"},
                                    reason="x", pass_id="merger_pass_1")
    with pytest.raises(ValueError):  # self-merge
        merger.apply_targeted_merge(sb, active, {"id": "p"},
                                    reason="x", pass_id="merger_pass_1")
    with pytest.raises(ValueError):  # inactive primary
        merger.apply_targeted_merge(sb, {"id": "p", "is_active": False},
                                    {"id": "s"}, reason="x", pass_id="merger_pass_1")
    with pytest.raises(ValueError):  # cycle: primary already merged into secondary
        merger.apply_targeted_merge(sb, {"id": "p", "merged_into_event_id": "s"},
                                    {"id": "s"}, reason="x", pass_id="merger_pass_1")


def test_apply_targeted_merge_deactivates_and_reparents():
    rows = [
        {"id": "p", "is_active": True, "secondary_source_urls": None},
        {"id": "s", "is_active": True},
        {"id": "c1", "is_active": True, "parent_event_id": "s"},
        {"id": "c2", "is_active": True, "parent_event_id": "s"},
    ]
    sb = _Client({"events": rows})
    primary = rows[0]
    secondary = rows[1]

    result = merger.apply_targeted_merge(
        sb, primary, secondary,
        primary_update={"secondary_source_urls": ["https://x/s"]},
        reason="merged into p via Pass 1", pass_id="merger_pass_1",
        repair_children=True,
    )

    store = {r["id"]: r for r in sb.rows("events")}
    assert store["s"]["is_active"] is False
    assert store["s"]["merged_into_event_id"] == "p"
    assert store["s"]["deactivated_by_pass"] == "merger_pass_1"
    assert store["c1"]["parent_event_id"] == "p"
    assert store["c2"]["parent_event_id"] == "p"
    assert store["p"]["secondary_source_urls"] == ["https://x/s"]
    assert sorted(result["repaired_children"]) == ["c1", "c2"]
    assert result["deactivated"] is True


def test_apply_targeted_merge_dry_run_writes_nothing():
    rows = [
        {"id": "p", "is_active": True},
        {"id": "s", "is_active": True},
    ]
    sb = _Client({"events": rows})

    result = merger.apply_targeted_merge(
        sb, rows[0], rows[1],
        primary_update={"secondary_source_urls": ["https://x/s"]},
        reason="x", pass_id="merger_pass_1", dry_run=True,
    )

    store = {r["id"]: r for r in sb.rows("events")}
    assert store["s"]["is_active"] is True       # untouched
    assert "merged_into_event_id" not in store["s"]
    assert result["dry_run"] is True
    assert result["deactivated"] is False


def test_apply_targeted_merge_sync_works_copies_metadata():
    rows = [
        {"id": "p", "is_active": True, "work_id": None, "director": None},
        {"id": "s", "is_active": True, "work_id": "W", "director": "D",
         "performer": None},
    ]
    sb = _Client({"events": rows})

    result = merger.apply_targeted_merge(
        sb, rows[0], rows[1],
        reason="film merge", pass_id="merger_pass_1", sync_works=True,
    )

    store = {r["id"]: r for r in sb.rows("events")}
    # Works metadata copied onto the primary event; works table itself untouched.
    assert store["p"]["work_id"] == "W"
    assert store["p"]["director"] == "D"
    assert "works" not in sb._store  # no works-table write
    assert result["synced_fields"] == ["work_id", "director"]
    assert store["s"]["is_active"] is False
