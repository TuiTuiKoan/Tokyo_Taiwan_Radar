from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

NOW = datetime(2026, 11, 13, 13, 0, tzinfo=timezone.utc)  # Friday 22:00 JST


@pytest.fixture(scope="module")
def wd(root):
    sys.path.insert(0, str(root / "scripts" / "ci"))
    path = root / "scripts" / "ci" / "weekly_digest.py"
    spec = importlib.util.spec_from_file_location("weekly_digest", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ago(days):
    return (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")


def _pr(n, tier=None, days=1, body="", **kw):
    labels = [{"name": "scraper"}] + ([{"name": f"tier:{tier}"}] if tier is not None else [])
    return {"number": n, "title": f"fix(scraper): pr {n}", "labels": labels, "body": body,
            "created_at": _ago(days), "draft": False, "mergeable_state": "clean",
            "gitleaks": "success", "verdicts": [], **kw}


def test_sections_and_routing(wd):
    data = {
        "open_prs": [
            _pr(601, "1", verdicts=["✅ 0 → 有產出"]),
            _pr(602, "1", mergeable_state="dirty"),
            _pr(603, "2"),
            _pr(604, None, gitleaks="in_progress"),
            _pr(605, "2", days=20),
            _pr(606, "1", body="Closes #512"),
            _pr(607, "1", body="Fixes #512"),
            _pr(608, "1", body="Closes #459"),
        ],
        "issue_state": {"512": "open", "459": "closed"},
        "merged": [{"number": 590, "title": "docs: x", "labels": [{"name": "tier:0"}]}],
        "auto_closed": [{"number": 460, "title": "waseda_taiwan：0 產出"}],
        "needs_human": [{"number": 540, "title": "b", "created_at": _ago(3)},
                        {"number": 109, "title": "a", "created_at": _ago(170)}],
        "ready_to_close": [{"number": 367, "title": "母 issue"}],
    }
    title, body = wd.build(data, NOW)
    assert title == "週審 digest：2026-W46（11/13）"
    s1, s2, s3, s4 = (body.split(f"## {i}.")[1].split("\n## ")[0] for i in (1, 2, 3, 4))
    assert "#590" in s1 and "自動合併" in s1 and "#460 waseda_taiwan：0 產出" in s1
    assert "#601" in s2 and "dry-run：✅ 0 → 有產出" in s2 and "⚠️ 與 main 衝突" in s2
    assert "#603" not in s2 and "#603" in s3 and "#605" in s3
    assert "#604" in s3 and "gitleaks in_progress" in s3 and "還沒有 tier label" in s3
    assert "#367 母 issue" in s3
    assert s3.index("#109") < s3.index("#540")  # needs-human oldest first
    assert "#605" in s4 and "開了 20 天" in s4                       # stale
    assert "#512 有 2 張 PR" in s4 and "建議保留 #607，關閉 #606" in s4  # duplicate Closes
    assert "#608" in s4 and "要關閉的 issue 已經關了" in s4            # orphan
    assert "#602" in s4 and "rebase" in s4                           # conflict


def test_empty_week(wd):
    title, body = wd.build({}, NOW)
    assert "待審 PR 0 張" in body and body.count("（沒有）") >= 3
    assert "本週沒有合併的 PR" in body and "本週沒有自動關閉" in body


def test_verdicts_only_from_bot(wd):
    ev = ("<!-- pr-dryrun-evidence -->\n| 來源 | 修復前 | 修復後 | 判讀 |\n| --- | --- | --- | --- |\n"
          "| `otto` | 0 筆（exit 0） | 3 筆（exit 0） | ✅ 0 → 有產出 |\n")
    comments = [{"user": {"login": "github-actions[bot]"}, "body": ev},
                {"user": {"login": "someone"}, "body": ev.replace("✅ 0 → 有產出", "✅ 偽造")}]
    assert wd.verdicts(comments) == ["✅ 0 → 有產出"]
    assert wd.verdicts([comments[1]]) == []


def test_titles_cleaned_and_lists_capped(wd):
    prs = [_pr(700 + i, "2") for i in range(20)]
    prs[0]["title"] = "@x `y` | z [link](u)"
    _, body = wd.build({"open_prs": prs}, NOW)
    assert "@​x" in body and "`y`" not in body and "| z" not in body and "[link]" not in body
    assert "…其餘 5 張" in body


def test_closes_parsing(wd):
    assert wd.closes({"body": "Closes #1, fixes #2 and Resolved #3; refs #4"}) == [1, 2, 3]
    assert wd.closes({"body": None}) == []


def test_cli_offline(wd, tmp_path):
    data = tmp_path / "d.json"
    data.write_text(json.dumps({"open_prs": [_pr(1, "1")]}), encoding="utf-8")
    out, title = tmp_path / "b.md", tmp_path / "t.txt"
    assert wd.main(["--data", str(data), "--output", str(out), "--title-file", str(title)]) == 0
    assert title.read_text(encoding="utf-8").startswith("週審 digest：")
    assert "#1 fix(scraper): pr 1" in out.read_text(encoding="utf-8")
