# Notes — ai-harness

執行證據與分類帳。只往後追加；既有段落不改寫。每段標明日期、執行者與工具版本。未實測的項目一律寫 NOT TESTED。

## 1. Phase 0 session（2026-10-20）

| 項目 | 值 |
|---|---|
| 執行者 | Claude Code 2.1.300；規劃由 Fable 5.1，spec 骨架由 Sonnet 5.5 建立 |
| 起點 | origin/main `90dab624`（docs(weekly_review): 2026-10-18 weekly review），fetch 後 main 與 origin/main 同步 |
| Worktree | `/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-harness-worktree`，branch `feat/ai-harness`，追蹤 origin/main |
| `.git/info/exclude` | 已 reconcile，含 `ttr-ai-harness-worktree/` |
| plan.md SHA-256 | `5f492d901f2846a6865aee0de5ebc1d73bed9889e88ccc1c00edc0e77ec585bf` |

- 主工作樹 `git status --short` 無輸出，無他人 WIP。
- `agents-repo` worktree（`…/Tokyo Taiwan Radar.worktrees/tokyo-taiwan-radar-agents-repo`，HEAD `3b04a6d3`）工作樹乾淨；尚未退役，等 Close Campaign agent。
- 治理文件中的 exclude reconcile 片段在 macOS 預設 bash 3.2 會語法錯誤（`$(… case "$x" in "$root"/*) … esac …)`），pattern 需寫成 `("$root"/*)`。本 session 用修正版執行並驗證 converged。後續應修正 `git.instructions.md` 的片段。
- hooks guard 拒絕了一次把 worktree 建立、reconcile 與驗證串成單一命令的呼叫（`unsupported-syntax`），拆成簡單命令後通過。

## 2. Phase 1 session（2026-10-23）

| 項目 | 值 |
|---|---|
| 執行者 | Claude Code 2.1.300，Sonnet 5.5（建議模型：Sonnet、medium effort） |
| 起點 | `a03ce9bf`（spec 骨架） |

實作：
- `scripts/sync_ai_adapters.py`：新增 `TIERS`（plan→opus/high、build→sonnet/medium、grunt→haiku/low）、`tier_problems()`、Codex 輸出 `.codex/agents/<kebab>.toml`（`model_reasoning_effort` 與 `developer_instructions`，不含 `model`）。`generated_files()` 與覆寫保護同時辨識 HTML 與 TOML 標記。
- 15 個來源 agent 都加了 `tier`（包含 architect、reviewer、researcher、scraper-expert 四個未投影權限的角色）。
- AGENTS.md「模型政策」改寫：tier 表、投影規則、執行前模型評估規則。

偏離計畫（原 §3 Phase 1 第 1 點）：計畫要把 `pinned_models()` 放寬為只攔完整 ID。實作時保留原行為，來源檔連別名都禁。理由：Copilot 讀同一份 `.agent.md`，會把 `model: opus` 當模型名稱解析，正是 2026-09-29 事故的同型風險。別名只出現在生成的 Claude wrapper。

驗證：

| 檢查 | 結果 |
|---|---|
| `python3 scripts/sync_ai_adapters.py --check` | PASS（exit 0） |
| `python3 -m pytest scripts/tests scripts/claude/tests -q` | PASS，492 passed |
| 15 個 `.codex/agents/*.toml` 可被 `tomllib` 解析並含必要欄位 | PASS |
| `claude -p --agent tester`（從 worktree 根目錄） | PASS，`modelUsage` 只有 `claude-haiku-5-5` |
| `codex doctor` 載入修改後的 `~/.codex/config.toml` | PASS（config parse ok） |
| Codex 是否實際讀取 `.codex/agents/*.toml` 並套用 effort | NOT TESTED（`codex doctor` 不列 agent；需互動 session 觀察） |
| `claude --agent plan-critic` 的 opus／high 實測 | NOT TESTED（只實測了 tester／Haiku） |
| `opusplan` 在 plan mode 與執行段的實際切換 | NOT TESTED（需互動 session） |
| `codex -p plan` 載入 `~/.codex/plan.config.toml` | NOT TESTED（`codex -p plan doctor` 不支援 profile，只有 `codex`、`exec` 等 runtime 命令可用） |

使用者層變更（備份在 session scratchpad；不入 repo）：
- `~/.claude/settings.json`：`model` 改 `opusplan`（使用者先前已把 `model` 與 opus effort 調過，原值 `opus`／`high`）；`claude-sonnet-5-5` effort 由 `high` 改 `medium`；新增 `env.CLAUDE_CODE_SUBAGENT_MODEL=haiku`（沒有 `model` 欄位的 subagent，如 general-purpose，會用 Haiku；若品質不足改 `sonnet`）。
- `~/.codex/plan.config.toml`（新）：`gpt-6.1-sol`、effort high，用 `codex -p plan` 啟動。
- `~/.codex/config.toml`：新增 `[agents] default_subagent_reasoning_effort = "low"`。
- `cheap` profile 未建：Ollama 只有 14 到 16 個月前的 7B 與 3B 模型，等 Phase 5。

grunt 的取捨：tester 與 lianbu-spokesperson 在 `grunt`（Haiku）。tester 要判讀爬蟲輸出，lianbu 要寫日文貼文，兩者若品質不足，調 tier 是治理決定，需使用者核准。
