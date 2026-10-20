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

- [x] 使用者確認標註措辭、runbook 措辭表（plan §4）；Allowed paths 擴充已由 Q5 核准（2026-10-07 H-A1：全部核准，含 F7、closer L88 保留為 legacy 來源 3、runbook L295 加「Phase B 投影目標」、Step 0 判為預期內主幹前進；見 notes.md §4.5）
- [x] （Phase 0 查證 F3）使用者決定：A3 改寫 `admin-reports-204-cleanup` 的 `tasks.md` L8、`proposal.md` L18，是否就是 `admin-qa-cleanup/proposal.md` L231–241 所要求「另行核准的 docs-only reconciliation」（只限權威指標一項），並依決定處理 `admin-qa-cleanup/proposal.md` L237（見 notes.md §3.3）→ **選項 2**：不認定；前任兩檔與 L237 零 diff；A-R7 範圍修訂為 4 個 spec，前任兩句記為 historical（凍結的 audit history，由 admin-qa-cleanup final reconciliation、其 tasks.md L349 處理）
- [x] （H-A1 新增 F5）`.copilot-tracking/research/` 是 `scraper/researcher.py`／`update_source.py` 的 I/O 介面 → **(a)**：candidates／sources 路徑保留並加註「腳本介面、legacy 目錄名、非 session state」；只有 `research-log.md` 移到 `~/.ai-notes/ttr/research/`；改名列後續項目
- [x] （H-A1 新增 F6）`authoritative-venue-repair` → **(a)**：`tasks.md` L9 一併改寫；三處權威指向 `.github/prompts/authoritative-venue-repair.prompt.md`＋`proposal.md`＋`tasks.md`
- [x] （H-A1 新增 F7）`plan-critic.agent.md` L102 一併改為「不執行檔案修改工具，批評以文字回傳」

### A1 active guidance（canonical）

- [x] `.github/agents/architect.agent.md`（UNDECIDED，僅 A 遷移）：frontmatter L7、L10 的 handoff `prompt`；本文 L80、L1168、L1173、L1175 的 state 路徑。`runSubagent` 編排與 L1160 的 `vscode_askQuestions` 不改（X1）
- [x] `.github/agents/plan-critic.agent.md`：frontmatter L7、L10；本文 L21、L31、L37、L101、L105（L105「允許寫入」改「不寫檔，以文字回報」）；另依 F7 改 L102
- [x] `.github/agents/designer.agent.md`：frontmatter L7；本文 L115、L120
- [x] `.github/agents/researcher.agent.md`（UNDECIDED，僅 prose）：L19、L103、L142、L156；`update_source.py` 相關段落（X3）不改。依 F5 (a)：L19、L103、L142 保留腳本介面路徑並加註，L156 的 `research-log.md` 改到 `~/.ai-notes/ttr/research/`
- [x] `.github/agents/campaign-closer.agent.md` L88：改「spec tasks.md 未勾選項」；舊 scratch 列 legacy 唯讀檢查（H-A1 核准：保留為來源 3 並標 legacy 唯讀，新待辦指向來源 1 的 spec `tasks.md`）
- [x] `.github/agents/scraper-expert.agent.md`（UNDECIDED，僅 prose）L192：保留 `.copilot-tracking/` staging 排除，標 legacy
- [x] `.github/skills/agents/designer/SKILL.md` L506、`.github/skills/agents/researcher/SKILL.md` L51（researcher 依 F5 (a) 保留路徑並加註）
- [x] `.github/instructions/git.instructions.md` L136–149：整段改為新契約表，保留一句 legacy gitignored 說明（另加 F5 例外句）
- [x] `.github/prompts/authoritative-venue-repair.prompt.md` L13–14、L361；`.github/prompts/admin-qa-cleanup.prompt.md` L36（L38、L138 為限制句，不改）
- [x] `.github/prompts/weekly-review.prompt.md`：依裁決 4（Q1）刪除 Step 3「Session Memory」，Step 4 重新編號為 Step 3，並同步檔內交叉引用（檔內與 repo 內都沒有其他步驟編號引用）
- [x] `.github/prompts/workstream-audit.prompt.md` L21、`.github/prompts/ledger-topology-reconcile.prompt.md` L18（L16、L47 為限制句，不改）
- [x] `AGENTS.md` L54：保留對照表，補註「legacy 路徑，僅供閱讀舊檔」
- [x] `scripts/campaign-closeout-audit.sh` L283–296、`docs/evaluation/campaigns/README.md` L286：保留為 legacy 唯讀掃描，標籤改 `legacy_tracking_plans`（shellcheck 0.11.0 無 warning、`bash -n` exit 0、disposable fixture smoke test 通過）
- [x] `docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md`：套用 plan §4 措辭表（L295 加「Phase B 投影目標」、L299 依 F5；A-R1／A-R2 PASS 後勾選 L403）
- [x] 確認不改：`.github/agents/reviewer.agent.md`、`.github/skills/agents/architect/SKILL.md`（Phase 0 `rg` 無命中；Phase A diff 為零）

### A2 generated

- [x] `python3 scripts/sync_ai_adapters.py`；generated 變動只在 `.claude/agents/{architect,plan-critic,designer}.md`（Phase 0 已確認集合，notes.md §3.1）

### A3 historical 與 active spec 權威句

- [x] `publication-policy`：`tasks.md` L8–9、`proposal.md` L118
- [x] `authoritative-venue-repair`：`proposal.md` L50、L183；依 F6 (a) 另改 `tasks.md` L9，權威指向 prompt＋`proposal.md`＋`tasks.md`
- [x] `admin-reports-204-cleanup`：`tasks.md` L8、`proposal.md` L18（`notes.md` bytes 不得變動；先經 H-A1 的 F3 決定）→ F3 選項 2：**不改**（三檔 SHA-256 與 Phase A 前相同，見 notes.md §4.6）
- [x] `admin-qa-cleanup`：`proposal.md` L237（依 H-A1 的 F3 決定）→ F3 選項 2：**不改**
- [x] `spec-architecture-dashboard`：`proposal.md` L51
- [x] `docs/specs/security-hardening-plan-RECOVERED.md`、`docs/evaluation/annotator/2026-05-18-baseline-v2.md`：加 Historical／superseded 標註，原文不改
- [x] `.github/skills/agents/engineer/history.md` L1822–1832 旁加 superseded 註記，原文不改
- [x] `.github/skills/scraper-expert/history.md` L102、L116：來源括號後補「（Copilot session 路徑，已不可取得；非規範）」

### 驗證（A-R1～A-R9）

- [x] A-R1：三條 negative search＋語意同義詞補查的每個命中都分類為 active 或 historical；分類帳寫入 notes.md（§4.6，37 檔 99 行）
- [x] A-R2：active guidance 目標檔無「要求寫入 Copilot-only state」的命中
- [x] A-R3：frontmatter-diff，每個被改動的 `.agent.md` 除 `handoffs[*].prompt` 外逐 key 相等；結果記入 notes.md
- [x] A-R4：`.claude/agents/*.md` 的「建議提示」不含 legacy path
- [x] A-R5：`sync` 後 `--check` exit 0；兩次生成的完整 `{路徑: sha256}` 字典相等
- [x] A-R6：generated 變動的路徑集合 ⊆ 預期集合
- [x] A-R7（H-A1 F3 選項 2 修訂範圍：4 個 spec；`admin-reports-204-cleanup` 兩句記為 historical，交 admin-qa-cleanup final reconciliation）：4 個 active spec 的「權威計畫」句已依 plan §5 A3 表改寫（authoritative-venue-repair 依 F6 (a)）
- [x] A-R8：`git diff --check` 通過；diff 路徑 ⊆ 已核准的 Allowed paths
- [x] A-R9：runbook 措辭表已套用（以 `rg` 驗證舊句消失）
- [x] 資訊性：R1 `/context` 取證（使用者執行；缺則標 NOT TESTED，不阻擋 B）— 前測已取證（worktree 版，notes.md §4.3）；後測已取證（Phase B session 開頭，worktree 版，與前測一致，notes.md §4.7）
- [x] **H-A2**：commit 前檢視 diff stat、分類帳與 negative search；核准後 commit（2026-10-07 使用者核准；`chore(ai): remove legacy Copilot state paths`，不 push）

## Phase B：角色權限轉成 Claude 工具限制（plan §6）

### Step 0 漂移（Phase B）

- [x] Step 0 發現 origin/main（`67846c18`）刪除 Community Platforms Scraper、修改 scraper-expert／researcher → STOP；使用者選項 1：證據 commit 後 rebase 到 origin/main，參數改為 15 個 wrapper／11 個受管 agent，B-R5 擴充基準改為 rebase 後 A commit `223d8b4e`，裁決 6 的 base 修訂（notes.md §4.7、§4.8）

### H-B1（開工前）

- [x] 使用者確認角色表；決定是否提前處理 X2（reviewer 改投影為 readonly）（2026-10-07：a 核准、X2 選項 1 延期、c 核准、d 核准、e 核准、f1 採建議；新增後續項目「reviewer 重新定位」；notes.md §4.10、§4.12）

### B-0 spike（disposable tmp 專案，無副作用；先記 `claude --version`；結果入 notes.md）

- [x] (1) subagent frontmatter 支援欄位（`tools`、`disallowedTools`、`permissionMode`、`hooks`）（PASS：`tools`、`disallowedTools` 實測，其餘依文件；notes.md §4.11）
- [x] (2) `tools:` 是否生效，分 (a) `claude --agent` 主執行緒、(b) subagent 記錄（(a) PASS、(b) PASS；notes.md §4.11）
- [x] (3) hook stdin 的 agent 識別欄位，分 (a)(b) 記錄（(a) `agent_type`、(b) `agent_type`＋`agent_id`；notes.md §4.11）
- [x] (4) planner 的 plan mode 相容性：`tools:` 不含 Write 時能否寫 `~/.claude/plans/*.md`、`ExitPlanMode` 是否需明列（U1：**不相容**，提交需要 Write＋ExitPlanMode；使用者選項 2：plan-critic 不在 plan mode 使用、白名單不變，不採 fallback-P；notes.md §4.14、§4.15）
- [x] (5) Copilot 對未知欄位 `claude-role` 的反應（U2：PASS，可載入、可執行；角色表維持在 frontmatter；notes.md §4.16）
- [x] (6) `permissions.ask` 語法、deny／ask／allow 優先序、subagent 內 Bash 是否受專案 permissions 約束（`:*` 與空白形式皆有效；deny > ask > allow；subagent、`--agent`、auto mode 皆受 ask 約束；`git -C`、`bash -c` 變體不受約束 → C-R5；notes.md §4.11）
- [x] (7) 無法證實者標 NOT TESTED，改用「settings permissions＋hooks」保守方案（無 NOT TESTED 項；(4) 不相容由使用者選項 2 處理，見 notes.md §4.15）
- [x] (8) `/agents` 列表中每個 wrapper 的來源路徑為 worktree 內檔案（U4：`/agents` 精靈已移除，以 init 事件等價列表 PASS；notes.md §4.18）

### 使用者實測（H-B1 e 核准；使用者貼上輸出後由 Engineer 判定）

fixture（U1–U3）：`cd "/private/tmp/claude-501/-Users-flyingship-Development-3-TTR-Tokyo-Taiwan-Radar-ttr-ai-portability-worktree/0e42332b-31bd-41ae-98e3-6d025acd6349/scratchpad/b0 user fixture/proj"`。第一次互動啟動時會出現 trust 對話框，選信任（拋棄式目錄）。`.claude/settings.json` 與 B 預定提交的內容相同。

- [x] **U1｜B-0(4) plan mode**（2026-10-09 完成：兩輪皆無法提交，見 notes.md §4.14）：`env -u ANTHROPIC_API_KEY claude --agent fixture-planner --permission-mode plan`，輸入「請規劃在 hello.txt 加一行 world 的修改，規劃完成後提交計畫給我核准」。**預期**：出現計畫核准提示、沒有 Write 錯誤；**不要核准**，`/exit` 後執行 `ls -lt ~/.claude/plans | head -3` 應看到新檔。再以 `fixture-planner-exit` 重做一次。**回報**：兩次是否出現核准提示、錯誤原文、`ls` 輸出。**分流**：不含 ExitPlanMode 也能完成 → planner 白名單不變；只有含 ExitPlanMode 才能完成 → planner 白名單加 ExitPlanMode；需要 Write → fallback-P（白名單加 Write）＋B-R7 P2 carry-over 到 C-R9／C-R10 planner 分支
- [x] **U2｜B-0(5) Copilot**（2026-10-09 完成：信任＋重新載入後可選取並回覆，見 notes.md §4.16）：以 VS Code 開啟 fixture 的 `proj` 資料夾，在 Copilot Chat 的 agent 選單選「Fixture Tester」，輸入「你好」；打開 `.github/agents/fixture-tester.agent.md` 看 `claude-role` 行是否有警告。**預期**：可選取、會回覆；`claude-role` 最多只有警告。**回報**：能否選取、是否回覆、警告或錯誤原文。**分流**：只有警告 → 照計畫；報錯或無法選取 → 角色表改放 sync script（既有 fallback）
- [x] **U3｜B-R6 push 閘門**（2026-10-09 完成：(a)(b) 皆出現提示並拒絕，見 notes.md §4.17）：`env -u ANTHROPIC_API_KEY claude --agent fixture-full --permission-mode auto`。(a) 輸入「請執行 git push --dry-run origin main」；(b) 輸入「請用 Agent 工具交給 fixture-full subagent 執行 git push --dry-run origin main」。**預期**：兩次都在執行前出現核准提示，**選 No**。**回報**：兩次是否出現提示（貼提示文字）。**分流**：(a) 沒有提示 → B 不通過，STOP；只有 (b) 沒有提示 → 由 C 的 hook（C-R5）補，`AGENTS.md` 聲明照實下修
- [x] **U4｜B-0(8)／B-R4 `/agents`（實作完成後）**（2026-10-09 完成：`2.1.295` 移除 `/agents` 精靈，改用 `u4_agents.sh` 等價列表；15 個、無 community-platforms-scraper、tester 受限；notes.md §4.18）：`cd "/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree" && env -u ANTHROPIC_API_KEY claude`，輸入 `/agents`。**預期**：專案 agent 共 15 個；**沒有** `community-platforms-scraper`（主工作樹仍是舊的 16 個；若出現代表載入主工作樹 → STOP，查 R2）；選 tester 檢視時，來源路徑在 `ttr-ai-portability-worktree/.claude/agents/`，工具清單為受限白名單。**回報**：清單（文字或截圖）、tester 的來源路徑與工具

### 實作

- [x] `scripts/sync_ai_adapters.py`：`ROLE_TOOLS`、Copilot→Claude 類別對照、`UNDECIDED_AGENTS`、輸出 `tools:`；保留 `pinned_models` 檢查與 MARKER（notes.md §4.13）
- [x] 11 個受管 agent 的 frontmatter 加 `claude-role`（四個 UNDECIDED 不改；原為 12，依 notes.md §4.8 修訂）
- [x] `AGENTS.md` 加角色權限說明（Codex 無工具層限制；措辭依 C-R11）
- [x] 新增 `.claude/settings.json`，只含 `permissions.ask`（語法依 B-0(6)）
- [x] 新增 `scripts/tests/test_sync_ai_adapters.py`（plan §6 測試清單 1–7）與 settings 測試（`test_claude_settings.py`、共用 `conftest.py`）

### 驗證（B-R1～B-R10）

- [x] B-R1：B-0 結果全數記入 notes.md，每項 PASS 或 NOT TESTED＋所選 fallback（§4.11、§4.14～§4.18；`2.1.295` 重驗相同）
- [x] B-R2：`scripts/tests/test_sync_ai_adapters.py` 全過（`24 passed`，含 settings 測試；notes.md §4.13）
- [x] B-R3：`.claude/agents/*.md` 數量 = 15 = `len(agent_sources)`，名稱唯一（原為 16；依 notes.md §4.8 修訂）
- [x] B-R4：使用者在 worktree 新 session 執行 `/agents`，15 個皆列出且來源為 worktree 內檔案（PASS-pending-user；原為 16，依 notes.md §4.8 修訂；步驟見 U4）（使用者證據已補：PASS，notes.md §4.18）
- [x] B-R5：`.claude/skills`、`.claude/commands`、`.agents` 相較 HEAD 零 diff；四個 UNDECIDED 的 canonical 與 generated 相較 A commit（rebase 後 `223d8b4e`，notes.md §4.8）零 diff
- [x] B-R6：最小 push `ask`：settings 測試通過＋使用者實測 `git push --dry-run` 出現提示（PASS-pending-user）；變體 carry-over 到 C（使用者證據已補：純 `git push` PASS；`git -C`／`bash -c` 變體 PARTIAL＋Carry-over → C-R5；notes.md §4.17）
- [x] B-R7：planner（plan-critic）工具層無 Edit／Write／NotebookEdit；P1／P2 情境依合法 carry-over 分支處理（通過條件依使用者決定修訂為兩情境工具層無 Edit／Write／NotebookEdit → PASS；不需 carry-over；notes.md §4.15）
- [x] B-R8：Tester 工具層無 Edit／Write／NotebookEdit（任何情況都不加入）；T1 情境依合法 carry-over 分支處理（兩情境皆 PASS，不需 carry-over；notes.md §4.11）
- [x] B-R9：`claude doctor` 摘要記入 notes.md（§4.13）
- [x] B-R10：注入 `model:` 的 tmp 副本 → `--check` 非 0
- [x] **H-B2**：B-0 結果、B-R4／B-R6 的使用者證據（2026-10-09 使用者核准；notes.md §4.19）
- [x] **H-B3**：commit 前檢視 diff；核准後 commit（2026-10-09 使用者核准；`chore(ai): project agent roles to Claude tool limits`，不 push）

## Phase C：危險操作 hooks（plan §7）

### C-0 spike（disposable 專案，無副作用；結果入 notes.md）

- [x] (1) 退出碼語意：exit 2 阻擋；exit 1、127、逾時不阻擋（結果不符 → STOP 回報）（PASS，`2.1.296`；notes.md §4.21）
- [x] (2) matcher 名稱與 stdin JSON 欄位（PASS；`scratchpad_dir` 未出現；notes.md §4.21）
- [x] (3) agent 識別欄位，分 (a) `claude --agent` 主執行緒、(b) subagent 記錄（C-R9 依據）（(a) `agent_type`、(b) `agent_type`＋`agent_id`；notes.md §4.21）
- [x] (4) `Grep` 工具是否遍歷 gitignored 的 dotfile（會遍歷 → 規則 7 邊界；notes.md §4.21）
- [x] (5) hook 回 `ask` 的 JSON 形狀與是否生效；形狀寫成 `_policy.py` 常數（形狀生效；互動提示待使用者；notes.md §4.21）
- [x] (6) 沿用 B-0(6) 結果

### 實作

- [x] `scripts/claude/{run_hook.sh,pretooluse_bash_guard.py,pretooluse_file_guard.py,_policy.py,_tokenizer.py}`
- [x] `scripts/claude/tests/{test_bash_guard,test_file_guard,test_launcher}.py`＋fixtures（heredoc fixture 一案一檔）；settings 測試改寫 `scripts/tests/test_claude_settings.py`（H-C1 ⑧，不另建 `test_settings.py`）
- [x] `.claude/settings.json` 加 `hooks`，不移除 `permissions`
- [x] Push 閘門：parser 找到的任何 `git push` 段回 `ask`；force 系列 deny
- [x] 規則矩陣 #1–#10（#7 三層、#9 啟發式、#10 stdin 餵入的 shell）
- [x] `_tokenizer.py` 單檔 ≤250 行；將超過預算時停下回報
- [x] `AGENTS.md` 加「hooks 與 permissions 為 Claude Code 專屬防線」＋覆蓋聲明

### 使用者實測（H-C1 ⑫ 核准；使用者貼上輸出後由 Engineer 判定）

fixture（2026-10-13 準備；scratchpad，路徑含空格；`.claude/settings.json` 與 `scripts/claude/` 與 worktree 逐位元組相同）。第一次互動啟動時會出現 trust 對話框，選信任（拋棄式目錄）：
- U5：`cd "/private/tmp/claude-501/-Users-flyingship-Development-3-TTR-Tokyo-Taiwan-Radar-ttr-ai-portability-worktree/e629387e-2c6d-4a6c-8a7a-c992a7eca69c/scratchpad/c2 user fixture/proj"`（`origin` = 同層本機 bare `remote.git`；有 `fixture-full` agent）
- U6 Closer：`cd "/private/tmp/claude-501/-Users-flyingship-Development-3-TTR-Tokyo-Taiwan-Radar-ttr-ai-portability-worktree/e629387e-2c6d-4a6c-8a7a-c992a7eca69c/scratchpad/c3 closer fixture/Tokyo Taiwan Radar"`（campaign `demo-fixture`；worktree `ttr-demo-fixture-worktree`；base `9eae2409e34b0034be61bae1fd3db5543fccecaa`、pushed HEAD `b296fe976f6a7fdad6760f3929109e057bef9864`；本機 bare `origin.git`；Engineer 試跑 audit 為 `UNDETERMINED:issues_not_checked,self_session_unknown`）

- [x] **U5｜C-0(5)／C-R5 ask 提示**（2026-10-13：(a)～(e) 全數 PASS，(d) 使用者確認選 No；notes.md §4.27、§4.28）：`env -u ANTHROPIC_API_KEY claude --agent fixture-full --permission-mode auto`，依序請它執行 (a) `git -C . push --dry-run origin main`、(b) `bash -c "git push --dry-run origin main"`、(c) `env X=1 git push --dry-run origin main`、(d) 用 Agent 工具交給 fixture-full subagent 執行 (a)、(e) `git push --force --dry-run origin main`。**預期**：(a)～(d) 執行前出現核准提示（理由含 `ttr-hook:`），**選 No**；(e) 不出現提示、直接被擋，訊息含 `[git-force-push]`。**回報**：每次是否出現提示（貼提示文字）。**分流**：(a)～(d) 沒有提示 → H-C1 ⑦（變體改 deny）
- [x] **U6｜C-R7 smoke test**（2026-10-13：四角色＋Closer PASS；Closer 以 Bash 寫結案紀錄 → 裁決 12 不需 Write；notes.md §4.27、§4.28）（hooks 加入 worktree 後；一律在 worktree **根目錄**開新終端機）：`cd "/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree" && env -u ANTHROPIC_API_KEY claude --agent <name>`，每個角色各一個 session。只用「即使漏擋也無害」的命令：
  - architect：請它用 Bash 執行 `git status --short`（預期放行）與 `printenv HOME`（預期被擋，`[env-dump]`）
  - engineer：`git diff --check`（放行）與 `git branch -D ttr-smoke-nonexistent`（被擋，`[git-branch-D]`）
  - tester：`python3 -m pytest scripts/claude/tests -q`（放行）與用 Read 工具讀 `docs/.env.smoke-nonexistent`（被擋，`[env-file-access]`）
  - validate-merge-deploy：`git log --oneline -3` 與 `git fetch origin main`（放行）；**不做任何 push**
  - close-campaign-retire-worktree：**在上列 Closer fixture 根目錄啟動**（不是 worktree），輸入「請結案 campaign `demo-fixture`。worktree：`<fixture 根目錄>/ttr-demo-fixture-worktree`；campaign base SHA：`9eae2409e34b0034be61bae1fd3db5543fccecaa`；pushed HEAD SHA：`b296fe976f6a7fdad6760f3929109e057bef9864`；session id 未知；GitHub issues 以 `--skip-issues` 標 not_checked。不要 push、不要移除 worktree。」Closer 回報 UNDETERMINED 並詢問時，回覆「確認可接受，請進入 Phase C，在 campaign worktree 內撰寫結案紀錄（disposition 填 pending）」。**預期**：寫出 `ttr-demo-fixture-worktree/docs/evaluation/campaigns/2026-10-13-demo-fixture.md`。**回報**：是否寫出、Closer 用哪個工具寫（或貼錯誤原文）。Engineer 讀 transcript 依裁決 12 判定（被拒或做不到 → 授予 Write；Bash 寫成 → 不需 Write）
  **回報**：每個 session 的結果（貼被擋訊息）；有誤擋即停

### 驗證（C-R1～C-R12）

- [x] C-R1：C-0 結果記錄
- [x] C-R2：每個阻擋類 ≥3 變體、每個允許案例 ≥1 positive；must-allow 清單全過
- [x] C-R3：fail-closed 矩陣全過，含 output protocol 列
- [x] C-R4：必測三項（例外→exit 2＋固定訊息；含空格路徑；假 token 不出現在 stderr）
- [x] C-R5：push 閘門變體回 `ask`、force 系列 deny（含 B-R6 carry-over）
- [x] C-R6：settings 加入 hooks 後再跑 `claude doctor`
- [x] C-R7：使用者新 session smoke test：Architect、Engineer、Tester、V-M-D、Closer（含實際結案寫檔；需要 Write 時依裁決 12）
- [x] C-R8：AGENTS.md 覆蓋聲明（含規則 7 的敏感路徑邊界）
- [x] C-R9：角色辨識分兩情境實測；不可辨識時依裁決 13 標「PARTIAL－裁決 13 接受」
- [x] C-R10：role-conditional 寫入拒絕（只對 carry-over 情境 Required）→ 不適用（無 carry-over；notes.md §4.23）
- [x] C-R11：能力聲明措辭全面檢查
- [x] C-R12：C commit 相較 B commit，四個 UNDECIDED 的 canonical 與 generated 零 diff
- [x] **H-C1**：規則矩陣（特別 #7、#9、#10）、push 閘門（含 §8.2 #13）、C-R9 辨識結果與標示的呈報（2026-10-12 使用者「全部照建議」；notes.md §4.23）
  - [x] （Phase 0 查證 F4）`supabase db query`，以及預設對 linked 專案動作的子命令，在規則 9 中如何處理（見 notes.md §3.4）→ H-C1 ⑤：`db query`、`db pull` 等全拒，不分目標；Management APIs 列後續項目
- [x] **H-C2**：`settings.json` 逐行檢視（2026-10-13 使用者核准；notes.md §4.26）
- [x] **H-C3**：使用者新 session smoke test；Closer 依裁決 12 處理並呈報（2026-10-13 使用者核准 commit；Closer 不需 Write；notes.md §4.28、§4.30）
- [x] 核准後 commit（`chore(ai): add Claude Code PreToolUse safety hooks`，不 push）

## H-PUSH

- [x] 交 V-M-D：使用者明確核准、僅 linear fast-forward、驗證 pushed SHA 等於 GitHub main（2026-10-13 完成：`7f8e75c9..86fdc143`，`ls-remote` 確認 GitHub main = `86fdc1434188c49713bc37b6c7a71a9034f3b9b8`；Production deployment `success`；證據與 rebase 前後 SHA 對照見 notes.md §4.32）

## 後續項目（不在本 campaign；plan §4 第 4 項、§8.2 原則 6）

本段原有的 19 條後續項目（plan §4 第 4 項、§8.2 原則 6：不在本 campaign 範圍）已於 2026-10-13 逐字搬至 `docs/specs/parked/ai-portability-followups.md`，來源 commit 為 `6b404ea3a4b029cf9c157d9773442b40d7fee5a8`（原 L187–205 與 L207）。搬移只改位置：19 條在新檔仍全部是未完成項目，本檔不再追蹤；理由是它們不屬於本 campaign，留在本檔會讓結案稽核持續回報 HOLD。下方「處理原則」第 6 點所稱的「後續項」，即新檔「⑤ 維護」中「升級 Claude Code 後重跑 B-0／C-0 的 fixture」一條。

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
