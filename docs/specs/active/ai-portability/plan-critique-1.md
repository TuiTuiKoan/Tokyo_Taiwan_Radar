# Plan Critique — ai-portability 三階段 hardening 計畫

> 審查對象：`~/.claude/plans/pasted-content-id-5a7f-docs-claude-code-greedy-cosmos.md`（326 行）
> 對照基準：`docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md` §六（L230–422）與步驟 5（L117–127）
> **模型註記**：本次批評使用 Claude Opus 5.5；原計畫由 Claude 系列模型（runbook 指定 sonnet）撰寫，屬**同一家族**，不是真正的第二視角。
> 本檔是 plan mode 唯一可寫位置；未修改任何 repo 檔案。依 AGENTS.md 對照表，正式落檔位置應為 `docs/specs/active/ai-portability/plan-critique.md`（Phase 0 建立後）。

## Context

使用者要求依 plan-critic 規則審查 Architect 的 A→B→C hardening 計畫，並逐項對照 runbook §六的驗收項目，找出遺漏。結論：**Phase A 可接受（小修）；Phase B 與 Phase C 必須退回 Architect 修改**。原因有三個結構性矛盾與四個驗收缺口，細節如下。

---

## 1. 商業主軸對齊 — 🟡 弱對齊

- 不直接對應 plan-critic SKILL 的主軸 1–4，屬「營運延續性」前置工作：Copilot Enterprise 被撤銷時，agent 系統必須仍能運作。
- 未偏離「全日本台灣活動聚合」的使命；`docs/monthly_review/2026-09.md` 沒有紅燈爬蟲項目，暫無更高優先的斷流事項排擠。
- 警示：這是治理元任務。plan-critic SKILL L95–121 已記錄「只批評元任務」的封閉迴圈風險；本計畫越長，越會排擠業務工作。

## 2. 複雜度 vs 價值 — ⚠ 複雜度 > 價值

| 項目 | 依據 | 評估 |
|---|---|---|
| Phase A | 約 17 個 canonical 檔＋5 個 spec＋3 個 historical 標註＋sync | medium |
| Phase B | sync script 改寫、16 份 frontmatter、新測試套件、B-0 spike | high |
| Phase C | 新 hook 系統、遞迴 shell parser、11 條規則 × ≥3 個變體 ≈ 35+ fixtures、settings.json | very-high |
| 總計 | 4 個 commit（含 Phase 0）、13 個核准點 | **very-high** |
| 業務價值 | 遷移保險，非營收／資料品質 | medium |

**必須警告**：Phase C 的遞迴 parser（`bash -c`／`eval`／`xargs`／`env`／`$'\x67it'` 偵測）是本計畫最大的成本來源，價值卻遞減。runbook 只要求「結構化解析，不以單一寬鬆 substring 取代」，並沒有要求防禦刻意混淆。建議範圍見 §6。

## 3. 優先順序提醒 — 🟢 順序正確，🟡 範圍過大

- A→B→C 順序符合 runbook L232。
- 但 Phase C 的混淆偵測與 prod-db 啟發式應延後到第二批；第一批只做 runbook L351–364 表格明列的項目。

## 4. 全站架構整合分析（核心問題）

### 4.1 結構性矛盾（必須在 Phase A 動工前解決）

**C1. Phase A 與 Phase B 對「Architect／Plan Critic 能否寫檔」互相矛盾。**
- Phase A（計畫 L66–67）把 plan 與 critique 改存 `docs/specs/active/<slug>/`，等於要求這兩個 agent 寫檔。
- runbook L295、L315 規定 Architect／Plan Critic「修改檔案：禁止」「無法使用 Edit／Write 類工具」。
- 計畫把這個問題放進 Q2，並排在 H-B1 決定。這太晚了：Phase A 改寫 agent 文字時就需要答案。**Q2 必須移到 H-A1。** 建議答案：planner 不寫檔，plan／critique 以文字回傳，由 Engineer 或使用者在 Phase 0 建立的 spec 目錄落檔。這是唯一同時滿足 runbook 兩處規定的做法。

**C2. Claude plan mode 本身就需要 Write。**
- runbook 步驟 2 以 `--agent architect --permission-mode plan` 啟動。Claude Code 的 plan mode 會用 Write 寫 `~/.claude/plans/*.md`（本 session 就是如此），並以 ExitPlanMode 結束。
- 若 readonly-planner 的 `tools:` 拿掉 Write、且沒有 ExitPlanMode，B-0 若證實 `--agent` 主執行緒會套用 `tools`，Architect 的標準啟動流程就壞了。**B-0 必須加測這一項**，並在矩陣中明確列出 ExitPlanMode 的處置。

**C3. 角色矩陣與 agent 的實際職責衝突（計畫沒有發現）。**

| Agent | 實際行為（證據） | 計畫給的權限 | 後果 |
|---|---|---|---|
| reviewer | 產出 `docs/skill_scan/YYYY-MM.md` 並 git commit（`reviewer.agent.md` L74） | readonly，不含寫入 | 月度復盤無法落檔 |
| researcher | 執行 `scraper/update_source.py`，對 Supabase `research_sources` 做 `.update()`（`update_source.py` L253；`researcher.agent.md` L30、L67–84） | Read/Grep/WebFetch/WebSearch/Write，**沒有 Bash** | 無法登記來源；而且這是 **production DB 寫入**，計畫完全沒提 |
| architect | 以 `runSubagent` 編排 Engineer→Tester 迴圈（`architect.agent.md` L1175–1180）；用 `vscode_askQuestions` 提問（L1160） | 沒有 Agent、沒有 AskUserQuestion | 編排流程與釐清提問都失效 |
| scraper-expert | 分派來源 subagent | engineer 類「含 Edit/Write/Bash」，沒列 Agent | 無法分派 |

計畫必須逐一處理：要嘛調整矩陣，要嘛在 proposal 寫明「runbook 矩陣與現行 agent 職責衝突，由使用者裁決」。不得沉默套用。

### 4.2 設計問題

- **兩個權威來源**：B1 的 `claude-role` 加上「Copilot `tools:`→Claude 對照」會形成兩份權限資料。lianbu 的 Copilot `tools:` 是唯讀；若 `claude-role` 標成別的值，誰說了算？必須定義：`claude-role` 是唯一權威，Copilot 對照只用來做**一致性檢查**（不一致就讓 `--check` 失敗）。這樣仍滿足 runbook 設計約束 3（L307）。
- **全權限角色不應列白名單**：engineer 類若寫成明確 `tools:` 清單，會漏掉 Agent、Skill、AskUserQuestion、MCP tools。全權限角色應**省略 `tools:`**（繼承全部）或改用 `disallowedTools`；只有受限角色才寫白名單。
- **Copilot 未知欄位**：在 `.github/agents/*.agent.md` 加 `claude-role`，VS Code 的 agent 檔驗證會對不支援的屬性顯示警告。B-0 必須確認這只是警告、不影響載入；否則改用 B2。
- **計畫內小錯**：`.github/skills/agents/architect/SKILL.md` 沒有 `/memories` 或 session memory 命中（rg 已驗證），A1 表 L74 這一列應刪除。

### 4.3 Phase C 技術缺陷

- **Fail-closed 宣稱不成立**：Claude Code hook 只有 exit 2 會阻擋；未捕捉的例外（exit 1）、找不到 `python3`、timeout 都是**非阻擋**，也就是 fail open。hook 主程式必須用 top-level `try/except` 讓所有錯誤都 `exit 2`，並加一個「hook 內部拋例外 → 仍阻擋」的測試。
- **路徑含空格**：worktree 路徑含 `Tokyo Taiwan Radar`。fixture tmp 目錄必須故意含空格，驗證 `"$CLAUDE_PROJECT_DIR"` 引號正確。
- **規則誤傷**：
  - `git clean` 對 `-d`／`-x` 也阻擋，會擋到 `git clean -n -d`（dry-run）。只應在出現 `-f`／`--force` 時阻擋。
  - `env-dump` 必須允許 `env -u ANTHROPIC_API_KEY claude ...`（runbook 步驟 2 的標準啟動命令）與 `env VAR=x cmd`；只擋無參數的 `env`。
  - `.env*` 規則必須排除 `.env.example`，並且不能擋 `git check-ignore -v scraper/.env`（計畫自己列為必須允許）。規則應以「讀取內容的動詞＋路徑」判斷，不能只看路徑字串。
  - `obfuscation` 對 `$(...)` 的判準模糊；`$(git rev-parse HEAD)` 是日常用法。必須定義成「替換結果流入命令動詞位置」才阻擋。
- **force-push 家族不完整**：漏了 `git push --delete`、`git push origin :main`、`--mirror`。這些與 force push 同等危險，應納入 git-force-push 規則。

### 4.4 Guard 檢查

本計畫不涉及 Category／Event Form／i18n／FC lock／SCRAPERS list 等業務 Guard，也沒有 migration、i18n key 或新 scraper。必檢清單全部不適用。

## 5. 既有資產復用 — 🟡 部分新增

- 應復用：`scripts/sync_ai_adapters.py` 既有的 `pinned_models` 檢查與 MARKER 機制（計畫已採用 ✅）；`.githooks/pre-commit` 的 secret scan 樣式，可作為 hook 中 secret 遮罩的參考實作。
- 新增 `scripts/tests/` 與 `scripts/claude/tests/` 合理，但 repo **沒有任何 CI 或 githook 會跑 `sync_ai_adapters.py --check` 或這些 pytest**（`.github/workflows`、`.githooks` 都沒有命中）。不接進任何自動檢查的測試很快就會失效。至少要在 `tasks.md` 列為後續項目。

---

## 6. 對照 runbook §六：驗收項目缺口

| runbook 驗收項 | 位置 | 計畫覆蓋 | 判定 |
|---|---|---|---|
| A：`rg` 每個剩餘命中都能解釋 | L266–276 | 計畫 L106–118 | ✅ |
| A：historical 相鄰標示 | L260 | A3 | ✅ |
| A：sync `--check` 通過 | L277 | ✅ | ✅ |
| A：「linked normative history」搜尋 | L256 | 只處理 engineer history L1822 | 🟡 scraper-expert history 的 2 處沒有判定是否仍被當規則 |
| **B：Architect 無法使用 Edit／Write** | L315 | Q2 保留「Write＋hook 限路徑」選項 | 🔴 **與驗收直接衝突**（見 C1） |
| B：Tester 不能改產品程式碼 | L316 | 拿掉 Edit/Write，Bash 寫入列為殘餘風險 | 🟡 可接受，但報告必須寫「部分達成」，不能寫 PASS |
| **B：Engineer 不能自行 push** | L317、L335 | Phase B 延後到 C；**Phase C 明確不攔 push**（計畫 L259） | 🔴 **沒有任何 phase 負責** |
| **B：V-M-D push 前仍需人工核准** | L318 | 只靠 prose＋「不加入 allow list」 | 🔴 沒有技術保證；使用者的 `settings.local.json` 若 allow `git push`，就直接放行 |
| B：16 個 wrapper 可正常載入 | L319 | 只有使用者 `/agents` 目測 | 🟡 需明確斷言「16 個」並記錄在 notes |
| B：idempotent | L320 | ✅ | ✅ |
| B：pinned-model negative check | L321 | 只做 rg 負向搜尋 | 🟡 應補「在 tmp 副本注入 `model:` → `--check` 必須失敗」的測試 |
| B：wrapper 手改被 `--check` 偵測 | L336 | ✅ | ✅ |
| C：每個阻擋／允許案例有測試 | L389–390 | ✅ | ✅ |
| C：rejection 不洩漏 secret | L391 | ✅ | ✅ |
| **C：`claude doctor` 通過** | L392 | Phase C 驗收段**沒有列出**（只在 Phase B 與總表第 4 項） | 🟡 Phase C 加入 `settings.json` 後必須再跑一次 |
| C：新 session 載入 settings | L393 | H-C3 | ✅ |
| C：四個角色 smoke test | L394 | ✅ | ✅ |
| **C：production write 核准不能用「繼續」推定** | L384 | 沒有處理 | 🔴 計畫寫「需人工 handoff」，但沒說明 hook 如何得知已核准；又不允許 bypass flag（L383）。必須明寫：**hook 一律阻擋，由使用者親自在終端執行**，agent 端沒有核准通道 |
| C：單一 hook 停用式 rollback | L398 | ✅ | ✅ |
| 完成定義：push 後驗證 exact SHA | L412 | H-PUSH | ✅ |
| 步驟 5 交付物 2：**Copilot／Claude／Codex surface matrix** | L122 | **完全沒有** | 🔴 遺漏交付物 |

### 缺口的具體修正建議（只標 diff 點，不重寫計畫）

1. **push 閘門（處理 3 個 🔴）**：Phase C 的 `.claude/settings.json` 加入 `permissions.ask: ["Bash(git push:*)"]`。Claude Code 的規則優先序是 deny > ask > allow，所以個人 local 的 allow 也無法讓 push 免提示。測試：在 settings 載入後，Engineer 執行 `git push --dry-run` 必須跳出核准提示。這樣「Engineer 不能自行 push」與「V-M-D 需人工核准」都有技術依據，且不妨礙 V-M-D 運作。
2. **Q2 改到 H-A1**，預設答案為「planner 不寫檔」；Phase A 的 agent 文字依此撰寫；B-0 加測 plan mode 的 Write／ExitPlanMode 相容性（C2）。
3. **矩陣修正（C3）**：reviewer、researcher、architect、scraper-expert 四列必須重新設計，並在 proposal 記錄 runbook 矩陣與現行職責的衝突。researcher 的 `update_source.py` 屬 production DB 寫入，必須納入 prod-db-mutation 規則的考量。
4. **補 surface matrix**：Phase 0 的 `proposal.md` 必須包含 Copilot／Claude／Codex 的 surface 對照（agents、skills、prompts／commands、handoff、state path、tools、hooks 各自的生效範圍）。
5. **Phase C 驗收補 `claude doctor`**，並補「hook 內部例外 → exit 2」與「路徑含空格」兩個測試。
6. **Phase C 範圍收斂**：第一批只做 runbook L351–364 列出的 10 類；`obfuscation` 只保留 `eval`、`base64 … | sh`、`bash -c` 內層遞迴三種；`$'\x..'`、`g''it` 這類字元層混淆移到 `tasks.md` 的後續項目。
7. 刪除 A1 表 `architect/SKILL.md` 那一列；補判定 `scraper-expert/history.md` 的 2 處命中。

---

## 結論與下一步

- **Phase A**：🟢 接受，套用修正 2、7 後即可動工。
- **Phase B**：🔴 退回。C1／C2／C3 沒解決前，不得動 frontmatter。
- **Phase C**：🟡 退回修改。補 push ask 規則、fail-closed 實作、誤傷修正，並收斂範圍。

建議下一步：
- ↩️ **回 Architect 修改計畫**（建議）：請 Architect 依本檔 §4 與 §6 的 7 個修正點修改計畫，特別是先決定 Q2，並補上 surface matrix。
- 🔧 交給 Engineer：只適用於 Phase 0 與修正後的 Phase A；Phase B／C 不得同時交付。
