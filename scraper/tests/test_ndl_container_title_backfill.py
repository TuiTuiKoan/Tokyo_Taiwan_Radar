"""Offline contract tests for the NDL container-title release unit.

No network, no Supabase client, no production data: every case runs against the
in-memory fake. The apply stage in particular is asserted to make zero network
calls, because a stage that re-plans can write a value no reviewer approved.
"""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

import _oneoff_backfill_ndl_container_title as b1
from _oneoff_backfill_publication_metadata import PHYSICAL_LOCATION_RE
from test_qa_auto_fix_unlock_only import FakeSupabase

EVENT_A = "11111111-1111-4111-8111-111111111111"
EVENT_B = "22222222-2222-4222-8222-222222222222"
EVENT_C = "33333333-3333-4333-8333-333333333333"
EVENT_D = "44444444-4444-4444-8444-444444444444"
EVENT_E = "55555555-5555-4555-8555-555555555555"
# The legacy pollution this cohort is defined by: a journal title parked in
# location_name that also trips the physical-venue detector.
JOURNAL = "台湾大学学報 = Taiwan studies / 台湾学会 編"
BOILERPLATE = "新刊のご購入は各販売チャネルでお願いします"
BODY = "本稿は台湾の文化交流を論じる。"
PLANNED = f"{b1.CONTAINER_TITLE_PREFIX}{JOURNAL}\n\n{BODY}"
EMPTY_DIGEST = {"row_count": 0, "sha256": b1.sha256([])}


def _row(event_id: str = EVENT_A, **overrides):
    row = {
        "id": event_id,
        "source_name": b1.SOURCE_NAME,
        "source_id": f"ndl_{event_id[:8]}",
        "source_url": f"https://ndlsearch.ndl.go.jp/books/{event_id}",
        "event_form": ["publication"],
        "raw_title": "台湾の文化交流",
        "name_ja": "[雑誌記事] 台湾の文化交流",
        "raw_description": BODY,
        "description_ja": BODY,
        "description_zh": "本文討論台灣的文化交流。",
        "description_en": "An essay on Taiwan cultural exchange.",
        "annotation_status": "annotated",
        "updated_at": "2026-07-11T00:00:00+00:00",
        "price_info": "1,200円",
        "location_address": None,
        "location_address_zh": None,
        "location_address_en": None,
        "business_hours": None,
        "business_hours_zh": None,
        "business_hours_en": None,
        "location_prefectures": None,
        "location_name": JOURNAL,
        "location_name_zh": None,
        "location_name_en": None,
        "location_url": None,
        "venue_id": None,
        "organizer_type": None,
    }
    row.update(overrides)
    return row


def _fake(rows=None, field_corrections=None):
    return FakeSupabase(
        {
            "events": deepcopy(rows if rows is not None else [_row()]),
            "field_corrections": deepcopy(field_corrections or []),
        }
    )


def _description_fc(event_id: str, field_name: str, value: str):
    return {
        "id": f"fc-{event_id[:4]}-{field_name}",
        "event_id": event_id,
        "field_name": field_name,
        "original_value": None,
        "corrected_value": value,
        "corrected_by": None,
        "report_id": None,
        "created_at": "2026-06-04T00:00:00+00:00",
    }


def _stub_lookups(monkeypatch, retrieved):
    monkeypatch.setattr(b1, "lookup_via_api", lambda _row: retrieved)
    monkeypatch.setattr(b1, "lookup_via_detail_page", lambda _row: None)


def _no_network(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("the apply stage must perform zero network calls")

    monkeypatch.setattr(b1.requests, "get", _boom)
    monkeypatch.setattr(b1, "lookup_via_api", _boom)
    monkeypatch.setattr(b1, "lookup_via_detail_page", _boom)


def _plan(sb, monkeypatch, *, retrieved=JOURNAL):
    _stub_lookups(monkeypatch, retrieved)
    rows = b1.select_cohort(b1.fetch_rows(sb))
    plans = [b1.plan_row(row) for row in rows]
    return b1.build_plan(
        rows,
        plans,
        description_field_corrections=b1.description_fc_digest(
            sb, [str(row["id"]) for row in rows]
        ),
    )


def _classify(monkeypatch, overrides, retrieved):
    """Classify one row directly, bypassing the cohort filter."""
    _stub_lookups(monkeypatch, retrieved)
    row = _row(**overrides)
    return b1.build_plan(
        [row], [b1.plan_row(row)], description_field_corrections=EMPTY_DIGEST
    )


def _reseal(plan):
    plan.pop("plan_sha256", None)
    plan["plan_sha256"] = b1.sha256(plan)
    return plan


def _round_trip(tmp_path, plan, name="plan.json"):
    path = tmp_path / name
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return b1.load_plan(path)


def _apply(sb, plan, monkeypatch):
    _no_network(monkeypatch)
    results = []
    error = None
    try:
        for entry in [entry for entry in plan["rows"] if entry["status"] == "planned"]:
            results.append(b1.apply_entry(sb, entry))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return b1.build_journal(
        plan,
        results,
        description_field_corrections_after=b1.description_fc_digest(
            sb, [entry["event_id"] for entry in plan["rows"]]
        ),
        error=error,
    )


# --- projection -----------------------------------------------------------


def test_projection_carries_every_acceptance_field_not_just_planning_inputs():
    columns = set(b1.projection_columns())
    assert {
        "annotation_status",
        "updated_at",
        "description_zh",
        "description_en",
        "price_info",
    } <= columns
    assert set(b1.PUBLICATION_NULL_FIELDS) <= columns
    assert set(b1.PUBLICATION_EXTENDED_CLEAR_FIELDS) <= columns
    assert len(b1.projection_columns()) == len(set(b1.projection_columns()))


def test_before_image_holds_the_whole_projection(monkeypatch):
    plan = _plan(_fake(), monkeypatch)
    assert set(plan["rows"][0]["before_image"]) == set(b1.projection_columns())


# --- two-stage artifact ---------------------------------------------------


def test_plan_is_digest_bound_and_tampering_is_refused(tmp_path, monkeypatch):
    plan = _plan(_fake(), monkeypatch)
    assert _round_trip(tmp_path, plan)["plan_sha256"] == plan["plan_sha256"]

    tampered = deepcopy(plan)
    tampered["rows"][0]["planned_raw_description"] = "injected"
    with pytest.raises(RuntimeError, match="plan digest mismatch"):
        _round_trip(tmp_path, tampered, name="tampered.json")


def test_apply_consumes_the_plan_and_performs_zero_network_calls(tmp_path, monkeypatch):
    sb = _fake()
    plan = _round_trip(tmp_path, _plan(sb, monkeypatch))
    journal = _apply(sb, plan, monkeypatch)

    assert journal["stopped_with_error"] is None
    assert journal["applied_event_ids"] == [EVENT_A]
    assert sb.tables["events"][0]["raw_description"] == PLANNED


def test_plan_holds_eligible_ids_while_the_journal_holds_what_was_written(tmp_path, monkeypatch):
    already = _row(EVENT_B, raw_description=f"{b1.CONTAINER_TITLE_LABEL}：{JOURNAL}")
    sb = _fake([_row(), already])
    plan = _round_trip(tmp_path, _plan(sb, monkeypatch))
    assert plan["eligible_event_ids"] == [EVENT_A]

    sb.tables["events"][0]["raw_description"] = "drifted between plan and apply"
    journal = _apply(sb, plan, monkeypatch)
    assert journal["applied_event_ids"] == []
    assert journal["cas_miss_event_ids"] == [EVENT_A]
    assert journal["results"][0]["after_image"] is None


def test_journal_records_the_observed_physical_after_image(tmp_path, monkeypatch):
    sb = _fake()
    journal = _apply(sb, _round_trip(tmp_path, _plan(sb, monkeypatch)), monkeypatch)
    after = journal["results"][0]["after_image"]
    assert set(after) == set(b1.projection_columns())
    assert after["raw_description"] == sb.tables["events"][0]["raw_description"]


# --- citation-safety classification ---------------------------------------


@pytest.mark.parametrize(
    "overrides,retrieved,status,safety",
    [
        ({}, JOURNAL, "planned", "pending_apply"),
        (
            {"raw_description": f"{b1.CONTAINER_TITLE_LABEL}：{JOURNAL}"},
            JOURNAL,
            "already_present",
            "safe",
        ),
        ({"location_name": "2026 16"}, None, "unavailable", "confirm_per_row"),
        ({}, "まったく別の学術誌", "needs_review", "unsafe"),
    ],
)
def test_each_status_maps_to_its_citation_safety_class(
    monkeypatch, overrides, retrieved, status, safety
):
    plan = _classify(monkeypatch, overrides, retrieved)
    entry = plan["rows"][0]
    assert (entry["status"], entry["citation_safety"]) == (status, safety)
    assert entry["event_id"] in plan["citation_safety_sets"][safety]


def test_only_planned_rows_are_ever_written(tmp_path, monkeypatch):
    sb = _fake([_row(), _row(EVENT_B)])
    plan = _plan(sb, monkeypatch)
    plan["rows"][1]["status"] = "needs_review"
    plan["rows"][1]["citation_safety"] = "unsafe"
    plan["citation_safety_sets"]["pending_apply"] = [EVENT_A]
    plan["citation_safety_sets"]["unsafe"] = [EVENT_B]
    plan["eligible_event_ids"] = [EVENT_A]

    journal = _apply(sb, _round_trip(tmp_path, _reseal(plan)), monkeypatch)
    assert journal["applied_event_ids"] == [EVENT_A]
    assert journal["citation_safety_sets"]["unsafe"] == [EVENT_B]
    assert journal["citation_safety_sets"]["pending_apply"] == []


# --- compare-and-set ------------------------------------------------------


def test_cas_covers_every_planning_input():
    assert set(b1.CAS_COLUMNS) == {
        "raw_description",
        "location_name",
        "source_url",
        "event_form",
    }


@pytest.mark.parametrize("column", ["raw_description", "location_name", "source_url", "event_form"])
def test_cas_miss_is_reported_rather_than_forced(tmp_path, monkeypatch, column):
    sb = _fake()
    plan = _round_trip(tmp_path, _plan(sb, monkeypatch))
    sb.tables["events"][0][column] = (
        ["publication", "lecture"] if column == "event_form" else "drifted"
    )

    journal = _apply(sb, plan, monkeypatch)
    assert journal["cas_miss_event_ids"] == [EVENT_A]
    assert journal["stopped_with_error"] is None
    assert sb.tables["events"][0]["raw_description"] != PLANNED
    assert journal["citation_safety_sets"]["unsafe"] == [EVENT_A]


def test_cas_hit_writes_exactly_one_column(tmp_path, monkeypatch):
    sb = _fake()
    _apply(sb, _round_trip(tmp_path, _plan(sb, monkeypatch)), monkeypatch)
    updates = [write for write in sb.writes if write[1] == "update"]
    assert [write[2] for write in updates] == [{"raw_description": PLANNED}]


# --- read-back and allowlist diff -----------------------------------------


def test_read_back_mismatch_raises(tmp_path, monkeypatch):
    sb = _fake()
    plan = _round_trip(tmp_path, _plan(sb, monkeypatch))
    monkeypatch.setattr(
        b1,
        "read_back",
        lambda _sb, _id: {**plan["rows"][0]["before_image"], "raw_description": "other"},
    )
    journal = _apply(sb, plan, monkeypatch)
    assert "read-back does not match the planned value" in journal["stopped_with_error"]


def _allowlist_gate_fires(tmp_path, monkeypatch, column, value):
    sb = _fake()
    plan = _round_trip(tmp_path, _plan(sb, monkeypatch))
    original = b1.read_back

    def _drifting_read_back(client, event_id):
        row = original(client, event_id)
        row[column] = value
        return row

    monkeypatch.setattr(b1, "read_back", _drifting_read_back)
    return "allowlist diff rejected" in (_apply(sb, plan, monkeypatch)["stopped_with_error"] or "")


def test_allowlist_diff_rejects_an_unexpected_column_delta(tmp_path, monkeypatch):
    assert _allowlist_gate_fires(tmp_path, monkeypatch, "price_info", "9,999円") is True


def test_allowlist_diff_permits_the_trigger_maintained_updated_at(tmp_path, monkeypatch):
    assert (
        _allowlist_gate_fires(tmp_path, monkeypatch, "updated_at", "2026-08-10T00:00:00+00:00")
        is False
    )


def test_projection_removal_makes_the_acceptance_gate_fail(tmp_path, monkeypatch):
    """Dropping a column from SELECT_COLUMNS must break a gate, not pass quietly."""
    assert _allowlist_gate_fires(tmp_path, monkeypatch, "price_info", "9,999円") is True

    narrowed = ",".join(column for column in b1.projection_columns() if column != "price_info")
    monkeypatch.setattr(b1, "SELECT_COLUMNS", narrowed)
    assert _allowlist_gate_fires(tmp_path, monkeypatch, "price_info", "9,999円") is False


# --- B2 no-write boundary -------------------------------------------------


def test_description_field_correction_digest_is_recorded_before_and_after(tmp_path, monkeypatch):
    locks = [
        _description_fc(EVENT_A, field, f"locked {field}") for field in b1.DESCRIPTION_FC_FIELDS
    ]
    sb = _fake(field_corrections=locks)
    journal = _apply(sb, _round_trip(tmp_path, _plan(sb, monkeypatch)), monkeypatch)

    assert journal["description_field_correction_digest_before"]["row_count"] == 3
    assert journal["description_field_corrections_unchanged"] is True
    assert (
        journal["description_field_correction_digest_before"]
        == journal["description_field_correction_digest_after"]
    )


def test_a_mutated_description_lock_breaks_the_digest_equality(tmp_path, monkeypatch):
    sb = _fake(field_corrections=[_description_fc(EVENT_A, "description_zh", "locked")])
    plan = _round_trip(tmp_path, _plan(sb, monkeypatch))
    sb.tables["field_corrections"][0]["corrected_value"] = "tampered"

    journal = _apply(sb, plan, monkeypatch)
    assert journal["description_field_corrections_unchanged"] is False


def test_this_release_unit_never_writes_a_description_or_its_field_correction(
    tmp_path, monkeypatch
):
    locks = [
        _description_fc(EVENT_A, field, f"locked {field}") for field in b1.DESCRIPTION_FC_FIELDS
    ]
    sb = _fake(field_corrections=locks)
    _apply(sb, _round_trip(tmp_path, _plan(sb, monkeypatch)), monkeypatch)

    assert [(write[0], write[1]) for write in sb.writes] == [("events", "update")]
    assert set(sb.writes[0][2]) == {"raw_description"}
    assert sb.tables["field_corrections"] == locks
    row = sb.tables["events"][0]
    assert (row["description_ja"], row["description_zh"], row["description_en"]) == (
        BODY,
        "本文討論台灣的文化交流。",
        "An essay on Taiwan cultural exchange.",
    )


# --- the cohort predicate tests citation identity, not venue shape --------

# Measured against the live cohort. Only the first value is venue-shaped, so a
# venue-shaped test selected it and dropped four real journals whose citation
# lives nowhere else. Pinned here so that coupling cannot return.
PREDICATE_SAMPLES = (
    ("北海道教育大学大学院高度教職実践専攻研究紀要 : 教職大学院研究紀要 (16):2026.3", True),
    ("神戸法学雑誌 = Kobe law journal 75(3・4):2026.3", True),
    ("文芸春秋 104(5):2026.5", True),
    ("月刊カレント 63(6)=982:2026.6", True),
    ("防衛技術ジャーナル / 防衛技術協会 [編] 46(4)=541:2026.4", True),
    ("新刊のご購入は各販売チャネルでお願いします", False),
)


@pytest.mark.parametrize("location_name,preserved", PREDICATE_SAMPLES)
def test_the_predicate_pins_the_real_location_names(location_name, preserved):
    assert b1.is_journal_title_in_location_name({"location_name": location_name}) is preserved


def test_venue_shape_is_not_what_decides_preservation():
    """Four of the five preserved values match no venue pattern, yet are preserved."""
    not_venue_shaped = [
        name
        for name, preserved in PREDICATE_SAMPLES
        if preserved and not PHYSICAL_LOCATION_RE.search(name)
    ]
    assert not_venue_shaped == [name for name, _ in PREDICATE_SAMPLES[1:5]]
    assert [
        name
        for name in not_venue_shaped
        if b1.is_journal_title_in_location_name({"location_name": name})
    ] == not_venue_shaped


@pytest.mark.parametrize("location_name,preserved", PREDICATE_SAMPLES)
def test_the_predicate_decides_the_write_cohort(location_name, preserved):
    cohort = b1.select_cohort([_row(location_name=location_name)])
    assert [row["id"] for row in cohort] == ([EVENT_A] if preserved else [])


@pytest.mark.parametrize("location_name", ["", "   ", "16", "2026.3"])
def test_an_empty_citation_core_never_enters_the_cohort(location_name):
    assert b1.citation_core(location_name) == ""
    assert b1.is_journal_title_in_location_name({"location_name": location_name}) is False
    assert b1.select_cohort([_row(location_name=location_name)]) == []


# --- every exact-pure candidate carries a determination -------------------


def _full_plan(sb, monkeypatch, *, retrieved=JOURNAL):
    """Stage 1 end to end: the write cohort planned, every other candidate assessed."""
    _stub_lookups(monkeypatch, retrieved)
    candidates = b1.cleanup_candidate_rows(b1.fetch_rows(sb))
    cohort = b1.select_cohort(candidates)
    cohort_ids = {str(row["id"]) for row in cohort}
    plans = [b1.plan_row(row) for row in cohort]
    plans.extend(b1.assess_row(row) for row in candidates if str(row["id"]) not in cohort_ids)
    return b1.build_plan(
        candidates,
        plans,
        description_field_corrections=b1.description_fc_digest(
            sb, [str(row["id"]) for row in candidates]
        ),
    )


def test_the_artifact_determines_every_exact_pure_candidate(monkeypatch):
    """The cleanup clears location_name on all of them, so all of them need a verdict."""
    plan = _full_plan(
        _fake(
            [
                _row(),
                _row(EVENT_C, source_name="hanmoto", location_name=BOILERPLATE),
                _row(EVENT_D, source_name="hanmoto", location_name=None),
                _row(EVENT_E, event_form=["publication", "lecture"]),
            ]
        ),
        monkeypatch,
    )
    determined = {
        event_id for values in plan["citation_safety_sets"].values() for event_id in values
    }
    assert determined == {EVENT_A, EVENT_C, EVENT_D}
    assert {entry["event_id"] for entry in plan["rows"]} == determined


def test_an_assessed_row_costs_no_network_call(monkeypatch):
    _no_network(monkeypatch)
    assert b1.assess_row(_row(source_name="hanmoto", location_name=BOILERPLATE))["status"] == (
        "no_citation"
    )


@pytest.mark.parametrize(
    "overrides,status,assessment",
    [
        ({"location_name": None}, "no_citation", "location_name_empty"),
        ({"location_name": BOILERPLATE}, "no_citation", "publication_boilerplate"),
        ({"location_name": "16"}, "unavailable", "no_citation_core"),
        (
            {
                "location_name": "文芸春秋 104(5):2026.5",
                "description_ja": "初出: 文芸春秋 104(5):2026.5。",
            },
            "citation_present_elsewhere",
            "description_ja",
        ),
        ({"location_name": "文芸春秋 104(5):2026.5"}, "needs_review", "citation_only_in_location_name"),
    ],
)
def test_an_assessed_row_records_why_it_needs_no_write(overrides, status, assessment):
    plan = b1.assess_row(_row(**overrides))
    assert (plan["status"], plan["assessment"]) == (status, assessment)
    assert plan["planned_raw_description"] is None


def test_a_journal_named_nowhere_else_is_unsafe_rather_than_quietly_safe():
    assert b1.PLAN_CITATION_SAFETY["needs_review"] == "unsafe"
    assert b1.PLAN_CITATION_SAFETY["no_citation"] == "safe"
    assert b1.PLAN_CITATION_SAFETY["citation_present_elsewhere"] == "safe"


# --- a shared word is a coincidence, not a citation ----------------------

# 25 live location_names shorten to a two-character everyday word once the
# catalogue tail is dropped. This is one of them.
SHORT_TITLE_CITATION = "交流 (1021):2026.4"


def test_a_title_fragment_the_prose_uses_in_passing_is_not_a_citation_match():
    """Five retained fields say `交流`; none reproduce the catalogue value."""
    row = _row(source_name="hanmoto", location_name=SHORT_TITLE_CITATION)

    assert [
        field for field in b1.CITATION_RETAINED_FIELDS if "交流" in str(row[field] or "")
    ] == ["raw_description", "description_ja", "description_zh", "raw_title", "name_ja"]
    assert not [
        field
        for field in b1.CITATION_RETAINED_FIELDS
        if SHORT_TITLE_CITATION in str(row[field] or "")
    ]

    assert b1.citation_present_elsewhere(row) is None
    plan = b1.assess_row(row)
    assert (plan["status"], plan["assessment"]) == (
        "needs_review",
        "citation_only_in_location_name",
    )
    assert b1.PLAN_CITATION_SAFETY[plan["status"]] == "unsafe"
