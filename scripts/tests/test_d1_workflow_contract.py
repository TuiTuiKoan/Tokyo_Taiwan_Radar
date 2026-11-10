"""Issue #633: lock the D1 evidence-factory contract so a rewrite cannot quietly undo it.

PR #600 rewrote ``source-diagnose.yml`` and removed the ``report`` job that #571
had added. The production-log excerpts disappeared from every diagnosis comment
and nothing noticed for a day (#608); #620 restored them. That PR changed only a
workflow file, and no CI job ran on it at all — its head commit had three checks
(Vercel preview comments, auto-merge skipped, gitleaks).

These assertions are structural on purpose: they describe what #620 shipped, not
how it is written, so ordinary edits stay free while the pieces the heartbeat
depends on cannot be dropped without a red test.

Contract:
- ``source-diagnose.yml`` keeps the two-job split. Only ``report`` may hold
  ``actions: read`` / ``issues: write``; ``diagnose`` runs scraper code against
  external sites and must hold neither.
- ``report`` must still call ``scripts/ci/prod_log_excerpt.py`` — the script
  #600 left orphaned in the tree.
- ``source-diagnose.yml`` must not schedule itself: picking targets belongs to
  ``source-diagnose-batch.yml`` (two schedulers diagnosed ten issues in one day
  on 2026-11-09).
- The E6 chain is Daily Scraper -> Zero-output Recovery -> Source Diagnose
  Batch, each with a ``guard`` job that skips a duplicate round and a fallback
  ``schedule`` so a missing event cannot stop the chain forever.
"""
from __future__ import annotations

import json

import pytest
import yaml

DIAGNOSE = "source-diagnose.yml"
RECOVERY = "zero-output-recovery.yml"
BATCH = "source-diagnose-batch.yml"

# Each downstream workflow and the workflow whose completion must trigger it.
CHAIN = {RECOVERY: "Daily Scraper", BATCH: "Zero-output Recovery"}


def _workflow(root, name: str) -> dict:
    return yaml.safe_load((root / ".github" / "workflows" / name).read_text(encoding="utf-8"))


def _triggers(data: dict) -> dict:
    # PyYAML reads the bare key `on` as the boolean True.
    on = data.get(True, data.get("on"))
    if isinstance(on, str):
        return {on: None}
    if isinstance(on, list):
        return dict.fromkeys(on)
    return dict(on or {})


def _jobs(data: dict) -> dict:
    return data.get("jobs") or {}


def _job(root, workflow: str, name: str) -> dict:
    jobs = _jobs(_workflow(root, workflow))
    assert name in jobs, f"{workflow} has no {name!r} job (see test_source_diagnose_keeps_both_jobs)"
    return jobs[name]


def _permissions(job: dict) -> dict:
    perms = job.get("permissions")
    return perms if isinstance(perms, dict) else {}


def test_source_diagnose_keeps_both_jobs(root):
    jobs = _jobs(_workflow(root, DIAGNOSE))
    assert "diagnose" in jobs, "the dry-run job is gone"
    assert "report" in jobs, (
        "the report job is gone; this is the #600 regression that removed "
        "production log excerpts from every diagnosis comment (#608)"
    )


@pytest.mark.parametrize("scope", ["actions", "issues"])
def test_report_job_can_read_actions_and_write_issues(root, scope):
    needed = {"actions": "read", "issues": "write"}[scope]
    perms = _permissions(_job(root, DIAGNOSE, "report"))
    assert perms.get(scope) == needed, (
        f"report needs {scope}: {needed} — reading scraper.yml run logs and posting "
        "the diagnosis both happen in this job"
    )


@pytest.mark.parametrize("scope", ["actions", "issues"])
def test_diagnose_job_holds_no_actions_or_issues_scope(root, scope):
    perms = _permissions(_job(root, DIAGNOSE, "diagnose"))
    assert scope not in perms, (
        f"diagnose must not hold {scope}: it runs scraper code against untrusted "
        "external sites, so it may only read the repository"
    )


def test_report_job_runs_prod_log_excerpt(root):
    report = _job(root, DIAGNOSE, "report")
    script = json.dumps(report.get("steps") or [], ensure_ascii=False)
    assert "scripts/ci/prod_log_excerpt.py" in script, (
        "report no longer calls prod_log_excerpt.py; the script would sit in the "
        "tree unused, as it did between #600 and #620"
    )


def test_source_diagnose_does_not_schedule_itself(root):
    triggers = _triggers(_workflow(root, DIAGNOSE))
    assert "schedule" not in triggers, (
        "source-diagnose.yml must not pick its own targets on a schedule; "
        "source-diagnose-batch.yml is the single entry point"
    )


@pytest.mark.parametrize("name", sorted(CHAIN))
def test_chain_is_triggered_by_the_upstream_workflow(root, name):
    triggers = _triggers(_workflow(root, name))
    workflow_run = triggers.get("workflow_run") or {}
    assert workflow_run.get("workflows") == [CHAIN[name]], (
        f"{name} must run when {CHAIN[name]!r} completes, so the daily round keeps "
        "its order instead of depending on cron delays (#614)"
    )
    assert "completed" in (workflow_run.get("types") or []), f"{name} must react to completion"


@pytest.mark.parametrize("name", sorted(CHAIN))
def test_chain_keeps_a_fallback_schedule(root, name):
    triggers = _triggers(_workflow(root, name))
    assert triggers.get("schedule"), (
        f"{name} must keep a fallback schedule: a workflow_run event that never "
        "arrives would otherwise stop the chain indefinitely"
    )


@pytest.mark.parametrize("name", sorted(CHAIN))
def test_chain_guards_against_a_duplicate_round(root, name):
    jobs = _jobs(_workflow(root, name))
    assert "guard" in jobs, (
        f"{name} has both an event trigger and a fallback schedule, so it needs the "
        "guard job; without it both fire and the day's work is done twice"
    )
    guard = jobs["guard"]
    assert _permissions(guard).get("actions") == "read", "guard reads this workflow's earlier runs"
    assert "skip" in (guard.get("outputs") or {}), "guard must publish a skip output"
    for job_name, job in jobs.items():
        if job_name == "guard":
            continue
        assert "needs.guard.outputs.skip" in str(job.get("if", "")), (
            f"{name}:{job_name} must be gated on the guard's skip output"
        )
