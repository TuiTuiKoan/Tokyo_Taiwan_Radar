"""Issue #561: production secrets live in the GitHub Environment `production`,
whose deployment branch policy allows only main.

Every job that reads a secret (other than GITHUB_TOKEN) must declare
`environment: production`, and must not be able to run on pull_request.
Otherwise, once the repository-level secrets are removed, the job silently
loses its credentials; or, before that, a PR's code runs with them.
"""
from __future__ import annotations

import json
import re

import pytest
import yaml

SECRET_RE = re.compile(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)|secrets\[")


def _workflows(root):
    return sorted((root / ".github" / "workflows").glob("*.yml"))


def _triggers(data) -> set[str]:
    on = data.get(True, data.get("on"))  # PyYAML reads the bare key `on` as True
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return set(on)
    return set(on or {})


def _secret_jobs(root):
    for path in _workflows(root):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, job in (data.get("jobs") or {}).items():
            names = {m.group(1) or "<dynamic>" for m in SECRET_RE.finditer(json.dumps(job))}
            names.discard("GITHUB_TOKEN")
            if names:
                yield path.name, name, job, _triggers(data)


def test_there_are_secret_jobs(root):
    assert len(list(_secret_jobs(root))) > 10


@pytest.mark.parametrize("workflow, job", [(w, j) for w, j, *_ in _secret_jobs(__import__("pathlib").Path(__file__).resolve().parents[2])])
def test_secret_jobs_use_production_environment(root, workflow, job):
    for w, j, body, triggers in _secret_jobs(root):
        if (w, j) != (workflow, job):
            continue
        env = body.get("environment")
        name = env.get("name") if isinstance(env, dict) else env
        assert name == "production", f"{workflow}:{job} reads secrets without environment: production"
        if triggers & {"pull_request", "pull_request_target"}:
            cond = str(body.get("if", ""))
            assert "github.event_name != 'pull_request'" in cond, (
                f"{workflow}:{job} reads secrets and can run on pull_request"
            )


# --- Issue #620 (agent-autonomy E1): the step that runs scraper code on external
# web content must hold no token and no secret. A scraper that gets compromised by
# a hostile page could otherwise use GH_TOKEN (issues: write) or production keys.
_TOKEN_RE = re.compile(r"github\.token|secrets\.|GH_TOKEN|GITHUB_TOKEN|GITHUB_PAT", re.IGNORECASE)


def _main_py_steps(root, workflow: str):
    data = yaml.safe_load((root / ".github" / "workflows" / workflow).read_text(encoding="utf-8"))
    for job_name, job in (data.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            if re.search(r"python3?\s+(\.\./)?main\.py", str(step.get("run", ""))):
                yield data, job_name, job, step


def test_source_diagnose_main_py_step_has_no_token(root):
    found = list(_main_py_steps(root, "source-diagnose.yml"))
    assert found, "source-diagnose.yml no longer has a step that runs main.py (test would pass vacuously)"
    for data, job_name, job, step in found:
        scopes = {
            "workflow env": data.get("env"),
            f"job {job_name} env": job.get("env"),
            f"step {step.get('name')} env": step.get("env"),
            f"step {step.get('name')} with": step.get("with"),
        }
        for label, scope in scopes.items():
            assert not _TOKEN_RE.search(json.dumps(scope or {})), f"source-diagnose.yml {label} exposes a token or secret to main.py"
        # The job that runs scrapers may only read contents (no issues/actions write).
        perms = job.get("permissions") or {}
        assert set(perms) <= {"contents"} and perms.get("contents", "read") == "read", (
            f"source-diagnose.yml job {job_name} runs main.py with permissions {perms}"
        )
        # The checkout in that job must not persist a credential into .git/config either.
        for other in job.get("steps") or []:
            if str(other.get("uses", "")).startswith("actions/checkout"):
                assert (other.get("with") or {}).get("persist-credentials") is False, (
                    "checkout in the main.py job must set persist-credentials: false"
                )


def test_source_diagnose_has_no_schedule(root):
    data = yaml.safe_load((root / ".github" / "workflows" / "source-diagnose.yml").read_text(encoding="utf-8"))
    assert "schedule" not in _triggers(data), "picking targets belongs to source-diagnose-batch.yml only"
