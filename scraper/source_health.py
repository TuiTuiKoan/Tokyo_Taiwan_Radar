"""Source health judged by output volume, not by run success (#319).

A run that raises nothing counts as "success" even when it produced nothing:
researcher.py reported 100% success for two months after its model was
retired. So health here is about events_processed.

- silent: ran in each of the last STREAK_WEEKS weeks and produced 0 events.
  Many are legitimate (a cinema with no Taiwan film this month).
- newly_silent: silent sources that did produce events in the LOOKBACK_WEEKS
  before the streak. These are the likely breakages and the ones to alert on.

Home-IP sources (#407) run weekly from a Mac via launchd, outside GitHub
Actions, so nothing else notices when the Mac is off or the job fails.
home_ip_stale() flags them by the age of their last successful run.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from db_paging import fetch_all

WEEK = timedelta(days=7)
STREAK_WEEKS = 2
LOOKBACK_WEEKS = 6

# Blocked from GitHub Actions IPs (#378); main.HOME_IP_ONLY_SOURCES must match
# (tests/test_source_health.py checks it).
HOME_IP_ONLY_SOURCES = frozenset({"mot", "taipei_fukuoka", "jposa_ja"})
# The job runs weekly; a day of slack covers a Mac that wakes late on Monday.
HOME_IP_MAX_AGE = timedelta(days=8)
HOME_IP_LOOKBACK = timedelta(days=30)

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


def fetch_home_ip_runs(sb, now: datetime, sources=HOME_IP_ONLY_SOURCES) -> list[dict]:
    return fetch_all(lambda: (
        sb.table("scraper_runs")
        .select("source,success,ran_at")
        .in_("source", sorted(sources))
        .gte("ran_at", (now - HOME_IP_LOOKBACK).isoformat())
        .order("id")
    ))


def home_ip_stale(
    runs: list[dict],
    now: datetime,
    *,
    sources=HOME_IP_ONLY_SOURCES,
    max_age: timedelta = HOME_IP_MAX_AGE,
) -> dict[str, dict]:
    """Home-IP sources that need attention: {source: {"reason", "last_success"}}.

    - failed: the latest run failed after the last success (or there was never one)
    - stale: the last success is older than max_age
    - missing: no run at all within HOME_IP_LOOKBACK
    """
    latest: dict[str, tuple[datetime, bool]] = {}
    last_success: dict[str, datetime] = {}
    for r in runs:
        name = r.get("source")
        if name not in sources:
            continue
        ran_at = datetime.fromisoformat(r["ran_at"])
        ok = bool(r.get("success", True))
        if name not in latest or ran_at > latest[name][0]:
            latest[name] = (ran_at, ok)
        if ok and (name not in last_success or ran_at > last_success[name]):
            last_success[name] = ran_at

    out: dict[str, dict] = {}
    for name in sorted(sources):
        success_at = last_success.get(name)
        info = {"last_success": success_at.isoformat() if success_at else None}
        if name not in latest:
            out[name] = {"reason": "missing", **info}
        elif not latest[name][1]:
            out[name] = {"reason": "failed", **info}
        elif now - success_at > max_age:
            out[name] = {"reason": "stale", **info}
    return out
