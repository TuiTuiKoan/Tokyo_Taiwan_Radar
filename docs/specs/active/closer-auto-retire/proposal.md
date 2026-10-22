---
slug: closer-auto-retire
title: Close Campaign 取得同意後自行執行 worktree 退役
status: active
branch: feat/closer-auto-retire
created: 2026-10-22
tags: [governance, agents, campaign-closer, worktree]
---

## What（做什麼）

Close Campaign & Retire Worktree（closer）在 Phase B 取得使用者一次同意後，若情況落在最小可行版本的自動範圍內
（只限 Claude Code、乾淨 `RETIRE_CANDIDATE`、ignored 集合全部可重建、path class 為 `canonical` 或 `divergent`、
由協調者派出的 closer subagent），Phase D 由 agent 自行執行可執行的退役步驟：移除 worktree、exclude 對帳、
`git branch -d`、殘留驗證，以及主工作樹的 disposition 回填 commit。範圍外的情況與任何 `git push` 維持現行
「產生指令交使用者」。

完整設計、裁決紀錄與試跑計畫見 [plan.md](./plan.md)；試跑證據寫在 [notes.md](./notes.md)。

## Why（為什麼）

- 現行 Phase D 全部由 agent 產生指令、使用者逐條複製貼上；一次退役要貼十條以上的獨立指令，其中多數是確定性步驟。
- 回填 disposition 時，「移除成功、回填中斷」會留下寫著 `pending` 的記錄；目前只能靠人工重做，沒有受測的冪等工具。
- D6 以「整份記錄 grep `pending`」判斷回填是否完成會誤判：已提交的記錄（例如 `2026-10-14-ai-portability.md`、
  `2026-10-13-senses-taxonomy.md`）在 disposition 區塊以外合法地出現 `pending` 這個字。

## Non-Goals（不做什麼）

- 任何 `git push` 的自動化（含 push 到 main 與 `git push origin --delete`）。
- 修改 `.claude/settings.json`、`scripts/claude/` 的 guard，或新增 allow 規則。
- 修改 `scripts/campaign-closeout-audit.sh` 的判定邏輯與 exit code。
- 改 closer 的 `claude-role`（維持 `closer`）。
- VS Code Copilot 與 Codex 的自動執行。
- 自動刪除殘留目錄。
- plan.md §5 的延後項 L1–L9。

## Design（設計摘要）

分三個 Phase（plan.md §7）：

1. **Phase 1：回填腳本與測試**。新增 `scripts/campaign-disposition-backfill.py`（純標準庫、不執行 git、不碰網路）
   與 `scripts/tests/test_campaign_disposition_backfill.py`。
   - apply：`--record <path> --block <file> --capsule <file>`，只替換 `## Worktree disposition` 到第一個 `###` 子節或下一個 `## `（取先出現者）之間的內容，
     子節原樣保留（2026-10-22 裁決）；
     區塊含 `pending` → 替換並印出 diff；已通過驗證 → `already_applied`；其他 → `unexpected_state`（exit 3）。
   - verify：`--verify --capsule <file>`，從 stdin 讀記錄（`git show origin/main:<record> |`），只檢查同一段 disposition 區塊（六值表必須寫在第一個 `###` 之前；
     `2026-10-13-senses-taxonomy.md` 是舊格式例外）。
   - capsule 每行 `key: value`；腳本讀取的鍵是 `decided_at`、六值的 `branch_tip`、`ahead`、`behind`、`dirty_count`、
     `ignored_artifact_set`、`path_identity`，apply 另需 `record`。鍵名在 Phase 3 寫進 closer SKILL 前視為暫定。
2. **Phase 2：試跑**（plan.md §8）。T-A 串接情境含遠端分支、T-B 無遠端分支、T-C scratch clone 驗證 B5、
   push base 交叉驗證與 D5 替身；依 §8.6 決策閘門決定是否進 Phase 3。
3. **Phase 3：規則文件**。closer agent 檔與 SKILL、`git.instructions.md`、`docs/evaluation/campaigns/README.md`、
   V-M-D agent 檔、`AGENTS.md`；之後跑 `python3 scripts/sync_ai_adapters.py`。

2026-10-22 起 Phase 2–3 暫停，等 pr-flow-tiering 試行結果；Phase 1 的腳本保留在分支上。進度見 [tasks.md](./tasks.md)。

## References

- [plan.md](./plan.md)（rev.4）
- [notes.md](./notes.md)
- `docs/evaluation/campaigns/README.md` § Recovery capsule、§ Freshness、§ Cleanup checklist
- `.github/skills/agents/campaign-closer/SKILL.md` § Recovery capsule
- `docs/specs/active/pr-flow-tiering/`（在 `origin/main`；Phase 2–3 的恢復條件）
