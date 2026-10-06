# Tasks

每完成一步把 `- [ ]` 改 `- [x]`，並 commit（即使只改這一行）。本檔是跨 session 進度的真值；執行證據記入 [notes.md](./notes.md)。各項的完整規格見 [plan.md](./plan.md) 對應章節，本檔只列可勾選的步驟。

## Phase 0：spec 骨架（plan §4）

- [x] Worktree 確認閘門（§4 2a）：使用者指定 `ttr-ai-portability-worktree`（CONTINUING）；以 `git worktree list --porcelain` 核對路徑與 branch；主工作樹 `git status --short` 取證（無 WIP）
- [x] Step 0 漂移檢查（§4 2b）：HEAD `565c1479`、工作樹乾淨；`git fetch origin` 後記錄 remote baseline 與 `ed09bece` 的關係（notes.md §2）
- [x] 自 `docs/specs/_template/` 建立 `proposal.md`、`tasks.md`；新建 `notes.md`
- [x] 存檔 `plan.md`（= rev.6）與 `plan-critique-1.md`～`plan-critique-6.md`（原樣複製，SHA-256 相符）
- [x] Phase 0 查證項記入 notes.md §3（A2 frontmatter `rg`、A1 語意補查、architect SKILL `rg`、admin-qa-cleanup L237、`supabase --help`）
- [x] 驗證：變動路徑只在本目錄（PASS）；新檔不含 secret、token 或 `.env` 內容（PASS，gitleaks＋regex）；`git diff --check`：本 session 撰寫的檔案 PASS，原樣複製的 `plan-critique-2/3/4.md` 帶有來源原有的 whitespace（notes.md §3.5），H0 決定方案 A：維持原樣
- [x] **H0**：使用者核准後 commit（`docs(ai): add ai-portability spec skeleton`），不 push

## Phase A：移除 legacy state path（plan §5）

### H-A1（開工前）

- [ ] 使用者確認標註措辭、runbook 措辭表（plan §4）；Allowed paths 擴充已由 Q5 核准
- [ ] （Phase 0 查證 F3）使用者決定：A3 改寫 `admin-reports-204-cleanup` 的 `tasks.md` L8、`proposal.md` L18，是否就是 `admin-qa-cleanup/proposal.md` L231–241 所要求「另行核准的 docs-only reconciliation」（只限權威指標一項），並依決定處理 `admin-qa-cleanup/proposal.md` L237（見 notes.md §3.3）

### A1 active guidance（canonical）

- [ ] `.github/agents/architect.agent.md`（UNDECIDED，僅 A 遷移）：frontmatter L7、L10 的 handoff `prompt`；本文 L80、L1168、L1173、L1175 的 state 路徑。`runSubagent` 編排與 L1160 的 `vscode_askQuestions` 不改（X1）
- [ ] `.github/agents/plan-critic.agent.md`：frontmatter L7、L10；本文 L21、L31、L37、L101、L105（L105「允許寫入」改「不寫檔，以文字回報」）
- [ ] `.github/agents/designer.agent.md`：frontmatter L7；本文 L115、L120
- [ ] `.github/agents/researcher.agent.md`（UNDECIDED，僅 prose）：L19、L103、L142、L156；`update_source.py` 相關段落（X3）不改
- [ ] `.github/agents/campaign-closer.agent.md` L88：改「spec tasks.md 未勾選項」；舊 scratch 列 legacy 唯讀檢查
- [ ] `.github/agents/scraper-expert.agent.md`（UNDECIDED，僅 prose）L192：保留 `.copilot-tracking/` staging 排除，標 legacy
- [ ] `.github/skills/agents/designer/SKILL.md` L506、`.github/skills/agents/researcher/SKILL.md` L51
- [ ] `.github/instructions/git.instructions.md` L136–149：整段改為新契約表，保留一句 legacy gitignored 說明
- [ ] `.github/prompts/authoritative-venue-repair.prompt.md` L13–14、L361；`.github/prompts/admin-qa-cleanup.prompt.md` L36（L38、L138 為限制句，不改）
- [ ] `.github/prompts/weekly-review.prompt.md`：依裁決 4（Q1）刪除 Step 3「Session Memory」，Step 4 重新編號為 Step 3，並同步檔內交叉引用
- [ ] `.github/prompts/workstream-audit.prompt.md` L21、`.github/prompts/ledger-topology-reconcile.prompt.md` L18（L16、L47 為限制句，不改）
- [ ] `AGENTS.md` L54：保留對照表，補註「legacy 路徑，僅供閱讀舊檔」
- [ ] `scripts/campaign-closeout-audit.sh` L283–296、`docs/evaluation/campaigns/README.md` L286：保留為 legacy 唯讀掃描，標籤改 `legacy_tracking_plans`
- [ ] `docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md`：套用 plan §4 措辭表
- [ ] 確認不改：`.github/agents/reviewer.agent.md`、`.github/skills/agents/architect/SKILL.md`（Phase 0 `rg` 無命中）

### A2 generated

- [ ] `python3 scripts/sync_ai_adapters.py`；generated 變動只在 `.claude/agents/{architect,plan-critic,designer}.md`（Phase 0 已確認集合，notes.md §3.1）

### A3 historical 與 active spec 權威句

- [ ] `publication-policy`：`tasks.md` L8–9、`proposal.md` L118
- [ ] `authoritative-venue-repair`：`proposal.md` L50、L183
- [ ] `admin-reports-204-cleanup`：`tasks.md` L8、`proposal.md` L18（`notes.md` bytes 不得變動；先經 H-A1 的 F3 決定）
- [ ] `admin-qa-cleanup`：`proposal.md` L237（依 H-A1 的 F3 決定）
- [ ] `spec-architecture-dashboard`：`proposal.md` L51
- [ ] `docs/specs/security-hardening-plan-RECOVERED.md`、`docs/evaluation/annotator/2026-05-18-baseline-v2.md`：加 Historical／superseded 標註，原文不改
- [ ] `.github/skills/agents/engineer/history.md` L1822–1832 旁加 superseded 註記，原文不改
- [ ] `.github/skills/scraper-expert/history.md` L102、L116：來源括號後補「（Copilot session 路徑，已不可取得；非規範）」

### 驗證（A-R1～A-R9）

- [ ] A-R1：三條 negative search＋語意同義詞補查的每個命中都分類為 active 或 historical；分類帳寫入 notes.md
- [ ] A-R2：active guidance 目標檔無「要求寫入 Copilot-only state」的命中
- [ ] A-R3：frontmatter-diff，每個被改動的 `.agent.md` 除 `handoffs[*].prompt` 外逐 key 相等；結果記入 notes.md
- [ ] A-R4：`.claude/agents/*.md` 的「建議提示」不含 legacy path
- [ ] A-R5：`sync` 後 `--check` exit 0；兩次生成的完整 `{路徑: sha256}` 字典相等
- [ ] A-R6：generated 變動的路徑集合 ⊆ 預期集合
- [ ] A-R7：5 個 active spec 的「權威計畫」句已依 plan §5 A3 表改寫
- [ ] A-R8：`git diff --check` 通過；diff 路徑 ⊆ 已核准的 Allowed paths
- [ ] A-R9：runbook 措辭表已套用（以 `rg` 驗證舊句消失）
- [ ] 資訊性：R1 `/context` 取證（使用者執行；缺則標 NOT TESTED，不阻擋 B）
- [ ] **H-A2**：commit 前檢視 diff stat、分類帳與 negative search；核准後 commit

## Phase B：角色權限轉成 Claude 工具限制（plan §6）

### H-B1（開工前）

- [ ] 使用者確認角色表；決定是否提前處理 X2（reviewer 改投影為 readonly）

### B-0 spike（disposable tmp 專案，無副作用；先記 `claude --version`；結果入 notes.md）

- [ ] (1) subagent frontmatter 支援欄位（`tools`、`disallowedTools`、`permissionMode`、`hooks`）
- [ ] (2) `tools:` 是否生效，分 (a) `claude --agent` 主執行緒、(b) subagent 記錄
- [ ] (3) hook stdin 的 agent 識別欄位，分 (a)(b) 記錄
- [ ] (4) planner 的 plan mode 相容性：`tools:` 不含 Write 時能否寫 `~/.claude/plans/*.md`、`ExitPlanMode` 是否需明列
- [ ] (5) Copilot 對未知欄位 `claude-role` 的反應
- [ ] (6) `permissions.ask` 語法、deny／ask／allow 優先序、subagent 內 Bash 是否受專案 permissions 約束
- [ ] (7) 無法證實者標 NOT TESTED，改用「settings permissions＋hooks」保守方案
- [ ] (8) `/agents` 列表中每個 wrapper 的來源路徑為 worktree 內檔案

### 實作

- [ ] `scripts/sync_ai_adapters.py`：`ROLE_TOOLS`、Copilot→Claude 類別對照、`UNDECIDED_AGENTS`、輸出 `tools:`；保留 `pinned_models` 檢查與 MARKER
- [ ] 12 個受管 agent 的 frontmatter 加 `claude-role`（四個 UNDECIDED 不改）
- [ ] `AGENTS.md` 加角色權限說明（Codex 無工具層限制；措辭依 C-R11）
- [ ] 新增 `.claude/settings.json`，只含 `permissions.ask`（語法依 B-0(6)）
- [ ] 新增 `scripts/tests/test_sync_ai_adapters.py`（plan §6 測試清單 1–7）與 settings 測試

### 驗證（B-R1～B-R10）

- [ ] B-R1：B-0 結果全數記入 notes.md，每項 PASS 或 NOT TESTED＋所選 fallback
- [ ] B-R2：`scripts/tests/test_sync_ai_adapters.py` 全過
- [ ] B-R3：`.claude/agents/*.md` 數量 = 16 = `len(agent_sources)`，名稱唯一
- [ ] B-R4：使用者在 worktree 新 session 執行 `/agents`，16 個皆列出且來源為 worktree 內檔案（PASS-pending-user）
- [ ] B-R5：`.claude/skills`、`.claude/commands`、`.agents` 相較 HEAD 零 diff；四個 UNDECIDED 的 canonical 與 generated 相較 A commit 零 diff
- [ ] B-R6：最小 push `ask`：settings 測試通過＋使用者實測 `git push --dry-run` 出現提示（PASS-pending-user）；變體 carry-over 到 C
- [ ] B-R7：planner（plan-critic）工具層無 Edit／Write／NotebookEdit；P1／P2 情境依合法 carry-over 分支處理
- [ ] B-R8：Tester 工具層無 Edit／Write／NotebookEdit（任何情況都不加入）；T1 情境依合法 carry-over 分支處理
- [ ] B-R9：`claude doctor` 摘要記入 notes.md
- [ ] B-R10：注入 `model:` 的 tmp 副本 → `--check` 非 0
- [ ] **H-B2**：B-0 結果、B-R4／B-R6 的使用者證據
- [ ] **H-B3**：commit 前檢視 diff；核准後 commit

## Phase C：危險操作 hooks（plan §7）

### C-0 spike（disposable 專案，無副作用；結果入 notes.md）

- [ ] (1) 退出碼語意：exit 2 阻擋；exit 1、127、逾時不阻擋（結果不符 → STOP 回報）
- [ ] (2) matcher 名稱與 stdin JSON 欄位
- [ ] (3) agent 識別欄位，分 (a) `claude --agent` 主執行緒、(b) subagent 記錄（C-R9 依據）
- [ ] (4) `Grep` 工具是否遍歷 gitignored 的 dotfile
- [ ] (5) hook 回 `ask` 的 JSON 形狀與是否生效；形狀寫成 `_policy.py` 常數
- [ ] (6) 沿用 B-0(6) 結果

### 實作

- [ ] `scripts/claude/{run_hook.sh,pretooluse_bash_guard.py,pretooluse_file_guard.py,_policy.py,_tokenizer.py}`
- [ ] `scripts/claude/tests/{test_bash_guard,test_file_guard,test_settings,test_launcher}.py`＋fixtures（heredoc fixture 一案一檔）
- [ ] `.claude/settings.json` 加 `hooks`，不移除 `permissions`
- [ ] Push 閘門：parser 找到的任何 `git push` 段回 `ask`；force 系列 deny
- [ ] 規則矩陣 #1–#10（#7 三層、#9 啟發式、#10 stdin 餵入的 shell）
- [ ] `_tokenizer.py` 單檔 ≤250 行；將超過預算時停下回報
- [ ] `AGENTS.md` 加「hooks 與 permissions 為 Claude Code 專屬防線」＋覆蓋聲明

### 驗證（C-R1～C-R12）

- [ ] C-R1：C-0 結果記錄
- [ ] C-R2：每個阻擋類 ≥3 變體、每個允許案例 ≥1 positive；must-allow 清單全過
- [ ] C-R3：fail-closed 矩陣全過，含 output protocol 列
- [ ] C-R4：必測三項（例外→exit 2＋固定訊息；含空格路徑；假 token 不出現在 stderr）
- [ ] C-R5：push 閘門變體回 `ask`、force 系列 deny（含 B-R6 carry-over）
- [ ] C-R6：settings 加入 hooks 後再跑 `claude doctor`
- [ ] C-R7：使用者新 session smoke test：Architect、Engineer、Tester、V-M-D、Closer（含實際結案寫檔；需要 Write 時依裁決 12）
- [ ] C-R8：AGENTS.md 覆蓋聲明（含規則 7 的敏感路徑邊界）
- [ ] C-R9：角色辨識分兩情境實測；不可辨識時依裁決 13 標「PARTIAL－裁決 13 接受」
- [ ] C-R10：role-conditional 寫入拒絕（只對 carry-over 情境 Required）
- [ ] C-R11：能力聲明措辭全面檢查
- [ ] C-R12：C commit 相較 B commit，四個 UNDECIDED 的 canonical 與 generated 零 diff
- [ ] **H-C1**：規則矩陣（特別 #7、#9、#10）、push 閘門（含 §8.2 #13）、C-R9 辨識結果與標示的呈報
  - [ ] （Phase 0 查證 F4）`supabase db query`，以及預設對 linked 專案動作的子命令，在規則 9 中如何處理（見 notes.md §3.4）
- [ ] **H-C2**：`settings.json` 逐行檢視
- [ ] **H-C3**：使用者新 session smoke test；Closer 依裁決 12 處理並呈報
- [ ] 核准後 commit

## H-PUSH

- [ ] 交 V-M-D：使用者明確核准、僅 linear fast-forward、驗證 pushed SHA 等於 GitHub main

## 後續項目（不在本 campaign；plan §4 第 4 項、§8.2 原則 6）

- [ ] 把 `sync --check` 與新 pytest 接進 CI／githook（目前無）
- [ ] 字元層混淆偵測（`$'\x67it'`、`g''it`、變數拼接）
- [ ] `xargs`／`env VAR=… git` 深層遞迴
- [ ] 裸 `git stash`
- [ ] `--no-verify`
- [ ] 經變數間接引用的 `source "$F"`／`. "$f"`
- [ ] `$VAR` 在 guarded 命令參數位置
- [ ] 敏感路徑的父目錄遞迴搜尋與 symlink／alias 偵測（plan §7 規則 7 邊界）
- [ ] script 介面的 production 寫入（`update_source.py`、`qa_auto_fix.py` 等）
- [ ] X1–X4 裁決後的 Phase B′／C′
- [ ] reviewer 改投影為 readonly（plan §6 X2）
- [ ] SQL 函式副作用偵測（plan §7 規則 9 殘餘風險）
- [ ] 升級 Claude Code 後重跑 B-0／C-0 的 fixture（本 campaign 不做自動化）

直接寫的 `source .env`／`. .env` 由規則 7 層 3 拒絕，`Edit`／`Write` 寫 `.env*` 由規則 7 工具層拒絕，皆已在第一批範圍內，不列後續項。

## NOT TESTED 處理表（plan §8.2，原樣搬入）

| # | 項目 | 對應 gate | 時機 | 執行者 | 方法 | 結果分流 |
|---|---|---|---|---|---|---|
| 1 | 遠端 baseline | §4 2b | Phase 0 開頭 | Engineer | `git fetch origin` 後比較 origin/main 與 `ed09bece` | 非預期漂移 → STOP 回報 |
| 2 | `/context` 載入來源（R1） | A 資訊性 | Phase A 前後 | 使用者 | worktree 新 session 執行 `/context` | 沒有證據就標 NOT TESTED，不阻擋 |
| 3 | `claude --version`、subagent 支援欄位、`claude doctor` | B-0(1)、B-R9 | Phase B 開頭 | Engineer | 執行命令並記錄 | 只記錄 |
| 4 | `tools:` 在兩種情境是否生效 | B-0(2) → B-R7、B-R8 | Phase B | Engineer 先以非互動 `claude -p --agent` 嘗試；做不到的情境交使用者 | disposable tmp 專案，fixture 角色嘗試 Write | 兩情境都 PASS → B-R7／B-R8 PASS；任一失敗 → carry-over 到 C-R9／C-R10 |
| 5 | plan mode 不給 Write 能否寫私有 plan | B-0(4) → B-R7 | Phase B | 使用者（需互動 plan mode） | fixture planner 以 `--permission-mode plan` 啟動並產出計畫 | 可以 → 不需 fallback；不行 → fallback-P＋C-R10 planner 分支 |
| 6 | Copilot 對 `claude-role` 的反應 | B-0(5) | Phase B | 使用者（需 VS Code） | Copilot Chat 載入一個受管 agent | 只警告 → 照計畫；報錯 → 角色表改放 sync script（既有 fallback） |
| 7 | `permissions.ask` 語法、subagent 內 Bash 是否受約束 | B-0(6) → B-R6、§1 R3-5 | Phase B | Engineer（語法）＋使用者（提示是否出現） | disposable 專案＋本機 bare remote，路徑含空格 | subagent 不受約束 → 由 C 的 hook（C-R5）補，AGENTS.md 聲明照實下修 |
| 8 | `/agents` 來源路徑 | B-0(8)、B-R4 | Phase B 結束 | 使用者 | worktree 新 session 執行 `/agents` | 載入主樹檔 → STOP，查 R2 |
| 9 | `git push --dry-run` 出現核准提示 | B-R6 | Phase B 結束 | 使用者 | 同 #7 | 沒有提示 → B 不通過 |
| 10 | hook 退出碼語意、matcher、stdin 欄位 | C-0(1)(2) | Phase C 開頭 | Engineer | fixture hook 回 exit 1／2／127／逾時，並把 stdin 存到 tmp | 與文件不符 → STOP 回報；欄位名寫成常數 |
| 11 | 角色辨識（兩情境） | C-0(3) → C-R9 | Phase C | Engineer；`--agent` 情境若需互動則交使用者 | 同 #10，看 `agent_type`／`agent_id` | 可辨識 → 實作 C-R10；不可辨識 → 依裁決 13 標「PARTIAL－裁決 13 接受」並繼續，在 H-C1 呈報（§2 規則 5） |
| 12 | `Grep` 是否掃到被 gitignore 的 dotfile | C-0(4) | Phase C | Engineer | fixture 專案放假 `.env`，以父目錄為 `path` 搜尋 | 記入規則 7 邊界或工具層 |
| 13 | ask JSON 形狀與提示 | C-0(5) → C-R5、launcher 常數 | Phase C | Engineer（形狀）＋使用者（提示是否出現） | fixture hook 回 ask | 形狀寫成常數；完全不生效 → STOP 回報，候選做法（push 變體改 deny 並提示改用純 `git push`）留待 H-C1 |
| 14 | hook 端到端：crash、無效 JSON、逾時、缺 python3、含空格路徑、假 token 不外洩 | C-R3、C-R4 | Phase C | Engineer | pytest＋launcher 測試 | 未過 → C 不通過 |
| 15 | settings 載入後 `claude doctor` | C-R6 | Phase C | Engineer | 執行並記錄 | 只記錄 |
| 16 | 五角色新 session smoke test（含 Closer 實際寫檔） | C-R7 | Phase C 結束 | 使用者 | 新 session 依序呼叫 Architect、Engineer、Tester、V-M-D、Closer | Closer 依裁決 12 處理 |

**處理原則**
1. 只有實際輸出能把 NOT TESTED 改成 PASS；每次結果連同 `claude --version` 記入 `notes.md`。
2. 失敗時照上表的預定分流處理；分流沒涵蓋的情況一律 STOP 回報，不臨場加新設計。
3. Required 項仍為 NOT TESTED 時阻擋下一階段（§2 規則 1），只有合法 carry-over 例外。
4. 使用者執行的項目：Engineer 事先在 `tasks.md` 寫好步驟與預期結果，使用者貼上輸出後由 Engineer 判定。
5. Engineer 用 `claude` CLI 做 spike 時只在 disposable tmp 專案進行，不在 worktree 內、不 push；依 handoff 已知事項以 `env -u ANTHROPIC_API_KEY` 啟動。
6. 這些行為綁定 Claude Code 版本。`tasks.md` 後續項加一條：升級 Claude Code 後重跑 B-0／C-0 的 fixture（本 campaign 不做自動化）。

**Phase 0 狀態**：#1 已於 Phase 0 執行並取得證據（notes.md §2；判定為預期內的主幹前進，未 STOP）。#2～#16 維持 NOT TESTED。
