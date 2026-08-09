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

## Why（為什麼）

三個獨立問題促成這份 spec：

1. **缺少 program 層級文件**。`docs/specs/active/` 全是單一功能 spec，沒有任何檔案
   記錄「整個專案現在有哪些工作線、各自在哪」。跨 session 交接時只能依賴會消失的
   session memory。

2. **三個維度已經漂移**。A–E 是任務分類、worktree 是 git 隔離機制、spec 是文件單位，
   三者從未設計成一對一。2026-08-08 live snapshot 有 16 個 spec 目錄位於
   `docs/specs/active/`，以及 10 個註冊 worktree（1 個 main + 9 個 linked）。9 個 linked
   worktree 中只有 2 個有同 branch 的 spec 目錄（`publication-policy`、
   `evaluation-framework`）；7 個沒有。16 個目錄中有 14 個沒有 dedicated linked
   worktree，其中包含 grandfathered spec 與刻意留在 main 的本治理 spec，不能把
   「無 dedicated worktree」一律判成違規。目錄位置與 frontmatter `status` 是兩份
   證據；本計數不宣稱 16 份 frontmatter 都是 `active`。

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
| Worktree | git 隔離機制 | 完整註冊路徑 + branch；basename 僅供顯示 |
| Spec | 文件單位 | `docs/specs/active/<slug>/` |

Architect 規則要求 spec ⟺ worktree 一對一，但**未要求**工作線與兩者對齊。
A–E 可以跨多個 worktree，也可以完全沒有 worktree。這是設計上的容許，不是缺陷。
缺口要依規則生效時間與 worktree 狀態分類：新建／重啟且持續實作的 worktree 缺 spec
是治理缺口；既有停滯 worktree 是 grandfathered inventory，先決定去留，不應為了湊數
追建 spec。

### Worktree 路徑身分

Worktree 身分不得只用 basename。權威證據是 `git worktree list --porcelain` 的完整
`worktree` 註冊字串，加上 branch 與實體路徑（`cd "$path" && pwd -P`）。

2026-08-08 查證發現三種拓撲：

1. 5 個 linked worktree 以 canonical
   `/Users/flyingship/Development/Tokyo Taiwan Radar/...` 註冊。
2. `publication-policy`、`taiwan-expo-japan`、`v8` 以小寫
   `/Users/flyingship/development/Tokyo Taiwan Radar/...` 註冊。現行 macOS 檔案系統上，
   大小寫兩條 parent path 解析為相同 device/inode，因此不是兩套實體目錄；但 Git
   保留不同 lexical registration，字串式 root containment 與自動化仍會分裂。
3. `ttr-security-hardening-worktree` 註冊在
   `/Users/flyingship/development/ttr-security-hardening-worktree`，實體上是 repo root
   的 sibling，不是 project child。主 repo 的 `.git/info/exclude` 不適用於它。

因此，basename-only inventory 會靜默吃掉 case-split 與 external placement；
`pwd -P`-only inventory 又會吃掉 Git 保存的小寫註冊字串。兩者必須並列。

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
