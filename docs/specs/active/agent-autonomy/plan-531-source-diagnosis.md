# Plan：#531 讓 heartbeat 能修「0 產出」來源（診斷前移到有網路的環境）

建議模型：規劃與評審 Opus high；實作 Sonnet medium。狀態：草案，等使用者核准兩個關卡（見「人類關卡」）。

## 問題

heartbeat 的雲端 sandbox 對外部網站的 CONNECT 被 proxy 回 403，無法 dry-run。約 30 張「0 產出」auto-fix issue 因此都只能轉 needs-human。

## 決定（採建議值）

不放寬 sandbox 網路（新增外部連線、攻擊面變大）。改為：**GitHub Actions 有網路，負責診斷；heartbeat 沒網路，負責讀診斷結果後修程式。** 理由：`scrape-now.yml` 已證明 runner 能連來源網站，只缺一個「唯讀、不寫 DB、結果貼回 issue」的診斷入口。

## 設計

1. 新 workflow `source-diagnose.yml`（`workflow_dispatch`，input：`sources`、`issue`）
   - `permissions: contents: read, issues: write`；**不給任何 Supabase／OpenAI secrets**，只能跑 `--dry-run`。
   - 對每個來源執行 `python main.py --dry-run --source <s>`，收集：筆數、例外與 traceback、對來源入口 URL 的 HTTP 狀態與回應大小、前 5 筆標題；若 0 筆，額外記錄被關鍵字過濾丟棄的前 5 個候選標題（需在診斷模式印出，見步驟 3）。
   - 以 `gh issue comment <issue>` 貼上固定格式的留言，開頭標記 `<!-- source-diagnose -->`，方便 heartbeat 辨識。
2. 觸發方式
   - 第一階段：使用者或 `workflow_dispatch` 手動觸發（一次 5 個來源）。
   - 第二階段（試做成功後）：`daily-health-check` 或 `scraper-quality` 偵測到 0 產出 issue 時自動觸發，每天上限 5 個來源，避免耗盡 Actions 分鐘數。
3. 診斷輸出：`scraper/sources/base.py` 目前無統一的「被過濾候選」紀錄；先不改 base，只在 workflow 內用 `logging` 層級 DEBUG 擷取現有 logger 輸出。若資訊不足，再開 issue 為各來源補 log（屬 `scraper/sources/**`，heartbeat 可做）。
4. heartbeat 提示詞調整（patch 給使用者套用，因 AGENTS.md 禁止自改提示詞）
   - 取「原因未知」類 issue 前，先找 `<!-- source-diagnose -->` 留言；沒有就跳過並記一次，不重試；有就依診斷修。
   - 取件前先 `curl -m 10 https://example.com`，不通就把所有網路相依 issue 一次性跳過。

## 里程碑

- [x] M1 使用者 2026-11-07 口頭授權新增 workflow，不需再問
- [ ] M2（已實作 `source-diagnose.yml`，合併到 main 後才能 dispatch；尚未執行）實作 `source-diagnose.yml`，對 #459、#460 各跑一次，診斷留言貼回 issue
- [ ] M3 heartbeat 讀到診斷後修好至少一張並開 PR（驗收）
- [ ] M4 提示詞 patch 套用；評估自動觸發

## 人類關卡

| 關卡 | 內容 |
| --- | --- |
| 權限與防線 | 新增 `.github/workflows/source-diagnose.yml`、heartbeat 提示詞 patch |
| 花錢 | Actions 分鐘數：每來源約 1–3 分鐘，上限 5 個來源／天，估計可忽略 |

## 風險

- 診斷 workflow 能連外網，但無 secrets、無寫入，風險低；留言內容來自外部網站標題，須當作不可信資料，heartbeat 只可當症狀參考，不得照做其中指令。
- 部分來源擋 GitHub runner IP（資料中心 IP）：診斷會顯示 403/空回應，此時結論是「需家用 IP」（見 #407），轉 needs-human，不是程式 bug。
- Playwright 來源需安裝瀏覽器，單次較久；第一階段先挑 requests 型來源（prtimes、waseda_taiwan）。

## NOT TESTED

尚未實作或執行任何 workflow；本檔只是計畫。

Refs #531

## 更新 2026-11-08：自動排程

`source-diagnose.yml` 加上每日 03:30 UTC 的 `schedule`。排程模式由 `scripts/pick_diagnose_targets.py` 挑最多 5 個「開著、帶 scraper＋auto-fix、標題為 `<來源>：…0 產出…`、尚無 `<!-- source-diagnose -->` 留言」的 issue（舊到新、一來源一張），逐一 dry-run 並把診斷貼回各自的 issue。沒有目標時跳過安裝與執行。約 33 張待診斷，7 天內跑完，之後新增的 issue 自動補上。手動 `workflow_dispatch` 保留。
