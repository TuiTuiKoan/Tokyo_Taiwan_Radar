"""Structure of .github/workflows/url-intake.yml (spec url-intake, plan-critique-1 #8, #9).

The job that fetches an external page must hold no secret and no token; the job
that writes production data must only switch to apply for the repo owner.
"""
from __future__ import annotations

import json
import re

import pytest
import yaml

_TOKEN_RE = re.compile(r"github\.token|secrets\.|GH_TOKEN|GITHUB_TOKEN|GITHUB_PAT", re.IGNORECASE)
_OWNER_GATE = (
    "github.event.sender.login == github.repository_owner",
    "github.event.sender.type == 'User'",
    "'url-intake:approved'",
)


@pytest.fixture(scope="module")
def wf(root):
    return yaml.safe_load((root / ".github" / "workflows" / "url-intake.yml").read_text(encoding="utf-8"))


def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text))


def test_triggers_are_issue_labels_and_dispatch_only(wf):
    on = wf.get(True, wf.get("on"))
    assert set(on) == {"issues", "workflow_dispatch"}
    assert on["issues"]["types"] == ["labeled"]
    assert wf["permissions"] == {}


def test_fetch_job_has_no_token_and_no_secret(wf):
    job = wf["jobs"]["fetch"]
    assert job["permissions"] == {"contents": "read"}
    assert "environment" not in job
    assert not _TOKEN_RE.search(json.dumps(job)), "fetch job must not see any token or secret"
    checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["persist-credentials"] is False


def test_issue_body_only_reaches_python_through_env(wf):
    for job in wf["jobs"].values():
        for step in job["steps"]:
            assert "github.event.issue" not in str(step.get("run", "")), step.get("name")
            assert "inputs." not in str(step.get("run", "")), step.get("name")


def test_fetch_job_is_limited_to_intake_labels(wf):
    cond = _norm(wf["jobs"]["fetch"]["if"])
    assert "github.event.label.name == 'url-intake'" in cond
    for part in _OWNER_GATE:
        assert part in cond


def test_db_job_runs_in_production_from_the_default_branch(wf):
    job = wf["jobs"]["db"]
    assert job["environment"] == "production"
    assert job["needs"] == "fetch"
    assert job["permissions"] == {"contents": "read", "issues": "write"}
    checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["ref"] == "${{ github.event.repository.default_branch }}"


def test_apply_mode_requires_the_owner(wf):
    mode = _norm(wf["jobs"]["db"]["env"]["MODE"])
    for part in _OWNER_GATE:
        assert part in mode
    assert "inputs.apply && github.actor == github.repository_owner" in mode
    assert mode.endswith("&& 'apply' || 'preview' }}")


def test_secrets_only_in_the_db_step(wf):
    steps = wf["jobs"]["db"]["steps"]
    with_secrets = [s["name"] for s in steps if "secrets." in json.dumps(s)]
    assert with_secrets == ["Preview or apply"]
