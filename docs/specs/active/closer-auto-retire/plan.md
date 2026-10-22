---
slug: closer-auto-retire
title: Close Campaign 取得同意後自行執行 worktree 退役
status: Phase 1 進行中；Phase 2–3 暫停（2026-10-22），恢復條件：pr-flow-tiering 試行結束並決定 Phase F 後
revision: 4
branch: feat/closer-auto-retire
worktree: ttr-closer-auto-retire-worktree（CONTINUING，已註冊，exclude 行已存在）
created: 2026-10-22
author: Architect
---

# Close Campaign 取得同意後自行執行 worktree 退役 — 計畫（rev.4）

> **狀態（2026-10-22）**：Phase 1 進行中（回填腳本與測試）；Phase 2 試跑與 Phase 3 規則改寫**暫停**。
> 恢復條件：pr-flow-tiering 的兩週試行結束，並決定其 Phase F 之後。理由見 §2.5 與 §14；恢復前要先處理 §13。
> 本檔 §4–§8 是 rev.3 的設計，暫停期間不再修改；其中的 tip 判定前提可能在恢復時失效。

## 修訂紀錄

| 版本 | 日期 | 內容 |
|------|------|------|
| rev.1 | 2026-10-22 | 初版：Phase B 一次同意，Phase D 的 D1–D5 由 agent 自行執行 |
| rev.2 | 2026-10-22 | 依使用者看過 Plan Critic 報告後的裁決，縮成**最小可行版本**。自動執行只限 Claude Code、乾淨的 `RETIRE_CANDIDATE`、ignored 集合在可重建樣式清單內；其餘退回現行「產生指令交使用者」。刪掉 step log、Phase B 提前分類、D2 digest 比對、capsule 存 patch-id。tip 判定改用確定性三條件（B5）。遠端分支先採選項 A。加入串接情境試跑與量化決策閘門。D3b 腳本化與選項 B 列為延後項 |
| rev.3 | 2026-10-22 | 寫入 Q8–Q10 裁決。`B_C` 改為 V-M-D 推送結案記錄那一次的 push base（推送前的 `origin/main`），B5 因此容忍 V-M-D rebase；D1 加 `HEAD^ == B_C` 與 `refs/remotes/origin/main` reflog 交叉驗證；刪除「B5 的已知後果」與延後項 L6；T-C 加 rebase 正向案例與偷插 commit 負向案例。試跑只觀察自然出現的核准提示（Q9）。維持主工作樹 root，試跑的協調者對話必須從主工作樹 root 新開（Q10） |
| rev.4 | 2026-10-22 | 只記錄裁決與暫停狀態，不重新設計。Plan Critic 複核 rev.3 的五項 blocking 與建議項整理成 §13「恢復前必修」（只寫修法方向）；新增 §14「與 pr-flow-tiering 的關係」；§2.5 第四輪裁決（先做 Phase 1、其餘暫停；cwd 外漏採 (a)、以 (c) 備援）；cwd 外漏的裁決寫進 §7 #5；§12 改列恢復時要回答的問題 |

## 0. 一句話

closer 在 Phase B 取得使用者一次同意後，只要情況落在「最小可行版本」的自動範圍內，Phase D 就由 agent 自行執行
可執行的退役步驟：移除 worktree、exclude 對帳、`git branch -d`、殘留驗證、主工作樹的 disposition 回填 commit。
範圍外的情況，以及任何 `git push`，一律維持現行「產生指令交使用者」。

## 1. 目標與非目標

### 目標

1. 範圍內的退役，D3a–D5 由 closer 自行執行，使用者不必複製貼上指令。
2. 同意只問一次（Phase B），而且只在同一個 closer subagent 實例內有效。D1 重新觀測與 Phase A 基準不一致，或任一
   STOP 條件命中，就停下重新詢問。
3. 中途被擋或失敗時，靠 capsule 加上對實際狀態的探測冪等續跑，回報寫明停在哪一步。
4. 規則定稿前，以量化門檻的試跑確認「自動化確實比貼指令省事」，否則停下不改文件。

### 非目標

* 任何 `git push` 的自動化，包括 push 到 main 與 `git push origin --delete`。guard 對 `git push origin main` 是 `ask`，closer 仍不呼叫。
* 修改 `.claude/settings.json`、`scripts/claude/` 的 guard，或新增任何 allow 規則。
* 修改 `scripts/campaign-closeout-audit.sh` 的判定邏輯與 exit code。
* 改 closer 的 `claude-role`（維持 `closer`，見 §6）。
* VS Code Copilot 與 Codex 的自動執行（只限 Claude Code，見 Q7）。
* 自動刪除殘留目錄。
* §5 的所有延後項。

## 2. 使用者裁決

### 2.1 第一輪（2026-10-22，rev.1 前）

| # | 裁決 |
|---|------|
| U1 | Phase B 一次同意；D1 重新觀測六值、`lsof -a -d cwd`、主工作樹分歧；全部一致且 STOP 條件都通過 → 自動執行；否則停下重新詢問；STALE 規則不變 |
| U2 | D5 納入：主工作樹同步、只改記錄的單一表格區塊、`git add <單一路徑>`、commit；push 交使用者 |
| U3 | 任何 `git push` 維持人工，不以換工具、拆指令、改寫形式繞過 |

### 2.2 第二輪（2026-10-22，看過 Plan Critic 報告後；rev.2 依此修訂）

| # | 裁決 |
|---|------|
| R1 | 範圍採 Plan Critic 的最小可行版本：只在 Claude Code、乾淨 `RETIRE_CANDIDATE`（Phase A 與 D1 稽核都 exit 0、無 `not_checked`、無點名例外）、ignored 集合為空或全部符合可重建樣式清單（`tmp/` 永遠不在清單內）時自動執行；其餘退回現行流程。刪掉 step log、Phase B 提前分類 ignored artifact、D2 digest 比對、capsule 存 patch-id。capsule 只有 README 原有五項、同意時間戳、`T_C`、`B_C` |
| R2 | 叫用方式：主對話由協調者派 closer subagent。同意在同一個 closer subagent 實例內有效（協調者以 SendMessage 續用）。試跑必須實測這條路徑在 Claude Code 2.1.307 可行；做不到就退回 Q1(c)：Phase D 先顯示 D1 對照表，再問一句是否執行。拒絕 Q1(b)。只測這一種叫用方式 |
| R3 | 遠端分支先採選項 A（Phase D 內 agent 檢查完停一次，請使用者刪）。選項 B 列為 pilot 通過後再評估的延後項 |
| R4 | 試跑要包含遠端分支情況（使用者推一個拋棄式分支，再親手刪除） |

### 2.3 第三輪（2026-10-22；rev.3 依此修訂）

| # | 裁決 |
|---|------|
| Q8 | `B_C` 改為 V-M-D 推送結案記錄那一次回報的 push base（推送前的 `origin/main`）。這個值已在交接契約「一次 push 一組 base／head」中，不新增欄位。B5 第一條改為 `rev-list --count <B_C>..HEAD == 1`，容忍 V-M-D rebase；記錄前偷插 commit 時計數為 2，仍判 STALE。D1 加交叉驗證：`B_C` 必須是 `HEAD^` 且是 `origin/main` 的祖先；並評估以 reflog 或 `HEAD^ == B_C` 獨立確認 push base |
| Q9 | 採 (a)：只觀察自然出現的核准提示，agent 不發任何 push 類指令 |
| Q10 | 採 (a)：維持主工作樹 root。試跑的協調者對話必須從主工作樹 root 新開；目前這個規劃對話的 shell cwd 因一次裸 `cd` 停在 `ttr-closer-auto-retire-worktree`，不能當試跑的協調者 |

### 2.4 依 Plan Critic 必須修正（rev.2 已納入）

| # | 修正 | 落在 |
|---|------|------|
| B1 | 例外不進自動範圍 | §4.1 E2 |
| B2 | 遠端檢查：fetch 後 `git cherry origin/main origin/<branch>` 沒有 `+`；`ls-remote` 的 SHA 是本地 tip 或其祖先；交接訊息提醒刪除會關閉該分支的 open PR | §4.4 D3c |
| B3 | 主工作樹每次 pull／commit 前檢查 `branch --show-current` 是 `main`，否則 STOP；pull 從 D1 移到 D3d 前與 D5；D1 維持唯讀 | §4.4 D1、D3d、D5 |
| B4 | 檔案清單補 README § Freshness、V-M-D Step 0.6 第 4 點前三子項、V-M-D frontmatter 的 closer handoff（要有「回到 Phase D」的路徑） | §7 |
| B5 | tip 判定改用確定性做法：`rev-list --count B_C..HEAD == 1`、`merge-base --is-ancestor HEAD origin/main`、HEAD 的 patch-id 等於 `T_C` 的 patch-id（D1 當場算）。`B_C` 的定義在 rev.3 依 Q8 改為 push base | §4.5 |
| B6 | 試跑納入串接情境；D3a–D4 連跑兩輪；量化門檻；D3b 列入閘門；D5 標為首次真實退役的 pilot 閘門 | §8 |
| 建議 1 | 啟動位置檢查提前到 Phase A | §4.2 |
| 建議 5 | worktree 計數重新推導時，回報寫明 X→Y | §4.4 D3b |
| 建議 4 | D3b 寫成受測腳本：**不放進最小可行版本**，列為延後項 | §5 L2 |

### 2.5 第四輪（2026-10-22，看過 Plan Critic 對 rev.3 的複核後；rev.4 依此記錄）

| # | 裁決 |
|---|------|
| R5 | **兩案先後：先做 Phase 1，其餘暫停。** pr-flow-tiering 已在 2026-10-22 實作 Tier 0（只動 `docs/**` 的 PR 由 workflow squash 合併），接下來試行兩週，其 Phase F 會改寫 closer、V-M-D 與 `git.instructions.md`。結案記錄位於 `docs/evaluation/campaigns/`，屬於 Tier 0；若改走 PR 再 squash 合併，SHA 會改變，也不會有 `update by push`，B5 與 reflog 判定都不適用。因此本計畫只執行 Phase 1（回填腳本與測試），Phase 2 試跑與 Phase 3 規則改寫暫停，等 pr-flow-tiering 的試行結果再決定 |
| R6 | **cwd 外漏：採 (a)，以 (c) 備援。** V-M-D Step 0.6 第 1 點的 `cd` 改用 `git -C` 或子 shell；若仍偵測到 cwd 在目標 worktree 內，一律 STOP。寫進 §7 #5 |

## 3. 現況事實（Architect 已查證）

| 事實 | 證據 |
|------|------|
| closer：`claude-role: closer`，Claude 白名單 `Read, Grep, Glob, Bash, AskUserQuestion`；Copilot `tools: [read, search, execute]` | `scripts/sync_ai_adapters.py` `ROLE_TOOLS`；agent frontmatter |
| `--check` 規定 Claude 白名單的能力類別不得超出 Copilot `tools:`；`Bash`→`execute` | `role_problems()` |
| `scripts/tests/test_sync_ai_adapters.py` 第 9 行固定 closer 為 `closer` | 同檔 |
| 靜態 guard 預判 66 條指令形式：不是 `allow` 的只有對帳 one-liner（deny `unsupported-syntax`）、`push --delete`（deny `git-force-push`）、`push origin main` 與 `push --dry-run`（ask `push-gate`） | `notes.md` §1 |
| auto mode 分類器與一般權限提示不在 guard 內，靜態預判看不到；agent 的 `git push origin HEAD:main` 曾被 auto mode 以 Production Deploy 拒絕 | SKILL § 遠端分支刪除與 push 到 main |
| Claude Code 目前 `2.1.307`；AGENTS.md 的白名單與 hooks 實測版本是 `2.1.292`–`2.1.296` | `claude --version`；AGENTS.md |
| Claude Code 的 Bash 環境有 `CLAUDECODE=1`，可用 `echo "claudecode=${CLAUDECODE:-unset}"` 判斷（guard 放行） | 本 session 實測 |
| 稽核腳本沒給 `--self-session` 就會 `self_session_unknown`，結果 `UNDETERMINED`（exit 20）。Claude Code session 不在 `~/.copilot/session-state/`，要傳 Claude Code 的 session id，exit 0 才可能出現 | `scripts/campaign-closeout-audit.sh` 第 868–871 行 |
| 全部 live worktree 的 ignored 項目樣式：`__pycache__/`、`.pytest_cache/`、`web/node_modules/`、`web/.next/`、`web/tsconfig.tsbuildinfo`、`web/next-env.d.ts`、`web/lib/specs/{specs-snapshot,system-map}.json`；另有**不可重建**的 `scraper/.env`、`web/.env.local`、`.copilot-tracking/`、`tmp/…`、`venv/`、`web/.vercel/`、`scraper/auto_scraper/runs/…` 等 | 以 `git status --porcelain --ignored` 盤點所有 live worktree |
| `web/lib/specs/*.json` 由 `web/scripts/build-specs-snapshot.ts` 從已追蹤的 docs 產生；過去的記錄都把它們與 `node_modules`、`.next` 分類為 `disposable` | `web/.gitignore` 第 48–49 行；`docs/evaluation/campaigns/2026-10-1*.md` |
| origin 上目前有 10 個 `feat/`／`fix/`／`chore/` 分支 | `git ls-remote --heads origin` |
| 從本 repo 推送時，`refs/remotes/origin/main` 會留下主旨為 `update by push` 的 reflog；2026-10-22 當天連續多筆皆是。`core.logAllRefUpdates=true` | `git reflog show refs/remotes/origin/main`（rev.3） |
| `~/.ai-notes/ttr/capsules/` 已存在、目前為空；capsule 位置沒有文件規定 | `ls`；全 repo grep |
| 封存的 `ai-portability` spec 有 0 個未勾選任務、0 行 deferred，可作為試跑時 Phase A exit 0 的 slug fixture | 掃描 `docs/specs/archive/*/` |

## 4. 最小可行版本（MVP）

圖例：**[agent]** closer 執行；**[user]** 使用者執行；**[STOP]** 停下回報、等使用者。

### 4.1 自動執行資格（全部成立才進自動路徑，否則整個 Phase D 走現行流程）

| # | 條件 | 怎麼判定 |
|---|------|---------|
| E1 | 在 Claude Code 中，且 session 從主工作樹 root 啟動（hooks 生效） | `echo "claudecode=${CLAUDECODE:-unset}"` 為 `1`；`echo "project_dir=${CLAUDE_PROJECT_DIR:-unset}"` 與 `/bin/pwd -P` 都是主工作樹 root 的物理路徑 |
| E2 | 乾淨 `RETIRE_CANDIDATE` | Phase A 稽核 exit 0；`not_checked` 為 0；使用者沒有點名接受任何例外（`ahead>0` 例外、確認取代 A3 等都不算乾淨） |
| E3 | ignored 集合為空，或每一行都符合可重建樣式清單 | 見下方清單。任何一行不符就不合資格 |
| E4 | path class 為 `canonical` 或 `divergent` | `external` 不合資格（殘留檢查與 exclude 的處理不同，留給延後項 L5） |
| E5 | 叫用方式是主對話協調者派出的 closer subagent | 唯一測過的叫用方式（R2） |

**可重建樣式清單**（比對 `git -C '<WT>' status --porcelain --ignored` 中 `!! ` 之後的路徑，整行比對，不是子字串）：

| 樣式 | 比對方式 | 重建方式 |
|------|---------|---------|
| `…/__pycache__/`（任何深度，含 root） | 正規式 `^(.+/)?__pycache__/$` | Python 從已追蹤的原始碼重新編譯 |
| `…/.pytest_cache/`（任何深度，含 root） | `^(.+/)?\.pytest_cache/$` | 任何一次 pytest 執行 |
| `web/node_modules/` | 字串相等 | `pnpm install`（lockfile） |
| `web/.next/` | 字串相等 | `next build` |
| `web/tsconfig.tsbuildinfo` | 字串相等 | `tsc`／`next build` |
| `web/next-env.d.ts` | 字串相等 | `next build`／`next dev` |
| `web/lib/specs/specs-snapshot.json` | 字串相等 | `web/scripts/build-specs-snapshot.ts` |
| `web/lib/specs/system-map.json` | 字串相等 | 同上 |

* `tmp/` 底下的任何東西、任何 `.env` 或 `.env.*`、`.copilot-tracking/`、`venv/`、`.venv/`、`web/.vercel/`、測試報告目錄、
  `scraper/auto_scraper/runs/`，以及**清單以外的任何一行**，都不合資格，不是「再判斷一下」。
* 不需要目錄 digest。清單內的項目全部可重建，D1 只比對「集合仍是清單的子集」。結案記錄的 Ignored artifacts 表照舊
  填寫：目錄填「not applicable (directory)」；清單內的單一檔案以 `shasum -a 256` 記錄 digest，但不拿來比對。

### 4.2 Phase A（小改）

在現行 A0–A6 之外新增三項，結果都寫進 A6 輸出：

1. **啟動位置與工具檢查**（建議 1）：E1 的三條指令。不成立時輸出 `auto_eligible=no (reason: …)`，並說明使用者要從主工作目錄
   重新啟動才可能自動執行。
2. **未完成的 capsule**：`ls -1 ~/.ai-notes/ttr/capsules/` 列出既有 capsule（Q5）。有其他 slug 的 capsule 代表某次退役沒做完，
   列在報告裡提醒使用者，不自行處理。
3. **自動資格**：輸出 `auto_eligible=yes`，或 `auto_eligible=no`，後者附上 E1–E5 中不成立的每一項。

### 4.3 Phase B 與 Phase C（小改）

* **Phase B**：`auto_eligible=yes` 時，詢問要一併列出：agent 會自動執行的步驟、使用者要做的三件事（推結案記錄、
  有遠端分支時刪遠端、推 disposition 回填），以及 D1 比對表中會讓 agent 停下的條件。`auto_eligible=no` 時照現行流程詢問。
  同意判準在 SKILL § Phase B 同意閘門的表格新增三列：「看到本次 Phase A 輸出後回覆『同意退役』＝同意 C 與 D 的自動執行」；
  「只同意寫記錄＝只同意 C」；「語意不清＝再問」。
* **同意當下 [agent]** 在 worktree 外寫 capsule：README 原有五項的「當時值」與同意時間戳（UTC），見 §4.6。
* **Phase C**：C1 與 C2 合成**一顆** commit，記為 `T_C` 寫進 capsule。Phase C **不**記 `B_C`：V-M-D 推送前通常要 rebase，
  commit 當下的 parent 不是最後的 push base。只有一顆 commit，B5 的 `rev-list --count <B_C>..HEAD == 1` 才成立。
* C4 交 V-M-D 時，closer 的回報要寫明：「push 完成後請協調者以 SendMessage 回到**這個** closer，進入 Phase D，並轉交 V-M-D
  這一次推送的 base／head」。這組值就是交接契約既有的「一次 push 一組 base／head」（SKILL § V-M-D → Closer 交接契約），不新增欄位。

### 4.4 Phase D（自動路徑）

| 步驟 | 誰 | 內容 | STOP 條件 |
|------|----|------|-----------|
| **D0 進入** | agent | (a) 是同一個 closer subagent 實例（context 裡有使用者對本次 Phase A 輸出的同意）；不是 → 走 Q1(c)：先做 D1，顯示對照表，再問一句是否執行；(b) capsule 存在且可讀；(c) 再跑一次 E1（`/bin/pwd -P` 仍是主工作樹 root，用來偵測 V-M-D `cd` 進 worktree 之後 cwd 有沒有漏過來）；(d) 從協調者轉交的結案記錄推送 base 取得 `B_C`，寫進 capsule（§4.6）。這個值在 D1 還要獨立驗證，不直接採信 | (b)(c) 不成立，或沒有轉交 push base → STOP |
| **D1 重新觀測（唯讀）** | agent | `git -C '<WT>' fetch origin main --quiet` 後依 §4.5 比對表逐項比對，並重跑稽核腳本（`--head` 沿用 pushed campaign HEAD） | 任一項不符 → STOP，輸出「Phase A／現在」對照表；需要新的同意 |
| **D2.5 capsule 更新** | agent | 寫入決策時間戳（D1 通過的時刻，與 README「decided at」語義一致）與 D1 觀測到的六值 | 寫入失敗 → STOP |
| **D3a 移除** | agent | 最後閘門：再跑一次 `lsof -a -d cwd` 與 dirty count。之後 `git -C '<主工作樹>' worktree remove '<registered path>'`，不加 `--force` | lsof 命中、dirty>0、rc≠0 → STOP；不 force，回報 git 原文訊息 |
| **D3b exclude 對帳** | agent | SKILL 的拆開版（per-path 子 shell 推導物理路徑 → 暫存檔 → 保留非 ttr 行並加入目標清單 → `mv` → `comm -23`、`comm -13`）。執行前以 `git worktree list` 計數當閘門，預期為 Phase A 計數減 1 | 計數不符 → 重新推導目標清單，回報寫明「計數 X→Y、重新推導」（建議 5）；`comm -23` 非空 → 重跑一次，仍非空 → STOP；任一指令被擋 → STOP 並走 fallback。回報逐行列出本 campaign 以外一併移除的過期行 |
| **D3c 遠端分支** | agent 檢查／user 刪除 | `git -C '<主工作樹>' fetch origin` → `git ls-remote --heads origin <branch>`。沒有 → 跳到 D3d。有（SHA 記為 `R`）→ `git -C '<主工作樹>' cherry origin/main origin/<branch>` 沒有 `+`，且 `git merge-base --is-ancestor R <local tip>` 為 yes；可用 `gh` 時以 `gh pr list --head <branch> --state open` 列出 open PR。通過後**停一次**，給使用者一行 `git -C '<主工作目錄>' push origin --delete <branch>`，並提醒「刪除會關閉這個分支的 open PR：<列表或 not_checked>」 | `cherry` 有 `+`，或 `R` 不是本地 tip 的祖先（遠端有本地沒有的 commit）→ STOP |
| **D3c 續** | agent | 使用者回報後，以 `ls-remote` 確認已刪，再 `git -C '<主工作樹>' fetch origin --prune` | 仍存在 → 再給一次指令 |
| **D3d 刪本地分支** | agent | `git -C '<主工作樹>' branch --show-current` 是 `main`（B3）→ `git -C '<主工作樹>' pull --ff-only origin main` → `git -C '<主工作樹>' merge-base --is-ancestor <branch tip> main` 為 yes → `git -C '<主工作樹>' branch -d <branch>` | 不在 `main`、pull 失敗、不是祖先、`-d` 拒絕 → STOP；絕不 `-D` |
| **D4 殘留驗證** | agent | README § Cleanup checklist 的四個標籤檢查，加上遠端分支、`.git/worktrees/<name>`、worktree 計數 | `directory=RESIDUE` → 跑 UNIQUE 檢查並回報，刪除交使用者；其餘不符 → STOP |
| **D5 回填（pilot 閘門）** | agent | 見 §4.7 | 見 §4.7 |
| **D5-push** | user | agent 給一行 `git -C '<主工作目錄>' push origin main`（行尾不加註解） | — |
| **D6 收尾** | agent | 使用者回報後 fetch；`git -C '<主工作樹>' show origin/main:'<record>' \| python3 '<主工作樹>/scripts/campaign-disposition-backfill.py' --verify --capsule '<capsule>'` 通過；通過後刪 capsule；輸出完成回報 | `--verify` 失敗 → STOP |

#### 遠端分支的順序

要守的不變式只有一條：**刪遠端必須在 `-d` 之前。** 遠端刪除後本地 upstream tracking ref 消失，`-d` 改以 HEAD（主工作樹的
`main`，D3d 已 pull）判定；遠端還在且等於本地 tip 時，`-d` 會平凡地通過，什麼都證明不了。是否有獨有 commit 仍以 A2 與
`git cherry` 判定，D3c 的兩道檢查與 D3d 的 `merge-base --is-ancestor` 都不弱於現行規則。MVP 的順序是
「remove → exclude → 檢查遠端並停一次 → 使用者刪遠端 → `-d` → D4 → D5」。

#### 使用者介入次數（MVP）

| 情境 | 使用者動作 |
|------|-----------|
| 沒有遠端分支 | 同意一次 → 推結案記錄（V-M-D 給的指令）→ 推 disposition 回填，外加偶爾的核准提示 |
| 有遠端分支 | 上述，再加 Phase D 中途刪遠端一次 |
| 不合資格（E1–E5 任一不成立） | 現行流程 |

### 4.5 D1 比對表（Q3 已決，2026-10-22）

| 項目 | Phase A 基準 | Phase D 要求 | STALE 條件 |
|------|-------------|-------------|-----------|
| branch tip | capsule 的 `B_C`（push base）、`T_C` | B5 三條件：`git -C '<WT>' rev-list --count <B_C>..HEAD` 等於 `1`；`git -C '<WT>' merge-base --is-ancestor HEAD origin/main` 為 yes；`git -C '<WT>' show HEAD \| git patch-id --stable` 與 `git -C '<WT>' show <T_C> \| git patch-id --stable` 的第一欄相同（D1 當場計算，不存在 capsule） | 任一條件不成立 |
| push base 交叉驗證 | capsule 的 `B_C` | 三項都成立：(1) `git -C '<WT>' rev-parse HEAD^` 等於 `B_C`；(2) `git -C '<WT>' merge-base --is-ancestor <B_C> origin/main` 為 yes；(3) reflog 確認：`git -C '<主工作樹>' reflog show --format='%H %gs' refs/remotes/origin/main` 中，值等於 `HEAD` 且主旨為 `update by push` 的那一筆，下一筆（較舊）的值等於 `B_C` | (1)(2) 不成立 → STALE；(3) 找不到該筆或值不同 → 無法獨立確認，依 Q1(c) 顯示對照表再問一句 |
| ahead | 0 | 0 | ≠0 |
| behind | 記錄 | **不比對**，只記錄 | — |
| dirty count | 0 | 0 | ≠0 |
| ignored artifact set | Phase A 集合（是清單的子集） | 仍是可重建樣式清單的子集。清單內新增或消失的項目都不算 STALE | 出現清單外的任何一行 |
| path identity | registered、physical、path class | 三者相同 | 任一不同 |
| 占用 | 無命中 | `lsof -a -d cwd` 無命中（外層 zsh 列為獨立占用者） | 有命中 |
| 主工作樹分歧 | — | `git -C '<主工作樹>' rev-list --left-right --count origin/main...main` 的右側為 0（落後沒關係，D3d 前會 pull）。D1 不 pull | 右側 >0（`main` 有未推送的 commit） |
| 稽核 verdict | exit 0 | exit 0 | 其他任何 exit code |
| worktree 計數 | `N_A` | 只供 D3b 閘門 | — |

**tip 判定為何容忍 rebase（Q8，rev.3）**：`B_C` 是推送前的 `origin/main`，所以不論 V-M-D 是否 rebase，推上去的結案記錄
commit 都直接接在 `B_C` 之後，`<B_C>..HEAD` 只有它一顆。記錄之前若有人在 worktree 偷插 commit 並一起推上去，`<B_C>..HEAD`
就是 2 顆，判 STALE。patch-id 條件確認那一顆就是 Phase C 寫的記錄。

**push base 能否獨立確認（評估結論）**：

* **`HEAD^ == B_C` 不是獨立證據。** 它只證明轉交的值與圖上的 parent 一致。若轉交的值本身錯了，而且剛好寫成 `HEAD^`
  （例如推送其實含兩顆 commit，真正的 base 是 `HEAD^^`），這一條與計數條件都會通過。它留作一致性檢查，擋下打錯或抄錯的值。
* **`refs/remotes/origin/main` 的 reflog 是獨立證據。** 使用者依規定從主工作目錄執行 `git -C '<主工作目錄>' push origin <分支>:main`
  時，git 會更新本 repo 共用的 remote-tracking ref，並寫一筆主旨為 `update by push` 的 reflog，新值是推上去的 head、前一筆的值就是
  推送前的 `origin/main`。這是 git 在推送當下寫的，不經過任何 agent 轉述。本機已實測存在：2026-10-22 當天的 `origin/main` reflog
  連續多筆都是 `update by push`（例如新值 `0099dbb5` docs(agents): record the ai-portability archive lessons in history and skills
  的那一筆，前一筆是 `3fe84edb` fix(agents): campaign closeout audit resolves date-prefixed archive directories）。
  `core.logAllRefUpdates` 為 `true`。
* **reflog 的限制**：推送若不是從本 repo 發出（別台機器、GitHub 網頁、別的 clone），本地只會在之後 fetch 時看到一筆
  `fetch: fast-forward`，可能一次跨過多顆 commit，無法確認 base。reflog 被 `git reflog expire` 清掉時同樣無法確認。這兩種情況
  不當作 STALE（資料沒有風險），但也不自動執行：依 Q1(c) 顯示對照表再問一句。
* **結論**：自動執行需要三項全部成立。(1)(2) 擋錯值，(3) 才是獨立確認。

### 4.5.1 判定案例

| 情境 | `<B_C>..HEAD` 計數 | `HEAD^ == B_C` | reflog | 結果 |
|------|-------------------|----------------|--------|------|
| 沒有 rebase，直接 ff 推送 | 1 | 是 | 前一筆 = `B_C` | 通過 |
| V-M-D rebase 到較新的 `origin/main` 後推送 | 1 | 是 | 前一筆 = `B_C` | 通過 |
| 記錄前偷插一顆 commit，一起推送，轉交的 base 正確 | 2 | 否 | 前一筆 = `B_C` | STALE |
| 同上，但轉交的 base 錯寫成 `HEAD^` | 1 | 是 | 前一筆 = `HEAD^^` ≠ `B_C` | 無法確認 → 再問一句（Q1(c)） |
| 推送不是從本 repo 發出 | 1 | 是 | 找不到 `update by push` 那一筆 | 無法確認 → 再問一句 |

### 4.6 capsule

* 位置：`~/.ai-notes/ttr/capsules/<YYYY-MM-DD>-<slug>.md`，在 repo 外，不 commit。
* 內容只有：README § Recovery capsule 的五項（六值、決策時間戳、記錄的 repo-relative 路徑、registered path 與 branch、
  ignored artifact 的處置與 digest）＋同意時間戳＋`T_C`＋`B_C`。**不含 step log、patch-id、最終區塊文字。**
* 寫入時點：五項與同意時間戳在 Phase B 同意當下；`T_C` 在 Phase C commit 之後；`B_C` 在 **V-M-D 回報推送之後**，於 D0(d) 由協調者
  轉交的那一次推送的 base 寫入（rev.3，Q8）。D1 再以 §4.5 的交叉驗證確認。
* 格式：每項一行 `key: value`（鍵名寫進 SKILL），讓回填腳本的 `--verify` 能直接解析。
* 處置（Q5 已決）：D6 的 `--verify` 通過後刪除。Phase A 會列出殘留的 capsule。

### 4.7 D5 回填（pilot 閘門）

主工作樹是 governance-only；disposition 回填屬於狀態對帳的文件 commit，符合 `git.instructions.md` 允許的範圍。

1. **[agent]** `git -C '<主工作樹>' branch --show-current` 是 `main`（B3）；不是 → STOP。
2. **[agent]** `git -C '<主工作樹>' status --porcelain -- '<record>'` 為空，且 `git -C '<主工作樹>' diff --cached --name-only` 為空；
   任一不空 → STOP。其他路徑的未提交修改不處理、不 stash、不 clean，只在回報中列出。
3. **[agent]** `git -C '<主工作樹>' pull --ff-only origin main`；失敗 → STOP。
4. **[agent]** agent 依 capsule 與 D4 的觀測寫出新區塊（寫在 scratch），再執行
   `python3 '<主工作樹>/scripts/campaign-disposition-backfill.py' --record '<主工作樹>/<record>' --block '<block file>' --capsule '<capsule>'`：
   * 區塊含 `pending` → 替換，印出 diff；
   * 區塊已不含 `pending` 且 `--verify` 的檢查通過 → `already_applied`（續跑時跳到步驟 6 或 D6）；
   * 其他 → `unexpected_state`（exit 3）→ STOP。
5. **[agent]** `git -C '<主工作樹>' diff --stat` 只列出這一個檔案；`git -C '<主工作樹>' add '<record>'`；再次確認在 `main`；
   `git -C '<主工作樹>' commit --only -m "$(cat <<'EOF' … EOF)" -- '<record>'`。
6. **[user]** 執行 D5-push 的一行指令。

**pilot 閘門**：D5 只在 scratch clone 中試過替身（§8），所以第一次真實退役的 D5 視為 pilot。任一步被擋，D5 的規則改寫成
「產生指令交使用者」，D3a–D4 的自動化不受影響。

### 4.8 中斷與續跑（沒有 step log，以實際狀態判斷）

| 步驟 | 完成探測 | 未完成時 |
|------|---------|---------|
| D3a | `git worktree list` 不含該路徑，且目錄不存在 | 從 D0 重新開始（worktree 還在，必須重新比對） |
| D3b | exclude 區塊與 live 目標清單的 `comm` 雙向都空 | 重跑整塊對帳 |
| D3c | `ls-remote` 沒有該分支 | 重做 D3c 的檢查，再給使用者同一行指令 |
| D3d | `refs/heads/<branch>` 不存在 | 執行 D3d |
| D4 | 標籤檢查全部是預期值 | 重跑 D4 |
| D5 | 主工作樹的記錄區塊通過 `--verify` | 從 §4.7 步驟 1 重跑 |
| D6 | `origin/main` 上的記錄通過 `--verify` | 再給 push 指令 |

D3a 之後的續跑不需要重新同意：worktree 已移除，剩下的步驟各有保護（對帳收斂、`-d` 拒絕未合併、回填冪等），是在完成
已同意的動作。若續跑時已不是同一個 closer 實例，依 Q1(c)，先顯示上表的探測結果再問一句。

### 4.9 Fallback 與回報

* 任何一步遇到 guard deny、auto mode 拒絕，或使用者在核准提示按拒絕：**停在該步**，不換形式重試。回報寫明停在哪一步、
  已完成哪些步、capsule 路徑、該步交使用者執行的完整指令（每行一條、行尾不加註解），以及「執行後回來說『繼續』」。
* 不得使用 `--dangerously-skip-permissions`、`disableAllHooks`、`settings.local.json`、`!` shell 前綴，或包成腳本來避開規則。
* 完成回報在現行內容之外新增：每一步的執行者與結果（agent 附 rc；交使用者的附指令）、停點、exclude 一併移除的過期行、
  計數 X→Y、capsule 處置。commit 一律附主旨與日期，不放裸 SHA。

## 5. 延後項（不在 MVP，各附觸發條件）

| # | 項目 | 為何延後 | 觸發條件 |
|---|------|---------|---------|
| L1 | 遠端刪除選項 B：與推送結案記錄同時刪，少停一次 | R3 | 首次真實退役 pilot 通過，且之後至少兩次遇到遠端分支 |
| L2 | D3b exclude 對帳寫成受測腳本（Plan Critic 建議 4） | 拆開版在 guard 層已放行（`notes.md` §1），演算法已寫在 SKILL；腳本化要同時改 `git.instructions.md` 的 canonical 機制，擴大這次的範圍 | 試跑或任一次真實退役中，D3b 被擋、重跑後 `comm -23` 仍非空，或模型打錯拆開版而需要人工修復；或 D3b 成為唯一剩下的人工步驟 |
| L3 | 點名例外（`ahead>0` rebase 例外、以使用者確認取代 A3）進入自動範圍 | B1 | pilot 通過後，有兩次以上這類退役，且例外的證據能機械化 |
| L4 | 清單以外的 ignored artifact（含 `tmp/`、`.env*`）以 digest 比對後自動處理 | R1 | 清單外的項目讓 3 次以上退役不合資格 |
| L5 | `external` path class 進入自動範圍 | E4 | 出現 external 的退役需求 |
| ~~L6~~ | ~~放寬 B5，容許 V-M-D rebase~~ | rev.3 刪除：Q8 把 `B_C` 改為 push base 後，B5 已容忍 rebase | — |
| L7 | VS Code Copilot、Codex 的自動執行 | 沒有 hooks 防線（Q7） | 另案評估 |
| L8 | 殘留目錄的自動刪除 | 少見、不可逆 | 另案 |
| L9 | Phase C 多顆 commit | B5 需要單一 commit | 出現無法合併成一顆的情況 |

## 6. D5 改記錄區塊的機制（Q4 已決，2026-10-22）

採用新增專案腳本 `scripts/campaign-disposition-backfill.py`（純標準庫，不執行 git，不碰網路）：

* `--record <path> --block <file> --capsule <file>`（apply）：只替換 `## Worktree disposition` 標題到下一個 `## ` 之間的內容；
  三種結果如 §4.7 步驟 4。
* `--verify --capsule <file>`，從 stdin 讀記錄全文（呼叫端以 `git show origin/main:<record> |` 餵入）：**只檢查 disposition 區塊**
  不含 `pending`、處置為 `remove`、`decided at` 等於 capsule 的決策時間戳、六值表格與 capsule 一致。exit 0／非 0。
  D6 用它取代「整份 grep pending」，因為記錄的其他段落可能合法地出現 `pending` 這個字。
* 測試 `scripts/tests/test_campaign_disposition_backfill.py`：`pending` 替換成功；已套用 → `already_applied`；區塊被改過 →
  `unexpected_state`；沒有該標題 → 錯誤；區塊外逐位元相同；檔尾區塊（後面沒有 `## `）；`--verify` 對區塊外的 `pending` 不誤判；
  capsule 缺鍵 → 錯誤。

`sync_ai_adapters.py --check` 不受影響：`claude-role` 與 Copilot `tools:` 都不變，腳本走 `Bash`（`execute`）。改角色
（`full` 或加 Edit）會觸發 `exceeds Copilot tools … edit`，還要改 `test_sync_ai_adapters.py` 第 9 行與 AGENTS.md，不採用。
保留 Bash 的角色可經重導寫檔，這是已接受的殘餘風險，不變。

## 7. 要改的檔案清單

> **rev.4**：目前只執行 Phase 1（#7、#8，以及 #9 的 `proposal.md`／`tasks.md`）。其餘各列屬 Phase 3，暫停到恢復條件成立（§2.5 R5）。

Engineer 在 `ttr-closer-auto-retire-worktree`（`feat/closer-auto-retire`）依序進行：**Phase 1** 腳本與測試（試跑的 D5 替身要用）→
**Phase 2** §8 試跑、寫 `notes.md` →（通過決策閘門）→ **Phase 3** 修改下列規則文件。閘門未通過就停在 Phase 2，腳本保留在分支、
不改規則文件。

| # | 檔案 | 要改的段落 |
|---|------|-----------|
| 1 | `.github/agents/campaign-closer.agent.md` | frontmatter `description`；frontmatter handoff「🚀 Push close-out record」的 prompt（push 完以 SendMessage 回到同一個 closer 的 Phase D）；開頭簡介；§ Phase A（新增 §4.2 三項）；§ Phase B（自動範圍的告知內容）；§ Phase C（單一 commit、`B_C`／`T_C`、C4 回報）；**§ Phase D 重寫**：開頭改為「符合 §4.1 資格時自動執行，否則維持產生指令」，加入 D0–D6 表，**保留**現行人工流程作為 fallback；§ 完成後（§4.9 回報） |
| 2 | `.github/skills/agents/campaign-closer/SKILL.md` | `ms.date`；新增 § 自動執行資格（E1–E5、可重建樣式清單、「Copilot／Codex 維持產生指令」）；§ Phase B 同意閘門表新增三列；§ Recovery capsule（位置、鍵名、只有 5＋3 項、D6 後刪除、Phase A 列出殘留）；§ Phase D 各小節：§ 重新觀測 session 占用（D3a 前最後閘門）、§ 給使用者的 push 指令（D5-push、遠端刪除兩種格式）、§ exclude 對帳被 hook 擋下時（拆開版是 agent 執行的主要形式）、§ exclude 目標清單第 2 點「貼上 D3 指令前」改為「執行 D3b 前（agent 執行或交使用者皆同）」並加 X→Y 回報、§ 遠端分支刪除與 push 到 main（B2 檢查、PR 提醒、停一次）、§ `git branch -d` 通過不代表沒有獨有 commit（不變式改寫、D3d 前置）、§ Cleanup 檢查（B3：每次 pull／commit 前 `branch --show-current`）；新增 § D1 比對表（§4.5：B5、`B_C` 的定義與取得時點、push base 交叉驗證與 reflog 的限制、§4.5.1 判定案例）；§ V-M-D → Closer 交接契約補一句「Phase D 的 `B_C` 取自結案記錄那一次推送的 base，不新增欄位」、§ 中斷與續跑（§4.8）、§ Fallback（§4.9）、§ 試跑結果（摘要 `notes.md`） |
| 3 | `.github/instructions/git.instructions.md` | § Cleanup：指令區塊後補一段「campaign worktree 符合 closer 自動資格時，由 closer 在使用者同意後執行 remove、`-d`、exclude 對帳；`git push` 類步驟由使用者執行；不合資格或被擋時產生指令」，指向 SKILL。§ Reconciling 最後一段補「closer 執行拆開版」。機制不改 |
| 4 | `docs/evaluation/campaigns/README.md` | **§ Freshness**（約第 241 行「If any of the six differs … STALE」）：補一句「The closer's automated path compares under the expected deltas in the campaign-closer SKILL (one close-out commit on the tip, `behind` not compared, regenerable ignored entries)；any other difference is STALE」。§ Recovery capsule：commit 由 agent、push 由 owner。§ Cleanup checklist：開頭補「可由 closing agent 在 owner 一次同意後執行，條件與比對規則見 SKILL；push 類步驟由 owner 執行」 |
| 5 | `.github/agents/validate-merge-deploy.agent.md` | **Step 0.6 第 1 點（R6，2026-10-22 裁決）**：「`cd` 進該 worktree」改為以 `git -C '<worktree>'` 或子 shell `( cd '<worktree>' && … )` 確認分支與路徑，不改變 Bash 的持續 cwd；closer 的 D0(c) 與 D1 若仍偵測到 cwd 在目標 worktree 內，一律 STOP（備援）。**Step 0.6 第 4 點**：前三個子項（記錄在 `origin/main`、重新觀測六值、ignored preflight）是 closer D1 的重複定義，改為一句「cleanup 前的重新觀測由 closer Phase D 的 D1 比對表負責」；第四子項改為「交回 closer」；「V-M-D 不自動執行 `git worktree remove` 或 `git branch -d`」保留。**frontmatter**：新增 handoff「↩️ Return to closer Phase D」，prompt 寫「結案記錄已推送，push base（推送前的 origin/main）= <base-sha>，pushed HEAD = <head-sha>。請以 SendMessage 回到原本的 Close Campaign closer 進入 Phase D；無法續用時，新開的 closer 從 D0 開始，依 Q1(c) 先顯示 D1 對照表再詢問，不從 Phase A 重新盤點」。既有「🧾 Close campaign & retire worktree」（從 Phase A 開始）保留給首次結案 |
| 6 | `AGENTS.md` | 角色路由表 Close Campaign 一列：補「符合資格時，使用者同意後執行 worktree 退役；push 類步驟交使用者」 |
| 7 | `scripts/campaign-disposition-backfill.py`（新） | §6 |
| 8 | `scripts/tests/test_campaign_disposition_backfill.py`（新） | §6 |
| 9 | `docs/specs/active/closer-auto-retire/proposal.md`、`tasks.md`（新） | 依 `_template/` 建立；`tasks.md` 依 Phase 1–3 與 §8 列項 |
| 10 | `docs/specs/active/closer-auto-retire/notes.md` | 試跑紀錄（已有 §1 靜態預判與 §2 空表） |
| 生成 | `.claude/agents/close-campaign-retire-worktree.md`、`.claude/agents/validate-merge-deploy.md` 等 | `python3 scripts/sync_ai_adapters.py` 產生，不手改 |

全 repo 搜尋後確認**不需要改**的引用（Phase 3 完成後再 grep 一次，確認沒有新增矛盾）：

| 位置 | 理由 |
|------|------|
| V-M-D Step 4 第 2 點（push 由使用者執行） | 與 U3 一致 |
| `AGENTS.md` 第 43 行（V-M-D 一列）、§ Hooks 規則表 | 與 U3 一致 |
| `docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md` 第 488 行 | 仍成立 |
| `docs/specs/README.md` 第 48 行 | 只描述機制 |
| `.github/prompts/ledger-topology-reconcile.prompt.md`、`.github/prompts/admin-qa-cleanup.prompt.md` | 歷史紀錄與禁令 |
| `docs/specs/active/workstream-tracking/tasks.md` | 資料，不是規則 |
| `docs/evaluation/campaigns/20*.md` | 已提交的記錄不改寫 |
| `.github/skills/agents/campaign-closer/history.md` | 由 Update History agent 追加，不改舊條目 |
| `scripts/claude/_policy.py`、`.claude/settings.json` | 非目標 |

## 8. 試跑計畫與決策閘門

### 8.1 已完成：靜態 guard 預判（Architect）

66 條指令形式離線評估，結果在 `notes.md` §1。只反映 guard，不反映 auto mode 與權限提示。

### 8.2 實測環境（全部記錄進 notes.md §2）

* Claude Code `2.1.307`（或當時版本）；從主工作樹 root 啟動；auto mode 開啟，與使用者平常相同。
* **試跑的協調者對話必須從主工作樹 root 新開**（Q10）。產出本計畫的規劃對話不能當協調者：它的 shell cwd 因一次裸 `cd`
  停在 `ttr-closer-auto-retire-worktree`，E1 會不成立，lsof 也可能命中它。新對話開始後先跑 E1 的三條指令確認。
* 叫用方式只有一種：主對話的協調者派 closer subagent（R2）。V-M-D 也以協調者派出的 subagent 執行。
* 每條指令單獨一次 Bash 呼叫，不平行送出；輸出帶 `<檢查名>=<結果>` 標籤。
* Phase A 的 slug fixture 用 `ai-portability`（已封存，0 未勾、0 deferred）；`--base` 與 `--head` 都給 trial 分支的起點
  （單段相容形式，range 為 0 commit 時 `range_todo=0`）；`--self-session` 傳協調者的 Claude Code session id。期望 exit 0；
  不是 exit 0 就記錄原因，那一輪改測人工路徑。
* 試跑分支沒有 commit，也不推結案記錄到 main，所以 B5、push base 交叉驗證與 D5 在 trial worktree 上無法測，改在 T-C 測。
  T-A 的 D1 對這幾項記為「試跑不適用」，其餘照常比對。

### 8.3 T-A 串接情境＋第一輪（有遠端分支）

1. **[user/agent]** 建 `ttr-closer-trial-a-worktree`（分支 `chore/closer-trial-a-20261022`，從 `origin/main`），加 exclude 行，
   放一個符合清單的 ignored 項目：`mkdir -p '<trial>/scripts/__pycache__'` 後
   `printf 'trial\n' > '<trial>/scripts/__pycache__/closer_trial.cpython-312.pyc'`（應顯示為 `!! scripts/__pycache__/`）。
2. **[user]** 推遠端：`git -C '<主工作目錄>' push origin chore/closer-trial-a-20261022`（R4）。
3. **[協調者]** 派 closer subagent，提示寫明這是試跑：Phase A → 回報。檢查 `auto_eligible`、capsule 列表、E1 輸出。
4. **[user]** 對 Phase A 輸出回覆「同意退役」→ **[協調者]** 以 SendMessage 續用**同一個** closer：「Phase C 試跑」只寫 capsule、不 commit。
5. **[協調者]** 派 V-M-D subagent，只執行 Step 0.6 第 1 點（`cd` 進 trial worktree、確認分支），不 rebase、不 commit、不給 push 指令，然後結束。
6. **[協調者]** 以 SendMessage 回到**同一個** closer，進入 Phase D。觀察並記錄：
   * **R2 可行性**：SendMessage 是否真的接回同一個實例（closer 能否引述 Phase A 的觀測值與同意時間）。不行 → 記錄並改用 Q1(c) 繼續。
   * **cwd 外漏**：D0(c) 的 `/bin/pwd -P`、D1 的 `lsof -a -d cwd` 是否命中 V-M-D 留下的 shell 或 closer 自己。
   * **背景 subagent 遇核准提示**：只觀察自然出現的提示（Q9 (a)）；agent 不為了測試而發任何 push 類指令。出現時記錄提示出現在
     哪裡（主對話或其他位置），以及 subagent 是等待、失敗還是被當作拒絕；整個試跑都沒出現就記「未觀察到」。
7. **[closer]** D1 → D2.5 → D3a → D3b → D3c（停）→ **[user]** 刪遠端 → **[closer]** D3c 續 → D3d → D4。

### 8.4 T-B 第二輪（沒有遠端分支）

建 `ttr-closer-trial-b-worktree`（分支 `chore/closer-trial-b-20261022`），不推遠端。先放 `tmp/closer-trial.txt` 跑一次 Phase A，
確認 `auto_eligible=no`（E3 負向案例），刪掉後再跑一次。協調者派**新的** closer subagent：Phase A →
同意 → 直接進 Phase D（不經 V-M-D），跑 D1–D4。這一輪重複 D3a–D4，檢查第一輪的結果能否重現。

### 8.5 T-C scratch clone（B5、push base 交叉驗證、D5 替身）

clone 裡沒有真的 push（Q9：agent 不發 push 類指令），所以「推送」以 `git -C '<clone>' merge --ff-only <分支>` 讓 clone 的 `main`
前進來模擬；`B_C` 取模擬推送前的 clone `main`。

1. `git clone --local '<主工作樹>' '<scratch>/d5-clone'`。
2. **正向（沒有 rebase）**：`B_C` = clone `main`；在分支上做 `T_C`（含 `pending` 的假記錄）一顆 commit，ff 到 `main`。
   預期：計數 1、`HEAD^ == B_C`、patch-id 相同 → 通過。
3. **正向（rebase 後）**：在分支上做 `T_C`；clone `main` 另加一顆上游 commit `U`；把 `T_C` rebase 到 `U`，`B_C` = `U`；ff 到 `main`。
   預期：計數 1、`HEAD^ == U`、patch-id 與 rebase 前的 `T_C` 相同 → 通過。
4. **負向（偷插 commit）**：在分支上先做一顆無關 commit `S`，再做 `T_C`；`B_C` = 模擬推送前的 `main`；ff 到 `main`。
   預期：計數 2、`HEAD^ ≠ B_C` → STALE。另以錯誤的 `B_C' = S` 重算：計數 1、`HEAD^ == S` 都通過，記錄「只有 reflog 能擋下這一案」。
5. **reflog 查找（唯讀，在真實 repo）**：對 2026-10-22 已知的一次推送（新值 `0099dbb5` docs(agents): record the ai-portability
   archive lessons in history and skills）執行 §4.5 的查找程序，預期找到的前一筆值是 `3fe84edb` fix(agents): campaign closeout
   audit resolves date-prefixed archive directories。再以錯誤的 base 查一次，預期不符。
6. D5 全程：`branch --show-current`、status 與 cached 檢查、`pull --ff-only`、腳本 apply、`diff --stat`、`add`、
   `commit --only -m "$(cat <<'EOF' … EOF)" -- <path>`、`--verify`（以 `git show main:<record> |` 餵入）。
7. 清理：`rm` 試跑 capsule、`rm -rf` clone（記錄是否出現核准提示）。
8. 首次真實退役時（pilot），再以真實推送驗證步驟 5 的 reflog 查找：預期找到 `update by push`，且前一筆等於 V-M-D 轉交的 base。

### 8.6 決策閘門

先算基準：**省下的貼上次數**＝兩輪中改由 agent 執行、在現行流程要使用者貼上的獨立指令條數（不含 push）。在 notes.md
逐條列出後加總，例如 `pull`、`worktree remove`、exclude 拆開版的每一條、`branch -d`。

| 結果 | 處置 |
|------|------|
| D3a 或 D3d 在任一輪被 auto mode 拒絕 | **停下回報，不進 Phase 3** |
| 任一輪被拒的步驟 | 該步改交使用者（規則寫成產生指令） |
| 改交使用者的步驟 ≥3（D3b 計入） | **停下回報，不進 Phase 3** |
| 兩輪核准提示次數合計 > 省下的貼上次數 | **停下回報，不進 Phase 3** |
| R2 路徑不可行 | 不停；Phase 3 的 D0 規則改寫為 Q1(c) |
| cwd 外漏使 D0(c) 或 lsof 命中 | 不停；記錄成因，規則補「協調者在 V-M-D 之後……」的具體處置，再進 Phase 3 |
| T-C 中 D5 的任一指令被擋 | D5 規則改為產生指令；其餘照常 |
| 都沒有命中上列停下條件 | 進 Phase 3；D5 在首次真實退役仍是 pilot 閘門（§4.7） |

清理：試跑結束後 `ttr-closer-trial-a-worktree`、`ttr-closer-trial-b-worktree` 應已由試跑本身退役。任一輪中途停下時，由使用者依
fallback 指令收尾。

## 9. 風險與殘餘風險

| 風險 | 處置 | 殘餘 |
|------|------|------|
| auto mode 行為看不到，且會隨版本改變 | §8 實測；fallback；SKILL 註明實測版本，升級後重跑 | 改版後第一次退役可能停在某一步 |
| 同意與執行相隔一個 V-M-D 週期 | D1 完整重新觀測；D3a 前最後閘門；同意只在同一個 closer 實例內有效 | 只開資料夾、沒有行程 cwd 的 VS Code 視窗偵測不到（既有邊界）；git 本身會拒絕移除有修改或未追蹤檔的 worktree |
| 轉交的 push base 有誤 | D1 的 `HEAD^ == B_C`、祖先檢查與 reflog 獨立確認（§4.5） | 推送不是從本 repo 發出時無法獨立確認，退回再問一句 |
| 主工作樹的平行 session | B3；只碰單一路徑、`commit --only`、index 有東西就停、不 stash／clean、`pull --ff-only` 失敗就停 | pull 與 commit 之間被改的機率極低，會在 push 被拒或 D6 被發現 |
| exclude 對帳競態 | 收斂式整塊對帳、雙向 `comm`、計數閘門 | 只能偵測、無法消除（既有） |
| 刪遠端會關閉 open PR | D3c 列出 open PR 並提醒 | `gh` 不可用時只能寫 `not_checked` |
| Bash 寫檔 | 角色不變；回填用受測腳本 | 已接受 |
| Copilot／Codex | 不自動執行，維持產生指令 | 無變化 |
| 試跑動到主工作樹（建、移除 trial worktree、改 exclude、推並刪遠端 trial 分支） | trial 分支從 `origin/main` 建、沒有 commit；對帳本身就是被驗證的對象 | 中途停下時由使用者依 fallback 收尾 |

## 10. 驗證步驟（Phase 3 完成後）

```bash
W='/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-closer-auto-retire-worktree'
python3 "$W/scripts/sync_ai_adapters.py"
python3 "$W/scripts/sync_ai_adapters.py" --check
python3 -m pytest "$W/scripts/claude/tests" "$W/scripts/tests" -q
```

文字檢查（每條輸出帶標籤）：

* closer agent 檔的 Phase D 開頭以資格條件區分兩條路徑；現行人工流程仍在，作為 fallback。
* SKILL 不再出現「貼上 D3 指令前」。
* README § Freshness 有 expected-delta 的指向。
* V-M-D Step 0.6 第 4 點不再重複六值與 ignored preflight 的定義；frontmatter 有「Return to closer Phase D」handoff。
* `git grep -n -E '由使用者執行|交使用者|不自動執行'` 逐筆對照 §7「不需要改」清單。
* `git -C "$W" diff --stat origin/main` 只列出 §7 的檔案與生成檔。
* `.claude/agents/close-campaign-retire-worktree.md` 的 `tools:` 仍是 `Read, Grep, Glob, Bash, AskUserQuestion`。

之後：交 Plan Critic 或 Tester 複核；首次真實退役當作 pilot（D5 閘門），結果由 Update History agent 寫進 closer 的 `history.md`。

## 11. Worktree & Spec Tracking

1. Spec：`docs/specs/active/closer-auto-retire/`（本檔、`notes.md`；Engineer 補 `proposal.md`、`tasks.md`）。
2. Worktree：`ttr-closer-auto-retire-worktree`，branch `feat/closer-auto-retire`，CONTINUING。基於 origin/main 的
   `0099dbb5` docs(agents): record the ai-portability archive lessons in history and skills（2026-10-22）；exclude 行已存在。
3. Phase 0：Engineer 先讀 `.github/instructions/git.instructions.md` § Isolated worktree，以 `git worktree list --porcelain` 確認現況；
   工作樹乾淨時 `git -C '<worktree>' fetch origin && git -C '<worktree>' rebase origin/main`。
4. 試跑需要協調者（主對話）主導，因為 R2 的叫用方式本身就是被測對象；Engineer 負責 Phase 1 與 Phase 3。試跑的協調者對話必須
   從主工作樹 root 新開（Q10，見 §8.2）。

## 12. 待決問題

### 已決

| # | 問題 | 裁決 | 日期 |
|---|------|------|------|
| Q1 | 同意的有效範圍 | 同一個 closer subagent 實例（SendMessage 續用）；試跑證實不可行時退回 (c)：Phase D 先顯示 D1 對照表再問一句。拒絕 (b) | 2026-10-22 |
| Q2 | 遠端刪除時機 | 選項 A；選項 B 列為延後項 L1 | 2026-10-22 |
| Q3 | D1「一致」的定義 | behind 不比對；tip 用 B5；verdict 一致＝兩次都 exit 0；可重建樣式內的新增不算 STALE；不需要目錄 digest | 2026-10-22 |
| Q4 | D5 機制 | 新增回填腳本，含 `--verify`（只檢查 disposition 區塊），D6 用它 | 2026-10-22 |
| Q5 | capsule 處置 | D6 通過後刪除；Phase A 列出殘留 capsule | 2026-10-22 |
| Q6 | 試跑是否含遠端分支 | 含（R4） | 2026-10-22 |
| Q7 | 適用工具 | 只限 Claude Code；SKILL 註明 Copilot／Codex 維持產生指令 | 2026-10-22 |
| Q8 | B5 與 V-M-D rebase 的衝突 | `B_C` 改為結案記錄那一次推送的 base（推送前的 `origin/main`），沿用既有交接契約；B5 第一條為 `rev-list --count <B_C>..HEAD == 1`；D1 加 `HEAD^ == B_C`、祖先檢查與 reflog 獨立確認（§4.5）；L6 刪除 | 2026-10-22 |
| Q9 | 試跑如何觀察核准提示 | (a) 只觀察自然出現的提示，agent 不發任何 push 類指令 | 2026-10-22 |
| Q10 | 啟動位置 | (a) 維持主工作樹 root；試跑的協調者對話必須從主工作樹 root 新開 | 2026-10-22 |

另於 2026-10-22 裁決 R5（先做 Phase 1、其餘暫停）與 R6（cwd 外漏採 (a)、以 (c) 備援），見 §2.5。

### 恢復時要回答的問題（rev.4）

暫停期間不裁決。恢復條件成立後（pr-flow-tiering 試行結束並決定 Phase F），依序回答：

| # | 問題 | 依賴 |
|---|------|------|
| **P1** | **結案記錄走 PR（Tier 0 squash 合併）時，Phase D 的 tip 怎麼判定？** squash 會產生新 SHA，`origin/main` 上沒有 `update by push`，worktree 的分支 tip 也不會是 `origin/main` 上的那顆 commit。B5 的三條件、push base 交叉驗證、`B_C` 的來源全部要重定義；候選依據包括 PR 的 merge commit、`--match-head-commit` 綁定的 head SHA、squash commit 的 patch-id 與 `T_C` 比對 | pr-flow-tiering 的 D1（是否放棄直接 push main）與 Phase F |
| **P2** | 若 Phase F 讓直接推送與 PR 並存，自動路徑要不要只限其中一種？（E6 候選：「結案記錄以直接推送進入 main」） | P1 |
| **P3** | pr-flow-tiering 的 M4（合併後自動收尾：比對 `git worktree list` 與 `git branch --merged`，列出可移除的 worktree）與本計畫 Phase D 的分工：M4 只列候選，退役的稽核、同意與證據仍由 closer 負責？還是 M4 會取代 D3a／D3d？ | pr-flow-tiering Phase F |
| **P4** | Tier 0 合併帶 `--delete-branch`，遠端分支會在合併時自動刪除。D3c 的選項 A 停頓在這種情況下是否就不會出現？`git branch -d` 改以 HEAD 判定時，squash 後的 tip 不是 `main` 的祖先，`-d` 會拒絕，要怎麼處理（不得改用 `-D`） | P1 |
| **P5** | §13 的五項 blocking 在新前提下哪些仍成立、哪些要改寫 | P1–P4 |
| **P6** | 恢復時 Claude Code 的版本（當時實測是 VS Code extension 內建的 2.1.299，不是 CLI 2.1.307）是否要統一，試跑以哪個執行檔為準 | — |

### rev.2 原始提問（已決，保留供追溯）

| # | 問題（rev.2 原文） | 選項 | rev.2 的 Architect 建議 |
|---|------|------|---------------|
| **Q8** | B5 在 V-M-D rebase 後必然判 STALE（§4.5「已知後果」）。只要 Phase C commit 之後有任何別的 campaign 推上 main，自動路徑就失效 | (a) MVP 照 B5 嚴格執行，pilot 期間記錄發生次數，達 L6 門檻再議；(b) 現在就請 Plan Critic 一起設計 rebase 容忍的確定性判定 | **(a)**。B5 是 Plan Critic 指定的確定性做法；先量頻率再決定，符合最小可行 |
| **Q9** | 試跑要觀察「背景 subagent 遇 `ask`」，但 MVP 的指令除了 push 都不會觸發 guard `ask`。要主動觸發嗎？ | (a) 只觀察自然出現的提示，沒出現就記「未觀察到」；(b) 由 closer 發一次 `git push --dry-run origin <trial 分支>`（guard 判 `ask`），使用者在提示中按**拒絕**，只觀察提示的路徑。這是 agent 發出的 push 指令（雖然是 dry-run 且會被拒），與 U3 的精神有張力 | **(a)**。(b) 需要使用者明確同意才可列入，且必須按拒絕 |
| **Q10** | E1 要求 `CLAUDE_PROJECT_DIR` 與 cwd 是主工作樹 root。若使用者平常從 worktree root 啟動主對話，就永遠不合資格 | (a) 維持主工作樹 root；(b) 也接受「不是目標 worktree 的其他 worktree root」 | **(a)**。hooks 在兩處都生效，但從別的 worktree 啟動會讓 Bash 的預設 cwd 停在另一個 campaign 的 worktree，與 SKILL「cwd 漏進別的 campaign」的教訓衝突 |

## 13. 恢復前必修（Plan Critic 複核 rev.3，2026-10-22）

只寫修法方向，不展開成設計：恢復時若結案記錄改走 squash 合併，整個 tip 判定的前提可能改變（§14），細節到時依 §12 P1–P5 重寫。

### 13.1 Blocking

| # | 問題 | 修法方向 |
|---|------|---------|
| K1 | E1 用的 `CLAUDE_PROJECT_DIR` 在 subagent 的 Bash 環境讀不到（Plan Critic 實測為 unset）；實測的執行檔是 VS Code extension 內建的 2.1.299，不是 CLI 2.1.307 | 改以 `lsof -a -d cwd -p "$PPID"` 量 claude 行程的啟動目錄；`/bin/pwd -P` 只用來判斷 cwd 有沒有外漏。§3 的版本事實與試跑環境要以實際執行檔為準 |
| K2 | Q8 漏一個情境：Phase A 之後先單獨推上 commit `S`，再在 `S` 上做 `T_C`。`<B_C>..HEAD` 仍是 1、`HEAD^ == B_C`、reflog 也對得上，全部通過 | Phase C commit 前確認 `HEAD == T_A`（Phase A 觀測的 tip），capsule 記 `T_A`；D1 加 `git rev-parse T_C^ == T_A` |
| K3 | reflog 判定的分支不對：查到 `update by push` 但前一筆對不上時，rev.3 走 Q1(c)，應判 STALE；查不到才走 Q1(c) | 改寫 §4.5 第 (3) 項的 STALE 條件；§4.5.1 補兩個案例：「推送被拒後重推，轉交的是第一次的 base」與「兩次推送，或推送前 fetch」 |
| K4 | 試跑排在規則改寫之前，但 closer 現行規則寫「不自動執行移除」，也沒有 E1、`auto_eligible`、D0–D6，試跑時 closer 會依規則拒絕；rev.3 只寫「提示寫明這是試跑」，試跑授權的來源與範圍沒有寫清楚，也沒有完整的「試跑不適用」清單（§8.2 只列 D1 幾項，但 D0(d) 是 STOP 條件，T-A 一進 D0 就會停） | 準備逐字的試跑授權 prompt 範本，授權必須來自使用者本人的訊息（不是協調者轉述）；列完整的試跑不適用清單：D0(d)、D1 的 tip 與 push base、capsule 缺 `T_C`／`B_C`、D5、D6 |
| K5 | cwd 外漏（V-M-D Step 0.6 的 `cd` 使 lsof 或 D0(c) 命中） | **已裁決（R6）**：V-M-D 改用 `git -C` 或子 shell，仍偵測到就 STOP。已寫進 §7 #5 |

### 13.2 建議項

| # | 建議 | 修法方向 |
|---|------|---------|
| S1 | 同意閘門表補一列 | 協調者**逐字轉交**使用者對本次 Phase A 輸出的回覆＝算；**摘要轉述**＝不算 |
| S2 | `B_C` 的主要來源 | 以 reflog 為主要來源，交接契約轉交的值降為一致性檢查（與 K3 一起改） |
| S3 | T-C clone 的 hooks | clone 要設 `core.hooksPath`（指向 `.githooks` 或明確停用並記錄），否則 commit 的行為與主工作樹不同 |
| S4 | Phase A fixture 預驗 | 試跑前先單獨跑一次 `ai-portability` fixture，確認 exit 0（含 `gh` 可用、`--self-session`），不是在試跑當下才發現 |
| S5 | §8.6 補兩個判斷點 | (1) T-A 中途停下時，T-B 還跑不跑；(2)「改交使用者的步驟」的計數單位，例如 D3b 整塊算 1 步。另：fixture 不是 exit 0 時改為「修正 fixture 後重跑，不進入門檻判定」，不要改測人工路徑（否則門檻算不出來） |
| S6 | 與 pr-flow-tiering 的關係 | 已在 §14 整理 |

## 14. 與 pr-flow-tiering 的關係

來源：`docs/specs/active/pr-flow-tiering/proposal.md`（`origin/main`，最後一次修改為 `d9f8bcc2` fix(ci): merge tier 0 only after gitleaks, pinned to the scanned commit，2026-10-22）。

### 14.1 相關範圍

| 項目 | pr-flow-tiering 的內容 | 對本計畫的影響 |
|------|----------------------|---------------|
| **Tier 0** | 只動 `docs/**`（`docs/specs/**`、`docs/architecture/**` 除外）與 `.github/skills/**/history.md` 的 PR，在 gitleaks 成功後由 workflow 以 `gh pr merge --squash --match-head-commit` 合併，並帶 `--delete-branch` | 結案記錄（`docs/evaluation/campaigns/`）與 D5 的 disposition 回填都屬於 Tier 0。若改走 PR，`origin/main` 上的是 squash 後的新 commit |
| **M4** 合併後自動收尾 | 開啟 `delete_branch_on_merge`；每日或 SessionStart 比對 `git worktree list --porcelain` 與 `git branch --merged origin/main`，列出可移除的 worktree | 與 Phase D 的 D3a／D3c／D3d 重疊；分工待 §12 P3 |
| **Phase F** | 試行通過、D1 裁決後才改寫 `git.instructions.md`、`validate-merge-deploy.agent.md`、`campaign-closer.agent.md` 與生成的 wrapper | 與本計畫 §7 Phase 3 要改的檔案完全重疊；兩案同時改會互相覆寫，所以本計畫 Phase 3 暫停（R5） |
| 待決點 D1 | 是否放棄「trunk-based、無 PR 閘門」；proposal 明列 closer 的 base／head 四參數交接以直接 push main 為前提 | 本計畫的 `B_C`（push base）正是這個交接契約的一部分 |

### 14.2 squash 合併下會失效的設計

* **B5 三條件**：squash 後 `origin/main` 上的 commit 不是 worktree 的 `HEAD`，`merge-base --is-ancestor HEAD origin/main` 不成立。
* **push base 與 reflog 交叉驗證**：合併由 GitHub workflow 執行，本機只會在 fetch 時看到 `fetch: fast-forward`，沒有 `update by push`。
* **E6 候選**（結案記錄以直接推送進入 main）：在 Tier 0 成為預設時失去意義，或變成把多數退役排除在自動路徑外。
* **D3d 的 `merge-base --is-ancestor <tip> main` 與 `git branch -d`**：squash 後分支 tip 不是 `main` 的祖先，`-d` 會拒絕（§12 P4）。

### 14.3 仍然適用的設計

* **D3b exclude 對帳的拆開版**：與合併方式無關，guard 層已放行。
* **D5 回填腳本**（Phase 1 進行中）：只替換 disposition 區塊與 `--verify`，不依賴 commit 如何進入 main；改走 PR 時仍可用來產生 PR 的內容與驗證合併結果。
* **STOP 條件**：lsof 占用、dirty、ahead、稽核 verdict、主工作樹必須在 `main`（B3）、`commit --only`、不 stash／clean、不 force、不 `-D`。
* **可重建樣式清單**與 E3 的判定。
* **capsule 的五項基本內容**與 D6 以 `--verify` 確認。
