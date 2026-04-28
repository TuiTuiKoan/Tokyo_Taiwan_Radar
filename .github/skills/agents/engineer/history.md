# Engineer Error History

<!-- Append new entries at the top -->

---
## 2026-04-28 — Report section: editable textarea per wrong-detail field

**Feature:** When a user checks a sub-field (name, date, venue, etc.) under "內容錯誤 / wrongDetails" in `ReportSection.tsx`, a textarea now appears pre-filled with the current localized event content. The user can edit the value before submitting; the edited text is stored as `fieldEdit:<field>:<value>` in `report_types` alongside the existing `field:<field>` entry.

**Implementation:**
- Added `eventFields?: Partial<Record<WrongDetailField, string | null>>` prop to `ReportSection`
- Added `fieldEdits: Partial<Record<WrongDetailField, string>>` state; populated on field checkbox toggle
- `toggleField()` now sets `fieldEdits[field] = eventFields?.[field] ?? ""` on check, and deletes the key on uncheck
- JSX: sub-field checkboxes moved from `<label>` wrappers to `<div>` with conditional textarea below each checkbox
- `handleSubmit` appends `fieldEdit:<field>:<value>` entries (max 500 chars each) when `edit.trim()` is non-empty
- `page.tsx`: passes `eventFields` using the locale-aware helpers `getEventName`, `getEventLocationName`, etc. already imported
- New i18n key `fieldEditHint` added to all three `messages/*.json` files

**Pattern replicated from:** `wrongSelectionReason` textarea — same pre-fill + clear-on-uncheck pattern.

**Lesson:** When reusing a textarea-on-checkbox pattern, extract the pre-fill logic into `toggle<X>()` so the JSX stays declarative. Avoid inline `onChange` that mutates state outside the toggle handler.

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
