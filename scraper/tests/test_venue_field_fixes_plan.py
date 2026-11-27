"""Plan for the six authoritative venue field fixes (#733), run through the existing engine."""

from __future__ import annotations

from copy import deepcopy

import pytest

import _oneoff_plan_venue_field_fixes as planner
import _oneoff_repair_authoritative_venues as repair
from test_qa_auto_fix_unlock_only import FakeSupabase

PROJECT_REF = "cjtndektjjpvvjofdvzr"
REPOSITORY_SHA = "c" * 40
CAPTURED_AT = "2026-11-22T06:00:00+00:00"
HATCHOZA, SALON, CENTURY, TCC = (fix["id"] for fix in planner.VENUE_FIELD_FIXES)
OTHER = "90000000-0000-4000-8000-000000000001"


def _venue(venue_id, name, aliases, **overrides):
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
        "aliases": list(aliases),
        "notes": None,
        "created_at": "2026-05-01T00:00:00+00:00",
        "updated_at": "2026-05-01T00:00:00+00:00",
        "is_authoritative": True,
        "is_multi_venue": False,
        "homepage": "https://old.example/",
        "prefectures": ["東京都"],
        "business_hours": None,
    }
    row.update(overrides)
    return row


def _live():
    """The six venues as read from production on 2026-11-22 (#733), plus one other."""
    return [
        _venue(HATCHOZA, "八丁座", ["Hatchobori", "サロンシネマ", "サロンシネマ1・2"],
               address="広島県広島市中区胡町6-26 福屋八丁堀本店8F", homepage="https://johakyu.co.jp"),
        _venue(SALON, "サロンシネマ", ["Salon Cinema", "サロンシネマ1・2"],
               address="広島県広島市中区八丁堀16-10 タカタビル8F", homepage="https://johakyu.co.jp"),
        _venue(CENTURY, "センチュリーシネマ", [],
               address="愛知県名古屋市中区栄3-15-13 スカイルビル地下2F",
               homepage="https://www.starcat-ticket.com/cc/theater/century/schedule",
               latitude=35.16, longitude=136.90),
        _venue(TCC, "台北駐日経済文化代表処 台湾文化センター",
               ["台北駐日経済文化代表処台湾文化センター", "台湾文化センター", "台湾文化中心"],
               address="東京都港区虎ノ門1-1-12 虎ノ門ビル2階",
               homepage="https://www.taiwanembassy.org/jp_ja/post/84095.html"),
        _venue(OTHER, "ほかの館", ["別館"]),
    ]


def _events():
    return [
        {"id": "e-century-1", "venue_id": CENTURY, "annotation_status": "annotated", "is_active": True},
        {"id": "e-century-2", "venue_id": CENTURY, "annotation_status": "reviewed", "is_active": True},
        {"id": "e-century-3", "venue_id": CENTURY, "annotation_status": "annotated", "is_active": True},
        {"id": "e-tcc-1", "venue_id": TCC, "annotation_status": "annotated", "is_active": True},
        {"id": "e-other", "venue_id": OTHER, "annotation_status": "annotated", "is_active": True},
    ]


def _client(live=None):
    return FakeSupabase({
        "venues": deepcopy(_live() if live is None else live),
        "events": _events(),
        "field_corrections": [
            {"id": "fc1", "event_id": "e-century-3", "field_name": "location_address",
             "corrected_value": "愛知県名古屋市中区栄3-15-13 スカイルビル地下2F"},
            {"id": "fc2", "event_id": "e-tcc-1", "field_name": "location_name", "corrected_value": "x"},
        ],
    })


def _plan(client=None, live=None):
    client = client or _client(live)
    return planner.build_venue_fix_plan(
        planner.fetch_all_venues(client),
        planner.fetch_references(client, [fix["id"] for fix in planner.VENUE_FIELD_FIXES]),
        captured_at=CAPTURED_AT,
        repository_sha=REPOSITORY_SHA,
        project_ref=PROJECT_REF,
    )


def _changed_fields(action):
    before, after = action["before"]["venue"], action["after"]["venue"]
    return {k for k in before if before[k] != after[k]}


def test_plan_changes_only_the_listed_fields():
    plan = _plan()
    by_name = {a["evidence"]["canonical_name_ja"]: a for a in plan["actions"]}

    assert {a["type"] for a in plan["actions"]} == {"venue_update"}
    assert set(by_name) == {"八丁座", "サロンシネマ", "センチュリーシネマ", "台北駐日経済文化代表処 台湾文化センター"}
    assert _changed_fields(by_name["八丁座"]) == {"aliases", "homepage"}
    assert by_name["八丁座"]["after"]["venue"]["aliases"] == ["Hatchobori"]
    assert _changed_fields(by_name["サロンシネマ"]) == {"address", "homepage"}
    # A moved venue loses the coordinates of its old building.
    assert _changed_fields(by_name["センチュリーシネマ"]) == {"address", "homepage", "latitude", "longitude"}
    tcc = by_name["台北駐日経済文化代表処 台湾文化センター"]
    assert _changed_fields(tcc) == {"aliases", "homepage"}
    assert tcc["after"]["venue"]["aliases"][-1] == "台湾駐日本代表処台湾文化センター"
    assert all(a["evidence"]["official_page"].startswith("https://") for a in plan["actions"])


def test_plan_reports_which_events_the_fix_reaches():
    plan = _plan()

    assert plan["event_impact"]["センチュリーシネマ"] == {
        "events": 3, "reviewed": 1, "address_locked": 1, "will_update": 1,
    }
    assert plan["event_impact"]["台北駐日経済文化代表処 台湾文化センター"]["will_update"] == 1
    century = next(a for a in plan["actions"] if a["id"] == CENTURY)
    assert century["before"]["venue_references"] == ["e-century-1", "e-century-2", "e-century-3"]


def test_already_fixed_venues_are_skipped():
    live = _live()
    live[0].update(homepage="https://johakyu.co.jp/", aliases=["Hatchobori"])
    plan = _plan(live=live)

    assert HATCHOZA not in {a["id"] for a in plan["actions"]}
    assert {"id": HATCHOZA, "reason": "exact_desired_venue_state"} in plan["skips"]


@pytest.mark.parametrize("mutate, message", [
    (lambda live: live.pop(1), "does not exist"),
    (lambda live: live[1].update(canonical_name_ja="サロンシネマ2"), "is now"),
    (lambda live: live[2].update(is_authoritative=False), "not a single authoritative venue"),
    (lambda live: live[4].update(aliases=["台湾駐日本代表処台湾文化センター"]), "would be shared"),
    (lambda live: live[4].update(extra_column=1), "columns differ"),
])
def test_plan_stops_on_drift(mutate, message):
    live = _live()
    mutate(live)
    with pytest.raises(RuntimeError, match=message):
        _plan(live=live)


def _root(monkeypatch, tmp_path):
    root = tmp_path / "worktree"
    monkeypatch.setattr(repair, "ROOT", root)
    monkeypatch.setattr(repair, "_is_git_ignored", lambda _path, *, root: True)
    return root


def test_engine_applies_then_noops_then_rolls_back(monkeypatch, tmp_path):
    client = _client()
    plan = _plan(client)
    plan.pop("event_impact")
    manifest = repair.preview_manifest(
        client, plan, project_ref=PROJECT_REF, repo_sha_verifier=lambda _sha: True, captured_at=CAPTURED_AT,
    )
    root = _root(monkeypatch, tmp_path)

    def run(fn, name):
        return fn(client, manifest, project_ref=PROJECT_REF,
                  journal_path=root / "tmp" / "venue-field-fixes" / name,
                  repo_sha_verifier=lambda _sha: True)

    first = run(repair.apply_manifest, "apply.jsonl")
    assert first["status"] == "completed" and first["mutation_count"] == 4
    salon = next(v for v in client.tables["venues"] if v["id"] == SALON)
    assert salon["address"] == "広島県広島市中区八丁堀16-10 広島東映プラザビル8階"
    assert client.tables["events"] == _events()   # events are never touched

    assert run(repair.apply_manifest, "again.jsonl")["status"] == "noop"
    back = run(repair.rollback_manifest, "rollback.jsonl")
    assert back["status"] == "completed"
    restored = {v["id"]: {k: v[k] for k in v if k != "updated_at"} for v in client.tables["venues"]}
    original = {v["id"]: {k: v[k] for k in v if k != "updated_at"} for v in _live()}
    assert restored == original
