from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

import _oneoff_backfill_publication_metadata as manifest
from test_qa_auto_fix_unlock_only import FakeSupabase


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


def _fc(row_id: str, event_id: str, field_name: str, corrected_value: str, **overrides):
    row = {
        "id": row_id,
        "event_id": event_id,
        "field_name": field_name,
        "original_value": None,
        "corrected_value": corrected_value,
        "corrected_by": None,
        "report_id": None,
        "created_at": "2026-06-26T04:00:00+00:00",
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


def _actions(candidate, apply_phase=None):
    return [
        action
        for action in candidate["field_correction_actions"]
        if apply_phase is None or action["apply_phase"] == apply_phase
    ]


def _fake_db(state, *, extra_events=None, extra_field_corrections=None):
    return FakeSupabase(
        {
            "events": deepcopy(state["tables"]["events"]) + list(extra_events or []),
            "field_corrections": deepcopy(state["tables"]["field_corrections"])
            + list(extra_field_corrections or []),
            "field_corrections_audit": [],
        }
    )


def _stamp_citation_join(result):
    """Fixture only: these cases exercise phase mechanics, not the join.

    Apply now re-verifies the citation-safety join from the manifest itself, so a
    cleanup manifest built without an artifact is refused. The join's own
    behaviour lives in `test_publication_citation_join.py`, which opts out with
    `stamp_citation_join=False`.
    """
    join = result.get("citation_safety_join")
    if result.get("scope") != manifest.MANIFEST_SCOPE_CLEANUP:
        return result
    if isinstance(join, dict) and join.get("performed"):
        return result
    result["citation_safety_join"] = {
        "required_for_scope": [manifest.MANIFEST_SCOPE_CLEANUP],
        "performed": True,
        "artifact": {
            "path": "fixture-b1-journal.json",
            "schema": {"name": manifest.CITATION_SAFETY_SCHEMA_NAMES[-1], "version": 1},
            "stage": "journal",
            "digest_field": "journal_sha256",
            "digest": "f" * 64,
            "set_sizes": {name: 0 for name in manifest.CITATION_SAFETY_SETS},
        },
        "excluded_sets": list(manifest.CITATION_SAFETY_EXCLUDED_SETS),
        "requires_determination_for_pure_candidates": True,
        "undetermined_event_ids": [],
        "confirmed_unavailable": [],
        "excluded_event_ids": {},
    }
    return result


def _apply(monkeypatch, tmp_path, sb, result, apply_phase, snapshots=None, stamp_citation_join=True):
    sink = snapshots if snapshots is not None else []
    if stamp_citation_join:
        result = _stamp_citation_join(result)
    monkeypatch.setattr(manifest, "assert_ignored_output_path", lambda path: path)
    monkeypatch.setattr(manifest, "write_immutable_json", lambda _path, payload: sink.append(payload))
    return manifest.apply_manifest(
        sb,
        result,
        manifest_path=tmp_path / "manifest.json",
        apply_phase=apply_phase,
        snapshot_path=tmp_path / f"rollback-{apply_phase}.json",
    )


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
                _fc(
                    f"fc-{event_id}-{field}",
                    event_id,
                    field,
                    json.dumps(value, ensure_ascii=False),
                    created_at=created.replace("00+00:00", f"0{suffix}+00:00"),
                )
            )
        if publisher:
            field_corrections.append(
                _fc(
                    f"fc-{event_id}-organizer",
                    event_id,
                    "organizer",
                    json.dumps(manifest.POSTER_POLLUTION_ORGANIZER, ensure_ascii=False),
                    created_at="2026-07-03T04:00:00+00:00",
                )
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


# The live row's location_url: a book purchase channel, never the venue.
ESLITE_BOOK_SALES_URL = "https://eslitespectrum-nihonbashi.shop/items/69907e237a275c0041dfeeff"
# The live body copy legitimately links to that purchase page. Body text is
# source material, not a write surface, so the cleanup must leave it intact.
ESLITE_LIVE_BODY_JA = (
    "誠品生活日本橋で開催するトークイベント。"
    f"書籍のご購入・お申し込みは {ESLITE_BOOK_SALES_URL} から。"
)
ESLITE_LIVE_BODY_ZH = f"於誠品生活日本橋舉辦的講座。購書與報名請至 {ESLITE_BOOK_SALES_URL}。"
ESLITE_LIVE_BODY_EN = (
    "A talk event at Eslite Spectrum Nihonbashi. "
    f"Buy the book and apply at {ESLITE_BOOK_SALES_URL}."
)


def _eslite_talk(**overrides):
    return _event(
        manifest.ESLITE_TALK_ID,
        source_name="eslite_spectrum",
        source_id=manifest.ESLITE_OLD_SOURCE_ID,
        source_url="https://www.eslitespectrum.jp/news/catalog/9",
        location_name="誠品生活日本橋",
        location_name_zh=None,
        location_name_en=None,
        location_address="東京都中央区日本橋室町3-2-1",
        location_address_zh=None,
        location_address_en=None,
        location_url=ESLITE_BOOK_SALES_URL,
        business_hours="新刊のご購入は各販売チャネルでお願いします",
        price_info="書籍代2,200円 + 手数料990円",
        raw_description=ESLITE_LIVE_BODY_JA,
        description_ja=ESLITE_LIVE_BODY_JA,
        description_zh=ESLITE_LIVE_BODY_ZH,
        description_en=ESLITE_LIVE_BODY_EN,
        **overrides,
    )


def _eslite_stale_fcs():
    return [
        _fc(
            "fc-eslite-address-zh",
            manifest.ESLITE_TALK_ID,
            "location_address_zh",
            "新書購買請洽各通路",
        ),
        _fc(
            "fc-eslite-address-en",
            manifest.ESLITE_TALK_ID,
            "location_address_en",
            "Please check each sales channel to purchase this new book.",
        ),
        _fc(
            "fc-eslite-name-zh",
            manifest.ESLITE_TALK_ID,
            "location_name_zh",
            "新書購買請洽各通路",
        ),
        _fc(
            "fc-eslite-name-en",
            manifest.ESLITE_TALK_ID,
            "location_name_en",
            "Please check each sales channel to purchase this new book.",
        ),
    ]


# --- classification / routing ------------------------------------------------


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


def test_human_field_corrections_are_a_hard_cleanup_exclusion():
    human = _event("human")
    rows = [
        _fc(
            "fc-human-zh",
            "human",
            "location_name_zh",
            "使用者回報的場地",
            corrected_by="99999999-9999-4999-8999-999999999999",
        )
    ]
    result = manifest.build_manifest(
        _state([human], field_corrections=rows),
        generated_at="2026-07-11T00:00:00+00:00",
    )
    candidate = _candidate(result, "human")

    assert candidate["action_type"] == "excluded"
    assert candidate["conflicts"][0]["type"] == "human_field_correction"
    assert "location_name_zh" in candidate["excluded_reason"]
    assert candidate["field_correction_actions"] == []
    assert result["summary"]["excluded_human_field_correction"] == 1
    assert result["summary"]["included_pure"] == 0
    preserve = {
        row["id"]
        for row in result["checkpoints"]["fc-remove.before"]["preserve_field_corrections"]
    }
    assert "fc-human-zh" in preserve


# --- G1: migrated legacy assertions -----------------------------------------


def test_route_action_replaces_the_old_phase_provenance_key():
    events, corrections = _poster_pollution_fixture()
    result = manifest.build_manifest(
        _state(events, field_corrections=corrections),
        generated_at="2026-07-11T00:00:00+00:00",
    )
    candidate = _candidate(result, "3dd4c8c8-d433-4221-961a-3b3c9b58d05e")
    actions = candidate["field_correction_actions"]

    assert actions
    assert {action["route_action"] for action in actions} == {"poster_placeholder_pollution_repair"}
    assert all("phase" not in action for action in actions)
    assert all(action["apply_phase"] in manifest.APPLY_PHASES for action in actions)
    with pytest.raises(KeyError):
        actions[0]["phase"]


def test_unlock_reason_is_the_expanded_digest_form_not_the_old_underscore_reason(monkeypatch, tmp_path):
    events, corrections = _poster_pollution_fixture()
    state = _state(events, field_corrections=corrections)
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    expected_reason = f"publication_manifest:fc-remove:{result['manifest_sha256']}"

    templates = {
        action["unlock_reason_template"]
        for candidate in result["candidates"]
        for action in candidate["field_correction_actions"]
    }
    assert manifest.MANIFEST_DIGEST_PLACEHOLDER in "".join(templates)
    assert result["manifest_sha256"] not in "".join(templates)

    sb = _fake_db(state)
    _apply(monkeypatch, tmp_path, sb, result, "fc-remove")

    reasons = {row["unlock_reason"] for row in sb.tables["field_corrections_audit"]}
    assert reasons == {expected_reason}
    assert "publication_manifest_poster_placeholder_pollution_repair" not in reasons
    assert "publication_manifest_pure_cleanup" not in reasons
    assert not any(reason.startswith("publication_manifest_") for reason in reasons)


def test_poster_repair_clears_venue_fields_and_never_writes_the_channel_placeholder():
    events, corrections = _poster_pollution_fixture()
    result = manifest.build_manifest(
        _state(events, field_corrections=corrections),
        generated_at="2026-07-11T00:00:00+00:00",
    )

    evidence_ids = {
        candidate["event_id"]
        for candidate in result["candidates"]
        if candidate.get("poster_pollution_repair", {}).get("status") == "evidence_only"
    }
    assert evidence_ids == set(manifest.POSTER_POLLUTION_REPAIRS)
    assert result["summary"]["poster_placeholder_pollution_evidence_rows"] == 8
    assert result["summary"]["unresolved_non_eslite_location_conflicts"] == 0

    for event_id, expected in manifest.POSTER_POLLUTION_REPAIRS.items():
        candidate = _candidate(result, event_id)
        assert candidate["action_type"] == "pure_cleanup"
        assert candidate["pre_actions"] == []
        assert candidate["event_after"]["location_name"] is None
        assert candidate["event_after"]["location_name"] != manifest.PUBLICATION_CHANNEL_LOCATION
        assert candidate["event_after"]["start_date"] == manifest.POSTER_POLLUTION_START_DATE
        assert candidate["poster_pollution_repair"]["executable_repair"] is False
        assert (
            candidate["poster_pollution_repair"]["read_only_findings"]["audited_clean_start_date"]
            == expected["clean_start_date"]
        )
        assert "lock_clean" not in {action["mode"] for action in candidate["field_correction_actions"]}
        assert [action["field_name"] for action in _actions(candidate, "fc-remove")] == ["location_name"]
        assert all(
            candidate["event_after"][field] is None
            for field in manifest.PUBLICATION_TARGET_FIELDS
        )


def test_poster_repair_fc_after_removes_pollution_without_a_replacement_lock():
    events, corrections = _poster_pollution_fixture()
    result = manifest.build_manifest(
        _state(events, field_corrections=corrections),
        generated_at="2026-07-11T00:00:00+00:00",
    )
    candidate = _candidate(result, "3dd4c8c8-d433-4221-961a-3b3c9b58d05e")
    before = {row["field_name"]: row for row in candidate["field_corrections_before"]}
    after = {row["field_name"]: row for row in candidate["field_corrections_after"]}

    assert manifest.decoded_fc_value(before["location_name"]["corrected_value"]) == "大阪城ホール"
    assert manifest.decoded_fc_value(before["start_date"]["corrected_value"]) == "2023-10-14T00:00:00+00:00"
    assert "location_name" not in after
    assert after["start_date"] == before["start_date"]
    assert after["organizer"] == before["organizer"]
    assert manifest.PUBLICATION_CHANNEL_LOCATION not in {
        row.get("corrected_value") for row in candidate["field_corrections_after"]
    }


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
    assert result["summary"]["poster_placeholder_pollution_evidence_rows"] == 7
    assert result["summary"]["unresolved_non_eslite_location_conflicts"] == 1


# --- G3: non-target fields stay read-only findings ---------------------------


def test_non_target_fields_are_byte_identical_and_absent_from_executable_actions():
    periodical = _event(
        "periodical",
        source_name="ndl_opensearch",
        source_url="https://ndlsearch.ndl.go.jp/books/1?recordFamily=R000000004",
        price_info="新書購買請洽各通路",
    )
    organizer = {
        "id": "org-1",
        "canonical_name_ja": "架空出版社",
        "canonical_name_zh": None,
        "canonical_name_en": None,
        "aliases": [],
        "homepage": "https://publisher.example.test/",
    }
    result = manifest.build_manifest(
        _state([periodical], organizers=[organizer]),
        generated_at="2026-07-11T00:00:00+00:00",
    )
    candidate = _candidate(result, "periodical")

    for field in ("price_info", "name_ja", "name_zh", "name_en", "organizer_id", "organizer_url"):
        assert candidate["event_after"][field] == periodical[field]
        assert field not in candidate["event_changes"]
    assert set(candidate["event_changes"]) <= set(manifest.PUBLICATION_TARGET_FIELDS)

    action_fields = {action["field_name"] for action in candidate["field_correction_actions"]}
    assert action_fields <= set(manifest.PUBLICATION_TARGET_FIELDS)
    assert not action_fields & {"price_info", "name_ja", "name_zh", "name_en", "organizer_url"}

    findings = candidate["read_only_findings"]
    assert findings["price_info"]["fake_placeholder_allowlist_match"] is True
    assert findings["price_info"]["executable"] is False
    assert findings["periodical_titles"]["candidates"]["name_zh"]["source_evidence"].startswith("[期刊專文]")
    assert findings["periodical_titles"]["executable"] is False
    assert findings["organizer_link"]["organizer_id"]["registry_match"] == "org-1"
    assert findings["organizer_link"]["executable"] is False
    assert candidate["periodical"]["planned_title_repairs"] == {}
    assert result["summary"]["fake_price_placeholders_read_only"] == 1
    assert result["summary"]["periodical_title_read_only_findings"] == 1


def test_non_target_fields_are_absent_from_every_after_image_delta(monkeypatch, tmp_path):
    event = _event("pure", price_info="新書購買請洽各通路", organizer_id="org-1")
    state = _state([event])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)

    _apply(monkeypatch, tmp_path, sb, result, "event-clear")

    row = sb.tables["events"][0]
    for field in ("price_info", "name_ja", "name_zh", "name_en", "organizer_id", "organizer_url"):
        assert row[field] == event[field]
    for payload in result["checkpoints"]["event-clear.after"]["events"]:
        for field in ("price_info", "name_ja", "organizer_id", "organizer_url"):
            assert payload[field] == event[field]


def test_ndl_periodical_title_findings_skip_fields_with_an_existing_fc():
    periodical = _event(
        "periodical",
        source_name="ndl_opensearch",
        source_url="https://ndlsearch.ndl.go.jp/books/1?recordFamily=R000000004",
    )
    title_fc = _fc("fc-ja", "periodical", "name_ja", "人工タイトル")
    result = manifest.build_manifest(
        _state([periodical], field_corrections=[title_fc]),
        generated_at="2026-07-11T00:00:00+00:00",
    )
    candidate = _candidate(result, "periodical")

    assert candidate["event_after"]["name_ja"] == periodical["name_ja"]
    assert candidate["event_after"]["name_zh"] == periodical["name_zh"]
    assert candidate["periodical"]["title_fc_preserved"] == ["name_ja"]
    assert candidate["periodical"]["source_metadata_confirmed"] is True
    assert "name_ja" not in candidate["read_only_findings"]["periodical_titles"]["candidates"]
    assert "name_zh" in candidate["read_only_findings"]["periodical_titles"]["candidates"]


def test_legacy_placeholder_detector_fixtures_still_match():
    assert manifest.is_fake_price("新書購買請洽各通路") is True
    assert manifest.is_fake_price("2,200円") is False
    assert manifest.PUBLICATION_CHANNEL_LOCATION in manifest.PUBLICATION_PLACEHOLDER_VALUES
    for legacy in manifest.FAKE_PRICE_PLACEHOLDERS:
        assert legacy in manifest.PUBLICATION_PLACEHOLDER_VALUES
    assert manifest.location_conflict_reason(_event("x")) is None
    assert manifest.location_conflict_reason(_event("x", location_name="丸善丸の内本店"))


# --- PN-3a.0: bibliographic catalogue sources carry no physical venue ---------


NDL_JOURNAL_LOCATION_NAME = "秋田大学高等教育グローバルセンター紀要 7"
TOKYO_DOME_EVENT_ID = "2b75e683-0231-46c3-99f0-5db207dcbc18"


def test_catalog_source_journal_title_is_not_a_location_conflict():
    event = _event(
        "ndl-journal",
        source_name="ndl_opensearch",
        source_id="ndl_1c05e6d1b5a2",
        source_url="https://ndlsearch.ndl.go.jp/books/R100000002-I111111111?recordFamily=R000000004",
        location_name=NDL_JOURNAL_LOCATION_NAME,
    )
    assert manifest.PHYSICAL_LOCATION_RE.search(NDL_JOURNAL_LOCATION_NAME)
    assert manifest.location_conflict_reason(event) is None

    result = manifest.build_manifest(_state([event]), generated_at="2026-08-06T00:00:00+00:00")
    candidate = _candidate(result, "ndl-journal")

    assert candidate["classification"]["location_conflict"] is None
    assert candidate["action_type"] == "pure_cleanup"
    assert candidate["event_after"]["location_name"] is None
    assert result["summary"]["included_pure"] == 1
    assert result["summary"]["unresolved_non_eslite_location_conflicts"] == 0


def test_non_catalog_source_physical_venue_still_conflicts():
    assert "hanmoto" not in manifest.BIBLIOGRAPHIC_CATALOG_SOURCES
    event = _event("hanmoto-osaka", location_name=manifest.POSTER_POLLUTION_LOCATION)
    reason = manifest.location_conflict_reason(event)
    assert reason and manifest.POSTER_POLLUTION_LOCATION in reason

    result = manifest.build_manifest(_state([event]), generated_at="2026-08-06T00:00:00+00:00")
    candidate = _candidate(result, "hanmoto-osaka")

    assert candidate["action_type"] == "excluded"
    assert result["summary"]["unresolved_non_eslite_location_conflicts"] == 1


def test_poster_pollution_rows_keep_evidence_only_routing_under_the_catalog_exemption():
    events, corrections = _poster_pollution_fixture()
    result = manifest.build_manifest(
        _state(events, field_corrections=corrections),
        generated_at="2026-08-06T00:00:00+00:00",
    )

    evidence_ids = {
        candidate["event_id"]
        for candidate in result["candidates"]
        if candidate.get("poster_pollution_repair", {}).get("status") == "evidence_only"
    }
    assert evidence_ids == set(manifest.POSTER_POLLUTION_REPAIRS)
    assert result["summary"]["poster_placeholder_pollution_evidence_rows"] == 8

    catalog_poster_ids = [
        event_id
        for event_id, expected in manifest.POSTER_POLLUTION_REPAIRS.items()
        if expected["source_name"] in manifest.BIBLIOGRAPHIC_CATALOG_SOURCES
    ]
    assert catalog_poster_ids
    for event_id in catalog_poster_ids:
        candidate = _candidate(result, event_id)
        assert candidate["action_type"] == "pure_cleanup"
        assert candidate["poster_pollution_repair"]["executable_repair"] is False
        assert candidate["pre_actions"] == []


def test_hanmoto_tokyo_dome_row_stays_an_included_pure_cleanup_candidate():
    assert TOKYO_DOME_EVENT_ID not in manifest.POSTER_POLLUTION_REPAIRS
    event = _event(
        TOKYO_DOME_EVENT_ID,
        source_id="hanmoto_9784575320985",
        location_name="東京ドーム",
    )
    assert manifest.location_conflict_reason(event) is None

    result = manifest.build_manifest(_state([event]), generated_at="2026-08-06T00:00:00+00:00")
    candidate = _candidate(result, TOKYO_DOME_EVENT_ID)

    assert candidate["action_type"] == "pure_cleanup"
    assert candidate["event_after"]["location_name"] is None
    assert result["summary"]["unresolved_non_eslite_location_conflicts"] == 0


def test_pure_cleanup_plans_thirteen_targets_with_seven_sentinels_and_six_cas_clears():
    result = manifest.build_manifest(_state([_event("pure")]), generated_at="2026-07-11T00:00:00+00:00")
    candidate = _candidate(result, "pure")

    for field in manifest.PUBLICATION_NULL_FIELDS:
        assert candidate["event_after"][field] is None
        action = next(
            action for action in _actions(candidate, "event-clear") if action["field_name"] == field
        )
        assert action["mode"] == "lock_empty"
        assert action["audit_contract"] == "qa_auto_fix.unlock_and_write"
    for field in manifest.PUBLICATION_EXTENDED_CLEAR_FIELDS:
        assert candidate["event_after"][field] is None
        assert field in candidate["extended_field_patch"]
        assert not any(action["field_name"] == field for action in candidate["field_correction_actions"])
    assert candidate["event_after"]["price_info"] == "2,200円"
    assert candidate["price_policy"]["real_price_preserved"] is True
    assert all(value == 1 for value in result["summary"]["planned_null_fields"].values())
    assert all(value == 1 for value in result["summary"]["planned_empty_sentinels"].values())


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
    assert candidate["publisher_resolution"]["executable"] is False
    assert candidate["reports"][0]["before"] == report
    assert candidate["reports"][0]["script_will_write"] is False
    assert result["wave2_boundary"]["status"] == "not_executed"
    assert result["apply_contract"]["unresolved_non_eslite_classification_conflicts_block_apply"] is True
    assert all(provider["enabled"] is False for provider in result["wave2_boundary"]["providers"])
    assert all(provider["max_cost"] == 0 for provider in result["wave2_boundary"]["providers"])


# --- checkpoints and digests -------------------------------------------------


def test_three_scoped_checkpoints_are_hashed_and_folded_into_one_manifest_digest():
    result = manifest.build_manifest(_state([_event("pure")]), generated_at="2026-07-11T00:00:00+00:00")

    assert sorted(result["checkpoints"]) == sorted(manifest.CLEANUP_CHECKPOINTS)
    for name, payload in result["checkpoints"].items():
        body = {key: value for key, value in payload.items() if key != "sha256"}
        assert payload["sha256"] == manifest.sha256(body)
        assert payload["checkpoint"] == name
    assert result["apply_contract"]["checkpoint_aliases"] == {"event-clear.before": "fc-remove.after"}

    tampered = deepcopy(result)
    tampered.pop("manifest_sha256")
    tampered["checkpoints"]["fc-remove.before"]["events"][0]["price_info"] = "0円"
    assert manifest.sha256(tampered) != result["manifest_sha256"]


def test_fc_remove_after_is_the_event_clear_before_gate():
    result = manifest.build_manifest(_state([_event("pure")]), generated_at="2026-07-11T00:00:00+00:00")

    assert manifest.CHECKPOINT_BEFORE["event-clear"] == "fc-remove.after"
    assert manifest.CHECKPOINT_AFTER["fc-remove"] == "fc-remove.after"
    assert result["checkpoints"]["fc-remove.after"]["events"] == result["checkpoints"]["fc-remove.before"]["events"]


def test_base_read_fingerprint_is_demoted_to_discovery_evidence():
    result = manifest.build_manifest(_state([_event("pure")]), generated_at="2026-07-11T00:00:00+00:00")

    assert result["base_read_fingerprint"]["role"] == "discovery_evidence_only"
    assert result["apply_contract"]["full_batch_fingerprint_drift_gate_before_any_write"] is False
    assert result["apply_contract"]["scoped_checkpoint_gate_before_any_write"] is True
    assert result["apply_contract"]["apply_phase_is_the_sole_write_selector"] is True
    assert result["apply_contract"]["apply_eligible_is_generation_time_metadata_only"] is True
    assert result["apply_contract"]["route_action_is_provenance_only"] is True


def test_checkpoints_exclude_volatile_updated_at():
    result = manifest.build_manifest(_state([_event("pure")]), generated_at="2026-07-11T00:00:00+00:00")

    for payload in result["checkpoints"].values():
        assert payload["volatile_event_fields_excluded"] == ["updated_at"]
        assert all("updated_at" not in row for row in payload["events"])


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


# --- CLI selector ------------------------------------------------------------


def test_apply_phase_is_required_only_with_apply_and_manifest():
    args = manifest.parse_args(
        ["--apply", "--manifest", "m.json", "--apply-phase", "fc-remove", "--target", "rehearsal"]
    )
    assert args.apply_phase == "fc-remove"

    with pytest.raises(SystemExit):
        manifest.parse_args(["--apply", "--manifest", "m.json", "--target", "rehearsal"])
    with pytest.raises(SystemExit):
        manifest.parse_args(["--apply-phase", "fc-remove"])
    with pytest.raises(SystemExit):
        manifest.parse_args(["--manifest-output", "o.json", "--apply-phase", "event-clear"])
    with pytest.raises(SystemExit):
        manifest.parse_args(
            ["--apply", "--manifest", "m.json", "--apply-phase", "nope", "--target", "rehearsal"]
        )

    # Cleanup generation now also requires the B1 citation-safety artifact.
    assert manifest.parse_args(["--citation-safety", "b1.json"]).apply_phase is None
    assert manifest.parse_args(["--scope", "eslite-identity"]).scope == "eslite-identity"


# --- phase-aware executor ----------------------------------------------------


def test_fc_remove_deletes_polluted_rows_writes_audit_and_leaves_events_untouched(monkeypatch, tmp_path):
    event = _event("pure")
    rows = [
        _fc("fc-loc", "pure", "location_name", manifest.PUBLICATION_CHANNEL_LOCATION),
        _fc("fc-hours", "pure", "business_hours", "10:00-18:00"),
        _fc("fc-sentinel", "pure", "location_address", ""),
        _fc("fc-title", "pure", "name_ja", "非対象"),
    ]
    state = _state([event], field_corrections=rows)
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)

    applied = _apply(monkeypatch, tmp_path, sb, result, "fc-remove")

    assert applied["apply_phase"] == "fc-remove"
    assert applied["applied_event_ids"] == ["pure"]
    assert {row["id"] for row in sb.tables["field_corrections"]} == {"fc-sentinel", "fc-title"}
    assert sb.tables["events"][0]["location_name"] == manifest.PUBLICATION_CHANNEL_LOCATION
    assert sb.tables["events"][0]["business_hours"] == event["business_hours"]

    applied_rows = [
        row for row in sb.tables["field_corrections_audit"] if row["operation_status"] == "applied"
    ]
    assert {row["field_correction_id"] for row in applied_rows} == {"fc-loc", "fc-hours"}
    assert all(row["verified_at"] for row in applied_rows)


def test_event_clear_runs_six_field_cas_before_canonical_lock_empty(monkeypatch, tmp_path):
    event = _event("pure")
    state = _state([event])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)

    _apply(monkeypatch, tmp_path, sb, result, "event-clear")

    event_updates = [write for write in sb.writes if write[0] == "events" and write[1] == "update"]
    first = event_updates[0]
    assert sorted(first[2]) == sorted(manifest.PUBLICATION_EXTENDED_CLEAR_FIELDS)
    assert not set(first[2]) & set(manifest.PUBLICATION_NULL_FIELDS)
    cas_columns = {column for _, column, _ in first[3]}
    assert cas_columns == {"id", "event_form", *manifest.PUBLICATION_EXTENDED_CLEAR_FIELDS}
    assert cas_columns != {"id"}

    canonical_updates = event_updates[1:]
    assert [list(write[2])[0] for write in canonical_updates] == list(manifest.PUBLICATION_NULL_FIELDS)
    for write in canonical_updates:
        assert not set(write[2]) & set(manifest.PUBLICATION_EXTENDED_CLEAR_FIELDS)
        assert {column for _, column, _ in write[3]} != {"id"}

    row = sb.tables["events"][0]
    for field in manifest.PUBLICATION_TARGET_FIELDS:
        assert row[field] is None
    assert row["price_info"] == "2,200円"
    assert row["name_ja"] == event["name_ja"]

    assert {row["field_name"] for row in sb.tables["field_corrections"]} == set(
        manifest.PUBLICATION_NULL_FIELDS
    )
    assert not [write for write in sb.writes if write[1] == "delete"]


def test_event_clear_creates_one_sentinel_when_none_exists(monkeypatch, tmp_path):
    state = _state([_event("pure")])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)

    _apply(monkeypatch, tmp_path, sb, result, "event-clear")

    rows = [row for row in sb.tables["field_corrections"] if row["field_name"] == "business_hours"]
    assert len(rows) == 1
    assert rows[0]["corrected_value"] == ""
    assert sb.tables["events"][0]["business_hours"] is None


def test_event_clear_preserves_an_exact_sentinel_and_still_clears_the_event(monkeypatch, tmp_path):
    event = _event("pure")
    sentinel = _fc("fc-sentinel", "pure", "business_hours", "")
    state = _state([event], field_corrections=[sentinel])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    action = next(
        action
        for action in _actions(_candidate(result, "pure"), "event-clear")
        if action["field_name"] == "business_hours"
    )
    assert action["expected_fc"]["id"] == "fc-sentinel"

    sb = _fake_db(state)
    _apply(monkeypatch, tmp_path, sb, result, "event-clear")

    rows = [row for row in sb.tables["field_corrections"] if row["field_name"] == "business_hours"]
    assert rows == [sentinel]
    assert sb.tables["events"][0]["business_hours"] is None
    assert not [
        write
        for write in sb.writes
        if write[0] == "field_corrections"
        and write[1] == "upsert"
        and write[2].get("field_name") == "business_hours"
    ]


def test_event_clear_skips_a_full_no_op_extended_patch(monkeypatch, tmp_path):
    event = _event(
        "pure",
        location_name=None,
        location_name_zh=None,
        location_name_en=None,
        location_url=None,
        venue_id=None,
        organizer_type=None,
    )
    state = _state([event])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)

    _apply(monkeypatch, tmp_path, sb, result, "event-clear")

    assert all(
        not set(write[2]) & set(manifest.PUBLICATION_EXTENDED_CLEAR_FIELDS)
        for write in sb.writes
        if write[0] == "events" and write[1] == "update"
    )


def test_wrong_phase_actions_are_never_touched(monkeypatch, tmp_path):
    event = _event("pure")
    rows = [_fc("fc-loc", "pure", "location_name", manifest.PUBLICATION_CHANNEL_LOCATION)]
    state = _state([event], field_corrections=rows)
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)

    _apply(monkeypatch, tmp_path, sb, result, "fc-remove")

    assert sb.tables["field_corrections"] == []
    for field in manifest.PUBLICATION_NULL_FIELDS:
        assert sb.tables["events"][0][field] == event[field]


def test_apply_eligible_cannot_select_writes_but_apply_phase_can(monkeypatch, tmp_path):
    event = _event("pure")
    rows = [_fc("fc-loc", "pure", "location_name", manifest.PUBLICATION_CHANNEL_LOCATION)]
    state = _state([event], field_corrections=rows)
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    _candidate(result, "pure")["apply_eligible"] = False
    sb = _fake_db(state)

    applied = _apply(monkeypatch, tmp_path, sb, result, "fc-remove")

    assert applied["applied_event_ids"] == ["pure"]
    assert sb.tables["field_corrections"] == []


def test_phase_effect_boundary_rejects_a_forbidden_mode():
    candidate = {
        "event_id": "pure",
        "event_before": _event("pure"),
        "extended_field_patch": {},
        "identity_patch": {},
        "field_correction_actions": [
            {
                "field_name": "location_name",
                "mode": "unlock_only",
                "new_value": None,
                "apply_phase": "event-clear",
                "route_action": "pure_cleanup",
                "expected_fc": None,
                "unlock_reason_template": manifest.unlock_reason_template("event-clear"),
            }
        ],
    }
    with pytest.raises(RuntimeError, match="forbids mode 'unlock_only'"):
        manifest.execute_candidate(
            object(), candidate, apply_phase="event-clear", manifest_digest="a" * 64
        )

    with pytest.raises(RuntimeError, match="not permitted in apply_phase"):
        manifest.plan_fc_actions(
            "pure", [], {"location_name": ("lock_clean", "x")}, apply_phase="fc-remove"
        )
    assert manifest.PHASE_ALLOWED_FC_MODES["fc-remove"] == frozenset({"unlock_only"})
    assert manifest.PHASE_ALLOWED_FC_MODES["event-clear"] == frozenset({"lock_empty"})


def test_unexpanded_digest_placeholder_is_never_written():
    with pytest.raises(RuntimeError, match="lacks digest placeholder"):
        manifest.expand_unlock_reason("publication_manifest_pure_cleanup", "a" * 64)
    assert manifest.expand_unlock_reason(
        manifest.unlock_reason_template("fc-remove"), "a" * 64
    ) == f"publication_manifest:fc-remove:{'a' * 64}"


# --- checkpoint drift gate ---------------------------------------------------


def test_unrelated_full_table_drift_is_accepted(monkeypatch, tmp_path):
    event = _event("pure")
    rows = [_fc("fc-loc", "pure", "location_name", manifest.PUBLICATION_CHANNEL_LOCATION)]
    state = _state([event], field_corrections=rows)
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(
        state,
        extra_events=[_event("unrelated", event_form=["lecture"])],
        extra_field_corrections=[_fc("fc-other", "unrelated", "location_name", "別会場")],
    )

    applied = _apply(monkeypatch, tmp_path, sb, result, "fc-remove")

    assert applied["applied_event_ids"] == ["pure"]
    assert {row["id"] for row in sb.tables["field_corrections"]} == {"fc-other"}


@pytest.mark.parametrize(
    "mutate,match",
    [
        (
            lambda sb: sb.tables["events"][0].update({"price_info": "999円"}),
            "fc-remove.before events drift",
        ),
        (
            lambda sb: sb.tables["field_corrections"].append(
                _fc("fc-extra", "pure", "business_hours", "10:00")
            ),
            "fc-remove.before target_field_corrections drift",
        ),
        (
            lambda sb: sb.tables["field_corrections"].remove(
                next(row for row in sb.tables["field_corrections"] if row["id"] == "fc-preserve")
            ),
            "preserve_field_corrections drift",
        ),
        (
            lambda sb: next(
                row for row in sb.tables["field_corrections"] if row["id"] == "fc-preserve"
            ).update({"corrected_value": "改ざん"}),
            "preserve_field_corrections drift",
        ),
    ],
)
def test_selected_row_and_preserve_drift_stop_before_any_write(monkeypatch, tmp_path, mutate, match):
    event = _event("pure")
    rows = [
        _fc("fc-loc", "pure", "location_name", manifest.PUBLICATION_CHANNEL_LOCATION),
        _fc("fc-preserve", "pure", "name_ja", "人手による題名"),
    ]
    state = _state([event], field_corrections=rows)
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)
    mutate(sb)
    before_fc = deepcopy(sb.tables["field_corrections"])

    with pytest.raises(RuntimeError, match=match):
        _apply(monkeypatch, tmp_path, sb, result, "fc-remove")

    assert sb.tables["field_corrections"] == before_fc
    assert sb.tables["field_corrections_audit"] == []
    assert sb.writes == []


def test_event_clear_is_rejected_before_the_exact_fc_remove_after_checkpoint(monkeypatch, tmp_path):
    event = _event("pure")
    rows = [_fc("fc-loc", "pure", "location_name", manifest.PUBLICATION_CHANNEL_LOCATION)]
    state = _state([event], field_corrections=rows)
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)

    with pytest.raises(RuntimeError, match="fc-remove.after target_field_corrections drift"):
        _apply(monkeypatch, tmp_path, sb, result, "event-clear")
    assert sb.writes == []

    _apply(monkeypatch, tmp_path, sb, result, "fc-remove")
    applied = _apply(monkeypatch, tmp_path, sb, result, "event-clear")
    assert applied["applied_event_ids"] == ["pure"]
    assert sb.tables["events"][0]["location_name"] is None


def test_missing_audit_anchor_fails_the_fc_remove_after_checkpoint(monkeypatch, tmp_path):
    event = _event("pure")
    rows = [_fc("fc-loc", "pure", "location_name", manifest.PUBLICATION_CHANNEL_LOCATION)]
    state = _state([event], field_corrections=rows)
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)

    _apply(monkeypatch, tmp_path, sb, result, "fc-remove")
    sb.tables["field_corrections_audit"] = []

    with pytest.raises(RuntimeError, match="audit anchor mismatch"):
        _apply(monkeypatch, tmp_path, sb, result, "event-clear")


def test_after_checkpoint_still_rejects_drift_on_phase_created_sentinels(monkeypatch, tmp_path):
    state = _state([_event("pure")])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)

    _apply(monkeypatch, tmp_path, sb, result, "event-clear")
    manifest.verify_checkpoint(sb, result, "event-clear.after", is_after_gate=True)

    sentinel = next(
        row for row in sb.tables["field_corrections"] if row["field_name"] == "business_hours"
    )
    sentinel["corrected_value"] = "10:00-18:00"
    with pytest.raises(RuntimeError, match="event-clear.after target_field_corrections drift"):
        manifest.verify_checkpoint(sb, result, "event-clear.after", is_after_gate=True)

    sentinel["corrected_value"] = ""
    sb.tables["field_corrections"].append(_fc("fc-extra", "pure", "location_name", "別会場"))
    with pytest.raises(RuntimeError, match="event-clear.after target_field_corrections drift"):
        manifest.verify_checkpoint(sb, result, "event-clear.after", is_after_gate=True)


def test_existing_rows_still_match_only_on_the_full_field_correction_id():
    expected = [_fc("fc-1", "pure", "business_hours", "")]
    observed = [_fc("fc-2", "pure", "business_hours", "")]
    for allow in (False, True):
        diff = manifest.structural_row_diff(expected, observed, allow_db_assigned_ids=allow)
        assert diff["missing"] == ["fc-1"]
        assert diff["unexpected"] == ["fc-2"]

    created = [{**_fc("fc-1", "pure", "business_hours", ""), "id": None}]
    assert manifest.structural_row_diff(created, observed, allow_db_assigned_ids=True) == {
        "missing": [],
        "unexpected": [],
        "changed": [],
    }
    assert manifest.structural_row_diff(created, observed)["unexpected"] == ["fc-2"]


def test_after_gate_failure_names_the_rollback_instead_of_claiming_zero_writes(
    monkeypatch, tmp_path
):
    state = _state([_event("pure")])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)
    execute = manifest.execute_candidate

    def _concurrent_writer(sb_arg, candidate, **kwargs):
        counts = execute(sb_arg, candidate, **kwargs)
        next(
            row
            for row in sb_arg.tables["field_corrections"]
            if row["field_name"] == "business_hours"
        )["corrected_value"] = "10:00-18:00"
        return counts

    monkeypatch.setattr(manifest, "execute_candidate", _concurrent_writer)

    with pytest.raises(RuntimeError) as failure:
        _apply(monkeypatch, tmp_path, sb, result, "event-clear")

    message = str(failure.value)
    assert "zero writes performed" not in message
    assert "event-clear.after target_field_corrections drift AFTER writes" in message
    assert f"rollback snapshot={tmp_path / 'rollback-event-clear.json'}" in message
    assert "applied_event_ids=['pure']" in message
    assert "fc_created=7; fc_deleted=0" in message
    assert "manual rollback required" in message
    # The writes the message refuses to disown really happened.
    assert sb.tables["events"][0]["location_address"] is None
    assert len(sb.tables["field_corrections"]) == 7


def test_before_gate_failure_still_reports_zero_writes(monkeypatch, tmp_path):
    event = _event("pure")
    rows = [_fc("fc-loc", "pure", "location_name", manifest.PUBLICATION_CHANNEL_LOCATION)]
    state = _state([event], field_corrections=rows)
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)
    sb.tables["field_corrections"][0]["corrected_value"] = "別会場"

    with pytest.raises(RuntimeError, match="zero writes performed") as failure:
        _apply(monkeypatch, tmp_path, sb, result, "fc-remove")

    assert "AFTER writes" not in str(failure.value)
    assert sb.writes == []


def test_the_event_clear_before_gate_is_id_exact_despite_its_after_payload_name(
    monkeypatch, tmp_path
):
    state = _state([_event("pure")])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)
    sb.tables["field_corrections"].append(_fc("fc-db-assigned", "pure", "business_hours", ""))

    forged = deepcopy(result)
    payload = forged["checkpoints"]["fc-remove.after"]
    payload["target_field_corrections"] = [
        {**_fc("ignored", "pure", "business_hours", ""), "id": None}
    ]
    payload["sha256"] = manifest.sha256(
        {key: value for key, value in payload.items() if key != "sha256"}
    )

    # Identical payload, identical database: only the gate's role differs.
    manifest.verify_checkpoint(sb, forged, "fc-remove.after", is_after_gate=True)
    with pytest.raises(RuntimeError, match="fc-remove.after target_field_corrections drift"):
        manifest.verify_checkpoint(sb, forged, "event-clear.before")
    with pytest.raises(RuntimeError, match="fc-remove.after target_field_corrections drift"):
        manifest.verify_checkpoint(sb, forged, "fc-remove.after")


def test_preserve_row_id_swap_stops_the_after_checkpoint(monkeypatch, tmp_path):
    state = _state(
        [_event("pure")],
        field_corrections=[
            _fc("fc-title-ja", "pure", "name_ja", "人手による和題"),
            _fc("fc-title-zh", "pure", "name_zh", "人手による中題"),
        ],
    )
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)

    applied = _apply(monkeypatch, tmp_path, sb, result, "event-clear")
    assert applied["applied_event_ids"] == ["pure"]
    manifest.verify_checkpoint(sb, result, "event-clear.after", is_after_gate=True)

    rows = {row["id"]: row for row in sb.tables["field_corrections"] if row.get("id")}
    rows["fc-title-ja"]["id"] = "fc-title-zh"
    rows["fc-title-zh"]["id"] = "fc-title-ja"
    with pytest.raises(RuntimeError, match="event-clear.after preserve_field_corrections drift"):
        manifest.verify_checkpoint(sb, result, "event-clear.after", is_after_gate=True)

    rows["fc-title-ja"]["id"] = "fc-title-ja"
    rows["fc-title-zh"]["id"] = "fc-title-zh"
    manifest.verify_checkpoint(sb, result, "event-clear.after", is_after_gate=True)

    sb.tables["events"][0]["id"] = "pure-renamed"
    with pytest.raises(RuntimeError, match="event-clear.after events drift"):
        manifest.verify_checkpoint(sb, result, "event-clear.after", is_after_gate=True)


def test_apply_rejects_a_phase_the_manifest_does_not_support(monkeypatch, tmp_path):
    state = _state([_event("pure")])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)

    with pytest.raises(RuntimeError, match="does not support apply_phase=eslite-identity"):
        _apply(monkeypatch, tmp_path, sb, result, "eslite-identity")
    assert sb.writes == []


def test_apply_blocks_unresolved_location_conflicts_before_database_read(monkeypatch, tmp_path):
    state = _state([_event("venue", location_name="丸善丸の内本店")])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    calls = []
    monkeypatch.setattr(manifest, "assert_ignored_output_path", lambda path: path)
    monkeypatch.setattr(manifest, "observe_checkpoint", lambda *_args: calls.append("read"))

    with pytest.raises(RuntimeError, match="unresolved classification/location conflicts"):
        manifest.apply_manifest(
            object(),
            _stamp_citation_join(result),
            manifest_path=tmp_path / "manifest.json",
            apply_phase="fc-remove",
        )
    assert calls == []


def test_phase_snapshot_is_written_before_the_first_write(monkeypatch, tmp_path):
    event = _event("pure")
    rows = [_fc("fc-loc", "pure", "location_name", manifest.PUBLICATION_CHANNEL_LOCATION)]
    state = _state([event], field_corrections=rows)
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    sb = _fake_db(state)
    snapshots: list = []

    _apply(monkeypatch, tmp_path, sb, result, "fc-remove", snapshots=snapshots)

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot["apply_phase"] == "fc-remove"
    assert snapshot["checkpoint"] == "fc-remove.before"
    assert snapshot["checkpoint_sha256"] == result["checkpoints"]["fc-remove.before"]["sha256"]
    assert {row["id"] for row in snapshot["observed"]["target_field_corrections"]} == {"fc-loc"}


# --- Eslite pre-cleanup manifest ---------------------------------------------


def test_eslite_manifest_has_two_checkpoints_and_only_one_candidate():
    state = _state([_eslite_talk(), _event("pure")], field_corrections=_eslite_stale_fcs())
    result = manifest.build_manifest(
        state, generated_at="2026-07-11T00:00:00+00:00", scope="eslite-identity"
    )

    assert [candidate["event_id"] for candidate in result["candidates"]] == [manifest.ESLITE_TALK_ID]
    assert sorted(result["checkpoints"]) == sorted(manifest.ESLITE_CHECKPOINTS)
    assert result["apply_contract"]["supported_apply_phases"] == ["eslite-identity"]
    candidate = _candidate(result, manifest.ESLITE_TALK_ID)
    assert candidate["action_type"] == "eslite_physical_identity_migration"
    assert candidate["identity_patch"]["event_form"]["after"] == ["lecture"]
    assert candidate["identity_patch"]["source_id"]["after"] == manifest.ESLITE_NEW_SOURCE_ID
    assert candidate["migration"]["apply_order"][0] == "identity_cas_event_form_and_source_identity"
    assert [
        action["field_name"]
        for action in candidate["field_correction_actions"]
        if action["mode"] == "unlock_only"
    ] == ["location_address_zh", "location_address_en"]
    assert all(
        action["apply_phase"] == "eslite-identity"
        for action in candidate["field_correction_actions"]
    )


def test_eslite_talk_is_separate_migration_and_preserves_physical_fields():
    talk = _eslite_talk()
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
    # location_url is registry-resolved, so it is never listed as preserved.
    assert "location_url" not in candidate["migration"]["preserved_fields"]
    assert candidate["event_after"]["location_url"] == manifest.ESLITE_VENUE_URL
    assert result["summary"]["eslite_migration_actions"] == 1


def test_eslite_apply_runs_identity_first_then_locks_and_removals(monkeypatch, tmp_path):
    talk = _eslite_talk()
    state = _state([talk], field_corrections=_eslite_stale_fcs())
    result = manifest.build_manifest(
        state, generated_at="2026-07-11T00:00:00+00:00", scope="eslite-identity"
    )
    sb = _fake_db(state)

    applied = _apply(monkeypatch, tmp_path, sb, result, "eslite-identity")

    assert applied["applied_event_ids"] == [manifest.ESLITE_TALK_ID]
    first = next(write for write in sb.writes if write[0] == "events" and write[1] == "update")
    assert sorted(first[2]) == ["event_form", "source_id", "source_url"]
    assert {column for _, column, _ in first[3]} == {"id", "event_form", "source_id", "source_url"}

    row = sb.tables["events"][0]
    assert row["event_form"] == ["lecture"]
    assert row["source_id"] == manifest.ESLITE_NEW_SOURCE_ID
    assert row["business_hours"] == "13:00〜"
    assert row["location_address"] == talk["location_address"]
    assert row["price_info"] == talk["price_info"]
    assert row["location_address_zh"] is None
    assert row["location_url"] == manifest.ESLITE_VENUE_URL
    assert row["location_name_zh"] == manifest.ESLITE_VENUE_NAME_ZH
    assert row["location_name_en"] == manifest.ESLITE_VENUE_NAME_EN

    locks = {row["field_name"] for row in sb.tables["field_corrections"]}
    assert {"event_form", "business_hours", "location_address"} <= locks
    assert {"location_url", "location_name_zh", "location_name_en"} <= locks
    assert "location_address_zh" not in locks
    assert "location_address_en" not in locks


def test_eslite_identity_patch_is_a_safe_fix_forward_after_interruption():
    talk = _eslite_talk()
    result = manifest.build_manifest(
        _state([talk], field_corrections=_eslite_stale_fcs()),
        generated_at="2026-07-11T00:00:00+00:00",
        scope="eslite-identity",
    )
    candidate = _candidate(result, manifest.ESLITE_TALK_ID)

    migrated = FakeSupabase(
        {
            "events": [
                {
                    **deepcopy(talk),
                    "event_form": ["lecture"],
                    "source_id": manifest.ESLITE_NEW_SOURCE_ID,
                    "source_url": manifest.ESLITE_ARTICLE_URL,
                }
            ],
            "field_corrections": [],
            "field_corrections_audit": [],
        }
    )
    assert manifest.execute_identity_patch(migrated, candidate) == 0
    assert [write for write in migrated.writes if write[1] == "update"] == []

    third_state = FakeSupabase(
        {
            "events": [{**deepcopy(talk), "event_form": ["lecture"]}],
            "field_corrections": [],
            "field_corrections_audit": [],
        }
    )
    with pytest.raises(RuntimeError, match="third state"):
        manifest.execute_identity_patch(third_state, candidate)


def test_eslite_venue_fields_come_from_the_authoritative_registry():
    result = manifest.build_manifest(
        _state([_eslite_talk()], field_corrections=_eslite_stale_fcs()),
        generated_at="2026-07-11T00:00:00+00:00",
        scope="eslite-identity",
    )
    candidate = _candidate(result, manifest.ESLITE_TALK_ID)
    after = candidate["event_after"]
    modes = {action["field_name"]: action for action in _actions(candidate)}

    # venues.fd330e2a-e8e8-40fb-9fcb-d1af44d7be3a (is_authoritative=true)
    assert manifest.ESLITE_VENUE_URL == "https://www.eslitespectrum.jp/"
    assert manifest.ESLITE_VENUE_NAME_ZH == "誠品生活日本橋"
    assert manifest.ESLITE_VENUE_NAME_EN == "Eslite Spectrum Nihonbashi"

    assert after["location_url"] == manifest.ESLITE_VENUE_URL
    assert after["location_url"] != ESLITE_BOOK_SALES_URL
    assert modes["location_url"]["mode"] == "lock_clean"
    assert modes["location_url"]["new_value"] == manifest.ESLITE_VENUE_URL

    for field, expected in (
        ("location_name_zh", manifest.ESLITE_VENUE_NAME_ZH),
        ("location_name_en", manifest.ESLITE_VENUE_NAME_EN),
    ):
        assert modes[field]["mode"] == "lock_clean"
        assert modes[field]["new_value"] == expected
        assert after[field] == expected

    for field in ("location_address_zh", "location_address_en"):
        assert modes[field]["mode"] == "unlock_only"
        assert after[field] is None

    assert "location_url" not in candidate["migration"]["preserved_fields"]
    assert candidate["migration"]["registry_resolved_fields"] == {
        "location_url": manifest.ESLITE_VENUE_URL,
        "location_name_zh": manifest.ESLITE_VENUE_NAME_ZH,
        "location_name_en": manifest.ESLITE_VENUE_NAME_EN,
    }
    # venue_id is read off the event row, so it is preserved, never registry-resolved.
    assert "venue_id" in candidate["migration"]["preserved_fields"]
    assert not (
        set(candidate["migration"]["registry_resolved_fields"])
        & set(candidate["migration"]["preserved_fields"])
    )


def test_eslite_book_sales_page_never_reaches_a_venue_field():
    result = manifest.build_manifest(
        _state([_eslite_talk()], field_corrections=_eslite_stale_fcs()),
        generated_at="2026-07-11T00:00:00+00:00",
        scope="eslite-identity",
    )
    candidate = _candidate(result, manifest.ESLITE_TALK_ID)
    after = candidate["event_after"]
    marker = "eslitespectrum-nihonbashi.shop"

    # Write surface 1 — the event row's venue fields.
    assert after["location_url"] == manifest.ESLITE_VENUE_URL
    for field in (
        "location_url",
        "location_name",
        "location_name_zh",
        "location_name_en",
        "location_address",
        "location_address_zh",
        "location_address_en",
    ):
        assert marker not in str(after.get(field) or "")

    # Write surface 2 — every planned field-correction value.
    for action in candidate["field_correction_actions"]:
        assert marker not in str(action["new_value"] or "")

    # Write surface 3 — the after-checkpoint's location field corrections.
    location_rows = [
        row
        for row in result["checkpoints"]["eslite-identity.after"]["target_field_corrections"]
        if str(row["field_name"]).startswith("location_")
    ]
    assert location_rows
    for row in location_rows:
        assert marker not in str(manifest.decoded_fc_value(row["corrected_value"]) or "")

    # Write surface 4 — the registry-resolved values recorded by the migration.
    assert marker not in json.dumps(
        candidate["migration"]["registry_resolved_fields"], ensure_ascii=False, default=str
    )

    # Body copy is not a write surface: the purchase link is legitimate source
    # text on the live row and must survive the migration untouched.
    assert marker in after["raw_description"]
    assert marker in after["description_ja"]
    assert marker in after["description_zh"]
    assert marker in after["description_en"]

    # The before image is the CAS gate, so it must still carry the live value.
    before_events = result["checkpoints"]["eslite-identity.before"]["events"]
    assert [row["location_url"] for row in before_events] == [ESLITE_BOOK_SALES_URL]


def test_cleanup_phases_never_select_the_eslite_candidate():
    # The pure row carries a polluted target FC so `fc-remove` has real work;
    # without one it is correctly skipped and the control assertion below would
    # pass against an empty selection.
    result = manifest.build_manifest(
        _state(
            [_eslite_talk(), _event("pure")],
            field_corrections=[
                _fc("fc-loc", "pure", "location_name", manifest.PUBLICATION_CHANNEL_LOCATION)
            ],
        ),
        generated_at="2026-07-11T00:00:00+00:00",
    )

    for phase in ("fc-remove", "event-clear"):
        selected = [candidate["event_id"] for candidate in manifest.phase_candidates(result, phase)]
        assert manifest.ESLITE_TALK_ID not in selected
        assert "pure" in selected
    assert manifest.phase_candidates(result, "eslite-identity")[0]["event_id"] == manifest.ESLITE_TALK_ID


def test_a_cleanup_manifest_predating_the_eslite_migration_is_refused_before_any_write(
    monkeypatch, tmp_path
):
    state = _state(
        [_eslite_talk(), _event("pure")],
        field_corrections=[
            _fc("fc-loc", "pure", "location_name", manifest.PUBLICATION_CHANNEL_LOCATION)
        ],
    )
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    # The eslite locks this manifest can never create are exactly what made
    # `fc-remove` write the pure cohort before failing its own after gate.
    assert [
        row
        for row in result["checkpoints"]["fc-remove.after"]["target_field_corrections"]
        if row["id"] is None
    ]
    sb = _fake_db(state)
    before_fc = deepcopy(sb.tables["field_corrections"])
    snapshots: list = []

    for phase in ("fc-remove", "event-clear"):
        with pytest.raises(RuntimeError, match="eslite_physical_identity_migration") as failure:
            _apply(monkeypatch, tmp_path, sb, result, phase, snapshots=snapshots)
        assert "Apply --scope eslite-identity first" in str(failure.value)

    assert sb.writes == []
    assert sb.tables["field_corrections"] == before_fc
    assert sb.tables["field_corrections_audit"] == []
    assert snapshots == []


def test_the_eslite_guard_leaves_a_clean_cleanup_manifest_alone(monkeypatch, tmp_path):
    state = _state([_event("pure")])
    result = manifest.build_manifest(state, generated_at="2026-07-11T00:00:00+00:00")
    manifest.assert_cleanup_manifest_excludes_eslite(result)

    eslite = manifest.build_manifest(
        _state([_eslite_talk()], field_corrections=_eslite_stale_fcs()),
        generated_at="2026-07-11T00:00:00+00:00",
        scope="eslite-identity",
    )
    manifest.assert_cleanup_manifest_excludes_eslite(eslite)
    assert _apply(monkeypatch, tmp_path, _fake_db(state), result, "event-clear")[
        "applied_event_ids"
    ] == ["pure"]


# --- unchanged safety surfaces ----------------------------------------------


def test_snapshot_contains_all_four_complete_tables():
    state = _state([_event("pure")], field_corrections=[_fc("fc", "pure", "name_ja", "x")])
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
