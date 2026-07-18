"""G1 regression: Auto-QA predicate correctness.

These lock in the tightened predicate semantics from Round G / Lane G1:

  * missing-hours fires only on *labelled event times* and rejects deadlines,
    ticket-sales windows, publication/article timestamps and update timestamps;
  * missing-performers requires a *conservative named-person candidate* — a bare
    role/group word no longer fires on its own;
  * thin-content does not fire for a sub-event that already carries its own
    structured data (the parent series supplies shared context);
  * annotation_error_stuck resolves only when the event's annotation reached a
    verified-complete state (annotated / reviewed);
  * detect() no longer emits the legacy auto_qa_simplified_zh finding;
  * a simplified-Chinese row is auto-eligible only when every SC-only char it
    contains is present in the SC->TC conversion map — any unmapped char leaves
    the row for MANUAL review.

The predicate-level behaviours (missing-hours / performers / thin-content /
annotation_error_stuck / legacy-emission) run against the existing functions and
FAIL against the pre-G1 code; the SC->TC gating helpers are new and are imported
inside the tests that need them so the rest of the file still collects.
"""
from __future__ import annotations

from auto_qa import (
    SC_ONLY,
    _check_missing_hours,
    _check_missing_performers,
    _check_thin_content,
    _reconcile_check,
    detect,
)


# --- missing-hours: labelled event time vs reject contexts -----------------

def _hours_event(**overrides):
    ev = {
        "id": "ev-hours",
        "source_name": "peatix",
        "category": ["performing_arts"],
        "event_form": ["performance"],
        "business_hours": None,
        "location_name": "渋谷 LOFT9",
        "location_address": "東京都渋谷区1-1",
        "raw_description": "",
        "annotation_status": "annotated",
        "is_active": True,
    }
    ev.update(overrides)
    return ev


def test_missing_hours_fires_on_labelled_event_time():
    for raw in ("開場 18:30 / 開演 19:00", "上映 14:00 スタート", "受付開始 13:30 集合"):
        ev = _hours_event(raw_description=raw)
        assert _check_missing_hours(ev) is not None, raw


def test_missing_hours_rejects_deadline_sales_publication_update_times():
    rejects = [
        "申込締切 5月10日 18:00まで",        # application deadline
        "チケット発売 10:00 開始",            # ticket-sales window
        "販売開始 12:00",                     # sales window
        "掲載 2024年 12:00 公開日",           # publication / article timestamp
        "記事更新 15:30",                     # update timestamp
        "エントリー受付終了 23:59",           # entry deadline
    ]
    for raw in rejects:
        ev = _hours_event(raw_description=raw)
        assert _check_missing_hours(ev) is None, raw


# --- missing-performers: named-person evidence required --------------------

def _perf_event(**overrides):
    ev = {
        "id": "ev-perf",
        "source_name": "peatix",
        "category": ["lifestyle_food"],
        "event_form": ["lecture"],
        "parent_event_id": None,
        "performers": None,
        "raw_title": "",
        "raw_description": "",
        "annotation_status": "annotated",
        "is_active": True,
    }
    ev.update(overrides)
    return ev


def test_missing_performers_ignores_generic_role_words_without_a_name():
    for raw in (
        "講師による特別講演を開催します",
        "出展ブランドとクリエイターが多数参加",
        "ゲストによるトークセッション",
    ):
        ev = _perf_event(raw_description=raw)
        assert _check_missing_performers(ev) is None, raw


def test_missing_performers_fires_when_a_named_person_is_present():
    cases = [
        "講師：山田太郎さん による講演",          # explicit "role: name" list entry
        "ゲストにジョン・スミスが登壇",            # middle-dot katakana full name
        "モデレーターは佐藤先生です",             # name carrying a personal title
    ]
    for raw in cases:
        ev = _perf_event(raw_description=raw)
        assert _check_missing_performers(ev) is not None, raw


# --- thin-content: child-with-structure context ----------------------------

def test_thin_content_skips_child_with_structured_data():
    child = {
        "id": "sub-1",
        "source_name": "peatix",
        "parent_event_id": "parent-1",
        "raw_description": "短い紹介",           # < 50 chars
        "start_date": "2026-03-01T10:00:00+09:00",
        "location_name": "会場A",
        "organizer": "主催B",
        "performers": None,
        "source_url": "https://example.test/sub-1",
    }
    assert _check_thin_content(child) is None


def test_thin_content_still_fires_for_thin_top_level_event():
    top = {
        "id": "top-1",
        "source_name": "peatix",
        "parent_event_id": None,
        "raw_description": "短い",
        "start_date": None,
        "location_name": None,
        "organizer": None,
        "performers": None,
        "source_url": "https://example.test/top-1",
    }
    assert _check_thin_content(top) is not None


# --- annotation_error_stuck predicate --------------------------------------

def test_annotation_error_stuck_resolves_only_when_annotated_or_reviewed():
    for status in ("annotated", "reviewed"):
        assert _reconcile_check("annotation_error_stuck", {"annotation_status": status}) is None
    for status in ("pending", "error", "processing", None):
        note = _reconcile_check("annotation_error_stuck", {"annotation_status": status})
        assert note is not None and note != "no_predicate_keep", status


# --- detect() no longer emits the legacy simplified alias ------------------

def test_detect_no_longer_emits_legacy_simplified_zh():
    ev = {
        "id": "ev-sc",
        "source_name": "peatix",
        "name_zh": "这个说读",             # SC chars present
        "description_zh": "",
        "location_name": "会場",
        "location_address": "東京都1-1",
        "category": ["art"],
    }
    types = {t for t, _ in detect(ev)}
    assert "auto_qa_simplified_zh" not in types


# --- SC->TC gating: all-mapped auto-eligible / any-unmapped manual ---------

def test_sc_row_gating_all_mapped_is_eligible():
    from auto_qa import sc_row_is_auto_eligible

    mapping = {"说": "說"}                  # 说 is in SC_ONLY and mapped here
    assert "说" in SC_ONLY
    assert sc_row_is_auto_eligible({"name_zh": "他说了"}, mapping=mapping) is True


def test_sc_row_gating_any_unmapped_char_is_manual():
    from auto_qa import sc_row_is_auto_eligible, _sc_unmapped_chars

    mapping = {"说": "說"}                  # 电 is in SC_ONLY but NOT mapped here
    assert "电" in SC_ONLY
    mixed = {"name_zh": "说电"}
    assert sc_row_is_auto_eligible(mixed, mapping=mapping) is False
    assert _sc_unmapped_chars(mixed, mapping) == {"电"}


def test_sc_row_gating_no_sc_chars_is_not_eligible():
    from auto_qa import sc_row_is_auto_eligible

    assert sc_row_is_auto_eligible({"name_zh": "純日本語のイベント"}, mapping={"说": "說"}) is False
