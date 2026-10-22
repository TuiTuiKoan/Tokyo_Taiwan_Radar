import annotator
from person_name_lookup import PersonInfo


def test_pick_title_prefers_bracket_for_news_sources():
    event = {
        "source_name": "google_news_rss",
        "raw_title": "映画「霧のごとく」公開へ",
        "name_ja": "映画公開",
    }
    assert annotator._pick_person_lookup_title(event) == ("bracket", "霧のごとく")


def test_pick_title_falls_back_to_name_ja_then_raw_title():
    assert annotator._pick_person_lookup_title(
        {"source_name": "sakurazaka", "name_ja": "霧のごとく", "raw_title": "x"}
    ) == ("name_ja", "霧のごとく")
    assert annotator._pick_person_lookup_title(
        {"source_name": "sakurazaka", "raw_title": "霧のごとく"}
    ) == ("raw_title", "霧のごとく")
    assert annotator._pick_person_lookup_title({"source_name": "sakurazaka"}) == ("none", "")


def test_resolve_event_people_uses_film_lookup_for_eligible_events(monkeypatch):
    people = {"ケイトリン・ファン": PersonInfo(name_zh="方郁婷", name_en="Caitlin Fang", role="出演")}
    monkeypatch.setattr(annotator, "lookup_person_names", lambda title: people)

    def _unexpected(name):
        raise AssertionError("katakana fallback must not run when the film lookup succeeds")

    monkeypatch.setattr(annotator, "lookup_single_person", _unexpected)
    assert annotator._resolve_event_people({"raw_description": ""}, "霧のごとく", True) is people


def test_resolve_event_people_falls_back_to_katakana_names(monkeypatch):
    info = PersonInfo(name_zh="柯煒林", name_en=None, role="")
    monkeypatch.setattr(annotator, "lookup_person_names", lambda title: {})
    monkeypatch.setattr(annotator, "lookup_single_person", lambda name: info)
    result = annotator._resolve_event_people(
        {"raw_title": "霧のごとく", "raw_description": "出演 ウィル・オー"}, "霧のごとく", True,
    )
    assert result == {"ウィル・オー": info}


def test_fix_descriptions_with_people_only_returns_changed_fields(monkeypatch):
    people = {
        "ケイトリン・ファン": PersonInfo(name_zh="方郁婷", name_en="Caitlin Fang", role="出演"),
    }
    monkeypatch.setattr(
        annotator, "_fix_person_names_gpt", lambda client, desc, mappings: "演員包括方郁婷"
    )
    monkeypatch.setattr(annotator, "_fix_person_names_gpt_en", lambda client, desc, mappings: None)

    update = annotator._fix_descriptions_with_people(None, "演員包括凱特琳·范", "cast Caitlin Fang", people)

    assert update == {"description_zh": "演員包括方郁婷"}


def test_fix_descriptions_with_people_skips_empty_descriptions():
    people = {"A": PersonInfo(name_zh="甲", name_en="A", role="出演")}
    assert annotator._fix_descriptions_with_people(None, "", "", people) == {}
