---
slug: workstream-tracking
title: 全專案工作線盤點與治理
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
   三者從未設計成一對一。實測結果：15 個 active spec、10 個 worktree，只有 3 個能直接對應；
   有 worktree 卻無 spec 的有 2 個；有 spec 卻無 worktree 的有 12 個。

3. **治理缺口沒有歸屬**。停滯 worktree、未納版控的 prompt、違反 spec ⟺ worktree
   規則的分支——這些問題不屬於任何單一功能 spec，因此一直沒有被追蹤。

## Non-Goals（不做什麼）

- **不取代**各功能 spec。本 spec 只記錄「有哪些線、在哪裡、缺什麼」，不記錄各線的實作細節。
- **不授權任何變更**。建立或刪除 worktree/branch、移動或歸檔 spec、production 寫入，
  全部需另行批准。
- **不自行決定停滯 worktree 的去留**。只負責盤點與提出建議。
- 不建立專屬 feature branch 或 worktree；本 spec 為 docs-only，直接落在 `origin/main`。

## Design（設計摘要）

### 三維度模型

| 維度 | 性質 | 命名 |
|---|---|---|
| 工作線 A–E | 任務追蹤分類（人為編號） | 字母 |
| Worktree | git 隔離機制 | `ttr-<slug>-worktree` |
| Spec | 文件單位 | `docs/specs/active/<slug>/` |

Architect 規則要求 spec ⟺ worktree 一對一，但**未要求**工作線與兩者對齊。
A–E 可以跨多個 worktree，也可以完全沒有 worktree。這是設計上的容許，不是缺陷；
真正的缺陷只有「有 worktree 卻無 spec」。

### Snapshot 紀律

[tasks.md](./tasks.md) 內所有計數、SHA、ahead/behind、dirty 數都是**觀測快照**，
不是真值。本 repo 經常有 3 個以上 session 平行寫入，數字會在數小時內失效。

任何分析前必須先重跑 tasks.md 的查證指令並回報差異，以 live 結果為準並就地更新，
不得沿用舊數字做判斷。

### 已確立的操作教訓

這些是從實際事故歸納、可重複套用的手法，詳見 [tasks.md](./tasks.md) 的「操作教訓」段落：

- 決策閘門修正：主工作樹有他人未提交變更時，即使 small change 也走 owning worktree
- 只推自己 commit：用 `origin/main` 起點的臨時 worktree + `git push origin HEAD:main`
- 清理 worktree 的安全順序：備份 patch → autostash rebase → 保留雙方 → 驗證後 drop stash → `git reset`
- 本 repo 實測的 shell 陷阱：路徑含空白、zsh 字串比較、`grep -c` 的 exit code、無效的 echo 驗證

## References

- `.github/prompts/workstream-audit.prompt.md` — 執行入口
- `.github/prompts/admin-qa-cleanup.prompt.md` — A 線 successor
- `.github/prompts/authoritative-venue-repair.prompt.md` — E 線 venue repair
- `.github/instructions/git.instructions.md` — Isolated worktree state matrix
- `.github/skills/agents/architect/SKILL.md` — 決策閘門規則
