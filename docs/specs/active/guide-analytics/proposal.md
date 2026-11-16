---
slug: guide-analytics
title: 專題導覽工具（/YYYYMM/*）的訪客動線、停留時間與搜尋詞統計
status: active
branch: feat/guide-analytics
created: 2026-11-16
tags: [web, supabase, analytics]
---

## What（做什麼）

讓後台看得到 `/202611/synchronic-constellation`（共時的星叢 クイックガイド）這類靜態專題導覽工具的使用情形：

- 各「頁面」（導覽內的 home／章節／作品／資料 view）被看了幾次、停留多久
- 一次造訪的動線（session 內依序看了哪些 view）
- 訪客用什麼工具：裝置類型、瀏覽器、LINE／Instagram／Threads／Facebook 的 in-app browser
- 從哪裡來：Google、LINE、SNS、AI 引擎（Perplexity、ChatGPT…）、direct；UTM
- 導覽內搜尋框輸入了什麼、有沒有結果（現場觀眾在找什麼）
- 站外搜尋關鍵字：Search Console 中落地在這個導覽 URL 的查詢詞
- 往外點了什麼（作品／資料清單 PDF、展覽官方頁、雷達主站）、切換了哪種語言

並在後台新增 `/admin/guides` 頁，與既有 `/admin/analytics`（活動點擊）互相連結但資料分開。

## Why（為什麼）

2026-11-16 盤點：

- 導覽是 `web/public/202611/synchronic-constellation/index.html` 單一靜態檔。Vercel Analytics／Speed Insights 只掛在 `app/[locale]/layout.tsx`，靜態檔沒有載入。
- `proxy.ts` 的 matcher 排除 `[0-9]{6}/`，`aeo_visits` 沒有記錄這條路徑。
- `event_views` 只由活動詳情頁的 `recordEventView` 寫入。
- 導覽內的章節／作品／資料是 hash 路由（`#ch3`、`#A2-05`、`#D1-001`）。即使掛上 pageview 工具，也只會看到同一個 URL；站內動線必須由頁面自己送事件。

結果：目前**完全沒有**這個導覽的使用資料。

## Non-Goals（不做什麼）

- 不引入第三方分析服務（GA4、Clarity、Plausible…）：屬「新增外部服務」人類關卡，也會讓靜態頁多一個跨站 script。
- 不記 IP、不設 cookie、不做跨日的訪客識別；session ID 只存在 `sessionStorage`，關分頁即消失。
- 不記錄 AI bot 爬取這個導覽（bot 不跑 JS）。要記需改 `proxy.ts` matcher，讓 `YYYYMM/` 走 middleware，影響 slides export 的靜態資源與 middleware 用量；另開 issue 觀察需求後再做。
- 不做 heatmap、session replay、捲動深度。
- 不把導覽資料併入 `event_views` 或 `/admin/analytics` 的既有數字。
- 不做 rate limit：目前沒有現成基礎設施（KV 等屬新增外部服務）。以同源檢查、大小上限與 slug 白名單降低濫用；被灌時再開 issue。
- 本 PR 不做資料保存期限與頁尾匿名統計說明，另開 issue（刪除舊資料屬 production 寫入）。

## Design（設計摘要與決定）

### 資料：`guide_events`（migration 108）

一列一個事件，`event_type` 五種：

| event_type | 何時送 | 主要欄位 |
| --- | --- | --- |
| `view` | 載入與每次 hash 切換 | `view_kind`（home／chapter／work／doc）、`view_id`、`seq`（session 內第幾個 view） |
| `leave` | 離開該 view（切換、分頁隱藏、關閉） | `view_kind`、`view_id`、`seq`、`dwell_ms`（只算分頁可見時間，單段上限 30 分）。同一 view 可能有多段，聚合時依 `(session_id, seq)` 加總 |
| `search` | 搜尋框停止輸入 1.2 秒、點作者 chip、點作品／資料頁上的作者連結 | `search_query`（≤100 字）、`result_count`、`target`（input／chip／artist） |
| `outbound` | 點外部連結 | `target`（URL，≤300 字） |
| `lang` | 切換語言 | `target`（ja／en／zh） |

共通欄位：`guide_slug`、`session_id`、`lang`、`device`、`browser`、`in_app`、`traffic_source`、`referrer_host`、`utm_source／medium／campaign`、`country`、`region`。

- **存取模型 Tier C＋admin 讀**：RLS 開，policy `TO authenticated USING ((select is_admin()))` 只給 SELECT；`REVOKE ALL … FROM anon, authenticated` 後只 `GRANT SELECT TO authenticated`、`GRANT INSERT, SELECT TO service_role`。寫入一律經 `/api/guide/track` 以 service role 寫。這**不會**比 anon insert 更難灌資料，好處是表結構不直接暴露給 PostgREST、所有欄位在伺服器端統一驗證與截斷。CHECK 限制 `event_type`、`view_kind`、`lang`、`guide_slug` 格式與各欄位長度。
- **聚合在 SQL 端**：`guide_stats(p_slug text, p_since timestamptz)`，`SECURITY INVOKER`、`search_path = pg_catalog, public`，回傳一個 jsonb（摘要、熱門 view、轉移、session 長度、搜尋詞、零結果詞、各維度分布、外連、語言）。RLS 照常套用，非 admin 呼叫只會得到空結果；仍 `REVOKE EXECUTE … FROM PUBLIC, anon`。後台一次 RPC 取回，不在 JS 端分頁抓原始列。
- **API 防護**：只接受同源（`Origin` 是本站，或 `Sec-Fetch-Site: same-origin`）；先 `req.text()`、超過 16KB 回 413，再 `JSON.parse`（`sendBeacon` 送字串是 `text/plain`，不依賴 content-type）；`guide_slug` 白名單（目前只有 `202611/synchronic-constellation`）；每批最多 20 筆。dev 環境不寫；帶 Supabase `sb-` cookie 時查身分，admin 自己的瀏覽不寫。
- `country`／`region`、`device`／`browser`／`in_app`、`traffic_source` 在伺服器端判斷，不信任 client 傳來的分類；client 只傳 `document.referrer` 與 URL 的 UTM。注意 request 的 `Referer` header 永遠是導覽頁本身，不能拿來分類。
- `traffic_source` 用共用的 `web/lib/analytics/trafficSource.ts`（google／line／instagram／threads／facebook／twitter／direct／other），導覽呼叫時加 `{ ai: true }` 另分出 perplexity／chatgpt／claude／gemini／copilot。`record-view.ts` 改為引用但不傳 `ai`，`event_views` 的分類**完全不變**。referrer 為空但 UA 是 LINE／IG／Threads／FB in-app 時，`traffic_source` 依 in-app 判斷。
- 送出用 `navigator.sendBeacon`（失敗退回 `fetch keepalive`），每批最多 20 筆。

### 前端：導覽頁只加一段 `<script>`

不改既有程式碼，只在 `</body>` 前加一段獨立的 tracker：

- 載入時自己送第一筆 `view`（既有的 `route()` 已先執行）；之後監聽 `hashchange`。導覽的 `go()` 會改 `location.hash`（回首頁設成空字串也會觸發）；hash 相同時只是重繪，不算新 view。
- view 分類直接讀導覽的全域 `docById`、`workById`，規則與 `route()` 相同，查無資料記 home。
- `visibilitychange` 隱藏與 `pagehide` 送 `leave` 並 flush，同一段計時只送一次；回到前景或 `pageshow`（bfcache 還原）重新計時。
- delegated 監聽（bubble phase，在導覽自己的 handler 之後，結果已渲染）：`#q` 的 `input`（略過 `isComposing`、debounce 1.2 秒）、`[data-q]` chip、`[data-a]` 作者連結、`[data-lang]`、外部 `<a>`。`result_count`：`#results .empty` 存在為 0，否則數 `#results li`。
- 頁尾不新增文字；匿名統計說明之後再加（需三語文案，另開 issue）。
- 決定：**inline 而非共用 JS 檔**。`/guide-track.js` 這類根路徑會進 `proxy.ts` 被加上 locale 前綴；導覽本身也設計成可整檔搬到其他網域。下一個專題導覽複製同一段並改 `GUIDE_SLUG` 即可；若累積到 3 個以上再抽共用檔（另開 issue）。

### 後台

- 新頁 `/[locale]/admin/guides`，AdminTabNav 加「導覽工具」分頁（排在 analytics、aeo 旁）。內容（預設近 30 天、可切 7／30／90 天，`?guide=` 選導覽）：
  1. 摘要卡：sessions、views、每 session 平均 view 數、view 停留中位數
  2. 熱門 view 排行（views、停留中位數），作品／資料 ID 直接顯示，章節顯示章號
  3. 動線：入口 view 分布、最常見的「下一步」轉移（from → to 前 15）、session 長度分布（1／2–3／4–9／10+ view）
  4. 搜尋詞：前 30（次數、平均結果數）＋ 零結果詞前 20
  5. 工具與來源：device、browser、in_app、traffic_source、country 分布
  6. 外連點擊前 15、語言切換次數
  7. Search Console：落地頁 URL 以這個導覽開頭的查詢詞前 20（clicks／impressions／position）；GSC 未設定時顯示既有的未設定訊息
- 聚合由 `guide_stats()` 在 SQL 端完成（見上）；GSC 以新的 `fetchGscQueriesForPage()` 查，page filter 用 `contains`（vercel.json 的 redirect 讓收錄 URL 可能是 `/index.html`）。
- `/admin/analytics` 摘要區下方加一張「專題導覽工具」卡片：近 30 天 sessions、views，連到 `/admin/guides`。兩頁資料完全分開，只有入口互通。

### 決定與理由（依 autonomy policy 採建議值）

- **slug `guide-analytics`，一個 PR**：改動都在 web＋一個 migration，彼此相依（API 寫入新表、後台讀新表），拆 PR 反而要協調套用順序。
- **migration 編號 108**：106、107 尚未套用，但與本表無相依，可先套 108。
- **dwell 上限 30 分**：分頁開著放在包包裡會被當成停留；30 分大約是在展場看一個章節的上限。
- **search debounce 1.2 秒、只記 ≥1 字、與上一筆相同不重送**：避免每打一個字送一筆。
- **不記 IP／UA 原文**：只存分類後的 device／browser／in_app。

## 人類關卡（交使用者）

1. 在 Supabase Dashboard SQL Editor 套用 `supabase/migrations/108_guide_events.sql`（production 寫入）。**必須在合併 PR 前套用**；否則 API 會回 500（tracker 靜默失敗，不影響導覽本身）。
2. 合併 PR（預期 Tier 2：含 migration 與 web）。
3. 確認 Vercel 已有 `SUPABASE_SERVICE_ROLE_KEY`（既有，`/api/admin/*` 已在用；不新增 secret）。

## 驗證方式

- `pnpm lint`、`pnpm exec tsc --noEmit`、`pnpm build`。
- `web/tests` 單元測試：`trafficSource`（含 AI 引擎）、UA 分類、track payload 驗證（欄位白名單、長度截斷、批次上限、非法 slug 拒絕）。
- 本機 `node` 以 jsdom 或 Playwright 開導覽頁，確認 hash 切換、搜尋、外連會呼叫 beacon（不需 DB）。
- 合併後：開導覽頁走幾個 view，`select event_type, view_id, dwell_ms from guide_events order by id desc limit 20` 有資料；`/admin/guides` 顯示。

## 評審

- [plan-critique-1.md](plan-critique-1.md)（Claude 代評，Codex 未安裝，同一模型家族），處置見該檔末段。

## 每個 phase 的建議模型

- 規劃與評審：Opus high。實作、驗證、PR：Sonnet medium（本 session 由 Opus 一併執行）。
