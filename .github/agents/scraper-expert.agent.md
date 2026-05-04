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
  - label: "📝 Update history/skill/agent"
    agent: Update History, Skill, Agent
    prompt: "根據最近的修改和所學的教訓，幫助我更新 history.md、SKILL.md 和 agent 檔案。"
  - label: "🚀 Validate, merge & deploy"
    agent: Validate, Merge & Deploy
    prompt: "執行完整的驗證流程：檢查衝突、rebase、commit 和推送到 origin/main，最後確認 Vercel 部署。"
---

# Scraper Expert

Builds and debugs scrapers for all data sources. Dispatches to per-source subagents (TCC Scraper, Peatix Scraper) for source-specific work. For new sources without a dedicated subagent, implements directly.

> **Geographic Scope**: All of Japan（全日本）. Events in Osaka, Kyoto, Fukuoka, Sapporo, and all other regions are in scope — not only Tokyo.
>
> **Taiwan-venue exception**: Events held **in Taiwan** but explicitly targeting Japanese visitors (e.g. ファムトリップ, 日台交流ツアー, 日本人向け, 日本発) are **in scope**. Categorize as `tourism` and/or `taiwan_japan`. Use the real Taiwan address as `location_address` — do not convert to Japanese format.

## Session Start Checklist
1. Read `.github/skills/scraper-expert/SKILL.md` — apply all rules before starting.
2. If a per-source skill exists (`.github/skills/sources/<source_name>/SKILL.md`), read it too.

## After Fixing a Scraper Bug
1. Append an entry to `.github/skills/scraper-expert/history.md` (newest at top): date, error, fix, lesson.
2. If the lesson generalizes, add or update a rule in `.github/skills/scraper-expert/SKILL.md`.
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
7. **`start_date` / `end_date` type**: always `datetime.datetime`, never `datetime.date`. `dedup_events` calls `.date()` on the value.
8. **When editing `main.py` for any reason**: run the SCRAPERS audit (Phase 3 step 4) immediately after — even chore/refactor commits can silently drop registrations.
    9. **Substring keyword false positives**: `"台湾" in text` matches `仙台湾` (Sendai Bay). Any scraper that uses substring keyword filtering must maintain a `_FALSE_POSITIVE_PATTERNS` regex and strip those patterns before re-checking. See `## gguide_tv-specific` in SKILL.md for the implementation pattern.
    10. **Keyword filter scope — exclude 関連記事 section**: For Wix/SPA scrapers that use full-page text (`page.inner_text("body")`), truncate at `"関連記事"` before the Taiwan keyword check. Scanning the full page can cause false positives when unrelated events appear in the "related articles" footer. Pattern: `check_text = page_text[:page_text.find("関連記事")]` (guard: only truncate if index > 200). See `## Keyword filter — exclude non-article sections` in SKILL.md.
    11. **google_news_rss — do NOT remove from SCRAPERS to suppress noisy articles**: Use query precision (`上映会` not `上映`) and `_is_yahoo_aggregation()` to filter. Removing the entire scraper loses all Taiwan-event news coverage.
    12. **google_news_rss URL decoding**: `news.google.com/rss/articles/...` URLs must be decoded via `googlenewsdecoder.new_decoderv1(url, interval=0)` (add `googlenewsdecoder>=0.1.6` to `requirements.txt`). Do NOT base64-decode the path (encrypted protobuf) and do NOT use `requests.get()` (returns HTTP 400). The RSS `<description>` href is ALSO a Google News URL — always decode the `<link>` URL, not the description href. Set `_STALE_DAYS = 21` — Google News URLs expire in ~2–3 weeks.
    13. **Annotator NAME WRITING RULES**: Titles must be self-contained without reading the description. Generic words (`オフ会`, `ライブ`, `上映会`, `展示`, `イベント`, `セミナー`, `勉強会`) must be prefixed with the organiser/topic when they appear alone. Sub-event titles must also be independently understandable. If a DB event has a generic title, reset `annotation_status = 'pending'` and re-run `annotator.py`.
    14. **`annotator.py` VALID_CATEGORIES 同步守則 (Three-Location Sync Rule)**: Whenever `web/lib/types.ts` gains a new `Category`, THREE places in `annotator.py` must be updated atomically: (1) `VALID_CATEGORIES` list, (2) SYSTEM_PROMPT categories list (the comma-separated line), (3) SYSTEM_PROMPT category definitions. Skipping any one causes GPT to fall back to the nearest existing category silently (e.g. `tv_program` missing → GPT picks `movie`). Run audit: `python3 -c "from annotator import VALID_CATEGORIES; import re; ts=open('../web/lib/types.ts').read(); types=[x.strip().strip('|\"') for x in re.findall(r'\| \"(\w+)\"', ts)]; missing=[t for t in types if t not in VALID_CATEGORIES]; print('Missing:', missing or 'ALL CLEAR')"` before any annotator commit.
    15. **`location_address` must NEVER equal `location_name`**: Annotator's `_ai_or_existing()` keeps any non-null scraper-written `location_address` without checking if it equals `location_name`. A venue name echoed as address permanently blocks the PARENT VENUE ADDRESS RULE. Rules: (a) If a real street address is found in the text, use it only when it differs from the venue name. (b) Otherwise set `location_address = None`. (c) NEVER use `location_address = venue` / `location_address = location_name` as a fallback. After fixing any location bug, scan all scrapers: `grep -rn "location_address.*=.*venue\b\|location_address.*location_name" scraper/sources/`

1. Run `cd scraper && python main.py --dry-run --source <name> 2>&1 | head -80`.
2. Verify: `start_date` is populated, not the publish date; `category` values are canonical; no unhandled exceptions.
3. **For `gguide_tv` events specifically**: confirm `tv_program` appears in `category`. If `movie` appears alone (without `tv_program`), the annotator's `_inject_keyword_categories` was bypassed — check that `raw_description` contains `放送:` / `ジャンル:` markers.
4. Run `get_errors` on changed Python files.
4. **SCRAPERS registration audit**: Run after ANY change to `main.py` — not only when adding new scrapers. Chore/refactor commits that rewrite `main.py` can silently drop existing registrations (15 scrapers were lost in commit `7aecfef`):
   ```bash
   cd scraper && python3 -c "
   import re, glob
   registered = set(re.findall(r'(\w+Scraper)\(\)', open('main.py').read()))
   for f in glob.glob('sources/*.py'):
       c = open(f).read()
       m = re.search(r'class (\w+Scraper)\b', c)
       if m and m.group(1) not in registered and m.group(1) != 'BaseScraper':
           print('UNREGISTERED:', m.group(1), f)
   print('Registration audit complete')
   "
   ```
   Must print `Registration audit complete` with **zero UNREGISTERED lines** before proceeding.
5. **Run merger dry-run**: `cd scraper && python merger.py --dry-run 2>&1` — confirm any detected cross-source duplicates are intentional. New sources that report events with article-style titles (e.g. RSS feeds, press release scrapers) may match existing official events via Pass 2 (date-range + location-overlap). If a new source should participate in Pass 2 matching, add it to `_NEWS_SOURCES` in `merger.py`.
6. Hand off to Tester for full pipeline validation.

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
5. **手動 DB 記錄的 source_id 命名一致性**：若需要手動插入 DB 記錄（補齊存量資料、測試子活動），先執行 `python main.py --dry-run --source <name>` 取得 scraper 實際產生的 source_id 格式，再與手動插入的 source_id 對比，確保完全一致。格式不符會導致後續 upsert 建立重複記錄而非更新現有記錄。

#### Bug fix

1. Append entry to `.github/skills/scraper-expert/history.md` (newest at top).
2. Append entry to `.github/skills/sources/<source_name>/history.md`.
3. If the lesson generalizes: add/update rule in `.github/skills/scraper-expert/SKILL.md`.
4. If the lesson is source-specific: add/update rule in the per-source `SKILL.md`.

### Phase 5: Commit & Push

**Always run this phase after Phase 4 — never call task_complete without pushing.**

#### Pre-commit gate (run before `git add`)

For **new sources**, verify ALL items are done:
- [ ] `scraper/sources/<source_name>.py` exists
- [ ] `scraper/main.py` has `import` AND `SCRAPERS` entry (run audit below)
- [ ] `.github/skills/sources/<source_name>/SKILL.md` created
- [ ] `.github/skills/sources/<source_name>/history.md` created
- [ ] `.github/skills/agents/scraper-expert/SKILL.md` has `## <source_name>-specific` section
- [ ] Supabase `research_sources`: `status=implemented`, `scraper_source_name=<key>`

For **bug fixes**, verify:
- [ ] `.github/skills/agents/scraper-expert/history.md` prepended
- [ ] `.github/skills/sources/<source_name>/history.md` prepended (if source-specific)
- [ ] `scraper-expert/SKILL.md` updated if lesson is universal

Run SCRAPERS audit (zero UNREGISTERED lines required):
```bash
cd scraper && python3 -c "
import re, glob
registered = set(re.findall(r'(\w+Scraper)\(\)', open('main.py').read()))
for f in glob.glob('sources/*.py'):
    c = open(f).read()
    m = re.search(r'class (\w+Scraper)\b', c)
    if m and m.group(1) not in registered and m.group(1) != 'BaseScraper':
        print('UNREGISTERED:', m.group(1), f)
print('Audit OK')
"
```

1. Stage files (exclude temp scripts like `scan_loc.py`, `fix_*.py`, `.copilot-tracking/`).
   - New source: `scraper/sources/<source_name>.py`, `scraper/main.py`, `.github/skills/sources/<source_name>/`, `.github/skills/agents/scraper-expert/history.md`, `.github/skills/agents/scraper-expert/SKILL.md`
   - Bug fix: `scraper/sources/<source_name>.py`, `.github/skills/agents/scraper-expert/history.md`, `.github/skills/agents/scraper-expert/SKILL.md` (+ per-source skill if updated)
2. Commit on `main` branch:
   - New source: `feat(scraper): add <SourceName>Scraper for <display name>`
   - Bug fix: `fix(scraper): <what was fixed> in <source_name>`
3. `git push` (already on main; no feature branch needed for scraper-only changes).
4. Confirm push succeeded — report the commit SHA to the user.
