---
slug: view-bot-filter
title: 活動點擊統計（event_views）區分真人與 bot
status: active
branch: feat/view-bot-filter
created: 2026-11-16
tags: [web, supabase, analytics]
---

## What（做什麼）

讓 `event_views` 的每一筆紀錄帶上「訪客類型」，後台預設排除 bot：

1. 新增欄位 `visitor_class`（`human`／`known_bot`／`suspected_bot`／`unclassified`）與 `bot_name`。
2. `recordEventView` 寫入時依 request header 分類，bot 紀錄**照樣保留**（它也是 AEO 的訊號），只是貼上標記。
3. 舊資料以「同一路徑、相近時間的 `aeo_visits` bot 紀錄」回填為 `known_bot`；對不上的保持 `unclassified`，不推測。
4. `/admin/analytics` 的摘要數字、熱門活動，以及 `/api/admin/insights/views`（地域別、國籍別等圖表）預設只算 `human`＋`unclassified`；儀表板新增「訪客類型」篩選（排除 bot／全部）。
5. 把 `proxy.ts` 的 bot 樣式表抽成共用模組 `web/lib/analytics/botDetect.ts`，`proxy.ts` 與 `record-view.ts` 共用。`aeo_visits` 的判定行為不變。

## Why（為什麼）

2026-11-16 使用者發現儀表板「ビジター地域別閲覧数」的北米 8,934 筆異常偏高。以 production 唯讀查詢盤點：

| 證據 | 數據 |
|---|---|
| 時段分布 | 美國的瀏覽數在 JST 每個小時都落在 280–570，沒有日夜起伏；日本在凌晨 4–6 點降到每小時 8 筆 |
| 語系 | 美國：ja 3,536、en 2,425、zh 2,315，各自涵蓋 1,200 個以上活動。真人不會把同一批活動的三種語言頁都讀一遍 |
| 和爬蟲的日別相關係數（近 45 天） | Applebot 0.73、Googlebot 0.21、LLM 爬蟲 0.11、Bingbot 約 0 |
| 直接比對（全期間） | 美國 8,934 筆中有 7,447 筆（83%），在 `aeo_visits` 找得到同一路徑（`/{locale}/events/{id}`）、在寫入前 30 秒到寫入後 5 秒之間的已知 bot 請求：Googlebot 2,853、Applebot 2,333、Bingbot 1,037、Meta-ExternalAgent 828、OAI-SearchBot 377。日本 1,524 筆只對上 2 筆 |

原因：`ViewTracker` 在 `useEffect` 裡呼叫 Server Action `recordEventView`，所以會執行 JS 的爬蟲（Googlebot、Applebot、Bingbot 的渲染器）每抓一頁就寫入一筆。`proxy.ts` 已經用 `BOT_PATTERNS` 把這些請求記進 `aeo_visits`，但 `record-view.ts` 沒有檢查 user agent。Server Action 是對活動頁路徑發的 POST，同樣經過 `proxy.ts`，所以上面的比對成立。

另外，中國、新加坡、香港從 2026-09-21 起每週數百筆，幾乎都對不上 `aeo_visits`。這可能是偽裝成一般瀏覽器的爬蟲，但 `event_views` 沒有存 user agent，目前無法確認。本 spec 上線後由新的分類資料判斷（見「觀察」）。

## Non-Goals

- 不存原始 user agent 或 IP（比照 `guide_events`，只存分類結果與已知 bot 名稱）。
- 不阻擋 bot，也不改 `aeo_visits`、`robots.txt`。
- 不用滑動視窗（同活動、同國家、短時間重複）判定 bot。試算結果：120 秒窗口在美國只標出 2.9%，日本反而有 10.9%（真人會重新整理頁面），會誤傷真人。
- 不改 `event_view_counts` view（程式碼沒有讀取它）。
- 不引入第三方 bot 偵測服務。

## Design（設計）

### D1 分類規則（`web/lib/analytics/botDetect.ts`，純函式）

依序判定，第一條命中即回傳：

| 條件 | `visitor_class` | `bot_name` |
|---|---|---|
| 沒有 `user-agent` | `suspected_bot` | `suspect:no_ua` |
| 命中 `AEO_BOT_PATTERNS`（原 `proxy.ts` 的 18 條，原樣搬移） | `known_bot` | 該 bot 名稱 |
| 命中通用自動化樣式（`HeadlessChrome`、`Lighthouse`、`Puppeteer`、`Playwright`、`Selenium`、`python-requests`、`curl/`、`Go-http-client`、`axios/`、`okhttp`、`Scrapy`、`facebookexternalhit`、`Amazonbot`…，最後是 `bot\b`、`bot/`、`crawl`、`spider`、`slurp`；先移除 `CUBOT` 機型字串） | `known_bot` | `generic:<token>` |
| 沒有 `accept-language` | `suspected_bot` | `suspect:no_accept_language` |
| 其他 | `human` | null |

`accept-language` 規則的依據：瀏覽器的 `fetch`（Server Action 的傳輸方式）一律帶這個標頭，許多 HTTP 函式庫和舊版無頭瀏覽器則不帶。只當作「可疑」，不當作確定。

### D2 Migration `109_event_views_visitor_class.sql`

- `ADD COLUMN IF NOT EXISTS visitor_class text NOT NULL DEFAULT 'unclassified'`，CHECK 四個值；`ADD COLUMN IF NOT EXISTS bot_name text`。
- 不加新索引（表約 1.45 萬列，既有 `viewed_at` 索引足夠）。
- 回填：對 `visitor_class = 'unclassified'` 的列，以 LATERAL 找 `aeo_visits` 中 `visit_type = 'bot'`、`path = '/' || locale || '/events/' || event_id`、`visited_at` 介於 `viewed_at - 30s` 與 `viewed_at + 5s` 之間、時間最接近的一筆，命中就設為 `known_bot` 並填 `bot_name`。一筆 `aeo_visits` 可以對到多筆 `event_views`。
- 同一段 UPDATE 另存為 `backfill.sql`（可重跑）：**部署後再跑一次**，補標「套用 109 到部署之間」舊程式寫入的列。
- `dryrun/109_dryrun.sql`：與 109 相同，但結尾是 `ROLLBACK`，供 V4 使用。
- 回填依賴 `aeo_visits` 的完整歷史。`scraper/monthly_health_check.py` 的 90 天清理用了不存在的 `created_at` 欄位，所以一直沒刪到資料；這個 bug 要在回填完成**之後**才修（另開 issue）。
- `SET LOCAL lock_timeout = '5s'`；結尾 `DO` 區塊檢查欄位、CHECK 存在。
- 不新增表、不改 RLS 與 GRANT（欄位繼承既有表權限；anon 原本就能 INSERT 任意值，偽造 `human` 並不會比現在更糟）。
- **順序**：必須在合併 PR 之前套用。否則新程式 INSERT 不存在的欄位會失敗，而 `recordEventView` 會吞掉錯誤，造成資料靜默流失；儀表板的篩選查詢也會報錯。

### D3 寫入端（`web/app/actions/record-view.ts`）

讀取 `user-agent`、`accept-language`，呼叫 `classifyVisitor()`，INSERT 時一併寫入 `visitor_class`、`bot_name`。其餘邏輯（admin 排除、國家、來源）不變。

### D4 讀取端

- 共用模組 `web/lib/analytics/visitorFilter.ts`：`VISITOR_FILTERS = ["exclude_bots", "human", "bots", "all"]`，以及 `visitorClassesFor(filter)`，回傳 `["human","unclassified"]`、`["human"]`、`["known_bot","suspected_bot"]` 或 null（不過濾）。未知值退回 `exclude_bots`。
- `/api/admin/insights/views`：新增 `visitor` 查詢參數，預設 `exclude_bots`，以 `.in("visitor_class", …)` 過濾。
- `/admin/analytics`：摘要四個數字、最近瀏覽、熱門活動都套用 `exclude_bots`，標題下加一行說明。熱門活動的分頁原本在第一頁（PostgREST 上限 1000 列）就停止，一併修正為「依實際回傳筆數前進、空頁才停」。
- `AnalyticsDashboard`：新增「訪客類型」下拉選單，只有「排除 bot（預設）」與「全部」兩項（API 接受四個值，`human`／`bots` 兩週觀察後再決定是否開放）；三語字串加到 `messages/*.json` 的 `admin` namespace。
- `database.instructions.md` 同步更新（Latest is 109、`event_views` 欄位）。

### D5 測試

`web/tests/visitor-class.test.ts`（`node:test`，比照 `guide-track.test.ts`）：

- 真實瀏覽器 UA（iPhone Safari、LINE in-app、Android Chrome、桌機 Chrome／Firefox／Edge）＋`accept-language` → `human`
- 本次證據中的 bot（Googlebot 桌機與手機版、Applebot、bingbot、meta-externalagent、OAI-SearchBot、ClaudeBot、GPTBot、PerplexityBot、DuckDuckBot、Bytespider）→ `known_bot`，名稱與 `aeo_visits` 一致
- `HeadlessChrome`、`python-requests`、`curl`、`Go-http-client` → `known_bot`／`generic`
- 沒有 UA、沒有 `accept-language` → `suspected_bot`
- `AEO_BOT_PATTERNS` 搬移前後，`detectAeoBot()` 對同一組 UA 的結果相同（防止 `aeo_visits` 行為改變）
- `visitorClassesFor()` 四個值與未知值

加入 `package.json` 的 `test:visitor-class`，並接進 `prebuild`。

## 驗證計畫

| # | 驗證什麼 | 怎麼做 | 何時 | 通過標準 |
|---|---|---|---|---|
| V1 | 分類函式 | `pnpm run test:visitor-class` | PR 內 | 全部通過 |
| V2 | 型別、lint、i18n 一致 | `tsc --noEmit`、`eslint` 改動檔、`scripts/assert-i18n-parity.ts` | PR 內 | 無新錯誤 |
| V3 | 回填規則不誤傷真人 | 以唯讀 SELECT 模擬 109 的回填；看 JST 白天（9–23 時）日本列的命中率作為真人側的反證，並記錄美國命中率 | PR 內 | 日本白天命中率 ≤ 1% |
| V4 | migration 語法與冪等 | 本機 PostgreSQL 以最小 schema 執行 109 兩次；production 套用前在 SQL Editor 執行 `dryrun/109_dryrun.sql` | PR 內＋套用前 | 兩次都成功，第二次回填 0 列；dryrun 的統計與 V3 一致 |
| V5 | 套用後的資料 | 唯讀查詢各 `visitor_class` 筆數，與 V3 一致 | 套用後 | 誤差 ≤ 1% |
| V6 | production 寫入 | 部署後跑一次 `backfill.sql`；24 小時後查**部署時間之後**新列的分布 | 合併後 | 沒有 `unclassified` 新列；日本新列中 `suspected_bot` ≤ 2%（超過就檢討 `accept-language` 規則）；`human` 列在 JST 有日夜起伏；`known_bot` 的 `bot_name` 與同時段 `aeo_visits` 吻合 |
| V7 | 儀表板 | 開 `/admin/analytics`，切換「訪客類型」四個選項 | 合併後 | 預設下北米明顯下降（預期由 8,934 降到約 1,500）；「全部」等於現在的數字 |

## 觀察（上線兩週後）

- 中國、新加坡、香港的新列是否大多落在 `suspected_bot` 或 `known_bot`。若仍大多是 `human`，代表對方偽裝得很完整，再考慮依「每國每日看過的不同活動數」做聚合層的異常標記。
- `unclassified` 只會留在歷史資料，報表上的說明要寫清楚，那部分仍混有未識別的 bot（美國約 1,490 筆）。
- 每個會執行 JS 的 bot 在 `aeo_visits` 留下兩筆（頁面 GET 與 Server Action POST），AEO 儀表板的這類 bot 數因此偏高。本 spec 不改，留作日後分析。

## 人類關卡

| 項目 | 關卡 |
|---|---|
| 套用 migration 109（含回填，production 寫入） | 使用者，必須在合併前；先跑 `dryrun/109_dryrun.sql` |
| 部署後執行 `backfill.sql`（production 寫入） | 使用者 |
| 合併 PR（`web/`＋migration，tier 2） | 使用者 |

## 驗證結果（PR 內，2026-11-16）

| # | 結果 |
|---|---|
| V1 | `pnpm run test:visitor-class` 6／6 通過；`test:guide-analytics` 9／9 不受影響 |
| V2 | `tsc --noEmit` 通過；改動的 5 個既有檔 eslint 結果與 main 相同（沒有新增問題），3 個新檔無問題；i18n parity 1,230 keys 一致；`pnpm run prebuild` 結束碼 0 |
| V3 | production 唯讀模擬（與 109 相同的 LATERAL 條件）：日本 JST 9–23 時 1,179 筆中命中 1 筆（0.08%）；美國 8,927 筆中命中 7,440 筆（83.3%）；中國 1／1,857、新加坡 0／826、香港 0／697 |
| V4（本機） | PostgreSQL 16 最小 schema：5 個情境（窗口內、不同語系路徑、超出 30 秒、兩個候選取最近、非 bot）結果正確；第二次執行與 `backfill.sql` 重跑都沒有變更；`dryrun/109_dryrun.sql` 結尾 rollback；CHECK 擋下非法值。production 的 dryrun 留待套用前（人類關卡） |
