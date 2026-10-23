"""Publication relevance gate eligibility (P5 C2).

Pure publications are born with 7 empty-sentinel field_corrections, which the
old "any FC -> skip" rule read as a human lock, so the gate never ran for ndl.
_publication_gate_eligible() accepts exactly the first-pass shape and nothing
else, behind a flag that stays False until holdout passes.
"""

import types

import pytest

import annotator
from annotator import (
    RELEVANCE_GATE_REASON,
    _publication_gate_eligible,
    _relevance_gate_update,
)
from publication_rules import PUBLICATION_NULL_FIELDS

SENTINELS = {name: "" for name in PUBLICATION_NULL_FIELDS}
NOT_TAIWAN = {"taiwan_relevance": {"is_relevant": False, "confidence": 0.95}}


def _first_pass_event(**overrides):
    event = {
        "id": "11111111-aaaa",
        "source_name": "ndl_opensearch",
        "event_form": ["publication"],
        "annotated_at": None,
        "annotation_status": "pending",
    }
    event.update(overrides)
    return event


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(annotator, "PUBLICATION_RELEVANCE_GATE_ENABLED", True)


def test_flag_defaults_to_off():
    assert annotator.PUBLICATION_RELEVANCE_GATE_ENABLED is False


# ── the ten cases of proposal 2.3 ───────────────────────────────────────────
def test_first_pass_with_exactly_seven_empty_sentinels_is_eligible(gate_on):
    assert _publication_gate_eligible(_first_pass_event(), dict(SENTINELS), True) == (
        True,
        "eligible",
    )


def test_already_annotated_is_not_eligible(gate_on):
    event = _first_pass_event(annotated_at="2026-10-01T00:00:00+00:00")
    assert _publication_gate_eligible(event, dict(SENTINELS), True) == (False, "already_annotated")


def test_one_extra_field_correction_is_not_eligible(gate_on):
    fields = {**SENTINELS, "description_zh": ""}
    assert _publication_gate_eligible(_first_pass_event(), fields, True) == (False, "fc_extra_fields")


def test_one_missing_sentinel_is_not_eligible(gate_on):
    fields = dict(SENTINELS)
    fields.pop("business_hours_en")
    assert _publication_gate_eligible(_first_pass_event(), fields, True) == (
        False,
        "fc_missing_sentinel",
    )


def test_non_empty_sentinel_is_not_eligible(gate_on):
    fields = {**SENTINELS, "location_address": "東京都千代田区"}
    assert _publication_gate_eligible(_first_pass_event(), fields, True) == (
        False,
        "fc_sentinel_not_empty",
    )


def test_fc_not_loaded_is_not_eligible_even_with_empty_map(gate_on):
    assert _publication_gate_eligible(_first_pass_event(), {}, False) == (False, "fc_not_loaded")
    assert _publication_gate_eligible(_first_pass_event(), dict(SENTINELS), False) == (
        False,
        "fc_not_loaded",
    )


def test_missing_annotated_at_key_is_not_eligible(gate_on):
    event = _first_pass_event()
    del event["annotated_at"]
    assert _publication_gate_eligible(event, dict(SENTINELS), True) == (False, "annotated_at_missing")


def test_reviewed_is_not_eligible(gate_on):
    event = _first_pass_event(annotation_status="reviewed")
    assert _publication_gate_eligible(event, dict(SENTINELS), True) == (False, "reviewed")


def test_mixed_event_form_is_not_eligible(gate_on):
    event = _first_pass_event(event_form=["publication", "lecture"])
    assert _publication_gate_eligible(event, dict(SENTINELS), True) == (False, "not_pure_publication")


def test_flag_off_is_not_eligible():
    assert _publication_gate_eligible(_first_pass_event(), dict(SENTINELS), True) == (False, "flag_off")


def test_empty_fc_map_is_not_eligible(gate_on):
    assert _publication_gate_eligible(_first_pass_event(), {}, True) == (False, "fc_missing_sentinel")
    assert _publication_gate_eligible(_first_pass_event(), None, True) == (False, "fc_missing_sentinel")


@pytest.mark.parametrize(
    "event",
    [
        # hanmoto 3187dc1b shape (2026-10-22): annotated_at NULL, status error, no FC
        _first_pass_event(source_name="hanmoto", annotation_status="error"),
        # ndl 5a51bd60 shape: annotated_at NULL, reviewed, many FC
        _first_pass_event(annotation_status="reviewed"),
    ],
)
def test_existing_null_annotated_at_records_are_still_excluded(gate_on, event):
    fields = {**SENTINELS, "name_zh": "x", "description_zh": "y"} if event["annotation_status"] == "reviewed" else {}
    eligible, reason = _publication_gate_eligible(event, fields, True)
    assert not eligible
    assert reason in {"reviewed", "fc_missing_sentinel"}


# ── _relevance_gate_update wiring ───────────────────────────────────────────
def test_eligible_publication_is_deactivated_on_confident_irrelevant_verdict(gate_on):
    update = _relevance_gate_update(_first_pass_event(), NOT_TAIWAN, dict(SENTINELS), False, True)
    assert update == {"is_active": False, "deactivated_reason": RELEVANCE_GATE_REASON}


def test_eligible_publication_relevant_or_low_confidence_is_untouched(gate_on):
    relevant = {"taiwan_relevance": {"is_relevant": True, "confidence": 0.99}}
    low = {"taiwan_relevance": {"is_relevant": False, "confidence": 0.5}}
    assert _relevance_gate_update(_first_pass_event(), relevant, dict(SENTINELS), False, True) is None
    assert _relevance_gate_update(_first_pass_event(), low, dict(SENTINELS), False, True) is None


def test_flag_off_never_deactivates_a_publication_even_without_any_fc():
    # Old behaviour would act here (no FC at all); the flag must stop it.
    assert _relevance_gate_update(_first_pass_event(), NOT_TAIWAN, {}, False, True) is None
    assert _relevance_gate_update(_first_pass_event(), NOT_TAIWAN, dict(SENTINELS), False, True) is None


def test_fc_load_failure_never_deactivates_a_publication(gate_on):
    assert _relevance_gate_update(_first_pass_event(), NOT_TAIWAN, {}, False, False) is None


def test_fix_reviewed_pass_never_deactivates_a_publication(gate_on):
    assert _relevance_gate_update(_first_pass_event(), NOT_TAIWAN, dict(SENTINELS), True, True) is None


def test_reason_code_is_logged(gate_on, caplog):
    with caplog.at_level("INFO", logger=annotator.logger.name):
        _relevance_gate_update(_first_pass_event(annotated_at="2026-10-01"), NOT_TAIWAN, dict(SENTINELS), False, True)
    assert "already_annotated" in caplog.text


# ── non-publications: behaviour unchanged ───────────────────────────────────
@pytest.mark.parametrize("flag", [False, True])
def test_non_publication_gate_ignores_the_publication_flag(monkeypatch, flag):
    monkeypatch.setattr(annotator, "PUBLICATION_RELEVANCE_GATE_ENABLED", flag)
    event = {"id": "e1", "source_name": "iwafu", "event_form": ["lecture"]}
    assert _relevance_gate_update(event, NOT_TAIWAN, {}, False, True) == {
        "is_active": False,
        "deactivated_reason": RELEVANCE_GATE_REASON,
    }
    assert _relevance_gate_update(event, NOT_TAIWAN, {"name_zh": "x"}, False, True) is None
    assert _relevance_gate_update(event, NOT_TAIWAN, {}, True, True) is None
    # fc_loaded=False does not change the non-publication path
    assert _relevance_gate_update(event, NOT_TAIWAN, {}, False, False) is not None


def test_mixed_form_keeps_physical_event_behaviour(gate_on):
    event = {"id": "e2", "source_name": "peatix", "event_form": ["publication", "lecture"]}
    assert _relevance_gate_update(event, NOT_TAIWAN, {}, False, True) is not None
    assert _relevance_gate_update(event, NOT_TAIWAN, {"name_zh": "x"}, False, True) is None


# ── fc_loaded + projection in the real fetch path ───────────────────────────
class _Query:
    def __init__(self, recorder, table):
        self._recorder = recorder
        self._table = table

    def __getattr__(self, name):
        def call(*args, **kwargs):
            if name == "select":
                self._recorder.append((self._table, args[0] if args else "*"))
            if name == "execute":
                return types.SimpleNamespace(data=[])
            return self
        return call


class _FakeSupabase:
    def __init__(self):
        self.selects = []

    def table(self, name):
        return _Query(self.selects, name)


def _run_fetch(monkeypatch, **kwargs):
    sb = _FakeSupabase()
    monkeypatch.setattr(annotator, "_check_category_sync", lambda: None)
    monkeypatch.setattr(annotator, "_get_supabase", lambda: sb)
    monkeypatch.setattr(annotator, "_get_openai", lambda: object())
    monkeypatch.setattr(annotator, "load_corrections", lambda _sb: [])
    annotator.annotate_pending_events(dry_run=True, **kwargs)
    return [cols for table, cols in sb.selects if table == "events"]


def _has_gate_columns(cols: str) -> bool:
    if cols.strip() == "*":
        return True
    names = {c.strip() for c in cols.split(",")}
    return {"event_form", "annotated_at", "annotation_status"} <= names


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"re_annotate_all": True},
        {"fix_translations": True},
        {"fix_reviewed": True},
        {"event_id": "e1"},
        {"event_ids": ["e1", "e2"]},
    ],
)
def test_every_fetch_path_returns_the_gate_columns(monkeypatch, kwargs):
    events_selects = _run_fetch(monkeypatch, **kwargs)
    assert events_selects, "annotate_pending_events never selected from events"
    assert all(_has_gate_columns(cols) for cols in events_selects), events_selects


def test_projection_check_fails_for_a_narrowed_select():
    assert not _has_gate_columns("id,name_ja,event_form")
    assert not _has_gate_columns("id,event_form,annotated_at")  # annotation_status missing
    assert _has_gate_columns("*")
    assert _has_gate_columns("id,event_form,annotated_at,annotation_status")


def test_fc_load_failure_sets_fc_loaded_false_in_the_main_flow():
    import inspect

    source = inspect.getsource(annotator.annotate_pending_events)
    assert "fc_loaded = True" in source
    assert "fc_loaded = False" in source
    assert "_relevance_gate_update(event, annotation, _human_protected, fix_reviewed, fc_loaded)" in source
