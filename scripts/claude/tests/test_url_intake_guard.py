"""url-intake approval rules (#702, spec coverage-audit Phase C).

Commands are only parsed and evaluated, never executed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CLAUDE_DIR))
import _policy  # noqa: E402

R = "repos/TuiTuiKoan/tokyo_taiwan_radar"

MUST_ASK = [
    # gh issue / pr label flags
    "gh issue edit 705 --add-label url-intake:approved",
    "gh issue edit 705 --add-label 'url-intake:approved'",
    "gh issue edit 705 --add-label=url-intake:approved",
    "gh issue edit 705 --add-label spec:url-intake,url-intake:approved",
    "gh issue edit 705 --add-label ' URL-Intake:Approved '",
    "gh issue edit 705 706 --add-label url-intake:approved",
    'gh issue edit 705 --add-label "$L"',
    "gh issue create --title t --body b --label url-intake --label url-intake:approved",
    "gh issue create --title t --body b -l url-intake:approved",
    "gh issue create --title t --body b --label=url-intake:approved",
    "gh -R TuiTuiKoan/tokyo_taiwan_radar issue edit 705 --add-label url-intake:approved",
    "gh pr edit 9 --add-label url-intake:approved",
    # gh api REST
    f"gh api {R}/issues/705/labels -f 'labels[]=url-intake:approved'",
    f"gh api {R}/issues/705/labels -f labels[]=URL-INTAKE:APPROVED",
    f"gh api {R}/issues/705/labels --raw-field 'labels[]=url-intake:approved'",
    f"gh api -X PATCH {R}/issues/705 -f 'labels[]=url-intake:approved'",
    f"gh api {R}/issues -f title=t -f 'labels[]=url-intake:approved'",
    f"gh api {R}/issues/705/labels --input labels.json",
    f'gh api {R}/issues/705/labels -f "labels[]=$L"',
    'gh api "repos/$R/issues/705/labels" -f "labels[]=url-intake:approved"',
    f"gh api https://api.github.com/{R}/issues/705/labels -f 'labels[]=url-intake:approved'",
    # gh api GraphQL label mutations
    "gh api graphql -f query='mutation { addLabelsToLabelable(input: {labelableId: \"I\", labelIds: [\"L\"]}) { clientMutationId } }'",
    "gh api graphql -f query='mutation { updateIssue(input: {id: \"I\", labelIds: [\"L\"]}) { issue { id } } }'",
    # workflow dispatch
    "gh workflow run url-intake.yml -f url=https://example.com -f apply=true -f issue=705",
    "gh workflow run url-intake.yml -f url=https://example.com",
    "gh workflow run 'URL Intake' -f apply=true",
    "gh workflow run 123456 -f apply=true",
    'gh workflow run "$WF"',
    "gh workflow run",
    f"gh api {R}/actions/workflows/url-intake.yml/dispatches -f ref=main -f 'inputs[apply]=true'",
    f"gh api -X POST {R}/actions/workflows/123456/dispatches --input inputs.json",
    # environment approval
    f"gh api -X POST {R}/actions/runs/42/pending_deployments -F 'environment_ids[]=1' -f state=approved",
    # wrapped forms are unwrapped first
    "env GH_PAGER= gh issue edit 705 --add-label url-intake:approved",
    "bash -c 'gh issue edit 705 --add-label url-intake:approved'",
    "true && gh issue edit 705 --add-label url-intake:approved",
]

MUST_ALLOW = [
    "gh issue edit 705 --add-label url-intake",
    "gh issue edit 705 --add-label spec:url-intake",
    "gh issue edit 705 --remove-label url-intake:approved",
    "gh issue edit 705 --body 'add url-intake:approved after review'",
    "gh issue create --title t --body b --label url-intake --label spec:url-intake",
    "gh issue view 705",
    "gh pr create --title t --body b --label spec:coverage-audit",
    f"gh api {R}/issues/705/labels -f 'labels[]=url-intake'",
    f"gh api {R}/issues/705/comments -f body='url-intake:approved is the owner label'",
    f"gh api {R}/issues/705/labels",
    f"gh api -X GET {R}/issues -f labels=url-intake:approved",
    f"gh api -X PATCH {R}/issues/705 -f state=closed -f state_reason=completed",
    f"gh api {R}/pulls -f title=t -f head=feat/x -f base=main",
    "gh workflow run scraper.yml",
    "gh workflow run annotate-now.yml -f source=peatix",
    "gh workflow list",
    "gh workflow view url-intake.yml",
    "gh run list --workflow url-intake.yml",
    f"gh api {R}/actions/workflows/annotate-now.yml/dispatches -f ref=main",
    f"gh api {R}/actions/runs/42/pending_deployments",
    "gh api graphql -f query='query { viewer { login } }'",
    'gh api "repos/$R/issues/705/comments" -f body=hi',
]


@pytest.mark.parametrize("command", MUST_ASK)
def test_url_intake_approval_asks(command):
    decision = _policy.evaluate_command(command)
    assert decision == _policy.ASK_URL_INTAKE, command


@pytest.mark.parametrize("command", MUST_ALLOW)
def test_unrelated_github_operations_pass(command):
    assert _policy.evaluate_command(command) == _policy.ALLOW, command


def test_ask_payload_is_valid_output():
    text = __import__("json").dumps(_policy.ask_payload(_policy.ASK_URL_INTAKE.message()))
    assert _policy.valid_output(text)
    assert "[url-intake-approval]" in _policy.ASK_URL_INTAKE.message()


def test_merge_deny_still_wins_over_the_label_rule():
    command = f"gh api -X PUT {R}/pulls/9/merge -f 'labels[]=url-intake:approved'"
    assert _policy.evaluate_command(command).kind == "deny"


def mcp(tool: str, data: dict) -> dict:
    return {"tool_name": f"mcp__github__{tool}", "tool_input": data}


@pytest.mark.parametrize("tool,data", [
    ("add_labels_to_issue", {"issue_number": 705, "labels": ["url-intake:approved"]}),
    ("issue_write", {"method": "update", "issue_number": 705, "labels": ["spec:url-intake", "URL-Intake:Approved"]}),
    ("update_issue", {"issue_number": 705, "labels": "url-intake,url-intake:approved"}),
    ("create_issue", {"title": "t", "body": "b", "labels": [" url-intake:approved "]}),
    ("future_tool_name", {"payload": {"nested": [{"label": "url-intake:approved"}]}}),
])
def test_mcp_tools_adding_the_label_ask(tool, data):
    assert _policy.mcp_decision(mcp(tool, data)) == _policy.ASK_URL_INTAKE


@pytest.mark.parametrize("tool,data", [
    ("add_labels_to_issue", {"issue_number": 705, "labels": ["url-intake"]}),
    ("add_issue_comment", {"issue_number": 705, "body": "please add url-intake:approved"}),
    ("create_issue", {"title": "t", "body": "b", "labels": ["spec:url-intake"]}),
    ("get_issue", {"issue_number": 705}),
])
def test_mcp_tools_without_the_label_pass(tool, data):
    assert _policy.mcp_decision(mcp(tool, data)) == _policy.ALLOW


def test_mcp_merge_deny_still_wins():
    data = {"pullNumber": 5, "labels": ["url-intake:approved"]}
    assert _policy.mcp_decision(mcp("merge_pull_request", data)).kind == "deny"
