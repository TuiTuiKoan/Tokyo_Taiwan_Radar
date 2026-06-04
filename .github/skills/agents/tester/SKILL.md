---
name: tester
description: Scraper test execution rules, output validation criteria, and report format for the Tester agent
applyTo: .github/agents/tester.agent.md
---

# Tester Skills

Read this at the start of every session before running any test.

## Scraper Testing
- Always run with `--dry-run` first to avoid writing to DB during validation.
- Check `start_date` is populated (not null) for every scraped event — missing dates are the most common data quality failure.
- Verify `source_id` is stable across two separate runs before declaring a scraper production-ready. Run twice, diff the IDs.
- For TCC scraper: confirm `start_date` is NOT the page update date (visible at the bottom of the page as `日付：`).

## Reporting
- Report failures with: source name, event title, field name, expected value, actual value.
- If > 20% of events from a source have null `start_date`, escalate to Engineer before proceeding.
- Distinguish between logic errors (wrong field extracted) and selector errors (selector no longer matches).

## Agent Tooling Baseline
- In `.github/agents/tester.agent.md`, declare tools using aliases (`read`, `search`, `execute`, `web`) rather than raw function names.
- Before running source tests, perform a quick terminal preflight (any no-op command) to confirm `execute` is available.
- Keep Tester read-only; do not add `edit` unless the role is intentionally expanded.
- Standard activation path for this repo is `source ../.venv/bin/activate`.

## Shell Safety (zsh history expansion) — 2026-05-26
- **Never embed bare `!` characters in inline shell commands** (e.g. `python -c "print(repr(x))"` with `!r` formatting flag). zsh expands `!r`, `!$`, `!!` from shell history *before* quoting takes effect, even inside single quotes.
- **Always use quoted heredocs** for multi-line scripts: `python3 - <<'PY'` (note the quoted `'PY'`). Quoted delimiter disables both variable interpolation and history expansion.
- **If `!` is unavoidable in a single-line command, escape it**: `\!r` instead of `!r`.
- **Always quote paths containing `[` or `]`** (for example `app/[locale]/account/events/new/page.tsx`) when passing them to zsh commands such as `eslint`, `grep`, or `sed`; otherwise zsh treats them as glob patterns and can fail with `no matches found`.
- **Preflight (machines without `NO_BANG_HIST`)**: `[[ -o BANG_HIST ]] && echo "WARN: history expansion enabled, use heredoc"`.
- **Detection signals during execution**: `zsh: event not found`, or an echoed command that doesn't match what you typed → stop immediately, do NOT press enter on follow-up prompts.
- This repo's owner shell has `setopt NO_BANG_HIST` permanently set in `~/.zshrc` since 2026-05-26 after a near-miss `rm` resurrection (see `history.md` 2026-05-26 entry).

## After a Test Failure
1. Append an entry to `.github/skills/agents/tester/history.md` (newest at top).
2. If the failing command already crossed a DB write boundary before crashing, immediately re-query the sample row and restore the pre-test state before continuing.
3. If the lesson generalizes, add a rule to this file.
