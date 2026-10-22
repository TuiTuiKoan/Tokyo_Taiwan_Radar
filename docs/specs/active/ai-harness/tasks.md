# Tasks

每完成一步把 `- [ ]` 改 `- [x]`，並 commit（即使只改這一行）。執行證據記入 [notes.md](./notes.md)，各項完整規格見 [plan.md](./plan.md) §3。

## Phase 0：盤點、量測、裁決

- [x] 建 worktree `ttr-ai-harness-worktree`（branch `feat/ai-harness`，起點 origin/main `90dab624`）；`.git/info/exclude` 已 reconcile
- [x] 使用者裁決 D1–D7（2026-10-20，全部依建議）；記入 proposal.md
- [x] 存檔 plan.md（SHA-256 `5f492d90…c585bf` 與 `~/.ai-notes/ttr/ai-harness-plan-rev1.md` 相符）
- [x] H0：使用者核准後 commit 本 spec 骨架（`a03ce9bf`），不 push
- [ ] `/context` 實測 TTR 的 skill 與 agent 常駐 token，記入 notes.md（D6 的 baseline）
- [ ] 以 Close Campaign agent 退役 `tokyo-taiwan-radar-agents-repo` worktree（D7；先審 unhandled work 與 session 占用，不用 `--force`）
- [ ] Plan Critic 審 plan.md（建議 `codex -s read-only`，不同模型家族）

## Phase 1：模型分級

- [x] `.github/agents/*.agent.md` 加 `tier`；`sync_ai_adapters.py` 投影 Claude `model`／`effort` 與 `.codex/agents/*.toml`
- [x] `--check` 要求每個 agent 皆有已知 `tier`。偏離計畫：`pinned_models()` 不放寬，來源檔仍禁任何 `model:`（含別名），因為 Copilot 會把別名當模型名稱解析；別名只出現在生成的 Claude wrapper（見 notes.md §2）
- [x] AGENTS.md「模型政策」改寫；測試更新（492 passed）
- [ ] 執行前模型評估（2026-10-23 使用者要求）：AGENTS.md 已寫入規則；仍待 Architect 計畫範本與 handoff 規則加「每個 phase／步驟的建議 tier 與主對話模型」欄位；agent 交接時先報建議模型再動工。主對話無法自動換模型，自動部分只靠 `opusplan`（plan mode 走 Opus、執行走 Sonnet）與 subagent `tier`
- [ ] 評估 `ANTHROPIC_DEFAULT_OPUS_MODEL=claude-fable-5-1` 讓 `opusplan` 的規劃段改走 Fable（副作用：所有 `model: opus` 的 subagent 也變 Fable）；未實測前不採用
- [x] 使用者層：`~/.claude/settings.json`（`opusplan`、sonnet effort medium、`CLAUDE_CODE_SUBAGENT_MODEL=haiku`）、Codex `plan` profile 與 `[agents]` effort；`cheap` profile 留到 Phase 5（尚無本機模型）
- [x] 驗證：`sync --check` exit 0、pytest 492 passed、`claude -p --agent tester` 實測用 Haiku
- [ ] 一週配額曲線對照 baseline（Phase 0 的 `/context` 與 cc-statusline 數字）

## Phase 2：Orca 與平行開發治理

- [ ] `.gitignore` 加 `.claude/worktrees/`；新增 `.worktreeinclude`（D4）
- [ ] 治理文件補三句（git 建立、git 清理、結案後以跨 session 訊息通知）
- [ ] Orca 安裝與設定（釘版本、不用 Delete）；spike：Orca orchestration 與 agent teams 各一次唯讀任務
- [ ] 驗證：Orca 內 `claude` 的 `/hooks` 與 push ask 生效；`/list-agents` 可見其他 worktree

## Phase 3：可攜 harness（新 repo）

- [ ] 建 `ai-harness` repo、Claude plugin、Codex install 腳本、搬 hooks 與 tests
- [ ] TTR 移除重複 hooks、改 generated、`sync --check` 比對 pinned SHA
- [ ] 第二個專案試裝驗證

## Phase 4：TTR 精簡（另開 worktree）

- [ ] 依 D6 量測結果決定是否合併來源 skill；architect 瘦身；prompts 改 skills；併入 parked X1–X4

## Phase 5（可選）：本機模型

- [ ] Ollama 拉 Qwen3-Coder-30B-A3B 或 gpt-oss-20b；Codex `cheap` profile；一個月 A/B 後決定去留
