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

1. Work on `main` in the main working directory; commit atomically with a descriptive message (see commit message conventions).
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

## Isolated worktree for large / multi-session features

> **Single source of truth** for worktree mechanics. The Architect / Engineer / V-M-D agents reference this section for the "how"; they own the "when".

**When** — a feature that earns a `docs/specs/active/<slug>/` entry (multi-session, multi-file, or a new module) gets a dedicated worktree. Small one-shot changes stay in the main working directory and follow the trunk-based flow above (no spec, no worktree). This applies **prospectively** to specs created / re-activated after this rule; existing specs are grandfathered.

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
# remove the ttr-<slug>-worktree/ line from .git/info/exclude
```

If any check fails → STOP, report, do not force. `git worktree prune` is safe — it drops only stale records, never branches or commits.

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
