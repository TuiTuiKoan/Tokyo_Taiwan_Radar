# Tasks

每完成一步把 `- [ ]` 改 `- [x]`，並 commit（即使只改這一行）。本檔只放里程碑；過程中增生的細項與 bug 改開 GitHub Issue，貼 `spec:pr-flow-tiering` label。

## Phase 0: Worktree Setup

- [x] 依 state matrix 建 `ttr-pr-flow-tiering-worktree`（branch `feat/pr-flow-tiering`，base `origin/main` `555fb9a5`）
- [x] idempotent append `ttr-pr-flow-tiering-worktree/` 至 `.git/info/exclude`
- [x] 取消 branch 對 `origin/main` 的 upstream 追蹤，避免無參數 `git push` 推到 main

## Phase A: Proposal

- [x] 撰寫 `proposal.md`：五個機制、三個分層、三個待決點、`check_push` 決策表

## Phase B: `check_push` 分流（Fable）

- [x] 依 proposal 決策表為每一列寫 positive／negative test，先確認新測試在現行程式碼上失敗（改前 40 failed／408 passed，見 `notes.md` B1）
- [x] 修改 `scripts/claude/_policy.py` 的 `check_push`，讓測試通過；既有 deny 測試全部維持
- [x] 跑 `python3 -m pytest scripts/claude/tests scripts/tests -q` 全綠（615 passed）
- [ ] 實測 Claude Code 2.1.304 下 hook allow 與 `permissions.ask` 的優先順序，以及 auto mode 是否放行推 feature branch，記錄到 `notes.md`（文件查證完成：ask 規則不受 hook allow 影響；互動實測 NOT TESTED，使用者步驟 U-B1～U-B4 見 `notes.md` B2）
- [ ] 依實測結果提出 `.claude/settings.json` 修改方案；方案寫進 `notes.md`，未經使用者核准不改檔（方案 A／B 已寫在 `notes.md` B2，建議方案 B；等使用者核准後才改檔與 `test_claude_settings.py`）
- [x] 更新 `AGENTS.md`「Hooks 與 permissions」第一批規則表的 push 列

## Phase C: Plan Critic（Codex）

- [ ] 以 `codex exec -s read-only` 評審 `proposal.md` 與 Phase B diff，報告存成 `critique.md`
- [ ] 逐條回應批評：採納、修改或附理由駁回，更新 proposal 與 tasks
- [ ] Phase B 的 commit 在 Phase C 完成前不合併到 main

## Phase D: GitHub 設定與 Tier 0 workflow

- [ ] 使用者核准後開啟 `allow_auto_merge`、`delete_branch_on_merge`，關閉 merge commit
- [ ] 新增 `.github/labeler.yml` 與 Tier 0 auto-merge workflow，路徑清單照 proposal 白名單
- [ ] 用一個只改 `docs/` 的測試 PR 驗證 Tier 0 自動合併，用一個改 `web/` 的 PR 驗證落入 Tier 2

## Phase E: 試行兩週

- [ ] 記錄每層 PR 數、Tier 0 被 revert 的次數、commit 到進 main 的時間
- [ ] 試行結束後請使用者裁決 D1、D2、D3

## Phase F: 治理文字改寫（D1 通過後）

- [ ] 改寫 `git.instructions.md` Branch strategy 與 Worktree 段落
- [ ] 改寫 V-M-D Step 4 與 campaign closer 交接參數
- [ ] 執行 `python3 scripts/sync_ai_adapters.py` 與 `--check`
- [ ] 開啟 `main` branch protection 與 required checks

## Verification

- [ ] `python3 -m pytest scripts/claude/tests scripts/tests -q` 全綠
- [ ] `python3 scripts/sync_ai_adapters.py --check` 通過
- [ ] 實際由 agent 推 feature branch 不被提示，推 main 仍被提示
