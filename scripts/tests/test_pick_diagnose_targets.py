"""Tests for scripts/pick_diagnose_targets.py (pure selection logic)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("pick_diagnose_targets", ROOT / "scripts" / "pick_diagnose_targets.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _issue(n, title):
    return {"number": n, "title": title}


def test_picks_oldest_first_and_respects_limit():
    issues = [_issue(i, f"src{i}：28 天以上 0 產出，原因未知") for i in (9, 3, 5, 7)]
    assert mod.select_targets(issues, {}, limit=2) == [("src3", 3), ("src5", 5)]


def test_skips_issues_already_diagnosed():
    issues = [_issue(1, "a：0 產出"), _issue(2, "b：0 產出")]
    assert mod.select_targets(issues, {1: True}) == [("b", 2)]


def test_skips_non_zero_output_titles_and_prs():
    issues = [
        _issue(1, "a：日期解析錯誤"),
        {"number": 2, "title": "b：0 產出", "pull_request": {}},
        _issue(3, "no source prefix 0 產出"),
        _issue(4, "C-Bad：0 產出"),
    ]
    assert mod.select_targets(issues, {}) == []


def test_one_issue_per_source():
    issues = [_issue(1, "a：0 產出"), _issue(2, "a：連續 0 產出")]
    assert mod.select_targets(issues, {}) == [("a", 1)]
