"""Offline contract tests for the citation-safety join, the restore script, and
the rehearsal production guard.

The cleanup clears `location_name`, which for the NDL cohort is the only
structured copy of the journal citation. These cases prove the cleanup cannot be
generated without the B1 artifact, and that a row B1 could not prove safe never
reaches an apply phase.
"""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

import _oneoff_backfill_ndl_container_title as b1
import _oneoff_backfill_publication_metadata as manifest
import _oneoff_restore_publication_snapshot as restore_cli
from test_publication_manifest import _apply, _candidate, _event, _fake_db, _fc, _state

SAFE_ID = "aaaaaaaa-1111-4111-8111-111111111111"
UNSAFE_ID = "bbbbbbbb-2222-4222-8222-222222222222"
PENDING_ID = "cccccccc-3333-4333-8333-333333333333"
UNAVAILABLE_ID = "dddddddd-4444-4444-8444-444444444444"
UNKNOWN_ID = "eeeeeeee-5555-4555-8555-555555555555"

REHEARSAL_URL = "https://abcdefghijklmnopqrst.supabase.co"
# Literal, never derived from the module under test: a mistyped or mutated
# PRODUCTION_PROJECT_REF must fail here rather than agree with itself.
PRODUCTION_REF = "cjtndektjjpvvjofdvzr"
PRODUCTION_URL = f"https://{PRODUCTION_REF}.supabase.co"


def _artifact(
    tmp_path,
    *,
    safe=(),
    pending_apply=(),
    confirm_per_row=(),
    unsafe=(),
    name="b1-journal.json",
):
    payload = {
        "schema": {"name": "tokyo-taiwan-radar/ndl-container-title-journal", "version": 1},
        "digest_field": "journal_sha256",
        "stage": "journal",
        "citation_safety_sets": {
            "safe": list(safe),
            "pending_apply": list(pending_apply),
            "confirm_per_row": list(confirm_per_row),
            "unsafe": list(unsafe),
        },
    }
    payload["journal_sha256"] = manifest.sha256(payload)
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _polluted_fc(event_id: str):
    return _fc(
        f"fc-{event_id[:4]}", event_id, "location_name", manifest.PUBLICATION_CHANNEL_LOCATION
    )


def _cohort_state():
    ids = [SAFE_ID, UNSAFE_ID, PENDING_ID, UNAVAILABLE_ID, UNKNOWN_ID]
    return _state(
        [_event(event_id) for event_id in ids],
        field_corrections=[_polluted_fc(event_id) for event_id in ids],
    )


def _joined(tmp_path, *, confirmed=()):
    return manifest.build_manifest(
        _cohort_state(),
        citation_safety=manifest.load_citation_safety(
            _artifact(
                tmp_path,
                safe=[SAFE_ID],
                unsafe=[UNSAFE_ID],
                pending_apply=[PENDING_ID],
                confirm_per_row=[UNAVAILABLE_ID],
            )
        ),
        confirmed_unavailable=confirmed,
    )


# --- the generator refuses to run without the join ------------------------


def test_cleanup_generation_requires_the_citation_safety_artifact():
    with pytest.raises(SystemExit):
        manifest.parse_args(["--scope", "cleanup"])


def test_eslite_scope_still_generates_without_it():
    assert manifest.parse_args(["--scope", "eslite-identity"]).citation_safety is None


def test_confirm_unavailable_is_only_accepted_with_the_artifact():
    with pytest.raises(SystemExit):
        manifest.parse_args(["--scope", "cleanup", "--confirm-unavailable", UNAVAILABLE_ID])


def test_citation_safety_is_rejected_on_the_apply_side():
    with pytest.raises(SystemExit):
        manifest.parse_args(
            [
                "--apply",
                "--manifest",
                "m.json",
                "--apply-phase",
                "fc-remove",
                "--target",
                "rehearsal",
                "--citation-safety",
                "b1.json",
            ]
        )


def test_an_unjoined_cleanup_manifest_is_never_written(tmp_path):
    unjoined = manifest.build_manifest(_cohort_state())
    assert unjoined["citation_safety_join"]["performed"] is False
    with pytest.raises(RuntimeError, match="requires the B1 citation-safety artifact"):
        manifest.write_manifest(tmp_path / "wave1.json", unjoined)


def test_a_joined_cleanup_manifest_is_written(tmp_path, monkeypatch):
    written = []
    monkeypatch.setattr(manifest, "assert_ignored_output_path", lambda path: path)
    monkeypatch.setattr(manifest, "write_immutable_json", lambda _p, payload: written.append(payload))
    manifest.write_manifest(tmp_path / "wave1.json", _joined(tmp_path))
    assert written[0]["citation_safety_join"]["performed"] is True


# --- artifact loading -----------------------------------------------------


def test_a_tampered_artifact_is_refused(tmp_path):
    path = _artifact(tmp_path, safe=[SAFE_ID])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["citation_safety_sets"]["safe"].append(UNSAFE_ID)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RuntimeError, match="digest mismatch"):
        manifest.load_citation_safety(path)


def test_an_unrelated_json_is_not_accepted_as_an_artifact(tmp_path):
    path = tmp_path / "other.json"
    path.write_text(json.dumps({"schema": {"name": "something-else"}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="not a citation-safety artifact"):
        manifest.load_citation_safety(path)


def test_the_real_b1_journal_loads_through_the_join_loader(tmp_path):
    plan = b1.build_plan(
        [],
        [],
        description_field_corrections={"row_count": 0, "sha256": manifest.sha256([])},
    )
    journal = b1.build_journal(
        plan, [], description_field_corrections_after=plan["description_field_correction_digest"]
    )
    path = tmp_path / "real-journal.json"
    path.write_text(json.dumps(journal, ensure_ascii=False), encoding="utf-8")

    loaded = manifest.load_citation_safety(path)
    assert loaded["digest"] == journal["journal_sha256"]
    assert set(loaded["sets"]) == set(manifest.CITATION_SAFETY_SETS)


# --- the join itself ------------------------------------------------------


def test_only_provably_safe_rows_survive_the_join(tmp_path):
    result = _joined(tmp_path)
    included = {
        candidate["event_id"]
        for candidate in result["candidates"]
        if candidate["action_type"] == "pure_cleanup"
    }
    assert included == {SAFE_ID, UNKNOWN_ID}


@pytest.mark.parametrize("event_id", [UNSAFE_ID, PENDING_ID, UNAVAILABLE_ID])
def test_each_unproven_row_is_excluded_with_a_recorded_reason(tmp_path, event_id):
    result = _joined(tmp_path)
    candidate = _candidate(result, event_id)
    assert candidate["action_type"] == "excluded"
    assert [conflict["type"] for conflict in candidate["conflicts"]] == ["citation_unsafe"]
    assert event_id in result["citation_safety_join"]["excluded_event_ids"]
    assert candidate["excluded_reason"].startswith("citation safety ")


def test_an_unavailable_row_joins_only_after_explicit_confirmation(tmp_path):
    result = _joined(tmp_path, confirmed=[UNAVAILABLE_ID])
    assert _candidate(result, UNAVAILABLE_ID)["action_type"] == "pure_cleanup"
    assert result["citation_safety_join"]["confirmed_unavailable"] == [UNAVAILABLE_ID]


def test_a_row_outside_the_b1_cohort_is_untouched_by_the_join(tmp_path):
    result = _joined(tmp_path)
    assert _candidate(result, UNKNOWN_ID)["action_type"] == "pure_cleanup"
    assert UNKNOWN_ID not in result["citation_safety_join"]["excluded_event_ids"]


def test_the_summary_records_both_sides_of_the_join(tmp_path):
    summary = _joined(tmp_path)["summary"]
    assert summary["pure_candidates_before_citation_join"] == 5
    assert summary["cleanup_candidates_after_citation_join"] == 2
    assert summary["excluded_citation_unsafe"] == 3


def test_the_manifest_records_the_artifact_digest_it_was_joined_to(tmp_path):
    path = _artifact(tmp_path, safe=[SAFE_ID], unsafe=[UNSAFE_ID], name="digest.json")
    loaded = manifest.load_citation_safety(path)
    result = manifest.build_manifest(_cohort_state(), citation_safety=loaded)
    artifact = result["citation_safety_join"]["artifact"]
    assert artifact["digest"] == loaded["digest"]
    assert artifact["set_sizes"] == {"safe": 1, "pending_apply": 0, "confirm_per_row": 0, "unsafe": 1}


# --- an excluded id never reaches an apply phase --------------------------


@pytest.mark.parametrize("apply_phase", ["fc-remove", "event-clear"])
def test_an_excluded_id_is_never_selected_by_any_apply_phase(tmp_path, apply_phase):
    result = _joined(tmp_path)
    selected = {
        candidate["event_id"] for candidate in manifest.phase_candidates(result, apply_phase)
    }
    assert selected == {SAFE_ID, UNKNOWN_ID}


def test_an_excluded_row_is_untouched_by_the_real_apply_phases(monkeypatch, tmp_path):
    state = _cohort_state()
    result = manifest.build_manifest(
        state,
        citation_safety=manifest.load_citation_safety(
            _artifact(tmp_path, safe=[SAFE_ID], unsafe=[UNSAFE_ID])
        ),
    )
    sb = _fake_db(state)
    before = deepcopy(next(row for row in sb.tables["events"] if row["id"] == UNSAFE_ID))

    for apply_phase in ("fc-remove", "event-clear"):
        outcome = _apply(monkeypatch, tmp_path, sb, result, apply_phase)
        assert outcome["applied_total"] > 0
        assert UNSAFE_ID not in outcome["applied_event_ids"]
    assert next(row for row in sb.tables["events"] if row["id"] == UNSAFE_ID) == before


def test_an_excluded_row_keeps_its_field_corrections(monkeypatch, tmp_path):
    lock = _polluted_fc(UNSAFE_ID)
    state = _state(
        [_event(SAFE_ID), _event(UNSAFE_ID)],
        field_corrections=[_polluted_fc(SAFE_ID), lock],
    )
    result = manifest.build_manifest(
        state,
        citation_safety=manifest.load_citation_safety(
            _artifact(tmp_path, safe=[SAFE_ID], unsafe=[UNSAFE_ID])
        ),
    )
    sb = _fake_db(state)
    _apply(monkeypatch, tmp_path, sb, result, "fc-remove")
    assert [row for row in sb.tables["field_corrections"] if row["event_id"] == UNSAFE_ID] == [lock]


# --- apply re-verifies the join from the manifest itself ------------------


def _legacy_manifest(tmp_path):
    """A cleanup manifest from before the join shipped: the block never existed."""
    stale = _joined(tmp_path)
    stale.pop("citation_safety_join")
    return stale


@pytest.mark.parametrize("apply_phase", ["fc-remove", "event-clear"])
def test_a_manifest_predating_the_join_is_refused_by_apply(monkeypatch, tmp_path, apply_phase):
    sb = _fake_db(_cohort_state())
    with pytest.raises(RuntimeError, match="no completed citation-safety join"):
        _apply(
            monkeypatch,
            tmp_path,
            sb,
            _legacy_manifest(tmp_path),
            apply_phase,
            stamp_citation_join=False,
        )
    assert sb.writes == []


@pytest.mark.parametrize("apply_phase", ["fc-remove", "event-clear"])
def test_an_unjoined_manifest_that_never_passed_write_manifest_is_refused(
    monkeypatch, tmp_path, apply_phase
):
    unjoined = manifest.build_manifest(_cohort_state())
    assert unjoined["citation_safety_join"]["performed"] is False
    sb = _fake_db(_cohort_state())
    with pytest.raises(RuntimeError, match="no completed citation-safety join"):
        _apply(monkeypatch, tmp_path, sb, unjoined, apply_phase, stamp_citation_join=False)
    assert sb.writes == []


def test_a_join_claiming_an_unrecognised_artifact_is_refused(monkeypatch, tmp_path):
    forged = _joined(tmp_path)
    forged["citation_safety_join"]["artifact"]["schema"] = {"name": "something-else"}
    sb = _fake_db(_cohort_state())
    with pytest.raises(RuntimeError, match="unrecognised artifact schema"):
        _apply(monkeypatch, tmp_path, sb, forged, "fc-remove", stamp_citation_join=False)
    assert sb.writes == []


@pytest.mark.parametrize("apply_phase", ["fc-remove", "event-clear"])
def test_an_excluded_id_inside_the_candidate_set_is_refused(monkeypatch, tmp_path, apply_phase):
    tampered = _joined(tmp_path)
    tampered["citation_safety_join"]["excluded_event_ids"][SAFE_ID] = "citation safety unsafe"
    sb = _fake_db(_cohort_state())
    with pytest.raises(RuntimeError, match="citation-unsafe rows reached"):
        _apply(monkeypatch, tmp_path, sb, tampered, apply_phase, stamp_citation_join=False)
    assert sb.writes == []


def test_a_correctly_joined_manifest_still_applies(monkeypatch, tmp_path):
    state = _cohort_state()
    result = _joined(tmp_path)
    sb = _fake_db(state)
    for apply_phase in ("fc-remove", "event-clear"):
        outcome = _apply(
            monkeypatch, tmp_path, sb, result, apply_phase, stamp_citation_join=False
        )
        assert sorted(outcome["applied_event_ids"]) == sorted([SAFE_ID, UNKNOWN_ID])


# --- rehearsal production guard -------------------------------------------


def test_project_ref_is_resolved_from_the_supabase_url():
    assert manifest.PRODUCTION_PROJECT_REF == PRODUCTION_REF
    assert manifest.resolve_project_ref(PRODUCTION_URL) == PRODUCTION_REF
    assert manifest.resolve_project_ref(REHEARSAL_URL) == "abcdefghijklmnopqrst"


def test_a_rehearsal_refuses_the_production_project_ref():
    with pytest.raises(RuntimeError, match="production project ref"):
        manifest.assert_non_production_target(PRODUCTION_URL)


def test_a_rehearsal_accepts_a_disposable_target():
    assert manifest.assert_non_production_target(REHEARSAL_URL) == "abcdefghijklmnopqrst"


def test_an_unresolvable_target_is_refused_rather_than_assumed_safe():
    with pytest.raises(RuntimeError, match="cannot resolve a Supabase project ref"):
        manifest.assert_non_production_target("postgresql://localhost:5432/postgres")


# --- the manifest executor's own apply target ------------------------------


def test_an_apply_must_declare_its_target():
    with pytest.raises(SystemExit):
        manifest.parse_args(["--apply", "--manifest", "m.json", "--apply-phase", "fc-remove"])


def test_a_target_is_only_accepted_with_apply():
    with pytest.raises(SystemExit):
        manifest.parse_args(["--scope", "eslite-identity", "--target", "rehearsal"])


def test_a_declared_apply_target_reaches_the_namespace():
    args = manifest.parse_args(
        ["--apply", "--manifest", "m.json", "--apply-phase", "fc-remove", "--target", "rehearsal"]
    )
    assert args.target == "rehearsal"


def test_a_rehearsal_apply_refuses_the_production_project_ref():
    with pytest.raises(RuntimeError, match="production project ref"):
        manifest.assert_apply_target("rehearsal", PRODUCTION_URL)


def test_a_rehearsal_apply_accepts_a_disposable_target():
    assert manifest.assert_apply_target("rehearsal", REHEARSAL_URL) == "abcdefghijklmnopqrst"


def test_a_rehearsal_apply_refuses_a_missing_env(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="cannot resolve a Supabase project ref"):
        manifest.assert_apply_target("rehearsal")


def test_a_production_apply_is_an_explicit_choice_rather_than_a_refusal():
    assert manifest.assert_apply_target("production", PRODUCTION_URL) == PRODUCTION_REF


def test_a_production_declaration_that_lands_elsewhere_is_refused():
    with pytest.raises(RuntimeError, match="not the production project ref"):
        manifest.assert_apply_target("production", REHEARSAL_URL)


def test_an_undeclared_target_is_refused_by_the_guard_itself():
    with pytest.raises(RuntimeError, match="requires --target"):
        manifest.assert_apply_target("", REHEARSAL_URL)


def test_the_executor_runs_the_target_guard_before_touching_the_manifest(monkeypatch, tmp_path):
    reached = []
    monkeypatch.setenv("SUPABASE_URL", PRODUCTION_URL)
    monkeypatch.setattr(
        "sys.argv",
        [
            "_oneoff_backfill_publication_metadata.py",
            "--apply",
            "--manifest",
            str(tmp_path / "m.json"),
            "--apply-phase",
            "fc-remove",
            "--target",
            "rehearsal",
        ],
    )
    monkeypatch.setattr(manifest, "get_supabase", lambda **_kwargs: object())
    monkeypatch.setattr(manifest, "load_manifest", lambda _path: reached.append("load"))
    monkeypatch.setattr(manifest, "apply_manifest", lambda *a, **k: reached.append("apply"))

    with pytest.raises(RuntimeError, match="production project ref"):
        manifest.main()
    assert reached == []


# --- restore script -------------------------------------------------------


def _snapshot_payload(events, field_corrections):
    payload = {
        "schema": {"name": f"{manifest.SCHEMA_NAME}/rollback", "version": 2},
        "generated_at": "2026-08-10T00:00:00+00:00",
        "manifest_sha256": "a" * 64,
        "apply_phase": "fc-remove",
        "checkpoint": "fc-remove.before",
        "checkpoint_sha256": "b" * 64,
        "observed": {
            "events": [manifest.checkpoint_event_row(row) for row in events],
            "target_field_corrections": deepcopy(field_corrections),
            "preserve_field_corrections": [],
        },
        "rollback_contract": {
            "restore_order": ["events", "field_corrections"],
            "delete_new_field_corrections_before_restore": True,
            "upsert_conflict_keys": {
                "events": ["id"],
                "field_corrections": ["event_id", "field_name"],
            },
            "read_back_every_row": True,
        },
    }
    payload["snapshot_sha256"] = manifest.sha256(payload)
    return payload


def _snapshot_file(tmp_path, payload, name="snapshot.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_a_tampered_snapshot_is_refused(tmp_path):
    payload = _snapshot_payload([_event(SAFE_ID)], [])
    payload["observed"]["events"][0]["price_info"] = "0円"
    with pytest.raises(RuntimeError, match="snapshot digest mismatch"):
        restore_cli.load_snapshot(_snapshot_file(tmp_path, payload))


def test_a_snapshot_without_a_usable_contract_is_refused(tmp_path):
    payload = _snapshot_payload([_event(SAFE_ID)], [])
    payload["rollback_contract"].pop("upsert_conflict_keys")
    payload.pop("snapshot_sha256")
    payload["snapshot_sha256"] = manifest.sha256(payload)
    with pytest.raises(RuntimeError, match="no usable rollback contract"):
        restore_cli.load_snapshot(_snapshot_file(tmp_path, payload, name="contract.json"))


def test_the_executor_snapshot_shape_is_what_the_restore_consumes(tmp_path, monkeypatch):
    state = _state([_event(SAFE_ID)])
    result = manifest.build_manifest(
        state,
        citation_safety=manifest.load_citation_safety(_artifact(tmp_path, safe=[SAFE_ID])),
    )
    sb = _fake_db(state)
    snapshot = manifest.phase_snapshot_payload(sb, result, "fc-remove")

    rows = restore_cli.snapshot_rows(snapshot)
    assert [row["id"] for row in rows["events"]] == [SAFE_ID]
    assert restore_cli.load_snapshot(_snapshot_file(tmp_path, snapshot, name="real.json"))


def test_a_dry_run_plans_the_restore_without_writing(tmp_path):
    created = _fc("fc-new", SAFE_ID, "location_name", "")
    snapshot = restore_cli.load_snapshot(
        _snapshot_file(tmp_path, _snapshot_payload([_event(SAFE_ID)], []))
    )
    sb = _fake_db(_state([_event(SAFE_ID, price_info="drifted")]), extra_field_corrections=[created])

    result = restore_cli.restore(sb, snapshot, apply=False)
    assert result["planned_deletes"] == ["fc-new"]
    assert result["planned_restores"] == {"events": 1, "field_corrections": 0}
    assert sb.writes == []
    assert sb.tables["events"][0]["price_info"] == "drifted"


def test_phase_created_target_corrections_are_deleted_before_the_restore(tmp_path):
    kept = _fc("fc-kept", SAFE_ID, "location_address", "元の住所")
    created = _fc("fc-new", SAFE_ID, "location_name", "")
    untouched = _fc("fc-other", SAFE_ID, "description_ja", "locked")
    snapshot = restore_cli.load_snapshot(
        _snapshot_file(tmp_path, _snapshot_payload([_event(SAFE_ID)], [kept]))
    )
    sb = _fake_db(
        _state([_event(SAFE_ID)]), extra_field_corrections=[kept, created, untouched]
    )

    result = restore_cli.restore(sb, snapshot, apply=True)
    assert result["deleted"] == 1
    remaining = sorted(row["id"] for row in sb.tables["field_corrections"])
    assert remaining == ["fc-kept", "fc-other"]


def test_restore_puts_back_a_cleared_event_and_reads_every_row_back(tmp_path):
    lock = _fc("fc-kept", SAFE_ID, "location_address", "元の住所")
    snapshot = restore_cli.load_snapshot(
        _snapshot_file(tmp_path, _snapshot_payload([_event(SAFE_ID)], [lock]))
    )
    cleared = _event(SAFE_ID, location_name=None, location_address=None, location_prefectures=None)
    sb = _fake_db(_state([cleared]))

    result = restore_cli.restore(sb, snapshot, apply=True)
    assert result["restored"] == {"events": 1, "field_corrections": 1}
    assert result["read_back_mismatches"] == []
    restored = sb.tables["events"][0]
    assert restored["location_name"] == _event(SAFE_ID)["location_name"]
    assert restored["location_prefectures"] == ["東京都"]


def test_a_restore_that_did_not_land_is_reported_rather_than_assumed(tmp_path):
    sb = _fake_db(_state([_event(SAFE_ID, price_info="still wrong")]))
    mismatches = restore_cli.read_back_mismatches(
        sb, "events", [manifest.checkpoint_event_row(_event(SAFE_ID))], ["id"]
    )
    assert len(mismatches) == 1
    assert "price_info" in mismatches[0]["reason"]


def test_a_missing_row_is_reported_rather_than_assumed(tmp_path):
    sb = _fake_db(_state([]))
    mismatches = restore_cli.read_back_mismatches(
        sb, "events", [manifest.checkpoint_event_row(_event(SAFE_ID))], ["id"]
    )
    assert mismatches[0]["reason"] == "missing after restore"


def test_an_unsupported_restore_table_is_refused(tmp_path):
    payload = _snapshot_payload([_event(SAFE_ID)], [])
    payload["rollback_contract"]["restore_order"] = ["organizers", "events"]
    payload.pop("snapshot_sha256")
    payload["snapshot_sha256"] = manifest.sha256(payload)
    snapshot = restore_cli.load_snapshot(_snapshot_file(tmp_path, payload, name="unsupported.json"))
    with pytest.raises(RuntimeError, match="unsupported tables"):
        restore_cli.restore(_fake_db(_state([_event(SAFE_ID)])), snapshot, apply=False)


def test_the_restore_cli_forces_an_explicit_target_choice():
    with pytest.raises(SystemExit):
        restore_cli.parse_args(["--snapshot", "snap.json"])
    assert restore_cli.parse_args(
        ["--snapshot", "snap.json", "--target", "rehearsal"]
    ).apply is False
