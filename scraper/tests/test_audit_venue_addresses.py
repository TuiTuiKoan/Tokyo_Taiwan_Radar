"""Read-only venue address audit (spec venue-ground-truth, Phase A)."""

from datetime import datetime, timezone

from audit_venue_addresses import (
    IN_SCOPE,
    NO_VENUE,
    QA_EXCLUDED,
    SAMPLE_PER_GRADE,
    audit,
    render_markdown,
    render_sample,
    scope_of,
)

NOW = datetime(2026, 11, 22, tzinfo=timezone.utc)
STREET_A = "東京都港区虎ノ門1-1-12 虎ノ門ビル2階"


def _event(i, name, address, *, source="peatix", venue_id=None, form=None,
           start="2026-12-01T10:00:00+00:00", created="2026-11-01T00:00:00+00:00"):
    return {
        "id": f"e{i}", "source_name": source, "location_name": name, "location_address": address,
        "venue_id": venue_id, "event_form": form or ["lecture"], "created_at": created,
        "start_date": start, "end_date": None,
    }


def test_scope_follows_auto_qa_predicates():
    assert scope_of(_event(1, "紫明会館", None)) == IN_SCOPE
    assert scope_of(_event(2, "オンライン", None)) == NO_VENUE
    assert scope_of(_event(3, "BS11", None, source="gguide_tv")) == NO_VENUE
    assert scope_of(_event(4, "書名", None, form=["publication"])) == NO_VENUE
    # A publication that is also a lecture keeps physical-event behaviour.
    assert scope_of(_event(5, "紫明会館", None, form=["publication", "lecture"])) == IN_SCOPE
    assert scope_of(_event(6, "某ホール", None, source="prtimes")) == QA_EXCLUDED


def test_counts_grades_and_windows():
    events = [
        _event(1, "台湾文化センター", STREET_A),
        _event(2, "紫明会館", "京都府京都市"),
        _event(3, "紫明会館", None, start="2026-01-01T00:00:00+00:00", created="2026-01-01T00:00:00+00:00"),
        _event(4, "オンライン", None),
        _event(5, "", STREET_A),
        _event(6, "台北世界貿易センター", "台北市信義區信義路五段5號"),
    ]
    report = audit(events, [], NOW)

    assert report["scopes"] == {IN_SCOPE: 4, NO_VENUE: 1}
    everything = report["in_scope"]["all"]
    assert everything["total"] == 4
    # The Taipei address is counted but is neither "needs fix" nor in the rate.
    assert everything["grades"]["non_japan"] == 1
    assert everything["needs_fix"] == 2
    assert everything["grades"]["street"] == 1
    assert everything["grades"]["region"] == 1
    assert everything["grades"]["empty"] == 1
    assert everything["street_rate"] == 0.3333
    assert report["in_scope"]["upcoming"]["total"] == 3
    assert report["in_scope"]["created_last_60_days"]["total"] == 3
    assert report["in_scope"]["without_venue_id"] == 4
    assert [g["location_name"] for g in report["venue_gaps"]] == ["紫明会館"]


def test_venue_gaps_group_by_name_and_put_upcoming_first():
    events = [
        _event(1, "A館", None, start="2026-01-01T00:00:00+00:00"),
        _event(2, "A館", None, start="2026-01-02T00:00:00+00:00"),
        _event(3, "A館", STREET_A, start="2026-01-03T00:00:00+00:00"),
        _event(4, "B館", "東京都"),
        _event(5, "C館", STREET_A),
    ]
    gaps = audit(events, [], NOW)["venue_gaps"]

    assert [g["location_name"] for g in gaps] == ["B館", "A館"]
    a = gaps[1]
    assert a["missing_events"] == 2 and a["total_events"] == 3 and a["upcoming_missing"] == 0
    assert a["sibling_street_addresses"] == [STREET_A]
    assert gaps[0]["example_event"] == "https://tokyotaiwanradar.com/ja/events/e4"


def test_registry_backfill_candidates_need_exactly_one_street_address():
    venues = [
        {"id": "v1", "canonical_name_ja": "一致館", "address": None, "is_authoritative": False, "is_multi_venue": False},
        {"id": "v2", "canonical_name_ja": "衝突館", "address": "", "is_authoritative": False, "is_multi_venue": False},
        {"id": "v3", "canonical_name_ja": "無證據館", "address": None, "is_authoritative": False, "is_multi_venue": False},
        {"id": "v4", "canonical_name_ja": "已有地址館", "address": STREET_A, "is_authoritative": True, "is_multi_venue": False},
        {"id": "v5", "canonical_name_ja": "影展", "address": None, "is_authoritative": True, "is_multi_venue": True},
    ]
    events = [
        # Full-width and half-width spellings of one address count as one.
        _event(1, "一致館", "東京都中央区日本橋室町3丁目2-1", venue_id="v1"),
        _event(2, "一致館", "東京都中央区日本橋室町３丁目２-１", venue_id="v1"),
        _event(3, "衝突館", STREET_A, venue_id="v2"),
        _event(4, "衝突館", "大阪府大阪市西区九条1-20-24", venue_id="v2"),
        _event(5, "無證據館", "東京都", venue_id="v3"),
        _event(6, "影展", STREET_A, venue_id="v5"),
    ]
    registry = audit(events, venues, NOW)["registry"]

    assert registry["venues"] == 5 and registry["authoritative"] == 2
    assert registry["without_address"] == 3
    assert [v["canonical_name_ja"] for v in registry["backfill_candidates"]] == ["一致館"]
    assert registry["backfill_candidates"][0]["addresses"] == {"東京都中央区日本橋室町3丁目2-1": 2}
    assert [v["canonical_name_ja"] for v in registry["backfill_conflicts"]] == ["衝突館"]
    assert registry["without_address_and_without_evidence"] == 1


def test_markdown_lists_event_links_not_bare_ids():
    report = audit([_event(1, "A|館", None)], [], NOW)
    markdown = render_markdown(report)

    assert "[活動頁](https://tokyotaiwanradar.com/ja/events/e1)" in markdown
    assert "| A｜館 |" in markdown


def test_reports_both_denominators_for_qa_excluded_sources():
    events = [
        _event(1, "A館", STREET_A),
        _event(2, "B館", None, source="prtimes"),
        _event(3, "C館", STREET_A, source="note_creators"),
    ]
    report = audit(events, [], NOW)

    assert report["in_scope"]["all"]["street_rate"] == 1.0
    assert report["qa_excluded"]["total"] == 2 and report["qa_excluded"]["needs_fix"] == 1
    assert report["in_scope_plus_qa_excluded"]["street_rate"] == 0.6667
    assert report["in_scope_plus_qa_excluded_upcoming"]["total"] == 3
    assert report["in_scope_plus_qa_excluded_created_last_60_days"]["needs_fix"] == 1
    # QA-excluded sources never enter the per-venue gap list.
    assert report["venue_gaps"] == []


def test_counts_phase_b_impact_and_hybrid_events():
    events = [
        _event(1, "A館", "東京都港区六本木"),            # is_vague() says specific, the grader says TOWN
        _event(2, "B館", "東京都"),                      # both say vague
        _event(3, "C館 / オンライン", STREET_A),         # hybrid: dropped from venue QA today
        _event(4, "オンライン", None),
    ]
    report = audit(events, [], NOW)

    assert report["not_vague_but_needs_fix"] == 1
    assert report["online_named_with_street_address"] == 1


def test_lists_authoritative_venues_without_address():
    venues = [
        {"id": "v1", "canonical_name_ja": "影展", "address": None, "is_authoritative": True, "is_multi_venue": True},
        {"id": "v2", "canonical_name_ja": "漏填館", "address": "", "is_authoritative": True, "is_multi_venue": False},
        {"id": "v3", "canonical_name_ja": "殘樁", "address": None, "is_authoritative": False, "is_multi_venue": False},
    ]
    registry = audit([], venues, NOW)["registry"]

    assert registry["authoritative_without_address"] == [
        {"canonical_name_ja": "影展", "is_multi_venue": True},
        {"canonical_name_ja": "漏填館", "is_multi_venue": False},
    ]
    assert "影展（多會場）、漏填館" in render_markdown(audit([], venues, NOW))


def test_sample_is_stable_distinct_and_capped():
    events = [_event(i, f"館{i}", f"東京都港区虎ノ門1-1-{i}") for i in range(SAMPLE_PER_GRADE + 10)]
    events += [_event(900, "重複館", "東京都港区虎ノ門1-1-1"), _event(901, "空白館", None)]

    first = audit(events, [], NOW)["grade_samples"]
    second = audit(list(reversed(events)), [], NOW)["grade_samples"]

    assert first == second
    assert set(first) == {"street"}
    assert len(first["street"]) == SAMPLE_PER_GRADE == len(set(first["street"]))
    assert "## street 街道級（合格）（30）" in render_sample(audit(events, [], NOW))
