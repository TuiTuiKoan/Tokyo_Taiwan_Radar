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
- For publication-related pending QA, clean by source and status transition first. If a source is mixed-content like `eslite_spectrum`, keep the rule set conservative and do not fold promotional talk events into the same batch.
- Venue homepage repairs (`location_url`) are provenance-sensitive. The only safe auto-fix target is the venue's own official homepage; never promote `source_url`, `official_url`, or `organizer_url` into `location_url` just because a search hit looks plausible.
- If a venue cannot be verified to have its own homepage, leave the report pending for human review. Shared municipal spaces and parent-organization pages are especially prone to false positives.
- For pending QA cleanup, use `qa_heartbeat.py` as the real dispatch entry. `qa_auto_fix.py` CLI only runs its own built-in maintenance batches (simplified Chinese + tokyoartbeat date sync); do not assume it will process the full safe-report backlog.
- Database-only QA cleanup does not require git push or deployment. Only change code or docs when the cleanup logic itself needs to be adjusted.
- For publication metadata backfills, keep the helper logic source-scoped: NDL OpenSearch periodical rows need breadcrumb-derived labels and publisher-backed organizer, while non-periodical publication rows may keep the generic publication placeholder.
- For publication metadata backfills, also prefer the official product page description when `official_url` is present, and prefix publication titles with `[新刊出版]` across locale variants. NDL magazine and journal rows should use bracketed periodical labels like `[期刊專文]`.

## Agent Handoff Reliability

- For workflow agents, treat handoffs as a required output path, not optional UI polish.
- If a handoff defines `prompt:`, set `send: true` when the intended behavior is one-click execution.
- Pre-ship check for agent changes: verify target agent names resolve correctly and at least one post-task handoff exists for the expected next action.
- **Every new agent file must include `handoffs:` at creation time.** An agent with no handoffs leaves users stranded after task completion.

## CSS Selector Specificity Pitfalls

- `[attr='x'].class` = same element (no space). `[attr='x'] .class` = descendant combinator (space = different element).
- When combining an attribute selector with a class on the **same element** (e.g., `data-preserve-theme` and `group` on the same `<Link>`), never insert a space between them.
- For theme-exception rules like `[data-preserve-theme='light'].group:hover h2`, verify: (1) the attribute and the class are on the same DOM element, (2) combined specificity beats any competing rule, (3) use `getComputedStyle` via Playwright to confirm hover color changes.

## Cross-browser Baseline Checks

- When a UI change touches shared pills, buttons, tabs, or dropdown triggers, verify the result in both Chrome and Safari before broadening the fix.
- If Safari alone looks vertically off, prefer the smallest browser-specific baseline correction over reworking every related component.
- Recheck computed `line-height`, `padding`, and element height in Safari after any shared `inline-flex` / `rounded-full` refactor.
- **Safari WebKit #169700 — `flex` on `<button>` mis-calculates height.** Never put `flex items-center justify-center gap-3` directly on a `<button>` className. Wrap the content in an inner `<span className="flex items-center justify-center gap-3">` instead. The `<button>` keeps only padding / border / background and remains at its native block height in both Chrome and Safari.

## Click Hit-Area Integrity

- Overriding a shared `Button`'s padding with `px-0 py-0` shrinks the clickable hit area down to the text glyphs — the element looks present but is effectively unclickable in the padding zone.
- To visually align a button flush with its container edge, offset with a negative margin (e.g. `-ml-4`) instead of zeroing the padding. Keep the component's native `px-4 py-2` hit area.
- In a `flex justify-between` row, always give the adjacent heading `truncate` and give the interactive element `shrink-0`. A long (often English) title can otherwise overlap and steal a low-padding sibling's hit area.

## API Route Error Surfacing

- "Success" for an API route is NOT "did not throw." Every external call (LLM, DB write, third-party fetch) must explicitly check `res.ok` / `error` and return a non-2xx status with a readable `detail`.
- Anti-pattern that hides root cause for days: `if (extRes.ok) { ... }` with no `else`, empty `catch {}` around `JSON.parse`, and unchecked `await supabase...update()` — then returning `200 { success: true }` regardless. The frontend's `t(res.error)` then has nothing to show and only the generic `saveFailed` appears.
- When adding a new backend error code, surface it end-to-end: non-2xx + `{ error, detail }` on the server, append `detail` to the frontend message, and add the i18n key to all three `messages/*.json` simultaneously.

## Navigation Action Pattern

- Nav click handlers must NOT do async DB pre-flight to decide the routing target. "Fetch-then-route" binds DB latency to click feedback and makes the action fragile if the fetch fails or times out.
- Let the destination page handle conditional redirects (e.g. profile-required check). The nav only pushes the canonical URL; the page reads its own state and redirects if needed.
- Remove any `loading` state that was only there to cover the pre-flight gap — users should see an immediate page transition, not a loading spinner inside the nav dropdown.

## E2E Local Server Prerequisite

- When running Playwright smoke tests that navigate to local paths (for example `/ja/announcements`), start a local Next server first (`npm run dev` or configured `webServer`) and verify port 3000 is reachable.
- Treat `net::ERR_CONNECTION_REFUSED` as an execution-environment failure first, not an application regression.
- After the test run, stop any background dev server to avoid orphaned processes and cross-session interference.
- Fixed-width device preview frames must use responsive constraints such as `w-full max-w-[390px]`; do not set `width: 390px` inside padded mobile pages. In visual smoke tests, assert document `scrollWidth <= clientWidth` and distinguish expected horizontal carousels from real page overflow.

## Secret Scanning — Three-Layer Defense（fail-open；2026-06-28 教訓）

新增/修改密鑰掃描時三層必須一致，且都是「降低風險」非 non-bypassable（真正強制需 server-side branch protection）：

| Layer | 位置 | 行為 |
|-------|------|------|
| 1 | `.githooks/pre-commit` | `gitleaks git --staged -c .gitleaks.toml`；缺 binary → 警告 + `exit 0`（fail-open，不擋本機 commit）|
| 2 | `.githooks/pre-push` | 有 gitleaks → 掃 push range；無 → regex fallback 擋 `github_pat_…{20,}` / `sk-…` / `eyJ…` JWT |
| 3 | `.github/workflows/secret-scan.yml` | CI merge gate；version-pinned + checksum-verified gitleaks binary（非 gitleaks-action，免 org license）；`permissions: contents: read` |

- **regex fallback 必含 placeholder allowlist**：shell fallback **不讀** `.gitleaks.toml`。tracked docs 的具名 placeholder（`github_pat_REPLACE_WITH_YOUR_TOKEN`、`github_pat_<NEW_TOKEN_VALUE>` 等）長度超過 `{20,}`，裸 fallback 會誤判為真 secret → 命中後先 `grep -vE '<placeholder>'` 過濾再判定。三份 allowlist（`.gitleaks.toml`、pre-push fallback、Hygiene git grep）同一份語意，改一處要三處同步。
- **Public Repo Secret Hygiene**：掃 tracked 檔用 `gitleaks git --redact --no-banner -c .gitleaks.toml`（命中數須為 0；allowlist-aware + redacted）。**禁止 repo-root `grep -rn`**——會讀進被 .gitignore 忽略的 `scraper/.env`，把真 PAT 印到 terminal / transcript / CI log。`git check-ignore -v scraper/.env` 須命中、`git ls-files --error-unmatch scraper/.env` 須失敗。
- **token docs 存在性檢查改 masked**：任何文件不得叫人 `grep "^GITHUB_TOKEN=" .env`（會印 token 行）；改 `awk -F= '/^GITHUB_TOKEN=/{print "present, len="length($2)", prefix_ok="...}'`（length/prefix，不印值）。canonical 來源 `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md` 與同步副本 `.github/instructions/token-rotation.instructions.md` 必須同 commit 保持一致。

## Admin GPT routes — server-side enum whitelist intersect（2026-05-26 教訓）

Admin OCR/annotate API routes（`web/app/api/admin/extract-from-image/route.ts`、`web/app/api/admin/annotate-event/route.ts`）由 GPT 直接輸出 enum 欄位（`category[]`、`event_form`、`prefecture_code`），**寫入 DB 前必須做白名單過濾**。三道天然防線對此無效：

| 防線 | 為何失效 |
|---|---|
| TypeScript | 只檢查靜態型別，不檢查 runtime LLM 輸出 |
| DB CHECK constraint | `text[]` 陣列**元素**無法 CHECK，只能 CHECK 整個陣列存在性 |
| `scraper/annotator.py::_validate_categories()` | 只有 daily scraper 路徑會跑，admin route 完全繞過 |

**規則：** 兩個 admin route 在 GPT 回傳後、`upsert` 前必須：

```ts
const VALID_CATEGORIES = new Set([
  /* 與 web/lib/types.ts CATEGORIES 同步 */
]);
const sanitized = (parsed.category ?? []).filter((c: string) => VALID_CATEGORIES.has(c));
```

`VALID_CATEGORIES` 集合可從 `web/lib/types.ts` 匯入 `CATEGORIES` 陣列轉成 Set，避免雙重維護。同理適用 `event_form`、`prefecture_code` 等所有 enum 欄位。

**Reference incident:** 2026-05-26 — event `25e27de9` GPT 自創 `photography` 入庫，前端顯示 `categories.photography` raw i18n key（commit `264afed` 解了眼前事件，未實作 whitelist filter，列 backlog）。

**Shared lib rule（2026-06-05 教訓）：** 兩條以上 annotate route 做相同 LLM 輸出過濾時，立刻抽到 `web/lib/eventFieldMerge.ts`（或同目錄的 shared module），不要各自內聯。`account/annotate-event` 與 `admin/annotate-event` 原本各自複製 `validCategories` / `validEventForms` / `VALID_PRIMARY_LANGUAGES`，2026-06-05 已統一到 `sanitizeCategoryValues()`、`sanitizeEventFormValues()`、`sanitizePrimaryLanguageValue()`。

**Location field overwrite protection：** annotate route 不可用 `cur === null || cur === ""` 的空值檢查來決定是否覆寫 `location_name`/`location_address`。必須同時考量：(1) web search score（空值填入 ≥ 3，非空 upgrade-overwrite ≥ 6），(2) 使用者是否明確鎖定欄位（`lockedFields`），(3) 欄位是否明確來自本次 create/edit session 的 auto-fill provenance（`overwriteableFields`，通常只包含 OCR 自動填入且尚未被手動改過的欄位）。邏輯已封裝在 `shouldApplyAnnotatedLocationField(field, cur, v, { bestScore, lockedFields, overwriteableFields })`。**缺少 provenance 時，非空欄位必須預設維持 fill-only，不得冒然覆寫。** 任何新 annotate route 與對應 create client 都應使用這組 shared contract，而不是各自內聯 overwrite 條件。

## Database
- Always verify a migration has been applied in Supabase before writing code that depends on it. Check: `SELECT table_name FROM information_schema.tables WHERE table_name = 'X';`
- When adding a DB column, wire up the code that populates it in the same commit. Empty columns = silent data gaps.
- Wrap non-critical DB inserts (logging, analytics) in `try/except`. Never let a failed log write break the main pipeline.
- **`supabase/migrations/` must contain only `NNN_name.sql` files.** Never place `.md` files, smoke-test scripts, validation reports, or any non-migration artifacts in this directory. Supabase CLI and tooling will attempt to run every `.sql` file in this directory as a migration — a misplaced file will cause schema errors or no-op runs. If a migration agent produces a smoke-test or verification file alongside the SQL, place it anywhere outside `supabase/` (e.g. a temp directory or delete it). Example incident: `027_smoke_test.sql`, `027_VALIDATION.md`, `027_VERIFICATION_REPORT.md` were accidentally created in `migrations/` by a previous agent and had to be manually deleted (commit `chore(migrations): remove non-migration 027 artifacts`).
- **PostgREST COUNT は必ず `{ count: 'exact', head: true }` を使う。** `.limit(n)` + client-side filter でカウントを計算すると PostgREST の `max-rows=1000` silent truncation により 1,000 件超で常に過小表示になる。カウントのみ必要な場合は行データを取得しない head-count クエリを使う：
  ```ts
  // ❌ client-side count — PostgREST silently truncates at 1000
  const { data } = await supabase.from("events").select("id").eq("is_active", true);
  const count = data?.length ?? 0;

  // ✅ head-count — 正確な COUNT、行データ不要
  const { count } = await supabase
    .from("events")
    .select("id", { count: "exact", head: true })
    .eq("is_active", true);
  ```
  複数の COUNT クエリは `Promise.all([...])` で並列実行すること（直列 await は不要）。Reference incident: AEO summary cards capped at 1,000 (commit `518b5a8`, 2026-05-15).
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
- **Admin が UPDATE/DELETE するテーブルには SELECT だけでなく全 DML の RLS policy を migration 時に一括作成する。** `CREATE TABLE` 時に SELECT policy のみ追加し UPDATE policy を漏らすと、admin UI からの更新が PostgREST により 0-row silent success として返り、JS 側では `error: null` なので原因特定が困難になる。チェックリスト（admin 操作テーブル）：`SELECT` / `INSERT` / `UPDATE` / `DELETE` の 4 種 policy を全て作成したか確認すること。参照インシデント：`research_reports` が UPDATE policy なしのため「標記為已審閱」ボタンが無反応（migration `070`、2026-05-15）。

## Supabase Client UPDATE — 0-row Silent Success Guard

任何 **client-side** `supabase.from(T).update(...).eq("id", x)` 在以下三種情況都會回傳 `error: null` + 空 `data`，supabase-js **不會丟錯**：

1. RLS policy 過濾掉（角色不對、anon 落地）
2. JWT expired，supabase-js 來不及自動 refresh
3. `id` 在 DB 不存在

三者透過 `error` 無法區分。Vercel 滾動部署期間 access token 短暫失效正是情境 (2)，曾於 2026-05-15 在 production 同時打掉 toggle / work 指派 / AI 報錯 checkbox 三個入口。

**規則：** 後台所有 client-side UPDATE 必須加 `.select("id")` 並檢查回傳列數，0 列視為失敗：

```ts
const { error, data } = await supabase
  .from("events")
  .update(update)
  .eq("id", eventId)
  .select("id");

if (error) {
  alert(`操作失敗：${error.message}`);
} else if (!data || data.length === 0) {
  alert("操作未生效（session 可能已過期），請重新整理頁面後再試。");
} else {
  // success path
}
```

**已知需套用的呼叫點（截至 2026-05-15）：**
- `web/components/IsActiveToggle.tsx` `handleToggle`
- `web/components/AdminEditClient.tsx` `handleSave`
- `web/components/AdminEventTable.tsx` `handleToggleActive` / `handleBulkToggleActive` / `handleBulkForceRescrape` / category bulk update / `handleSaveWork`
- `web/components/AdminCreatorsClient.tsx` `toggleActive`
- `web/components/AdminReportsTable.tsx` 所有 bulk-confirm 路徑

替代設計：高風險寫入改走 server action / route handler 用 service role key，繞過 client JWT 過期問題。

## RLS Policy Matrix Completeness Guard（建表時 SELECT/INSERT/UPDATE/DELETE 缺一即 silent failure）

任何含 admin 後台 UPDATE/DELETE 入口的表，建表 migration 必須**同時建立**對應的 RLS policy。缺失任一動詞的 policy，PostgREST 會靜默拒絕（0 rows affected，`error: null`），符合「0-row Silent Success」模式——前端看不出來，DB log 也只是普通 RLS deny。

**規則：** 設計新表 migration 時，逐一檢查 admin UI 是否會對該表執行：

| 動詞 | 觸發場景 | 必要 policy |
|------|---------|-------------|
| SELECT | 列表頁、詳情頁 | `FOR SELECT` |
| INSERT | 新增按鈕、表單送出 | `FOR INSERT` |
| UPDATE | 「標記為…」按鈕、toggle、編輯 | `FOR UPDATE` |
| DELETE | 「刪除」按鈕 | `FOR DELETE` |

任一動詞會被 admin UI 觸發但 policy 不存在 → 後續一定要回頭補一支 migration（如 `070_research_reports_update_policy.sql`）。

**已知 incident：** Migration `008_research_reports.sql` 只建 SELECT policy，admin「標記為已審閱」按鈕 silent failure（2026-05-15 補 migration `070`）。

**偵測 SQL（在 Supabase Dashboard 跑）：**
```sql
SELECT tablename, cmd, count(*)
FROM pg_policies
WHERE schemaname = 'public'
GROUP BY tablename, cmd
ORDER BY tablename, cmd;
-- 任何 admin UI 操作的表，cmd 必須涵蓋 SELECT + UPDATE 至少。
```

## Admin Mutation 成對原則（confirm / dismiss / toggle）

**admin mutation handler は必ずペアで同じ実装パターンを使う。**

`confirmReport` が server action ならば `dismissReport` も server action でなければならない。片方だけ昇格させると、残った方が 0-row silent success トラップに落ちる（2026-05-15 `handleDismiss` 事例）。

**チェックリスト（新規 admin mutation を追加する前に確認）：**
1. 同じテーブル・同じ権限を必要とする配対 handler が他にないか？
2. 配対 handler が client-side UPDATE のままなら、同時に server action へ昇格させる。
3. server action は `.select("id")` + `data.length === 0` guard + `return { ok: false, error }` パターンを必ず含める。
4. client-side handler は `result.ok` を確認し、false の場合 `alert(result.error)` で即時フィードバックを表示する。

```ts
// web/app/actions/dismiss-report.ts — server action テンプレート
"use server";
import { createClient } from "@/lib/supabase/server";
export async function dismissReport(reportId: string): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();
  const { error, data } = await supabase
    .from("event_reports")
    .update({ status: "dismissed" })
    .eq("id", reportId)
    .select("id");
  if (error) return { ok: false, error: error.message };
  if (!data || data.length === 0) return { ok: false, error: "0 rows updated" };
  return { ok: true };
}
```

## URL 存在確認 — apex と www の両方を試す

会場・組織の公式サイト有無を `curl` で確認する際は **apex ドメインと `www.` サブドメインの両方**を必ず試すこと。

```bash
# ❌ apex のみ確認 — 日本サイトは www なしを DNS に登録しないことが多い
curl -s --max-time 5 -o /dev/null -w "%{http_code}" "https://example.jp/"   # → 000 (DNS 失敗)

# ✅ 両方確認
curl -s --max-time 5 -o /dev/null -w "%{http_code}" "https://example.jp/"     # 000
curl -s --max-time 5 -o /dev/null -w "%{http_code}" "https://www.example.jp/" # 200 ← 正解
```

- `000` = curl が DNS 解決に失敗した = 「その変形が存在しない」であり「サイト全体が存在しない」ではない
- `2xx` が返るまで apex / www / 短縮ドメインを試し、すべて失敗した場合のみ「公式サイトなし」と判断する
- 参照インシデント: `coconeri.jp` → `000`、`www.coconeri.jp` → `200`（2026-05-17、event `eeb5b12e`）

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

**出版來源の追加規則：**
- `ndl_opensearch` / `hanmoto` / `kawade_rss` は `scraper/annotator.py::_PUBLICATION_SOURCES` と source SKILL の出版模板規則を同時に同期する。片方だけ更新すると「規範有、程式碼漏」が再発する。
- 出版來源の error backlog は source-scoped one-off で reset する。`eslite_spectrum` は混合來源なので同じ batch に混ぜない。
- reset 対象は `is_active=true` かつ `annotation_status='error'` を基本にし、`field_corrections` が 1 件でもあるイベントは丸ごと skip する。人工修正済みイベントを再注入しないため。
- batch 実行前に live DB が migration `047_add_broadcast_event_form.sql` を反映済みか確認する。未反映だと `event_form=['publication']` の書き戻しが `events_event_form_check` で失敗する。
- publication 系の修正で `event_form` を追加・強制する場合は、同じ変更で 4 箇所を同期する: Supabase constraint / migration、`scraper/annotator.py`（`VALID_EVENT_FORMS` と source-specific overwrite）、`web/lib/types.ts` の `EVENT_FORMS`、`web/messages/*.json` の `eventForm` namespace。どれか 1 つ欠けると `23514` constraint error か raw key 表示になる。
- publication batch の完了判定は `annotation_status` だけでは不十分。対象 source の active rows が期待する `event_form` に収斂していることを DB query で確認し、前台で raw key が出ないところまで確認する。

**注意事項：**
- `daily_report.py` は `.limit(5)` でエラー件数を表示するため、実際の件数と一致しない。COUNT で別途確認すること。
- 薄い `raw_description`（1行のみ）の sub-event も、親イベントのコンテキストを参照することで正常アノテーション可能。
- error 件数が多い場合は `annotator.py` の GPT JSON パースロジックに問題がある可能性もある（レスポンス形式の変化等）。

## Async Fetch AbortSignal Timeout Guard（UI 永久 loading 防護）

後台任何「觸發外部 API + 等待結果 + 更新 UI 狀態」的 client-side fetch **必須**加 `signal: AbortSignal.timeout(N)` 防護：

**問題場景：** `fetch("/api/admin/annotate-event", ...)` 無 AbortSignal → Vercel function 被 gateway 截斷時（504 但無正常 HTTP 回應），`await fetch()` 永遠 pending → `setAnnotating(false)` 不執行 → UI 卡在「標注中，請稍候…」。

**規則：**
```ts
// client-side：呼叫可能耗時 >5s 的 API 一律加 AbortSignal
const res = await fetch("/api/admin/annotate-event", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ eventId }),
  signal: AbortSignal.timeout(58000), // 58s hard cap
});

// API route 端：外部 AI API（OpenAI 等）也必須加 timeout
const openaiRes = await fetch("https://api.openai.com/v1/chat/completions", {
  ...
  signal: AbortSignal.timeout(25000), // 防止超過 Vercel maxDuration
});
```

**已修復（commit `77fc092`，2026-05-15）：**
- `AdminEventTable.tsx` `handleSaveAndAnnotate` 的 annotate-event fetch
- `annotate-event/route.ts` OpenAI call
- `AdminEventTable.tsx` `handlePublish` 補 `.select("id")` + 0-row guard

## React busy timer reset rule

Client component 如果要顯示 save / extract / annotate 的 elapsed 秒數，`useEffect` 只能負責 timer 的啟停與 cleanup，不要在 effect body 內同步呼叫 `setState` 做 reset。React 19 lint 會以 `react-hooks/set-state-in-effect` 直接報錯。

**Rules:**
- 將 `setBusyElapsedMs(0)` 這類 reset 與 `busyStartedAtRef.current = Date.now()` 放在事件入口，例如 `handleSave`、`handleImageExtract`、`beginPrimaryAction`。
- `useEffect` 只做三件事：判斷 timer 是否需要運行、掛上 `setInterval`、在 cleanup 清除 interval。
- busy 結束時可以清空 ref；若 UI 需要下一次從 `0s` 開始，應在下一次 action 開始時設定，不要在 effect 的 idle branch 內 reset。

Reference incident: 2026-06-04 `OwnerCreateClient.tsx` targeted lint FAIL.

## Client Component 直接 INSERT 禁止 — Server Action 義務化

**Client Component 内で `supabase.from(...).insert()` を直接呼び出してはならない（admin・一般ユーザー問わず）。**

ブラウザ→PostgREST のリクエストがネットワークレベルでハングすると、`await` は永遠に pending → `try/catch` は発動しない（thrown error ではなく hanging fetch のため） → `setStatus("error")` が呼ばれない → ボタンが loading 状態で固まる（2026-05-15 `ReportSection` commit `53445be`、2026-05-20 `AdminEventTable` Safari hang）。

**規則：**
- ユーザー向けフォームの INSERT（anon・authenticated 問わず）は必ず Server Action で行う。
- RLS で `anon INSERT` を許可していても、ブラウザ直接 INSERT はハング耐性がない。
- **Safari は特に hang しやすい**。Chrome で動いても Safari で再現する。

**暫定防護（Server Action 化が間に合わないとき）：** `withClientTimeout(promise, ms, label)` helper で `supabase.from(...).insert/.update()` を包む。Promise.race + setTimeout で hard cap reject → catch 分岐が必ず発動 → `setSaving(false)` 復帰。
- insert：20 秒
- update（軽い）：15 秒
- bulk handlers + works fetch 等、Server Action 化が未完了の path 用の保底メカニズム。

**完了済み Server Action 化（2026-05-22 commit）：** `web/components/AdminEventTable.tsx` の `handleSaveNew` / `handleSaveAndAnnotate` / `handlePublish` は `@/app/actions/admin-events.ts` の `createEventNoAnnotate` / `createDraftEvent` / `publishEvent` を呼び出す。共通 admin 認証は `@/app/actions/_shared/admin-guard.ts` (`requireAdmin()`)。`withClientTimeout` ラップは defense-in-depth として保持。

**残存技術債（同 file 内 7+ 處）：** `AdminEventTable.tsx` の bulk handlers（`handleBulkToggleActive` / `handleBulkForceRescrape` / `handleBulkRemoveCategory` / `handleBulkAssignWork` / `handleBulkAddCategory`）と単列 toggle（`force_rescrape` / `is_active`）はまだ client-side `supabase.from("events").update()` を使用。Safari hang が再発したら同 pattern で Server Action 化する。

```ts
function withClientTimeout<T>(p: PromiseLike<T>, ms: number, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms);
    Promise.resolve(p).then(
      (v) => { clearTimeout(timer); resolve(v); },
      (e) => { clearTimeout(timer); reject(e); },
    );
  });
}
```

## annotate-event SELECT 紀律（ユーザー入力欄を守る）

`web/app/api/admin/annotate-event/route.ts` は **「OCR 已填值は保持、空欄のみ GPT 補完」** パターン：
```ts
const cur = (event as Record<string, unknown>)[k];
if (cur === null || cur === undefined || cur === "") {
  returnedFields[k] = v;  // GPT 値で上書き
}
```

**これは SELECT 句で fetch したフィールドにしか効かない**。SELECT 漏れ ＝ `undefined` ＝ 空判定 ＝ サイレント上書き。

**規則：**
1. `extractionFields` 配列に列挙したフィールドは **すべて L258 の SELECT 句に含める**。
2. 新規「保持したい」フィールドを追加するときは 3 箇所同時編集：
   - L258 SELECT 句
   - `extractionFields` 配列（L437 付近）
   - 必要なら `alwaysOverwriteFields`（description 系のみ）
3. PR レビュー時：`extractionFields` の各 key が SELECT 句にあるか目視確認。

**Reference incident:** 2026-05-20 — `end_date` が `extractionFields` にあるのに SELECT に無く、ユーザーが画面で選択した `end_date` が毎回 GPT 幻覚（例：`2023-10-14`）で上書きされていた（commit `e0a5ea8`）。
- Server Action はネットワークハング時も Next.js が適切なエラーレスポンスを返すため `catch` ブロックが確実に発動する。

```ts
// ❌ Client Component での直接 INSERT — ハング時に永久 loading
const supabase = createClient(); // browser client
const { error } = await supabase.from("event_reports").insert({ ... }); // may hang silently

// ✅ Server Action 経由 INSERT — ハング耐性あり
const result = await submitReport({ eventId, reportTypes, locale, suggestedCategory });
if (!result.ok) { setStatus("error"); return; }
```

**参照：** `web/app/actions/submit-report.ts`（user-facing）、`web/app/actions/dismiss-report.ts`（admin）

---

## Auth — ブラウザ `SIGNED_OUT` を単独の真実源にしない / route handler `<Link>` の prefetch 副作用（2026-06-03 教訓）

ログイン状態を扱う Client Component（`Navbar` など）の二大落とし穴。両方とも「ログイン直後に勝手にログアウトされる」症状を出す。

**① `onAuthStateChange` の `SIGNED_OUT` を信用しない — 必ずサーバで再検証する。**
Supabase SSR では `proxy.ts`（middleware）・`/api/me`・ブラウザ client が同じ refresh token をほぼ同時にローテーション要求する。token rotation 有効環境ではレースの敗者が `Invalid Refresh Token` を受け取り、ブラウザ client が**偽の `SIGNED_OUT`** を発火する。このときサーバ session はまだ有効なので、`SIGNED_OUT` で無条件に `setUser(null)` するとログイン直後に未ログイン表示へ戻る（フリッカー）。

```tsx
// ❌ ブラウザ client のイベント種別を真実源にする — 偽 SIGNED_OUT でログアウト化
supabase.auth.onAuthStateChange((event) => {
  if (event === "SIGNED_OUT") { setUser(null); return; }
  void loadMe();
});

// ✅ 常にサーバ (/api/me の getUser()) を真実源として再検証し、
//    サーバが user なしと返したときのみクリアする
supabase.auth.onAuthStateChange(() => { void loadMe(); });
// loadMe() は fetch("/api/me", { cache: "no-store" }) → setUser(data?.user ?? null)
```

**② `<Link>` が route handler（副作用を伴う GET）を指す場合は必ず `prefetch={false}`。**
Next.js の `<Link>` はホバーで対象 URL を prefetch する。対象が route handler だと**実 GET が飛ぶ**。ログアウトリンク（`/auth/logout` → `supabase.auth.signOut()`）を `<Link>` で置くと、メニュー内で隣の項目へマウスを動かしただけでホバー prefetch が `signOut()` を実行し、ユーザーが勝手にログアウトする。

- ログアウト等、副作用を伴う route handler への `<Link>` には `prefetch={false}` 必須。
- 受保護ルート（`/saved`・`/account` 等）への `<Link>` も prefetch が login へ redirect されるため `prefetch={false}` が安全。
- クライアント側ロジックでナビゲートする項目（権限分岐など）は `<Link>` ではなく `<button onClick>` にして prefetch 自体を発生させない。

Reference incident: `Navbar` auth flicker + hover logout（2026-06-03 commit `c4e1bde`）.

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

**規則：** 任何 Admin 頁面的 save / confirm handler，只要後面接 `router.push()`，一律在其前加 `router.refresh()`。這是 Next.js App Router 的必要模式，不是 optional 優化。

**⚠️ 逆に stay-on-page handler（`router.push()` を伴わない dismiss / toggle など）では `router.refresh()` を呼ばない。** `router.refresh()` が RSC 再レンダリングをトリガーし、Realtime `UPDATE` イベントと同時着火することで state/render race → 画面破損が起きる（2026-05-15 `handleDismiss` commit `390826a`）。ローカル state（`setReports()`）と Realtime 購読で十分。

| ハンドラータイプ | `router.refresh()` | 理由 |
|---|---|---|
| confirm（event fields 変更 → `router.push()` あり） | ✅ 必要 | SSR キャッシュ無効化が必要 |
| dismiss（report status のみ変更、stay-on-page） | ❌ 不要・禁止 | Realtime と RSC re-render が競合し画面破損 |

## Python
- When changing a function's return type (e.g. `dict` → `tuple`), immediately smoke-test before committing: `python -c "from module import fn; print(type(fn(...)))"`
- Use `getattr(obj, 'attr', default)` when reading an attribute that may not exist on all subclasses.
- **Pipeline parity rule:** Any post-processing step added to CI workflow (`scraper.yml`) must also be called in `main.py`'s normal (non-dry-run) flow. Otherwise manual scraper runs produce incomplete results. Current full pipeline in `main.py`: scrape → merger → annotate → `enrich_movie_titles()` → `enrich_person_names()` → IndexNow. Enrich functions are idempotent — double execution (main.py + CI) is safe (just extra DB queries). When adding a new enrichment function: (1) add to `main.py` after `annotate_pending_events()`; (2) add CLI flag + step to `scraper.yml`.
- **Inline Python safety rule — Prompt Injection:** Never use `python3 -c "..."` or heredoc `python3 << 'PY' ... PY` for scripts that **interpolate DB values** (e.g. f-strings over `field_corrections.corrected_value`, event fields, or any user-supplied text). Two attack vectors: (1) shell history pollution injects code into f-string braces; (2) **DB data itself can contain injected shell commands** — rows in `field_corrections` or other tables may embed `rm -f ...` or similar, which then appear inside `{...}` braces and corrupt the inline script. **Rule:** Always use `create_file /tmp/<name>.py` + `python3 /tmp/<name>.py` for any script that queries the DB and formats results with f-strings. File-based execution is fully isolated from the shell. If SyntaxError points at a `{` in `-c` mode, treat it as a **prompt injection alert** and switch to file mode immediately.
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
- **Server Component から client module の純関数を呼ばない:** `"use client"` file exports belong to the client module graph. If a Server Component needs a parser, filter builder, or URL state helper, put the type/function in a server-safe `web/lib/*.ts` module and import only client components/hooks from the client file. Do not add compatibility re-exports from client context modules. Reference incident: 2026-06-03 homepage `buildInitialFilters()` render error.
- Never set `autoInstrumentServerFunctions: false` — it silently disables server-side error capture.
- Gate source map upload: `sourcemaps: { disable: !process.env.SENTRY_AUTH_TOKEN }`.

## API Route JSON Safety Guard（Safari SyntaxError 防護）

**所有 API route POST handler 必須用 try/catch 包整個函式體，確保任何情況下都回傳 JSON。**

Safari 的 `fetch().then(r => r.json())` 遇到非 JSON 回應（如原始 HTML error page）直接拋 `SyntaxError: The string did not match the expected pattern.`；Chrome 在同樣情況下靜默失敗。不包 try/catch 的 route 在 uncaught exception 時回傳 HTML 500，Safari 用戶看到崩潰，Chrome 用戶靜默無感——跨瀏覽器行為完全不同，難以 debug。

```ts
// ❌ 未包 try/catch — uncaught exception 回傳 HTML, Safari 拋 SyntaxError
export async function POST(request: Request) {
  const data = await request.formData(); // 若此行拋例外 → 回傳 HTML 500
  return NextResponse.json({ url: "..." });
}

// ✅ 包整個函式體
export async function POST(request: Request) {
  try {
    const data = await request.formData();
    // … all logic …
    return NextResponse.json({ url: "..." });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Server error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
```

**配套規則：**
- **File extension 必須消毒**：從 user-uploaded filename 取副檔名前必須過濾特殊字元，防止破壞 Supabase storage path：
  ```ts
  const rawExt = file.name.split(".").pop() ?? "jpg";
  const ext = rawExt.replace(/[^a-zA-Z0-9]/g, "").slice(0, 10) || "jpg";
  ```
- **Client side fallback**：`const json = await res.json().catch(() => ({ error: "Upload failed (server error)" }))` — 防止 non-JSON 500 在 client 端拋 SyntaxError。
- **`SUPABASE_SERVICE_ROLE_KEY` 必須顯式 guard**：若依賴 service role 的 route 缺 key，要回傳明確錯誤訊息而非 undefined 引爆 TypeError：
  ```ts
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!serviceKey) return NextResponse.json({ error: "Server misconfiguration: storage key not set" }, { status: 500 });
  ```

Reference incident: 2026-05-31 — `web/app/api/upload/route.ts` 未包 try/catch + extension 未消毒，Safari 上傳圖片全失敗；Chrome 無感（commit `616eecc`）。

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
| `performers[]` | `TEXT[]` | **日本語（カタカナ）多人陣列**；日本語ソースページのキャスト表記を使用；`performers_zh[]` は繁体字対応 |
| `performers_zh[]` | `TEXT[]` | performers の繁体字対応；`getEventPerformer(event,'zh')` が参照する |
| `performers_en[]` | `TEXT[]` | performers の英語対応；`getEventPerformer(event,'en')` が参照する |

**⚠ 絕不可刪除 `performer`**：`performer_zh/en` 錨定於它；34+ 處程式碼引用它；`performers[]` 有多人時翻譯欄位才有意義。

**Auto-sync 規則（commit `4526d3a`）**：annotator 滿足以下四個條件時自動設 `performers = [performer]`：
1. 本次 pass 設定了 `performer`
2. 現有 `performers[]` 為空/null
3. GPT 本次未回傳 `performers` 陣列
4. `performers` 未在 `field_corrections` 保護中

此機制確保 UI 永遠能從 `performers[]` 讀取，不需在前端 fallback 回 `performer`。

**performers[] 言語規則**：`performers[]` は必ず**日本語（カタカナ）**で入力する。繁体字 film DB・works.cast_summary から補完したデータは `performers_zh[]` に入れること。日本語の映画サイト・劇場サイトのキャスト欄（例：`出演：ケイトリン・ファン、ウィル・オー、9m88...`）が権威ソース。繁体字が `performers[]` に混入すると日本語ロケールで漢字が表示される（incident: 霧のごとく 11 件, 2026-05-20）。

**performer multi-value 淨化規則（commit `c4bd9e1`）**：`performer` 字段必須是單一人物名。annotator 輸出 `performer` 時必須經過 `_MULTI_SEP_RE`（`[、,，×／/]`）檢查：
- 包含區切符 → `performers[]` に分割し、`performer / performer_zh / performer_en` を `None` にクリア
- `enrich_person_names()` の B1 策略が `performers[]` の各名前を `ja_to_info` で翻訳 → `performers_zh/performers_en` を生成
- 既存汚染 DB の一括移行は `_oneoff_migrate_multi_performer.py --execute` で実行する（`--dry-run` で事前確認）

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

**OCR-回填 array 欄位 sync rule:** `handleExtractFromImage` 的 `ARRAY_FIELDS = new Set([...])` 必須涵蓋**所有** OCR Vision prompt 會回傳的陣列欄位。未列入集合的 array 會走 `String(val)` 分支被強轉成字串，**污染 form state**（型別變成字串而非 `string[] | null`），但 TypeScript 不會報錯（`updateField` 接 `unknown`）。新增任何 array OCR 欄位時，這四處必須同 commit 同步：
1. `web/app/api/admin/extract-from-image/route.ts` Vision prompt 加欄位定義（含視覺位置提示，如「海報底部 credit block」）
2. `web/components/AdminEventTable.tsx` `ARRAY_FIELDS` 集合擴增該欄位 key
3. `web/lib/types.ts` Event interface 欄位定義為 `string[] | null`
4. `web/components/AdminEventForm.tsx` 表單 state 初始值（避免新增欄位卻無 input UI）

Reference incident: 2026-05-26 — `co_organizers` / `sponsors` 三路徑 sync 同時補齊（commits `280fdc4` + `e54b925`）。

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
- **Annotator business-hours pre-extraction:** `_extract_hours_from_raw()` runs before GPT and before localized `business_hours_*` output. If raw text contains multiple explicit `M月D日 HH:MM-HH:MM` pairs across distinct days, preserve them as date-labelled multiline `business_hours` instead of returning the first bare time range. Bare single-range output is only safe when the hours apply uniformly to the whole event.
- **Structured `raw_description` extraction — prioritize content blocks over enumeration:** Detail pages often contain navigation noise (navigation links, footers, breadcrumbs). Never enumerate `<p>` tags or slice first N elements to populate `raw_description`. Instead: (1) identify structural blocks (e.g., `<table class="theater-detail">`, `<div class="detail-root">`, or semantic headers) that contain event metadata, (2) extract each block as a labeled section (e.g., `"作品紹介: ..."`, `"料金: ..."`, `"公式サイト: <url>"`), (3) join with `\n\n`. This ensures annotator receives clean context rather than noisy text, preventing misclassification. Incident (2026-05-15): `kawasaki_ac` extracted first 8 `<p>` tags (mostly navigation), caused GPT to reject valid Taiwan film events as "unrelated".
- **Address conflict pre-flight normalization (2026-06-02):** Any scraper/oneoff logic that compares street numbers using regex (for example `\d+(?:-\d+)+`) must normalize Unicode minus variants before matching. Minimum required transform: `"−" -> "-"` inside address normalization. Without this, `venues` pre-flight conflict checks can report false positives for the same location written with `U+2212` in one source and ASCII hyphen in another.
- **Series-type scraper pattern — coordinate date format support with field extraction:** When expanding a scraper's date parsing to support new formats (e.g., adding `YYYY年M/D(土)～` support), **simultaneously** audit all related field extraction (pricing, times, location, organizer). Series-type sources often embed metadata in structured page sections (cinema event blocks, performance program tables) that depend on date parsing success to identify the correct block. If date parsing changes but pricing/times extraction doesn't, you risk incomplete or misaligned records. Pattern from `kawasaki_ac` (2026-05-15): supporting new date formats required also upgrading `raw_description` structure and extraction of `business_hours`, `price_info`, and `official_url` from the same detail page. Rule: **When modifying a scraper's date logic, assume you must also update 3-5 other fields in the same commit.**
- **selection_reason is documentation, not a gate:** The `selection_reason` field records why an event was annotated (e.g., "Taiwan-related" vs "not selected"). It is **not** an enforcement mechanism. Three dangers: (1) a negative `selection_reason` written by annotator does NOT set `is_active=false` automatically, (2) upstream layers cannot rely on `selection_reason` to exclude bad data from downstream, (3) contradictions (e.g., `is_active=true` with `selection_reason="not selected"`) silently propagate. To enforce exclusions, either: (a) have the scraper skip bad records entirely (preferred), (b) have annotator explicitly set `is_active=false` when rejecting, or (c) add consistency checks in DB with a `CHECK` constraint on `(is_active, selection_reason)` pairs. Do not rely on `selection_reason` text alone.
- **New scraper checklist — all 4 steps required:**
  1. Create `scraper/sources/<name>.py` extending `BaseScraper`
  2. Register in `scraper/main.py` → `SCRAPERS` (import + add instance)
  3. **Insert a row in `research_sources`** with `status='implemented'`, `scraper_source_name=<key>`, and a valid `url`. Skipping this causes `researcher.py` to re-report the source as a new candidate and triggers a `⚠️ WARNING` in CI logs every day.
  4. Validate: `python main.py --dry-run --source <key>` returns events cleanly
- `_warn_unregistered_scrapers()` in `main.py` runs on every non-dry-run and emits a WARNING for any scraper key missing from `research_sources`. Check CI logs if you see `⚠️ scraper(s) NOT registered`.
- **Auto-QA via `event_reports` queue (2026-05-01):** New automated content-quality checks must write findings into `event_reports` with an `auto_*` prefix in `report_types[]` (e.g. `auto_qa_simplified_zh`, `auto_qa_missing_address`). Do NOT build a separate admin queue — the existing `/admin/reports` confirm/dismiss flow handles auto-findings unchanged. Always dedup against existing rows of the same `auto_*` type per `event_id` — check **ALL statuses** (`pending`, `confirmed`, `dismissed`), not just `pending`. A confirmed/dismissed report means the admin has already reviewed it; re-creating it undoes admin work. Also dedup within a single run via in-memory set. See `scraper/auto_qa.py` and engineer `history.md` 2026-05-01 / 2026-05-05.
  Current `QA_TYPES` (as of 2026-06-03): `auto_qa_simplified_zh`, `auto_qa_missing_address`, `auto_qa_missing_hours`, `auto_simplified_chinese`, `auto_qa_same_work_duplicate`, `auto_qa_performer_ai_translation_marker`, `auto_qa_performer_multi_value_pollution`, `auto_qa_performer_zh_equals_katakana`, `auto_qa_location_url_is_event_url`.
- **Admin dashboard count — use `head=True` queries (2026-05-15, commit `518b5a8`):** Any summary/count card in admin pages must use `.select('id', count='exact', head=True)` rather than fetching rows and counting client-side. PostgREST silently truncates at `max-rows=1000` regardless of `.limit()` — client-side count is always wrong for large tables. The `head: true` option fetches only the `Content-Range` header with the total count, returning no rows.
- **`SIMP_RE` / `SC_ONLY` / `annotator._SIMP_TO_TRAD` char addition rule (2026-05-01, updated 2026-05-11):** Only add a char when its Traditional Chinese / Japanese form is **a different glyph**. Verify each candidate via CC-CEDICT or kanji.jitenon.jp **before** adding. Counter-example: `亮` is identical in Trad/Simp (`照亮` is valid Trad) and triggered a false positive in production. When adding a new char, update **all three** simultaneously: `annotator.py._SIMP_TO_TRAD`, `auto_qa.py.SIMP_RE`, and `auto_qa.py.SC_ONLY`. Ensure `SC_ONLY ⊆ _SIMP_TO_TRAD_RAW.keys()` — detection must never find chars that fix cannot convert. See scraper-expert `history.md` 2026-05-01 and engineer `history.md` 2026-05-11.
- **Cron-driven slot rotation modulo wrap (2026-05-01):** When N weekdays drive a `(DAY-1) % M` slot selector with `M < N`, days M+1..N silently re-run slots 0..(N-M-1). Acceptable when slots are idempotent (search + `skip_hint` dedup); NOT acceptable for slots requiring fixed cadence (e.g. Peatix slot 3 only on Thursdays). Override via `DISCOVERY_SLOT` env on extra cron entries, or raise `SLOT_COUNT`. See `discovery-accounts.yml` and engineer `history.md` 2026-05-01.
- **Body article > sidebar/footer widget rule (2026-05-22):** When a single-source homepage shows the same event in multiple places (e.g. main `<article>` body **and** a footer/sidebar widget), always parse the **body article first** and fall back to the widget only if missing. Widgets are common "set once, forgotten on update" traps — main article is where editors focus. When both parse successfully and disagree, log a warning and prefer the body. Pattern: `_parse_body_article()` + `_parse_widget()` → `chosen = body or widget`. Date regex must support year-prefixed format (`(20\d{2})年(\d{1,2})月(\d{1,2})日.*?～(?:(\d{1,2})月)?(\d{1,2})日`). Incident: `taiwan_festival_tokyo` (event `80214e50`) was stuck on widget's stale 6/25–28 dates while main article said 7/9–7/12.
- **Multi-city tour detection — never hardcode venue address (2026-05-01):** Any scraper with a hardcoded `location_address` must add multi-city detection logic. Pattern for `taiwan_cultural_center.py`:
  - Check `description + name` for ≥2 regional keywords (`_MULTI_CITY_REGIONS = ["北海道", "大阪", "京都", "神奈川", "福岡", "名古屋", "仙台"]`)
  - Threshold = **2** (not 1) to avoid false positives where a Tokyo event's description merely mentions another city
  - When triggered: set `location_name` to a generic tour label (e.g. `台湾文化センター（全国巡回）`) and set `location_address = None`
  - For DB-patching already-scraped tours: update `location_name`, clear `location_address` directly in Supabase

## Venue ground truth merge & DB schema gotchas

When consolidating duplicate venues onto an authoritative `venues` row (e.g. 誠品生活日本橋), follow this three-step merge and heed the schema traps:

1. **Fix the authoritative row first** — ensure `address` carries the prefecture prefix (`東京都…`); the venue-registry/annotator copies this verbatim into events.
2. **Add sub-venue names as `aliases`, but never generic names** — a hall/space name containing a clear venue identifier (`誠品生活日本橋 イベントスペース「FORUM」`) is safe to alias (include BOTH the half-width and full-width `\u3000` space variants). A **generic** name (`誠品書店`, bare `イベントスペース`) must NOT be aliased — it will false-match other branches/locations later; handle those events individually.
3. **Repoint events then delete orphans** — set `events.venue_id` to the authoritative id for all referencing events, re-verify `refs=0`, then delete the duplicate venue rows.

Schema gotchas (each caused a real PostgREST/SQL error):
- **`venues` has NO `name` column** — use `canonical_name_ja` / `canonical_name_zh` / `canonical_name_en`. Selecting/filtering `name` returns 400.
- **`events.id` is `uuid` — `.like('8-char-prefix%')` is invalid** (uuid columns reject pattern match). Either fetch rows and prefix-match in Python, or resolve full uuids first (e.g. via `venue_id`) then `.eq()`.
- **Fixing a noisy `location_*` base field requires clearing the localized mirror columns too** — `location_name_zh/en` and `location_address_zh/en` carry the same scraped noise; if you only fix the base, the front end still renders the localized noise per locale. Set the 4 localized columns to `NULL` so the front end falls back to the corrected base (matches existing sibling rows). When the base is FC-locked, the localized NULLs need no separate lock.

## Broadcast / Public Output Quality Gate

**Any public-facing output** (LINE weekly broadcast, RSS feeds, API responses, etc.) must exclude `annotation_status='pending'` events. Pending events have incomplete data (null `name_zh`/`name_en`, missing category, etc.) and will surface as Japanese-only or broken entries to end users.

**Rule:** All broadcast/feed queries must include `.in_("annotation_status", ["annotated", "reviewed"])` — do NOT assume all `is_active` events are fully annotated.

**Reference:** `weekly_line_broadcast.py` `_fetch_upcoming_events()` — pool filter added in commit `b2864ea` after pending events appeared with Japanese-only titles in the LINE weekly broadcast.

### weekly_line_broadcast URL placement rule

URLs belong **only in the `【小霧精選】` weekly picks section**. The nearterm (national-scope + prefecture-grouped) and monthly sections must NOT append `lines.append(f"  {url}")` — message length is the concern.

Checklist when editing `_build_message()`:
- `weekly_events` loop → URL line ✅ keep
- nearterm sections (national + prefecture) → URL line ❌ remove
- monthly loop → URL line ❌ remove

### weekly_line_broadcast — regenerate / overwrite an existing draft slug

`run_generate_draft()` has **no date parameter** — it always computes `send_date = now()+1day` and `slug = weekly-<send_date>`. To regenerate/overwrite a specific existing slug (e.g. re-render `weekly-2026-06-28` after DB fixes), write a `/tmp` oneoff that reuses the internals with a fixed date:
- `send_date = datetime(Y,M,D, tzinfo=JST)`; reuse `_generate_weekly_content(sb, ai, send_date)` + `_build_message(...)` for zh/ja/en; `upsert(on_conflict="slug")` then replace `announcement_events`.
- **Pre-flight: check `published_at` of that slug.** If it is non-NULL (already sent), DO NOT overwrite — the upsert resets `published_at=NULL`, re-arming it for a duplicate send. Only overwrite drafts that are still pending.
- The draft body is a **render-time snapshot**: fixing event rows in DB does NOT update an existing draft. You must regenerate to reflect name/location corrections.

### weekly_line_broadcast nearterm grouping model

The nearterm (今週・来週の全イベント) block uses a **two-tier layout** (重構 2026-06-28):
1. **National-scope sections pinned to top**, fixed order **books → online → TV** (no physical location).
2. **Prefecture groups** below — flat, date-sorted list under each `_city_label` heading; unknown-region (`地域未設定`) bucket always last.

Re-test these edge cases after ANY `_build_message()` change (empty groups must NOT leak headers):
- national-only (no prefecture) → no orphan `地域未設定`
- prefecture-only (no national) → no empty national-header leak
- empty nearterm list → no nearterm major-header leak
- spacing → exactly one blank line between sections, never `\n\n\n` (double blank)

### city_label diagnosis checklist

`_city_label()` returns empty when **both** of these are missing:
1. `location_prefectures` is `null`
2. `location_address` does not **contain** a prefecture name anywhere (matched via substring since 2026-06-28 — `会場は東京都渋谷区…` now matches `東京都`; `_TOKYO_EN_HINTS` also catches English `tokyo`)

Common cause: `location_address == location_name` (venue name written as address — caught by `auto_qa_address_is_venue_name`). Typical sub-patterns:
- Address is just the venue hall name with no prefecture string (e.g. `早稲田大学早稲田キャンパス11号館710教室`) → still a miss even with substring matching
- Online tokens (`オンライン/online/virtual`) in `location_name` **or** `location_address` route to the online label via `_is_online_event()`

**Fix**: look up the real street address, set `location_address = '東京都…'` and `location_prefectures = ['東京都']`, FC-lock both fields.

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

## Tailwind CSS Dark Mode — Semantic Tokens Rule

The app uses **class-based dark mode** (`html.dark` set by anti-flash script in `layout.tsx`). The `:root.dark` block in `globals.css` overrides all semantic token variables.

**Rule: Never use hardcoded hex for text/background colors in page components.**

| Use case | Correct class | Dark mode value |
|---|---|---|
| Headings (h1, h2) | `text-fg-strong` | `#fafafa` |
| Body paragraphs | `text-fg` | `#ededed` |
| Secondary text | `text-fg-muted` | `#a1a1aa` |
| Breadcrumb current | `text-fg-strong` | `#fafafa` |
| Page background | `bg-surface` | `#1f1f1f` |

**Do NOT use:**
- `text-[#3A261F]` (mocha brown — invisible on dark background)
- `text-[#4A362D]` (dark brown — invisible on dark background)
- `dark:text-xxx` variants — semantic tokens self-switch via `:root.dark`, no need for per-class dark variants

**`dark:` variants are still valid** for decorative colors not covered by semantic tokens (e.g. `dark:bg-zinc-800`).

Reference: `about/page.tsx` commit `8ab8d05` (2026-05-15).

---

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

**⚠️ performer 修正後 FC cleanup 必須：** `events` テーブルで `performer=null` にセットした後、同じ event_id の `field_corrections` に `performer` 行が残っていると、次回 annotator 実行時に悪い値が復元される。必ずセットで確認・削除すること：
```python
# FC performer lock が残っていれば削除
fc = sb.table('field_corrections').select('id,corrected_value').eq('event_id', eid).eq('field_name', 'performer').execute()
if fc.data:
    sb.table('field_corrections').delete().eq('event_id', eid).eq('field_name', 'performer').execute()
```
Reference incident: 2026-05-17 — `9084ad67` の `performer='阿仁、安和'` FC lock が残存し、events table 修正（null化）が次回 annotation で上書きされるリスクがあった。

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
