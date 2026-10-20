# Tokyo Taiwan Radar — Codex / Claude Code 轉接指南

本檔供 Codex / Claude Code 使用。專案總規則的權威來源是 `.github/copilot-instructions.md`；開始任何工作前，必須先完整讀取該檔，不要以本摘要取代原文。

最關鍵的 5 點摘要：

1. 回覆語言預設使用繁體中文。
2. 列出活動時不可只列 event id，必須提供 `https://tokyotaiwanradar.com/ja/events/<event_id>` 格式的可點擊連結；若使用者指定 locale，替換 `ja`。
3. 專案地理範圍是全日本；不要只因活動不在東京就排除。
4. 主工作樹只供治理與盤點；實作前必須先向使用者確認要用哪個 worktree，並依 `.github/instructions/git.instructions.md` 建立或切換。
5. 不得提交 secrets；任何 `.env`、token、API key 僅能留在本機或平台 secrets。

## 路徑規則表

修改下列路徑前，必須先讀對應 instruction。`**` 表示永遠適用。

| 修改路徑 | 必讀檔案 |
| --- | --- |
| `**` | `.github/instructions/token-rotation.instructions.md` |
| `.github/**` | `.github/instructions/git.instructions.md` |
| `scraper/**` | `.github/instructions/scraper.instructions.md` |
| `supabase/**` | `.github/instructions/database.instructions.md` |
| `web/**` | `.github/instructions/web.instructions.md` |

## 角色路由表

Claude Code 可直接叫用 `.claude/agents` 下的 subagent wrapper。Codex 沒有 persona 檔；使用者說「用 Architect 模式」這類指令時，請讀對應 `.github/agents/*.agent.md` 或 `.github/agents/subagents/*.agent.md` 並照做。

| 原名 | kebab 名 | 原始檔路徑 | 用途 |
| --- | --- | --- | --- |
| Architect | `architect` | `.github/agents/architect.agent.md` | 規劃架構、roadmap 與技術設計；唯讀、不改 code。 |
| Close Campaign & Retire Worktree | `close-campaign-retire-worktree` | `.github/agents/campaign-closer.agent.md` | 關閉完成的 campaign、檢查 worktree 爭用與未處理工作。 |
| Designer | `designer` | `.github/agents/designer.agent.md` | UI / visual design、theme、motion、i18n consistency 與 Recraft pipeline。 |
| Engineer | `engineer` | `.github/agents/engineer.agent.md` | 全端實作、CI/CD 與部署流程。 |
| History Teller | `history-teller` | `.github/agents/history-teller.agent.md` | 管理 `history.md`、`SKILL.md` 與 agent 文件更新。 |
| Lianbu Spokesperson | `lianbu-spokesperson` | `.github/agents/lianbu-spokesperson.agent.md` | 以小霧 / レンブちゃん人格撰寫社群貼文與回覆草案。 |
| Plan Critic | `plan-critic` | `.github/agents/plan-critic.agent.md` | 評審 Architect 計畫、指出複雜度與風險。 |
| Researcher | `researcher` | `.github/agents/researcher.agent.md` | 發掘並評估新的台灣相關活動來源。 |
| Reviewer | `reviewer` | `.github/agents/reviewer.agent.md` | 月度治理復盤，分析爬蟲健康、Skills 新鮮度與 Agent scope overlap。 |
| Scraper Expert | `scraper-expert` | `.github/agents/scraper-expert.agent.md` | 建置、除錯與驗證 scraper，並分派來源 subagent。 |
| Tester | `tester` | `.github/agents/tester.agent.md` | 執行 scraper / web 驗證並回報 pass/fail 與風險。 |
| Update History, Skill, Agent | `update-history-skill-agent` | `.github/agents/update-history-agent.agent.md` | 依最近修改更新 history、skill 與 agent 文件。 |
| Validate, Merge & Deploy | `validate-merge-deploy` | `.github/agents/validate-merge-deploy.agent.md` | 檢查衝突、rebase、commit、推送 main 與驗證部署；只有使用者明確同意後才 push。 |
| Peatix Scraper | `peatix-scraper` | `.github/agents/subagents/scraper-peatix.agent.md` | Peatix 來源 scraper subagent。 |
| TCC Scraper | `tcc-scraper` | `.github/agents/subagents/scraper-tcc.agent.md` | Taiwan Cultural Center 來源 scraper subagent。 |

## Copilot 對照表

| Copilot / VS Code 機制 | Claude Code / Codex 對應方式 |
| --- | --- |
| `runSubagent` | Claude Code：呼叫對應 `.claude/agents/<kebab>.md` subagent（Task）。Codex：若有 subagent 能力則使用對應 subagent，否則讀原始 agent 檔後依序自行執行。 |
| `vscode_askQuestions` / `ask_user` | 在對話中直接向使用者提問並等待回答。 |
| `/memories/session/plan.md`（legacy 路徑，僅供閱讀舊檔） | 優先寫到 `docs/specs/active/<slug>/`；沒有 slug 時寫到本機 `~/.ai-notes/ttr/plan.md` 並告知使用者。舊檔讀不到時，向使用者要 slug 或內容，不改讀其他位置。 |
| `semantic_search` / `grep_search` / `read_file` / `fetch_webpage` / `get_errors` | 使用 Claude Code / Codex 內建的對應搜尋、讀檔、網頁抓取與診斷工具。 |
| handoff 按鈕 | 在回覆結尾列出建議下一步 agent 與建議提示。 |
| instructions 的 `applyTo` 自動注入 | 依上方「路徑規則表」手動讀取相關 instruction。 |
| agent frontmatter 的 `model:` | 本 repo 已不再寫死模型；若在舊分支看到，一律忽略，見下方「模型政策」。 |

## 模型政策

- agents、prompts、skills 的 frontmatter（含 handoffs）**一律不寫死 `model:`**。模型會持續更新或下架，寫死會讓 agent 無法啟動（2026-09-29：所有寫死 `claude-sonnet-4-5` 的 agent 同時失效）。`python3 scripts/sync_ai_adapters.py --check` 會把寫死的模型視為錯誤。
- 模型由當下使用的工具與使用者決定：
  - Claude Code：啟動時 `claude --model <名稱或別名>`，或對話中輸入 `/model` 切換。
  - Codex：`codex -m <模型>`，或對話中 `/model`；常用組合可寫在個人的 `~/.codex/config.toml` profile（`codex -p <profile>`）。
  - VS Code Copilot：在 Chat 的模型選單選擇。
- **本機模型**：Codex 可用 `codex --oss --local-provider ollama`（或 `lmstudio`）接本機模型；Claude Code 可透過 `ANTHROPIC_BASE_URL` 指向相容 Anthropic API 的本機或自架閘道。這些是個人環境設定，放在使用者層（`~/.codex/`、shell 環境變數），不要提交到 repo。
- 需要「不同模型視角」的角色（例：Plan Critic）只描述意圖：盡量使用與撰寫者不同家族的模型；做不到時照常執行，並在報告中註明使用同一模型。
- 本機模型的能力可能較弱。涉及正式資料庫寫入、推送到 main、部署這類高風險步驟時，若目前模型無法可靠遵循 agent 規則中的驗證閘門，應停下來請使用者改用較強模型或親自確認。
- 本政策只涵蓋開發用 agents；網站與爬蟲程式內呼叫的 LLM（`scraper/`、`web/` 中的 `gpt-4o*`）另案規劃，不在此範圍。

## 角色工具限制（Claude Code）

`.github/agents/*.agent.md` frontmatter 的 `claude-role` 是 Claude Code 工具限制的唯一權威。`python3 scripts/sync_ai_adapters.py` 依角色在 `.claude/agents/<kebab>.md` 寫入 `tools:` 白名單；`full` 不寫，繼承全部工具。agent 檔的 Copilot `tools:` 不受影響，只用來做一致性檢查：Claude 白名單的能力類別不得超出 Copilot 宣告的類別。

| `claude-role` | Agent | Claude Code 工具層 |
| --- | --- | --- |
| `full` | engineer、designer、history-teller、update-history-skill-agent、peatix-scraper、tcc-scraper | 不限制（繼承全部工具） |
| `planner` | plan-critic | 禁用 Edit／Write／NotebookEdit；保留 Bash 做唯讀診斷 |
| `tester` | tester | 禁用 Edit／Write／NotebookEdit；保留 Bash 執行測試 |
| `vmd` | validate-merge-deploy | 禁用 Edit／Write／NotebookEdit；保留 Bash 執行 git 與驗證 |
| `closer` | close-campaign-retire-worktree | 禁用 Edit／Write／NotebookEdit，沒有 web 工具；保留 Bash |
| `readonly` | lianbu-spokesperson | 只有 Read、Grep、Glob、WebFetch |
| 未投影 | architect、reviewer、researcher、scraper-expert | 權限衝突待裁決（`docs/specs/archive/2026-10-ai-portability/proposal.md` X1–X4），繼承全部工具 |

- 保留 Bash 的角色仍能經 Bash 重導寫入檔案。這是已接受的殘餘風險；上表只表示工具層禁用 Edit／Write／NotebookEdit，不代表沒有寫入能力。
- 白名單在 `claude --agent <name>` 主執行緒與 subagent 兩種情境都已實測生效（Claude Code `2.1.292`、`2.1.295`，證據見 `docs/specs/archive/2026-10-ai-portability/notes.md`）。升級 Claude Code 後應重跑該實測。
- macOS 上 Claude Code 預設不提供 Grep／Glob，保留 Bash 的角色改用 Bash 搜尋；白名單中的 Grep、Glob 只對沒有 Bash 的角色生效。
- tester、plan-critic、lianbu-spokesperson 本文中「修正錯誤後更新 history.md／SKILL.md」的步驟無法以工具層寫檔完成：教訓以文字回報，交 Update History, Skill, Agent 或使用者寫入。
- plan-critic 不在 Claude Code 的 plan mode 使用：plan mode 送出計畫需要 Write 與 ExitPlanMode，planner 白名單刻意不含這兩者。以一般模式啟動（`claude --agent plan-critic`），讀計畫檔後以文字回傳批評。
- Codex 沒有依角色的工具限制，只靠各 agent 檔內文的角色規則；需要唯讀時（例如請 Codex 評審計畫），由使用者以 `codex -s read-only` 啟動。VS Code Copilot 依 agent 檔自己的 `tools:` 運作，不讀 `claude-role`。
- `.claude/settings.json` 的 `permissions.ask`（`Bash(git push:*)`）讓 `git push` 執行前要求核准。這是全專案設定，對所有角色生效（含未投影的四個），在主執行緒、subagent 與 auto mode 下都已實測會觸發；但只在從 repo（或 worktree）根目錄啟動的 session 生效（見下一段）。`git -C … push`、`env X=1 git push`、`bash -c 'git push …'` 等變體不受這條規則約束，由下一段的 hooks 補上。
- 新增 agent 時必須加 `claude-role`，或列入 `scripts/sync_ai_adapters.py` 的 `UNDECIDED_AGENTS`，否則 `--check` 失敗。

## Hooks 與 permissions（Claude Code 專屬防線）

`.claude/settings.json` 的 `permissions.ask` 與 PreToolUse hooks（`scripts/claude/`）只保護 Claude Code。VS Code Copilot 與 Codex 不讀這個檔，**不受這道防線保護**，只靠各 agent 檔內文的角色規則。

**生效條件**

- 只在從 repo（或 worktree）根目錄啟動的 session 生效。從子目錄啟動時，Claude Code 不載入根目錄的 `.claude/settings.json`，push 核准與 hooks 都不存在（Claude Code `2.1.296` 實測）。
- 對所有角色生效，含未投影權限的 architect、reviewer、researcher、scraper-expert（使用者裁決 Q8）；`claude --agent` 主執行緒與 subagent 兩種情境都已實測（`2.1.296`）。hooks 不依角色區分。
- `Bash` 與 `Monitor` 工具的命令走同一個 guard；`Read`、`Grep`、`Write`、`Edit`、`NotebookEdit` 的路徑走 file guard。
- fail-closed：launcher 缺失、找不到 `python3`、guard 崩潰、逾時、輸出不符協定，一律阻擋。被誤擋時停下回報使用者，由使用者決定回退 hook commit 或停用單一規則（並補 positive test）；不得以 `--dangerously-skip-permissions`、`disableAllHooks` 或 `settings.local.json` 繞過。
- 驗證：`python3 -m pytest scripts/claude/tests scripts/tests -q`。

**第一批規則**

| 規則 | 處理 |
| --- | --- |
| 任何 `git push`（含 `git -C … push`、`env X=1 git push`、`bash -c 'git push …'`） | 要求核准 |
| `--force`、`-f`、`--force-with-lease`、`--force-if-includes`、`+refspec`、刪除遠端 ref（`--delete`、`-d`、`:ref`）、`--mirror`、`--prune` 的 push | 阻擋 |
| `git reset --hard`；沒有 `-n`／`--dry-run` 的 `git clean`；`git branch -D`（含 `--delete --force`）；`git worktree remove --force`；`git worktree add --force` | 阻擋 |
| `.env`、`.env.*`（`.env.example`、`.env.sample`、`.env.template` 除外）的讀取、搜尋、複製、寫入、刪除與重導 | 阻擋。例外：單一路徑的 `git check-ignore -v`、`git ls-files --error-unmatch`、`test -f`、`stat`、`ls -l`、`wc -l`，以及 `.github/instructions/token-rotation.instructions.md`、`docs/GITHUB_TOKEN_SYNC_CHECKLIST.md` 的 masked awk 模板（逐字相同、不在 pipeline 內） |
| `env`（無命令）、`printenv`、`export -p`、`declare -p`／`-x`、無參數 `set` 等環境變數傾印 | 阻擋 |
| `supabase db push`（只放行精確的 `supabase db push --dry-run`）、`db reset`、`db query`、`db pull`、`migration up／down／repair／squash`、`seed`；`psql` 必須帶 `-X` 且只能是單一 `SELECT`／`SHOW`／`EXPLAIN`（不含 `ANALYZE`）；`python -c` 或 heredoc 餵入的 python 同時含 `create_client` 與 `.insert(`／`.update(`／`.upsert(`／`.delete(` | 阻擋（啟發式） |
| `eval`、stdin 餵入的 shell（`… \| sh`、`bash <<EOF`、`sh -s`）、無法檢查的 `bash -c`、動詞位置的命令替換、`git`／`psql`／`supabase` 參數中的命令替換（`git rev-parse`、`git branch --show-current`、`pwd` 與 heredoc commit 訊息除外）、guard 不支援的語法 | 阻擋 |

**未涵蓋（殘餘風險）**

- prod-db 規則是啟發式，**不代表 production 寫入全面受保護**。經專案腳本的寫入（`scraper/update_source.py`、`qa_auto_fix.py`、`annotator.py` 等）、Supabase CLI 的 Management APIs、claude.ai 帳號層的 Supabase MCP 連接器（`execute_sql`、`apply_migration` 等）、`SELECT` 呼叫有副作用的函式、`.rpc(`、經 pipe 餵入的 python，都不在範圍內。
- `.env` 規則是字面路徑檢查。只給父目錄的遞迴讀取（`grep -r`、`rg -uu`、以父目錄為 `path` 的 Grep 工具、`cp -r`、`tar`）、symlink／hard link 等別名路徑、直譯器程式碼字串內的路徑（如 `python3 -c "open('.env')"`）都不涵蓋。
- 字元層混淆（`$'\x67it'`、變數拼接）、`$VAR` 當動詞或 guarded 參數、`xargs`、`find -exec`、git alias、未解包的包裝動詞（`uv run`、`npx` 等）、經變數間接引用的 `source "$F"`、在直譯器內讀取環境變數，都不涵蓋。
- hook 失敗與逾時以 `onFailure: "block"` 阻擋，需 Claude Code `2.1.295` 以上；舊版會忽略這個欄位，逾時時放行（launcher 缺失仍由命令本身的 `|| exit 2` 阻擋）。Claude Code 改版若不再辨識 decision JSON，`ask` 會退化為不提示。
- `.claude/settings.local.json`、`disableAllHooks`、`--settings` 等覆蓋不在邊界內。
- 保留 Bash 的角色仍可經 Bash 重導寫入一般檔案（見上一段）。

## Skills wrappers

`.claude/skills`（Claude）與 `.agents/skills`（Codex）都是指向 `.github/skills` 的 pointer wrapper；真正規則仍以 `.github/skills/**/SKILL.md` 與同資料夾補充檔為準。

新增或修改 agent、skill、prompt 後，必須執行：

```bash
python3 scripts/sync_ai_adapters.py
```

提交前可用下列命令確認生成檔未漂移：

```bash
python3 scripts/sync_ai_adapters.py --check
```
