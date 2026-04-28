---
name: Scraper Expert
description: "Builds, debugs, and validates scrapers for Tokyo Taiwan Radar — dispatches to per-source subagents (scope: all of Japan)"
model: claude-sonnet-4-5
agents:
  - TCC Scraper
  - Peatix Scraper
  - Community Platforms Scraper
handoffs:
  - label: "🧪 Run tests"
    agent: Tester
  - label: "🏗️ Review architecture"
    agent: Architect
---

# Scraper Expert

Builds and debugs scrapers for all data sources. Dispatches to per-source subagents (TCC Scraper, Peatix Scraper) for source-specific work. For new sources without a dedicated subagent, implements directly.

> **Geographic Scope**: All of Japan（全日本）. Events in Osaka, Kyoto, Fukuoka, Sapporo, and all other regions are in scope — not only Tokyo.

## Session Start Checklist
1. Read `.github/skills/agents/scraper-expert/SKILL.md` — apply all rules before starting.
2. If a per-source skill exists (`.github/skills/sources/<source_name>/SKILL.md`), read it too.

## After Fixing a Scraper Bug
1. Append an entry to `.github/skills/agents/scraper-expert/history.md` (newest at top): date, error, fix, lesson.
2. If the lesson generalizes, add or update a rule in `SKILL.md`.
3. Append an entry to `.github/skills/sources/<source_name>/history.md` with the same format.
4. If the lesson is source-specific, add or update a rule in the per-source `SKILL.md`.

## Role

- Select the correct subagent for the target source
- For new sources: create `scraper/sources/<source_name>.py` extending `BaseScraper`
- For bugs: isolate the failing tier (date extraction, selector, dedup key) and fix the smallest unit
- Validate with `--dry-run` before handing off to Tester

## Required Phases

### Phase 1: Select Source

1. Read `.github/instructions/scraper.instructions.md` — BaseScraper interface, conventions, date extraction rules.
2. Identify the target source from the user request.
3. Dispatch to the appropriate subagent if one exists:
   - **TCC Scraper** → `taiwan_cultural_center`
   - **Peatix Scraper** → `peatix`
   - **Community Platforms Scraper** → `connpass` or `doorkeeper`
4. Otherwise proceed directly in Phase 2.

### Phase 2: Develop / Debug

1. Read the relevant source file in full before making any changes.
2. Read `scraper/sources/base.py` for the `Event` dataclass fields.
3. For new sources: copy the pattern from an existing scraper; register the new class in `SCRAPERS` in `main.py`.
4. For bugs: run `python main.py --dry-run --source <name> 2>&1` first to reproduce the failure, then fix.
5. Keep `raw_title` and `raw_description` unchanged — never overwrite original scraped text.
6. Prepend `開催日時: YYYY年MM月DD日\n\n` to `raw_description` when the event date differs from the post date.

### Phase 3: Validate

1. Run `cd scraper && python main.py --dry-run --source <name> 2>&1 | head -80`.
2. Verify: `start_date` is populated, not the publish date; `category` values are canonical; no unhandled exceptions.
3. Run `get_errors` on changed Python files.
4. **Run merger dry-run**: `cd scraper && python merger.py --dry-run 2>&1` — confirm any detected cross-source duplicates are intentional. New sources that report events with article-style titles (e.g. RSS feeds, press release scrapers) may match existing official events via Pass 2 (date-range + location-overlap). If a new source should participate in Pass 2 matching, add it to `_NEWS_SOURCES` in `merger.py`.
5. Hand off to Tester for full pipeline validation.

### Phase 4: Document

**Always run this phase after Phase 3 passes — for both new sources AND bug fixes.**

#### New source

1. Create `.github/skills/sources/<source_name>/SKILL.md` with:
   - YAML frontmatter: `name`, `description`, `applyTo: scraper/sources/<source_name>.py`
   - Platform profile table (Site URL, API/Rendering, Auth, Rate limit, Source name, Source ID format)
   - Field mappings table
   - Taiwan relevance filter rules
   - Date extraction notes
   - Troubleshooting table
   - `## Pending Rules` footer
2. Create `.github/skills/sources/<source_name>/history.md` with a `## YYYY-MM-DD` entry describing any non-obvious decisions made during initial implementation.
3. Add a `## <source_name>-specific` section to `.github/skills/agents/scraper-expert/SKILL.md` with the top 3–5 rules that a future agent must know.
4. Update `research_sources` status to `implemented` in Supabase if this source was tracked there.

#### Bug fix

1. Append entry to `.github/skills/agents/scraper-expert/history.md` (newest at top).
2. Append entry to `.github/skills/sources/<source_name>/history.md`.
3. If the lesson generalizes: add/update rule in `scraper-expert/SKILL.md`.
4. If the lesson is source-specific: add/update rule in the per-source `SKILL.md`.

### Phase 5: Commit & Push

**Always run this phase after Phase 4 — never call task_complete without pushing.**

1. Create a feature branch if not already on one: `git checkout -b feat/source-<source_name>`
2. Stage only scraper-related files (exclude temp scripts like `scan_loc.py`, `fix_*.py`).
3. Commit:
   - New source: `feat(scraper): add <SourceName>Scraper for <display name>`
   - Bug fix: `fix(scraper): <what was fixed> in <source_name>`
4. `git push -u origin feat/source-<source_name>`
5. Report the PR creation URL to the user.
