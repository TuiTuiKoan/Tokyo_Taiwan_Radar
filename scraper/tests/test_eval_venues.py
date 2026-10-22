"""Venue pipeline eval (#325): scoring, snapshot registry, golden-file integrity."""

import hashlib
import json
from pathlib import Path

import pytest

import venue_registry
from eval_venues import (
    CASES_PATH,
    MANIFEST_PATH,
    SNAPSHOT_PATH,
    check_baseline,
    load_cases,
    raw_md5,
    registry_from,
    run_resolve,
    score_extract,
    score_resolve,
    summarize_extract,
    summarize_resolve,
    write_report,
)

ROWS = [
    {"id": "v1", "canonical_name_ja": "誠品生活日本橋", "aliases": ["誠品生活"]},
    {"id": "v2", "canonical_name_ja": "八丁座", "aliases": ["サロンシネマ"]},
    {"id": "v3", "canonical_name_ja": "サロンシネマ", "aliases": []},
]


# ─── Resolve scoring ──────────────────────────────────────────────────────────

def _case(label, expected, **kw):
    return {"case_id": "r1", "kind": kw.pop("kind", "canonical"), "label": label,
            "expected_venue_id": expected, "expected_venue": expected, **kw}


@pytest.mark.parametrize("expected,got,outcome", [
    ("v1", "v1", "correct"),
    ("v1", None, "missed"),
    ("v1", "v2", "wrong_venue"),
    (None, "v1", "false_positive"),
    (None, None, "correct"),
])
def test_resolve_outcomes(expected, got, outcome):
    venue = {"id": got, "canonical_name_ja": got} if got else None
    assert score_resolve(_case("x", expected), venue, False)["outcome"] == outcome


def test_preserve_label_checked_only_when_venue_is_correct():
    r = score_resolve(_case("誠品生活日本橋 expo", "v1", expected_preserve_label=True), {"id": "v1"}, False)
    assert r["outcome"] == "correct" and r["label_ok"] is False
    r = score_resolve(_case("x", "v1", expected_preserve_label=True), None, False)
    assert r["label_ok"] is None


def test_snapshot_registry_reproduces_ambiguous_key_rejection():
    cases = [
        _case("誠品生活日本橋 expo", "v1", kind="sub_space", expected_preserve_label=True),
        _case("誠品生活", "v1", kind="alias"),
        _case("サロンシネマ", "v3"),  # canonical of v3, alias of v2 → rejected
        _case("オンライン", None, kind="negative"),
    ]
    results = run_resolve(cases, ROWS)
    assert [r["outcome"] for r in results] == ["correct", "correct", "missed", "correct"]
    assert results[0]["label_ok"] is True
    s = summarize_resolve(results)
    assert (s["correct"], s["missed"], s["wrong_venue"], s["false_positive"]) == (3, 1, 0, 0)
    assert s["recall"] == round(2 / 3, 4)


def test_registry_is_restored_after_snapshot_run():
    original = venue_registry._get_client
    with registry_from(ROWS):
        assert venue_registry._get_client is not original
    assert venue_registry._get_client is original
    assert venue_registry._CANONICAL is None


# ─── Extract scoring ──────────────────────────────────────────────────────────

def _xcase(expected, accepted=()):
    return {"case_id": "x1", "source_name": "s", "event_id": "e",
            "expected_location_name": expected, "accepted": list(accepted)}


def test_extract_accepts_alternatives_and_normalizes():
    case = _xcase("築地本願寺本堂", ["築地本願寺"])
    assert score_extract(case, "築地本願寺")["outcome"] == "correct"
    assert score_extract(case, "  築地本願寺本堂 ")["outcome"] == "correct"
    assert score_extract(case, "")["outcome"] == "missed"
    assert score_extract(case, "東京駅")["outcome"] == "wrong"


def test_extract_null_expected_flags_hallucination():
    assert score_extract(_xcase(None), None)["outcome"] == "correct"
    assert score_extract(_xcase(None), "   ")["outcome"] == "correct"
    assert score_extract(_xcase(None), "台湾文化センター")["outcome"] == "hallucinated"


def test_extract_summary_separates_named_null_and_drifted():
    results = [
        {"expected": "A", "outcome": "correct"},
        {"expected": "B", "outcome": "missed"},
        {"expected": None, "outcome": "hallucinated"},
        {"expected": "C", "outcome": "drifted"},
    ]
    s = summarize_extract(results, [{"case_id": "x9"}])
    assert (s["tested"], s["correct"], s["named_tested"], s["missed"]) == (3, 1, 2, 1)
    assert (s["null_tested"], s["hallucinated"], s["drifted"]) == (1, 1, ["x9"])


def test_raw_md5_matches_the_sql_recipe():
    # SQL: md5(coalesce(raw_title,'') || E'\n' || coalesce(raw_description,''))
    assert raw_md5("題", None) == hashlib.md5("題\n".encode()).hexdigest()


# ─── Baseline gate and report ─────────────────────────────────────────────────

def test_baseline_gate():
    manifest = {"resolve": {"min_correct": 52, "max_wrong": 0}}
    ok = {"correct": 52, "wrong_venue": 0, "false_positive": 0}
    assert check_baseline(ok, manifest) == []
    assert check_baseline({**ok, "correct": 51}, manifest)
    assert check_baseline({**ok, "false_positive": 1}, manifest)


def test_report_renders_both_stages(tmp_path: Path):
    resolve = run_resolve([_case("サロンシネマ", "v3")], ROWS)
    extract = [score_extract(_xcase(None), "どこか")]
    out = tmp_path / "r.md"
    write_report(out, registry_label="test", resolve=(resolve, summarize_resolve(resolve)),
                 extract=(extract, summarize_extract(extract, [])), cost=0.01, runtime_s=1.0)
    text = out.read_text()
    assert "サロンシネマ" in text and "hallucinated" in text and "定位" in text


# ─── Golden files ─────────────────────────────────────────────────────────────

def test_golden_cases_are_well_formed():
    cases = load_cases()
    ids = [c["case_id"] for c in cases]
    assert len(ids) == len(set(ids))
    venue_ids = {v["id"] for v in json.loads(SNAPSHOT_PATH.read_text())["venues"]}
    for c in cases:
        if c["stage"] == "resolve":
            assert c["expected_venue_id"] is None or c["expected_venue_id"] in venue_ids, c["case_id"]
            assert (c["expected_venue_id"] is None) == (c["kind"] == "negative"), c["case_id"]
        else:
            assert c["stage"] == "extract"
            assert len(c["raw_md5"]) == 32 and c["event_id"]


def test_snapshot_md5_matches_its_rows():
    snap = json.loads(SNAPSHOT_PATH.read_text())
    lines = "\n".join(
        f"{r['id']}|{r['canonical_name_ja']}|{'~'.join(r['aliases'])}|{r['prefecture'] or ''}|"
        f"{str(r['is_multi_venue']).lower()}"
        for r in sorted(snap["venues"], key=lambda r: r["id"])
    )
    assert hashlib.md5(lines.encode()).hexdigest() == snap["md5"]


def test_committed_snapshot_meets_the_manifest_baseline():
    results = run_resolve(load_cases(stage="resolve"), json.loads(SNAPSHOT_PATH.read_text())["venues"])
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert len(results) == manifest["resolve"]["cases"]
    assert check_baseline(summarize_resolve(results), manifest) == []
