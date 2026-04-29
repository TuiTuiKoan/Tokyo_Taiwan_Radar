# Engineer Error History

<!-- Append new entries at the top -->

---

## 2026-04-29 — skills/engineer/ 反覆復活（stray dir）

**問題：** 子代理更新 engineer SKILL.md 時寫入 `.github/skills/engineer/SKILL.md`（舊路徑），而非 `.github/skills/agents/engineer/SKILL.md`（正確路徑）。同一 session 發生兩次。

**修復：** SKILL.md 頂部新增 `## ⚠️ CRITICAL: Canonical File Paths`，列出所有 agent 正確路徑。

**教訓：** 路徑遷移必須在 SKILL.md **頂部第一章節**加 CRITICAL 警告，否則子代理讀不到就走舊路徑。

---
## 2026-04-29 — AdminSourcesTable 分類對照表編輯器（localStorage 覆蓋層）

**新增功能：**
1. `SOURCE_TYPE_LABELS` 加入「📦 歸檔」選項（key: `"archived"`）
2. `typeOverrides` state，初始值從 `localStorage` 讀取（key: `source_type_overrides`）
3. `getFilteredSources` 改用 `effectiveTypeMap = { ...SOURCE_TYPE_MAP, ...typeOverrides }` — 使用者覆蓋優先
4. 新增 Modal：搜尋框、所有來源依分類→名稱排序、分類下拉、被覆蓋列綠色標示 + 「↩」還原、「儲存」/「取消」
5. 移除 `sources/page.tsx` 冗餘 `<h2>` 標題

**教訓：**
- 硬寫 ID→分類對照表需配合 localStorage 覆蓋層（`effectiveTypeMap = { ...defaultMap, ...userOverrides }`），讓管理者無需改程式碼即可重新分類
- Modal 必須區分 draft state（`draftOverrides`）與 committed state（`typeOverrides`）：取消不影響已儲存狀態
- `localStorage` key 慣例：`source_type_overrides`（snake_case，明確表示功能範圍）

---
## 2026-04-29 — discovery_accounts.py 搜尋 query 年份硬寫 "2026"

**問題：** `discovery_accounts.py` lines 78, 93, 107, 123 的 4 個搜尋 query 字串硬寫 `"2026"`，每年需要手動更新，否則搜尋結果只含當年活動。

**修復：** 新增 `_THIS_YEAR = datetime.now(JST).year`（line 46），4 個 query 改為 f-string `{_THIS_YEAR}`。

**教訓：** Discovery query 中的年份必須動態計算。禁止在 query 字串裡硬寫年份數字。

---
## 2026-04-29 — AdminSourcesTable 缺少 peatix_organizer 篩選支援

**問題：** `SOURCE_TYPE_LABELS` 沒有 `peatix_organizer` 分類，`getFilteredSources` 依靠硬寫 ID 對照表偵測 Peatix 主辦者，導致新增的 Peatix 主辦者無法在 Admin Sources Table 被篩選。

**修復：**
1. `SOURCE_TYPE_LABELS` 新增 `peatix_organizer: "Peatix 主辦者"`
2. `getFilteredSources` 改為直接讀取 `agent_category` 欄位，不再依賴硬寫 ID 列表

**教訓：** 每次新增 `agent_category` 型別時，必須同步更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯。

---
## 2026-04-29 — AdminEventTable 分類篩選器顯示各分類事件總數
**新增/修改：**
- 新增 `categoryCounts` useMemo，遍歷全量 `events` 陣列計算每個 category 的數量
- Dropdown 選項改為「電影 (12)」格式，數量為 0 時不顯示括號（`count > 0 ? ` (${count})` : ''`）
- 教訓：Admin 側 UI 的顯示統計（如 per-category 數量）應以 `useMemo([events])` 直接從已載入的 `events` state 派生，無需額外 API 呼叫

---
## 2026-04-29 — Discovery Pipeline 架構固化（daily review）
**新增/修改：**
- 新增 `## Discovery Pipeline` 段落（slot rotation 設計、Peatix 驗證模式、platform-aware upsert）
- 記錄 `discovery_accounts.py` 與 `BaseScraper` 的分離關係
- 記錄 `agent_category` 作為 scraper 路由機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — researcher.yml 缺少 playwright install，URL 驗證靜默失敗數週
**新增/修改：**
- GitHub Actions Workflow Rules 新增 Step parity rule
- 多個 workflow 共用相同工具依賴時，必須同步所有 setup 步驟
- 引用 commit `d7f4b41` 作為反例（researcher.yml 缺 playwright install → url_verified=False）
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — source filter hardcoded list omitted new scrapers
**新增/修改：**
- Filter-option sync rule 拆分為「closed sets（hardcode options）」vs「open-ended sets（動態衍生）」
- 補充 `source_name` 必須用 `Array.from(new Set(...))` 動態衍生，禁止 hardcode
- 引用 commit `fe1b39e` 作為反例說明
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — AdminReportsTable 分類選單錯亂：從 flat CATEGORIES 改為 CATEGORY_GROUPS
**Problem:** `AdminReportsTable.tsx` 的 wrongCategory 分類選取用 `CATEGORIES.map(...)` 顯示所有分類為一整排無序標籤，而 `AdminEventForm.tsx` 和 `ReportSection.tsx` 使用 `CATEGORY_GROUPS` 群組佈局。導致 `/admin/reports` 校對 AI 報錯時分類列表錯亂，無群組標籤且順序不一致。
**Fix:** 將 `AdminReportsTable.tsx` 的分類區塊從 `CATEGORIES.map(...)` 改為 `CATEGORY_GROUPS.map(...)` + `grid-cols-[4.5rem_1fr]` 群組佈局，與 `AdminEventForm.tsx` 完全一致。Commit `580577d`。
**Lesson:** 三個檔案共享分類群組選擇器：`AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx`。任何一個的佈局變更必須同步更新其他兩個。已將 SKILL.md paired-file rule 擴展為 **three-file rule**，並更新 UI surfaces 表格（AdminReportsTable 改為 CATEGORY_GROUPS）。

---
## 2026-04-28 — Category group picker layout: AdminEventForm + ReportSection must stay in sync
**Problem:** Adding `literature` to `group_arts` (now 8 items) caused the group label (`w-16 shrink-0`) and tags to share one `flex-wrap` row in `AdminEventForm.tsx`. When tags overflowed to a second line, they wrapped under the group label instead of staying in the tag column.
**Fix:** Replaced `flex-wrap mixed` layout with `grid-cols-[4.5rem_1fr]` in both `AdminEventForm.tsx` and `ReportSection.tsx`: col 1 = group label (right-aligned, fixed width), col 2 = `flex-wrap` tags. `ReportSection` had an existing but narrower `3rem` column; widened to `4.5rem` for longer labels like 知識交流. Commit `31d7dd3`.
**Lesson:** `AdminEventForm.tsx` and `ReportSection.tsx` share the exact same category group picker structure. Any layout change to one must be applied to both in the same commit. This is now a paired-file rule.

---
## 2026-04-28 — merger.py: Pass 2 news-report matching added
**Feature:** `google_news_rss` (and `prtimes`, `nhk_rss`) events were not being merged into their official primary events because Pass 1 requires both (a) name similarity ≥ 0.85 and (b) same `start_date`. News-article titles fail (a) and article publish dates differ from event dates, failing (b).
**Fix:** Added `Pass 2` to `run_merger()`:
- New `_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})` constant
- `_location_overlap()` — checks for ≥1 common token of ≥2 chars between `location_name` fields
- `_date_in_range()` — checks `news.start_date ∈ [official.start_date, official.end_date]`
- DB select extended to include `end_date, location_name`
- News events are always secondary (priority 100); official events are always primary
- Idempotent: subsequent runs skip already-merged pairs
**Lesson:** News/article scrapers require a separate merge strategy. When adding a new scraper that publishes article-style content (RSS, press releases, news aggregation), add it to `_NEWS_SOURCES` in `merger.py` immediately — before merging. Also add `_NEWS_SOURCES` note to the source-specific SKILL.md section.

---
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

---
## 2026-04-29 — discovery_accounts.py 搜尋 query 年份硬寫 "2026"

**問題：** `discovery_accounts.py` lines 78, 93, 107, 123 的 4 個搜尋 query 字串硬寫 `"2026"`，每年需要手動更新，否則搜尋結果只含當年活動。

**修復：** 新增 `_THIS_YEAR = datetime.now(JST).year`（line 46），4 個 query 改為 f-string `{_THIS_YEAR}`。

**教訓：** Discovery query 中的年份必須動態計算。禁止在 query 字串裡硬寫年份數字。

---
## 2026-04-29 — AdminSourcesTable 缺少 peatix_organizer 篩選支援

**問題：** `SOURCE_TYPE_LABELS` 沒有 `peatix_organizer` 分類，`getFilteredSources` 依靠硬寫 ID 對照表偵測 Peatix 主辦者，導致新增的 Peatix 主辦者無法在 Admin Sources Table 被篩選。

**修復：**
1. `SOURCE_TYPE_LABELS` 新增 `peatix_organizer: "Peatix 主辦者"`
2. `getFilteredSources` 改為直接讀取 `agent_category` 欄位，不再依賴硬寫 ID 列表

**教訓：** 每次新增 `agent_category` 型別時，必須同步更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯。

---
## 2026-04-29 — AdminEventTable 分類篩選器顯示各分類事件總數
**新增/修改：**
- 新增 `categoryCounts` useMemo，遍歷全量 `events` 陣列計算每個 category 的數量
- Dropdown 選項改為「電影 (12)」格式，數量為 0 時不顯示括號（`count > 0 ? ` (${count})` : ''`）
- 教訓：Admin 側 UI 的顯示統計（如 per-category 數量）應以 `useMemo([events])` 直接從已載入的 `events` state 派生，無需額外 API 呼叫

---
## 2026-04-29 — Discovery Pipeline 架構固化（daily review）
**新增/修改：**
- 新增 `## Discovery Pipeline` 段落（slot rotation 設計、Peatix 驗證模式、platform-aware upsert）
- 記錄 `discovery_accounts.py` 與 `BaseScraper` 的分離關係
- 記錄 `agent_category` 作為 scraper 路由機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — researcher.yml 缺少 playwright install，URL 驗證靜默失敗數週
**新增/修改：**
- GitHub Actions Workflow Rules 新增 Step parity rule
- 多個 workflow 共用相同工具依賴時，必須同步所有 setup 步驟
- 引用 commit `d7f4b41` 作為反例（researcher.yml 缺 playwright install → url_verified=False）
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — source filter hardcoded list omitted new scrapers
**新增/修改：**
- Filter-option sync rule 拆分為「closed sets（hardcode options）」vs「open-ended sets（動態衍生）」
- 補充 `source_name` 必須用 `Array.from(new Set(...))` 動態衍生，禁止 hardcode
- 引用 commit `fe1b39e` 作為反例說明
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — AdminReportsTable 分類選單錯亂：從 flat CATEGORIES 改為 CATEGORY_GROUPS
**Problem:** `AdminReportsTable.tsx` 的 wrongCategory 分類選取用 `CATEGORIES.map(...)` 顯示所有分類為一整排無序標籤，而 `AdminEventForm.tsx` 和 `ReportSection.tsx` 使用 `CATEGORY_GROUPS` 群組佈局。導致 `/admin/reports` 校對 AI 報錯時分類列表錯亂，無群組標籤且順序不一致。
**Fix:** 將 `AdminReportsTable.tsx` 的分類區塊從 `CATEGORIES.map(...)` 改為 `CATEGORY_GROUPS.map(...)` + `grid-cols-[4.5rem_1fr]` 群組佈局，與 `AdminEventForm.tsx` 完全一致。Commit `580577d`。
**Lesson:** 三個檔案共享分類群組選擇器：`AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx`。任何一個的佈局變更必須同步更新其他兩個。已將 SKILL.md paired-file rule 擴展為 **three-file rule**，並更新 UI surfaces 表格（AdminReportsTable 改為 CATEGORY_GROUPS）。

---
## 2026-04-28 — Category group picker layout: AdminEventForm + ReportSection must stay in sync
**Problem:** Adding `literature` to `group_arts` (now 8 items) caused the group label (`w-16 shrink-0`) and tags to share one `flex-wrap` row in `AdminEventForm.tsx`. When tags overflowed to a second line, they wrapped under the group label instead of staying in the tag column.
**Fix:** Replaced `flex-wrap mixed` layout with `grid-cols-[4.5rem_1fr]` in both `AdminEventForm.tsx` and `ReportSection.tsx`: col 1 = group label (right-aligned, fixed width), col 2 = `flex-wrap` tags. `ReportSection` had an existing but narrower `3rem` column; widened to `4.5rem` for longer labels like 知識交流. Commit `31d7dd3`.
**Lesson:** `AdminEventForm.tsx` and `ReportSection.tsx` share the exact same category group picker structure. Any layout change to one must be applied to both in the same commit. This is now a paired-file rule.

---
## 2026-04-28 — merger.py: Pass 2 news-report matching added
**Feature:** `google_news_rss` (and `prtimes`, `nhk_rss`) events were not being merged into their official primary events because Pass 1 requires both (a) name similarity ≥ 0.85 and (b) same `start_date`. News-article titles fail (a) and article publish dates differ from event dates, failing (b).
**Fix:** Added `Pass 2` to `run_merger()`:
- New `_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})` constant
- `_location_overlap()` — checks for ≥1 common token of ≥2 chars between `location_name` fields
- `_date_in_range()` — checks `news.start_date ∈ [official.start_date, official.end_date]`
- DB select extended to include `end_date, location_name`
- News events are always secondary (priority 100); official events are always primary
- Idempotent: subsequent runs skip already-merged pairs
**Lesson:** News/article scrapers require a separate merge strategy. When adding a new scraper that publishes article-style content (RSS, press releases, news aggregation), add it to `_NEWS_SOURCES` in `merger.py` immediately — before merging. Also add `_NEWS_SOURCES` note to the source-specific SKILL.md section.

---
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

---
## 2026-04-29 — discovery_accounts.py 搜尋 query 年份硬寫 "2026"

**問題：** `discovery_accounts.py` lines 78, 93, 107, 123 的 4 個搜尋 query 字串硬寫 `"2026"`，每年需要手動更新，否則搜尋結果只含當年活動。

**修復：** 新增 `_THIS_YEAR = datetime.now(JST).year`（line 46），4 個 query 改為 f-string `{_THIS_YEAR}`。

**教訓：** Discovery query 中的年份必須動態計算。禁止在 query 字串裡硬寫年份數字。

---
## 2026-04-29 — AdminSourcesTable 缺少 peatix_organizer 篩選支援

**問題：** `SOURCE_TYPE_LABELS` 沒有 `peatix_organizer` 分類，`getFilteredSources` 依靠硬寫 ID 對照表偵測 Peatix 主辦者，導致新增的 Peatix 主辦者無法在 Admin Sources Table 被篩選。

**修復：**
1. `SOURCE_TYPE_LABELS` 新增 `peatix_organizer: "Peatix 主辦者"`
2. `getFilteredSources` 改為直接讀取 `agent_category` 欄位，不再依賴硬寫 ID 列表

**教訓：** 每次新增 `agent_category` 型別時，必須同步更新 `AdminSourcesTable.tsx` 的 `SOURCE_TYPE_LABELS` 和 `getFilteredSources` 邏輯。

---
## 2026-04-29 — AdminEventTable 分類篩選器顯示各分類事件總數
**新增/修改：**
- 新增 `categoryCounts` useMemo，遍歷全量 `events` 陣列計算每個 category 的數量
- Dropdown 選項改為「電影 (12)」格式，數量為 0 時不顯示括號（`count > 0 ? ` (${count})` : ''`）
- 教訓：Admin 側 UI 的顯示統計（如 per-category 數量）應以 `useMemo([events])` 直接從已載入的 `events` state 派生，無需額外 API 呼叫

---
## 2026-04-29 — Discovery Pipeline 架構固化（daily review）
**新增/修改：**
- 新增 `## Discovery Pipeline` 段落（slot rotation 設計、Peatix 驗證模式、platform-aware upsert）
- 記錄 `discovery_accounts.py` 與 `BaseScraper` 的分離關係
- 記錄 `agent_category` 作為 scraper 路由機制
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — researcher.yml 缺少 playwright install，URL 驗證靜默失敗數週
**新增/修改：**
- GitHub Actions Workflow Rules 新增 Step parity rule
- 多個 workflow 共用相同工具依賴時，必須同步所有 setup 步驟
- 引用 commit `d7f4b41` 作為反例（researcher.yml 缺 playwright install → url_verified=False）
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — source filter hardcoded list omitted new scrapers
**新增/修改：**
- Filter-option sync rule 拆分為「closed sets（hardcode options）」vs「open-ended sets（動態衍生）」
- 補充 `source_name` 必須用 `Array.from(new Set(...))` 動態衍生，禁止 hardcode
- 引用 commit `fe1b39e` 作為反例說明
**來源：** daily-skills-review（Step 4 建議）

---
## 2026-04-28 — AdminReportsTable 分類選單錯亂：從 flat CATEGORIES 改為 CATEGORY_GROUPS
**Problem:** `AdminReportsTable.tsx` 的 wrongCategory 分類選取用 `CATEGORIES.map(...)` 顯示所有分類為一整排無序標籤，而 `AdminEventForm.tsx` 和 `ReportSection.tsx` 使用 `CATEGORY_GROUPS` 群組佈局。導致 `/admin/reports` 校對 AI 報錯時分類列表錯亂，無群組標籤且順序不一致。
**Fix:** 將 `AdminReportsTable.tsx` 的分類區塊從 `CATEGORIES.map(...)` 改為 `CATEGORY_GROUPS.map(...)` + `grid-cols-[4.5rem_1fr]` 群組佈局，與 `AdminEventForm.tsx` 完全一致。Commit `580577d`。
**Lesson:** 三個檔案共享分類群組選擇器：`AdminEventForm.tsx`、`ReportSection.tsx`、`AdminReportsTable.tsx`。任何一個的佈局變更必須同步更新其他兩個。已將 SKILL.md paired-file rule 擴展為 **three-file rule**，並更新 UI surfaces 表格（AdminReportsTable 改為 CATEGORY_GROUPS）。

---
## 2026-04-28 — Category group picker layout: AdminEventForm + ReportSection must stay in sync
**Problem:** Adding `literature` to `group_arts` (now 8 items) caused the group label (`w-16 shrink-0`) and tags to share one `flex-wrap` row in `AdminEventForm.tsx`. When tags overflowed to a second line, they wrapped under the group label instead of staying in the tag column.
**Fix:** Replaced `flex-wrap mixed` layout with `grid-cols-[4.5rem_1fr]` in both `AdminEventForm.tsx` and `ReportSection.tsx`: col 1 = group label (right-aligned, fixed width), col 2 = `flex-wrap` tags. `ReportSection` had an existing but narrower `3rem` column; widened to `4.5rem` for longer labels like 知識交流. Commit `31d7dd3`.
**Lesson:** `AdminEventForm.tsx` and `ReportSection.tsx` share the exact same category group picker structure. Any layout change to one must be applied to both in the same commit. This is now a paired-file rule.

---
## 2026-04-28 — merger.py: Pass 2 news-report matching added
**Feature:** `google_news_rss` (and `prtimes`, `nhk_rss`) events were not being merged into their official primary events because Pass 1 requires both (a) name similarity ≥ 0.85 and (b) same `start_date`. News-article titles fail (a) and article publish dates differ from event dates, failing (b).
**Fix:** Added `Pass 2` to `run_merger()`:
- New `_NEWS_SOURCES = frozenset({"google_news_rss", "prtimes", "nhk_rss"})` constant
- `_location_overlap()` — checks for ≥1 common token of ≥2 chars between `location_name` fields
- `_date_in_range()` — checks `news.start_date ∈ [official.start_date, official.end_date]`
- DB select extended to include `end_date, location_name`
- News events are always secondary (priority 100); official events are always primary
- Idempotent: subsequent runs skip already-merged pairs
**Lesson:** News/article scrapers require a separate merge strategy. When adding a new scraper that publishes article-style content (RSS, press releases, news aggregation), add it to `_NEWS_SOURCES` in `merger.py` immediately — before merging. Also add `_NEWS_SOURCES` note to the source-specific SKILL.md section.

---
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

---
## 2026-04-29 - GitHub Actions resolver could not fetch actions/checkout@v4

**Error:** `.github/workflows/secret-rotation-reminder.yml` failed at parse/resolve stage with `Unable to resolve action actions/checkout@v4, repository or version not found`.

**Fix:** Downgraded action refs in the same workflow to resolver-friendly majors for older environments:
- `actions/checkout@v4` -> `actions/checkout@v3`
- `actions/setup-python@v5` -> `actions/setup-python@v4`

**Lesson:** If a workflow must run on older GitHub Enterprise resolvers or constrained action mirrors, prefer the latest major that is known to exist in that environment, and downgrade related core actions together to keep compatibility expectations consistent.

---
## 2026-04-28 — Multi-locale field editing: always expose all locale variants simultaneously

**Context:** `ReportSection.tsx` initially showed a single textarea pre-filled with the *current locale's* value when a user flagged a wrong field. A user pointed out that the Japanese original may be correct while only the Chinese or English translation is wrong. Showing one locale obscures which specific translation is faulty.

**Upgrade:** Changed the textarea to three stacked labeled textareas (中文 / English / 日本語), each pre-filled with the field's own locale column value. Users edit only the incorrect locale(s) and leave others unchanged.

**Type change:**
```ts
// Before
eventFields?: Partial<Record<WrongDetailField, string | null>>;
fieldEdits:   Partial<Record<WrongDetailField, string>>;

// After
eventFields?: Partial<Record<WrongDetailField, Partial<Record<LocaleKey, string | null>>>>;
fieldEdits:   Partial<Record<WrongDetailField, Partial<Record<LocaleKey, string>>>>;
```

**Submission format:** `fieldEdit:<field>:<locale>:<value>` — only non-empty edits are appended to `report_types`.

**Lesson:** When a UI component edits a field that maps to localized DB columns (`*_ja`, `*_zh`, `*_en`), **never show only the current locale's value**. Show all locale variants with language labels. This applies to any future correction/review UI (admin edit forms, report flows, feedback widgets). → Added to SKILL.md as **Multi-locale Edit Pattern**.

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
