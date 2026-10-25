# agent-autonomy — notes

執行證據與限制。里程碑在 [tasks.md](./tasks.md)，設計在 [proposal.md](./proposal.md)。

## §1 Phase A：政策 PR 以新流程交付（2026-10-25）

| 項目 | 證據 |
| --- | --- |
| worktree | `ttr-agent-autonomy-worktree`，分支 `feat/agent-autonomy`，起點 `origin/main` `f2c548ef`；agent 自建並回報，未詢問 |
| 推送 | `git push -u origin feat/agent-autonomy`，hook 放行、無核准提示；gitleaks 掃描 0 洩漏 |
| PR | [#454](https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/pull/454)，PR Tier workflow 在 Secret Scan 之後貼 `tier:2`，符合預期（含 `AGENTS.md` 與 agent 檔） |
| 使用者釐清 | Codex 只做 Plan Critic；規劃與實作留在 Claude，模型依 tier 與成本。第二個 commit `a217e802` 修正；#451、#452 關閉 |
| 合併 | 使用者於 GitHub 按 Squash and merge；merge commit `4d162dc9`；commit status `success`（Vercel）；Production deployment `7309725516` |
| 測試 | `pytest scripts/claude/tests scripts/tests`：1007 passed；`sync --check` exit 0 |
| 人工步驟 | 使用者：1 次合併按鈕、1 則釐清。沒有 push 指令、沒有 worktree 問答 |

## §2 ai-harness 搭上新軌道（2026-10-25）

- `feat/ai-harness` 原本領先 20、落後 19，等「使用者從主工作目錄 push」。改為：在 `ttr-ai-harness-worktree` 檢查乾淨（0 dirty、無 rebase 進行中、最近 session 1 天前）→ `git rebase origin/main` 無衝突（兩邊都改 `validate-merge-deploy.agent.md`，hunk 不重疊）→ 重生成 wrapper 無差異 → `pytest` 1060 passed → `git push -u origin feat/ai-harness` → [PR #458](https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/pull/458)。
- 以 `SendMessage` 通知三個可能受影響的 session（兩個 ai-harness、一個 japan-scope-gate）：分支已 rebase、新推送規則；未等回覆。

## §3 Phase B：heartbeat 排程建立（2026-10-25）

| 項目 | 值 |
| --- | --- |
| label | `auto-fix`（0E8A16）、`needs-human`（D93F0B）已建立 |
| routine | `trig_01CEwNUKeAdxVu9UVLWav7tG`，名稱「TTR heartbeat：issue 分類與單一來源修復（agent-autonomy Phase B）」 |
| 排程 | `0 1,9,17 * * *` UTC＝每日 10:00、18:00、02:00 JST（每 8 小時） |
| 環境／模型 | TTR 環境（`env_01CkXzQsSbqJZ7u5YW3vFG8W`）、`claude-sonnet-5-5`；工具只有 Bash、Read、Write、Edit、Glob、Grep |
| MCP 連接器 | 建立時被預設附上全部連接器（含 Supabase）；已立即以 `clear_mcp_connections` 清空，避免 heartbeat 經 Supabase MCP 寫 production |
| 提示詞 | [heartbeat-prompt.md](./heartbeat-prompt.md) 的內容，加一條「本次分類若貼了任何新 label 或建了子 issue 就結束，不進修復」。效果：分類與修復交替，第一次執行只分類 |
| 第一次執行 | 以 `run` 手動觸發，session `cse_01BjDbtc6Ex4LwPedfRVgWD7`，06:52 UTC；結果見 §4 |

未採用的選項：Codex cloud（使用者釐清開發不用 Codex）、GitHub Actions 跑 agent（API 計費）、家用 Mac launchd（依賴開機）。

## §4 第一次 heartbeat 執行結果（2026-10-25 06:52 UTC，手動 `run`）

| 項目 | 觀測 |
| --- | --- |
| 結果 | `success`，21 回合，46 秒；只做分類，照「貼了新 label 就不進修復」的規則結束 |
| 分類 | #367（10 個來源 0 產出）拆成 5 張子 issue 貼 `auto-fix`＋`scraper`：#459 prtimes、#460 waseda_taiwan、#461 ciema、#462 kbc_cinema、#463 bookandbeer；母 issue 留言列出；其餘 5 個來源留待下次。#407 貼 `needs-human` 並留言原因（告警通道、使用者 Mac、執行環境選擇都是人類關卡）。#381 未處理（本次 5 張額度已用完） |
| 查重 | 事後核對：5 張子 issue 在 open issue 中無重複（`bookandbeer`、`tokyo_now` 的舊 issue #377、#376 已關閉）。但提示詞原本沒有查重步驤，且下次要拆的清單含已退役的 `tokyo_now`，所以已在 routine 與 `heartbeat-prompt.md` 補「建子 issue 前先 `gh issue list --state all --search "<source> in:title"` 查重，已退役不建」 |
| 雲端環境 | 成功 clone repo；`gh pr list` 因「GitHub GraphQL is not available from Claude Code sessions」失敗（403），agent 自行改用環境內建的 GitHub MCP 工具（`mcp__github__*`）完成 issue 讀寫；REST（`gh api repos/...`）可用。log 顯示 `hook_started ×4`，repo 的 PreToolUse hooks 在雲端有執行 |
| 尚未驗證 | 推 branch 與 `gh pr create`（第一次只分類，沒走到）；配額歸屬；dry-run 在雲端的網路可達性。下一次排程 09:05 UTC（18:05 JST）會取件 #459 prtimes，屆時補驗 |
| 清理 | 建立時被附上全部 MCP 連接器（含 Supabase）→ 已清空；提示詞補查重規則後以 `update` 覆寫 |
