# Tasks

本檔只放不超過十條里程碑。完成一個里程碑就把 `- [ ]` 改 `- [x]` 並 commit。過程中增生的細項、評審意見與 bug 開 GitHub issue，貼 `spec:auto-learning` label；進度看 TTR Roadmap 看板。

## Phase 0: 規劃

- [x] 診斷、計畫、使用者裁決（2026-11-22）；Plan Critic 評審存檔（[plan-critique-1.md](./plan-critique-1.md)，Claude 代評）
- [ ] 建 `spec:auto-learning` 與 `learning` label；使用者確認評審後的範圍縮減

## Phase A: 退役與教訓段（PR A）

- [ ] 退役三個元件與提醒 workflow；handoff、路由表、tier 表、測試同步；`AGENTS.md` 與 `copilot-instructions.md` 加「教訓」規則；PR 由使用者合併
- [ ] 合併後關閉仍 open 的 daily-review 提醒 issue；第一張 heartbeat PR 的 body 有「教訓」段

## Phase B: 學習訊號（PR B）

- [ ] `weekly_digest.py` 新增學習訊號區與 `learning` 項目清單，含 fixture 測試；下一張週審 digest 出現該區

## Phase C: learner report-only（PR C）

- [ ] `learner.agent.md` 與 `learner-prompt.md` 合併；使用者建立排程並清空 MCP 連接器；確認 agent 無法修改該排程
- [ ] learner 執行兩輪，各產出一張報告 issue，沒有任何檔案或 PR 寫入

## Phase D: 關卡

- [ ] 兩輪盤點寫進 `notes.md`（卡片數、👍 數、被實作數、訂閱配額用量）；使用者裁決 go／no-go；go 則另寫第二階段計畫，no-go 則停用排程

## Verification

- [ ] `python3 -m pytest scripts/tests scripts/claude/tests -q` 全綠；`python3 scripts/sync_ai_adapters.py --check` exit 0
- [ ] `pnpm --dir web run build` 通過（`docs/architecture/system-map.json` 有變更）
