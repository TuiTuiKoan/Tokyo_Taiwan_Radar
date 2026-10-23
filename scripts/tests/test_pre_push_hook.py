"""Behaviour of .githooks/pre-push (issue #346: it used to fail open when the remote SHA is unknown locally)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".githooks" / "pre-push"
ZERO = "0" * 40
UNKNOWN = "deadbeef" * 5


def git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True, env=env)
    return result.stdout.strip()


def commit(repo: Path, name: str, text: str) -> str:
    (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", f"add {name}")
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo copy"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    base = commit(path, "a.txt", "a\n")
    git(path, "update-ref", "refs/remotes/origin/main", base)
    return path


@pytest.fixture
def no_gitleaks_path(tmp_path: Path) -> str:
    """A PATH with the tools the hook needs but without gitleaks, so the regex fallback runs."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("git", "bash", "grep", "python3", "env", "dirname", "cat", "sed"):
        found = shutil.which(tool)
        if found:
            (bin_dir / tool).symlink_to(found)
    return str(bin_dir)


def run_hook(repo: Path, path: str, remote: str, lines: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HOOK), remote, "git@example.com:org/repo.git"],
        cwd=repo,
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": path},
        check=False,
    )


def test_hook_is_executable():
    assert os.access(HOOK, os.X_OK)


def test_fast_forward_range_without_secrets_passes(repo, no_gitleaks_path):
    base = git(repo, "rev-parse", "HEAD")
    head = commit(repo, "b.txt", "hello\n")
    result = run_hook(repo, no_gitleaks_path, "origin", [f"refs/heads/x {head} refs/heads/x {base}"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_new_branch_uses_merge_base_and_passes(repo, no_gitleaks_path):
    head = commit(repo, "b.txt", "hello\n")
    result = run_hook(repo, no_gitleaks_path, "origin", [f"refs/heads/x {head} refs/heads/x {ZERO}"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_other_remotes_are_ignored(repo, no_gitleaks_path):
    head = commit(repo, "b.txt", "hello\n")
    result = run_hook(repo, no_gitleaks_path, "upstream", [f"refs/heads/x {head} refs/heads/x {UNKNOWN}"])
    assert result.returncode == 0


def test_secret_in_range_is_blocked_by_the_fallback(repo, no_gitleaks_path):
    base = git(repo, "rev-parse", "HEAD")
    head = commit(repo, "leak.txt", "token = github_pat_" + "A" * 30 + "\n")
    result = run_hook(repo, no_gitleaks_path, "origin", [f"refs/heads/x {head} refs/heads/x {base}"])
    assert result.returncode == 1
    assert "potential secret" in result.stdout


def test_unknown_remote_sha_blocks_instead_of_scanning_nothing(repo, no_gitleaks_path):
    """#346: the range cannot be built, so the scan covered 0 commits and the push was let through."""
    head = commit(repo, "b.txt", "hello\n")
    result = run_hook(repo, no_gitleaks_path, "origin", [f"refs/heads/x {head} refs/heads/x {UNKNOWN}"])
    assert result.returncode == 1, result.stdout + result.stderr
    assert "git fetch origin" in result.stdout + result.stderr


def test_deleting_a_ref_is_not_scanned(repo, no_gitleaks_path):
    result = run_hook(repo, no_gitleaks_path, "origin", [f"(delete) {ZERO} refs/heads/x {UNKNOWN}"])
    assert result.returncode == 0
