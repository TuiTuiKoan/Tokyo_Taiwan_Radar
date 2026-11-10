# Plan Critique 3：Phase E 消化率（proposal §10）

- 日期：2026-11-10
- 評審者：Claude plan-critic subagent（雲端 session 連不到 OpenAI，`codex exec` 不可用；**與撰寫者同一模型家族**，不算第二視角）
- 對象：proposal.md §10 初稿（修訂前版本）
- 處置：見 notes.md §11

---

本次批評與 Architect 用的是同一個模型（Claude），不算第二視角。

**結論：go with changes。** E1、E6 方向對而且便宜。但 E1 的根因只對一半，E2 會把真故障蓋掉，E4 做太大。

**Blockers**
1. **E1 前提只對一半。** #608 的 10 張「取不到 production log」發生在 11-08 09:14 和 11:03 UTC。#600 到 15:22 UTC 才合併，當時 #571 的 report job 還在，而且結論是 success（run 42474068192，job 128711491089）。所以把 report job 原樣合回來，結果還是「取不到」。我用 REST 抓 scraper job log 成功（1.28 MB，含 `=== Starting scraper: <Class> ===`），所以問題出在 report job 裡面：`gh api …/logs 2>/dev/null` 把錯誤吞掉了。改法：去掉 `2>/dev/null`，把下載失敗或 class 對應失敗的原因寫進留言。驗收改成在 prtimes 實際看到 log 段落。
2. **E1 漏了 #600 的兩個回歸**（main 上的 `source-diagnose.yml`，我用 REST 比對過）：
   - (a) 跑 `main.py` 的那一步 env 帶 `GH_TOKEN`（有 issues: write），違反 D1「執行 scraper 的步驟不持有 token」。
   - (b) 不再移除 `needs-diagnosis`，而 batch 對 requested 的 issue 不檢查既有診斷，同一張會每天被重派一次。
   - 改法：兩點都在 E1 明列，並在 `test_workflow_secrets.py` 加一條檢查：跑 scraper 的 job 不能持有 token。
3. **E2 會把真故障蓋掉。** 「例外無、筆數 0」也是網站改版、selector 失效時的典型樣子。診斷沒有過濾前的筆數，「過濾邏輯可從原始碼確認」證明不了頁面還抓得到。登記之後，recovery 會依 `quiet_expected` 直接關 issue；max_quiet_days 設 180 或 365，等於半年到一年都不會告警。改法：
   - 登記條件加一條：診斷顯示過濾前 >0 筆，或 scraper_runs 過去有過零星 >0。
   - 上限 ≤120 天，不給 365。
   - 每張 PR 最多 5 條。

**Major**
4. **E2 會變成 PR 洪水。** heartbeat 每 4 小時跑一輪，「同一輪合成一張」還是會每天開好幾張改同一個 JSON 的 PR，互相衝突。改法：同時只能有一張 open 的 `chore/expectations-*`，有就跳過。這張 PR 是 tier 2（我實測 `classify(['scraper/source_expectations.json'])==2`），計畫應寫明由使用者合併。
5. **E2 的建議值表放錯地方。** 計畫說放 `.github/skills/**`，那在 heartbeat 白名單內（`heartbeat-prompt.md:17`），heartbeat 可以改這張約束自己的表。上限應該由 default branch 的 workflow 檢查 diff 來執行；至少要在 PR 說明逐條列出數值。
6. **E6 的順序其實沒有保證。**
   - 兩個 workflow 掛在同一個 completed 事件上，會同時跑，batch 會去診斷 recovery 正要關的 issue。改法：recovery 掛 Daily Scraper，batch 改掛 `Zero-output Recovery`（兩層，沒超過三層上限）。
   - `conclusion == success` 太嚴：`validate` 或 `notify` 失敗，兩個當天都不跑。改成看 scrape job 結果，或改條件為 `!= cancelled`。
   - Daily Scraper 被 GitHub 略過時兩個都不跑，要留一條保底 cron（當天跑過就不做事）。
   - #614 是延遲問題，workflow_run 解決不了，應該用 Refs，不是 Closes。
   - 以 GITHUB_TOKEN 執行 `gh workflow run` 是允許的，這個前提成立。
7. **E3 的 `<!-- home-ip-run -->` 擋不住偽造。** G1 已證實 agent 和使用者用的是同一個帳號，heartbeat 自己就能貼出同樣的標記。改法：這類留言只當參考，不能當成「可以修」的判準。
8. **E4 範圍太大，還有時序問題。**
   - PR Tier 只在 Secret Scan 完成後觸發（`pr-tier.yml:17-19`），那時 tests 和 dry-run 多半還沒跑完；新的 push 之後 `ready-to-merge` 會殘留。
   - 計畫寫「三個 ✅」，實際列了四項。
   - 建議縮成：產生 digest 時由 `weekly_digest.py` 唯讀計算是否可合併，不做 label 狀態機。
   - D3 的前提 #562、#568 都還開著。以 GITHUB_TOKEN 合併不會觸發 main 上的 push workflow（`secret-scan`、`web-*-smoke`、`eval-*`）。merge job 擴大到 tier 1 屬於「權限與防線」。
9. **E5 的數字不可靠。** 由 LLM 監控 routine 自己數，容易數錯；heartbeat 關的 issue 和使用者關的也分不出來（同一個帳號）。改法：
   - 由 workflow 或 `weekly_digest.py` 用 REST 計算。
   - 加護欄指標：recovery 關了又被重開的數量、登記為零星的來源數、revert 數。否則「淨關閉」可以靠自動關閉灌水。

**Minor**
- E1：保留 batch，刪掉 `pick_diagnose_targets.py` 和它的測試。它不檢查留言作者，在公開 repo 任何人都能貼標記擋住診斷；它也不處理 needs-diagnosis 和家用 IP 來源。
- E1：每個來源 `timeout 600`，5 個就是 50 分鐘，超過 job 的 `timeout-minutes: 45`。
- E2：v3 要同時刪掉 `heartbeat-prompt.md:20` 那句禁止，並改寫第 65 行。
- E3：issue 轉回 auto-fix 時要移除 `nh:*`。
- E4：讀 `codex-review-state` 時要限定作者 `chatgpt-codex-connector[bot]`。

**人類關卡補列**
- E1、E6 新增 `actions: read` 和 workflow_run 觸發，屬於 workflow 權限。
- E2 每一張登記 PR 都要使用者合併。
- E5：若「D1 排程每日監控」是使用者建立的排程，改它的提示詞要由使用者貼上。
- E4：擴大 merge job 的權限。

**砍掉或合併**
- 砍掉 E3 的 `triage_needs_human.py`。label 不是 production 資料，由 heartbeat 每輪補 10 張以內就好。
- E4、E5 併進 #559 的 `weekly_digest.py`。
- E1 和 E6 合成同一張 PR，避免再出現 #600 和 #571 那種平行改同一檔的衝突。
