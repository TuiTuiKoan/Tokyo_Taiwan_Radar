"""Shared harness for the campaign-anchor tests.

Every fixture here is synthetic. No test in this directory may read a real
Copilot transcript, and every git assertion runs against a throwaway repository
created under ``tmp_path``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SKILL_ROOT = TESTS_DIR.parent
GENERATOR_REL = ".github/skills/session-analytics/oneoff_campaign_anchor.py"
GENERATOR = SKILL_ROOT / "oneoff_campaign_anchor.py"

if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "anchor-test",
    "GIT_AUTHOR_EMAIL": "anchor-test@example.invalid",
    "GIT_COMMITTER_NAME": "anchor-test",
    "GIT_COMMITTER_EMAIL": "anchor-test@example.invalid",
}

SESSION_ID = "11111111-1111-4111-8111-111111111111"
CAMPAIGN = "2026-08-03-fixture-campaign"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


anchor = _load("oneoff_campaign_anchor", GENERATOR)
detectors = _load("detectors", SKILL_ROOT / "detectors.py")


def load_generator(workspace):
    """Import the copy living inside the throwaway repo, so ``__file__`` resolves there."""
    return _load("oneoff_campaign_anchor_workspace", workspace.generator)


def uid(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


def event(n: int, timestamp: str, event_type: str, tool: str | None = None, **extra) -> dict:
    payload = {"id": uid(n), "timestamp": timestamp, "type": event_type}
    if tool is not None:
        payload["data"] = {"toolName": tool}
    payload.update(extra)
    return payload


def canonical_events() -> list[dict]:
    """Eight selected events between uid(2) (inclusive) and uid(10) (exclusive)."""
    return [
        event(1, "2026-08-03T00:00:00Z", "session.start"),
        event(2, "2026-08-03T00:00:01Z", "user.message"),
        event(3, "2026-08-03T00:00:02Z", "assistant.turn_start"),
        event(4, "2026-08-03T00:00:03Z", "tool.execution_start", "read_file"),
        event(5, "2026-08-03T00:00:04Z", "tool.execution_start", "read_file"),
        event(6, "2026-08-03T00:00:05Z", "tool.execution_start", "grep_search"),
        event(7, "2026-08-03T01:00:00Z", "user.message"),
        event(8, "2026-08-03T01:00:01Z", "assistant.turn_start"),
        event(9, "2026-08-03T01:00:02Z", "tool.execution_start", "run_in_terminal"),
        event(10, "2026-08-03T02:30:00Z", "user.message"),
        event(11, "2026-08-03T03:00:00Z", "assistant.turn_start"),
    ]


def render_transcript(events, newline: str = "\n", trailing_newline: bool = True) -> bytes:
    lines = [json.dumps(ev, ensure_ascii=False) for ev in events]
    body = newline.join(lines)
    if trailing_newline:
        body += newline
    return body.encode("utf-8")


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr or proc.stdout}")
    return proc.stdout.strip()


class Workspace:
    def __init__(self, root: Path, transcripts: Path) -> None:
        self.root = root
        self.transcripts = transcripts
        self.head = git(root, "rev-parse", "HEAD")

    @property
    def generator(self) -> Path:
        return self.root / GENERATOR_REL

    @property
    def generator_commit(self) -> str:
        """The commit the generator pins its provenance to: its own last-touching commit."""
        return git(self.root, "log", "-1", "--format=%H", "--", GENERATOR_REL)

    @property
    def record(self) -> Path:
        return self.root / "docs/evaluation/campaigns" / f"{CAMPAIGN}.md"

    @property
    def ledger_dir(self) -> Path:
        return self.root / "docs/evaluation/campaigns/ledger"

    def ledgers(self) -> list[Path]:
        return sorted(self.ledger_dir.glob("*.jsonl")) if self.ledger_dir.is_dir() else []

    def stray_temp_files(self) -> list[Path]:
        return sorted(p for p in self.root.rglob("*.tmp-*") if p.is_file())

    def write_transcript(self, data: bytes, session_id: str = SESSION_ID) -> Path:
        path = self.transcripts / f"{session_id}.jsonl"
        path.write_bytes(data)
        return path

    def argv(self, slices=None, outcome_refs=None, campaign: str = CAMPAIGN) -> list[str]:
        args = ["--campaign", campaign]
        for value in slices if slices is not None else [f"{SESSION_ID}:{uid(2)}:{uid(10)}"]:
            args += ["--session-slice", value]
        for ref in outcome_refs if outcome_refs is not None else [self.head]:
            args += ["--outcome-ref", ref]
        args += [
            "--record-output",
            f"docs/evaluation/campaigns/{campaign}.md",
            "--ledger-dir",
            "docs/evaluation/campaigns/ledger",
            "--transcripts-dir",
            str(self.transcripts),
        ]
        return args

    def run(self, slices=None, outcome_refs=None, campaign: str = CAMPAIGN):
        return subprocess.run(
            [sys.executable, str(self.generator), *self.argv(slices, outcome_refs, campaign)],
            capture_output=True,
            text=True,
            env=GIT_ENV,
        )


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    root = tmp_path / "repo"
    (root / GENERATOR_REL).parent.mkdir(parents=True)
    shutil.copy2(GENERATOR, root / GENERATOR_REL)
    (root / "README.md").write_text("fixture repo\n", encoding="utf-8")

    git(root.parent, "init", "-q", "-b", "main", str(root))
    git(root, "config", "commit.gpgsign", "false")
    git(root, "config", "core.hooksPath", str(tmp_path / "no-hooks"))
    git(root, "add", "-A")
    git(root, "commit", "-qm", "seed")
    git(root, "update-ref", "refs/remotes/origin/main", git(root, "rev-parse", "HEAD"))

    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()

    workspace = Workspace(root, transcripts)
    workspace.write_transcript(render_transcript(canonical_events()))
    return workspace
