"""Source health judged by output volume, not by run success (#319).

A run that raises nothing counts as "success" even when it produced nothing:
researcher.py reported 100% success for two months after its model was
retired. So health here is about events_processed.

- silent: ran in each of the last STREAK_WEEKS weeks and produced 0 events.
  Many are legitimate (a cinema with no Taiwan film this month).
- newly_silent: silent sources that did produce events in the LOOKBACK_WEEKS
  before the streak. These are the likely breakages and the ones to alert on.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from db_paging import fetch_all

WEEK = timedelta(days=7)
STREAK_WEEKS = 2
LOOKBACK_WEEKS = 6

# scraper_runs rows that are not event sources.
_NON_SOURCES = frozenset({"annotator"})


def _is_event_source(name: str) -> bool:
    return bool(name) and name not in _NON_SOURCES and "/" not in name


def fetch_runs(sb, start: datetime, end: datetime) -> list[dict]:
    return fetch_all(lambda: (
        sb.table("scraper_runs")
        .select("source,events_processed,ran_at")
        .gte("ran_at", start.isoformat())
        .lt("ran_at", end.isoformat())
        .order("id")
    ))


def zero_output(
    runs: list[dict],
    window_end: datetime,
    *,
    streak_weeks: int = STREAK_WEEKS,
    lookback_weeks: int = LOOKBACK_WEEKS,
) -> dict[str, list[str]]:
    """Classify sources from scraper_runs rows ending at window_end (exclusive)."""
    streak_start = window_end - streak_weeks * WEEK
    lookback_start = streak_start - lookback_weeks * WEEK
    # source -> week index (0 = most recent) -> [runs, events]
    weeks: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    earlier_events: dict[str, int] = defaultdict(int)

    for r in runs:
        name = r.get("source") or ""
        if not _is_event_source(name):
            continue
        ran_at = datetime.fromisoformat(r["ran_at"])
        events = r.get("events_processed") or 0
        if streak_start <= ran_at < window_end:
            cell = weeks[name][int((window_end - ran_at) / WEEK)]
            cell[0] += 1
            cell[1] += events
        elif lookback_start <= ran_at < streak_start:
            earlier_events[name] += events

    silent = sorted(
        name for name, by_week in weeks.items()
        if all(by_week[w][0] > 0 and by_week[w][1] == 0 for w in range(streak_weeks))
    )
    return {
        "silent": silent,
        "newly_silent": [name for name in silent if earlier_events[name] > 0],
    }


def check(sb, window_end: datetime, **kwargs) -> dict[str, list[str]]:
    streak = kwargs.get("streak_weeks", STREAK_WEEKS)
    lookback = kwargs.get("lookback_weeks", LOOKBACK_WEEKS)
    start = window_end - (streak + lookback) * WEEK
    return zero_output(fetch_runs(sb, start, window_end), window_end, **kwargs)
