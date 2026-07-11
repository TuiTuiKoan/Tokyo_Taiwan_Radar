from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import _oneoff_backfill_publication_metadata as manifest


def _event(event_id: str, **overrides):
    row = {
        "id": event_id,
        "source_name": "hanmoto",
        "source_id": f"source-{event_id}",
        "source_url": f"https://example.test/{event_id}",
        "official_url": None,
        "updated_at": "2026-07-11T00:00:00+00:00",
        "event_form": ["publication"],
        "category": ["books_media"],
        "is_active": True,
        "name_ja": "[新刊出版] 本",
        "name_zh": "[新刊出版] 書",
        "name_en": "[New Release] Book",
        "organizer": "架空出版社",
        "organizer_id": None,
        "organizer_url": None,
        "location_name": "新刊のご購入は各販売チャネルでお願いします",
        "location_address": "新刊のご購入は各販売チャネルでお願いします",
        "location_address_zh": "新書購買請洽各通路",
        "location_address_en": "Please check each sales channel to purchase this new book.",
        "business_hours": "新刊のご購入は各販売チャネルでお願いします",
        "business_hours_zh": "新書購買請洽各通路",
        "business_hours_en": "Please check each sales channel to purchase this new book.",
        "location_prefectures": ["東京都"],
        "location_url": "https://venue.example.test/",
        "image_url": "https://images.example.test/cover.jpg",
        "start_date": "2026-01-01T00:00:00+00:00",
        "end_date": "2026-01-01T00:00:00+00:00",
        "price_info": "2,200円",
        "annotation_status": "annotated",
    }
    row.update(overrides)
    return row


def _state(events, field_corrections=None, event_reports=None, organizers=None):
    tables = {
        "events": sorted(events, key=manifest.row_sort_key),
        "field_corrections": sorted(field_corrections or [], key=manifest.row_sort_key),
        "event_reports": sorted(event_reports or [], key=manifest.row_sort_key),
        "organizers": sorted(organizers or [], key=manifest.row_sort_key),
    }
    exact = {name: len(rows) for name, rows in tables.items()}
    base = {
        "exact_counts": exact,
        "fetched_counts": exact,
        "table_hashes": {name: manifest.sha256(rows) for name, rows in tables.items()},
    }
    return {"tables": tables, "fingerprint": {**base, "sha256": manifest.sha256(base)}}


def _candidate(result, event_id):
    return next(row for row in result["candidates"] if row["event_id"] == event_id)


def _poster_pollution_fixture():
    events = []
    field_corrections = []
    for index, (event_id, expected) in enumerate(manifest.POSTER_POLLUTION_REPAIRS.items()):
        publisher = expected.get("publisher")
        events.append(
            _event(
                event_id,
                source_name=expected["source_name"],
                source_id=expected["source_id"],
                image_url="https://www.hanmoto.com/bd/img/noimage.jpg?cache=1",
                location_name=manifest.POSTER_POLLUTION_LOCATION,
                start_date=manifest.POSTER_POLLUTION_START_DATE,
                end_date=(
                    "2026-09-15T00:00:00+00:00"
                    if expected["date_evidence"] == "same_isbn_source"
                    else expected["clean_start_date"]
                ),
                organizer=manifest.POSTER_POLLUTION_ORGANIZER if publisher else "既存出版社",
            )
        )
        created = f"2026-06-26T04:{index:02d}:00+00:00"
        for suffix, (field, value) in enumerate(
            (
                ("start_date", manifest.POSTER_POLLUTION_START_DATE),
                ("location_name", manifest.POSTER_POLLUTION_LOCATION),
            )
        ):
            field_corrections.append(
                {
                    "id": f"fc-{event_id}-{field}",
                    "event_id": event_id,
                    "field_name": field,
                    "original_value": None,
                    "corrected_value": json.dumps(value, ensure_ascii=False),
                    "created_at": created.replace("00+00:00", f"0{suffix}+00:00"),
                    "report_id": None,
                }
            )
        if publisher:
            field_corrections.append(
                {
                    "id": f"fc-{event_id}-organizer",
                    "event_id": event_id,
                    "field_name": "organizer",
                    "original_value": None,
                    "corrected_value": json.dumps(
                        manifest.POSTER_POLLUTION_ORGANIZER,
                        ensure_ascii=False,
                    ),
                    "created_at": "2026-07-03T04:00:00+00:00",
                    "report_id": None,
                }
            )
    peer = _event(
        "same-isbn-peer",
        source_name="hanmoto",
        source_id="hanmoto_9784816379222",
        start_date="2026-09-14T00:00:00+00:00",
        end_date="2026-09-14T00:00:00+00:00",
        location_name=manifest.PUBLICATION_CHANNEL_LOCATION,
    )
    events.append(peer)
    return events, field_corrections


def test_manifest_uses_exact_helper_and_excludes_mixed_and_physical_location():
    pure = _event("pure")
    mixed = _event("mixed", event_form=["publication", "lecture"], is_active=False)
    venue = _event("venue", location_name="丸善丸の内本店")
    result = manifest.build_manifest(_state([pure, mixed, venue]), generated_at="2026-07-11T00:00:00+00:00")

    assert _candidate(result, "pure")["action_type"] == "pure_cleanup"
    assert _candidate(result, "mixed")["action_type"] == "excluded"
    assert _candidate(result, "mixed")["classification"]["exact_pure_helper"] is False
    assert _candidate(result, "venue")["excluded_reason"].startswith("location_name has physical")
    assert result["summary"]["included_pure"] == 1
    assert result["summary"]["excluded_mixed"] == 1
    assert result["summary"]["excluded_location_conflict"] == 1
    assert result["summary"]["inactive_mixed_exclusions"] == 1


def test_exact_eight_poster_signature_repairs_before_pure_cleanup_with_zero_blockers():
    events, corrections = _poster_pollution_fixture()
    result = manifest.build_manifest(
        _state(events, field_corrections=corrections),
        generated_at="2026-07-11T00:00:00+00:00",
    )

    repaired_ids = {
        candidate["event_id"]
        for candidate in result["candidates"]
        if candidate.get("poster_pollution_repair", {}).get("status") == "planned"
    }
    assert repaired_ids == set(manifest.POSTER_POLLUTION_REPAIRS)
    assert result["summary"]["poster_placeholder_pollution_repair_actions"] == 8
    assert result["summary"]["unresolved_non_eslite_location_conflicts"] == 0

    for event_id, expected in manifest.POSTER_POLLUTION_REPAIRS.items():
        candidate = _candidate(result, event_id)
        assert candidate["action_type"] == "pure_cleanup"
        assert candidate["pre_actions"][0]["ordering"] == "before_pure_cleanup"
        assert candidate["event_after"]["location_name"] == manifest.PUBLICATION_CHANNEL_LOCATION
        assert candidate["event_after"]["start_date"] == expected["clean_start_date"]
        if expected.get("publisher"):
            assert candidate["event_after"]["organizer"] == expected["publisher"]
        pre_fields = [
            action["field_name"]
            for action in candidate["field_correction_actions"]
            if action["phase"] == "poster_placeholder_pollution_repair"
        ]
        assert pre_fields[:2] == ["location_name", "start_date"]
        assert all(
            candidate["event_after"][field] is None
            for field in manifest.PUBLICATION_NULL_FIELDS
        )


def test_poster_repair_near_miss_remains_conflict_without_source_blanket():
    events, corrections = _poster_pollution_fixture()
    target = next(iter(manifest.POSTER_POLLUTION_REPAIRS))
    corrections = [
        row
        for row in corrections
        if not (row["event_id"] == target and row["field_name"] == "start_date")
    ]
    result = manifest.build_manifest(
        _state(events, field_corrections=corrections),
        generated_at="2026-07-11T00:00:00+00:00",
    )
    candidate = _candidate(result, target)

    assert candidate["action_type"] == "excluded"
    assert candidate["poster_pollution_repair"]["status"] == "conflict"
    assert "missing start_date field-correction evidence" in candidate["poster_pollution_repair"]["failures"]
    assert result["summary"]["poster_placeholder_pollution_repair_actions"] == 7
    assert result["summary"]["unresolved_non_eslite_location_conflicts"] == 1


def test_poster_repair_fc_before_after_replaces_pollution_with_clean_locks():
    events, corrections = _poster_pollution_fixture()
    target = "3dd4c8c8-d433-4221-961a-3b3c9b58d05e"
    result = manifest.build_manifest(
        _state(events, field_corrections=corrections),
        generated_at="2026-07-11T00:00:00+00:00",
    )
    candidate = _candidate(result, target)
    before = {row["field_name"]: row for row in candidate["field_corrections_before"]}
    after = {row["field_name"]: row for row in candidate["field_corrections_after"]}

    assert manifest.decoded_fc_value(before["location_name"]["corrected_value"]) == "大阪城ホール"
    assert manifest.decoded_fc_value(before["start_date"]["corrected_value"]) == "2023-10-14T00:00:00+00:00"
    assert after["location_name"]["corrected_value"] == manifest.PUBLICATION_CHANNEL_LOCATION
    assert after["start_date"]["corrected_value"] == "2026-03-13T00:00:00+00:00"
    assert after["organizer"]["corrected_value"] == "金沢文圃閣"


def test_pure_cleanup_plans_seven_nulls_and_lock_empty_sentinels_and_keeps_real_price():
    result = manifest.build_manifest(_state([_event("pure")]), generated_at="2026-07-11T00:00:00+00:00")
    candidate = _candidate(result, "pure")

    for field in manifest.PUBLICATION_NULL_FIELDS:
        assert candidate["event_after"][field] is None
        action = next(action for action in candidate["field_correction_actions"] if action["field_name"] == field)
        assert action["mode"] == "lock_empty"
        assert action["audit_contract"] == "qa_auto_fix.unlock_and_write"
    assert candidate["event_after"]["price_info"] == "2,200円"
    assert candidate["price_policy"]["real_price_preserved"] is True
    assert all(value == 1 for value in result["summary"]["planned_null_fields"].values())
    assert all(value == 1 for value in result["summary"]["planned_empty_sentinels"].values())


def test_only_explicit_fake_price_allowlist_is_cleared():
    fake = _event("fake", price_info="新書購買請洽各通路")
    dash = _event("dash", price_info="—")
    result = manifest.build_manifest(_state([fake, dash]), generated_at="2026-07-11T00:00:00+00:00")

    assert _candidate(result, "fake")["event_after"]["price_info"] is None
    assert _candidate(result, "fake")["price_policy"]["action"] == "cleared_explicit_fake_placeholder"
    assert _candidate(result, "dash")["event_after"]["price_info"] == "—"


def test_ndl_periodical_repairs_only_titles_without_existing_fc():
    periodical = _event(
        "periodical",
        source_name="ndl_opensearch",
        source_url="https://ndlsearch.ndl.go.jp/books/1?recordFamily=R000000004",
    )
    title_fc = {
        "id": "fc-ja",
        "event_id": "periodical",
        "field_name": "name_ja",
        "corrected_value": "人工タイトル",
        "report_id": None,
    }
    result = manifest.build_manifest(
        _state([periodical], field_corrections=[title_fc]),
        generated_at="2026-07-11T00:00:00+00:00",
    )
    candidate = _candidate(result, "periodical")

    assert candidate["event_after"]["name_ja"] == periodical["name_ja"]
    assert candidate["event_after"]["name_zh"].startswith("[期刊專文]")
    assert candidate["event_after"]["name_en"].startswith("[Periodical Article]")
    assert candidate["periodical"]["title_fc_preserved"] == ["name_ja"]
    assert candidate["periodical"]["source_metadata_confirmed"] is True


def test_eslite_talk_is_separate_migration_and_preserves_physical_fields():
    talk = _event(
        manifest.ESLITE_TALK_ID,
        source_name="eslite_spectrum",
        source_id=manifest.ESLITE_OLD_SOURCE_ID,
        source_url="https://www.eslitespectrum.jp/news/catalog/9",
        location_name="誠品生活日本橋",
        location_address="東京都中央区日本橋室町3-2-1",
        business_hours="新刊のご購入は各販売チャネルでお願いします",
        price_info="書籍代2,200円 + 手数料990円",
    )
    result = manifest.build_manifest(_state([talk]), generated_at="2026-07-11T00:00:00+00:00")
    candidate = _candidate(result, manifest.ESLITE_TALK_ID)

    assert candidate["included"] is False
    assert candidate["action_type"] == "eslite_physical_identity_migration"
    assert candidate["migration"]["live_remap_performed"] is False
    assert candidate["event_after"]["source_id"] == manifest.ESLITE_NEW_SOURCE_ID
    assert candidate["event_after"]["source_url"] == manifest.ESLITE_ARTICLE_URL
    assert candidate["event_after"]["event_form"] == ["lecture"]
    assert candidate["event_after"]["business_hours"] == "13:00〜"
    assert candidate["event_after"]["location_address"] == talk["location_address"]
    assert candidate["event_after"]["price_info"] == talk["price_info"]
    assert result["summary"]["eslite_migration_actions"] == 1


def test_manifest_contains_full_before_after_reports_organizer_and_wave2_boundary():
    event = _event("pure", organizer_id="org-1")
    report = {
        "id": "report-1",
        "event_id": "pure",
        "report_types": ["auto_qa_missing_address"],
        "status": "pending",
    }
    organizer = {
        "id": "org-1",
        "canonical_name_ja": "架空出版社",
        "canonical_name_zh": None,
        "canonical_name_en": None,
        "aliases": [],
        "homepage": None,
    }
    result = manifest.build_manifest(
        _state([event], event_reports=[report], organizers=[organizer]),
        generated_at="2026-07-11T00:00:00+00:00",
    )
    candidate = _candidate(result, "pure")

    assert candidate["event_before"] == event
    assert candidate["event_after"]["organizer_id"] == "org-1"
    assert candidate["publisher_resolution"]["organizer_before"] == organizer
    assert candidate["publisher_resolution"]["organizer_after"] == organizer
    assert candidate["publisher_resolution"]["status"] == "unresolved_homepage_allowed"
    assert candidate["reports"][0]["before"] == report
    assert candidate["reports"][0]["script_will_write"] is False
    assert result["wave2_boundary"]["status"] == "not_executed"
    assert result["apply_contract"]["unresolved_non_eslite_classification_conflicts_block_apply"] is True
    assert all(provider["enabled"] is False for provider in result["wave2_boundary"]["providers"])
    assert all(provider["max_cost"] == 0 for provider in result["wave2_boundary"]["providers"])


def test_manifest_hash_rejects_tampering(tmp_path):
    result = manifest.build_manifest(_state([_event("pure")]), generated_at="2026-07-11T00:00:00+00:00")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    assert manifest.load_manifest(path)["manifest_sha256"] == result["manifest_sha256"]

    tampered = deepcopy(result)
    tampered["summary"]["candidate_total"] = 999
    path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        manifest.load_manifest(path)


def test_apply_stops_on_full_batch_drift_before_snapshot_or_write(monkeypatch, tmp_path):
    before = _state([_event("pure")])
    result = manifest.build_manifest(before, generated_at="2026-07-11T00:00:00+00:00")
    drifted = _state([_event("pure", updated_at="2026-07-11T01:00:00+00:00")])
    calls = []
    monkeypatch.setattr(manifest, "assert_ignored_output_path", lambda path: path)
    monkeypatch.setattr(manifest, "read_database_state", lambda _sb: drifted)
    monkeypatch.setattr(manifest, "write_immutable_json", lambda *_args: calls.append("snapshot"))
    monkeypatch.setattr(manifest, "execute_candidate", lambda *_args: calls.append("write"))

    with pytest.raises(RuntimeError, match="zero writes performed"):
        manifest.apply_manifest(object(), result, manifest_path=tmp_path / "manifest.json")
    assert calls == []


def test_apply_uses_manifest_actions_after_snapshot_without_replanning(monkeypatch, tmp_path):
    state = _state([_event("pure")])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    calls = []
    monkeypatch.setattr(manifest, "assert_ignored_output_path", lambda path: path)
    monkeypatch.setattr(manifest, "read_database_state", lambda _sb: state)
    monkeypatch.setattr(manifest, "write_immutable_json", lambda _path, _payload: calls.append("snapshot"))
    monkeypatch.setattr(
        manifest,
        "execute_candidate",
        lambda _sb, candidate: calls.append(("execute", candidate["event_id"])),
    )

    applied = manifest.apply_manifest(
        object(),
        result,
        manifest_path=tmp_path / "manifest.json",
        snapshot_path=tmp_path / "rollback.json",
    )

    assert calls == ["snapshot", ("execute", "pure")]
    assert applied["applied_event_ids"] == ["pure"]
    assert applied["reports_written"] == 0
    assert applied["wave2_provider_calls"] == 0


def test_execute_candidate_orders_poster_pre_action_then_pure_cleanup_and_readback(monkeypatch):
    events, corrections = _poster_pollution_fixture()
    target = "3dd4c8c8-d433-4221-961a-3b3c9b58d05e"
    result = manifest.build_manifest(
        _state(events, field_corrections=corrections),
        generated_at="2026-07-11T00:00:00+00:00",
    )
    candidate = _candidate(result, target)
    audited_fields = {action["field_name"] for action in candidate["field_correction_actions"]}
    candidate["event_changes"] = {
        field: change
        for field, change in candidate["event_changes"].items()
        if field in audited_fields
    }
    calls = []
    monkeypatch.setattr(
        manifest,
        "audited_write",
        lambda _sb, **kwargs: calls.append(kwargs["unlock_reason"]) or True,
    )
    monkeypatch.setattr(
        manifest,
        "verify_candidate_read_back",
        lambda _sb, _candidate: calls.append("readback"),
    )

    manifest.execute_candidate(object(), candidate)

    assert calls[:3] == [
        "publication_manifest_poster_placeholder_pollution_repair",
        "publication_manifest_poster_placeholder_pollution_repair",
        "publication_manifest_poster_placeholder_pollution_repair",
    ]
    assert all(call == "publication_manifest_pure_cleanup" for call in calls[3:-1])
    assert calls[-1] == "readback"


def test_apply_blocks_unresolved_location_conflicts_before_database_read(monkeypatch, tmp_path):
    state = _state([_event("venue", location_name="丸善丸の内本店")])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    calls = []
    monkeypatch.setattr(manifest, "assert_ignored_output_path", lambda path: path)
    monkeypatch.setattr(manifest, "read_database_state", lambda _sb: calls.append("read"))

    with pytest.raises(RuntimeError, match="unresolved classification/location conflicts"):
        manifest.apply_manifest(object(), result, manifest_path=tmp_path / "manifest.json")
    assert calls == []


def test_snapshot_contains_all_four_complete_tables():
    state = _state([_event("pure")], field_corrections=[{"id": "fc", "event_id": "pure"}])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    snapshot = manifest.snapshot_payload(state, result)

    assert set(snapshot["tables"]) == set(manifest.TABLES)
    assert snapshot["tables"] == state["tables"]
    assert snapshot["rollback_contract"]["read_back_every_row"] is True
    assert snapshot["manifest_sha256"] == result["manifest_sha256"]


class _CountQuery:
    def __init__(self, rows, exact_count):
        self.rows = rows
        self.exact_count = exact_count
        self.head = False
        self.start = 0
        self.end = len(rows)

    def select(self, _columns, *, count=None, head=False):
        self.head = head
        return self

    def order(self, _field):
        return self

    def range(self, start, end):
        self.start, self.end = start, end
        return self

    def execute(self):
        if self.head:
            return SimpleNamespace(data=[], count=self.exact_count)
        return SimpleNamespace(data=self.rows[self.start : self.end + 1], count=None)


class _CountClient:
    def __init__(self, rows, exact_count):
        self.rows = rows
        self.exact_count = exact_count

    def table(self, _name):
        return _CountQuery(self.rows, self.exact_count)


def test_exact_count_mismatch_blocks_manifest_read():
    with pytest.raises(RuntimeError, match="exact/fetched mismatch"):
        manifest.fetch_table_exact(_CountClient([{"id": "1"}], 2), "events")


def test_secret_like_material_is_rejected(monkeypatch):
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="secret-like material"):
        manifest.assert_no_secret_material({"value": "github_pat_abcdefghijklmnopqrstuvwxyz"})


def test_default_client_proxy_blocks_every_supabase_mutation_method():
    proxy = manifest._ReadOnlyProxy(SimpleNamespace())

    for method in manifest._MUTATION_METHODS:
        with pytest.raises(RuntimeError, match="read-only client blocked"):
            getattr(proxy, method)


def test_cli_can_load_explicit_untracked_env_without_copying_it(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SUPABASE_URL=https://example.test\nSUPABASE_SERVICE_ROLE_KEY=test-key\n")
    created = []
    monkeypatch.setenv("PUBLICATION_MANIFEST_ENV_FILE", str(env_file))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(
        "supabase.create_client",
        lambda url, key: created.append((url, key)) or SimpleNamespace(),
    )

    client = manifest.get_supabase(read_only=True)

    assert isinstance(client, manifest._ReadOnlyProxy)
    assert created == [("https://example.test", "test-key")]
