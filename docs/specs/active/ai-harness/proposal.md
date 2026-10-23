---
slug: ai-harness
title: AI harness v2（模型分級、Orca 平行開發、跨專案可攜 harness、TTR 精簡）
description: 以 tier 欄位投影各工具的模型與 effort，導入 Orca 平行 worktree，並把通用 agent 抽成可跨專案的 Claude plugin
status: active
branch: feat/ai-harness
created: 2026-10-20
tags: [tooling, governance, ai, harness]
---

## What（做什麼）

ai-portability 結案後的下一個 campaign。分五個 phase：Phase 0 盤點與裁決、Phase 1 模型分級、Phase 2 Orca 與平行開發治理、Phase 3 抽出可攜 harness、Phase 4 TTR 精簡。Phase 5（本機模型）為可選。完整設計見 [plan.md](./plan.md)（rev.3，2026-10-23，依 [plan-critique-1.md](./plan-critique-1.md) 修訂；rev.1、rev.2 原檔在 `~/.ai-notes/ttr/ai-harness-plan-rev1.md`、`…-rev2.md`）。進度真值是 [tasks.md](./tasks.md)，證據在 [notes.md](./notes.md)。

## Why（為什麼）

- 成本是 Claude Pro 與 Codex 的訂閱配額，不是 API 費用；router 與 gateway 會改走 API 計費，不適用。
- Phase 1 之前，repo 的模型政策只有「不寫死」，沒有分級；`xhigh` effort 與 Fable 是最大的配額消耗。Phase 1 已實作 `tier` 分級。
- agent 與防線只存在於 TTR repo，其他專案無法重用。
- 一次只開一個 session 的流程，無法善用 Orca 與 Claude Code 原生的平行與跨 session 訊息。

## Non-Goals（不做什麼）

- 不採用 claude-code-router、LiteLLM、OpenRouter 等 gateway。
- 不在 Orca 內建立或刪除 campaign worktree；不用 Claude `--worktree` 建 campaign worktree。
- 不改 `scraper/**`、`web/**`、`supabase/**`，不寫 production DB。
- 不複製正式 secrets（`scraper/.env`、`web/.env.local`）進任何 worktree；hooks 只保護 Claude Code，不能當作複製 secrets 的安全依據。
- 不把工具搬遷本身當成已證明的配額效益；配額效益只認 Phase 1 之後量到的數據。
- 不合併 54 個來源 skill（D6 量測後否決）。
- Phase 3 前不搬動通用 agent 的權威位置。
- 本機模型不得用於任何由 hooks 守護的動作。

## Design（設計摘要）

- `tier: plan | build | grunt` 寫在 `.github/agents/*.agent.md` frontmatter，由 `scripts/sync_ai_adapters.py` 投影成 Claude wrapper 的 `model`／`effort` 與 Codex agent TOML 的 `model_reasoning_effort`。來源檔一律不寫 `model:`（含別名），別名只出現在生成的 wrapper。
- 使用者層（不入 repo）：`~/.claude/settings.json`、`~/.codex/config.toml` profiles。
- 可攜 harness 為獨立 repo，輸出 Claude plugin 與 Codex install 腳本；Copilot 由各 repo 的 sync 複製。

## 使用者裁決（D1–D7 於 2026-10-20 依 plan rev.1 的建議裁決；rev.2 於 2026-10-23 修訂 D4、D6、D7 並新增 D8）

| # | 裁決 |
|---|---|
| D1 | slug `ai-harness`，worktree `ttr-ai-harness-worktree`，branch `feat/ai-harness`；Phase 1、2 共用，Phase 3 在新 repo，Phase 4 另開 |
| D2 | 通用 agent 權威檔搬到 harness repo，TTR `.github/agents` 變 generated；到 Phase 3 才做 |
| D3 | 主對話預設 `opusplan`，規劃 session 手動 `/model fable` |
| D4 | **撤回（2026-10-23）**：原裁決要把 `scraper/.env`、`web/.env.local` 複製進每個 worktree，經 Plan Critic 指出不安全。待重新裁決 D4' |
| D4' | **已裁決採用（2026-10-23）**（Phase 2a 的條件已成立）：worktree 不帶正式 secrets；agent worktree 的 dry-run 驗證只限已確認不需憑證的來源（目前僅 TCC，本機實測；其他來源 NOT TESTED，靜態核對有反例）；其他來源用 fixture、mock 或使用者自行驗證；web 驗證用佔位值或 `web/.env.example`（NOT TESTED）；需要 secrets 的操作由使用者在自己的環境執行 |
| D5 | worktree 一律以 git 指令建立，Orca 只顯示與啟動 |
| D6 | 先以 `/context` 量測；常駐超過約 3k tokens 才合併 54 個來源 skill。**量測結果（2026-10-23）：專案約 2.6k，不合併**；改做 `AGENTS.md` 瘦身 |
| D7 | 退役 `tokyo-taiwan-radar-agents-repo` worktree，由本 campaign 取代。**已達成（2026-10-23）：該 worktree 已不存在，無需退役** |
| D8 | **已裁決採用（2026-10-23）**（只在 Phase 3b 生效；3a 試點不需要）：`harness.lock` 是來源版本紀錄，完整釘選需涵蓋 checkout、adapter、plugin 安裝與載入版本、Codex 安裝結果；plugin 缺失時選「只警告」或「阻擋寫入操作」。採用 lock 加「只警告」，3b 之前不搬 hooks。見 plan §3 Phase 3 |

## References

- [docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md](../../../CLAUDE_CODE_MIGRATION_RUNBOOK.md)
- [docs/specs/parked/ai-portability-followups.md](../../parked/ai-portability-followups.md)
- [docs/evaluation/campaigns/2026-10-14-ai-portability.md](../../../evaluation/campaigns/2026-10-14-ai-portability.md)
