---
title: Authoritative Venue Repair Close-out
description: Thirteen commits that made the venue registry authoritative, routed TIFF films to physical venues, and added an immutable manifest repair tool are on origin/main; the production repair was paused before any capture, and this record lists what that pause costs and where the remaining work is tracked
ms.date: 2026-10-22
ms.topic: reference
keywords:
  - authoritative venue repair
  - venue registry
  - tiff
  - data repair
  - campaign close-out
estimated_reading_time: 12
---

## Outcome

The code half of the authoritative-venue-repair campaign is delivered, and the
production half is paused. Thirteen commits sit on `origin/main`. No production
row was captured, written, or deleted by this campaign.

What is true now:

* Venue resolution in the scraper takes `venue_id` and canonical fields only from a
  unique hit on a venue with `is_authoritative = true`. Canonical, alias, same-tier,
  and cross-tier collisions fail closed, and a registry load failure caches an empty
  state rather than a partial one.
* Seed desired state and propagation follow the registry, field corrections stay
  above it, pure publications bypass venue resolution, and `location_url` accepts
  only verified facility homepages.
* TIFF films are routed to physical venues in first-appearance act order. A film
  whose screen or venue cannot be proven is skipped whole.
* The fixed venue data of Johakyu and Starcat (Century) was corrected.
* `scraper/_oneoff_repair_authoritative_venues.py` can capture an immutable manifest,
  apply it with exact-before CAS and read-back, and roll it back. After the
  correction cycle 2 commit its planner emits the full inventory: 6 venue updates,
  3 venue inserts, 59 event and field-correction actions, and 2 conditional
  duplicate deletions, 70 actions in total.

What is not true:

* The repair has never run against production. On 2026-10-22 the repository owner
  paused the production phase after Gate 1. The capture, Gate 2, the production
  CAS, and the read-back are not done.
* Because the three new venues the plan would insert do not exist in production,
  the weekly TIFF source currently delivers no event at all. See Known risks.

| Field | Value |
|-------|-------|
| Campaign base (`origin/main` before the first push) | `8113549c6ae1c72a47d4e28f18ccfa77804dad7c` (2026-08-08, docs(specs): record D-lane delivery in workstream tracking) |
| Segment 1 | `8113549c..01754b85`, 11 commits, pushed 2026-08-09 14:49 JST |
| Segment 2 | `02ab2027..10770777`, 1 commit, pushed 2026-10-22 15:29 JST |
| Segment 3 | `10770777..208a59a6`, 1 commit, pushed 2026-10-22 15:34 JST |
| Commits in the full range `8113549c..208a59a6` | 197: 13 from this campaign, 184 from other work |
| Push approval | Gate 1 approval by the repository owner on 2026-10-22 for segment 2; segment 3 is the spec parking commit |

## Delivered commits

| Commit | Change | Ancestor of `origin/main` |
|--------|--------|---------------------------|
| `28403a3aef918ea1dd2dcad1a8320ba17359a1a9` | 2026-08-06. docs(docs): establish authoritative venue repair spec | yes |
| `1e268ba1bd64e55be721618d7ef33667d7e02cae` | 2026-08-06. feat(scraper): make venue registry collision-safe | yes |
| `9c9778833f6563b86d08f235dadd4f86a388cc1c` | 2026-08-06. feat(scraper): enforce authoritative venue desired state | yes |
| `f86f0d4d38a9df81c8bf4314f64f21bd4e690d3f` | 2026-08-06. feat(scraper): enforce authoritative venue propagation | yes |
| `4aadac8fc556dab85c23b7a7d9c3b5107e5ba373` | 2026-08-06. feat(scraper): route TIFF films to physical venues | yes |
| `d1025148ab14a3e9cf0d1945723cc82508063809` | 2026-08-06. fix(scraper): update fixed venue locations | yes |
| `ac8472641c73f2a0e8a6e9fc92f4b11b623f1258` | 2026-08-06. feat(scraper): add immutable authoritative venue repair tool | yes |
| `a0eb7c8e2901a8185d7ad82da347bdef12c43bc5` | 2026-08-06. feat(scraper): add production venue repair planner | yes |
| `bdd4716ef663b351a9bcd7e95f2901169c2a81dd` | 2026-08-06. docs(docs): record authoritative venue validation | yes |
| `bfdb220b3863dce761a4be5efd0f335aa531f627` | 2026-08-06. docs(docs): record tester correction cycle triage | yes |
| `01754b85eeaba72bf13e5ef9da4ec69ca886d17c` | 2026-08-06. docs(docs): close authoritative venue tester phase | yes |
| `10770777b3baa49ffb6c24aec2579bf42b9fe009` | 2026-08-09 (authored), pushed 2026-10-22. fix(scraper): include authoritative venue updates; Gate 1 correction cycle 2 | yes |
| `208a59a633af2ade560cdd497d553d580277ec8a` | 2026-10-22. docs(specs): park the authoritative-venue-repair production phase | yes |

Each row was checked with `git merge-base --is-ancestor` against `origin/main`
`eb6c664543b0bacf15a0e54b903dc052b954ccf9` at 2026-10-22T07:49Z, after a fetch, and
all thirteen returned `ANCESTOR`. The dates in the table are author dates; the
first eleven were pushed on 2026-08-09, see Known risks.

`10770777` is the non-conflicting rebase of the earlier local commit `3f7c00f6`
(base `e8f756c0`, 2026-08-09) onto `02ab2027`. The tasks file records
`git range-diff` as `3f7c00f6 = 10770777`. Before the rebase the commit was saved
with `git format-patch` to the local notes directory
`~/.ai-notes/ttr/venue-repair-20261022/`, which is outside the worktree.

The campaign has no remote branch: `origin/feat/authoritative-venue-repair` does
not exist and the local branch has no upstream. All three segments were
fast-forward pushes to `main`.

The commit dated 2026-10-22 with subject `docs(skills): record the tester lessons
from the venue repair Gate 1 check` came after the last segment and is not a
delivered commit of this campaign.

## Verification

| Check | Result | Evidence |
|-------|--------|----------|
| All thirteen commits are ancestors of `origin/main` | PASS | `merge-base --is-ancestor` returned `ANCESTOR` for each at 2026-10-22T07:49Z |
| Campaign task list is closed | PASS | `docs/specs/active/authoritative-venue-repair/tasks.md` holds 0 unchecked and 138 checked items at `208a59a6`. At `10770777` it held 36 unchecked items: 26 were moved to the parked spec and 10 were checked in `208a59a6` |
| Remaining items moved without loss | PASS | The documented command in the parked spec re-derives the 26 moved lines from `tasks.md` at `10770777`; the close-out agent re-ran it and got SHA-256 `7c3ba6f5de1361455a526be9e2629422ec4bd7be7cecfdb2f827fd48f1ba21a3`, equal to the expected value |
| Independent Tester acceptance at `10770777` | PASS | Recorded by the campaign on 2026-10-22: 16 of 16 matrix items PASS, focused repair suite of 60 tests PASS on Python 3.14.3 and 3.12.15, 278 tests in the 10 related files PASS, full scraper suite 1055 passed and 1 skipped. The close-out agent read `tasks.md` and did not re-execute these |
| Independent Tester acceptance at the 2026-08-06 head | PASS, later found insufficient | Tester correction cycle 1 reported PASS with 64 eligible actions; correction cycle 2 found that the plan held no venue update action. See Correction and supersession |
| Gate 1 push approval | PASS | Recorded in `tasks.md`: the owner approved the exact changeset `10770777` on 2026-10-22 |
| Pushes were fast-forward and deployed cleanly | PASS | Both 2026-10-22 pushes appear as `update by push` in the `origin/main` reflog with a linear parent chain. The Vercel and gitleaks checks of `10770777` and `208a59a6` reported `success`, measured by the coordinating session on 2026-10-22; the close-out agent did not query them |
| Source dry-runs of `tiff`, `johakyu`, and `starcat_cinema` | NOT TESTED | On 2026-08-06 `tiff` returned 0 events because the 2026 API hostname did not resolve, `johakyu` returned 0 events, and `starcat_cinema` returned 5 events with one inverted date range. None of the three is a PASS; the items are in the parked spec |
| Weekly TIFF source in production | FAIL | GitHub Actions run 39192650984 (2026-10-19) skipped all 10 Taiwanese TIFF 2026 films and logged `tiff: 0 Taiwan films found (years=[2026])`. Measured by the coordinating session; see Known risks |
| Production repair capture, apply, second apply, and read-back | NOT TESTED | Paused by the owner before any production query for this phase. Production was not queried or mutated by the campaign in correction cycle 2 or after |
| Full-plan rollback to the exact before state | FAIL | The 2026-10-22 Tester run stopped the rollback after the 37th mutation in reverse order with an event and field-correction read-back mismatch. This is R1 in Known risks |
| Session contention at the close-out audit | NOT TESTED | The script's `SOLE_OWNER (CLI-scope)` covers Copilot CLI only. See Worktree disposition |

## Correction and supersession

None. No earlier close-out record exists for this campaign.

One claim in the spec was overtaken by the campaign itself. The 2026-08-06 Final
Test Report in `tasks.md`, shipped in segment 1, recorded a Tester PASS in which
the read-only planner classified 64 eligible actions. When capture preparation
began, the pushed planner was found to emit zero concrete venue update actions
for the six approved existing venues, so that PASS did not cover the approved
mutation inventory. The commit `10770777` (fix(scraper): include authoritative
venue updates) added the six updates and the dependent event actions, and the
spec records the correction as Gate 1 correction cycle 2. The 2026-08-06 text was
left in place, which is correct for the spec's history.

## Known risks

* **The production pause has a real cost: the weekly TIFF source delivers
  nothing.** GitHub Actions run 39192650984 (Monday 2026-10-19; `tiff` is a weekly
  source) logged that all 10 Taiwanese TIFF 2026 films were skipped:
  39001CMP01, 39001CMP05, 39004GLS02, 39004GLS09, 39005WFC13 to 39005WFC17, and
  39032AIC01, ending with `tiff: 0 Taiwan films found (years=[2026])`.
  * Cause. `scrape()` in `scraper/sources/tiff.py` selects Taiwanese films by
    `made_in_en`, then calls `_resolve_film_venues()`. The registry reads only
    production `venues` rows with `is_authoritative = true`, and a film whose venue
    is not found is skipped whole. This is the fail-closed behaviour the campaign
    shipped in segment 1.
  * Missing venues, per film in that run: ヒューリックホール東京 for 3 films
    (39001CMP01, 39001CMP05, 39005WFC13), TOHOシネマズ シャンテ for 3 (39005WFC16,
    39005WFC17, 39032AIC01), TOHOシネマズ 日比谷 スクリーン12・13 for 2 (39005WFC14,
    39005WFC15), and 丸の内ピカデリー for 2 (39004GLS02, 39004GLS09); 10 films in
    total. The first three are exactly the three venue inserts in this campaign's
    plan. 丸の内ピカデリー is **not in the plan**, because the plan was built from
    the 2025 venues.
  * Production state. A read-only query approved by the owner on 2026-10-22
    found none of these four venues in `venues`; the only near match was the
    unrelated 日比谷図書文化館 with `is_authoritative = false`. `events` holds 0 rows
    with `source_name = 'tiff'`, so this source has never been ingested. `tiff_jp`,
    `johakyu`, and `starcat_cinema` ingest normally; `starcat_cinema` returned 0
    films on 2026-10-22 because its site answered 503, which is a temporary fault.
    These facts were measured by the coordinating session, not by the close-out
    agent.
  * Mitigation. The owner decided to handle the four venue inserts in a separate
    session, from a new worktree on the latest `main`, inserting only these four
    venues, with a read-only capture first and a Gate 2 owner approval before any
    production write. The full 70-action repair and R1 stay paused. The handoff
    lives in the local notes file `~/.ai-notes/ttr/tiff-venue-inserts-handoff.md`
    and is not committed.
* **R1: the full plan cannot roll back to the exact before state.** For the online
  grant event `dec284a5-983a-4149-a093-b24dd6212a9a`, the before state holds field
  correction `corrected_value` entries of `"null"` and `"[]"` while the event itself
  carries a real address and prefecture. `unlock_and_write` keeps event and field
  corrections in step, so it cannot rebuild that inconsistency; the rollback stops
  after the 37th mutation in reverse order, and the venue update rollbacks never
  run. The older 64-action planner fails identically, so this is not a regression
  of correction cycle 2. No current test exercises a full-plan rollback. Before
  Gate 2 an engineer has to add a rollback path for the malformed state, or Gate 2
  has to disclose that this action cannot be rolled back exactly.
* **The plan inventory is a 2026-08-06 snapshot.** Production has drifted since
  that baseline, and the plan does not know about 丸の内ピカデリー. Every live
  number must be captured again on restart, as the parked spec states.
* **The audit script's verdict is `HOLD:unhandled_work`, and it stands.** The open
  issue 339 names the slug and is counted as unhandled work. It is the board card
  for the parked runbook, created on 2026-10-22 after the first audit. The owner
  ruled, after reading the re-run audit, that issue 339 is the second tracking
  location of the deferred work and not new work of this campaign. That ruling is
  the owner's; this record does not rewrite the script result.
* **Attribution of three commits that no segment covers.** In the full range, 184
  commits belong to no segment. Three of them add 16 lines containing the literal
  work-marker words: `717b97e4` (2026-08-12, feat(governance): add campaign
  close-out and worktree retirement agent, 9 lines), `6acae937` (2026-10-13,
  docs(agents): add senses-taxonomy campaign close-out record, 1 line), and
  `8f09543d` (2026-10-13, docs(agents): record senses-taxonomy close-out lessons in
  campaign-closer, 6 lines). All 16 are prose describing the audit scan itself.
  They belong to the campaign-closer and senses-taxonomy work, and the owner
  confirmed that attribution. The only other uncovered commit touching this spec,
  `dfcd529e` (2026-10-07, chore(ai): remove legacy Copilot state paths), adds no
  marker line.
* **The Validate, Merge and Deploy step for `10770777` was performed by the main
  session, not by that agent.** Before the push the main session fetched again and
  confirmed `origin/main` was still `02ab2027`, ahead 1 and behind 0, and the owner
  pushed with a fast-forward. The owner accepted this as equivalent.
* **Push dates differ from author dates.** The first eleven commits carry author
  dates of 2026-08-06 but were rebased and pushed on 2026-08-09 14:49 JST, and
  `10770777` carries an author date of 2026-08-09 but was pushed on 2026-10-22.
  The audit script prints author dates for its segments, so a reader using them as
  push times is off by days or months. The push times above come from the
  `origin/main` reflog.
* **Session contention rests partly on observation outside the script.** The
  script covers Copilot CLI sessions only. The main session `7933f2c9` and its
  Tester subagent used this worktree on 2026-10-22 for the rebase, the test runs,
  and the commits; no other recent Claude Code or Codex transcript had it as its
  working directory, `lsof` found no process with it as working directory or open
  file, and VS Code workspaceStorage and the recent list did not contain it.
  Undetectable is not the same as absent.
* **Source residuals outside the venue scope stay unfixed.** Starcat keeps one
  inverted date range, the TCC writer keeps the noncanonical `culture` category and
  four publish-date fallbacks, and Johakyu's parser found zero Taiwan hits. The
  2026-08-06 TIFF hostname failure no longer applies: the 2026-10-19 run fetched
  the 2026 films.
* **After the branch is deleted, the pre-rebase commit `3f7c00f6` survives only as
  the local patch file.** Its content is on `main` as `10770777`.
* **No evidence anchor exists**, so the process telemetry of the sessions that
  produced this campaign cannot be recomputed.

## Deferred work

The deferred items are relocated, not completed. The owner accepted closing the
campaign with production paused.

* **The production runbook lives in
  `docs/specs/parked/authoritative-venue-repair-followups.md`**, the authoritative
  list. It holds 28 unchecked items: the 26 items moved verbatim from `tasks.md`
  (official evidence for 高田世界館 and the TIFF stable root, the three source
  dry-runs, the half-done Gate 1 report line, the read-only capture, Gate 2, the
  production CAS and read-back, and the ban on mutation before Gate 2), plus R1 and
  a test that runs apply, a second apply, and rollback over the complete 70-action
  plan.
* **Issue 339 is the board card for that runbook**, the second tracking location.
  A gated runbook stays in one parked file with one card rather than being split
  into separate issues. The coordinating session updated its item count and
  completion condition from 26 to 28.
* **The four TIFF venue inserts go to a separate session**, including the
  丸の内ピカデリー gap, which is not in the parked spec. That session owns it; its
  handoff is the local notes file named in Known risks.
* **The spec directory is not archived yet.** See Spec disposition.
* **No evidence anchor was generated.** See Evidence anchors.

## Spec disposition

`archive` for `docs/specs/active/authoritative-venue-repair/`, target
`docs/specs/archive/2026-10-authoritative-venue-repair/`, because every task in
`tasks.md` is checked or moved and the remaining production work is tracked in the
parked spec and issue 339.

The move has **not happened**. The directory is still under `docs/specs/active/`
when this record is written, and its `proposal.md` frontmatter still says
`status: active` and `branch: feat/authoritative-venue-repair`; both are updated
with the move. The parked spec already says where to look once the directory is
archived. The audit script resolves `archive/<YYYY-MM>-<slug>`, so a re-audit after
the move still finds the spec.

## Worktree disposition

`remove`, decided at 2026-10-22T08:11:18Z (the time the recovery capsule was
written, after the owner ruled issue 341 a deferred-work tracking location).
The owner removed the worktree from a terminal outside it with
`git worktree remove` on the registered path, without `--force`, deleted the
branch with `git branch -d`, without `-D`, and reconciled the
`.git/info/exclude` block as a whole. The branch had no remote counterpart.

| Freshness value | Re-observed at 2026-10-22T08:10:09Z (D1, immediately before the decision) |
|-----------------|--------------------------|
| branch tip | `aadac0fe780136cdeddeed20bf906abdd1ee779e`, this record's commit, on `origin/main` |
| ahead of `origin/main` | `0` |
| behind `origin/main` | `0` |
| dirty count | `0` |
| ignored artifact set | `9`, the entries listed under Ignored artifacts and handling; per-directory file-list digests unchanged between 08:05Z and 08:10Z |
| path identity | `divergent`, directory `ttr-authoritative-venue-repair-worktree`, branch `feat/authoritative-venue-repair` |

No process had the worktree as its working directory or held a file open in it
(`lsof`). The main checkout's `main` matched `origin/main` (`0 0`).
`git cherry origin/main feat/authoritative-venue-repair` printed no line.

Residue check after removal, run by the coordinating session: registration gone,
branch gone, directory gone, administrative directory under `.git/worktrees/`
gone, exclude line gone, `git worktree prune --dry-run` printed nothing, and the
registered worktree count fell from 11 to 10. The exclude block held exactly the
nine live nested worktrees afterwards, so the reconciliation removed no line
beyond this campaign's own.

The recovery capsule is kept outside the repository at
`~/.ai-notes/ttr/capsules/2026-10-22-authoritative-venue-repair.md`
(SHA-256 `8bedb4591b0bd56510ef0904c305e6e196767e7d6ea052044033f32e07b3be7f`).
After the branch deletion, the pre-rebase commit `3f7c00f6` survives only as the
patch file named under Delivered commits; its content is `10770777`.

The earlier Phase A observation is kept below for reference.

| Freshness value | Observed at 2026-10-22T07:48:55Z (Phase A re-run, not a decision) |
|-----------------|--------------------------|
| branch tip | `208a59a633af2ade560cdd497d553d580277ec8a` |
| ahead of `origin/main` | `0` |
| behind `origin/main` | `5`; `origin/main` advanced to `eb6c6645` with other work, which is not a branch change |
| dirty count | `0` |
| ignored artifact set | `9`, the entries listed under Ignored artifacts and handling |
| path identity | `divergent`, directory `ttr-authoritative-venue-repair-worktree`, branch `feat/authoritative-venue-repair` |

The worktree is registered through the symlinked parent path and resolves inside
the repository root, so both strings name one directory. Stashes for the branch: 0.
No rebase, merge, cherry-pick, or revert was in progress. `git cherry origin/main
feat/authoritative-venue-repair` printed no line.

### Gates at the close-out audit

The audit script `scripts/campaign-closeout-audit.sh` ran three times against the
campaign worktree, each time with one `--range` per push and the full range
`8113549c..208a59a6`.

| Unhandled-work source | Run 1, 2026-10-22T06:36Z | Run 2, 07:14Z | Run 3, 07:48Z |
|-----------------------|--------------------------|---------------|---------------|
| `tasks.md` unchecked items | 0 | 0 | 0 |
| Deferred section of `changes-log.md` and `proposal.md` | 0 | 0 | 0 |
| Legacy tracking plans | 0 | 0 | 0 |
| Work-marker words on lines added in the segments | 0, plus 16 on uncovered commits | same | same |
| Open GitHub issues naming the slug, excluding `daily-review` | 0 | 1 (issue 339) | 1 (issue 339) |
| Script verdict | `UNDETERMINED` | `HOLD:unhandled_work` | `HOLD:unhandled_work` |

The segment bases and heads were derived from the `origin/main` reflog, where
each push appears as `update by push`, and checked against the first-parent chain.
Issue 339 appeared between runs 1 and 2. The owner's decisions to write this
record, to treat issue 339 as deferred-work tracking, and to accept the
attributions above were given after reading the run 2 result, and were relayed to
the close-out agent by the coordinating session.

## Ignored artifacts and handling

All nine ignored entries are Python and pytest caches that a fresh test run
regenerates, about 9.0 MB in 383 files. The worktree has no untracked file and no
ignored file under `tmp/`; the only file there, `tmp/gnews_streaming_ids.txt`, is
tracked. Manifest capture never ran, so no manifest, baseline, journal, or
rollback snapshot exists in the worktree. The preflight is repeated immediately
before removal, and any difference stops the removal.

| Artifact | Handling | SHA-256 |
|----------|----------|---------|
| `.pytest_cache/` (24K) | `disposable` | not applicable (directory) |
| `scraper/.pytest_cache/` (88K) | `disposable` | not applicable (directory) |
| `scraper/__pycache__/` (3.2M) | `disposable` | not applicable (directory) |
| `scraper/auto_scraper/__pycache__/` (104K) | `disposable` | not applicable (directory) |
| `scraper/auto_scraper/tests/__pycache__/` (88K) | `disposable` | not applicable (directory) |
| `scraper/external_stats/__pycache__/` (68K) | `disposable` | not applicable (directory) |
| `scraper/security/__pycache__/` (36K) | `disposable` | not applicable (directory) |
| `scraper/sources/__pycache__/` (1.9M) | `disposable` | not applicable (directory) |
| `scraper/tests/__pycache__/` (3.5M) | `disposable` | not applicable (directory) |

## Evidence anchors

None. The sessions that took part before 2026-08-09 can no longer be traced, and
the 2026-10-22 main session `7933f2c9` is a Claude Code transcript, which the
anchor generator does not support; its format compatibility was not verified. No
anchor and no ledger were generated, so the process telemetry of this campaign
cannot be recomputed.

### Update after the close-out (2026-10-22)

Issue 341, "TIFF 2026: add four authoritative venues so the tiff scraper can
ingest the Taiwanese films", carries the `spec:authoritative-venue-repair` label.
The coordinating session opened it at 2026-10-22T07:52:23Z, after audit run 3 and
before this record was committed, so the record above does not name it. It is the
board card for the four-venue work described under Known risks (the three planned
TIFF venue inserts plus 丸の内ピカデリー), owned by a separate session.

The D1 audit at 2026-10-22T08:10:30Z, run with `--head 208a59a6`, reported
`HOLD:unhandled_work` with two open issues, 339 and 341. After reading that
result, the owner ruled issue 341 a deferred-work tracking location, as for
issue 339, and decided to retire the worktree. This update records the ruling; it
does not change the script verdict.

The spec directory was moved to
`docs/specs/archive/2026-10-authoritative-venue-repair/` in the same commit as
this update, with `status: archived` in its `proposal.md`. The Spec disposition
section above was written before the move and is kept as written.
