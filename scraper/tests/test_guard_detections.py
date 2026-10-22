"""Guard detections (#356): query construction against the real PostgREST builder, and trends."""

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from postgrest import SyncPostgrestClient

from guard_detections import (
    DETECTIONS,
    apply_filters,
    load_history,
    run_detections,
    trends,
    write_outputs,
)

NOW = datetime(2026, 10, 22, 3, 0, tzinfo=timezone.utc)


def _params(detection) -> list[tuple[str, str]]:
    """Build the request without sending it and return its query params."""
    client = SyncPostgrestClient("http://localhost:3000")
    query = client.from_(detection["table"]).select("*", count="exact", head=True)
    query = apply_filters(query, detection["filters"], NOW)
    return [(k, v) for k, v in query.request.params.multi_items() if k != "select"]


def _by_id(i):
    return next(d for d in DETECTIONS if d["id"] == i)


def test_detection_ids_are_unique_and_tables_known():
    ids = [d["id"] for d in DETECTIONS]
    assert len(ids) == len(set(ids))
    assert {d["table"] for d in DETECTIONS} <= {"events", "scraper_runs", "research_sources", "event_reports"}


@pytest.mark.parametrize("detection", DETECTIONS, ids=lambda d: d["id"])
def test_every_detection_builds_a_query(detection):
    params = _params(detection)
    assert params, detection["id"]
    for _key, value in params:
        assert "True" not in value and "False" not in value  # booleans go out lowercase


def test_merged_but_active_params():
    assert _params(_by_id("merged_but_active")) == [
        ("merged_into_event_id", "not.is.null"), ("is_active", "eq.true")]


def test_window_and_negation_params():
    params = dict(_params(_by_id("failed_run_without_notes_30d")))
    assert params["success"] == "eq.false" and params["notes"] == "is.null"
    assert params["ran_at"].startswith("gte.2026-09-22")
    report = _params(_by_id("report_prefix_injected"))
    assert ("source_name", "not.in.(google_news_rss,nhk_rss,prtimes,walkerplus,note_creators)") in report
    assert ("raw_title", "not.ilike.*レポ*") in report


def test_or_expression_passes_through():
    params = dict(_params(_by_id("online_with_physical_fields")))
    assert params["or"] == "(venue_id.not.is.null,location_address.not.is.null,location_prefectures.not.is.null)"


class _FailingTable:
    def __init__(self, fail):
        self.fail = fail

    def select(self, *_a, **_k):
        return self

    def filter(self, *_a):
        return self

    def or_(self, *_a):
        return self

    @property
    def not_(self):
        return self

    def execute(self):
        if self.fail:
            raise RuntimeError("column does not exist")
        return SimpleNamespace(count=3)


def test_one_failing_detection_does_not_hide_the_others():
    sb = SimpleNamespace(table=lambda name: _FailingTable(fail=(name == "research_sources")))
    results = run_detections(sb, NOW, DETECTIONS[:2] + [_by_id("implemented_without_scraper_key")])
    assert [r["count"] for r in results] == [3, 3, None]
    assert "column does not exist" in results[2]["error"]


# ─── Trends ───────────────────────────────────────────────────────────────────

def _month(counts, proxy=()):
    return {"results": [{"id": i, "count": c, "proxy": i in proxy} for i, c in counts.items()]}


def test_prune_needs_three_zero_months_and_skips_proxies():
    history = [_month({"a": 0, "b": 2, "p": 0}), _month({"a": 0, "b": 0, "p": 0})]
    current = _month({"a": 0, "b": 0, "p": 0}, proxy={"p"})["results"]
    t = trends(current, history)
    assert t["prune_candidates"] == ["a"]
    assert trends(current, history[-1:])["prune_candidates"] == []  # only two months known


def test_rising_compares_with_last_month():
    t = trends(_month({"a": 5, "b": 1})["results"], [_month({"a": 2, "b": 1})])
    assert t["rising"] == [{"id": "a", "previous": 2, "current": 5}]


def test_history_and_outputs_round_trip(tmp_path: Path):
    for m, c in (("2026-08", 0), ("2026-09", 0), ("2026-11", 9)):
        (tmp_path / f"{m}.json").write_text(json.dumps(_month({"a": c})))
    history = load_history(tmp_path, "2026-10", 2)
    assert [h["results"][0]["count"] for h in history] == [0, 0]  # 2026-11 is in the future: ignored
    results = [{"id": "a", "guard": "G", "proxy": False, "count": 0, "error": None}]
    md = write_outputs(tmp_path, "2026-10", results, trends(results, history), NOW).read_text()
    assert "連續 3 個月為 0（候選精簡）：a" in md
    assert json.loads((tmp_path / "2026-10.json").read_text())["results"][0]["count"] == 0
