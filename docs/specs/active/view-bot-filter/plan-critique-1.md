# Plan critique 1（2026-11-16）

> 評審者：Claude（Plan subagent，依 `.github/agents/plan-critic.agent.md` 角色）。Codex 未安裝於此環境，**同一模型家族**，不算第二視角。以下為評審全文，處置見文末。

---

本次批評與 Architect 使用同一模型家族（Codex 未安裝，改以 Claude 執行，不算第二視角）。

## 總評

方向正確，我建議修正後接受。我用 production 證據做的 83% 比對成立：Server Action POST 打的是 `/{locale}/events/{id}`，`web/proxy.ts` 的 matcher 會涵蓋它。不刪 bot 紀錄、只加標記，也不存 UA，這兩點的取捨是對的。

計畫有三個實質缺口：
- 回填只跑一次，會漏掉「套用 migration 到部署」之間寫入的資料。
- 分類結果無法事後檢查誤判。
- 熱門活動的分頁本身已經有 bug，套上篩選後數字仍然是錯的。

另外，`web/lib/analytics/botDetect.ts` 和 `visitorFilter.ts` 在計畫審查前已經寫進 working tree。以下凡提到它們，都是對照現有程式碼。

## Must fix

1. **回填有空窗，V6 會誤判。**
   - 現況：109 在合併前套用，舊程式在部署前會繼續 INSERT，這些新列全部拿到 DEFAULT `'unclassified'`，而回填只在套用當下跑一次。
   - 應該怎麼改：把回填 UPDATE 拆成可重跑的獨立 SQL，部署後再跑一次。V6 的「沒有 `unclassified` 新列」必須以部署時間為界線。

2. **`SET LOCAL` 必須包在交易裡。**
   - 現況：計畫寫了 `SET LOCAL lock_timeout = '5s'`，卻沒寫 `begin; … commit;`。在 SQL Editor 裡，沒有交易時 `SET LOCAL` 不會生效。
   - 應該怎麼改：比照 `108_guide_events.sql` 寫 `begin; set local …`。V4 要「在 rollback 交易裡跑兩次」，就必須另外放一份 dryrun 副本（先例：`docs/specs/active/supabase-advisor-hardening/dryrun/`），否則檔案自帶的 `commit` 會讓 rollback 失效。

3. **CHECK 的冪等寫法要寫清楚。**
   - 現況：`ADD CONSTRAINT … CHECK` 沒有 `IF NOT EXISTS`。
   - 應該怎麼改：把 CHECK 寫在 `ADD COLUMN IF NOT EXISTS … CHECK (...)` 裡（欄位已存在時整句跳過），或者用具名 constraint 加 `DO` 守衛。不這樣做，V4 第二次執行會失敗。

4. **熱門活動的分頁本來就壞了，計畫沒有處理。**
   - 位置：`web/app/[locale]/admin/analytics/page.tsx:194-211`。
   - 現況：pageSize 設 5000，`pageData.length < pageSizeViews` 就停止。PostgREST 預設上限是 1000，所以第一頁回來就結束，30 天熱門活動只算了前 1000 筆。`insights/views/route.ts` 已經改用 `offset += pageData.length`，這頁沒有跟上。
   - 應該怎麼改：既然本 PR 要動這段查詢，就一併修正。否則 V7「北米明顯下降」在熱門活動上無法驗證。

## Should fix

1. **分類原因要可追溯。**
   - 現況：不存 UA 可以理解，但 `suspected_bot`、`generic` 無從檢查是否誤判；中、星、港的兩週觀察也會卡在同一個問題。
   - 應該怎麼改：`bot_name` 存比對到的 token（如 `generic:HeadlessChrome`），`suspected_bot` 存原因（`no_ua` 或 `no_accept_language`）。這只是分類結果，不違反 Non-Goals。

2. **`accept-language` 規則的誤判風險偏低，但缺少監測。**
   - 現況：Chrome、Safari、Firefox 的 `fetch` 都會自動加上 Accept-Language，iOS WKWebView 和 Android WebView（LINE、Instagram、FB 的 in-app 瀏覽器）也會帶。風險在於少數隱私擴充套件和企業 proxy 會把它拿掉。
   - 應該怎麼改：V6 加一條通過標準：日本新列中 `suspected_bot` 的比例必須 ≤ 2%，超過就回頭檢討這條規則。

3. **`bot\b` 會誤傷真人手機。**
   - 現況：`GENERIC_BOT_PATTERN` 不分大小寫比對 `bot\b`。像 `CUBOT KINGKONG` 這類 Android 機型名稱會命中，被判成 `known_bot`。
   - 應該怎麼改：D5 的測試加入這類機型 UA，或把規則改為 `\bbot\b|bot/|[a-z]bot\b` 並排除機型字串。

4. **`aeo_visits` 的清理一直在失敗，回填正好依賴這個事實。**
   - 現況：`scraper/monthly_health_check.py:166` 用 `created_at` 刪除 `aeo_visits`，但這張表只有 `visited_at`（029）。清理每次都失敗，只記一行 warning，所以全期間的 ~120k 列都還在。
   - 應該怎麼改：計畫要明寫「回填在修這個 bug 之前執行」，並另開 issue 修正，否則這筆依據會被誤刪。

5. **索引 `(visitor_class, viewed_at)` 沒有必要。**
   - 現況：表只有 14.5k 列，現有讀取都以 `viewed_at` 範圍為主，既有的 `event_views_viewed_at_idx` 就夠用。
   - 應該怎麼改：刪掉這個索引，少一個寫入成本。

6. **同步點漏了文件。**
   - 現況：`.github/instructions/database.instructions.md` 寫著「Latest is 108」。
   - 應該怎麼改：把更新 migration 清單（109 的 apply 狀態與 read-back）列入計畫的必做項目。

## Nice to have

1. **回填成本和鎖定可以放心。**
   - 寫法：用 `LATERAL (… ORDER BY abs(extract(epoch from …)) LIMIT 1)`，靠 `aeo_visits_visit_type_idx (visit_type, visited_at desc)` 做 35 秒範圍掃描，再過濾 `path`。
   - 成本：14.5k 次探測，不需要新增 `path` 索引。
   - 鎖定：PG11 以後，`NOT NULL DEFAULT` 常數只改 metadata。row-level UPDATE 不會擋住 anon INSERT。
   - 但計畫要寫明：一筆 `aeo_visits` 對多筆 `event_views` 是允許的。

2. **下拉選單只需要兩個選項。**
   - 現況：四個選項（`exclude_bots`／`human`／`bots`／`all`）超出目前需求，只有「預設排除」和「全部」是 V7 實際要驗的。
   - 而且 `bots` 選項會漏掉歷史上未對上的 bot，容易誤導。
   - 建議：先只放這兩個，`human` 留到兩週觀察後再決定。

3. **V3 的通過標準是循環論證。**
   - 現況：80% 這個門檻就是從同一批資料算出來的。
   - 建議：改成抽樣 JST 白天的日本列，確認命中率 ≤ 1%，用它當真人側的反證。

4. **觀察期可以順便記錄一個訊號。**
   - 現況：每個 bot 頁面會在 `aeo_visits` 留下兩筆（GET 與 Server Action POST），AEO 儀表板的 bot 數因此偏高一倍。
   - 建議：本 spec 不改，但在觀察段落記下這點，留作日後分析參考。

5. **其他讀取者已確認沒有遺漏。**
   - 讀取 `event_views` 的只有 `admin/analytics/page.tsx`（四個 count、最近 20 筆、熱門活動）和 `api/admin/insights/views/route.ts`，`insights/events` 沒有讀它。
   - `scraper/_oneoff_clean_null_country_views.py` 只會刪除 `country` 為 null 的列，不受影響。

---

## 處置（Architect，2026-11-16）

| 項目 | 處置 |
|---|---|
| Must 1 回填空窗 | 採納。回填拆成 `backfill.sql`（可重跑），109 套用時跑一次、部署後再跑一次；V6 以部署時間為界 |
| Must 2 交易 | 109 已有 `begin; set local …; commit;`。另放 `dryrun/109_dryrun.sql`（結尾 `rollback`）供 V4 |
| Must 3 CHECK 冪等 | 已用具名 constraint＋`DO` 守衛 |
| Must 4 熱門活動分頁 | 採納，改為 `offset += pageData.length`、空頁才停，並加 `order by id` |
| Should 1 可追溯 | 採納：`bot_name` 存 `generic:<token>`；`suspected_bot` 存 `suspect:no_ua`／`suspect:no_accept_language` |
| Should 2 監測 | 採納，V6 加「日本新列 `suspected_bot` ≤ 2%」 |
| Should 3 CUBOT | 已處理（排除機型字串，測試含 CUBOT UA） |
| Should 4 `aeo_visits` 清理 | 已查證（`monthly_health_check.py` 用 `created_at`）。開 issue；spec 寫明回填必須在修正前執行 |
| Should 5 索引 | 採納，移除 |
| Should 6 文件 | 採納，同 PR 更新 `database.instructions.md` |
| Nice 1 | 回填改用 LATERAL；spec 註明一對多允許 |
| Nice 2 下拉選單 | 採納：UI 只放「排除 bot（預設）」與「全部」；API 仍接受四個值，方便日後擴充 |
| Nice 3 V3 | 採納，改用 JST 白天日本列的命中率當反證 |
| Nice 4 | 寫入觀察段落 |
