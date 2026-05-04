---
name: architect
description: Planning principles, model selection, and scope rules for the Architect agent
applyTo: .github/agents/architect.agent.md
---

# Architect Skills

Read this at the start of every session before producing any plan.

## Planning
- Always check whether a new feature requires a DB schema change. If yes, mark Step 1 as a manual migration with verification SQL.
- Identify all code paths affected by a data model change — not just the obvious one (a new column needs both the table AND every writer that populates it).
- Never ship a plan with an untested API or signature change. Include an explicit smoke-test step.
- Confirm that all pending migrations are applied before designing features that build on them.

## Auto-Generate Promotion Checklist

When a plan includes promoting an auto-generated scraper (`auto_scraper_status=success`) to `status=implemented`, the plan must explicitly include **all 5 steps**:

1. PR merged — `scraper/sources/<name>.py` exists and is registered in `scraper/main.py`.
2. `research_sources` row: `status = 'implemented'`.
3. **`scraper_source_name = '<scraper key>'`** — MUST be filled or `/admin/sources` shows 0 events and cannot trigger Run Scraper (backend JOINs `scraper_runs` by this key). **auto_generate does NOT fill this automatically.**
4. Smoke-test: `python main.py --dry-run --source <key>` confirms events are found.
5. For annual-subdomain sites (e.g. `YYYY.tiff-jp.net`): replace hardcoded year with dynamic year resolution (follow redirect from root domain → fallback `datetime.now().year`).

Missing step 3 has no compile-time or runtime error — it silently appears as a 0-count row in the admin UI.

## Database Safety Rules

- **NEVER batch-set `is_active = False` based on `end_date < today`**. Past events must remain `is_active = True` so users can view event history. Visibility for ended events is controlled by the frontend `FilterBar` ("顯示已結束活動" toggle), not by `is_active`.
- **`is_active` has exactly two legitimate write sources**:
  1. Admin manually disables a specific event via the admin page.
  2. `merger.py` deactivates a duplicate secondary event during merge.
- Any bulk UPDATE touching `is_active` must be verified against these two sources before execution. If it does not match either, abort.

## Annotator Backfill QA Rule

任何計畫包含 `annotator.py --backfill-*` 步驟時，**必須**在步驟清單中明確列出「backfill 後多語言欄位 QA 驗證」子步驟：

- `selection_reason["ja"]`：必須含假名（平假名或片假名）；無假名表示語言污染
- 驗證 SQL：
  ```sql
  SELECT id, source_name, (selection_reason->>'ja') as ja_text
  FROM events
  WHERE selection_reason->>'ja' IS NOT NULL
    AND selection_reason->>'ja' !~ '[ぁ-んァ-ン]'
  LIMIT 20;
  ```
- 發現污染 → 執行翻譯修正腳本（從 zh 欄 GPT 翻譯覆寫）

**Incident**: 2026-05-04 `--backfill-tier1` 導致 49 筆 `selection_reason["ja"]` 為中文，需人工腳本修正。

## Scope

- State explicitly what is NOT in scope. Ambiguous scope = scope creep = breaking changes.
- List every affected file path explicitly — vague descriptions ("the scraper files") are not acceptable.

## Docs Update Rule

`/docs` 是**結構性文件**，只在架構改動時需要更新。以下情況屬於架構性改動，計畫中必須明確包含「更新 docs/ARCHITECTURE.md 或 docs/SCRAPER_PIPELINE.md」步驟：

| 改動類型 | 需更新 |
|---------|-------|
| 新增或移除整個 CI workflow | ARCHITECTURE.md |
| 新增或移除 pipeline layer（auto_scraper、researcher 等） | SCRAPER_PIPELINE.md |
| 新增或移除 Supabase 整合點（LINE bot、新 webhook） | ARCHITECTURE.md |
| 新增 `web/app/api/` 下的 API endpoint | ARCHITECTURE.md |

**不**屬於架構性改動（無需更新 docs）：bug fix、單一 scraper 新增、i18n 修改、CSS 調整、新增個別 Supabase migration。

`/docs` 記錄的是「系統怎麼運作」，不是「系統現在的狀態」。不要在文件中寫入會每天變動的數字（scraper 數量、事件總數、migration 編號）。

## Server Component + Realtime 分離模式 Guard

在任何包含「Server Component 中有 badge 或動態計數器」的 feature plan 中，**必須**明確標示：

> **⚠️ 此 badge / 計數器需要即時性嗎？若是，plan 必須包含「拆出 Client Component + Supabase Realtime 訂閱」步驟。**

**分離模式：**
```
ParentComponent (Server Component)
  └─ 查詢初始 count（SSR，一次性）
  └─ <DynamicBadge initialCount={n} />（Client Component）
       └─ Supabase Realtime 訂閱 INSERT + UPDATE 保持即時更新
```

**強制規則：**
- Server Component 的資料在 SSR 時固定，頁面渲染後不再更新。任何需要即時性的計數器 / badge，**不得**留在 Server Component 中。
- Client Component 接收 `initialCount` prop 作為 SSR 初始值，啟動後改由 Realtime 維護。
- 計畫中必須明確列出：哪個元件需要拆分、Realtime 訂閱哪個 table 的哪些事件（INSERT / UPDATE）。

**無操作 Quality Section 應直接移除：**
Quality check section 如果沒有對應的可執行 action（fix button / batch action），且數值永遠不清空（例如 archive cron 一天只跑一次的 expired-but-active），**計畫不應包含此 section**，已存在的應移除。只有數值能被操作清零的 check section 才值得顯示。

Reference incident: `AdminTabNav` badge（2026-05-02）—（commit `4a71258`）; expired-but-active section（commit `cd4cc29`）.

## Quality Check Design Rules

在任何包含「新增或修改 `/admin/quality` check 條件」的 feature plan 中，**必須**確認以下三點：

### 規則一：判斷欄位 = 詳情頁顯示欄位

> Quality check 用哪個欄位 IS NULL 做判斷，該欄位必須是詳情頁實際 render 的欄位。

- 設計 check 前先查前端程式碼（`app/[locale]/events/[id]/page.tsx`），確認「哪個欄位 null 才真正影響使用者體驗」。
- 錯誤範例：用 `location_address IS NULL` 做缺地點 check，但詳情頁顯示 `location_name`（commit `b82849d` → `80920ce`）。

### 規則二：排除「天生無法填寫」的事件類型

設計每個 quality check 時，同步列出「哪些事件類型天生不需要此欄位」，並在 DB query 層排除：

| Check 類型 | 已知排除 | 排除原因 |
|-----------|---------|---------|
| 缺地點（`location_name IS NULL`）| `source_name = 'gguide_tv'` | 電視節目 |
| 缺地點（`location_name IS NULL`）| `category` 含 `competition` | 競賽/補助，全國性活動 |

若未排除 → flag 永遠無法清零 → 無意義的噪音。

**排除語法（Supabase RPC）：**
```ts
.not('source_name', 'eq', 'gguide_tv')
.not('category', 'cs', '{"competition"}')
```

### 規則三：DB 層過濾優先於 client-side 過濾

所有 quality check 的排除條件**必須**推到 DB query（`.not()`），禁止在 JS 側 `.filter()` 排除。原因：DB 層過濾減少傳輸量，且排除邏輯集中在 query 中易於審查與維護。

Reference incident: 2026-05-02 quality page — `gguide_tv` 排除原為 JS client-side filter，後移至 DB query（commit `80920ce`）；`competition` 排除直接寫在 DB query（commit `4ca383a`）.

### 規則四：Client-Side Filter Prerequisites

撰寫任何依賴 DB 欄位的 client-side filter 前，必須確認以下三步驟：

1. **欄位出現在 `.select("...")` 字串中**：否則欄位值為 `undefined`，filter 條件永遠不成立，靜默通過所有資料（不報錯）。
2. **TypeScript interface 包含該欄位及正確型別**（如 `location_prefectures?: string[] | null`）。
3. 確認以上兩點後才撰寫 filter 邏輯。

**反例**（commit `bf22756` 之前）：
```ts
// ❌ location_prefectures 不在 select 字串 → 欄位 = undefined → 過濾靜默無效
if ((e.location_prefectures?.length ?? 0) > 1) return false;
```

**正確做法**：
```ts
// Step 1: 確認 select 含欄位
.select("id, location_name, location_prefectures, ...")
// Step 2: interface 宣告型別
interface QualityRow { location_prefectures?: string[] | null; ... }
// Step 3: 才寫 filter 邏輯
if ((e.location_prefectures?.length ?? 0) > 1) return false;
```

Reference incident: 2026-05-02 — `location_prefectures` 未加入 select，多城市活動過濾靜默失效。

## auto_qa False Positive Guard

在審核任何 auto_qa 偵測器的改動或新增 `auto_qa_*` 類型前，**必須**確認：

1. **城市名誤報**：`location_name` 為純城市名（東京、大阪、岡山 等）時，新聞彙整類 source（`google_news_rss`、`koryu` 等）本就無法提供具體場地。`auto_qa_missing_address` 不應 flag 此類事件。維護 `VAGUE_CITY_NAMES` frozenset。
2. **海外場地誤報**：非日本場地（スイス、フランス 等）不在日本地址查核範圍內。維護 `OVERSEAS_KEYWORDS` tuple。
3. **正常 flag 保留**：有具體場地名（大學、美術館、○○ホール 等）但 `location_address = NULL` 的事件，仍應 flag。
4. **偵測精準度原則**：寧可少報，不可誤報——誤報會使管理員對回報系統失去信任。

Reference incident: 2026-05-04 — 13 筆 auto_qa_missing_address pending，其中 5 筆為城市名/海外場地誤報（commit `15c5b4b`）。

## RLS Cross-Status Query Guard

在任何涉及「SSR 頁面查詢關聯資料（父事件、鏈結實體）」的 feature plan 中，**必須**確認以下三點：

### 規則一：anon key 不讀非 active 資料

RLS `"Public read events"` policy 限制 anon key 只讀 `is_active = true` 的事件。若查詢目標（如父事件）被下架（`is_active = false`），anon key 查詢**靜默回傳 null**，不拋 error，難以察覺。

### 規則二：跨 active 狀態查詢必須用 service role key

若查詢的關聯資料可能處於 `is_active = false` 狀態（例如：父事件下架、存檔紀錄），**必須在 Server Component / route handler 中用 service role key**：

```ts
// Server Component only — 不可傳到 client-side
const adminClient = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
)
const { data } = await adminClient
  .from("events")
  .select("id, name_ja, name_zh, name_en")  // 只查需要的欄位
  .eq("id", parentId)
  .single()
```

**強制限制**：service role key **絕對不得**暴露到 client-side。只在 Server Components 或 API route handlers 使用。

### 規則三：最小欄位原則

用 service role key 查詢關聯資料時，**只 select 當前頁面真正需要的欄位**（如 `id, name_ja, name_zh, name_en`），不得用 `select("*")` 避免洩漏敏感欄位。

Reference incident: 2026-05-02 — 父事件（台東祭）被設為 `is_active = false` 後，子事件詳情頁父事件連結消失；改用 service role key 後恢復（commit `f5931e0`）。

## Admin UI Dashboard Necessity Check

Before planning any new admin page or dashboard column whose primary output is a count / status / health number, ask:

1. **「這頁面真的會被點開嗎？」** — Admin UI requires manual navigation. If the signal isn't urgent enough to justify proactively visiting `/admin/...`, it will be ignored.
2. **「沒有 action 按鈕的純計數值得做嗎？」** — A dashboard column without a one-click fix / batch action / drill-down is visual decoration. If the user will read it and do nothing, the value is near zero.
3. **Is a passive push channel cheaper?** — LINE message, weekly email, or auto-filed GitHub issue cost less than a new page and have higher retention (signal arrives without being requested).

**Default preference order for monitoring features:**
1. Passive push (LINE / email / issue) → preferred for periodic health, budget, quality summaries.
2. Existing page extension with **actionable** column (e.g. add a row to AdminEventTable that has a fix button) → acceptable when tightly coupled to existing workflow.
3. New `/admin/<topic>` page → only when the user explicitly asks for an interactive审查 surface (multi-row triage, manual selection, bulk action).

If a plan introduces a new admin page or count column with no associated action, document the rationale explicitly in the plan; otherwise propose the passive push variant first.

Reference incident: 2026-05-01 Tier 1 monitoring — `/admin/quality` page and `/admin/stats` SLA columns were planned, implemented, then撤銷 same week; only the LINE budget push (`weekly_report.py`) survived.

## Annotator Scraper-Priority Guard

Before approving any change to `annotator.py` annotation field priority, verify:

1. **Scraper values always take precedence** over GPT inference for factual fields:
   - `start_date` / `end_date`
   - `location_name` / `location_address`
   - `business_hours`
   - `is_paid`
2. **GPT only fills in** when the scraper left the field empty (`None`/`null`).
3. **Translation fields are always GPT-generated** — `name_zh`, `name_en`, `description_*`, `location_name_zh/en`, `business_hours_zh/en`.
4. **`name_ja` special case**: when `name_ja_locked=true`, the scraper's value is preserved verbatim. The source title may be in Japanese, Chinese, or English — `name_ja` is a field identifier, not a language constraint.
5. **`location_url`** — conditional write: GPT may extract it from `raw_description` text (schema prompt must say "extract from text only, no hallucination"). Write only when non-null (`_loc_url = event.get("location_url") or _str(annotation.get("location_url"))`); never write `null` back to DB — `null` would overwrite admin-entered values. This is a field shared between scraper/GPT extraction and admin manual entry. (commit `fb568c4`, 2026-05-02)
6. The safe way to fix a GPT-overwritten date: prepend `開催日時: YYYY年MM月DD日` header to `raw_description`, then set `annotation_status='pending'` to trigger re-annotation.

## Hallucination Scan Safety Guard

Before acting on any hallucination scan result (address/location not found in raw_description), verify:

1. **Scan result = suspicion only**: An address absent from raw_description does NOT confirm hallucination. GPT correctly recalls well-known venues from training data.
2. **Always verify with Google Maps before editing**: Search the venue name directly — takes 30 seconds. Do NOT infer address from venue name, neighborhood, or landmark associations.
3. **Venue name ≠ postal address**: `MoN Takanawa` (inside Takanawa Gateway City) has postal address 港区三田 — not 高輪. Station names, building brands, and postal addresses can differ.
4. **Incident**: 2026-05-02 — architect changed correct GPT address `港区三田3-16-1` to wrong `港区高輪4-10-30` based on venue name reasoning. Reverted after user confirmation.

## After Identifying a Planning Mistake
1. Append an entry to `.github/skills/agents/architect/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.

## Stop-Point Contract (Architect 直接編輯時)

Architect 預設為 read-only（規劃 + 報告）。但在以下情況會直接編輯檔案：revert 操作、緊急修正、小幅文檔更新。**直接編輯後必須走完以下其一**，禁止留半成品：

1. **完整鏈路**：編輯 → 自呼叫 V-M-D（commit + push + Vercel 驗證）→ 報告結果。
2. **明示交還**：編輯 → 在最終回應**第一行**標注「⚠️ 工作樹有未提交修改，需手動處理」並列出檔案，**禁止只報「已完成」**。

絕不允許：編輯完直接呈現 commit hash 或「完成」字樣而沒明確指出 push 狀態。

## Status Reporting Vocabulary

呈現 git 狀態時，**必須**用以下三種標籤之一，禁止只給 hash：

- ✅ **已推送**：`<hash> → origin/main`（已驗證 Vercel 部署或 push 成功 exit code 0）
- ⏳ **本地 only**：`<hash> (local, not pushed)`
- 📝 **未 commit**：`N files modified (working tree)` 並列檔名

裸 hash（如「commit cf1e0a9」）會讓用戶誤以為已推送，這是 anti-pattern。

## Atomic Revert Rule

刪除 i18n key、type union member、或任何被多處引用的 symbol 時，**同一 commit 必須同時刪所有 caller**：

1. 編輯前先 `grep_search` 找出所有引用點。
2. 改動順序：先刪 caller，再刪 definition（反之會留下編譯壞掉的中間狀態）。
3. 完成後跑 `cd web && npx tsc --noEmit` 確認 0 error 才 commit。

反例：2026-05-01 撤銷 Tier 1 時刪掉 `statsSlaHeader` 等 i18n keys，但 stats/page.tsx 仍呼叫 `t("statsSlaHeader")`，導致工作樹半成品狀態（用戶察覺後手動修復）。

## AEO Feature Planning Rules

When planning any AEO (AI Engine Optimization) or SEO feature:

- **Static file checklist**: Any `web/public/` file added (e.g. `llms.txt`, IndexNow key `.txt`, Google verification `.html`) must have a corresponding `proxy.ts` matcher exclusion step in the plan. Without it, next-intl i18n middleware 307-redirects the file to a locale path (e.g. `/zh/google...html`), making it unreachable by external services. Use `google[0-9a-f]+\.html` to cover all Google verification file formats.
- **FAQPage plan must include visible `<dl>`**: Never plan "add FAQPage JSON-LD" without also planning "add matching visible `<dl>` section on the page". Google requires FAQ content to be visually present.
- **Migration number pre-check**: Before assigning a migration number, confirm the next available number with `ls supabase/migrations/ | sort | tail -5`. Two migrations with the same number must use `NNN` and `NNNb_` suffix.
- **i18n namespaces upfront**: When planning new page types (city pages, category pages), explicitly list all new i18n namespace keys needed in all three messages files as a plan step. Silent namespace miss = raw key on page.
- **IndexNow env vars**: Plans that add IndexNow submission must explicitly list `INDEXNOW_KEY` and `NEXT_PUBLIC_SITE_URL` as required env vars in both GitHub Actions secrets and (if needed) Vercel.
- **GSC integration must use OAuth2 refresh token**: Google Search Console UI **only accepts regular Google accounts** as users — service account emails return "找不到電子郵件" and cannot be added. Always design GSC API integration with OAuth2 refresh token (`GSC_CLIENT_ID` + `GSC_CLIENT_SECRET` + `GSC_REFRESH_TOKEN`), never service account JWT.
- **OAuth Playground requires test user setup**: When the OAuth consent screen is in "Testing" mode, the authorizing account must be added as a test user first, otherwise the flow returns 403 `access_denied`. Plans that include OAuth token generation steps must note this prerequisite.

## OG Image Multi-Language Truncation Rules

When planning or reviewing changes to `web/app/[locale]/events/[id]/opengraph-image.tsx`:

- **截斷閾值必須以英文長度為基準**：日/中文每字元視覺寬，36 字足以填滿標題區域；英文每字元視覺窄，需 50+ 字元才填滿同等空間。截斷 `N` 值應設 ≥ 55（英文基準），而非 36（日文基準）。
- **優先增加字體縮小級別，而非降低截斷閾值**：新增中間字體層（如 40px）讓長英文標題縮小後多行顯示，保留完整語意；只有視覺上確實溢出時才截斷。
- **目前三級字體設計**（截至 2026-05-01）：
  - ≤ 22 字 → 72px
  - 23–36 字 → 54px
  - 37–55 字 → 40px
  - > 55 字 → 40px + 截斷至 53 字
- 任何修改此邏輯的 plan 必須包含「用英文長標題（如 40+ 字母）和日文短標題（≤ 10 字）各一組」的視覺驗收步驟。

## Category Union Change Guard

After any plan that touches `web/lib/types.ts` Category union:
- `multi_replace_string_in_file` `oldString` for union type changes must include **≥3 lines** before and after the target member — insufficient context silently truncates adjacent union members (see: `retail` removed when `drama` added, commit `f9e6b52`)
- Plan must include an explicit post-change verify step: `cd web && npx tsc --noEmit`, confirming **all** prior union members still compile

## Admin Form New Field Checklist

When adding a new optional field to the `events` table that also appears in the Admin UI, all 7 points must be in the same plan:

1. **Migration** (manual step): `ALTER TABLE events ADD COLUMN IF NOT EXISTS <field> <type>;` — must be executed in Supabase Dashboard SQL Editor **before** any Python client seed or upsert referencing the new field. (Error if skipped: `PGRST204: Could not find the '<field>' column`)
2. **`scraper/sources/base.py`**: Add to `Event` dataclass as `Optional[str] = None`.
3. **`web/lib/types.ts`**: Add to `Event` interface as `field: type | null`.
4. **`AdminEventForm.tsx`** — two sub-steps:
   - `EMPTY_FORM`: add `field: ""`
   - UI: add corresponding `<input>` or `<textarea>` element
5. **`AdminEditClient.tsx`**: add `field: event.field ?? ""` to form initialization.
6. **`web/messages/*.json`**: add i18n key to all three files (`zh`, `en`, `ja`) simultaneously.
7. **Event detail page** (`web/app/[locale]/events/[id]/page.tsx`): if the field is user-visible, add locale-aware rendering (e.g. conditional `<a>` for URL fields).

Missing any point causes silent failures. Particularly:
- Missing point 1 → `PGRST204` at runtime, not at compile time.
- Missing EMPTY_FORM or form init → field appears blank in admin even when DB has a value.
- Missing i18n key → raw key string rendered in UI.
- Vercel build failure from a TypeScript error does **not** take the site down — it serves the previous build silently. Regression is invisible to users until manually checked.
- All 6 locations must be updated in the same commit (union, CATEGORIES, CATEGORY_GROUPS, zh/en/ja messages). See Engineer SKILL.md § Category Update Protocol for the full list.


- `sources/{name}/` — per-scraper platform profile（有 `applyTo: scraper/sources/*.py`）
- `agents/{name}/` — per-agent operational rules
- top-level — workflow/tooling skills only（local-preview, cc-statusline, session-analytics）
- 任何新的 per-source skill **必須** 放在 `sources/` 子目錄下，不可直接放頂層

## SQL Privilege Syntax Guard
- For PostgreSQL privilege statements, verify object-type syntax before finalizing migration SQL.
- View privilege revocation should use `REVOKE ... ON TABLE <view_name> ...`, not `ON VIEW`.
- For Supabase Security Advisor fixes, validate these statements line-by-line before execution:
  - `GRANT ... ON ...`
  - `REVOKE ... ON ...`
  - `ALTER VIEW ... SET (...)`
- If SQL Editor reports a syntax error, resolve by exact failing line first; do not change security model design until syntax is confirmed valid.

## Supabase RPC Auth Context Guard
- For `SECURITY DEFINER` RPC functions that gate admin access, do not rely only on `request.jwt.claim.sub`.
- Use `auth.uid()` as the primary identity source for real app requests, then fallback to claim only for SQL Editor simulation: `coalesce(auth.uid(), v_sub::uuid)`.
- Keep the function deterministic and explicit: `set search_path = pg_catalog`, schema-qualify cross-schema objects (`public.user_roles`, `auth.users`).
- Preserve strict denial path: when no effective user id or role mismatch, raise `42501` (`admin privileges required`).
- Before approving migration rollout, verify four cases:
  - app admin request: PASS
  - app non-admin request: DENY 42501
  - SQL Editor with `request.jwt.claim.sub` set to admin uid: PASS
  - SQL Editor without claim injection: DENY 42501

## Classifier Keywords
- Avoid single-character or title words (博士, 先生, 教授) in category keyword lists — they appear as proper nouns (person names) and trigger false positives. Prefer compound terms: 「博士課程」「博士論文」「教授法」.
- After adding a new category with new keywords, run a dry-run of `backfill_categories.py` and manually inspect every match before applying to DB.
- When a backfill produces a suspicious tag (e.g., a plant-walk event tagged `academic`), trace which keyword triggered it and tighten the rule immediately.

## AI Model Selection
- Verify model capabilities before designing features requiring real-time data (web search, live prices, current events). `gpt-4o-mini` and `gpt-4o` have no web browsing. Use `gpt-4o-search-preview` or a real search API for current data.
- "Plausible-looking output" ≠ "real data access." A model without search access will hallucinate convincing-looking URLs.

## HTMLParser Thin Content Guard

在審核任何使用 `html.parser.HTMLParser` 的 scraper PR 前，**必須**確認以下三點：

1. **噪音標籤已被過濾**：`<script>`、`<style>`、`<nav>`、`<header>`、`<footer>` 等噪音標籤必須在 `handle_starttag`/`handle_endtag` 中跳過。
   - 標準 pattern：`_SKIP = frozenset({"script","style","nav","header","footer"})` + `_skip` 計數器
   ```python
   def handle_starttag(self, tag, attrs):
       if tag in _SKIP:
           self._skip += 1
   def handle_endtag(self, tag):
       if tag in _SKIP and self._skip > 0:
           self._skip -= 1
   def handle_data(self, data):
       if self._skip == 0:
           self._buf.append(data)
   ```
2. **有效內容不僅是 `len(text) > 0`**：JS/CSS 代碼也是非空文字，但對業務邏輯無用。需確認業務關鍵字（如 `日時`、`場所`）是否存在於提取文字中。
3. **字元限制是否足夠**：對含大量 JS 的頁面，2000 字元常常不夠（JS 代碼先消費完預算，業務內容在限制之後）。建議至少 4000 字元。

Reference incident: 2026-05-04 hakusuisha `_T` HTMLParser 未過濾 script/nav，`■日時：` 出現在 2000 字元之後 → `raw_description` 無效（commit `4784266`）。

## Listing Page Date vs Event Date Guard

在審核任何 auto-generated 或人工撰寫的 scraper，其 `FIELD_SELECTORS["date"]` 或 listing page 日期提取邏輯時，**必須**確認以下兩點：

1. **listing page 日期欄位語意需驗證**：`span.note`、`time.published`、`.date` 等 selector 抓到的可能是**記事公開日**（YYYY.MM.DD），而非**活動日**。需實際檢視 listing page HTML 確認語意。
2. **活動日應從 detail 頁 `日時：` 標籤提取**：若 listing page 日期語意不可靠，必須從 detail 頁的 `日時：`、`開催日時：`、`■日時：` 等結構化標籤提取。
   - 有 `日時`：prepend `開催日時: YYYY年MM月DD日` 到 `raw_description`
   - 無 `日時`（公告/新聞文）：prepend `（記事投稿日: YYYY年MM月DD日）` 年份錨點
   - 參考實作：`scraper/sources/hakusuisha.py` → `_extract_event_dates(detail_text, card_year)`

Reference incident: 2026-05-04 hakusuisha `FIELD_SELECTORS["date"] = "span.note"` 抓取記事公開日而非活動日（commit `b3708e1`）。

## reviewed 保護邊界 Guard

在審核任何觸及 `annotation_status = 'reviewed'` 保護邏輯的計畫或 PR 前，**必須**明確區分以下兩種情境：

### 保護有值欄位（不允許覆蓋）
- 已有值的 `category`、`start_date`、`end_date`、`name_ja`（若 `name_ja_locked`）等欄位，`reviewed` 狀態**應阻止** GPT 重新覆蓋。
- 違反此規則 = 人工確認的資料被機器覆蓋 = data quality regression。

### 允許補填空欄位（不應被阻止）
- 值為 `NULL` 的 `business_hours`、`location_name`（若原本就空）等欄位，`reviewed` 狀態**不應阻止**確定性（非 GPT）邏輯補填。
- 空值補填是「填入缺失資料」，不是「覆蓋已確認資料」。

**設計準則**：
1. `--fix-reviewed` 模式應支援「空值補填」——只有當欄位目前為 `null`/空 時才寫入，有值則跳過。
2. 確定性提取（regex pattern）比 GPT 更適合用於 `reviewed` 事件的補填，因為不會產生幻覺。
3. 計畫中若包含「修復 reviewed 事件缺失欄位」，需明確說明是「補填空值」而非「重新標注」。

Reference incident: 2026-05-04 `business_hours=NULL` 因 `reviewed` 狀態保護永遠不修復（commit `54a20d7`）。

## Online Location Standard
- **Canonical online event representation**: `location_name = 'オンライン'`, `location_address = 'オンライン'`. **Both columns must be set; neither should be NULL.** DB also requires `location_address_zh = '線上'`, `location_address_en = 'Online'`.
- All scrapers must normalize online markers **before** building the `Event` object. Use `_ONLINE_RE` pattern: `r'(?:online|オンライン|ライブ配信|配信のみ|[Zz][Oo][Oo][Mm])'`.
- The web `location=online` filter queries `location_name ILIKE '%オンライン%'` (location_address is redundant for filtering but must still be set).
- The `location=other_japan` filter must exclude online events via BOTH `location_name NOT ILIKE '%オンライン%'` AND `location_address NOT ILIKE '%オンライン%'`.
- `AdminEventTable.tsx` `other_japan` filter must also check `!addr.includes('オンライン')` before accepting the event.
- Variants like `'オンライン（Zoom）'` must be canonicalized to `'オンライン'`.

## TV / Non-Physical Location Standard
- **Canonical TV/broadcast event representation**: `location_name = '電視頻道'`, `location_address = null`. TV programmes have no physical address — do not attempt to fill `location_address`.
- `gguide_tv` scraper must always set `location_name = '電視頻道'` regardless of the actual channel name (tvk1, BS朝日1, etc.). Storing raw channel names causes them to be treated as venue names and creates false positives in `other_japan` filtering and the quality page address check.
- The `location=other_japan` filter must exclude TV events via `location_name NOT ILIKE '%電視頻道%'`. Add this alongside the existing `オンライン` exclusion.
- **Quality page address check whitelist**: The「缺地址」(missing address) quality check must skip sources/venues that are inherently address-free. Current whitelist: `source_name = 'gguide_tv'` and `location_name ILIKE '%電視頻道%'`.
- When adding a new no-physical-address source in the future, update BOTH the `other_japan` filter exclusion AND the quality page whitelist.

## New Location Type Checklist

> **Pre-flight check**: Before adding a new location filter option, run `SELECT count(*) FROM events WHERE location_name = '<value>' AND is_active = true` to confirm there are enough matching events. A location option with zero or near-zero results is an invalid option and should not be added (or must be removed). The `tv` filter was added and later removed because `location_name` no longer matched — always verify DB data format against the actual scraper output first.

When adding a new `location` filter type (e.g., a new region or a new special category like `tv`), update ALL 6 of the following in the same commit:

1. **Scraper** — Set a canonical `location_name` value in the relevant scraper(s)
2. **`web/app/[locale]/page.tsx`** — Add the new filter branch with the correct Supabase query; update `other_japan` to exclude the new type if applicable
3. **`web/messages/{zh,en,ja}.json`** — Add the new i18n key to ALL THREE files simultaneously
4. **`web/components/FilterBar.tsx`** — Add the new `<option>` to the location select
5. **`web/components/AdminEventTable.tsx`** — Update BOTH `getFiltered` AND `sourceCountMap` with the new filter logic; add the `<option>` to the admin select; update `other_japan` exclusion
6. **Quality page** (`web/app/[locale]/admin/quality/page.tsx`) — If the new type has no physical address, add it to the「缺地址」whitelist

Missing any one of these causes: filter mismatch (items appear in wrong section), missing translation (raw key shown), or quality false positives.

### Overseas (Taiwan Cities) Filter Special Notes
- **Address format differs from Japan**: Taiwan city addresses are stored directly in the `address` column (e.g. `台北市…`). No prefix guard or `.startswith()` check is needed — Taiwan city names are not substrings of Japanese place names.
- **Use `ilike '%城市名%'`** for matching; do NOT use `location_name` equality — Taiwan events use the raw address column.
- **`OVERSEAS_MARKERS` must stay in sync** between `page.tsx` and `AdminEventTable.tsx`. The canonical 16-city list: 台北、台中、高雄、台南、新竹、嘉義、花蓮、台東、基隆、宜蘭、桃園、屏東、南投、彰化、雲林、澎湖.
- Overseas filter does **not** require exclusion from `other_japan` — these are physically separate geographic categories.

## Online Events (Peatix)
- Peatix renders online-only events as `LOCATION\n\nOnline event` (single line, no address group). The two-part regex `LOCATION\n\n(.+)\n\n(.+)` will NOT match — always add a separate `loc_online_m` check BEFORE the two-part regex.
- Set an `is_confirmed_online` flag immediately on match and **skip all CSS and regex address fallbacks** — description body text often mentions a venue as a conditional/secondary option and must never be used as `location_address`.
- For confirmed online events: `location_name = 'オンライン'`, `location_address = 'オンライン'`.
- The final body-text online fallback must also set `location_address = 'オンライン'`, NOT `None`.

## Address Verification
- **Never change a hardcoded address based on a DB value alone.** The DB may contain AI-hallucinated addresses from `backfill_locations.py` or the annotator. Always verify against the official source website first.
- Every hardcoded `location_address` in a scraper must include a comment citing the verification URL and date, e.g.:
  ```python
  # Verified: https://jp.taiwan.culture.tw/cp.aspx?n=362 (2026-04-26)
  location_address = "東京都港区虎ノ門1-1-12 虎ノ門ビル2階"
  ```
- When a user questions a displayed address, use `fetch_webpage` on the official source URL before drawing any conclusion.
- If `backfill_locations.py` has run on a source with a known fixed address, audit those DB records — AI-generated translations may contain hallucinated street numbers.
- **`enrich_addresses.py` batch fills are AI-generated and NOT verified**: GPT-4o-mini fills `location_address` / `_zh` / `_en` for events with a venue name but no address. These must be treated as unverified estimates. Known failure: MoN Takanawa (新場館) was filled with `東京都港区高輪4-10-30` (incorrect) instead of `東京都港区高輪2-21-2` (2026-05-01). After any batch fill run, manually spot-check records from high-profile partner venues (SSFF, TAICCA co-hosted venues, etc.) against their official access pages (`会場・アクセス` section).

## i18n Completeness
- After writing or reviewing any TSX file with visible UI text, run the CJK audit before approving: `python3 -c "import os, re; [print(f+':'+str(i)+':'+l.strip()) for root,_,files in os.walk('web') for f in files if f.endswith('.tsx') for i,l in enumerate(open(os.path.join(root,f)).readlines(),1) if re.search(r'[\u4e00-\u9fff\u3040-\u30ff]',l) and not any(p in l for p in ['t(','tFilters(','tCat(','tEvent(','getEvent','MARKERS','//',"'//"])]" 2>/dev/null`
- Module-level consts that include translated strings CANNOT use `useTranslations()` (React hook rules). Either move the const inside the component function, or pass the translation function as a parameter.

## Cross-Platform Environment Variables

When a feature spans **both GitHub Actions and Vercel** (e.g., LINE broadcast runs in GitHub Actions; LINE webhook runs on Vercel), each platform needs its own copy of every required secret.

**GitHub Actions secrets ≠ Vercel environment variables.** They are completely separate systems and do not share values automatically.

### LINE bot deployment checklist
Both of the following must be set in **both** platforms before the feature goes live:

| Variable | GitHub Actions Secrets | Vercel Env Vars |
|---|---|---|
| `LINE_CHANNEL_TOKEN` | ✅ (for broadcast) | ✅ (for webhook signature) |
| `LINE_CHANNEL_SECRET` | ✅ (for broadcast) | ✅ (for webhook signature) |

Setting a secret in only one platform silently breaks the other side. Webhook 401 failures are especially hard to detect because LINE does **not** retry failed webhook deliveries — events are permanently lost.

### General rule for cross-platform features
In the Verification section of any plan involving both CI (GitHub Actions) and web hosting (Vercel), explicitly list:
1. Which env vars are needed on **Vercel** (web-facing features: webhooks, API routes)
2. Which env vars are needed in **GitHub Actions** (CI/cron features: scrapers, broadcasts)
3. Any vars that are needed in both (shared secrets like LINE credentials)

## GITHUB_TOKEN Permission Consistency Guard

- Canonical wording for this repo:
  - Fine-grained PAT: `Issues: write + Metadata: read`
  - Classic token: `repo` scope
- Any change that touches token requirements must update all relevant layers in one batch:
  1. Runtime/error message (`scraper/update_source.py`)
  2. Operational docs (`docs/GITHUB_TOKEN_SYNC_CHECKLIST.md`, `.github/instructions/token-rotation.instructions.md`)
  3. Agent workflow docs (`.github/agents/researcher.agent.md`)
  4. Lifecycle summary (`.github/SECRETS_LIFECYCLE.md`)
- Do not allow non-standard permission wording (e.g. combining read+write with an `&`) to coexist with the canonical `Issues: write + Metadata: read`.

## Secrets Documentation Single Source Rule

- `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md` is the single source of truth for the GITHUB_TOKEN sync checklist.
- Other files may reference it, but must not maintain an independent duplicated checklist body.
- If a legacy path must remain for compatibility (for example, `.github/TOKEN_SYNC_CHECKLIST.md`), convert it to a redirect-style stub that points to the docs source.

## Public Repo Secret Hygiene Check

- For public repositories, treat secret-documentation changes as security-sensitive changes.
- Before closing a token-related task, verify:
  1. `scraper/.env` is ignored by git (`git check-ignore -v scraper/.env`)
  2. No real token examples are committed in docs (use placeholders like `github_pat_xxx`)
  3. Secret references in tracked files are descriptive only, never literal credentials
- If a real credential is found in tracked files: rotate immediately, purge history if needed, then update docs with placeholders.
- Every new i18n key must be added to ALL THREE `messages/*.json` files simultaneously — never add to just zh.json.
- When an admin page uses `getTranslations("admin")`, check if it also needs `getTranslations("general")` for shared strings (footer, error banners).
## i18n Regression Prevention (CRITICAL)
- **翻譯 JSON 只能新增、修改，絕不刪除 key**，除非確認全 codebase 所有 TSX/TS 都已移除該 key 的引用。
- **Scraper / DB / Agent 等非 web commit 不得修改 `web/messages/*.json`**。如果 AI 在同一 commit 中捆綁了翻譯修改，必須 split commit 或手動 revert 翻譯部分。
- 每次修改翻譯後，執行 key 完整性驗證：
  ```bash
  python3 -c "import json; a=set(json.load(open('web/messages/zh.json')).keys()); b=set(json.load(open('web/messages/en.json')).keys()); c=set(json.load(open('web/messages/ja.json')).keys()); print('zh-en diff:', a-b); print('zh-ja diff:', a-c)"`
  ```
- 若懷疑翻譯被洗掉，立即執行：`git log --oneline --since="3 days ago" -- 'web/messages/*.json'` 逐一檢查可疑 commit 的 diff（`git show <hash> -- 'web/messages/*.json' | grep '^-'`）。
- **根本防護**：`categories` namespace 中的 group_ 標籤（`group_arts`/`group_lifestyle`/`group_knowledge`/`group_society`/`group_archive`）和晚期新增的子分類（`competition`/`indigenous`/`history`/`urban`/`workshop`）是歷史上最常被意外洗掉的 key，每次 web 功能發布前必須確認這些 key 存在。

## Reviewed Event Translation Guard (CRITICAL)
- **`reviewed` 狀態的活動不應有 `name_zh = NULL` 或 `name_en = NULL`**。若有，後台 AdminEventTable 會顯示紅色 ⚠ 徽章提醒管理員。
- **永遠不要在翻譯欄位未填齊的情況下將活動標記為 `reviewed`**。完整欄位清單：`name_zh`、`name_en`（必要）；`description_zh`、`description_en`（建議）。
- `annotator.py` 的 `--fix-reviewed` 旗標可自動修復缺少翻譯的 reviewed 活動（僅補翻譯欄位，保留 category 和 `annotation_status = "reviewed"`）。
- **daily CI 已設定每日自動執行 `python annotator.py --fix-reviewed`**，作為背景防護網。
- 設計涉及 `annotation_status` 流程的功能時，必須考慮 reviewed 活動跳出翻譯流程的問題。
## Prompt Efficiency (User-Side Rules)

## Migration Verification Protocol
- For any `SECURITY DEFINER` RPC or privilege-critical migration, establish a **four-quadrant verification matrix**:
  - App request with admin user (real auth.uid())
  - App request with non-admin user (real auth.uid())
  - SQL Editor with claim-injected admin uid (`request.jwt.claim.sub = '<admin_uuid>'`)
  - SQL Editor without claim injection (no auth context)
- Create an executable SQL smoke test suite (e.g., `027_smoke_test.sql`) with temp tables to avoid manual UUID copy-paste errors.
- Generate a verification report (e.g., `027_VERIFICATION_REPORT.md`) documenting:
  - Test date and status (ALL TESTS PASSED or FAILING with step number)
  - Each test's code line reference and expected result
  - Security architecture diagram (e.g., "Prefer auth.uid(), fallback to claim with exception handler, then role gate")
  - Deployment readiness checklist
- Mark migration as "PRODUCTION READY" only after all four quadrants + return type validation pass.

## Separate Workflow Decision（新 Pipeline 的 CI 設計原則）

當設計新的自動化 pipeline（auto-research、auto-generate、heartbeat PR 等）時：

- **禁止將新 pipeline 加入 `scraper.yml`**。`scraper.yml` 是事件抓取主流程，任何非必要的步驟失敗都不應中斷每日爬蟲排程。
- **每個獨立 pipeline 必須有自己的 workflow file**（例如 `auto-research.yml`、`auto-generate.yml`）。
- **排程時間設計**：新 pipeline 應在主爬蟲完成後排程。參考時間線（JST）：
  - 00:00 — researcher Slot 3（現有）
  - 00:30 — auto-research（30 分鐘緩衝後）
  - 01:00 — auto-generate（再 30 分鐘後）
  - 02:00 — daily report（彙總上述結果）
- 每個新 workflow 都應有 `workflow_dispatch` 以便手動觸發，並支援 `dry_run` input。

## Heartbeat Pipeline Guard（auto PR 建立的前提條件）

在設計或重啟「heartbeat PR 自動建立（auto-generated scraper PR）」pipeline 之前，以下三個先決條件必須全部滿足：

### 1. Prompt Injection 防護（必要）
`generate.py` 在 spec 生成時把 sample HTML 直接送入 LLM prompt。外部網站的 HTML 可能包含惡意 comment（如 `<!-- SYSTEM: ignore previous instructions -->`），操控 LLM 輸出惡意程式碼，再自動 commit 進 repo。

**解法（必須先實作）**：在 HTML 進入 LLM 前先 sanitize：
```python
from bs4 import BeautifulSoup, Comment

def sanitize_html(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "meta", "link", "noscript", "iframe"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    return str(soup)
```
此 sanitize 步驟必須在 `_fetch_sample_html()` 回傳前執行，不能只在 spec 生成時執行。

### 2. sandbox 驗證強化（必要）
目前 sandbox 只檢查 `events_found >= 1`，不足以確認品質。heartbeat pipeline 啟用前須加入：
- `source_id` 穩定性：連續兩次執行 `source_id` 值不變
- `start_date` 非空且非 fallback 至今日（排除以發布日代替活動日的情形）

### 3. main.py 衝突避免（必要）
多個 auto-generated PR 同時修改 `scraper/main.py` 的 `SCRAPERS` 列表，merge 時必定衝突。解法之一：每個 PR 僅新增一行，並在 PR description 中標示唯一的插入位置（如「在 peatix.py 之後」）。

**此規則的後果**：在三個條件都滿足之前，`auto-generate.yml` 不應啟用 `--create-pr` 或 heartbeat 模式，只允許 dry-run + sandbox 驗證。

## Scraper Source Registration Audit
- Monthly audit: Compare `sources/` directory against `SCRAPERS` list in `scraper/main.py` to find unregistered source files.
  - Command: `comm -23 <(find sources/ -name '*.py' | xargs -I {} basename {} .py | grep -v '^__' | sort) <(grep 'Scraper()' scraper/main.py | sed 's/.*\(.*\)Scraper().*/\1/' | sort)`
- When a new scraper source file is created, immediately register it in `SCRAPERS` and run `python main.py --dry-run --source <name>` to verify event count is non-zero or document expected reason (offline season, no Taiwan matches, festival in October).
- Do not rely on CI discovery or daily cron to catch missing registrations — manual registration is mandatory at commit time.

## Cinema Official URL Extraction
- Cinema scrapers must extract `official_url` from the film detail page using one of:
  - Link with text "チケット" or "購入" (ticket/purchase keywords)
  - Href pattern containing `/ticket/` or `/purchase/` (domain-agnostic)
- Always verify extracted URL domain is not a third-party ticket vendor (e.g., Playplay, Peatix reseller, Rakuten Ticket) — maintain a domain whitelist of known official cinema URLs.
- When adding `official_url` extraction to an existing scraper, immediately backfill validation:
  1. Run scraper with `--dry-run` and manually inspect first 5 events
  2. Confirm URLs are valid, resolve without 404, and point to official pages (not redirects to vendor)
  3. Only then commit and push to production
- For Google Search fallback in film title lookup: always prioritize `name_ja` (Japanese title) regardless of current request locale. Google Search ranks results by search query locale, not result locale — using a locale-specific name variable will cause wrong film matches and incorrect `official_url` extraction.

## Prompt Efficiency (User-Side Rules)

When plans involve multiple similar tasks or iterative fixes, guide the user toward these batching patterns to avoid unnecessary tool overhead:

- **Scope creep via URL**: If a user pastes a URL and asks to "check similar cases", clarify scope first. Do NOT do a full codebase scan unless explicitly requested. Ask: "只修這個？還是要檢查所有同類？"
- **Sequential same-type tasks**: When the user says "請繼續做 XXX" for each item, propose batching: "建議一次列出全部，我依序完成後統一回報" to avoid repeated context reloading.
- **Fix + rule update coupling**: When discovering a bug, fix it first. Defer history/skill updates to a dedicated batch step. Recommend: "先修完所有 bug，稍後一次批次更新 skill 和 history。"

See `.github/skills/session-analytics/SKILL.md` for the full anti-pattern catalogue and efficiency thresholds.

## Agent Handoff Design

When designing agent workflows that need one-click handoff buttons:

### `.prompt.md` vs `.agent.md` Distinction
- **`.prompt.md`** — One-off tasks invoked via `/` command or skill menus. No persistent role, no tool restrictions per task. Use for: "Generate test cases", "Create README", "Summarize metrics".
- **`.agent.md`** — Persistent agent persona with role, tools, and instructions. Use for: long-running workflows, role-based tool restrictions, or handoff chains. Can be invoked via agent picker or as handoff target.
- **Handoffs only route to `.agent.md` files** — the `agent:` field in `handoffs:` must reference an `.agent.md` file's `name`, NOT a `.prompt.md` filename.

### Handoff Frontmatter Format
```yaml
handoffs:
  - label: "🔧 Button text"
    agent: AgentNameFromFile        # Must match .agent.md name exactly
    prompt: "Chinese instruction"    # Pre-filled when user clicks
    send: false                       # Optional, default false
    model: "Claude Sonnet 4.5 (copilot)"  # Optional, inherits agent default if omitted
```

### Subagent Configuration for Handoff Targets
When creating an agent **only for handoff invocation** (not for manual picker):
```yaml
---
name: My Handoff Agent
description: "Brief role description"
user-invocable: false               # Hide from agent picker
disable-model-invocation: false     # But allow handoff invocation
tools: [read, search, execute, web] # Minimal necessary tools
---
```

### Best Practices
1. **Name consistency**: Agent `name:` in frontmatter must match the handoff `agent:` field exactly (case-sensitive).
2. **Chinese instructions in prompt**: Always include `prompt:` field with clear Chinese task description to ensure context transfer.
3. **Workflow grouping**: If two agents form a natural sequence (e.g., Plan → Implement → Review), add all three as handoffs in each agent to enable any→any routing.
4. **Testing**: After adding handoffs, verify in VS Code: restart Copilot Chat, check that buttons appear, test context passing via `prompt:` field.

## Resource Monitoring

預算層——`scraper/weekly_report.py`（LINE 週報）為全站唯一資源使用監控來源：

- 三個門檻常數：`WEEKLY_OPENAI_USD_WARN = 5.0`、`WEEKLY_DEEPL_CHARS_WARN = 100_000`、`MONTHLY_BUDGET_USD = 20.0`。
- LINE 訊息包含：本月迄今 / OpenAI 本週 / DeepL 本週，超過閾值顯示 ⚠ 或 🚨。
- 適用時機：每週一 09:00 JST（GitHub Actions cron）。
- 閾值調整請同步更新這份文件與 `weekly_report.py` 常數。

## Admin Page Consistency

新增任何 `/admin/` 子頁面時，**header 必須使用完整 tab nav** 而非「← 返回管理後台」連結：

1. 從 `getTranslations("admin")` 取得所有 tab 標籤的 i18n 翻譯。
2. 使用與其他 admin 頁面一致的 Link 列表結構（參考 `web/app/[locale]/admin/aeo/page.tsx` 或 `events/page.tsx`）。
3. 把新 tab 的 key 同步加入三個 `messages/*.json` 中的 `admin` namespace。
4. 不可只放「← 返回」連結——這會破壞 admin 導航一致性。

反例：2026-05-01 aeo 頁面原本只有「← 返回管理後台」連結，後來在 commit 5cae991 才補齊完整 tab nav。計劃階段就應強制要求。

## Untrusted-Code Sandbox Rules (auto-scraper Phase 2+)

When designing any feature that runs LLM-generated or otherwise untrusted Python in a subprocess (auto-scraper codegen, plugin execution, etc.):

- **env scrubbing must be allowlist, not blacklist.** Pass only `PATH` / `HOME` / `PYTHONUNBUFFERED` / `PLAYWRIGHT_BROWSERS_PATH` / `TMPDIR` / `LANG` / `LC_ALL`. Never pop known secret keys (`SUPABASE_*`, `OPENAI_API_KEY`, `GITHUB_TOKEN`, `LINE_*`) from a copied env — any future `.env` addition will silently leak. Allowlist is fail-closed; blacklist requires constant maintenance.
- **Temp file cleanup needs both `try/finally` AND `atexit.register(cleanup)`.** `try/finally` covers normal + exception paths; `atexit` covers SIGKILL / unhandled exit. One alone is insufficient for codegen artifacts (e.g. `_auto_<name>.py` shimmed for subprocess import).
- **Mutation surface must be locked per phase.** Codegen / unsafe-validation phases must NOT register into production lookup tables (e.g. `SCRAPERS`), open PRs, or write to user-facing DB tables (`events`). Only the source's own status row may be updated. Activation must live in a separate phase / commit / reviewer to keep the unsafe→safe boundary auditable.
- **AST safety check + sandbox dry-run is the minimum bar** before promoting any auto-generated code to "ready for review". Both gates fail-closed.

Reference incident: 2026-05-01 commit `a0606fe` (auto-scraper Phase 2). Pre-implementation review chose allowlist after enumerating future `.env` additions.

## LLM Pricing Constants Re-verification

Any code path that gates on LLM cost (per-call budget, daily ceiling, abort-on-overspend) hardcodes pricing constants that drift over time. Architect session checklist when reviewing such code:

- **Verify pricing constants vs current OpenAI / Anthropic public pricing page** at every quarterly review or whenever the model upgrades (e.g. `gpt-4o` → `gpt-4.1`).
- **Centralize constants in one file.** Do not duplicate `INPUT_USD_PER_1M` / `OUTPUT_USD_PER_1M` across scrapers. Current home: `scraper/auto_scraper/generate.py` (`$2.50/1M input`, `$10.00/1M output`, default budget `$1.50/source`).
- **Pair every pricing constant with a comment citing the verification source URL and date.**
- **Treat budget guards as security-critical.** A stale pricing constant means the abort threshold is wrong — either runaway costs or premature abort. Add to release-readiness checklist: "Pricing constants checked? Y/N".

## Prompt-Referenced Artifact Verification

When reviewing any plan whose prompt copy says things like "matching the schema (provided)", "following the spec attached", "as listed below", verify the referenced artifact is **actually injected** into the LLM `messages` array — not merely cited by name.

- `grep` the prompt text for the file/schema name, then trace every reference to confirm: (a) the file is read at runtime, (b) its contents are concatenated into a `system` or `user` message, (c) the injection point sits BEFORE any place where the LLM is asked to use it.
- A prompt that references X without injecting X is functionally equivalent to omitting X entirely. The LLM will hallucinate a plausible-looking version of X.
- For required-field checklists in `spec.json`-style outputs, also enumerate critical fields explicitly in the prompt body (belt + braces). Schema injection alone is not enough — the LLM ignores schema details when verbose.
- Reference incident: 2026-05-02 Phase 2 — SYSTEM_PROMPT cited `spec_schema.json` but the schema was never loaded. Three retries omitted `base_url`. Fix in `b6e1768`.

**Plan-review checklist line**: "Every prompt-referenced artifact (schema, sample, examples) is verified to actually appear in the messages array."

## LLM-Generated Artifact Validation Pattern

For any LLM-generated artifact that references real-world identifiers (CSS selectors, file paths, function names, API endpoints, package names, environment variables), add a **fast pre-validation step** that confirms the reference exists before downstream consumption.

- **Grounding > trust.** LLMs hallucinate plausible-looking identifiers (`.event-card`, `.user-list-item`, `getUserById`) at high rates, especially when the reference base is large or the LLM is verbose.
- **Pre-validation should fail-fast and feed back into the retry loop.** Failure messages must be specific ("selector `.event-card` matches 0 elements in sample HTML; available repeating elements: `li.article-list` (12), `article.post` (4)") so the next LLM call can correct itself.
- **Cost asymmetry justifies the validation step.** A 50ms BeautifulSoup check vs a 30s Playwright sandbox + $0.04 LLM round-trip is 600× / $0.04 cheaper per failed validation.
- Reference incident: 2026-05-02 Phase 2.3 — `_validate_selectors_against_html()` added before sandbox spawn. Zepp Tokyo / Fukuoka Now batch1 wasted $0.04 each on sandbox-failed; batch2 fast-failed in <100ms with no Playwright spawn.

**Pattern catalogue** for future LLM-generated artifacts:

| Artifact | Validation step | Tool |
|----------|----------------|------|
| CSS selectors | `BeautifulSoup.select()` count ≥ 1 against sample HTML | bs4 |
| File paths in repo | `Path(...).exists()` | pathlib |
| Python function/class names | `ast.parse` + symbol walk | ast |
| URLs | HEAD request, expect 2xx/3xx | requests |
| Env var references | `os.environ.get(...) is not None` | os |

## Failure-Path Instrumentation

When a function returns different shapes for success/failure paths, instrumentation (cost, retry count, elapsed time, token usage) must be in a `finally` block or shared mutable accumulator — not after the success-only return.

- Symptom: meta files show `cost_usd=0.0` and `retries=0` on failed runs even though logs prove multiple LLM calls happened.
- Fix pattern: maintain `accumulator = {"cost": 0.0, "retries": 0}` at function scope; mutate in every retry branch; persist in `finally` regardless of exit path.
- Reference incident: 2026-05-02 Phase 2.3 spec-invalid path — 3 retries shown in logs, 0 cost in meta. Phase 2.4 TODO.

