"""G1 regression: Auto-QA reconciliation dispositions.

Locks in the H0 writer-safety semantics that Lane G1 must preserve, plus the G1
simplified-Chinese reroute:

  * a reviewed event is NOT auto-confirmed by virtue of being reviewed — its
    type predicate is re-run;
  * an all-Auto compound row confirms only when EVERY type resolves and stays
    pending while any one type still fires;
  * a row mixing a manual/unknown token with an Auto-QA token, or an empty row,
    is untouched by every automatic writer (all_known_auto_types -> None);
  * the legacy auto_qa_simplified_zh alias reconciles through the SAME predicate
    as the canonical auto_simplified_chinese, so historical rows remain
    reconcilable and produce an identical note.

The two legacy-alias tests FAIL against the pre-G1 code (the legacy type still
ran the detect() path, producing a different note); the remaining tests are H0
regression guards that must keep passing.
"""
from __future__ import annotations

from auto_qa import (
    _reconcile_check,
    _resolve_report_disposition,
    all_known_auto_types,
)

AUTO_ADDR = "auto_qa_missing_address"
AUTO_TITLE = "auto_qa_missing_title"
SIMP_LEGACY = "auto_qa_simplified_zh"
SIMP_CANON = "auto_simplified_chinese"
HUMAN = "wrongCategory"


def _event(**overrides):
    ev = {
        "id": "rec-1",
        "source_name": "peatix",
        "name_ja": "テストイベント",
        "raw_title": "テストイベント",
        "name_zh": "測試活動",
        "description_zh": "純繁體字の説明",
        "category": ["art"],
        "event_form": ["exhibition"],
        "location_name": "会場",
        "location_address": "東京都渋谷区1-1",
        "location_prefectures": ["東京都"],
        "organizer": "主催者",
        "annotation_status": "annotated",
        "is_active": True,
    }
    ev.update(overrides)
    return ev


# --- reviewed events still run their predicate -----------------------------

def test_reviewed_event_with_missing_address_stays_pending():
    ev = _event(annotation_status="reviewed", location_name="渋谷ホール", location_address="")
    disposition, reason = _resolve_report_disposition(ev, [AUTO_ADDR])
    assert disposition == "keep"
    assert reason == "predicate still fires"


def test_reviewed_event_confirms_when_predicate_resolves():
    ev = _event(
        annotation_status="reviewed",
        location_name="渋谷ホール",
        location_address="東京都渋谷区2-2",
    )
    disposition, reason = _resolve_report_disposition(ev, [AUTO_ADDR])
    assert disposition == "confirm"
    assert reason == "issue resolved"


# --- all-Auto compound: confirm only when EVERY type resolves --------------

def test_compound_confirms_only_when_all_resolved():
    ev = _event(name_ja="テストイベント", raw_title="テストイベント", category=["art"])
    disposition, reason = _resolve_report_disposition(
        ev, [AUTO_TITLE, "auto_qa_missing_category"]
    )
    assert disposition == "confirm"
    assert reason == "compound: every type resolved"


def test_compound_keeps_pending_when_one_type_still_fires():
    ev = _event(name_ja="テストイベント", raw_title="テストイベント", organizer=None)
    disposition, _reason = _resolve_report_disposition(
        ev, [AUTO_TITLE, "auto_qa_missing_organizer"]
    )
    assert disposition == "keep"


# --- mixed / unknown / empty rows are untouched ----------------------------

def test_mixed_and_unknown_and_empty_rows_are_not_all_auto():
    assert all_known_auto_types([AUTO_ADDR, HUMAN]) is None
    assert all_known_auto_types([HUMAN, AUTO_ADDR]) is None
    assert all_known_auto_types(["mystery_type"]) is None
    assert all_known_auto_types([]) is None
    assert all_known_auto_types(None) is None


# --- legacy simplified alias reconciles via the canonical predicate --------

def test_legacy_simplified_alias_uses_same_predicate_as_canonical():
    sc_ev = _event(name_zh="这说读", description_zh="")
    legacy = _reconcile_check(SIMP_LEGACY, sc_ev)
    canon = _reconcile_check(SIMP_CANON, sc_ev)
    assert legacy is not None
    assert legacy == canon


def test_legacy_simplified_alias_resolves_for_clean_event():
    clean = _event(name_zh="測試活動", description_zh="純繁體字の説明")
    assert _reconcile_check(SIMP_LEGACY, clean) is None
