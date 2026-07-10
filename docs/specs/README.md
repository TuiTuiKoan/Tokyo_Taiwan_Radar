---
title: Spec Directory — Tokyo Taiwan Radar
ms.date: 2026-05-05
---

# Spec Directory

每個進行中的功能或改動都有一份 spec，讓你在 Copilot Chat 換 session 後不需要重述脈絡。

## 目錄結構

```
docs/specs/
├── _template/          ← Copilot 新建 spec 時抄這裡
├── parked/             ← 暫存的 idea，單一 .md 檔
├── active/<slug>/      ← 進行中（proposal.md + tasks.md [+ notes.md]）
└── archive/            ← 完成後 git mv 進來（單一 .md 或子目錄）
```

## Frontmatter 規約（proposal.md）

```yaml
---
slug: <kebab-case 唯一識別>
title: <人類可讀標題>
status: active          # parked | active | archived
branch: feat/<slug>     # 對應 git branch（可空）
created: YYYY-MM-DD
tags: [scraper, web, infra, tooling]
---
```

## Status 流轉

```
parked → active → archived
```

- `parked` → `active`：開新 git branch，把 `parked/<slug>.md` 移至 `active/<slug>/proposal.md` 並補 `tasks.md`
- `active` → `archived`：`git mv docs/specs/active/<slug> docs/specs/archive/$(date +%Y-%m)-<slug>`

## Worktree 生命週期（大型功能）

每個規則上線後新建/重啟的 active implementation spec，1:1 對應一個 repo-root worktree（既有 spec grandfather，不回溯）。**worktree 路徑不寫進 frontmatter**，由 `slug` 推導：`ttr-<slug>-worktree`（branch `feat/<slug>`），每次以 `git worktree list --porcelain` 驗證實況。

- `parked → active`：依 `.github/instructions/git.instructions.md § Isolated worktree` 的 state matrix 建 worktree + idempotent `.git/info/exclude`。
- 開發期間：所有 commit 在 worktree 內；`tasks.md` 逐步打勾。
- `active → archived`：merge 進 main 後，依 canonical 的 STOP 條件 `git worktree remove` + `git branch -d` + 移除 exclude 行，再 `git mv docs/specs/active/<slug> docs/specs/archive/$(date +%Y-%m)-<slug>`。

命令細節一律見 canonical section；小改動不建 spec 也不建 worktree。

## 給 Copilot 的使用守則

1. **新功能前先建 spec**：在 `active/<slug>/proposal.md` 寫清楚 what/why/non-goals，再開 branch；大型 feature 依「Worktree 生命週期」建對應 `ttr-<slug>-worktree`。
2. **tasks.md 是唯一進度依據**：每完成一步就把 `- [ ]` 改 `- [x]`，commit 進 git。
3. **換 session 時**：把 `docs/specs/active/<slug>/tasks.md` 貼給 Copilot，說明「繼續執行未完成項目」，不需要重述背景。
