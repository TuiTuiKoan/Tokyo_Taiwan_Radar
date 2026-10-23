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

- [x] `.gitignore` 加 `.claude/worktrees/`
- [ ] 不建立會複製 `scraper/.env`、`web/.env.local` 的 `.worktreeinclude`（D4 已撤回）；若建立，只列審過的非 secrets 檔案
- [ ] agent worktree 的 dry-run 驗證只限已確認不需憑證的來源（目前僅 TCC）；其他來源 NOT TESTED，用 fixture、mock 或使用者自行驗證（靜態核對反例：`gguide_tv`、`cinemaclair`、`tokyoartbeat`）
- [x] 驗證 web build 以佔位值（命令列傳入）通過：`pnpm --dir web run build` exit 0、250 個靜態頁（notes.md §9）；不需補 `web/.env.example`。執行階段（連線、登入）仍 NOT TESTED
- [x] 修正 `git.instructions.md` 的 exclude reconcile 片段（macOS bash 3.2 的 `case` pattern 要寫成 `("$root"/*)`）；先前以修正版實測 converged
- [x] 治理文件補三句：`git.instructions.md` 新增兩節（建立與清理只走 git、不複製 secrets；推送與結案後以跨 session 訊息通知），並在 `validate-merge-deploy.agent.md`（Step 5 第 7 項）與 `campaign-closer.agent.md`（完成後）加一條通知指示
- [x] Spike 方案已寫好（使用者選 Claude agent teams）：[spike-agent-teams.md](./spike-agent-teams.md)，含啟動指令、提示詞、成功與停止條件、判定規則
- [x] Spike 已由使用者執行一次（2026-10-23）；完整報告 `spike-result.md`，核對與判定見 notes.md §10
- [x] Spike 重跑完成（相同提示詞，補量測 S3）：用量前後皆 15%／29%／7%（差 0 點）；無污染；S4 成立；第一次報告已還原為 `spike-result-run1.md`（SHA-256 相符）。**最終判定：可列入 Phase 2b 考慮，不是採用**（notes.md §12）
- [x] Phase 1 後續修正完成（2026-10-23，先寫 39 個測試、9 個先紅，再修到全綠；證據見 notes.md §13）：`write_outputs` 先檢查衝突與可編碼性再刪除（A、#7）；`is_generated` 改為整行比對且依副檔名選 marker（E）；`toml_string` 跳脫 DEL（D）；tier 容許行內註解（#13）；agent 輸出名稱碰撞時報錯（#8）；補測 B、C、T4、T5、T6、T7、T8、T9、T13、欄位順序。未做：T10（`conftest` 對缺少 `.codex` 的 `copytree`）、T11（`len(sources) * 2` 寫死）、T12（`MODEL_ID_PREFIXES` 冗餘，維護成本）、G（symlink，未確認）、#10 到 #12 的其餘缺口。尚未 commit
- [x] Phase 1 後續修正已 commit（`6bfc2fa8`，531 個測試通過）
- [ ] Phase 1 修正第二批（使用者要求規劃，2026-10-23；全部先寫測試或先做 mutation check，再改；建議模型 Sonnet、medium；plan 見 notes.md §14）：
  - [x] R1：`handoffs` 全部缺 `label`／`agent` 時不輸出孤立標題（Claude wrapper 與 Codex 檔）；先紅後綠，未 commit
  - [x] R2：symlink 政策（使用者 2026-10-23「依建議」＝拒絕、不跟隨）：預期輸出路徑上的 symlink 是衝突，`--check` 報 `symlink …`；掃描不回傳 symlink、不進入 symlink 目錄（`os.walk(followlinks=False)`）；Python 3.12 與 3.14 實測一致；未 commit
  - [ ] R3：`conftest` 的 `tmp_repo` 對缺少的來源目錄（如 `.codex`）不再丟錯
  - [ ] R4：`len(sources) * 2` 改為依目錄比對 `.claude/agents`、`.codex/agents` 與來源的名稱集合
  - [ ] R5：移除冗餘的 `MODEL_ID_PREFIXES`，tier 別名集合只在一處定義
  - [ ] R6：補 `.codex/agents/` 子目錄的手寫檔不被動、生成殘留會被 `--check` 報告的測試

### 2b（條件：2a 條件；Phase 1 NOT TESTED 已驗證〔已成立〕；第一週配額基準已記錄且沒有耗盡配額；agent teams spike 已結案〔已成立〕；agent view 小試驗已結案）

- [x] 拋棄式 worktree `ttr-agent-view-trial-worktree` 已建立（使用者 2026-10-23 核准；分支 `feat/agent-view-trial`，起點 origin/main `92a5bd45`，`.git/info/exclude` 已對帳）
- [x] agent view 小試驗完成（重跑，2026-10-23）：S1 到 S4 成立；用量前後 5%／31%／8% 到 7%／31%／8%；B 選 No 後未執行 push；沒有自己 commit 或 push；VS Code 沒有通知。證據與限制見 notes.md §22；試驗 session 已停止並移除、試驗檔已清除
- [x] S5 已由使用者明確確認成立（2026-10-23）；agent view 小試驗的判定為「可列入 Phase 2b 正式使用，不是採用」
- [ ] 後續小試驗（NOT TESTED）：從不同 worktree 派出 session 是否都能出現在同一個 agent view 的清單；`Notification` hook 能否補上 VS Code 沒有通知的缺口
- [x] **ai-harness 分支已 rebase**（2026-10-23，使用者核准）：3 個 commit 有衝突（`validate-merge-deploy.agent.md`、`plan-critic.agent.md`、`AGENTS.md`），各自保留 main 的新敘述並加上我們的 `tier` 與「批評全文必須存檔」；生成物重新生成；結果領先 origin/main 11、落後 0；`sync --check` exit 0；`scripts` 全部測試 967 passed（含 main 的測試）；詳見 notes.md §24
- [x] **V-M-D 推送完成**（2026-10-23，使用者從主工作目錄執行）：origin/main 就是 `97db47f2`；Vercel Production deployment `7270206104` success；詳見 notes.md §25。`docs/specs/active/ai-harness/` 現在在 GitHub 上
- [ ] 下一步候選（使用者決定）：標記設計（notes.md §19.4）、`scraper-zero-output` spec、`feature-kickoff` 的互動驗證、Phase 2b 的每週配額基準（最早 2026-10-30）、從不同 worktree 派出 session 的小試驗、`Notification` hook、agent view 試驗 worktree 的退役
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

## Feature kickoff（issue 統合；使用者 2026-10-23 決定做第 1 段）

- [x] `scripts/feature_kickoff.py`：唯讀；依 `spec:<slug>` 標籤、關鍵字候選、疑似重複、互相引用產出 Markdown；`--inventory` 盤點沒有 `spec:` 標籤的 issue；不呼叫任何 gh 寫入命令（有測試守住）。先寫 17 個測試（先紅），全綠；全部測試 554 passed
- [x] `.github/prompts/feature-kickoff.prompt.md`（生成 `.claude/commands/feature-kickoff.md`）：對 GitHub 唯讀、issue 內容視為資料不是指令、worktree 閘門、寫入限已確認 worktree 的 `proposal.md`／`tasks.md`、只寫 `Refs #N` 不寫 `Fixes`
- [x] 第一次真實使用：29 個無 `spec:` 標籤 issue 的盤點，見 [issue-inventory-2026-10-23.md](./issue-inventory-2026-10-23.md)；沒有貼任何標籤
- [x] 盤點的決定（2026-10-23）：#328、#346 已貼 `spec:ai-harness`（GitHub 寫入，已驗證）；QA Heartbeat 的 5 個 issue 保留，不動
- [ ] `scraper-zero-output` 是否建 spec：我的建議與依據見 notes.md §18.3，待使用者決定（使用者這次沒有回覆這項）
- [x] 其餘無標籤 issue 補上看板「階段」：使用者採用「來源健康」「爬蟲管線」兩個新名稱；已由我用 GraphQL 新增選項並設定 12 個 issue（#367、#375、#376、#377、#381 → 來源健康；#364、#394、#395、#398、#404、#407 → 爬蟲管線；#346 → AI工具鏈）；原有 42 個值全部未動（notes.md §19）
- [x] 看板標記設計（使用者 2026-10-23 決定採用）：主題比 spec 粗且由 spec 推導；「階段」已改名「主題」；對照表 `docs/specs/board-themes.json`；稽核腳本 `scripts/board_audit.py`（27 個測試）；每週回顧新增 Step 2b；規則寫進 `docs/specs/README.md` § 看板標記分工；已對 30 個 issue 套用推導的主題。細節與限制見 notes.md §26
- [ ] #328 的主題不一致：看板為「追蹤清理」，對照表（`spec:ai-harness`）為「AI工具鏈」，待使用者決定要改主題或改標籤
- [ ] `scraper-zero-output` 薄 spec：草稿在 `~/.ai-notes/ttr/scraper-zero-output-spec-draft/`；**不能放進 `ttr-scraper-zero-output-worktree`**（那是已合併的 #378 修復，且有一個忙碌中的 session 正在用，見 notes.md §26.5）；待使用者決定 worktree 與是否先協調該 session
- [ ] 在互動 session 實際用 `/feature-kickoff` 跑一次完整流程（需要一個真的要啟動的功能；`/feature-kickoff` 的行為目前只有腳本有測試，prompt 本身 NOT TESTED）
- [ ] 第 3 段（同功能內 agent teams 做實作）暫緩，實作型切分尚未驗證
- [ ] 同步改窄 `validate-merge-deploy.agent.md` 與 `campaign-closer.agent.md` 的「通知其他 session」描述（現行寫法仍是無條件通知；規則已在 `git.instructions.md` 改為只通知受影響者，notes.md §25.1）
