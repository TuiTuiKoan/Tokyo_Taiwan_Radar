"""Tests for scripts/board_audit.py: a read-only audit of the board's 主題 field against the spec map."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "board_audit.py"
REAL_MAP = ROOT / "docs" / "specs" / "board-themes.json"

MAPPING = {
    "board": {"owner": "o", "project": 1, "field": "主題"},
    "themes": {"成本": "cost", "Eval": "eval", "追蹤清理": "tidy", "AI工具鏈": "ai"},
    "specs": {"llm-cost-reset": "成本", "evaluation-framework": "Eval", "workstream-tracking": "追蹤清理", "ai-harness": "AI工具鏈"},
    "exempt": {"labels": ["daily-review"], "issues": {"9": "single-point item, not a roadmap theme"}},
    "overrides": {"7": {"theme": "追蹤清理", "reason": "the work is cleanup although the spec is ai-harness"}},
}


@pytest.fixture(scope="session")
def audit():
    spec = importlib.util.spec_from_file_location("board_audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def item(number, labels=(), theme=None, state="OPEN", title=None, item_id=None):
    return {
        "number": number,
        "title": title or f"issue {number}",
        "state": state,
        "labels": list(labels),
        "theme": theme,
        "item_id": item_id or f"ITEM{number}",
        "url": f"https://github.com/o/r/issues/{number}",
    }


def test_a_spec_label_with_no_theme_gets_the_mapped_theme(audit):
    report = audit.audit_items([item(1, ["spec:llm-cost-reset"])], MAPPING)
    assert [(r["number"], r["theme"]) for r in report["derive"]] == [(1, "成本")]


def test_a_matching_theme_is_fine(audit):
    report = audit.audit_items([item(1, ["spec:llm-cost-reset"], theme="成本")], MAPPING)
    assert report["derive"] == [] and report["mismatch"] == [] and report["ok"] == 1


def test_a_different_theme_is_a_mismatch_and_not_derived(audit):
    report = audit.audit_items([item(1, ["spec:llm-cost-reset"], theme="Eval")], MAPPING)
    assert [(r["number"], r["theme"], r["expected"]) for r in report["mismatch"]] == [(1, "Eval", "成本")]
    assert report["derive"] == []


def test_a_spec_label_missing_from_the_map_is_reported(audit):
    report = audit.audit_items([item(1, ["spec:brand-new"])], MAPPING)
    assert [(r["number"], r["spec"]) for r in report["unmapped_spec"]] == [(1, "spec:brand-new")]
    assert report["derive"] == []


def test_an_issue_with_no_spec_and_no_theme_needs_a_decision(audit):
    report = audit.audit_items([item(1, ["scraper"])], MAPPING)
    assert [r["number"] for r in report["needs_decision"]] == [1]


def test_an_issue_with_a_theme_but_no_spec_is_fine(audit):
    report = audit.audit_items([item(1, ["scraper"], theme="成本")], MAPPING)
    assert report["needs_decision"] == [] and report["ok"] == 1


def test_closed_issues_are_ignored(audit):
    report = audit.audit_items([item(1, ["spec:llm-cost-reset"], state="CLOSED"), item(2, [], state="CLOSED")], MAPPING)
    assert report["derive"] == [] and report["needs_decision"] == [] and report["ok"] == 0


def test_two_specs_with_different_themes_are_ambiguous(audit):
    report = audit.audit_items([item(1, ["spec:evaluation-framework", "spec:llm-cost-reset"])], MAPPING)
    assert [r["number"] for r in report["ambiguous"]] == [1]
    same = audit.audit_items([item(2, ["spec:ai-harness", "spec:workstream-tracking"])], MAPPING)
    assert [r["number"] for r in same["ambiguous"]] == [2]


def test_two_specs_mapping_to_one_theme_derive_that_theme(audit):
    mapping = json.loads(json.dumps(MAPPING))
    mapping["specs"]["extra"] = "Eval"
    report = audit.audit_items([item(1, ["spec:evaluation-framework", "spec:extra"])], mapping)
    assert [(r["number"], r["theme"]) for r in report["derive"]] == [(1, "Eval")]


def test_a_theme_not_in_the_theme_list_is_flagged(audit):
    report = audit.audit_items([item(1, [], theme="Typo")], MAPPING)
    assert [(r["number"], r["theme"]) for r in report["unknown_theme"]] == [(1, "Typo")]


def test_map_entries_without_open_issues_are_listed_as_unused(audit):
    report = audit.audit_items([item(1, ["spec:llm-cost-reset"], theme="成本")], MAPPING)
    assert report["unused_map_specs"] == ["ai-harness", "evaluation-framework", "workstream-tracking"]


def test_a_map_entry_with_an_unknown_theme_is_rejected(audit):
    bad = json.loads(json.dumps(MAPPING))
    bad["specs"]["llm-cost-reset"] = "Nope"
    with pytest.raises(audit.AuditError):
        audit.validate_map(bad)


def test_an_exempt_label_skips_every_check(audit):
    report = audit.audit_items([item(1, ["daily-review"]), item(2, ["daily-review", "spec:brand-new"])], MAPPING)
    assert report["needs_decision"] == [] and report["unmapped_spec"] == []
    assert [r["number"] for r in report["exempt"]] == [1, 2]


def test_an_exempt_issue_number_skips_every_check_and_keeps_its_reason(audit):
    report = audit.audit_items([item(9, ["enhancement"]), item(10, ["enhancement"])], MAPPING)
    assert [r["number"] for r in report["needs_decision"]] == [10]
    assert [(r["number"], r["reason"]) for r in report["exempt"]] == [(9, "single-point item, not a roadmap theme")]


def test_an_exempt_issue_that_already_has_a_theme_is_still_just_exempt(audit):
    report = audit.audit_items([item(9, [], theme="成本")], MAPPING)
    assert [r["number"] for r in report["exempt"]] == [9] and report["ok"] == 0


def test_a_map_without_an_exempt_section_still_works(audit):
    bare = {k: v for k, v in MAPPING.items() if k != "exempt"}
    assert audit.audit_items([item(1, ["scraper"])], bare)["exempt"] == []


def test_a_non_numeric_exempt_issue_key_is_rejected(audit):
    bad = json.loads(json.dumps(MAPPING))
    bad["exempt"]["issues"]["abc"] = "x"
    with pytest.raises(audit.AuditError):
        audit.validate_map(bad)


def test_the_report_lists_exempt_issues_with_their_reason(audit):
    text = audit.render_report(audit.audit_items([item(9, ["enhancement"])], MAPPING))
    assert "豁免" in text and "single-point item" in text


def test_an_override_replaces_the_spec_theme_for_that_issue_only(audit):
    report = audit.audit_items([item(7, ["spec:ai-harness"], theme="追蹤清理"), item(8, ["spec:ai-harness"], theme="追蹤清理")], MAPPING)
    assert report["ok"] == 1
    assert [(r["number"], r["theme"], r["expected"]) for r in report["mismatch"]] == [(8, "追蹤清理", "AI工具鏈")]


def test_an_override_is_derived_when_the_theme_is_missing(audit):
    report = audit.audit_items([item(7, ["spec:ai-harness"])], MAPPING)
    assert [(r["number"], r["theme"]) for r in report["derive"]] == [(7, "追蹤清理")]


def test_an_override_that_disagrees_with_the_board_is_a_mismatch(audit):
    report = audit.audit_items([item(7, ["spec:ai-harness"], theme="AI工具鏈")], MAPPING)
    assert [(r["number"], r["theme"], r["expected"]) for r in report["mismatch"]] == [(7, "AI工具鏈", "追蹤清理")]


def test_overrides_are_listed_with_their_reason(audit):
    report = audit.audit_items([item(7, ["spec:ai-harness"], theme="追蹤清理")], MAPPING)
    assert [(r["number"], r["theme"], r["spec_theme"]) for r in report["overridden"]] == [(7, "追蹤清理", "AI工具鏈")]
    text = audit.render_report(report)
    assert "覆寫" in text and "the work is cleanup" in text


def test_an_override_works_for_an_issue_without_a_spec_label(audit):
    report = audit.audit_items([item(7, ["scraper"])], MAPPING)
    assert [(r["number"], r["theme"]) for r in report["derive"]] == [(7, "追蹤清理")]
    assert report["needs_decision"] == []


def test_an_override_with_an_unknown_theme_or_no_reason_is_rejected(audit):
    bad_theme = json.loads(json.dumps(MAPPING))
    bad_theme["overrides"]["7"]["theme"] = "Nope"
    with pytest.raises(audit.AuditError):
        audit.validate_map(bad_theme)
    no_reason = json.loads(json.dumps(MAPPING))
    no_reason["overrides"]["7"]["reason"] = ""
    with pytest.raises(audit.AuditError):
        audit.validate_map(no_reason)
    bad_key = json.loads(json.dumps(MAPPING))
    bad_key["overrides"]["abc"] = {"theme": "成本", "reason": "x"}
    with pytest.raises(audit.AuditError):
        audit.validate_map(bad_key)


def test_a_map_without_overrides_still_works(audit):
    bare = {k: v for k, v in MAPPING.items() if k != "overrides"}
    assert audit.audit_items([item(1, ["spec:llm-cost-reset"], theme="成本")], bare)["overridden"] == []


def test_the_real_map_is_internally_consistent(audit):
    mapping = json.loads(REAL_MAP.read_text(encoding="utf-8"))
    audit.validate_map(mapping)
    assert set(mapping["specs"].values()) <= set(mapping["themes"])
    assert mapping["board"]["field"] == "主題"


# --- applying: only deterministic rows, only on request ---------------------------------


def test_apply_edits_only_the_derived_rows(audit):
    items = [
        item(1, ["spec:llm-cost-reset"]),
        item(2, ["spec:llm-cost-reset"], theme="Eval"),
        item(3, ["scraper"]),
        item(4, ["spec:brand-new"]),
        item(5, ["spec:evaluation-framework"]),
    ]
    report = audit.audit_items(items, MAPPING)
    calls = []
    audit.apply_derived(report["derive"], calls.append, project_id="P", field_id="F", option_ids={"成本": "O1", "Eval": "O2"})
    assert [c[c.index("--id") + 1] for c in calls] == ["ITEM1", "ITEM5"]
    assert [c[c.index("--single-select-option-id") + 1] for c in calls] == ["O1", "O2"]
    assert all(c[:3] == ["project", "item-edit", "--id"] for c in calls)


def test_apply_refuses_a_theme_without_an_option_id(audit):
    report = audit.audit_items([item(1, ["spec:llm-cost-reset"])], MAPPING)
    with pytest.raises(audit.AuditError):
        audit.apply_derived(report["derive"], lambda call: None, project_id="P", field_id="F", option_ids={})


# --- rendering and parsing -----------------------------------------------------------------


def test_the_report_names_each_section_and_escapes_pipes(audit):
    report = audit.audit_items([item(1, ["scraper"], title="a | b")], MAPPING)
    text = audit.render_report(report)
    assert "需要決定" in text and "a \\| b" in text and "#1" in text


def test_parse_nodes_reads_a_graphql_item(audit):
    nodes = [
        {"id": "I1", "content": {"number": 7, "title": "t", "state": "OPEN", "url": "u", "labels": {"nodes": [{"name": "spec:x"}]}}, "theme": {"name": "成本"}},
        {"id": "I2", "content": {}, "theme": None},
        {"id": "I3", "content": {"number": 8, "title": "t2", "state": "CLOSED", "url": "u2", "labels": {"nodes": []}}, "theme": None},
    ]
    parsed = audit.parse_nodes(nodes)
    assert [(p["number"], p["theme"], p["labels"], p["state"]) for p in parsed] == [(7, "成本", ["spec:x"], "OPEN"), (8, None, [], "CLOSED")]


# --- the command line -----------------------------------------------------------------------


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)


def write_items(tmp_path, items):
    path = tmp_path / "items.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    return str(path)


def test_cli_reads_items_from_a_file(tmp_path):
    items = write_items(tmp_path, [item(1, ["spec:llm-cost-reset"])])
    result = run_cli("--map", str(REAL_MAP), "--items-json", items)
    assert result.returncode == 0
    assert "#1" in result.stdout and "成本" in result.stdout


def test_cli_strict_fails_when_there_are_findings(tmp_path):
    items = write_items(tmp_path, [item(1, ["spec:llm-cost-reset"])])
    assert run_cli("--map", str(REAL_MAP), "--items-json", items, "--strict").returncode == 1
    clean = write_items(tmp_path, [item(2, ["spec:llm-cost-reset"], theme="成本")])
    assert run_cli("--map", str(REAL_MAP), "--items-json", clean, "--strict").returncode == 0


def test_cli_apply_needs_the_live_board_and_a_confirmation(tmp_path):
    items = write_items(tmp_path, [item(1, ["spec:llm-cost-reset"])])
    offline = run_cli("--map", str(REAL_MAP), "--items-json", items, "--apply", "--yes")
    assert offline.returncode == 2 and "items-json" in offline.stderr
    unconfirmed = run_cli("--map", str(REAL_MAP), "--apply")
    assert unconfirmed.returncode == 2 and "--yes" in unconfirmed.stderr


def test_the_script_never_changes_issues_labels_or_the_board_schema():
    text = SCRIPT.read_text(encoding="utf-8") if SCRIPT.exists() else ""
    for word in ("issue edit", "issue close", "issue create", "issue comment", "label create", "updateProjectV2Field", "deleteProjectV2", "--add-label", "--remove-label"):
        assert word not in text
