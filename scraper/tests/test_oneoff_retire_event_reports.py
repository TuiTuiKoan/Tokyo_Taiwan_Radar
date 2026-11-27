"""Planning logic of _oneoff_retire_event_reports.py (spec no-event-reports)."""

import json

from _oneoff_retire_event_reports import (
    plan_category_corrections,
    plan_events,
    plan_field_corrections,
    read_id_file,
)
from event_report import EVENT_REPORT_REASON


def _row(id_, title, source="taiwan_cultural_center", cats=("movie", "report"), forms=("screening_with_talk",),
         active=True, name=None):
    return {"id": id_, "source_name": source, "raw_title": title, "name_ja": name or title, "name_zh": None,
            "name_en": None, "category": list(cats), "event_form": list(forms), "is_active": active,
            "parent_event_id": None, "updated_at": "2026-11-01T00:00:00+00:00"}


def _patch(plan, id_):
    return next(u["patch"] for u in plan["updates"] if u["id"] == id_)


def test_recap_is_deactivated_and_untagged_with_prefix_removed():
    plan = plan_events([_row("a", "映画『うなぎ』トークイベント レポート", name="【レポート】映画『うなぎ』")], [], set())
    p = _patch(plan, "a")
    assert p["category"] == ["movie"]
    assert p["name_ja"] == "映画『うなぎ』"
    assert p["is_active"] is False and p["deactivated_reason"] == EVENT_REPORT_REASON
    assert [r["id"] for r in plan["buckets"]["deactivate"]] == ["a"]


def test_prefix_on_name_does_not_make_a_recap():
    # raw_title decides, not the injected name prefix
    plan = plan_events([_row("b", "台湾映画上映会", name="【レポート】台湾映画上映会")], [], set())
    assert "is_active" not in _patch(plan, "b")


def test_publication_and_upcoming_presentation_only_lose_the_tag():
    rows = [
        _row("p", "台湾研修報告", source="ndl_opensearch", forms=("publication",)),
        _row("u", "アジア教育視察2026報告会", source="kokuchpro", forms=("lecture",)),
    ]
    plan = plan_events(rows, [], set())
    for id_ in ("p", "u"):
        assert _patch(plan, id_) == {"category": ["movie"]}


def test_news_source_goes_to_review_and_extra_ids_deactivate():
    row = _row("n", "ジュディ・オング、母親への思いを語る", source="tiff_jp")
    assert [r["id"] for r in plan_events([row], [], set())["buckets"]["review"]] == ["n"]
    plan = plan_events([row], [], {"n"})
    assert _patch(plan, "n")["is_active"] is False


def test_empty_category_bucket_and_inactive_rows_only_untagged():
    rows = [_row("e", "台湾フェス", cats=("report",), source="iwafu"),
            _row("i", "トークイベント レポート", active=False)]
    plan = plan_events(rows, [], set())
    assert [r["id"] for r in plan["buckets"]["empty_category"]] == ["e"]
    assert _patch(plan, "i") == {"category": ["movie"]}


def test_active_children_of_deactivated_reports_follow():
    parent = _row("a", "開催報告｜台湾祭", source="prtimes", forms=("market",))
    child = {"id": "c", "parent_event_id": "a", "is_active": True, "updated_at": "x", "source_name": "prtimes"}
    plan = plan_events([parent], [child], set())
    assert _patch(plan, "c")["is_active"] is False


def test_field_and_category_corrections():
    fcs = [
        {"id": 1, "field_name": "category", "corrected_value": json.dumps(["business", "report"])},
        {"id": 2, "field_name": "name_zh", "corrected_value": "【活動報導】選拔結果公告"},
        {"id": 3, "field_name": "name_en", "corrected_value": "Kyoto Taiwan Fest"},
    ]
    assert plan_field_corrections(fcs) == [
        {"id": 1, "corrected_value": '["business"]'},
        {"id": 2, "corrected_value": "選拔結果公告"},
    ]
    ccs = [{"id": 9, "ai_category": ["movie", "report"], "corrected_category": ["movie"]},
           {"id": 8, "ai_category": ["art"], "corrected_category": ["movie"]}]
    assert plan_category_corrections(ccs) == [{"id": 9, "patch": {"ai_category": ["movie"]}}]


def test_read_id_file_ignores_comments_and_blanks():
    assert read_id_file("# note\n\n a \nb\n  # x\n") == {"a", "b"}


def test_confirmed_review_file_has_36_uuids():
    from pathlib import Path
    import uuid

    f = Path(__file__).resolve().parents[2] / "docs/specs/active/no-event-reports/review-confirmed-2026-11-22.txt"
    ids = read_id_file(f.read_text(encoding="utf-8"))
    assert len(ids) == 36
    for i in ids:
        uuid.UUID(i)
