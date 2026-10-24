"""Scoring v2 for the annotator golden set (#324) and validated output (#383)."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

from eval_annotator import (
    BUCKET_ANNOTATOR,
    BUCKET_LOOKUP,
    build_snapshot,
    compare_fields,
    fuzzy_score,
    is_title_lookup_case,
    normalize_annotation,
    normalize_text,
    semantic_scores_for,
    write_report,
)


def _exp(value, tier=1):
    return {"value": value, "tier": tier, "from_fc": True}


def _by_field(results):
    return {r["field"]: r for r in results}


# ─── Normalization and fuzzy ──────────────────────────────────────────────────

def test_normalize_ignores_quotes_brackets_width_and_case():
    assert normalize_text('"ADRIFT"') == normalize_text("adrift")
    assert normalize_text("「大濛」") == normalize_text("大濛")
    assert normalize_text("シネマ・クレール 丸の内１・２") == normalize_text("シネマクレール丸の内12")


def test_fuzzy_score_bounds():
    assert fuzzy_score("大濛", "大濛") == 1.0
    assert fuzzy_score("大濛", None) == 0.0
    assert fuzzy_score("大濛", "") == 0.0
    assert 0.0 < fuzzy_score("Taiwan Cultural Center", "Taiwan Cultural Centre") < 1.0


def test_location_name_passes_on_punctuation_only_difference():
    r = _by_field(compare_fields({"location_name": _exp('"ADRIFT"')}, {"location_name": "ADRIFT"}))
    assert r["location_name"]["match"] is True
    assert r["location_name"]["method"] == "fuzzy"


def test_location_name_fails_when_missing():
    r = _by_field(compare_fields({"location_name": _exp("シネマ・クレール")}, {"location_name": None}))
    assert r["location_name"]["match"] is False
    assert r["location_name"]["score"] == 0.0


def test_list_and_bool_fields_keep_exact_semantics():
    r = _by_field(compare_fields(
        {"category": _exp(["movie", "art"]), "is_paid": _exp(True), "description_zh": None},
        {"category": ["art", "movie"], "is_paid": False},
    ))
    assert r["category"]["match"] is True and r["category"]["method"] == "set"
    assert r["is_paid"]["match"] is False and r["is_paid"]["method"] == "exact"
    assert "description_zh" not in r


# ─── Semantic ─────────────────────────────────────────────────────────────────

def test_description_uses_precomputed_semantic_score():
    exp = {"description_zh": _exp("台灣電影上映。"), "description_en": _exp("A Taiwanese film.")}
    r = _by_field(compare_fields(
        exp,
        {"description_zh": "完全不同的文字", "description_en": "Different words"},
        semantic_scores={"description_zh": 0.91, "description_en": 0.42},
    ))
    assert r["description_zh"]["method"] == "semantic" and r["description_zh"]["match"] is True
    assert r["description_en"]["method"] == "semantic" and r["description_en"]["match"] is False


def test_description_falls_back_to_fuzzy_without_semantic_score():
    r = _by_field(compare_fields({"description_en": _exp("A film.")}, {"description_en": "A film."}))
    assert r["description_en"]["method"] == "fuzzy" and r["description_en"]["match"] is True


class _FakeEmbeddings:
    """Embeds text as a 2-d vector: same leading word → same direction."""

    def __init__(self):
        self.calls = []

    async def create(self, model, input):
        self.calls.append(list(input))
        vecs = [[1.0, 0.0] if t.startswith("A") else [0.0, 1.0] for t in input]
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=v) for v in vecs],
            usage=SimpleNamespace(total_tokens=10 * len(input)),
        )


def test_semantic_scores_and_negative_control():
    fake = _FakeEmbeddings()
    client = SimpleNamespace(embeddings=fake)
    cases = [
        {"expected": {"description_en": _exp("A first")}},
        {"expected": {"description_en": _exp("B second")}},
        {"expected": {"description_en": _exp("A third")}},
    ]
    annotations = [{"description_en": "A one"}, {"description_en": "B two"}, {"description_en": ""}]
    scores, negative, usage = asyncio.run(semantic_scores_for(client, cases, annotations))
    assert scores[0]["description_en"] == 1.0
    assert scores[1]["description_en"] == 1.0
    assert scores[2]["description_en"] == 0.0  # empty output: no embedding call for it
    assert len(fake.calls) == 1 and len(fake.calls[0]) == 4
    # Cross pairs: case0-exp vs case1-got (orthogonal) and case1-exp vs case0-got (orthogonal).
    assert negative["description_en"] == [0.0, 0.0]
    assert usage.total_tokens == 40


# ─── Title lookup bucket ──────────────────────────────────────────────────────

def test_movie_case_detected_from_category_or_cinema_source():
    assert is_title_lookup_case({"source_name": "peatix", "expected": {}}, {"category": ["movie"]})
    assert is_title_lookup_case(
        {"source_name": "peatix", "expected": {"category": _exp(["movie", "lecture"])}}, {"category": ["lecture"]}
    )
    assert is_title_lookup_case({"source_name": "ks_cinema", "expected": {}}, {})
    assert not is_title_lookup_case({"source_name": "peatix", "expected": {}}, {"category": ["lecture"]})


def test_movie_titles_go_to_lookup_bucket_other_fields_stay():
    r = _by_field(compare_fields(
        {"name_zh": _exp("大濛"), "name_en": _exp("A Foggy Tale"), "location_name": _exp("K's cinema")},
        {"name_zh": "霧的如同", "name_en": "Like the Mist", "location_name": "K's cinema"},
        title_lookup=True,
    ))
    assert r["name_zh"]["bucket"] == BUCKET_LOOKUP
    assert r["name_en"]["bucket"] == BUCKET_LOOKUP
    assert r["location_name"]["bucket"] == BUCKET_ANNOTATOR


def _sample_diffs():
    movie = compare_fields(
        {"name_zh": _exp("大濛"), "location_name": _exp("K's cinema")},
        {"name_zh": "霧的如同", "location_name": "K's cinema"},
        title_lookup=True,
    )
    event = compare_fields(
        {"name_zh": _exp("台灣文化講座"), "category": _exp(["lecture"])},
        {"name_zh": "台灣文化講座", "category": ["art"]},
    )
    cases = [{"case_id": "m1", "source_name": "ks_cinema"}, {"case_id": "e1", "source_name": "peatix"}]
    return cases, [movie, event]


def test_snapshot_keeps_all_buckets_in_per_field_and_splits_the_rest():
    cases, diffs = _sample_diffs()
    snap = build_snapshot(cases, diffs, {"mode": "frozen", "stage": 1}, 1.0, [None, None])
    assert snap["scoring_version"] == 2
    # Existing CI guards read per_field.name_zh: both cases still counted there.
    assert snap["per_field"]["name_zh"]["tested"] == 2
    assert snap["annotator_fields"]["name_zh"] == {
        "tier": 1, "tested": 1, "passed": 1, "failed": 0, "method": "fuzzy", "mean_score": 1.0,
    }
    assert snap["lookup_fields"]["name_zh"]["tested"] == 1
    assert snap["lookup_fields"]["name_zh"]["passed"] == 0
    # Annotator totals: location_name pass, name_zh pass, category fail.
    assert (snap["tier1_tested"], snap["tier1_passed"]) == (3, 2)
    assert (snap["lookup_tested"], snap["lookup_passed"]) == (1, 0)
    assert len(snap["entries"]) == 4
    assert {e["bucket"] for e in snap["entries"] if e["case_id"] == "m1" and e["field"] == "name_zh"} == {"lookup"}


def test_report_separates_lookup_from_annotator_summary(tmp_path: Path):
    cases, diffs = _sample_diffs()
    out = tmp_path / "report.md"
    write_report(cases, diffs, {"mode": "frozen", "stage": 1}, out, 1.0, [None, None])
    text = out.read_text()
    assert "## 片名查詢（不計入 annotator 分數）" in text
    assert "- Total Tier 1 accuracy (annotator): 66.7%" in text
    assert "- Title lookup accuracy (not in annotator score): 0.0%" in text
    # The movie title miss is not listed as an annotator failure.
    assert "霧的如同" not in text.split("## Failures")[1]


# ─── Validated output (#383) ─────────────────────────────────────────────────

def test_normalize_applies_production_validators():
    ann = normalize_annotation({"category": ["performance", "not_a_category"], "event_form": ["exhibition", "bogus"]})
    assert ann["category"] == ["performing_arts"]
    assert ann["event_form"] == ["exhibition"]


def test_run_golden_scores_validated_category(tmp_path: Path, monkeypatch):
    import json

    import eval_annotator

    case = {
        "case_id": "c1",
        "source_name": "peatix",
        "input": {"raw_title": "t", "raw_description": "d"},
        "expected": {"category": _exp(["performing_arts"]), "event_form": _exp(["performance"])},
    }
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(json.dumps(case) + "\n")

    async def fake_annotate(*_args, **_kwargs):
        # Raw LLM output: an alias production maps, and a value it drops.
        return {"category": ["performance"], "event_form": ["performance", "bogus"]}, None

    async def no_semantic(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(eval_annotator, "annotate_one_async", fake_annotate)
    monkeypatch.setattr(eval_annotator, "get_async_client", lambda _name: None)
    monkeypatch.setattr(eval_annotator, "semantic_scores_for", no_semantic)

    snap_path = tmp_path / "snap.json"
    asyncio.run(eval_annotator.run_golden(
        cases_path, tmp_path / "missing_frozen.json", tmp_path / "report.md", json_output=snap_path,
    ))
    snap = json.loads(snap_path.read_text())
    assert {e["field"]: e["match"] for e in snap["entries"]} == {"category": True, "event_form": True}
    assert snap["validator_changed"] == {"category": 1, "event_form": 1}
    assert "category 1 筆、event_form 1 筆" in (tmp_path / "report.md").read_text()
