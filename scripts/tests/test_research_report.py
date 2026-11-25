"""Tests for scripts/research/render_report.py: research-team state validation and report rendering."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "research" / "render_report.py"


@pytest.fixture(scope="session")
def rr():
    spec = importlib.util.spec_from_file_location("render_report", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def state():
    return copy.deepcopy(
        {
            "slug": "sample",
            "title": "範例議題",
            "question": "A 是否導致 B？",
            "round": 2,
            "issues": [
                {"id": "I0", "title": "A 與 B 的關係", "parent": None},
                {"id": "I1", "title": "機制", "parent": "I0"},
                {"id": "I2", "title": "反例", "parent": "I0"},
            ],
            "hypotheses": [
                {"id": "H1", "issue": "I1", "statement": "A 經由 X 導致 B", "status": "active", "claims": ["C1"]},
                {"id": "H2", "issue": "I1", "statement": "A 與 B 只是相關", "status": "refuted", "claims": ["C2"]},
                {"id": "H3", "issue": "I2", "statement": "A 經由 X 與 Y 導致 B", "status": "active", "parents": ["H1"], "claims": ["C1"]},
            ],
            "claims": [
                {"id": "C1", "text": "X 在實驗中升高", "sources": ["S1"], "verification": "verified", "quote": "X rose by 40%"},
                {"id": "C2", "text": "沒有劑量反應", "sources": ["S2"], "verification": "contradicted"},
            ],
            "sources": [
                {"id": "S1", "type": "paper", "title": "On X", "authors": ["Lin, A."], "year": 2021, "doi": "10.1000/x1", "primary": True, "fetched": True},
                {"id": "S2", "type": "web", "title": "Blog <b>post</b>", "url": "https://example.org/post", "fetched": True},
            ],
            "matches": [
                {"round": 1, "a": "H1", "b": "H2", "winner": "H1", "reason": "證據較直接"},
                {"round": 2, "a": "H3", "b": "H1", "winner": "H3", "reason": "涵蓋較多"},
            ],
            "meta_review": {"limitations": ["樣本偏小 [^S2]"]},
            "report": {
                "summary": "主要結論見 [^S2]，機制見 [^S1]，再次引用 [^S2]。",
                "sections": [{"issue": "I1", "heading": "機制", "body": "**X** 是關鍵 [^S1]。\n\n- 第一點\n- 第二點"}],
            },
        }
    )


def test_valid_state_has_no_errors(rr, state):
    errors, warnings = rr.validate(state)
    assert errors == []
    assert warnings == []


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda s: s["claims"][0].pop("quote"), "沒有原文引句"),
        (lambda s: s["sources"][0].update(fetched=False), "沒有實際開啟過"),
        (lambda s: s["sources"][1].pop("url"), "沒有 url 或 doi"),
        (lambda s: s["sources"][1].update(url="javascript:alert(1)"), "不是 http(s)"),
        (lambda s: s["claims"][1].update(sources=[]), "但沒有來源"),
        (lambda s: s["claims"][1].update(sources=["S9"]), "引用不存在的來源 S9"),
        (lambda s: s["hypotheses"][0].update(issue="I9"), "issue `I9` 不存在"),
        (lambda s: s["hypotheses"][0].update(claims=["C9"]), "引用不存在的主張 C9"),
        (lambda s: s["issues"][1].update(parent=None), "恰有一個根議題"),
        (lambda s: s["issues"][1].update(parent="I2") or s["issues"][2].update(parent="I1"), "成環"),
        (lambda s: s["matches"][0].update(winner="H3"), "winner 必須是"),
        (lambda s: s["report"].update(summary="見 [^S7]"), "引用不存在的來源 [^S7]"),
        (lambda s: s["hypotheses"].append(dict(s["hypotheses"][0])), "id 重複"),
        (lambda s: s["claims"][0].update(verification="sure"), "不在允許值內"),
    ],
)
def test_validation_errors(rr, state, mutate, expected):
    mutate(state)
    errors, _ = rr.validate(state)
    assert any(expected in e for e in errors), errors


def test_unused_source_and_unchecked_claim_are_warnings(rr, state):
    state["sources"].append({"id": "S3", "title": "Extra", "url": "https://example.org/extra"})
    state["claims"][1].update(verification="unchecked")
    errors, warnings = rr.validate(state)
    assert errors == []
    assert any("S3" in w for w in warnings)
    assert any("C2" in w for w in warnings)


def test_elo_and_ranking(rr, state):
    table = rr.elo_table(state)
    assert table["H1"]["win"] == 1 and table["H1"]["loss"] == 1
    assert table["H3"]["elo"] > table["H1"]["elo"] > table["H2"]["elo"]
    assert round(sum(v["elo"] for v in table.values())) == 3600
    ranked = [h["id"] for h in rr.ranking(state)]
    assert ranked == ["H3", "H1", "H2"]  # refuted sorts last whatever its Elo


def test_draw_keeps_equal_ratings(rr, state):
    state["matches"] = [{"a": "H1", "b": "H2", "winner": "draw"}]
    table = rr.elo_table(state)
    assert table["H1"]["elo"] == table["H2"]["elo"] == 1200
    assert table["H1"]["draw"] == 1


def test_footnotes_numbered_by_first_citation(rr, state):
    page = rr.render(state)
    # S2 is cited first, so it is footnote 1; the repeat reuses the number without a second anchor.
    assert page.count('id="fnref-1"') == 1
    assert page.count('href="#fn-1"') == 3  # twice in the summary, once in the meta-review
    assert page.index('id="fn-1"') < page.index('id="fn-2"')
    fn1 = page.split('id="fn-1"')[1].split("</li>")[0]
    assert "https://example.org/post" in fn1 and 'href="#src-S2"' in fn1 and 'href="#fnref-1"' in fn1
    fn2 = page.split('id="fn-2"')[1].split("</li>")[0]
    assert "https://doi.org/10.1000/x1" in fn2


def test_bibliography_lists_every_used_source_once(rr, state):
    page = rr.render(state)
    assert page.count('id="src-S1"') == 1 and page.count('id="src-S2"') == 1
    biblio = page.split('id="bibliography"')[1]
    assert "一手來源" in biblio and "二手來源" in biblio
    assert 'target="_blank" rel="noopener noreferrer"' in biblio


def test_render_escapes_untrusted_text(rr, state):
    state["hypotheses"][0]["statement"] = '<script>alert("x")</script>'
    page = rr.render(state)
    assert "<script>" not in page
    assert "Blog &lt;b&gt;post&lt;/b&gt;" in page
    assert "<strong>X</strong>" in page and "<li>第一點</li>" in page


def test_issue_map_has_nodes_links_and_lineage(rr, state):
    page = rr.render(state)
    svg = page.split('<svg class="map"')[1].split("</svg>")[0]
    for anchor in ("#issue-I0", "#issue-I1", "#issue-I2", "#hyp-H1", "#hyp-H2", "#hyp-H3"):
        assert f'href="{anchor}"' in svg
    assert svg.count('class="edge"') == 5  # 2 sub-issues + 3 hypotheses
    assert svg.count('class="edge lineage"') == 1
    assert "s-refuted" in svg
    for target in ("issue-I1", "issue-I2", "hyp-H1", "hyp-H2", "hyp-H3"):
        assert f'id="{target}"' in page


def test_wrap_counts_cjk_as_double_width(rr):
    assert rr.wrap("短標題") == ["短標題"]
    lines = rr.wrap("這是一個非常非常長的假說敘述需要被截斷成兩行並且在結尾加上省略號才不會超出節點的寬度")
    assert len(lines) == 2 and lines[1].endswith("…")
    assert all(sum(rr._units(c) for c in line) <= 30 for line in lines)


def test_page_follows_artifact_contract(rr, state):
    page = rr.render(state)
    assert page.startswith("<title>範例議題</title>")
    assert "<html" not in page and "<body" not in page
    assert ':root:not([data-theme="light"])' in page and ':root[data-theme="dark"]' in page


def test_cli_refuses_to_render_invalid_state(rr, state, tmp_path, capsys):
    state["claims"][0].pop("quote")
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "report.html"
    assert rr.main(["render", str(path), "-o", str(out)]) == 1
    assert not out.exists()
    assert "沒有原文引句" in capsys.readouterr().err


def test_cli_render_and_rank(rr, state, tmp_path, capsys):
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out" / "report.html"
    assert rr.main(["render", str(path), "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("<title>")
    capsys.readouterr()
    assert rr.main(["rank", str(path)]) == 0
    assert capsys.readouterr().out.splitlines()[0].startswith("1\tH3\t")


def test_merge_reflection_updates_claims_and_dedupes_sources(rr, state):
    result = {
        "hypothesis": "H2",
        "status": "refuted",
        "verdict": "核心主張被來源否定",
        "claims": [
            {"id": "C2", "verification": "contradicted", "quote": "a clear dose response", "sources": ["S2", "p1"]},
            {"tmp": "n1", "text": "反證：另一研究無法重現", "sources": ["p1"], "verification": "partial", "note": "只讀到摘要"},
        ],
        "sources": [
            {"id": "S2", "fetched": False},  # must not undo the earlier successful fetch
            {"tmp": "dup", "url": "http://www.example.org/post/", "fetched": True},  # same page as S2
            {"tmp": "p1", "type": "paper", "title": "Replication", "doi": "10.1000/r1", "primary": True, "fetched": True},
        ],
    }
    log = rr.merge(state, result)
    assert [s["id"] for s in state["sources"]] == ["S1", "S2", "S3"]
    assert state["sources"][1]["fetched"] is True
    claims = {c["id"]: c for c in state["claims"]}
    assert claims["C2"]["sources"] == ["S2", "S3"] and claims["C2"]["quote"] == "a clear dose response"
    assert claims["C3"]["sources"] == ["S3"] and state["hypotheses"][1]["claims"] == ["C2", "C3"]
    assert state["hypotheses"][1]["verdict"] == "核心主張被來源否定"
    assert any("S3" in line for line in log)
    assert rr.validate(state)[0] == []


def test_merge_generation_ranking_and_proximity(rr, state):
    result = {
        "hypotheses": [
            {"tmp": "h1", "statement": "新假說", "parents": ["H1", "H99"], "claims": [{"text": "新主張", "sources": ["s1", "ghost"]}, {"id": "C1"}]}
        ],
        "sources": [{"tmp": "s1", "title": "New", "url": "https://example.org/new"}],
    }
    log = rr.merge(state, result, issue="I2")
    hyp = state["hypotheses"][-1]
    assert hyp["id"] == "H4" and hyp["issue"] == "I2" and hyp["origin"] == "evolution" and hyp["parents"] == ["H1"]
    assert hyp["claims"] == ["C3", "C1"] and state["claims"][-1]["sources"] == ["S3"]
    assert state["sources"][-1]["fetched"] is False
    assert any("ghost" in line for line in log)
    rr.merge(state, {"matches": [{"a": "H4", "b": "H1", "winner": "H4", "reason": "r"}]})
    assert state["matches"][-1]["round"] == 2
    rr.merge(state, {"merge": [{"keep": "H1", "drop": ["H4"], "reason": "重複"}]})
    assert hyp["status"] == "merged"
    assert rr.validate(state)[0] == []
    with pytest.raises(SystemExit):
        rr.merge(state, {"hypotheses": []})


def test_cli_merge_writes_state(rr, state, tmp_path, capsys):
    path, res = tmp_path / "state.json", tmp_path / "res.json"
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    res.write_text(json.dumps({"matches": [{"a": "H1", "b": "H3", "winner": "draw", "reason": "x"}]}), encoding="utf-8")
    assert rr.main(["merge", str(path), str(res)]) == 0
    assert len(json.loads(path.read_text(encoding="utf-8"))["matches"]) == 3


def test_match_log_is_rendered(rr, state):
    page = rr.render(state)
    assert "對戰紀錄" in page and "H3 vs H1" in page and "證據較直接" in page
    state["matches"] = []
    assert "對戰紀錄" not in rr.render(state)
