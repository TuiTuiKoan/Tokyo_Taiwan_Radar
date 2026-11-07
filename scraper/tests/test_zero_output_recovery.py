"""Zero-output issue recovery detection (agent-autonomy Phase D1③)."""

from datetime import datetime, timedelta, timezone

from zero_output_recovery import (
    MARKER,
    candidate_issues,
    decide,
    parse_source,
    referencing_prs,
)

NOW = datetime(2026, 11, 8, 2, 0, tzinfo=timezone.utc)  # November in JST


def _issue(n, title, labels=("auto-fix", "scraper"), **extra):
    return {"number": n, "title": title, "state": "open",
            "labels": [{"name": name} for name in labels], **extra}


def _run(days_ago, n, success=True):
    return {"ran_at": (NOW - timedelta(days=days_ago)).isoformat(),
            "events_processed": n, "success": success}


def test_parse_source_accepts_heartbeat_title():
    assert parse_source("whitestone_gallery：28 天以上 0 產出，原因未知") == "whitestone_gallery"


def test_parse_source_rejects_other_titles():
    assert parse_source("agent-autonomy：heartbeat 連不到來源網站，約 30 張「0 產出」") is None  # hyphen
    assert parse_source("prtimes：日期解析錯誤") is None  # not a zero-output issue
    assert parse_source("prtimes: 28 天以上 0 產出") is None  # half-width colon
    assert parse_source(None) is None


def test_candidate_issues_needs_scraper_label_and_skips_prs():
    issues = [
        _issue(512, "whitestone_gallery：28 天以上 0 產出，原因未知"),
        _issue(511, "united_cinemas：28 天以上 0 產出，原因未知", pull_request=None),  # jq map() shape
        _issue(513, "otto：28 天以上 0 產出，原因未知", labels=("auto-fix",)),
        _issue(514, "otto：28 天以上 0 產出，原因未知", pull_request={"url": "x"}),
        _issue(515, "otto：28 天以上 0 產出，原因未知", state="closed"),
    ]
    assert candidate_issues(issues) == {511: "united_cinemas", 512: "whitestone_gallery"}


def test_recovered_source_is_closed_with_report_numbers():
    got = decide({512: "whitestone_gallery"}, {"whitestone_gallery": [_run(40, 0), _run(1, 3)]}, {}, NOW)
    assert [(a["issue"], a["status"]) for a in got] == [(512, "active")]
    assert got[0]["comment"].startswith(MARKER)
    assert "| 1 | 3 | 3 |" in got[0]["comment"]


def test_latest_run_failed_stays_open_even_with_output_this_week():
    # Same rule as the weekly report: a failing latest run is red, not recovered (critique F6).
    runs = {"otto": [_run(3, 4), _run(1, 0, success=False)]}
    assert decide({504: "otto"}, runs, {}, NOW) == []


def test_still_zero_stays_open():
    runs = {"otto": [_run(d, 0) for d in (60, 30, 10, 1)]}
    assert decide({504: "otto"}, runs, {}, NOW) == []
    assert decide({500: "livepocket"}, {}, {}, NOW) == []  # no runs


def test_registered_sporadic_and_seasonal_sources_close_with_reason():
    exp = {
        "kbc_cinema": {"pattern": "sporadic", "max_quiet_days": 180, "note": "很少放台灣片"},
        "oaff": {"pattern": "seasonal", "active_months": [2, 3, 4], "note": "每年 3 月"},
        "tiff": {"pattern": "broken", "issue": 341},
    }
    runs = {k: [_run(90, 2), _run(1, 0)] for k in exp}
    got = decide({462: "kbc_cinema", 400: "oaff", 341: "tiff"}, runs, exp, NOW)
    assert [(a["issue"], a["status"]) for a in got] == [(400, "off_season"), (462, "quiet_expected")]
    assert "很少放台灣片" in got[1]["comment"]


def test_sporadic_quiet_too_long_stays_open():
    exp = {"kbc_cinema": {"pattern": "sporadic", "max_quiet_days": 30}}
    assert decide({462: "kbc_cinema"}, {"kbc_cinema": [_run(90, 2), _run(1, 0)]}, exp, NOW) == []


def test_referencing_prs_are_listed():
    prs = [{"number": 600, "title": "fix", "body": "Closes #512"},
           {"number": 601, "title": "x", "body": "Refs #5120"},
           {"number": 602, "title": "#512 follow-up", "body": None}]
    assert referencing_prs(prs, 512) == [600, 602]
    got = decide({512: "whitestone_gallery"}, {"whitestone_gallery": [_run(1, 3)]}, {}, NOW, prs)
    assert got[0]["prs"] == [600, 602]
    assert "#600、#602" in got[0]["comment"]
