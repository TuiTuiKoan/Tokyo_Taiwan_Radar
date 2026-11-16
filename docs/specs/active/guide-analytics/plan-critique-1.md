# Plan critique 1（2026-11-16）

> 評審者：Claude（Plan subagent，依 `.github/agents/plan-critic.agent.md` 角色）。Codex 未安裝於此環境，**同一模型家族**，不算第二視角。以下為評審全文，處置見文末。

---

> 本次批評與 Architect 使用同一模型（Codex 未安裝），不算取得第二視角。

## 總評
方向正確，非目標也劃得清楚：不引入第三方服務、不記 IP、不改既有程式碼。我對照了程式碼，主要問題有三個：leave 事件的資料模型有漏洞、聚合量估得太低、範圍偏大。商業對齊 🟡，因為它不在核心爬蟲主軸，但對現場導覽有實際價值。複雜度 medium-high，價值 medium，建議先砍到 MVP 再做。

## Must fix
1. **`leave` 缺 `seq`，dwell 會被切碎**。分頁隱藏時送出 leave，回到前景後重新計時，同一個 view 會產生多筆 leave，「每列取中位數」就失真。改法：leave 帶 `seq`，後台依 `(session_id, seq)` 先 SUM 再取中位數。hidden 和 `pagehide` 會連續觸發，必須去重，同一段計時只送一次。`pageshow` 的 `persisted=true`（bfcache 還原）時要恢復計時。
2. **view 的分類必須和 `route()` 一致**。`route()` 遇到不存在的 hash（例如 `#D1-999`、`#foo`）會 `renderHome()`，tracker 照 regex 分類就會記成 doc 或 work。兩段 classic script 共用全域 lexical scope，tracker 可以直接讀 `current`、`docById`、`workById`，用和 `route()` 相同的規則判斷，查無資料一律記為 home。
3. **hashchange 涵蓋率**我驗證過，大致成立：`go("")` 把 `location.hash` 設成空字串，仍會觸發 hashchange；`go()` 在 hash 相同時不改 hash，這只是重繪，本來就不算新 view。漏網的有兩處：初次載入要由 tracker 自己送第一筆 view（`route()` 在 tracker 之前就已執行）；`[data-a]` 作者連結用 `setQuery()` 加 `go("")` 程式化設定搜尋，不會觸發 `input`，搜尋事件會漏記，要加 `target=artist`。
4. **`trafficSource` 共用的說法自相矛盾**。計畫說「`record-view.ts` 行為不變」，但共用函式一加 AI 分類，chatgpt.com 等來源就會從 `other` 變成 `chatgpt`，`event_views` 的數字也跟著變。二選一：用參數控制，或者明寫這是刻意的行為變更。另外分類必須用 body 裡的 `document.referrer`，不能用 request 的 `Referer` header，那個永遠是導覽頁本身，會全部歸成 direct。
5. **GRANT 和 RLS 要寫死**，比照 099：`REVOKE ALL ... FROM anon, authenticated`，之後 `GRANT SELECT TO authenticated`，再 `GRANT INSERT, SELECT TO service_role`。policy 用 `TO authenticated USING ((select is_admin()))`，符合 107 的 initplan 寫法。欄位加 CHECK：`event_type` 枚舉、`guide_slug ~ '^[0-9]{6}/[a-z0-9-]+$'`、各欄位長度。
6. **GSC 沒有現成函式可用**。`fetchGscStats()` 撈的是全站前 20 查詢詞，沒有 page filter。需要新增帶 `dimensionFilterGroups`（page `contains` `/202611/synchronic-constellation`）的查詢。vercel.json 有 redirect，GSC 實際收錄的 URL 可能是 `/index.html` 那一條，所以要用 contains。

## Should
- **聚合量低估了**。「每天數百筆」說的是事件數還是 session 數？一個 session 若有 10 個 view，view 加 leave 就是 20 筆事件以上；300 sessions/天、90 天就是數十萬列。PostgREST 一頁 1000 列，等於要抓數百次。既然本來就要寫 migration，建議同時建 2～3 個 `security_invoker` view 或 RPC 在 SQL 端聚合，不要等到 5 萬列才改。
- **公開端點的濫用防護**。改走 service role 並沒有比 anon insert 更防灌，只是多了欄位驗證，計畫裡的理由別寫過頭。最低限度：檢查 `Origin` 或 `Sec-Fetch-Site`；先讀 `req.text()` 並限制大小（例如 16KB）再 `JSON.parse`，不要依賴 content-type，`sendBeacon` 送字串時是 `text/plain`；`guide_slug` 用白名單。rate limit 目前沒有現成基礎設施，可以接受不做，但要寫進 Non-Goals。
- **in-app browser 的 referrer**。LINE、IG 的 in-app browser 常常不帶 referrer。referrer 為空且 `in_app` 有值時，`traffic_source` 應該依 `in_app` 判斷，否則 LINE 會全部算成 direct。
- **IME 輸入**。日文、中文輸入在選字過程中也會觸發 `input`，要排除 `e.isComposing`，或者改在 `compositionend` 之後才開始 debounce。
- **`result_count` 的取得方式沒寫**。要指定讀 `#results` 裡哪個 DOM 節點。chip 自己的 listener 先觸發，document 上的 delegated listener 後觸發，所以讀的時候結果已經渲染好，但仍要寫進計畫。
- **排除 admin 自己的瀏覽和 dev 環境**，比照 `recordEventView` 的做法。同源請求會帶 Supabase cookie，可以只在 cookie 存在時才檢查身分。
- **UTM 是否保留**。要實測 vercel.json 的 redirect 會不會保留 query string。

## Nice
- **砍範圍**。展覽有期限，MVP 只做 view、leave、search、outbound，後台只放摘要、熱門 view、搜尋詞（含零結果）、來源和裝置。轉移矩陣、session 長度分布、語言切換、GSC、analytics 頁的入口卡片延到第二輪。
- **資料保存期限**。搜尋框輸入的是自由文字，可能含個資。建議訂保存期限（例如 180 天後刪除），並盡快補上三語匿名統計說明。
- **CSP 不是阻礙**。`connect-src` 有 `'self'`、`script-src` 允許 `'unsafe-inline'`，而且目前是 Report-Only，next.config 的 headers 也套用到 `public/` 下的檔案。同源 POST 和 inline tracker 都沒有問題，日後改成強制模式也不受影響。

---

## 處置（作者，2026-11-16）

| 項目 | 處置 |
| --- | --- |
| Must 1 leave/seq/去重/bfcache | 採納。leave 帶 `seq`；以「本段計時是否已送出」旗標去重 `visibilitychange`／`pagehide`；`pageshow persisted` 與回到前景時重新開始計時。聚合依 `(session_id, seq)` 加總後取中位數 |
| Must 2 分類與 route() 一致 | 採納。tracker 直接讀 `docById`、`workById`，規則與 `route()` 相同，查無資料記 home |
| Must 3 初次 view、`[data-a]` | 採納。tracker 載入時送第一筆 view；`[data-a]` 點擊記為 search（`target=artist`） |
| Must 4 trafficSource | 採納「參數控制」：`classifyReferrer(ref, { ai })`，`record-view.ts` 不傳 `ai`，`event_views` 行為不變。導覽一律用 body 的 `document.referrer` |
| Must 5 GRANT/RLS/CHECK | 採納 |
| Must 6 GSC page filter | 採納。新增 `fetchGscQueriesForPage(contains)` |
| Should SQL 端聚合 | 採納。migration 加 `SECURITY INVOKER` 的 `guide_stats(p_slug, p_since)` 回傳 jsonb，RLS 照常生效（只有 admin 讀得到資料）；後台一次 RPC 取回 |
| Should 濫用防護 | 採納 Origin／`Sec-Fetch-Site` 檢查、16KB 上限、`req.text()`、slug 白名單；rate limit 寫入 Non-Goals。proposal 改寫走 service role 的理由 |
| Should in-app referrer | 採納 |
| Should IME | 採納（略過 `isComposing`，`compositionend` 後重新 debounce） |
| Should result_count | 採納：`#results .empty` 存在為 0，否則數 `#results li` |
| Should 排除 admin/dev | 採納：dev 不寫；帶 `sb-` cookie 時查身分，admin 不寫 |
| Should UTM 經 redirect | Vercel redirect 預設保留 query string；合併後驗收時實測 |
| Nice 砍範圍 | **不採納**。使用者明確要求「動線、keyword research、與原統計頁的區隔或整合」，轉移、GSC、入口卡片正是這幾項；改在 SQL 聚合後成本低。語言切換只是一個 event_type，保留 |
| Nice 保存期限、匿名說明 | 開 issue：180 天保存（刪除屬 production 寫入，另案排程）、三語頁尾說明 |
| Nice CSP | 確認，無需改動 |
