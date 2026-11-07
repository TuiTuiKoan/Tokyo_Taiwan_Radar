from __future__ import annotations

import importlib.util
import json

import pytest


@pytest.fixture(scope="module")
def ev(root):
    path = root / "scripts" / "ci" / "dryrun_evidence.py"
    spec = importlib.util.spec_from_file_location("dryrun_evidence", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stdout(*titles):
    return "INFO noise [not json\n" + json.dumps([{"name_ja": t} for t in titles], ensure_ascii=False)


def test_parse_events_finds_trailing_array(ev):
    assert len(ev.parse_events(_stdout("a", "b"))) == 2
    assert ev.parse_events("no json here") is None
    assert ev.parse_events('{"not": "a list"}') is None


def test_clean_neutralises_markdown_and_mentions(ev):
    s = ev.clean("@user <!-- x --> `rm` [link](http://e) | col\n## h")
    assert "@​user" in s
    for ch in "`<>[]|#":
        assert ch not in s
    assert "\n" not in s
    assert len(ev.clean("あ" * 200)) == ev.MAX_TITLE_LEN


def test_summarize_counts_and_titles(ev):
    s = ev.summarize(_stdout("台湾映画祭", ""), "line1\nline2", 0)
    assert s == {"rc": 0, "exception": None, "count": 2, "titles": ["台湾映画祭"],
                 "stderr_tail": ["line1", "line2"]}
    assert ev.summarize("", "Traceback", 1)["count"] is None


def test_summarize_detects_swallowed_scraper_exception(ev):
    # main.py logs the exception and still exits 0 with an empty array (critique F1).
    err = "ERROR OttoScraper: scraper failed: TimeoutError('page.goto') @evil\nINFO Total events scraped: 0"
    s = ev.summarize("[]", err, 0)
    assert s["rc"] == 0 and s["count"] == 0
    assert s["exception"].startswith("TimeoutError(") and "@\u200bevil" in s["exception"]
    assert ev.verdict({"rc": 0, "count": 0}, s) == "⚠️ 修復後 scraper 拋出例外"


@pytest.mark.parametrize("base,head,expect", [
    ({"rc": 0, "count": 0}, {"rc": 0, "count": 4}, "✅ 0 → 有產出"),
    ({"rc": 1, "count": None}, {"rc": 0, "count": 4}, "✅ 修復後有產出（修復前無法執行或拋出例外）"),
    ({"rc": 0, "count": 0, "exception": "x"}, {"rc": 0, "count": 4}, "✅ 修復後有產出（修復前無法執行或拋出例外）"),
    ({"rc": 0, "count": 3}, {"rc": 0, "count": 0}, "⚠️ 修復後仍是 0 筆"),
    ({"rc": 0, "count": 3}, {"rc": 0, "count": 40}, "⚠️ 筆數暴增超過 10 倍，請檢查過濾條件"),
    ({"rc": 0, "count": 5}, {"rc": 0, "count": 2}, "⚠️ 筆數減少"),
    ({"rc": 0, "count": 55}, {"rc": 0, "count": 55},
     "ℹ️ 修復前 dry-run 已有產出：無法以 dry-run 證明修好 production，合併後看下一次 Daily Scraper（#450）"),
    ({"rc": 0, "count": 5}, {"rc": 124, "count": None}, "⚠️ 修復後 dry-run 失敗"),
    ({"rc": 0, "count": 5}, None, "⚠️ 修復後 dry-run 失敗"),
])
def test_verdict(ev, base, head, expect):
    assert ev.verdict(base, head) == expect


def test_render_has_marker_table_and_cap(ev):
    results = {"otto": {"base": {"rc": 0, "count": 0, "titles": []},
                        "head": {"rc": 0, "count": 2, "titles": ["x"], "stderr_tail": ["e" * 10] * 3}}}
    body = ev.render(results, 541, "a" * 40, "b" * 40, skipped="base.py")
    assert body.startswith(ev.MARKER)
    assert "| `otto` | 0 筆（exit 0） | 2 筆（exit 0） | ✅ 0 → 有產出 |" in body
    assert "未檢查：base.py" in body
    big = {"otto": {"head": {"rc": 0, "count": 1, "titles": [], "stderr_tail": ["x" * 199] * 20000}}}
    assert len(ev.render(big, 1, "a", "b")) <= ev.MAX_COMMENT


def test_render_recleans_untrusted_summary(ev):
    # The summary JSON may come from a job that ran the PR's code.
    results = {"otto": {"head": {"rc": 0, "count": 1, "titles": ["@x <!-- y --> `z`"],
                                 "exception": "<b>@x</b>", "stderr_tail": ["</details> @y"]}}}
    body = ev.render(results, 1, "a", "b")
    assert "@x" not in body.replace("@\u200bx", "") and "<b>" not in body and "</details> @" not in body


def test_diagnose_section(ev, tmp_path):
    s = ev.summarize("[]", "E: scraper failed: HTTPError 403", 0)
    sec = ev.diagnose_section("prtimes", s)
    assert sec.startswith("\n### prtimes\n- exit code: 0\n- 筆數: 0\n- 例外：HTTPError 403")
    f = tmp_path / "s.json"; f.write_text(__import__("json").dumps(s))
    out = tmp_path / "r.md"
    assert ev.main(["diagnose-section", "--source", "prtimes", "--summary", str(f), "--output", str(out)]) == 0
    assert ev.main(["diagnose-section", "--source", "Bad;rm", "--summary", str(f), "--output", str(out)]) == 2
    assert out.read_text().count("### prtimes") == 1


def test_render_without_sources(ev):
    assert "沒有改到已註冊的來源" in ev.render({}, 1, "a", "b")


def test_cli_roundtrip(ev, tmp_path):
    (tmp_path / "o").write_text(_stdout("t"), encoding="utf-8")
    (tmp_path / "e").write_text("", encoding="utf-8")
    res = tmp_path / "res"
    res.mkdir()
    assert ev.main(["summarize", "--out", str(tmp_path / "o"), "--err", str(tmp_path / "e"),
                    "--rc", "0", "--json-output", str(res / "otto.head.json")]) == 0
    (res / "../evil.head.json").resolve().write_text("{}")  # outside dir, ignored
    (res / "Bad-Name.head.json").write_text("{}")           # invalid source, ignored
    out = tmp_path / "body.md"
    assert ev.main(["render", "--results-dir", str(res), "--pr", "7", "--base", "a", "--head", "b",
                    "--output", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "`otto`" in text and "Bad-Name" not in text and "evil" not in text
