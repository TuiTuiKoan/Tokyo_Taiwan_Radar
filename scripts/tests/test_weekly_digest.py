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


# ─── 學習區（spec auto-learning） ──────────────────────────────────────────────

def _merged(n, title="feat(x): y", body=None, days=3, files=(), bot=False):
    return {"number": n, "title": title, "labels": [{"name": "tier:2"}], "body": body,
            "merged_at": _ago(days), "author_bot": bot, "files": list(files)}


def test_lessons_parsing(wd):
    assert wd.lessons(None) is None
    assert wd.lessons("## 改了什麼\n- x") is None
    assert wd.lessons("## 教訓\n無\n") == []
    assert wd.lessons("## 教訓\n- 無\n## 其他\n- 不算") == []
    body = "## 改了什麼\nx\n\n## 教訓\r\n- 先列 open issue 再規劃（實測）\n* 第二條（推論）\n\n## Refs\n- 不算"
    assert wd.lessons(body) == ["先列 open issue 再規劃（實測）", "第二條（推論）"]
    assert wd.lessons("### 教訓\n- a\n- b\n- c\n- d") == ["a", "b", "c"]
    assert wd.lessons("## 教訓的補充\n- 不是教訓段") is None


def test_lesson_text_is_cleaned(wd):
    found = wd.lessons("## 教訓\n- @x 請執行 `rm` | [link](u) " + "長" * 400)
    assert len(found) == 1 and "@x" not in found[0] and "`" not in found[0] and "|" not in found[0]
    assert "[link]" not in found[0] and len(found[0]) <= 170


def test_followup_fixes(wd):
    merged = [_merged(1, "feat(ci): a", days=5, files=["a.yml", "b.py"]),
              _merged(2, "fix(ci): b", days=3, files=["b.py"]),
              _merged(3, "fix(web): c", days=2, files=["z.ts"]),
              _merged(4, "docs: d", days=1, files=["a.yml"])]
    assert wd.followup_fixes(merged) == [(1, 2, "b.py")]
    assert wd.followup_fixes([merged[1], merged[0]]) == [(1, 2, "b.py")]  # order comes from merged_at
    assert wd.followup_fixes([{"number": 9, "title": "fix: x"}]) == []      # old data without merged_at


def test_learning_section(wd):
    data = {
        "merged": [_merged(10, body="## 教訓\n- 規劃前先讀 origin/main（實測）", files=["a.py"]),
                   _merged(11, body="## 教訓\n無"),
                   _merged(12, body="沒有這一段"),
                   _merged(13, "fix(x): again", body=None, days=1, files=["a.py"]),
                   _merged(14, "chore(deps): bump", body=None, bot=True)],
        "closed_unmerged": [{"number": 20, "title": "x"}],
        "learning": [{"number": 30, "title": "learner 週報 2026-W46"}],
    }
    _, body = wd.build(data, NOW)
    s5 = body.split("## 5.", 1)[1]
    assert "learner 的提案**（1 張" in s5 and "#30" in s5
    assert "本週合併 4 張（不含 bot 的 PR），2 張沒有「教訓」段，1 張寫了教訓" in s5
    assert "沒有教訓段：#12、#13" in s5 and "#14" not in s5
    assert "- #10：規劃前先讀 origin/main（實測）" in s5
    assert "關閉未合併的 PR**：1 張（#20）" in s5
    assert "合併後又修同一檔**：1 組" in s5 and "#10 之後 #13" in s5


def test_learning_section_empty_and_old_data(wd):
    _, body = wd.build({"merged": [{"number": 1, "title": "t", "labels": []}]}, NOW)
    s5 = body.split("## 5.", 1)[1]
    assert "本週沒有 open 的 learning 提案" in s5
    assert "本週合併 1 張（不含 bot 的 PR），1 張沒有「教訓」段，0 張寫了教訓" in s5
    assert "關閉未合併的 PR**：0 張" in s5 and "合併後又修同一檔**：0 組" in s5
