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

ai-portability 結案後的下一個 campaign。分五個 phase：Phase 0 盤點與裁決、Phase 1 模型分級、Phase 2 Orca 與平行開發治理、Phase 3 抽出可攜 harness、Phase 4 TTR 精簡。Phase 5（本機模型）為可選。完整設計見 [plan.md](./plan.md)（= `~/.ai-notes/ttr/ai-harness-plan-rev1.md`，逐字存檔）。

## Why（為什麼）

- 成本是 Claude Pro 與 Codex 的訂閱配額，不是 API 費用；router 與 gateway 會改走 API 計費，不適用。
- repo 已有單一權威加 adapter，但模型政策只有「不寫死」，沒有分級；`xhigh` effort 與 Fable 是最大的配額消耗。
- agent 與防線只存在於 TTR repo，其他專案無法重用。
- 一次只開一個 session 的流程，無法善用 Orca 與 Claude Code 原生的平行與跨 session 訊息。

## Non-Goals（不做什麼）

- 不採用 claude-code-router、LiteLLM、OpenRouter 等 gateway。
- 不在 Orca 內建立或刪除 campaign worktree；不用 Claude `--worktree` 建 campaign worktree。
- 不改 `scraper/**`、`web/**`、`supabase/**`，不寫 production DB。
- Phase 3 前不搬動通用 agent 的權威位置。
- 本機模型不得用於任何由 hooks 守護的動作。

## Design（設計摘要）

- `tier: plan | build | grunt` 寫在 `.github/agents/*.agent.md` frontmatter，由 `scripts/sync_ai_adapters.py` 投影成 Claude `model`／`effort` 與 Codex agent TOML。具體 model ID 仍禁止，家族別名與 effort 允許。
- 使用者層（不入 repo）：`~/.claude/settings.json`、`~/.codex/config.toml` profiles。
- 可攜 harness 為獨立 repo，輸出 Claude plugin 與 Codex install 腳本；Copilot 由各 repo 的 sync 複製。

## 使用者裁決（2026-10-20，全部依 plan §5 建議）

| # | 裁決 |
|---|---|
| D1 | slug `ai-harness`，worktree `ttr-ai-harness-worktree`，branch `feat/ai-harness`；Phase 1、2 共用，Phase 3 在新 repo，Phase 4 另開 |
| D2 | 通用 agent 權威檔搬到 harness repo，TTR `.github/agents` 變 generated；到 Phase 3 才做 |
| D3 | 主對話預設 `opusplan`，規劃 session 手動 `/model fable` |
| D4 | `.worktreeinclude` 含 `scraper/.env`、`web/.env.local`（配合既有 `.env` hooks） |
| D5 | worktree 一律以 git 指令建立，Orca 只顯示與啟動 |
| D6 | 先以 `/context` 量測；常駐超過約 3k tokens 才合併 54 個來源 skill |
| D7 | 退役 `tokyo-taiwan-radar-agents-repo` worktree，由本 campaign 取代 |

## References

- [docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md](../../../CLAUDE_CODE_MIGRATION_RUNBOOK.md)
- [docs/specs/parked/ai-portability-followups.md](../../parked/ai-portability-followups.md)
- [docs/evaluation/campaigns/2026-10-14-ai-portability.md](../../../evaluation/campaigns/2026-10-14-ai-portability.md)
