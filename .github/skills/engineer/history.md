---
## 2026-04-28 — database.instructions.md Step 6 not followed on first use (020_creators.sql)
**Error:** Migration `020_creators.sql` was committed in `21039ad` without updating `database.instructions.md`. The Step 6 rule ("Update this file in the same commit") had been added only 2 days earlier in `a91ba57`. Result: Latest still showed `018b`, next = `019` (already skipped), and `creators`/`creator_events` tables were absent from Other tables.
**Fix:** Manually updated `database.instructions.md` in the next session: Latest → `020_creators.sql`, next → `021`, added skipped-019 note to Known conflicts, added creators tables.
**Lesson:** Step 6 is easily forgotten because it is not in the same file as the migration SQL. Consider adding a `-- REMINDER: update database.instructions.md` comment at the bottom of every new migration template as an in-file prompt.

---
## 2026-04-26 - ja.json duplicate keys recurred after earlier fix
**Error:** `web/messages/ja.json` contained duplicate keys `actionHide`, `actionApplyCategory`, `actionReannotate` (lines 186–191). VS Code reported `Duplicate object key` errors. This was the **third recurrence** of duplicate keys in this file — previous fixes (commits `2f19a08`, `e61b81c`) did not prevent re-introduction by subsequent edits.
**Fix:** Used Python json-module rewrite (`json.loads` + `json.dumps`) to canonicalise the file. `json.loads` automatically deduplicates (last-wins), removing the 3 duplicate lines. Verified with `get_errors`.
**Lesson:** `web/messages/ja.json` is a repeat-offender for duplicate keys. **After every edit to any `*.json` message file**, run `get_errors` to confirm no duplicates. When a key already exists in the file, search for it first before inserting. Never insert keys via string append — always use the Python json-module pattern which naturally deduplicates.

---
## 2026-04-26 - _loc_zh() char map incomplete — new Simplified chars found in location_name_zh
**Error:** After deploying `_loc_zh()` with 8 chars, production scan found 5 active events still had Simplified Chinese in `location_name_zh`: `伊伊诺大厅` (イイノホール, 4 events) and `中野區役所（ナ卡诺巴、外面網）` (1 event). Missing chars: `诺`→諾, `厅`→廳, `络`→絡, `设`→設, `联`→聯, `馆`→館, `门`→門, `发`→發, `会`→會.
**Fix:** Added 9 new entries to `_LOC_ZH_SIMP_TO_TRAD` in `annotator.py`. DB-patched 17 events total (5 active + 12 inactive) using a one-off `fix_loc_simp.py` script. Final scan confirmed 0 events with Simplified in location fields.
**Lesson:** The `_loc_zh()` char map will never be exhaustive on first deployment. After adding or expanding it, **always run a full-DB scan** against `location_name_zh` and `location_address_zh` using `scan_loc.py` pattern (see SKILL.md). Any new Simplified char found = add to map + DB-patch existing rows immediately.

---
## 2026-04-26 - GPT-4o-mini outputs Simplified Chinese in location fields despite LANGUAGE RULE
**Error:** After adding a top-level `LANGUAGE RULE` to `SYSTEM_PROMPT`, GPT-4o-mini still produced Simplified Chinese in `location_name_zh` and `location_address_zh` (e.g. `东京都千代田区内幸町` → should be `東京都千代田區內幸町`, `桜美林大学新宿校园` → `桜美林大学新宿校園`). Affected 5 active events.
**Fix:** Added `_loc_zh()` post-processing helper inside `annotate_event()` that applies a `str.maketrans` char map (东→東, 区→區, 内→內, 园→園, 来→來, 长→長, 进→進, 实→實) to `location_name_zh` and `location_address_zh` before writing to DB. This is a deterministic safety net that works regardless of GPT output quality. Patched 5 DB rows directly and ran final scan confirming 0 active events with Simplified chars.
**Lesson:** Prompt-only fixes are not sufficient for location fields — GPT-4o-mini ignores language rules on short transliteration tasks. Always pair a `LANGUAGE RULE` in `SYSTEM_PROMPT` with a deterministic post-processing char map (`_loc_zh()`) on all `*_zh` location fields.

---
## 2026-04-26 - backup.yml upload-artifact path causes YAML schema validator warning
**Error:** GitHub Actions YAML schema validator reported `Expected a scalar value, a sequence, or a mapping` on `path: ${{ steps.snapshot.outputs.snapshot_dir }}` in `upload-artifact@v4`. The expression was syntactically valid YAML but the schema validator required it to be quoted when it is a bare expression in a `path:` field.
**Fix:** Changed `path: ${{ ... }}` → `path: "${{ ... }}"`. Added newline at end of file.
**Lesson:** In GitHub Actions workflows, any `with:` field whose value is a pure `${{ expression }}` (no surrounding text) should be quoted. Additionally, any `run:` step whose command contains **both** a `${{ }}` expression AND shell double-quote characters must use a block scalar (`|`) — inline scalars with that combination trigger VS Code YAML extension schema validation warnings.\n\n---\n## 2026-04-26 - Annotator produced Simplified Chinese for 29 events
**Error:** 29 events had `*_zh` fields in Simplified Chinese (e.g. `东京都千代田区`, `会议1`, `发言`). Root causes: (1) `sub_events[].name_zh` / `description_zh` schema strings said "in Chinese" without "Traditional"; (2) no top-level language reminder in system prompt.
**Fix:** Added LANGUAGE RULE at top of `SYSTEM_PROMPT`: ALL `*_zh` fields MUST be Traditional Chinese (繁體中文), never Simplified. Changed sub-events schema to "in Traditional Chinese (繁體中文)". Reset 29 affected events to pending and re-ran annotator.
**Lesson:** Every zh-field description in the GPT JSON schema must say "Traditional Chinese (繁體中文)". After any bulk re-annotation, scan for simplified-only chars (regex: `[东来这发会说时问门关对长]`) to verify zero regressions.


# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 - Bulk remove common categories from selected events in admin
**Feature:** Added bulk common-category removal to `AdminEventTable.tsx`. When multiple events are selected, a second row appears in the Bulk Action Bar listing category tags that are **common to all selected events** (set intersection). Clicking a tag removes it from all selected events via parallel Supabase updates.
**Implementation:**
- `commonCategories` = `useMemo` computing intersection of `category[]` across all selected events; auto-recalculates when selection or events change
- `handleBulkRemoveCategory(cat)` = `Promise.all` parallel updates + optimistic local state
- Bulk action bar restructured from `flex` single row to `flex-col space-y-2` with optional second row
- New i18n keys: `admin.bulkCommonCategories`, `admin.bulkRemoveCategoryHint` (zh/en/ja)
- If no common categories exist, second row is hidden — no layout disruption
**Lesson:** When implementing bulk operations that depend on a derived value from selected items, use `useMemo` keyed on `[selected, events]` rather than computing inline in the render. This avoids recomputing on every keystroke and keeps the handler simple.

---
## 2026-04-26 - replace_string_in_file fails silently on U+30FB (katakana middle dot) in JSON
**Error:** Multiple `replace_string_in_file` calls targeting `web/messages/*.json` appeared to succeed (no error reported) but left the files unchanged. The root cause: the `oldString` contained U+30FB `・` (KATAKANA MIDDLE DOT), which was encoded differently between the tool input and the actual file bytes, causing the match to silently fail. Affected commits: `group_arts`→五感, `group_knowledge`→知識交流, `geopolitics` EN/JA, `performing_arts` JA — all required re-applying via Python.
**Fix:** Rewrote all affected patches using `python3 -c "import json, pathlib; ..."` with explicit `encoding='utf-8'`, which reads and writes the exact Unicode code points regardless of how the shell or tool layer encodes the string literal.
**Lesson:** Never use `replace_string_in_file` to edit `web/messages/*.json` files when the `oldString` contains any non-ASCII characters (especially Japanese/Chinese punctuation like `・` U+30FB, `。`, `「」`, fullwidth characters). Always use the Python json-module pattern instead:
```python
import json, pathlib
path = pathlib.Path('web/messages/XX.json')
data = json.loads(path.read_text(encoding='utf-8'))
data['section']['key'] = 'new value'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```
After writing, always verify with `grep "key" web/messages/XX.json` before committing.

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
## 2026-04-26 - Annotation status badge/filter label mismatch (two i18n key families)
**Error:** `getAnnotationLabel()` in `AdminEventTable.tsx` used `filterAnnotatedShort`/`filterReviewedShort`/`filterErrorShort`/`filterPendingShort` (short-form keys: "AI"/"人工"/"失敗"/"待命"), while the filter dropdown used `annotated`/`reviewed`/`error` (full-form keys: "AI標註"/"人工標註"/"標註失敗"). Same status value → different visible text in badge vs filter. Plus: `<option value="pending">` was missing from the dropdown even though `filterAnnotation` state accepted `"pending"`.
**Fix:** Changed `getAnnotationLabel()` to use the same full-form keys as the filter (`t("annotated")`, `t("reviewed")`, `t("error")`, `t("pending")`). Added `<option value="pending">`. Commits `fcdf513` + `2a0571c`.
**Lesson:** One status value = one i18n key, used consistently in badge, filter option, and any other display. Never maintain two parallel key families (short + long) for the same canonical set. Prefer long-form; delete orphaned short-form keys once confirmed unused.

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
