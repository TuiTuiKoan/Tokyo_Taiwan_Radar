# Plan critique 1 — url-intake

- 日期：2026-11-22
- 評審者：Claude plan-critic subagent（Codex 在此環境不可用，**同一模型家族評審**）
- 對象：`proposal.md`、`tasks.md` 初稿
- 本檔為評審回覆全文（由主 session 代存；plan-critic 為唯讀角色）

---

**同一模型家族評審**：Codex 在這個環境不能用，本次評審和撰寫者都是 Claude，不算取得第二視角。本次只讀檔，沒有改任何檔案。

## 發現

1. **blocker：merger 的優先序 98 實際上會讓 url_intake 勝過多數正式來源。**
   - 證據：`merger.py:55-71` 的 `SOURCE_PRIORITY` 只列了 14 個來源，但 `scraper/sources` 約有 120 個 .py。`merger.py:1038-1039` 對沒列出的來源一律給預設值 99，所以 98 會贏過它們。
   - 另外，url_intake 不在 `_NEWS_SOURCES`（`merger.py:79`），走不到按日期加地點比對的 Pass 2（`merger.py:1132-1180`）。
   - 建議：比照 `user_submission` 加入 `_NEWS_SOURCES`，讓它永遠只當次要來源；優先序改成大於 99。

2. **major：核准閘門擋不住使用者 token。proposal 說 required reviewers 是「更強防線」，這個說法也不成立。**
   - 證據：`proposal.md:74-76`、`:88`。用同一個 token 呼叫 `actions/runs/*/pending_deployments` 就能核准部署；這個端點也不在 AGENTS.md 的 hook 阻擋清單裡。
   - 建議：spec 直接寫明殘餘風險，不要聲稱有防線。另做一個 hook patch 交使用者套用，擋下這四類操作：
     - `gh issue edit … url-intake:approved`
     - `gh api …/issues/*/labels`
     - `gh workflow run url-intake… apply=true`
     - `pending_deployments`
   - 影響範圍只有一筆列，而且可以停用，可以接受；report 留言要寫出 sender。

3. **major：設計過重。** 四個 job 加四個子命令，對「一週審一次」的需求來說太多。
   - 建議：精簡成兩個 job，`fetch`（無 secrets）和 `db`（production，負責預覽或寫入，並直接留言）。`extract-url` 併進 fetch，Playwright 第一版先不做。

4. **major：apply 裡直接呼叫 annotator，會漏步驟也會漏例外。**
   - 證據一：`annotator.py:619-648` 的 `_check_category_sync` 會丟 `SystemExit`，`finish()` 也會（`llm_client.py:337-339`）；`except Exception` 都接不住，結果 JSON 不會輸出。
   - 證據二：每日管線在標註後還會跑 `enrich_movie_titles`、`enrich_person_names`、IndexNow（`main.py:518-556`），apply 都不會做。
   - 另外，D1（`:60`）寫在程式內呼叫，流程圖（`:22`）寫 CLI，兩處矛盾。
   - 建議：最小版的 apply 只插入、保持 `pending`，交給每日的 `main.py` 處理（merger 之後接著標註和 enrich）。
   - 次要：proposal 說「與 google_news_rss 相同不解析日期」不正確，`google_news_rss.py:316` 其實有抽日期。

5. **major：查重不足。**
   - DB 裡存的 `source_url` 沒有正規化，用正規化後的 URL 比對會漏掉，要同時比對原始和正規化兩種形式，並加查 `official_url`。
   - `upsert_events` 只回傳新插入的 id（`database.py:884`）。遇到被停用、已審核、被 exclusion 擋下（`:893-921`）的情況會回傳空清單，apply 要再用 `(source_name, source_id)` 查一次，並說明原因。
   - 查既有列失敗時，`upsert_events` 只記 warning 就繼續（`:961-962`），接著以 upsert 覆寫（`:1111`）。apply 自己的查重查詢失敗時必須中止。

6. **minor：SSRF。** fetch job 沒有 secrets，所以影響有限，但還是要處理：
   - 每一跳 redirect 都重新驗證，驗證對象是 DNS 解析後的 IP（`ip.is_global`），不是 hostname。
   - 限制回應大小（約 2MB）、設 timeout。

7. **major：artifact 和頁面內容的信任邊界。**
   - 標題和正文要跳脫 markdown，中和 `@mention`、HTML 註解、偽造的 `<!-- -->` 標記。
   - `image_url` 先不寫入。
   - 正文會進 annotator prompt，有 prompt injection 的可能，要記為殘餘風險。

8. **minor：觸發條件。** 任何 label 事件都會啟動這個 workflow，每個 job 都要用 `if` 限定 label 名稱。

9. **major：測試缺口。** `test_workflow_secrets.py:76-98` 只檢查 `source-diagnose.yml`。必須補單元測試：
   - fetch job 沒有 token，只有 `contents: read`，`persist-credentials: false`。
   - 寫入 job 的 `if` 條件裡有核准條件。
   - URL 正規化和 SSRF 拒絕案例（內網 IP、redirect 到內網）。
   - artifact 驗證：型別、長度、多餘欄位。
   - 查重涵蓋原始與正規化兩種形式。
   - 留言跳脫。
   - 相關性閘門豁免 url_intake。

## 建議的最小版本

- **流程**：issue 內文放 URL；使用者貼 `url-intake:approved`，或從 Actions 執行 dispatch。
- **job 1（fetch）**：只用 requests，帶 SSRF 檢查，產出 JSON artifact。
- **job 2（db，production）**：重新驗證 artifact → 查重 → 用 `upsert_events` 寫入 `source_name=url_intake`、狀態 `pending` → 留言並關閉 issue。
- **其餘交給隔天的每日管線**：標註、enrich、IndexNow。
- **annotator 與 merger 的改動**：加入相關性閘門豁免；url_intake 加入 `_NEWS_SOURCES`，優先序改成大於 99。
- **預覽**：之後由 agent 的 skill 在本機完成，不寫進 workflow。
- **閘門**：寫明殘餘風險，並附 hook patch 交使用者套用。

---

## 處理結果（主 session 填寫）

| # | 採納 | 說明 |
|---|---|---|
| 1 | 採納 | `url_intake` 加入 `_NEWS_SOURCES`，`SOURCE_PRIORITY` 設 100（低於 `user_submission` 的 99） |
| 2 | 採納 | proposal 改寫為「殘餘風險」，刪除 required reviewers 是更強防線的說法；hook patch 屬權限與防線，另開 issue 交使用者 |
| 3 | 部分採納 | 改為 fetch／db 兩個 job、只用 requests、不做 Playwright。**保留** workflow 內的預覽：雲端 agent 常被來源站擋（#531），預覽在 Actions 跑才看得到真實頁面，且使用者週審時可直接在 issue 上看 |
| 4 | 採納 | apply 只插入 `pending`，標註、enrich、IndexNow 交給每日 `main.py`；修正 google_news_rss 的錯誤敘述 |
| 5 | 採納 | 查重比對原始與正規化 URL、`official_url`；任何查重查詢失敗即中止；upsert 後以 `(source_name, source_id)` 再查並回報原因 |
| 6 | 採納 | 自行處理 redirect（最多 5 跳），每跳以 DNS 解析結果檢查 `is_global`；回應上限 2 MB、timeout 20 秒 |
| 7 | 採納 | 留言跳脫 markdown／`@`／HTML 註解；不寫 `image_url`；prompt injection 列為殘餘風險並在預覽顯示 injection_guard 結果 |
| 8 | 採納 | job 層 `if` 限定 label 名稱 |
| 9 | 採納 | 新增 `scraper/tests/test_ingest_url.py` 與 `scripts/tests/test_url_intake_workflow.py` |
