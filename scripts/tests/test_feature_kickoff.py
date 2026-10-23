"""Tests for scripts/feature_kickoff.py: read-only issue intake for a feature kickoff."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "feature_kickoff.py"


@pytest.fixture(scope="session")
def kick():
    spec = importlib.util.spec_from_file_location("feature_kickoff", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def issue(number, title, labels=(), body="", updated="2026-10-20T00:00:00Z"):
    return {
        "number": number,
        "title": title,
        "labels": [{"name": name} for name in labels],
        "body": body,
        "updatedAt": updated,
        "url": f"https://github.com/o/r/issues/{number}",
    }


ISSUES = [
    issue(1, "cost alert threshold", ["spec:llm-cost-reset"]),
    issue(2, "cost alert threshold needs a week of data", ["spec:llm-cost-reset", "enhancement"]),
    issue(3, "people backfill", ["spec:people-ground-truth"], body="Related to #1 and #99"),
    issue(4, "tokyo_now returns 404", ["scraper"]),
    issue(5, "LLM cost spikes on weekends", [], body="seen in the annotate step"),
    issue(6, "Docs gap", ["documentation"]),
    issue(7, "unrelated | pipe in title", []),
]


def test_selects_only_issues_with_the_spec_label(kick):
    result = kick.build_report(ISSUES, slug="llm-cost-reset", keywords=[])
    assert [i["number"] for i in result["covered"]] == [1, 2]


def test_issues_of_other_specs_are_never_candidates(kick):
    result = kick.build_report(ISSUES, slug="llm-cost-reset", keywords=["backfill"])
    assert [i["number"] for i in result["candidates"]] == []


def test_keyword_candidates_come_only_from_issues_without_any_spec_label(kick):
    result = kick.build_report(ISSUES, slug="llm-cost-reset", keywords=["LLM COST"])
    assert [i["number"] for i in result["candidates"]] == [5]


def test_keywords_match_the_body_too(kick):
    result = kick.build_report(ISSUES, slug="llm-cost-reset", keywords=["annotate step"])
    assert [i["number"] for i in result["candidates"]] == [5]


def test_no_keywords_means_no_candidates(kick):
    result = kick.build_report(ISSUES, slug="llm-cost-reset", keywords=[])
    assert result["candidates"] == []


def test_near_duplicate_titles_are_flagged(kick):
    result = kick.build_report(ISSUES, slug="llm-cost-reset", keywords=[])
    assert [(a, b) for a, b, _ in result["duplicates"]] == [(1, 2)]


def test_a_short_title_inside_another_is_not_flagged(kick):
    result = kick.build_report(
        [issue(1, "bug", ["spec:x"]), issue(2, "bug in the scraper retry path", ["spec:x"])],
        slug="x",
        keywords=[],
    )
    assert result["duplicates"] == []


def test_dissimilar_titles_are_not_flagged(kick):
    result = kick.build_report(
        [issue(1, "alpha beta", ["spec:x"]), issue(2, "completely different words", ["spec:x"])],
        slug="x",
        keywords=[],
    )
    assert result["duplicates"] == []


def test_references_are_kept_only_when_both_ends_are_in_the_report(kick):
    result = kick.build_report(ISSUES, slug="people-ground-truth", keywords=[])
    assert result["references"] == []
    wide = kick.build_report(ISSUES, slug="people-ground-truth", keywords=["cost alert"])
    assert wide["references"] == []
    linked = kick.build_report(
        [issue(1, "a", ["spec:x"]), issue(2, "b", ["spec:x"], body="blocked by #1 and #404")],
        slug="x",
        keywords=[],
    )
    assert linked["references"] == [(2, 1)]


def test_inventory_groups_issues_without_a_spec_label_by_their_other_labels(kick):
    groups = kick.inventory(ISSUES)
    assert groups["scraper"] == [4]
    assert groups["documentation"] == [6]
    assert groups["(no label)"] == [5, 7]
    assert 1 not in sum(groups.values(), [])


def test_markdown_escapes_pipes_in_titles(kick):
    text = kick.render_report(kick.build_report(ISSUES, slug="x", keywords=["unrelated"]), slug="x")
    assert "unrelated \\| pipe in title" in text


def test_a_slug_with_no_issues_says_so_instead_of_failing(kick):
    text = kick.render_report(kick.build_report(ISSUES, slug="brand-new", keywords=[]), slug="brand-new")
    assert "spec:brand-new" in text and "沒有" in text


def run_cli(*args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env, check=False)


def test_cli_reads_a_json_file_and_prints_markdown(tmp_path):
    path = tmp_path / "issues.json"
    path.write_text(json.dumps(ISSUES), encoding="utf-8")
    result = run_cli("--slug", "llm-cost-reset", "--keyword", "llm cost", "--issues-json", str(path))
    assert result.returncode == 0
    assert "#1" in result.stdout and "#5" in result.stdout


def test_cli_inventory_mode(tmp_path):
    path = tmp_path / "issues.json"
    path.write_text(json.dumps(ISSUES), encoding="utf-8")
    result = run_cli("--inventory", "--issues-json", str(path))
    assert result.returncode == 0
    assert "scraper" in result.stdout and "#4" in result.stdout


def test_cli_needs_a_slug_or_inventory():
    assert run_cli().returncode == 2


def test_cli_reports_a_gh_failure_clearly(tmp_path):
    env = {"PATH": "/usr/bin:/bin", "FEATURE_KICKOFF_GH": str(tmp_path / "no-such-gh")}
    result = run_cli("--slug", "x", env=env)
    assert result.returncode == 2
    assert "gh" in result.stderr and "Traceback" not in result.stderr


def test_the_script_never_calls_a_gh_write_command():
    text = SCRIPT.read_text(encoding="utf-8") if SCRIPT.exists() else ""
    for word in ("issue edit", "issue close", "issue create", "issue comment", "label create", "api -X", "--method"):
        assert word not in text
