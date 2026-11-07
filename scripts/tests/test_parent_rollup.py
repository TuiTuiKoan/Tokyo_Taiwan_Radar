from __future__ import annotations

import importlib.util
import json
import sys

import pytest

# The real #381 source list (2026-11-07): 30 keys, only 16 children say "母 issue：#381".
BODY_381 = """## 背景
#354 的第一份品質週報（PR #379，2026-10-22）中，有 30 個來源 28 天以上產出為 0。

acros_fukuoka、ciema、cine_gallery、cineplaza、cineswitch_ginza、faam_fukuoka、hankyu_hakata、hankyu_kobe、hankyu_umeda、hanshin_amagasaki、hanshin_mikage、hanshin_nishinomiya、hanshin_umeda、human_trust_cinema、internet_museum、livepocket、maruhiro、midland_cinema、nagano_aioiza、nhk_rss、otto、stranger、taiwanshi、theater_kino、tokyo_filmex、tuat_global、united_cinemas、us_cinema_chiba_gekijo、walkerplus、whitestone_gallery

## 做法（同 #327）
1. 本機 `python main.py --dry-run --source <key>`。
"""
KEYS_381 = [k for k in BODY_381.split("\n\n")[1].split("、")]


@pytest.fixture(scope="module")
def pr(root):
    sys.path.insert(0, str(root / "scripts" / "ci"))
    path = root / "scripts" / "ci" / "parent_rollup.py"
    spec = importlib.util.spec_from_file_location("parent_rollup", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def known(pr, root):
    return pr.scraper_keys((root / "scraper" / "main.py").read_text(encoding="utf-8"))


def _i(n, state="open", body="", labels=("scraper",), reason=None, title=None, closed_at=None, **kw):
    return {"number": n, "title": title or f"issue {n}", "state": state, "state_reason": reason,
            "closed_at": closed_at or ("2026-11-08T02:00:00Z" if state == "closed" else None),
            "body": body, "labels": [{"name": x} for x in labels], "pull_request": None, **kw}


def test_scraper_keys_from_real_main_py(known):
    assert len(KEYS_381) == 30
    assert {"prtimes", "waseda_taiwan", "taiwan_cultural_center", "peatix", "hanshin_umeda"} <= known
    assert set(KEYS_381) <= known  # every source #381 lists is still registered
    assert len(known) > 100


def test_381_children_all_closed_is_not_enough(pr, known):
    # Children closed, but most listed sources have no conclusion: list them, no label (G16).
    issues = [_i(381, body=BODY_381, labels=("needs-human", "scraper")),
              _i(512, "closed", "母 issue：#381", reason="completed", title="whitestone_gallery：0 產出")]
    got = pr.decide(issues, known, {})
    assert [(a["parent"], a["action"]) for a in got] == [(381, "unresolved")]
    assert "`acros_fukuoka`" in got[0]["comment"] and "`whitestone_gallery`" not in got[0]["comment"]


def test_ready_when_every_source_concluded(pr, known):
    issues = [_i(381, body=BODY_381)]
    for n, k in enumerate(KEYS_381, start=600):
        if k == "kbc_cinema":
            continue
        issues.append(_i(n, "closed", "母 issue：#381" if n % 2 else "", title=f"{k}：0 產出", reason="completed"))
    exp = {"otto": {"pattern": "sporadic"}}  # an expectation alone also concludes a source
    issues = [x for x in issues if x["title"] != "otto：0 產出"]
    got = pr.decide(issues, known, exp)
    assert [(a["parent"], a["action"]) for a in got] == [(381, "ready")]
    assert got[0]["marker"].startswith("<!-- parent-rollup:ready:")
    assert "ready-to-close" in got[0]["comment"] and "| #601 ciema：0 產出 | 完成 |" in got[0]["comment"]


def test_open_child_blocks_and_open_key_issue_does_not_conclude(pr, known):
    body = "列出：prtimes、ciema"
    assert pr.decide([_i(367, body=body), _i(459, "open", "母 issue：#367", title="prtimes：0")],
                     known, {}) == []
    got = pr.decide([_i(367, body=body), _i(459, "closed", "母 issue：#367", title="prtimes：0"),
                     _i(461, "open", title="ciema：0 產出")], known, {})
    assert got[0]["action"] == "unresolved" and "`ciema`" in got[0]["comment"]


def test_withdraw_when_child_reopens(pr, known):
    issues = [_i(367, body="prtimes", labels=("scraper", "ready-to-close")),
              _i(459, "open", "母 issue：#367", title="prtimes：再度 0 產出")]
    got = pr.decide(issues, known, {})
    assert [(a["parent"], a["action"]) for a in got] == [(367, "withdraw")]
    assert "#459" in got[0]["comment"]
    # Labelled and still complete: nothing to do.
    done = [_i(367, body="prtimes", labels=("scraper", "ready-to-close")),
            _i(459, "closed", "母 issue：#367", title="prtimes：0")]
    assert pr.decide(done, known, {}) == []


def test_ready_marker_changes_when_children_reclose(pr, known):
    a = pr.decide([_i(367, body="prtimes"), _i(459, "closed", "母 issue：#367", title="prtimes：0",
                                               closed_at="2026-11-08T00:00:00Z")], known, {})
    b = pr.decide([_i(367, body="prtimes"), _i(459, "closed", "母 issue：#367", title="prtimes：0",
                                               closed_at="2026-12-01T00:00:00Z")], known, {})
    assert a[0]["marker"] != b[0]["marker"]


def test_unlabelled_or_pr_children_do_not_count(pr, known):
    issues = [_i(381, body="otto"), _i(504, "closed", "母 issue：#381", title="otto：0"),
              _i(600, "open", "母 issue：#381", labels=()),
              _i(601, "open", "母 issue：#381", pull_request={"url": "x"})]
    assert [a["action"] for a in pr.decide(issues, known, {})] == ["ready"]
    # An outsider's closed, unlabelled "otto：" issue does not conclude a source either.
    issues = [_i(381, body="otto ciema"), _i(504, "closed", "母 issue：#381", title="otto：0"),
              _i(700, "closed", labels=(), title="ciema：done")]
    assert pr.decide(issues, known, {})[0]["action"] == "unresolved"


def test_titles_cleaned(pr, known):
    issues = [_i(381, body="otto"), _i(504, "closed", "母 issue：#381", title="otto：@x `y` | z")]
    body = pr.decide(issues, known, {})[0]["comment"]
    assert "@​x" in body and "`y`" not in body and "| z" not in body


def test_cli(pr, root, tmp_path):
    f = tmp_path / "i.json"
    f.write_text(json.dumps([_i(367, body="prtimes"), _i(459, "closed", "母 issue：#367", title="prtimes：0")]),
                 encoding="utf-8")
    out = tmp_path / "a.json"
    assert pr.main(["--issues", str(f), "--main", str(root / "scraper" / "main.py"),
                    "--expectations", str(root / "scraper" / "source_expectations.json"),
                    "--output", str(out)]) == 0
    assert json.loads(out.read_text())[0]["action"] == "ready"
