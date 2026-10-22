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

## 8. Phase 1 使用端驗證（2026-10-23）

使用者要求驗證 Phase 1 的四項 NOT TESTED。執行者：Claude Code（Opus 5.5）。工具版本：Claude Code 2.1.308、Codex 0.163.0（兩者都比先前紀錄的 2.1.300、0.160.0 新，自動更新；notes §2 的 pytest 與 hooks 實測是舊版，升級後重跑 fixture 仍是 parked 項目）。所有測試都從 `ttr-ai-harness-worktree` 根目錄執行；原始輸出在 session scratchpad，未入 repo。

| # | 項目 | 方法 | 結果 |
|---|---|---|---|
| 1 | Codex 讀取 agent TOML 並套用 effort | `codex exec -s read-only --json`，以明確的使用者要求叫它 spawn `tester`；讀子 thread 的 rollout metadata | **PASS**：子 thread `agent_role=tester`，`effort=low`；父 thread `effort=medium`；子 thread 模型沿用 `gpt-6-luna`（TOML 沒有 `model`，符合設計）。spawn 參數 `agent_type="tester"` |
| 2 | `claude --agent plan-critic` 用 Opus | `claude -p --agent plan-critic --output-format json` | **PASS**：`modelUsage` 含 `claude-opus-5-5` |
| 3 | `opusplan` 切換 | `claude -p --model opusplan`，一次一般、一次 `--permission-mode plan` | **PASS**：一般執行 `claude-sonnet-5-5`；plan mode `claude-opus-5-5` |
| 4a | Haiku wrapper 的 `effort: low` | 讀 transcript 的 API 請求 | **PASS（限制）**：以 subagent 委派時，每個請求都是 `claude-haiku-5-5` 加 `low`，主對話為 Sonnet 加 `medium`。**以 `claude --agent tester` 當主執行緒時請求是 `medium`**，frontmatter 的 `effort` 不生效，只有模型別名生效 |
| 4b | grunt 任務品質 | 20 筆 TCC 事件 JSON，人為製造 4 筆缺開始日期與 1 筆結束早於開始；問筆數、缺日期數、是否有結束早於開始；Sonnet 與 Haiku-low tester 各 3 次 | **3/3 對 3/3**，都與標準答案一致 |

證據與限制：
- 所有 `modelUsage` 都另含 `claude-haiku-5-5`，是 Claude Code 的背景用量，不是被測 agent 的證據。判斷被測 agent 用哪個模型，要看 subagent transcript 的 assistant 訊息與 API 請求，不能看 `modelUsage`，也不能用粗略 grep（一次用 grep 抓到 `opus` 其實是別的欄位，已改用逐筆解析）。
- 4b 的 3 次委派都在 `subagents/` 底下留下 `agentType: tester` 的 transcript，每個請求都是 Haiku 加 low，確認 Haiku 臂真的由 Haiku-low tester 作答。
- 4b 只是極有限的探測：樣本數 3、題型是計數與日期比較。**不能推論到**選擇器除錯、判讀失敗原因、日文貼文撰寫（lianbu）等任務；那些仍未驗證。
- Codex 的第一、二次嘗試都沒有真的 spawn：事件紀錄只有 `cat`，沒有 `collab_tool_call`；第一次它的回覆卻說「spawned successfully」，是不實的轉述。第三次以明確的使用者要求才 spawn。原因是 Codex 的 `multi_agent_mode` 規則：沒有使用者或 AGENTS.md 明確要求就不 spawn sub-agent。因此**不能只信模型的自述，要看事件或 rollout metadata**。
- 這是否表示日常使用 Codex 時 `.codex/agents/*.toml` 會自動被派用：不會。需要使用者或 AGENTS.md 明確要求委派。AGENTS.md 的角色路由表目前沒有要求 Codex 主動委派，這是設計上的現況，不是缺陷。

影響：
- AGENTS.md 模型政策補一句：`effort` 只在 agent 被當作 subagent 委派時生效（已修改，未 commit）。
- plan §3.1 Phase 2b 的條件 (c) 成立；仍須滿足 (d) 配額基準與 (e) spike 結案。

## 9. Phase 2a（2026-10-23）

使用者核准開始 Phase 2，spike 選 Claude agent teams（不測 Orca orchestration）。執行者：Claude Code，Opus 5.5。起點：`2f5021e0`。

完成的 housekeeping：

| 項目 | 變更 |
|---|---|
| `.gitignore` | 加 `.claude/worktrees/` |
| `git.instructions.md` | exclude reconcile 片段的 `case` pattern 改為 `("$root"/*)`，並說明 macOS bash 3.2 的原因；新增 § Tools that show or create worktrees（只用 git 建立與清理、不使用工具的 Delete、不複製 secrets）與 § Telling other running sessions（Claude Code 專屬，純文字，不等回覆，不是核准） |
| `validate-merge-deploy.agent.md` | Step 5 新增第 7 項：部署驗證後通知其他 session |
| `campaign-closer.agent.md` | 「完成後」加一段：結案後通知其他 session |

驗證：`python3 scripts/sync_ai_adapters.py` 重生成成功，`--check` exit 0，生成的 `.claude/agents` 沒有變動（只改了本文，沒改 frontmatter）。主工作樹 `git status` 乾淨，沒有與這三個檔案衝突的未提交修改。exclude 片段的修正版先前已在 bash 3.2 下實測 converged（§1）；這次沒有重跑，因為 guard 會擋直接以 `/bin/bash` 執行檔案的檢查命令。

Spike：agent teams 在非互動模式（`claude -p`）不會 spawn teammate（官方文件），而且需要實驗旗標，所以無法由我代跑。方案、啟動指令、提示詞、成功與停止條件、判定規則已寫在 [spike-agent-teams.md](./spike-agent-teams.md)，執行前寫定、事後不改。待使用者執行並回報後，結果記在本檔的下一節。

不在 2a 範圍：Orca 安裝、`.worktreeinclude`（D4' 決定不建立）、web 佔位值 build 驗證、agent worktree 的 dry-run 範圍限定。後兩項是 2a 的待辦，尚未做；見 tasks.md。

### 9.1 web build 以佔位值驗證（2026-10-23，本機實測）

方法：在 `ttr-ai-harness-worktree`（沒有任何 env 檔，用 `test -f` 確認 scraper 端沒有；web 端未讀取任何 env 檔）執行 `pnpm --dir web install --frozen-lockfile`，再以命令列傳入三個佔位值執行 `pnpm --dir web run build`：

| 變數 | 值 |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://placeholder.invalid` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `placeholder-anon-key` |
| `NEXT_PUBLIC_SITE_URL` | `http://localhost:3000` |

結果：exit 0；`prebuild`（i18n parity、JSON-LD security、specs snapshot）通過；Next.js 編譯成功並產生 250 個靜態頁。`git status` 沒有因 build 而新增或修改被追蹤的檔案（`web/node_modules/`、`web/.next/` 是 ignored）。

意義：D4' 的 web 部分成立，web build 不需要 secrets，也不需要補 `web/.env.example`。
限制：build 以外沒有驗證。需要真實 Supabase 的執行階段行為（`next dev`、登入、Admin CRUD、帶資料的頁面）仍 NOT TESTED，且依 D4' 不在 agent worktree 內做。這次 build 沒有觸及真實 Supabase，所以也沒有驗證「佔位值是否讓有資料的靜態頁變成空頁」。

### 9.2 工作樹上他人的修改

04:21（本 session 的 Phase 2a 工作期間），`AGENTS.md` 出現一段不是本 session 寫的修改：新增「Codex 委派」小節並改寫 Copilot 對照表的 `runSubagent` 列，內容引用 §8 的 Codex 發現（必須明確要求才會 spawn、以事件紀錄而非模型自述判斷）。修改者不明，內容與 §8 一致，本 session 當作現況保留，未 commit，等使用者確認後一併 commit。

## 10. Spike 結果：agent teams（2026-10-23）

使用者依 [spike-agent-teams.md](./spike-agent-teams.md) 執行一次。完整報告：[spike-result.md](./spike-result.md)（lead 寫入，6,514 bytes，未修改）。核對者：Claude Code（Opus 5.5），事後獨立查證。

### 10.1 這是真正的 agent team

報告自己寫「本環境沒有 team 建立工具，以兩個具名 Plan 類型 subagent 加 SendMessage 模擬」。**這是 lead 對機制的誤解**：官方文件說，啟用 agent teams 後，以 `name` 啟動的 subagent 就是以 teammate 方式啟動。證據（本機）：`~/.claude/teams/session-092ec819/config.json` 存在，成員為 `team-lead`、`correctness`（agentType `Plan`、model `sonnet`）、`tests`（`Plan`、`sonnet`），並有 `inboxes/team-lead.json` 與 `inboxes/tests.json`。所以 spike 有效，只是 lead 的自我描述不可信，與 §8 Codex 的情形同型：**判斷要看紀錄，不看模型自述**。

### 10.2 客觀數據（來自 session transcript，不是 `/usage`）

| 項目 | 值 |
|---|---|
| 耗時 | 04:35:59 到 04:37:27，約 1.5 分鐘（上限 15 分鐘） |
| 模型與 effort | lead、correctness、tests 全為 `claude-sonnet-5-5`、effort `medium` |
| lead | 16 則 assistant 訊息；輸出 17.2k；cache 寫入 163k；cache 讀取 946k |
| correctness | 7 則；輸出 9.1k；cache 寫入 82k；cache 讀取 342k |
| tests | 6 則；輸出 8.8k；cache 寫入 144k；cache 讀取 242k |
| 合計 | 輸出約 35k；cache 寫入約 389k；cache 讀取約 1.53M |

用量百分比（S3）：使用者沒有提供開始與結束的 `/usage`，我無法觀測；token 數不能換算成方案百分比，所以 **S3 未成立也未失敗，維持待確認**。

### 10.3 發現的核對（lead 事後逐項）

| # | 發現 | 核對方式與結果 |
|---|---|---|
| A | `write_outputs` 先 `unlink` 全部生成檔，才逐檔檢查 "refusing to overwrite" | **已重現**：在拋棄式副本放一個無 marker 的 `.codex/agents/tester.toml`，`sync` exit 1 並報 refusing to overwrite；失敗後 175 個生成檔少了 2 個（排序在 tester 之後的 `update-history-skill-agent.toml`、`validate-merge-deploy.toml`），其餘已被重寫。手寫檔本身完好。影響：`git restore` 或修好後重跑即可復原，所以是順序缺陷，不是資料遺失；嚴重度 low 到 medium。此排序在加入 `.codex` 之前就存在，`.codex` 增加了被觸發的機會 |
| B | 缺 tier 時寫入模式拒絕寫檔沒有測試 | **靜態核對成立**：測試檔只有 `test_write_mode_refuses_when_roles_are_broken`，沒有 tier 版本 |
| C | `tier=None` 時 `agent_outputs` 靜默省略欄位 | 靜態核對成立；`main()` 兩種模式都先擋，所以不是缺陷，是缺測。兩位各自獨立提出 |
| D | `json.dumps(ensure_ascii=False)` 不跳脫 DEL（U+007F） | **已重現**：DEL 使 `tomllib` 報 `Illegal character '\x7f'`；引號、反斜線、tab、換行、U+2028、emoji、NUL、U+0085 都能 round-trip。實際 agent 的 description 不會含 DEL，所以嚴重度 low。兩位各自獨立提出（但 correctness 評 low、tests 評 high，lead 的 low 較貼近實況） |
| E | `is_generated` 用子字串比對，兩種 marker 跨副檔名互通 | 靜態核對成立（`MARKER in text or TOML_MARKER in text`）；手寫檔只要引用 marker 文字就會被視為生成檔。low |
| F | handoffs 全被略過時仍輸出空標題 | 靜態核對成立；既有行為，現在也出現在 Codex 檔。low |
| G | `rglob` 對 symlink 的行為隨 Python 版本改變 | 未確認，維持 uncertain |
| T4–T13 | 測試缺口 | 靜態核對：T4、T5、T6、T7、T8、T9、T10、T11、T12、T13 描述與測試檔相符；T12 報告自己也說只是維護成本。未逐項寫測試重現 |

「兩位皆未找到可確認的 high 級程式缺陷」：同意，除了 tests 把 B、C、D 評為 high（缺測的重要性），核對後 D 是 low、C 是缺測、B 是真實測試缺口。

### 10.4 判定規則的套用

| 條件 | 結果 |
|---|---|
| S1 兩位 15 分鐘內交出附檔案與行號的發現 | **成立**（約 1.5 分鐘；行號由 diff 推算，報告自己註明可能差 1 到 2 行） |
| S2 至少一項經確認的真實問題，且兩人的發現不全重複 | **成立**：A 與 D 已重現；A 只有 correctness 提出，B 與 T4 到 T13 只有 tests 提出；重疊只有 C、D |
| S3 用量消耗 ≤ 5 個百分點 | **待使用者提供** |
| S4 結束後 `git status` 只多出 `spike-result.md` | **成立**：`scripts/` 無任何修改；新增的未追蹤檔只有 `spike-agent-teams.md`（本 session 的方案）與 `spike-result.md` |
| 停止條件 | 無觸發：沒有超時、teammate 沒要求寫入權限（`Plan` 類型沒有 Edit／Write）、lead 沒有自己實作 |

**暫定判定**：S3 確認前不下最終判定。若使用者回報的用量消耗 ≤ 5 個百分點，記為「可列入 Phase 2b 考慮」，**不是採用**。

### 10.5 這次結果能與不能說明什麼

- 能：agent teams 在 Claude Code 2.1.308 可用；兩位 Sonnet teammate 在 1.5 分鐘內完成唯讀審查並找到至少兩個真實問題；全程沒有寫入。
- 不能：沒有單一 agent 的對照組，所以不知道單一 session 是否也會找到同樣的問題，也不知道團隊的 token 成本相對單一 agent 是多少。三個 agent 合計約 1.53M cache 讀取，是否值得，需要與一次單 agent 審查的用量比較才能下結論，那是另一次實驗，本 spike 依停止規則不重跑。
- 已知缺陷：lead 的自我描述不可信（§10.1）；報告行號是推算；teammate 回報被截斷時要靠 SendMessage 補送。

### 10.6 後續（等使用者決定）

spike 發現的 Phase 1 程式碼問題與測試缺口已列在 tasks.md，未動手修。

### 10.7 S3 的量測缺口（2026-10-23）

使用者貼上 spike 結束後的 `/usage`（只有「結束後」，沒有「開始前」的數字）：

| 項目 | 值 |
|---|---|
| 該 session 的 API 等值花費 | $0.85（claude-sonnet-5-5：輸入 2.1k、輸出 16.7k、快取讀取 1.2m、快取寫入 192.3k；claude-haiku-5-5 $0.0006）。這是 lead session 的數字，與 transcript 合計的三個 agent（快取讀取約 1.53M、寫入約 389k）不完全相同，差異未查明，所以只當量級參考 |
| Current session | 13% used（8:39am 重置） |
| Current week（all models） | 28% used |
| Current week（Fable） | 7% used |

這些百分比是**帳號層、跨所有 session 的累計**，包含當時其他 session（含本 session 的規劃與驗證）的用量，所以無法從「結束後」單一數字反推 spike 自己消耗了幾個百分點。找過本機是否有開始前的歷史紀錄：`~/.claude/cc-statusline/` 只有 session 計時與訊息計數，沒有配額歷史；`~/.claude` 內其他命中只是舊 transcript 的文字。**S3 因此未量測，不是失敗**。

上界：該 5 小時 session 視窗目前是 13%，spike 消耗必然 ≤ 13 個百分點，這不足以確認 ≤ 5。

依事先寫定的判定規則，S1 到 S4 必須全部成立才記為「可列入 Phase 2b 考慮」；S3 未成立，故**最終判定暫記為：無法確認明確收益，不採用**，直到有量測到的 S3。不因結果不理想而重跑；若重跑只是為了補量測，必須使用相同提示詞與條件，並在開始前記下用量，同時保留本次結果。這個選擇留給使用者。

/usage 面板自己的提示（近 24 小時，僅本機 session，百分比互相重疊）：「給簡單的 subagent 較便宜的模型」68%、「同時開太多 session」46%（最多同時 16 個）、「超過 8 小時還沒停的 session」56%。前兩項與 Phase 1 的 tier 分級、Phase 2b 的配額門檻方向一致，但這是近似歸因，不是 spike 的證據。

## 11. Spike 重跑的事前登記（2026-10-23）

使用者選擇選項二：用完全相同的提示詞重跑一次，補上 S3 的量測。條件寫在 [spike-agent-teams.md](./spike-agent-teams.md) 的「第二次執行」一節，執行前已寫定。

檔案處理（追加式更正，§10 的原文不改）：§10 與 tasks.md 提到的 `spike-result.md` 指**第一次**的報告。第一次的報告已移到 `~/.ai-notes/ttr/ai-harness-spike-run1-result.md`（SHA-256 `dad945c6b515112e1d31a467ae3397ed5d86360d0091faed3fa0193a4d5e6bfd`，移動前後相同），第二次結束後還原為 `docs/specs/active/ai-harness/spike-result-run1.md`；第二次 lead 寫入的 `spike-result.md` 是第二次的報告。

已知風險：`notes.md` §10 含第一次的核對結果，teammate 若去讀它會被污染。防止方式是提示詞限定範圍；事後檢查方式是讀 teammate 的 transcript。S4 的基準是目前 9 行的 `git status --short` 快照。

## 12. Spike 重跑結果與最終判定（2026-10-23）

使用者依 §11 的登記執行第二次（相同提示詞、全新 session）。核對者：Claude Code（Opus 5.5）。第二次的報告：[spike-result.md](./spike-result.md)（6,009 bytes，lead 寫入，未修改）；第一次的報告已還原為 [spike-result-run1.md](./spike-result-run1.md)（SHA-256 `dad945c6…e6bfd`，與移出前相同）。§10 與 tasks 先前提到的 `spike-result.md` 指第一次，現為 `spike-result-run1.md`。

### 12.1 S3：用量

| | session | 週（all models） | 週（Fable） |
|---|---|---|---|
| 開始前（全新 session，$0.0000） | 15% | 29% | 7% |
| 結束後（$0.73） | 15% | 29% | 7% |
| 差值 | 0 | 0 | 0 |

意義：**S3 成立**（上限 5 個百分點）。限制：`/usage` 的解析度是 1 個百分點，所以真實消耗小於約 1 到 2 點；百分比是帳號層累計，使用者確認重跑期間沒有其他 session 的活動；只有一次量測。lead session 的 API 等值花費 $0.73。

### 12.2 客觀數據（來自 transcript）

| 項目 | 第一次 | 第二次 |
|---|---|---|
| 耗時 | 約 1.5 分鐘 | 約 1.6 分鐘 |
| 輸出 tokens（三個 agent 合計） | 約 35k | 約 32k |
| cache 寫入 | 約 389k | 約 427k |
| cache 讀取 | 約 1.53M | 約 843k |
| 模型與 effort | 全為 Sonnet 5.5、medium | 同左 |
| 團隊 | `session-092ec819`：team-lead、correctness、tests | `session-0a094a35`：同左（`~/.claude/teams/…/config.json` 證實） |

兩次 lead 的報告都自稱「不是原生 team、是具名 subagent」，兩次都被設定檔推翻。這是 lead 對機制的誤解；再次提醒：判斷看紀錄，不看模型自述。

### 12.3 污染檢查與 S4

- 污染：兩位 teammate 各只有 2 與 3 次工具呼叫，**沒有任何一次涉及** `docs/specs/active/ai-harness/`、`spike-result` 或 `notes.md`。lead 共 4 次工具呼叫，唯一涉及該目錄的是寫入 `spike-result.md`。結論：第二次沒有受第一次污染。
- S4：`git status --short` 與基準快照相比，唯一差異是多出 `?? docs/specs/active/ai-harness/spike-result.md`。`scripts/` 沒有任何修改。成立。

### 12.4 兩次結果的比較（只報告）

第二次的主要發現幾乎全部與第一次獨立重現，說明這組發現是訊號而不是雜訊：

| 主題 | 第一次 | 第二次 |
|---|---|---|
| `write_outputs` 先刪後檢查 | A（已重現） | #2 |
| `is_generated` 子字串與跨副檔名 | E | #1（兩位都提出） |
| tier 寫入模式缺測 | B | #3 |
| 缺 tier 輸出契約缺測 | C | #4 |
| DEL 未跳脫 | D（已重現） | #6 |
| description 特殊字元缺測 | T 系列 | #5 |
| handoffs 空標題 | F | #9 |
| 第二次新增、已重現 | | #7 孤立 surrogate 使寫檔丟 `UnicodeEncodeError`；#8 兩個名稱 kebab 後相同會靜默覆蓋（`Foo Bar` 與 `foo-bar` 同為 `foo-bar`）；#13 `tier: build # note` 因 `parse_scalar` 不去除行內註解而報 unknown tier |
| 第二次新增、未重現 | | #10、#11、#12（測試缺口，靜態判斷）；#14 是資訊項，與已有的 haiku 實測一致 |

兩次都沒有高嚴重度缺陷。第二次報告自己列出「不列入」項目與「檢查後判定無問題」項目，條理比第一次完整；差異不影響判定。

### 12.5 最終判定

| 條件 | 結果 |
|---|---|
| S1 15 分鐘內交出附檔案與行號的發現 | 成立（約 1.6 分鐘） |
| S2 至少一項經確認的真實問題且不全重複 | 成立（#2 即 A 已重現；#7、#8、#13 本次重現） |
| S3 用量消耗 ≤ 5 個百分點 | 成立（0 點，解析度 1 點） |
| S4 只多出 `spike-result.md` | 成立 |
| 停止條件 | 無觸發 |

**判定：可列入 Phase 2b 考慮。這不是採用。**

### 12.6 這個結果能與不能說明什麼

- 能：agent teams 在 Claude Code 2.1.308 可用；一次兩位 Sonnet teammate 的唯讀審查約 1.5 分鐘、對帳號用量的影響小於約 1 到 2 個百分點，並兩次獨立找到同一組真實問題；全程沒有寫入，沒有污染。
- 不能：沒有單一 agent 的對照組，所以不知道單一 session 是否也會找到同樣的問題，也不知道團隊相對單一 agent 的成本差。兩次的 token 總量不小（cache 寫入約 400k），只是在這個方案的用量視窗裡看不出來。**一次 1.5 分鐘的小審查不代表長時間、多人的正式平行開發的成本**，那要等 Phase 2b 的配額記錄。
- 可複製性：兩次一致是好訊號，但樣本只有兩次、同一個標的、同一個提示詞。
- 已知缺陷：lead 的自我描述不可信；行號由 diff 推算；Plan 類型的 teammate 仍有 Bash，唯讀只靠類型與提示詞，工具層沒有阻擋重導寫入。

### 12.7 後續（等使用者決定）

兩次 spike 共同指向的 Phase 1 程式碼問題與測試缺口已更新在 tasks.md，未動手修。Phase 2b 的條件現況：(c) 已成立，(d) 第一週配額基準尚未開始記錄，(e) spike 已結案；所以 2b 仍差 (d)。
