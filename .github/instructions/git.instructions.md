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

## Parallel agent work

True parallel execution is not possible in a single VS Code window. Use one of:

1. **Sequential work with state in `.copilot-tracking/`**: each agent saves its progress; the next agent reads and continues.
2. **Multiple VS Code windows on git worktrees**:
   ```bash
   git worktree add ../tokyo-radar-feat-connpass feat/source-connpass
   code ../tokyo-radar-feat-connpass
   ```
3. **GitHub Copilot Workspace** (cloud-based): supports true parallel agents — use when available.

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
