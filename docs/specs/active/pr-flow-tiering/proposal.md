---
slug: pr-flow-tiering
title: 以 PR 分層取代手動 push，只讓人決定重要的合併
status: active
branch: feat/pr-flow-tiering
created: 2026-10-22
tags: [tooling, infra, governance]
---

## What（做什麼）

把開發流程裡唯一的人工決策點，從「使用者手動執行 `git push origin <branch>:main`」移到「GitHub 上合併 PR」。agent 在 worktree 內完成實作後，自己把 feature branch 推上 origin 並開 PR。PR 依變更路徑分三層：低風險的自動合併，中風險的一鍵合併，高風險的完整 review。推到 `main` 的權限仍然只屬於使用者。

本 spec 包含五個機制、三個分層與三個待決點，並以 `scripts/claude/_policy.py` 的 `check_push` 分流作為第一個實作里程碑。

## Why（為什麼）

- **每個小任務都要經過同一串手動步驟。** 決定要不要開 worktree、開新 terminal、複製 push 指令、回報 push 結果，再請 V-M-D 驗證部署。使用者在 2026-10-22 明確表示這些步驟浪費最多時間。
- **權限系統已經不讓 agent 推 main。** auto mode 的分類器把 `git push origin HEAD:main` 視為 Production Deploy 並拒絕（使用者 memory，2026-10-13）。現行 V-M-D Step 4 因此改成把指令交給使用者執行，人工複製貼上成了固定成本。
- **短命 branch 與 worktree 持續累積。** 2026-10-20 盤點時有 19 個 worktree、22 個本機 branch，其中 17 個領先 main 0 個 commit、落後 47 到 264 個 commit，散在四個父目錄。沒有合併後自動清理的機制。
- **跨工具切換會遺失狀態。** 從 claude.ai 雲端、VS Code chat 到 terminal CLI 之間切換時，曾發生 stash 踩踏。若工作單位改成「origin 上的 branch 加 PR」，各工具看到的就是同一份狀態。
- **為什麼現在做：** GitHub repo 目前 `allow_auto_merge=false`、`delete_branch_on_merge=false`、`main` 沒有 branch protection。基礎設定為零，正適合從頭設計，不必拆既有規則。

## Non-Goals（不做什麼）

- 不處理 OpenAI 成本（海報 OCR、search-preview 下架），那是另一份 spec。
- 不處理 Issues、spec 目錄與 ledger 的清理，那是另一份 spec。
- 不取消 V-M-D 的驗證內容（conflict、rebase、build、gitleaks、i18n gate），只改變它在哪個時間點、由誰觸發。
- 不在本 spec 的第一個里程碑改寫 `git.instructions.md`、V-M-D agent 或 campaign closer 的規範文字。依 Architect SKILL「工作流／治理計畫三查」，政策改寫另立 Phase F，在試行通過後才做。
- 不放寬 force push、刪除遠端 ref、`--mirror`、`--prune` 的阻擋。

## Design（設計摘要）

### 五個機制

| 代號 | 機制 | 現況 | 目標 |
|---|---|---|---|
| M1 | worktree 變成預設 | 每次實作前問使用者用哪個 worktree，再手動建立與加 exclude | 主目錄的 file guard 直接拒絕寫入 `scraper/`、`web/`、`supabase/`、`scripts/`。agent 遇到實作任務自己建立 worktree。可用 Claude Code 2.1.304 的 `claude -w <slug> --tmux`、`EnterWorktree`、subagent `isolation: "worktree"` |
| M2 | feature branch 自動推，main 仍歸使用者 | `check_push` 對所有 push 回傳 ask，`.claude/settings.json` 另有 `Bash(git push:*)` ask | 目標是 `main` 才 ask。其他 branch allow。破壞性 push 照舊 deny。推完由 agent 執行 `gh pr create`，PR body 帶 spec slug 與 `Closes #n` |
| M3 | PR 依路徑分層合併 | 沒有 PR 流程 | 見下方「三個分層」 |
| M4 | 合併後自動收尾 | 手動 `git worktree remove`、`git branch -d`、清 exclude | 開啟 `delete_branch_on_merge`。每日或 SessionStart 比對 `git worktree list --porcelain` 與 `git branch --merged origin/main`，列出可移除的 worktree |
| M5 | 跨工具延續 | 狀態散在各工具的本機工作目錄與 stash | 工作單位是 origin 上的 branch 與 PR。雲端 session 用 `claude --teleport` 接回本機。主目錄不再有人實作，stash 踩踏的來源消失 |

### 三個分層

| 層級 | 路徑條件 | 合併方式 |
|---|---|---|
| Tier 0 自動合併 | 只動到 `docs/**`（`docs/specs/**`、`docs/architecture/**` 除外，兩者在 web build 時被讀進 admin specs 頁）、`.github/skills/**/history.md`；dependabot 的 semver-patch 沿用既有 workflow | PR Tier workflow 在 gitleaks 對 PR 成功後貼 `tier:0`，以 `gh pr merge --squash --match-head-commit` 直接合併被掃描的那個 commit |
| Tier 1 一鍵 | 只動到單一 `scraper/sources/<source>.py` 及其 skill、tests；tests 綠且 dry-run 有產出 | 貼 `tier:1` 並推播通知，使用者在手機或網頁按 merge |
| Tier 2 完整 review | 任何 `web/**`、`supabase/**`、`scraper/annotator.py`、寫入 production DB 的 script、`.github/workflows/**`、`scripts/claude/**`、`.claude/**`、`AGENTS.md`、`.github/instructions/**`、`.github/agents/**` | 現有 V-M-D 驗證加 Vercel preview，使用者親自看 |

一個 PR 同時符合多層時，取最高層。Tier 0 與 Tier 1 的路徑清單採白名單，任何不在清單上的路徑自動落入 Tier 2。

### 三個待決點（需使用者裁決）

- **D1 是否放棄「trunk-based、無 PR 閘門」的規範文字。** `git.instructions.md` 的 Branch strategy、V-M-D 的 Step 4、campaign closer 的 base/head 四參數交接都以直接 push main 為前提。改成以 PR 為單位是治理改寫。建議：Phase E 試行兩週後再裁決，試行期間兩種流程並存。
- **D2 worktree 路徑慣例。** 現行是 repo 根目錄下的 `ttr-<slug>-worktree`，手動維護 `.git/info/exclude`。Claude Code 原生用 `.claude/worktrees/<name>`，工具自己管生命週期。建議改用原生路徑，ledger 對帳改讀 `git worktree list --porcelain`。
- **D3 Tier 0 的範圍。** 自動合併等於放棄這些路徑的事前 review。建議只放上表列出的路徑；`.github/workflows/**`、`scripts/claude/**`、`.claude/**` 永遠不得進 Tier 0。

### `check_push` 決策表（Phase B 實作依據）

判斷原則：只看 refspec 的目的端是否「可能是 `main`」。無法從命令本身確定目的端時，一律 ask。

| 命令形式 | 決策 | 理由 |
|---|---|---|
| `git push`、`git push origin`（沒有 refspec） | ask | 目的端取決於當前 branch 與 upstream，可能是 main |
| `git push origin HEAD`、`git push origin @` | ask | HEAD 可能是 main |
| `git push origin feat/x`、`git push -u origin feat/x`、`git push origin feat/x:feat/x` | allow | 目的端確定不是 main |
| `git push origin main:feat/x` | allow | 來源是 main，但目的端不是 |
| 目的端是 `main` 或 `refs/heads/main`：`main`、`HEAD:main`、`feat/x:main`、`x:refs/heads/main` | ask | 推 main |
| branch 名稱只是包含 main 字串：`feat/main-fix`、`maintenance` | allow | 用完整名稱比對，不用子字串 |
| `--all`、`--branches`、`--tags`、`--follow-tags`、目的端在 `refs/tags/` | ask | 可能連帶推 main，或發布 tag |
| 多個 refspec | 取最嚴格者 | 任一 ask 即 ask，任一 deny 即 deny |
| remote 是 URL 或 `--repo=<url>` | 依目的端判斷 | remote 名稱不影響目的端 |
| `--dry-run`、`-n` | 和不帶 dry-run 時相同 | 保持規則單純 |
| force、`--force-with-lease`、`--force-if-includes`、`--delete`、`-d`、`--mirror`、`--prune`、`+refspec`、`:ref` | deny | 不變 |
| `git -C <path> push …`、`env X=1 git push …`、`bash -c 'git push …'` 等包裝 | 解包後套用同一張表 | 沿用既有解包邏輯 |

**與 `.claude/settings.json` 的互動是已知風險。** `permissions.ask` 的 `Bash(git push:*)` 會讓所有 push 都提示，不論 hook 回傳 allow。Phase B 必須在 Claude Code 2.1.304 實測 hook allow 與 settings ask 的優先順序，以及 auto mode 分類器是否放行推 feature branch，再提出 settings 的修改方案。修改 `.claude/settings.json` 屬於權限設定變更，必須在 PR 上由使用者明確核准，不得由 agent 自行合併。

### GitHub 端設定順序

1. 關閉 merge commit，merge method 只留 squash 與 rebase。這符合既有「禁 `--no-ff`，避免 secret scan 重掃整段歷史」的規則。`delete_branch_on_merge` 在 2026-10-22 已是開啟狀態。Phase D 改版後不使用 GitHub auto-merge，`allow_auto_merge` 維持關閉。
2. ~~為 `main` 建立只要求 status checks 的 ruleset~~ 延到 Phase F。Plan Critic P1 擔心的「checks 完成前就合併」已由 workflow 設計排除：合併只在 gitleaks 成功之後發生，且綁定被掃描的 commit。repo 內另有一個 2026-06-12 建立、已停用、沒有指定 branch 的 ruleset「TuiTuiKoan manager」，不動它。
3. 新增 PR Tier workflow（`.github/workflows/pr-tier.yml`）與分類程式 `scripts/ci/pr_tier.py`。
   - **觸發改用 Secret Scan 成功後的 `workflow_run`，不用 `actions/labeler`，也不用 `pull_request`。** 一般的 `pull_request` 執行的是 PR 自己帶的 workflow 與程式，PR 改掉分類規則就能讓自己被自動合併。`workflow_run` 固定執行 default branch 上的 workflow 與程式，job 只透過 API 讀檔名，絕不 checkout 或執行 PR 的內容。第一版用 `pull_request_target` 加 GitHub auto-merge，Phase D 資安審查（`critique-phase-d.md`）指出 auto-merge 會沿用到之後的 commit，因此改版。
   - **不使用 GitHub auto-merge。** 合併以 `--match-head-commit` 綁定被掃描的 commit；之後的 push 會有自己的掃描與判斷。
   - **檔案清單必須完整。** API 回傳的檔案數要等於 `changed_files` 且少於 3000，否則一律 Tier 2。
   - 兩個 job 分權：分類的 job 只有讀取權限，貼 label 與合併的 job 不 checkout 程式碼。
   - 只處理同 repo 的 PR；只有 repo owner 開的、非 draft、head 仍是被掃描 commit 的 Tier 0 PR 才會合併。tier label 在 gitleaks 跑完後才出現。
   - 由 `GITHUB_TOKEN` 完成的合併不會觸發 main 上以 push 觸發的 workflow；Tier 0 只有文件，可接受。
   - 殘餘風險：files API 不提供檔案模式，docs 下的 symlink 仍判 Tier 0。日後若有程式開始在 build 或執行時讀取 docs 其他子目錄，必須同步更新 `pr_tier.py` 的排除清單。
4. 「要求 PR」的保護放到最後。一旦要求 PR，使用者就不能再直接 push main，必須等 Phase E 試行通過、D1 裁決之後才開。

以上設定會改動對外的 repo 狀態，每一步都由使用者核准或親自操作。

### `check_push` 決策表的補充（Plan Critic 後，見 `critique.md` 與 `notes.md` B3）

- `push` 前帶有 `-C <path>` 以外的 git 全域選項（`-c`、`--config-env`、`--git-dir`、`--work-tree`、`--namespace` 等）時一律 ask。實測 `git -c remote.origin.push=refs/heads/feat/x:refs/heads/main push origin feat/x` 會把 feat/x 推到 main。
- `git config` 寫入 `remote.*.push`、`remote.*.mirror`、`push.*`、`core.hookspath`、`url.*.insteadof`、`url.*.pushinsteadof`、`alias.*` 時 ask。
- push 選項採已知清單，清單外的選項 ask。

### 試行指標與停止條件

- 每個小任務從「開始實作」到「進 main」的人工步驟數與耗時。試行前先手動記錄五個任務當基準。
- 各層 PR 數、Tier 0 被 revert 的次數。
- 停止條件：試行兩週後人工步驟或耗時沒有明顯下降，就停在 Phase D，不做 Phase F 的治理改寫與「要求 PR」。

### 影響的檔案

- `scripts/claude/_policy.py`、`scripts/claude/tests/test_bash_guard.py`
- `.claude/settings.json`（需使用者核准）
- `AGENTS.md` 的「Hooks 與 permissions」一節
- 新增 `.github/workflows/pr-tier.yml`、`scripts/ci/pr_tier.py`、`scripts/tests/test_pr_tier.py`
- Phase F 才動：`.github/instructions/git.instructions.md`、`.github/agents/validate-merge-deploy.agent.md`、`.github/agents/campaign-closer.agent.md`，以及 `python3 scripts/sync_ai_adapters.py` 生成的 wrapper

### Worktree & Spec Tracking

- spec：`docs/specs/active/pr-flow-tiering/`
- worktree：`ttr-pr-flow-tiering-worktree`，branch `feat/pr-flow-tiering`，2026-10-22 從 `origin/main` `555fb9a5` 新建，使用者已確認。
- D2 若裁決改用 `.claude/worktrees/`，本 worktree 照舊完成，不搬移。

## References

- 2026-10-20 至 10-22 的盤點對話：worktree 與 branch 數量、repo merge 設定、`gh api` branch protection 回傳 404。
- `scripts/claude/_policy.py` 的 `check_push`；`.claude/settings.json` 的 `permissions.ask`。
- `.github/workflows/dependabot-auto-merge.yml`：既有的 `gh pr merge --auto --squash` 模式。
- `.github/instructions/git.instructions.md`：Branch strategy、Worktree confirmation gate、Isolated worktree。
- `.github/skills/agents/architect/SKILL.md`：「工作流／治理計畫三查」。
- `AGENTS.md`：「Hooks 與 permissions」「角色工具限制」。
- `critique.md`：Codex 的 Plan Critic 報告與逐條回應。
- `critique-phase-d.md`：Codex 對 PR Tier workflow 第一版的資安審查與回應。
