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


def _home(source, days_ago, ok=True):
    return {"source": source, "success": ok, "ran_at": (END - timedelta(days=days_ago)).isoformat()}


def test_home_ip_sources_match_main():
    import main

    assert source_health.HOME_IP_ONLY_SOURCES == main.HOME_IP_ONLY_SOURCES


def test_home_ip_healthy_when_last_success_within_eight_days():
    runs = [_home(s, 3) for s in sorted(source_health.HOME_IP_ONLY_SOURCES)]
    assert source_health.home_ip_stale(runs, END) == {}


def test_home_ip_stale_after_eight_days_without_success():
    runs = [_home("mot", 9), _home("taipei_fukuoka", 8), _home("jposa_ja", 2)]
    result = source_health.home_ip_stale(runs, END)
    assert list(result) == ["mot"]
    assert result["mot"]["reason"] == "stale"
    assert result["mot"]["last_success"] == (END - timedelta(days=9)).isoformat()


def test_home_ip_failed_when_latest_run_failed_even_if_success_is_recent():
    runs = [_home("mot", 5), _home("mot", 1, ok=False)]
    runs += [_home("taipei_fukuoka", 2), _home("jposa_ja", 2)]
    result = source_health.home_ip_stale(runs, END)
    assert result == {"mot": {"reason": "failed", "last_success": (END - timedelta(days=5)).isoformat()}}


def test_home_ip_failed_with_no_success_and_missing_without_runs():
    runs = [_home("mot", 1, ok=False), _home("taipei_fukuoka", 2)]
    result = source_health.home_ip_stale(runs, END)
    assert result["mot"] == {"reason": "failed", "last_success": None}
    assert result["jposa_ja"] == {"reason": "missing", "last_success": None}
    assert "taipei_fukuoka" not in result


def test_home_ip_recovers_after_a_later_success():
    runs = [_home("mot", 12), _home("mot", 6, ok=False), _home("mot", 1)]
    runs += [_home("taipei_fukuoka", 1), _home("jposa_ja", 1)]
    assert source_health.home_ip_stale(runs, END) == {}


def test_home_ip_ignores_other_sources():
    runs = [_home("peatix", 1, ok=False)]
    assert set(source_health.home_ip_stale(runs, END)) == set(source_health.HOME_IP_ONLY_SOURCES)
