# Tasks

本檔只放不超過十條里程碑。完成一個里程碑就把 `- [ ]` 改 `- [x]` 並 commit（即使只改這一行）。
過程中增生的細項、評審意見與 bug 開 GitHub issue，貼 `spec:<slug>` label，不寫進本檔；進度看 TTR Roadmap 看板。

## Phase 0: Worktree Setup（大型功能；小改動跳過）

- [ ] 依 `.github/instructions/git.instructions.md § Isolated worktree` 的 state matrix 建 `ttr-<slug>-worktree`（branch `feat/<slug>`）
- [ ] idempotent append `ttr-<slug>-worktree/` 至 `.git/info/exclude`
- [ ] 建立 `spec:<slug>` label：`gh label create "spec:<slug>" --color 1D76DB --description "Work tracked by this spec"`
- [ ] 在 worktree 內開發，完成里程碑時勾選以下項目

## Phase A: <第一階段>

- [ ] 里程碑 1
- [ ] 里程碑 2

## Phase B: <第二階段>

- [ ] 里程碑 1
- [ ] 里程碑 2

## Verification

- [ ] build/lint pass
- [ ] 本地測試通過
- [ ] deploy 驗證
