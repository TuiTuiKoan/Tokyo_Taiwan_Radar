# Spike：agent view 小試驗（一次性，Phase 2b 的第二個 spike）

目的：驗證 agent view（`claude agents`，研究預覽）能不能在不違反本 repo 規則的前提下，集中監看多個背景 session。這是 notes.md §16.4 第 2 段，使用者 2026-10-23 決定排進 Phase 2b 的 spike。條件在執行前寫定，事後不得更改，只跑一次。

## 要驗證的疑點（官方文件的描述，本機都未驗證）

1. 派出的 session 預設會自己搬進 `.claude/worktrees/<name>/`（分支 `worktree-<name>`）；文件說已在 linked worktree 內就跳過隔離。
2. 文件說 session 完成程式碼修改後，Claude 會 commit、push 分支並可能開 draft PR（不會推 main）。這與本 repo「commit 經核准、push 由使用者執行」衝突；對 linked worktree 是否也會這樣，文件沒說。
3. 背景 session 是否載入 repo 的 hooks（`git push` 的 ask）；文件說在 peek 面板回覆不能回答權限對話框，要 attach。
4. 是否能在 VS Code 的整合終端機使用，通知是否有效。

## 設定

| 項目 | 值 |
|---|---|
| 工作樹 | **已建立（2026-10-23，使用者核准）**，分支 `feat/agent-view-trial`，起點 origin/main `92a5bd45`，路徑 `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-agent-view-trial-worktree`，`.git/info/exclude` 已對帳，工作樹乾淨且有 `.claude/settings.json` 與 `scripts/claude/run_hook.sh`（hooks 會載入）。注意起點是 origin/main，**不含尚未 push 的 ai-harness 變更**。原則：**拋棄式 worktree**，不用 `ttr-ai-harness-worktree`，避免把試驗的 commit 混進 `feat/ai-harness`。建議名稱 `ttr-agent-view-trial-worktree`、分支 `feat/agent-view-trial`、起點 origin/main。依 `git.instructions.md` 的 Worktree 確認閘門，**由使用者核准後才建立**，用 git 指令建立並 reconcile `.git/info/exclude` |
| 啟動位置 | 該 worktree 根目錄（hooks 才會載入） |
| 工具 | `claude agents`（agent view），在 VS Code 整合終端機執行 |
| 規模 | 兩個背景 session，不再多 |
| 模型 | Sonnet |

## 執行前先記錄

- `/usage` 的 Current session %、Current week (all models) %、Current week (Fable) %，以及時間。
- 試驗 worktree 的 `git status --short`（應為空）與 `git log -1 --format=%h`。
- 執行期間不要在任何其他 session 輸入或啟動工作（包含本 session）。

## 兩個提示詞（在 agent view 底部輸入框各送一次）

提示 A（會修改檔案，明確禁止 commit）：

```text
在 docs/_agent-view-trial.md 新增一行文字「trial A」。不要 commit，不要 push。完成後只回報你改了哪個檔案。
```

提示 B（觸發被 hooks 管控的指令，且即使放行也不會推送）：

```text
執行 `git push origin HEAD --dry-run`，回報輸出。如果被要求核准，等我回覆。
```

## 觀察項

| # | 觀察 | 怎麼看 |
|---|---|---|
| O1 | 兩個 session 的工作目錄是試驗 worktree，沒有新建 `.claude/worktrees/` | `git worktree list`；`ls .claude/worktrees` |
| O2 | 提示 B 讓 session 進入 Needs input，也就是 hooks 的 ask 在背景 session 生效 | agent view 的狀態列 |
| O3 | 在 peek 面板回覆無法答覆權限對話框，必須 attach | 實際操作並記錄 |
| O4 | 提示 A 完成後沒有自己 commit、沒有 push | `git log origin/main..HEAD`；`git ls-remote --heads origin feat/agent-view-trial` |
| O5 | 在 VS Code 整合終端機可開啟；完成或需要輸入時有通知 | 使用者記錄 |
| O6 | 狀態顯示與實際相符（Working、Needs input、Completed） | 使用者記錄 |
| O7 | 用量差值 | 結束後再看 `/usage` |

## 成功條件

- S1：O1 成立，沒有新的 `.claude/worktrees/` 目錄。
- S2：O2 成立，且拒絕後 `git push` 沒有被執行。
- S3：O4 成立，沒有未被要求的 commit 或 push。
- S4：用量差值 ≤ 3 個百分點。
- S5：使用者能在一個畫面監看兩個 session，除了權限對話框外不必 attach（使用者主觀記錄）。

## 停止條件（任一成立立刻停止，不重跑）

- 任何 session 實際執行了非 dry-run 的 `git push`。
- 任何 session 修改了試驗 worktree 以外的檔案。
- 超過 15 分鐘。
- 用量消耗超過 5 個百分點。

## 判定規則

- S1 到 S5 全部成立：記為「可列入 Phase 2b 正式使用」，不是「採用」，且仍受 plan §3.1 其他條件約束。
- S3 不成立（它自己 commit 或 push）：記為「只可用於唯讀任務」，並寫下是否可用 `worktree.bgIsolation` 之類的設定關閉；本 spike 不嘗試調整設定重跑。
- 其他情況：記為「不採用」。

## 風險與清理

- 若背景 session 自動 push 了 `feat/agent-view-trial`，遠端會多一個分支。本 repo 的 hooks 會擋 `git push --delete`，所以**清理要由使用者處理**（GitHub 網頁或 `gh`）。這是預先登記的風險，不是失敗。
- 試驗 worktree 若有未合併的 commit，`git branch -d` 會拒絕；依規則不使用 `-D`，由使用者決定如何處理。

## 第一次嘗試（未記錄前置用量，已中止）與重跑登記（2026-10-23，重跑前寫定）

第一次嘗試在 12:55 開始，使用者忘了先記 `/usage`，且 agent view 一時關不掉，所以 S4 無法量測，中止並重置。第一次的觀察已從 session transcript 與 `git` 取得並保留，見 notes.md §20；**重跑使用完全相同的提示詞與條件**，且在開始前先記錄用量。判定採用重跑（只有它能量測 S4），第一次保留作對照，不因重跑結果調整。

## 結果記錄（執行後填入 notes.md）

| 項目 | 值 |
|---|---|
| 開始前與結束後用量（session／週／Fable 週） | 13:04：5%／31%／8%；結束後：7%／31%／8%（`/usage`，方案 Max）。差值 +2／0／0 |
| O1 到 O6 | O1 成立；O2 成立（`Ask rule Bash(git push *HEAD *) overrides auto mode`）；O3 peek 沒有選項，必須按 `→` 進入；O4 成立；O5 VS Code 沒有特別通知，只有畫面顯示；O6 狀態與實際相符 |
| S1／S2／S3／S4／S5 | 成立／成立／成立／成立（最大差值 2 點，且含本 session 同時的活動）／S5 使用者已明確確認成立（2026-10-23） |
| 判定 | **可列入 Phase 2b 正式使用（不是採用）**；限制見 notes.md §22 |
