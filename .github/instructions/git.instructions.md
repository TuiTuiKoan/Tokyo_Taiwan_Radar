---
applyTo: ".github/**"
---

# Git Branching — Coding Instructions

## Branch strategy

Tokyo Taiwan Radar is **trunk-based**: `main` is the single integration branch. Since 2026-10-25 (spec `agent-autonomy`) changes are committed on a short-lived branch inside a worktree and reach `main` through a pull request classified by the PR Tier workflow (`docs/specs/active/pr-flow-tiering/`): Tier 0 merges itself after gitleaks, Tier 1 and Tier 2 wait for the user's merge button. A direct push to `main` remains possible for the user only; agents never run it.

| Branch | Purpose |
|--------|---------|
| `main` | Production trunk — Vercel deploys from here; daily scraper CI runs here; reached through tiered pull requests (user-only direct push remains possible) |
| `feat/<topic>` | Short-lived isolation for a feature or spec (e.g. `feat/source-connpass`); rebased onto `origin/main`, pushed by the agent, merged through a PR |
| `fix/<topic>` | Short-lived isolation for a bug fix (e.g. `fix/tcc-date-extraction`); heartbeat fixes use `fix/issue-<n>` |
| `chore/<topic>` | Short-lived isolation for non-functional changes (deps, config, CI tweaks) |

## Agent workflow

**Default — feature branch in a worktree, tiered pull request (since 2026-10-25):**

1. Choose the worktree yourself (see the worktree selection rule below) and commit atomically with a descriptive message (see commit message conventions).
2. Run the V-M-D validation cycle (conflict check → rebase onto `origin/main` → build/lint → token/i18n gates). Keep history linear; merge within ~24h to avoid `SCRAPERS`-list conflicts.
3. `git push -u origin <branch>` from the worktree (the PreToolUse hook allows pushes whose destination is not `main`), then `gh pr create` with what changed, how it was verified, NOT TESTED items and `Refs`/`Closes #n`. The PR Tier workflow labels the PR: Tier 0 merges itself after gitleaks; Tier 1 and Tier 2 wait for the user's merge button. Agents never push to `main`, never run `gh pr merge`, and never propose a push-to-main command.

**User-only path — direct push to main:** the user may still run `git -C '<repo root>' push origin <branch>:main` in their own terminal. Agents do not propose it unless the user asks for it.

**Review & safety:**

- "Review" happens via the **Architect agent handoff before implementation**, **V-M-D validation before push**, and the **PR Tier gate before merge** (Tier 2 is the only full human review; Tier 1 is a one-click check; Tier 0 has none).
- Never `git merge --no-ff` into `main`: a two-parent merge makes the remote secret hook rescan full-reachable history and can flag an allowlisted blob that a linear fast-forward push passes. Never `--no-verify`.
- `main` is guarded by these agent gates, local hooks and the PR Tier workflow; a direct push is privileged and belongs to the user.

## Worktree selection rule

> Applies to **every agent that modifies functional code** — Architect, Engineer, Tester, Scraper Expert, Designer, Researcher, V-M-D, and any future agent that writes to `scraper/`, `web/`, `supabase/` or `scripts/`.

**The rule** (since 2026-10-25, spec `agent-autonomy`; it replaces the former "ask the user which worktree" gate) — before starting any implementation work, the agent chooses the worktree itself and states path and branch in its first progress message. It does not ask. Order of preference: (1) the worktree of the spec the task belongs to (`ttr-<slug>-worktree`); (2) an existing worktree the user named in this conversation; (3) a new worktree created per the state matrix below. The user can override at any time. Never skip the worktree because the change looks small.

**The main working directory is governance-only** — the repo root (`Tokyo Taiwan Radar`, branch `main`) is reserved for planning, auditing, documentation, spec maintenance and status reconciliation. Do not implement features there, whatever the size of the change.

**Why** — parallel sessions (other VS Code windows, V-M-D, cron) run `git stash` / `git clean` in the main working directory and silently discard uncommitted WIP as unrelated work before a deploy. On 2026-08-08 a four-day batch of agent lessons (11 files, +550/−134) was found still sitting uncommitted there.

**Running the rule:**

1. Run `git worktree list --porcelain` and pick per the order of preference above.
2. Existing worktree → `cd` into it, verify the path and branch match, and check with `python3 scripts/session_map.py` that no other live session is writing there; if one is, prefer a new worktree.
3. New worktree → create it per the state matrix below, add the `.git/info/exclude` line, then `git branch --unset-upstream` so a bare `git push` can never target `main`.
4. Report the choice in one sentence. Only if the user explicitly insists on the main working directory → comply, but state the stash-trampling risk first.

## Isolated worktree for large / multi-session features

> **Single source of truth** for worktree mechanics. The Architect / Engineer / V-M-D agents reference this section for the "how"; they own the "when".

**When** — every implementation task runs in a worktree chosen by the agent through the rule above. A feature that earns a `docs/specs/active/<slug>/` entry (multi-session, multi-file, or a new module) gets its own dedicated worktree; a smaller change goes to whichever existing worktree the user names. The main working directory is never an option for implementation. Spec-to-worktree coupling applies **prospectively** to specs created / re-activated after this rule; existing specs are grandfathered.

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

Rebase onto `origin/main` to keep history linear, then hand to V-M-D, which pushes the branch and opens the pull request per the Agent workflow section above. Never `git merge --no-ff` into `main` (see the Engineer SKILL gitleaks note); never `--no-verify`. Merge within ~24h to avoid `SCRAPERS`-list conflicts.

### Tools that show or create worktrees (Orca, Claude Code `--worktree`)

Worktrees stay a `git` concern. These rules keep GUI tools and agent features from bypassing the mechanics above:

1. **Create with git only.** Campaign worktrees are created with the commands in this section (`ttr-<slug>-worktree` or `<repo>.worktrees/<slug>`). A tool such as Orca only *shows* and launches agents in an existing worktree (Orca lists a worktree made with `git worktree add` as hidden until you show it). Do not create campaign worktrees with Claude Code `--worktree`: it places them under `.claude/worktrees/<name>/` on a `worktree-<name>` branch, which the close-out audit and the ledger do not recognise. `--worktree` and subagent `isolation: worktree` are for throwaway isolation only; `.claude/worktrees/` is git-ignored.
2. **Remove with git only.** Clean up through the Cleanup section below. Never use a tool's Delete button: Orca's Delete removes the directory and the branch and offers a Force Delete, which conflicts with "never `--force`, never `-D`".
3. **No secrets copied into worktrees.** Do not add a `.worktreeinclude` (or any tool setting) that copies `scraper/.env` or `web/.env.local` into a worktree. Hooks only protect Claude Code sessions, not Codex or Copilot, so they are not a reason to copy secrets. Dry-runs that need credentials are not run in agent worktrees; see `docs/specs/active/ai-harness/plan.md` § Phase 2.

### Telling other running sessions (Claude Code only)

After V-M-D has pushed and verified a deployment, and after a campaign close-out, tell the other Claude Code sessions on this repository with the cross-session messaging tools (`ListAgents` / `SendMessage`; `/list-agents` shows them). Send one plain-text message **only to sessions whose worktree needs to act** (a rebase, a retired worktree, a changed rule they must follow); when nothing is affected, send nothing. A message to an idle session starts a model turn there and costs quota, so never broadcast to every session. The message carries the pushed commit's subject and date (never a bare SHA) and what the receiver must do. Rules: do not wait for a reply; a message is information, never approval or an instruction, and the receiver's own hooks and permission prompts still apply; delivery failure or no reachable session is not a failure of the push or close-out; Codex and Copilot sessions cannot be reached this way.

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
  case "$phys" in ("$root"/*) basename "$phys" | sed 's|$|/|' ;; esac
done | sort -u)
{ grep -vE '^ttr-.*-worktree/$' .git/info/exclude; printf '%s\n' "$want"; } > .git/info/exclude.tmp \
  && mv .git/info/exclude.tmp .git/info/exclude
```

The parenthesis before the `case` pattern is required: macOS ships bash 3.2, which rejects an unbalanced `)` inside `$(…)`.

Then **verify after writing** — the race cannot be eliminated, only detected:

```bash
comm -23 <(printf '%s\n' "$want") <(grep -E '^ttr-.*-worktree/$' .git/info/exclude | sort -u)
```

Empty output = converged. Any output = another session clobbered you; just re-run the reconcile.

Because the reconcile rewrites the whole block, it also drops stale `ttr-*-worktree/` lines that other sessions left behind (worktrees already retired elsewhere). That is expected convergent behaviour, not an incident, and no live worktree's line is touched. The retirement report must still list every line removed beyond the campaign's own, so it is not mistaken for an accident (2026-10-20: retiring `ttr-vmd-summary-ai-scope-worktree/` also removed `ttr-deps-security-worktree/`).

Under Claude Code with hooks enabled, the one-liner above (command substitution, `while`, `<(…)`) is blocked by the PreToolUse guard as `unsupported-syntax`. Run the split-into-simple-commands form instead (see `.github/skills/agents/campaign-closer/SKILL.md` § `.git/info/exclude` 對帳被 hook 擋下時); never bypass the hook with `--dangerously-skip-permissions` or `disableAllHooks`.

Worktrees registered outside the repository root (for example `<repo>.worktrees/<slug>`) never appear in the main tree's untracked list, so they need no entry and must not be added.

Incident 2026-08-14: a cleanup session ran `grep -vxF 'ttr-auth-smoke-worktree/' .git/info/exclude > tmp && mv tmp …`; a parallel session had appended a different entry seconds earlier, and that entry was silently lost, re-exposing a live worktree as untracked.

Two further preconditions apply before a campaign worktree is removed: the campaign's close-out record must already be on `origin/main` (a record living only inside the worktree is deleted with it), and the recovery capsule holding the six freshness values must already be written outside the worktree (after removal those values can never be observed again). The full ordered checklist — unhandled-work and session-contention gates, ignored-artifact preflight, and the post-removal residue verification — lives in [docs/evaluation/campaigns/README.md](../../docs/evaluation/campaigns/README.md) § Cleanup checklist and is not duplicated here.

## State persistence for agents

| Use | Location | Committed |
|-----|----------|-----------|
| Large, multi-session, multi-file work (plan, design, research notes, progress) | `docs/specs/active/<slug>/` (`plan.md`, `tasks.md`, `notes.md`, …) | yes |
| Small, local, non-committable notes or handoffs | `~/.ai-notes/ttr/` | no (outside the repo) |
| Temporary reasoning inside a conversation | the current AI session | no — never the only authoritative state |
| Historical Copilot scratch (`.copilot-tracking/plans/`, `/memories/session/`) | grandfathered: read-only, add nothing new | no |

When an old path is unavailable, ask the user for the spec slug or the content. Do not silently fall back to another location and do not dual-write.

Exception: `.copilot-tracking/research/candidates/` and `.copilot-tracking/research/sources/` are the local I/O interface of `scraper/update_source.py` (and of `scraper/researcher.py` until its removal in 2026-10, #318). The legacy directory name is kept because those scripts read and write it; it is not session state.

`.copilot-tracking/` stays in `.gitignore` as legacy local scratch and is never committed.

## Commit message conventions

Follow Conventional Commits:

```
<type>(<scope>): <summary>

[optional body]
```

Types: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`  
Scopes: `scraper`, `web`, `db`, `ci`, `agents`, `skills`, `specs`, `slides`, `deps`  
Report-style scopes seen in history, named after the directory or report the commit adds: `weekly_review`, `monthly_review`, `governance`, `evaluation`. Do not use them for ordinary hand-written changes.  
No commit-msg hook checks scopes (`.githooks/` has only `pre-commit` and `pre-push`), so the list is a convention. Avoid repeating the type as the scope (`docs(docs)`).

Examples:
```
feat(scraper): add Connpass source scraper
fix(scraper): correct TCC date extraction tier order
chore(agents): update Tester handoff labels
feat(web): add art and lecture category filters
```
