# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 - Category label changes only updated i18n, not all 5 UI surfaces
**Error:** When renaming category labels or group labels (e.g., `group_arts`→五感, `performing_arts`→音楽・演劇, `geopolitics` EN/JA), changes were made only to `web/messages/*.json`. The team discovered that 5 UI surfaces all consume categories from the same source and none require separate code changes for label renames — but the complete list of surfaces was not documented, risking future partial updates.
**Fix:** Established the Category Update Protocol and documented all 5 surfaces:
1. 前台篩選器 (`FilterBar.tsx`) — `CATEGORY_GROUPS`
2. 後台篩選器 (`AdminEventTable.tsx`) — `CATEGORY_GROUPS`
3. AI 報錯選單 (`ReportSection.tsx`) — `CATEGORY_GROUPS`
4. 活動編輯頁 (`AdminEventForm.tsx`) — `CATEGORY_GROUPS`
5. 後台問題回報審核 (`AdminReportsTable.tsx`) — `CATEGORIES` flat array
**Lesson:** All category display labels flow through `messages/categories.*` keys. For label-only renames, update all 3 message files in one commit. For structural changes (add/remove), also update `lib/types.ts` (`Category` union, `CATEGORIES`, `CATEGORY_GROUPS`). See Category Update Protocol in SKILL.md.

---
## 2026-04-26 - Filter dropdown missing `pending` option — filter and list options not synced
**Error:** The annotation status filter dropdown in `AdminEventTable.tsx` had options `all / annotated / reviewed / error`, but was missing `pending`. The `filterAnnotation` state type already included `"pending"`, the filter logic already handled it generically, and the i18n key `t("pending")` already existed in `zh.json`. Only the `<option>` element was never added to the `<select>`. Result: admins could not filter by `pending` status (commit `2f19a08`).
**Fix:** Added `<option value="pending">{t("pending")}</option>` as the first option after "全部".
**Lesson:** Whenever a filter dropdown and a list/table share a canonical set of values (e.g. `annotation_status`, `category`, `source_name`), the `<option>` list in the dropdown **must exactly mirror** the canonical set. Adding a new value to a TypeScript union type, DB enum, or i18n file is NOT sufficient — the `<option>` element must be added too. TypeScript does not catch missing `<option>` values.

---
## 2026-04-26 - Admin table address cell only read `location_address`, missing fallback
**Error:** The address `<td>` in `AdminEventTable.tsx` annotated view only read `event.location_address`. Events where addresses were stored in `location_address_zh` (zh-first scrapers) or embedded in `location_name` showed `—` in the admin list, even though the detail page showed the correct address.
**Fix:** Changed to `addr = event.location_address || event.location_address_zh || event.location_name`, matching the fallback chain used by `getEventLocationAddress()` in `lib/types.ts` (commit `f45d5d5`). Also patched 2 specific DB rows.
**Lesson:** Any field displayed in the admin table that has a locale fallback chain in `lib/types.ts` (`getEventLocationAddress`, `getEventLocationName`, etc.) **must use the same fallback** in the admin table cell. Using a single field (no fallback) creates silent empty columns for zh-first or multilingual events.

---
## 2026-04-26 - AdminEventTable orphaned `<td>` after removing a `<th>` column
**Error:** When the `isPaid` `<th>` column was removed from the `annotated` view header in `AdminEventTable.tsx`, the corresponding `<td>` cell (rendering `event.is_paid`) was left in every row. This caused the row columns to silently misalign — the data appeared under the wrong header but no build/type error was thrown.
**Fix:** Removed the orphaned `<td>` block in commit `5597150`.
**Lesson:** Whenever a `<th>` column is removed from `AdminEventTable.tsx`, immediately do a paired removal of the matching `<td>` in the row renderer. The `<thead>` and `<tbody>` column counts must always match. TypeScript does not catch table column count mismatches.

---
## 2026-04-26 - AdminEventTable filter label/style regressions after later commits
**Error:** Three UI fixes made in commits `dfe6e24` and `3aef2c0` (search label → `tFilters("search")`, category label → `tFilters("category")`, category button `bg-white` → `bg-gray-50`) were silently overwritten when a later commit (`9c4010d`) modified the same file for an unrelated change (reannotate label rename). The regression was only noticed by the user.
**Fix:** Re-applied all three changes in [fix(web): re-apply admin filter label/style fixes lost in regression].
**Lesson:** When modifying `AdminEventTable.tsx` for any reason, **always verify** these three invariants before committing:
1. Search filter label: `tFilters("search")` — NOT `t("name")`
2. Category filter label: `tFilters("category")` — NOT `t("category")`
3. Category button: `bg-gray-50` — NOT `bg-white`

---
## 2026-04-25 - GitHub Actions env context warning for artifact path
**Error:** In `.github/workflows/backup.yml`, `upload-artifact` used `${{ env.SNAPSHOT_DIR }}` where `SNAPSHOT_DIR` was set via `$GITHUB_ENV` in a prior step. Static validation reported `Context access might be invalid: SNAPSHOT_DIR`.
**Fix:** Added `id: snapshot` to the backup step, wrote `snapshot_dir` to `$GITHUB_OUTPUT`, and switched later steps to `${{ steps.snapshot.outputs.snapshot_dir }}`.
**Lesson:** For values consumed by later workflow expressions, prefer step outputs over runtime shell env exports to avoid context-validation mismatches.

---
## 2026-04-25 - annotator `location_address_zh` prompt produced Simplified Chinese
**Error:** After migration 010 added `location_address_zh`, the annotator prompt described the field as `"address in Chinese-friendly format"` without specifying Traditional Chinese. GPT-4o-mini output Simplified Chinese (e.g. `东京都千代田区丸之内`) for ~4 events.
**Fix:** Changed prompt to `"address in Traditional Chinese (繁體中文) — transliterate Japanese city/area names to Traditional Chinese; keep street numbers as-is"`. Reset affected events to `pending` and re-annotated. One stubborn event (`神奈川`) required manual DB correction.
**Lesson:** All `*_zh` fields in the annotator prompt must explicitly say "Traditional Chinese (繁體中文)". Verify a sample of `location_address_zh` values for simplified characters after any batch re-annotation.

---
## 2026-04-25 - Next.js inferred wrong Turbopack root and risked worker OOM
**Error:** `next build` inferred the workspace root as `/Users/flyingship` because another lockfile existed above the app. That widened Turbopack's filesystem scope beyond `web/`, which can inflate worker memory usage and surface `Worker terminated due to reaching memory limit: JS heap out of memory`.
**Fix:** Set `turbopack.root` explicitly in `web/next.config.ts` to the absolute `web` project directory.
**Lesson:** In nested workspaces, do not rely on Next.js root auto-detection when parent directories contain lockfiles. Pin `turbopack.root` before chasing application-level memory leaks.

---
## 2026-04-23 — scraper_runs deepl_chars column always 0
**Error:** `deepl_chars` added to `scraper_runs` but never populated. DeepL is called in individual scrapers (`peatix.py`, `taiwan_cultural_center.py`), not in `annotator.py` where the logging was added.
**Fix:** Add `self._deepl_chars_used: int = 0` to `BaseScraper`, increment at each DeepL call, read via `getattr(scraper, "_deepl_chars_used", 0)` in `main.py` when writing the `scraper_runs` row.
**Lesson:** When adding a new DB column, identify every code path that produces data for it before shipping the migration. → Added to SKILL.md under Database.

---
## 2026-04-23 — _annotate_one return type changed without smoke test
**Error:** Return type changed from `dict` to `(dict, usage)` tuple. Change committed and pushed without running the annotator to verify tuple unpacking worked end-to-end.
**Fix:** Run `python annotator.py 2>&1 | tail -10` after any function signature change; confirm no `ValueError: too many values to unpack`.
**Lesson:** Always smoke-test changed function signatures before committing. → Added to SKILL.md under Python.

---
## 2026-04-23 — Sentry autoInstrumentServerFunctions: false disabled server capture
**Error:** Set `autoInstrumentServerFunctions: false` in `withSentryConfig` to suppress a build warning. This inadvertently disabled Sentry's ability to capture errors in Next.js Server Components and API routes.
**Fix:** Remove the option entirely (defaults to `true`).
**Lesson:** Never set Sentry config options to suppress build warnings without reading what they control. → Added to SKILL.md under Next.js / Sentry.
