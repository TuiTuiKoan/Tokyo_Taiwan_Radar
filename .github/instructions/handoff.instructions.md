---
applyTo: "**"
description: "交給使用者執行的步驟：交接卡片、session 命名與父子關係、可點連結"
---

# 交給使用者執行的步驟（Handoff）

agent 要使用者動手時（執行指令、開新 session、看檔案、在網站上操作、核准），使用者只看得到這一則訊息。前幾則設的 shell 變數、agent 自己知道的目錄與 session，使用者都不一定記得。所以每次交接都要讓人不回頭翻對話也能照做。

追蹤：#425（交接卡片）、#426（session 辨識）。

## 1. 交接卡片

每一個要使用者動手的步驟寫成一張卡片。一張卡片只做一件事；多步驟就寫多張，標「第 N 步／共 M 步」。

```markdown
### ▶ 交給你執行（第 1 步／共 2 步）· 唯讀
- **在哪裡**：你原本跑 runbook 的那個 terminal 分頁
- **目錄**：/Users/…/ttr-japan-scope-gate-worktree/scraper
- **本 session**：終端機 handoff 指引 (72ddde89)
- **指令**：（code block，可整段複製）
- **預期結果**：最後一行是 `validate=ok`
- **失敗時**：不要重試，把整段輸出貼回這個 Claude 對話
- **做完**：回這個對話貼結果；terminal 分頁先別關，第 2 步還要用
- **建議模型**：Sonnet · medium（只有需要換 session 或換模型時才寫）
```

欄位規則：

| 欄位 | 規則 |
| --- | --- |
| 標題的風險標記 | `唯讀`、`寫本機`、`寫 production`、`不可逆` 擇一。`寫 production` 與 `不可逆` 的步驟獨立成卡，不和唯讀步驟同卡 |
| 在哪裡 | 只用下列詞彙之一：「這個 Claude 對話」、「你原本那個 terminal 分頁（說明是做什麼的那個）」、「新開的 terminal 分頁」、「新開的 Claude session（名稱見下）」、「瀏覽器：<網站名>」附可點連結、「Supabase Dashboard › <頁面>」附可點連結。不得只寫「在 scraper 目錄」這種相對位置 |
| 目錄 | 絕對路徑。worktree 要寫出完整 worktree 名稱 |
| 指令 | 不依賴前幾則訊息的狀態，優先寫絕對路徑。一定要用變數時，第一段先重設全部變數。跨多則訊息的 runbook，把變數寫到 `~/.ai-notes/ttr/<slug>.env`（不得含 secrets），每步開頭 `source` 這個字面路徑 |
| 預期結果 | 寫出成功時會看到的具體文字或數字 |
| 失敗時 | 要不要重試、要貼回什麼、貼回哪裡 |
| 做完 | 回哪個 session、貼什麼；用過的 terminal 分頁或 session 可以關還是要保留 |

不需要使用者動手的資訊（agent 自己做完的事、背景說明）不寫成卡片。

## 2. 開新 session 或新 terminal

叫使用者開新 session 或新 terminal 時，卡片要多交代：

- **為什麼要開新的**：例如要在另一個 worktree 根目錄啟動，hooks 才會生效。
- **原本這個要不要保留**：保留就說明之後回來做什麼；不保留就說可以關。
- **新的那邊做完帶什麼回來**：要貼的輸出、commit SHA，或「不用回來」。
- **新 session 的名稱**，依第 3 節。

## 3. session 命名與辨識

一個 Claude session 有三種名稱，只有自動標題看得到（2026-10-23 在 VS Code side chat 實測）：

| 名稱 | 使用者看得到？ | 用途 |
| --- | --- | --- |
| 自動標題（例：`終端機 handoff 指引`） | 看得到：面板標題、歷史清單 | 給人辨識 |
| session ID（UUID） | 看不到；是 `~/.claude/projects/<專案>/<UUID>.jsonl` 的檔名，`claude -r <UUID>` 可接續 | 追蹤 |
| ListAgents 代號（例：`tokyo-taiwan-radar-5c [1295ca]`） | 看不到，短 id 也不是 UUID 開頭 | 只供 session 互傳訊息 |

規則：

- 給使用者看的 session 一律寫成「標題 (UUID 前 8 碼)」。不得把 ListAgents 代號當成使用者能找到的名稱。
- Claude Code 取得自己 UUID 的方法：scratchpad 路徑的最後一段。取得不到時寫「ID 未知」，不要猜。
- 新 session 的名稱格式是 `<spec-slug>·<用途>`，例：`japan-scope-gate·apply`。沒有 spec 時用主題短詞。
  - terminal：`claude -n "japan-scope-gate·apply"`，在要工作的 worktree 根目錄啟動。
  - VS Code side chat：開新對話後，第一則輸入 `/rename japan-scope-gate·apply`。
  - 既有的舊 session 要繼續用時，先 `/rename`；不再用的舊 session 不必補名稱。
- 交接卡片涉及兩個 session 時，同時寫「本 session」與「父 session」（做完回哪裡）。

## 4. 連結

- 檔案用 markdown 連結。VS Code 裡用相對 workspace 根目錄的路徑，例：`[AGENTS.md](AGENTS.md)`；純 terminal 用絕對路徑，方便 ⌘-click。
- 網址寫成 `[說明](https://…)`，不只丟一行網址。
- issue、PR、活動頁照既有規則附完整連結。

## 5. 範例：改寫前後

改寫前（2026-10-23 japan-scope-gate 實例）：

> 先確認變數還在：`echo "$M"`、`echo "$DG"` … 再執行（你已在 scraper 目錄）：`../.venv/bin/python _oneoff_… --validate …`

問題：沒說在哪個 terminal、哪個 worktree；`$D` 沒給重設方法；唯讀和寫 production 在同一段；沒說輸出貼回哪裡。

改寫後：第 1 節的卡片範例，加上第 2 步獨立一張 `· 寫 production · 需要你的核准句` 卡片，寫明「核准句貼在這個 Claude 對話；收到『可以執行』後才在同一個 terminal 執行，digest 前 12 碼由你親手輸入」。
