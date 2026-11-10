# Tasks

本檔只放不超過十條里程碑。完成一個里程碑就把 `- [ ]` 改 `- [x]` 並 commit。過程中增生的細項、評審意見與 bug 開 GitHub issue，貼 `spec:agent-autonomy` label；進度看 TTR Roadmap 看板。

## Phase 0: Worktree Setup

- [x] 從 `origin/main` `f2c548ef` 建 `ttr-agent-autonomy-worktree`（branch `feat/agent-autonomy`），`.git/info/exclude` 已加，`--unset-upstream` 已做；`spec:agent-autonomy` label 已建（2026-10-25，agent 自建）

## Phase A: 政策與文件（本 PR，Tier 2）

- [x] `AGENTS.md`、`copilot-instructions.md`、`git.instructions.md`、`handoff.instructions.md`、V-M-D agent 檔改寫；`sync_ai_adapters.py` 重生成；`pytest scripts/claude/tests scripts/tests` 全綠；以 agent 推 branch＋`gh pr create` 交付（第一個新流程實例），使用者合併（PR #454，merge commit `4d162dc9`，2026-10-25；notes §1）

## Phase B: Heartbeat 試做（合併後 7 天）

- [x] 建 `auto-fix`、`needs-human` label；建立每 8 小時的排程雲端 agent（`trig_01CEwNUKeAdxVu9UVLWav7tG`），提示詞取自 `heartbeat-prompt.md`；第一次執行只分類（5 張子 issue、1 張 needs-human；notes §3、§4）
- [ ] 第一張 heartbeat PR 經 Tier 1 一鍵合併；下一次 Daily Scraper 執行後該來源有產出
- [ ] 7 天盤點：PR 數、被關閉或 revert 數、配額影響、使用者人工步驟數；go／no-go 寫進 `notes.md`，no-go 就停用排程

## Phase C: 擴大

- [ ] 合併後驗證迴路：下一次 scraper 執行後自動在 issue 留言產出數，0 產出就重開；Tier 1 LINE 推播；heartbeat 分類段改用 Haiku（grunt tier）
- [ ] `pr-flow-tiering` Phase F 其餘文字（campaign closer 交接參數）與「要求 PR」ruleset，由使用者裁決

## Phase D: 週審節奏下的全自動開發迴路（proposal §8）

- [ ] D1 證據工廠、D2 提示詞 v2、D4 週審 digest、D5 第二車道（proposal §9）依各自 issue 完成，D3 由使用者裁決 go／no-go；14 天盤點（每週關閉 issue 數、PR 中位等待天數、revert 數）寫進 `notes.md`

## Phase E: 消化率（proposal §10）

- [ ] E1 診斷含 production log、E6 排程改 workflow_run、E5 量測行上線；E2 登記 PR 與 E3 分流合併；E4 `merge-readiness` 跑一週後使用者裁決 D3；四週盤點（每週淨關閉、needs-human 存量、合併的 heartbeat PR 數）寫進 `notes.md`

## Verification

- [ ] `python3 -m pytest scripts/claude/tests scripts/tests -q` 全綠；`python3 scripts/sync_ai_adapters.py --check` 通過
- [x] 本 PR 的合併由使用者在 GitHub 完成，V-M-D 以 merge commit SHA 驗證部署（`4d162dc9`，Vercel success，deployment 7309725516）
