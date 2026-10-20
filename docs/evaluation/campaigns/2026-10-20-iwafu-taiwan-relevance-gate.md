---
title: iwafu Taiwan Relevance Gate Close-out
description: Two commits stopped non-Taiwan iwafu events after the site redesign and then removed a katakana false match; this record proves the delivery under different commit hashes, states what could not be checked, and records the worktree disposition
ms.date: 2026-10-20
ms.topic: reference
keywords:
  - campaign close-out
  - iwafu
  - taiwan relevance gate
  - rebase merge
  - worktree retirement
estimated_reading_time: 8
---

## Outcome

The iwafu-taiwan-relevance-gate campaign is delivered. Its two commits were
merged into `origin/main` by pull request 295 as a rebase merge, so the commits
on `main` carry different hashes from the ones on the campaign branch. Their
patches are identical, and the Vercel Production deployment of the final commit
on `main` reported `success`. The campaign changed the iwafu scraper, the
annotator, two test files, and the iwafu skill and history.
It wrote no migration. According to the iwafu history entry, 21 events were set
to inactive in production by hand as part of the incident response; that write
happened outside the commits and was not observed by the close-out agent.

What is true now:

* The iwafu detail page title comes from `og:title`, then `h1`, then `h2`, then
  the card, and never from a user-interface string such as the label
  `詳細を見る`. The card title no longer depends on line order.
* The body text is read from `main`, `#app-content`, or `[role=main]`, with
  `og:description` and then the card summary as fallbacks. The global-tour
  pattern also checks `og:description`.
* Phase 2 is restored: a detail page must mention Taiwan. The bare katakana
  `タイワン` is no longer a match, because it matched `タイワンザル`, the
  invasive macaque, and let a stage play through.
* A run in which one title makes up half the results or more (five or more
  events) is dropped as a whole and logged as an error.
* The annotator returns a structured `taiwan_relevance` verdict. A confident
  `is_relevant=false` (confidence at least 0.8) sets `is_active=false`, except
  for human-reviewed and user-submitted events, and suppresses sub-events.
* `.github/skills/sources/iwafu/SKILL.md` and `history.md` record the gates, the
  incident, and the lessons.

| Field | Value |
|-------|-------|
| Campaign base (`origin/main` before the replayed commits) | `9cb1e11e5cfd8e0c148be3c385c4be048eab78ff` |
| Pull request | 295, merged 2026-10-12T18:18:38Z, rebase merge, merge result `7f8e75c9030badc96d10dd52f1f0023083e606be` |
| Range on `main` | `9cb1e11e5cfd8e0c148be3c385c4be048eab78ff..7f8e75c9030badc96d10dd52f1f0023083e606be`, 2 commits, linear |
| Branch tip | `294d3a509e4223e9071b4a675d9caff01e00c3f7`, equal to `origin/fix/iwafu-taiwan-relevance-gate` (`git ls-remote`, 2026-10-20T03:55Z) |
| Production deployment | `7021409971` for `7f8e75c9`, created 2026-10-12T19:04:12Z, latest status `success` |
| Push approval | Not observed by the close-out agent |

## Delivered commits

Both campaign commits were written by a cloud Claude session and sit on the
branch with hashes that differ from their copies on `main`.

| On the branch | On `main` | Change | Proof of delivery |
|---------------|-----------|--------|-------------------|
| `28999b391cf0b11506dcb7503569b101c981f86e` | `116203a3467c86951e3b47d4571ef3c5b51776da` | 2026-10-12 19:37 +0900. `fix(scraper): stop non-Taiwan iwafu events after layout change`. 6 files, 414 insertions, 23 deletions: the iwafu scraper, the annotator gate, two test files, and the iwafu skill and history | patch-id `0b3bb2d7c54a…` on both; `main` copy is an ancestor of `origin/main` |
| `294d3a509e4223e9071b4a675d9caff01e00c3f7` | `7f8e75c9030badc96d10dd52f1f0023083e606be` | 2026-10-13 01:42 +0900. `fix(scraper): drop katakana タイワン from iwafu Phase 2 Taiwan match`. 3 files, 15 insertions, 1 deletion: the Phase 2 pattern, one regression test, and the history follow-up | patch-id `fd10e73c49f9…` on both; `main` copy is an ancestor of `origin/main` |

The branch hashes are not ancestors of `origin/main`. That is why the audit
script reported `ahead=2` and the verdict `HOLD:ahead`. The proof that nothing
is lost is the patch equality in the table, plus `git cherry origin/main
<branch>`, which prints both branch commits with a leading minus (an equivalent
change is already upstream) and none with a plus.

## Verification

| Check | Result | Evidence |
|-------|--------|----------|
| Both branch commits have an equivalent on `origin/main` | PASS | `git cherry` printed `-` for both branch commits and no `+`; `git patch-id --stable` gave equal ids for each pair, 2026-10-20T03:50Z |
| Both `main` copies are ancestors of `origin/main` | PASS | `merge-base --is-ancestor` returned `ANCESTOR` for `116203a3` and `7f8e75c9` against `origin/main` at `90dab62483e8ef35924dcae5a000c3086b18f4ea` |
| Production deployment of the final commit | PASS | Looked up by exact SHA through the GitHub deployments API: `7021409971`, Production, latest status `success`. The first commit has no deployment of its own; it was delivered in the same push |
| Campaign test files | PASS | `tests/test_iwafu_relevance.py` and `tests/test_annotator_relevance_gate.py`, run in the worktree at the branch tip with bytecode and the cache provider disabled: 20 passed in 0.95 s |
| Work-marker words on added lines (source 4) | PASS | 0 over `9cb1e11e..7f8e75c9` (script, 2026-10-20T03:49Z) |
| Open GitHub issues naming the slug, excluding `daily-review` (source 5) | PASS | 0 from the script. A separate search for open issues mentioning iwafu found two older feature requests, listed under Known risks |
| Legacy tracking plans (source 3) | PASS | 0; the worktree has no `.copilot-tracking/plans` directory |
| Unchecked items in a specification `tasks.md`, and Deferred sections (sources 1 and 2) | NOT TESTED | The slug resolves to no directory under `docs/specs/active/` or `docs/specs/archive/`, so both are `not_checked`. The owner stated that the campaign has no specification |
| Session contention | NOT TESTED | The script returned `SOLE_OWNER (CLI-scope)`, which covers Copilot CLI sessions only. The campaign was carried out in a cloud Claude session, which is not detectable. The owner was asked to confirm that no other session uses the worktree and did not answer that part separately |
| Production data state (the 21 events set to inactive) | NOT TESTED | No database tool is available to the close-out agent; the figure comes from the iwafu history entry |
| Live behaviour of the Daily Scraper with the new gates | NOT TESTED | No scraper run was observed after the merge |

## Correction and supersession

None.

## Known risks

* **The script verdict is `HOLD:ahead`, accepted by the owner as a false
  positive.** After reading the Phase A output, the owner accepted that the two
  commits were merged under different hashes and said the campaign has no
  specification. This record does not rewrite the verdict. The evidence for the
  exception is the patch equality and the `git cherry` output above.
* **Two unhandled-work sources were not checked.** Sources 1 and 2 are
  `not_checked` because the campaign has no specification. Accepting that does
  not resolve the unknown; an item of this campaign that is only in a file this
  audit does not read was not seen.
* **Session contention rests on the owner's statement and on a process scan.**
  See the Verification row. The retirement preflight repeats the scan of
  working directories before the decision time is recorded.
* **Two older issues mention the source.** Open issues 2 and 4, both titled
  `feat(scraper): add iwafu source`, are feature requests from before the source
  existed. They do not name this campaign. Whether they should be closed is not
  decided here.
* **The production deactivation of 21 events is unverified here.** The history
  entry says they were set to inactive with a reason naming the layout change.
  If any of them was reactivated or re-ingested since, this record does not
  know.
* **The branch also exists on the remote.** `origin/fix/iwafu-taiwan-relevance-gate`
  is at the branch tip. Removing the worktree does not remove it.
* **No evidence anchor exists**, so the process telemetry of the session that
  produced this campaign cannot be recomputed.

## Deferred work

Two items come from the iwafu history entry. They are relocated here, not
completed.

| Item | Source |
|------|--------|
| The event `iwafu_1061560` (a steam-locomotive run at a ranch in Chiba, ingested in April) is a legitimate match for the gates, because the locomotive once served in Taiwan, but it is a borderline case. The history says a person decides whether to deactivate it in the admin screen, and that the prompt should not be tightened for it | `.github/skills/sources/iwafu/history.md`, the follow-up of 2026-10-13 |
| Whether to close the two stale feature-request issues (2 and 4) named under Known risks | This close-out |

## Spec disposition

`none` for `docs/specs/active/iwafu-taiwan-relevance-gate/`, because the campaign
has no specification and the owner confirmed it. The audit script resolves the
slug to no directory. Nothing needs archiving or moving.

One consequence: every re-audit of this slug reports the specification sources as
`not_checked`, so the script verdict can reach `UNDETERMINED` at best, and
`HOLD:ahead` for as long as the branch exists. Both are properties of the
campaign's shape, not defects to repair before removal.

## Worktree disposition

`pending`. The owner has accepted the `ahead=2` exception and confirmed that
there is no specification, after reading the Phase A output (2026-10-20T03:49Z).
No removal decision exists yet. The decision time is written when the retirement
preflight has re-observed the six values below and a recovery capsule exists
outside the worktree.

| Freshness value | Observed at the close-out audit (2026-10-20T03:49Z) |
|-----------------|-----------------------------------------------------|
| branch tip | `294d3a509e4223e9071b4a675d9caff01e00c3f7` |
| ahead of `origin/main` | 2 (both have an equivalent on `main`; see Delivered commits) |
| behind `origin/main` | 45 |
| dirty count | 0 |
| ignored artifact set | 3 directories, 134 files, listed under Ignored artifacts |
| path identity | `canonical`, directory `ttr-iwafu-gate-worktree`, branch `fix/iwafu-taiwan-relevance-gate` |

Stashes: 0. No rebase, merge, cherry-pick, or revert was in progress. The
branch has a remote counterpart at the same tip, so a remote deletion is owed
at retirement, and `git branch -d` needs the upstream tip to contain the local
tip (it does: 0 ahead, 0 behind the upstream).

## Ignored artifacts and handling

The worktree holds 134 ignored files in three directories: `scraper/__pycache__/`,
`scraper/security/__pycache__/`, and `scraper/sources/__pycache__/`. Every file
is a compiled bytecode cache. Each one maps to a tracked source file with the
same name (134 of 134 checked), so all are regenerable and classified
`disposable`. There were no symbolic links, no special files, and no ignored
file outside those directories.

Instead of 134 separate rows, the table gives one digest over the sorted list of
`<sha-256>  <path>` lines of all files, computed at 2026-10-20T03:55Z. The
retirement preflight observes the set again and records any difference.

| Artifact set | Handling | Manifest digest (SHA-256 of the sorted per-file digest lines) |
|--------------|----------|----------------------------------------------------------------|
| 134 `.pyc` files under the three `__pycache__` directories | `disposable` | `7f775f47e95484b62a5bab7485131ce247515b93faf66f94d8f207b6f5a50712` |

## Evidence anchors

None. No session id was supplied for this campaign and no session slice was
specified, so no anchor and no ledger were generated. This is listed as
unfinished work. The generator reads local transcripts only, and the campaign's
session was a cloud session whose transcript is not on this machine.
