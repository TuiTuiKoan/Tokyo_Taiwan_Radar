---
title: Japan Scope Gate Close-out
description: The scope gate shipped, the 22 reviewed non-Japan events were deactivated in production through a transactional RPC and verified, and the public pages for them now answer 404
ms.date: 2026-10-25
ms.topic: reference
keywords:
  - japan scope gate
  - scope cleanup
  - production data cleanup
  - event detail 404
  - campaign close-out
estimated_reading_time: 10
---

## Outcome

The Japan scope gate is delivered and the reviewed cleanup is done in production.

What is true now:

* The annotator emits a structured scope decision. A non-Japan finding becomes an
  admin report that a person confirms row by row. Nothing is deactivated
  automatically. Migration `098` (atomic confirm RPC) and migration `103`
  (transactional cleanup RPC) are applied in production.
* On 2026-10-23 the owner applied the digest-bound manifest with the RPC while the
  writers were paused and the 094 maintenance lock was held. 22 events were
  deactivated (`is_active = false`, `deactivated_by_pass = 'admin_manual'`). Read-back
  and a second check the next day both held, and no writer overwrote them.
* Migration `097` (retire the Connpass and Doorkeeper sources) was applied by the
  owner on 2026-10-25. It was found already written during the campaign and is
  independent of the scope gate.
* The detail pages of the 22 deactivated events answer HTTP 404 in production. The
  decision is made in `web/proxy.ts` before rendering, because
  `[locale]/loading.tsx` streams a 200 skeleton before any page or nested layout runs.
  Merged events answer 308 through the same path.

## Delivered commits

Each row is a pull request merged by rebase. The tip is the last commit of the
pull request on `origin/main`; the count is how many commits it carried.

| Commit (tip) | Change | Ancestor of `origin/main` |
|--------------|--------|---------------------------|
| `b19a08e9` | PR 359, 15 commits: scope decision contract, admin per-row confirm, migration 098, digest-bound cleanup manifest | yes |
| `52d7d649` | PR 405, 3 commits: Phase 6b plan and live facts | yes |
| `e26cd570` | PR 413: `apply_scope_cleanup` RPC, migration 103 | yes |
| `e069f2b9` | PR 414: cleanup CLI v2 that applies through the RPC | yes |
| `0ef149ea` | PR 418: runbook and events writer inventory | yes |
| `07674bce` | PR 428: execution record of the apply and runbook fixes | yes |
| `706d2c8c` | PR 434: post-apply verification record | yes |
| `1a7ffb34` | PR 435, 2 commits: event detail layout guard (superseded, see Correction) | yes |
| `77d9a647` | PR 437: migration 097 marked applied | yes |
| `a05c8168` | PR 438: 404 and 308 for event detail from `web/proxy.ts` | yes |
| `fc3416d6` | PR 439: record the 404 fix in the spec | yes |
| `ed2b0e9a` | PR 447: runtime canary marked not run | yes |
| `bff0444b` | PR 456: Wave 2 items point at issue 455 | yes |

## Verification

| Check | Result | Evidence |
|-------|--------|----------|
| Manifest apply of 22 events | PASS | `applied_count = 22`; the CLI read-back and a Dashboard query agreed; active events 2406 to 2384 |
| Apply was not overwritten by later writers | PASS | A day later every one of the 22 still had `is_active = false` and the `updated_at` of the apply moment; the active count differed from 2384 only by events created after the apply |
| Writers paused, lock held, writers restored | PASS | 16 workflows paused and the same 43 re-enabled, launchd job unloaded and reloaded, 094 lock acquired and released |
| Rollback path prepared | PASS | Rollback SQL prepared and digested before the apply; not used |
| Migration 097 read-back | PASS | `sources_active 0`, `doorkeeper_active 0`, `doorkeeper_retired 5`, `research_pending 0` |
| Detail pages of the 22 events in production | PASS | All 22 answered 404, an unknown id answered 404, three active events from the home page answered 200 |
| Proxy gate behaviour | PASS | `next build` and `next start` against a mock PostgREST: inactive and unknown ids 404, merged id 308, active id 200, an RSC request 404; 7 unit tests |
| Merged event 308 in production | NOT TESTED | No merged id was available in production. Covered by the mock run and unit tests; residual risk is a production-only difference |
| Runtime canary of the deployed annotator on three events | NOT TESTED | Decided not to run on 2026-10-25: the next day's scheduled run on the new code and the cleanup verification cover its purpose, and running it would write production data or spend on the model API |
| PostgREST response to `40001` and timeouts from the RPC | NOT TESTED | No test exists for it; the production apply did not meet either case |
| Session contention at the close-out audit | NOT TESTED | The audit script covers Copilot CLI sessions only; see Worktree disposition |

## Correction and supersession

One claim was wrong and was corrected.

PR 435 added `events/[id]/layout.tsx` and described it as settling 404 and 308 before
`loading.tsx` streams. It did not. `app/[locale]/loading.tsx` sits above that layout,
so the status was already 200 when the layout ran, and production still answered 200
for the 22 pages. The author had verified only that `next build` passed and had not
looked at a status code. `a05c8168` (PR 438) moved the decision to `web/proxy.ts`,
removed the layout, and was verified against production. The lesson recorded here:
status codes are checked with `next start` or `curl`, never inferred from a build.

Two statements in the spec were overtaken and updated in PR 439: the runbook's
acceptance criterion for the public pages (it expected a 200 page with `noindex`) and
the note that guessed the cause of that 200.

## Known risks

* A first Dashboard check after the apply once returned zero marked rows for a query
  that later returned 22. The rows were verified individually and had not changed;
  the cause of the zero was not found. It is recorded in `notes.md`.
* `anon` and `authenticated` hold Supabase's default table privileges on `events`,
  including `TRUNCATE`, and rely on row level security. Judged low risk. No issue was
  opened for it.
* The detail page now costs one extra single-row query in `web/proxy.ts` per request.
  A lookup failure falls through to `page.tsx`, which keeps its own checks.
* `scraper.yml` fails every day at its last step (`Fail on LLM step errors`) while the
  write steps succeed. It predates this campaign and is tracked in issue 403.
* The close-out audit script reported `HOLD` for reasons the owner reviewed on
  2026-10-25 and accepted as known and handed over: four unchecked boxes in `tasks.md`
  (Wave 2, moved to issue 455); open issues whose title or body names the slug
  (455, 403, 436, 426, 444) but which are not tracked by the spec label; and three
  commits in the full range whose added lines contain the scan words only as prose in
  the close-out tooling's own documentation (`717b97e4`, `6acae937`, `8f09543d`). The
  full range holds 333 commits from other campaigns that no segment covers.

## Deferred work

* Wave 2, four evaluations that were deliberately left out: issue 455.
* Documentation gaps and the `scraper.yml` LLM-step failure: issue 403.
* Maintenance-lock coverage check for the shared Core files: issue 436.

## Spec disposition

`archive` for `docs/specs/active/japan-scope-gate/`, because every milestone in its
`tasks.md` is done or decided (the runtime canary was decided not to run) and the
only open items left are tracked as issues. The directory is moved in the commit
that backfills the worktree disposition.

## Worktree disposition

`remove`, decided at 2026-10-25T07:14:54Z (the time the recovery capsule was written,
after the owner reviewed the close-out audit result and confirmed the items it held on).
The owner removed the worktree from a terminal outside it with `git worktree remove` on
the registered path, without `--force`, deleted the branch with `git branch -d`, without
`-D`, and reconciled the `.git/info/exclude` block as a whole. This section is written
after that removal; it is merged only once the removal has happened.

| Freshness value | Re-observed at 2026-10-25T07:14:54Z (immediately before the decision) |
|-----------------|--------------------------|
| branch tip | `eb88c9c085d347b889c4d7dfc5511d72e01ea053`, the commit that put this record on `origin/main` |
| ahead of `origin/main` | `0` |
| behind `origin/main` | `0` |
| dirty count | `0` |
| ignored artifact set | `28` entries, classified under Ignored artifacts and handling |
| path identity | `divergent`, directory `ttr-japan-scope-gate-worktree`, branch `docs/japan-scope-gate-closeout` |

The audit script held at `HOLD` and exited 10. The owner reviewed each held item on
2026-10-25 and accepted it as known and handed over; they are listed under Known risks.
Session contention was re-observed with `lsof -a -d cwd` on the physical path: the only
processes with that directory as their working directory were this campaign's own
Claude Code session, its terminal shell, and child processes of both. The owner
confirmed no other Claude Code, Codex or VS Code window used the worktree. The script
itself covers Copilot CLI sessions only.

The recovery capsule is kept outside the repository at
`~/.ai-notes/ttr/capsules/2026-10-25-japan-scope-gate.md`.

## Ignored artifacts and handling

Files below were copied to the owner's local notes directory
(`~/.ai-notes/ttr/japan-scope-gate/worktree-tmp/`) and each copy was checked against
the digest before the worktree is removed.

| Artifact | Handling | SHA-256 |
|----------|----------|---------|
| `tmp/_scope_evidence_probe.json` | `exported` | `bcfb4165bbe73d065fcbc20933498032248f43b1d87d7eeb0167fb443e6d99d5` |
| `tmp/_scope_evidence_probe.py` | `exported` | `8566bef954a8b5342e8758f2c102172f7485dcb1f999ebcb2f7b8ab2696e3e88` |
| `tmp/_scope_preflight_v31.py` | `exported` | `fe17201c1fd539c4d5dcaa2ac268e0ec800c9ff7501a57411a41b7ab41273e13` |
| `tmp/phase0_5_annotator_console.txt` | `exported` | `d51609db97ed0f4423f8e4ff7478afaa8ed48fc3aae3dc4986b70b6fc1b91a15` |
| `tmp/phase0_sitecustomize/sitecustomize.py` | `exported` | `94f2e2f192407e255f390adf974b12238d9da258c14d735ad86aa292eb95eb4d` |
| `tmp/phase2-precleanup.patch` | `exported` | `b0b3236e49e0fbe9e57e187ac3381ffc8ad99d683ac7d2457b17a0317219cb87` |
| `tmp/phase3-precleanup.patch` | `exported` | `fae0c9cba4e9411c6868156cbb3f28a3d3513836f383749ba9245708882dfd47` |
| `tmp/scope_preflight_v31_output.json` | `exported` | `2db99b13d6ccb02e6c269be37c17255c23d7ef6aba61a5454c29c7122267f8ff` |
| `tmp/update_scope_i18n.py` | `exported` | `da39ccbecc2ce625d41963144eaceb778d114f65ca86a2cecb26c02267e5b1d0` |
| `scraper/auto_scraper/runs/42/meta.json` | `exported` | `848c4bf1c76a8755c41518c897def2cbcbc6ef4a3b03fe378031c569ac008896` |
| `scraper/auto_scraper/runs/42/prompt.txt` | `exported` | `3558d0b80840086b7e61ff5e8e59ee84ac0c6e36ae69ca2c070c8a7687b72f30` |
| `scraper/auto_scraper/runs/42/sample.html` | `exported` | `b633a587c652d02386c4f16f8c6f6aab7352d97f16367c3c40576214372dd628` |
| `tmp/phase0_sitecustomize/__pycache__/` | `disposable` | not hashed; compiled cache of the file above |
| `.copilot-tracking/pr/` | `disposable` | not hashed; legacy Copilot scratch, never committed |
| `.pytest_cache/`, `scraper/.pytest_cache/`, every `__pycache__/` | `disposable` | not hashed; regenerated by the test runs |
| `web/.next/`, `web/node_modules/`, `web/tsconfig.tsbuildinfo`, `web/next-env.d.ts` | `disposable` | not hashed; regenerated by install and build |
| `web/lib/specs/system-map.json` | `disposable` | not hashed; regenerated by the specs snapshot script |

## Evidence anchors

None. This campaign ran in Claude Code sessions, and the telemetry anchor generator
reads Copilot chat transcripts, so no anchor or ledger was produced.
