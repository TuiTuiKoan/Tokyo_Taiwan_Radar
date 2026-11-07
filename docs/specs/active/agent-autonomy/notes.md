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

## §5 heartbeat 停擺 12 天與上限調整（2026-11-07）

| 項目 | 觀測 |
| --- | --- |
| 症狀 | 2026-10-25 的 #485～#488 四張 `auto-fix` PR 未合併，open 數達上限 4 → 之後每次執行（約 27 秒）都只分類、不修。到 2026-11-07 為止 38 張 `auto-fix` issue 沒有被取件（#446、#459 以下的爬蟲 0 產出）；期間沒有任何通知，使用者只看到「issue 一週都沒結清」 |
| 連帶問題 | 使用者合併 #485 後，#487、#488 與 main 衝突（四張都改 closeout 稽核腳本或 campaign-closer 的 history.md）。heartbeat 不 force-push，無法自行修復；由互動 session rebase 後重開成 #526、#527 |
| 判斷 | 上限是 WIP 限制（使用者的審核量與配額），不是 PR 之間的依賴；但腳本與文件類修復常改同一個檔，先合併一張就會讓其他張衝突。爬蟲來源修復各改各的 `scraper/sources/<source>.py`，幾乎不會衝突。真正的瓶頸是「滿額時沒有通知」 |
| 調整（使用者同意） | ① 上限分兩類：爬蟲類（只改 `scraper/sources/**`、`scraper/tests/**`、`.github/skills/sources/**`）6 張，腳本文件類 1 張；② 取件先挑帶 `scraper` label 的 issue；③ 預計要改的檔案與任何 open PR（不限 `auto-fix`）重疊就跳過；④ 滿額時在固定追蹤 issue #528 留言列出待合併 PR，清單沒變就不重複留言；⑤ 停止條件「連續兩張被關閉未合併」不計寫明「已由 #n 取代」的 PR；⑥ sandbox 連不到來源網站且無法從原始碼確定原因時，改貼 `needs-human`，不做猜測式修復 |
| 套用 | 排程是以 HTTP API 建立的，agent 的 `update_trigger` 被拒（「Agents can only update routines they created」）。新提示詞寫在 [heartbeat-prompt.md](./heartbeat-prompt.md)，由使用者到 routine 頁面貼上 |
| 待觀察 | 7 天盤點時一併看：爬蟲類 PR 的合併速度、#528 通知是否讓等待天數縮短、配額是否吃緊 |

## §6 Phase D 規劃、評審與 D1 交付（2026-11-07）

| 項目 | 內容 |
| --- | --- |
| 起點 | 使用者一週約一個早上能審 PR，要求逐日自動驗證、排查、開發、推送。規劃寫進 proposal §8；以 main 2026-11-07 的現況為基準（`source-diagnose.yml` 已上線、上限爬蟲類 6／腳本文件類 1） |
| 評審 | [plan-critique-1.md](./plan-critique-1.md)：Claude plan-critic（同一模型家族；此環境沒有 codex），go with changes，2 blocker、8 major |
| 兩個 blocker | F1：`main.py` 吞掉 scraper 例外仍 exit 0，診斷與證據改以 `scraper failed:` 為主訊號；F2：public repo 任何人可偽造診斷留言，heartbeat 與 workflow 只信 `github-actions[bot]` |
| 本 PR 處理 | F1–F4、F6、F10–F21 全部；F7 的判讀文字；F9 在 D1② 標為未測 |
| 偏離評審 | D-f：D1② 不延後（使用者指示實作三個 workflow）；D-g：`source_expectations.json` 暫不加白名單（評審 F5 建議加，但會觸發 F8 的 secrets 暴露） |
| 開成 issue | D1 #557、D2 #558、D4 #559、D3 裁決 #560、F8 #561、F9 #562、F7 #563 |
| 實作時抓到的 bug | ①stdout 有含 `[` 的 log 時，從第一個 `[` 解析 JSON 會失敗（既有 source-diagnose 也有），改成逐一嘗試行首 `[`；②`jq map({…pull_request})` 讓每張 issue 帶 `pull_request: null`，以「有 key」判斷 PR 會把所有 issue 濾掉，改看值。②是對 live issue 資料乾跑時發現的 |
| 乾跑證據 | batch 選件邏輯對 live issue 乾跑（dispatch 換成 echo）：#459、#460 已有 bot 診斷被跳過，取 #461、#462、#463、#468、#469；復原偵測的候選辨識對 live 資料取出 35 張 |
| 與並行 session 的交會 | 本 PR 開發期間，另一個 session 合併了 `ca49fb9`（#538 的 name_ja 修正＋`heartbeat-prompt-531-patch.md`）。rebase 時 `source-diagnose.yml` 取本 PR 版本（已改用共用解析器、同樣讀 name_ja）；531-patch 由 v2 取代（v2 檔頭有說明） |
| NOT TESTED | 四個 workflow 都只有 actionlint＋shellcheck 與本機單元測試，未在 Actions 上執行（workflow_dispatch 需要檔案先在 main）；`zero_output_recovery.py` 的 Supabase 查詢未實測 |

## §7 Phase D5 規劃、評審與 D1 後續交付（2026-11-07）

| 項目 | 內容 |
| --- | --- |
| D1 上線實測 | #565 合併後由 agent 手動觸發：zero-output-recovery（dry-run）在 Actions 上查 Supabase 成功，35 張候選中 10 張符合關閉條件、未動作；source-diagnose-batch dispatch #461、#462、#463、#468、#469，診斷留言已貼回（4 張「0 筆、無例外」，#463 執行中）。排程版尚未執行 |
| 新事實 | production log（2026-11-04～06）：prtimes 每天寫入 53～55 筆、waseda_taiwan 2 筆、midland_cinema 1 筆。#459、#460 的「0 產出」已過時；taiwanshi 在 production 是 403 |
| 評審 | [plan-critique-2.md](./plan-critique-2.md)：go with changes，1 blocker（G1）、14 major |
| G1（blocker） | 「核准檔在 main＝使用者核准」不成立：main 無 branch protection、ruleset disabled；agent 以使用者帳號操作，合併事件與使用者無法區分；hooks 只管 `git push`，`gh pr merge`、`gh api` 寫 main、GitHub MCP 寫入工具都無規則。處置：proposal §9 照實改寫，runner 排程延到前提 1–4 完成 |
| 本 PR 處理 | G13（log 擷取保留尾段）、G14（source-diagnose 拆兩個 job）、G15、G16（母 issue 對照內文每個來源）、G17（撤回 label）、G19（heartbeat v2 不用 --paginate）、G11（heartbeat v2 不取 lane2 條目）；§9、核准檔 schema、runner 提示詞依 G2–G12、G18–G22 改寫 |
| 開成 issue 或併入 | G1 → #568；G3／G21 → #569；G5 → 併入 #561（留言擴大範圍）；D5 runner 建立 → #570（列前提 1–4） |
| 實測的母 issue 狀態 | #381 列 30 個仍註冊的來源、子 issue 16 張，30 個都沒有結論；#367 列 9 個仍註冊的來源（tokyo_now 已退役），4 個沒有結論 |
| NOT TESTED | 拆成兩個 job 的 source-diagnose 與 parent-rollup job 未在 Actions 上執行；report job 的組裝邏輯在 sandbox 以真實 production log 模擬過（gh 抓 log、不貼留言） |
