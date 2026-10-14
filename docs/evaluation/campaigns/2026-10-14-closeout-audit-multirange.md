---
title: Closeout Audit Multi-range Close-out
description: Six commits taught the campaign close-out audit to count work-marker words per push, to list commits that no push covers, and to refuse empty segments; this record proves the delivery, states what could not be checked, and holds the worktree disposition as pending
ms.date: 2026-10-14
ms.topic: reference
keywords:
  - campaign close-out
  - audit script
  - per-push range
  - uncovered commits
  - worktree retirement
estimated_reading_time: 9
---

## Outcome

The closeout-audit-multirange campaign is delivered. Six of its commits sit on
`origin/main`, and the Vercel Production deployments of the three push heads
`6672b320`, `f321bc25`, and `06a5f4d1` reported `success`. The campaign changed
the close-out audit script, its tests, agent guidance, and the parked
ai-portability specification only; it touched no scraper or web runtime code,
wrote nothing to the production database, and rotated no secret.

What is true now:

* `scripts/campaign-closeout-audit.sh` accepts a repeatable
  `--range <base>..<head>`, one per push. Each segment is counted and printed
  with its first and last commit, and the total is taken over the distinct
  commits of all segments. A campaign pushed in several rounds is no longer
  charged with the added lines of other campaigns that landed between the rounds.
* Given a full range (`--base` and `--head` next to `--range`), the script counts
  the commits in the full range that no segment covers and lists, for each one
  that adds work-marker words, its short SHA, date, author, subject, files, and
  the added line. Those lines are not added to the unhandled total, but they hold
  the verdict at `UNDETERMINED` until a person attributes them. Without a full
  range that figure is `not_checked`.
* A segment that does not resolve, or that holds no commit because its base and
  head are swapped or equal, makes the range figure `not_checked`, never `0`.
  Both ends are peeled to commits first, so a tree or blob no longer passes as a
  range end.
* Open-issue source 5 excludes the `daily-review` label, because those reminders
  list commit subjects and match any slug named in one.
* Two older defects found while writing the tests are fixed: a value flag given
  last no longer loops forever, and a failing `git log` no longer leaves a
  clean-looking zero.
* The handoff contract, the Validate, Merge and Deploy agent, the Close Campaign
  agent and skill, and `docs/evaluation/campaigns/README.md` all carry per-push
  base and head pairs plus the full range.
* Two documentation errors in the Validate, Merge and Deploy agent are corrected:
  a push that touches no `web/` file can still produce a Production deployment,
  so Step 5 looks it up by exact SHA every time; and a reference to a missing
  commit-message instruction file now points to `git.instructions.md`.
* Two lessons from the ai-portability retirement are recorded in the Close
  Campaign skill and history: a bare `cd` in the Bash tool leaks the working
  directory into another campaign's worktree, and verification checks must carry
  explicit labels because parallel results may not display in call order. This
  record cites them; it does not restate them.

| Field | Value |
|-------|-------|
| Campaign base (`origin/main` before the first push) | `c757e07057f351a108d24939a9884aa26a0268ce` |
| Segment 1 | `c757e07057f351a108d24939a9884aa26a0268ce..6672b320438e6fefc99e54f9f2be729b31acf12f`, 1 commit, 5 files (685 insertions, 21 deletions); `origin/main` reflog: updated by push at 2026-10-13T08:24:36Z |
| Segment 2 | `6672b320438e6fefc99e54f9f2be729b31acf12f..f321bc251caf5148a8d42b34b5b6bd87a2f706b5`, 4 commits; reflog: 2026-10-13T14:40:30Z |
| Segment 3 | `96097f533de822bab4d5a945e95882585792cc88..06a5f4d162aa95ce55a1e8a48b58fa2a70f46664`, 1 commit, 2 files (92 insertions); reflog: 2026-10-13T19:06:44Z |
| Full range | `c757e07057f351a108d24939a9884aa26a0268ce..06a5f4d162aa95ce55a1e8a48b58fa2a70f46664`, 9 commits, 0 merge commits, one author |
| Commits in the full range | 9: 6 delivered by this campaign, 3 that no segment covers (see Delivered commits) |
| Production deployments | `7033673184` for `6672b320`, `7041536267` for `f321bc25`, `7047601044` for `06a5f4d1`; all `success` |
| Push approval | Not observed by the close-out agent. The push times above come from the local `origin/main` reflog |

## Delivered commits

All dates are 2026-10-13 or 2026-10-14 as shown, in the author's +0900 time.

| Commit | Change | Ancestor of `origin/main` |
|--------|--------|---------------------------|
| `6672b320438e6fefc99e54f9f2be729b31acf12f` | 2026-10-13 17:01. `feat(agents): campaign closeout audit counts per-push ranges and skips daily-review`. Repeatable `--range`, distinct-commit total, `daily-review` exclusion, the new test file, and the first skill and history entries | yes (`ANCESTOR`) |
| `3d52efacea50c4e1c8452bbc7433db298ce81315` | 2026-10-13 18:05. `fix(agents): campaign closeout audit refuses an empty --range segment`. An empty segment makes the range figure `not_checked` | yes (`ANCESTOR`) |
| `7bd000aee85b1d6ead20f29a54f80a8107f6a6c2` | 2026-10-13 18:10. `feat(agents): campaign closeout audit reports commits no segment covers`. Full-range detection and the readable per-commit listing | yes (`ANCESTOR`) |
| `ac5e3b8625f581838c78f3998d1e88aea8e89690` | 2026-10-13 18:13. `docs(agents): carry per-push base/head pairs and the full range through close-out`. Handoff template, Close Campaign agent and skill, runbook, and the campaigns README | yes (`ANCESTOR`) |
| `f321bc251caf5148a8d42b34b5b6bd87a2f706b5` | 2026-10-13 18:14. `docs(agents): correct two V-M-D documentation errors recorded in the parked spec`. Validate, Merge and Deploy Step 3 and Step 5, a correction entry in the Engineer history, and the parked specification. Attributed to this campaign by the owner; see Known risks | yes (`ANCESTOR`) |
| `06a5f4d162aa95ce55a1e8a48b58fa2a70f46664` | 2026-10-14 04:06. `docs(agents): record bare-cd cwd leak and labeled-check lessons in campaign-closer`. Two skill sections and two history entries. Attributed to this campaign by the owner; see Known risks | yes (`ANCESTOR`) |

Each row was checked with `git merge-base --is-ancestor` against `origin/main`
(`06a5f4d162aa95ce55a1e8a48b58fa2a70f46664`, confirmed against the remote with
`git ls-remote`) between 2026-10-14T00:41Z and 00:43Z, and all six returned
`ANCESTOR`.

Three commits sit in the full range but in no segment. They are not delivered by
this campaign as far as the owner has decided:

| Commit | Date | Subject | Attribution |
|--------|------|---------|-------------|
| `ca569d8d7e21abf85c6e0418df2393437cfc001f` | 2026-10-14 | `docs(agents): add ai-portability campaign close-out record` | ai-portability, by the owner's decision |
| `96097f533de822bab4d5a945e95882585792cc88` | 2026-10-14 | `docs(agents): record ai-portability worktree retirement` | ai-portability, by the owner's decision |
| `1c5abfb9b88902134931f7af4811ef7682b459db` | 2026-10-14 | `docs(ai): record post-close-out follow-ups in the parked ai-portability spec` | **No decision.** Its added text on line 70 of the parked specification names this campaign's slug, and the four open items it adds are listed under Deferred work. The audit script's hint reads only the subject and the paths, and neither names the slug |

All three also returned `ANCESTOR` in the same check. None of the three adds a
work-marker word.

## Verification

| Check | Result | Evidence |
|-------|--------|----------|
| All six delivered commits are ancestors of `origin/main` | PASS | `merge-base --is-ancestor` returned `ANCESTOR` for each SHA, 2026-10-14T00:41Z to 00:43Z |
| Production deployments of the three push heads | PASS | Looked up by exact SHA through the GitHub deployments API, with the latest status read at 2026-10-14T00:41Z: `7033673184`, `7041536267`, and `7047601044` each reported `success`. The same identifiers were reported by the Validate, Merge and Deploy session and re-queried by the close-out agent between 2026-10-13T19:14Z and 19:18Z, and again at 2026-10-14T00:41Z |
| Audit script test suite at the tip | PASS | `scripts/tests/test_campaign_closeout_audit.py`: 46 passed in 9.72 s, run by the close-out agent at `06a5f4d1` with bytecode and cache writing disabled; the dirty count stayed 0 and the ignored set stayed at 5 entries |
| Generated adapters match their sources | PASS | `python3 scripts/sync_ai_adapters.py --check` exited 0 at `06a5f4d1` |
| Work-marker words on lines added in the commit range (source 4) | PASS | 0 in each of the three segments over 6 distinct commits; the 3 uncovered commits add none. An independent recount over the full range of 9 commits, case-sensitive, also found 0. A case-insensitive scan found 168 further lines, all of them the audit script's own output-key names, not work items |
| Open GitHub issues naming the slug, excluding `daily-review` (source 5) | PASS | 0 from the script, and 0 from a separate `gh issue list --state open --search` with the label excluded; a search for the label together with the slug is also empty |
| Legacy tracking plans (source 3) | PASS | 0; the worktree has no `.copilot-tracking/plans` directory |
| Unchecked items in a specification `tasks.md`, and Deferred sections (sources 1 and 2) | NOT TESTED | The slug resolves to no directory under `docs/specs/active/` or `docs/specs/archive/`, so both are `not_checked`. The campaign has no specification. The open items that name it are in the parked specification and are listed under Deferred work. Residual risk: an item of this campaign that is not in that file was not seen |
| Session contention at the close-out audit | NOT TESTED | The script returned `UNDETERMINED` because no session id was supplied, so the audit session could not be excluded. The owner's statement, recorded under Worktree disposition, replaces detection. Detection covers Copilot CLI sessions only |
| Other test suites under `scripts/` (hooks, settings, adapters) | NOT TESTED | The campaign changed no hook or settings code. Only the audit script suite and the adapter check were run. Residual risk is low and limited to code this campaign did not touch |

## Correction and supersession

None.

## Known risks

* **Two unhandled-work sources were not checked.** Sources 1 and 2 are
  `not_checked` because the campaign has no specification directory. The script
  verdict is `UNDETERMINED` with the reasons `spec_dir_unresolved` and
  `self_session_unknown`. The owner accepted `UNDETERMINED`. Accepting it does
  not resolve either unknown, and this record does not rewrite the verdict.
* **Session contention rests on the owner's statement.** After reading the audit
  output the owner stated that no other session uses this worktree, and supplied
  no session id. The statement reached the close-out agent through the
  coordinating agent, not directly, and was taken at 2026-10-14T00:43Z. It
  replaces the detection result; it is not one. Detection covers Copilot CLI
  sessions only. According to the coordinating agent the campaign was carried out in
  Claude Code sessions, which write nothing the script reads, and VS Code chat
  sessions are not detectable either.
  A process scan for any working directory inside the worktree found none between
  2026-10-13T19:14Z and 19:18Z, and again at 2026-10-14T00:41Z; it cannot see a
  window that merely has the folder open.
* **Attribution of three commits that no segment covers.** The owner attributed
  `ca569d8d` and `96097f53` to ai-portability. For `1c5abfb9` the table put to the
  owner carried no recommendation, so the reply is not an attribution decision for
  it. Its added text names this campaign, and the four items it adds are tracked
  under Deferred work. If the owner later attributes it, a Correction section is
  the place to record that. The audit counts do not depend on the decision, because
  none of the three adds a work-marker word.
* **Two commits inside the segments were attributed by the owner, and both edit
  another campaign's files.** `f321bc25` changes the ai-portability parked
  specification and a Validate, Merge and Deploy documentation file, and its added
  text names this campaign as the one that handled two documentation errors.
  `06a5f4d1` records lessons whose background is the ai-portability worktree
  retirement, in the same skill this campaign changed. The audit counts do not
  depend on either decision.
* **Two Phase A commands were split after a guard block.** The PreToolUse hook
  blocked two of the close-out agent's read-only observation commands as
  `unsupported-syntax`. The same observations were re-run as single simple
  commands. No deny rule was involved and none was bypassed.
* **A real work issue given the `daily-review` label would be missed.** The label
  exclusion in source 5 exists because those issues are automatic reminders; the
  label must stay reserved for them.
* **A non-web push producing a Production deployment is observed, not explained.**
  The three push heads of this campaign touched no `web/` file and each has a
  Production deployment, as did four earlier non-web pushes recorded in the
  Engineer history. The cause was not investigated. The documentation now tells
  the verifier to look it up and not to assume.
* **Ignored artifacts are not yet classified.** 15 files in five cache
  directories exist. They are expected to be regenerable, but no classification or
  digest exists until the retirement preflight, which observes them again.
* **No evidence anchor exists**, so the process telemetry of the sessions that
  produced this campaign cannot be recomputed.

## Deferred work

The deferred items are relocated, not completed. Five unchecked items in
`docs/specs/parked/ai-portability-followups.md` came out of this campaign's work
or out of the ai-portability close-out that it ran alongside, and the owner
decided to list them here. They are tracked there, not forgotten. The line numbers
are those of the file at `06a5f4d1`.

| Line | Added by | Item |
|------|----------|------|
| 66 | `f321bc25` | Decide whether the `ai` commit scope, and scopes already used in recent history but not listed (for example `governance`, `skills`, `deps`, `evaluation`), join the scope list in `.github/instructions/git.instructions.md`. A convention decision, not a documentation typo |
| 72 | `1c5abfb9` | The Validate, Merge and Deploy Step 5 lacks a note that the deployments API returns an empty list until the build finishes, so a lookup during the pending period can be recorded as `NONE FOUND` by mistake |
| 73 | `1c5abfb9` | The push command is written three different ways in the Validate, Merge and Deploy agent; choose one and unify, and say why the push is not run inside the worktree |
| 74 | `1c5abfb9` | The Close Campaign agent and skill need two additions: what to do when the worktree's HEAD predates the script, and treating the terminal tab's outer shell as a separate occupant that `/exit` does not release |
| 75 | `1c5abfb9` | 149 `daily-review` issues are open and nothing closes them; decide between auto-closing, a single rolling issue, or accepting the exclusion |

The other 19 unchecked items in that file belong to ai-portability and are not
listed here. The 2026-10-13 history entries in the Close Campaign skill note that
the V-M-D handoff template was first left unchanged and was updated in
`ac5e3b86`; nothing further is outstanding on it.

## Spec disposition

`none` for `docs/specs/active/closeout-audit-multirange/`, because no such
directory exists, and no commit in any ref has ever contained one. The campaign
was run from a worktree and a branch without its own specification, and its
follow-up items are tracked in the parked ai-portability specification. Nothing
needs archiving or moving.

One consequence: every re-audit of this slug reports the specification sources as
`not_checked`, so the script verdict can reach `UNDETERMINED` at best. That is a
property of having no specification, not a defect to repair before removal.

## Worktree disposition

`pending`, decided at `pending`.

The owner answered that the worktree should be retired, at the Phase B reply,
after reading the audit output. That is an intention, not a disposition: no
removal has happened and no decision time exists yet. Removal is gated on all of
the following:

* This record is on `origin/main`.
* The recovery capsule is written outside the worktree.
* The six values below are re-observed immediately before removal and match.
* Occupancy is re-observed with `lsof`, and no process other than the close-out
  session holds the worktree as its working directory.
* The ignored artifacts are classified and their digests recorded.
* The owner states at that time that no other session uses the worktree.

At the Phase B reply the owner stated that no other session uses the worktree.
That statement is recorded here at 2026-10-14T00:43Z (09:43 JST) as the owner's
confirmation replacing detection, and it covers that moment only.

| Freshness value | Observed at the decision |
|-----------------|--------------------------|
| branch tip | `pending` |
| ahead of `origin/main` | `pending` |
| behind `origin/main` | `pending` |
| dirty count | `pending` |
| ignored artifact set | `pending` |
| path identity | `pending` |

For reference, the observation at the close-out audit (2026-10-13T19:14Z): branch
tip `06a5f4d162aa95ce55a1e8a48b58fa2a70f46664`, ahead 0, behind 0, dirty 0,
ignored artifact set 5, path identity `canonical` with directory
`ttr-closeout-audit-multirange-worktree` and branch
`feat/closeout-audit-multirange`. Stashes: 0. No rebase, merge, cherry-pick, or
revert was in progress. The branch tip, ahead and behind counts, dirty count, and
ignored set were observed again at 2026-10-14T00:41Z before this record was
written, with the same values. The branch has no remote counterpart, and its tip
equals `origin/main`.

### Gates at the close-out audit

The audit script `scripts/campaign-closeout-audit.sh` ran once against the
campaign worktree, with the three per-push segments and the full range given.

| Unhandled-work source | Close-out audit, 2026-10-13T19:14Z | Final |
|-----------------------|------------------------------------|-------|
| Unchecked items in `tasks.md` | `not_checked`: the slug resolves to no specification directory | `not_checked` |
| Deferred section of `changes-log.md` and `proposal.md` | `not_checked`: same reason | `not_checked` |
| Legacy tracking plans | 0 | 0 |
| Work-marker words on lines added in the commit range | 0 over three segments and 6 distinct commits; 0 on the 3 uncovered commits | 0 |
| Open GitHub issues naming the slug | 0, excluding `daily-review` | 0 |
| Script verdict | `UNDETERMINED` (`spec_dir_unresolved`, `self_session_unknown`) | not rewritten by this record |

Session contention. The script could not exclude the audit session because no
session id was supplied, so its result is `UNDETERMINED`. The close-out agent
inspected the Copilot session state by hand: of 35 session directories two held a
lock, and neither records a working directory inside this worktree. No session's
recorded root names the worktree. A scan for processes with the worktree as
working directory found none. Only Copilot CLI sessions are detectable; Claude
Code, VS Code chat, and Codex sessions are not.

## Ignored artifacts and handling

The worktree holds five ignored entries, 15 files in total: the pytest cache and
four bytecode cache directories. They are expected to be regenerable, so none is
expected to need preserving, but the classification and the digests are produced
at the retirement preflight, which observes the set again. Until then the
handling is `pending`. `tmp/` holds one file, `tmp/gnews_streaming_ids.txt`, which
is tracked and exists on `origin/main`; it is not an ignored artifact.

| Artifact | Handling | SHA-256 |
|----------|----------|---------|
| `.pytest_cache/` | `pending` (expected `disposable`) | `pending` |
| `scripts/__pycache__/` | `pending` (expected `disposable`) | `pending` |
| `scripts/claude/__pycache__/` | `pending` (expected `disposable`) | `pending` |
| `scripts/claude/tests/__pycache__/` | `pending` (expected `disposable`) | `pending` |
| `scripts/tests/__pycache__/` | `pending` (expected `disposable`) | `pending` |

## Evidence anchors

None. No session id was supplied for this campaign, and no session slice was
specified, so no anchor and no ledger were generated. This is listed as
unfinished work. The generator reads local transcripts only; when slice
boundaries are specified, one anchor per slice can be added in a later commit,
listed separately and never summed.
