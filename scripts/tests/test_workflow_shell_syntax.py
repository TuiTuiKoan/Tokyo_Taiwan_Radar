"""Issue #633: parse every workflow and check the shell syntax of every `run:` block.

Most of this repository's CI logic is shell inside `run:` blocks, and until now a
pull request that only touched `.github/workflows/**` ran no checks at all, so a
typo there was found by the next scheduled firing rather than by review.

`bash -n` parses without executing, which catches unbalanced quotes, `if`/`fi`
and heredoc mistakes — the errors that make a job fail on its first line. It
does not understand GitHub expressions: `${{ ... }}` is substituted before the
shell sees it, so each one is replaced with a placeholder token first.

This is deliberately not actionlint: it needs no third-party binary, runs
offline, and covers the failure mode that actually bites here. Adding actionlint
on top is tracked in #633.
"""
from __future__ import annotations

import re
import subprocess

import pytest
import yaml

# `${{ secrets.X }}`, `${{ inputs.y }}`, … are expanded by the runner before the
# shell runs. A bare word keeps the surrounding shell syntax intact.
EXPRESSION = re.compile(r"\$\{\{[^}]*\}\}")
PLACEHOLDER = "gha_expression"
# Only these two are POSIX shells; `shell: python` and friends are not ours to parse.
SHELLS = {None, "bash", "sh", "bash -e {0}", "bash -eo pipefail {0}"}


def _run_blocks(root):
    """Yield (workflow, job, step index, step name, script) for every shell `run:` block."""
    for path in sorted((root / ".github" / "workflows").glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in (data.get("jobs") or {}).items():
            for index, step in enumerate(job.get("steps") or []):
                script = step.get("run")
                if not script:
                    continue
                shell = step.get("shell") or job.get("defaults", {}).get("run", {}).get("shell")
                if shell not in SHELLS:
                    continue
                yield path.name, job_name, index, step.get("name") or f"step {index}", script


def _ids(root):
    return [f"{w}:{j}:{i}" for w, j, i, _, _ in _run_blocks(root)]


def test_every_workflow_parses_as_yaml(root):
    """A workflow that does not parse never runs, and GitHub reports it only in the UI."""
    for path in sorted((root / ".github" / "workflows").glob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:  # pragma: no cover - only on a broken workflow
            pytest.fail(f"{path.name} is not valid YAML: {exc}")
        assert data.get("jobs"), f"{path.name} declares no jobs"


def test_there_are_run_blocks_to_check(root):
    """Guard against the collection logic silently matching nothing."""
    assert len(list(_run_blocks(root))) > 100


def test_shell_syntax_of_every_run_block(root):
    failures = []
    for workflow, job_name, index, step_name, script in _run_blocks(root):
        result = subprocess.run(
            ["bash", "-n"],
            input=EXPRESSION.sub(PLACEHOLDER, script),
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr.strip().splitlines() or ["(no output)"])[-1]
            failures.append(f"{workflow} / {job_name} / {step_name}: {detail}")
    assert not failures, "bash -n rejected these run blocks:\n" + "\n".join(failures)
