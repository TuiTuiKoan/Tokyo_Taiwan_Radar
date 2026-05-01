---
name: engineer
description: Implementation rules for database migrations, Python scrapers, and Next.js web for the Engineer agent
applyTo: .github/agents/engineer.agent.md
---

# Engineer Skills

Read this at the start of every session before touching any code.

## ⚠️ CRITICAL: Canonical File Paths

> **NEVER write to `.github/skills/agents/engineer/`** — that path has been deleted. The canonical location is:
> `.github/skills/agents/engineer/SKILL.md` and `.github/skills/agents/engineer/history.md`

Same rule applies to ALL agent skills:
| Agent | Canonical path |
|-------|---------------|
| engineer | `.github/skills/agents/engineer/` |
| researcher | `.github/skills/agents/researcher/` |
| scraper-expert | `.github/skills/agents/scraper-expert/` |
| scraper-dev | `.github/skills/agents/scraper-dev/` |
| architect | `.github/skills/agents/architect/` |
| tester | `.github/skills/agents/tester/` |

Writing to a top-level `skills/<name>/` path recreates deleted directories. Always use `skills/agents/<name>/`.

## Database
- Always verify a migration has been applied in Supabase before writing code that depends on it. Check: `SELECT table_name FROM information_schema.tables WHERE table_name = 'X';`
- When adding a DB column, wire up the code that populates it in the same commit. Empty columns = silent data gaps.
- Wrap non-critical DB inserts (logging, analytics) in `try/except`. Never let a failed log write break the main pipeline.
- **`supabase/migrations/` must contain only `NNN_name.sql` files.** Never place `.md` files, smoke-test scripts, validation reports, or any non-migration artifacts in this directory. Supabase CLI and tooling will attempt to run every `.sql` file in this directory as a migration — a misplaced file will cause schema errors or no-op runs. If a migration agent produces a smoke-test or verification file alongside the SQL, place it anywhere outside `supabase/` (e.g. a temp directory or delete it). Example incident: `027_smoke_test.sql`, `027_VALIDATION.md`, `027_VERIFICATION_REPORT.md` were accidentally created in `migrations/` by a previous agent and had to be manually deleted (commit `chore(migrations): remove non-migration 027 artifacts`).
- When a logging table gains new `NOT NULL` columns (e.g. `success`, `duration_seconds`), **both** the success path and the `except` block must write those columns explicitly. Pattern from `scraper_runs`:
  ```python
  # success path
  {"success": True, "duration_seconds": int(time.time() - start)}
  # except block
  {"success": False, "duration_seconds": 0}
  ```
  If only the success path is updated, failure rows leave the column NULL and break `NOT NULL` constraints (or silently insert the default, hiding failures).

## Supabase Realtime

Supabase Realtime is **NOT enabled by default** for tables. Frontend `.on("postgres_changes", ...)` subscriptions will silently never fire unless the table has been added to the publication first.

**Required database step before any Realtime feature can work:**
```sql
ALTER PUBLICATION supabase_realtime ADD TABLE <table_name>;
```

**Required migration pattern:**
1. Create a new migration SQL file: `ALTER PUBLICATION supabase_realtime ADD TABLE <table>;`
2. Apply via Supabase Dashboard SQL editor (or CLI)
3. Only then will the frontend subscription receive events

**Diagnosis:** Supabase Dashboard → Database → Replication — confirm the target table appears in the `supabase_realtime` publication list.

**Frontend subscription rules:**
- Admin pages must subscribe to **both INSERT and UPDATE** — INSERT picks up new rows; UPDATE syncs status changes (confirm/dismiss) across open tabs.
- Always clean up in `useEffect` return: `supabase.removeChannel(channel)`.
- Extract a `fetchRow(id)` helper when both INSERT and UPDATE handlers need to re-fetch the full row (avoids duplicating the SELECT clause).

```ts
// ✅ Subscribe to both INSERT and UPDATE for admin pages
supabase
  .channel("event_reports_changes")
  .on("postgres_changes", { event: "INSERT", schema: "public", table: "event_reports" }, handleInsert)
  .on("postgres_changes", { event: "UPDATE", schema: "public", table: "event_reports" }, handleUpdate)
  .subscribe();
```

## Python
- When changing a function's return type (e.g. `dict` → `tuple`), immediately smoke-test before committing: `python -c "from module import fn; print(type(fn(...)))"`
- Use `getattr(obj, 'attr', default)` when reading an attribute that may not exist on all subclasses.

## Next.js / Sentry
- Never set `autoInstrumentServerFunctions: false` — it silently disables server-side error capture.
- Gate source map upload: `sourcemaps: { disable: !process.env.SENTRY_AUTH_TOKEN }`.

## TSX Component vs Helper — react-hooks/static-components Rule

Next.js 15+ / React 19 lints any `PascalCase` function that returns JSX as a React component. Components declared **inside another component's render body** trigger `react-hooks/static-components` and fail Vercel build.

**Rules:**
- A function returning JSX with `PascalCase` name is treated as a component → must live at module top level (or be `export`ed). Never declare it inside another component body.
- A render-only helper used inline (not as `<Tag />`) must use `camelCase` and be invoked as a plain function call: `{eventLink(event)}`, not `<EventLink event={event} />`.
- If you need closure over parent state, either:
  1. Lift the helper to module scope and pass needed values as props/args, or
  2. Use `useMemo` / `useCallback` to derive the JSX, then render `{memoizedNode}` directly.

```tsx
// ❌ Fails react-hooks/static-components
export default function Page() {
  function SectionHeader({ title }) { return <h2>{title}</h2>; }
  function eventLink(e) { return <a href={...}>{e.name}</a>; } // PascalCase trap if renamed
  return <SectionHeader title="..." />;
}

// ✅ Component at module top level
function SectionHeader({ title }: { title: string }) { return <h2>{title}</h2>; }
export default function Page() {
  return <SectionHeader title="..." />;
}

// ✅ camelCase helper invoked as function call
function renderEventLink(e: Event) { return <a href={...}>{e.name}</a>; }
export default function Page() {
  return <ul>{events.map(e => <li key={e.id}>{renderEventLink(e)}</li>)}</ul>;
}
```

Reference incident: 2026-05-01 `/admin/quality` page first Tester FAIL — `SectionHeader` and `eventLink` declared inside `QualityPage` render body. Fix: hoisted `SectionHeader` to module scope; renamed `eventLink` to `renderEventLink` and called as function.

## OG Image（opengraph-image.tsx）— Edge Runtime 規則

`app/[locale]/events/[id]/opengraph-image.tsx` 使用 `ImageResponse`（Satori 引擎），必須設定 `export const runtime = "edge"`。

**Edge runtime 限制：只能用純 Web API。**

| 可用 | 不可用 |
|------|--------|
| `fetch(url)` | `fetch(url, { next: { revalidate } })` |
| `Response`, `Request`, `TextDecoder` | `next: { tags }`, `next: { revalidate }` |
| `ArrayBuffer`, `Uint8Array` | Node.js `fs`, `path`, `crypto` 模組 |

```ts
// ❌ Edge runtime 拋錯
const res = await fetch(url, { next: { revalidate: 86400 } });

// ✅ 純 Web API，正確
const res = await fetch(url);
```

**Google Fonts text API 子集化：**
- 使用 `?text=...` 參數只取頁面用到的字元，大幅縮小 ArrayBuffer 體積。
- CSS 中 `src:` 與 `url(` 之間可能有空白；regex 必須用 `/src:\s*url\(/`，不可寫死 `/src: url\(/`。

```ts
// ❌ 若 CSS 為 "src:  url(..." 就會 miss
css.match(/src: url\(https:\/\//);

// ✅ 容許任意空白
css.match(/src:\s*url\(https:\/\//);
```

## Bulk Action Pattern (AdminEventTable / AdminReportsTable)

When adding a new bulk operation that operates on a **derived value from selected events** (e.g. common categories, common source, common status):
1. Compute the derived value with `useMemo([selected, events])` — never inline in render
2. Add a loading state (`useState(false)`) guarding the async handler
3. Use `Promise.all(selectedEvents.map(...))` for parallel DB updates — do NOT loop with `await` sequentially
4. Apply optimistic local state update in `setEvents()` after `Promise.all` resolves
5. Only show the derived-value UI when the derived value is non-empty (conditional render in bulk bar)
6. Add i18n keys to all 3 message files using the Python json-module pattern

**Exception — sequential loop required when sub-handler has internal `setState`:**
If the bulk handler calls an existing `handleXxx` that internally calls `setSaving` (or any React state setter), use `await for` loop instead of `Promise.all`. Parallel calls will cause state races.

```ts
// ✅ sequential — safe when handleConfirm calls setSaving internally
for (const id of selectedIds) {
  await handleConfirm(id);
}

// ❌ parallel — causes setSaving race if handleConfirm has internal state updates
await Promise.all([...selectedIds].map(id => handleConfirm(id)));
```

### Checkbox in list rows — wrapper element rule

When a list row is currently a `<button>` and you need to add a checkbox:
- **DO NOT** put the checkbox inside the `<button>` — violates HTML spec (interactive element inside button)
- **Refactor wrapper**: `<button className="w-full ...">` → `<div className="flex items-stretch"> + <label> checkbox </label> + <button className="flex-1 ...">`
- On the checkbox label, add `onClick={(e) => e.stopPropagation()}` to prevent bubble triggering row expand/collapse

```tsx
// ✅ correct structure
<div className="flex items-stretch">
  <label onClick={(e) => e.stopPropagation()} className="flex items-center px-2 cursor-pointer">
    <input type="checkbox" checked={...} onChange={...} />
  </label>
  <button className="flex-1 text-left ..." onClick={handleExpand}>
    {/* row content */}
  </button>
</div>
```

### Bulk action bar placement

Place bulk action bar in the **section header** (flex justify-between), not a bottom footer bar — more intuitive for list sections with variable item counts.

## AdminReportsTable — Protected Feature: Bulk Confirm

⚠️ **This feature MUST NOT be removed** unless a PRD explicitly requests it. Any refactor touching `AdminReportsTable.tsx` must verify all of the following remain intact:

| State / function | Purpose |
|---|---|
| `selectedIds: Set<string>` | Tracks which pending rows are checked |
| `bulkConfirming: boolean` | Loading guard during bulk operation |
| `handleBulkConfirm(rows: ReportRow[])` | Sequential loop calling `handleConfirm` per id, then clears `selectedIds` |

**Row structure** (each pending row):
```tsx
<div className="flex items-stretch">
  <label onClick={(e) => e.stopPropagation()} className="flex items-center px-2 cursor-pointer">
    <input type="checkbox" checked={selectedIds.has(row.id)} onChange={...} />
  </label>
  <button className="flex-1 text-left ..." onClick={handleExpand}>
    {/* row content */}
  </button>
</div>
```

**Bulk action bar** (section header, flex justify-between):
- 「取消選取」→ `t("bulkCancelSelect")`
- 「通過已選取 (n)」→ `t("bulkConfirmSelected", { count })`
- 「全部通過 (n)」→ `t("bulkConfirmAll", { count })`

**Why sequential loop (not `Promise.all`):** `handleConfirm` internally calls `setSaving` (React state setter). Parallel calls cause state races. Always use `for...of` with `await`.

**Incident:** commit `3d45de6` removed bulk confirm alongside Realtime subscription removal. Restored in `4c30ab3`. Do NOT repeat.

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

**Filter display counts pattern:** When a filter dropdown should show per-option counts (e.g. "電影 (12)"), derive them with `useMemo([events])` from the already-loaded `events` state — no extra API call needed:
```ts
const categoryCounts = useMemo(() => {
  const counts: Record<string, number> = {}
  events.forEach(e => { counts[e.category] = (counts[e.category] ?? 0) + 1 })
  return counts
}, [events])
// Render: `${label}${count > 0 ? ` (${count})` : ''}`
```
This pattern applies to any `<select>` filter whose options map 1-to-1 with a field on the `events` array.

**Annotation status label consistency rule:** One status value = one i18n key, used consistently in **all** display surfaces: badge (`getAnnotationLabel`), filter dropdown `<option>`, any column header. Use the **short-form keys**: `t("filterAnnotatedShort")`, `t("filterReviewedShort")`, `t("filterErrorShort")`, `t("filterPendingShort")`. The long-form family (`annotated`, `reviewed`, `error`, `pending`) has been deleted — do not recreate it.

## AdminSourcesTable.tsx — agent_category Sync Rule

`web/components/AdminSourcesTable.tsx` maintains a `SOURCE_TYPE_LABELS` map and a `getFilteredSources` function. Both must be updated whenever a new `agent_category` value is introduced in `discovery_accounts.py`:

1. **`SOURCE_TYPE_LABELS`** — add the new key: `{ ..., <new_category>: "<display label>" }`
2. **`getFilteredSources`** — detect the new category by reading `source.agent_category` directly, NOT by hardcoded ID lists. Hardcoded ID lists silently omit newly discovered sources.

This is a **paired-file rule**: `discovery_accounts.py` (defines agent_category) ↔ `AdminSourcesTable.tsx` (displays it).

## AdminSourcesTable.tsx — i18n Rule: No Hardcoded Labels

**All visible text in `AdminSourcesTable.tsx` must use `t()`.** Never hardcode Chinese/Japanese strings.

Required i18n keys (must exist in all three `messages/*.json`):
| Key | zh | en | ja |
|---|---|---|---|
| `sourcesFilterStatus` | 狀態 | Status | ステータス |
| `sourcesFilterAll` | 全部 | All | すべて |
| `sourcesFilterType` | 來源分類 | Type | 分類 |
| `sourcesEditTypeMap` | 編輯分類對照表 | Edit Type Map | 分類マップを編集 |
| `sourcesEditTypeMapTitle` | 編輯分類對照表 | Edit Source Type Map | 分類マップを編集 |

**Incident:** 2026-05-01 — filter labels `狀態`、`全部`、`來源分類`、`編輯分類對照表` were hardcoded. Fixed in commit `4c30ab3`.

**Rule:** Any new label added to `AdminSourcesTable.tsx` must immediately get a key in all three `messages/` files. Use the Python json-module pattern for edits.

## AdminSourcesTable.tsx — Filter Dropdown Count Pattern (typeCountMap)

When showing per-option counts in a filter `<select>` (e.g. "Peatix 主辦者 (5)"), the count must reflect:
- **Apply** all other active filters (e.g. status/`filter`)
- **Exclude** the filter's own dimension (e.g. type/`selectedType`)

This lets users see how many items they'd get if they switched to that option.

```ts
const typeCountMap = useMemo(() => {
  // Apply status filter only — do NOT apply selectedType
  const statusFiltered = sources.filter(s => {
    if (filter === "implemented" && s.status !== "implemented") return false;
    if (filter === "not-viable" && s.status !== "not-viable") return false;
    if (filter === "candidate" && s.status !== "candidate") return false;
    if (filter === "researched" && s.status !== "researched") return false;
    if (filter === "recommended" && s.status !== "recommended") return false;
    if (filter === "has_issue" && !s.github_issue_url) return false;
    return true;
  })
  const counts: Record<string, number> = {}
  statusFiltered.forEach(s => {
    const type = effectiveTypeMap[s.id] ?? s.agent_category ?? "unknown"
    counts[type] = (counts[type] ?? 0) + 1
  })
  return counts
}, [sources, filter, effectiveTypeMap])

// Render option:
// count > 0 → `${label} (${count})`
// count === 0 → `${label}` (no parentheses, avoid UI noise)
// "all" option → never show count (semantic total, `filtered.length` shown elsewhere)
```

**Rule:** Every multi-dimensional filter should use this "exclude self, apply others" approach. Never count from the fully-filtered result — it would always show N for the active option and mislead for inactive ones.

**Sibling IIFE parity rule:** `AdminSourcesTable.tsx` has two parallel count computations: `typeCountMap` (sources per type) and `eventCountByType` (active events per type). Both must apply the **identical** status-filter logic. When a new status value is added to the `<select>`, add its guard to ALL count IIFEs in the same commit. Adding to only one causes stale counts on the other.

## Scraper Implementation

- Every new scraper source must extend `BaseScraper` (`scraper/sources/base.py`) and implement `scrape() → list[Event]`.
- `source_id` must be stable across runs — it is the upsert dedup key. Use a deterministic hash or platform ID, never a timestamp.
- `raw_title` and `raw_description` store original scraped text. **Never overwrite** them with translated or processed content.
- Date rules: follow the 4-tier cascade in `.github/skills/date-extraction/SKILL.md`. Tier 4 (publish date fallback) fires only when tiers 1–3 all fail.
- Prepend `開催日時: YYYY年MM月DD日\n\n` to `raw_description` whenever `start_date` is known.
- Register every new scraper in `scraper/main.py` → `SCRAPERS` list.
- Validate with `python main.py --dry-run --source <name>` before committing.

## Discovery Accounts Pipeline (`discovery_accounts.py`)

**Year must be dynamic — never hardcoded:**
```python
# CORRECT
_THIS_YEAR = datetime.now(JST).year
query = f"台湾 イベント {_THIS_YEAR}"

# WRONG — requires manual update every year
query = "台湾 イベント 2026"
```
Any query string that contains a year literal must use `_THIS_YEAR` or an equivalent `datetime.now(...)` derivation.

**agent_category paired-file rule:** When adding a new `agent_category` value in `discovery_accounts.py`, **always** update `web/components/AdminSourcesTable.tsx` in the same commit:
1. `SOURCE_TYPE_LABELS` — add `<new_category>: "<display label>"`
2. `getFilteredSources` — add a branch that reads `source.agent_category` directly (do NOT use hardcoded ID lists)

Current agent_category values and their labels:
| `agent_category` | `SOURCE_TYPE_LABELS` label |
|---|---|
| `peatix_organizer` | `"Peatix 主辦者"` |

## After Fixing Any Error
1. Append an entry to `.github/skills/agents/engineer/history.md` (newest at top).
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

## AEO Monitoring — proxy.ts Edge Middleware Rules

`web/proxy.ts` is Next.js Edge middleware (not a server component or API route). All logging inside it must follow Edge Runtime constraints.

### Fire-and-forget logging rule
**Never `await` a Supabase insert inside `proxy`** — this blocks every single request until the DB call completes. Never `throw` either — an uncaught error crashes the middleware and returns 500 for all routes.

Correct pattern:
```ts
// Fire-and-forget: no await, no throw
void fetch(supabaseUrl + "/rest/v1/aeo_visits", {
  method: "POST",
  headers: { "apikey": anonKey, "Content-Type": "application/json" },
  body: JSON.stringify({ ... }),
});
// Continue immediately
return intlMiddleware(request);
```

Use the native `fetch` Web API directly — do NOT use `createClient` from `@supabase/ssr` in `proxy.ts`. The SSR client calls `cookies()` which forces dynamic rendering context and is incompatible with fire-and-forget.

### Bot / AI referral detection pattern
Two independent detection layers (mutually exclusive — UA check takes priority):
1. `BOT_PATTERNS: Array<[RegExp, string]>` — User-Agent regex → bot name label (`GPTBot`, `ClaudeBot`, `PerplexityBot`, etc.)
2. `AI_REFERER_HOSTS: Record<string, string>` — referer hostname → AI source label (`perplexity.ai` → `Perplexity`, `chatgpt.com` → `ChatGPT`, etc.)

If a request matches a bot UA, log as `visit_type='bot'` with `bot_name`. If it has an AI referer but no bot UA, log as `visit_type='ai_referral'` with `ai_source`. Ordinary requests: skip logging entirely.

### Static file exclusion rule
Any file added to `web/public/` (e.g. `llms.txt`, custom JSON) **must also be excluded in the `proxy.ts` matcher regex**. Without exclusion, the intl middleware 307-redirects all requests to `/zh/<filename>`, returning 404.

Matcher pattern (append new static file extensions/names here):
```ts
export const config = {
  matcher: ["/((?!_next|api|.*\\.(?:ico|png|jpg|svg|webp|txt|xml|json)).*)"],
};
```
Current exclusions: `llms.txt` (via `txt` extension), standard static assets. When adding a new `public/` file with an unusual extension, verify the matcher covers it.

## AEO — JSON-LD Rules

### FAQPage visibility requirement
Google requires FAQ content to be **visually present on the page**, not only in JSON-LD. Always add a visible `<dl>` section that mirrors the FAQPage schema content. Omitting the visible section causes Google to reject the rich result.

```tsx
{/* JSON-LD */}
<script type="application/ld+json">{JSON.stringify(faqSchema)}</script>

{/* Visible FAQ — REQUIRED alongside JSON-LD */}
<dl>
  <dt>What is this?</dt>
  <dd>Answer...</dd>
</dl>
```

### JSON-LD layering
- **Global (layout.tsx):** `WebSite` + `SearchAction` + `Organization` via `@graph`
- **Page-level (page.tsx):** `BreadcrumbList`, `CollectionPage`, `ItemList`, `FAQPage`
- Never duplicate WebSite/Organization schemas in page-level files — they are already in layout.

### sitemap.ts — x-default alternates
When adding `alternates.languages` to sitemap entries, always include `x-default` pointing to the canonical locale (zh):
```ts
languages: { "x-default": zhUrl, zh: zhUrl, en: enUrl, ja: jaUrl }
```
Without `x-default`, search engines cannot determine the primary language version.

## AEO — IndexNow Integration

`scraper/indexnow.py` provides `submit_urls(urls)` and `event_urls(uuids)`.

### database.py return type contract
`upsert_events()` returns `list[str]` — the UUIDs of **newly inserted** events (not updates). Callers that only needed the side-effect can safely ignore the return value. Callers that need to act on new events (e.g. IndexNow) should capture and process it.

### scraper.yml env vars required
Both `INDEXNOW_KEY` and `NEXT_PUBLIC_SITE_URL` must be set in the workflow `env:` block. `NEXT_PUBLIC_SITE_URL` is used by `indexnow.py` to construct canonical event URLs.

### Key verification file
The IndexNow key verification file (`web/public/<key>.txt`) must be excluded from the proxy.ts matcher. The current `.txt` wildcard already covers it, but verify if you use a non-standard extension.

## AEO — Topic Aggregation Pages

`web/app/[locale]/cities/[city]/page.tsx` and `web/app/[locale]/categories/[category]/page.tsx` are static aggregation pages (generateStaticParams).

### i18n namespace rules
- City descriptions → `cities.*` namespace in `messages/*.json`
- Category descriptions → `categoryDesc.*` namespace in `messages/*.json`
- Both namespaces must exist in **all three** message files before the page is built; missing namespace causes `t("key")` to return raw key string silently.

### sitemap inclusion
Add city and category pages to `sitemap.ts` with `priority: 0.7` and `changeFrequency: "daily"`. Add them in the **same commit** as the page files — sitemap-only or page-only commits leave dangling entries.

## GitHub Actions Workflow Rules

- Any `with:` field in an action step whose value is a **pure `${{ expression }}`** (no surrounding text) must be quoted: `path: "${{ steps.x.outputs.y }}"`.
- Bare expressions in `path:`, `name:`, and similar scalar fields cause YAML schema validator warnings in VS Code and some CI linters.
- Any `run:` step whose command contains **both** a `${{ }}` expression **and** shell double-quote characters (e.g. `--input "${{ steps.x.outputs.y }}"`) must use a block scalar (`|`) instead of an inline scalar. Inline scalars mixing `"` and `${{ }}` trigger VS Code YAML extension schema validation warnings. All other `run:` steps may remain inline.
- **Step parity rule**: When multiple workflows share the same tool dependencies (e.g. Playwright, Python packages), they must have identical setup steps. When adding a new setup step to one workflow (e.g. `playwright install chromium --with-deps`), immediately check **all other workflows** for the same dependency and add the step there too. Divergence causes silent failures — missing setup steps do not error at workflow startup, only at the point of use. Example: `researcher.yml` was missing `playwright install` for weeks while `scraper.yml` had it, causing all URL verifications to return `url_verified=False` silently (fixed in commit `d7f4b41`).
- **Node.js 24 opt-in**: Any workflow using `actions/checkout@v4` or `actions/setup-python@v5` must include `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` at the **top-level `env:`** block. GitHub mandates Node.js 24 for Actions starting 2025-06-02; without this opt-in, the workflow emits Node.js 20 deprecation warnings. Template:
  ```yaml
  env:
    FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
  ```
  This is a top-level `env:` key (parallel to `jobs:`), NOT a step-level `env:`.

### Scraper/Merger pipeline step order

The daily CI pipeline **must** run steps in this order:

```
main.py → merger.py → annotator.py → annotator.py --fix-reviewed
```

- `merger.py` must come **after** `main.py` so new scraped events are present for deduplication.
- `annotator.py` must come **after** `merger.py` so merged events are re-annotated immediately (not left `pending` until the next cycle).
- `merger.yml` runs separately (3× daily cron: 01:00 / 09:00 / 16:00 UTC) with the same annotator follow-up steps, ensuring cross-source duplicates are cleaned between full scraper runs.

## Discovery Pipeline

`scraper/discovery_accounts.py` is a separate pipeline from `BaseScraper`. It discovers new organizer accounts on external platforms and upserts them into `research_sources`.

### Slot rotation design
- **4 daily slots** (Mon–Thu), derived from weekday: Mon=0, Tue=1, Wed=2, Thu=3.
- Slots 0–2 run `note.com` keyword discovery; Slot 3 runs Peatix group discovery.
- Controlled by `DISCOVERY_SLOT` env var (set by `discovery-accounts.yml` via `$(date +%u) - 1`) or `--slot` CLI arg.
- The `.github/workflows/discovery-accounts.yml` cron runs Mon–Thu only (not Fri–Sun).
- **Adding a new platform**: add a new slot (increment total), add a `_run_{platform}_task()` function, update the `DISCOVERY_SLOT` derivation in the workflow.

### Peatix organizer verification
- `_verify_peatix_group(group_id)` performs an HTTP GET to `https://peatix.com/group/{group_id}` and checks for a non-404 response.
- Verified groups are upserted to `research_sources` with `agent_category='peatix_organizer'`.
- `peatix.py` Layer 3 reads these rows at runtime — no code change needed when a new organizer is discovered.

### Platform-aware upsert
- `agent_category` in `research_sources` determines which scraper picks up the organizer:
  - `'peatix_organizer'` → `peatix.py` Layer 3
  - (future) `'connpass_organizer'` → `connpass.py`
- Always set `agent_category` when upserting a new discovered account.

## Multi-locale Edit Pattern

This codebase stores localized values in parallel columns: `name_ja`, `name_zh`, `name_en`, `description_ja`, `description_zh`, `description_en`, etc.

**Rule:** Any UI component that lets a user view or correct a localized field **must expose all three locale variants simultaneously** — never only the current locale.

**Why:** The Japanese original is often correct (scraped directly from source), while the AI-translated Chinese or English may be wrong. Showing only the current locale hides the other variants and makes it impossible to tell which translation is faulty.

**Canonical pattern (TypeScript):**
```ts
type LocaleKey = "zh" | "en" | "ja";
const LOCALES_ORDER: LocaleKey[] = ["zh", "en", "ja"];
const LOCALE_LABELS: Record<LocaleKey, string> = { zh: "中文", en: "English", ja: "日本語" };

// Prop type for a multi-locale field value
Partial<Record<FieldKey, Partial<Record<LocaleKey, string | null>>>>

// State type for edits
Partial<Record<FieldKey, Partial<Record<LocaleKey, string>>>>

// Render: 3 labeled textareas
LOCALES_ORDER.map((loc) => (
  <div key={loc}>
    <p className="text-xs text-amber-400 mb-0.5">{LOCALE_LABELS[loc]}</p>
    <textarea value={edits[field]?.[loc] ?? ""} onChange={...} rows={2} />
  </div>
))

// Submission: only append non-empty edits
for (const loc of LOCALES_ORDER) {
  const edit = edits[field]?.[loc]?.trim();
  if (edit) reportTypes.push(`fieldEdit:${field}:${loc}:${edit.slice(0, 500)}`);
}
```

**page.tsx — pass all three locale values explicitly (do NOT use locale-aware helpers):**
```ts
eventFields={{
  name: { zh: event.name_zh, en: event.name_en, ja: event.name_ja },
  venue: { zh: event.location_name_zh, en: event.location_name_en, ja: event.location_name },
  // ...
}}
```

> Applies to: `ReportSection.tsx`, any future admin review/correction UI, feedback forms.

## Cross-Platform Environment Variables

GitHub Actions secrets and Vercel environment variables are **completely separate systems**. Never assume a secret set in one platform is available in the other.

**Rule:** When implementing a feature that has components in both GitHub Actions (cron/scraper) and Vercel (API route/webhook), explicitly set required credentials in both platforms.

**LINE bot example — both platforms must have both variables:**
| Variable | GitHub Actions Secrets | Vercel Env Vars |
|---|---|---|
| `LINE_CHANNEL_TOKEN` | ✅ broadcast | ✅ webhook |
| `LINE_CHANNEL_SECRET` | ✅ broadcast | ✅ webhook signature |

Missing a Vercel env var for a webhook causes silent HTTP 401 failures. LINE does **not** retry failed deliveries — follow events are permanently lost.

**Diagnostic checklist when a webhook writes 0 rows:**
1. Check the table directly: `SELECT count(*) FROM line_subscribers`
2. Test INSERT with the same logic manually — confirms schema is not the problem
3. Check the **Vercel** env var list (not just GitHub Actions secrets)
4. If a variable is missing in Vercel, add it; then have the user block + unblock the bot to re-trigger the follow event
