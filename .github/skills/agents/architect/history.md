# Architect Error History

<!-- Append new entries at the top -->

---
## 2026-05-01 — Phase 1+3 SLA + Quality Dashboard 成功重建（commit bd818cf）

**背景：** Phase 1（SLA 欄位）和 Phase 3（Quality Dashboard）在首次實作（commit 644a0ad）後因 `react-hooks/static-components` lint error 和用戶決定 revert（commit cf1e0a9）。本次成功重建。

**本次做對的：**
1. `quality/page.tsx` 的 `renderDetailTable` 函式宣告在 module 頂層（`export default` 之前），避免 PascalCase-in-render lint error。
2. 使用 camelCase IIFE `{(() => {...})()}` 做 inline 計算，不觸發 react-hooks/static-components。
3. i18n 9 keys 與所有 caller 在同一 commit 新增，無遺漏。

**教訓：**
- 被 revert 的功能重建時，先回顧 revert 原因（lint error），確認 SKILL.md 已有對應規則（TSX Component vs Helper），再按規則重寫。
- Engineer SKILL 的 `react-hooks/static-components` 規則在此次發揮作用：首次失敗是因為規則尚未建立；第二次成功是因為規則已存在且被遵守。

---
## 2026-05-01 — OG image 英文標題截斷過早（字元密度差異）

**工作內容（commit 47ac1ee）：**
`web/app/[locale]/events/[id]/opengraph-image.tsx` 截斷邏輯從兩級改為三級：
- 舊：`> 36 字 → 截斷至 34 字`（字體：`> 22 字 → 54px`，否則 `72px`）
- 新：`> 55 字 → 截斷至 53 字`（字體：`> 36 字 → 40px`、`> 22 字 → 54px`、否則 `72px`）

新字體三級表：
| 標題長度 | 字體大小 |
|---------|----------|
| ≤ 22 字 | 72px |
| 23–36 字 | 54px |
| 37–55 字 | 40px（新增） |
| > 55 字 | 40px + 截斷至 53 字 |

**根因：**
英文標題字元數通常是日文的 2–3 倍（日文一個字 = 一個 CJK 字元；英文一個單字 = 5–8 字元）。原本 36 字截斷設計以日文視覺寬度為基準，英文標題在 36 字元時視覺上僅填滿約 40–50% 的標題區域，導致文字被過早截斷（顯示 "C…" 等不完整字串）。

**教訓：**
1. **OG image 截斷閾值應依語言分開設計**：日/中以字元視覺寬度計（每字元寬，36 字足夠）；英文以字元數計（每字元窄，需 50+ 字才填滿同等空間）。
2. **增加字體縮小級別優先於截斷**：新增 40px 中間層讓長英文標題縮小後多行顯示，而非硬截斷，保留完整語意。
3. **截斷欄位設計必須考慮多語言字元密度**：任何 `text.length > N ? text.slice(0, M) + "…" : text` 邏輯，N 值應以最長語言（英文）為基準，並搭配字體縮小梯級。

---
## 2026-05-01 — 電視頻道地點類型 + 品質檢查白名單 + AdminEventTable 雙重篩選同步

**工作內容（commits 5851e46 + enrich_addresses commit）：**
1. `scraper/sources/gguide_tv.py`：`location_name` 統一改為 `"電視頻道"`，取代各頻道名稱（tvk1, BS朝日1 等）
2. `web/app/[locale]/page.tsx`：新增 `tv` 地點篩選分支（`ilike '%電視頻道%'`）；`other_japan` 排除電視節目
3. `web/components/AdminEventTable.tsx`：`filterLocation` 型別加 `"tv"`；`getFiltered` 和 `sourceCountMap` 兩處同步更新；select 新增 TV 選項
4. `web/components/FilterBar.tsx`：location select 新增 `tv` 選項
5. `web/messages/{zh,en,ja}.json`：新增 `locationTv` i18n key（三個檔案同時）
6. `scraper/enrich_addresses.py`（新建）：GPT-4o-mini 為「有場館名但無地址」的活動補 ja/zh/en 地址；跳過 gguide_tv 和線上活動
7. `web/app/[locale]/admin/quality/page.tsx`：「缺地址」品質檢查排除 `source_name = 'gguide_tv'` 和 `location_name = '電視頻道'`

**根因（gguide_tv 混入地區篩選）：**
`gguide_tv` 爬取的是 TV 番組，無實體地點，但 `location_name` 原先儲存各頻道名稱（tvk1、BS朝日1 等），被 `other_japan` 篩選邏輯誤匹配，品質檢查也誤報「缺地址」。

**根因（AdminEventTable 計數與列表不一致）：**
`AdminEventTable.tsx` 內有兩套平行的篩選邏輯：`getFiltered`（控制列表顯示）和 `sourceCountMap`（控制各 source 計數）。只更新 `getFiltered` 而遺漏 `sourceCountMap` 會造成計數與列表對不上。

**教訓：**
1. **無實體地點的來源必須設 canonical location_name**：電視、廣播、串流等無地點活動應設固定 canonical 值（如 `電視頻道`），避免被地址篩選誤匹配、品質檢查誤報。
2. **`other_japan` 篩選必須明確排除所有特殊類型**：目前需排除 online（`オンライン`）和 TV（`電視頻道`）兩種。每新增一種無地點類型，`other_japan` 篩選邏輯都需更新。
3. **新增地點類型需同步更新 6 個地方**（見 SKILL.md 新增的「新增地點類型 Checklist」）。
4. **品質檢查「缺地址」規則需白名單機制**：天生無地址的來源（gguide_tv、online 等）必須在 quality page 明確排除，否則製造噪音。
5. **AdminEventTable 雙重篩選同步**：`getFiltered` 和 `sourceCountMap` 使用相同邏輯，任何篩選修改必須同步兩處，否則計數和列表對不上。

---
## 2026-05-01 — SEO/AEO 強化 + GSC OAuth2 + proxy.ts 排除規則 + Admin tab 一致性

**工作內容（commits a9ef1d1 → d2fddcd）：**
1. sub-events 日期補 `<time dateTime>` 語意標籤（a9ef1d1）
2. 新增 `web/app/api/admin/gsc/route.ts` + `web/components/GscSection.tsx`（GSC 監控卡片）
3. GSC API 從 service account JWT 改為 OAuth2 refresh token（c6f8075）
4. HTML 驗證檔 `web/public/google12eeb8b1a7239866.html` + `proxy.ts` 排除（e698874）
5. aeo 頁面 header 改為完整 tab nav（5cae991）
6. `aeoTab` i18n key 改名「SEO-AEO 監控」（d2fddcd）

**根因（GSC service account 問題）：**
Google Search Console UI **只允許一般 Google 帳號**作為使用者；service account email 提交時報「找不到電子郵件」。原本設計用 service account JWT 的方案無法走通，必須改用 OAuth2 refresh token（`GSC_CLIENT_ID` + `GSC_CLIENT_SECRET` + `GSC_REFRESH_TOKEN`）。

**根因（HTML 驗證檔被 i18n 攔截）：**
`web/public/` 下的靜態檔案若不在 `proxy.ts` matcher 的排除規則內，會被 next-intl middleware 307 重導向至語言路徑（`/zh/google...html`），導致 Google 無法讀到驗證檔。排除規則 `google[0-9a-f]+\.html` 可涵蓋所有 Google 驗證檔格式。

**教訓：**
1. **Google Service Account 無法加入 Search Console**：設計 GSC 整合時，預設方案必須是 OAuth2 refresh token，而非 service account。
2. **OAuth Playground 需先設定測試使用者**：App 處於「測試」模式時，需在 OAuth consent screen 把自己的帳號加入「測試使用者」，否則授權流程 403 `access_denied`。
3. **所有 `web/public/` 靜態檔案都需要同步更新 `proxy.ts` 排除規則**：這是 AEO Feature Planning Rules 中「Static file checklist」的延伸，必須把它列為每次新增靜態資源的預設檢查步驟。
4. **Admin 子頁面 header 必須使用完整 tab nav**：不可只放「← 返回」連結；必須使用 `getTranslations("admin")` + Link 列表，與其他 admin 頁面保持一致。

---
## 2026-05-01 — Architect 直接編輯後留半成品：停止點契約缺失

**情境：**
撤銷 Tier 1 監控（Phase 1+3）時，Architect 親自刪除 `web/messages/{zh,en,ja}.json` 中 10 個 i18n keys 與 `stats/page.tsx` 的 SLA 欄位、整個 `quality/page.tsx`。但**沒同步刪 stats/page.tsx 中的 `t("statsSlaHeader")`、`t("statsAvgDuration")` 呼叫**，工作樹留下會編譯失敗的半成品。用戶察覺後質疑「agent 開發完最後一步究竟停在哪裡？」

**根因：**
1. Architect 預設 read-only，沒有「直接編輯後須收尾」的停止點契約。
2. 報告中常用裸 commit hash（如「commit cf1e0a9」），用戶誤以為已推送，但實際只是 local commit 或甚至 working tree。
3. 刪 i18n key 沒先 `grep_search` 找 caller，違反 atomic revert 原則。

**修正：**
SKILL.md 新增三節 —
- **Stop-Point Contract**：直接編輯後必須走完 V-M-D 鏈路或明示「⚠️ 未提交」。
- **Status Reporting Vocabulary**：強制使用 ✅已推送 / ⏳本地only / 📝未commit 三種標籤。
- **Atomic Revert Rule**：刪 symbol 前必 grep caller，先刪 caller 再刪 definition，commit 前 `tsc --noEmit`。

**教訓：**
- 「Architect 不寫 code」是預設值不是絕對值；一旦破例就必須明示交接狀態。
- commit hash 出現 ≠ 已推送。報告必須區分三種狀態。
- 不是 git 分支策略問題（main 全程同步），是 agent 工作流程契約缺失。

---
## 2026-05-01 — AEO 架構設計（Phase A/B/C）：AI Engine Optimization 全域規劃

**工作內容：**  
設計並規劃 AEO 三階段實作，涵蓋 AI 搜尋引擎可見度提升、IndexNow 即時提交、監控追蹤。

**架構決策：**

1. **JSON-LD 分層策略**：全域 JSON-LD（WebSite + Organization）放 `layout.tsx`；頁面級 JSON-LD（BreadcrumbList、CollectionPage、FAQPage）放各自的 `page.tsx`。避免全域與頁面級 schema 衝突。

2. **AEO 監控不依賴伺服器組件**：monitoring 放在 Edge middleware（`proxy.ts`），而非 Server Component 或 API route，因為 proxy 是所有請求的必經路徑，能攔截 bot UA 和 AI referrer 而不影響正常渲染。

3. **IndexNow 整合點**：在 `upsert_events()` 返回新 UUID 列表（非修改現有函式簽名的破壞性變更，而是擴展返回型別），使 `main.py` 的 orchestrator 能在每次 scraper run 後立即提交新活動 URL，延遲最短。

4. **聚合頁 URL 設計**：`/[locale]/cities/[city]` 和 `/[locale]/categories/[category]` 靜態路由（generateStaticParams），可被搜尋引擎快取，也適合 CollectionPage + ItemList JSON-LD schema。

5. **FAQPage 設計規則**：FAQ 問答設計為 2-4 個問題，涵蓋「什麼是台灣文化活動」「如何找到最新活動」等常見 AI 查詢。**關鍵：** JSON-LD 必須搭配頁面上可見的 `<dl>` 元素，Google 不接受僅 JSON-LD 而無可見內容的 FAQPage。

**教訓：**
- AEO 計劃必須明確標注「static file → proxy.ts matcher 同步」的步驟，這是最容易被遺漏的實作細節。
- FAQPage JSON-LD 必須在計劃中同時要求可見 `<dl>` section，否則 Engineer 只會做 JSON-LD 而跳過可見部分。
- Migration 號碼衝突（如兩個 029_）要在規劃期確認最新 migration 號碼，避免衝突。規劃新 migration 前必查 `ls supabase/migrations/` 確認下一個可用號碼。

---
## 2026-05-01 — Tier 1 資源監控：保留預算護欄，撤銷 SLA + 品質 Dashboard

**背景：** 原本規劃三層儀表板（SLA、品質、預算），但實際上線後 `/admin/stats` 的 SLA 欄與 `/admin/quality` 全頁被使用者撤回，僅保留 `weekly_report.py` 的預算護欄。

**最終結果：**
- ✅ 保留：`weekly_report.py` 新增 `MONTHLY_BUDGET_USD = 20.0` 護欄與「本月迄今 / OpenAI 本週 / DeepL 本週」三行。
- ❌ 撤銷：`/admin/stats` 的「30 日成功率」「平均耗時」兩欄、`/admin/quality` 整頁、相關 i18n keys（statsSlaHeader/AvgDuration/qualityTab/qualityTitle 等 10 個）。

**教訓：**
- 規劃 admin UI 時，先問清楚「這頁面真的會被點開嗎？」單純的計數 dashboard 若沒導向具體 action（一鍵修正、批次處理）容易淪為視覺裝飾。
- 預算層信號（單一 LINE 訊息推送）成本低、留存率高；UI 層信號（需主動訪問）容易被忽略。下次規劃監控功能優先做被動推送（LINE / email / issue）而非新頁。
- 撤銷比新增便宜：留下 plan、commit history、SKILL.md「未來如需…」備註，將來想做時隨時可以重做。

---
## 2026-05-01 — Tier 1 規劃版本（已部分撤銷，記錄保留）

**背景：** 原本 `/admin/stats` 只顯示最近一次執行狀態、`weekly_report.py` 只看週費用、並無資料品質審核面。長期下來難以推斷「某個來源是偶發失敗還是長期退化」。

**變更：**
- `/admin/stats` Source Status 表加入「30 日成功率（🟢/🟡/🔴）」與「平均耗時」兩欄，來源為 `scraper_runs.duration_seconds`（migration 014）。
- `weekly_report.py` 新增 `MONTHLY_BUDGET_USD = 20.0` 護欄，並推送「本月迄今 / OpenAI 本週 / DeepL 本週」三行，超過閾值走 ⚠ / 🚨。
- 新建 `/admin/quality` 頁，並行查 4 個品質信號（已審缺翻譯 / 過期仍開放 / 已標註無分類 / 卸地址），每類列出前 50 筆詳情。

**教訓：**
- 「崩湬 / 安全」與「品質 / 退化」是兩個身分，儀表板也要分開；SLA 看來源健康、quality 看資料完整、budget 看費用。
- TypeScript 的 `latestBySource.r.duration_seconds` 在不同 migration 狀態下可能為 `undefined`，需以 `?? 0` 傅底，不能讓 SLA 表崩。
- LINE 週報 `format_line_message()` 报告變豊富時，請主動加一行空行，避免 「📊 周報」 與 「💰 本月迄今」 默一起。

---
## 2026-04-29 — AdminEventTable 日期範圍篩選器無法搜索未來活動

**問題：** `filterTimeMode === "past"` 分支在 `getFiltered` 和 `sourceCountMap` 兩處都有 `isPast` 判斷（`end_date < today`），導致「搜尋特定期間」無法找到 end_date 在未來的活動。

**根本原因：** 日期範圍篩選器把「過去期間」和「任意日期範圍」的語意混在一起；且 `getFiltered` 與 `sourceCountMap` 使用相同邏輯卻未同步修改。

**修復（7f00d4e）：** 移除兩處的 `isPast` 限制，改為純粹 from/to 日期邊界篩選；同時重命名 i18n 標籤為「搜尋特定期間」。

**教訓：**
- 日期範圍篩選器設計原則：from/to 應為純粹的日期邊界，不應附加「只搜過去」的語意
- 計劃中任何涉及 `AdminEventTable` 篩選邏輯的修改，都必須明確標注「`getFiltered` 和 `sourceCountMap` 兩處需同步更新」
- 篩選器 i18n 標籤應精確描述行為（「特定期間」而非「過去期間」）

---
## 2026-04-29: drama 新增導致 'retail' 從 Category union 遺失

**錯誤：**
`multi_replace_string_in_file` 新增 `"drama"` 到 Category union 時，意外刪除了 `"retail"`。
TypeScript build 失敗 → Vercel 停在舊版本 → 用戶看不到 drama 分類。

**修復：** `f9e6b52` — 補回 `| "retail"` 到 Category union。

**教訓：**
- Category union 新增後，必須立即執行 `npx tsc --noEmit`，確認所有既有成員仍存在
- `multi_replace_string_in_file` 的 oldString 必須包含足夠上下文（≥3行），避免截斷鄰近 union 成員
- Vercel build 失敗時頁面不更新但不會下線（顯示舊版），需主動檢查 TypeScript 錯誤

---
## 2026-04-29: Peatix organizer Layer 3 + daily discovery rotation

**工作內容：**
- peatix.py 加入 DB-driven organizer 動態載入（Layer 3 模式）
- discovery_accounts.py 完整重寫為 4 槽每日輪流
- discovery-accounts.yml 從每週日改為週一到週四每日執行

**教訓：**
- Layer 3 擴充到新平台（Peatix）時，需要獨立的 agent_category（`peatix_organizer`），不可與 `note_creator` 混用
- Skills 資料夾整理：per-source skill 必須放 `sources/{name}/`，不可在頂層建立

**Skills folder audit lesson：**
- `.github/skills/` 頂層只放 workflow/tooling skills（local-preview, cc-statusline, session-analytics）
- per-agent skills → `agents/{agent-name}/`
- per-source skills → `sources/{source-name}/`（有 `applyTo: scraper/sources/*.py` 的都應在這裡）

---
## 2026-04-29 — LINE webhook 0 subscribers — `LINE_CHANNEL_TOKEN` missing from Vercel
**Error:** After users added the LINE bot as a friend, `line_subscribers` remained at 0 rows. Schema INSERT worked fine in manual test; the issue was at the webhook layer.
**Diagnosis:** GitHub Actions secrets (`LINE_CHANNEL_TOKEN`, `LINE_CHANNEL_SECRET`) and Vercel environment variables are **completely separate systems**. The webhook runs on Vercel, not in GitHub Actions. `LINE_CHANNEL_TOKEN` was never set in Vercel → signature verification failed → HTTP 401 → follow events rejected. LINE does not retry failed webhook deliveries.
**Fix:** Added `LINE_CHANNEL_TOKEN` to Vercel Dashboard → Settings → Environment Variables (Production). User blocked + unblocked the bot to re-trigger the follow event → 1 row successfully inserted.
**Lesson:** When a feature spans GitHub Actions (scraper/broadcast) **and** Vercel (webhook/API), both platforms need their own copy of shared credentials. Never assume that secrets in one CI/CD platform propagate to another. Architect plans for cross-platform features must list required env vars per platform explicitly.

---
## 2026-04-26 — Admin table address cell lacked locale fallback
**Error:** `AdminEventTable.tsx` address column only read `location_address` (Japanese/default). Events with addresses stored only in `location_address_zh` (zh-first scrapers like `koryu`) or with address embedded in `location_name` showed blank in admin. The front-end detail page was correct because it used `getEventLocationAddress()` with a fallback chain.
**Fix:** Updated the `<td>` to `addr = location_address || location_address_zh || location_name` (commit `f45d5d5`).
**Lesson:** Architect plans must note: admin table display logic for any locale-aware field must match the helper function fallback in `lib/types.ts`. When designing a new table column, always reference the corresponding `getEvent*()` helper and replicate its fallback chain.

---
## 2026-04-26 — AdminEventTable orphaned `<td>` after `<th>` removal
**Error:** The `isPaid` `<th>` was deleted from the annotated-view header, but its paired `<td>` in the row renderer was not deleted in the same change. The misalignment was invisible to TypeScript and only caught visually by the user.
**Fix:** Removed the orphaned `<td>` (commit `5597150`). Added column-pairing rule to `engineer/SKILL.md`.
**Lesson:** Architect plans that include removing a column from `AdminEventTable.tsx` must explicitly state: "remove the matching `<td>` in the same PR". Column count is a visual contract that static analysis cannot enforce.

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

---
## 2026-04-26 — Admin table address cell lacked locale fallback
**Error:** `AdminEventTable.tsx` address column only read `location_address` (Japanese/default). Events with addresses stored only in `location_address_zh` (zh-first scrapers like `koryu`) or with address embedded in `location_name` showed blank in admin. The front-end detail page was correct because it used `getEventLocationAddress()` with a fallback chain.
**Fix:** Updated the `<td>` to `addr = location_address || location_address_zh || location_name` (commit `f45d5d5`).
**Lesson:** Architect plans must note: admin table display logic for any locale-aware field must match the helper function fallback in `lib/types.ts`. When designing a new table column, always reference the corresponding `getEvent*()` helper and replicate its fallback chain.

---
## 2026-04-26 — AdminEventTable orphaned `<td>` after `<th>` removal
**Error:** The `isPaid` `<th>` was deleted from the annotated-view header, but its paired `<td>` in the row renderer was not deleted in the same change. The misalignment was invisible to TypeScript and only caught visually by the user.
**Fix:** Removed the orphaned `<td>` (commit `5597150`). Added column-pairing rule to `engineer/SKILL.md`.
**Lesson:** Architect plans that include removing a column from `AdminEventTable.tsx` must explicitly state: "remove the matching `<td>` in the same PR". Column count is a visual contract that static analysis cannot enforce.

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
