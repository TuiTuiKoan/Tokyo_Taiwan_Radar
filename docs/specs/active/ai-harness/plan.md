# AI Harness v2 計畫 rev.2 — Orca 平行開發、模型分級、跨專案可攜 harness

rev.1：2026-10-15，Architect（Claude Fable 5.1，Claude Code 2.1.300）。rev.2：2026-10-23，依 Codex Plan Critic 的六項修訂意見更新（Claude Opus 5.5 執行）。

狀態（2026-10-23）：D1、D2、D3、D5、D6、D7 已定案；**D4 撤回，需重新裁決（D4'）**；**D8（Phase 3 的版本釘選機制）待裁決**。Phase 0 與 Phase 1 的程式碼已完成，Phase 1 的使用端驗證與配額量測未完成。進度真值是 [tasks.md](./tasks.md)，執行證據是 [notes.md](./notes.md)；本文與兩者衝突時以兩者為準。

rev.1 原檔保留在 `~/.ai-notes/ttr/ai-harness-plan-rev1.md`（SHA-256 `5f492d901f2846a6865aee0de5ebc1d73bed9889e88ccc1c00edc0e77ec585bf`）。rev.2 完整替代 rev.1。

## rev.2 變更摘要

| # | Codex 意見 | rev.2 處理 | 位置 |
|---|---|---|---|
| 1 | Secrets 與 D4：`.worktreeinclude` 不得複製 `scraper/.env`、`web/.env.local` | 撤回 D4 的建議；改為「worktree 不帶正式 secrets」。以實測證明 scraper dry-run 不需要 `.env`；web 驗證改用不含 secrets 的方式。D4 標為需重新裁決。移除「hooks 禁止 agent 讀寫 `.env` 所以可複製」的論述 | §3 Phase 2、§4、§5 |
| 2 | 進度漂移 | D1–D7 已於 2026-10-20 裁決；Phase 0、1 狀態、仍未完成項目已同步；刪除「回覆 D1–D7、再執行 Phase 0→1」的下一步 | 全文、§6 |
| 3 | 模型投影 | 移除「放寬 `pinned_models()`」；來源 `.agent.md` 只宣告 `tier`，別名只寫入生成的 Claude wrapper；Codex effort 等 NOT TESTED 項目保留為待驗證 | §1.3、§3 Phase 1 |
| 4 | Phase 4 | 合併 54 個來源 skill 標為已否決；改為 `AGENTS.md` 瘦身 | §3 Phase 4 |
| 5 | Phase 3 前置決策 | 提出 pinned commit SHA（`harness.lock`）方案、更新與同步的責任流程、plugin 未安裝缺口的驗收條件；列為 D8，待使用者裁決 | §3 Phase 3、§5 |
| 6 | 繼續工作的門槛 | 新增 Go/No-Go 門檻；一週配額曲線與使用端驗證是 Phase 2、3 的依據；明確聲明工具搬遷本身不是已證明的配額效益 | §3.1 |


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
| 專案 harness 體積 | 13 個 agent 檔 3,138 行（architect 一檔 1,197 行）；68 個 SKILL.md 共 17,537 行、history.md 20,309 行；其中 54 個是 `sources/` 爬蟲來源 skill |
| 防線 | `.claude/settings.json` 的 `permissions.ask`（push）＋ PreToolUse hooks（`scripts/claude/`）；只保護從 repo／worktree 根啟動的 Claude Code；Copilot、Codex 無防線 |

## 1. 三個問題的直接答案

### 1.1 不需要先準備本機硬體與開源模型基礎設施

- 「省成本」在你的情況是**省訂閱配額**，不是省 API 美元：Claude 是 Pro 訂閱，Codex 走 ChatGPT 登入。
- 任何 gateway／router（claude-code-router、LiteLLM、OpenRouter、Opper）都要用 API key 計費。Claude Code 文件明言：gateway credential 生效時「訂閱登入不送出、訂閱額度不適用」，而且 Anthropic 不支援經 gateway 把 Claude Code 導到非 Claude 模型。對 Pro 使用者這條路是**加錢**而不是省錢，且會破壞 hooks 以外的功能假設（Explore subagent 的特殊模型規則、prompt cache、Remote Control 等）。
- 真正的省配額手段都在訂閱內、都不需要新硬體：主對話 `opusplan` 或降 effort、subagent 走 `haiku`／`sonnet`、Codex 作第二個配額池、本機模型只接「零風險小任務」。
- 本機模型是**可選的第五階段**，M1 Max 32 GB 已足夠跑 MoE 類 coder 模型（例：Qwen3-Coder-30B-A3B，Q4 約 18–19 GB；gpt-oss-20b 約 13 GB），不必買機器。它們的角色限定為摘要、翻譯、commit 訊息、簡單重構，**不**用於任何要過 hooks／權限閘門的 production 動作（AGENTS.md 模型政策已有此條）。

### 1.2 Orca ADE 可行，而且與現有 worktree 治理相容，但要守三條邊界

Orca（stablyai/orca，MIT，桌面 Electron app，macOS／Windows／Linux）是「一個 app 裡平行跑多個 CLI agent，每個 agent 一個 git worktree」。它**不是** VS Code 擴充；它內嵌 VS Code 的編輯器元件。你的 VS Code 工作流照舊，Orca 只負責「開多個 worktree、各跑一個 Claude Code／Codex、看 diff、合併」。

相容性實測依據（Orca 文件）：
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
- `~/.claude/settings.json`：`model: "opusplan"`（日常）；需要 Fable 時 `/model fable` 只在規劃 session；`modelSettings` 的 `xhigh` 降到 `high`（規劃）／`medium`（執行）；`env.CLAUDE_CODE_SUBAGENT_MODEL: "haiku"` 兜住沒有 `tier` 的 agent（Explore、general-purpose、X1–X4 四個未投影角色）。
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

## 3. 分階段計畫（各自一個 campaign worktree、各自 atomic commit）

### Phase 0 — 盤點、量測、裁決（狀態：僅剩使用者決定是否處理 D4'）
- [x] 建 spec `docs/specs/active/ai-harness/`、worktree `ttr-ai-harness-worktree`（commit `a03ce9bf`）。
- [x] 使用者裁決 D1–D7（2026-10-20）；D4 於 rev.2 撤回。
- [x] `/context` 實測：整體 41.6k tokens（4%）；專案 skill 估計約 2.6k，低於 3k 門檻（notes.md §3）。
- [x] D7：agents-repo worktree 已不存在（notes.md §4）。
- [x] Plan Critic（Codex）已審；意見已在 rev.2 處理。Codex 回傳的是修訂提示，批評全文未提供，未另存。
- [ ] D4'：worktree 不帶 secrets 的設計需使用者確認（§5）。

### Phase 1 — 模型分級（狀態：程式碼完成並 commit `361d17c1`；使用端驗證與配額量測未完成）
1. [x] `.github/agents/*.agent.md` 加 `tier`；`sync_ai_adapters.py` 投影 Claude `model`／`effort` 與 `.codex/agents/<kebab>.toml`；`--check` 要求每個 agent 有已知 `tier`。**`pinned_models()` 不放寬**（§1.3）。
2. [x] AGENTS.md「模型政策」改寫：tier 表、投影規則、執行前模型評估。
3. [x] 使用者層：`~/.claude/settings.json`（`opusplan`、sonnet effort medium、`CLAUDE_CODE_SUBAGENT_MODEL=haiku`）、`~/.codex/plan.config.toml`、`[agents] default_subagent_reasoning_effort`。`cheap` profile 留到 Phase 5。
4. 驗證：
   - [x] `sync --check` exit 0；pytest 492 passed；`claude -p --agent tester` 的 `modelUsage` 只有 Haiku。
   - **NOT TESTED**：Codex 是否讀取 `.codex/agents/*.toml` 並套用 effort；`codex -p plan` 載入 profile；`claude --agent plan-critic` 的 Opus 實測；`opusplan` 在 plan mode 與執行段的切換。這四項需互動 session，保留為待驗證，不得寫成通過。
5. [ ] 量測：記錄 Phase 1 之後一週的 cc-statusline 配額曲線。**注意：Phase 1 之前沒有留下配額基準**（只有 `/context` 的 token 數，那不是配額），所以只能做「之後各週」的相對比較，結論僅供參考（§3.1）。

### Phase 2 — 平行開發（Orca + Claude 原生，不改治理規則）
1. `.gitignore` 加 `.claude/worktrees/`（防止誤用 `--worktree` 污染主工作樹 untracked 清單）。
2. **不複製 secrets**（取代 rev.1 的 D4 建議；D4' 待確認）：
   - 不建立會複製 `scraper/.env` 或 `web/.env.local` 的 `.worktreeinclude`；若需要該檔，只列非 secrets 的 gitignored 設定，且逐項審過。
   - 依據：secrets 一旦被複製進多個 worktree，就多了多份需要輪替與清理的副本，且 hooks 只擋 Claude Code 的讀寫、不保護 Codex 與 Copilot（AGENTS.md「Hooks 與 permissions」），所以「hooks 禁止 agent 讀寫 `.env`」不能當成複製 secrets 的安全依據。
   - 實測：2026-10-23 在沒有 `.env` 的 `ttr-ai-harness-worktree` 執行 `python main.py --dry-run --source taiwan_cultural_center`，exit 0 並輸出事件 JSON（scraper 的 `--dry-run` 本來就不呼叫 DB 與 AI）。所以爬蟲 dry-run 不需要 secrets。
   - web 驗證（NOT TESTED）：程式讀取 `NEXT_PUBLIC_SUPABASE_URL`、`NEXT_PUBLIC_SUPABASE_ANON_KEY`、`NEXT_PUBLIC_SITE_URL` 等；repo 沒有 `web/.env.example`。方案是 Phase 2 驗證 build 能否以命令列傳入佔位值通過；若不行，補 `web/.env.example`（只含佔位值）需另案並讀 `web.instructions.md`。
   - 需要正式 secrets 的操作（非 dry-run 的爬蟲、`annotator.py`、DB 寫入、連線 production 的 web）不在 agent 的 worktree 內做；由使用者在自己的環境執行，或另案設計。
3. Orca：安裝；Repository settings 的「Auto-run commands on worktree create」填 `pnpm install --frozen-lockfile`（web）與 `.git/info/exclude` reconcile 片段（只對 repo root 內的 worktree）；每個 agent 的啟動 hooks 保持預設；**關閉／不使用** Orca 的 Delete。
4. 治理文件補三句：（a）worktree 一律用 git 指令建立，Orca 只「顯示」；（b）清理只走 git；（c）V-M-D 推送、Close Campaign 結案後，用跨 session 訊息通知仍在跑的 worktree session（`git.instructions.md`、`validate-merge-deploy.agent.md`、`campaign-closer.agent.md`）。
5. 修正 `git.instructions.md` 的 exclude reconcile 片段：macOS 預設 bash 3.2 對 `$(… case … esac …)` 內的 `case` pattern 語法錯誤，pattern 需寫成 `("$root"/*)`（notes.md §1）。
6. Spike（不入治理）：Orca orchestration 與 Claude agent teams 各做一次 3-agent 的唯讀研究任務（例如 plan-critic 三視角），記錄 token 用量與可用性到 notes.md；結果決定是否進 Phase 3 之後的治理。
7. 驗證：在 Orca 開的 worktree 內跑 `claude`，確認 `/hooks` 列出兩組 PreToolUse、`git push` 觸發 ask；`/list-agents` 看得到另一個 worktree 的 session。

### Phase 3 — 抽出可攜 harness（新 repo + Claude plugin + Codex install）
1. 建 `ai-harness` repo：`plugins/core/{.claude-plugin/plugin.json, agents/, skills/, hooks/hooks.json, scripts/}`、`.claude-plugin/marketplace.json`、`codex/{agents/*.toml, hooks.json}`、`install.sh`、tests（從 `scripts/claude/tests` 搬）。
2. `claude plugin validate`、`claude --plugin-dir ./plugins/core` 測試；`claude plugin marketplace add <path>`；user scope 安裝。
3. TTR：移除 `.claude/settings.json` 的重複 hooks（保留 `permissions.ask`）、`.claude/settings.json` 加 `enabledPlugins` 讓每個 clone 都提示安裝；`.claude/agents` 只留專案專屬 wrapper；`.github/agents` 的通用 agent 改為 generated（Copilot 用）；`sync --check` 比對 harness pinned SHA。
4. 第二個專案試裝（任一非 TTR repo），確認 agents、hooks、skills 都在，且 hooks 的 fail-closed 行為一致。
5. 風險：plugin 未安裝的機器沒有防線（與現在「從子目錄啟動就沒防線」同級的殘餘風險）；`claude plugin eval` 可做回歸。

**Phase 3 前置決策（D8，待使用者裁決；以下為建議，不是已核准）**

- **版本釘選：採 pinned commit SHA，不採 git submodule。** TTR 根目錄放 `harness.lock`（harness repo URL、commit SHA、plugin 版本）。理由：本 repo 同時有十多個 worktree，submodule 要每個 worktree 各自 init，且 `git clean`、`git stash` 對 submodule 的行為會讓既有的 worktree 治理更脆弱；lock 檔是純文字，可被 `sync --check` 與測試直接驗證。
- **責任流程**：
  1. harness repo 改動，並在 harness 自己的測試通過後打 tag。
  2. TTR 開 campaign worktree，更新 `harness.lock` 的 SHA，執行 sync，再跑 `sync --check` 與 pytest；全部通過才 commit，並經 V-M-D 與使用者核准後 push。
  3. `sync --check` 比對 `harness.lock` 與本機 harness checkout 的 `HEAD`；不一致即失敗。沒有 harness checkout 時，`--check` 必須明確失敗，不得略過。
  4. 把 `sync --check` 與 pytest 接進 CI 是 parked 的後續項目（ai-portability-followups ①），Phase 3 開工前應先完成，否則漂移無人攔截。
- **plugin 未安裝缺口的驗收條件**（全部通過才算 Phase 3 完成）：
  1. `permissions.ask` 的 push 規則留在 TTR 的 `.claude/settings.json`，不依賴 plugin。
  2. TTR 的 `.claude/settings.json` 宣告 `extraKnownMarketplaces` 與 `enabledPlugins`，讓新 clone 啟動時被提示安裝。
  3. 在沒有安裝 plugin 的乾淨環境啟動 `claude`，實測並記錄：哪些防線消失（預期：PreToolUse hooks）、是否有可見警告。若沒有警告，加一個只在 plugin 缺失時輸出警告的 SessionStart 檢查，並實測。
  4. AGENTS.md 的「未涵蓋」段明寫「plugin 未安裝＝沒有 hooks 防線」。
  5. hooks 的 fail-closed 測試（現有 `scripts/claude/tests`）在 harness repo 內通過，且第二個專案實測同樣阻擋 `git push --force`。
  6. 原 `.claude/settings.json` 的重複 hooks 已移除，同一事件不會跑兩次。

### Phase 4 — TTR 精簡（與 parked followups ④ 合併）
1. ~~54 個 `sources/` skill 合併為 1 個~~ **已否決（D6，2026-10-23）**：`/context` 與估算顯示專案 skill 常駐約 2.6k tokens（來源 skill 約 2.1k，占 1M 視窗約 0.2%），低於 3k 門檻，不值得合併。除非日後來源 skill 數量或 description 長度明顯增加，否則不再討論。
1b. **`AGENTS.md` 瘦身**（取代上一項）：Memory files 的 8.7k tokens 是專案端最大的常駐項，`AGENTS.md` 17KB，其中 hooks 規則表與殘餘風險清單占大半。把這兩段移到 `docs/`，`AGENTS.md` 只留 5 點摘要、路徑規則表、角色路由、模型政策與一行連結。動手前先確認 Codex 與 Copilot 不依賴那些段落的字面內容，並重量 `/context`。
2. `architect.agent.md` 1,197 行瘦身：TTR 專屬段落（資料模型、scraper 契約）移到 `.github/instructions/`，通用規劃原則進 harness。
3. `.github/prompts` → skills（Claude 的 `.claude/commands` 已是舊格式，官方建議新用 `skills/`）。
4. X1–X4 裁決與 reviewer 去留（parked ④）一併處理。
5. 驗證：`sync --check`、pytest、`/context` 前後對照、一次完整 scraper dry-run（確認 scraper-expert 仍能找到來源規則）。

### Phase 5 — 本機模型（可選，最後）
1. `ollama pull` Qwen3-Coder-30B-A3B（或 gpt-oss-20b）；刪舊 `qwen2:7b`、`llama3.2`。
2. Codex `cheap` profile、Copilot BYOK → Ollama。用途白名單寫進 `~/.codex/AGENTS.md` 與 `~/.claude/CLAUDE.md`：摘要、翻譯、commit 訊息、單檔重構、測試資料生成；禁止：DB 寫入、push、部署、任何 hooks 守的動作。
3. 用 `monthly-experiment` 跑一個月 A/B，看配額節省是否值得維護成本；不值得就撤。

### 3.1 Go/No-Go 門檻

工具搬遷（Orca、plugin、harness repo）本身**不是**已證明的配額效益。配額效益只能來自 Phase 1 的降級，而且必須以量到的數據為準；其餘 phase 的價值是治理與可攜性，不要與配額混為一談。

| 進入 | 必要條件（全部成立才 go） |
|---|---|
| Phase 2 | (a) Phase 1 commit 存在（`361d17c1`，已成立）。(b) Phase 1 的四項 NOT TESTED 已驗證，或使用者明確接受留作未驗證。(c) D4' 已由使用者裁決。 |
| Phase 3 | (a) Phase 1 之後至少一週的 cc-statusline 配額紀錄（最早 2026-10-30），與之前沒有退步，或使用者明確接受。因為 Phase 1 前沒有配額基準，此比較只能是指標，不是證明。(b) D8 已裁決。(c) ai-portability-followups ① 的 CI 接線已完成。(d) Phase 2 的 spike 結果已記入 notes.md。 |
| Phase 4 | Phase 3 完成；`AGENTS.md` 瘦身前先重量 `/context`。 |
| Phase 5 | 本機模型僅限白名單用途；一個月 A/B 結果決定去留。 |

任一必要條件未成立即 no-go，回報使用者，不自行放寬門檻。

## 4. 風險與限制（已查證）

- **配額是真正的瓶頸。** Fable + xhigh 是目前最貴的組合；Orca 或 agent teams 一次 fan-out 5 個 agent 會更快撞到 Pro 限制。平行度上升必須伴隨 Phase 1 的降級，否則適得其反。
- **Orca 迭代極快**（30 天 18 個 release、Electron 常駐 400–800 MB）；請釘版本、把版本記進 notes.md。
- **Claude `--worktree` 與 repo 命名規範衝突**；只給 subagent 隔離用。
- **Codex custom agent 不能換 provider**；本機模型只能 session 級切換。
- **Copilot BYOK 目前 GA 在 Business／Enterprise**；若 Enterprise 被撤銷，個人方案能否 BYOK 需到時實測。
- **Plugin agent 的 frontmatter 限制**（hooks／mcpServers／permissionMode 被忽略）；hooks 改走 plugin 的 `hooks/hooks.json`。
- **Secrets 副本**（rev.2 新增）：複製 `.env` 進多個 worktree 會增加需輪替與清理的副本；hooks 只保護 Claude Code。因此不複製（§3 Phase 2 第 2 點）。
- **沒有配額基準**（rev.2 新增）：Phase 1 之前沒有留下配額紀錄，後續比較只是指標。
- **跨 session 訊息不是指令通道**：收方不會因訊息改設定或核准任何事，這是設計上的好事，但也表示「讓 agent 彼此了解 context」仍以檔案為主。

## 5. 裁決狀態

| # | 問題 | 狀態（2026-10-23） |
|---|---|---|
| D1 | spec slug 與 campaign worktree：`ai-harness` → `ttr-ai-harness-worktree`／`feat/ai-harness` | 已裁決（2026-10-20，依建議） |
| D2 | 權威位置反轉：通用 agent 權威檔搬到 harness repo，TTR 的 `.github/agents` 變 generated | 已裁決，但到 Phase 3 才做 |
| D3 | 主對話預設模型：`opusplan`，規劃時手動 `/model fable` | 已裁決；`~/.claude/settings.json` 已設 |
| D4 | ~~`.worktreeinclude` 包含 `scraper/.env`、`web/.env.local`~~ | **撤回**。rev.1 的建議不安全 |
| D4' | worktree 一律不帶正式 secrets；爬蟲 dry-run 免 secrets（已實測）；web 驗證用佔位值或 `web/.env.example`（待驗證）；需要 secrets 的操作由使用者在自己的環境執行。建議：採用 | **待使用者裁決** |
| D5 | Orca 只顯示與啟動，worktree 一律用 git 指令建立 | 已裁決 |
| D6 | 合併 54 個來源 skill | 已裁決（先量測）；量測後結論：不合併 |
| D7 | `tokyo-taiwan-radar-agents-repo` worktree 退役 | 已達成：該 worktree 已不存在 |
| D8 | Phase 3 版本釘選：pinned commit SHA（`harness.lock`）而非 git submodule，含責任流程與驗收條件（§3 Phase 3）。建議：採用 | **待使用者裁決** |

## 6. 下一步

1. 使用者裁決 D4'（建議採用）。Phase 2 開工前必須完成。
2. 在互動 session 驗證 Phase 1 的四項 NOT TESTED，或明確接受留作未驗證（Phase 2 go 條件 b）。
3. 開始記錄 Phase 1 之後的每週配額（Phase 3 go 條件 a，最早 2026-10-30 可評估）。
4. D4' 與上兩項就緒後，Engineer 在 `ttr-ai-harness-worktree` 開始 Phase 2。建議模型：Sonnet、medium effort。
5. D8 與 Phase 3 的其他條件，在 Phase 2 結束後再處理。

## 7. 來源

- Orca：https://www.onorca.dev/ 、https://www.onorca.dev/docs/model/worktrees 、https://www.onorca.dev/docs/settings 、https://www.onorca.dev/docs/cli/orchestration 、https://www.onorca.dev/docs/agents/hooks-memory 、https://www.onorca.dev/docs/agents/claude-code 、https://github.com/stablyai/orca 、https://blog.bokvi.com/blog/orca-ade-parallel-coding-agents/
- Claude Code：https://code.claude.com/docs/en/sub-agents 、/model-config 、/worktrees 、/agent-teams 、/cross-session-messaging 、/plugins 、/plugins/create 、/llm-gateway 、/memory 、/settings
- Codex：https://learn.chatgpt.com/docs/config-file/config-basic 、https://learn.chatgpt.com/docs/agent-configuration/subagents.md 、https://learn.chatgpt.com/docs/hooks.md
- Copilot BYOK：https://github.blog/changelog/2026-04-22-bring-your-own-language-model-key-in-vs-code-now-available/
- Router 生態（僅供對照，不建議採用）：https://www.morphllm.com/claude-code-router 、https://dev.to/opper/claude-code-with-any-model-three-ways-to-route-it-incl-the-2-minute-one-2md2
