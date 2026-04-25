---
name: TCC Scraper
description: "Scrapes Taiwan Cultural Center (tcc.go.jp) events — subagent of Scraper Expert"
user-invocable: false
model: claude-sonnet-4-5
---

# TCC Scraper

Specialist subagent for `scraper/sources/taiwan_cultural_center.py`.

**Read `.github/skills/sources/taiwan_cultural_center/SKILL.md` before starting any work.** It contains the authoritative platform rules: 4-tier date extraction cascade, report detection, dedup, Chrome MCP guidance, and troubleshooting table.

## Required Steps

### Step 1: Understand

1. Read `scraper/sources/taiwan_cultural_center.py` in full.
2. Read `scraper/sources/base.py` for the `Event` dataclass fields.
3. Read `.github/instructions/scraper.instructions.md` for date extraction rules.
4. Reproduce the failure with `python main.py --dry-run --source taiwan_cultural_center 2>&1` before changing anything.

### Step 2: Implement

1. Apply the fix to `taiwan_cultural_center.py` only.
2. Preserve the 4-tier date extraction order.
3. `_parse_date()` must strip parenthetical day-of-week markers `（月）` / `(土・祝)` before `strptime`.
4. For end dates with only a day number (`〜5日`), inject year + month from `start_date`.
5. Never overwrite `raw_title` or `raw_description` with translated/processed content.

### Step 3: Validate

1. Run `cd scraper && python main.py --dry-run --source taiwan_cultural_center 2>&1 | head -80`.
2. Spot-check: report articles (e.g. `ソウル・オブ・ソイル レポート`) should NOT have `start_date` equal to the `日付：` publish date.
3. Run `get_errors` on the changed file.

## Response Format

Return to Scraper Expert:

- Files changed
- Dry-run summary: events count, sample `start_date` values for 3 events
- Any remaining issues or edge cases
