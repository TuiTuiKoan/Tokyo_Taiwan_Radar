---
slug: workstream-tracking
title: 全專案工作線盤點與治理
description: 全專案工作線、worktree 註冊路徑與 spec 對照的治理真值
status: active
branch: origin/main
created: 2026-08-08
tags: [governance, tracking, meta]
---

## What（做什麼）

維護一份 program 層級的工作線盤點：五條主要工作線（A–E）的進度、未被納入編號體系的
工作線、以及「工作線 ↔ worktree ↔ spec」三方對照與其落差。

本 spec 是這份盤點的**權威持久位置**。`.github/prompts/workstream-audit.prompt.md`
只負責指示 agent 讀取本 spec 並重新查證，不自帶內容副本。

2026-10-22 起，`AGENTS.md`「進度追蹤」把**進度入口**改為 GitHub Project TTR Roadmap 看板，細項一律開 issue。
本 spec 因此收斂為 worktree／spec 拓撲、退役證據與治理缺口的紀錄；各工作線「做到哪」以看板 issue 為準，
本檔只放指向 issue 的連結，不重複維護細項清單。

## Why（為什麼）

三個獨立問題促成這份 spec：

1. **缺少 program 層級文件**。`docs/specs/active/` 全是單一功能 spec，沒有任何檔案
   記錄「整個專案現在有哪些工作線、各自在哪」。跨 session 交接時只能依賴會消失的
   session memory。

2. **三個維度已經漂移**。A–E 是任務分類、worktree 是 git 隔離機制、spec 是文件單位，
   三者從未設計成一對一。2026-10-25 live snapshot 有 20 個目錄位於 `docs/specs/active/`、6 個目錄位於
   `docs/specs/archive/`，以及 16 個註冊 worktree（1 個 main + 15 個 linked，含本次對帳 worktree）。
   linked worktree 中只有 1 個（`ttr-venue-data-cleanup-worktree`，#371）沒有對應 spec；但目錄名、branch 名與
   spec slug 經常不同（同一個目錄會被其他 session 換成新 branch），對應關係必須逐一查證，不能用名稱推斷。
   不能把「無 dedicated worktree」或「無同名 spec」一律判成違規，必須辨識 grandfathered 與明確指定關係。
   目錄位置與 frontmatter `status` 是兩份證據；目前 2 個 spec 的兩者不一致（見 tasks.md inventory）。

3. **治理缺口沒有歸屬**。停滯 worktree、未納版控的 prompt、違反 spec ⟺ worktree
   規則的分支——這些問題不屬於任何單一功能 spec，因此一直沒有被追蹤。

## Non-Goals（不做什麼）

- **不取代**各功能 spec。本 spec 只記錄「有哪些線、在哪裡、缺什麼」，不記錄各線的實作細節。
- **不授權任何變更**。建立或刪除 worktree/branch、移動或歸檔 spec、production 寫入，
  全部需另行批准。
- **不自行決定停滯 worktree 的去留**。只負責盤點與提出建議。
- 不建立、移動、repair 或重新註冊 worktree；本 spec 為 docs-only，直接落在 `origin/main`。

## Design（設計摘要）

### 三維度模型

| 維度 | 性質 | 命名 |
|---|---|---|
| 工作線 A–E | 任務追蹤分類（人為編號） | 字母 |
| Worktree（舊慣例） | git 隔離機制；repo root 內巢狀 | `<repo>/ttr-<slug>-worktree` + `feat/`、`fix/` 或 `chore/` branch |
| Worktree（新慣例） | git 隔離機制；repo root 外 sibling | `<repo>.worktrees/<slug>` + `agents/<slug>` branch |
| Spec | 文件單位 | `docs/specs/active/<slug>/` |

Architect 規則要求 spec ⟺ worktree 一對一，但**未要求**工作線與兩者對齊。
A–E 可以跨多個 worktree，也可以完全沒有 worktree。這是設計上的容許，不是缺陷。
缺口要依規則生效時間與 worktree 狀態分類：新建／重啟且持續實作的 worktree 缺 spec
是治理缺口；既有停滯 worktree 是 grandfathered inventory，先決定去留，不應為了湊數
追建 spec。

### Worktree 路徑身分

Worktree 身分不得只用 basename。權威證據是 `git worktree list --porcelain` 的完整
`worktree` 註冊字串，加上 branch 與實體路徑（`cd "$path" && pwd -P`）。

repo 實體根目錄已搬到 `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar`，
舊路徑 `/Users/flyingship/Development/Tokyo Taiwan Radar`（及 `.worktrees`）成為 symlink（2026-09-10）。
2026-10-25 live 拓撲有三種註冊形態（共 16 個，含 main）：

1. **新路徑註冊**：repo root 內 11 個 `ttr-*-worktree`（清單見 tasks.md 拓撲表，必須以
   `.git/info/exclude` 防止 `git add -A` 誤掃），以及 root 外的 `3-TTR/Tokyo Taiwan Radar.worktrees/ledger-topology-reconcile`。
2. **舊路徑 symlink-alias 註冊**：其餘 3 個 linked worktree（admin-qa-cleanup、japan-scope-gate 目錄、
   publication-policy，全在 root 內）的 Git 註冊字串仍是搬移前的
   `/Users/flyingship/Development/Tokyo Taiwan Radar...`（`publication-policy` 為小寫
   `development`）。`pwd -P` 全部落在 `3-TTR/` 下，是同一套實體 repo 的 lexical alias；
   字串前綴 classifier 會把它們誤列為 `external`，需以 `pwd -P` containment 重新分類。
3. **新慣例 `<repo>.worktrees/<slug>` + `agents/<slug>`**：2026-10-20 觀測時共 9 個（7 個 alias 註冊、
   2 個新路徑註冊），2026-10-22 全數以非強制移除退役（見 [tasks.md](./tasks.md) 的合併結案紀錄）；
   現存只有本次對帳專屬的 `agents/ledger-topology-reconcile`。此慣例在 repo root 外，不污染主工作樹
   untracked 清單，也不需要 exclude。相對舊慣例的差異：分支前綴 `agents/`、位置為 sibling、
   無 exclude 條目。**建議**後續將其正式寫入 git 規則並界定使用時機；本次只提出建議，不改寫
   `.github/instructions/git.instructions.md`。

2026-10-22 曾觀測到同層目錄 `agents-vscode-performance-issues` 含 `.git`、但不在 `git worktree list`，
gitdir 指標指向不存在的目標；2026-10-25 確認它已被刪除（刪除者不明，#352）。這段保留「未註冊但含 `.git` 的
目錄可能存在」的歷史證據，遇到時仍不可自行 prune、re-add 或刪除。

2026-08-08 曾另觀測到一個 repo-root sibling 的 external registration，以及 `v8` 的小寫註冊；
前者已於 2026-08-09 以非強制移除與安全 branch deletion 正常退役（見 [tasks.md](./tasks.md) 的
Tier 1 結案紀錄），`v8`（`feat/event-intake-wizard`）已於 2026-10-14 退役。這段只保留
「external placement 與 lexical alias 可能存在」的歷史證據，不主張它們現在仍存活。

因此，basename-only inventory 會靜默吃掉 case-split 與 external placement；
`pwd -P`-only inventory 又會吃掉 Git 保存的小寫註冊字串。兩者必須並列。

建議後續把新慣例正式寫入 git 規則，並明確界定何時用 `agents/`、何時沿用舊慣例；本次只提出
建議，不改寫 `.github/instructions/git.instructions.md`。

### Snapshot 紀律

[tasks.md](./tasks.md) 內所有計數、SHA、ahead/behind、dirty 數都是**觀測快照**，
不是真值。本 repo 經常有 3 個以上 session 平行寫入，數字會在數小時內失效。

任何分析前必須先重跑 tasks.md 的查證指令並回報差異，以 live 結果為準並就地更新，
不得沿用舊數字做判斷。查證輸出必須保留 registered path、physical path 與 path class，
不得先取 basename 才做判斷。

### 已確立的操作教訓

這些是從實際事故歸納、可重複套用的手法，詳見 [tasks.md](./tasks.md) 的「操作教訓」段落：

- Worktree 確認閘門：功能實作前由使用者明確指定 worktree；主工作樹只做治理與盤點
- 路徑身分證據：同時保存 Git registered path 與 `pwd -P` physical path，不以 basename
   或單一路徑表示取代完整拓撲
- 只推自己 commit：用 `origin/main` 起點的臨時 worktree + `git push origin HEAD:main`
- 清理 worktree 的安全順序：備份 patch → autostash rebase → 保留雙方 → 驗證後 drop stash → `git reset`
- 本 repo 實測的 shell 陷阱：路徑含空白、zsh 字串比較、`grep -c` 的 exit code、無效的 echo 驗證

## References

- `.github/prompts/workstream-audit.prompt.md` — 執行入口
- `.github/prompts/admin-qa-cleanup.prompt.md` — A 線 successor
- `.github/prompts/authoritative-venue-repair.prompt.md` — E 線 venue repair
- `.github/instructions/git.instructions.md`：Worktree confirmation gate 與 state matrix
- `.github/skills/agents/architect/SKILL.md`：決策閘門規則
