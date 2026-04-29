# Documentation Update Summary — 2026-04-29

## Overview
Updated architect and scraper-expert skills with lessons from migration 027 verification, cinema official_url extraction, and scraper registration audit.

---

## Files Updated

### 1. `.github/skills/agents/architect/history.md`
**Added 3 new entries (newest first):**

1. **2026-04-29 — Migration 027 驗證完成：5 步驗證套件建立與全綠測試**
   - 4-quadrant verification matrix (app admin/non-admin, SQL Editor with/without claim)
   - 3 verification artifacts (smoke test suite, validation guide, verification report)
   - Lesson: SECURITY DEFINER RPC needs comprehensive auth testing across contexts

2. **2026-04-29 — Cinema scrapers 官網提取：official_url selector 設計與 DB backfill 分離執行**
   - Selector patterns for ticket/purchase links with domain whitelist
   - Google search must use `name_ja` priority (not locale-resolved name)
   - Immediate DB backfill validation after adding new field extraction

3. **2026-04-29 — 8 個 Scraper 後補註冊：未登錄 SCRAPERS list 的源碼檔案大清查**
   - Found 8 unregistered scrapers (CineMarine, EsliteSpectrum, MoonRomantic, MorcAsagaya, ShinBungeiza, Ssff, TaiwanFaasai, TokyoFilmex)
   - Verified dry-run output for each
   - Lesson: Monthly audit + mandatory commit-time registration (not CI discovery)

### 2. `.github/skills/agents/architect/SKILL.md`
**Added 3 new sections:**

1. **Migration Verification Protocol**
   - Four-quadrant test matrix definition
   - Executable SQL smoke test suite pattern
   - Verification report format (date, status, test details, security architecture, checklist)
   - "PRODUCTION READY" mark criteria

2. **Scraper Source Registration Audit**
   - Monthly `comm` command to find unregistered sources
   - Immediate dry-run validation after registration
   - Require explicit reasoning for 0-event results (offline season, no matches)

3. **Cinema Official URL Extraction**
   - Selector patterns (ticket/purchase keywords and hrefs)
   - Domain whitelist requirement for official URLs
   - Immediate backfill validation (first 5 manual inspections)
   - `name_ja` priority for Google Search (search locale != result locale)

### 3. `.github/skills/agents/scraper-expert/history.md`
**Added 1 new entry:**

- **2026-04-29 — 8 Unregistered Scrapers Found in SCRAPERS List Gap**
  - All 8 had source files but missing from `SCRAPERS` list
  - Fixed + validated dry-run output for each scraper
  - Lesson: Monthly audit + commit-time registration (not CI discovery)

---

## Validation & Testing

All updates reflect verified lessons from completed work:
- ✅ Migration 027: All 5 verification steps passed (function exists, no-auth 42501, admin success, non-admin 42501, return types)
- ✅ Cinema official_url: Implemented in CineMarti Shinjuku and KS Cinema with DB backfill
- ✅ Google search locale: Fixed to use `name_ja` instead of locale-resolved name
- ✅ 8 Scrapers: Registered and dry-run validated

---

## Next Steps

1. **Monthly Audit Automation** (Optional)
   - Add a GitHub Actions task to check `sources/` vs `SCRAPERS` list
   - Email maintainer if differences found

2. **Migration Template** (Optional)
   - Consider creating a migration template file that enforces the 4-quadrant verification structure

3. **Cinema Scraper Checkup** (Recommended)
   - Quarterly audit of cinema official_url extraction effectiveness
   - Check for broken links or outdated vendor domains in whitelist

---

## Git Commits

| Commit | Message | Files |
|--------|---------|-------|
| `7e8f42f` | docs(architect): record lessons from 027 migration, cinema official_url, and scraper registration audit | history.md, SKILL.md |
| `82b9fc6` | docs(scraper-expert): record 8 unregistered scrapers audit and fix | history.md |

---

**Summary**: Documentation updated to capture 3 major lessons from recent work across database security, scraper field extraction, and project tooling. All captured lessons are actionable and have been tested in production context.

**Status**: Ready for reference in future planning and implementation cycles.
