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
from test_qa_auto_fix_unlock_only import FakeSupabase

EVENT_A = "11111111-1111-4111-8111-111111111111"
EVENT_B = "22222222-2222-4222-8222-222222222222"
# The legacy pollution this cohort is defined by: a journal title parked in
# location_name that also trips the physical-venue detector.
JOURNAL = "台湾大学学報 = Taiwan studies / 台湾学会 編"
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
