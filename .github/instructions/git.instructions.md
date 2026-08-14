---
applyTo: ".github/**"
---

# Git Branching — Coding Instructions

## Branch strategy

Tokyo Taiwan Radar is **trunk-based**: `main` is the single integration branch. Most changes are committed and pushed directly to `main` after the Validate/Merge/Deploy (V-M-D) validation cycle. Short-lived branches are an **isolation option**, not a mandatory gate.

| Branch | Purpose |
|--------|---------|
| `main` | Production trunk — Vercel deploys from here; daily scraper CI runs here; validated changes push straight here |
| `feat/<topic>` | Optional short-lived isolation for a large / multi-session or parallel-churn-prone feature (e.g. `feat/source-connpass`); rebased onto `origin/main` and fast-forward merged back |
| `fix/<topic>` | Optional short-lived isolation for a bug fix (e.g. `fix/tcc-date-extraction`) |
| `chore/<topic>` | Optional short-lived isolation for non-functional changes (deps, config, CI tweaks) |

## Agent workflow

**Default — trunk-based, direct fast-forward:**

1. Confirm the worktree with the user (see the worktree confirmation gate below), then commit atomically with a descriptive message (see commit message conventions).
2. Run the V-M-D validation cycle (conflict check → rebase → build/lint → token/i18n gates).
3. After **explicit user approval**, `git push origin main` (fast-forward). There is no pull-request gate.

**Isolation exception — short-lived branch / worktree:**

Use for large / multi-session features, parallel-session-churn-prone work, or shared-list edits (e.g. the `SCRAPERS` list). See the worktree section below for mechanics.

1. Develop on `feat/<topic>` (in a worktree when the work spans sessions).
2. Rebase onto `origin/main` to keep history linear.
3. Fast-forward merge into `main` via V-M-D (`git push origin HEAD:main`). Merge within ~24h to avoid `SCRAPERS`-list conflicts.

**Review & safety:**

- "Review" happens via the **Architect agent handoff before implementation** and **V-M-D validation before push** — not a GitHub pull-request review gate.
- Never `git merge --no-ff` into `main`: a two-parent merge makes the remote secret hook rescan full-reachable history and can flag an allowlisted blob that a linear fast-forward push passes. Never `--no-verify`.
- `main` is guarded only by these agent gates plus local hooks; treat a direct push as privileged — always get user approval first.

## Worktree confirmation gate

> Applies to **every agent that modifies functional code** — Architect, Engineer, Tester, Scraper Expert, Designer, Researcher, V-M-D, and any future agent that writes to `scraper/`, `web/`, `supabase/` or `scripts/`.

**The gate** — before starting any implementation work, ask the user which worktree to use and wait for an explicit answer. Never infer it, and never skip the question because the change looks small.

**The main working directory is governance-only** — the repo root (`Tokyo Taiwan Radar`, branch `main`) is reserved for planning, auditing, documentation, spec maintenance and status reconciliation. Do not implement features there, whatever the size of the change.

**Why** — parallel sessions (other VS Code windows, V-M-D, cron) run `git stash` / `git clean` in the main working directory and silently discard uncommitted WIP as unrelated work before a deploy. On 2026-08-08 a four-day batch of agent lessons (11 files, +550/−134) was found still sitting uncommitted there.

**Running the gate:**

1. Run `git worktree list --porcelain` and present the current worktrees to the user together with your recommendation.
2. User names an existing worktree → `cd` into it, then verify the path and branch match.
3. User asks for a new one → create it per the state matrix below and add the `.git/info/exclude` line.
4. User explicitly chooses the main working directory → comply, but state the stash-trampling risk first.

## Isolated worktree for large / multi-session features

> **Single source of truth** for worktree mechanics. The Architect / Engineer / V-M-D agents reference this section for the "how"; they own the "when".

**When** — every implementation task runs in a worktree confirmed with the user through the gate above. A feature that earns a `docs/specs/active/<slug>/` entry (multi-session, multi-file, or a new module) gets its own dedicated worktree; a smaller change goes to whichever existing worktree the user names. The main working directory is never an option for implementation. Spec-to-worktree coupling applies **prospectively** to specs created / re-activated after this rule; existing specs are grandfathered.

**Why** — parallel sessions (other VS Code windows, V-M-D, cron) run `git stash` / `git clean` and can silently destroy uncommitted WIP in the main working dir. A linked worktree has its own working dir they cannot touch.

**Naming** — `ttr-<slug>-worktree` at the repo root, on branch `feat/<slug>` (matches the existing `ttr-v8-worktree`). Derive the path from the spec `slug`; do not persist it in spec frontmatter. Verify reality each session with `git worktree list --porcelain`.

### Create — state matrix (choose by current git state)

| State | Command |
|-------|---------|
| branch missing | `git worktree add ttr-<slug>-worktree -b feat/<slug>` |
| branch exists, no worktree | `git worktree add ttr-<slug>-worktree feat/<slug>` (no `-b`) |
| worktree already mounted | skip `add`; `cd ttr-<slug>-worktree`; verify path + branch match |
| path exists but NOT a registered worktree | **STOP** — report and ask the user (never `-f`) |

Then hide the worktree dir from the main repo (idempotent, local-only, not committed):

```bash
grep -qxF 'ttr-<slug>-worktree/' .git/info/exclude || echo 'ttr-<slug>-worktree/' >> .git/info/exclude
```

Without this line the main repo shows the worktree as untracked and a careless `git add -A` in a parallel session sweeps it in.

### Work inside the worktree

- All feature commits happen inside `ttr-<slug>-worktree/` on `feat/<slug>`. `git add -A` is safe INSIDE the worktree (isolated); in the MAIN repo with parallel sessions still use selective `git add <path>`.
- Before any local preview/build **or** rebase, the working tree must be clean (`git status --porcelain` empty). If dirty, commit — **never `git stash`** (a repo-wide stash reintroduces the very trampling this isolates against).
- A linked worktree freezes its base at creation time. Before previewing, align to latest main: `cd ttr-<slug>-worktree && git fetch origin && git rebase origin/main` — otherwise localhost shows a behind-by-N snapshot.

### Merge back

Rebase onto `origin/main` to keep history linear, then hand to V-M-D, which pushes per the trunk-based direct fast-forward flow in the Branch strategy / Agent workflow sections above. Never `git merge --no-ff` into `main` (see the Engineer SKILL gitleaks note); never `--no-verify`. Merge within ~24h to avoid `SCRAPERS`-list conflicts.

### Cleanup (all STOP conditions must pass first)

Verify: worktree clean (no uncommitted) · no unpushed commits (feature HEAD is an ancestor of the target remote branch) · no rebase/merge in progress. Then:

```bash
git worktree remove ttr-<slug>-worktree     # never --force
git branch -d feat/<slug>                    # never -D
# then reconcile .git/info/exclude — see below, never hand-delete a single line
```

If any check fails → STOP, report, do not force. `git worktree prune` is safe — it drops only stale records, never branches or commits.

#### Reconciling `.git/info/exclude` (never blind-delete a line)

Every available editor rewrites the whole file: `grep -v … > tmp && mv`, and `sed -i` too — on macOS `sed -i` replaces the inode, so it is not in-place. `flock` is not installed by default. There is therefore **no race-free single-line delete**, and a blind rewrite silently drops entries another session appended between your read and your write.

So do not delete a line. Reconcile the whole `ttr-*-worktree/` block against live worktrees — that is idempotent and convergent, so concurrent sessions heal each other instead of clobbering:

```bash
root=$(git rev-parse --show-toplevel) && cd "$root" || exit 1
want=$(git worktree list --porcelain | sed -n 's|^worktree ||p' | while IFS= read -r p; do
  phys=$(cd "$p" 2>/dev/null && pwd -P) || continue
  case "$phys" in "$root"/*) basename "$phys" | sed 's|$|/|' ;; esac
done | sort -u)
{ grep -vE '^ttr-.*-worktree/$' .git/info/exclude; printf '%s\n' "$want"; } > .git/info/exclude.tmp \
  && mv .git/info/exclude.tmp .git/info/exclude
```

Then **verify after writing** — the race cannot be eliminated, only detected:

```bash
comm -23 <(printf '%s\n' "$want") <(grep -E '^ttr-.*-worktree/$' .git/info/exclude | sort -u)
```

Empty output = converged. Any output = another session clobbered you; just re-run the reconcile.

Worktrees registered outside the repository root (for example `<repo>.worktrees/<slug>`) never appear in the main tree's untracked list, so they need no entry and must not be added.

Incident 2026-08-14: a cleanup session ran `grep -vxF 'ttr-auth-smoke-worktree/' .git/info/exclude > tmp && mv tmp …`; a parallel session had appended a different entry seconds earlier, and that entry was silently lost, re-exposing a live worktree as untracked.

Two further preconditions apply before a campaign worktree is removed: the campaign's close-out record must already be on `origin/main` (a record living only inside the worktree is deleted with it), and the recovery capsule holding the six freshness values must already be written outside the worktree (after removal those values can never be observed again). The full ordered checklist — unhandled-work and session-contention gates, ignored-artifact preflight, and the post-removal residue verification — lives in [docs/evaluation/campaigns/README.md](../../docs/evaluation/campaigns/README.md) § Cleanup checklist and is not duplicated here.

## State persistence for agents

Agents save in-progress work to `.copilot-tracking/` (gitignored):

```
.copilot-tracking/
  research/
    sources/<source-name>.md    # Researcher output
    research-log.md
  plans/
    <topic>.md                  # Architect plans
```

This directory is **not committed** — it is local scratch space for agent coordination.

## Commit message conventions

Follow Conventional Commits:

```
<type>(<scope>): <summary>

[optional body]
```

Types: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`  
Scopes: `scraper`, `web`, `db`, `ci`, `agents`

Examples:
```
feat(scraper): add Connpass source scraper
fix(scraper): correct TCC date extraction tier order
chore(agents): update Tester handoff labels
feat(web): add art and lecture category filters
```
