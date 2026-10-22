"""Historical backtest (#355): sampling and classification."""

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from eval_historical import (
    classify_event,
    classify_field,
    stratified_sample,
    summarize,
    write_report,
)


def _rows(spec):
    return [{"id": f"{src}-{i:03d}", "source_name": src} for src, n in spec.items() for i in range(n)]


# ─── Sampling ─────────────────────────────────────────────────────────────────

def test_sample_is_proportional_and_exact():
    rows = _rows({"peatix": 500, "ndl_opensearch": 300, "ks_cinema": 150, "tiny": 50})
    sample = stratified_sample(rows, 100, seed=202610)
    assert len(sample) == 100
    assert Counter(r["source_name"] for r in sample) == {"peatix": 50, "ndl_opensearch": 30, "ks_cinema": 15, "tiny": 5}


def test_sample_uses_largest_remainder_and_is_reproducible():
    rows = _rows({"a": 2, "b": 2, "c": 2})
    first = stratified_sample(rows, 4, seed=1)
    assert len(first) == 4
    assert first == stratified_sample(rows, 4, seed=1)
    assert stratified_sample(rows, 10, seed=1) == stratified_sample(rows, 6, seed=1)  # capped at population


def test_different_months_sample_differently():
    rows = _rows({"a": 200})
    assert stratified_sample(rows, 10, seed=202610) != stratified_sample(rows, 10, seed=202611)


# ─── Classification ───────────────────────────────────────────────────────────

def _entry(field, stored, new, match):
    return {"field": field, "expected": stored, "got": new, "match": match}


def test_classify_field():
    assert classify_field(_entry("name_zh", "台灣講座", "台灣講座", True), locked=False) == "agree"
    assert classify_field(_entry("name_zh", "台灣講座", "別的", False), locked=True) == "protected"
    assert classify_field(_entry("name_zh", "台灣講座", None, False), locked=False) == "regression"
    assert classify_field(_entry("category", ["lecture"], ["senses"], False), locked=False) == "regression"
    assert classify_field(_entry("category", ["lecture"], ["art"], False), locked=False) == "silent_drift"


def test_classify_event_skips_movie_titles_and_empty_stored_fields():
    event = {"id": "e1", "source_name": "ks_cinema", "name_zh": "大濛", "name_en": None,
             "description_zh": None, "description_en": None, "category": ["movie"], "event_form": []}
    annotation = {"name_zh": "霧的如同", "name_en": "Like the Mist", "category": ["movie"]}
    results = classify_event(event, annotation, locked_fields=set(), semantic={})
    assert [(r["field"], r["class"]) for r in results] == [("category", "agree")]


def test_classify_event_uses_locks_and_semantic_scores():
    event = {"id": "e2", "source_name": "peatix", "name_zh": "台灣文化講座", "name_en": "Taiwan Talk",
             "description_zh": "講座介紹台灣文化。", "description_en": None,
             "category": ["lecture"], "event_form": ["lecture"]}
    annotation = {"name_zh": "台灣文化講座", "name_en": "A different title",
                  "description_zh": "完全不同", "category": ["senses"], "event_form": ["lecture"]}
    results = {r["field"]: r["class"] for r in classify_event(
        event, annotation, locked_fields={"name_en"}, semantic={"description_zh": 0.4})}
    assert results == {"name_zh": "agree", "name_en": "protected", "description_zh": "silent_drift",
                       "category": "regression", "event_form": "agree"}


def test_new_output_goes_through_production_validators_and_publication_form_is_skipped():
    event = {"id": "e3", "source_name": "ndl_opensearch", "name_zh": None, "name_en": None,
             "description_zh": None, "description_en": None,
             "category": ["performing_arts"], "event_form": ["publication"]}
    annotation = {"category": ["performance", "networking"], "event_form": ["lecture"]}
    results = classify_event(event, annotation, locked_fields=set(), semantic={})
    assert [(r["field"], r["class"]) for r in results] == [("category", "agree")]


def test_report_lists_review_queue_with_event_links(tmp_path: Path):
    results = [
        {"event_id": "abcdef12-0000", "source_name": "peatix", "field": "category", "class": "silent_drift",
         "stored": ["lecture"], "new": ["art"], "method": "set", "score": None},
        {"event_id": "ffff0000-1111", "source_name": "iwafu", "field": "name_zh", "class": "regression",
         "stored": "台灣祭", "new": None, "method": "fuzzy", "score": 0.0},
        {"event_id": "x", "source_name": "a", "field": "name_zh", "class": "agree",
         "stored": "a", "new": "a", "method": "fuzzy", "score": 1.0},
    ]
    assert summarize(results)["totals"] == {"silent_drift": 1, "regression": 1, "agree": 1}
    out = tmp_path / "h.md"
    write_report(out, now=datetime(2026, 10, 22, tzinfo=timezone.utc), n_events=3, n_eligible=10,
                 seed=202610, results=results, cost=0.01, skipped=[])
    text = out.read_text()
    assert "https://tokyotaiwanradar.com/ja/events/abcdef12-0000" in text
    assert "## GPT 倒退（1）" in text and "## 沉默漂移：人工檢查清單（1）" in text
