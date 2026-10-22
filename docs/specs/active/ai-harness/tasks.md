# Tasks

每完成一步把 `- [ ]` 改 `- [x]`，並 commit（即使只改這一行）。執行證據記入 [notes.md](./notes.md)，各項完整規格見 [plan.md](./plan.md) §3。

## Phase 0：盤點、量測、裁決

- [x] 建 worktree `ttr-ai-harness-worktree`（branch `feat/ai-harness`，起點 origin/main `90dab624`）；`.git/info/exclude` 已 reconcile
- [x] 使用者裁決 D1–D7（2026-10-20，依 rev.1 建議）；記入 proposal.md。**D4 於 2026-10-23 撤回（不得複製 secrets），待重新裁決 D4'**
- [x] 存檔 plan.md（SHA-256 `5f492d90…c585bf` 與 `~/.ai-notes/ttr/ai-harness-plan-rev1.md` 相符）
- [x] H0：使用者核准後 commit 本 spec 骨架（`a03ce9bf`），不 push
- [x] `/context` 實測 TTR 的 skill 與 agent 常駐 token，記入 notes.md §3（D6 的 baseline；結論：不合併來源 skill）
- [x] D7：`tokyo-taiwan-radar-agents-repo` worktree 已不存在（2026-10-23 Close Campaign Phase A 與本 session 各自查證：登記、目錄、本地與遠端分支、exclude 行皆無）；無需退役，見 notes.md §4
- [x] Plan Critic（Codex）第一次：只回傳六項修訂提示，批評全文遺失（使用者貼上命令範本時未替換 `<提示>`）；plan.md 更新為 rev.2
- [x] Plan Critic（Codex）第二次：`codex exec -p plan -s read-only -o plan-critique-1.md`，全文存檔；結論 rev.2 未通過（B1–B6、N1–N5）；plan.md 更新為 rev.3（`~/.ai-notes/ttr/ai-harness-plan-rev3.md` 有副本）
- [x] D4'：使用者 2026-10-23 裁決採用「worktree 不帶正式 secrets」（plan §5）；Phase 2a 條件已成立
- [x] D8：使用者 2026-10-23 裁決採用：`harness.lock` 為來源版本紀錄、缺 plugin 只警告、3b 之前不搬 hooks；只在 Phase 3b 生效，3a 試點不需要
- [x] rev.2 的 plan.md、proposal.md、tasks.md、notes.md 已 commit（`dfb40b6b`），未 push
- [ ] rev.3 的 plan.md、proposal.md、tasks.md、notes.md 與 `plan-critique-1.md` 一併 commit（等使用者核准）
- [ ] AGENTS.md 的「Plan Critic 批評全文必須存檔」規則（已修改、未 commit）一併 commit（等使用者核准）

## Phase 1：模型分級

- [x] `.github/agents/*.agent.md` 加 `tier`；`sync_ai_adapters.py` 投影 Claude `model`／`effort` 與 `.codex/agents/*.toml`
- [x] `--check` 要求每個 agent 皆有已知 `tier`。偏離計畫：`pinned_models()` 不放寬，來源檔仍禁任何 `model:`（含別名），因為 Copilot 會把別名當模型名稱解析；別名只出現在生成的 Claude wrapper（見 notes.md §2）
- [x] AGENTS.md「模型政策」改寫；測試更新（492 passed）
- [ ] 執行前模型評估（2026-10-23 使用者要求）：AGENTS.md 已寫入規則；仍待 Architect 計畫範本與 handoff 規則加「每個 phase／步驟的建議 tier 與主對話模型」欄位；agent 交接時先報建議模型再動工。主對話無法自動換模型，自動部分只靠 `opusplan`（plan mode 走 Opus、執行走 Sonnet）與 subagent `tier`
- [ ] 評估 `ANTHROPIC_DEFAULT_OPUS_MODEL=claude-fable-5-1` 讓 `opusplan` 的規劃段改走 Fable（副作用：所有 `model: opus` 的 subagent 也變 Fable）。**延後，未實測前不採用**（plan §1.3）
- [x] 使用者層：`~/.claude/settings.json`（`opusplan`、sonnet effort medium、`CLAUDE_CODE_SUBAGENT_MODEL=haiku`）、Codex `plan` profile 與 `[agents]` effort；`cheap` profile 留到 Phase 5（尚無本機模型）
- [x] 驗證：`sync --check` exit 0、pytest 492 passed、`claude -p --agent tester` 實測用 Haiku
- [ ] 記錄 Phase 1 之後每週的 cc-statusline 配額。注意：Phase 1 之前沒有留下配額基準，`/context` 的 token 數不是配額；比較只能是指標，不是證明
- [x] `codex -p plan` 載入 profile：`codex exec -p plan` 的執行標頭顯示 gpt-6.1-sol、effort high（2026-10-23）
- [x] Phase 1 的四項驗證（2026-10-23，非互動命令完成，證據與限制見 notes.md §8）：Codex 讀取 `.codex/agents/*.toml` 並套用 effort low；`--agent plan-critic` 用 Opus；`opusplan` 在執行段 Sonnet、plan mode Opus；Haiku wrapper 以 subagent 委派時 effort low（`--agent` 主執行緒不生效）；grunt 品質探測 3/3（極有限）
- [ ] 決定是否要補驗 grunt 的其他任務（選擇器除錯、日文貼文）；目前未驗證

## Phase 2：Orca 與平行開發治理

分兩段（plan §3.1）：**2a** 受限工作，**2b** 正式平行開發。

### 2a（條件：Phase 1 commit 存在；D4' 已裁決。兩項都已成立）

- [ ] `.gitignore` 加 `.claude/worktrees/`
- [ ] 不建立會複製 `scraper/.env`、`web/.env.local` 的 `.worktreeinclude`（D4 已撤回）；若建立，只列審過的非 secrets 檔案
- [ ] agent worktree 的 dry-run 驗證只限已確認不需憑證的來源（目前僅 TCC）；其他來源 NOT TESTED，用 fixture、mock 或使用者自行驗證（靜態核對反例：`gguide_tv`、`cinemaclair`、`tokyoartbeat`）
- [ ] 驗證 web build 能否以佔位值（命令列傳入）通過；不行則另案補 `web/.env.example`（需讀 `web.instructions.md`）
- [ ] 修正 `git.instructions.md` 的 exclude reconcile 片段（macOS bash 3.2 的 `case` pattern 要寫成 `("$root"/*)`）
- [ ] 治理文件補三句（git 建立、git 清理、結案後以跨 session 訊息通知）
- [ ] Spike（一次性）：**一個**工作流、**一個**工具（Orca orchestration 或 agent teams 擇一），事先寫下成功與停止條件；一次執行後無明確收益即停止

### 2b（條件：2a 條件；Phase 1 NOT TESTED 已驗證〔已成立〕；第一週配額基準已記錄且沒有耗盡配額；spike 已結案）

- [ ] Orca 安裝並釘版本、設定 worktree 建立後的安裝命令、不使用 Delete
- [ ] 驗證（NOT TESTED，通過前不得稱相容）：Orca 內 `claude` 的 `/hooks` 與 push ask 生效；`/list-agents` 可見其他 worktree

## Phase 3：可攜 harness（新 repo）

### 3a 試點（條件：Phase 2b 的條件；至少兩週可比較的配額紀錄）

- [ ] `ai-harness` repo 只放一個 agent 與一個 skill；第二專案以 `--plugin-dir` 載入；TTR 保留現有 hooks，不搬防線
- [ ] 評估實際復用收益並記入 notes.md；收益不明確就停在 3a

### 3b 擴大（條件：3a 有明確收益；D8 已裁決；ai-portability-followups ① 的 CI 接線完成）

- [ ] `harness.lock` 為來源版本紀錄；驗收涵蓋乾淨 checkout、adapter 重生成、plugin 安裝與載入版本、Codex 安裝結果；CI 有依 lock 取得 harness 的步驟
- [ ] 缺口驗收：未安裝、停用、載入失敗、版本不符的預期行為與警告來源（TTR 保留的 SessionStart 腳本）；移除本地 hooks 前驗證 Bash guard、file guard、launcher 失敗、單次觸發
- [ ] 延伸既有 `agent_outputs()`／`expected_outputs()`／`check()`；拆分通用 guard 測試與 TTR 接線測試（含 `scripts/tests/test_claude_settings.py`）

- [ ] 建 `ai-harness` repo、Claude plugin、Codex install 腳本、搬 hooks 與 tests
- [ ] TTR 移除重複 hooks、改 generated、`sync --check` 比對 pinned SHA
- [ ] 第二個專案試裝驗證

## Phase 4：TTR 精簡（另開 worktree；不依賴 Phase 3）

- [x] D6 判定：不合併來源 skill（專案端約 2.6k tokens，低於 3k 門檻；notes.md §3）
- [ ] 先逐檔量測 Memory files（8.7k 未拆解）；再 `AGENTS.md` 瘦身：hooks 規則表與殘餘風險移到 `docs/`，Codex 與 Copilot 仍需遵循的行為規則不全部改成連結；architect 瘦身；prompts 改 skills；併入 parked X1–X4

## Phase 5（可選）：本機模型

- [ ] Ollama 拉 Qwen3-Coder-30B-A3B 或 gpt-oss-20b；Codex `cheap` profile；一個月 A/B 後決定去留
