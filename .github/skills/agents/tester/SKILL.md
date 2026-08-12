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

## Batch Repair Validation
- For any reset + re-annotate / backfill run, do not stop at command success or `annotation_status`. Query the affected slice and verify the intended structural end-state (`event_form`, required template fields, missing translations) in DB.
- For publication backfills, confirm pure rows are exact-only (`event_form=['publication']`) and mixed rows (for example `['publication', 'lecture']`) are not folded into pure behavior.
- For pure publication rows, verify seven intentional-null fields and matching empty sentinels: `location_address`, `location_address_zh`, `location_address_en`, `business_hours`, `business_hours_zh`, `business_hours_en`, `location_prefectures`.
- Preserve real DB prices (`is_paid`, `price_info`, `price_amount`) and verify they are hidden only from pure-publication UI and JSON-LD. Price fields, `location_name`, and `location_url` must not enter the seven-field NULL/clear policy.
- For publication backfills, confirm publisher/organizer remains present and `missing_name_zh` / `missing_name_en` are zero before calling the run a pass.
- When publication handling changes, include a writer-whitelist check (`scraper/database.py::_VALID_EVENT_FORMS` includes `publication`) in regression validation.
- If the repaired slice includes named public figures or other high-risk proper nouns, add at least one human semantic spot check on `name_en` / `name_zh`. GPT can fill all required fields while still hallucinating a person name.

## Verification Discipline (applies to every test, not just scrapers)
- **Establish a positive control before you trust a negative result.** Before accepting that a fail-closed script correctly returned `UNDETERMINED` / non-zero, first prove that a clean environment with all arguments supplied *actually reaches* the success path (e.g. `RETIRE_CANDIDATE`, exit 0). Without that control you cannot distinguish "correctly refused" from "broken and refuses everything" — both look identical from the outside, and the second one passes review.
- **Never accept the implementer's self-reported fix as evidence.** Re-derive it independently. Example: Engineer reported the `trim()` defect as fixed; direct execution showed `trim()` still returned `TokyoTaiwanRadarclone` for a path containing spaces, while `trim_edges()` preserved it. Self-reports describe intent; only execution describes behavior.
- **Never read an exit code through a pipeline.** In `cmd | tail`, `$?` is `tail`'s status, not `cmd`'s — a failing command reads as exit 0. Capture output to a file or variable first, then test `$?`, or use `set -o pipefail` / `${PIPESTATUS[0]}`. Assert the exit code and the stdout marker as two separate checks.
- **Probe with a variant the implementer has not seen.** A fix aimed at one shape of input (say, quoted values) frequently leaves neighbouring shapes (quoted *and* padded with whitespace) broken. Choose the untested combination on purpose.

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
