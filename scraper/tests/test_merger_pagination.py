"""Round G / LANE G3 regressions — merger pagination + id-batched fetch.

Defect (fail-before): scraper/merger.py read every active-event input with a
single unpaginated ``.execute()``, so Supabase silently capped each scan at
1000 rows and Passes 0–5 never saw later events. Pass 4 additionally fetched
all parent rows with one un-chunked ``.in_(parent_ids)`` (caps at 1000 ids).

G3 adds:
  * ``merger._fetch_all_rows`` — paginate past the 1000-row cap (mirrors the G2
    ``backfill_location_prefectures.fetch_all_rows`` contract: per-page /
    exact-count / accumulated logging, filters applied to count + every page).
  * ``merger._fetch_by_ids`` — chunk an id list so an ``.in_()`` lookup never
    caps at 1000.
  * Every active-event scan in ``run_merger`` (Passes 0–5) + the orphan /
    grandchild scans route through ``_fetch_all_rows``.

Run:
    python -m pytest scraper/tests/test_merger_pagination.py -q
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import merger


# ---------------------------------------------------------------------------
# In-memory Supabase test double (read-only; enough for merger SELECT chains)
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


def _is_null_arg(v) -> bool:
    return v is None or v == "null"


class _FakeQuery:
    """Minimal PostgREST-style builder over an in-memory list of dict rows."""

    def __init__(self, rows):
        self._rows = rows
        self._preds = []
        self._negate_next_is = False
        self._count = None
        self._head = False
        self._order_col = None
        self._order_desc = False
        self._start = None
        self._end = None

    def select(self, *_cols, count=None, head=None):
        self._count = count
        self._head = bool(head)
        return self

    @property
    def not_(self):
        self._negate_next_is = True
        return self

    def is_(self, col, val):
        want_null = _is_null_arg(val)
        neg = self._negate_next_is
        self._negate_next_is = False

        def pred(r):
            v = r.get(col)
            res = (v is None) if want_null else (v == val)
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
        vs = set(vals)
        self._preds.append(lambda r: r.get(col) in vs)
        return self

    def contains(self, col, vals):
        def pred(r):
            cur = r.get(col) or []
            return all(v in cur for v in vals)

        self._preds.append(pred)
        return self

    def order(self, col, desc=False):
        self._order_col = col
        self._order_desc = desc
        return self

    def range(self, start, end, foreign_table=None):
        self._start = start
        self._end = end
        return self

    def _filtered(self):
        data = [r for r in self._rows if all(p(r) for p in self._preds)]
        if self._order_col:
            data = sorted(
                data,
                key=lambda r: (r.get(self._order_col) is None, r.get(self._order_col)),
                reverse=self._order_desc,
            )
        return data

    def execute(self):
        data = self._filtered()
        count = len(data) if self._count == "exact" else None
        if self._head:
            return _FakeResp([], count=count)
        if self._start is not None:
            data = data[self._start : self._end + 1]
        else:
            data = data[:1000]  # emulate PostgREST default max-rows cap
        return _FakeResp(list(data), count=count)


class _FakeClient:
    def __init__(self, rows_by_table):
        self._rows_by_table = rows_by_table

    def table(self, name):
        return _FakeQuery(list(self._rows_by_table.get(name, [])))


# ---------------------------------------------------------------------------
# _fetch_all_rows — paginate past the 1000-row cap
# ---------------------------------------------------------------------------

def test_fetch_all_rows_paginates_past_1000():
    rows = [{"id": f"id-{i:05d}", "name_ja": "x"} for i in range(2350)]
    sb = _FakeClient({"events": rows})

    got = merger._fetch_all_rows(sb, "events", "id,name_ja", label="t")

    assert len(got) == 2350
    assert got[0]["id"] == "id-00000"
    assert got[-1]["id"] == "id-02349"
    assert len({r["id"] for r in got}) == 2350  # no dropped / duplicated pages


def test_fetch_all_rows_applies_filters_to_count_and_pages():
    rows = [
        {"id": f"id-{i:05d}", "is_active": (i % 2 == 0), "name_ja": "x"}
        for i in range(3000)
    ]
    sb = _FakeClient({"events": rows})

    got = merger._fetch_all_rows(
        sb,
        "events",
        "id,name_ja",
        apply_filters=lambda q: q.eq("is_active", True),
        label="active",
    )

    assert len(got) == 1500  # only the active half, still well past 1000
    assert all(r["is_active"] for r in got)


# ---------------------------------------------------------------------------
# _fetch_by_ids — chunk an id list so .in_() never caps at 1000
# ---------------------------------------------------------------------------

def test_fetch_by_ids_chunks_past_1000():
    rows = [{"id": f"id-{i:05d}", "parent_event_id": None} for i in range(1500)]
    sb = _FakeClient({"events": rows})
    ids = [r["id"] for r in rows]

    got = merger._fetch_by_ids(sb, "events", ids, "id,parent_event_id", label="parents")

    assert len(got) == 1500
    assert len({r["id"] for r in got}) == 1500


def test_fetch_by_ids_dedups_input_ids():
    rows = [{"id": "a"}, {"id": "b"}]
    sb = _FakeClient({"events": rows})

    got = merger._fetch_by_ids(sb, "events", ["a", "a", "b", "a"], "id")

    assert sorted(r["id"] for r in got) == ["a", "b"]


# ---------------------------------------------------------------------------
# run_merger routes EVERY active-event scan through the paginating helper
# ---------------------------------------------------------------------------

def test_run_merger_routes_every_scan_through_pagination(monkeypatch):
    seen_labels: list[str] = []

    def _spy(sb, table, columns, *, apply_filters=None, order_col="id",
             page_size=1000, label=""):
        seen_labels.append(label)
        return []

    monkeypatch.setattr(merger, "_fetch_all_rows", _spy)
    monkeypatch.setattr("database._get_client", lambda: _FakeClient({}))

    total = merger.run_merger(dry_run=True)

    assert total == 0
    # Passes 0–5 active-event inputs + orphan (Pass 3) + grandchild (Pass 4)
    # scans must all be paginated.
    for label in ("pass0_gnews", "pass1_2_events", "pass3_orphan_subs", "pass4_subs"):
        assert label in seen_labels, f"scan '{label}' did not use _fetch_all_rows"


def test_run_merger_loads_all_events_beyond_1000(monkeypatch, caplog):
    base = date(2026, 1, 1)
    rows = [
        {
            "id": f"ev-{i:05d}",
            "source_name": "peatix",
            "source_id": f"peatix-{i}",
            "source_url": f"https://peatix.com/e/{i}",
            "name_ja": f"活動{i}",
            "start_date": (base + timedelta(days=i)).isoformat(),
            "category": ["art"],
            "event_form": ["exhibition"],
        }
        for i in range(1500)
    ]
    sb = _FakeClient({"events": rows})
    monkeypatch.setattr("database._get_client", lambda: sb)

    with caplog.at_level(logging.INFO, logger="merger"):
        total = merger.run_merger(dry_run=True)

    assert total == 0  # unique names + unique dates → nothing merges
    # The shared Pass 1/2 scan loaded every row, not just the first 1000.
    assert "loaded 1500 active events" in caplog.text
