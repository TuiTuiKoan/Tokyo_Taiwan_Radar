---
name: engineer
description: Implementation rules for database migrations, Python scrapers, and Next.js web for the Engineer agent
applyTo: .github/agents/engineer.agent.md
---

# Engineer Skills

Read this at the start of every session before touching any code.

## Database
- Always verify a migration has been applied in Supabase before writing code that depends on it. Check: `SELECT table_name FROM information_schema.tables WHERE table_name = 'X';`
- When adding a DB column, wire up the code that populates it in the same commit. Empty columns = silent data gaps.
- Wrap non-critical DB inserts (logging, analytics) in `try/except`. Never let a failed log write break the main pipeline.
- When a logging table gains new `NOT NULL` columns (e.g. `success`, `duration_seconds`), **both** the success path and the `except` block must write those columns explicitly. Pattern from `scraper_runs`:
  ```python
  # success path
  {"success": True, "duration_seconds": int(time.time() - start)}
  # except block
  {"success": False, "duration_seconds": 0}
  ```
  If only the success path is updated, failure rows leave the column NULL and break `NOT NULL` constraints (or silently insert the default, hiding failures).

## Python
- When changing a function's return type (e.g. `dict` → `tuple`), immediately smoke-test before committing: `python -c "from module import fn; print(type(fn(...)))"`
- Use `getattr(obj, 'attr', default)` when reading an attribute that may not exist on all subclasses.

## Next.js / Sentry
- Never set `autoInstrumentServerFunctions: false` — it silently disables server-side error capture.
- Gate source map upload: `sourcemaps: { disable: !process.env.SENTRY_AUTH_TOKEN }`.

## Bulk Action Pattern (AdminEventTable)

When adding a new bulk operation that operates on a **derived value from selected events** (e.g. common categories, common source, common status):
1. Compute the derived value with `useMemo([selected, events])` — never inline in render
2. Add a loading state (`useState(false)`) guarding the async handler
3. Use `Promise.all(selectedEvents.map(...))` for parallel DB updates — do NOT loop with `await` sequentially
4. Apply optimistic local state update in `setEvents()` after `Promise.all` resolves
5. Only show the derived-value UI when the derived value is non-empty (conditional render in bulk bar)
6. Add i18n keys to all 3 message files using the Python json-module pattern

## i18n JSON File Editing — Unicode Safety Rule

**Never use `replace_string_in_file` to edit `web/messages/*.json`** when `oldString` contains any non-ASCII characters (Japanese/Chinese punctuation, CJK characters, fullwidth symbols like `・` U+30FB). The tool can silently fail to match without reporting an error.

**Always use the Python json-module pattern for i18n edits:**
```python
import json, pathlib
path = pathlib.Path('web/messages/XX.json')
data = json.loads(path.read_text(encoding='utf-8'))
data['section']['key'] = 'new value'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
```
After writing, verify with `grep "key" web/messages/XX.json` before committing.

`replace_string_in_file` is safe only for ASCII-only strings in JSON files.

## Category Update Protocol

**Canonical source of truth:** `web/lib/types.ts` → `Category` union type, `CATEGORIES` array, `CATEGORY_GROUPS` array.

### When renaming a category display label (i18n only)
Update all three message files simultaneously:
- `web/messages/zh.json` — key under `categories.*`
- `web/messages/en.json` — same key
- `web/messages/ja.json` — same key

For group labels: keys are `group_arts`, `group_lifestyle`, `group_knowledge`, `group_society`, `group_archive`.

### When adding or removing a category value
Update **all 6 locations** in a single commit — do NOT split across commits:
1. `web/lib/types.ts` — `Category` union type
2. `web/lib/types.ts` — `CATEGORIES` flat array
3. `web/lib/types.ts` — `CATEGORY_GROUPS` (place in the correct group)
4. `web/messages/zh.json` — label under `categories.*`
5. `web/messages/en.json` — same key
6. `web/messages/ja.json` — same key

### 6 UI surfaces that consume categories (all derive from types.ts — no component code changes needed for label renames)
| Surface | File | Source | Type |
|---------|------|--------|------|
| 前台篩選器 | `web/components/FilterBar.tsx` | `CATEGORY_GROUPS` + `messages/categories.*` | 選擇器 |
| 後台篩選器 | `web/components/AdminEventTable.tsx` | `CATEGORY_GROUPS` + `messages/categories.*` | 選擇器 |
| AI 報錯選單 | `web/components/ReportSection.tsx` | `CATEGORY_GROUPS` + `messages/categories.*` | 選擇器 |
| 活動編輯頁 | `web/components/AdminEventForm.tsx` | `CATEGORY_GROUPS` + `messages/categories.*` | 選擇器 |
| 後台問題回報審核 | `web/components/AdminReportsTable.tsx` | `CATEGORY_GROUPS` + `messages/categories.*` | 選擇器 |
| 首頁活動卡片標籤 | `web/components/EventCard.tsx` | `messages/categories.*` only | 展示用 |

> **Note:** `EventCard.tsx` renders category tags on the homepage card — display-only, no picker. Label renames propagate automatically.

### Category group picker layout — paired-file rule
`AdminEventForm.tsx`, `ReportSection.tsx`, **and `AdminReportsTable.tsx`** all render the category group picker with `CATEGORY_GROUPS`. They **must use the same layout** at all times:
- Structure: `grid-cols-[4.5rem_1fr]` per group row — col 1 = group label (right-aligned, `shrink-0`), col 2 = `flex-wrap` tags
- Any layout change to **any one** of these three files must be applied to **all three** in the same commit
- Do NOT use `flex-wrap` with a mixed label+tags row — overflows cause label misalignment when a group has many items

## AdminEventTable.tsx — Protected Invariants
Whenever this file is modified for **any reason**, verify these 3 lines are intact before committing:
1. **Search filter label**: `{t("name")}` — `tFilters` namespace does NOT exist; using `tFilters("search")` silently renders the raw key string
2. **Category filter label** (in filter bar, not table column header): `{t("category")}` — same reason, do NOT use `tFilters("category")`
3. **Category dropdown button**: `bg-white` — do NOT revert to `bg-gray-50`

These were regressed at least twice when unrelated changes overwrote them. The `tFilters` mistake specifically recurred because old SKILL notes incorrectly listed it as the correct value.

**Column pairing rule:** When adding or removing a `<th>` column, always add or remove the matching `<td>` in the same commit. TypeScript does not detect thead/tbody column count mismatches. This caused an orphaned `is_paid` `<td>` (commit `5597150`) after its `<th>` was already removed.

**Address cell fallback rule:** The address `<td>` must use `event.location_address || event.location_address_zh || event.location_name`. Never read a single field. Any locale-aware field displayed in admin must apply the same fallback chain as the corresponding helper in `lib/types.ts`.

**Filter-option sync rule — closed sets:** Any `<select>` filter whose options come from a **closed** canonical set (e.g. `annotation_status`, `category`) must list **every** value in that set as an `<option>`. When a new value is added to a TypeScript union, DB enum, or i18n file, the corresponding `<option>` element must be added in the same commit. TypeScript does not detect missing dropdown options.

**Filter-option sync rule — open-ended sets:** For sets that grow with new data (e.g. `source_name`, which gains a new value every time a scraper is added), **never hardcode options**. Instead, derive them from the loaded data:
```ts
Array.from(new Set(events.map(e => e.source_name))).sort()
```
A hardcoded `source_name` list will silently omit new scrapers and require a code change for every new source. This was fixed in commit `fe1b39e` after 10+ scrapers were added without appearing in the filter.

**Annotation status label consistency rule:** One status value = one i18n key, used consistently in **all** display surfaces: badge (`getAnnotationLabel`), filter dropdown `<option>`, any column header. Use the **short-form keys**: `t("filterAnnotatedShort")`, `t("filterReviewedShort")`, `t("filterErrorShort")`, `t("filterPendingShort")`. The long-form family (`annotated`, `reviewed`, `error`, `pending`) has been deleted — do not recreate it.

## React / Form Pitfalls

### Controlled input `value` prop ≠ state

React controlled input 的 `value` prop 是顯示用，不等於 state。只有 `onChange` 被觸發時 state 才會更新。

**Rule:** 當 form 用 `value` prop 預填來自 props/data source 的值（例如用戶回報的建議修改），且管理員可能不修改直接送出時：
- **Option A（推薦）**：submit 前從 props/data source 重新解析預填值，merge 進 state（state 明確輸入優先，data source 為 fallback）。
- **Option B**：在 `useState(initialValue)` 初始化或 `useEffect` 中將預填值寫入 state，確保 state 從一開始就反映顯示值。

**絕對不要**只依賴 `value` prop 在 submit handler 中取值——它是 display-only，submit 時不保證 state 已更新。

## Scraper Implementation

- Every new scraper source must extend `BaseScraper` (`scraper/sources/base.py`) and implement `scrape() → list[Event]`.
- `source_id` must be stable across runs — it is the upsert dedup key. Use a deterministic hash or platform ID, never a timestamp.
- `raw_title` and `raw_description` store original scraped text. **Never overwrite** them with translated or processed content.
- Date rules: follow the 4-tier cascade in `.github/skills/date-extraction/SKILL.md`. Tier 4 (publish date fallback) fires only when tiers 1–3 all fail.
- Prepend `開催日時: YYYY年MM月DD日\n\n` to `raw_description` whenever `start_date` is known.
- Register every new scraper in `scraper/main.py` → `SCRAPERS` list.
- Validate with `python main.py --dry-run --source <name>` before committing.
- **`scraper_source_name` sync**: After registering a new scraper, also set `scraper_source_name` on the corresponding `research_sources` row so the admin on-demand rescrape UI can target it. Pattern: `UPDATE research_sources SET scraper_source_name = '<key>' WHERE id = <id>;` — include this in the same migration SQL that creates the source row, or run it as a one-off.
- **Retroactive DB patch rule**: When a code fix changes **how an existing field is parsed** (rather than adding a new field), the fix only applies to NEW events inserted after the fix. Existing DB records are skipped by `upsert_events` behavior #3 (idempotent skip). Always check whether a one-off DB patch is needed for existing records after fixing a field-extraction bug.

## New API Route Checklist

When adding a new Next.js API route under `web/app/api/`:

1. The route lives in a **new directory** — `git add <file>` only stages named files. Run `git status` and confirm the new directory appears under "Changes to be committed", not "Untracked files".
2. Run `npm run build` and verify the route appears in the output (e.g. `ƒ /api/admin/your-route`). Missing routes = the file was not staged or has a compile error.
3. For routes that call external APIs (e.g. GitHub API), ensure the required env var (`GITHUB_TOKEN`, etc.) is set in Vercel project settings before deploying.

## After Fixing Any Error
1. Append an entry to `.github/skills/engineer/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.

## Annotator — Traditional Chinese (繁體中文) Rule

**ALL `*_zh` fields produced by `annotator.py` must be Traditional Chinese (繁體中文), never Simplified Chinese (简体字).** This includes `name_zh`, `description_zh`, `location_name_zh`, `location_address_zh`, `business_hours_zh`, `selection_reason.zh`, and all sub-event zh fields.

**Checklist when modifying `SYSTEM_PROMPT` in `annotator.py`:**
1. The first few lines must contain a `LANGUAGE RULE` block explicitly stating ALL `*_zh` fields → Traditional Chinese, NEVER Simplified.
2. Every zh-field description in the JSON schema must say `"... in Traditional Chinese (繁體中文)"`.
3. Sub-event fields (`sub_events[].name_zh`, `sub_events[].description_zh`) must also say "Traditional Chinese (繁體中文)".

**After any batch re-annotation, verify with:**
```python
import re
SIMP = re.compile(r'[东来这发会说时问门关对长进现与实变内还单层达]')
# Check name_zh, description_zh, location_name_zh, location_address_zh for all affected events
```
If any Simplified chars found: reset those events to `pending` and re-annotate.

### `_loc_zh()` — Deterministic post-processing safety net

Prompt-only fixes are insufficient for location fields: GPT-4o-mini ignores language rules on short transliteration tasks. The `_loc_zh()` helper inside `annotate_event()` applies a `str.maketrans` char map as a deterministic safety net **after** GPT returns:

```python
_LOC_ZH_SIMP_TO_TRAD = str.maketrans({
    "东": "東",  # 東京
    "区": "區",  # 千代田區
    "内": "內",  # 內幸町
    "园": "園",  # 校園、公園
    "来": "來",
    "长": "長",
    "进": "進",
    "实": "實",    # Added 2026-04-26 from production scan
    "诺": "諾",  # イイノホール → 伊伊諾大廳
    "厅": "廳",  # 大廳
    "络": "絡",
    "设": "設",
    "联": "聯",
    "馆": "館",
    "门": "門",
    "发": "發",
    "会": "會",})
```

**When to expand the map:** If a post-annotation scan finds a new Simplified character in any location field, add it to `_LOC_ZH_SIMP_TO_TRAD` **and** immediately DB-patch all existing rows using:
```python
import os, re; from dotenv import load_dotenv; from supabase import create_client
load_dotenv('.env'); sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
MAP = str.maketrans({"诺":"諾", "厅":"廳", ...})  # full map
res = sb.table('events').select('id,location_name_zh,location_address_zh').execute()
for ev in res.data:
    updates = {f: (ev[f] or '').translate(MAP) for f in ['location_name_zh','location_address_zh'] if (ev.get(f) or '') != (ev.get(f) or '').translate(MAP)}
    if updates: sb.table('events').update(updates).eq('id', ev['id']).execute()
```

**Scan pattern** — run after every annotator change or char map expansion:
```python
import re, os; from dotenv import load_dotenv; from supabase import create_client
load_dotenv('.env'); sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
SIMP = re.compile(r'[东来这发会说时问门关对长进现与实变内还单层达诺厅络设联馆园]')
res = sb.table('events').select('id,is_active,location_name_zh,location_address_zh').execute()
bad = [(e['id'][:8], e['is_active'], f, e[f]) for e in res.data
       for f in ['location_name_zh','location_address_zh'] if SIMP.search(e.get(f) or '')]
print(f'Simplified in location fields: {len(bad)}')
[print(f'  {i} active={a} [{f}] {v!r}') for i,a,f,v in bad]
```

**Fields covered:** `location_name_zh` and `location_address_zh` (both main-event and sub-event). `_loc_zh()` is applied instead of `_loc()` for these two fields only.

## GitHub Actions Workflow Rules

- Any `with:` field in an action step whose value is a **pure `${{ expression }}`** (no surrounding text) must be quoted: `path: "${{ steps.x.outputs.y }}"`.
- Bare expressions in `path:`, `name:`, and similar scalar fields cause YAML schema validator warnings in VS Code and some CI linters.
- Any `run:` step whose command contains **both** a `${{ }}` expression **and** shell double-quote characters (e.g. `--input "${{ steps.x.outputs.y }}"`) must use a block scalar (`|`) instead of an inline scalar. Inline scalars mixing `"` and `${{ }}` trigger VS Code YAML extension schema validation warnings. All other `run:` steps may remain inline.
- **Step parity rule**: When multiple workflows share the same tool dependencies (e.g. Playwright, Python packages), they must have identical setup steps. When adding a new setup step to one workflow (e.g. `playwright install chromium --with-deps`), immediately check **all other workflows** for the same dependency and add the step there too. Divergence causes silent failures — missing setup steps do not error at workflow startup, only at the point of use. Example: `researcher.yml` was missing `playwright install` for weeks while `scraper.yml` had it, causing all URL verifications to return `url_verified=False` silently (fixed in commit `d7f4b41`).
