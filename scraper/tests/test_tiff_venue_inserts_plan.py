from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import stat
from uuid import UUID

import pytest

import _oneoff_plan_tiff_venue_inserts as planner
import _oneoff_repair_authoritative_venues as repair
import venue_registry
from _oneoff_seed_authoritative_venues import SEED_DATA
from sources.tiff import _resolve_film_venues, _screen_to_nearest_cinema
from test_qa_auto_fix_unlock_only import FakeSupabase

PROJECT_REF = "cjtndektjjpvvjofdvzr"
REPOSITORY_SHA = "b" * 40
CAPTURED_AT = "2026-10-25T06:00:00+00:00"
FIXTURES = Path(__file__).parent / "fixtures"
HUMANTRUST_ID = "61f052f3-8cd0-475a-9947-cc459c482025"
CINESWITCH_ID = "be9ca259-925c-4fb4-bacc-41ed6c8a83d2"
GENERATED_IDS = [
    "20000000-0000-4000-8000-000000000001",
    "20000000-0000-4000-8000-000000000002",
    "20000000-0000-4000-8000-000000000003",
    "20000000-0000-4000-8000-000000000004",
]


def _live_venue(venue_id: str, name: str, aliases: list[str], **overrides):
    row = {
        "id": venue_id,
        "canonical_name_ja": name,
        "canonical_name_zh": name,
        "canonical_name_en": None,
        "address": "東京都千代田区有楽町1-5-1",
        "prefecture": "東京都",
        "city": "千代田区",
        "latitude": None,
        "longitude": None,
        "aliases": aliases,
        "notes": None,
        "created_at": "2026-05-01T00:00:00+00:00",
        "updated_at": "2026-05-01T00:00:00+00:00",
        "is_authoritative": True,
        "is_multi_venue": False,
        "homepage": f"https://{venue_id[:8]}.example/",
        "prefectures": ["東京都"],
        "business_hours": None,
    }
    row.update(overrides)
    return row


def _live_venues():
    return [
        _live_venue(HUMANTRUST_ID, "ヒューマントラストシネマ有楽町", ["human_yurakucho"]),
        _live_venue(CINESWITCH_ID, "シネスイッチ銀座", ["Cineswitch Ginza"]),
        _live_venue(
            "f5febc84-9084-401f-a20e-4c725283456d",
            "日比谷図書文化館",
            [],
            is_authoritative=False,
        ),
    ]


def _ids():
    values = iter(GENERATED_IDS)
    return lambda: UUID(next(values))


def _plan(live=None, **kwargs):
    return planner.build_tiff_insert_plan(
        _live_venues() if live is None else live,
        captured_at=kwargs.pop("captured_at", CAPTURED_AT),
        repository_sha=REPOSITORY_SHA,
        project_ref=PROJECT_REF,
        id_factory=kwargs.pop("id_factory", _ids()),
    )


def _client(live=None):
    return FakeSupabase({"venues": deepcopy(_live_venues() if live is None else live), "events": []})


def _preview(client, plan):
    return repair.preview_manifest(
        client,
        plan,
        project_ref=PROJECT_REF,
        repo_sha_verifier=lambda _sha: True,
        captured_at=CAPTURED_AT,
    )


def _artifact_root(monkeypatch, tmp_path):
    root = tmp_path / "worktree"
    monkeypatch.setattr(repair, "ROOT", root)
    monkeypatch.setattr(repair, "_is_git_ignored", lambda _path, *, root: True)
    return root


def _apply(client, manifest, monkeypatch, tmp_path, name):
    root = _artifact_root(monkeypatch, tmp_path)
    return repair.apply_manifest(
        client,
        manifest,
        project_ref=PROJECT_REF,
        journal_path=root / "tmp" / "tiff-venue-inserts" / name,
        repo_sha_verifier=lambda _sha: True,
    )


def _seed(name):
    return next(row for row in SEED_DATA if row.get("canonical_name_ja") == name)


def test_seed_tiff_venues_match_official_2026_sources():
    assert _seed("TOHOシネマズ シャンテ")["homepage"] == (
        "https://www.tohotheater.jp/theater/041/access.html"
    )
    assert _seed("TOHOシネマズ 日比谷 スクリーン12・13")["address"] == (
        "東京都千代田区有楽町1-1-3 東京宝塚ビル地下"
    )
    piccadilly = _seed("丸の内ピカデリー")
    assert piccadilly["address"] == "東京都千代田区有楽町2-5-1 有楽町マリオン9F"
    assert piccadilly["homepage"] == "https://www.smt-cinema.com/site/marunouchi/access.html"
    assert piccadilly["prefectures"] == ["東京都"]
    assert piccadilly["is_authoritative"] is True
    assert piccadilly["is_multi_venue"] is False
    assert "_expected_id" not in piccadilly


def test_plan_holds_exactly_four_frozen_venue_inserts():
    plan = _plan()

    assert plan["project_ref"] == PROJECT_REF
    assert plan["repository_sha"] == REPOSITORY_SHA
    assert [action["type"] for action in plan["actions"]] == ["venue_insert"] * 4
    assert [action["id"] for action in plan["actions"]] == GENERATED_IDS
    assert [
        action["after"]["venue"]["canonical_name_ja"] for action in plan["actions"]
    ] == list(planner.TIFF_INSERT_VENUE_NAMES)
    for action, name in zip(plan["actions"], planner.TIFF_INSERT_VENUE_NAMES):
        row = action["after"]["venue"]
        seed = _seed(name)
        assert set(row) == repair.VENUE_REQUIRED_FIELDS
        for field in (
            "canonical_name_zh",
            "canonical_name_en",
            "address",
            "prefecture",
            "city",
            "aliases",
            "homepage",
            "prefectures",
            "business_hours",
        ):
            assert row[field] == seed[field]
        assert row["created_at"] == row["updated_at"] == CAPTURED_AT
        assert action["before"]["venue"] is None
        assert action["after"]["venue_references"] == []
        assert action["eligibility"]["status"] == "eligible"


def test_plan_has_no_event_update_or_delete_actions():
    manifest = _preview(_client(), _plan())

    assert {action["type"] for action in manifest["actions"]} == {"venue_insert"}
    assert manifest["already_applied"] == []
    assert manifest["conflicts"] == []


@pytest.mark.parametrize(
    "existing",
    [
        _live_venue("30000000-0000-4000-8000-000000000001", "丸の内ピカデリー", []),
        _live_venue(
            "30000000-0000-4000-8000-000000000002",
            "別の劇場",
            ["TOHOシネマズシャンテ"],
            is_authoritative=False,
        ),
        _live_venue(
            "30000000-0000-4000-8000-000000000003",
            "Marunouchi Piccadilly",
            [],
        ),
    ],
    ids=["canonical-name-exists", "alias-collides-non-authoritative", "alias-as-canonical"],
)
def test_plan_stops_when_name_or_alias_already_exists(existing):
    with pytest.raises(RuntimeError, match="already exists on venues"):
        _plan([*_live_venues(), existing])


def test_plan_stops_when_generated_uuid_already_exists():
    live = [*_live_venues(), _live_venue(GENERATED_IDS[0], "既存", [])]
    with pytest.raises(RuntimeError, match="UUID already exists"):
        _plan(live)


def test_plan_stops_on_live_column_drift():
    live = _live_venues()
    live[0]["new_column"] = None
    with pytest.raises(RuntimeError, match="columns differ"):
        _plan(live)


def test_plan_stops_on_empty_snapshot_and_fractional_timestamp():
    with pytest.raises(RuntimeError, match="empty"):
        _plan([])
    with pytest.raises(RuntimeError, match="whole-second"):
        _plan(captured_at="2026-10-25T06:00:00.123456+00:00")


def test_capture_timestamp_is_whole_second_utc():
    moment = datetime(2026, 10, 25, 6, 0, 0, 987654, tzinfo=timezone.utc)
    assert planner.capture_timestamp(moment) == CAPTURED_AT


def test_apply_inserts_four_rows_then_second_apply_is_noop(monkeypatch, tmp_path):
    client = _client()
    manifest = _preview(client, _plan())

    first = _apply(client, manifest, monkeypatch, tmp_path, "first.jsonl")

    assert first["status"] == "completed"
    assert first["mutation_count"] == 4
    assert first["completed_action_ids"] == GENERATED_IDS
    inserted = [row for row in client.tables["venues"] if row["id"] in GENERATED_IDS]
    assert inserted == [action["after"]["venue"] for action in manifest["actions"]]
    untouched = [row for row in client.tables["venues"] if row["id"] not in GENERATED_IDS]
    assert untouched == _live_venues()

    second = _apply(client, manifest, monkeypatch, tmp_path, "second.jsonl")

    assert second["status"] == "noop"
    assert second["mutation_count"] == 0
    assert len(client.tables["venues"]) == len(_live_venues()) + 4


def test_apply_stops_with_zero_writes_when_a_name_appears_after_capture(
    monkeypatch,
    tmp_path,
):
    client = _client()
    manifest = _preview(client, _plan())
    client.tables["venues"].append(
        _live_venue("40000000-0000-4000-8000-000000000001", "丸の内ピカデリー", [])
    )
    before = deepcopy(client.tables["venues"])

    with pytest.raises(RuntimeError, match="partial or third state"):
        _apply(client, manifest, monkeypatch, tmp_path, "drift.jsonl")

    assert client.tables["venues"] == before


def test_capture_writes_immutable_manifest_without_mutation(monkeypatch, tmp_path):
    client = _client()
    root = _artifact_root(monkeypatch, tmp_path)
    output = root / "tmp" / "tiff-venue-inserts" / "manifest.json"

    written, manifest = repair.capture_manifest(
        client,
        _plan(),
        output,
        project_ref=PROJECT_REF,
        repo_sha_verifier=lambda _sha: True,
        captured_at=CAPTURED_AT,
    )

    assert repair.load_manifest(written) == manifest
    assert stat.S_IMODE(written.stat().st_mode) == 0o444
    assert client.tables["venues"] == _live_venues()


def test_cli_writes_plan_read_only_and_refuses_sha_off_origin_main(monkeypatch, tmp_path):
    client = _client()
    root = _artifact_root(monkeypatch, tmp_path)
    output = root / "tmp" / "tiff-venue-inserts" / "plan.json"
    kwargs = {
        "client_factory": lambda *, read_only: client,
        "project_ref_getter": lambda: PROJECT_REF,
        "repository_sha_getter": lambda: REPOSITORY_SHA,
        "now": datetime(2026, 10, 25, 6, 0, 0, tzinfo=timezone.utc),
    }

    with pytest.raises(RuntimeError, match="not on origin/main"):
        planner.run_cli(
            ["--plan-output", str(output)],
            repo_sha_verifier=lambda _sha: False,
            **kwargs,
        )
    assert not output.exists()

    result = planner.run_cli(
        ["--plan-output", str(output)],
        repo_sha_verifier=lambda _sha: True,
        **kwargs,
    )

    assert result["mutations"] == 0
    assert [venue["canonical_name_ja"] for venue in result["venues"]] == list(
        planner.TIFF_INSERT_VENUE_NAMES
    )
    plan = json.loads(output.read_text(encoding="utf-8"))
    assert plan["captured_at"] == CAPTURED_AT
    assert stat.S_IMODE(output.stat().st_mode) == 0o444
    assert client.tables["venues"] == _live_venues()
    with pytest.raises(FileExistsError):
        planner.run_cli(
            ["--plan-output", str(output)],
            repo_sha_verifier=lambda _sha: True,
            **kwargs,
        )


def test_all_2026_taiwan_films_resolve_after_inserts(monkeypatch, tmp_path):
    venues_tree = json.loads((FIXTURES / "tiff_2026_venues.json").read_text(encoding="utf-8"))
    films = json.loads((FIXTURES / "tiff_2026_taiwan_films.json").read_text(encoding="utf-8"))
    screen_map = _screen_to_nearest_cinema(venues_tree)
    client = _client()
    monkeypatch.setattr(venue_registry, "_get_client", lambda: client)

    venue_registry._reset_cache_for_tests()
    try:
        assert all(_resolve_film_venues(film, screen_map) is None for film in films)

        _apply(client, _preview(client, _plan()), monkeypatch, tmp_path, "routing.jsonl")
        venue_registry._reset_cache_for_tests()
        resolved = {
            film["film_identifier"]: _resolve_film_venues(film, screen_map) for film in films
        }
    finally:
        venue_registry._reset_cache_for_tests()

    assert len(films) == 10
    assert all(resolved.values())
    names = {
        film_id: [venue["canonical_name_ja"] for venue in venues]
        for film_id, venues in resolved.items()
    }
    assert names["39004GLS09"] == ["丸の内ピカデリー"]
    assert names["39005WFC14"] == ["TOHOシネマズ 日比谷 スクリーン12・13", "シネスイッチ銀座"]
    assert names["39001CMP01"] == [
        "ヒューリックホール東京",
        "丸の内ピカデリー",
        "ヒューマントラストシネマ有楽町",
    ]
