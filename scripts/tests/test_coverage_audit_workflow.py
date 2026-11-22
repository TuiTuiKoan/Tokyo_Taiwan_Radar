"""Structure of the coverage-audit jobs in scraper-quality.yml (spec coverage-audit Phase B).

plan-critique-2 PB1: the job holding the database key never touches external
content; the job that reads PR TIMES holds no secret and gets a token only in
its final comment step.
"""
from __future__ import annotations

import json
import re

import pytest
import yaml

_SECRET_RE = re.compile(r"secrets\.", re.IGNORECASE)
_TOKEN_RE = re.compile(r"github\.token|secrets\.|GH_TOKEN|GITHUB_TOKEN|GITHUB_PAT", re.IGNORECASE)
_RUN_ONLY_ON = "github.event_name != 'pull_request' && (github.event_name == 'schedule' || github.event_name == 'workflow_dispatch')"


@pytest.fixture(scope="module")
def wf(root):
    return yaml.safe_load((root / ".github" / "workflows" / "scraper-quality.yml").read_text(encoding="utf-8"))


def test_coverage_jobs_never_run_on_push_or_pull_request(wf):
    for name in ("coverage-db", "coverage-probe"):
        assert wf["jobs"][name]["if"] == _RUN_ONLY_ON


def test_db_job_is_select_only_and_never_fetches_external_content(wf):
    job = wf["jobs"]["coverage-db"]
    assert job["environment"] == "production"
    assert job["permissions"] == {"contents": "read"}
    runs = " ".join(step.get("run", "") for step in job["steps"])
    assert "coverage_audit.py db" in runs
    assert "probe" not in runs


def test_probe_job_has_no_secrets_and_token_only_in_comment_step(wf):
    job = wf["jobs"]["coverage-probe"]
    assert job["needs"] == "coverage-db"
    assert "environment" not in job
    assert job["permissions"] == {"contents": "read", "issues": "write"}
    assert not _SECRET_RE.search(json.dumps(job))
    for step in job["steps"][:-1]:
        assert not _TOKEN_RE.search(json.dumps(step)), step
    checkout = job["steps"][0]
    assert checkout["with"]["persist-credentials"] is False
    last = job["steps"][-1]
    assert last["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert "--label coverage-audit --state open" in last["run"]


def test_probe_installs_only_requests_and_bs4(wf):
    install = next(s for s in wf["jobs"]["coverage-probe"]["steps"] if s.get("name") == "Install probe dependencies")
    assert "requests|beautifulsoup4" in install["run"]
    assert "pip install -r scraper/requirements.txt" not in install["run"]


def test_known_artifact_is_short_lived(wf):
    upload = next(s for s in wf["jobs"]["coverage-db"]["steps"] if s.get("uses", "").startswith("actions/upload-artifact"))
    assert upload["with"]["retention-days"] == 1
    assert upload["with"]["name"] == "coverage-known"


def test_existing_jobs_are_untouched(wf):
    assert wf["jobs"]["unit-tests"]["if"] == "github.event_name == 'pull_request'"
    assert wf["jobs"]["report"]["if"] == "github.event_name != 'pull_request'"
    assert "needs" not in wf["jobs"]["report"]


def test_failure_notify_watches_scraper_quality(root):
    notify = yaml.safe_load((root / ".github" / "workflows" / "workflow-failure-notify.yml").read_text(encoding="utf-8"))
    assert "Scraper Quality Report" in notify[True]["workflow_run"]["workflows"]
