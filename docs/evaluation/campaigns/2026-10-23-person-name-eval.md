---
title: Person Name Eval Close-out
description: Records that the katakana person-name extraction fix and the eval stage 3 person-name enrichment are on origin/main, and what the open follow-up issues are
ms.date: 2026-10-23
ms.topic: reference
keywords:
  - campaign close-out
  - person name
  - eval stage 3
  - worktree disposition
estimated_reading_time: 4
---

## Outcome

Katakana person-name extraction keeps ファン as a surname, and the eval stage 3 pass `enrich_person_names` with title sync is on `origin/main`. The ja.wikipedia fallback no longer matches non-katakana stage names. The worktree `ttr-person-name-eval-worktree` holds no unique commit and no uncommitted change. The remaining work for person names (generated `person_key`, DB-first lookup, stage 3 CI decision) is tracked by issues #392 and #393, not by this campaign.

## Delivered commits

| Commit | Change | Ancestor of `origin/main` |
|--------|--------|---------------------------|
| `f93a87c0` (2026-10-23, "fix(scraper): stop ja.wikipedia fallback matching non-katakana stage names") | Stage-name fallback restricted to katakana matches | yes |
| `776859ce` (2026-10-23, "feat(scraper): add eval stage 3 with enrich_person_names and title sync") | Adds eval stage 3 with `enrich_person_names` and title sync | yes |
| `89a93fe0` (2026-10-23, "fix(scraper): keep ファン as a surname in katakana name extraction") | Katakana name extraction keeps ファン as a surname | yes |

Other commits on `feat/person-name-eval` (migration 100 and 101 work, Playwright unpin, and related docs) belong to other campaigns and are not counted here.

## Verification

| Check | Result | Evidence |
|-------|--------|----------|
| Delivered commits are ancestors of `origin/main` | PASS | `git merge-base --is-ancestor` printed `yes` for `f93a87c0`, `776859ce`, `89a93fe0` at 2026-10-23T03:30 JST, after `git fetch origin main` |
| Branch holds no unique commit | PASS | `git rev-list --count main..feat/person-name-eval` = 0 at 2026-10-23T02:38 JST |
| Working tree clean | PASS | `git status --porcelain --untracked-files=all` empty; no stash, no rebase, merge, cherry-pick or revert in progress |
| Open PRs for the branch | PASS | `gh pr list --head feat/person-name-eval --state all` returned no entries |
| Spec sources 1 and 2 (`tasks.md`, Deferred) | NOT TESTED | No `docs/specs/active/<slug>/` or `archive/` directory resolves for this slug; the audit reported `not_checked`. Risk accepted, see Known risks |
| Open issues naming the slug | NOT TESTED (attribution open) | `gh issue list --search "person-name-eval"` returned #392 and #393. Both are judged follow-ups of other tracks, see Known risks |
| Campaign-closeout audit verdict | `HOLD:unhandled_work` (script output at 2026-10-23T04:20Z UTC) | Driven only by the two open issues above; also `UNDETERMINED` for `self_session_unknown` |
| Session contention | NOT TESTED (CLI scope only) | Latest `lsof -a -d cwd` before this record showed no holder; the audit cannot exclude its own session. See Known risks |

## Correction and supersession

None.

## Known risks

* Open issues #392 (`spec:people-ground-truth`) and #393 (no spec label) match the slug text. #393 is the eval stage 3 follow-up that came from `776859ce`. Under the closer contract these are recorded here as other-track work, with the attribution accepted by the user at Phase B. The audit script still reports `HOLD:unhandled_work` on this basis; the attribution is a user decision, not a script result.
* Spec disposition sources were `not_checked`, not zero. No spec directory exists on `main` for this slug. The people-ground-truth spec lives on its own branch and is not part of this campaign.
* Session contention is CLI-scoped. Claude Code and VS Code sessions are not detectable. The audit could not exclude its own session. The user confirmation at Phase B is the backstop.
* The branch `feat/person-name-eval` has no upstream. It is behind `origin/main` and must be rebased before V-M-D pushes this record. The local `main` also holds one unpushed commit (`6294a6cd`, plan-critic Codex read-only note) that is not part of this campaign; removal must wait until that is pushed.
* `scraper/.env` in this worktree is a symlink to the main repo's `scraper/.env`. Removing the worktree removes only the link. The digest of the target was not computed because reading env files is blocked by the guard.

## Deferred work

* Issue #393: eval stage 3 follow-ups (concurrency limit, whether to run in CI, standard-name application check). Tracked as an open issue without a spec label.
* Issue #392: DB-first person-name lookup, tracked under `spec:people-ground-truth`.

## Spec disposition

`none` for `docs/specs/active/person-name-eval/`, because the campaign never had a spec directory on `main`. The people-ground-truth spec is tracked separately under issue #392.

## Worktree disposition

`pending`. The decision timestamp is not recorded yet. Removal waits until this record is on `origin/main`, `main` matches `origin/main`, and the six freshness values are re-observed in the recovery capsule outside the worktree.

## Ignored artifacts and handling

* `scraper/.env`: `duplicated`. A symlink to the main repo's `scraper/.env`, which survives removal. Digest not computed (env reads are blocked by the guard). After removal, verify the target still exists.
* `scraper/.pytest_cache/` and `scraper/**/__pycache__/*.pyc`: `disposable`. Regenerated by pytest and python. No digest, because they are regenerable.

## Evidence anchors

None. The anchor generator reads Copilot CLI transcripts only, and this campaign ran in Claude Code sessions, so no telemetry anchor or ledger could be produced.
