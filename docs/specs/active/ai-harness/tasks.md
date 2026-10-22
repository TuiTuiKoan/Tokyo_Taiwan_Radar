# Tasks

每完成一步把 `- [ ]` 改 `- [x]`，並 commit（即使只改這一行）。執行證據記入 [notes.md](./notes.md)，各項完整規格見 [plan.md](./plan.md) §3。

## Phase 0：盤點、量測、裁決

- [x] 建 worktree `ttr-ai-harness-worktree`（branch `feat/ai-harness`，起點 origin/main `90dab624`）；`.git/info/exclude` 已 reconcile
- [x] 使用者裁決 D1–D7（2026-10-20，依 rev.1 建議）；記入 proposal.md。**D4 於 2026-10-23 撤回（不得複製 secrets），待重新裁決 D4'**
- [x] 存檔 plan.md（SHA-256 `5f492d90…c585bf` 與 `~/.ai-notes/ttr/ai-harness-plan-rev1.md` 相符）
- [x] H0：使用者核准後 commit 本 spec 骨架（`a03ce9bf`），不 push
- [x] `/context` 實測 TTR 的 skill 與 agent 常駐 token，記入 notes.md §3（D6 的 baseline；結論：不合併來源 skill）
- [x] D7：`tokyo-taiwan-radar-agents-repo` worktree 已不存在（2026-10-23 Close Campaign Phase A 與本 session 各自查證：登記、目錄、本地與遠端分支、exclude 行皆無）；無需退役，見 notes.md §4
- [x] Plan Critic（Codex）審 plan.md：回傳六項修訂意見；plan.md 已更新為 rev.2（`~/.ai-notes/ttr/ai-harness-plan-rev2.md` 有副本）。批評全文未提供，未另存
- [ ] D4'：使用者裁決「worktree 不帶正式 secrets」（plan §5）；Phase 2 go 條件
- [ ] D8：使用者裁決 Phase 3 版本釘選機制（plan §5）；Phase 3 go 條件，可在 Phase 2 之後處理
- [ ] 修訂後的 plan.md 與 proposal.md、tasks.md、notes.md 一併 commit（等使用者核准）

## Phase 1：模型分級

- [x] `.github/agents/*.agent.md` 加 `tier`；`sync_ai_adapters.py` 投影 Claude `model`／`effort` 與 `.codex/agents/*.toml`
- [x] `--check` 要求每個 agent 皆有已知 `tier`。偏離計畫：`pinned_models()` 不放寬，來源檔仍禁任何 `model:`（含別名），因為 Copilot 會把別名當模型名稱解析；別名只出現在生成的 Claude wrapper（見 notes.md §2）
- [x] AGENTS.md「模型政策」改寫；測試更新（492 passed）
- [ ] 執行前模型評估（2026-10-23 使用者要求）：AGENTS.md 已寫入規則；仍待 Architect 計畫範本與 handoff 規則加「每個 phase／步驟的建議 tier 與主對話模型」欄位；agent 交接時先報建議模型再動工。主對話無法自動換模型，自動部分只靠 `opusplan`（plan mode 走 Opus、執行走 Sonnet）與 subagent `tier`
- [ ] 評估 `ANTHROPIC_DEFAULT_OPUS_MODEL=claude-fable-5-1` 讓 `opusplan` 的規劃段改走 Fable（副作用：所有 `model: opus` 的 subagent 也變 Fable）；未實測前不採用
- [x] 使用者層：`~/.claude/settings.json`（`opusplan`、sonnet effort medium、`CLAUDE_CODE_SUBAGENT_MODEL=haiku`）、Codex `plan` profile 與 `[agents]` effort；`cheap` profile 留到 Phase 5（尚無本機模型）
- [x] 驗證：`sync --check` exit 0、pytest 492 passed、`claude -p --agent tester` 實測用 Haiku
- [ ] 記錄 Phase 1 之後每週的 cc-statusline 配額。注意：Phase 1 之前沒有留下配額基準，`/context` 的 token 數不是配額；比較只能是指標，不是證明
- [ ] 驗證 Phase 1 的四項 NOT TESTED：Codex 是否讀取 `.codex/agents/*.toml` 並套用 effort；`codex -p plan` 載入 profile；`claude --agent plan-critic` 實測 Opus；`opusplan` 的切換（需互動 session）

## Phase 2：Orca 與平行開發治理

- [ ] 前置（go 條件）：D4' 已裁決；Phase 1 的四項 NOT TESTED 已驗證或使用者明確接受
- [ ] `.gitignore` 加 `.claude/worktrees/`
- [ ] 不建立會複製 `scraper/.env`、`web/.env.local` 的 `.worktreeinclude`（D4 已撤回）；若建立，只列審過的非 secrets 檔案
- [ ] 驗證 web build 能否以佔位值（命令列傳入）通過；不行則另案補 `web/.env.example`（需讀 `web.instructions.md`）
- [ ] 修正 `git.instructions.md` 的 exclude reconcile 片段（macOS bash 3.2 的 `case` pattern 要寫成 `("$root"/*)`）
- [ ] 治理文件補三句（git 建立、git 清理、結案後以跨 session 訊息通知）
- [ ] Orca 安裝與設定（釘版本、不用 Delete）；spike：Orca orchestration 與 agent teams 各一次唯讀任務
- [ ] 驗證：Orca 內 `claude` 的 `/hooks` 與 push ask 生效；`/list-agents` 可見其他 worktree

## Phase 3：可攜 harness（新 repo）

- [ ] 前置（go 條件）：Phase 1 之後至少一週的配額紀錄（最早 2026-10-30；Phase 1 前沒有基準，僅作指標）；D8 已裁決；ai-portability-followups ① 的 CI 接線完成；Phase 2 spike 結果已記入 notes.md
- [ ] `harness.lock` 與 `sync --check` 比對 harness checkout 的 `HEAD`（無 checkout 時明確失敗）
- [ ] 驗收：plan §3 Phase 3 的六項 plugin 未安裝缺口條件全數通過

- [ ] 建 `ai-harness` repo、Claude plugin、Codex install 腳本、搬 hooks 與 tests
- [ ] TTR 移除重複 hooks、改 generated、`sync --check` 比對 pinned SHA
- [ ] 第二個專案試裝驗證

## Phase 4：TTR 精簡（另開 worktree）

- [x] D6 判定：不合併來源 skill（專案端約 2.6k tokens，低於 3k 門檻；notes.md §3）
- [ ] `AGENTS.md` 瘦身：hooks 規則表與殘餘風險移到 `docs/`（目前 17KB，Memory files 8.7k 是最大常駐項）；architect 瘦身；prompts 改 skills；併入 parked X1–X4

## Phase 5（可選）：本機模型

- [ ] Ollama 拉 Qwen3-Coder-30B-A3B 或 gpt-oss-20b；Codex `cheap` profile；一個月 A/B 後決定去留
