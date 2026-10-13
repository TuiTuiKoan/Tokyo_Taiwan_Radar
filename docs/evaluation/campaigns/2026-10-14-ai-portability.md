---
title: AI Portability Close-out
description: Eleven commits that removed Copilot-only state paths, projected agent roles to Claude Code tool limits, and added Claude Code safety hooks are on origin/main; this record proves the delivery and lists what remains open
ms.date: 2026-10-14
ms.topic: reference
keywords:
  - ai portability
  - claude code
  - agent roles
  - pretooluse hooks
  - campaign close-out
estimated_reading_time: 10
---

## Outcome

The ai-portability campaign is delivered. Eleven of its commits sit on
`origin/main`, and the Vercel Production deployments of `86fdc143`, `6b404ea3`,
and `87c2b557` reported `success`. The campaign changed agent guidance, adapters, and Claude
Code configuration only; it touched no scraper or web runtime code, wrote
nothing to the production database, and rotated no secret.

What is true now:

* Copilot-only state locations (the session-memory path and the legacy tracking
  plans directory) are no longer write targets in active guidance. Committed
  working state goes to `docs/specs/active/<slug>/`, and local non-committed notes go
  to `~/.ai-notes/ttr/`. The legacy locations are read-only history. The
  research profile directory under the legacy tracking name stays, because two
  scraper scripts use it as an interface.
* Eleven managed agents carry a `claude-role` key. `scripts/sync_ai_adapters.py`
  turns it into a tool allowlist in the 15 `.claude/agents/*.md` wrappers, and
  its `--check` mode rejects pinned model names and generated-file drift. Four
  agents (architect, reviewer, researcher, scraper-expert) keep full tools on
  purpose, pending owner decisions recorded as X1 to X4 in the specification.
* `.claude/settings.json` asks for approval before any push and registers
  PreToolUse hooks under `scripts/claude/`. The hooks block force pushes,
  destructive git operations, reads and writes of local secrets files,
  environment dumps, heuristic production-database writes, and shell forms the
  guard cannot inspect. They fail closed.
* `AGENTS.md` states the boundary: the protection exists only for Claude Code
  sessions started from the repository or worktree root. Copilot and Codex are
  not protected, and the production-database rule is a heuristic.

| Field | Value |
|-------|-------|
| Campaign base (`origin/main` before the first push) | `7f8e75c9030badc96d10dd52f1f0023083e606be` |
| Segment 1 | `7f8e75c9030badc96d10dd52f1f0023083e606be..6b404ea3a4b029cf9c157d9773442b40d7fee5a8`, 8 commits, 78 files (6672 insertions, 72 deletions) |
| Segment 2 | `8f09543dc46164d48b8f64825115b0b210b8a113..87c2b55779377852bb0c262d95441d7c0bedba95`, 3 commits, 3 files (68 insertions, 21 deletions) |
| Commits in the full range | 21: 11 from this campaign, 10 from another campaign |
| Production deployments | `7024731927` for `86fdc143`, `7024868392` for `6b404ea3`, `7032193512` for `87c2b557`; all `success` |
| Push approval | The repository owner approved each push explicitly (the H-PUSH gate in `tasks.md`) |

## Delivered commits

| Commit | Change | Ancestor of `origin/main` |
|--------|--------|---------------------------|
| `1d1e3d4727b33b53738c41eed679b20dfa627366` | 2026-10-01. Added the Claude Code migration runbook | yes |
| `d239843182c6b46422f76ca6167c310107ec5b35` | 2026-10-06. Added the specification skeleton: proposal, tasks, notes, plan, and six plan critiques | yes |
| `dfcd529e96f28bde2541222e1ba545fc5ed43c78` | 2026-10-07. Phase A: removed legacy Copilot state paths from active guidance | yes |
| `1c7f760010fe0debf552a1a0136a9b7384ca84b5` | 2026-10-07. Recorded the Phase B drift stop and the context post-test | yes |
| `d71543c7844d9ea87b30816d6f602740b0560d81` | 2026-10-09. Phase B: projected agent roles to Claude tool limits | yes |
| `588a42b2a354033cf5be5f6aec9717d7bdbe2122` | 2026-10-13. Phase C: added the Claude Code PreToolUse safety hooks | yes |
| `86fdc1434188c49713bc37b6c7a71a9034f3b9b8` | 2026-10-13. Recorded the phase A to C lessons in agent history and skills | yes |
| `6b404ea3a4b029cf9c157d9773442b40d7fee5a8` | 2026-10-13. Recorded the push evidence and the post-rebase SHA map | yes |
| `f6c2dad2d7c898174504b1a58be684c0e97c9021` | 2026-10-13. Moved the follow-up backlog out of `tasks.md` into a parked specification | yes |
| `0d0d98114015e69dcdecb96a85c064411b3b53bf` | 2026-10-13. Pointed the follow-up note in `notes.md` to the parked specification | yes |
| `87c2b55779377852bb0c262d95441d7c0bedba95` | 2026-10-13. Recorded two documentation errors found during the push in the parked specification | yes |

Each row was checked with `git merge-base --is-ancestor` against `origin/main`
(`f321bc251caf5148a8d42b34b5b6bd87a2f706b5`, confirmed against the remote with
`git ls-remote`) at 2026-10-13T16:18Z, and all eleven returned `ANCESTOR`. The
SHAs are the ones on `origin/main`; the pre-rebase SHAs are mapped in
`docs/specs/active/ai-portability/notes.md` section 4.32.

Ten commits of the senses-taxonomy campaign sit between the two segments. They
are not delivered by this campaign; see Gates at the close-out audit.

The campaign has no remote branch: `origin/feat/ai-portability` does not exist,
because its commits were pushed to `main` directly. The local branch tracks
`origin/main`.

## Verification

| Check | Result | Evidence |
|-------|--------|----------|
| All eleven commits are ancestors of `origin/main` | PASS | `merge-base --is-ancestor` returned `ANCESTOR` for each SHA at 2026-10-13T16:18Z |
| Production deployments of `86fdc143`, `6b404ea3`, and `87c2b557` | PASS | `7024731927`, `7024868392`, and `7032193512` each reported `success`, queried by the close-out agent through the GitHub deployments API between 2026-10-13T16:18Z and 16:22Z. The deployments of `f6c2dad2` and `0d0d9811` were not queried |
| Hook and adapter test suites at `87c2b557` | PASS | `scripts/claude/tests` and `scripts/tests`: 437 passed in 6.37 s, run by the close-out agent in the campaign worktree with caches disabled; the dirty and ignored sets were unchanged afterwards |
| Generated adapters match their sources | PASS | `python3 scripts/sync_ai_adapters.py --check` exited 0 at `87c2b557` |
| Campaign task list is closed | PASS | `docs/specs/active/ai-portability/tasks.md` holds 0 unchecked and 110 checked items at `87c2b557` |
| Follow-up backlog moved without loss | PASS | All 19 lines of the follow-up section of `tasks.md` at `6b404ea3` (lines 187 to 205) appear byte-identical in the parked specification at `87c2b557`, 19 of 19 |
| Phase gates A-R1 to A-R9, B-R1 to B-R10, C-R1 to C-R12, the owner-run tests U1 to U6, and the five-role smoke test | PASS | Recorded by the campaign: every item is checked in `tasks.md`, and the underlying evidence lives in `notes.md`. The close-out agent read `tasks.md` and did not re-execute these checks |
| Five unhandled-work sources after attribution review | PASS | 0, 0, 0, 0, 0; see Gates at the close-out audit |
| Session contention at the close-out audit | NOT TESTED | The script's `SOLE_OWNER (CLI-scope)` covers Copilot CLI only. Live Claude Code sessions and two Codex daemon processes were observed with this worktree as working directory. The owner's statement is recorded under Worktree disposition, and the observation is repeated before removal |
| Protection of Copilot and Codex sessions | NOT TESTED | Out of design: hooks and permission rules exist only for Claude Code. The residual risk is listed below |
| Behaviour under a newer Claude Code version | NOT TESTED | The tool-limit and hook behaviour was measured on Claude Code 2.1.295 and 2.1.296. Re-running the fixtures after an upgrade is a follow-up item |

## Correction and supersession

None.

## Known risks

* **Session contention rests on the owner's statement.** Detection covers
  Copilot CLI sessions only. At the audit, a Claude Code engineer session and two
  Codex app-server daemon processes had this worktree as their working
  directory. The owner stated that no session other than the close-out session
  and that engineer session uses the worktree, and that the daemons are not their
  conversations. The statement is theirs, not a detected result.
* **Protection is Claude Code only.** Copilot and Codex sessions get no hook and
  no permission rule. The production-database rule is a heuristic: writes through
  project scripts, the Supabase CLI management APIs, the account-level Supabase
  connector, functions with side effects, and piped interpreter input are not
  covered. Roles that keep Bash can still write files through redirection.
  Details are in `plan.md` section 8 and the proposal's residual risk section.
* **Attribution of ten commits that no segment covers.** The new audit script
  reported ten commits between the two segments. Seven are named in the
  senses-taxonomy close-out record: six as its delivered commits and one
  (`6acae937`) as the record commit itself. Two (`701b559a`, `8f09543d`) carry
  the campaign name in their subject. One (`4ac6bd83`) is an **inference**: that
  record does not list it, and it is attributed by its subject (it aligns the
  category sync rule with `taxonomy.md`) and by the category-guidance files it
  touches. It contributed no work-marker line. The owner confirmed the
  attribution of all ten.
* **Seven added lines contain the literal work-marker words.** All seven are prose
  in the other campaign's commits that describes the audit rule itself, so the
  figure of seven reported by the single-span audit is a false positive for this
  campaign.
* **One open issue was excluded by label.** Issue 296 is an automatically
  generated daily review reminder that lists commit subjects, and it matched the
  slug because three subjects name it. The audit script now excludes the
  `daily-review` label. A real work issue given that label would be missed.
* **The `NOT TESTED` table at the end of `tasks.md` is a Phase 0 snapshot.** Its
  last line still says items 2 to 16 remain not tested, although later phases
  recorded their results elsewhere. The table was not updated and this record
  does not edit it, so a reader of that file alone can be misled.
* **No evidence anchor exists**, so the process telemetry of the sessions that
  produced this campaign cannot be recomputed.

## Deferred work

The deferred items are relocated, not completed. The repository owner accepted
that reading at the Phase B reply.

* **The follow-up backlog now lives in
  `docs/specs/parked/ai-portability-followups.md`.** The campaign moved 19 items
  there verbatim, plus two documentation errors found during the push. At
  `origin/main` `f321bc25` the file holds 20 unchecked items (the original 19 and
  one item split out of the second documentation error, the decision on the `ai`
  commit scope) and 2 checked items (the two documentation errors in the
  Validate, Merge and Deploy agent, corrected by `f321bc25`). At `87c2b557` it
  held 21 unchecked items.
* **The specification directory is not archived yet.** See Spec disposition.
* **`notes.md` gained a two-line addendum in `0d0d9811`.** It points to the parked
  specification and corrects the earlier statement that the audit was expected
  to return `HOLD`. That statement described the state before the move.
* **No evidence anchor was generated.** See Evidence anchors.

## Spec disposition

`archive` for `docs/specs/active/ai-portability/`, because every phase task and
the push gate are checked, and the follow-up backlog is tracked in the parked
specification.

The move has **not happened**. The directory is still under `docs/specs/active/`
when this record is written, so this is a decision, not a completed state. The
owner asked for the move and the reference updates to be a separate commit after
the worktree is removed, following the worktree lifecycle in `docs/specs/README.md`.

One consequence to check first: the audit script resolves a slug only under
`docs/specs/active/<slug>` and `docs/specs/archive/<slug>`. The README names the
archive directory with a date prefix, so after the move a re-audit would report
the spec sources as `not_checked` unless the directory keeps the bare slug.

## Worktree disposition

`pending`, decided at `pending`.

The owner answered `remove` at the Phase B reply, after reading the audit output.
That is an intention, not a disposition: no removal has happened and no decision
time exists yet. Removal is gated on all of the following:

* This record is on `origin/main`.
* The recovery capsule is written outside the worktree.
* The six values below are re-observed immediately before removal and match.
* Occupancy is re-observed with `lsof`, and no process other than the close-out
  session holds the worktree as its working directory.
* The owner states at that time that no other session uses the worktree.

At the Phase B reply the owner reported that, apart from the close-out session
and an engineer session they will close before removal, no session of theirs uses
the worktree; that the two Codex daemons are not conversations they use; that all
VS Code sidebar processes run with the main working tree as their working
directory; and that a paused conversation of the senses-taxonomy campaign stays
paused until the push completes.

| Freshness value | Observed at the decision |
|-----------------|--------------------------|
| branch tip | `pending` |
| ahead of `origin/main` | `pending` |
| behind `origin/main` | `pending` |
| dirty count | `pending` |
| ignored artifact set | `pending` |
| path identity | `pending` |

For reference, the observation at the close-out audit (2026-10-13T15:37Z): branch
tip `87c2b55779377852bb0c262d95441d7c0bedba95`, ahead 0, behind 6, dirty 0,
ignored artifact set 6, path identity `canonical` with directory
`ttr-ai-portability-worktree` and branch `feat/ai-portability`. Stashes: 0. No
rebase, merge, cherry-pick, or revert was in progress.

### Gates at the close-out audit

The audit script `scripts/campaign-closeout-audit.sh` ran three times against the
campaign worktree.

| Unhandled-work source | Run 1, 2026-10-12T22:20Z | Run 2, 2026-10-13T07:48Z | Run 3, 2026-10-13T15:37Z | Final |
|-----------------------|--------------------------|--------------------------|--------------------------|-------|
| `tasks.md` unchecked items | 19 | 0 | 0 | 0 |
| Deferred section of `changes-log.md` and `proposal.md` | 0 | 0 | 0 | 0 |
| Legacy tracking plans | 0 | 0 | 0 | 0 |
| Work-marker words on lines added in the commit range | 0 | 7 | 0, plus 7 on uncovered commits | 0, by attribution review |
| Open GitHub issues naming the slug | 0 | 1 | 0, excluding `daily-review` | 0, by attribution review |
| Script verdict | `HOLD` | `HOLD` | `UNDETERMINED` | not applicable |

Run 1 used the range to `6b404ea3` and counted the 19 items that the campaign
then moved. Run 2 used one span from the campaign base to `87c2b557`, which
swallowed ten commits of another campaign. Run 3 used the multi-range script
from `f321bc25`: one range per push plus the full range, so the script itself
lists commits no range covers. The two ranges were supplied by the owner. The
close-out agent confirmed that the base of segment 2 is the parent of its first
commit and that the base of segment 1 is the campaign base.

Run 3 stopped at `UNDETERMINED` because ten commits in the full range belong to
no segment, and two of them add work-marker words. The attribution is below. The
script verdict is not rewritten by this record.

| Commit | Date | Subject | Campaign | Evidence |
|--------|------|---------|----------|----------|
| `936ed076` | 2026-10-13 | feat(scraper): move category definitions to taxonomy.md and narrow senses | senses-taxonomy | listed in that campaign's record |
| `25b28dfa` | 2026-10-13 | fix(web): rewrite senses descriptions to match new definition | senses-taxonomy | listed in that record |
| `14657618` | 2026-10-13 | docs(skills): document removal of the senses fallback | senses-taxonomy | listed in that record |
| `e9497dc0` | 2026-10-13 | fix(scraper): stop inviting empty categories and alias performance | senses-taxonomy | listed in that record |
| `d28d7f5f` | 2026-10-13 | fix(web): broaden geopolitics description to society and politics | senses-taxonomy | listed in that record |
| `e17cf4d9` | 2026-10-13 | docs(skills): record event_form alias and empty-category lessons | senses-taxonomy | listed in that record |
| `6acae937` | 2026-10-13 | docs(agents): add senses-taxonomy campaign close-out record | senses-taxonomy | that record's own commit, named in it; 1 marker line |
| `701b559a` | 2026-10-13 | docs(agents): record senses-taxonomy worktree retirement | senses-taxonomy | subject; child of `6acae937` |
| `4ac6bd83` | 2026-10-13 | docs(agents): align category sync rule with taxonomy.md | senses-taxonomy (inferred) | subject and touched files only; not named in that record |
| `8f09543d` | 2026-10-13 | docs(agents): record senses-taxonomy close-out lessons in campaign-closer | senses-taxonomy | subject; 6 marker lines |

Session contention, observed at 2026-10-13T15:37Z. The script returned
`SOLE_OWNER (CLI-scope)`: at the first audit, of 35 Copilot session-state
directories only two held a lock, and neither resolves to this worktree. The close-out agent additionally
observed, with `lsof` and the Claude session registry, an idle engineer session
and its shell, two `codex app-server` daemon processes, and the close-out
session itself, all with this worktree as working directory. Those observations
make the result `UNDETERMINED` in the close-out agent's reading. Only Copilot CLI
sessions are detectable; Claude Code, VS Code chat, and Codex sessions are not.

## Ignored artifacts and handling

All six ignored entries are caches or tool output that a fresh run regenerates,
so none needs preserving. The worktree has no ignored file under `tmp/`. The set
was observed between 2026-10-13T16:18Z and 16:22Z, after the test run, and is the
same set as at the first audit. The
preflight is repeated immediately before removal, and any difference stops the
removal.

| Artifact | Handling | SHA-256 |
|----------|----------|---------|
| `.pytest_cache/` | `disposable` | not applicable (directory) |
| `scripts/__pycache__/` | `disposable` | not applicable (directory) |
| `scripts/claude/__pycache__/` | `disposable` | not applicable (directory) |
| `scripts/claude/tests/__pycache__/` | `disposable` | not applicable (directory) |
| `scripts/tests/__pycache__/` | `disposable` | not applicable (directory) |
| `supabase/.temp/cli-latest` (8 bytes, inside the ignored directory `supabase/.temp/`) | `disposable` | `008368133cc42a3c2209c6e9dbf2612e56f28a1534b4c60383ec6403ea4d556f` |

## Evidence anchors

None. The repository owner decided on 2026-10-13 not to anchor any session slice
and specified none, and the close-out agent selected none. No anchor and no
ledger were generated, so this is listed as unfinished work. Seven sessions are
known to have taken part in the campaign; the generator reads local transcripts
only, so when slice boundaries are specified, one anchor per slice can be added
in a later commit, listed separately and never summed.
