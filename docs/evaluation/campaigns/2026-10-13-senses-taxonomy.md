---
title: Senses Taxonomy Close-out
description: Six commits that narrowed the senses category, moved category definitions to taxonomy.md, and removed the senses fallback are in production; this record proves the delivery and lists the follow-up work no specification tracks
ms.date: 2026-10-13
ms.topic: reference
keywords:
  - senses taxonomy
  - category definitions
  - annotator
  - campaign close-out
estimated_reading_time: 9
---

## Outcome

The senses taxonomy campaign is delivered and deployed. Six commits sit on
`origin/main`, and the Vercel Production deployment that followed the push
reported success.

What is true in production now:

* `scraper/taxonomy.md` is the single source of category definitions. The
  annotator builds the category section of its system prompt from
  `VALID_CATEGORIES` plus the `PROMPT` block of that file, and a test keeps the
  two in agreement. The old list omitted `market`; it is now exposed.
* `senses` is a narrow, concept-level category: identity as a concept,
  aesthetics, locality, folk culture as a subject of study, and vernacular
  culture. It is no longer a fallback. Political identity history belongs to
  `history`, and contemporary society and elections belong to `geopolitics`.
* An event whose category list comes back empty stays empty and is queued as a
  pending `wrongCategory` event report for admin review. The prompt no longer
  invites an empty list; empty results are handled in code only.
* The unambiguous `event_form` leak `performance` is mapped to
  `performing_arts`. `tour` is deliberately not mapped.
* Keyword injection covers `history` (湾生, 国民党, 二二八, 白色テロ, 戒厳) and
  `geopolitics` (総統選, 選挙), and the classifier maps art keywords to `art`.
  The `senses` defaults were removed from the Fukuoka Now and Taiwan Bunkasai
  scrapers and from the researcher.
* The Japanese, Traditional Chinese, and English category descriptions for
  `senses` and `geopolitics` match the new definitions, and the `llms.txt`
  geopolitics label gained its missing Japanese suffix.

This change affects newly annotated events only. Existing events keep the
categories they already have; see Deferred work.

| Field | Value |
|-------|-------|
| Base (`origin/main` before the push) | `6b404ea3a4b029cf9c157d9773442b40d7fee5a8` |
| Pushed head | `e17cf4d9f996fac6f28eb27c40040e0c96b5193e` |
| Commits in range | 6 |
| Files touched | 17 (470 insertions, 75 deletions) |
| Production deployment | Vercel Production, deployment `7025112098`, `success` |
| Pushed by | The repository owner, from their own terminal |

## Delivered commits

| Commit | Change | Ancestor of `origin/main` |
|--------|--------|---------------------------|
| `936ed076c3976b4a29416ca6ec9ae11e7d8379a8` | Moved category definitions to `taxonomy.md`, narrowed `senses`, removed the senses fallback, added keyword injection | yes |
| `25b28dfa50488431d5ad859a80a8cf3a6405ec87` | Rewrote the `senses` descriptions to match the new definition | yes |
| `146576184243082b226681f861789312dcb6e4b1` | Documented the removal of the senses fallback in skills | yes |
| `e9497dc04b2c071400aafd931f5f6408345575e0` | Stopped the prompt from inviting empty categories and aliased `performance` | yes |
| `d28d7f5f7d4b5afc092aca4fa3ec52ccf36427be` | Broadened the geopolitics description to society and politics | yes |
| `e17cf4d9f996fac6f28eb27c40040e0c96b5193e` | Recorded the `event_form` alias and empty-category lessons in skills | yes |

Each row was checked with `git merge-base --is-ancestor` against `origin/main`
during the close-out audit, and all six returned `ANCESTOR`.

The remote branch `origin/feat/senses-taxonomy` stopped at `8e70c515`, the
history from before the rebase. `git cherry origin/main
origin/feat/senses-taxonomy` marked all three of its commits (`a0884cb7`,
`b779cc23`, `8e70c515`) as `-`, so each has an equivalent patch on `origin/main`
and the branch holds no unique content.

## Verification

| Check | Result | Evidence |
|-------|--------|----------|
| All six commits are ancestors of `origin/main` | PASS | `merge-base --is-ancestor` returned `ANCESTOR` for each SHA at 2026-10-12T22:27Z |
| Taxonomy unit tests at the pushed head | PASS | `scraper/tests/test_taxonomy.py` ran 36 tests, 36 passed in 0.84 s, run by the close-out agent in the campaign worktree with no caches written |
| Dry-run effect of the new prompt on empty categories | PASS | On the same batch of 100 samples, events with an empty category fell from 28 to 11, as reported in the hand-off |
| Vercel Production deployment | PASS | Deployment `7025112098` reported `success` in the hand-off; the close-out agent did not re-query the Vercel API |
| Production smoke after deployment | PASS | Reported as passed in the hand-off; the checks themselves are not reproduced here |
| First scraper CI run after deployment | NOT TESTED | It has not run against the new prompt. The expected effect is an estimated 3 to 7 new pending `wrongCategory` reports, which is an estimate and not a measurement |
| Admin Reports display of the new pending reports | NOT TESTED | No new pending report existed to display when this record was written |
| OAuth, magic link, and Admin operations after login | NOT TESTED | The campaign changed no authentication or admin code; the web changes are limited to `web/messages/{en,ja,zh}.json` and `web/public/llms.txt`. The residual risk is a regression outside this diff that the campaign could not have introduced |
| Re-annotation of existing events | NOT TESTED | Not performed; see Deferred work item 1 |

## Correction and supersession

None.

## Known risks

* About 195 existing events still carry the old fallback `senses` label (77 from
  `ndl_opensearch`, 118 from other sources). This is a Tester estimate that
  excludes manually corrected events. Until they are re-annotated, those events
  appear under a category whose published description now means something
  narrower.
* `ndl_opensearch` is the largest source of empty categories. Its relevance
  filter is loose, so newly annotated records from that source will keep
  reaching the admin review queue in volume.
* The close-out audit could not rule out another session through detection.
  Contention detection covers Copilot CLI sessions only and could not exclude
  the auditing session because no session id was handed over. The verdict rests
  on the repository owner's confirmation recorded under Worktree disposition,
  not on a detected `SOLE_OWNER` result.
* No evidence anchor exists for this campaign, so the process telemetry of the
  sessions that produced it cannot be recomputed.

## Deferred work

No specification and no issue tracks any item below. This record is the only
tracking until the repository owner opens a specification or an issue for them.

1. **Re-annotate existing `senses` events.** About 195 events (77 from
   `ndl_opensearch`, 118 from other sources; a Tester estimate that excludes
   manually corrected events) still carry the old fallback label. Run a dry run
   first and show the before and after list to the repository owner. Do not use
   `--all`: `--limit` is not passed through to `annotate_pending_events`, and
   `--all` overwrites valid categories with `[]`.
2. **Tighten the `ndl_opensearch` relevance filter.** `_is_taiwan` in
   `scraper/sources/ndl_opensearch.py` accepts a record when either the title or
   the description contains a Taiwan keyword. It is currently the largest source
   of empty categories.
3. **Resolve the Dependabot findings.** GitHub reports 8 vulnerabilities (3
   high, 2 medium, 3 low), all in indirect dependencies recorded in
   `web/pnpm-lock.yaml`. Earlier work exists on branch `chore/deps-security`:
   4 commits ahead of and 85 commits behind `origin/main` when checked at
   2026-10-12T22:28Z. Nobody has checked whether `origin/main` already supersedes
   it.
4. **Remove the outdated Three-Location Sync wording.** The category definitions
   now live in `taxonomy.md`, but these locations still describe editing the
   `annotator.py` system prompt:
   * `.github/agents/scraper-expert.agent.md` line 108
   * `.github/agents/architect.agent.md` lines 520 to 523
   * `.github/prompts/add-category.prompt.md` lines 42 to 45
   * `.github/skills/agents/architect/SKILL.md` line 194
   * `.github/skills/agents/designer/SKILL.md` line 307
5. **Close the post-deployment verification gaps.** Observe the first scraper CI
   run after deployment and how Admin Reports displays the new pending reports.
   The OAuth, magic link, and post-login Admin checks stay NOT TESTED because
   nothing in this campaign touched that code.
6. **`tour` is not aliased on purpose.** An `event_form` value of `tour` leaking
   into `category` appears in roughly 1 of 100 events, and the word is
   ambiguous between tourism, a concert tour, and a guided tour. Revisit it only
   if the frequency rises.

## Spec disposition

`none` for `docs/specs/active/senses-taxonomy/`, because the campaign never had
a specification. The slug resolves under neither `docs/specs/active/` nor
`docs/specs/archive/`, none of the six commits touches `docs/specs/`, and the
repository owner confirmed at 2026-10-12T22:27Z (2026-10-13 07:27 JST) that no
specification directory exists for this campaign.

## Worktree disposition

`remove`, decided at `2026-10-12T22:39:21Z`. The worktree was removed without
`--force` at 2026-10-12T22:39:40Z, after the six values were re-observed and
found unchanged. The table at the end of this section holds the values observed
at the decision and replaces the earlier close-out audit observation
(2026-10-12T22:27:56Z).

Result of the retirement, observed 2026-10-12T22:38Z to 22:40Z:

* The record commit `6acae937667954af2dcd1a10e9c69b18397b1be8` had landed on
  `origin/main` before removal, and the recovery capsule was written outside the
  worktree first.
* An interactive shell opened at 2026-10-12T22:33:30Z held the worktree as its
  working directory. The repository owner reported at 2026-10-12T22:38Z
  (2026-10-13 07:38 JST) that it was their own push terminal and that it was
  closed. `lsof` showed no process in the worktree at 22:38:36Z and 22:39:40Z.
* The local branch `feat/senses-taxonomy` was deleted with `git branch -d`; it
  pointed at `6acae937667954af2dcd1a10e9c69b18397b1be8`.
* The remote branch `origin/feat/senses-taxonomy` was absent at 22:38:36Z. The
  repository owner deleted it from their own terminal after 22:34:26Z, when it
  still existed at `8e70c515`. The close-out agent did not delete it.
* The post-removal check reported the worktree unregistered, the branch deleted,
  the exclude entry removed, and the directory gone.

### Gates at the close-out audit

The audit script `scripts/campaign-closeout-audit.sh` was run against the
campaign worktree at 2026-10-12T22:28:02Z with base
`6b404ea3a4b029cf9c157d9773442b40d7fee5a8` and head
`e17cf4d9f996fac6f28eb27c40040e0c96b5193e`. It exited `20` with
`UNDETERMINED:spec_dir_unresolved,self_session_unknown`. Two inputs were
unknown, and the repository owner supplied both.

| Unhandled-work source | Script result | Final result |
|-----------------------|---------------|--------------|
| `tasks.md` unchecked items | `not_checked` | 0, by owner confirmation that no specification exists |
| Deferred section of `changes-log.md` and `proposal.md` | `not_checked` | 0, by the same confirmation |
| Legacy `.copilot-tracking/plans` | 0 | 0 |
| `TODO` or `FIXME` on lines added in the commit range | 0 | 0 |
| Open GitHub issues naming the slug | 0 | 0 |

Session contention was `UNDETERMINED` because the auditing session id was
unknown. Contention detection covers Copilot CLI sessions only; VS Code chat
sessions cannot be detected, so a detected `SOLE_OWNER` would still have been
CLI-scoped. The close-out agent also found nothing pointing at the worktree: no
Copilot session-state `workspace.yaml` naming the slug, no process holding a
file under the worktree, and no process command line naming it. Those checks are supporting
observations and not a clearance.

The repository owner replaced the detection with an explicit confirmation made
through an option prompt at 2026-10-12T22:27Z (2026-10-13 07:27 JST), after
reading the audit output:

* Confirmed that the senses-taxonomy campaign has no specification directory.
* Confirmed that no other session or VS Code window is using the senses-taxonomy
  worktree ("沒有其他 session 或 VS Code 視窗在使用 ttr-senses-taxonomy-worktree").
* Approved writing this record in the campaign worktree.

With those confirmations applied, no hard blocker remains and the worktree is a
retirement candidate. The script's own verdict stays `UNDETERMINED`; this
record does not rewrite it.

The branch state at the audit: the local branch `feat/senses-taxonomy` is an
ancestor of `origin/main`, and the remote branch `origin/feat/senses-taxonomy`
at `8e70c515b6e50a93ff0dab1ff25fcc63d5f0ed6a` still existed when this record
was written. The repository owner deletes it from their own terminal, because
the agent hook blocks remote ref deletion. Its deletion is a planned step, not
a completed one.

| Freshness value | Observed at the decision (2026-10-12T22:39:21Z) |
|-----------------|-------------------------------------------------|
| branch tip | `6acae937667954af2dcd1a10e9c69b18397b1be8` |
| ahead of `origin/main` | `0` |
| behind `origin/main` | `0` |
| dirty count | `0` |
| ignored artifact set | `11` |
| path identity | `canonical`, directory `ttr-senses-taxonomy-worktree`, branch `feat/senses-taxonomy` |

Stashes: 0. No rebase, merge, cherry-pick, or revert was in progress.

## Ignored artifacts and handling

All 11 ignored entries are build or cache output that a fresh install or build
regenerates, so none needs preserving. The worktree has no ignored file under
`tmp/`; its one file there, `tmp/gnews_streaming_ids.txt`, is tracked by Git.

| Artifact | Handling | SHA-256 |
|----------|----------|---------|
| `web/node_modules/` (about 803 MB) | `disposable` | not applicable (directory, restored by `pnpm install`) |
| `web/.next/` (about 260 MB) | `disposable` | not applicable (directory, rebuilt by `next build`) |
| `web/lib/specs/specs-snapshot.json` | `disposable` | `caf38b46014f8ca64b7da3a4c092b7ef3adf319d8cdd30fe66c8817e58abd7d2` |
| `web/lib/specs/system-map.json` | `disposable` | `ca5afccd4e340187c0f54c143826c4be87b9469259ff58c6eb67d2bd3c1c2da1` |
| `web/next-env.d.ts` | `disposable` | `1862ac4bbbc5192d4bf562161df66ea547ed3e67173100656ab606ae9797db2b` |
| `.pytest_cache/` | `disposable` | not applicable (directory) |
| `scraper/.pytest_cache/` | `disposable` | not applicable (directory) |
| `scraper/__pycache__/` | `disposable` | not applicable (directory) |
| `scraper/security/__pycache__/` | `disposable` | not applicable (directory) |
| `scraper/sources/__pycache__/` | `disposable` | not applicable (directory) |
| `scraper/tests/__pycache__/` | `disposable` | not applicable (directory) |

The two JSON files are generated by `web/scripts/build-specs-snapshot.ts` in the
`prebuild` step, and `next-env.d.ts` is written by Next.js. The directories
`web/node_modules/` and `web/.next/` were created when the validation cycle
built the web app.

## Evidence anchors

`not_checked`. The session id was not handed over, so no telemetry anchor and no
ledger were generated for this campaign. Three of the six commits carry a
Claude session trailer, which the close-out agent did not evaluate: the anchor
generator reads local transcripts only. When the transcript location and the
slice boundaries are known, one anchor per session slice can be added in a later
commit, listed separately and never summed.
