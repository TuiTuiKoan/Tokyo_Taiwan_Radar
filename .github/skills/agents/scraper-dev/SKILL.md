---
name: scraper-dev
description: "Step-by-step workflow for creating a new scraper source for Tokyo Taiwan Radar"
applyTo: scraper/sources/**
---

# Scraper Dev

Guides creation of a new event scraper source for Tokyo Taiwan Radar. Covers the full workflow from generating the source file to registering it in the pipeline and validating dry-run output.

## Prerequisites

- Python 3.12 virtual environment activated: `source venv/bin/activate` (from repo root)
- Playwright browsers installed: `playwright install chromium`
- `scraper/.env` populated with `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`, `DEEPL_API_KEY`

## Quick Start

```bash
# 1. Create the source file
cp scraper/sources/taiwan_cultural_center.py scraper/sources/<source_name>.py

# 2. Register it in the pipeline
#    Add to SCRAPERS list in scraper/main.py

# 3. Test without DB writes
cd scraper && python main.py --dry-run --source <source_name>
```

## New Source Checklist

1. **Source file** — create `scraper/sources/<source_name>.py`:
   - Set `SOURCE_NAME = "<source_name>"` as a class attribute
   - Implement `scrape() → list[Event]` via `BaseScraper`
   - Set `source_id` to a stable, run-invariant value (URL hash, page slug, etc.)
   - Set `raw_title` and `raw_description` to original scraped text — never overwrite
   - Populate `start_date`; prepend `開催日時: YYYY年MM月DD日\n\n` to `raw_description`
   - Use only canonical `category` values (see `web/lib/types.ts` → `CATEGORIES`)

2. **Register** — in `scraper/main.py`:
   ```python
   from sources.<source_name> import <ClassName>
   SCRAPERS = [
       TaiwanCulturalCenterScraper(),
       PeatixScraper(),
       <ClassName>(),   # ← add here
   ]
   ```
   > **BLOCKING:** Do NOT commit the source file without also committing the `main.py` registration in the same commit. A source file that is not in `SCRAPERS` will never run in CI.

3. **Test**:
   ```bash
   cd scraper && python main.py --dry-run --source <source_name> 2>&1
   ```
   > **BLOCKING:** Do NOT commit until dry-run exits 0 and logs at least one event. A source that has never been dry-run verified is not ready to merge.

4. **Verify output** — every event must have:
   - `start_date` populated (not null, not the publish date)
   - `raw_title` and `raw_description` non-empty
   - `source_id` stable across runs (re-run twice and confirm same IDs)

5. **Document** — before committing, create these files:

   | File | Content |
   |------|---------|
   | `.github/skills/sources/<source_name>/SKILL.md` | Platform profile, field mappings, Taiwan filter, date extraction, troubleshooting |
   | `.github/skills/sources/<source_name>/history.md` | Initial implementation decisions and any first-run surprises |

   Then update `.github/skills/agents/scraper-expert/SKILL.md` — add a `## <source_name>-specific` section with 3–5 key rules.
   Also update `research_sources` in Supabase: set `status → implemented`.

   > See `.github/skills/agents/scraper-expert/SKILL.md` → "Documentation Protocol" for full template.

## Parameters Reference

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source_name` | `str` | Yes | Snake-case identifier, unique per source |
| `source_id` | `str` | Yes | Stable dedup key — used for Supabase upsert |
| `original_language` | `str` | Yes | `"ja"` / `"zh"` / `"en"` |
| `raw_title` | `str` | Yes | Original scraped title — never translated |
| `raw_description` | `str` | Yes | Original scraped body — never translated |
| `start_date` | `datetime` | Yes | Event start; must NOT be the publish/scrape date |
| `end_date` | `datetime` | No | Same as `start_date` for single-day events |
| `category` | `list[str]` | No | Values from canonical list only |
| `parent_event_id` | `str` | No | Set on sub-events; leave `None` for top-level |

## Technology Selection (before writing any code)

Before choosing Playwright, check if the site offers a lighter alternative:

| Priority | Method | How to test |
|----------|--------|-------------|
| 1 | **WordPress REST API** | `curl -s "https://example.com/wp-json/wp/v2/posts?per_page=1" \| python3 -m json.tool` |
| 2 | **RSS / Atom feed** | Look for `<link rel="alternate" type="application/rss+xml">` in page `<head>` |
| 3 | **Static HTML** (requests + BS4) | `curl -s URL \| grep -c "<script"` — if fewer than ~10 script tags, likely server-rendered |
| 4 | **Playwright** | Only when JavaScript rendering is required and no API/feed exists |

WordPress REST API and RSS have zero Playwright dependency, run faster in CI, and use far less memory. Prefer them for government/NGO/cultural-institution sites. Example: `jposa_ja` uses WP RSS; `taiwanbunkasai` uses static HTML.

## Branch Strategy

| When | Action |
|------|--------|
| Scraper is fully tested, dry-run passes, low-risk source | Commit directly to `main` |
| Scraper needs further validation, depends on pending DB migration, or is large/experimental | Create `feat/source-<name>` branch, push PR |
| Working across multiple sessions on the same source | Always use a branch to avoid partial commits on `main` |

After merging a feature branch, set `research_sources.status → implemented` in Supabase.

## Script Reference

```bash
# Test a single source (dry-run, no DB writes):
bash .github/skills/agents/scraper-dev/scripts/test-source.sh <source_name>

# Test all sources (dry-run):
bash .github/skills/agents/scraper-dev/scripts/test-source.sh
```

## Troubleshooting

**`start_date` is null** — The scraper fell through all extraction tiers. Check whether the event page structure matches the regex patterns. For TCC, run `--dry-run` and inspect `raw_description` for the date string.

**`source_id` changes between runs** — Do not use timestamps or random values. Use a hash of the stable URL path or the platform's own event ID.

**Playwright timeout** — Increase `timeout` in `page.goto()`. Some JS-heavy pages need `wait_until="domcontentloaded"` instead of `"networkidle"`.

**Category `"culture"` in output** — `"culture"` is not a canonical category. Use `"senses"`, `"art"`, or another value from `CATEGORIES` in `web/lib/types.ts`.

**DeepL quota exceeded** — The annotator translates; the scraper should not call DeepL. If you added translation in the scraper, remove it and let `annotator.py` handle it.
