"""Unit tests for the P5 ndl relevance evaluation harness (no DB, no network)."""

import csv
import types
from pathlib import Path

import pytest

import _oneoff_eval_ndl_relevance as ev

SCRIPT = Path(ev.__file__)


# ── read-only guarantee ─────────────────────────────────────────────────────
@pytest.mark.parametrize("forbidden", [".insert(", ".update(", ".upsert(", ".delete(", ".rpc("])
def test_script_source_has_no_write_calls(forbidden):
    assert forbidden not in SCRIPT.read_text(encoding="utf-8")


# ── stratification ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "title, stratum",
    [
        ("朝鮮半島有事に備えよ", "S1"),
        ("日本企業の実行投資額：マレーシア", "S1"),
        ("アジア主要国における化学物質登録制度の比較研究：中国・韓国・台湾・フィリピン", "S2"),
        ("半導体関連で外資投資が急伸：マレーシア、韓国、台湾", "S2"),
        ("日本・台湾の交流", "S3"),  # only two countries -> not a list
        ("台湾の現代美術", "S3"),
        ("Taiwan cinema", "S3"),
        ("", "S1"),
    ],
)
def test_classify_stratum(title, stratum):
    assert ev.classify_stratum(title) == stratum


# ── P_dev / P_seal split ────────────────────────────────────────────────────
@pytest.mark.parametrize("n, expected", [(0, 0), (1, 1), (2, 1), (3, 2), (5, 3), (10, 6), (99, 59), (100, 60)])
def test_dev_count_rounding_and_edges(n, expected):
    assert ev.dev_count(n) == expected


def test_dev_count_keeps_both_sides_non_empty_for_n_ge_2():
    for n in range(2, 60):
        assert 1 <= ev.dev_count(n) <= n - 1


def _strata(n_s1=7, n_s2=3, n_s3=20):
    out = {}
    for i in range(n_s1):
        out[f"a{i}"] = "S1"
    for i in range(n_s2):
        out[f"b{i}"] = "S2"
    for i in range(n_s3):
        out[f"c{i}"] = "S3"
    return out


def test_split_is_reproducible_and_complete():
    first, stats = ev.split_dev_seal(_strata())
    second, _ = ev.split_dev_seal(dict(reversed(list(_strata().items()))))
    assert first == second
    assert set(first) == set(_strata())
    assert stats["S1"] == {"n": 7, "dev": 4, "seal": 3}
    assert stats["S2"] == {"n": 3, "dev": 2, "seal": 1}
    assert stats["S3"] == {"n": 20, "dev": 12, "seal": 8}
    for stratum, stat in stats.items():
        assert sum(1 for k, v in first.items() if _strata()[k] == stratum and v == "dev") == stat["dev"]


def test_split_depends_on_seed():
    a, _ = ev.split_dev_seal(_strata(), seed="p5-ndl-2026-10")
    b, _ = ev.split_dev_seal(_strata(), seed="another")
    assert a != b


def test_split_two_item_stratum_has_one_each():
    split, stats = ev.split_dev_seal({"x": "S2", "y": "S2"})
    assert sorted(split.values()) == ["dev", "seal"]
    assert stats["S2"] == {"n": 2, "dev": 1, "seal": 1}


# ── blind sheets ────────────────────────────────────────────────────────────
def _records():
    split, _ = ev.split_dev_seal(_strata(n_s3=100))
    strata = _strata(n_s3=100)
    return [
        {"id": i, "raw_title": f"title {i}", "raw_description": f"<p>desc <b>{i}</b></p>",
         "stratum": strata[i], "split": split[i]}
        for i in sorted(strata)
    ]


def test_dev_sheet_takes_all_s1_s2_plus_forty_others():
    records = _records()
    chosen = ev.select_dev_sheet(records)
    dev = [r for r in records if r["split"] == "dev"]
    assert all(r["split"] == "dev" for r in chosen)
    assert {r["id"] for r in dev if r["stratum"] in ("S1", "S2")} <= {r["id"] for r in chosen}
    assert sum(1 for r in chosen if r["stratum"] == "S3") == 40


def test_blind_rows_hide_model_fields_and_are_deterministic_but_shuffled():
    records = _records()
    rows = ev.blind_rows(records, "dev")
    assert rows == ev.blind_rows(list(reversed(records)), "dev")
    assert [r[0] for r in rows] != [r["id"] for r in records]
    assert len(ev.BLIND_HEADER) == 5
    assert all(r[-1] == "" for r in rows)
    flat = " ".join(" ".join(r) for r in rows).lower()
    for banned in ("relevant", "confidence", "gate", "selection_reason", "category", "stratum", "split"):
        assert banned not in flat
    assert rows[0][1].startswith("https://tokyotaiwanradar.com/ja/events/")
    assert "<" not in rows[0][3]


def test_plain_excerpt_strips_tags_and_truncates():
    assert ev.plain_excerpt("<p>a  <b>b</b></p>") == "a b"
    assert len(ev.plain_excerpt("x" * 900)) == 500
    assert ev.plain_excerpt(None) == ""


# ── Clopper-Pearson ─────────────────────────────────────────────────────────
def test_cp_lower_edges():
    assert ev.cp_lower(0, 10) == 0.0
    assert ev.cp_lower(10, 10) == pytest.approx(0.05 ** (1 / 10))
    assert ev.cp_lower(60, 60) == pytest.approx(0.05 ** (1 / 60))
    assert ev.cp_lower(0, 0) is None
    assert ev.cp_lower(5, 0) is None


def test_cp_lower_satisfies_its_defining_equation():
    for x, n in [(1, 10), (9, 10), (59, 60), (57, 60), (95, 100)]:
        bound = ev.cp_lower(x, n)
        assert ev._upper_tail(bound, x, n) == pytest.approx(0.05, abs=1e-9)


def test_cp_lower_matches_scipy_beta_quantile():
    stats = pytest.importorskip("scipy.stats")
    for x, n in [(1, 10), (9, 10), (59, 60), (57, 60), (95, 100), (3, 7)]:
        assert ev.cp_lower(x, n) == pytest.approx(stats.beta.ppf(0.05, x, n - x + 1), abs=1e-9)


# ── seal metrics ────────────────────────────────────────────────────────────
def _row(i, label, r1=False, g=False):
    return {"id": f"r{i}", "drops": {"R1": r1, "G": g}, "label": label}


def _k_rows(start, labels):
    return [_row(start + i, label) for i, label in enumerate(labels)]


def test_seal_metrics_all_relevant_k_sample_x_equals_n():
    rows = _k_rows(0, ["R"] * 60) + [_row(100, "N", g=True), _row(101, "N", g=True)]
    m = ev.seal_metrics(rows, "G", "label")
    assert m["status"] == "ok" and (m["x"], m["n"]) == (60, 60)
    assert m["recall_point"] == 1.0
    assert m["recall_lower"] == 1.0  # nothing lost -> recall is 1 for any p
    assert m["recall_verdict"] == "pass"
    assert m["lost_keep_ids"] == []
    assert m["n_removal_point"] == pytest.approx(2 / 2)  # A_N=2, K has no N
    assert m["n_removal_verdict"] == "pass"


def test_seal_metrics_lost_relevant_record_lowers_recall():
    rows = _k_rows(0, ["R"] * 60) + [_row(100, "R", g=True), _row(101, "N", g=True)]
    m = ev.seal_metrics(rows, "G", "label")
    assert m["lost_keep_ids"] == ["r100"]
    # kept = 0 + 60 * 1.0, lost = 1
    assert m["recall_point"] == pytest.approx(60 / 61)
    lb_kept = 60 * 0.05 ** (1 / 60)
    assert m["recall_lower"] == pytest.approx(lb_kept / (lb_kept + 1))
    assert m["recall_verdict"] == "pass"
    two_lost = rows + [_row(102, "R", g=True)]
    assert ev.seal_metrics(two_lost, "G", "label")["recall_verdict"] == "fail"  # 60/62 < 98%


def test_seal_metrics_small_k_sample_gives_insufficient_not_pass():
    # K has 100 records, only 10 sampled (5 R, 5 N); one relevant record lost by G.
    rows = [_row(i, "R" if i < 5 else "N" if i < 10 else None) for i in range(100)]
    rows.append(_row(500, "R", g=True))
    m = ev.seal_metrics(rows, "G", "label")
    assert m["recall_point"] >= 0.98 and m["recall_lower"] < 0.96
    assert m["recall_verdict"] == "insufficient"
    assert ev.seal_metrics(rows, "G", "label", extra_sampled=True)["recall_verdict"] == "fail"


def test_seal_metrics_x_zero_gives_zero_lower_bound_and_all_n_removal_possible():
    rows = _k_rows(0, ["N"] * 60) + [_row(100, "N", g=True)]
    m = ev.seal_metrics(rows, "G", "label")
    assert (m["x"], m["p_hat"], m["p_lb"]) == (0, 0.0, 0.0)
    assert m["recall_point"] is None  # kept 0 and lost 0 -> denominator 0
    assert m["recall_verdict"] == "not_applicable"
    assert m["n_removal_point"] == pytest.approx(1 / 61)
    assert m["n_removal_verdict"] == "fail"


def test_seal_metrics_n_zero_with_non_empty_k_is_insufficient_sample():
    rows = [_row(0, None), _row(1, None), _row(100, "N", g=True)]
    assert ev.seal_metrics(rows, "G", "label")["status"] == "insufficient_sample"


def test_seal_metrics_empty_k_zone_needs_no_sample():
    rows = [_row(0, "R", g=True), _row(1, "N", g=True), _row(2, "N", r1=True)]
    m = ev.seal_metrics(rows, "G", "label")
    assert m["status"] == "ok" and m["n_k"] == 0 and m["n"] == 0
    assert m["recall_point"] == 0.0  # kept 0, lost 1
    assert m["recall_verdict"] == "fail"


def test_seal_metrics_empty_a_zone():
    rows = _k_rows(0, ["R"] * 59 + ["N"])
    m = ev.seal_metrics(rows, "G", "label")
    assert m["status"] == "ok"
    assert m["recall_point"] == 1.0  # nothing dropped, so nothing lost
    assert m["n_removal_point"] == 0.0  # nothing dropped
    assert m["n_removal_verdict"] == "fail"


def test_seal_metrics_all_n_everywhere():
    rows = _k_rows(0, ["N"] * 20) + [_row(100, "N", g=True), _row(101, "N", r1=True)]
    m = ev.seal_metrics(rows, "G", "label")
    assert m["lost_keep_ids"] == [] and m["x"] == 0
    assert m["n_removal_point"] == pytest.approx(1 / (2 + 20 * 1.0))


def test_seal_metrics_requires_every_a_zone_row_to_be_labelled():
    rows = _k_rows(0, ["R"] * 10) + [_row(100, None, g=True)]
    m = ev.seal_metrics(rows, "G", "label")
    assert m["status"] == "incomplete" and m["unlabeled_a_zone"] == ["r100"]


def test_seal_metrics_boundary_label_counts_as_keep():
    rows = _k_rows(0, ["B"] * 60) + [_row(100, "B", g=True)]
    m = ev.seal_metrics(rows, "G", "label")
    assert m["x"] == 60 and m["lost_keep_ids"] == ["r100"]


def test_a_zone_row_kept_by_this_rule_counts_toward_kept_r():
    # dropped by R1 only; judging G it is a kept relevant record
    rows = _k_rows(0, ["R"] * 60) + [_row(100, "R", r1=True)]
    m = ev.seal_metrics(rows, "G", "label")
    assert m["lost_keep_ids"] == []
    assert m["recall_point"] == 1.0
    assert ev.seal_metrics(rows, "R1", "label")["lost_keep_ids"] == ["r100"]


def test_extra_sample_turns_insufficient_into_fail():
    assert ev.recall_verdict(0.99, 0.95, extra_sampled=False) == "insufficient"
    assert ev.recall_verdict(0.99, 0.95, extra_sampled=True) == "fail"
    assert ev.recall_verdict(0.99, 0.97, extra_sampled=False) == "pass"
    assert ev.recall_verdict(0.97, 0.99, extra_sampled=False) == "fail"
    assert ev.recall_verdict(None, None, extra_sampled=False) == "not_applicable"


def test_worst_verdict_is_conservative():
    assert ev.worst_verdict(["pass", "insufficient"]) == "insufficient"
    assert ev.worst_verdict(["pass", "fail", "insufficient"]) == "fail"
    assert ev.worst_verdict(["pass", "pass"]) == "pass"


# ── P_h / H ─────────────────────────────────────────────────────────────────
def _zone(labels_and_drops):
    return [
        {"id": f"z{i}", "drops": {"G": drop}, "label": label}
        for i, (label, drop) in enumerate(labels_and_drops)
    ]


def test_gate_zone_passes_with_at_most_one_lost_keep():
    rows = _zone([("N", True), ("R", True), (None, False), (None, False)])
    m = ev.gate_zone_metrics(rows, "label")
    assert m["verdict"] == "pass" and m["lost_keep_ids"] == ["z1"]


def test_gate_zone_fails_with_two_lost_keep():
    rows = _zone([("R", True), ("B", True), ("N", True)])
    assert ev.gate_zone_metrics(rows, "label")["verdict"] == "fail"


def test_gate_zone_incomplete_when_a_dropped_row_is_unlabeled():
    rows = _zone([("N", True), (None, True)])
    m = ev.gate_zone_metrics(rows, "label")
    assert m["verdict"] == "incomplete" and m["unlabeled_dropped"] == ["z1"]


def test_gate_zone_with_nothing_dropped_passes():
    assert ev.gate_zone_metrics(_zone([(None, False)] * 5), "label")["verdict"] == "pass"
    assert ev.gate_zone_metrics([], "label")["verdict"] == "pass"


# ── frozen SHA enforcement ──────────────────────────────────────────────────
def test_sealed_splits_need_matching_frozen_sha():
    text = "prompt body"
    sha = ev.sha256_text(text)
    for split in ("seal", "hanmoto", "holdout"):
        with pytest.raises(SystemExit):
            ev.check_frozen(split, text, None)
        with pytest.raises(SystemExit):
            ev.check_frozen(split, text, "0" * 64)
        ev.check_frozen(split, text, sha)
    ev.check_frozen("dev", text, None)  # development split is free


def test_cmd_run_refuses_before_touching_db_or_openai(tmp_path, monkeypatch):
    import annotator

    def boom(*_a, **_k):
        raise AssertionError("must not be reached")

    monkeypatch.setattr(annotator, "_get_supabase", boom)
    monkeypatch.setattr(annotator, "_get_openai", boom)
    prompt = tmp_path / "p.txt"
    prompt.write_text("candidate", encoding="utf-8")
    args = types.SimpleNamespace(
        prompt_file=str(prompt), split="seal", frozen_sha="deadbeef", snapshot=str(tmp_path / "s.json"),
        out=str(tmp_path / "o.jsonl"), cost_cap=6.0,
    )
    with pytest.raises(SystemExit):
        ev.cmd_run(args)


# ── cost cap ────────────────────────────────────────────────────────────────
def _usage(prompt_tokens, completion_tokens):
    return types.SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)


def test_usage_cost_uses_gpt_4o_mini_prices():
    assert ev.usage_cost(_usage(1_000_000, 0)) == pytest.approx(0.15)
    assert ev.usage_cost(_usage(0, 1_000_000)) == pytest.approx(0.60)
    assert ev.usage_cost(None) == 0.0


def test_run_records_stops_at_the_cost_cap_and_reports_completed_part():
    records = [{"id": f"e{i}", "split": "dev"} for i in range(10)]
    calls = []

    def annotate(record):
        calls.append(record["id"])
        return {"category": []}, _usage(1_000_000, 0)  # $0.15 per call

    results, cost, stopped = ev.run_records(records, annotate, lambda r, a: False, cost_cap=0.40, workers=1)
    assert stopped is True
    assert len(results) == 3 and cost == pytest.approx(0.45)
    assert len(calls) == 3  # no new call started after the cap was exceeded


def test_run_records_below_cap_completes_everything():
    records = [{"id": f"e{i}", "split": "dev"} for i in range(5)]
    results, cost, stopped = ev.run_records(
        records, lambda r: ({"category": []}, _usage(1000, 500)), lambda r, a: True, cost_cap=6.0, workers=3
    )
    assert not stopped and len(results) == 5 and all(r["gate_deactivates"] for r in results)


# ── real annotation / gate path ─────────────────────────────────────────────
def test_annotate_fn_calls_the_production_path_with_the_record_type(monkeypatch):
    import annotator

    seen = {}

    def fake(client, title, desc, fb, sr, record_type=None):
        seen.update(client=client, title=title, desc=desc, fb=fb, sr=sr, record_type=record_type)
        return {"category": []}, None

    monkeypatch.setattr(annotator, "_annotate_one", fake)
    annotate = ev.make_annotate_fn("CLIENT", "FB", "SR")
    annotate({"id": "x", "raw_title": "T", "raw_description": "D", "event_form": ["publication"]})
    assert seen == {"client": "CLIENT", "title": "T", "desc": "D", "fb": "FB", "sr": "SR", "record_type": "publication"}
    annotate({"id": "y", "raw_title": "T", "raw_description": "D", "event_form": ["publication", "lecture"]})
    assert seen["record_type"] is None


def test_gate_deactivates_calls_the_production_gate_and_restores_the_flag():
    import annotator

    record = {"id": "x", "source_name": "ndl_opensearch", "event_form": ["publication"]}
    irrelevant = {"taiwan_relevance": {"is_relevant": False, "confidence": 0.95}}
    relevant = {"taiwan_relevance": {"is_relevant": True, "confidence": 0.95}}
    assert annotator.PUBLICATION_RELEVANCE_GATE_ENABLED is False
    assert ev.gate_deactivates(record, irrelevant) is True
    assert ev.gate_deactivates(record, relevant) is False
    assert annotator.PUBLICATION_RELEVANCE_GATE_ENABLED is False  # production default untouched


# ── labels, rows, sheets, report ────────────────────────────────────────────
def _write_labels(path, rows, header=("event_id", "blind_label", "final_label", "reason")):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def test_load_labels_merges_files_and_keeps_blind_label(tmp_path):
    first, second = tmp_path / "a.csv", tmp_path / "b.csv"
    _write_labels(first, [("e1", "R", "", ""), ("e2", "N", "", "")])
    _write_labels(second, [("e2", "", "B", "series title only, but the article is about Taiwan")], )
    labels = ev.load_labels([first, second])
    assert labels["e2"] == {"blind": "N", "final": "B", "reason": "series title only, but the article is about Taiwan"}
    assert labels["e1"]["final"] == ""


def test_load_labels_accepts_the_sheet_label_column_and_rejects_bad_values(tmp_path):
    sheet = tmp_path / "sheet.csv"
    _write_labels(sheet, [("e1", "r")], header=("event_id", "label"))
    assert ev.load_labels([sheet])["e1"]["blind"] == "R"
    _write_labels(sheet, [("e1", "X")], header=("event_id", "label"))
    with pytest.raises(SystemExit):
        ev.load_labels([sheet])


def test_select_sheet_records_a_zone_excludes_already_labelled_and_k_prefix_is_stable():
    rows = [
        {"id": f"s{i}", "split": "seal", "drops": {"R1": False, "G": False}} for i in range(130)
    ] + [
        {"id": "a1", "split": "seal", "drops": {"R1": True, "G": False}},
        {"id": "a2", "split": "hanmoto", "drops": {"R1": False, "G": True}},
        {"id": "a3", "split": "seal", "drops": {"R1": True, "G": True}},
        {"id": "d1", "split": "dev", "drops": {"R1": True, "G": True}},
    ]
    a = ev.select_sheet_records("a", rows, {"a3"})
    assert {r["id"] for r in a} == {"a1", "a2"}
    k = ev.select_sheet_records("k", rows, set())
    extra = ev.select_sheet_records("extra", rows, set())
    assert len(k) == 60 and len(extra) == 40
    assert not {r["id"] for r in k} & {r["id"] for r in extra}
    assert not any(r["id"] in {"a1", "a3"} for r in k + extra)


def test_report_metrics_requires_model_output():
    rows = [{"id": "x", "split": "seal", "drops": {"R1": True}, "final": "N", "blind": "N"}]
    assert ev.report_metrics(rows, False)["status"] == "no_model_output"


def test_report_metrics_end_to_end_with_conservative_label_set():
    rows = []
    for i in range(60):
        rows.append({"id": f"k{i}", "split": "seal", "drops": {"R1": False, "G": False},
                     "final": "R", "blind": "R", "title": "t", "stratum": "S3", "reason": ""})
    rows.append({"id": "a1", "split": "seal", "drops": {"R1": True, "G": True},
                 "final": "N", "blind": "R", "title": "t", "stratum": "S1", "reason": "adjudicated"})
    rows.append({"id": "a2", "split": "seal", "drops": {"R1": True, "G": True},
                 "final": "N", "blind": "R", "title": "t", "stratum": "S1", "reason": "adjudicated"})
    rows.append({"id": "h1", "split": "hanmoto", "drops": {"R1": False, "G": False},
                 "final": None, "blind": None, "title": "t", "stratum": "S3", "reason": ""})
    report = ev.report_metrics(rows, extra_sampled=False)
    assert report["status"] == "ok"
    assert report["label_sets"]["final"]["seal"]["G"]["recall_verdict"] == "pass"
    assert report["label_sets"]["blind"]["seal"]["G"]["recall_verdict"] == "fail"  # two blind-R records lost
    assert report["conservative"]["G_recall"] == "fail"
    assert report["conservative"]["P_h"] == "pass"
    assert "H" not in report["conservative"]


def test_compact_csv_has_no_description_or_model_reasoning():
    rows = [{"id": "e1", "title": "T", "stratum": "S1", "split": "seal", "blind": "N", "final": "N",
             "reason": "ok", "drops": {"R1": True, "G": False}}]
    out = ev.compact_csv_rows(rows, {"ids_sha256": "abc"})
    assert out[0][0] == "e1" and out[0][-1] == "abc" and out[0][-2] == ev.SEED
    header = " ".join(ev.COMPACT_HEADER).lower()
    assert "description" not in header and "selection_reason" not in header


def test_parser_wires_the_four_subcommands():
    parser = ev.build_parser()
    ns = parser.parse_args(["run", "--prompt-file", "p", "--split", "dev", "--out", "o"])
    assert ns.func is ev.cmd_run and ns.cost_cap == 6.0
    for name in ("snapshot", "sheets --stage a", "metrics --outputs o --labels l"):
        assert parser.parse_args(name.split()).func


def test_no_regex_is_catastrophic_on_long_titles():
    assert ev.classify_stratum("台湾" + "・日本" * 5000) in ("S2", "S3")
