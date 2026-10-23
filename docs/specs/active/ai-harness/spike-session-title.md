# Spike：用 SessionStart hook 自動給 session 暫時名稱（#426）

目的：驗證 `SessionStart` hook 輸出的 `sessionTitle` 能否在本機各種啟動方式下，依「worktree 或 branch」自動命名 session，且不蓋掉手動命名。條件在執行前寫定，只跑一次。

## 要驗證的疑點（官方文件 code.claude.com/docs/en/hooks 的描述；以下三點文件都沒載明）

1. VS Code 面板新對話是否套用 `sessionTitle`。
2. `claude --bg` 背景 session 是否套用。
3. 手動 `-n`／`/rename` 的名稱是否保留：hook 自己先檢查 stdin 的 `session_title`，有就不輸出，所以預期保留；這項要看實際行為，不假設。

文件有載明的：輸出格式為 `{"hookSpecificOutput":{"hookEventName":"SessionStart","sessionTitle":"…"}}`，exit 0、stdout 只能有一個 JSON 物件；`sessionTitle` 在 `source` 為 startup、resume、fork 時有效；stdin 在已有自訂名稱時帶 `session_title`。

## 設計

不讀對話內容（SessionStart 時還沒有）。名稱規則：

| 啟動位置 | 名稱 | 例 |
|---|---|---|
| `ttr-<slug>-worktree` 內 | `<slug>`；branch（去掉 `feat/` 等前綴）與 slug 不同時加 `·<branch>`；startup 與 fork 再加 `·HHMM` | `ai-harness·2224` |
| 主工作目錄 | `root·<branch>`，同上加時間 | `root·main·2224`、`root·event-detail-404·2224` |
| 其他目錄 | 不命名 | |

主工作目錄一律以 `root` 開頭，是刻意的：規則說主工作樹只供治理與盤點，名稱讓實作 session 開在那裡時一眼看得出來。從 worktree 子目錄（例如 `scraper/`）啟動也算 worktree。resume 不加時間（避免誤導）。

腳本與 log 在使用者層（不進 repo）：`~/.ai-notes/ttr/tools/session_title_hook.py`、`~/.ai-notes/ttr/session-title-hook.log`（只記時間、session 前 8 碼、決定與名稱）。fail-open，永遠 exit 0。已用 8 種假輸入測過（worktree、主工作目錄、子目錄、已有名稱、非 TTR、`clear`、resume、壞輸入）。

## 情境與成功條件

| # | 情境 | 做法 | 成立條件 |
|---|---|---|---|
| T1 | 終端機互動 session（worktree） | `claude --model haiku` 於 ai-harness worktree，不加 `-n` | 名稱出現在 `claude agents --json`／transcript 的 `custom-title`，形如 `ai-harness·HHMM` |
| T2 | 手動命名保留 | 同上但加 `-n "manual-keep"` | 名稱仍是 `manual-keep`，log 為 `skip reason=has-title` |
| T3 | `--bg` | `claude --bg --model haiku "只回報 pwd，不改檔"` 於主工作目錄 | 名稱形如 `root·main·HHMM` |
| T4 | VS Code 面板新對話 | 使用者開新對話 | 面板標題或 `session_map.py` 顯示 `ai-harness·HHMM`（注意：自動標題會不會蓋掉？看最終顯示） |
| T5 | resume | 使用者 `claude -r` 接續 T1 | 名稱不變（log 為 `skip reason=has-title`） |

## 停止條件與清理

- 任何 session 被命名成非預期的字串（例如含路徑）：立刻停止，移除 hook。
- 超過 15 分鐘，或用量差 > 3 點：停止。
- 清理：`python3 ~/.ai-notes/ttr/tools/apply_session_title_hook.py --remove`（會先備份），測試用的 `--bg` session 用 `claude stop` 與 `claude rm`（不使用 `daemon stop --any`）。

## 判定

T1、T2 成立且 T3 或 T4 至少一個成立 → 可作為「暫時名稱」採用；哪個啟動方式沒套用就如實記錄。T2 不成立（蓋掉手動名稱）→ 不採用。本試驗不處理 issue 編號（那需要 `UserPromptSubmit`，另案）。

## 建議模型

試驗與紀錄用 Sonnet、medium；測試 session 用 Haiku。
