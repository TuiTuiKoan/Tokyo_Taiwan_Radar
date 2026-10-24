"""Report cost reads llm_cost_daily, paged past PostgREST's 1000-row cap (#322)."""

from __future__ import annotations

from datetime import date, timedelta

import daily_report
import llm_cost
import quota_monitor


class _Query:
    """Enough of the postgrest builder for llm_cost: filters, ordering and range()."""

    def __init__(self, rows: list[dict], log: list):
        self._rows = rows
        self._filters: list = []
        self._range: tuple[int, int] | None = None
        self._log = log

    def select(self, _cols):
        return self

    def gte(self, col, val):
        self._filters.append(lambda r: r[col] >= val)
        return self

    def lt(self, col, val):
        self._filters.append(lambda r: r[col] < val)
        return self

    def like(self, col, pattern):
        assert pattern.endswith("%") and "%" not in pattern[:-1]
        self._filters.append(lambda r: r[col].startswith(pattern[:-1]))
        return self

    def order(self, *_a, **_k):
        return self

    def range(self, start, end):
        assert self._range is None, "range() applied twice to one builder"
        self._range = (start, end)
        return self

    def execute(self):
        rows = [r for r in self._rows if all(f(r) for f in self._filters)]
        start, end = self._range or (0, len(rows) - 1)
        page = rows[start : min(end + 1, start + 1000)]  # PostgREST caps a page at 1000
        self._log.append(len(page))
        return type("R", (), {"data": page})()


class _DB:
    def __init__(self, rows):
        self.rows = rows
        self.pages: list[int] = []

    def table(self, name):
        assert name == "llm_cost_daily"
        return _Query(self.rows, self.pages)


def _row(day: date, caller: str, cost: float, *, calls=1, errors=0, unpriced=0):
    return {
        "day": day.isoformat(), "caller": caller, "model": "gpt-4o-mini",
        "calls": calls, "errors": errors, "cost_usd": f"{cost:.6f}", "unpriced_calls": unpriced,
    }


def test_window_cost_reads_every_page():
    day = date(2026, 11, 3)
    rows = [_row(day, f"enrich.c{i:04d}", 0.001) for i in range(2500)]
    db = _DB(rows)
    s = llm_cost.window_cost(db, day, day + timedelta(days=1))
    assert db.pages == [1000, 1000, 500]
    assert s["calls"] == 2500
    assert round(s["total"], 6) == 2.5


def test_window_is_end_exclusive_and_groups_by_caller():
    d = date(2026, 11, 3)
    db = _DB([
        _row(d - timedelta(days=1), "annotator.annotate", 9.0),
        _row(d, "annotator.annotate", 0.30),
        _row(d, "enrich.poster", 0.50, unpriced=2),
        _row(d, "annotator.annotate", 0.10),
        _row(d + timedelta(days=1), "enrich.poster", 9.0),
    ])
    s = llm_cost.window_cost(db, d, d + timedelta(days=1))
    assert round(s["total"], 6) == 0.9
    assert list(s["by_caller"]) == ["enrich.poster", "annotator.annotate"]
    assert round(s["by_caller"]["annotator.annotate"], 6) == 0.4
    assert s["unpriced_calls"] == 2


def test_coverage_note_only_before_the_ledger():
    assert llm_cost.coverage_note(llm_cost.LEDGER_START) is None
    assert "2026-10-22" in llm_cost.coverage_note(date(2026, 10, 1))


def test_check_cost_anomalies_flags_by_caller():
    d = date(2026, 12, 3)  # its 30-day window starts after LEDGER_START
    spike = daily_report.COST_SOURCE_SPIKE + 0.25
    db = _DB([
        _row(d, "enrich.poster", spike),
        _row(d, "annotator.annotate", 0.10),
        _row(d - timedelta(days=10), "annotator.annotate", daily_report.COST_MONTH_ALERT),
    ])
    c = daily_report.check_cost_anomalies(db, d, d + timedelta(days=1), d - timedelta(days=29), d + timedelta(days=1))
    assert round(c["today_cost"], 6) == round(spike + 0.10, 6)
    assert c["today_alert"] and c["month_alert"] and c["any_alert"]
    assert c["spike_sources"] == [("enrich.poster", spike)]
    assert c["top3_today"][0][0] == "enrich.poster"
    assert c["ledger_note"] is None


def test_check_cost_anomalies_survives_a_read_failure():
    class Broken:
        def table(self, _name):
            raise RuntimeError("down")

    d = date(2026, 11, 3)
    c = daily_report.check_cost_anomalies(Broken(), d, d + timedelta(days=1), d, d + timedelta(days=1))
    assert c["today_cost"] == 0 and not c["any_alert"]


def _budget_db(today: date):
    return _DB([
        _row(today, "eval.annotator", 0.30),
        _row(today - timedelta(days=6), "eval.annotator.stage3", 0.25),
        _row(today - timedelta(days=7), "eval.annotator", 5.0),   # outside the 7 days
        _row(today, "eval.historical", 5.0),                      # other eval
        _row(today, "annotator.annotate", 5.0),                   # production annotator
    ])


def test_budget_counts_only_the_annotator_eval_over_seven_days():
    today = date(2026, 11, 8)
    assert quota_monitor.check_budget(0.50, sb=_budget_db(today), today=today) == 1  # $0.55
    assert quota_monitor.check_budget(0.60, sb=_budget_db(today), today=today) == 0


def test_budget_passes_through_when_the_read_fails():
    class Broken:
        def table(self, _name):
            raise RuntimeError("down")

    assert quota_monitor.check_budget(0.50, sb=Broken(), today=date(2026, 11, 8)) == 0
