"""Issue #569: PR Tier flags lane2-approved.yml changes that are mixed with other
files or do not match the schema (plan critique G3, G21)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys

import pytest

LANE2 = "docs/specs/active/agent-autonomy/lane2-approved.yml"


@pytest.fixture(scope="module")
def lane2(root):
    path = root / "scripts" / "ci" / "lane2_approval.py"
    spec = importlib.util.spec_from_file_location("lane2_approval", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tier(root):
    path = root / "scripts" / "ci" / "pr_tier.py"
    spec = importlib.util.spec_from_file_location("pr_tier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _files(*names, previous=None):
    entries = [{"filename": n, "status": "modified"} for n in names]
    if previous:
        entries[0]["previous_filename"] = previous
    return [entries]


# ── tier regression (G21) ────────────────────────────────────────────────


def test_approval_file_is_always_tier2(tier):
    assert tier.classify([LANE2]) == 2
    assert tier.classify_api_files(_files(LANE2), expected=1) == 2


# ── touch status ─────────────────────────────────────────────────────────


def test_status_none(lane2):
    assert lane2.touch_status(_files("docs/a.md"), 1) == "none"


def test_status_only(lane2):
    assert lane2.touch_status(_files(LANE2), 1) == "only"


def test_status_mixed_with_other_files(lane2):
    assert lane2.touch_status(_files(LANE2, "scraper/sources/iwafu.py"), 2) == "mixed"


def test_status_rename_into_approval_path_is_mixed(lane2):
    assert lane2.touch_status(_files(LANE2, previous="docs/x.yml"), 1) == "mixed"


def test_status_truncated_list_is_never_only(lane2):
    assert lane2.touch_status(_files(LANE2), 2) == "mixed"


# ── schema ───────────────────────────────────────────────────────────────

VALID = """\
version: 1
paused: false
resume_after: 2026-11-08
entries:
  - issue: 540
    type: implement
    scope: external_stats_pull 的 upsert 指定 on_conflict
    files: [scraper/external_stats/pull.py, scraper/tests/test_external_stats.py]
    suggested: "衝突鍵用 (source, period)"
    answer: "同意"
    judgement: false
    risk: low
    week: 2026-W46
"""


def test_valid_file_passes(lane2):
    assert lane2.validate_text(VALID) == []


def test_current_main_file_passes(lane2, root):
    assert lane2.validate_text((root / LANE2).read_text(encoding="utf-8")) == []


def test_empty_answer_is_allowed(lane2):
    assert lane2.validate_text(VALID.replace('answer: "同意"', "answer:")) == []


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda s: s + "  : [", "YAML parse error"),
        (lambda s: s.replace("version: 1", "version: 2"), "version must be 1"),
        (lambda s: s.replace("paused: false", "paused: maybe"), "paused"),
        (lambda s: s.replace("resume_after: 2026-11-08", "resume_after: soon"), "resume_after"),
        (lambda s: s.replace("    type: implement\n", "    type: implement\n    sneaky: 1\n"), "unknown keys"),
        (lambda s: s.replace("    risk: low\n", ""), "missing keys"),
        (lambda s: s.replace("issue: 540", "issue: -1"), "positive integer"),
        (lambda s: s.replace("type: implement", "type: merge"), "type must be"),
        (lambda s: s.replace("risk: low", "risk: none"), "risk must be"),
        (lambda s: s.replace("week: 2026-W46", "week: next"), "week must"),
        (lambda s: s.replace("judgement: false", "judgement: maybe"), "judgement"),
        (lambda s: s.replace("scraper/tests/test_external_stats.py", ".github/workflows/scraper.yml"), "forbidden"),
        (lambda s: s.replace("scraper/tests/test_external_stats.py", LANE2), "forbidden"),
        (lambda s: s.replace("scraper/tests/test_external_stats.py", "scraper/.env"), "forbidden"),
        (lambda s: s.replace("scraper/tests/test_external_stats.py", "AGENTS.md"), "forbidden"),
        (lambda s: s.replace("files: [scraper/external_stats/pull.py, scraper/tests/test_external_stats.py]", "files: []"), "files must"),
        (lambda s: s + "extra: 1\n", "unknown top-level"),
    ],
)
def test_invalid_files_are_rejected(lane2, mutate, needle):
    errors = lane2.validate_text(mutate(VALID))
    assert errors and any(needle in e for e in errors), errors


def test_duplicate_issue_is_rejected(lane2):
    doubled = VALID + VALID.split("entries:\n", 1)[1]
    assert any("listed twice" in e for e in lane2.validate_text(doubled))


def test_non_mapping_top_level(lane2):
    assert lane2.validate_text("- a\n- b\n") == ["top level must be a mapping"]


# ── CLI ──────────────────────────────────────────────────────────────────


def test_cli(root, tmp_path):
    script = root / "scripts" / "ci" / "lane2_approval.py"
    files = tmp_path / "files.json"
    files.write_text(json.dumps(_files(LANE2, "web/x.ts")), encoding="utf-8")
    out = subprocess.run([sys.executable, str(script), "status", "--files-json", str(files), "--expected", "2"],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "mixed"
    bad = tmp_path / "bad.yml"
    bad.write_text("version: 2\n", encoding="utf-8")
    res = json.loads(subprocess.run([sys.executable, str(script), "validate", str(bad)],
                                    capture_output=True, text=True, check=True).stdout)
    assert res["ok"] is False and res["errors"]
    missing = json.loads(subprocess.run([sys.executable, str(script), "validate", str(tmp_path / "nope.yml")],
                                        capture_output=True, text=True, check=True).stdout)
    assert missing["ok"] is False
