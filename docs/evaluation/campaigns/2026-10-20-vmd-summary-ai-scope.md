---
title: V-M-D Summary AI Scope Close-out
description: Records that the V-M-D summaries now state the no-self-push rule and no longer list an ai scope, and what proves it
ms.date: 2026-10-20
ms.topic: reference
keywords:
  - campaign close-out
  - validate-merge-deploy
  - worktree disposition
estimated_reading_time: 3
---

## Outcome

The one-line summaries of Validate, Merge & Deploy in `AGENTS.md`, its agent file and its Claude wrapper now say it provides the user-run push command and verifies the deploy afterwards, instead of pushing itself. The `ai` scope is dropped from the commit scope list in `.github/instructions/git.instructions.md` and from the parked follow-ups note. The change is on `origin/main`.

## Delivered commits

| Commit | Change | Ancestor of `origin/main` |
|--------|--------|---------------------------|
| `0badac5b` (2026-10-20, "docs(agents): align V-M-D summaries with the no-self-push rule and drop the ai scope", campaign vmd-summary-ai-scope) | Five one-line edits in five files. Rebased from the earlier `db26f6ef` before the push; that pre-rebase SHA is not an ancestor and is listed for traceability only | yes |

## Verification

| Check | Result | Evidence |
|-------|--------|----------|
| Delivered commit is an ancestor of `origin/main` | PASS | `git merge-base --is-ancestor` printed `ancestor=yes` at 2026-10-20T12:50Z |
| Branch holds no unique commit | PASS | `git cherry origin/main feat/vmd-summary-ai-scope` printed nothing; ahead 0, behind 0 |
| Added lines carry no unfinished-work marker | PASS | Audit `range_todo=0` over `d1bf30de..0badac5b` ("docs(agents): record the proxy-rewritten lockfile incident in engineer history", 2026-10-20) |
| Open issues naming the slug | PASS | Audit `open_issues=0`, excluding label `daily-review` |
| Generated adapters match sources | NOT TESTED | `sync_ai_adapters.py --check` was not rerun for this record; the delivered commit touched a generated wrapper and its source together, so drift is unlikely but unproven |
| Session contention | NOT TESTED | Audit reported `SOLE_OWNER (CLI-scope)`, but live `lsof` showed shells and a `claude` process with this worktree as cwd; their ownership is not confirmed (see Known risks) |

## Correction and supersession

None.

## Known risks

* Spec sources 1 and 2 of the unhandled-work audit were `not_checked` because no spec directory exists for this slug. They are recorded as cleared on the user's confirmation at 2026-10-20 (relayed by the coordinating session after the user saw the Phase A output), not on a read of any file.
* Session contention is CLI-scoped. Claude Code and VS Code sessions are not detectable by the audit. At 2026-10-20T12:56Z `lsof` still listed processes holding this worktree as cwd; the user plans to close the remaining terminal tab at retirement. Retirement stays blocked until a fresh `lsof -a -d cwd` shows no holder.

## Deferred work

None.

## Spec disposition

`none` for `docs/specs/active/vmd-summary-ai-scope/`, because the campaign never had a spec directory, as confirmed by the user.

## Worktree disposition

`pending`. No decision to retire has been taken; this block is backfilled after the decision.

| Freshness value | Observed at 2026-10-20T12:50:18Z (Phase A, not a decision) |
|-----------------|--------------------------|
| branch tip | `0badac5b640e73dd48dd23239110aa6f3e29f03e` |
| ahead of `origin/main` | `0` |
| behind `origin/main` | `0` |
| dirty count | `0` |
| ignored artifact set | none |
| path identity | `canonical`, directory `ttr-vmd-summary-ai-scope-worktree`, branch `feat/vmd-summary-ai-scope` |

## Ignored artifacts and handling

None. The worktree held no ignored files.

## Evidence anchors

None. The anchor generator reads Copilot CLI transcripts only, and this campaign was carried out in Claude Code sessions, so no telemetry anchor or ledger could be produced.
