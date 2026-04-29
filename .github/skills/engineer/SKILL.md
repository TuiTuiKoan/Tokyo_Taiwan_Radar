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

## Movie Title Lookup Pattern

When a scraper targets cinema events (`category=["movie"]`), **always call `lookup_movie_titles(name_ja)`** from `scraper/movie_title_lookup.py` before constructing `Event()`:

```python
from movie_title_lookup import lookup_movie_titles
name_zh, name_en = lookup_movie_titles(title)
event = Event(
    ...
    name_zh=name_zh,
    name_en=name_en,
    ...
)
```

- Returns `(None, None)` if not found — GPT annotator fills in as fallback
- Never skip the call: AI translation diverges from official titles (e.g. AI → "赤色的線 輪迴的秘密" vs official → "月老 Till We Meet Again")
- The module uses in-memory `_cache` — no extra latency for repeated titles in one run
- `eiga_com.py` is exempt — it already has native 原題 parsing in `_parse_original_title()`

### gguide_tv 特殊規則 — 日本放送邦題

`gguide_tv` 的 raw_title 使用**日本放送局自訂的本地化邦題**，可能與台灣官方片名完全不同：
- 日本邦題：`スクリュー・ガール　一発逆転婚！！`
- 台灣官方：`螺絲小姐要出嫁`（英文：Miss Rose）

`lookup_movie_titles()` 對此類劇名通常回傳 `(None, None)`（eiga.com 未登錄台灣電視劇）。
GPT annotator 亦會用日文邦題翻譯，結果仍然偏離官方。

**手動 DB patch 規則（gguide_tv / 台灣電視劇）：**
1. 先查 Wikipedia（搜尋日文邦題，通常有對應條目）
2. 或查 IMDb、MyDramaList 取得 zh/en 官方片名
3. **絕對不能**直接翻譯日文邦題作為 name_zh/name_en

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

### SOURCE_TYPE_LABELS completeness rule

`SOURCE_TYPE_LABELS` must always include `"other"` as a catch-all for IDs not mapped in `SOURCE_TYPE_MAP`. If `"other"` is absent, those sources silently disappear from the filter dropdown with no error. The `<option value="other">` must come from the map — never hardcoded separately in the editor modal.

Current canonical set (keep in sync):
`all`, `event_platform`, `academic`, `venue`, `cinema`, `tv`, `government`, `department_store`, `organizer`, `personal`, `peatix_organizer`, `other`, `archived`

### Filter status values — AdminSourcesTable

The status filter dropdown must list **all 6 status values** (plus "全部"). The full set:
`candidate` (候選中) / `researched` (已深度研究) / `recommended` (已推薦) / `implemented` (已建立爬蟲) / `not-viable` (不適合) / `has_issue` (已建立 Issue)

### Derived counts consistency rule

`AdminSourcesTable` computes two derived counts per type: `typeCountMap` (source count) and `eventCountByType` (active event count). **Both must use the identical `statusFiltered` predicate.** Extract one shared subset first:

```ts
const statusFiltered = sourceList.filter((s) => {
  if (filter === "implemented" && s.status !== "implemented") return false;
  if (filter === "not-viable" && s.status !== "not-viable") return false;
  if (filter === "candidate" && s.status !== "candidate") return false;
  if (filter === "researched" && s.status !== "researched") return false;
  if (filter === "recommended" && s.status !== "recommended") return false;
  if (filter === "has_issue" && !s.github_issue_url) return false;
  return true;
});
// Both typeCountMap and eventCountByType must iterate statusFiltered, not sourceList
```

When a new status option is added, update **all three** locations simultaneously: `getFilteredSources`, `typeCountMap` statusFiltered, `eventCountByType` statusFiltered. TypeScript does not detect this mismatch.

### Server-side event counts pattern

When the filter dropdown needs to show active event counts per type, query them server-side in `page.tsx` and pass as a prop:

```ts
// page.tsx (server component)
const { data: eventRows } = await supabase
  .from("events").select("source_name").eq("is_active", true);
const eventCountBySourceName: Record<string, number> = {};
for (const row of eventRows ?? []) {
  if (row.source_name)
    eventCountBySourceName[row.source_name] = (eventCountBySourceName[row.source_name] ?? 0) + 1;
}
// Pass as prop to <AdminSourcesTable eventCountBySourceName={eventCountBySourceName} />
```

In the component, map `scraper_source_name → count`, then group by source type using `effectiveTypeMap`.

### localStorage Override Layer Pattern

When a hardcoded map (e.g. ID → category) needs to be overridable by admin users **without a code deploy**, use the localStorage override layer pattern:

```ts
// 1. Load overrides from localStorage on init
const [typeOverrides, setTypeOverrides] = useState<Record<string, string>>(() => {
  try { return JSON.parse(localStorage.getItem('source_type_overrides') || '{}') }
  catch { return {} }
})

// 2. Merge: user overrides win over defaults
const effectiveTypeMap = { ...SOURCE_TYPE_MAP, ...typeOverrides }

// 3. Draft state for the editor modal — separate from committed state
const [draftOverrides, setDraftOverrides] = useState(typeOverrides)

// 4. Save commits draft to state + localStorage; Cancel discards draft
const handleSave = () => {
  setTypeOverrides(draftOverrides)
  localStorage.setItem('source_type_overrides', JSON.stringify(draftOverrides))
}
```

**Rules:**
- Always initialise `typeOverrides` from `localStorage` in the `useState` initialiser function (lazy init) to avoid SSR/hydration mismatches
- Keep draft state (`draftOverrides`) strictly separate from committed state (`typeOverrides`) — Cancel must not mutate `typeOverrides`
- Use `snake_case` localStorage keys scoped to the feature (e.g. `source_type_overrides`)
- Show override count at the bottom of the modal; highlight overridden rows distinctly (e.g. `bg-green-50`)
- Provide a per-row restore button (「↩」) that deletes the key from `draftOverrides`

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
