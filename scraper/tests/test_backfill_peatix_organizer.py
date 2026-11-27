"""Pure helpers of backfill_peatix_organizer.py (no DB, no browser)."""
import pytest

from backfill_peatix_organizer import is_blocked, parse_event_ids, select_targets

A = "60dfab63-30ab-43cc-8cee-85b51c5e174c"
B = "92292bdd-acaf-4840-8c59-1693830fc631"


def test_parse_event_ids_accepts_space_and_comma_separated():
    assert parse_event_ids([f"{A}, {B.upper()}"]) == [A, B]
    assert parse_event_ids([A, B]) == [A, B]
    assert parse_event_ids([]) == []
    assert parse_event_ids(None) == []


def test_parse_event_ids_rejects_non_uuid():
    # Workflow input reaches the script verbatim; anything else must fail.
    with pytest.raises(ValueError):
        parse_event_ids(["abc; rm -rf /"])
    with pytest.raises(ValueError):
        parse_event_ids(["peatix_8134728"])


def _row(id_, **kw):
    base = {"id": id_, "organizer": None, "source_url": "https://peatix.com/event/1"}
    base.update(kw)
    return base


def test_select_targets_keeps_empty_unlocked_peatix_rows():
    targets, skipped = select_targets([_row(A)], set())
    assert [r["id"] for r in targets] == [A]
    assert skipped == []


def test_select_targets_skips_locked_filled_and_non_peatix():
    rows = [
        _row(A),
        _row(B, organizer="already"),
        _row("c", source_url="https://example.com/x"),
    ]
    targets, skipped = select_targets(rows, {A})
    assert targets == []
    reasons = sorted(reason for _, reason in skipped)
    assert reasons == [
        "organizer already set",
        "organizer locked in field_corrections",
        "source_url is not a Peatix page",
    ]


def test_is_blocked():
    assert is_blocked("台湾交流会 Social", ["交流会"])
    assert not is_blocked("台湾文化センター", ["交流会"])
