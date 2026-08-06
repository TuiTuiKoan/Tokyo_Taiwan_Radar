from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

import _oneoff_repair_authoritative_venues as repair
import qa_auto_fix
from test_qa_auto_fix_unlock_only import FakeSupabase


PROJECT_REF = "cjtndektjjpvvjofdvzr"
REPOSITORY_SHA = "a" * 40
EVENT_ID = "11111111-1111-4111-8111-111111111111"
EVENT_ACTION_ID = "22222222-2222-4222-8222-222222222222"
VENUE_UPDATE_ACTION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VENUE_INSERT_ACTION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
VENUE_DELETE_ACTION_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
VENUE_UPDATE_ID = "77777777-7777-4777-8777-777777777777"
VENUE_INSERT_ID = "88888888-8888-4888-8888-888888888888"
VENUE_DELETE_ID = "99999999-9999-4999-8999-999999999999"


def _fc(row_id: str, field_name: str, corrected_value: str, **overrides):
    row = {
        "id": row_id,
        "event_id": EVENT_ID,
        "field_name": field_name,
        "original_value": None,
        "corrected_value": corrected_value,
        "corrected_by": None,
        "report_id": None,
        "created_at": "2026-08-06T00:00:00+00:00",
    }
    row.update(overrides)
    return row


def _fc_image(target_fields, rows):
    ordered_fields = sorted(target_fields)
    ordered_rows = sorted(deepcopy(rows), key=repair.row_sort_key)
    present = {row["field_name"] for row in ordered_rows}
    return {
        "event_id": EVENT_ID,
        "target_fields": ordered_fields,
        "rows": ordered_rows,
        "absent_fields": sorted(set(ordered_fields) - present),
    }


def _state_image(*, event=None, venue=None, fc=None, references=None):
    return {
        "venue": deepcopy(venue),
        "event": deepcopy(event),
        "field_corrections": deepcopy(fc or repair.empty_fc_image()),
        "venue_references": sorted(references or []),
    }


def _event_action(**overrides):
    before_event = {
        "id": EVENT_ID,
        "venue_id": None,
        "location_name": "TIFF",
        "location_prefectures": ["東京都", "大阪府"],
        "submission_url": None,
        "updated_at": "2026-08-06T00:00:00+00:00",
    }
    after_event = {
        **before_event,
        "location_prefectures": ["東京都"],
    }
    target_before = _fc(
        "33333333-3333-4333-8333-333333333333",
        "location_prefectures",
        repair.fc_text(before_event["location_prefectures"]),
    )
    target_after = {
        **target_before,
        "corrected_value": repair.fc_text(after_event["location_prefectures"]),
    }
    unrelated = _fc(
        "44444444-4444-4444-8444-444444444444",
        "name_ja",
        "手動で維持する名称",
    )
    before = _state_image(
        event=before_event,
        fc=_fc_image(["location_prefectures"], [target_before, unrelated]),
    )
    after = _state_image(
        event=after_event,
        fc=_fc_image(["location_prefectures"], [target_after, unrelated]),
    )
    action = {
        "id": EVENT_ACTION_ID,
        "type": "event_fc",
        "dependencies": [],
        "eligibility": {"status": "eligible", "reason": "synthetic fixture"},
        "evidence": {"complete": True, "source": "synthetic"},
        "before": before,
        "after": after,
        "apply_expected": deepcopy(before),
        "rollback_expected": deepcopy(after),
        "apply_operations": [
            {
                "field_name": "location_prefectures",
                "mode": "lock_clean",
                "new_value": ["東京都"],
                "expected_event_value": ["東京都", "大阪府"],
                "expected_fc": deepcopy(target_before),
            }
        ],
        "rollback_operations": [
            {
                "field_name": "location_prefectures",
                "mode": "lock_clean",
                "new_value": ["東京都", "大阪府"],
                "expected_event_value": ["東京都"],
                "expected_fc": deepcopy(target_after),
            }
        ],
        "conflicts": [],
        "skips": [],
        "already_applied": [],
        "volatile_event_fields": ["updated_at"],
    }
    action.update(overrides)
    return action


def _plan(*actions):
    return {
        "project_ref": PROJECT_REF,
        "repository_sha": REPOSITORY_SHA,
        "actions": [deepcopy(action) for action in actions],
    }


def _client_for_action(action, *, event=None, fcs=None):
    return FakeSupabase(
        {
            "events": [deepcopy(event or action["before"]["event"])],
            "field_corrections": deepcopy(
                fcs if fcs is not None else action["before"]["field_corrections"]["rows"]
            ),
            "field_corrections_audit": [],
            "venues": [],
        }
    )


def _preview(client, *actions):
    return repair.preview_manifest(
        client,
        _plan(*actions),
        project_ref=PROJECT_REF,
        repo_sha_verifier=lambda _sha: True,
        captured_at="2026-08-06T00:00:00+00:00",
    )


def _venue(venue_id: str, name: str, address: str):
    return {
        "id": venue_id,
        "canonical_name_ja": name,
        "canonical_name_zh": None,
        "canonical_name_en": None,
        "aliases": [f"{name} alias"],
        "address": address,
        "homepage": f"https://{venue_id[:8]}.example/",
        "prefectures": ["東京都"],
        "is_authoritative": True,
        "is_multi_venue": False,
        "updated_at": "2026-08-06T00:00:00+00:00",
    }


def _venue_action(
    *,
    action_id: str,
    action_type: str,
    before_venue,
    after_venue,
    before_references=None,
    after_references=None,
    dependencies=None,
):
    before = _state_image(venue=before_venue, references=before_references)
    after = _state_image(venue=after_venue, references=after_references)
    return {
        "id": action_id,
        "type": action_type,
        "dependencies": list(dependencies or []),
        "eligibility": {"status": "eligible", "reason": "synthetic fixture"},
        "evidence": {"complete": True, "source": "synthetic"},
        "before": before,
        "after": after,
        "apply_expected": deepcopy(before),
        "rollback_expected": deepcopy(after),
        "apply_operations": [],
        "rollback_operations": [],
        "conflicts": [],
        "skips": [],
        "already_applied": [],
        "volatile_event_fields": [],
    }


def _unlink_action(delete_venue, *, dependencies=None):
    before_event = {
        "id": EVENT_ID,
        "venue_id": delete_venue["id"],
        "location_name": delete_venue["canonical_name_ja"],
        "location_prefectures": ["東京都"],
        "submission_url": None,
        "updated_at": "2026-08-06T00:00:00+00:00",
    }
    after_event = {**before_event, "venue_id": None}
    before_fc = _fc(
        "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        "venue_id",
        delete_venue["id"],
    )
    after_fc = {**before_fc, "corrected_value": ""}
    unrelated = _fc(
        "ffffffff-ffff-4fff-8fff-ffffffffffff",
        "name_ja",
        "保持する名称",
    )
    before = _state_image(
        event=before_event,
        fc=_fc_image(["venue_id"], [before_fc, unrelated]),
    )
    after = _state_image(
        event=after_event,
        fc=_fc_image(["venue_id"], [after_fc, unrelated]),
    )
    return {
        "id": EVENT_ACTION_ID,
        "type": "event_fc",
        "dependencies": list(dependencies or []),
        "eligibility": {"status": "eligible", "reason": "synthetic unlink"},
        "evidence": {"complete": True, "source": "synthetic"},
        "before": before,
        "after": after,
        "apply_expected": deepcopy(before),
        "rollback_expected": deepcopy(after),
        "apply_operations": [
            {
                "field_name": "venue_id",
                "mode": "lock_empty",
                "new_value": None,
                "expected_event_value": delete_venue["id"],
                "expected_fc": deepcopy(before_fc),
            }
        ],
        "rollback_operations": [
            {
                "field_name": "venue_id",
                "mode": "lock_clean",
                "new_value": delete_venue["id"],
                "expected_event_value": None,
                "expected_fc": deepcopy(after_fc),
            }
        ],
        "conflicts": [],
        "skips": [],
        "already_applied": [],
        "volatile_event_fields": ["updated_at"],
    }


def _batch_fixture():
    update_before = _venue(VENUE_UPDATE_ID, "Updated Venue", "Old address")
    update_after = {**update_before, "address": "New address"}
    insert_after = _venue(VENUE_INSERT_ID, "Inserted Venue", "Insert address")
    delete_before = _venue(VENUE_DELETE_ID, "Duplicate Venue", "Duplicate address")
    update_action = _venue_action(
        action_id=VENUE_UPDATE_ACTION_ID,
        action_type="venue_update",
        before_venue=update_before,
        after_venue=update_after,
    )
    insert_action = _venue_action(
        action_id=VENUE_INSERT_ACTION_ID,
        action_type="venue_insert",
        before_venue=None,
        after_venue=insert_after,
        dependencies=[VENUE_UPDATE_ACTION_ID],
    )
    event_action = _unlink_action(
        delete_before,
        dependencies=[VENUE_UPDATE_ACTION_ID, VENUE_INSERT_ACTION_ID],
    )
    delete_action = _venue_action(
        action_id=VENUE_DELETE_ACTION_ID,
        action_type="venue_delete",
        before_venue=delete_before,
        after_venue=None,
        before_references=[EVENT_ID],
        after_references=[],
        dependencies=[EVENT_ACTION_ID],
    )
    client = FakeSupabase(
        {
            "venues": [deepcopy(update_before), deepcopy(delete_before)],
            "events": [deepcopy(event_action["before"]["event"])],
            "field_corrections": deepcopy(
                event_action["before"]["field_corrections"]["rows"]
            ),
            "field_corrections_audit": [],
        }
    )
    actions = [update_action, insert_action, event_action, delete_action]
    return client, actions


def _journal_path(monkeypatch, tmp_path, name):
    root = tmp_path / "worktree"
    monkeypatch.setattr(repair, "ROOT", root)
    monkeypatch.setattr(repair, "_is_git_ignored", lambda _path, *, root: True)
    return root / "tmp" / "authoritative-venue-repair" / name


def _journal_entries(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _apply(client, manifest, monkeypatch, tmp_path, *, name="apply.jsonl", **kwargs):
    return repair.apply_manifest(
        client,
        manifest,
        project_ref=PROJECT_REF,
        journal_path=_journal_path(monkeypatch, tmp_path, name),
        repo_sha_verifier=lambda _sha: True,
        **kwargs,
    )


def _rollback(client, manifest, monkeypatch, tmp_path, *, name="rollback.jsonl", **kwargs):
    return repair.rollback_manifest(
        client,
        manifest,
        project_ref=PROJECT_REF,
        journal_path=_journal_path(monkeypatch, tmp_path, name),
        repo_sha_verifier=lambda _sha: True,
        **kwargs,
    )


def test_cli_modes_are_exclusive_and_default_to_read_only_preview():
    assert repair.parse_args([]).mode == "preview"
    assert repair.parse_args(["--plan", "plan.json"]).mode == "preview"
    assert repair.parse_args(
        ["--capture", "--plan", "plan.json", "--manifest-output", "tmp/manifest.json"]
    ).mode == "capture"
    assert repair.parse_args(["--apply", "--manifest", "tmp/manifest.json"]).mode == "apply"
    assert repair.parse_args(["--rollback", "--manifest", "tmp/manifest.json"]).mode == "rollback"

    with pytest.raises(SystemExit):
        repair.parse_args(["--capture", "--apply"])
    with pytest.raises(SystemExit):
        repair.parse_args(["--capture", "--plan", "plan.json"])
    with pytest.raises(SystemExit):
        repair.parse_args(["--apply"])


def test_default_cli_dispatch_is_mechanically_read_only_and_query_free():
    calls = []
    client = FakeSupabase()

    result = repair.run_cli(
        [],
        client_factory=lambda *, read_only: calls.append(read_only) or client,
        project_ref_getter=lambda: pytest.fail("default no-plan preview must not read env"),
    )

    assert calls == [True]
    assert result == {
        "mode": "preview",
        "status": "no_plan",
        "read_only": True,
        "queries": 0,
        "mutations": 0,
    }
    assert client.writes == []


def test_read_only_proxy_blocks_all_mutators_on_client_and_query_chain():
    target = SimpleNamespace()
    target.table = lambda _name: target
    target.select = lambda *_args, **_kwargs: target
    target.execute = lambda: SimpleNamespace(data=[])
    proxy = repair.ReadOnlyProxy(target)

    assert proxy.table("events").select("*").execute().data == []
    for method in repair.MUTATION_METHODS:
        with pytest.raises(RuntimeError, match=f"blocked Supabase mutation: {method}"):
            getattr(proxy, method)
        with pytest.raises(RuntimeError, match=f"blocked Supabase mutation: {method}"):
            getattr(proxy.table("events"), method)


def test_immutable_manifest_is_canonical_exclusive_and_read_only(monkeypatch, tmp_path):
    root = tmp_path / "worktree"
    output = root / "tmp" / "repair" / "manifest.json"
    monkeypatch.setattr(repair, "ROOT", root)
    monkeypatch.setattr(repair, "_is_git_ignored", lambda _path, *, root: True)
    payload = repair.seal_manifest(
        {
            "project_ref": "project-ref",
            "repository_sha": "a" * 40,
            "actions": [],
        }
    )

    written = repair.write_immutable_json(output, payload)

    assert written == output
    assert written.read_bytes() == repair.canonical_json_bytes(payload) + b"\n"
    assert stat.S_IMODE(written.stat().st_mode) == 0o444
    assert json.loads(written.read_text(encoding="utf-8")) == payload
    repair.verify_manifest(payload)
    with pytest.raises(FileExistsError):
        repair.write_immutable_json(output, payload)


def test_capture_validates_then_exclusively_writes_an_immutable_manifest(monkeypatch, tmp_path):
    action = _event_action()
    client = _client_for_action(action)
    root = tmp_path / "worktree"
    output = root / "tmp" / "repair" / "captured.json"
    monkeypatch.setattr(repair, "ROOT", root)
    monkeypatch.setattr(repair, "_is_git_ignored", lambda _path, *, root: True)

    written, manifest = repair.capture_manifest(
        client,
        _plan(action),
        output,
        project_ref=PROJECT_REF,
        repo_sha_verifier=lambda _sha: True,
        captured_at="2026-08-06T00:00:00+00:00",
    )

    assert written == output
    assert manifest["capture_mode"] == "capture-read-only"
    assert repair.load_manifest(output) == manifest
    assert stat.S_IMODE(output.stat().st_mode) == 0o444
    assert client.writes == []
    with pytest.raises(FileExistsError):
        repair.capture_manifest(
            client,
            _plan(action),
            output,
            project_ref=PROJECT_REF,
            repo_sha_verifier=lambda _sha: True,
            captured_at="2026-08-06T00:00:00+00:00",
        )


def test_artifacts_are_rejected_outside_ignored_tmp(monkeypatch, tmp_path):
    root = tmp_path / "worktree"
    monkeypatch.setattr(repair, "ROOT", root)
    monkeypatch.setattr(repair, "_is_git_ignored", lambda _path, *, root: True)

    with pytest.raises(RuntimeError, match="inside worktree tmp"):
        repair.assert_ignored_tmp_path(root / "manifest.json")
    with pytest.raises(RuntimeError, match="inside worktree tmp"):
        repair.assert_ignored_tmp_path(tmp_path / "outside" / "manifest.json")

    monkeypatch.setattr(repair, "_is_git_ignored", lambda _path, *, root: False)
    with pytest.raises(RuntimeError, match="not ignored"):
        repair.assert_ignored_tmp_path(root / "tmp" / "manifest.json")


def test_action_and_whole_manifest_digests_reject_independent_tampering():
    action = _event_action()
    manifest = _preview(_client_for_action(action), action)
    assert manifest["actions"][0]["digest"] == repair.action_digest(manifest["actions"][0])
    repair.verify_manifest(manifest)

    action_tamper = deepcopy(manifest)
    action_tamper["actions"][0]["after"]["event"]["location_name"] = "tampered"
    with pytest.raises(RuntimeError, match="action digest mismatch"):
        repair.verify_manifest(action_tamper)

    manifest_tamper = deepcopy(manifest)
    manifest_tamper["already_applied"] = [{"action_id": EVENT_ACTION_ID}]
    with pytest.raises(RuntimeError, match="manifest SHA-256 mismatch"):
        repair.verify_manifest(manifest_tamper)


def test_resealing_does_not_duplicate_derived_review_conflicts():
    action = _event_action()
    unrelated = next(
        row
        for row in action["before"]["field_corrections"]["rows"]
        if row["field_name"] == "name_ja"
    )
    unrelated["corrected_by"] = "55555555-5555-4555-8555-555555555555"
    action["after"]["field_corrections"]["rows"] = deepcopy(
        action["before"]["field_corrections"]["rows"]
    )
    action["apply_expected"] = deepcopy(action["before"])
    action["rollback_expected"] = deepcopy(action["after"])

    first = repair.seal_manifest(_plan(action))
    second = repair.seal_manifest(first)

    assert len(second["actions"][0]["conflicts"]) == 1
    repair.verify_manifest(second)


def test_preview_preserves_plan_level_conflict_and_skip_evidence():
    action = _event_action()
    plan = _plan(action)
    plan["conflicts"] = [
        {"action_id": EVENT_ACTION_ID, "type": "classifier_conflict", "evidence": "x"}
    ]
    plan["skips"] = [
        {"action_id": EVENT_ACTION_ID, "reason": "classifier_skip", "evidence": "y"}
    ]

    manifest = repair.preview_manifest(
        _client_for_action(action),
        plan,
        project_ref=PROJECT_REF,
        repo_sha_verifier=lambda _sha: True,
        captured_at="2026-08-06T00:00:00+00:00",
    )

    assert manifest["conflicts"] == plan["conflicts"]
    assert manifest["skips"] == plan["skips"]
    repair.verify_manifest(manifest)


def test_complete_before_after_and_explicit_fc_absence_are_required():
    action = _event_action()
    missing_event_column = deepcopy(action)
    missing_event_column["after"]["event"].pop("location_name")
    missing_event_column["rollback_expected"] = deepcopy(missing_event_column["after"])
    with pytest.raises(RuntimeError, match="event before/after columns differ"):
        repair.seal_manifest(_plan(missing_event_column))

    missing_fc_absence = deepcopy(action)
    missing_fc_absence["before"]["field_corrections"]["rows"] = [
        row
        for row in missing_fc_absence["before"]["field_corrections"]["rows"]
        if row["field_name"] != "location_prefectures"
    ]
    missing_fc_absence["apply_expected"] = deepcopy(missing_fc_absence["before"])
    with pytest.raises(RuntimeError, match="explicit target FC presence/absence"):
        repair.seal_manifest(_plan(missing_fc_absence))

    incomplete_fc = deepcopy(action)
    incomplete_fc["before"]["field_corrections"]["rows"][0].pop("created_at")
    incomplete_fc["apply_expected"] = deepcopy(incomplete_fc["before"])
    with pytest.raises(RuntimeError, match="field_correction row is incomplete"):
        repair.seal_manifest(_plan(incomplete_fc))


def test_generated_fc_after_state_requires_complete_database_row_shape():
    action = _sentinel_action()
    manifest = repair.seal_manifest(_plan(action))
    incomplete_sentinel = next(
        deepcopy(row)
        for row in action["after"]["field_corrections"]["rows"]
        if row["field_name"] == "location_address"
    )
    incomplete_sentinel["id"] = "field_corrections-2"
    incomplete_sentinel.pop("created_at")
    unrelated = next(
        deepcopy(row)
        for row in action["after"]["field_corrections"]["rows"]
        if row["field_name"] == "name_ja"
    )
    client = _client_for_action(
        action,
        event=action["after"]["event"],
        fcs=[incomplete_sentinel, unrelated],
    )

    with pytest.raises(RuntimeError, match="partial, third, or drifted"):
        repair.preflight_actions(client, manifest)

    assert client.writes == []


def test_preview_validates_complete_before_images_without_mutation():
    action = _event_action()
    client = _client_for_action(action)

    manifest = _preview(client, action)

    assert manifest["capture_mode"] == "preview-read-only"
    assert manifest["already_applied"] == []
    assert client.writes == []
    assert manifest["actions"][0]["before"] == action["before"]
    assert manifest["actions"][0]["after"] == action["after"]

    incomplete_live = deepcopy(action["before"]["event"])
    incomplete_live.pop("location_name")
    drifted = _client_for_action(action, event=incomplete_live)
    with pytest.raises(RuntimeError, match="partial, third, or drifted"):
        _preview(drifted, action)
    assert drifted.writes == []


def test_full_preflight_reads_all_actions_before_any_write_and_accepts_exact_after():
    action = _event_action()
    manifest = _preview(_client_for_action(action), action)
    before_client = _client_for_action(action)

    state, observations = repair.preflight_actions(before_client, manifest)

    assert state == "before"
    assert observations[EVENT_ACTION_ID]["event"] == action["before"]["event"]
    assert before_client.writes == []

    after_client = _client_for_action(
        action,
        event=action["after"]["event"],
        fcs=action["after"]["field_corrections"]["rows"],
    )
    assert repair.preflight_actions(after_client, manifest)[0] == "after"
    assert after_client.writes == []


@pytest.mark.parametrize(
    "conflict", ["target_human_fc", "unrelated_human_fc", "submission_url"]
)
def test_human_fc_and_different_nonempty_submission_are_review_conflicts(conflict):
    action = _event_action()
    if conflict != "submission_url":
        field_name = (
            "location_prefectures" if conflict == "target_human_fc" else "name_ja"
        )
        for image_name in ("before", "after"):
            target = next(
                row
                for row in action[image_name]["field_corrections"]["rows"]
                if row["field_name"] == field_name
            )
            target["corrected_by"] = "55555555-5555-4555-8555-555555555555"
        action["apply_expected"] = deepcopy(action["before"])
        action["rollback_expected"] = deepcopy(action["after"])
        if field_name == "location_prefectures":
            action["apply_operations"][0]["expected_fc"] = deepcopy(
                next(
                    row
                    for row in action["before"]["field_corrections"]["rows"]
                    if row["field_name"] == "location_prefectures"
                )
            )
            action["rollback_operations"][0]["expected_fc"] = deepcopy(
                next(
                    row
                    for row in action["after"]["field_corrections"]["rows"]
                    if row["field_name"] == "location_prefectures"
                )
            )
    else:
        action["before"]["event"]["submission_url"] = "https://existing.example/"
        action["after"]["event"]["submission_url"] = "https://replacement.example/"
        new_fc = _fc(
            None,
            "submission_url",
            "https://replacement.example/",
            created_at=None,
        )
        intermediate_fc = {
            **new_fc,
            "corrected_value": "https://existing.example/",
        }
        for image_name in ("before", "after"):
            image = action[image_name]["field_corrections"]
            image["target_fields"] = ["location_prefectures", "submission_url"]
        action["before"]["field_corrections"]["absent_fields"] = ["submission_url"]
        action["after"]["field_corrections"]["rows"] = sorted(
            [*action["after"]["field_corrections"]["rows"], new_fc],
            key=repair.row_sort_key,
        )
        action["after"]["field_corrections"]["absent_fields"] = []
        action["apply_operations"].append(
            {
                "field_name": "submission_url",
                "mode": "lock_clean",
                "new_value": "https://replacement.example/",
                "expected_event_value": "https://existing.example/",
                "expected_fc": None,
            }
        )
        action["rollback_operations"] = [
            {
                "field_name": "submission_url",
                "mode": "lock_clean",
                "new_value": "https://existing.example/",
                "expected_event_value": "https://replacement.example/",
                "expected_fc": deepcopy(new_fc),
            },
            {
                "field_name": "submission_url",
                "mode": "unlock_only",
                "new_value": None,
                "expected_event_value": "https://existing.example/",
                "expected_fc": intermediate_fc,
            },
            *action["rollback_operations"],
        ]
        action["apply_expected"] = deepcopy(action["before"])
        action["rollback_expected"] = deepcopy(action["after"])

    client = _client_for_action(action)
    manifest = _preview(client, action)

    assert manifest["actions"][0]["eligibility"]["status"] == "review_conflict"
    assert manifest["conflicts"][0]["action_id"] == EVENT_ACTION_ID
    with pytest.raises(RuntimeError, match="review_conflict"):
        repair.preflight_actions(client, manifest)
    assert client.writes == []


@pytest.mark.parametrize(
    "mutate,match",
    [
        (
            lambda client, action: client.tables["field_corrections"].append(
                _fc("66666666-6666-4666-8666-666666666666", "venue_id", "unexpected")
            ),
            "partial, third, or drifted",
        ),
        (
            lambda client, action: client.tables["events"][0].update(
                {"location_prefectures": ["北海道"]}
            ),
            "partial, third, or drifted",
        ),
        (
            lambda client, action: client.tables["events"][0].update(
                {"location_prefectures": action["after"]["event"]["location_prefectures"]}
            ),
            "partial, third, or drifted",
        ),
    ],
)
def test_extra_fc_before_drift_and_partial_event_fc_state_stop_with_zero_mutation(
    mutate, match
):
    action = _event_action()
    manifest = _preview(_client_for_action(action), action)
    client = _client_for_action(action)
    mutate(client, action)

    with pytest.raises(RuntimeError, match=match):
        repair.preflight_actions(client, manifest)

    assert client.writes == []
    assert client.tables["field_corrections_audit"] == []


@pytest.mark.parametrize("kind", ["project", "repo"])
def test_project_ref_and_repo_sha_mismatch_stop_capture_before_database_mutation(kind):
    action = _event_action()
    client = _client_for_action(action)
    project_ref = "wrong-project" if kind == "project" else PROJECT_REF
    verifier = (lambda _sha: False) if kind == "repo" else (lambda _sha: True)

    with pytest.raises(RuntimeError, match="project ref mismatch|not present in origin/main"):
        repair.preview_manifest(
            client,
            _plan(action),
            project_ref=project_ref,
            repo_sha_verifier=verifier,
        )

    assert client.writes == []


def test_full_batch_preflight_finishes_before_first_write(monkeypatch, tmp_path):
    client, actions = _batch_fixture()
    manifest = _preview(client, *actions)
    client.tables["events"][0]["location_name"] = "concurrent drift"

    with pytest.raises(RuntimeError, match="mutation_count=0"):
        _apply(client, manifest, monkeypatch, tmp_path)

    assert client.writes == []
    assert {row["id"] for row in client.tables["venues"]} == {
        VENUE_UPDATE_ID,
        VENUE_DELETE_ID,
    }


def test_eligible_action_cannot_depend_on_skipped_action(monkeypatch, tmp_path):
    venue_before = _venue(VENUE_UPDATE_ID, "Skipped Venue", "Old address")
    venue_after = {**venue_before, "address": "New address"}
    skipped = _venue_action(
        action_id=VENUE_UPDATE_ACTION_ID,
        action_type="venue_update",
        before_venue=venue_before,
        after_venue=venue_after,
    )
    skipped["eligibility"] = {"status": "skip", "reason": "synthetic skip"}
    skipped["skips"] = [{"reason": "synthetic skip"}]
    event_action = _event_action(dependencies=[VENUE_UPDATE_ACTION_ID])
    client = FakeSupabase(
        {
            "venues": [deepcopy(venue_before)],
            "events": [deepcopy(event_action["before"]["event"])],
            "field_corrections": deepcopy(
                event_action["before"]["field_corrections"]["rows"]
            ),
            "field_corrections_audit": [],
        }
    )
    manifest = _preview(client, skipped, event_action)

    with pytest.raises(RuntimeError, match="depend on non-eligible"):
        _apply(client, manifest, monkeypatch, tmp_path, name="skip-dependency.jsonl")

    assert client.writes == []


@pytest.mark.parametrize("collision", ["id", "canonical_name"])
def test_venue_insert_requires_simultaneous_id_and_canonical_name_absence(
    monkeypatch, tmp_path, collision
):
    insert_after = _venue(VENUE_INSERT_ID, "Inserted Venue", "Insert address")
    action = _venue_action(
        action_id=VENUE_INSERT_ACTION_ID,
        action_type="venue_insert",
        before_venue=None,
        after_venue=insert_after,
    )
    clean = FakeSupabase({"venues": [], "events": [], "field_corrections": []})
    manifest = _preview(clean, action)
    if collision == "id":
        live = {**insert_after, "canonical_name_ja": "Different Venue"}
    else:
        live = {
            **insert_after,
            "id": "14141414-1414-4414-8414-141414141414",
        }
    client = FakeSupabase({"venues": [live], "events": [], "field_corrections": []})

    with pytest.raises(RuntimeError, match="mutation_count=0"):
        _apply(client, manifest, monkeypatch, tmp_path, name=f"insert-{collision}.jsonl")

    assert client.writes == []


def test_reordered_actions_are_rejected_even_if_whole_digest_is_recomputed():
    client, actions = _batch_fixture()
    manifest = _preview(client, *actions)
    reordered = deepcopy(manifest)
    reordered["actions"][0], reordered["actions"][1] = (
        reordered["actions"][1],
        reordered["actions"][0],
    )
    body = {key: value for key, value in reordered.items() if key != "manifest_sha256"}
    reordered["manifest_sha256"] = repair.sha256_json(body)

    with pytest.raises(RuntimeError, match="fixed action order"):
        repair.verify_manifest(reordered)


def test_apply_inspects_helper_args_payload_order_full_cas_and_read_back(
    monkeypatch, tmp_path
):
    client, actions = _batch_fixture()
    manifest = _preview(client, *actions)
    helper_calls = []

    def recording_writer(sb, **kwargs):
        helper_calls.append(deepcopy(kwargs))
        return qa_auto_fix.unlock_and_write(sb, **kwargs)

    result = _apply(
        client,
        manifest,
        monkeypatch,
        tmp_path,
        writer=recording_writer,
    )

    assert result["status"] == "completed"
    assert result["completed_action_ids"] == [
        VENUE_UPDATE_ACTION_ID,
        VENUE_INSERT_ACTION_ID,
        EVENT_ACTION_ID,
        VENUE_DELETE_ACTION_ID,
    ]
    data_writes = [write for write in client.writes if write[0] != "field_corrections_audit"]
    assert [(table, operation) for table, operation, *_ in data_writes] == [
        ("venues", "update"),
        ("venues", "insert"),
        ("events", "update"),
        ("field_corrections", "upsert"),
        ("venues", "delete"),
    ]

    update_action, insert_action, event_action, delete_action = manifest["actions"]
    venue_update = data_writes[0]
    assert venue_update[2] == {
        key: value for key, value in update_action["after"]["venue"].items() if key != "id"
    }
    assert {column for _, column, _ in venue_update[3]} == set(
        update_action["before"]["venue"]
    )
    assert data_writes[1][2] == insert_action["after"]["venue"]
    assert data_writes[-1][2] is None
    assert {column for _, column, _ in data_writes[-1][3]} == set(
        delete_action["before"]["venue"]
    )

    assert len(helper_calls) == 1
    helper = helper_calls[0]
    expected_fc = next(
        row
        for row in event_action["before"]["field_corrections"]["rows"]
        if row["field_name"] == "venue_id"
    )
    assert helper["expected_event_value"] == VENUE_DELETE_ID
    assert helper["expected_fc"] == expected_fc
    assert helper["mode"] == "lock_empty"
    assert helper["new_value"] is None
    assert helper["dry_run"] is False

    assert _fetch_event(client, EVENT_ID)["venue_id"] is None
    assert _fetch_venue(client, VENUE_UPDATE_ID) == update_action["after"]["venue"]
    assert _fetch_venue(client, VENUE_INSERT_ID) == insert_action["after"]["venue"]
    assert _fetch_venue(client, VENUE_DELETE_ID) is None
    assert next(
        row for row in client.tables["field_corrections"] if row["field_name"] == "name_ja"
    ) == next(
        row
        for row in event_action["before"]["field_corrections"]["rows"]
        if row["field_name"] == "name_ja"
    )

    entries = _journal_entries(Path(result["journal"]))
    event_names = [entry["event"] for entry in entries]
    assert event_names.index("invariant_result") < max(
        index
        for index, entry in enumerate(entries)
        if entry["event"] == "action_start"
        and entry["action_id"] == VENUE_DELETE_ACTION_ID
    )
    assert sum(entry["event"] == "action_read_back" for entry in entries) == 4
    assert stat.S_IMODE(Path(result["journal"]).stat().st_mode) == 0o444


def _fetch_event(client, event_id):
    return next((row for row in client.tables["events"] if row["id"] == event_id), None)


def _fetch_venue(client, venue_id):
    return next((row for row in client.tables["venues"] if row["id"] == venue_id), None)


def test_array_serialization_unrelated_fc_preservation_and_helper_exact_args(
    monkeypatch, tmp_path
):
    action = _event_action()
    client = _client_for_action(action)
    manifest = _preview(client, action)
    calls = []

    def recording_writer(sb, **kwargs):
        calls.append(deepcopy(kwargs))
        return qa_auto_fix.unlock_and_write(sb, **kwargs)

    _apply(client, manifest, monkeypatch, tmp_path, writer=recording_writer)

    target = next(
        row
        for row in client.tables["field_corrections"]
        if row["field_name"] == "location_prefectures"
    )
    unrelated = next(
        row for row in client.tables["field_corrections"] if row["field_name"] == "name_ja"
    )
    assert target["corrected_value"] == '["東京都"]'
    assert unrelated == next(
        row
        for row in action["before"]["field_corrections"]["rows"]
        if row["field_name"] == "name_ja"
    )
    assert calls[0]["new_value"] == ["東京都"]
    assert calls[0]["expected_event_value"] == ["東京都", "大阪府"]
    assert calls[0]["expected_fc"]["corrected_value"] == '["東京都", "大阪府"]'


def _sentinel_action():
    before_event = {
        "id": EVENT_ID,
        "location_address": "Old address",
        "submission_url": None,
        "updated_at": "2026-08-06T00:00:00+00:00",
    }
    after_event = {**before_event, "location_address": None}
    unrelated = _fc(
        "12121212-1212-4212-8212-121212121212",
        "name_ja",
        "保持する名称",
    )
    sentinel = _fc(
        None,
        "location_address",
        "",
        created_at=None,
    )
    restored = {**sentinel, "corrected_value": "Old address"}
    before = _state_image(
        event=before_event,
        fc=_fc_image(["location_address"], [unrelated]),
    )
    after = _state_image(
        event=after_event,
        fc=_fc_image(["location_address"], [sentinel, unrelated]),
    )
    return {
        "id": EVENT_ACTION_ID,
        "type": "event_fc",
        "dependencies": [],
        "eligibility": {"status": "eligible", "reason": "synthetic sentinel"},
        "evidence": {"complete": True, "source": "synthetic"},
        "before": before,
        "after": after,
        "apply_expected": deepcopy(before),
        "rollback_expected": deepcopy(after),
        "apply_operations": [
            {
                "field_name": "location_address",
                "mode": "lock_empty",
                "new_value": None,
                "expected_event_value": "Old address",
                "expected_fc": None,
            }
        ],
        "rollback_operations": [
            {
                "field_name": "location_address",
                "mode": "lock_clean",
                "new_value": "Old address",
                "expected_event_value": None,
                "expected_fc": deepcopy(sentinel),
            },
            {
                "field_name": "location_address",
                "mode": "unlock_only",
                "new_value": None,
                "expected_event_value": "Old address",
                "expected_fc": restored,
            },
        ],
        "conflicts": [],
        "skips": [],
        "already_applied": [],
        "volatile_event_fields": ["updated_at"],
    }


def test_absent_system_fc_uses_empty_sentinel_and_rolls_back_to_explicit_absence(
    monkeypatch, tmp_path
):
    action = _sentinel_action()
    client = _client_for_action(action)
    manifest = _preview(client, action)
    calls = []

    def recording_writer(sb, **kwargs):
        calls.append(deepcopy(kwargs))
        result = qa_auto_fix.unlock_and_write(sb, **kwargs)
        for row in sb.tables["field_corrections"]:
            row.setdefault("original_value", None)
            row.setdefault("corrected_by", None)
            if row.get("created_at") is None:
                row["created_at"] = "2026-08-06T00:00:00+00:00"
        return result

    _apply(client, manifest, monkeypatch, tmp_path, writer=recording_writer)

    sentinel = next(
        row
        for row in client.tables["field_corrections"]
        if row["field_name"] == "location_address"
    )
    assert sentinel["corrected_value"] == ""
    assert calls[0]["expected_fc"] is None
    assert calls[0]["expected_event_value"] == "Old address"

    _rollback(
        client,
        manifest,
        monkeypatch,
        tmp_path,
        writer=recording_writer,
    )

    assert _fetch_event(client, EVENT_ID) == action["before"]["event"]
    assert [
        row for row in client.tables["field_corrections"] if row["field_name"] == "location_address"
    ] == []
    assert next(
        row for row in client.tables["field_corrections"] if row["field_name"] == "name_ja"
    ) == next(
        row
        for row in action["before"]["field_corrections"]["rows"]
        if row["field_name"] == "name_ja"
    )


def test_second_apply_is_all_already_applied_and_zero_mutation(monkeypatch, tmp_path):
    client, actions = _batch_fixture()
    manifest = _preview(client, *actions)
    _apply(client, manifest, monkeypatch, tmp_path, name="first.jsonl")
    writes_after_first = deepcopy(client.writes)

    second = _apply(client, manifest, monkeypatch, tmp_path, name="second.jsonl")

    assert second["status"] == "noop"
    assert second["mutation_count"] == 0
    assert client.writes == writes_after_first
    statuses = [
        entry["details"].get("status")
        for entry in _journal_entries(Path(second["journal"]))
        if entry["event"] == "action_result"
    ]
    assert statuses == ["already_applied"] * 4


def test_rollback_runs_exact_reverse_action_order(monkeypatch, tmp_path):
    client, actions = _batch_fixture()
    manifest = _preview(client, *actions)
    _apply(client, manifest, monkeypatch, tmp_path, name="apply-before-rollback.jsonl")
    before_rollback_writes = len(client.writes)

    result = _rollback(client, manifest, monkeypatch, tmp_path)

    starts = [
        entry["action_id"]
        for entry in _journal_entries(Path(result["journal"]))
        if entry["event"] == "action_start"
    ]
    assert starts == [
        VENUE_DELETE_ACTION_ID,
        EVENT_ACTION_ID,
        VENUE_INSERT_ACTION_ID,
        VENUE_UPDATE_ACTION_ID,
    ]
    rollback_data_writes = [
        write
        for write in client.writes[before_rollback_writes:]
        if write[0] != "field_corrections_audit"
    ]
    assert [(table, operation) for table, operation, *_ in rollback_data_writes] == [
        ("venues", "insert"),
        ("events", "update"),
        ("field_corrections", "upsert"),
        ("venues", "delete"),
        ("venues", "update"),
    ]
    assert repair.preflight_actions(client, manifest)[0] == "before"


def test_live_reference_delete_guard_preserves_partial_state_and_failed_journal(
    monkeypatch, tmp_path
):
    client, actions = _batch_fixture()
    manifest = _preview(client, *actions)
    journal_path = _journal_path(monkeypatch, tmp_path, "failed.jsonl")

    def concurrent_reference(sb, manifest_arg):
        repair.verify_predelete_invariants(sb, manifest_arg)
        sb.tables["events"].append(
            {
                "id": "13131313-1313-4313-8313-131313131313",
                "venue_id": VENUE_DELETE_ID,
            }
        )

    with pytest.raises(RuntimeError, match="automatic rollback disabled"):
        repair.apply_manifest(
            client,
            manifest,
            project_ref=PROJECT_REF,
            journal_path=journal_path,
            repo_sha_verifier=lambda _sha: True,
            invariant_verifier=concurrent_reference,
        )

    assert _fetch_venue(client, VENUE_UPDATE_ID) == manifest["actions"][0]["after"]["venue"]
    assert _fetch_venue(client, VENUE_INSERT_ID) is not None
    assert _fetch_event(client, EVENT_ID)["venue_id"] is None
    assert _fetch_venue(client, VENUE_DELETE_ID) is not None
    entries = _journal_entries(journal_path)
    assert any(
        entry["event"] == "action_error"
        and entry["action_id"] == VENUE_DELETE_ACTION_ID
        for entry in entries
    )
    assert entries[-1]["details"]["status"] == "failed"
    assert entries[-1]["details"]["automatic_rollback"] is False
    assert entries[-1]["details"]["mutation_count"] == 3
    assert stat.S_IMODE(journal_path.stat().st_mode) == 0o444


@pytest.mark.parametrize("mismatch", ["project", "repo", "digest"])
def test_apply_identity_and_digest_mismatch_are_zero_mutation_with_preserved_journal(
    monkeypatch, tmp_path, mismatch
):
    client, actions = _batch_fixture()
    manifest = _preview(client, *actions)
    project_ref = "wrong-project" if mismatch == "project" else PROJECT_REF
    verifier = (lambda _sha: False) if mismatch == "repo" else (lambda _sha: True)
    if mismatch == "digest":
        manifest["actions"][0]["after"]["venue"]["address"] = "tampered"
    journal_path = _journal_path(monkeypatch, tmp_path, f"{mismatch}.jsonl")

    with pytest.raises(RuntimeError, match="mutation_count=0"):
        repair.apply_manifest(
            client,
            manifest,
            project_ref=project_ref,
            journal_path=journal_path,
            repo_sha_verifier=verifier,
        )

    assert client.writes == []
    entries = _journal_entries(journal_path)
    assert entries[-1]["details"]["status"] == "failed"
    assert entries[-1]["details"]["mutation_count"] == 0