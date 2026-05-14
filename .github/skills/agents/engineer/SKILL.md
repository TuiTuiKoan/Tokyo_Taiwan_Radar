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

## Workflow Automation Guardrails

- For alert-driven automation, split into two stages: `triage` first, `auto-fix` second. Never mix high-risk remediation into the triage stage.
- Keep high-risk classes (for example selector drift or source-structure breakage) in human-review only paths; safe auto-fix should only touch deterministic transforms.
- Every LINE alert message must include a direct next action (exact workflow name + trigger mode). A warning without CTA is operational noise.

## Agent Handoff Reliability

- For workflow agents, treat handoffs as a required output path, not optional UI polish.
- If a handoff defines `prompt:`, set `send: true` when the intended behavior is one-click execution.
- Pre-ship check for agent changes: verify target agent names resolve correctly and at least one post-task handoff exists for the expected next action.
- **Every new agent file must include `handoffs:` at creation time.** An agent with no handoffs leaves users stranded after task completion.

## CSS Selector Specificity Pitfalls

- `[attr='x'].class` = same element (no space). `[attr='x'] .class` = descendant combinator (space = different element).
- When combining an attribute selector with a class on the **same element** (e.g., `data-preserve-theme` and `group` on the same `<Link>`), never insert a space between them.
- For theme-exception rules like `[data-preserve-theme='light'].group:hover h2`, verify: (1) the attribute and the class are on the same DOM element, (2) combined specificity beats any competing rule, (3) use `getComputedStyle` via Playwright to confirm hover color changes.

## TypeScript `void` Operator Pitfall (TS2873)

`void expr` evaluates `expr` and returns `undefined`. Placing `void` before a ternary **condition** makes the condition permanently falsy:

```ts
// ❌ TS2873: 'void event' is always falsy — ternary never takes true branch
void event ? getEventName(event, locale) : undefined;

// ✅ If you want to call for side effect only:
getEventName(event, locale);   // or just delete the line if unused

// ✅ If you want to suppress an unused variable warning:
const _name = getEventName(event, locale);
```

**Rule:** When removing a feature that used an import, **always remove the import too**. Unused imports: (1) increase bundle size, (2) may trigger TS "unused variable" warnings in strict mode, (3) silently mislead future readers into thinking the symbol is used.

**Incident:** 2026-05-14 — `opengraph-image.tsx` punk Bauhaus redesign removed title rendering but left `void event ? getEventName(...) : undefined` as dead code. TS2873 caught it at compile time (commit `4d8b873`).


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
- **Every migration that creates a new table MUST include explicit `GRANT` statements** (Supabase policy change, effective October 30, 2026). Without them, PostgREST/supabase-js returns `42501` permission error silently. Migration `069_explicit_grants.sql` retroactively covers all pre-existing tables. Use the tier template in `.github/instructions/database.instructions.md §GRANT template`:
  - **Tier A** (public-read): `GRANT SELECT ON ... TO anon, authenticated, service_role;`
  - **Tier B** (admin-only): `GRANT SELECT, INSERT, UPDATE, DELETE ON ... TO authenticated, service_role;`
  - **Tier C** (service-role only): `GRANT SELECT, INSERT, UPDATE, DELETE ON ... TO service_role;`
  Always `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` before adding GRANTs.
- **GRANT scope を決める前に「誰が書くか」を Python コードから逆引きする。** RLS ポリシーのみ参照すると書き込み GRANT が漏れる。典型的な漏れパターン：`scraper_runs`・`research_reports` は scraper/annotator が service_role で INSERT するため `service_role INSERT` が必要。`creators` は admin UI から `authenticated` が CRUD するため `authenticated CRUD` が必要。

## annotation_status エラーイベントの定期リセット

`annotator.py` は `annotation_status='pending'` のみ処理する。`'error'` になったイベントは**自動リトライされない**。

**確認コマンド（定期的に実行）：**
```python
res = sb.table('events').select('id,name_ja', count='exact') \
    .eq('annotation_status','error').eq('is_active', True).execute()
print(f"error count: {res.count}")
```

**リセット手順：**
```python
ids = [r['id'] for r in res.data]
sb.table('events').update({'annotation_status': 'pending'}).in_('id', ids).execute()
# その後 python annotator.py を実行
```

**注意事項：**
- `daily_report.py` は `.limit(5)` でエラー件数を表示するため、実際の件数と一致しない。COUNT で別途確認すること。
- 薄い `raw_description`（1行のみ）の sub-event も、親イベントのコンテキストを参照することで正常アノテーション可能。
- error 件数が多い場合は `annotator.py` の GPT JSON パースロジックに問題がある可能性もある（レスポンス形式の変化等）。

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
- **Create the Supabase client INSIDE `useEffect`** — never at component top level. Top-level creation creates a stale closure risk: the `useEffect` captures the initial instance and may reference a stale/invalidated client after re-renders.
- Admin pages must subscribe to **both INSERT and UPDATE** — INSERT picks up new rows; UPDATE syncs status changes (confirm/dismiss) across open tabs.
- Always clean up in `useEffect` return: `supabase.removeChannel(channel)`.
- Extract a `fetchRow(id)` helper when both INSERT and UPDATE handlers need to re-fetch the full row (avoids duplicating the SELECT clause).

```tsx
// ✅ 正確：在 useEffect 內部建立 client，避免 stale closure
useEffect(() => {
  const rt = createClient();
  const channel = rt
    .channel("table_changes")
    .on("postgres_changes", { event: "INSERT", schema: "public", table: "t" }, handleInsert)
    .on("postgres_changes", { event: "UPDATE", schema: "public", table: "t" }, handleUpdate)
    .subscribe();
  return () => { rt.removeChannel(channel); };
}, []);

// ❌ 錯誤：在頂層建立 client 再傳入 effect（stale closure 風險）
const supabase = createClient();
useEffect(() => {
  const channel = supabase.channel(...); // 可能捕捉到舊實例
}, []);
```

**Server Component + Realtime 分離模式:**

Server Component 中的動態 UI（badge、計數器）如果需要即時性，**必須**拆出為 Client Component：

```tsx
// AdminTabNav.tsx（Server Component）
const pending = await getPendingCount();
return <AdminReportsBadge initialCount={pending} />; // Client Component

// AdminReportsBadge.tsx（Client Component）
const [count, setCount] = useState(initialCount);
useEffect(() => {
  const rt = createClient();
  const ch = rt.channel("badge")
    .on("postgres_changes", { event: "INSERT", ... }, () => setCount(c => c + 1))
    .on("postgres_changes", { event: "UPDATE", ... }, async () => setCount(await fetchCount()))
    .subscribe();
  return () => { rt.removeChannel(ch); };
}, []);
```

Reference incident: `AdminTabNav` badge（2026-05-02）— SSR-only badge 在報告提交後數字不更新，直到建立 `AdminReportsBadge` client component 才修復（commit `4a71258`）.

```ts
// ✅ Subscribe to both INSERT and UPDATE for admin pages
supabase
  .channel("event_reports_changes")
  .on("postgres_changes", { event: "INSERT", schema: "public", table: "event_reports" }, handleInsert)
  .on("postgres_changes", { event: "UPDATE", schema: "public", table: "event_reports" }, handleUpdate)
  .subscribe();
```

## Next.js SSR 快取無效化（`router.refresh()`）

**Admin Client Component 執行 mutation 後導航回 SSR 頁面，必須先呼叫 `router.refresh()`。**

Next.js App Router 的 router cache 不會因為 `router.push()` 自動失效；若省略 `router.refresh()`，SSR 頁面將繼續顯示 mutation 前的快取資料（如舊的 `is_active`、`annotation_status`）。

```ts
// ❌ mutation 後只 push — 頁面仍顯示舊資料
await saveToDb(data);
router.push('/admin');

// ✅ 先 refresh 再 push — 強制 SSR 頁面重新執行 Server Component
await saveToDb(data);
router.refresh();
router.push('/admin');
```

**適用場景（兩種更新模式，應同時部署）：**

| 場景 | 解法 |
|------|------|
| 同一 tab 內的即時 row 更新（新報告、狀態變更） | Supabase Realtime 訂閱（`INSERT` + `UPDATE`）|
| 跨頁面導航後列表顯示最新資料 | `router.refresh()` before `router.push()` |

**規則：** 任何 Admin 頁面的 save / confirm / dismiss handler，只要後面接 `router.push()`，一律在其前加 `router.refresh()`。這是 Next.js App Router 的必要模式，不是 optional 優化。

## Python
- When changing a function's return type (e.g. `dict` → `tuple`), immediately smoke-test before committing: `python -c "from module import fn; print(type(fn(...)))"`
- Use `getattr(obj, 'attr', default)` when reading an attribute that may not exist on all subclasses.
- **Pipeline parity rule:** Any post-processing step added to CI workflow (`scraper.yml`) must also be called in `main.py`'s normal (non-dry-run) flow. Otherwise manual scraper runs produce incomplete results. Current full pipeline in `main.py`: scrape → merger → annotate → `enrich_movie_titles()` → `enrich_person_names()` → IndexNow. Enrich functions are idempotent — double execution (main.py + CI) is safe (just extra DB queries). When adding a new enrichment function: (1) add to `main.py` after `annotate_pending_events()`; (2) add CLI flag + step to `scraper.yml`.
- **Inline Python safety rule:** Never use `python3 -c "..."` or heredoc `python3 << 'PY' ... PY` for scripts that contain f-strings with `{` / `}`. Shell history pollution can inject malicious fragments into f-string braces, causing SyntaxError or silent code execution. **Rule:** If inline Python fails with SyntaxError pointing at a brace `{`, immediately switch to `create_file /tmp/<name>.py` + `python3 /tmp/<name>.py`. File-based execution is fully isolated from the shell.
- **`requests.Session()` must always mount HTTPAdapter with Retry**: Any scraper using `requests.Session()` must mount a retry adapter in `__init__`. Without it, a single transient network blip from GitHub Actions runners raises `Max retries exceeded` and triggers Sentry. Required pattern:
  ```python
  from requests.adapters import HTTPAdapter
  from urllib3.util.retry import Retry

  _retry = Retry(
      total=3,
      backoff_factor=2,
      status_forcelist=[429, 500, 502, 503, 504],
      raise_on_status=False,
  )
  self._session.mount("https://", HTTPAdapter(max_retries=_retry))
  self._session.mount("http://", HTTPAdapter(max_retries=_retry))
  ```
  Backoff: 2s → 4s → 8s. Apply to both `https://` and `http://` mounts.

## Next.js / Sentry
- Never set `autoInstrumentServerFunctions: false` — it silently disables server-side error capture.
- Gate source map upload: `sourcemaps: { disable: !process.env.SENTRY_AUTH_TOKEN }`.

## Homepage vs EventCard — Two Render Paths

事件卡片在本專案有**兩條獨立渲染路徑**，修改前必須同時檢查：

| 路徑 | 檔案 | 用途 |
|------|------|------|
| 共用元件 | `web/components/EventCard.tsx` | saved、category、search 等其他頁面 |
| 首頁 inline | `web/app/[locale]/page.tsx`（行 ~290 的 `events.map`） | **首頁專用**，不 import EventCard |

**修卡片視覺前的 SOP**：
1. `grep -rn '<EventCard\|EventCard ' web/app/ web/components/` 列出所有 call site。
2. 確認首頁使用的渲染路徑（首頁是 inline，不是 EventCard）。
3. 共用邏輯（`getCityLabel`、日期格式、地址解析等純函式）抽至 `web/lib/<name>.ts`，兩處 import；切忌在兩處複製貼上同樣邏輯。
4. Vercel 部署後驗證：`curl https://tokyotaiwanradar.com/zh | grep -c '<新元素 class>'`，期望非 0。

Reference: 2026-05-05 城市徽章兩輪才生效（commit `5a29c13` → `9f4b468`）。

## Event Detail Page — Performer Display Priority

`web/app/[locale]/events/[id]/page.tsx` 的 performer 顯示邏輯必須依照以下優先序：

1. **zh/en locale + performer_zh/en 存在** → `getEventPerformer(event, locale)`（多語言欄位優先）
2. **performers[] 非空** → `performers[].join("、")`（日文多人列表 fallback）
3. **fallback** → `getEventPerformer(event, locale)`

**關鍵規則**：`performers[]` 是**日文陣列**，永遠不可作為 zh/en locale 的主要顯示來源。新增 `performer_zh`/`performer_en` 欄位後，必須同步更新此優先序，否則新欄位永遠不會被 end-user 看到（隱性迴歸）。

Reference incident: 2026-05-09 — migration 054 新增多語言欄位後 UI 未同步，zh 頁面始終顯示日文（commit `2e6f4c2`）。

## performer / performers[] / performer_zh/en — 三欄架構

| Field | Type | 職責 |
|-------|------|------|
| `performer` | `TEXT` | 日文單人主表演者；annotator GPT/regex 輸出；`getEventPerformer()` fallback 錨點 |
| `performer_zh` / `performer_en` | `TEXT` | performer 的語言翻譯（一對一對應）；GPT 填入或人工設定 |
| `performers[]` | `TEXT[]` | 多人顯示陣列；學術研討會全體發表者；annotator 自動 sync 自 `performer` |

**⚠ 絕不可刪除 `performer`**：`performer_zh/en` 錨定於它；34+ 處程式碼引用它；`performers[]` 有多人時翻譯欄位才有意義。

**Auto-sync 規則（commit `4526d3a`）**：annotator 滿足以下四個條件時自動設 `performers = [performer]`：
1. 本次 pass 設定了 `performer`
2. 現有 `performers[]` 為空/null
3. GPT 本次未回傳 `performers` 陣列
4. `performers` 未在 `field_corrections` 保護中

此機制確保 UI 永遠能從 `performers[]` 讀取，不需在前端 fallback 回 `performer`。

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

### Sticky filter + bulk action container

Filter bar and bulk action bar **must be wrapped in a single sticky container** (`sticky top-14 z-20`). Separate sticky elements for each bar cause jittering on scroll. Incident: commits `15d6ab3`→`bf22756`.

### Bulk add category (AdminEventTable)

The bulk action bar includes a "新增分類" row with a multi-select category picker (same `CATEGORY_GROUPS` layout as inline editor). Implementation:
1. State: `bulkAddCatPending: Set<string>` tracks pending selections, `bulkAddCatOpen: boolean` toggles dropdown
2. Merge: `new Set([...prevCategory, ...catsToAdd])` — never duplicates
3. Writes `category_corrections` for AI feedback loop (same as single-event category edit)
4. Auto-resets `selected` Set on success (same as bulk remove)

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

## Admin Quality Page — Supabase Query Rules

**Quality page `is_active` filter rule:** Every Supabase query on the quality page (`/admin/quality`) must include `.eq("is_active", true)`. Without it, deactivated events appear in the list; clicking them returns 404 because the detail page only renders active events. Apply to **all** section queries — `missingAddr`, `missingCat`, `reviewedMissing`, `annotatedNoCat`, and any future additions.

**Quality section actionability rule:** Only include a Quality section if its value can be cleared to zero by user action (fix button / batch action) or by an automated process running within a reasonable interval. If a section's value persists indefinitely due to scheduling (e.g. archive cron runs once daily, so daytime-expired events always appear) **and** no actionable button exists, remove the section entirely. Display of permanently non-zero unactionable data erodes trust in the quality page. Reference incident: expired-but-active section removed in commit `cd4cc29`.

**`missingAddr` filter exclusion list:** The "缺地址" section must exclude all of the following:
- DB: `location_name` containing `「オンライン」` (online events) — `.not("location_name", "ilike", "%オンライン%")`
- DB: `location_name` containing `「電視頻道」` (TV channel events)
- DB: events with `source_name = 'gguide_tv'` (TV guide source)
- DB: `location_name` containing `〒` (address already embedded in name) — `.not("location_name", "like", "%〒%")`
- DB: `location_name` containing `・` (multi-city events — `location_name` uses `・`-joined city names by convention; no single address exists)
- Client: short geographic name ≤6 chars with no spaces (e.g. `東京`, `香港`, `岡山`, `文京区` — no actionable address)

~~**Archive cutoff 一致性規則：** `database.py` 的 `archive_ended_events()` cutoff 必須與 quality page 的 `today` 截止一致。~~

> **⚠️ archiver 已刪除（2026-05-06）**：`archive_ended_events()` 已從 `database.py` 和 `main.py` 完全移除。Quality page 的截止邏輯不再有對應的自動下架機制；事件 `is_active` 改為純手動管理。此規則已廢止。

**Admin list page link rule:** Event hyperlinks in admin list pages (quality, reports, etc.) must point to `/{locale}/events/{id}` (detail page, `target="_blank"`), **not** `/{locale}/admin/{id}` (edit page). Quality pages are for review, not editing.

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

**Namespace placement rule:** Always use `data["<namespace>"]["key"] = value`, never `data["key"] = value` (top-level). next-intl `t("key")` only searches within the namespace declared in `useTranslations("<namespace>")` — missing keys silently render as the key name string (no error thrown). Confirm the target namespace from the component's `useTranslations()` call:

| Component / Usage | Namespace |
|---|---|
| FilterBar location/time options | `filters` |
| Category labels, group names | `categories` |
| Other keys | Check `useTranslations("X")` at the call site |

After adding a key, verify placement with `grep -n "newKey" web/messages/zh.json` — line number should be within the expected block, not at the bottom of the file (top-level).

Reference incident: `locationOverseas` written to top-level (L400+) instead of `filters.{}` (L10–L40) — production FilterBar rendered key name string, timeMode default disappeared (commit `049edd8`).  

## FilterBar timeMode 預設值規則

`FilterBar.tsx` 的每個 timeMode 切換必須同步設定合理的 URL 預設值：

| 切換到 | 動作 |
|--------|------|
| `active` | 清空 `from`/`to`，立即 push |
| `all` | 清空 `from`/`to`，立即 push |
| `past` | 若 `to` 為空，預填今日（`new Date().toISOString().slice(0,10)`），立即 push |

**Rule:** 不能讓 `EventListClient` 在 URL 參數不足時猜測 mode 的含義。每個 mode 必須有完整的 URL 狀態才能正確過濾。

```ts
// ✅ 正確：切換 past 時預填 to=today
} else if (e.target.value === "past") {
  const today = new Date().toISOString().slice(0, 10);
  setDraft((prev) => {
    const next = { ...prev, timeMode: "past", to: prev.to || today };
    pushWith(next);
    return next;
  });
}
```

**Reference incident:** 2026-05-14 — 切換 `past` 後畫面不動，因 `from`/`to` 皆空，EventListClient past 分支無任何過濾條件執行（commit `2ed3c7b`）。

**zsh `git add` with glob bracket paths:**
Any path containing `[...]` (e.g. `web/app/[locale]/page.tsx`) will fail in zsh with `no matches found` because zsh expands brackets as glob patterns.

**Rule:** Always wrap such paths in single quotes:
```bash
# ❌ fails in zsh
git add web/app/[locale]/page.tsx

# ✅ correct
git add 'web/app/[locale]/page.tsx'
```
Applies to all shell operations: `git add`, `cp`, `mv`, `cat`, etc.

## GITHUB_TOKEN Permission Wording Sync

When touching any implementation or docs related to `--create-issue` and `GITHUB_TOKEN`, enforce one canonical wording only:

* Fine-grained PAT: `Issues: write + Metadata: read`
* Classic token: `repo` scope

In the same change set, sync all related layers:

1. Runtime/error text in `scraper/update_source.py`
2. Operational docs in `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md`
3. Rotation instruction in `.github/instructions/token-rotation.instructions.md`
4. Agent usage docs in `.github/agents/researcher.agent.md`
5. Lifecycle summary in `.github/SECRETS_LIFECYCLE.md`

Never leave non-standard Issues permission wording (e.g. the `&`-separated form) in any tracked file.

## Secrets Checklist Ownership

`docs/GITHUB_TOKEN_SYNC_CHECKLIST.md` is the single source of truth for the token sync checklist.

* `.github/TOKEN_SYNC_CHECKLIST.md` must remain a redirect stub only.
* Do not maintain duplicate checklist content in multiple files.
* For public repo safety, examples must use placeholders (`github_pat_xxx`), never real values.

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

### When reorganizing category groups (moving categories between groups)
- Modify **only** `CATEGORY_GROUPS` in `web/lib/types.ts` — no component code changes needed.
- `AdminEventForm.tsx`, `ReportSection.tsx`, and `AdminReportsTable.tsx` all read `CATEGORY_GROUPS` at runtime; they auto-reflect any reorganization.
- `group_knowledge` canonical members: `business`, `academic`, `lecture`, `taiwan_japan`.
- `group_lifestyle` includes: `competition`, `workshop`, `exhibition`, `books_media`, `tv_program`, `healthcare`.

**Incident:** 2026-05-01 — `competition`, `workshop`, `exhibition`, `books_media`, `tv_program` moved from `group_knowledge` → `group_lifestyle` (commits `a07b792`, `5b66c33`). Only `CATEGORY_GROUPS` in `types.ts` required changing.

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

**Work dropdown modal rule:** The "＋ 建立新作品" entry in the per-row work `<select>` dropdown must call `setShowCreateWorkModal(true)` — **never** use `<a href>` or `router.push`. This keeps the UX consistent with the bulk action bar "＋ 新增作品" button. Reference: commit `4a266a1`.

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

## Admin Tab Nav Sync Rule

All admin pages (`web/app/[locale]/admin/*/page.tsx`) share a **manually duplicated** tab nav bar. Every page must list the **exact same tabs in the exact same order**:

```
Events → Announcements → Reports → Stats → Quality → Research → Sources → Users → Creators → SEO-AEO
```

**Current page** renders as `<span>` (no link, visually distinct); all others render as `<Link>`.

### When adding a new admin sub-page
1. Add the tab link to **all 10 existing admin pages** in the same commit.
2. Add the new page's own tab nav with the full set of tabs.
3. Add `flex-wrap` to the tab container if not already present.
4. Add i18n key for the new tab label to all three `messages/*.json`.

### Verification command
```bash
grep -roh 'admin/[a-z_-]*' web/app/\[locale\]/admin/*/page.tsx | sort | uniq -c | sort -rn
```
Every route slug must appear the **same number of times** (= total number of admin pages). If any count differs, a page is missing that tab.

**Incident:** 2026-05-01 — announcements/page.tsx had only 5 tabs while admin main page had 10. Fixed in commit `1f37bb4`.

## Scraper Implementation

- Every new scraper source must extend `BaseScraper` (`scraper/sources/base.py`) and implement `scrape() → list[Event]`.
- `source_id` must be stable across runs — it is the upsert dedup key. Use a deterministic hash or platform ID, never a timestamp.
- `raw_title` and `raw_description` store original scraped text. **Never overwrite** them with translated or processed content.
- Date rules: follow the 4-tier cascade in `.github/skills/date-extraction/SKILL.md`. Tier 4 (publish date fallback) fires only when tiers 1–3 all fail.
- Prepend `開催日時: YYYY年MM月DD日\n\n` to `raw_description` whenever `start_date` is known.
- **New scraper checklist — all 4 steps required:**
  1. Create `scraper/sources/<name>.py` extending `BaseScraper`
  2. Register in `scraper/main.py` → `SCRAPERS` (import + add instance)
  3. **Insert a row in `research_sources`** with `status='implemented'`, `scraper_source_name=<key>`, and a valid `url`. Skipping this causes `researcher.py` to re-report the source as a new candidate and triggers a `⚠️ WARNING` in CI logs every day.
  4. Validate: `python main.py --dry-run --source <key>` returns events cleanly
- `_warn_unregistered_scrapers()` in `main.py` runs on every non-dry-run and emits a WARNING for any scraper key missing from `research_sources`. Check CI logs if you see `⚠️ scraper(s) NOT registered`.
- **Auto-QA via `event_reports` queue (2026-05-01):** New automated content-quality checks must write findings into `event_reports` with an `auto_*` prefix in `report_types[]` (e.g. `auto_qa_simplified_zh`, `auto_qa_missing_address`). Do NOT build a separate admin queue — the existing `/admin/reports` confirm/dismiss flow handles auto-findings unchanged. Always dedup against existing rows of the same `auto_*` type per `event_id` — check **ALL statuses** (`pending`, `confirmed`, `dismissed`), not just `pending`. A confirmed/dismissed report means the admin has already reviewed it; re-creating it undoes admin work. Also dedup within a single run via in-memory set. See `scraper/auto_qa.py` and engineer `history.md` 2026-05-01 / 2026-05-05.
- **`SIMP_RE` / `SC_ONLY` / `annotator._SIMP_TO_TRAD` char addition rule (2026-05-01, updated 2026-05-11):** Only add a char when its Traditional Chinese / Japanese form is **a different glyph**. Verify each candidate via CC-CEDICT or kanji.jitenon.jp **before** adding. Counter-example: `亮` is identical in Trad/Simp (`照亮` is valid Trad) and triggered a false positive in production. When adding a new char, update **all three** simultaneously: `annotator.py._SIMP_TO_TRAD`, `auto_qa.py.SIMP_RE`, and `auto_qa.py.SC_ONLY`. Ensure `SC_ONLY ⊆ _SIMP_TO_TRAD_RAW.keys()` — detection must never find chars that fix cannot convert. See scraper-expert `history.md` 2026-05-01 and engineer `history.md` 2026-05-11.
- **Cron-driven slot rotation modulo wrap (2026-05-01):** When N weekdays drive a `(DAY-1) % M` slot selector with `M < N`, days M+1..N silently re-run slots 0..(N-M-1). Acceptable when slots are idempotent (search + `skip_hint` dedup); NOT acceptable for slots requiring fixed cadence (e.g. Peatix slot 3 only on Thursdays). Override via `DISCOVERY_SLOT` env on extra cron entries, or raise `SLOT_COUNT`. See `discovery-accounts.yml` and engineer `history.md` 2026-05-01.
- **Multi-city tour detection — never hardcode venue address (2026-05-01):** Any scraper with a hardcoded `location_address` must add multi-city detection logic. Pattern for `taiwan_cultural_center.py`:
  - Check `description + name` for ≥2 regional keywords (`_MULTI_CITY_REGIONS = ["北海道", "大阪", "京都", "神奈川", "福岡", "名古屋", "仙台"]`)
  - Threshold = **2** (not 1) to avoid false positives where a Tokyo event's description merely mentions another city
  - When triggered: set `location_name` to a generic tour label (e.g. `台湾文化センター（全国巡回）`) and set `location_address = None`
  - For DB-patching already-scraped tours: update `location_name`, clear `location_address` directly in Supabase

## Broadcast / Public Output Quality Gate

**Any public-facing output** (LINE weekly broadcast, RSS feeds, API responses, etc.) must exclude `annotation_status='pending'` events. Pending events have incomplete data (null `name_zh`/`name_en`, missing category, etc.) and will surface as Japanese-only or broken entries to end users.

**Rule:** All broadcast/feed queries must include `.in_("annotation_status", ["annotated", "reviewed"])` — do NOT assume all `is_active` events are fully annotated.

**Reference:** `weekly_line_broadcast.py` `_fetch_upcoming_events()` — pool filter added in commit `b2864ea` after pending events appeared with Japanese-only titles in the LINE weekly broadcast.

## Person Name Lookup Pattern

GPT-4o-mini translates katakana person names phonetically, producing wrong Chinese names (e.g. ギデンズ・コー → 「紀德恩」instead of 「九把刀」). `scraper/person_name_lookup.py` corrects this for **all events**, not just movies.

**Two pipelines:**

### Movie events (structured lookup via eiga.com)
1. **eiga.com movie page** → extract cast/crew list (role, katakana name, person URL)
2. **eiga.com person page** → extract English name (`英語表記`) and origin country (`出身`)
3. **zh.wikipedia** → search English name + origin country for Chinese name. Fallback: **ja.wikipedia** CJK title or zh interlanguage link.
- Uses `lookup_person_names(name_ja)` → returns all cast/crew.
- Wikipedia uses `strict=False` (default) — allows CJK title fallback because input is known to be a person.

### Non-movie events (general katakana extraction)
1. **Regex extraction**: `extract_katakana_names(text)` extracts katakana patterns with ・ separator (e.g. `リン・チーリン`, `ツァイ・インウェン`).
2. **eiga.com person search** → if found, get English name + origin.
3. **Wikipedia lookup** with `strict=True` — **requires** person-keyword match (zh.wikipedia) or zh interlanguage link (ja.wikipedia). No CJK title fallback.
- Uses `lookup_single_person(ja_name)` → returns single PersonInfo or None.
- Noise filtering: max 3 ・-parts, max 7 chars/part, noise suffix exclusion.
- Self-filtering: non-person terms (place names, brands) naturally return None from Wikipedia.

**Critical rules:**
- **strict mode prevents false positives:** Without strict mode, ja.wikipedia returns unrelated CJK titles (e.g. `リン・インジュ` → `安永亜季`). Always use `strict=True` for general (non-movie) lookups.
- **Character name prefix stripping:** eiga.com cast names include character names (e.g. 「孝綸（シャオルン）クー・チェンドン」). Must use `_CHAR_NAME_PREFIX_RE` regex to strip.
- **Wikipedia disambiguation requires origin country:** Bare English names return unrelated results. Always append the origin country to the search query.
- **desc_zh fix requires GPT:** Wrong names in desc_zh are GPT-generated phonetic translations. Must use GPT-4o-mini (`_fix_person_names_gpt()`) to identify and replace them.
- **desc_en fix uses direct replacement:** Katakana names leaked into English text → replace with English name.

**Annotator integration:**
- `enrich_person_names()` in `annotator.py` — queries ALL events (excl. `eiga_com` + already reviewed), routes movie vs non-movie, fixes desc_zh via GPT and desc_en via direct replacement.
- CLI: `python annotator.py --enrich-person-names`
- Caching: in-memory per movie and per person URL within a single run.

## Auto-Scraper Layer B — `generate.py`

`scraper/auto_scraper/generate.py` is the Phase 2 codegen + sandbox validation pipeline. It reads a `research_sources` row, fetches sample HTML via Playwright, calls GPT-4o for a `spec.json`, validates via `spec_to_code.render()`, then dry-runs the generated scraper in a subprocess.

### Scope boundaries (intentional non-scope)
Phase 2 does NOT:
- Open PRs or push branches
- Register the generated scraper into `main.py`'s `SCRAPERS` list
- Write to `events` or `scraper_runs` tables
Generated code lives in `scraper/auto_scraper/runs/<source_id>/` and is **excluded from git** (`.gitignore`).

### Sandbox security — env allowlist
The validation subprocess receives **only** these env vars:
```
PATH, HOME, PYTHONUNBUFFERED, PLAYWRIGHT_BROWSERS_PATH, TMPDIR, LANG, LC_ALL
```
`SUPABASE_*`, `OPENAI_API_KEY`, `GITHUB_TOKEN`, `LINE_*` are **never** passed to the sandbox. Passing secrets to a subprocess running untrusted LLM-generated code is a critical security violation.

```python
sandbox_env = {k: os.environ[k] for k in (
    "PATH", "HOME", "PYTHONUNBUFFERED", "PLAYWRIGHT_BROWSERS_PATH",
    "TMPDIR", "LANG", "LC_ALL",
) if k in os.environ}
```

### Cleanup — defense in depth
The temporary `sources/_auto_<name>.py` file must be deleted via **both**:
1. `try/finally` block (runs on normal exit and exceptions)
2. `atexit.register(cleanup_fn)` (runs if process is killed mid-flight)

Using only one is insufficient. Missing the `atexit` means a SIGTERM leaves the temp file in `sources/`.

### Budget guard
`generate.py` estimates token cost **before** committing the LLM call. If estimated cost exceeds `DEFAULT_BUDGET_USD` ($1.50), raise `GenerateError("budget-exceeded", ...)` and abort.

```python
GPT4O_INPUT_COST_PER_1M = 2.50   # verify against current OpenAI pricing
GPT4O_OUTPUT_COST_PER_1M = 10.00
```
These constants must be reviewed whenever OpenAI changes pricing. Last verified: 2026-05.

### 7-day retry cooldown
Each `research_sources` row may only be retried once every 7 days (checked via `auto_scraper_attempted_at`). A `GenerateError` updates `auto_scraper_status` and `auto_scraper_failed_reason` but does NOT reset the cooldown — the next attempt must wait the full 7 days from the failed attempt.

### CLI flags
```bash
python -m auto_scraper.generate --source-id <int>
  [--mock-llm spec.json]   # offline testing: read spec from file
  [--skip-sandbox]         # skip subprocess dry-run (unit tests)
  [--dry-run]              # no DB writes
  [--output-dir PATH]      # override runs/<source_id>/
  [--budget-usd FLOAT]     # override DEFAULT_BUDGET_USD
```

### Required DB migration (migration 032)
```sql
ALTER TABLE research_sources
  ADD COLUMN IF NOT EXISTS auto_scraper_status TEXT,
  ADD COLUMN IF NOT EXISTS auto_scraper_pr_url TEXT,
  ADD COLUMN IF NOT EXISTS auto_scraper_failed_reason TEXT,
  ADD COLUMN IF NOT EXISTS auto_scraper_attempted_at TIMESTAMPTZ;
```

### OpenAI Org-Level Quota Monitoring (separate concern from per-call budget)

`--budget-usd` (default $1.50/source) is a **per-run** safeguard. It does NOT protect against **org-level monthly quota** exhaustion.

- Once OpenAI org quota is hit, **all** calls return 429 `insufficient_quota` — not just auto-scraper, but also `annotator.py`, `researcher.py`, `enrich_addresses.py`, etc. The entire pipeline halts silently if this happens during a cron window.
- Per-call budget guards are **necessary but not sufficient**. Mitigation layers, in priority order:
  1. **Daily dev report** (`daily-dev-report.yml`, 02:00 JST) should surface the OpenAI billing dashboard URL so the on-call dev can spot-check usage.
  2. **Future**: poll `/v1/usage` endpoint and post a LINE alert when org-level usage > 80% of monthly cap. Treat as Tier-1 ops alert.
  3. **Manual**: at start of any large batch run (e.g. auto-scraper batch e2e), check the OpenAI usage page first.
- Reference incident: 2026-05-02 — mid-batch e2e exhausted monthly quota. All subsequent calls 429'd, batch silently aborted.

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

## Auto Research Pipeline (`auto_research.py`)

`scraper/auto_scraper/auto_research.py` is the Phase 1.5 AI research pipeline. It reads `research_sources` rows with `status='candidate'`, queries GPT/web search to assess viability, and writes back `auto_research_status`.

### Batch query — `auto_research_status` filter rule

**The batch query MUST include ALL "not yet processed" status values**, not just `NULL`:

```python
# CORRECT — includes both null and pending
.or_("auto_research_status.is.null,auto_research_status.eq.pending,auto_research_status.eq.error")

# WRONG — misses rows where DEFAULT 'pending' was inserted by migration
.or_("auto_research_status.is.null,auto_research_status.eq.error")
```

**Why this matters:** Migration 033 set `auto_research_status DEFAULT 'pending'`. Any new `candidate` row inserted after migration 033 gets `'pending'`, not NULL. A query that only filters NULL silently skips all of them forever — no error log, just 0 rows processed.

**Rule:** When a DB column has a non-NULL DEFAULT value, always verify that all batch queries filtering for "not yet processed" include that DEFAULT value as one of the OR conditions.

**Incident (2026-05-05):** 14 candidates silently skipped for days. Detected by noticing cron ran with 0 processed rows. Fixed in commit `5d2585d`; 14 existing rows manually reset to NULL.

## After Fixing Any Error
1. Append an entry to `.github/skills/agents/engineer/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.

## Admin Correction Protection — Two-Tier Pattern

When building a UI that allows admins to correct AI-generated field values and triggers re-annotation (e.g. resetting `annotation_status` to `pending`), implement **both** tiers:

### Tier P0 — Implicit preservation (`_ai_or_existing()`)
In normal re-annotation mode (not `--all`/`--id`), existing non-null DB values are preserved. AI output only fills null fields.
```python
def _ai_or_existing(ai_val, existing_val, *, human_protected: bool = False):
    if human_protected:
        return existing_val        # Tier P1: NEVER overwrite
    if existing_val is not None:
        return existing_val        # Tier P0: keep non-null
    return ai_val                  # fill null with AI
```

### Tier P1 — Explicit persistence (`field_corrections` table)
Admin corrections are recorded in `field_corrections(event_id, field_name, original_value, corrected_value)`. The annotator loads a `human_field_map` at startup (event_id → set of protected column names). Fields in this set are NEVER overwritten by AI, even in `--all` mode.

**Schema:** `field_corrections(id, event_id, field_name, original_value, corrected_value, corrected_by, created_at)` with UNIQUE on `(event_id, field_name)`.

**Write path:** `confirm-report.ts` writes corrections to BOTH the `events` table AND `field_corrections` table in the same request.

**Few-shot context:** The annotator injects past corrections as few-shot examples into the SYSTEM_PROMPT, so GPT learns from admin feedback over time.

**⚠️ 手動 upsert 前必須驗證值來自 raw_description**：FC 的 P1 保護是「永久覆寫保護」，一旦鎖入錯誤值，後續 re-annotation 永遠無法自動修復（污染 + 鎖定 = 永久污染）。操作前必須先執行：
```sql
SELECT id, raw_title, raw_description, name_ja, name_zh FROM events WHERE id = '<eid>';
```
確認要鎖的值來自 `raw_description`（原始資料），而非來自已被 annotator 污染的 `name_ja`/`name_zh` 欄位。若需刪除錯誤 FC：
```python
sb.table('field_corrections').delete().eq('event_id', eid).eq('field_name', '<field>').execute()
```

Reference incident: 2026-05-09 — `c6d5232a` 手動修正把污染後的 `name_zh=大濛` 鎖進 FC，需手動 delete + 正確值 re-upsert 才能修復。

**Why both tiers are needed:**
- P0 alone: `--all` mode or admin overriding a non-null AI value with a different value → correction lost on next re-annotation.
- P1 alone: excessive DB reads for every field; P0 handles the common case (null-fill) cheaply.

### Price Regex Pattern for Japanese Yen
When parsing price fields, handle both `1500円` and `¥1,500` formats:
```python
PRICE_RE = re.compile(r'[¥￥]?\s*([\d,]+)\s*円?')
```

## Annotator — google_news_rss 文章補抓

> **Full translation pipeline documentation:** See `docs/TRANSLATION_PIPELINE.md` for the complete 6-layer pipeline (scraper → DeepL → GPT-4o-mini → movie title lookup → person name fix → frontend fallback chain), CI execution order, and field inventory.

`annotator.py` has special handling for `google_news_rss` events whose `start_date = NULL`:

1. **Playwright follow-redirect**: For each such event, `_fetch_gnews_article_text(url, browser)` navigates the Google News redirect URL and waits 3 s for the JS redirect to resolve. If the final URL is still on `google.com`, the redirect failed — return `None`.
2. **Article body extraction**: Tries selectors in order: `article`, `main`, `.article-body`, `.entry-content`, `.post-content`, `body`. Takes the first that returns >200 chars. Truncated to `_GNEWS_ARTICLE_MAX_CHARS = 4000` chars.
3. **Passed to GPT as `raw_desc`**: The fetched text replaces `raw_description` in the annotation call only — it is **NOT written back to the DB**. `raw_description` stays unchanged.
4. **Shared browser instance**: A single `Browser` is launched before the annotation loop and closed in `finally`. Never launch per-event — startup cost is too high.
5. **Silent fail on errors**: Timeout, paywall, bad redirect → return `None`, log `DEBUG`, continue annotation with the original (short) `raw_desc`.

```python
# Key invariant: raw_description in DB is never overwritten
if article_text:
    raw_desc = article_text   # only for this GPT call
# DB upsert uses the original raw_description unchanged
```

**When modifying this pattern:** If you remove the Playwright fetch, `google_news_rss` events will have `start_date = NULL` permanently (the scraper intentionally omits pubDate fallback). Confirm that removing it is intentional before proceeding.

## Annotator — name_ja Preservation & Sub-event Original Naming

**`name_ja` is NEVER overwritten by GPT (2026-05-02 policy change).** The annotator always preserves the scraper's original `name_ja` (= `raw_title`). GPT's `name_ja` output is only used for sub-events (which have no scraper-provided title). The `name_ja_locked` flag is now redundant for the annotator but remains in the DB/scraper for backward compatibility.

**Sub-event `name_ja` / `raw_title` preservation (2026-05-02):**
- On re-annotation, the annotator pre-fetches existing sub-events by `parent_event_id` and preserves their `name_ja` and `raw_title` if already set.
- Logic: `sub_name_ja = existing["name_ja"] or gpt_name_ja` — identical to parent preservation (`event.get("name_ja") or raw_title`).
- This prevents GPT from rewriting katakana person names to kanji on re-annotation (e.g. `チャン・ツィイー` → `章子怡`).
- First annotation's GPT output is kept as source of truth; subsequent re-annotations cannot overwrite `name_ja`.

**Sub-event `name_ja` / `description_ja` must use original Japanese text:**
- Movie titles → use the Japanese release title exactly as in the source (e.g. `赤い糸 輪廻のひみつ`)
- Person names → use the original Japanese notation (katakana/kanji as in source, e.g. `ギデンズ・コー`, `クー・チェンドン`)
- NEVER translate Chinese/Taiwanese person names into Japanese or invent katakana readings
- This is enforced by the `SUB-EVENT name_ja / description_ja` rule in `SYSTEM_PROMPT`

**General principle:** All `*_ja` fields are source-of-truth original text. Translation corrections (movie titles, person names) only apply to `*_zh` and `*_en` fields.

## Annotator — Subtitle Completeness Rule

**GPT-4o-mini habitually truncates academic subtitles.** When a `name_ja` contains a subtitle separator (`――`, `──`, `―`, `—`), GPT translates only the main title and silently drops the subtitle in `name_zh` and `name_en`.

**SYSTEM_PROMPT rule** (already added 2026-05-02): The SUBTITLE RULE section instructs GPT to always carry the complete subtitle into `name_zh` and `name_en`. Do NOT remove or weaken this rule.

**Post-annotation QA — scan for truncated subtitles after any batch re-annotation of locked events:**
```python
import re, os; from dotenv import load_dotenv; from supabase import create_client
load_dotenv('.env'); sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
SEP = re.compile(r'――|──|―|—')
r = sb.table('events').select('id,name_ja,name_zh,name_en').eq('name_ja_locked', True).eq('is_active', True).execute()
for e in r.data:
    nj = e.get('name_ja') or ''
    if SEP.search(nj):
        subtitle = SEP.split(nj, 1)[1].strip()
        print(f"CHECK {e['id'][:8]} | {nj}\n  zh: {e.get('name_zh')}\n  en: {e.get('name_en')}\n")
```
After finding truncated translations, correct them manually — re-running annotator will produce the same error unless you verify GPT respected the SUBTITLE RULE.

**Incident (2026-05-02):** 4 of 15 locked events had subtitle-truncated `name_zh`/`name_en` after initial annotation. Identified by manual scan + URL inspection. Corrected via direct DB update.

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

### `_to_trad()` — Deterministic post-processing safety net (全 `*_zh` 欄位)

Prompt-only fixes are insufficient: GPT-4o-mini ignores language rules intermittently. The `_to_trad()` helper inside `annotate_event()` applies a `str.maketrans` char map as a deterministic safety net **after** GPT returns, covering **ALL** `*_zh` fields:

- `name_zh`, `description_zh`, `business_hours_zh` — via `_to_trad(_str(annotation.get(...)))`
- `location_name_zh`, `location_address_zh` — via `_loc_zh()` which calls `_to_trad()` internally
- `organizer_zh` — via `_to_trad()` on the organizer translation output
- Sub-event `name_zh`, `description_zh` — via `_to_trad(sub.get(...))`

The char map `_SIMP_TO_TRAD` contains ~300 Simplified→Traditional character mappings (grown from ~50 initial entries), with identity mappings automatically removed. See `annotator.py` for the full table.

**⚠ Maintenance burden:** This mapping table approach is inherently incomplete — every time GPT-4o-mini uses a new SC character not in the table, it silently passes through. The table has grown from ~50 to 300+ entries and still requires periodic expansion (e.g. 2026-05-08: +9 chars, 2026-05-11: +3 chars). **Long-term solution:** evaluate OpenCC or a complete Unicode SC→TC library for robust coverage. Until then, continue manual maintenance.

**When to expand the map:** If a post-annotation scan finds a new Simplified character in any `*_zh` field, add it to `_SIMP_TO_TRAD` in `annotator.py` **and** `SIMP_RE` / `SC_ONLY` in `auto_qa.py` simultaneously, then DB-patch all existing rows:
```python
import os, re; from dotenv import load_dotenv; from supabase import create_client
load_dotenv('.env'); sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
MAP = str.maketrans({"新字":"舊字", ...})  # add new chars to full map
ZH_FIELDS = ['name_zh','description_zh','location_name_zh','location_address_zh','business_hours_zh']
res = sb.table('events').select('id,' + ','.join(ZH_FIELDS)).execute()
for ev in res.data:
    updates = {f: (ev[f] or '').translate(MAP) for f in ZH_FIELDS if (ev.get(f) or '') != (ev.get(f) or '').translate(MAP)}
    if updates: sb.table('events').update(updates).eq('id', ev['id']).execute()
```

**Scan pattern** — run after every annotator change or char map expansion:
```python
import re, os; from dotenv import load_dotenv; from supabase import create_client
load_dotenv('.env'); sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
SIMP = re.compile(r'[东来这发会说时问门关对长进现与实变内还单层达诺厅络设联馆园'
                   r'个记构传经验弥与对让认为总视历强调节约运动办报导环义务战组织'
                   r'国际临产业属创据体点击继续阅读开艺术观众场举声画获奖选赛参团电'
                   r'热爱岛独虑忆仅尝试谈请龙丰华灵纪录极标准规细带广庆响惊显难类'
                   r'宝贵丽尽挡将断湾览间气坛静满简洁优连释迹态仪壮汇灯蕴韵须恳'
                   r'统种学数编价乡网绍预称评议论结处应欢]')
ZH = ['name_zh','description_zh','location_name_zh','location_address_zh','business_hours_zh']
res = sb.table('events').select('id,is_active,' + ','.join(ZH)).execute()
bad = [(e['id'][:8], e['is_active'], f, e[f]) for e in res.data
       for f in ZH if SIMP.search(e.get(f) or '')]
print(f'Simplified in *_zh fields: {len(bad)}')
[print(f'  {i} active={a} [{f}] {v!r}') for i,a,f,v in bad]
```

**Fields covered:** ALL `*_zh` fields — main-event and sub-event. `_to_trad()` is applied to `name_zh`, `description_zh`, `business_hours_zh` directly; `_loc_zh()` (which calls `_to_trad()`) is applied to `location_name_zh` and `location_address_zh`.

### `_lock_fields_via_corrections()` — SC→TC Chokepoint Guard

**`_lock_fields_via_corrections()` 對 field name 以 `_zh` 結尾的值，寫入 FC 前自動呼叫 `_to_trad()`。**

This is the chokepoint guard (Layer 2) of the SC→TC three-layer defence. Any value that enters `field_corrections` becomes permanently locked — if SC characters slip through, they are immune to all automated fixes (annotator re-annotation is blocked by P1 protection).

**Guard 實作位置**：`annotator.py` `_lock_fields_via_corrections()` 函式內，在 `json.dumps(fvalue)` 前加 `fvalue = _to_trad(str(fvalue)) if fname.endswith("_zh") else fvalue`。

**適用場景（所有寫入 FC 的路徑）**：
- `_lock_fields_via_corrections()` 被 annotator 主迴圈呼叫
- backfill 腳本（如 `_oneoff_backfill_organizer_i18n.py`）呼叫
- `enrich_movie_titles()` / `enrich_person_names()` 呼叫
- 手動 DB patch 後透過此函式鎖定

**反模式：** 直接 upsert `field_corrections` 表而不經 `_lock_fields_via_corrections()` → 繞過 SC→TC guard。所有 FC 寫入**必須**經此函式。

Reference incident: 2026-05-11 commit `f7790a2` — 39 筆 `organizer_zh` SC 被 kanji copy 永久鎖入 FC。

### SC→TC Detection/Fix Consistency Rule

`auto_qa.py` 的偵測範圍與修復範圍必須完全一致：

| 系統 | 字元集來源 | 掃描欄位 |
|------|-----------|---------|
| `_detect_simplified_chinese()` | `SC_ONLY` | 6 個 `_zh` 欄位 |
| `fix_simplified()` | `_SIMP_TO_TRAD_RAW` | 6 個 `_zh` 欄位（2026-05-11 起） |

**一致性規則：**
1. `SC_ONLY ⊆ _SIMP_TO_TRAD_RAW.keys()` — 偵測到的字元必須都有對應映射可修復
2. `SC_ONLY` 不可含 SC/TC 共用字元（如 征/蹈/零/蒙）— 這些在 TC 中有合法用法
3. `fix_simplified()` 的欄位清單必須與 `_detect_simplified_chinese()` 完全相同

**驗證字元是否為假陽性**：CC-CEDICT 或 kanji.jitenon.jp 查詢，確認 TC 字形與 SC 字形**不同**才可加入 `SC_ONLY`。

Reference incident: 2026-05-11 commit `aa24400` — 征/蹈/零/蒙 假陽性 + 见/从/库 缺映射 → 無限 dismiss 循環。

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

### Non-locale route exclusion rule
Any route that should NOT be locale-prefixed **must be excluded in the `proxy.ts` matcher regex**. Without exclusion, the intl middleware 307-redirects all requests to `/zh/<path>`, returning 404. This applies to:
- **Static files** in `web/public/` (e.g. `llms.txt`, custom JSON)
- **Non-locale routes** such as short redirect routes (`/r/*`), API routes, webhook endpoints
- Any new route pattern not under `/{locale}/`

Matcher pattern (append new exclusions here):
```ts
export const config = {
  matcher: ["/((?!_next|api|r/|.*\\.(?:ico|png|jpg|svg|webp|txt|xml|json)).*)"],
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

### localhost Lighthouse canonical rule
When validating locale pages on `http://localhost` or `http://127.0.0.1`, do not blindly reuse the deployed `alternates.languages` block in page metadata. Lighthouse can false-fail `canonical` with `Points to another hreflang location` even when the canonical URL equals the current localhost page.

Use a localhost-only branch in `generateMetadata()`:
```ts
if (isLocalRequest) {
  return {
    alternates: {
      canonical: `${base}/${locale}`,
    },
  };
}

return {
  alternates: {
    canonical: `${base}/${locale}`,
    languages: {
      zh: `${base}/zh`,
      en: `${base}/en`,
      ja: `${base}/ja`,
      "x-default": `${base}/zh`,
    },
  },
};
```

Keep deployed hosts unchanged: full hreflang output including `x-default` must still ship in production.

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

## Agent Frontmatter Rules

- **Handoff target agents 禁止設 `user-invocable: false`**：此旗標讓 VS Code 把 agent 從可解析清單移除，所有指向它的 `handoffs:` 按鈕靜默失效。
- 判斷原則：**任何在其他 agent `handoffs:` 裡被引用的 agent，一律不得設 `user-invocable: false`**。
- `user-invocable: false` 僅適用於純 subagent（只被 parent agent 透過 `agents:` list 呼叫、不出現在 Agent Picker、無人 handoff 到它）。
- Incident：`update-history-agent.agent.md` 與 `validate-merge-deploy.agent.md` 誤設此旗標，Engineer/Designer/Scraper Expert 的 handoff 按鈕全部消失（commit `6188653` 修正）。

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
- **YAML parser quirk — `if:` multi-line blocks**: Multi-line `if:` conditions using `>-` or `|` block scalars sometimes fail with `All mapping items must start at the same column` or similar. Always prefer **single-line double-quoted strings** for `if:` expressions. If multi-line is unavoidable, test with `act` or push a draft branch before merging.
- **YAML parser quirk — `[{...}]` inline jq filters in `run:` blocks**: GitHub's YAML parser incorrectly flags `[{type:"text",...}]` inside `run: |` block scalars as `Nested mappings not allowed in compact mappings`. Fix: assign the jq filter to a shell variable:
  ```yaml
  run: |
    JQ_FILTER='[{type:"text",text:"..."}]'
    curl ... --data "$(jq -n --arg t "$MSG" "$JQ_FILTER")"
  ```
  Reference: commits `c38ddd5`, `b9a462c`.

### Scraper/Merger pipeline step order

The daily CI pipeline **must** run steps in this order:

```
main.py → merger.py → annotator.py → annotator.py --fix-reviewed
```

- `merger.py` must come **after** `main.py` so new scraped events are present for deduplication.
- `annotator.py` must come **after** `merger.py` so merged events are re-annotated immediately (not left `pending` until the next cycle).
- `merger.yml` runs separately (3× daily cron: 01:00 / 09:00 / 16:00 UTC) with the same annotator follow-up steps, ensuring cross-source duplicates are cleaned between full scraper runs.

### merger.py `_normalize()` — Rules for safe similarity matching

`_normalize()` preprocesses both names before `SequenceMatcher`. Current transformations (order matters):

1. **Trademark normalization**: `®`/`Ⓡ` → `(r)`, `™` stays lowercased
2. **iwafu subtitle stripping**: `[－—\-]…[－—\-]` at end of string removed
3. **Year suffix stripping**: `re.sub(r"20\d{2}[春夏秋冬]?\s*$", "", name)` — strips year-only and year+season suffixes so recurring annual events match across years
4. **Whitespace collapse**: all Unicode whitespace removed, lowercase

**When adding a new normalization rule:**
- Run similarity spot-checks for: (a) intended matches (must hit ≥ 0.85), (b) known non-duplicates (must stay < 0.85)
- Classic pitfall: two different annual events with similar short names. Example: `"台湾フェスティバル™TOKYO"` vs `"台湾文化祭"` → 0.200 after year strip (safe). Confirm before committing.

**Incident (2026-05-05):** `台湾文化祭2026` (iwafu) vs `台湾文化祭` (taiwanbunkasai) scored 0.714 before year-strip fix, causing manual merge to be required every year.

### merger.py Pass 2 location matching rules

- `_location_overlap()` accepts: (a) **substring containment** for strings ≥ 4 chars, OR (b) **shared token ≥ 2 chars** after split on `[\s\u3000、,（()）・]`.
- Both branches needed because location strings vary widely:
  - `イオン太田` ⊂ `イオンモール太田` — substring branch
  - `東京都新宿区` shares `新宿区` token with `新宿K's cinema 新宿区` — token branch
- DO NOT lower min-length below 4 — `東京` ⊂ `東京都` would create false matches.

### `_NEWS_SOURCES` membership criteria

A source belongs to `_NEWS_SOURCES` if **any** of:
- titles do NOT match the official event name verbatim (news rewrites, RSS summaries)
- `start_date` may be article-publish date instead of event date
- location may be city-only / prefecture-only instead of venue

These will always be Pass 2 secondaries (never primary). Current members: `google_news_rss`, `prtimes`, `nhk_rss`, `walkerplus`. When adding a new member, also confirm its `SOURCE_PRIORITY` value is higher (lower priority) than every official organizer source.

### Event deactivation audit fields (migration 044)

Every code path that sets `events.is_active = false` MUST also write three audit columns:
- `deactivated_at` — ISO timestamp (`new Date().toISOString()` or Python `datetime.now(timezone.utc).isoformat()`)
- `deactivated_reason` — short human-readable string
- `deactivated_by_pass` — one of: `merger_pass_0` (gnews dedup), `merger_pass_1` (name similarity), `merger_pass_2` (news date+location), `merger_pass_3` (orphan reattach), `merger_pass_4` (grandchild flatten), `orphan_cleanup` (orphan with no parent), `admin_manual` (UI deactivate)

When **re-activating** (setting `is_active = true`), null out all three fields so stale audit data does not persist.

Inventory of setters that must comply (audit when modifying any of them):
- `scraper/merger.py` — use the `_deactivate_payload(reason, pass_id)` helper
- `web/components/IsActiveToggle.tsx`
- `web/components/AdminEventTable.tsx` (`handleToggleActive` + `handleBulkToggleActive`)
- `web/app/actions/confirm-report.ts` (three branches: wrongCategory unresolved, wrongDetails needsReannotation, isIrrelevant)

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

## enrich_addresses.py — 地址補齊工具

`scraper/enrich_addresses.py` 使用 OpenAI gpt-4o-mini 查詢有場館名但缺地址的活動，並寫回 DB。

### 使用方式
```bash
# dry-run（只預覽，不寫入 DB）
python enrich_addresses.py --dry-run

# 只處理特定 source
python enrich_addresses.py --source ssff --dry-run
python enrich_addresses.py --source ssff

# 處理所有符合條件的事件
python enrich_addresses.py
```

### 跳過邏輯（以下情況不查詢）
- `source_name = 'gguide_tv'`（TV 頻道，無實體地址）
- `location_name` 包含 `オンライン` 或 `電視頻道`（線上活動）
- `location_address` 已有值（不覆蓋）

### 寫入欄位
| 欄位 | 說明 |
|------|------|
| `location_address` | 日文地址（主欄位） |
| `location_address_zh` | 中文地址 |
| `location_address_en` | 英文地址 |

**信心度過濾：** LLM 回傳 `confidence` 欄位；只有 `confidence=high` 才寫入，`low`/`medium` 直接跳過。避免寫入 LLM 猜測的錯誤地址。

### 可複用模式
任何「有 venue name 但缺地址」的來源都適用。執行前先用以下 SQL 確認目標範圍：
```sql
SELECT source_name, COUNT(*) AS cnt
FROM events
WHERE location_name IS NOT NULL
  AND location_address IS NULL
  AND source_name NOT IN ('gguide_tv')
  AND location_name NOT LIKE '%オンライン%'
  AND location_name != '電視頻道'
GROUP BY source_name
ORDER BY cnt DESC;
```

## Quality Page — 缺欄位誤報排除模式

當 Quality page 顯示「缺 X 欄位」的筆數異常高時，**先分組統計，再決定 filter 邏輯**。

### 診斷步驟
```sql
-- 確認哪些 source 貢獻了「缺地址」的事件
SELECT source_name, COUNT(*) AS cnt
FROM events
WHERE location_name IS NOT NULL
  AND location_address IS NULL
  AND is_online IS NOT TRUE
GROUP BY source_name
ORDER BY cnt DESC;
```

若某個 source（如 `gguide_tv`）的事件天然沒有實體地址，應在 **前端 filter 排除**，而不是標記為「待修」。

### Quality page filter 排除模式（TypeScript）
```ts
// ❌ 錯誤：把 TV 頻道事件也算進缺地址
const missingAddr = events.filter(e =>
  e.location_name && !e.location_address && !e.is_online
);

// ✅ 正確：DB 層排除天然無實體地址的來源 + client 層排除短地名
// DB query:
//   .not("location_name", "is", null)
//   .is("location_address", null)
//   .neq("source_name", "gguide_tv")
//   .not("location_name", "like", "%〒%")
//   .not("location_name", "ilike", "%オンライン%")
// Client filter:
const missingAddr = (dbResults).filter(e => {
  const loc = e.location_name ?? "";
  if (loc.length <= 6 && !loc.includes(" ") && !loc.includes("　")) return false;
  return true;
});
```

### 原則
- **TV 頻道 / 廣播節目**：`source_name = 'gguide_tv'`，`location_name` 存頻道名稱 → DB `.neq()` 排除。
- **線上活動**：`location_name` 含 `オンライン` → DB `.not()` 排除。
- **地址嵌入名稱**：`location_name` 含 `〒`（郵便番号）→ DB `.not()` 排除。
- **短地名（≤6 字元）**：如「東京」「香港」「文京区」→ client filter 排除（無更精確地址可填）。
- 新增 quality check 時，先確認「哪些情況下欄位為空是合理的」，再寫 filter。

**Incident:** 2026-05-01 — `missingAddr` 顯示 29 筆，實際 18 筆是 gguide_tv 誤報。2026-05-02 — 加入 〒/オンライン/短地名排除後進一步降低（commits `229810f`、`f5931e0`）。

## Location Filter Three-File Sync Rule

The location filter is implemented in **three separate files** that must always stay in sync:

| File | What to update |
|------|---------------|
| `web/components/FilterBar.tsx` | `options` array (labels + values) + i18n keys |
| `web/app/[locale]/page.tsx` | Server-side OR query (`location_address ilike` per region marker) |
| `web/components/AdminEventTable.tsx` | `filterLocation` state type (union literal) + marker arrays + `getFiltered` predicate + `sourceCountMap` |

**Region marker logic (current 6-option layout):**

| Value | Detection |
|-------|-----------|
| `"tokyo"` | `location_address` contains Tokyo ward/city markers, or is null (default) |
| `"kanto"` | ilike markers: 神奈川, 埼玉, 千葉, 茨城, 栃木, 群馬, 山梨, 東北各縣, 北海道 |
| `"chubu"` | ilike markers: 愛知, 静岡, 岐阜, 長野, 新潟, 富山, 石川, 福井, 大阪, 京都, 兵庫, 奈良, 滋賀, 和歌山, 三重 |
| `"chugoku"` | ilike markers: 広島, 岡山, 鳥取, 島根, 山口, 九州各縣, 四國各縣, 沖縄 |
| `"online"` | `location_name` contains `オンライン` |
| `"tv"` | `location_name` contains `電視頻道` |

**Rules:**
1. **State type must match options exactly.** The `filterLocation` state is a TypeScript string literal union. If a new option value is added but the union type is not updated, TypeScript will NOT report an error — instead, the unknown value silently falls through all predicates and shows zero results.
2. **Use `ilike` marker lists, not NOT logic.** Defining regions by exclusion (e.g. "not Tokyo, not online") misses events with null addresses or partial matches. Always use explicit positive marker lists per region.
3. **All three files in one commit.** Partial sync (e.g. only updating FilterBar) causes the server query to return wrong data or the admin filter to show stale counts.

**Incident:** 2026-05-01 — rewrote from `tokyo / other_japan / taiwan / online / tv` to `tokyo / kanto / chubu / chugoku / online / tv`. All three files updated in commit `b8dfe2b`.

## Works Entity Conventions

(Migration `048_works_entity.sql` — 2026-05-05)

`works` 是電影／舞台劇／巡演的「作品層級」上層實體；`events.work_id` 為 nullable FK 指向 `works.id`，`ON DELETE SET NULL`。

**`work_type` 有效值（migration 048 + 051 check constraint）：**
`film` | `stage` | `exhibition` | `concert_tour` | `tv_drama` | `tv_variety` | `other`
> `conference` **不在**允許清單！學術研討會建 work 用 `other`。PostgreSQL check constraint 執行時才報錯，無 schema 預覽——建立前先查現有值：`sb.table("works").select("work_type").execute()`。

**規則：**

1. **僅 admin 維護**：`works` 表不由 annotator 寫入；只有 `web/app/actions/works.ts` 的 admin server actions 可建立／更新／刪除。RLS：anon SELECT，admin ALL via `user_roles`。
2. **與 `parent_event_id` 並存**：兩者職責正交。`work_id` 跨 events 串作品；`parent_event_id` 在單一活動內串 master/sub-event。同一筆 event 可同時設定兩者（影展中的某場放映 → `work_id` 指向被放映的電影、`parent_event_id` 指向影展整體）。
3. **詳情頁 cross-link 必須用 service role**：anon-key client 對 `is_active=false` 的 sibling event 會 silently 過濾為 null（RLS 規則）。查同 `work_id` 的其他場次必須用 `SUPABASE_SERVICE_ROLE_KEY` 建立 client，且 `select` 限定最少欄位（`id,name_*,start_date,location_name,...`），絕不 `select("*")`。
4. **`work_id` 變更不更新 `events.updated_at`**：assign/unassign 只是 metadata link，不應觸發任何 ISR revalidate 或 re-annotation。`assignWorkToEvent` action 直接 `update({work_id: ...})`，不附帶其他欄位。
5. **Migration 應用後**：跑一次 `scraper/_oneoff_backfill_works.py` 補上既有觸發 case（月老、大濛），再刪除腳本。
6. **`original_title` UNIQUE**：migration 048 在 `original_title` 上建立 unique index，backfill 才能用 `on_conflict='original_title'` 或「先 select 再 update」。新增腳本若需 idempotent upsert，先用 `.eq('original_title', ...).limit(1)` 檢查，避免依賴 PostgREST `on_conflict` 對複合條件的 brittle 行為。
7. **merger Pass 1 整合**：同 `work_id` 跨 venue 的 movie/performing_arts pair 不再合併（會破壞「同作品多場次」呈現）。`merger.py` 已在 Pass 1 加入兩個跳過條件：(a) 雙方 `work_id` 非空且不同 → skip；(b) category 含 movie/performing_arts 且 `_location_overlap()=False` → skip。輸出 `[Pass 1 SKIP]` log。
8. **`original_title`（中文片名）必須先用 `lookup_movie_titles(title_ja)` 查 eiga.com**：`scraper/movie_title_lookup.py` 已有完整 pipeline 從 eiga.com 的 `原題または英題` 欄位取得正確中文片名。函式回傳 **3-tuple** `(name_zh, name_en, official_url)`（commit `a4ecdba`，2026-05-12 起）。批次建立 works 時，必須先對每筆 `title_ja` 呼叫此函式；僅對回傳 `(None, None, None)` 的才需用維基百科、台灣電影網或 IMDb 人工交叉驗證。解包時必須用 3-tuple：`name_zh, name_en, official_url = lookup_movie_titles(title_ja)`，不可沿用舊 2-tuple 解包（`name_zh, name_en = ...`）——會觸發 `ValueError: too many values to unpack`。禁止用 GPT 直譯生成 `original_title`——日文片名與中文原始片名的關係不可預測（如 `超低予算ムービー大作戦` 的原題是 `導演你有病`，不是 `超低預算電影大作戰`）。
9. **batch 腳本必須呼叫 `post_batch_enrich(event_ids)`**：所有 `_oneoff_*.py` 在寫入 DB 後，必須 `from annotator import post_batch_enrich` 並呼叫。此函式自動執行 eiga.com 片名 lookup + `field_corrections` 鎖定。人名修正需額外執行 `python annotator.py --enrich-person-names`。禁止在 batch 腳本中用 GPT 直譯生成 `name_zh`/`name_en`。

**Reference**: 月老 (`f970e4e3` shin_bungeiza ↔ `4a8772ec` cinemart_shinjuku) 與 大濛 (`dec5031b` cinemart_shinjuku ↔ `d201c261` taioan_dokyokai) — migration 048 + Phase 7 cohort.
