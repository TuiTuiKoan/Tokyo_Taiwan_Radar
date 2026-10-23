# Spike：agent view 的兩個後續小試驗（Phase 2b）

來源：[spike-agent-view.md](./spike-agent-view.md) 與 tasks.md 的「後續小試驗（NOT TESTED）」。條件在執行前寫定，事後不得更改，各只跑一次。兩個試驗互相獨立，可分開做。

共通規則：唯讀提示詞、Haiku、不 commit、不 push；任何 session 動了檔案或執行非 dry-run 的 `git push` 立刻停止。用量前後各記一次 `/usage`（session、週、Fable 週三個百分比）；任一試驗用量差 > 3 個百分點視為失敗。

## 試驗 1：跨 worktree 的 session 是否出現在同一個清單

**疑點**：從不同 worktree 目錄各自派出的背景 session，是否都出現在同一份 `claude agents` 清單。`claude agents --help` 有 `--cwd <path>`（「只顯示在 <path> 底下啟動的 session」），暗示預設是全部都顯示；`--json` 不需要 TTY，所以清單這一段可以用命令驗證，不必看 TUI。

**設定**：不新建 worktree。用兩個既有目錄：

- A：`/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-harness-worktree`
- B：`/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar`（主工作目錄；只跑唯讀提示詞，符合「主工作樹只供治理與盤點」）

兩處都在 repo 或 worktree 根目錄啟動，hooks 才會載入。

**步驟**（都是簡單命令，各自一行，避開 guard 擋的複合語法）：

1. 在 A 執行 `claude --bg --model haiku -n "trial-A" "只回報目前的工作目錄與分支名稱。不要修改任何檔案。"`
2. 在 B 執行同一個命令，名稱改 `trial-B`。
3. 在 A 執行 `claude agents --json`，在 B 再執行一次。
4. 在 A 執行 `claude agents --json --cwd "<B 的路徑>"`。
5. 在 A 開 `claude agents`（TUI），肉眼確認兩個 session。
6. 結束後 `claude stop` 與 `claude rm` 兩個 session（用 8 碼短 ID），最後 `claude daemon stop --any`，確認沒有殘留背景程序。

**觀察項與成功條件**

| # | 觀察 | 成立條件 |
|---|---|---|
| S1 | 步驟 3 兩次輸出都同時包含 trial-A 與 trial-B | 兩次都成立 |
| S2 | 每筆的 `cwd` 與各自啟動目錄一致 | 一致 |
| S3 | 步驟 4 的 `--cwd` 過濾只回 B 的 session | 成立 |
| S4 | TUI 清單同時看到兩個，且能 peek | 成立（使用者記錄） |
| S5 | 兩個 session 都沒有改檔、沒有 commit、沒有 push（`git status --short` 兩處皆空） | 成立 |
| S6 | 用量差 ≤ 3 點 | 成立 |

**判定**：S1 到 S6 全成立 → 「跨 worktree 可集中監看」，記入 notes.md。S1 不成立 → 記為「清單依目錄分開」，Phase 2b 的多 worktree 監看改用 `python3 scripts/session_map.py`。其他 → 不採用。

**已知限制**：`session_map.py` 讀 transcript，與 `claude agents --json` 是兩個來源；本試驗只測後者。

## 試驗 2：`Notification` hook 能否補上 VS Code 沒有通知的缺口

**疑點**：agent view 試驗時 VS Code 整合終端機沒有通知（notes.md §22）。`Notification` hook 在 Claude 需要使用者時觸發（權限提示、閒置等）；能否在**背景 session** 與 **VS Code 面板的 session** 都觸發，未驗證。

**設定**（使用者層，不進 repo）：`~/.claude/settings.json` 的 `hooks.Notification`，兩個動作：

1. 附加一行時間與 session 資訊到 `~/.ai-notes/ttr/notification-hook.log`（客觀證據，不依賴 macOS 通知權限）。
2. `osascript` 顯示 macOS 通知。

不改 repo 的 `.claude/settings.json`：那是治理用的 hooks（fail-closed），通知屬個人偏好；也不用 `settings.local.json`。**settings 修改由使用者套用**（agent 改 settings 會被分類器擋）；我先出 patch，使用者貼上後在新 session 以 `/hooks` 確認已載入。具體 patch 在試驗前另出，並先確認 `Notification` hook 的 matcher 與 stdin JSON 欄位名稱（查官方文件，不憑記憶）。

**情境與提示詞**（會觸發權限提示、且即使放行也不會推送）：

```text
執行 `git push origin HEAD --dry-run`，回報輸出。如果被要求核准，等我回覆。
```

| 情境 | 做法 |
|---|---|
| N1 | VS Code 整合終端機內的互動式 `claude`（haiku），送上面提示詞，切到別的視窗等待 |
| N2 | `claude --bg` 派出的背景 session，送同一提示詞，不 attach，切到別的視窗等待 |
| N3 | VS Code Claude 面板（非終端機）的 session，送同一提示詞 |

三個情境都在 A（ai-harness worktree）進行，每個等待最多 2 分鐘，到時仍未收到通知就記為「沒有」。

**觀察項與成功條件**

| # | 觀察 | 怎麼看 |
|---|---|---|
| O1 | log 有對應該情境的新行 | `~/.ai-notes/ttr/notification-hook.log` |
| O2 | macOS 通知實際出現（使用者記錄；若沒出現，先查系統設定的通知權限，那算環境問題不算 hook 失敗） | 使用者記錄 |
| O3 | 點通知或回到 session 後，回覆「不核准」，`git push --dry-run` 沒有執行 | transcript |
| O4 | log 內容不含 prompt 全文或 secrets | 讀 log |

**判定**：N2 的 O1 與 O2 成立 → 「Notification hook 可補背景 session 的通知缺口」。N1、N3 的結果各自記錄，不互相推論。O1 成立但 O2 不成立 → 「hook 會觸發，通知呈現受環境限制」。N2 的 O1 不成立 → 「無法補缺口」，改靠 `claude agents` 的狀態列輪詢，不再嘗試其他 hook 事件。

**停止條件**：任何 session 實際執行了非 dry-run 的 `git push`；超過 15 分鐘；用量超過 5 點。

## 順序與建議模型

先做試驗 1（純命令、無設定改動），再做試驗 2。兩者執行與紀錄用 Sonnet、medium；使用者層 settings 的 patch 先查文件再出，不需要 Opus。紀錄寫入 notes.md 新章節，tasks.md 的「後續小試驗」項在結案時勾選。
