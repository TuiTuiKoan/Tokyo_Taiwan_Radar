# AI Harness v2 計畫 rev.3 — Orca 平行開發、模型分級、跨專案可攜 harness

rev.1：2026-10-15，Architect（Claude Fable 5.1，Claude Code 2.1.300）。rev.2：2026-10-23，依 Codex 的六項修訂意見更新（commit `dfb40b6b`）。rev.3：2026-10-23，依 Codex Plan Critic 全文（[plan-critique-1.md](./plan-critique-1.md)，gpt-6.1-sol、effort high）的六項阻擋與五項建議更新（Claude Opus 5.5 執行）。

狀態（2026-10-23）：D1、D2、D3、D5、D6、D7 已定案；D4 已撤回，**D4' 已裁決採用**；**D8 已裁決採用**（範圍限 Phase 3b，缺 plugin 只警告，3b 之前不搬 hooks）。Phase 0 完成；Phase 1 的程式碼已完成並 commit，使用端驗證與配額量測未完成；Phase 2 以後尚未開始。進度真值是 [tasks.md](./tasks.md)，執行證據是 [notes.md](./notes.md)；本文與兩者衝突時以兩者為準。

rev.1 原檔：`~/.ai-notes/ttr/ai-harness-plan-rev1.md`（SHA-256 `5f492d901f2846a6865aee0de5ebc1d73bed9889e88ccc1c00edc0e77ec585bf`）。rev.2 原檔：`~/.ai-notes/ttr/ai-harness-plan-rev2.md`（SHA-256 `dd9ca68973ca86fd77dbceebda8e9fe0be5de2d101b3abf07fd9855f5b1d5f42`，也在 git 的 `dfb40b6b`）。rev.3 完整替代 rev.2。

## rev.2 變更摘要

| # | Codex 意見 | rev.2 處理 | 位置 |
|---|---|---|---|
| 1 | Secrets 與 D4：`.worktreeinclude` 不得複製 `scraper/.env`、`web/.env.local` | 撤回 D4 的建議；改為「worktree 不帶正式 secrets」。以實測證明 scraper dry-run 不需要 `.env`；web 驗證改用不含 secrets 的方式。D4 標為需重新裁決。移除「hooks 禁止 agent 讀寫 `.env` 所以可複製」的論述 | §3 Phase 2、§4、§5 |
| 2 | 進度漂移 | D1–D7 已於 2026-10-20 裁決；Phase 0、1 狀態、仍未完成項目已同步；刪除「回覆 D1–D7、再執行 Phase 0→1」的下一步 | 全文、§6 |
| 3 | 模型投影 | 移除「放寬 `pinned_models()`」；來源 `.agent.md` 只宣告 `tier`，別名只寫入生成的 Claude wrapper；Codex effort 等 NOT TESTED 項目保留為待驗證 | §1.3、§3 Phase 1 |
| 4 | Phase 4 | 合併 54 個來源 skill 標為已否決；改為 `AGENTS.md` 瘦身 | §3 Phase 4 |
| 5 | Phase 3 前置決策 | 提出 pinned commit SHA（`harness.lock`）方案、更新與同步的責任流程、plugin 未安裝缺口的驗收條件；列為 D8，待使用者裁決 | §3 Phase 3、§5 |
| 6 | 繼續工作的門槛 | 新增 Go/No-Go 門檻；一週配額曲線與使用端驗證是 Phase 2、3 的依據；明確聲明工具搬遷本身不是已證明的配額效益 | §3.1 |


## rev.3 變更摘要（對照 [plan-critique-1.md](./plan-critique-1.md)）

評審結論：rev.2 未通過，六項先前意見 3 項 CLOSED、3 項 PARTIAL。以下是每個阻擋項（B）與建議（N）的處理。我先核對了 Codex 引用的程式碼（`main.py` 的 `scrape()` 先於 dry-run 判斷、`gguide_tv.py` 建立 Supabase client、`cinemaclair.py` 與 `tokyoartbeat.py` 讀環境變數），事實屬實。

| 項目 | 處理 | 位置 |
|---|---|---|
| B1 配額門檻 | 統一 plan、tasks、§6 的門檻；區分「受限 spike」與「正式平行開發」；指定人工記錄的最簡方式；第一週只建立觀測基準，不判定「沒有退步」 | §3.1、§6、Phase 2 |
| B2 D8 的 SHA 檢查 | `harness.lock` 改稱「來源版本紀錄」；補上鎖定的產物、乾淨 checkout、plugin 安裝與載入版本、Codex 安裝結果的驗收，更新與回退責任，CI 取得 harness 的步驟 | Phase 3 |
| B3 dry-run 保證過度推廣 | 結論限縮為「TCC 來源在無 `.env` 時成功」；其他來源 NOT TESTED；以 fixture、mock 或使用者自行驗證補足，不另建 secrets 系統 | Phase 2、§5 D4' |
| B4 進度與模型描述漂移 | 列出 Phase 1 未完成項；更正 X1–X4「未投影權限不等於未投影模型」；§0 標為歷史盤點；各 phase 標示建議模型與 effort；修正 worktree 標題矛盾；`ANTHROPIC_DEFAULT_OPUS_MODEL` 評估去留明寫 | §0、§1.3、§3 |
| B5 安裝缺口驗收 | 補「已安裝但停用、載入失敗、版本錯誤」的狀態表；警告由 TTR 自己保留的設定與腳本發出；取捨列入 D8；移除本地 hooks 前必須驗證 Bash guard、file guard、launcher 失敗、單次觸發；刪除與「子目錄啟動」風險等級的比較 | Phase 3、§5 D8 |
| B6 已查證與實測混淆 | 每項標示「文件描述／靜態核對／本機實測／NOT TESTED」；notes 追加更正，不改原文 | §1.2、§4、notes §6 |
| N1 Phase 3 縮小 | 第一個交付改為「第二專案以 `--plugin-dir` 載入一個 agent 與一個 skill，TTR 保留現有 hooks」；之後才決定發布與防線搬遷 | Phase 3 |
| N2 Phase 4 解耦 | Phase 4 不再依賴 Phase 3；不把 Codex 仍需遵循的行為規則全部改成連結 | Phase 4、§3.1 |
| N3 縮小 spike | 只選一個具體工作流、一個工具，設一次性停止條件 | Phase 2 |
| N4 沿用生成器 | 延伸 `agent_outputs()`、`expected_outputs()`、`check()`；拆分通用 guard 測試與 TTR 接線測試，並處理 `scripts/tests/test_claude_settings.py` | Phase 3 |
| N5 提交後紀錄 | tasks 更新為已 commit；notes 追加提交結果 | tasks、notes §6 |

## 0. 現況盤點（本 session 實測，2026-10-15）

| 項目 | 觀測值 |
|---|---|
| Claude Code | 2.1.300；登入方式 claude.ai，`subscriptionType: pro`；使用者層 `model: fable`，`modelSettings` 對 opus/sonnet 5.5 都設 `effortLevel: xhigh` |
| Codex | codex-cli 0.160.0；`~/.codex/config.toml` `model = "gpt-6-luna"`、effort medium；`hooks`、`goals`、`apps` 等 feature 為 stable；無 `~/.codex/agents/`、無 `~/.codex/AGENTS.md`、無 `~/.codex/hooks.json` |
| Copilot | repo 仍以 `.github/agents/*.agent.md`、`.github/skills`、`.github/prompts` 為權威；runbook 前提是 Copilot Enterprise 可能被撤銷 |
| 硬體 | Apple M1 Max、32 GB；Ollama 已安裝，只有舊的 `qwen2:7b`、`llama3.2`（14–16 個月前） |
| 使用者層 Claude 設定 | 沒有 `~/.claude/CLAUDE.md`、`~/.claude/agents/`、`~/.claude/rules/`；只有 cc-statusline plugin |
| ai-portability campaign | 已結案（2026-10-14 close-out record）；worktree 已退役；24 條後續項目在 `docs/specs/parked/ai-portability-followups.md`（含 X1–X4 角色裁決） |
| `tokyo-taiwan-radar-agents-repo` worktree | rev.1 撰寫時（2026-10-15）：外部路徑、`agents/…` 分支、0 ahead／87 behind、無 spec、無 commit。**2026-10-23 已不存在**（登記、目錄、本地與遠端分支皆無；notes.md §4），D7 目標已達成 |
| 專案 harness 體積（2026-10-15 的歷史盤點，不代表 Phase 1 之後的現況） | 13 個 agent 檔 3,138 行（architect 一檔 1,197 行）；68 個 SKILL.md 共 17,537 行、history.md 20,309 行；其中 54 個是 `sources/` 爬蟲來源 skill |
| 防線 | `.claude/settings.json` 的 `permissions.ask`（push）＋ PreToolUse hooks（`scripts/claude/`）；只保護從 repo／worktree 根啟動的 Claude Code；Copilot、Codex 無防線 |

## 1. 三個問題的直接答案

### 1.1 不需要先準備本機硬體與開源模型基礎設施

- 「省成本」在你的情況是**省訂閱配額**，不是省 API 美元：Claude 是 Pro 訂閱，Codex 走 ChatGPT 登入。
- 任何 gateway／router（claude-code-router、LiteLLM、OpenRouter、Opper）都要用 API key 計費。Claude Code 文件明言：gateway credential 生效時「訂閱登入不送出、訂閱額度不適用」，而且 Anthropic 不支援經 gateway 把 Claude Code 導到非 Claude 模型。對 Pro 使用者這條路是**加錢**而不是省錢，且會破壞 hooks 以外的功能假設（Explore subagent 的特殊模型規則、prompt cache、Remote Control 等）。
- 真正的省配額手段都在訂閱內、都不需要新硬體：主對話 `opusplan` 或降 effort、subagent 走 `haiku`／`sonnet`、Codex 作第二個配額池、本機模型只接「零風險小任務」。
- 本機模型是**可選的第五階段**，M1 Max 32 GB 已足夠跑 MoE 類 coder 模型（例：Qwen3-Coder-30B-A3B，Q4 約 18–19 GB；gpt-oss-20b 約 13 GB），不必買機器。它們的角色限定為摘要、翻譯、commit 訊息、簡單重構，**不**用於任何要過 hooks／權限閘門的 production 動作（AGENTS.md 模型政策已有此條）。

### 1.2 Orca ADE 可行，而且與現有 worktree 治理相容，但要守三條邊界

Orca（stablyai/orca，MIT，桌面 Electron app，macOS／Windows／Linux）是「一個 app 裡平行跑多個 CLI agent，每個 agent 一個 git worktree」。它**不是** VS Code 擴充；它內嵌 VS Code 的編輯器元件。你的 VS Code 工作流照舊，Orca 只負責「開多個 worktree、各跑一個 Claude Code／Codex、看 diff、合併」。

相容性依據（Orca 官方文件描述；本機整合 NOT TESTED，需在 Phase 2 驗證）：
- Orca 以 worktree 為 cwd 啟動 `claude`，會讀 worktree 內的 `.claude/`；「你既有的 hooks 會在 Orca 啟動 agent 時照跑」。本 repo 的 `.claude/settings.json` 與 `scripts/claude/` 都已 commit，所以每個 worktree 根目錄都有防線。
- 自己用 `git worktree add` 建的 worktree 在 Orca 裡是 hidden，可從「hidden worktrees」卡片顯示進側欄 → 可以**完全沿用** `git.instructions.md` 的 `ttr-<slug>-worktree`／`<repo>.worktrees/<slug>` 命名與 `.git/info/exclude` 規則，Orca 只當檢視器與啟動器。
- `.worktreeinclude`（Orca 與 Claude Code 共用同一個檔名）：把 gitignored 檔案**複製**到每個新 worktree；`orca.yaml` 的 `worktree.sharedDirectories` 用 APFS clone／symlink 共享 `node_modules` 之類。
- Orca 有「Auto-run commands on worktree create」與每 agent 的啟動 hooks。

三條邊界：
1. **不要在 Orca 內刪 worktree。** Orca 的 Delete「同時刪目錄與 branch」，且有 Force Delete；這直接牴觸 repo「never `--force`、never `-D`」規則與 Close Campaign 的結案前置條件。清理一律走 `git worktree remove` + `git branch -d`（hooks 已擋 force 變體）。
2. **不要用 Claude Code 的 `--worktree` 建 campaign worktree。** 它固定放 `.claude/worktrees/<name>/`、分支叫 `worktree-<name>`，結案稽核腳本與 ledger 都認不得；而且 hooks 的 `$CLAUDE_PROJECT_DIR` 不跟著進 worktree。`--worktree` 只留給「subagent 臨時隔離」（agent frontmatter `isolation: worktree`）。
3. **「agents 彼此了解 context」要分層理解。** Orca 本身沒有共享記憶；它提供的是「diff 行註解批次送成 prompt」與實驗性的 orchestration CLI（run／task／worker-start／send／ask／gate）。共享 context 的真值仍是檔案（`docs/specs/active/<slug>/tasks.md`、`notes.md`），這點 repo 已經做對了。Claude Code 2.1.300 原生另有兩個機制：
   - **跨 session 訊息**（`ListAgents`／`SendMessage`，同機 Unix socket，免設定、2.1.224+ 預設開）：兩個 worktree 裡的 Claude 可以互相通知「我改了 schema」「rebase 安全了」。只傳純文字，不傳對話歷史；收方的 hooks 與權限照常生效。
   - **Agent teams**（`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`，實驗）：共享 task list + mailbox，teammate 可用既有 subagent 定義與各自模型。代價是 token 線性增長，且 split-pane 不支援 VS Code 終端。
   Codex 與 Claude 之間沒有跨工具訊息通道，只能靠檔案與 Orca。

### 1.3 模型調控：三個工具各有原生 knob，repo 只該表達「tier」

| 工具 | 可用 knob（已查官方文件） | 適合放哪一層 |
|---|---|---|
| Claude Code | 主對話：`/model opusplan`（規劃 Opus、執行自動 Sonnet）、`best`／`fable`／`opus`／`sonnet`／`haiku` 別名、`/effort`、`modelSettings.<id>.effortLevel`。Subagent：frontmatter `model: haiku|sonnet|opus|fable|inherit` + `effort: low…max`；`CLAUDE_CODE_SUBAGENT_MODEL` 作無 `model` 欄位者的預設（2.1.251 起優先序：呼叫參數 > frontmatter > env > 主對話）；`CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` 強制全員同一模型 | 別名與 effort 可進 repo；具體 ID 只能在使用者層 |
| Codex | `~/.codex/config.toml` profiles（`codex -p plan` / `-p cheap`）、`--oss` + `model_providers.ollama`；custom agents `.codex/agents/*.toml`：`model`、`model_reasoning_effort`（low…ultra）；`[agents] default_subagent_model`／`default_subagent_reasoning_effort`。限制：custom agent **不能**改 `model_provider`、`sandbox_mode`、`approval_policy` → 本機模型只能整個 session 切 profile | effort 可進 repo；model／provider 放使用者層 profile |
| Copilot (VS Code) | Chat 模型選單；BYOK（2026-04-22 GA，Business／Enterprise；可接 Anthropic／OpenAI／OpenRouter／Ollama／Foundry Local；涵蓋 chat、plan agent、custom agents，不含 inline completion） | 全部在 VS Code 使用者設定 |

結論：repo 的 agent 權威檔新增一個與工具無關的 `tier: plan | build | grunt` 欄位，由 `scripts/sync_ai_adapters.py` 投影：

| tier | Claude wrapper | Codex agent TOML | Copilot |
|---|---|---|---|
| plan（architect、plan-critic） | `model: opus`（或 `inherit`，由使用者在主對話選 fable）、`effort: high` | `model_reasoning_effort = "high"` | 不投影 |
| build（engineer、designer、scraper-expert、vmd、closer） | `model: sonnet`、`effort: medium` | `"medium"` | 不投影 |
| grunt（tester、history-teller、update-history、peatix／tcc subagent、lianbu） | `model: haiku`、`effort: low` | `"low"` | 不投影 |

模型政策（rev.2，已依實作更正）：**來源檔一律不寫 `model:`，連家族別名也不行**。具體 model ID 會下架（`claude-sonnet-4-5` 事故），而 Copilot 讀同一份 `.agent.md`，會把 `model: opus` 當模型名稱解析，是同型風險。`pinned_models()` 因此維持原行為。來源檔只宣告 `tier`；別名（opus／sonnet／haiku）與 effort 只出現在 sync 生成的 Claude wrapper，Codex agent 檔只含 `model_reasoning_effort`，不含 `model`。rev.1 曾要求放寬 `pinned_models()`，已撤回。

使用者層（不入 repo）建議值：
- `~/.claude/settings.json`：`model: "opusplan"`（日常）；需要 Fable 時 `/model fable` 只在規劃 session；`modelSettings` 的 `xhigh` 降到 `high`（規劃）／`medium`（執行）；`env.CLAUDE_CODE_SUBAGENT_MODEL: "haiku"` 兜住沒有 `model` 欄位的 subagent（例如內建的 general-purpose；Explore 另有特殊規則）。15 個專案 agent 都已有 `tier`，包含 X1–X4 四個未投影權限的角色（architect 為 Opus，其餘三者為 Sonnet），所以它們不靠這個預設；**未投影權限不等於未投影模型**。`ANTHROPIC_DEFAULT_OPUS_MODEL=claude-fable-5-1`（讓 `opusplan` 規劃段改走 Fable）：評估延後，未實測前不採用，結論記在 tasks.md。
- `~/.codex/config.toml`：三個 profile：`plan`（gpt-6.1-sol、high）、`build`（gpt-6-luna、medium）、`cheap`（`--oss`、ollama、Qwen3-Coder-30B-A3B）；`[agents] default_subagent_reasoning_effort = "low"`。

## 2. 跨專案可攜的三層架構

```
Layer 0  使用者層（跨專案、不入任何 repo）
         ~/.claude/CLAUDE.md、~/.claude/rules/*.md、~/.claude/settings.json（model、effort、env、teammateMode）
         ~/.codex/AGENTS.md、~/.codex/config.toml（profiles、model_providers、[agents]）、~/.codex/hooks.json
         VS Code 使用者設定（Copilot 模型、BYOK）

Layer 1  可攜 harness（獨立 git repo，例如 ~/Development/ai-harness）
         權威：agents/*.md（通用角色 10 個）、skills/（architect、plan-critic、engineer、tester、campaign-closer…）、
               hooks guard（scripts/claude/ 搬過來，含 tests）、sync 腳本
         產出：
           • Claude plugin：.claude-plugin/plugin.json + agents/ + skills/ + hooks/hooks.json（用 ${CLAUDE_PLUGIN_ROOT}）
             → `claude plugin marketplace add <local path 或 GitHub>`，user scope 安裝，所有專案都有
           • Codex：install 腳本寫 ~/.codex/agents/*.toml、~/.codex/hooks.json、~/.codex/skills/
           • Copilot：沒有 user-scope plugin 機制 → 由各 repo 的 sync 從 harness 複製到 .github/agents，--check 比對漂移

Layer 2  專案層（TTR repo）
         只留專案專屬：.github/copilot-instructions.md、.github/instructions/*、
         scraper 來源 skills（54 個）、scraper-expert／peatix／tcc／researcher／lianbu／designer 的 TTR 段落、prompts、
         .claude/settings.json（permissions.ask + 專案專屬 hooks 若有）
```

要點：
- Claude plugin 的 agent 會帶前綴（`ai-harness:engineer`），`claude --agent ai-harness:engineer` 與 `.claude/commands` 內的 handoff 文字要跟著改；plugin agent 的 `tools:` 白名單正常生效，但 frontmatter 的 `hooks`／`mcpServers`／`permissionMode` 會被忽略（repo 目前沒用這三個欄位）。
- plugin 的 hooks 在「plugin 啟用的每個 session」都跑 → 防線自動跨專案；原本 `.claude/settings.json` 的同一組 hooks 要移除，否則同一事件跑兩次。`test_claude_settings.py::test_settings_exact_shape` 要改。
- 啟用中的 plugin，其每個 agent／skill 的 name+description 會常駐每一輪 context（官方說明）。harness 要瘦：agent ≤ 10、skill ≤ 6；54 個爬蟲來源 skill 絕不進 harness。
- `.github/agents` 從「權威」降級為「Copilot adapter」，這是 ai-portability 的反向；要在 AGENTS.md 與 runbook 明寫新的權威位置，並讓 `sync --check` 在 TTR 內比對 harness 版本（用 git submodule 或 pinned commit SHA）。

## 3. 分階段計畫（Phase 1、2 共用 `ttr-ai-harness-worktree`（D1）；Phase 3 在新 repo；Phase 4 另開 worktree；各自 atomic commit）

建議模型：Phase 1、2、4 的實作與文件用 Sonnet（medium）；Phase 3 的設計決策與任何安全相關改動用 Opus（high），實作回到 Sonnet；計畫與審查用 Opus，必要時才用 Fable。

### Phase 0 — 盤點、量測、裁決（狀態：完成；D4' 與 D8 皆已於 2026-10-23 裁決）
- [x] 建 spec `docs/specs/active/ai-harness/`、worktree `ttr-ai-harness-worktree`（commit `a03ce9bf`）。
- [x] 使用者裁決 D1–D7（2026-10-20）；D4 於 rev.2 撤回。
- [x] `/context` 實測：整體 41.6k tokens（4%）；專案 skill 估計約 2.6k，低於 3k 門檻（notes.md §3）。
- [x] D7：agents-repo worktree 已不存在（notes.md §4）。
- [x] Plan Critic（Codex，`codex exec -p plan -s read-only -o …`，gpt-6.1-sol、effort high）：全文存於 [plan-critique-1.md](./plan-critique-1.md)；意見已在 rev.3 處理。第一次（rev.2 之前）只拿到修訂提示、沒有全文，不能宣稱當時的原報告已全部結案。
- [x] D4'：worktree 不帶正式 secrets（使用者 2026-10-23 裁決採用）；Phase 2a 的條件已成立。
- [x] D8：使用者 2026-10-23 裁決採用建議版：`harness.lock` 為來源版本紀錄，缺 plugin 時只警告，Phase 3 擴大（3b）之前不搬 hooks；只在 3b 才需要。

### Phase 1 — 模型分級（狀態：程式碼完成並 commit `361d17c1`；使用端驗證已於 2026-10-23 完成（含一項限制）；文件與配額量測未完成）
已完成（本機實測或靜態核對）：
1. [x] `tier` 欄位、sync 投影、`.codex/agents/*.toml`、`--check` 驗證；`pinned_models()` 不放寬（§1.3）。
2. [x] AGENTS.md「模型政策」改寫，含執行前模型評估規則。
3. [x] 使用者層：`~/.claude/settings.json`（`opusplan`、sonnet effort medium、`CLAUDE_CODE_SUBAGENT_MODEL=haiku`）、`~/.codex/plan.config.toml`、`[agents] default_subagent_reasoning_effort`。`cheap` profile 留到 Phase 5。
4. [x] `sync --check` exit 0；pytest 492 passed；`claude -p --agent tester` 的 `modelUsage` 只有 Haiku；**`codex exec -p plan` 實際載入 profile**（2026-10-23 執行標頭顯示 `model: gpt-6.1-sol`、`reasoning effort: high`）。

未完成：
- 文件：Architect 計畫範本與 handoff 規則加「建議模型與 effort」欄位（AGENTS.md 已寫規則，範本未改）。
- 評估：`ANTHROPIC_DEFAULT_OPUS_MODEL` 讓規劃段走 Fable。**延後**，未實測前不採用（會連帶改變所有 `model: opus` 的 subagent）。
- 使用端驗證（2026-10-23，本機實測，證據與限制見 notes.md §8）：
  - [x] Codex 讀取 `.codex/agents/tester.toml` 並套用 effort：子 thread 的角色是 tester，effort 為 low（父 thread 為 medium）；模型沿用 gpt-6-luna。
  - [x] `claude --agent plan-critic` 實際用 `claude-opus-5-5`。
  - [x] `opusplan`：執行段用 `claude-sonnet-5-5`，plan mode 用 `claude-opus-5-5`。
  - [x] Haiku wrapper：以 subagent 委派時，每個 API 請求都是 `claude-haiku-5-5` 加 `effort: low`。**限制**：以 `claude --agent <name>` 當主執行緒時，effort 沿用 session（實測為 medium），frontmatter 的 effort 不生效。
  - [x] grunt 品質（極有限的探測）：在有標準答案的 20 筆事件 JSON 統計題上，Haiku-low tester 3/3 正確，與 Sonnet 3/3 相同。這只涵蓋計數與日期比較，**不代表**選擇器除錯、日文貼文撰寫等任務的品質，那些仍未驗證。
- 量測：配額記錄見 §3.1。Phase 1 之前沒有配額基準。

### Phase 2 — 平行開發（Orca + Claude 原生，不改治理規則）
狀態（2026-10-23）：2a 的 housekeeping 與 web 佔位值 build 驗證已完成；spike（Claude agent teams，見 [spike-agent-teams.md](./spike-agent-teams.md)）已執行兩次（第二次補量測 S3），S1 到 S4 全部成立，判定「可列入 Phase 2b 考慮」（不是採用）；2b 尚未開始。

分成兩段，准入條件不同（§3.1）：**2a 受限工作**（housekeeping 與一個 spike）與 **2b 正式平行開發**（日常同時跑多個 agent session）。

**2a（不需要配額門檻）**
1. `.gitignore` 加 `.claude/worktrees/`（防止誤用 `--worktree` 污染主工作樹 untracked 清單）。
2. **不複製 secrets**（取代 rev.1 的 D4 建議；D4' 已於 2026-10-23 裁決採用）：
   - 不建立會複製 `scraper/.env` 或 `web/.env.local` 的 `.worktreeinclude`；若需要該檔，只列非 secrets 的 gitignored 設定，且逐項審過。
   - 依據：secrets 被複製進多個 worktree，就多了多份需要輪替與清理的副本；hooks 只擋 Claude Code 的讀寫、不保護 Codex 與 Copilot，所以「hooks 禁止 agent 讀寫 `.env`」不能當成複製 secrets 的安全依據。
   - **證據界線（本機實測）**：2026-10-23 在沒有 `scraper/.env` 的 `ttr-ai-harness-worktree` 執行 `python main.py --dry-run --source taiwan_cultural_center`，exit 0 並輸出事件 JSON。這只證明 **TCC 這一個來源**可行。
   - **不可推廣（靜態核對）**：`main.py` 先對每個來源執行 `scrape()`，才處理 dry-run 輸出（約第 433 行）；`gguide_tv.py` 會建立 Supabase client；`cinemaclair.py` 在有 `OPENAI_API_KEY` 時會呼叫 OpenAI；`tokyoartbeat.py` 讀取 `CONTENTFUL_TOKEN`。因此「dry-run 跳過 orchestrator 的寫入與後續 annotation」成立，但各來源內部是否需要憑證**需逐一確認，其他來源 NOT TESTED**。
   - 做法（較簡單的替代）：agent worktree 的驗證只限已確認不需憑證的來源（目前僅 TCC）；其他來源用 fixture、mock 或由使用者在自己的環境驗證；不為此另建 secrets 系統。
   - web 驗證（本機實測，2026-10-23）：在沒有任何 env 檔的 worktree，以命令列傳入 `NEXT_PUBLIC_SUPABASE_URL=https://placeholder.invalid`、`NEXT_PUBLIC_SUPABASE_ANON_KEY=placeholder-anon-key`、`NEXT_PUBLIC_SITE_URL=http://localhost:3000` 執行 `pnpm --dir web run build`，exit 0，250 個靜態頁產生，prebuild 的 i18n 與 JSON-LD 檢查通過，沒有改動任何被追蹤的檔案。所以 web build 不需要 secrets，也不需要補 `web/.env.example`。限制：這只證明 build；執行階段（`next dev` 連線、登入、Admin CRUD）仍需真實 Supabase，NOT TESTED，且不在 agent worktree 內做。
   - 需要正式 secrets 的操作（非 dry-run 的爬蟲、`annotator.py`、DB 寫入、連線 production 的 web）不在 agent 的 worktree 內做。
3. 修正 `git.instructions.md` 的 exclude reconcile 片段：macOS 預設 bash 3.2 對 `$(… case … esac …)` 內的 `case` pattern 語法錯誤，pattern 需寫成 `("$root"/*)`（notes.md §1）。
4. 治理文件補三句：（a）worktree 一律用 git 指令建立，Orca 只「顯示」；（b）清理只走 git；（c）V-M-D 推送、Close Campaign 結案後，用跨 session 訊息通知仍在跑的 worktree session。
5. **Spike（一次性，不入治理）**：只選**一個**具體工作流與**一個**工具（Orca orchestration 或 Claude agent teams，擇一），例如對這份計畫做兩個視角的唯讀審查。事先寫下成功條件與停止條件：一次執行後沒有明確收益（配額、品質或時間）即停止，不繼續疊加治理。記錄 token 用量與可用性到 notes.md。不同時測兩個工具，不開三個以上 agent。

**2b（正式平行開發；准入見 §3.1）**
6. Orca：安裝並釘版本；Repository settings 的「Auto-run commands on worktree create」填 `pnpm install --frozen-lockfile`（web）；每個 agent 的啟動 hooks 保持預設；**不使用** Orca 的 Delete。
7. **agent view 小試驗**（使用者 2026-10-23 決定排入；方案與成功、停止條件見 [spike-agent-view.md](./spike-agent-view.md)）：驗證從 git 建立的 worktree 派出的背景 session 是否維持本 repo 的 worktree 與 commit／push 規則。
8. 驗證：在 Orca 開的 worktree 內跑 `claude`，確認 `/hooks` 列出兩組 PreToolUse、`git push` 觸發 ask；`/list-agents` 看得到另一個 worktree 的 session。這些都是 NOT TESTED，通過前不得稱為相容。

### Phase 3 — 抽出可攜 harness（新 repo + Claude plugin + Codex install）
商業對齊：弱對齊（主要價值是開發成本與維護效率，不直接改善活動資料）。複雜度 high、已證明價值 low、預期價值 medium，因此**第一個交付刻意縮小**（N1）。

**3a 試點（第一個交付）**
1. 建 `ai-harness` repo，只放**一個 agent 與一個 skill**（例如 plan-critic 與其 skill）。
2. 第二個專案以本地 `claude --plugin-dir <path>` 載入；`claude plugin validate`。**TTR 保留現有 hooks 與 `.claude/agents`，不搬任何防線。**
3. 評估實際復用收益（第二專案是否真的用到、維護成本多少），記入 notes.md。收益不明確就停在這裡，不繼續。

**3b 擴大（3a 有明確收益後才做；D8 已裁決）**
4. 其餘通用 agent 與 skill、`.claude-plugin/marketplace.json`、Codex install 腳本、發布。
5. TTR 把通用 agent 改為 generated（Copilot 用）；`enabledPlugins` 與 `extraKnownMarketplaces` 讓新 clone 被提示安裝。
6. **延伸既有生成器，不另造 adapter 系統**（N4）：擴充 `agent_outputs()`、`expected_outputs()`、`check()`；把通用 guard 測試（現有 `scripts/claude/tests`）與 TTR 接線測試分開，後者包含 `scripts/tests/test_claude_settings.py`（含 `test_settings_exact_shape`），搬 hooks 時要一併改。
7. 是否把 hooks 搬進 plugin，是 3b 之後獨立的決定，取決於下列驗收。

**D8：版本釘選與缺口取捨（使用者 2026-10-23 裁決採用：lock 為來源版本紀錄、缺 plugin 只警告、3b 之前不搬 hooks；以下細節是該裁決的內容）**

- **`harness.lock` 的定位**：它是「來源版本紀錄」，不是完整的版本釘選。它記錄 harness repo URL、commit SHA、plugin 版本。完整釘選還要涵蓋下列產物，缺一不可：
  | 產物 | 驗收 |
  |---|---|
  | harness 來源 | 本機 checkout 的 `git status --porcelain` 為空，且 `HEAD` 等於 lock 的 SHA；有未提交修改即失敗 |
  | TTR 生成的 adapter | `sync --check` 以該 checkout 重生成後無差異 |
  | 已安裝的 Claude plugin | `claude plugin list` 的名稱與版本等於 lock 的 plugin 版本 |
  | 目前 session 實際載入的版本 | 更新後必須 `/reload-plugins` 或重啟 session；磁碟已更新不代表 session 已載入（官方文件） |
  | Codex 使用者層安裝結果 | 安裝腳本寫出的檔案雜湊等於 harness 內對應檔案 |
- **為何採 lock 而非 git submodule**：本 repo 同時有十多個 worktree，submodule 要每個 worktree 各自 init，且 `git clean`、`git stash` 對 submodule 的行為會讓既有的 worktree 治理更脆弱；lock 是純文字，可被測試直接驗證。
- **更新與回退責任**：harness 改動 → harness 測試通過並打 tag → TTR 開 campaign worktree 更新 lock、重生成、跑 `sync --check` 與 pytest → 經 V-M-D 與使用者核准後 push → 使用者在各機器重新安裝並 `/reload-plugins`。回退 = revert lock 的 commit、重新安裝舊版 plugin、重載 session。
- **CI**：必須有「依 lock 取得 harness」的步驟（clone 到 lock 的 SHA），再執行 `sync --check`。本機沒有 checkout 時明確失敗並提示取得方式；CI 的取得步驟是它的取得方式，不是略過。`sync --check` 與 pytest 接進 CI 本身是 parked 的後續項目（ai-portability-followups ①），Phase 3b 開工前必須先完成。
- **plugin 狀態與預期行為**（警告必須由 TTR 自己保留的 `.claude/settings.json` 與腳本發出，不能依賴缺失的 plugin）：
  | 狀態 | 預期 | 警告來源 |
  |---|---|---|
  | 未安裝 | 沒有 plugin 提供的 hooks；TTR 保留的 SessionStart 檢查輸出明確警告 | TTR 的 SessionStart 腳本 |
  | 已安裝但停用 | 同上 | 同上 |
  | 載入失敗 | 同上；`/plugin` Errors 分頁有記錄 | 同上 |
  | 版本與 lock 不符 | 警告並列出兩個版本 | 同上 |
  | 正常 | 無警告，hooks 只觸發一次 | 無 |
  - **取捨（已裁決選項一）**：缺少防線時，選項一是「只警告，session 繼續」；選項二是「阻擋會寫入的操作，直到 plugin 就緒」。已採選項一，因為 `permissions.ask` 的 push 規則留在 TTR 的 `.claude/settings.json`，不依賴 plugin。但要注意，這條規則只涵蓋直接的 push，不涵蓋包裝命令與破壞性操作，那些原本由 hooks 的 guard 擋下；選項一等於接受這段缺口。
  - 移除 TTR 本地 hooks 前，至少驗證：Bash guard、file guard、launcher 失敗處理（fail-closed）、同一事件只觸發一次。第二專案的實測不能只測 force push。
  - AGENTS.md 的「未涵蓋」段明寫「plugin 未安裝、停用、載入失敗或版本不符＝沒有 hooks 防線」。這是新增的依賴，本計畫不宣稱它與「從子目錄啟動」的現有風險同級。
  - `claude plugin eval` 可做回歸。

### Phase 4 — TTR 精簡（與 parked followups ④ 合併；**不依賴 Phase 3**）
量測、刪除重複說明與 `AGENTS.md` 精簡可以獨立完成，不必等 plugin 化。
1. ~~54 個 `sources/` skill 合併為 1 個~~ **已否決（D6，2026-10-23）**：專案 skill 常駐估計約 2.6k tokens（來源 skill 約 2.1k，占 1M 視窗約 0.2%），低於 3k 門檻。這是 bytes 換算的估算，不是逐 skill 實測。除非來源 skill 數量或 description 長度明顯增加，否則不再討論。
2. **`AGENTS.md` 瘦身**：Memory files 的 8.7k tokens 是專案端最大的常駐項，但尚未逐檔拆解，歸因待重量。先逐檔量測，再決定移出什麼。可移到 `docs/` 的是 hooks 規則表與殘餘風險清單；**Codex 與 Copilot 仍需直接遵循的行為規則不要全部改成連結**。動手前確認它們不依賴被移走段落的字面內容。
3. `architect.agent.md` 1,197 行瘦身：TTR 專屬段落移到 `.github/instructions/`，通用規劃原則留在原檔（Phase 3 後再決定是否進 harness）。
4. `.github/prompts` → skills（Claude 的 `.claude/commands` 已是舊格式，官方建議新用 `skills/`）。
5. X1–X4 裁決與 reviewer 去留（parked ④）一併處理。
6. 驗證：`sync --check`、pytest、`/context` 前後對照、一次完整 scraper dry-run（確認 scraper-expert 仍能找到來源規則）。

### Phase 5 — 本機模型（可選，最後）
1. `ollama pull` Qwen3-Coder-30B-A3B（或 gpt-oss-20b）；刪舊 `qwen2:7b`、`llama3.2`。
2. Codex `cheap` profile、Copilot BYOK → Ollama。用途白名單寫進 `~/.codex/AGENTS.md` 與 `~/.claude/CLAUDE.md`：摘要、翻譯、commit 訊息、單檔重構、測試資料生成；禁止：DB 寫入、push、部署、任何 hooks 守的動作。
3. 用 `monthly-experiment` 跑一個月 A/B，看配額節省是否值得維護成本；不值得就撤。

### 3.1 Go/No-Go 門檻

工具搬遷（Orca、plugin、harness repo）本身**不是**已證明的配額效益。配額效益只能來自 Phase 1 的降級，而且必須以量到的數據為準；其餘 phase 的價值是治理與可攜性，不要與配額混為一談。

**配額記錄方式（最簡）**：每週一次，由使用者在 notes.md 追加一列：日期、Claude 方案用量百分比與重置時間（取自 `/usage` 或 statusline 當下顯示）、Codex 用量、該週完成的任務數、返工次數（被退回或重做的任務）。Phase 1 之前沒有基準，`~/.claude/cc-statusline/` 的檔案只含 session 計時，未確認含配額歷史，所以**第一週只建立觀測基準，不能判定「沒有退步」**；至少兩週後才能做週與週的比較，而且仍只是指標，不是因果證明。

| 進入 | 必要條件（全部成立才 go） |
|---|---|
| Phase 2a（housekeeping 與一個 spike） | (a) Phase 1 commit 存在（`361d17c1`，已成立）。(b) D4' 已裁決（2026-10-23，已成立）。 |
| Phase 2b（正式平行開發，即日常同時跑多個 agent session） | 2a 的條件，加上：(c) Phase 1 的 NOT TESTED 項目已驗證，或使用者明確接受留作未驗證（**已成立，2026-10-23，見 notes.md §8**）。(d) 第一週配額基準已記錄，且沒有因平行 session 在重置前耗盡配額；若耗盡即 no-go，降低平行度後重評。(e) 兩個 spike 都已依停止條件結案並記入 notes.md：agent teams（已完成）與 agent view 小試驗（[spike-agent-view.md](./spike-agent-view.md)，待執行）。 |
| Phase 3a（試點） | Phase 2b 的條件，加上：至少兩週配額紀錄可比較。 |
| Phase 3b（擴大與防線搬遷） | 3a 有明確復用收益；D8 已裁決；ai-portability-followups ① 的 CI 接線完成。 |
| Phase 4 | 不依賴 Phase 3。條件：先逐檔量測 `/context` 的 Memory files。 |
| Phase 5 | 本機模型僅限白名單用途；一個月 A/B 結果決定去留。 |

任一必要條件未成立即 no-go，回報使用者，不自行放寬門檻。

## 4. 風險與限制

標示：**文件描述**＝來自官方或第三方文件，未在本機驗證；**靜態核對**＝讀程式碼確認；**本機實測**＝在本機執行並有紀錄；**NOT TESTED**＝尚未驗證。未標示者視為文件描述。

- **配額是真正的瓶頸。** Fable + xhigh 是目前最貴的組合；Orca 或 agent teams 一次 fan-out 5 個 agent 會更快撞到 Pro 限制。平行度上升必須伴隨 Phase 1 的降級，否則適得其反。
- **Orca 迭代極快**（文件描述，來自第三方評測文章：30 天 18 個 release、Electron 常駐 400–800 MB；未在本機量測）；請釘版本、把版本記進 notes.md。
- **Claude `--worktree` 與 repo 命名規範衝突**（文件描述：固定放 `.claude/worktrees/`、分支 `worktree-<name>`）；只給 subagent 隔離用。
- **Codex custom agent 不能換 provider**（文件描述）；本機模型只能 session 級切換。
- **Copilot BYOK 目前 GA 在 Business／Enterprise**；若 Enterprise 被撤銷，個人方案能否 BYOK 需到時實測。
- **Plugin agent 的 frontmatter 限制**（hooks／mcpServers／permissionMode 被忽略）；hooks 改走 plugin 的 `hooks/hooks.json`。
- **Secrets 副本**（rev.2 新增）：複製 `.env` 進多個 worktree 會增加需輪替與清理的副本；hooks 只保護 Claude Code。因此不複製（§3 Phase 2 第 2 點）。dry-run 不需憑證的結論只限 TCC（本機實測），其他來源 NOT TESTED（靜態核對有反例）。
- **沒有配額基準**（rev.2 新增）：Phase 1 之前沒有留下配額紀錄，後續比較只是指標。
- **跨 session 訊息不是指令通道**：收方不會因訊息改設定或核准任何事，這是設計上的好事，但也表示「讓 agent 彼此了解 context」仍以檔案為主。

## 5. 裁決狀態

| # | 問題 | 狀態（2026-10-23） |
|---|---|---|
| D1 | spec slug 與 campaign worktree：`ai-harness` → `ttr-ai-harness-worktree`／`feat/ai-harness` | 已裁決（2026-10-20，依建議） |
| D2 | 權威位置反轉：通用 agent 權威檔搬到 harness repo，TTR 的 `.github/agents` 變 generated | 已裁決，但到 Phase 3 才做 |
| D3 | 主對話預設模型：`opusplan`，規劃時手動 `/model fable` | 已裁決；`~/.claude/settings.json` 已設 |
| D4 | ~~`.worktreeinclude` 包含 `scraper/.env`、`web/.env.local`~~ | **撤回**。rev.1 的建議不安全 |
| D4' | worktree 一律不帶正式 secrets；agent worktree 的 dry-run 驗證只限已確認不需憑證的來源（目前僅 TCC，本機實測），其他來源用 fixture、mock 或使用者自行驗證；web 驗證用佔位值或 `web/.env.example`（NOT TESTED）；需要 secrets 的操作由使用者在自己的環境執行。**已裁決採用（2026-10-23）** | 已裁決 |
| D5 | Orca 只顯示與啟動，worktree 一律用 git 指令建立 | 已裁決 |
| D6 | 合併 54 個來源 skill | 已裁決（先量測）；量測後結論：不合併（估算值，非逐 skill 實測） |
| D7 | `tokyo-taiwan-radar-agents-repo` worktree 退役 | 已達成：該 worktree 已不存在 |
| D8 | Phase 3 的版本釘選與缺口取捨：`harness.lock` 是來源版本紀錄，完整釘選需涵蓋 checkout、adapter、plugin 安裝與載入版本、Codex 安裝結果（§3 Phase 3）；plugin 缺失時選「只警告」或「阻擋寫入操作」。**已裁決採用（2026-10-23）**：採 lock 加「只警告」，3b 之前不搬 hooks | 已裁決（只在 Phase 3b 需要；3a 試點不需要） |

## 6. 下一步

1. D4' 已裁決（Phase 2a 的條件 b 已成立）。
2. Phase 2a 可以開始（housekeeping 與一個受限 spike），建議模型：Sonnet、medium effort。
3. 開始每週配額記錄（§3.1）；第一週結束才有觀測基準。
4. Phase 1 的四項 NOT TESTED 已驗證（notes.md §8），Phase 2b 的條件 (c) 成立；仍須滿足 (d) 配額基準與 (e) spike 結案。
5. Phase 2b 與 Phase 3a 依 §3.1 的條件逐一放行；D8 已裁決，只在 3b 生效。
6. Phase 4 的量測與 `AGENTS.md` 精簡可獨立進行，不必等 Phase 3。

## 7. 來源

- Orca：https://www.onorca.dev/ 、https://www.onorca.dev/docs/model/worktrees 、https://www.onorca.dev/docs/settings 、https://www.onorca.dev/docs/cli/orchestration 、https://www.onorca.dev/docs/agents/hooks-memory 、https://www.onorca.dev/docs/agents/claude-code 、https://github.com/stablyai/orca 、https://blog.bokvi.com/blog/orca-ade-parallel-coding-agents/
- Claude Code：https://code.claude.com/docs/en/sub-agents 、/model-config 、/worktrees 、/agent-teams 、/cross-session-messaging 、/plugins 、/plugins/create 、/llm-gateway 、/memory 、/settings
- Codex：https://learn.chatgpt.com/docs/config-file/config-basic 、https://learn.chatgpt.com/docs/agent-configuration/subagents.md 、https://learn.chatgpt.com/docs/hooks.md
- Copilot BYOK：https://github.blog/changelog/2026-04-22-bring-your-own-language-model-key-in-vs-code-now-available/
- Router 生態（僅供對照，不建議採用）：https://www.morphllm.com/claude-code-router 、https://dev.to/opper/claude-code-with-any-model-three-ways-to-route-it-incl-the-2-minute-one-2md2
