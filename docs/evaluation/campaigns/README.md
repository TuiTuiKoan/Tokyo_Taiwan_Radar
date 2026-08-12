---
title: Campaign Close-out Records
description: When a campaign close-out is required, the ten sections every record must carry, and the identity, freshness, and correction contracts that govern them
ms.date: 2026-08-11
ms.topic: reference
keywords:
  - campaign close-out
  - worktree disposition
  - evidence anchor
  - governance
estimated_reading_time: 10
---

## Scope

This directory holds close-out records for finished campaigns. A campaign is a unit of
work large enough to outlive a single session, usually because it owned a dedicated
worktree, mutated production data, or moved a specification forward.

A record answers one question: what is true now, and what proves it. It is written by
hand. The only generated companion is the process telemetry anchor described under
[Evidence anchors](#evidence-anchors), which freezes measurable session facts so the
prose cannot drift away from them.

Three artifacts share this directory and must not be confused:

| Artifact | Produced by | Mutable |
|----------|-------------|---------|
| Close-out record | A person, following this guide | Yes, through a correction |
| Process telemetry anchor and its ledger | `.github/skills/session-analytics/oneoff_campaign_anchor.py` | No |
| Session statistics | `.github/skills/session-analytics/analyze.py` | Not stored here |

## When a close-out is required

Write one when any of the following is true:

* The work owned a dedicated worktree that is about to be removed or retained.
* Production data was mutated outside the normal scheduled pipeline.
* A specification under `docs/specs/active/` changes disposition as a result.
* The work spanned more than one session, so no single commit message describes it.
* A published record turns out to be wrong and needs correction.

## When a close-out is not required

Skip it when the change is fully described by its own commit, and none of the triggers
above applies. Routine scheduled runs, single-session fixes, isolated documentation
edits, and dependency bumps do not earn a record. Writing one anyway dilutes the corpus
and makes the real records harder to find.

## The ten required sections

Every record carries all ten. A section with nothing to report says `None` rather than
disappearing, so a reader can tell silence apart from omission.

| Section | Must contain |
|---------|--------------|
| Outcome | The finished condition in production, not the activity log |
| Delivered commits | Every shipped commit, each proven to be an ancestor of `origin/main` |
| Verification | One row per check, each `PASS`, `FAIL`, or `NOT TESTED`, with an evidence summary |
| Correction and supersession | The wrong claim, why it was wrong, and the correcting commit, or `None` |
| Known risks | Residual risk accepted at publication, or `None` |
| Deferred work | Work consciously not done, and where it is now tracked, or `None` |
| Spec disposition | One of `active`, `parked`, `archive`, `none`, with the reason |
| Worktree disposition | One of `remove`, `retain`, `already_removed`, with the decision timestamp and the six freshness values |
| Ignored artifacts and handling | One of `duplicated`, `exported`, `disposable`, `retain_worktree` per artifact, with a digest |
| Evidence anchors | Every telemetry anchor and ledger, one entry per session slice |

`NOT TESTED` is a legitimate verification result and is preferred over a `PASS` that
nobody produced evidence for. Pair it with the residual risk it creates.

### Copyable skeleton

```markdown
---
title: <Campaign> Close-out
description: <one line stating what shipped and what this record proves>
ms.date: YYYY-MM-DD
ms.topic: reference
keywords:
  - <keyword>
estimated_reading_time: <minutes>
---

## Outcome

<What is true in production now. Describe the finished condition, not the steps taken.>

## Delivered commits

| Commit | Change | Ancestor of `origin/main` |
|--------|--------|---------------------------|
| `<sha>` | <what it changed> | yes |

## Verification

| Check | Result | Evidence |
|-------|--------|----------|
| <check> | PASS | <summary of the evidence, not a restatement of the check> |
| <check> | NOT TESTED | <why it was not run, and the residual risk accepted> |

## Correction and supersession

<None.>

<Or: the earlier claim, why it was wrong, the commit that corrected it, and the
reciprocal pointer if a separate record supersedes this one.>

## Known risks

<None, or the residual risk accepted at publication.>

## Deferred work

<None, or the work not done and the specification or issue now tracking it.>

## Spec disposition

`<active | parked | archive | none>` for `docs/specs/active/<slug>/`, because <reason>.

## Worktree disposition

`<remove | retain | already_removed>`, decided at `<YYYY-MM-DDTHH:MM:SSZ>`.

| Freshness value | Observed at the decision |
|-----------------|--------------------------|
| branch tip | `<sha>` |
| ahead of `origin/main` | `<n>` |
| behind `origin/main` | `<n>` |
| dirty count | `<n>` |
| ignored artifact set | `<count, or none>` |
| path identity | `<canonical, divergent, or external>`, directory `ttr-<slug>-worktree`, branch `feat/<slug>` |

## Ignored artifacts and handling

| Artifact | Handling | SHA-256 |
|----------|----------|---------|
| `tmp/<file>` | `duplicated` | `<digest>` |

## Evidence anchors

* `docs/evaluation/campaigns/<slug>.md`, ledger `ledger/<slug>-<digest>.jsonl`
* <One entry per session slice. Slices are listed, never merged into one figure.>
```

## Contracts

Six contracts turn the sections above from a template into something a reviewer can
falsify. The first three exist because a published record already failed them. The last
three exist because a retirement decision would otherwise be allowed to pass on evidence
that nobody gathered.

### Identity

A worktree is never identified by its directory name alone. Basenames are unique today,
yet they hide two divergences, and the two are independent of each other.

The first is lexical. A worktree registered through a parent directory whose
capitalization differs from the real one resolves to the same inode on a case-insensitive
filesystem, so the registered string and the physical path name one directory under two
names. Only the registered string preserves that difference.

The second is placement. A worktree can be registered outside the repository root
entirely, as a sibling of the root rather than a child, while its registered string and
its physical path agree perfectly. Comparing registered against physical calls that
indistinguishable from a worktree sitting inside the repository.

Both axes are therefore required, and together they yield three path classes:

| Path class | Physical path | Registered string |
|------------|---------------|-------------------|
| `canonical` | under the repository root | equals the physical path |
| `divergent` | under the repository root | differs from the physical path |
| `external` | outside the repository root | either |

Placement is decided first: a worktree outside the root is `external` whether or not its
two strings agree.

Each class carries a different obligation. `canonical` needs nothing beyond the verdict.
`divergent` means one directory under two names, so both strings are quoted when observed
and neither is normalized away, because automation keyed on the registered string splits
from automation keyed on the physical one. `external` breaks two root-relative habits: the
repository's `.git/info/exclude` entry that hides nested worktrees does not apply to it, so
there is no exclude line to check or to remove, and the post-removal residue check below
tests a directory relative to the repository root and therefore reports `directory=gone`
for an external directory that is still present. Point both at the external path
explicitly, and enumerate its ignored artifacts from inside it.

Record four things: the registered path, the resolved physical path, the resulting path
class, and the branch. Store the path class verdict, the directory, and the branch in the
record itself. The directory is repository-relative for `canonical` and `divergent`, and
is the bare directory name for `external`, which has no repository-relative form. Do not
paste the absolute home path into the document, because the verdict is the part a reader
needs and the raw path is not. The two raw paths stay observations: a reviewer re-derives
them with the commands below instead of reading them out of the record.

```bash
# Registered paths. Parse with sed, not awk: the repository path contains spaces,
# so a field-splitting parser truncates every path at the first space.
git worktree list --porcelain | sed -n 's/^worktree //p'

# Canonical repository root, resolved physically. The first entry of `git worktree list`
# is always the main worktree, so this resolves the same root from inside any worktree.
# Use /bin/pwd, not the shell builtin: zsh's builtin re-derives the path from getcwd()
# and so reports the real capitalization, while the bash and sh builtins hand back the
# string you typed. A builtin therefore reports a `divergent` worktree as `external`.
MAIN=$( git worktree list --porcelain | sed -n '1s/^worktree //p' )
ROOT=$( cd "$( git -C "$MAIN" rev-parse --show-toplevel )" && /bin/pwd -P )

# Physical path and path class for one registered path. The "$ROOT"/ form is required:
# a bare "$ROOT"* would also match a sibling whose name merely starts with the root's.
WT='<registered-path>'
PHYS=$( cd "$WT" && /bin/pwd -P )
case "$PHYS" in
  "$ROOT"|"$ROOT"/*)
    [ "$WT" = "$PHYS" ] && echo 'class=canonical' || echo 'class=divergent' ;;
  *)
    echo 'class=external' ;;
esac

# Branch.
git -C "$WT" rev-parse --abbrev-ref HEAD
```

Inventory itself is out of scope here. `workstream-tracking` is the single authority for
which worktrees exist. A close-out quotes its snapshot and the time that snapshot was
observed. It never builds a second mutable inventory, because two inventories disagree
the moment either one is edited.

### Freshness

A disposition is a statement about a moment, so it is only valid while that moment holds.
Bind every disposition to six observed values:

1. Branch tip SHA.
2. Commits ahead of `origin/main`.
3. Commits behind `origin/main`.
4. Dirty file count.
5. Ignored artifact set.
6. Registered path and resolved physical path.

If any of the six differs when the disposition is acted on, the disposition is `STALE`.
Re-observe and re-decide. Never carry an earlier `PASS` forward into a removal.

```bash
WT='<registered-path>'
git -C "$WT" fetch origin main --quiet
git -C "$WT" rev-parse HEAD                                     # 1. tip
git -C "$WT" rev-list --left-right --count HEAD...origin/main   # 2. ahead  3. behind
git -C "$WT" status --porcelain | wc -l                         # 4. dirty count
git -C "$WT" status --porcelain --ignored | grep '^!!'          # 5. ignored set
( cd "$WT" && /bin/pwd -P )                                     # 6. physical path
```

Every commit listed under Delivered commits is proven, not assumed:

```bash
git merge-base --is-ancestor '<sha>' origin/main && echo ANCESTOR || echo NOT_ANCESTOR
```

### Correction

A published record that turns out to be wrong is never silently overwritten and never
deleted. Choose one of two repairs:

* Amend in place by adding to the Correction and supersession section. Name the claim
  that was wrong, explain why it was wrong, and cite the commit that corrected the
  underlying defect. The record stays authoritative.
* Publish a replacement record. The new record states what it supersedes, and the old
  record gains the reciprocal `superseded_by` pointer. Both remain in the directory.

Either way a reader must be able to determine which version is authoritative without
reading the repository history.

```bash
grep -rn 'supersedes\|superseded_by' docs/evaluation/campaigns/
```

### Unhandled work

A campaign is not finished because its last commit landed. It is finished when nothing is
still waiting on it. Five sources are consulted before a worktree is proposed for
retirement, and each one reports a number or reports `not_checked`:

1. Unchecked items in `docs/specs/active/<slug>/tasks.md`.
2. Deferred entries in that spec's `changes-log.md` and `proposal.md`.
3. Unfinished items in `.copilot-tracking/plans/*.md` inside the worktree.
4. `TODO` and `FIXME` on lines **added** by the campaign's own commits.
5. Open GitHub issues naming the slug.

`not_checked` and `0` are different claims. `0` means the source was read and held nothing;
`not_checked` means it was never read. Only the first supports retirement, so a verdict of
`RETIRE_CANDIDATE` requires all five to be numbers.

Source 4 needs a commit range, and the range is `<base>..<head>` where `base` is the
`origin/main` tip **before** the campaign was pushed. The three-dot `origin/main...HEAD`
form is refused: after the push `HEAD` equals `origin/main`, so that form is empty for
every campaign that actually shipped and would report a false zero. When the base SHA was
not handed over, source 4 reports `not_checked` rather than falling back.

### Session contention

A worktree is only retired by the session that owns it. Ownership is decided from the
Copilot CLI session state, one level deep, and conservatively:

* A session holding no `inuse.*.lock` is not counted.
* A session whose recorded root resolves to the target worktree, holding a lock, with a
  recently modified transcript, is `CONTENDED`.
* The same session with a quiet transcript is `UNDETERMINED`, never cleared. A lock that
  has gone quiet is an open but idle session, not a finished one.
* The session performing the audit excludes itself.

Two traps are worth naming, because both were measured on this machine rather than
imagined.

A process id is not a liveness signal. Copilot CLI sessions share one Code Helper process,
so unrelated sessions legitimately record the same pid; three did. Any `kill -0` style
check therefore marks strangers as contenders, and no such check belongs in this gate.

A recorded root may differ from the physical path only in capitalization, which on a
case-insensitive filesystem is the same directory. Resolve with `/bin/pwd -P` before
comparing. When a recorded root cannot be resolved at all, an inexact match is a doubt and
yields `UNDETERMINED`; it is never treated as a clearance.

The coverage boundary is stated in every report. **Only Copilot CLI sessions are visible.**
VS Code chat sessions are not: every workspaceStorage entry pointing at this project
resolves to the repository root rather than to a worktree, so it cannot say who holds what.
A clear result is therefore recorded as `SOLE_OWNER (CLI-scope)`, and the user confirmation
gate is the backstop. Undetectable is not the same as absent.

`UNDETERMINED` means stop and ask a person. It is neither a pass nor a permanent block; the
missing input is supplied, or the user confirms, and the gate is re-run.

### Recovery capsule

Removal destroys the ability to observe the six freshness values ever again. Before the
removal command runs, they are written to a capsule **outside the worktree** — a capsule
stored inside it disappears with it. The capsule carries the six values, the decision
timestamp, the repository-relative path of the close-out record, the registered path and
branch, and each ignored artifact's handling and digest.

The capsule exists to make one specific failure recoverable: removal succeeds and the
disposition backfill is then interrupted, leaving the worktree gone and the record still
saying `pending`. Backfill is therefore idempotent and resumable. Re-running it means
reading the six values from the capsule, editing only that one table block in the record,
staging that single path, committing, and pushing. A permanent `pending` is not an
acceptable end state.

## Evidence anchors

The anchor generator freezes process telemetry for one session slice and writes a ledger
that makes every published number recomputable. Treat its output as immutable evidence:
never hand-edit an anchor or a ledger.

```bash
python3 .github/skills/session-analytics/oneoff_campaign_anchor.py \
  --campaign '<slug>' \
  --session-slice '<session-uuid>:<start-uuid>:<end-exclusive-uuid>' \
  --outcome-ref '<sha>' \
  --record-output 'docs/evaluation/campaigns/<slug>.md' \
  --transcripts-dir '<copilot-chat-transcripts-dir>'
```

The generator accepts `--session-slice` exactly once, by design: one anchor covers one
slice. A campaign that spans several sessions therefore produces several anchors. List
each of them in the Evidence anchors section and leave them separate. Do not sum turns or
average tool counts across slices, and do not build a rollup script to do it. An aggregate
that nobody can recompute from a single ledger is not evidence.

## Grandfathered records

`2026-08-03-organizer-type-authority` predates this guide. It is a process telemetry
reference only, kept for its ledger and its recompute procedure. It is exempt from the ten
sections, and it is not upgraded in place or regenerated. Leave it byte-identical.

## Cleanup checklist

Removal is the last step, and it is irreversible for anything Git does not track. Work
through the list in order.

Before removal:

1. Re-observe all six freshness values. Any change since the disposition means `STALE`.
2. Confirm the close-out record itself has landed on `origin/main`. A record that only
   exists inside the worktree disappears with it.
3. Clear the unhandled work and session contention gates above. A `not_checked` source and
   an `UNDETERMINED` contention verdict both stop the removal.
4. Run the ignored artifact preflight below and resolve every finding.
5. Write the recovery capsule, outside the worktree.

```bash
WT='<registered-path>'

# Ignored and untracked payloads that git worktree remove would delete with the directory.
git -C "$WT" status --porcelain --ignored | grep '^!!'
find "$WT/tmp" -type f 2>/dev/null

# For each candidate, prove another copy exists before calling it disposable.
shasum -a 256 "$WT/tmp/<file>"
find . -name '<file>' -not -path "$WT/*"
```

Campaign baselines and rollback snapshots are written under `tmp/` and are frequently the
only copy on the machine. Classify each artifact as `duplicated`, `exported`,
`disposable`, or `retain_worktree`, record the digest, and only then continue.

Removal follows the mechanics in `.github/instructions/git.instructions.md`. Never use
`--force` and never use `git branch -D`.

After removal, verify that nothing survived. A successful `git worktree remove` does not
guarantee an empty parent directory. The checks below take the observed directory name and
branch rather than deriving them from the slug: `ttr-<slug>-worktree` and `feat/<slug>` are
the convention, not a guarantee, and this repository already holds worktrees that follow
neither. For an `external` worktree, `DIR` is an absolute path outside the repository root,
and the exclude check does not apply because no exclude line was ever added.

```bash
DIR='<observed-directory>'      # repository-relative, or absolute when external
BRANCH='<observed-branch>'

git worktree list --porcelain | sed -n 's/^worktree //p' | grep -F "$DIR" \
  || echo 'unregistered=ok'
git rev-parse --verify --quiet "refs/heads/$BRANCH" >/dev/null \
  && echo 'branch=STILL PRESENT' || echo 'branch=deleted'
grep -qF "$DIR/" .git/info/exclude \
  && echo 'exclude=STILL PRESENT' || echo 'exclude=removed'
[ -d "$DIR" ] && echo 'directory=RESIDUE' || echo 'directory=gone'
```

When a residual directory is found, prove it holds nothing unique before anyone deletes
it. Every file must be byte-identical to `origin/main`, and the directory must contain no
ignored artifacts:

```bash
find "$DIR" -type f | while IFS= read -r f; do
  rel=${f#"$DIR"/}
  if [ "$(git hash-object "$f")" = "$(git rev-parse "origin/main:$rel" 2>/dev/null)" ]; then
    echo "identical $rel"
  else
    echo "UNIQUE    $rel"
  fi
done
```

A single `UNIQUE` line stops the deletion and returns the case to a person.

Phase A of this checklist is automated by `scripts/campaign-closeout-audit.sh`, which is
read-only and exits `0` for `RETIRE_CANDIDATE`, `10` for `HOLD`, and `20` for
`UNDETERMINED`. It is a single-worktree probe and not an inventory; `workstream-tracking`
remains the only authority for which worktrees exist. It never fetches, so ahead and behind
are relative to the local `origin/main` ref and the caller fetches first.

## Privacy boundary

Records describe outcomes and carry digests. They do not carry conversation material.

Never include verbatim conversation text, prompts, tool arguments, or raw request and
response payloads. Never include per-request usage counters or raw billing figures. Never
include absolute paths from a personal machine: use the path class verdict together with
the repository-relative directory, or with the bare directory name when the class is
`external`.

Model identifiers and usage figures sit on a line worth drawing precisely, because a future
per-slice metrics index is expected to cross it in one direction only. A model alias, and
token or cost figures **aggregated over a whole session slice**, are outcome facts about
the campaign and are permitted. A per-request counter is not, because a sequence of
per-request figures reconstructs the shape of the conversation that produced it. The
aggregate is the safe form; the sequence is not.

Any such aggregate is reported as measured, never derived. A figure obtained by multiplying
tokens by a published rate is not evidence: on this project's own measurements, cached
input dominated the token count and the request multiplier varied by more than tenfold
within a single session. When a measured figure is unavailable the field is `null`, and
figures are never compared across clients.

Digests, commit SHAs, counts, and durations are safe, because they identify evidence
without reproducing it.

## What the retrospective cases proved

Each contract above was derived from a record that already failed it. The three cases were
reviewed read-only; none of the original records was modified.

An in-place correction is sufficient, and it must name the defect. The authenticated
intake close-out first published at `e3135b90` reported the visual work complete. The new
utility resolved to the same painted value as the rule it replaced, so the change was
invisible. The repair added a Correction section naming the false claim and citing
`dc1d2387`, the commit that fixed the controlling surface, with the lesson recorded in
`0c5b12a3`. The original record stayed authoritative, which is why the template offers
amendment as the first option rather than forcing a replacement record.

A prospective declaration is not a disposition. The Eslite record's first version at
`0a1a8c8e` stated that the worktree "may therefore be removed after this report lands".
Two further commits, `1c81270a` and `37aaad40`, then landed on the same record, so the
state described at declaration time no longer held when removal actually happened. The
final version instead records a completed removal, the state observed at that decision,
and the SHA-256 of each preserved ignored artifact. This is the reason the template
demands a decision timestamp and the six freshness values rather than an intention.

Cleanup is not finished when `git worktree remove` returns, and an observation without a
timestamp is not usable. A read-only check of `ttr-admin-qa-cleanup-worktree`, made between
`2026-08-11T12:05Z` and `2026-08-11T13:04Z`, found the worktree unregistered, its branch
deleted, and its exclude entry removed, yet the directory still present with five files.
That window is approximate and was reconstructed afterwards, because the check was
read-only and left nothing behind to timestamp. Its upper bound is the branch reflog entry
that recreated `feat/admin-qa-cleanup` at `2026-08-11T13:04:26Z`, which the check preceded;
its lower bound follows from the re-check below, which happened less than an hour later.
Having to reconstruct a bound rather than quote a recorded value is exactly the failure
this contract now prevents. Every file was byte-identical to `origin/main` and no ignored
artifacts remained, so the residue was inert. The authenticated intake record describes the
same shape at another path, where reconciliation found an unregistered four-file skeleton.
Two independent campaigns produced the identical leftover, which is why the post-removal
verification above exists.

That same case then demonstrated the freshness contract on itself. A re-check at
`2026-08-11T13:05:47Z`, within the same working session, found the directory re-registered
by a parallel session, the branch restored at the current `origin/main` tip, the exclude
entry back in place, and a full checkout of more than a thousand files where the five-file
skeleton had been. Acting on the first observation would have deleted an active worktree.
Re-observe immediately before acting, every time, and write the observation time into the
record.
