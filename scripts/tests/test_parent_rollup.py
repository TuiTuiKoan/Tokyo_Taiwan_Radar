from __future__ import annotations

import importlib.util
import json
import sys

import pytest


@pytest.fixture(scope="module")
def pr(root):
    sys.path.insert(0, str(root / "scripts" / "ci"))
    path = root / "scripts" / "ci" / "parent_rollup.py"
    spec = importlib.util.spec_from_file_location("parent_rollup", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _i(n, state="open", body="", labels=("scraper",), reason=None, title=None, **kw):
    return {"number": n, "title": title or f"issue {n}", "state": state, "state_reason": reason,
            "body": body, "labels": [{"name": x} for x in labels], "pull_request": None, **kw}


def test_all_children_closed_marks_parent(pr):
    issues = [_i(381, labels=("needs-human", "scraper")),
              _i(510, "closed", "母 issue：#381（週報盤點）", reason="completed", title="united_cinemas：0 產出"),
              _i(511, "closed", "母 issue: #381", reason="not_planned")]
    got = pr.decide(issues)
    assert [(a["parent"], a["children"]) for a in got] == [(381, [510, 511])]
    body = got[0]["comment"]
    assert body.startswith(pr.MARKER) and "ready-to-close" in body
    assert "| #510 united_cinemas：0 產出 | 完成 |" in body and "| #511 issue 511 | 不處理 |" in body


def test_open_child_blocks(pr):
    issues = [_i(381), _i(510, "closed", "母 issue：#381"), _i(511, "open", "母 issue：#381")]
    assert pr.decide(issues) == []


def test_unlabelled_or_pr_children_do_not_count(pr):
    # An outsider can mention the parent but cannot label: neither blocks nor triggers.
    issues = [_i(381), _i(510, "closed", "母 issue：#381"),
              _i(600, "open", "母 issue：#381", labels=()),
              _i(601, "open", "母 issue：#381", pull_request={"url": "x"})]
    assert [a["parent"] for a in pr.decide(issues)] == [381]
    assert pr.decide([_i(381), _i(600, "closed", "母 issue：#381", labels=())]) == []


def test_parent_closed_already_labelled_or_missing(pr):
    child = _i(510, "closed", "母 issue：#381")
    assert pr.decide([_i(381, "closed"), child]) == []
    assert pr.decide([_i(381, labels=("ready-to-close",)), child]) == []
    assert pr.decide([child]) == []  # parent not in the list


def test_self_reference_and_titles_cleaned(pr):
    issues = [_i(381, body="母 issue：#381"), _i(510, "closed", "母 issue：#381", title="@x `y` | z")]
    body = pr.decide(issues)[0]["comment"]
    assert "@​x" in body and "`y`" not in body and "| z" not in body


def test_cli(pr, tmp_path):
    f = tmp_path / "i.json"
    f.write_text(json.dumps([_i(367), _i(461, "closed", "母 issue：#367")]), encoding="utf-8")
    out = tmp_path / "a.json"
    assert pr.main(["--issues", str(f), "--output", str(out)]) == 0
    assert json.loads(out.read_text())[0]["parent"] == 367
