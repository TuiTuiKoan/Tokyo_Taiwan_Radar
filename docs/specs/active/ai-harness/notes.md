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

## 13. Phase 1 後續修正：先紅後綠（2026-10-23）

使用者核准依兩次 spike 的共同發現，先寫會失敗的測試再修。執行者：Claude Code（Opus 5.5）；這類實作用 Sonnet 加 medium 就夠。起點：`5b3165f5`。

### 13.1 先寫測試，先紅

新增 `scripts/tests/test_sync_hardening.py`，共 39 個測試。修程式碼前執行：**9 個失敗、29 個通過**。失敗的正好是已重現的缺陷；通過的是鎖定現有正確行為的測試（B、C、T4 等，本來就綠，這是預期）。

| 先紅的測試 | 對應發現 |
|---|---|
| `test_hand_written_same_name_toml_aborts_before_deleting_anything`、`test_hand_edit_that_removes_the_marker_blocks_the_next_write` | A、T5、T6：寫入失敗後少了生成檔 |
| `test_marker_text_in_prose_does_not_make_a_file_generated`、`test_a_marker_for_the_other_file_type_does_not_make_a_file_generated` | E：子字串比對與跨副檔名 marker |
| `test_tier_value_boundaries[inline-comment]`、`test_a_tier_with_an_inline_comment_still_projects_its_tier` | #13：`tier: build # note` |
| `test_toml_string_round_trips[del]` | D：DEL 未跳脫 |
| `test_an_unencodable_description_aborts_before_any_file_changes` | #7：孤立 surrogate 在刪檔後才崩潰 |
| `test_duplicate_output_names_are_rejected_without_touching_files` | #8：名稱碰撞靜默覆蓋 |

### 13.2 修改（`scripts/sync_ai_adapters.py`）

- `write_outputs`：先檢查所有衝突（無法解碼的檔案也算衝突）與所有輸出能否編碼，通過後才刪除與寫入；任何一項失敗就一個檔案都不動。
- `is_generated(text, suffix)`：只認「整行等於該副檔名對應的 marker」；`.md` 只認 HTML marker，`.toml` 只認 TOML marker。
- `toml_string`：把 DEL 換成 `\u007f`。其餘控制字元原本就由 `json.dumps` 跳脫。
- `tier_value`：去掉行內 YAML 註解；`tier_problems` 與投影都使用它。
- `agent_outputs`：兩個來源 kebab 後同名時，以 `duplicate agent output name …` 中止。
- 孤立 surrogate 無法表示成 TOML（TOML 只接受 Unicode scalar value），所以不嘗試轉義，而是在任何檔案變動前以明確訊息中止。

### 13.3 結果

| 檢查 | 結果 |
|---|---|
| 新測試 | 39 passed（含修完後另補的「無法解碼檔案是衝突而非崩潰」） |
| 全部測試 `scripts/tests scripts/claude/tests` | **531 passed**（先前 492） |
| `python3 scripts/sync_ai_adapters.py` 重新生成 | 175 個檔案，`git status` 只有腳本與新測試檔，生成物無差異 |
| `--check` | exit 0 |

### 13.4 未處理與限制

- 未做：T10（`conftest` 的 `copytree` 對缺少 `.codex` 的情況）、T11（`len(sources) * 2` 寫死）、T12（`MODEL_ID_PREFIXES` 冗餘，是維護成本）、G（symlink 行為，未確認）、第二次報告 #10 到 #12 的其餘缺口。
- `is_generated` 改為整行比對後，若有人把 marker 單獨一行貼進手寫檔（例如文件中的 fenced code block），仍會被當成 generated。這比子字串比對窄很多，但不是零。
- 這些修正以 spike 的讀碼推論為起點，除 A、D、#7、#8、#13 在 spike 核對時已重現外，其餘缺口是以測試鎖定行為，不是缺陷證明。
- 尚未 commit，等使用者核准。

## 14. Phase 1 修正第二批的規劃（2026-10-23，尚未動手）

起點：`6bfc2fa8`。使用者要求規劃「沒處理的」三類：測試維護項、symlink、第二次報告其餘低嚴重度缺口。以下先核對現況，再列做法。

### 14.1 現況核對

| 項目 | 核對結果 |
|---|---|
| 生成目錄內的 symlink | 目前 5 個生成目錄都是 0 個 |
| `rglob` 對 symlink | 本機 Python 3.14.3：會列出指向檔案的 symlink，不進入指向目錄的 symlink。CI 用 Python 3.12，**行為是否相同未驗證**（本機是否有 3.12 也未確認） |
| 第二次報告 #11（idempotence 與 `.codex`） | 已被現有測試涵蓋：`GENERATED_DIRS` 含 `.codex/agents`，`test_generation_is_idempotent` 寫入後立刻 `--check` 回 0。不需處理 |
| 第二次報告 #12（欄位順序） | 已在 `test_wrapper_frontmatter_fields_have_each_projected_key_once_in_order` 涵蓋 |
| 第二次報告 #10 | 非 UTF-8、README 已涵蓋；**子目錄**未涵蓋 → R6 |
| 第二次報告 #14 | 資訊項，與已有的 Haiku 實測一致，不處理 |
| git hooks 與 CI | `.githooks/pre-commit`、`pre-push` 沒有呼叫 `sync_ai_adapters.py` 或 pytest；`.github/workflows/` 也沒有。CI 的 Python 是 3.12。這是 parked 的 ai-portability-followups ①，也是 plan 的 Phase 3b 條件，**不在本批**，但它決定這些測試實際會不會被執行 |

### 14.2 項目與做法

| # | 項目 | 做法 | 驗證 |
|---|---|---|---|
| R1 | handoffs 全被略過仍輸出孤立標題（F／#9） | `agent_outputs` 只在至少有一個有效項目時才加標題；兩個輸出共用同一份 `handoff_lines` | 先寫紅測試：全部項目缺 `label`／`agent` 時，Claude wrapper 與 Codex `developer_instructions` 都不含「完成後建議的下一步」 |
| R2 | symlink（G） | 先在 3.12 與 3.14 重現實際行為。建議政策：**生成目錄內或預期輸出路徑上的 symlink 一律當作衝突，拒絕寫入、不跟隨**，行為與 Python 版本無關 | 紅測試：預期輸出路徑是指向外部檔案（內容含 marker）的 symlink，寫入必須拒絕且外部檔案不變；指向目錄的 symlink 不被掃描也不被刪除 |
| R3 | `conftest` 的 `copytree` 對缺少目錄丟錯（T10） | 只複製存在的來源目錄 | 在沒有 `.codex` 的樹上能建立 `tmp_repo` |
| R4 | `len(sources) * 2` 寫死（T11） | 改為比對 `.claude/agents/*.md`、`.codex/agents/*.toml` 與來源三組名稱集合相等 | mutation check：暫時加第三種輸出，舊斷言會誤報、新斷言不會 |
| R5 | `MODEL_ID_PREFIXES` 冗餘（T12） | 刪除它與其斷言；別名白名單只在一處（`{opus, sonnet, haiku}`）；測試檔另有「來源不得寫 `model:`」的測試守住 ID 問題 | 加入別名 `fable` 時只需改一處 |
| R6 | 子目錄未涵蓋（#10） | 補測試：`.codex/agents/sub/` 下手寫 `.md`、`.toml` 不被動；子目錄內帶 marker 的殘留檔被 `--check` 報告為 stale | mutation check：暫時讓 `generated_files` 不掃子目錄，測試必須失敗 |

### 14.3 順序與提交

1. R1 與 R2：先寫紅測試，確認紅，再改程式；一個 commit（`fix(ai)`）。
2. R3 到 R6 都是測試維護：每項先做 mutation check 證明新斷言真的會失敗，再提交；一個 commit（`test(ai)`）。
3. 每步後跑 `python3 -m pytest scripts/tests scripts/claude/tests -q` 與 `sync --check`；全部通過才請使用者核准 commit。

### 14.4 需要使用者決定

- R2 的政策：拒絕（建議）、忽略，或跟隨 symlink。
- 是否把 CI／hooks 接線（parked ①）一起排進這一批，還是維持為 Phase 3b 的前置條件另做。

### 14.5 限制

- R2 在 Python 3.12 的行為未驗證；若本機沒有 3.12，只能以文件與 3.14 的實測推論，結論標 NOT TESTED。
- 這批都是低嚴重度項目，沒有已知的資料損失風險；做與不做的差別是測試的可信度與維護成本。

## 15. 修正第二批：R1、R2 完成與決定（2026-10-23）

使用者回覆「其他依據建議」：R2 的 symlink 政策採拒絕（建議）；CI 與 hooks 接線維持獨立任務，不混進這批。執行者：Claude Code（Opus 5.5）。起點 `6bfc2fa8`。

| 項目 | 先紅 | 修改 | 結果 |
|---|---|---|---|
| R1 孤立 handoff 標題 | `test_no_handoff_heading_when_no_item_is_usable` 紅 | `agent_outputs` 先收集有效項目，至少一項才輸出標題；Claude wrapper 與 Codex 檔共用 | 綠；既有 agent 的輸出沒有變化 |
| R2 symlink | 紅 3 項：預期輸出路徑是 symlink 時被寫穿、`--check` 不報、帶 marker 的 symlink 檔被刪 | 預期輸出路徑上的 symlink 視為衝突；`--check` 報 `symlink <path>`；`generated_files` 改用 `os.walk(followlinks=False)`，不回傳 symlink、不進入 symlink 目錄 | 綠 |

驗證：全部測試 537 passed；用 `uv run --python 3.12 --with pytest` 在 **Python 3.12.15（CI 版本）**重跑也是 537 passed（本機預設是 3.14.3）；重新生成 175 個檔案，生成物無差異；`--check` exit 0。
附帶發現：Python 3.12 與 3.14 的 `rglob` 對「指向目錄的 symlink」行為一致（不進入），所以先前 spike 的擔憂（行為隨版本改變）在這個情境沒有發生；改用 `os.walk` 是為了讓行為不依賴 Python 版本，不是修一個已發生的錯誤。

R3 到 R6 尚未做。未 commit。

## 16. 評估：issue 統合與平行作業（2026-10-23，尚未決定）

使用者的問題：我有很多 issue、很多平行 session，能否每次啟動一個功能修改，就統合相關 issue 需求、建立 agent teams 平行作業，不用看那麼多 chat session 或 terminal。標示：**文件描述**（官方文件，本機未驗證）、**本機實測**、**NOT TESTED**。

### 16.1 現況（本機實測）

- `gh` 已登入；開放 issue 76 個，其中 47 個已有 `spec:<slug>` 標籤，涵蓋 13 個 spec（`llm-cost-reset` 11、`evaluation-framework` 11、`people-ground-truth` 6、`japan-scope-gate` 5、`ai-portability-followups` 5 等）；29 個沒有 spec 標籤，多數是 scraper 來源問題（例如 #367、#375、#376、#377）。`spec:ai-harness` 已有 1 個（#420）。
- 所以「issue 對應 feature」的分組機制**已經存在**（`spec:<slug>` 標籤對應 `docs/specs/active/<slug>/`）；缺的是啟動時把它們彙整進 proposal／tasks 的步驟。

### 16.2 官方文件對「不用看很多 terminal」的描述（文件描述）

| 機制 | 說明 | 與本 repo 規則的關係 |
|---|---|---|
| Agent view（`claude agents`，研究預覽） | 一個畫面列出所有背景 session 與狀態（Needs input、Working、Ready for review、Completed…），可 peek 回覆、attach；完成或需要輸入時發終端通知；`--json` 可給腳本 | **最直接解決「很多 terminal」**。但：派出的 session 預設會自己搬進 `.claude/worktrees/<name>/`（`worktree-<name>` 分支），與 repo 的 `ttr-<slug>-worktree` 命名衝突；文件說「已在 linked worktree 內則跳過隔離」，所以從我們用 git 建的 worktree 派出就不會另建。文件還說 session 完成後會 commit、push 分支並可能開 draft PR（不會推 main）——與「push 由使用者執行」「commit 經核准」衝突，**對 linked worktree 是否同樣會做，NOT TESTED** |
| Agent teams（實驗） | lead 加 teammate，共用 task list 與 mailbox | **不隔離 worktree**，teammate 共用 lead 的目錄，必須切分檔案；一個 session 一個 team，不能 resume；token 隨人數線性增加。所以只適合「同一個 spec、同一個 worktree 內、檔案不重疊」的工作，不適合跨功能平行 |
| Dynamic workflows（`/workflows`） | 用腳本跑大量 subagent 並交叉驗證 | 適合唯讀的 fan-out（讀 N 個 issue、分群、去重、起草 proposal），需使用者明確要求 |
| Cross-session messaging | 同機 session 互傳純文字 | 已在 Phase 2a 的治理文件採用 |
| Projects（雲端 threads，公開 beta） | 一個長期對話，Claude 開平行 thread 並顯示哪些需要你 | 最接近「不用看多個 session」，但在雲端跑，本機 secrets、worktree、hooks 的行為 **NOT TESTED**，也牽涉 D4' 的 secrets 規則，不建議現在做 |
| Codex | `codex agents` 可瀏覽共用 daemon 上的所有 session | 只涵蓋 Codex session |

### 16.3 能做與不能做

- 能：啟動時依 `spec:<slug>` 標籤用 `gh issue list` 取出相關 issue，加上關鍵字搜尋補漏，去重、分群，對應到 `tasks.md`，在 `proposal.md` 寫「涵蓋的 issue」連結；這是唯讀、便宜、不需要 agent teams 的步驟。
- 能：把互不相干的功能各自放在 git 建立的 worktree，用 agent view 派出並集中監看。
- 不能做到「完全不看」：權限提示（`git push` 要核准、hooks 的 ask）要 attach 才能回答；push、部署、D 類裁決依規則仍是人工；agent view 的 peek 回覆不能代替權限對話框（文件描述）。
- 限制：agent view 是研究預覽、agent teams 是實驗功能；agent view 是否能在 VS Code 擴充內使用，文件我讀到的部分沒提，**NOT TESTED**（至少可在 VS Code 的整合終端機以 `claude agents` 啟動，也未驗證）；平行度越高，配額消耗越快，plan §3.1 的條件 (d) 仍然適用。
- 一個重要的區別：「統合 issue 成一個功能」是**規劃**問題，「平行實作」是**執行**問題。前者幾乎不需要平行 agent；後者在跨功能時用多個 worktree，在同一功能內用 teams，兩者的隔離機制不同，不要混用。

### 16.4 我的評估

可行，但最划算的是分三段，且每段獨立可停：

1. **Kickoff 彙整（便宜，建議先做）**：一個 prompt／skill，輸入 spec slug 或主題，輸出「涵蓋 issue 表、去重結果、對應的 tasks、尚未有 spec 標籤的相關 issue」並寫進 `proposal.md`；唯讀。需要同時處理 29 個沒有 spec 標籤的 issue（建議先盤點歸屬，不自動貼標籤）。
2. **跨功能平行（中等，需先試）**：用 `claude agents --cwd <git 建立的 worktree>` 或在該 worktree 內 `claude --bg` 派 2 到 3 個 session；先做一次受限試驗，驗證：hooks 是否載入、`git push` 是否變成 Needs input、完成後是否自己 commit／push、peek 與 attach 的實際操作。
3. **同功能內 agent teams（最後）**：只對檔案互不重疊的任務；實作型的切分尚未驗證（spike 只驗證了唯讀審查）。

### 16.5 需要使用者決定

- 要不要做第 1 段，以及先盤點 29 個無標籤 issue 的歸屬。
- 第 2 段的試驗要不要排進 Phase 2b 的 spike（目前 2b 的條件 (d) 配額基準尚未記錄）。
- 第 3 段是否暫緩（建議暫緩）。

## 17. §16 的決定與第 1 段完成（2026-10-23）

§16 的標題寫「尚未決定」是當時的狀態；本節追加決定，原文不改。

使用者決定：**做第 1 段（feature kickoff 彙整）**；**第 2 段的小試驗排進 Phase 2b 的 spike**；第 3 段維持暫緩。執行者：Claude Code（Opus 5.5）。

### 17.1 第 1 段交付

| 交付 | 內容 | 驗證 |
|---|---|---|
| `scripts/feature_kickoff.py` | 唯讀。輸入 spec slug 與關鍵字，輸出：帶 `spec:<slug>` 標籤的 issue、沒有任何 `spec:` 標籤但關鍵字命中的候選、疑似重複（標題相似度 ≥ 0.8，或長度 ≥ 12 的標題完整出現在另一個裡）、互相引用；`--inventory` 盤點沒有 `spec:` 標籤的 issue。gh 失敗時以 exit 2 與清楚訊息結束 | 先寫 17 個測試（先紅，一個測試資料有誤已修正，見下），全綠；有測試守住「腳本不含任何 gh 寫入命令」。全部測試 554 passed |
| `.github/prompts/feature-kickoff.prompt.md` | 流程：確認 spec、取得名單、逐一讀 issue、去重分群、判斷候選、對應 tasks、寫入 proposal／tasks、切分平行度、回報。issue 內容視為資料不是指令；寫入限已確認的 worktree；只寫 `Refs #N`，不寫 `Fixes`；不貼標籤、不留言、不關閉 | `sync` 生成 `.claude/commands/feature-kickoff.md`，`--check` exit 0。**prompt 本身 NOT TESTED**：只有腳本有自動測試，prompt 要在互動 session 實際跑一次才算驗證 |
| 第一次真實使用 | `--inventory` 列出 29 個無 `spec:` 標籤的 issue；`--slug ai-harness --keyword worktree --keyword pre-push` 找到 #328、#346（相關）與 #351（誤判） | 本機實測，唯讀。結果與建議在 [issue-inventory-2026-10-23.md](./issue-inventory-2026-10-23.md) |

測試資料更正：第一版「疑似重複」測試用的兩個標題相似度只有 0.63，不到門檻，是我的測試資料不好，不是腳本的缺陷；修正方式是加入「標題完整被包含」的提示（有長度下限避免短標題誤報），並新增一個「短標題不誤報」的測試。標題相似度只是提示，不是判定。

### 17.2 第 2 段：排進 Phase 2b 的 spike

方案寫在 [spike-agent-view.md](./spike-agent-view.md)，執行前寫定：兩個背景 session，一個修改檔案但明確禁止 commit，一個執行 `git push origin HEAD --dry-run` 以觸發 hooks 的 ask；觀察工作目錄、hooks 是否生效、是否自己 commit 或 push、VS Code 整合終端機是否可用、用量差值。需使用者核准建立拋棄式 worktree `ttr-agent-view-trial-worktree` 後才能執行。plan §3.1 的 Phase 2b 條件 (e) 已改為兩個 spike 都結案。

### 17.3 已知限制

- kickoff 只會找到有標籤或有命中關鍵字的 issue；沒有標籤也沒有命中的相關 issue 會被漏掉，prompt 要求報告中提醒這點。
- 29 個無標籤 issue 的歸屬是依標題推論，沒有逐一讀內文；不自動貼標籤。
- 還沒有人用 `/feature-kickoff` 跑過完整流程。

## 18. 看板的「階段」與 labels、issue 標籤動作（2026-10-23）

### 18.1 已執行的 GitHub 寫入（使用者明確要求）

| 動作 | 結果 |
|---|---|
| `gh issue edit 328 --add-label spec:ai-harness` | #328 現在的標籤：`enhancement`、`spec:ai-harness` |
| `gh issue edit 346 --add-label spec:ai-harness` | #346 現在的標籤：`spec:ai-harness`（原本沒有標籤） |

沒有其他 issue 被貼標籤，也沒有修改看板欄位。QA Heartbeat 的 5 個 issue 依使用者決定保留，沒有動作。

### 18.2 看板現況（本機實測，唯讀）

看板：TTR Roadmap（<https://github.com/users/TuiTuiKoan/projects/1>），96 個項目，全是 issue（open 76、Done 20）。
欄位：除了內建欄位，自訂的有 `Status`（Todo、In Progress、Done；目前 In Progress 為 0）與 `階段`（單選，10 個選項：止血、PR 分層、成本、Eval、追蹤清理、架構圖、來源 intake、QA heartbeat、AI工具鏈、資料修復）。
看板 README 的分工：Status 是進度；階段對應 roadmap 的各節；spec 看「為什麼、做什麼」，過程中增生的細項與 bug 開 issue 並貼 `spec:<slug>`；PR 的 `tier:` label 看合併方式（tier:0 自動合併、tier:1 一鍵合併、tier:2 完整 review）。

實際使用（96 個項目的交叉統計）：

| 階段 | 數量 | 與 `spec:` 標籤的關係 |
|---|---|---|
| 成本 | 11 | 全部是 `spec:llm-cost-reset`（該 spec 共 13 個，另 2 個沒設階段） |
| AI工具鏈 | 5 | 全部是 `spec:ai-portability-followups`（5 個全有） |
| PR 分層 | 1 | `spec:pr-flow-tiering` |
| 資料修復 | 2 | `spec:authoritative-venue-repair`、`spec:japan-scope-gate` 各 1 |
| Eval | 4 | 都沒有 spec 標籤（#324–#327，Done）；而 `spec:evaluation-framework` 的 14 個 issue 全都沒設階段 |
| 來源 intake | 6 | 都沒有 spec 標籤（有 `source-intake` 標籤） |
| QA heartbeat | 5 | 都沒有 spec 標籤 |
| 止血 3、追蹤清理 4、架構圖 1 | 8 | 都沒有 spec 標籤 |
| **沒有階段** | **54** | 36 個有 spec 標籤、18 個沒有 |

觀察：42 個有階段、54 個沒有；2026-10-22 從 roadmap 搬進來的 issue（#313 到 #339）幾乎都設了階段，之後新開的 issue（#341 起）大多沒設。成本、AI工具鏈、PR 分層這三個階段與一個 spec 一對一，等於同一件事標了兩次；Eval 階段卻和 `spec:evaluation-framework` 沒有交集。

工具的小陷阱：`gh project item-list --format json` 會把「階段」這個欄位名稱的首字壞成亂碼鍵（`���段`），用 `階段` 取值會全是空。要用程式讀這欄時，改用以「段」結尾的鍵，或走 GraphQL。

### 18.3 `scraper-zero-output` 要不要建 spec（建議，待決定）

事實：

- 相關 issue：#367（10 個來源自 2026-09 中起連續 0 產出，prtimes 之前 6 週有 1148 筆；issue 自己推測「可能有共同原因（runner、依賴版本、網站改版或封鎖）」）、#381（30 個「28 天以上 0、原因未知」的來源，接續已完成的 #327）、#375、#376、#377（個別來源）。兩個彙總 issue 都已有明確做法與完成條件。
- 本機有 worktree `ttr-scraper-zero-output-worktree`（分支 `fix/scraper-zero-output`），**但它是空的**：乾淨、沒有任何 commit、與 origin/main 沒有差異；docs/specs/active 裡也沒有對應的 spec。它不是本 session 建立的，沒有動它。
- 看板 README 的原則：spec 只放 why、what 與不超過十條里程碑；細項與 bug 開 issue 並貼 `spec:<slug>`。

建議：**建立一個很薄的 spec**（proposal 加不超過 6 條里程碑，tasks 只放決策規則），理由：(1) #367 自己懷疑有共同原因，需要一個地方記錄「修、確認是自然的 0 件、還是退役」的決策規則與結論；(2) 涉及 CI、爬蟲程式、`scraper/source_expectations.json` 與 `docs/evaluation/scrapers/`，不是單一來源的修補；(3) 讓 `spec:scraper-zero-output` 標籤把 #367、#375、#376、#377、#381 分在一起，之後 `/feature-kickoff` 與看板都能依標籤找到。每個來源的實際工作仍然是 issue，不是 spec 的任務。

不建議把另外 6 個爬蟲管線缺陷（#364、#394、#395、#398、#404、#407）併進去：它們是彼此獨立的程式缺陷，各自開 issue 處理即可。

反方：如果第一步查 prtimes 就發現每個來源原因都不同，spec 的價值會降低，issue 單獨管理就夠；這個判斷要等查過才知道，所以 spec 要保持薄。

### 18.4 其餘無標籤 issue 補「階段」（建議，待決定）

「依盤點補階段」的可行範圍：

- 現有 10 個選項中，只有 **#346（pre-push gitleaks）適用「AI工具鏈」**，且與剛貼上的 `spec:ai-harness` 同方向；#328 已是「追蹤清理」，不改。
- 盤點的其他群沒有對應選項：來源產出為 0（#367、#375、#376、#377、#381，若建 spec 則同上）、爬蟲管線缺陷（#364、#394、#395、#398、#404、#407）、產品與後台 UI（#342、#351）。
- 命名建議（沿用現有邏輯：roadmap 主題的短名詞、不加前綴）：新增 **「來源健康」**（0 產出，5 個）與 **「爬蟲管線」**（6 個缺陷）；#342、#351 不設階段，因為它們是單點事項，不是 roadmap 主題。
- 為什麼新增選項要在網頁操作：單選欄位的選項要透過 GraphQL 整組更新，我沒有驗證更新時既有項目的值會不會被清掉，所以採保守做法，由使用者在看板網頁上新增；新增後我可以用 `gh project item-edit` 設定各 issue 的值。
- 尚未做：沒有修改任何看板欄位，也沒有新增選項。

## 19. 看板新增階段選項、agent view 試驗 worktree、標記設計評估（2026-10-23）

使用者核准：建立拋棄式 worktree；採用「來源健康」「爬蟲管線」；核准 commit。並提問：針對看板標記的落差，是否可以更好地規劃，還是不用管、讓 LLM 自動盤點。執行者：Claude Code（Opus 5.5）。

### 19.1 拋棄式 worktree

`ttr-agent-view-trial-worktree`：分支 `feat/agent-view-trial`，起點 origin/main `92a5bd45`（fetch 後），`.git/info/exclude` 對帳 converged，工作樹乾淨，有 hooks 檔案。注意：從 linked worktree 內執行對帳片段會讀不到 `.git/info/exclude`（linked worktree 的 `.git` 是檔案），必須在主工作目錄執行。

### 19.2 新增階段選項：先實測再動真實看板

我原本打算請使用者在網頁新增，因為不確定 API 更新選項時會不會清掉既有項目的值。改為先驗證：

| 步驟 | 結果（本機實測） |
|---|---|
| GraphQL 介紹 | `ProjectV2SingleSelectFieldOptionInput` 有 `id`、`name`、`color`、`description` 四個欄位，更新時可以傳入既有選項的 `id` |
| 臨時私人 project 實測 | 建立 `tmp-option-test-DELETE-ME`（編號 2），建立單選欄位與一個項目並設值，再以 `updateProjectV2Field` 傳入「既有選項附 id、外加一個新選項」：既有選項 id 不變、項目的值保留、新選項加入。實測後已刪除，`gh project list` 只剩 TTR Roadmap |
| 真實看板 | 先備份 96 個 issue 的階段值到 `~/.ai-notes/ttr/board-stage-backup-2026-10-23.json`；更新後逐一比對：既有選項 id 與名稱不變、96 個值不變；再設定 12 個 issue。結束時比對：原有 42 個值全部未動，現在共 54 個有階段 |

新增選項：「來源健康」（ORANGE，來源連續 0 產出或原因未知的健康問題）、「爬蟲管線」（PINK，爬蟲管線本身的缺陷與守門問題）。設定的 issue：#367、#375、#376、#377、#381 → 來源健康；#364、#394、#395、#398、#404、#407 → 爬蟲管線；#346 → AI工具鏈。沒有設階段的：#342、#351（單點事項，依先前建議），以及 #421（每日提醒 issue）。

結論更正：§18.4 寫「新增選項要在網頁操作」是保守假設；實測證明傳入既有選項的 `id` 可以安全更新。這個做法只在「傳入全部既有選項與其 id」時成立，少傳一個既有選項的 id 會有什麼後果，我沒有測。

### 19.3 落差的成因（本機實測，唯讀）

| 落差 | 成因 |
|---|---|
| 覆蓋率（42／96，現 54／96） | 階段是 2026-10-22 搬遷 roadmap 時一次性手動設的；之後建 issue 的路徑（agent、`gh issue create`、人工）沒有任何一步會設階段。看板的 Auto-add 只負責加入，不設欄位 |
| 重複標記 | 成本、AI工具鏈、PR 分層三個階段與一個 spec 一對一：階段與 spec 在這三處是同一軸 |
| 沒對上 | Eval 階段在 spec 之前就存在，後來的 `spec:evaluation-framework`（14 個）與 `spec:people-ground-truth`（6 個）都沒回頭設階段；兩者是平行長出來的 |
| 名稱 | 選項是主題，不是依序的階段；只有「止血」是真正的階段 |

### 19.4 評估：要不要規劃，還是讓 LLM 盤點（建議，待決定）

結論：**兩個都不是最好的答案**。不用管會讓覆蓋率繼續掉；全交給 LLM 則把一個大部分可以用規則決定的事變成每次都要花配額、結果還會漂移的判斷。建議「規則決定能決定的，LLM 只處理剩下的，人確認」。

1. **先定義兩個軸各回答什麼問題**
   - `spec:<slug>`：這個 issue 屬於哪份 spec（精確、對應文件，建立時就貼）。
   - 階段（建議改名為「主題」）：我在看板上要在哪個區塊找到它（用來分組與篩選）。
   - Status：進度。類型標籤（scraper、bug、documentation…）：工作性質。
   - 為什麼需要第二個軸：我沒有驗證 Projects 能不能依 label 分組；若不能，階段欄位就是為了分組而存在，而不是為了表達 spec。
2. **讓主題比 spec 粗，並由 spec 推導，不逐個 issue 手填**：多個 spec 對應到少數主題，所以主題回答的是「領域」而 spec 回答的是「文件」，兩軸才不重複。維護一張 spec 到主題的對照表（單一來源），有 `spec:` 標籤的 issue 其主題由對照表決定。草案如下，**只是我的提案**：

   | spec | 建議主題 | 把握 |
   |---|---|---|
   | `llm-cost-reset` | 成本 | 高（11／13 已如此） |
   | `ai-portability-followups`、`ai-harness` | AI工具鏈 | 高（前者 5／5 已如此） |
   | `pr-flow-tiering` | PR 分層 | 高 |
   | `evaluation-framework`、`people-ground-truth` | Eval | 中（#393 就叫「eval stage 3 後續」） |
   | `japan-scope-gate`、`authoritative-venue-repair` | 資料修復 | 中（已各有 1 個如此） |
   | `workstream-tracking`、`closer-auto-retire`、`admin-qa-cleanup` | 追蹤清理？ | 低，需要決定 |
   | `publication-policy`、`ndl-relevance-publication` | 沒有現成主題 | 低，需要決定 |
   | `scraper-zero-output`（若建立） | 來源健康 | 高 |
3. **一支唯讀的稽核腳本**（沿用 `feature_kickoff.py` 的載入方式；階段欄位必須走 GraphQL，因為 `gh project item-list` 會把鍵弄成亂碼）：列出沒有主題的 issue、主題與對照表不一致的 issue、對照表沒有的 spec、沒有 spec 也沒有主題的 issue。預設只報告；`--apply` 只對「對照表可決定」的列設定，且需確認。
4. **LLM 只做剩下的**：沒有 spec 標籤、也沒有對照表可套的 issue，由 LLM 提議主題或「需要新主題」並附一句理由，**人確認後才寫入**。理由：這次盤點中，關鍵字就產生過誤判（#351），LLM 也可能誤判；誤判會讓看板分組悄悄出錯；多次執行結果也可能不一致。
5. **在哪裡跑**：`/feature-kickoff` 與既有的每週回顧（`weekly-review`）各加一步；先不做 GitHub Action。我所知使用者帳號擁有的 Projects v2 無法用 `GITHUB_TOKEN` 寫入，需要放一個有 project 權限的 PAT 到 secrets，會牽涉 `token-rotation` 的輪替規則；我沒有驗證這點，所以不建議現在做。
6. **改名**：階段改名為「主題」可以去掉「依序」的誤導，也和 workstream-tracking 的 A 到 E「工作線」分開。代價：README、舊文件與任何以名稱讀取該欄位的程式要同步更新（本 session 的腳本就用名稱 `階段` 取值）。

成本與限制：對照表加稽核腳本加測試是小工程（沿用現有載入與測試方式）；對照表需要人維護，新增 spec 時要同步一行，稽核會提醒缺漏；低把握的 5 個 spec 需要使用者先決定主題；沒有實測過稽核腳本，也沒有評估看板可否依 label 分組。

### 19.5 需要使用者決定

1. 是否採用「主題比 spec 粗、由 spec 推導」的方向。
2. 是否把「階段」改名為「主題」。
3. 對照表草案中低把握的列要怎麼歸。
4. 是否做稽核腳本與每週回顧的一步（建議做，且不做 GitHub Action）。

## 20. agent view 試驗：第一次嘗試與重置（2026-10-23）

使用者回報：忘了先輸入 `/usage` 量測前置用量，想重置 agent view 但關不掉。執行者：Claude Code（Opus 5.5）。

### 20.1 第一次嘗試留下的觀察（本機實測，來自 `claude agents --json`、session transcript 與 `git`）

| 觀察 | 結果 |
|---|---|
| O1 工作目錄 | 兩個背景 session 的 `cwd` 都是 `ttr-agent-view-trial-worktree`；`.claude/worktrees/` 不存在；沒有多出新的 worktree。**成立** |
| 提示 A（改檔案） | 在試驗 worktree 建立 `docs/_agent-view-trial.md`（內容 `trial A`），回報「未 commit」。`git status` 只有該未追蹤檔；`git log origin/main..HEAD` 為 0；遠端沒有 `feat/agent-view-trial`。**沒有自己 commit 或 push（O4 的初步證據）** |
| 提示 B（`git push origin HEAD --dry-run`） | transcript 只有該 Bash 的 tool_use，沒有結果；session 狀態為 `waiting`。**hooks 的 ask 在背景 session 生效的證據（O2 的初步證據）**；session 自己也寫「依專案規則應會觸發核准提示」 |
| 用量差值 | 未記錄前置用量，**無法量測** |
| O3（peek 回覆是否能答權限）、O5（VS Code 整合終端機、通知）、O6（狀態是否相符） | 我沒有觀察到；使用者的主觀記錄未提供，維持 NOT TESTED |

限制：O2、O4 是在約 6 分鐘後的瞬間狀態，不是完整生命週期；A 結束後我沒有觀察更久，所以「完成後不會自己 commit 或 push」只證明到那個時間點。

### 20.2 為什麼關不掉，以及怎麼重置

- agent view 的背景 session 由獨立的 supervisor 程序執行（本次是 `claude daemon run --origin transient`，由 `claude agents` 啟動）；關掉終端機分頁不會停止 session。
- 離開 agent view：`Esc` 回到 shell（若是用 `←` 從對話進入則回到該對話）、`Ctrl+C` 按兩次、或輸入 `/exit`、`/quit`（文件描述）。離開不會停止 session。
- 停止 session：`claude stop <id>`。**這個 `<id>` 是 8 碼短 ID（如 `ad7c5b69`），不是完整 session ID**；用完整 ID 會得到 `No job matching`，我第一次就踩到。移除：`claude rm <id>`（對話紀錄保留，可用 `claude attach`／`--resume`）。停止 supervisor 與其背景 session：`claude daemon stop --any`。
- 本次執行：`claude stop ad7c5b69`、`claude stop 71b76964`、對兩者 `claude rm`、`claude daemon stop --any`；之後確認背景 session 為 0、daemon 為 not running、相關程序已消失。使用者其他 36 個互動 session 沒有受影響。`claude agents --json` 這類指令本身可能重新啟動一個 transient supervisor，用完要再停。
- 清理：刪除試驗檔 `docs/_agent-view-trial.md`（內容與校驗碼前綴 `ecff734b` 已記錄）。試驗 worktree 現在乾淨、沒有 commit、遠端沒有分支。

### 20.3 重跑

依 [spike-agent-view.md](./spike-agent-view.md)「第一次嘗試與重跑登記」：相同提示詞與條件；**先記錄 `/usage` 再開 agent view**；判定採用重跑，第一次保留作對照。

## 21. agent view 重跑的觀察（2026-10-23，進行中，使用者回報加上本機查證）

重跑於 13:04:52（A）與 13:04:57（B）開始；13:07:52 查證時 A 為 idle、B 為 waiting。以下 O3 與 O6 是使用者的主觀回報，O1、O2、O4 是我的本機查證（唯讀）。

| 觀察 | 結果 | 來源 |
|---|---|---|
| O1 工作目錄 | 兩個背景 session 的 `cwd` 都是 `ttr-agent-view-trial-worktree`；`.claude/worktrees/` 不存在。**成立** | `claude agents --json`、`ls` |
| O2 hooks／ask 規則在背景 session 生效 | B 停在權限對話框：`Ask rule Bash(git push *HEAD *) overrides auto mode for this command`，選項 1. Yes、2. No。**成立**，並顯示背景 session 跑在 auto mode，ask 規則仍然壓過 auto mode | 使用者貼上的對話框 |
| O3 peek 面板能否答覆權限 | **不能**：空白鍵的 peek 面板沒有選項，必須按 `→` 進入（attach）才看得到對話框。與文件描述一致 | 使用者回報 |
| O4 沒有自己 commit 或 push | A 完成後（Completed）：`git status` 只有未追蹤的 `docs/_agent-view-trial.md`；`git log origin/main..HEAD` 為 0；遠端沒有 `feat/agent-view-trial`。**成立（至查證時刻）** | `git` |
| O6 狀態是否相符 | 完成顯示為 `Completed`，行內有一句摘要與耗時（`18s`）；需要輸入顯示為 `Needs input`，行內寫 `approve Bash: git push origin HEAD --dry-run`，並顯示等待時間（`1m`）。與實際相符 | 使用者回報 |
| O5 通知 | 使用者尚未回報 | — |
| O7 用量 | 使用者尚未回報前後數字 | — |

意義：背景 session 能被集中看到狀態，但**需要核准的動作一定要人進入該 session 才能回答**，peek 不能代勞。這正好印證 notes.md §16.3「不能做到完全不看」；也就是 agent view 解決的是「看哪些 session 在等我」，不是「不用回答」。

### 21.1 規則的來源與一個 rebase 風險

對話框裡的規則 `Bash(git push *HEAD *)` 來自試驗 worktree 的 `.claude/settings.json`（起點是 origin/main）。origin/main 在 `0df5d775`（chore(claude): narrow the push ask rules to main-like destinations）把 `Bash(git push:*)` 縮窄成六條只針對 main 類目的地的規則：`git push`、`git push origin`、`git push *main`、`git push *main *`、`git push *HEAD`、`git push *HEAD *`。我們 ai-harness 分支的 `.claude/settings.json` 還是舊的 `Bash(git push:*)`。

因此 ai-harness 分支需要 rebase：領先 origin/main 10 個 commit，落後 128 個；兩邊都改過 12 個檔案：`.claude/agents/plan-critic.md`、`.claude/agents/validate-merge-deploy.md`、`.github/agents/` 下的 7 個檔案、`.github/instructions/git.instructions.md`、`AGENTS.md`、`scripts/sync_ai_adapters.py`。我沒有嘗試 rebase，也沒有評估衝突的難度；`sync_ai_adapters.py` 兩邊都改過是最需要注意的一個。生成物（`.claude/agents`、`.codex`）應該在解完衝突後重新生成，不要逐行合併。這屬於 V-M-D 之前的步驟，時機需使用者核准。

## 22. agent view 試驗結果與判定（2026-10-23）

使用者完成重跑並回報。核對者：Claude Code（Opus 5.5），事後唯讀查證與清理。

### 22.1 用量（S4）

| | session（5 小時） | 週（all models） | 週（Fable） |
|---|---|---|---|
| 開始前（13:04，Account & Usage 頁） | 5% | 31% | 8% |
| 結束後（`/usage`） | 7% | 31% | 8% |
| 差值 | +2 | 0 | 0 |

最大差值 2 個百分點，在上限 3 以內，**S4 成立**。限制：解析度 1 點；百分比是帳號層累計，**本 session 在重跑期間也在工作**（13:05 到 13:10 有多次工具呼叫與寫入），所以 +2 是試驗本身的上界，不是精確值；結束後的 `/usage` 貼的是另一個 session（Fable，$0.76）的面板，該面板的花費不是兩個背景 session 的花費。**方案是 Max**（見 22.4）。

### 22.2 觀察與條件

| 條件 | 結果 | 證據 |
|---|---|---|
| S1（O1）工作目錄是試驗 worktree，沒有 `.claude/worktrees/` | **成立** | `claude agents --json` 的 `cwd`；`ls` |
| S2（O2）背景 session 的 hooks／ask 生效，且拒絕後 push 沒有被執行 | **成立** | 對話框 `Ask rule Bash(git push *HEAD *) overrides auto mode`；使用者選 No；B 的 transcript 結果為 "The user doesn't want to proceed with this tool use. The tool use was rejected"；畫面顯示 `Interrupted · What should Claude do instead?` |
| S3（O4）沒有未被要求的 commit 或 push | **成立**（至查證時刻：A 完成後約 5 分鐘以上） | `git status` 只有未追蹤檔；`git log origin/main..HEAD` 為 0；遠端沒有 `feat/agent-view-trial` |
| S4 用量 | **成立** | 22.1 |
| S5 一個畫面監看兩個 session，除權限對話框外不必 attach | **待使用者明確確認**（依回報推論成立：狀態都顯示在畫面上；需要 attach 的只有權限對話框） | 使用者回報 |
| O3 peek 能否答覆權限 | **不能**，空白鍵的 peek 沒有選項，必須按 `→` 進入 | 使用者回報 |
| O5 通知 | **沒有**：VS Code 整合終端機沒有特別通知，只有畫面顯示 | 使用者回報 |
| O6 狀態相符 | 相符：`Completed`（行內有摘要與 `18s`）、`Needs input`（行內 `approve Bash: git push origin HEAD --dry-run`、`1m`） | 使用者回報 |

停止條件：沒有觸發（沒有實際 push、沒有修改試驗 worktree 以外的檔案、沒有超過 15 分鐘、用量未超過 5 點）。

### 22.3 判定與限制

**判定（暫定，待 S5 確認）：可列入 Phase 2b 正式使用，不是採用。**

這個結果能說明：從 git 建立的 linked worktree 派出的背景 session 維持該 worktree，不會另建 `.claude/worktrees/`；repo 的 ask 規則在背景 session（auto mode）仍然生效並壓過 auto mode；拒絕後動作不會執行；完成的 session 沒有自己 commit 或 push；成本很小。

不能說明（仍 NOT TESTED）：
- **無通知**：在 VS Code 整合終端機裡沒有通知，「不用一直看」並沒有達成；你仍然要定期看畫面。官方文件描述 agent view 開著時會觸發 `Notification` hook（`agent_needs_input`、`agent_completed`），可以用 hook 補上桌面通知，我沒有試過。
- **兩個 session 在同一個 worktree**：這次兩個 session 都在同一個試驗 worktree。若兩個都會修改檔案，agent view 在 linked worktree 內不再隔離（文件描述），它們會互相覆蓋。真正的跨功能平行需要「每個功能一個 worktree、各自派出」；**同一個 agent view 能不能看到來自不同 worktree 的 session、要怎麼從不同 worktree 派出，沒有測**。官方文件說清單是全機器的（本次 `--json` 也列出 36 個互動 session），但派發位置是 agent view 開啟時的目錄。
- **只驗證了極小的工作**：A 只是建立一個檔案；沒有驗證會修改多個檔案、跑測試、跑很久的工作，也沒有驗證非 dry-run 的 push 被拒絕後的行為。
- **背景 session 跑在 auto mode**：它能自動執行很多命令而不問；ask 規則與 hooks 仍會擋，但這是它與互動 session 不同的地方，使用時要知道。
- 觀察時間短（約 10 分鐘）；只跑一次。

### 22.4 方案是 Max，不是 Pro

`/usage` 的 Account 頁寫 `Plan: Claude max`，`claude auth status` 回 `subscriptionType: max`；2026-10-15 我查到的是 `pro`。方案何時變更不知道。影響：plan §1.1 與 §4 假設 Pro 的敘述已更新註記；配額上限比我先前推論的高，但門檻仍以實測 `/usage` 為準，不因方案變動而放寬。記憶檔 `user-ai-tooling-setup` 已更正。

### 22.5 清理

兩個試驗背景 session 已 `claude stop` 與 `claude rm`，`claude daemon stop --any` 已執行，沒有殘留程序；試驗檔 `docs/_agent-view-trial.md` 已刪除；試驗 worktree 乾淨、沒有 commit、遠端沒有分支。worktree 與分支本身還在，未退役。

## 23. S5 確認與接下來的順序（2026-10-23）

使用者確認 S5 成立，agent view 小試驗的最終判定為**可列入 Phase 2b 正式使用，不是採用**（§22.3 的限制仍然有效）。使用者並決定：ai-harness 分支要 rebase；核准 commit；並提問是否需要先 V-M-D 推送，因為 `docs/specs/active/ai-harness/` 目前不在 GitHub 上。

事實：這個 spec 與全部 ai-harness 的 commit 都只在本機分支 `feat/ai-harness`（領先 origin/main 12 個 commit，落後 128 個），從未 push。GitHub 上帶 `spec:ai-harness` 標籤的 issue（#328、#346、#420）因此指向一個 main 上不存在的 spec。順序與理由見 §24。

## 24. rebase 與推送前的閘門（2026-10-23）

更正：§23 寫「領先 origin/main 12 個 commit」是筆誤；rebase 前實際是領先 11 個、落後 128 個（含 §23 當時的 commit）。

### 24.1 rebase（使用者核准）

起點：rebase 前的 HEAD 是 `0cd4b237`（docs(specs): record the agent-view trial verdict and the ai-harness branch state）。`git rebase origin/main`，11 個 commit 中 3 個有衝突，都只是內容衝突：

| 衝突的 commit | 檔案 | 處理 |
|---|---|---|
| Phase 1（`tier`） | `.github/agents/validate-merge-deploy.agent.md`、`.github/agents/plan-critic.agent.md` | main 改寫了 `description`（V-M-D 改為「交付推送指令、使用者推送後驗證部署」；plan-critic 改為「透過 Codex read-only 執行，不當作 Claude subagent」）；保留 main 的 `description`，加上我們的 `tier: build`／`tier: plan` |
| Phase 1（`tier`） | `AGENTS.md` | main 把 push 的 ask 規則改寫成縮窄版；保留 main 那一條，並保留我們「新增 agent 必須加 `tier`」的那一條 |
| rev.3 | `AGENTS.md` | 保留 main 的兩條，並把我們的「Plan Critic 的批評全文必須存檔」放在中間（移除與 main 重複的 VS Code Copilot 句子） |

每次解完衝突都重新執行 `python3 scripts/sync_ai_adapters.py` 重生成 `.claude/`、`.codex/`，不逐行合併生成物。

結果：`feat/ai-harness` 領先 origin/main 11、落後 0；`sync --check` exit 0；`python3 -m pytest scripts` 967 passed（含 main 的新測試，先前我們只有 554）。限制：只驗證了 rebase 後的最終狀態，**沒有逐個中間 commit 驗證**能否單獨通過測試。rebase 前的 commit 仍可由 reflog 取回，不另開備份分支（hooks 擋 `branch -D`，備份分支之後沒辦法由我刪）。

另外：我先前 `pnpm run build` 的 prebuild 在 `web/lib/specs/` 產生了未追蹤的 `specs-snapshot.json`（main 沒有追蹤它、也沒有 ignore），已刪除，沒有提交。這表示在 worktree 裡跑 web build 會留下需要手動清理的檔案；是否該加進 `.gitignore` 沒有評估。

### 24.2 推送前閘門（V-M-D 的 Step 0 到 3，已在本機跑完，沒有 push）

| 閘門 | 結果 |
|---|---|
| 衝突檢查與 rebase | 落後 0；rebase 完成 |
| 推送範圍 | 11 個 commit、66 個檔案、+2969／−40；**沒有 `web/` 檔案**，所以跳過本機 `pnpm run build` |
| gitleaks（`origin/main..HEAD`） | 11 個 commit 掃描，no leaks found |
| 個資與密鑰字串 | 對新增行 grep（電子郵件、`gmail.com`、`ghp_`、`github_pat_`、`sk-…`、`password`）沒有命中 |
| 測試與同步 | 同上：967 passed、`sync --check` exit 0 |
| 其他分支的影響 | 15 個 worktree 分支逐一檢查：沒有任何一個動到 `.github/agents`、`sync_ai_adapters.py`、`AGENTS.md` 或 `.claude/settings.json`，所以現在推送不會讓它們因「新 agent 必須有 `tier`」而失敗 |
| 主工作目錄 | 本機 `main` 落後 origin/main 4 個 commit（GitHub 上已合併的 people-ground-truth，#392）；不影響推送，推送後要 `git pull` |

未涵蓋：Vercel deployment 要推送後才能以 exact-SHA 查；`.githooks/pre-push` 是否另外檢查是在使用者推送時才會執行，我沒有預跑。

### 24.3 要不要先 V-M-D 推送（使用者提問）與我的建議

**建議：現在推。** 理由：
1. **GitHub 上沒有這個 spec**：`docs/specs/active/ai-harness/` 只在本機分支，帶 `spec:ai-harness` 標籤的 #328、#346、#420 指向一個 main 上不存在的 spec；其他 session、Codex 與 `/feature-kickoff` 讀不到。
2. **分支漂移已經付過代價**：落後 128 個 commit，rebase 時 3 個 commit 有衝突；多放一天只會更多。
3. **其他 session 才能用到成果**：`tier` 投影、`.codex/agents`、sync 的 all-or-nothing 寫入與符號連結處理、`/feature-kickoff`、治理文件都在這 11 個 commit 裡。

風險：
- 一次推 66 個檔案、11 個 commit，其中 `AGENTS.md` 的模型政策與「新 agent 必須有 `tier`」會影響所有之後新增 agent 的 session；目前沒有分支受影響（見上表），但推送後新開的分支要遵守。
- 推送範圍沒有 `web/`，但 repo 實測 docs-only 的 push 也會產生 Production deployment（V-M-D 檔已記載），仍須以 exact-SHA 查。
- notes 內有 `~/.ai-notes/ttr/...` 與本機路徑引用，GitHub 上沒有那些檔案；已確認沒有密鑰或個資。

推送指令（依 V-M-D 規則由使用者從**主工作目錄**執行，ref 明寫分支名，行尾不加註解；不在 worktree 內執行，避免之後結案偵測誤命中）：

```bash
git -C "/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar" push origin feat/ai-harness:main
```

推送後：我用 exact-SHA 查 Vercel deployment（先看 commit status 是否 pending）；使用者在主工作目錄 `git pull`；依 `git.instructions.md` § Telling other running sessions 通知其他 Claude Code session。
