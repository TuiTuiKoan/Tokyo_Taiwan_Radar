---
applyTo: ".github/**"
---

# Git Branching — Coding Instructions

## Branch strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production — Vercel deploys from here; daily scraper CI runs on here |
| `feat/<topic>` | New features or scraper sources (e.g. `feat/source-connpass`) |
| `fix/<topic>` | Bug fixes (e.g. `fix/tcc-date-extraction`) |
| `chore/<topic>` | Non-functional changes (deps, config, CI tweaks) |

## Agent workflow

1. **Before starting any work**, create a feature branch:
   ```bash
   git checkout -b feat/<topic>
   ```
2. Commit early and often with descriptive messages (see commit message conventions).
3. **Never push directly to `main`** — all changes go through a feature branch.
4. Open a PR from the feature branch; the Architect agent reviews before merge.

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
