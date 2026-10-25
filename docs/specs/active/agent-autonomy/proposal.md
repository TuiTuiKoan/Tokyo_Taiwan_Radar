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

- 每 8 小時一次；每次最多 1 張 issue；同時最多 2 張待合併的 heartbeat PR。
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
| A5 | 節奏與上限 | 每 8 小時、每次 1 張、同時 2 張待合併 |
| A6 | 分類範圍 | 只碰沒有 `spec:` label 的 issue |

### 影響的檔案

- `AGENTS.md`、`.github/copilot-instructions.md`：新增「自主程度與人類關卡」；Codex 只做 Plan Critic，規劃與實作留在 Claude。
- `.github/instructions/git.instructions.md`：Branch strategy 與 Agent workflow 改為 PR 預設；Worktree confirmation gate 改為 selection rule。
- `.github/instructions/handoff.instructions.md`：只有人類關卡才交接卡片。
- `.github/agents/validate-merge-deploy.agent.md`：Step 4 推 branch 與開 PR；Step 5 以 merge commit 驗證；`python3 scripts/sync_ai_adapters.py` 重生成 wrapper。
- `docs/specs/board-themes.json`：`agent-autonomy` → 「AI工具鏈」。
- `docs/specs/active/pr-flow-tiering/proposal.md`：D1 註明由本 spec 承接。
- 新增：本目錄 `proposal.md`、`tasks.md`、`heartbeat-prompt.md`。

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
