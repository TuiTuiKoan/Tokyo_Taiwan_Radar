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
├── parked/             ← 暫存的 idea，或暫停工作線的後續清單，單一 .md 檔
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

- `parked` → `active`：開新 git branch，把 `parked/<slug>.md` 移至 `active/<slug>/proposal.md` 並補 `tasks.md`；建立 `spec:<slug>` label
- `active` → `archived`：`git mv docs/specs/active/<slug> docs/specs/archive/$(date +%Y-%m)-<slug>`

## Worktree 生命週期（大型功能）

每個規則上線後新建/重啟的 active implementation spec，1:1 對應一個 repo-root worktree（既有 spec grandfather，不回溯）。**worktree 路徑不寫進 frontmatter**，由 `slug` 推導：`ttr-<slug>-worktree`（branch `feat/<slug>`），每次以 `git worktree list --porcelain` 驗證實況。

- `parked → active`：依 `.github/instructions/git.instructions.md § Isolated worktree` 的 state matrix 建 worktree + idempotent `.git/info/exclude`。
- 開發期間：所有 commit 在 worktree 內；里程碑完成時在 `tasks.md` 打勾，過程中的細項開 issue（見「Spec 與 Issue 分工」）。
- `active → archived`：merge 進 main 後，依 canonical 的 STOP 條件 `git worktree remove` + `git branch -d` + 移除 exclude 行，再 `git mv docs/specs/active/<slug> docs/specs/archive/$(date +%Y-%m)-<slug>`。

命令細節一律見 canonical section；小改動不建 spec 也不建 worktree。

## Spec 與 Issue 分工

| 內容 | 放哪裡 |
|---|---|
| 現在做到哪、下一步 | TTR Roadmap 看板：https://github.com/users/TuiTuiKoan/projects/1 |
| 為什麼做、做什麼、不做什麼、設計 | `proposal.md` |
| 不超過十條的里程碑 | `tasks.md` |
| 過程中增生的細項、評審意見、測試發現的 bug、之後要處理的待辦 | GitHub issue，貼 `spec:<slug>` label |

- 每個 active spec 都有一個 `spec:<slug>` label；新 spec 在 `parked` → `active` 時建立。
- **parked 裡的後續清單**：spec 結案或暫停時剩下的待辦，依性質分兩種：彼此獨立的項目開 issue（可依主題合併成幾張，用 checklist 列出），並在 parked 檔開頭註明搬到哪些 issue；有先後順序或需要使用者核准關卡的執行手冊，留在 `docs/specs/parked/<slug>-followups.md`，看板上只開一張代表卡連到該檔。範例：`ai-portability-followups.md` 的五類已搬成 #334～#338；`authoritative-venue-repair-followups.md` 是有 Gate 的手冊，代表卡是 #339。
- 既有 `tasks.md` 裡已經存在的細項 checkbox 保留原狀，不搬移；新增的細項才開 issue。
- 同一套規則寫在 `AGENTS.md`（Claude Code、Codex）與 `.github/copilot-instructions.md`（VS Code Copilot），agent 會自動遵守。

## 給 AI agent 的使用守則

1. **新功能前先建 spec**：在 `active/<slug>/proposal.md` 寫清楚 what/why/non-goals，再開 branch；大型 feature 依「Worktree 生命週期」建對應 `ttr-<slug>-worktree`。
2. **tasks.md 只放里程碑**：完成一個里程碑就把 `- [ ]` 改 `- [x]` 並 commit。過程中的細項開 issue 貼 `spec:<slug>`；進度看 TTR Roadmap 看板。
3. **換 session 時**：請 agent 先看 `label:spec:<slug>` 的 open issue，再讀 `docs/specs/active/<slug>/tasks.md` 的里程碑，接續未完成的項目，不需要重述背景。
