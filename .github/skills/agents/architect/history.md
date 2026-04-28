# Architect Error History

<!-- Append new entries at the top -->

---
## 2026-04-29 — Migration 027 驗證完成：5 步驗證套件建立與全綠測試

**工作內容：** 修復 migration 027 中 `admin_list_users()` RPC 的假拒絕問題後，建立完整的 5 步驗證套件並全部通過。

**驗證框架（4 象限 + 回傳型別）：**
1. ✅ Function exists — `pg_proc` 查詢確認定義存在
2. ✅ No auth context → 42501 — Empty claim 和無 auth.uid() 時正確拒絕
3. ✅ Admin user → success — Admin 用戶取得行數並順利查詢
4. ✅ Non-admin user → 42501 — 非 admin 用戶正確被拒
5. ✅ Return type validation — 所有 5 欄位（id, email, created_at, last_sign_in_at, role）型別正確

**驗證產物：**
- `027_smoke_test.sql` — 可執行的 5 步 SQL 套件，包含 temp table 重用邏輯
- `027_VALIDATION.md` — 步驟分解指引與預期結果
- `027_VERIFICATION_REPORT.md` — Executive summary 和 deployment checklist

**Lesson：** Supabase `SECURITY DEFINER` RPC 函式若涉及權限閘，驗證不能只做單點測試（app 或 SQL Editor），必須建立**四象限驗證矩陣**（app admin/non-admin, SQL Editor with claim/without claim）並配合回傳型別檢查。「all tests passed」報告應包含具體測試 ID 和通過時間戳，方便事後審計。

---
## 2026-04-29 — Cinema scrapers 官網提取：official_url selector 設計與 DB backfill 分離執行

**工作內容：** CineMarti Shinjuku 和 KS Cinema 的 scraper 中添加 official_url 抽取邏輯；識別出 Google search 結果用了不同 locale 的電影名稱。

**場景：** Cinema scraper 需要從官網電影詳頁面提取官方購票連結（official_url），以優先於一般 source_url 在前台顯示。

**修復：**
1. Selector pattern：`a[href*=".../ticket..."]` 或 `a[href*=".../purchase..."]` 的 link-text 和 href（驗證 URL domain 非跨域）
2. 選擇邏輯：優先選 Japanese locale 的電影標題 `name_ja`，而非使用者 `locale` 變數
3. DB backfill：在 scraper 新增欄位後，必須**立即執行一次手動檢查**，確認新抽取的 official_url 不是偽造 / 過期連結

**Lesson：** 
- Cinema 官網連結提取必須包含 domain whitelist（避免第三方票券販賣站）
- Google search 結果中的電影名稱取決於 search box locale，與用戶 locale 無關；務必優先使用 `name_ja`（日本官網）而非 locale 參數
- 新增欄位後不能依賴日後人工驗證；須立即執行 dry-run 並手檢前 5 筆

---
## 2026-04-29 — 8 個 Scraper 後補註冊：未登錄 SCRAPERS list 的源碼檔案大清查

**工作內容：** 發現 CineMarineScraper、EsliteSpectrumScraper、MoonRomanticScraper、MorcAsagayaScraper、ShinBungeizaScraper、SsffScraper、TaiwanFaasaiScraper、TokyoFilmexScraper 都有 `.py` 源碼但未在 `scraper/main.py` 的 `SCRAPERS` 列表中註冊。

**修復方法：** 在 `SCRAPERS = [...]` 列表中追加 8 個 scraper 類別；執行 `python main.py --dry-run` 驗證各源碼發揮應有的事件抽取數量。

**驗證結果：**
- CineMarineScraper (横浜シネマリン, id=56) — 1 件
- EsliteSpectrumScraper (誠品生活日本橋, id=46) — 2 件
- MoonRomanticScraper (Moon Romantic, id=48) — 1 件
- MorcAsagayaScraper (Morc阿佐ヶ谷, id=51) — 0 件（正常，查無當日台灣電影）
- ShinBungeizaScraper (新文芸坐, id=50) — 1 件
- SsffScraper (SSFF, id=58) — 6 件
- TaiwanFaasaiScraper (台湾發祭, id=57) — 1 件
- TokyoFilmexScraper (東京フィルメックス, id=59) — 0 件（正常，十月無影展）

**Lesson：** 定期檢查 `sources/` 目錄與 `SCRAPERS` list 是否同步。實施策略：每月執行 `find sources/ -name '*.py' -exec basename {} .py \;` 並與 list 對比，找出未登錄源碼。新增源碼後不應依賴 CI 自動發現；必須立刻檢查 dry-run 數量是否合理。

---
## 2026-04-29 — Admin Users 後台誤擋：`admin_list_users()` 在 web request 出現 false-deny

**錯誤：** 後台使用者頁面呼叫 RPC `admin_list_users()` 時回傳 `42501 admin privileges required`，但同一管理員帳號在 SQL Editor 測試可通過。

**根本原因：** 權限閘門一度只依賴 `request.jwt.claim.sub`。在 `SECURITY DEFINER` 與不同呼叫上下文下，claim 可用性和 app request 不一致，導致正式網站請求被誤判為非管理員。

**修復方法：** 新增 migration `027_admin_list_users_uid_fallback.sql`，將 gate 改為 `coalesce(auth.uid(), v_sub::uuid)`，優先使用 app request 的 `auth.uid()`，僅在 SQL Editor 模擬時 fallback 到 claim；保留 `42501` 與 admin role 檢查。

**Lesson：** 任何 Supabase `SECURITY DEFINER` 的 admin RPC，若需辨識目前登入者，必須以 `auth.uid()` 為主，claim 僅作測試 fallback，並以「app admin / app non-admin / SQL editor with claim / SQL editor without claim」四象限驗證。

---
## 2026-04-29 | 多語言修正 UI 設計不完整 | 只設計單語版本再補改 | 重寫為三語 textarea UI | 涉及多語欄位的修正 UI 必須一次設計成三語版

**錯誤：** 設計「選取理由不準確」報告審核 UI 時，第一版只做了單一 textarea，預填用戶提交的修正文字。
**根本原因：** `selection_reason` 是 JSON 格式，包含 `zh`/`en`/`ja` 三欄。單語 textarea 只能修改一個 locale，其他兩個 locale 的既有值會被靜默覆蓋或丟失。
**修復方法：** 重寫為 3 個 textarea（中文 / English / 日本語），各自從活動現有 `selection_reason` JSON 帶入預設值，用戶提交的修正文字優先覆蓋對應欄位，`confirm-report.ts` 接收 pre-built JSON 字串直接寫入。
**Lesson：** 任何涉及 `selection_reason`、`name_*`、`description_*` 等多語欄位的修正或輸入 UI，**必須一次設計成三語版（zh/en/ja）**，不能先做單語再補。

---
## 2026-04-29 — Supabase migration 執行錯誤：`REVOKE ... ON VIEW` 語法不被 PostgreSQL 接受
**錯誤：** 在 `024_security_advisor_auth_view_fix.sql` 執行時出現 `syntax error at or near "public"`，錯誤定位在：
`revoke all on view public.admin_users_view from anon, authenticated;`

**根本原因：** PostgreSQL `REVOKE` 對 view 物件使用 `ON TABLE` 語法，而不是 `ON VIEW`。

**修復方法：** 將語句改為：
`revoke all on table public.admin_users_view from anon, authenticated;`
並重新在 Supabase SQL Editor 執行 migration。

**Lesson：**
1. 在撰寫權限語句時，先以 PostgreSQL 語法為準，不要依直覺使用 `ON VIEW`。
2. Security Advisor 修復 migration 必須先做一次語法快檢，特別是 `GRANT/REVOKE/ALTER VIEW`。
3. 對於 Supabase SQL Editor 的報錯，優先依錯誤行數回到 migration 原文逐行比對，不要直接懷疑權限模型本身。

---
## 2026-04-28 — Agent handoff 功能實現：.prompt.md vs .agent.md 混淆
**錯誤：** 設計了兩個工作流（update-history 和 validate-deploy），創建了 `.prompt.md` 文件並在 6 個 agent 的 `handoffs:` 中引用，但 handoff 按鈕在 VS Code 中沒有出現。

**根本原因：** VS Code Copilot Chat 的 `handoffs:` frontmatter 中的 `agent:` 字段**必須指向 `.agent.md` 文件的 name**，不能指向 `.prompt.md` 文件。`.prompt.md` 文件是獨立的 `/` 命令任務，不是 agent。

**修復方法：**
1. 刪除 `.github/prompts/update-history-skill-agent.prompt.md` 和 `validate-merge-deploy.prompt.md`
2. 創建 `.github/agents/update-history-agent.agent.md` 和 `.github/agents/validate-merge-deploy.agent.md`
3. 設置 `user-invocable: false`（只通過 handoff 調用，不在 agent 選擇器中顯示）
4. 在 6 個主要 agent 的 handoff 中添加 `prompt:` 字段（預填中文指令）

**Lesson：**
1. **Custom agents 有三種引用方式**：
   - `.prompt.md` → 通過 `/` 命令或 `/prompts` 調用，獨立任務
   - `.agent.md` → 通過 agent 選擇器調用或作為 handoff 目標，持久化角色
   - Handoff 中的 `agent:` 只能指向 `.agent.md` 文件，不能指向 prompt

2. **Handoff 完整格式**：
   ```yaml
   handoffs:
     - label: "按鈕文字"
       agent: AgentNameFromFile
       prompt: "預填指令"
       send: false  # 可選，false=用戶點擊後需手動發送
       model: "Claude Sonnet 4.5 (copilot)"  # 可選
   ```

3. **工作流設計需考慮調用方式**：若需通過 handoff 按鈕一鍵調用，必須建立 `.agent.md`；若僅作偶發任務，`.prompt.md` 足夠。

---
## 2026-04-28 — Reviewed 活動缺翻譯：annotator 永久跳過 reviewed 狀態導致翻譯缺漏
**錯誤：** 11 個活動被標記為 `reviewed` 後，`name_zh` / `name_en` 仍為 NULL。後台顯示活動標題為空白，前台無法正確顯示語言版本。

**根本原因：** `annotator.py` 的 query 一律排除 `annotation_status = 'reviewed'`（line 276: `.neq("annotation_status", "reviewed")`），導致這些活動**永遠不會再被 AI 翻譯**，即使翻譯欄位是空的。

**修復（三層防護，Option C）：**
1. **DB 緊急修復**：把 11 筆缺漏活動改回 `pending`，手動執行 `python annotator.py`，完成後確認 0 筆缺漏。
2. **annotator.py `--fix-reviewed` 旗標**：新增模式，只查詢 `reviewed + name_zh/name_en IS NULL` 的活動，補齊翻譯欄位，完成後維持 `annotation_status = "reviewed"`（不降級，不覆蓋 category / 日期）。
3. **scraper.yml CI 步驟**：`python main.py` 之後加 `python annotator.py --fix-reviewed`，每日自動掃描修復。
4. **AdminEventTable 紅色徽章**：每列若 `name_zh` 或 `name_en` 為 NULL，顯示 `⚠ name_zh / name_en` 提醒管理員。

**Lesson：**
1. **設計 annotation_status 保護規則時，必須同時考慮「已 reviewed 但翻譯未完整」的邊界狀況**。
2. 事件審核前應確認所有關鍵翻譯欄位已填齊。
3. 規則已寫入 SKILL.md §Reviewed Event Translation Guard。

---
## 2026-04-28 — 翻譯大規模回歸：scraper commit 意外洗掉 web/messages
**錯誤：** commit `1d3cd1c`（標題：fix scraper expand taiwan_matsuri）在修改 scraper 的同時，把 `web/messages/zh/en/ja.json` 覆蓋成舊版快照，將之前四、五個翻譯 commit 的成果全部洗掉。受害清單：
- `categories` 遺失：`competition`、`indigenous`、`history`、`urban`、`workshop`、全部 `group_*` 群組標籤（5 個）
- `categories` 標籤值還原為舊版：`performing_arts` en/ja、`geopolitics` en/ja
- `filters` 遺失：`timeModeAll`、`locationOnline`
- `admin` 遺失：`source`、`annotationLabel`、`annotationStatusLabel`、`scrapedAt`、`filterAnnotatedShort/ReviewedShort/ErrorShort/PendingShort`、`selectAll`、`bulkHide/Show`、`bulkForceRescrape`、`forceRescrapeOn/Off/Queued`、`statsTotalEventsLabel`、`statsActiveCount`、`statsPendingLabel`、`statsUsersLabel/Desc`、`statsReportsLabel/Desc`、`pendingSummaryInactiveOnly`、`bulkCommonCategories/Hint`

**根本原因：** AI 在大 context 中同時持有新舊版翻譯快照，將舊版本作為整份 JSON 輸出，覆蓋了所有中間的增量改動。

**修復：** 以 Python 腳本從 `b5a574a` / `65b90ca` / `471b66d` commit 取回正確值，逐一 merge 回三個語言檔案，並以 assert 驗證後 push。

**Lesson：**
1. **Scraper / non-web commit 絕不應修改 `web/messages/*.json`**
2. 翻譯 key 只增不減；刪除 key 前必須確認 codebase 無任何引用
3. 規則已寫入 SKILL.md §i18n Regression Prevention

---
## 2025-05-04 — Session 61b5118d 效率復盤：三個高工具數反模式
**觀察：** session `61b5118d` 共 54 回合、945 次工具呼叫，平均 17.5 次/回合（正常 < 12）。
分析出三個反模式：
1. **URL + 隱含大範圍**：貼 URL + 「請檢查類似狀況」→ 全域掃描（T04 61 tools, T12 68 tools）
2. **「請繼續做 XXX」連發**：同類爬蟲拆成 7 輪分別要求，每輪重新載入 context（T08–T14）
3. **問題 + 修正 + 規則更新三合一**：每個 bug 立即觸發 fix + history + skill 三連寫（T21→T22 71 tools）

**改善規則（已寫入 `session-analytics/SKILL.md`）：**
1. 指定明確範圍：「僅修這個 event，規則稍後批次更新」
2. 一次列出全部任務：「建 A、B、C 三個爬蟲，按順序，每完成告訴我」
3. 累積再批次：「先修 bug，我說『批次更新 skill』時再一次整理」

**Lesson：** 提示模式本身就是可優化的成本來源。每月 `--days 30` 確認效率趨勢，高峰 session 用 `--verbose` 定位回合後，對照三個反模式判斷原因。

---
## 2026-04-26 — AdminEventTable filter label/style regressions repeated across multiple commits
**Error:** Three UI fixes (`tFilters("search")` search label, `tFilters("category")` category label, `bg-gray-50` category button) were re-introduced and re-regressed multiple times because later commits modifying the same file for unrelated reasons (bulk-toggle refactor, reannotate label rename) overwrote the corrected lines with default values.
**Fix:** Re-applied the three fixes; added protected-invariants rule to `engineer/SKILL.md`; added regression entry to `engineer/history.md`.
**Lesson:** Files with frequently-touched UI logic accumulate "sticky regressions". The architect plan for any `AdminEventTable.tsx` change must explicitly mention the protected invariants as a check item.

---
## 2026-04-26 — Online canonical form corrected: location_address must be 'オンライン', not NULL
**Error:** Previous session established `location_address = NULL` as the canonical form for online events. This was wrong: it caused online events to appear in the `tokyo` admin filter (which treats NULL address as "Tokyo"), and `other_japan` filtering relied solely on `location_name` to exclude online events, creating fragile single-point-of-failure logic. The `AdminEventTable.tsx` `other_japan` filter had no online exclusion at all, meaning online events would appear there too.

**Fix:**
1. New canonical form: `location_name = 'オンライン'`, `location_address = 'オンライン'`. Both columns set. DB also requires `location_address_zh = '線上'`, `location_address_en = 'Online'`.
2. `peatix.py`: all 3 places that set `location_address = None` for online events changed to `= 'オンライン'`.
3. `connpass.py` + `doorkeeper.py`: `_normalize_location_address()` now returns `'オンライン'` instead of `None`.
4. `AdminEventTable.tsx`: added `if (addr.includes('オンライン')) return false` to `other_japan` filter.
5. `page.tsx`: updated comment; filter logic unchanged (still queries `location_name`).
6. DB: patched 7 peatix online events (`location_address = 'オンライン'`, zh/en translations set).

**Lesson:** `location_address = NULL` must not be used as a sentinel for "online" — NULL means "unknown/unset", not "online". Scrapers must always set `location_address = 'オンライン'` for online events. Any filter that gates on `location_address IS NOT NULL` will mis-classify events if online events have NULL address. Updated "Online Location Standard" rule in SKILL.md.

---
## 2026-04-26 — Online location filter broken: queried wrong column + scrapers lacked normalization
**Error:** The `location=online` filter in `page.tsx` queried `location_address ILIKE '%オンライン%'`. After the correct normalization (online events should have `location_address = NULL`), the filter returned 0 results. Additionally:
1. Several peatix events had `location_name = 'オンライン（Zoom）'` with non-null address — the `(Zoom)` suffix was not canonicalized and the address was not cleared.
2. `connpass.py` and `doorkeeper.py` had no online detection at all — API fields `place`/`venue_name` containing 'オンライン' were passed through without normalization.
3. `other_japan` filter excluded online via `location_address NOT ILIKE '%オンライン%'` which also failed once addresses became NULL.

**Fix:**
1. `page.tsx`: online filter → `location_name ILIKE '%オンライン%'`; other_japan exclusion → `location_name NOT ILIKE '%オンライン%'`.
2. `peatix.py`: added final canonicalize step after all fallbacks: if `location_name` matches online marker → `'\u30aa\u30f3\u30e9\u30a4\u30f3'`, address = None.
3. `connpass.py` + `doorkeeper.py`: added `_ONLINE_RE`, `_normalize_location_name()`, `_normalize_location_address()` helpers.
4. DB: cleared address for 7 active peatix events with online markers.

**Lesson:** The canonical online event representation is **`location_name = '\u30aa\u30f3\u30e9\u30a4\u30f3'`, `location_address = None`**. Any query filtering for online events must check `location_name`, not `location_address`. All scrapers must normalize their output before building the Event object. Added “Online Location Standard” rule to SKILL.md.

---
## 2026-04-26 — Peatix online event incorrectly assigned a physical address (×2 errors in same session)
**Error:** Event `05aefbdf` (周美花講演) is a hybrid/online event. Peatix renders its LOCATION block as a single line `"LOCATION\n\nOnline event"` — no second group. The scraper's primary regex (`LOCATION\n\n(.{3,100})\n\n([^\n]{3,200})`) requires two groups separated by a blank line, so it didn't match. All CSS and regex fallbacks then ran, finding:
1. A campus name from the description body text → `location_name = '桜美林大学新宿キャンパス'`
2. `東京都新宿区` from the description → `location_address`

In the same session, the previous turn had wrongly "verified" and patched this same event with the full campus address `東京都新宿区百人町3-23-1`, compounding the error.

**Fix:**
1. Added `is_confirmed_online` guard in Peatix scraper: detect `LOCATION\n\n(Online event|オンライン|…)` FIRST, set the flag, and skip ALL subsequent address fallbacks.
2. Fixed final body-text online fallback to set `location_address = None` (was `'オンライン'`).
3. Patched DB event `05aefbdf`: `location_name='オンライン'`, all address fields `None`.

**Lesson:** When a Peatix LOCATION block contains an online marker, it must **immediately short-circuit all address extraction**. Address fallbacks must never run against the event description body — venue names mentioned in prose ("会場…桜美林大学") are conditional/secondary and must not become `location_address`. Added rule to SKILL.md under Online Events.

---
## 2026-04-26 — AI confidently reversed a correct scraper address to a wrong one (×2 errors)
**Error:** The taiwan_cultural_center scraper hardcoded `location_address = "東京都港区虎ノ門1-1-12"`. A user questioned whether this matched the DB value `南青山3-10-33`. Without verifying the official source, Architect incorrectly agreed the DB value was correct and committed `fix(scraper): correct … from 虎ノ門 to 南青山` (commit 2cbb8b8). In the same session, the `backfill_locations.py` pipeline had previously generated hallucinated addresses (`南青山3-10-33`, `南青山2-1-1`) via OpenAI for 2 events, which were stored as fact in the DB. The real address, confirmed at https://jp.taiwan.culture.tw/cp.aspx?n=362, is **〒105-0001 東京都港区虎ノ門1-1-12 虎ノ門ビル2階**.
**Fix:**
1. Reverted scraper to correct address `東京都港区虎ノ門1-1-12 虎ノ門ビル2階` with source URL in comment.
2. Patched 2 DB events (`f7ff56ca`, `e646c256`) — all three locale fields — to the verified address.
3. Amended/replaced the bad commit.
**Lesson:** **Never accept a hardcoded address change based on a DB value alone.** The DB may itself be wrong (backfill AI hallucination). Always verify against the official source URL before any address change. Every hardcoded address in a scraper must cite the verification URL in a comment. Added "Address Verification" rule to SKILL.md.

---
## 2026-04-25 — Repeated hardcoded CJK strings across admin components (multi-session)
**Error:** Over three sessions, 30+ hardcoded Traditional Chinese strings were found across 6 admin TSX files and 2 page files. Problems accumulated because each new feature/admin component was written with hardcoded zh strings instead of `t()` calls, and the audit/test step was skipped. The issues were only discovered when users switched to English or Japanese mode and saw Chinese labels:
- Stats cards: `活動總數`, `待標注`, `註冊用戶`, `擁有角色的用戶`, `待審問題回報`, `status = pending`
- AdminEventTable filter bar: 時間範圍, 地點, 標注狀態 labels + all options (22 strings)
- AdminReportsTable: `有料`/`無料` in a module-level const (couldn't use hooks; required passing `tEvent` as param)
- AdminResearchTable: status labels, URL valid/invalid badges, tooltip
- AdminSourcesTable: STATUS_FILTERS filter button labels
- Footer: `營運維護：對對觀 2026`
- Stats error banner: `scraper_runs 表尚未建立`

**Fix:** Replaced all hardcoded zh strings with `t()` / `tFilters()` / `tEvent()` calls. Added new i18n keys to all three `messages/*.json` files simultaneously. Fixed module-scope const limitation in AdminReportsTable by passing `tEvent` as a function parameter.

**Lesson:** After writing ANY TSX file with visible text, run the CJK audit script before committing. Module-level consts that contain UI strings cannot use `useTranslations()` — either move them inside the component function, or pass the translation function as a parameter. → Added i18n rules to web.instructions.md and SKILL.md.

---
## 2026-04-25 — classifier keyword "博士" caused false `academic` tag on nature event
**Error:** Added `"博士"` to the `academic` keyword list in `classifier.py` as part of the new-category rollout. A nature/flower-walk event at 高知県立牧野植物園 was tagged `['academic']` instead of `['nature', 'tech', 'tourism']` because its description contained「牧野博士ゆかりの桜」— a proper noun (person's name), not an academic context.
**Fix:** Removed `"博士"` from the `academic` rule. Re-classified the event and confirmed no other active events were affected.
**Lesson:** When designing classifier keyword lists, avoid person-title words (博士, 先生, 教授 as names) and other common words that can appear in non-academic contexts as proper nouns. Prefer compound terms (e.g., 「博士課程」「博士論文」) or context-specific phrases. → Added rule to SKILL.md under Classifier Keywords.

---
## 2026-04-25 — researcher.py used model without web browsing capability
**Error:** Designed `researcher.py` using `gpt-4o-mini` to simulate web research across 5 categories. Did not verify model capabilities first. Result: all discovered URLs were hallucinated (404s, wrong pages, non-existent organizations) in daily research reports.
**Fix:** Rewrote with `gpt-4o-search-preview` (real Bing search) + 5 parallel `CategoryAgent` instances via `ThreadPoolExecutor` + Playwright URL verification on every discovered source.
**Lesson:** Before designing any AI feature requiring real-time data, verify the model’s tool/capability list. → Added "AI Model Selection" rule to SKILL.md.

---
## 2026-04-23 — Monitoring stack shipped without confirming migration state
**Error:** Designed and handed off the full monitoring stack (scraper_runs table, /admin/stats page, Sentry) without first confirming that pending migrations 006 and 007 had been applied in the Supabase project. On first load, the stats page showed an error banner and the event_reports admin tab was broken.
**Fix:** Retrospectively identified missing migrations as Step 1 (manual) in the remediation plan.
**Lesson:** Check migration state as Phase 1 research whenever a feature assumes or extends DB schema. → Added to SKILL.md under Planning.
