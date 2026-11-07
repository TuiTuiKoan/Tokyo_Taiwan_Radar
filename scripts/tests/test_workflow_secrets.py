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
