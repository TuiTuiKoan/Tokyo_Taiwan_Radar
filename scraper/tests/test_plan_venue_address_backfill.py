"""Read-only venue address backfill planner (venue-ground-truth Phase D, step 4a)."""

from datetime import datetime, timezone

from plan_venue_address_backfill import plan, render_markdown

NOW = datetime(2026, 11, 22, tzinfo=timezone.utc)
T0 = "2026-11-01T00:00:00+00:00"
ADDR = "大阪府大阪市港区弁天1-2-3 ORC200"


def _e(i, name, address, source="s1", start="2026-12-01", **extra):
    return {"id": f"e{i}", "location_name": name, "location_address": address, "source_name": source,
            "created_at": T0, "start_date": start, "end_date": None, "event_form": ["lecture"], **extra}


def _lock(eid, value, **extra):
    return {"event_id": eid, "field_name": "location_address", "corrected_value": value,
            "corrected_by": None, "report_id": None, "created_at": T0, **extra}


def _stub(vid, name, **extra):
    return {"id": vid, "canonical_name_ja": name, "address": None,
            "is_authoritative": False, "is_multi_venue": False, **extra}


def test_backfill_needs_independent_same_name_evidence_and_counts_reachable_events():
    events = [
        _e(1, "台湾華語教室", ADDR, "note", start="2026-01-01"),
        _e(2, "台湾華語教室", ADDR, "peatix", start="2026-02-01"),
        _e(3, "台湾華語教室", "大阪府大阪市港区"),              # upcoming, unlocked: reachable
        _e(4, "台湾華語教室", "大阪府大阪市港区"),              # upcoming but locked
        _e(5, "別の館", ADDR, "s1"), _e(6, "別の館", ADDR, "s1"),  # one source only
    ]
    locks = [_lock("e1", ADDR), _lock("e2", ADDR), _lock("e4", "大阪府大阪市港区"),
             _lock("e5", ADDR), _lock("e6", ADDR)]
    venues = [_stub("v1", "台湾華語教室"), _stub("v2", "別の館")]

    report = plan(events, venues, locks, NOW)

    assert [b["canonical_name_ja"] for b in report["venue_backfill"]] == ["台湾華語教室"]
    backfill = report["venue_backfill"][0]
    assert backfill["address"] == ADDR and backfill["upcoming_reachable"] == 1
    assert backfill["upcoming_reachable_events"] == ["https://tokyotaiwanradar.com/ja/events/e3"]
    assert report["phase_4b_recommended"] is False


def test_venue_id_alone_is_not_same_name_evidence():
    """Non-authoritative venue_id links come from fuzzy clustering (#371)."""
    events = [_e(1, "似た名前A", ADDR, "s1", venue_id="v1"), _e(2, "似た名前B", ADDR, "s2", venue_id="v1")]
    locks = [_lock("e1", ADDR), _lock("e2", ADDR)]
    assert plan(events, [_stub("v1", "本当の名前")], locks, NOW)["venue_backfill"] == []


def test_stale_and_copy_locks_and_org_names():
    venues = [{"id": "a1", "canonical_name_ja": "センチュリーシネマ", "address": "愛知県名古屋市中区栄3-29-1 名古屋パルコ東館8F",
               "is_authoritative": True, "is_multi_venue": False}]
    events = [
        _e(1, "センチュリーシネマ", "愛知県名古屋市中区栄3-15-13", venue_id="a1"),
        _e(2, "センチュリーシネマ", "愛知県名古屋市中区栄3-29-1", venue_id="a1"),
        _e(3, "NPO法人日台協会", "埼玉県", organizer="NPO法人日台協会"),
    ]
    locks = [
        _lock("e1", "愛知県名古屋市中区栄3-15-13 スカイルビル地下2F"),
        _lock("e2", '"愛知県名古屋市中区栄３丁目２９−１"'),
        _lock("e1", "x", corrected_by="admin") | {"field_name": "location_name"},
    ]
    report = plan(events, venues, locks, NOW)

    assert [s["event"][-2:] for s in report["stale_auto_locks"]] == ["e1"]
    assert report["stale_auto_locks"][0]["upcoming"] is True
    assert [c["event"][-2:] for c in report["copy_locks"]] == ["e2"]
    assert report["org_as_venue"] == ["NPO法人日台協会"]
    markdown = render_markdown(report)
    assert "解鎖是 production 寫入" in markdown and "只列給使用者判斷" in markdown


def test_publications_and_inactive_events_are_ignored():
    events = [_e(1, "書店", ADDR, event_form=["publication"]), _e(2, "書店", ADDR, "s2", is_active=False)]
    assert plan(events, [_stub("v1", "書店")], [_lock("e1", ADDR), _lock("e2", ADDR)], NOW)["venue_backfill"] == []


def test_stub_named_like_an_authoritative_venue_is_a_duplicate_not_a_backfill():
    events = [_e(1, "台湾文化センター", ADDR, raw_description=f"会場 {ADDR}")]
    venues = [
        _stub("stub", "台湾文化センター"),
        {"id": "auth", "canonical_name_ja": "台北駐日経済文化代表処 台湾文化センター", "aliases": ["台湾文化センター"],
         "address": ADDR, "is_authoritative": True, "is_multi_venue": False},
    ]
    report = plan(events, venues, [], NOW)

    assert report["venue_backfill"] == []
    assert report["duplicate_of_authoritative"] == [{
        "venue_id": "stub", "canonical_name_ja": "台湾文化センター",
        "authoritative": "台北駐日経済文化代表処 台湾文化センター",
    }]
