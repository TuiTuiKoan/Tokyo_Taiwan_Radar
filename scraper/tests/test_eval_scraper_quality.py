"""Per-source scraper quality report (#354) and the shared field counter."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from eval_scraper_quality import (
    EXPECTATIONS_PATH,
    action_items,
    build_rows,
    classify_output,
    completeness,
    correction_rates,
    detect_drift,
    is_scraper_key,
    map_event_sources,
    parse_run_notes,
    write_report,
)
from quality_fields import applicable_fields, count_filled, is_filled, run_notes
from sources.base import Event

NOW = datetime(2026, 10, 22, 3, 0, tzinfo=timezone.utc)


def _run(days_ago, n, success=True, notes=None):
    return {"ran_at": (NOW - timedelta(days=days_ago)).isoformat(), "events_processed": n,
            "success": success, "notes": notes}


# ─── quality_fields ───────────────────────────────────────────────────────────

def test_is_filled_treats_false_as_an_answer():
    assert is_filled(False) and is_filled(0)
    assert not is_filled(None) and not is_filled("  ") and not is_filled([])


def test_pure_publication_skips_policy_null_fields():
    pub = {"event_form": ["publication"], "location_address": None, "organizer": "河出書房新社"}
    fields = applicable_fields(pub)
    assert "location_address" not in fields and "business_hours" not in fields and "location_name" not in fields
    assert "organizer" in fields
    mixed = {"event_form": ["publication", "lecture"]}
    assert "location_address" in applicable_fields(mixed)


def test_run_notes_from_event_objects():
    events = [
        Event(source_name="tokyoartbeat", source_id="1", source_url="u", original_language="ja",
              start_date=NOW, location_name="森美術館", official_url="https://x"),
        Event(source_name="tokyoartbeat", source_id="2", source_url="u", original_language="ja",
              start_date=NOW),
    ]
    assert count_filled(events[0]) == 3
    assert run_notes(events) == "parsed_fields_median=2, event_sources=tokyoartbeat"
    assert run_notes([]) == "parsed_fields_median=none"


# ─── Output health ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("runs,expectation,status", [
    ([_run(1, 5)], None, "active"),
    ([_run(1, 0), _run(10, 3)], None, "quiet"),
    ([_run(1, 0), _run(40, 3)], None, "zero_unexplained"),
    ([_run(1, 0, success=False), _run(2, 4)], None, "failing"),
    ([_run(1, 0)], {"pattern": "broken", "issue": 375}, "known_broken"),
    ([_run(1, 0)], {"pattern": "seasonal", "active_months": [3]}, "off_season"),
    ([_run(1, 0)], {"pattern": "seasonal", "active_months": [10]}, "zero_unexplained"),
    ([_run(1, 0), _run(50, 2)], {"pattern": "sporadic", "max_quiet_days": 90}, "quiet_expected"),
    ([_run(1, 0), _run(100, 2)], {"pattern": "sporadic", "max_quiet_days": 90}, "quiet_too_long"),
    ([_run(1, 0)], {"pattern": "sporadic", "max_quiet_days": 365}, "quiet_expected"),
    ([], None, "no_runs"),
])
def test_classify_output(runs, expectation, status):
    assert classify_output(runs, expectation, NOW)["status"] == status


def test_classify_output_counts_windows():
    o = classify_output([_run(1, 2), _run(3, 3), _run(20, 7), _run(60, 1)], None, NOW)
    assert (o["runs_7d"], o["events_7d"], o["events_28d"]) == (2, 5, 12)
    assert o["last_nonzero"] == "2026-10-21" and o["days_since_nonzero"] == 1


def test_meta_sources_are_not_scrapers():
    assert is_scraper_key("peatix")
    assert not is_scraper_key("annotator") and not is_scraper_key("researcher/slot1")
    assert not is_scraper_key("enrich_location")


# ─── Notes, drift, source mapping ─────────────────────────────────────────────

def test_parse_run_notes():
    assert parse_run_notes("parsed_fields_median=4.5, event_sources=a|b") == {
        "parsed_fields_median": 4.5, "event_sources": ["a", "b"]}
    assert parse_run_notes(None) == {"parsed_fields_median": None, "event_sources": []}
    assert parse_run_notes("parsed_fields_median=none")["parsed_fields_median"] is None


def test_drift_needs_history_then_alerts_on_sustained_drop():
    assert detect_drift([6, 6, 2, 2]) is None
    assert detect_drift([6, 6, 6, 3, 3, 3])["alert"] is True
    assert detect_drift([6, 6, 6, 3, 5, 3])["alert"] is False  # one run recovered
    assert detect_drift([6, 6, 6, 5, 5, 5])["alert"] is False  # -17% only


def test_map_event_sources():
    names = {"tokyoartbeat", "peatix", "ttcg_umeda"}
    assert map_event_sources("tokyo_art_beat", names, []) == ["tokyoartbeat"]
    assert map_event_sources("peatix", names, []) == ["peatix"]
    assert map_event_sources("ginsee_roble", names, []) == []
    assert map_event_sources("x", names, ["ttcg_umeda"]) == ["ttcg_umeda"]


# ─── Completeness and corrections ─────────────────────────────────────────────

def test_completeness_counts_only_applicable_fields():
    events = [
        {"event_form": ["publication"], "organizer": "出版社", "location_address": None},
        {"event_form": ["lecture"], "organizer": None, "location_address": "東京都"},
    ]
    t = completeness(events)
    assert t["organizer"] == {"filled": 1, "applicable": 2}
    assert t["location_address"] == {"filled": 1, "applicable": 1}


def test_correction_rates_split_human_and_script():
    fc = [
        {"event_id": "e1", "corrected_by": "u1", "report_id": None},
        {"event_id": "e2", "corrected_by": None, "report_id": "r1"},
        {"event_id": "e3", "corrected_by": None, "report_id": None},
        {"event_id": "zz", "corrected_by": "u1", "report_id": None},  # unknown event: ignored
    ]
    rates = correction_rates(fc, {"e1": "a", "e2": "a", "e3": "a"}, {"a": 10})
    assert rates["a"] == {"human": 2, "script": 1, "events": 10, "human_per_100": 20.0, "script_per_100": 10.0}


# ─── Rows, action items, report ───────────────────────────────────────────────

def _fixture_rows():
    runs_by_key = {
        "tokyo_art_beat": [_run(d, 0) for d in range(1, 30)],
        "peatix": [_run(d, 5, notes=f"parsed_fields_median={v}, event_sources=peatix")
                   for d, v in zip(range(6, 0, -1), [6, 6, 6, 2, 2, 2])],
        "mystery": [_run(d, 0) for d in range(1, 40)],
    }
    events_by_name = {
        "tokyoartbeat": [{"id": f"t{i}", "event_form": [], "start_date": "x"} for i in range(3)],
        "peatix": [{"id": f"p{i}", "event_form": [], "start_date": "x", "location_name": "会場",
                    "organizer": "主催"} for i in range(12)],
    }
    fc = [{"event_id": "p1", "corrected_by": "u", "report_id": None}]
    source_by_event = {e["id"]: n for n, evs in events_by_name.items() for e in evs}
    expectations = {"tokyo_art_beat": {"pattern": "broken", "issue": 375}}
    return build_rows(["tokyo_art_beat", "peatix", "mystery"], runs_by_key, events_by_name,
                      fc, source_by_event, expectations, NOW)


def test_build_rows_and_action_items():
    rows = {r["source"]: r for r in _fixture_rows()}
    assert rows["tokyo_art_beat"]["event_sources"] == ["tokyoartbeat"]
    assert rows["tokyo_art_beat"]["output"]["status"] == "known_broken"
    assert rows["peatix"]["drift"]["alert"] is True
    assert rows["peatix"]["annotator_fill"] == pytest.approx(3 - 4)
    assert rows["peatix"]["corrections"]["human_per_100"] == round(100 / 12, 1)
    assert rows["mystery"]["output"]["status"] == "zero_unexplained"
    reasons = [(i["source"], i["reason"][:8]) for i in action_items(list(rows.values()))]
    assert ("mystery", "🔴 28 天以上") in reasons
    assert any(s == "peatix" and r.startswith("DOM") for s, r in reasons)
    assert all(s != "tokyo_art_beat" for s, _ in reasons)  # known broken: tracked by its issue


def test_report_renders(tmp_path: Path):
    out = tmp_path / "r.md"
    write_report(_fixture_rows(), NOW, out)
    text = out.read_text()
    assert "## 需要處理" in text and "#375" in text and "DOM drift" in text


def test_expectations_file_is_well_formed():
    data = json.loads(EXPECTATIONS_PATH.read_text())
    for key, exp in data["sources"].items():
        assert exp["pattern"] in {"seasonal", "sporadic", "broken"}, key
        if exp["pattern"] == "seasonal":
            assert exp["active_months"] and all(1 <= m <= 12 for m in exp["active_months"]), key
        if exp["pattern"] == "sporadic":
            assert exp["max_quiet_days"] > 0, key
        if exp["pattern"] == "broken":
            assert isinstance(exp["issue"], int), key
