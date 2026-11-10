---
slug: agent-autonomy
title: 自主開發迴路：細節採建議值、PR 是人類關卡、issue 到 PR 的 heartbeat
status: active
branch: feat/agent-autonomy
created: 2026-10-25
tags: [governance, agents, tooling, infra]
---

## What（做什麼）

把開發流程的預設從「每個細節問使用者、每次推送由使用者貼指令」改成「agent 依建議值自己決定並留下紀錄，只在少數人類關卡停下」。三件事：

1. **自主程度政策**。寫進 `AGENTS.md` 與 `.github/copilot-instructions.md`。設計細節、worktree 選擇、模型選擇、試做參數一律採建議值（通常是「最小範圍試做，觀察幾天再擴大」）；只有「人類關卡」清單上的動作才停下來問。Claude 規劃完成後自動以 `codex exec` 交給 Codex Plan Critic 評審，不再請使用者手動開 Codex session；規劃與實作都留在 Claude，模型等級依 tier 與成本選。
2. **推送改走 PR**。沿用 `pr-flow-tiering` 已上線的三層：agent 自己推 feature branch、開 PR；Tier 0 自動合併，Tier 1 使用者一鍵合併，Tier 2 使用者看過再合併。V-M-D 不再產生要使用者貼到終端機的 push 指令。
3. **issue 到 PR 的 heartbeat**。使用者（或 CI 失敗通知）開 issue 之後，排程的 agent 每天數次自動分類、挑一張可自動修的 issue、在隔離分支修好、推上去開 PR。使用者只做兩件事：驗證結果（看 PR、看網站、看資料）；覆核不精準的輸入（分類錯、修錯、範圍判斷錯），開 issue 或在 PR 留言。

## Why（為什麼）

- **使用者 2026-10-25 的指示**：非軟體專業，多數決定仰賴預設建議；不想被每個細節問；規劃後交 Codex 不必每次問；推送不想一個一個貼終端機；平行的大量 bug fixing 已淹沒人力；希望自己只做驗證與覆核不精準的輸入，其餘由 agent 經 heartbeat 全天自動開發與推送。
- **安全網已經在了，剩下的人工步驤是習慣不是防線**。`pr-flow-tiering` Phase D 完成：hook 放行推 feature branch、推 main 要核准（notes B5）；PR Tier workflow 在 gitleaks 之後分類，Tier 0 自動合併已實測（PR #307、#308）；auto mode 分類器與 hooks 擋 production 寫入、`.env`、force push。既有規則卻仍要求「問 worktree」「使用者貼 push 指令」「使用者手動開 Codex」。
- **規模**：2026-10-25 有 15 個 linked worktree、69 張 open issue、十多個 active spec。單一使用者無法逐一追蹤；需要 WIP 上限與自動收尾。
- **資料側已有 heartbeat**（`qa-heartbeat.yml`、`error-recovery.yml`、`workflow-failure-notify.yml`），開發側沒有。issue 開了之後要等人開 session 才會動。

## Non-Goals（不做什麼）

- 不放寬任何現有 deny：force push、刪遠端 ref、`.env` 讀寫、production DB 寫入、`git reset --hard`。
- 不讓 agent 修改 `.claude/settings.json`、`scripts/claude/` hooks、GitHub repo 設定與 secrets；仍由使用者套用（分類器以 Self-Modification 拒絕，見 memory 2026-10-22）。
- 不自動合併 Tier 1、Tier 2 的 PR；合併按鈕是使用者的。
- 不把需要人工判斷的輸入自動化：annotation 人工標記、ground truth、活動範圍（in／out of scope）判斷、SNS 發文。
- 不做 Orca、plugin、模型分級（`ai-harness`），不做 worktree 自動退役（`closer-auto-retire`）。
- 不取代 `pr-flow-tiering` Phase E 的量測；量測照常記錄，只是不再阻擋 PR 流程成為預設。
- 第一輪 heartbeat 只處理 Tier 1 路徑能涵蓋的 issue（單一 `scraper/sources/<x>.py` 與其 skill、tests）；`web/`、`supabase/`、annotator、workflows 不在自動修範圍。

## Design（設計摘要）

### 1. 自主程度政策

寫進 `AGENTS.md`「自主程度與人類關卡」一節（Copilot 版在 `.github/copilot-instructions.md`），所有 agent 自動遵守：

| 類型 | agent 怎麼做 |
| --- | --- |
| 設計細節、slug、worktree、模型、試做參數、小範圍取捨 | 採建議值，把決定與一句理由寫進 spec 的 proposal 或 issue，不問 |
| 規劃完成後的 Plan Critic 評審 | 自己執行 `codex exec`（§3），不問 |
| 規劃與實作用哪個模型 | Claude 的 agent 依 tier 與成本選（§3），不交 Codex 實作，不問 |
| 推 feature branch、開 PR、建 issue 與 label、建 worktree | 自己做，回報裡一句話說明 |
| 人類關卡（下表） | 停下，依 handoff 規則交一張卡片 |

人類關卡（窮舉；不在表上的不問）：

| 關卡 | 為什麼留給人 |
| --- | --- |
| 合併到 `main`（Tier 1、Tier 2 的 PR 合併按鈕）；直接 push main | production 部署；Tier 0 除外 |
| production 資料寫入：Supabase 非 dry-run 寫入、migration apply、annotator live、`qa_auto_fix` live | 不可逆或難回滾 |
| 權限與防線：`.claude/settings.json`、`scripts/claude/`、hooks、GitHub repo 設定、rulesets、secrets、workflow 權限 | agent 不得改自己的限制 |
| 不可逆動作：刪遠端 branch、移除含未推 commit 的 worktree、刪資料 | 無法復原 |
| 花錢或新增外部服務、帳號、API key；提高排程頻率到可能耗盡配額 | 成本是使用者的 |
| 需要人類判斷的輸入：annotation、ground truth、範圍判斷、分類定義 | 這是使用者的核心工作 |
| 對外發布：SNS 貼文、公開公告 | 代表專案發言 |

使用者的角色因此只剩兩件：**驗證**（PR、網站、資料）與**覆核不精準的輸入**（開 issue、PR 留言、改 label）。

### 2. 推送與合併

```
worktree 內 commit → rebase origin/main → git push -u origin <branch>（hook 放行）
→ gh pr create（body 含驗證證據、Refs/Closes #n、label spec:<slug>）
→ PR Tier workflow（gitleaks 之後）貼 tier:N
   tier:0 → 自動 squash 合併 → V-M-D 查 merge commit 的部署
   tier:1 → 使用者一鍵合併（之後加 LINE 推播，#issue）
   tier:2 → 使用者看 diff／Vercel preview 後合併
→ 合併後 V-M-D 以 merge commit SHA 做部署驗證（squash 會產生新 SHA）
```

- `pr-flow-tiering` 的 D1（是否放棄「無 PR 閘門」文字）由本 spec 承接：**PR 流程從 2026-10-25 起是預設**；使用者仍可自己直接 push main，agent 不提議也不執行。D2 維持 `ttr-<slug>-worktree`；D3 Tier 0 範圍不變。
- V-M-D agent 檔 Step 4 改為「自己推 branch、開 PR、等合併」；Step 5 以 merge commit 驗證。推 main 的指令不再出現在交接卡片。
- 新建 worktree 後 `git branch --unset-upstream`，避免無參數 `git push` 推到 main（沿用 `pr-flow-tiering` Phase 0 的做法）。
- `.claude/settings.json` 不需改：推 feature branch 已不提示（notes B5）。

### 3. Codex 只做 Plan Critic；規劃與實作留在 Claude，模型依 tier 與成本

使用者 2026-10-25 釐清：Codex 的用途只有 Plan Critic（不同模型家族的評審視角）；開發與規劃都用 Claude。規則寫在 `AGENTS.md`：

- 評審：Claude 規劃完成後自己執行 `codex exec -p plan -s read-only -o docs/specs/active/<slug>/plan-critique-N.md "<提示>"`，不再請使用者開 Codex；全文必須存檔（既有規則）。Codex 啟動失敗時改用 Claude 的 plan-critic 評審，報告註明同一模型家族。
- 規劃與實作：architect、engineer、scraper-expert、designer、tester、validate-merge-deploy 都是 Claude 的 agent。subagent 的模型由 `tier` 投影（plan→Opus high、build→Sonnet medium、grunt→Haiku low，見 `ai-harness`）；主對話依「執行前的模型評估」選最便宜夠用的等級，Fable 只在跨 phase 架構規劃或 Opus 卡關時用。這些選擇是細節，agent 自己決定並在回報開頭說明，不問。
- 不用 Codex 實作，也不把 Codex cloud 當 heartbeat 的執行者。

### 4. Heartbeat：issue 到 PR

**Runner 選項與採用**

| 選項 | 配額歸屬 | 優點 | 缺點 |
| --- | --- | --- | --- |
| A. Claude Code 排程雲端 agent（routine） | Claude 訂閱 | 本 session 就能建立；讀同一份 `AGENTS.md`；可 push branch、開 PR | hooks 在雲端 session 的行為、配額歸屬 NOT TESTED |
| B. Codex cloud 的 GitHub 整合 | ChatGPT 訂閱 | 第二個配額池 | 開發不用 Codex（使用者 2026-10-25 釐清）；不採用 |
| C. GitHub Actions 跑 agent CLI | API 計費 | 完全在 repo 內 | 要 API key，與「成本＝配額」衝突；不採用 |
| D. 家用 Mac launchd | Claude 訂閱 | hooks 完整 | 依賴 Mac 開機（#407 同類問題）；不採用為主線 |

**採用 A。** 理由：不需使用者動手，規則與安全網和本 repo 一致，開發留在 Claude。配額壓力由模型等級控制：heartbeat 的修 scraper 屬 build tier（Sonnet medium），分類屬 grunt tier（Haiku low）。

**一次執行的流程**（提示詞草稿在 [heartbeat-prompt.md](./heartbeat-prompt.md)）

1. 分類：讀沒有 `spec:` label、沒有 `auto-fix`／`needs-human` label 的 open issue。單一來源故障且可用 Tier 1 路徑修 → 貼 `auto-fix`；否則貼 `needs-human` 並留言說缺什麼。帶 `spec:` label 的 issue 不碰，那是該 spec session 的工作。像 #381 這種「30 個來源 0 產出」的總表 issue → 拆成每來源一張子 issue（主題「來源健康」），一次最多 5 張。
2. 取件：open 的 `auto-fix` issue 中最舊、且沒有 open PR 關聯的一張。同時 open 的 heartbeat PR 已達 2 張 → 本次只做分類。
3. 修：分支 `fix/issue-<n>`，依 `AGENTS.md`、scraper instructions 與該來源 skill 修改；跑 `scraper/tests`；dry-run 只對不需憑證的來源有效（D4'），其他寫 NOT TESTED。
4. 交付：`git push -u origin fix/issue-<n>`、`gh pr create`，body 含「改了什麼、怎麼驗證、NOT TESTED、`Closes #n`」，label `auto-fix`、`scraper`。在 issue 留言附 PR 連結。修不動 → 不開 PR，在 issue 留言寫到哪、缺什麼，改貼 `needs-human`。
5. 不做：不碰 Tier 2 路徑；不 push main；不 `gh pr merge`；不寫 production；不改自己的提示或 workflow。

**限制與停止條件**

- 每 8 小時一次；每次最多 1 張 issue；同時最多 2 張待合併的 heartbeat PR。（2026-11-07 現況：每 4 小時、每次最多 2 張；待合併上限分爬蟲類 6 張、腳本文件類 1 張，滿額時在 #528 通知。見 notes §5）
- 任一 heartbeat PR 合併後被 revert → 停用排程，開 issue 檢討。
- 連續 2 張 PR 被使用者關閉不合併 → 停用排程。
- 排程因配額限制失敗 2 次 → 停用排程，降頻後再議（成本是人類關卡）。
- 試做 7 天後盤點（§6）。

### 5. WIP 與收尾

- merged branch 自動刪除已開（repo 設定；Tier 0 用 `--delete-branch`）。
- 本機 worktree 的退役仍走 `closer-auto-retire`（暫停中，恢復條件見 #345）；本 spec 不自動刪 worktree。
- 新 worktree 由 agent 自建，但同一 spec 只有一個；heartbeat 在雲端不建本機 worktree。

### 6. 試做範圍與停止條件

| 階段 | 範圍 | 成功 | 停止 |
| --- | --- | --- | --- |
| Phase A（本 PR） | 政策文字與 V-M-D 改寫 | PR 以新流程交付（agent 推 branch、開 PR、使用者合併），測試全綠 | 使用者在 PR 否決任何一項預設決定 → 改文字再提 |
| Phase B（合併後 7 天） | 排程雲端 agent，第一次只分類，之後每次最多 1 張 Tier 1 issue | 至少 1 張 heartbeat PR 經一鍵合併，且下一次 scraper 執行該來源有產出；人工步驟只剩「按合併」 | §4 的任一停止條件 |
| Phase C | 合併後驗證迴路自動留言；Tier 1 LINE 推播；heartbeat 分類段降到 Haiku | 一張 PR 從 issue 到合併到驗證全程無人工步驤 | 配額曲線惡化 |

### 7. 本 spec 預設採用的決定

依新政策，下列決定直接採用；使用者在本 PR 的 review 留言即可否決，不必另開會議。

| # | 決定 | 採用值 |
| --- | --- | --- |
| A1 | PR 流程是預設（承接 pr-flow-tiering D1） | 是；直接 push main 只留給使用者 |
| A2 | worktree 由誰決定 | agent 自選自建並回報；路徑慣例不變（D2） |
| A3 | Tier 0 範圍 | 不變（D3） |
| A4 | heartbeat runner | Claude Code 排程雲端 agent；不用 Codex |
| A5 | 節奏與上限 | 每 8 小時、每次 1 張、同時 2 張待合併（2026-11-07 改為每 4 小時、每次 2 張、爬蟲類 6 張／腳本文件類 1 張；notes §5） |
| A6 | 分類範圍 | 只碰沒有 `spec:` label 的 issue |

### 8. Phase D：週審節奏下的全自動開發迴路（2026-11-07 起）

**使用者 2026-11-07 的指示**：一週大約只有一個早上能審 PR；希望 agent 逐日自動驗證、排查、開發、推送。建議模型：規劃與評審 Opus high；workflow 與腳本實作 Sonnet medium。

**問題（2026-11-07 盤點）**

- 節奏不對稱：heartbeat 每 4 小時產出，合併每週一次。上限一滿（爬蟲類 6、腳本文件類 1），其餘時間只分類不修（notes §5）。
- 證據缺口：sandbox 連不到來源網站（#531）。`source-diagnose.yml` 已上線但只能手動觸發；PR 本身沒有「修復前後筆數」，使用者審 PR 時要自己判斷。
- 配額佔用：重複 PR（#488／#526 同修 #445）、久未合併 PR 佔住名額（#532）。
- 已自愈的 issue 沒人關：「0 產出」issue 的來源恢復後，issue 仍佔著 heartbeat 的取件佇列。

**四個改造**（D1、D2、D4 新增 workflow 權限與使用 secret，屬「權限與防線」，以 tier 2 PR 交使用者合併；D3 是治理決定，裁決前不實作）

| # | 改造 | 內容 | 人類關卡 |
| --- | --- | --- | --- |
| D1 | 證據工廠 | ①`source-diagnose-batch.yml`：每日挑最多 5 張還沒有 bot 診斷留言的「0 產出」issue（或貼了 `needs-diagnosis` 的），dispatch `source-diagnose.yml`；`source-diagnose.yml` 改為共用解析器、顯示被吞掉的例外、執行 scraper 的步驟不持有 token、成功或失敗都留一則 bot 留言並移除 `needs-diagnosis`（涵蓋 #538）；②`pr-dryrun-evidence.yml`：改到 `scraper/sources/**` 的同 repo PR，在 Actions 上對 base 與 head 各跑一次 dry-run，留言修復前後筆數與判讀；③`zero-output-recovery.yml`：每日以每週報表同一套判定（`classify_output`＋`source_expectations.json`）找出已恢復、季節外或零星預期內的「0 產出」issue，附數據留言並關閉，每次最多 5 張 | 權限：batch `actions: write`＋`issues: write`；diagnose `issues: write`；evidence `pull-requests: write`（只在不跑 PR 程式碼的 job）；recovery `issues: write`＋`SUPABASE_SERVICE_ROLE_KEY`（只 select）。dry-run 都不帶 secrets、不寫 production |
| D2 | 配額衛生 | heartbeat 提示詞 v2（[heartbeat-prompt.md](./heartbeat-prompt.md)，2026-11-07 啟用）：「0 產出／原因未知」類 issue 先看診斷留言，沒有就貼 `needs-diagnosis` 跳過；盤點時以 `Closes #n` 去重；open 超過 14 天的 PR 在 #528 列為「建議關閉或重開」；PR body 引用診斷與 dry-run 證據 | 提示詞由使用者貼到 routine |
| D3 | 證據門檻自動合併 | 前提：F8（pull_request workflow 帶 production secrets，#561）與 F9（`pr_tier` 把共用模組判為 tier 1，#562）先修好。門檻：tier 1、測試綠、D1② 是「修復前 0 → 修復後 >0」（修復前已有產出的 PR 不適用，見 prtimes #538）、無例外、未暴增、無同檔 PR → 自動合併；先圈 3–5 個來源試行兩週 | **使用者裁決 go／no-go**，裁決前不實作 |
| D4 | 週審 digest | 週五晚把待審 PR 整理成一張清單（稽核區／一鍵合併區／判斷區／回收區），使用者一個早上處理完；週日收尾 | 新增 workflow（tier 2 PR） |

**與既有工作的關係**：D1 一併改 `source-diagnose.yml`（評審 F3、F14、F15），#538 的標題欄位修正因此被涵蓋；#450（合併後驗證迴路）看的是已合併 PR 的來源，D1③ 看的是 open issue，兩者互補；#545（失敗訊號 intake）負責把 CI 失敗變成 issue，D1 負責讓這些 issue 有證據可修。上限沿用 notes §5 的爬蟲類 6／腳本文件類 1，不改。

**預設採用的決定**

| # | 決定 | 採用值與理由 |
| --- | --- | --- |
| D-a | 診斷批次的量 | 每日最多 5 個來源（plan-531 第二階段的上限）；Actions 分鐘數每來源 1–3 分鐘 |
| D-b | dry-run 證據帶不帶 secrets | 不帶，與 source-diagnose 一致。需要憑證的來源顯示失敗，記 NOT TESTED。判讀以 stderr 的 `scraper failed:` 為主：`main.py` 吞掉例外後仍 exit 0（評審 F1） |
| D-c | PR 程式碼在哪個 job 跑 | 跑 PR 程式碼的 job 只有 `contents: read`；留言由另一個不 checkout PR 的 job 用 artifact 貼上 |
| D-d | 復原偵測是否直接關 issue | 關，但只在每週報表的同一套判定（`classify_output`＋`source_expectations.json`，120 天資料）不再把來源列為待處理時：`active`、`off_season`、`quiet_expected`。最近一次執行失敗（`failing`）不關。每次最多 5 張；手動執行預設 dry-run；曾被關又被人重開的不再關。緊急停止用 `gh workflow disable`，不依賴 repo variable（評審 F6、F11） |
| D-e | 14 天未合併的 PR | 仍算入上限（不擴大 WIP），只在 #528 標示，由使用者週審時關或重開；Closes 對象已關閉的孤兒 PR 不計入上限（評審 F18） |
| D-f | D1② 是否延到第二批（評審建議延後） | 不延後：使用者 2026-11-07 指示本次實作 D1 的三個 workflow。評審指出的 F10（數來源而非模組、300 秒、artifact 一定上傳）、F7（修復前已有產出時不給綠勾）、F9（共用模組標為未測）已一併處理 |
| D-g | `source_expectations.json` 是否加進 heartbeat 白名單（評審 F5 建議加） | 暫不加：改它會觸發 `scraper-quality.yml` 以 service role key 執行 PR 程式碼（F8）。F8 修好前，heartbeat 轉 needs-human 並附建議 JSON 片段；修好後再開白名單與 expectations 批次 PR |

**驗收**

- D1：至少一張「0 產出」issue 經批次診斷後由 heartbeat 開出 PR（#531 的驗收標準）；復原偵測第一次執行的處理數寫進 notes。
- D2：14 天內不再出現同一 `Closes #n` 被重複計數。
- D4：使用者一次週審 ≤90 分鐘。
- 14 天盤點：每週關閉的 issue 數、PR 中位等待天數、revert 數，寫進 notes.md。

### 9. Phase D5：第二車道——使用者核准、agent 實作（2026-11-07 起）

**使用者 2026-11-07 的指示**：把 heartbeat 不碰的 issue 也納入自動開發；同時處理 #459／#460（「dry-run 正常、production 0」）與母 issue #367、#381 的收尾。建議模型：規劃與評審 Opus high；runner 實作 Sonnet medium。評審見 [plan-critique-2.md](./plan-critique-2.md)。

**盤點（2026-11-07，open issue 134 張）**：會自動前進的只有 38 張（0 產出 33、其他 auto-fix 5）；needs-human 28、spec 底下 60、新來源申請 6、系統用 2，共 94 張沒有自動車道。heartbeat 白名單刻意排除 `main.py`、`web/`、`supabase/`、workflow，且不碰 spec issue 與 source-intake。缺的是「使用者核准過的範圍」。

**核准管道：與「合併到 main」是同一道防線，不比它強**（評審 G1，已實測）

- 雲端 agent 的 issue、留言、label、**合併**動作都以使用者帳號 TuiTuiKoan 進行（`performed_via_github_app` 為空），API 上和使用者本人無法區分；看板（Projects V2）在雲端 session 讀寫都被擋。所以 label 與留言不能當核准。
- 核准清單放在 main 上的 [lane2-approved.yml](./lane2-approved.yml)，經 tier 2 PR 由使用者合併。這和「production 部署要使用者合併」是同一道關卡。
- 但這道關卡目前**只有文字規則**：main 沒有 branch protection（`protected: false`，唯一的 ruleset 是 disabled），hooks 只解析 `git push`，`gh pr merge`、`gh api` 寫入 main、GitHub MCP 的合併與寫檔工具都沒有規則。被 prompt injection 的 agent 可以自己合併或直接寫檔。lane2 沒有降低門檻，但也沒有補強；而 runner 每天讀大量 issue 內容，攻擊面比 heartbeat 大。
- 所以 **runner 的排程在下列前提完成前不建立**（各自開 issue）：
  1. 合併與寫 main 的防線：bash guard 擋 `gh pr merge` 與 `gh api` 寫入 `pulls/*/merge`、`merges`、`contents/`、`git/refs`、`git/commits`、`rulesets`、`branches/*/protection`；`mcp__github__.*` 的合併、寫檔類工具加 PreToolUse matcher；是否開 main 的「require pull request」ruleset 由使用者決定。屬「權限與防線」，以 patch 交使用者套用。
  2. production secrets 只給 main：#561 擴大為把 secrets 移到只允許 `main` 的 GitHub Environment，並請使用者確認 Vercel Preview 不含 production 的 service role key（G5）。
  3. 核准檔的夾帶防線：`pr_tier.py`／`pr-tier.yml`（workflow_run，PR 改不了它）偵測「改了 `lane2-approved.yml` 又改其他檔」與 YAML 格式錯誤，貼 `lane2-approval-mixed`／`lane2-approval-invalid` 並留言；回歸測試鎖定這個檔是 tier 2（G3、G21）。
  4. D1 四個 workflow 第一次在 Actions 上執行的結果寫進 `notes.md`。

**流程**

1. **週五提案 PR**：runner 挑「3 減去仍未消耗的已核准條目數」筆（至少 1、最多 4；前兩週最多 3），只改 `lane2-approved.yml`，貼 `lane2-proposal` label。開出後不再推 commit（使用者合併的必須是他看過的版本）。
2. **週六週審**：使用者在 PR 的網頁編輯器刪掉不核准的條目、填 `answer`，然後合併。不合併＝不核准。
3. **週日、週一、週二實作**：每天最多 1 筆，open 的 `lane2` PR 上限 3。其他日子 runner 不做事（省配額，也避免週審當天有新 PR）。
4. **evaluate（新來源評估）不需核准**：只在 issue 留言，屬 agent 本來就能做的事；每天最多 1 張。implement 段仍要核准，且「這個來源在範圍內嗎」由使用者親手填 `answer`（G12）。

**runner 的界線**（禁止路徑優先於條目的 files：核准也不能放寬）

| | 可以 | 不可以 |
| --- | --- | --- |
| 路徑 | `scraper/**`（含 `main.py`）、`web/**`、`scripts/**`、`docs/**`、`.github/skills/sources/**` | `.github/workflows/`、`.claude/`、`scripts/claude/`、`scripts/ci/`、`scripts/sync_ai_adapters.py`、`.codex/`、`.agents/`、`AGENTS.md`、`CLAUDE.md`、`.github/copilot-instructions.md`、`.github/agents/`、`.github/instructions/`、`.github/skills/agents/`、`docs/specs/active/agent-autonomy/`（含核准檔與提示詞）、`supabase/migrations/`（第一輪不開放：合併後 web 先部署、migration 未套用的空窗會讓 production 出錯，G9）、任何 `.env` |
| 觸發帶 secrets 的 pull_request workflow 的路徑 | 前提 2 完成前不碰；清單在實作當下從 main 的 `.github/workflows/*.yml` 算出，不手抄（G5） | — |
| 依賴清單 | `scraper/requirements.txt`、`web/package.json`、lockfile 只在條目明列且 risk ≥ medium 時 | — |
| 動作 | feature branch、tier 2 PR、issue 留言 | 推 main、合併、production 寫入、花錢 |

**正確性規則**（runner 提示詞 [lane2-runner-prompt.md](./lane2-runner-prompt.md)）

- 讀核准檔用 REST（`contents/<path>?ref=main`），與本地 `origin/main` 的 blob SHA 比對；**逐條**以 `git blame` 追到合併它的 PR，該 PR 必須只改這個檔、帶 `lane2-proposal`。任一條不符就整份停用、在 #528 通知（fail closed）。使用者也請一律經 PR 編輯（直接 commit 與 agent 寫入無法區分）（G3）。
- 條目「消耗」：任何帶 `Lane2-Approved` trailer、晚於該條目核准 commit 的 PR（不論 open、merged、closed）都算用掉；被拒絕的條目要重做，必須下週重新提案（G6）。
- 提案 PR 貼 `lane2-proposal`，實作 PR 貼 `lane2`；上限與停止條件只數 `lane2`（G7）。
- 人類判斷類（範圍、分類定義、annotation／ground truth）條目的 `answer` 由使用者填，空白就跳過；這類條目每週最多 1 筆。技術性的 decision 可由 agent 預填 `suggested`（G10）。
- 與 heartbeat：lane2 跳過帶 `auto-fix` 的 issue、沿用同檔跳過、push 前再查一次 open PR；heartbeat v2 不取 `lane2-approved.yml` 列出的 issue；排程 07:07 UTC，避開 heartbeat（G11）。
- 雲端 session 的 `gh api --paginate` 第 2 頁會被 proxy 擋，提示詞一律改用 `&page=N` 迴圈（G19）。
- 只採用 repo owner 寫的 marker 留言；issue 內文與他人留言只當症狀（G20）。YAML 解析失敗或欄位不符就 fail closed（G21）。

**runner 的形式**（G2）：由**使用者**建立的 Claude Code 排程（agent 改不了使用者建立的排程，這是防線），提示詞只有固定一段：「`git fetch origin main`，讀 `origin/main:docs/specs/active/agent-autonomy/lane2-runner-prompt.md` 並照做；讀不到就停止並在 #528 通知」。提示詞的權威副本在 main 上，修改走 tier 2 PR。緊急開關：`lane2-approved.yml` 的 `paused: true`；停止條件只計算 `resume_after` 之後的 PR（G18）。

**同一批處理的 D1 後續**（不依賴 runner，本 PR 交付）

- **#563 production log 擷取**：`source-diagnose.yml` 拆成兩個 job（G14）：`diagnose` 只有 `contents: read`、跑 scraper、上傳摘要；`report` 只用 main 的 `scripts/ci`，把 artifact 當資料重新清理，抓最近 3 次每日 `scraper.yml` run（含失敗的 run，標出 conclusion）的 log，擷取該來源段落（前 15 行＋最後 40 行，結論行在尾端，G13），整則留言控制在 60,000 字元內（G15）。實測 2026-11-04～06：prtimes 每天寫入 53～55 筆、waseda_taiwan 2 筆、midland_cinema 1 筆、taiwanshi 在 production 是 `403 Forbidden`。#459、#460 的「0 產出」已過時，會由 zero-output-recovery 依資料關閉。
- **母 issue 收尾**：母 issue 只有在「子 issue 全關」**且**「內文列的每個來源都有結論（已關閉的 `<key>：` issue 或 expectations 登記）」時才貼 `ready-to-close`（G16）；子 issue 全關但還有來源沒結論時，留言列出這些來源；子 issue 重開或來源失去結論時撤回 label（G17）。不自動關閉母 issue（使用者指示）。實測：#381 列 30 個來源、子 issue 只有 16 張，目前 30 個來源都沒有結論；#367 列 9 個仍註冊的來源，4 個沒有結論。

**預設採用的決定**

| # | 決定 | 採用值與理由 |
| --- | --- | --- |
| D5-a | 核准管道 | main 上的 `lane2-approved.yml`，與合併 main 同一道防線；前提 1–3 補強後才啟用 |
| D5-b | 量與節奏 | 每週提案 ≤ 3–4、週日至週二實作、每天 1 筆、open 上限 3；觀察 2 週再調 |
| D5-c | runner 是否改 workflow 與 migration | 都不改（第一輪最小範圍） |
| D5-d | 提案優先序 | production 正在出錯的 bug（例：#540、#554、#404）＞阻擋其他工作的＞小型功能；人類判斷類每週最多 1 筆 |
| D5-e | 母 issue 是否自動關 | 不關，只提醒（使用者指示） |
| D5-f | runner 由誰建立 | 使用者（評審 G2）；agent 不以 `create_trigger` 建立 |

**驗收**：前提 1–4 完成；第一張提案 PR 被合併；兩週內至少 3 張 lane2 PR 合併且 0 revert；14 天盤點記錄 lane2 的配額、已消耗／未消耗／被拒的條目數。

### 10. Phase E：消化率——讓 issue 真的減少（2026-11-10 起；依 plan-critique-3 修訂）

**觀察（D1 上線三天，notes §9–§10、#592）。** open issue 130；三天新開 43、關閉 22；自動關閉只有 recovery 的每天 5 張。heartbeat v2 對 20 張已診斷的 0 產出 issue 全部轉 needs-human、**0 張修復 PR**，needs-human 由 39 漲到 46、auto-fix 由 18 降到 6。原因有三：

1. **診斷沒有 production log。** 兩層原因：#571 的 `report` job 用 `gh api …/logs 2>/dev/null` 把下載或 class 對應失敗吞掉，只留「取不到」（11-08 的 10 張，#608）；之後 #600（另一個 session，2026-11-08 15:22 UTC 合併）重寫 `source-diagnose.yml`，整個拿掉 `report` job（`scripts/ci/prod_log_excerpt.py` 現在沒人用），另在 workflow 內加一條每日排程（12:30 JST，`scripts/pick_diagnose_targets.py`）與 `source-diagnose-batch.yml`（13:00 JST）重複挑件，並讓跑 `main.py` 的步驟持有 `GH_TOKEN`（issues: write），不再移除 `needs-diagnosis`。heartbeat 的規則「例外無、筆數 >0 → 需查 production 紀錄」因此每張都只能轉 needs-human。
2. **「登記為零星來源」是最常見的結論，但 agent 不能寫 `source_expectations.json`。** 建議片段散在各 issue 留言，要人逐張抄。#561 已合併（PR 不再拿到 production secrets），當初排除這個檔的理由已消失。
3. **needs-human 沒有分流。** 46 張混在一起，使用者看不出哪些是「按一下就好」、哪些要家用 IP、哪些要判斷；週審一個早上做不完就累積。

**目標。** 四週後：每週淨關閉 ≥ 新開；needs-human 存量下降；每週至少 3 張 heartbeat 修復 PR 或登記 PR 被合併。護欄指標一起看：recovery 關了又被重開的數、登記為零星的來源數、revert 數——淨關閉不能靠自動關閉灌水。量測見 E5。

**E1＋E6 一張 PR：診斷修回 production log、排程改事件驅動（build）。** 同一個 PR 改 `source-diagnose.yml`、`source-diagnose-batch.yml`、`zero-output-recovery.yml`，避免再出現 #600／#571 平行改同一檔：
- 合回 `report` job（`actions: read`、讀最近 3 次 `scraper.yml` schedule run、`prod_log_excerpt.py`、60,000 字預算）；**去掉 `2>/dev/null`**，下載失敗或 class 對應不到時把原因（HTTP 狀態、job id、找不到的 class）寫進留言。驗收：手動 dispatch `prtimes`，留言出現該來源在 production 的 `=== Starting scraper:` 段落。
- 跑 `main.py` 的步驟不得持有 `GH_TOKEN`；`scripts/tests/test_workflow_secrets.py` 加一條：執行 scraper 的 step 的 `env` 不含 `github.token`／`secrets.*`。
- 刪掉 workflow 內的每日排程與 `scripts/pick_diagnose_targets.py`（含測試）：它不檢查留言作者（公開 repo 任何人貼標記就能擋住診斷），也不處理 `needs-diagnosis` 與家用 IP 來源。挑件只留 batch；診斷貼出後移除 `needs-diagnosis`（#571 行為）。
- `timeout 600` × 5 來源 = 50 分鐘，超過 job 的 45 分鐘：每來源改 `timeout 420`，job `timeout-minutes: 50`。
- 觸發：`zero-output-recovery.yml` 改 `on: workflow_run: workflows: ["Daily Scraper"], types: [completed]`，條件 `conclusion != 'cancelled'` 且原 event 是 `schedule`；`source-diagnose-batch.yml` 改掛 `Zero-output Recovery` 完成（兩層，未超過 GitHub 的三層上限），這樣 batch 不會去診斷 recovery 正要關的 issue。兩者都保留 `workflow_dispatch`，並各留一條保底 cron（UTC 06:00、07:00，當天已跑過就直接結束），Daily Scraper 被 GitHub 略過時仍有一次機會。Closes #608、#563；Refs #614（延遲本身無法由 workflow_run 解決）。

**E2 heartbeat 可寫 `source_expectations.json`，登記建議合成一張 PR（build＋使用者改提示詞）。** 白名單加 `scraper/source_expectations.json`（前提 #561 已合併）。
- **登記條件（三者皆要）**：診斷「例外無」；診斷顯示**過濾前 >0 筆**（列表抓得到，只是沒有台灣相關；診斷留言若沒有這個數字，E1 的 report 要補印 `Found N …` 行）；過濾邏輯可從原始碼確認。「筆數 0 且過濾前也 0」是網站改版或 selector 失效的典型樣子，**不登記**，維持 needs-human（`nh:prod-check`）。
- `max_quiet_days` 上限 **120**，不給 180／365；pattern 與天數照固定表填（百貨 120、戲院 120、研究機構 120、RSS 120、週更來源 60）。這張表放在 `scripts/ci/expectations_policy.json`（**不在 heartbeat 白名單**），PR Tier workflow 在 default branch 檢查 `source_expectations.json` 的 diff：新增條目超過表的上限、或單一 PR 新增超過 5 條，就在 PR 留言標 ⚠️ 並貼 `needs-human`。
- 同時只能有**一張** open 的 `chore/expectations-*` PR；有就跳過本輪登記。這張 PR 是 tier 2（`pr_tier.classify` 實測），由使用者合併；body 每來源一行附診斷連結與過濾前筆數，`Refs` 各 issue、不 `Closes`——合併後由 recovery 依新設定自動關閉。
- 提示詞改成 v3（diff：白名單一行、刪第 20 行的禁止句、改寫第 65 行分支、交付段加「登記 PR」），由使用者貼進排程。

**E3 needs-human 分流（build；只改 heartbeat 提示詞與 digest）。** heartbeat 轉 needs-human 時同時貼次分類 label：`nh:home-ip`、`nh:prod-check`、`nh:decision`、`nh:stale`；轉回 auto-fix 時移除 `nh:*`。既有 46 張不寫一次性腳本，由 heartbeat 每輪補最多 10 張（依留言關鍵字），一週內補完。weekly digest 的「判斷區」依四類分組，每類一句處理方式；`nh:home-ip` 另產一行可貼到 Mac 的命令（`cd scraper && python main.py --dry-run --source a b c`）。使用者貼回的輸出**只當參考**（agent 與使用者同帳號，`<!-- home-ip-run -->` 標記擋不住偽造），不能單獨當成「可以修」的判準；真正的證據仍是 E1 的 production log 與 pr-dryrun-evidence。

**E4 可合併判定併進 weekly digest（build；不做 label 狀態機）。** `weekly_digest.py` 產生時唯讀計算每張 tier 1／auto-fix PR 的四項：tests（check-runs）、dry-run 修復前 0 → 修復後 N（`<!-- pr-dryrun-evidence -->`，作者限 `github-actions[bot]`）、Codex 無未解決（`codex-review-state:v1`，作者限 `chatgpt-codex-connector[bot]`）、`mergeable_state` 非 dirty；四項齊全列在「一鍵合併區」最上面並標 ✅。不加 `ready-to-merge` label（PR Tier 在 Secret Scan 後就觸發，tests 與 dry-run 多半未完成，label 會殘留）。**D3 自動合併維持 no-go**：前提 #562、#568 仍 open；以 `GITHUB_TOKEN` 合併不會觸發 main 的 push workflow（secret-scan、web-*-smoke、eval-*）；擴大 merge job 權限屬「權限與防線」。等 E4 的 ✅ 判定跑兩週、使用者看過準確率再議。

**E5 量測（grunt）。** 「D1 排程每日監控」留言加一行 `<!-- counts: open= needs-human= auto-fix= opened-24h= closed-24h= closed-by-bot-24h= -->`（2026-11-10 已改提示詞，agent 建立的排程可由 agent 改）。LLM 自己數會數錯：`weekly_digest.py` 另以 REST 計算同一組數字加護欄指標（重開數、登記數、revert 數）寫進週報，#592 的每日值只當走向參考，以週報為準。

**各項建議模型（AGENTS.md「執行前的模型評估」要求；subagent 依 tier 自動投影，主對話由使用者 `/model` 切換）。**

| 工作 | 角色（tier） | 模型與 effort | 理由 |
| --- | --- | --- | --- |
| 規劃、修訂方案 | architect（plan） | Opus high | 設計取捨；Fable 只在跨 phase 架構規劃或 Opus 卡關時用 |
| 評審 | plan-critic（plan） | Opus high（Codex 可用時改 Codex） | 不同視角；雲端連不到 OpenAI 時同一模型家族，報告註明 |
| E1＋E6、E2、E3、E4 的 workflow 與腳本實作 | engineer（build） | Sonnet medium | 範圍明確、有測試 |
| 驗證（跑測試、靜態檢查、觸發矩陣） | tester（grunt） | Haiku low | 機械性；發現缺陷再退回 engineer |
| commit、推 feature branch、開 PR | validate-merge-deploy（build）或主對話 | Sonnet medium | 照規則執行 |
| 主對話（協調、回報、開 issue） | — | Sonnet medium | 不需要更強的模型 |
| E2 heartbeat v3 提示詞撰寫 | architect（plan） | Opus high | 提示詞改錯會讓排程偏離，改完交 plan-critic |
| 每日監控、heartbeat 排程本身 | 排程 agent | Sonnet（排程設定的 model） | 長期執行，成本優先 |

**實際紀錄（2026-11-10）。** 方案 §10 與協調在主對話 Fable 5.1 完成（偏高，應為 Sonnet／Opus）；plan-critic 用 Opus，engineer 用 Sonnet，tester 用 Haiku。E1＋E6 兩個 commit 的 `Co-Authored-By` 誤寫 Fable 5.1，實際作者是 Sonnet（已推送，不改歷史；以 PR 留言更正）。之後 commit 訊息的署名以實際執行的模型為準，派工提示詞不再預填模型名。

**不做。** 不碰 `scraper/main.py`、web、production 寫入；不放寬 heartbeat 對 `scraper/sources/` 以外路徑的修復；不自動 resolve Codex thread；不做 D3 自動合併。

**順序與工時。** E1＋E6 先（一天，解除 heartbeat 判斷的阻塞；合併後 heartbeat 對「例外無、筆數 >0」的 issue 才有 production 證據可用）；E5 已做；E2、E3 第二週（各一天，E2 的 v3 提示詞需使用者貼）；E4 第三週（一天）。四週盤點寫 notes。

**人類關卡。** 使用者：合併 E1＋E6 的 PR（新增 `actions: read` 與 `workflow_run` 觸發，屬 workflow 權限）；貼 heartbeat v3 提示詞（E2、E3）；合併每一張 `chore/expectations-*` PR（tier 2）；D3 go／no-go（維持 no-go）。其餘 agent 自做，走 tier 2 PR。

**教訓（寫進 AGENTS.md 待辦 #607）。** #600 與 #571 改同一個 workflow、互不知情：動 `.github/workflows/` 前，先查該檔最近 7 天的 PR（`gh api repos/.../commits?path=…`）與 open 的 spec issue；本 spec 的 workflow 檔都在檔頭註明 spec 與 issue。

### 影響的檔案

- `AGENTS.md`、`.github/copilot-instructions.md`：新增「自主程度與人類關卡」；Codex 只做 Plan Critic，規劃與實作留在 Claude。
- `.github/instructions/git.instructions.md`：Branch strategy 與 Agent workflow 改為 PR 預設；Worktree confirmation gate 改為 selection rule。
- `.github/instructions/handoff.instructions.md`：只有人類關卡才交接卡片。
- `.github/agents/validate-merge-deploy.agent.md`：Step 4 推 branch 與開 PR；Step 5 以 merge commit 驗證；`python3 scripts/sync_ai_adapters.py` 重生成 wrapper。
- `docs/specs/board-themes.json`：`agent-autonomy` → 「AI工具鏈」。
- `docs/specs/active/pr-flow-tiering/proposal.md`：D1 註明由本 spec 承接。
- 新增：本目錄 `proposal.md`、`tasks.md`、`heartbeat-prompt.md`。
- Phase D5 新增：本目錄 `lane2-approved.yml`、`lane2-runner-prompt.md`、`plan-critique-2.md`；`scripts/ci/parent_rollup.py`、`scripts/ci/prod_log_excerpt.py` 與測試；`source-diagnose.yml`、`zero-output-recovery.yml` 增修。
- Phase D 新增：`.github/workflows/source-diagnose-batch.yml`、`pr-dryrun-evidence.yml`、`zero-output-recovery.yml`；`scraper/zero_output_recovery.py` 與其測試；本目錄 `heartbeat-prompt.md` 改為 v2（2026-11-07 啟用）。

### Worktree & Spec Tracking

- spec：`docs/specs/active/agent-autonomy/`
- worktree：`ttr-agent-autonomy-worktree`，branch `feat/agent-autonomy`，2026-10-25 從 `origin/main` `f2c548ef` 新建；依新政策由 agent 自建並回報，未詢問。

## References

- `docs/specs/active/pr-flow-tiering/`：proposal（五個機制、三個分層、D1–D3）、notes B5（推 feature branch 不提示）、B6（Tier 0 實測）。
- `docs/specs/active/ai-harness/plan.md`：模型分級、Codex `plan` profile、D4'（worktree 不帶 secrets）。
- `docs/specs/active/closer-auto-retire/`：worktree 退役自動化（暫停）。
- `.github/workflows/pr-tier.yml`、`scripts/ci/pr_tier.py`：Tier 判定。
- `.github/workflows/qa-heartbeat.yml`：資料側 heartbeat 的既有模式。
- 使用者 memory：push to main 由使用者執行（2026-10-13）；settings 變更由使用者套用（2026-10-22）；成本＝配額（2026-10-15）。
