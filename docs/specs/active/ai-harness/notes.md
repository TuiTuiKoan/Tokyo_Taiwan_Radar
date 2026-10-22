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

## 3. Phase 0 量測：`/context` baseline（2026-10-23）

使用者在 `ttr-ai-harness-worktree` 根目錄啟動 `claude`（Sonnet 5.5）執行 `/context`：

| 類別 | tokens | 佔 1M 視窗 |
|---|---|---|
| System prompt | 2.9k | 0.3% |
| System tools | 16.6k | 1.7% |
| MCP tools＋MCP server instructions | 0.6k＋3.3k | 0.4% |
| Custom agents | 0.9k | 0.1% |
| Memory files | 8.7k | 0.9% |
| Skills | 8.5k | 0.8% |
| 合計 | 41.6k | 4% |

專案端估算（`.claude/skills/*/SKILL.md` frontmatter bytes ÷ 3.5，粗估，非 `/context` 實測）：

| 項目 | 數量 | 估計 tokens |
|---|---|---|
| 專案 skill 全部 | 68 | 約 2.6k |
| 其中 `sources/` 來源 skill | 54 | 約 2.1k（79%） |

D6 判定：D6 的門檻是專案 skill 常駐超過約 3k tokens。`/context` 的 Skills 8.5k 含內建與使用者層 skill，專案端估計約 2.6k，低於門檻，且只占視窗 0.2%。**不合併 54 個來源 skill。** Phase 4 的該項改為「不做」，除非日後來源 skill 數量或 description 長度明顯增加。

意外發現：Memory files 8.7k 是專案端最大的常駐項。`AGENTS.md` 17,013 bytes（中文，約 5k 至 6k tokens），其中 hooks 規則表與「未涵蓋」清單占大半。這些內容 Claude 每個 session 都載入，但多數 session 用不到。Phase 4 的精簡目標改為：把 hooks 規則表與殘餘風險清單移到 `docs/` 並以一行連結取代，`AGENTS.md` 只保留 5 點摘要、路徑規則表、角色路由與模型政策。需先確認 Codex 與 Copilot 不依賴這些段落的字面內容。

不確定：`/context` 沒列出各 skill 的個別 token，上表專案端數字是估算；若要確認可暫時移開 `.claude/skills` 後重測（會動到工作樹，不建議）。

## 4. D7：agents-repo worktree 已不存在（2026-10-23）

Close Campaign agent 的 Phase A 稽核與本 session 的獨立查證一致：

| 檢查 | 結果 |
|---|---|
| `git worktree list` | 15 筆，沒有 `tokyo-taiwan-radar-agents-repo`，也沒有 prunable |
| 登記路徑下的目錄 | 不存在；`/Users/flyingship/Development/Tokyo Taiwan Radar.worktrees` 是指向 `3-TTR/Tokyo Taiwan Radar.worktrees` 的符號連結，裡面只有 `agents-vscode-performance-issues` |
| 分支 `agents/tokyo-taiwan-radar-agents-repo` | 本地與遠端都沒有 |
| `.git/info/exclude` | 無相關行（該路徑在 repo root 外，本來就不需要） |
| 先前觀測 | 2026-10-15 與 2026-10-20 的 `git worktree list` 仍列出它，HEAD `3b04a6d3`，工作樹乾淨；10-23 已不在，移除者與時間不明 |

結論：D7 的目標（該 worktree 不再存在）已達成，沒有寫結案紀錄（無 slug、無 commit、無 spec）。`3b04a6d3` 是 origin/main 的祖先，沒有遺失的工作。先前記載的「87 behind」是 10-15 的觀測，現在同一個 commit 落後約 203，數字差異來自 main 前進。

另一個觀察（不屬本 campaign）：`Tokyo Taiwan Radar.worktrees/agents-vscode-performance-issues` 目錄存在但不在 `git worktree list`，疑似未登記的殘骸，由使用者決定是否處理。

## 5. Plan Critic（Codex）與 plan.md rev.2（2026-10-23）

使用者貼回 Codex 的輸出，內容是一份給 Claude 的修訂提示，列六項必須處理的意見；Codex 的批評全文未提供，所以沒有另存 critique 檔。執行者：Claude Code，Opus 5.5。

| # | 意見 | 處理 |
|---|---|---|
| 1 | Secrets 與 D4 | 撤回 D4；plan §3 Phase 2、§4、§5 改寫；以實測證明爬蟲 dry-run 不需要 `.env` |
| 2 | 進度漂移 | plan 狀態、Phase 0、Phase 1、§6 更新；proposal 的裁決表更新 |
| 3 | 模型投影 | plan §1.3 與 Phase 1 改為「來源檔不寫 `model:`」；NOT TESTED 四項保留 |
| 4 | Phase 4 | 合併來源 skill 標為已否決；改為 `AGENTS.md` 瘦身 |
| 5 | Phase 3 前置決策 | 提出 `harness.lock`（pinned commit SHA）方案與驗收條件，列為 D8，待裁決 |
| 6 | 繼續工作的門槛 | plan 新增 §3.1 Go/No-Go；tasks.md 各 phase 加前置條件 |

新證據：
- 在沒有 `.env` 的 `ttr-ai-harness-worktree`（`test -f scraper/.env` 回傳 1）執行 `python main.py --dry-run --source taiwan_cultural_center`：exit 0，輸出事件 JSON。結論：爬蟲 dry-run 不需要 secrets。Python 依賴（playwright、supabase、dotenv）已安裝。
- `web/.env.example` 不存在；`scraper/.env.example` 存在。web 程式讀取 `NEXT_PUBLIC_SUPABASE_URL`（36 處）、`NEXT_PUBLIC_SITE_URL`（21）、`NEXT_PUBLIC_SUPABASE_ANON_KEY`（17）、`SUPABASE_SERVICE_ROLE_KEY`（19）、`GITHUB_TOKEN`（10）、`OPENAI_API_KEY`（6）等。web build 以佔位值通過與否：NOT TESTED。
- 這個 worktree 本來就沒有 `.env`，所以 rev.1 的 D4 建議會「新增」secrets 副本，不是維持現狀。
- cc-statusline 目錄（`~/.claude/cc-statusline/`）有 579 個 `active-*.json` 與 `agents-*.json`；抽查的檔案只含 `activeMs`、`turnStartAt`，未確認含配額歷史。Phase 1 之前的配額基準：沒有留下。

觀察：從 worktree 的 `scraper/` 子目錄執行命令時，Claude Code 的 hooks 不載入（AGENTS.md「生效條件」）。本 session 的命令先 `cd` 到子目錄再回到根目錄，期間 hooks 實際上沒有保護那一次執行；dry-run 本身只讀取與列印，不涉及 secrets。以後在子目錄執行命令應改用絕對路徑或在根目錄用 `python3 scraper/main.py`。

尚未 commit：plan.md、proposal.md、tasks.md、notes.md 的修訂等使用者核准。

## 6. Plan Critic 全文與 plan.md rev.3（2026-10-23）

### 6.1 第二次 Plan Critic 的經過

- 使用者回報「跑完了」，但 03:42 的 Codex session（`~/.codex/sessions/2026/10/23/rollout-…03-42-24-….jsonl`，工作目錄是主工作樹）收到的提示是字面的 `<提示>`：我上一則訊息的命令範本沒有替換成真正的提示詞，所以 Codex 什麼都沒審，也沒有輸出檔。這是執行者（Claude）的疏漏。
- 重跑：`codex exec -p plan -s read-only -o docs/specs/active/ai-harness/plan-critique-1.md -`，提示詞由檔案經 stdin 餵入。Codex 執行標頭：v0.163.0（`codex doctor` 先前顯示 0.160.0，升級時間不明）、`model: gpt-6.1-sol`、`reasoning effort: high`、`sandbox: read-only`。結果寫入 [plan-critique-1.md](./plan-critique-1.md)（19,019 bytes）。
- 這同時證明 `codex -p plan` 能載入 `~/.codex/plan.config.toml`（先前列為 NOT TESTED）。它沒有證明 agent TOML 的 effort 生效。

### 6.2 評審結論與處理

結論：rev.2 未通過；六項先前意見 3 項 CLOSED（a、c、d）、3 項 PARTIAL（b、e、f）；阻擋項 B1–B6、建議 N1–N5。處理方式見 plan.md「rev.3 變更摘要」。

核對 Codex 引用的程式碼（靜態核對，未執行）：

| 位置 | 內容 | 結論 |
|---|---|---|
| `scraper/main.py` 約第 433 行 | `events = scraper.scrape()` 在 `if not dry_run:` 之前執行 | 成立：dry-run 只跳過 upsert 與後續 annotation，不跳過來源內部行為 |
| `scraper/sources/cinemaclair.py` 約第 175 行 | 有 `OPENAI_API_KEY` 才呼叫 OCR，沒有則回傳 `{}` | 成立：缺少憑證不會崩潰，但輸出會變少 |
| `scraper/sources/gguide_tv.py` 約第 39 行 | `_get_works_sb()` 惰性建立 Supabase client | 成立：需要 Supabase 憑證才會成功 |
| `scraper/sources/tokyoartbeat.py` 約第 25 行 | `CONTENTFUL_TOKEN = os.environ.get(..., "")` | 成立：缺少時為空字串 |

### 6.3 對先前紀錄的更正（追加式，原文不改）

- §5 寫「爬蟲 dry-run 不需要 secrets」：**過度推廣**。本機實測只涵蓋 `taiwan_cultural_center` 一個來源；其餘來源 NOT TESTED，靜態核對有上表的反例。D4'「不複製正式 secrets」的原則不受影響。
- §5 寫「從子目錄執行命令時 hooks 不載入，那次執行實際上沒有保護」：**混淆了 session 啟動目錄與命令的工作目錄**。官方文件指出 `CLAUDE_PROJECT_DIR` 保持在 session 起點，hook 輸入的 `cwd` 才隨 `cd` 變動。那次 Bash 命令當時是否由 hooks 把關，沒有 debug 紀錄，**維持未知**。往後仍避免在子目錄執行命令，以免依賴這個不確定性。
- §3 寫「專案 skill 約 2.6k tokens」與 §1.3 的 X1–X4 預設模型說明：前者是 bytes 換算的估算，不是逐 skill 實測；後者錯誤，15 個 agent 都有 tier（plan.md 已更正）。
- 這份 notes 與 plan §1.2、§4 中來自 Orca 官方文件或第三方文章的敘述，是「文件描述」，不是本機實測；plan.md 已逐項標示。

### 6.4 提交紀錄（N5）

rev.2 的四份文件已 commit：`dfb40b6b`（docs(specs): revise ai-harness plan to rev.2 after Codex plan critique），未 push。AGENTS.md 的「Plan Critic 批評全文必須存檔」規則已修改但未 commit。rev.3 的修訂尚未 commit。

## 7. 使用者裁決與核准（2026-10-23）

- **D4' 採用**：worktree 不帶正式 secrets。Phase 2a 的條件 (b) 成立。
- **D8 採用（建議版）**：`harness.lock` 是來源版本紀錄；plugin 缺失時只警告，不阻擋；Phase 3 擴大（3b）之前不搬 hooks。D8 只在 3b 生效，3a 試點不需要。
- **要求驗證 Phase 1 的四項 NOT TESTED**：Codex 是否讀取 `.codex/agents/*.toml` 並套用 effort；`claude --agent plan-critic` 的 Opus 實測；`opusplan` 的切換；Haiku wrapper 的 `effort: low` 與 grunt 任務品質。結果記入下一節。在全部驗證前，plan §3.1 的 Phase 2b 條件 (c) 不成立。
- **核准 commit**：rev.3 的 plan.md、proposal.md、tasks.md、notes.md、`plan-critique-1.md`，以及 AGENTS.md 的「Plan Critic 批評全文必須存檔」規則。
