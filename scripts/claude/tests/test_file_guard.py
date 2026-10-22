"""Tool-layer rule 7 tests for the Read/Grep/Write/Edit/NotebookEdit guard."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CLAUDE_DIR))
import _policy  # noqa: E402

REPO = "/Users/x/Tokyo Taiwan Radar"

DENY = [
    ("Read", {"file_path": f"{REPO}/scraper/.env"}, "env-file-access"),
    ("Read", {"file_path": f"{REPO}/.env"}, "env-file-access"),
    ("Read", {"file_path": f"{REPO}/web/.env.local"}, "env-file-access"),
    ("Read", {"file_path": f"{REPO}/web/.env.production", "offset": 1, "limit": 5}, "env-file-access"),
    ("Read", {"file_path": f"{REPO}/docs/.env.smoke-nonexistent"}, "env-file-access"),
    ("Grep", {"pattern": "TOKEN", "path": f"{REPO}/scraper/.env"}, "env-file-access"),
    ("Grep", {"pattern": "TOKEN", "glob": ".env*"}, "env-file-access"),
    ("Grep", {"pattern": "TOKEN", "glob": "**/.env"}, "env-file-access"),
    ("Grep", {"pattern": "TOKEN", "glob": "{a,.env}"}, "env-file-access"),
    ("Write", {"file_path": f"{REPO}/scraper/.env", "content": "X=1"}, "env-file-write"),
    ("Write", {"file_path": f"{REPO}/.env.local", "content": "X=1"}, "env-file-write"),
    ("Edit", {"file_path": f"{REPO}/scraper/.env", "old_string": "a", "new_string": "b"}, "env-file-write"),
    ("Write", {"file_path": f"{REPO}/web/.env.production", "content": "X=1"}, "env-file-write"),
    ("Edit", {"file_path": f"{REPO}/.env.test", "old_string": "a", "new_string": "b"}, "env-file-write"),
    ("Edit", {"file_path": f"{REPO}/web/.env.local", "old_string": "a", "new_string": "b"}, "env-file-write"),
    ("NotebookEdit", {"notebook_path": f"{REPO}/.env", "cell_id": "c1", "new_source": "x"}, "env-file-write"),
    ("NotebookEdit", {"notebook_path": f"{REPO}/x/.env.dev", "new_source": "x"}, "env-file-write"),
    ("NotebookEdit", {"notebook_path": f"{REPO}/.env.production", "new_source": "x"}, "env-file-write"),
]

ALLOW = [
    ("Read", {"file_path": f"{REPO}/AGENTS.md"}),
    ("Read", {"file_path": f"{REPO}/scraper/.env.example"}),
    ("Read", {"file_path": f"{REPO}/docs/environment.md"}),
    ("Grep", {"pattern": "TOKEN"}),
    ("Grep", {"pattern": "TOKEN", "path": f"{REPO}/scraper"}),  # rule 7 boundary (notes.md §4.21)
    ("Grep", {"pattern": "TOKEN", "glob": "*.py"}),
    ("Grep", {"pattern": "TOKEN", "glob": "!.env"}),
    ("Write", {"file_path": f"{REPO}/docs/notes.md", "content": "mentions .env"}),
    ("Edit", {"file_path": f"{REPO}/scraper/.env.example", "old_string": "a", "new_string": "b"}),
    ("NotebookEdit", {"notebook_path": f"{REPO}/nb.ipynb", "new_source": "x"}),
    # git config files are readable; only writes ask (git-config-gate)
    ("Read", {"file_path": f"{REPO}/.git/config"}),
    ("Grep", {"pattern": "push", "path": f"{REPO}/.git/config"}),
    ("Write", {"file_path": f"{REPO}/.git/info/exclude", "content": "x"}),
    ("Write", {"file_path": f"{REPO}/.github/config", "content": "x"}),
    ("Edit", {"file_path": f"{REPO}/web/.gitconfig", "old_string": "a", "new_string": "b"}),
    ("Write", {"file_path": f"{REPO}/.git/config.bak", "content": "x"}),
    ("Write", {"file_path": f"{REPO}/scraper/config", "content": "x"}),
]

# Phase C P1: writes to the repository's git configuration ask, since remote.<name>.push,
# push.default, url.*.pushInsteadOf and core.hooksPath change where a later push goes.
ASK = [
    ("Write", {"file_path": f"{REPO}/.git/config", "content": "[push]\n\tdefault = current"}),
    ("Edit", {"file_path": f"{REPO}/.git/config", "old_string": "a", "new_string": "b"}),
    ("NotebookEdit", {"notebook_path": f"{REPO}/.git/config", "new_source": "x"}),
    ("Write", {"file_path": f"{REPO}/.git/config.worktree", "content": "x"}),
    ("Write", {"file_path": f"{REPO}/.git/worktrees/ttr-x-worktree/config", "content": "x"}),
    ("Edit", {"file_path": f"{REPO}/.git/worktrees/ttr-x-worktree/config.worktree", "old_string": "a", "new_string": "b"}),
    ("Write", {"file_path": f"{REPO}/.git/modules/sub/config", "content": "x"}),
    ("Write", {"file_path": ".git/config", "content": "x"}),
]

BAD = [
    {"tool_name": "Read", "tool_input": {}},
    {"tool_name": "Read", "tool_input": {"file_path": None}},
    {"tool_name": "Grep", "tool_input": {"pattern": "x", "path": 3}},
    {"tool_name": "Write", "tool_input": "x"},
    {"tool_name": "Glob", "tool_input": {"pattern": "*"}},
    {"tool_input": {"file_path": "/x"}},
    "Read",
]


@pytest.mark.parametrize(("tool", "data", "rule"), DENY)
def test_deny(tool, data, rule):
    decision = _policy.file_decision({"tool_name": tool, "tool_input": data})
    assert (decision.kind, decision.rule) == ("deny", rule)


@pytest.mark.parametrize(("tool", "data"), ALLOW)
def test_allow(tool, data):
    assert _policy.file_decision({"tool_name": tool, "tool_input": data}).kind == "allow"


@pytest.mark.parametrize(("tool", "data"), ASK)
def test_git_config_write_asks(tool, data):
    decision = _policy.file_decision({"tool_name": tool, "tool_input": data})
    assert (decision.kind, decision.rule) == ("ask", "git-config-gate"), (tool, data, decision)


def test_git_config_ask_goes_through_launcher_protocol():
    result = subprocess.run(
        [sys.executable, str(CLAUDE_DIR / "pretooluse_file_guard.py")],
        input=json.dumps({"tool_name": "Write", "tool_input": {"file_path": f"{REPO}/.git/config", "content": "x"}}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0 and result.stderr == ""
    assert _policy.valid_output(result.stdout)
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"


@pytest.mark.parametrize("payload", BAD)
def test_bad_payload_raises(payload):
    with pytest.raises(ValueError):
        _policy.file_decision(payload)


def test_every_guarded_tool_has_three_deny_variants():
    from collections import Counter

    counts = Counter(tool for tool, _, _ in DENY)
    assert all(counts[tool] >= 3 for tool in _policy.FILE_FIELDS), counts


@pytest.mark.parametrize("payload", ["{", json.dumps(BAD[0]), json.dumps(BAD[4])])
def test_guard_internal_error_is_fixed_message(payload):
    result = subprocess.run(
        [sys.executable, str(CLAUDE_DIR / "pretooluse_file_guard.py")],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert result.stderr == _policy.INTERNAL_ERROR + "\n"
    assert result.stdout == ""
