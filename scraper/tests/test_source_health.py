from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import db_paging
import source_health

END = datetime(2026, 10, 22, tzinfo=timezone.utc)


def _run(source, days_ago, events):
    return {"source": source, "events_processed": events, "ran_at": (END - timedelta(days=days_ago)).isoformat()}


def test_zero_output_separates_newly_silent_from_long_quiet():
    runs = [
        # broke: produced earlier, nothing in the last two weeks
        _run("broken", 1, 0), _run("broken", 9, 0), _run("broken", 20, 5),
        # long quiet: nothing for the whole lookback
        _run("quiet", 2, 0), _run("quiet", 10, 0), _run("quiet", 30, 0),
        # healthy
        _run("healthy", 1, 3), _run("healthy", 8, 2),
        # produced last week only: not a two-week streak
        _run("recovering", 1, 4), _run("recovering", 10, 0),
        # did not run in the latest week: no evidence either way
        _run("weekly_gap", 10, 0),
        # not event sources
        _run("annotator", 1, 0), _run("annotator", 9, 0),
        _run("researcher/slot1", 1, 0), _run("researcher/slot1", 9, 0),
    ]
    assert source_health.zero_output(runs, END) == {
        "silent": ["broken", "quiet"],
        "newly_silent": ["broken"],
    }


def test_rows_outside_the_window_are_ignored():
    runs = [_run("future", -1, 0), _run("old", 60, 9), _run("old", 1, 0), _run("old", 9, 0)]
    assert source_health.zero_output(runs, END) == {"silent": ["old"], "newly_silent": []}


class _Query:
    def __init__(self, rows, log):
        self.rows, self.log, self.offset = rows, log, None

    def range(self, start, end):
        assert self.offset is None, "a builder must not be paged twice"
        self.offset = start
        self.log.append((start, end))
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows[self.offset:self.offset + 2])


def test_fetch_all_builds_a_fresh_query_per_page():
    rows = [{"id": i} for i in range(5)]
    log = []
    assert db_paging.fetch_all(lambda: _Query(rows, log), page_size=2) == rows
    assert log == [(0, 1), (2, 3), (4, 5)]


def test_fetch_all_stops_on_an_exact_multiple():
    rows = [{"id": i} for i in range(4)]
    log = []
    assert db_paging.fetch_all(lambda: _Query(rows, log), page_size=2) == rows
    assert log == [(0, 1), (2, 3), (4, 5)]
