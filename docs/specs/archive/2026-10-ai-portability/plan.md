# ai-portability 三階段 hardening 計畫（rev.6：依 critique-5-codex 的 R5-1 定點修訂）

> 狀態：**只修訂計畫，不實作**。未修改 repo、未 commit、未 push、未 fetch、未操作 production DB。
> 作者模型：Claude Opus 5.5（`claude-opus-5-5`）；rev.4 作者為 Claude Sonnet 5。與第四、五輪評審 GPT（Codex）不同家族。
> **尚未通過 Plan Critic 複審**：第五輪（`critique-5-codex.md`）判定 rev.5 只有 R5-1 一項阻擋，R4-1～R4-4 全數 CLOSED、§6 建議全部已納入。rev.6 只修 R5-1，須經第六輪窄範圍確認 R5-1 關閉、且 rev.5 → rev.6 沒有其他變動後，才能視為可進 Phase 0；通過前不得標為「已通過評審」。
> rev.5 原檔保留（SHA-256 `fb6b5476…549ff3`，即第五輪審查的版本）。
> Worktree：`/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree`，branch `feat/ai-portability`，HEAD `565c1479`（ahead 1 = runbook commit，未 push；2026-10-06 `git status --short` 無輸出）。
> Campaign base SHA：**固定 `ed09bece`**（handoff Q4 裁決）。每次執行另記「當時的 remote baseline」，兩者分開記錄；本機快取的 origin/main 未 fetch，不得當作遠端最新證據。
> 依據：`plan-rev4.md`（SHA-256 `5ab1ecca…504a5f`，保留原檔）、`critique-4-codex.md`（四項阻擋＋§6 非阻擋建議）、`handoff.md` 2026-10-05 裁決。

## 0. 修改對照表

### rev.5 → rev.6（R5-1）

| 項 | 第五輪阻擋 | 處理 | 位置 |
|---|---|---|---|
| **R5-1** | §6 角色表下方「對齊 Copilot 的理由」段仍寫「若做不到，回報使用者決定是否授予 `Write`」，與裁決 12 的預先核准衝突，Engineer 不知道該直接執行還是停下等決定 | 該段改為引用 §6 判準段與裁決 12：依判準證明需要 Write 時直接授予並重測；Bash 能完成時不授予。刪除「回報使用者決定」。判準段的「不授予，並回報使用者」同步改為「在 `notes.md` 與 H-C3 呈報結果（不需等待決定）」，避免同一歧義 | §6 |
| 存檔與下一步 | rev.6 成為最終版 | §4 第 2 項存檔清單加入 critique-5／critique-6；§9 改為第六輪窄範圍確認 | §4、§9 |

除檔頭說明與上表所列位置外，rev.6 與 rev.5 內容相同（可用 `diff -u plan-rev5.md plan-rev6.md` 驗證）。

### rev.4 → rev.5

本輪只處理第四輪的四個確定衝突與 §6 文字／fixture 修正。**不重開 Q1～Q8，不新增防護規則類別**（第一批仍為 10 類）。rev.3 → rev.4 的對照見 `plan-rev4.md` §0。

| 項 | 第四輪阻擋／建議 | 處理 | 位置 |
|---|---|---|---|
| **R4-1** | Phase A 必改三個 UNDECIDED agent 檔，§1／§8 卻寫成全 campaign 禁改 | 依裁決 2 字面「B、C 不動這四個 agent 檔」統一：**A 依 A1 只遷移 legacy prose 與 handoff `prompt`，權限 metadata 全部不變；B／C 不修改四檔與權限投影**。新增 B-R5 擴充與 C-R12 零 diff 驗證 | §1、§5 A1、§6 範圍、B-R5、C-R12、§8 Out、§8.1 Q8 |
| **R4-2** | masked awk 例外排在一般讀取拒絕之後，永遠到不了 | 規則 7 改為「**層 1 敏感寫入 deny → 層 2 精確 metadata 或精確 masked awk 例外 → 層 3 其他敏感存取 deny**」；例外以單一 simple command 判定、不得位於 pipeline；串接段各自獨立檢查；補負向 fixture | §7 規則 7 |
| **R4-3** | Tester 套用 planner 的「保留 Write」fallback，違反 Copilot 類別子集檢查；B→C gate 與能力聲明不一致 | 拆開兩者：**Tester 投影永不含 Edit／Write／NotebookEdit**，planner fallback 另列；§2 規則 1 明列 B-R6／7／8 的合法 carry-over 分支與 C 端對應項；「無 repo 寫入」全部改成 C-R11 的工具層聲明（含 runbook 措辭表） | §2 規則、B-R7、B-R8、C-R9～C-R11、§4 措辭表、§6 角色表 |
| **R4-4** | Phase 0 的具名 `git stash push -u -m` fallback 違反 `git.instructions.md` L87「never `git stash`」 | 刪除。改為：屬本工作且已到核准點的變更依閘門 commit；否則 STOP 回報，不替他人 stash／commit／清除 | §4 2c |
| §6-1 | A1 語意掃描另有兩個「更新 session memory」 | `workstream-audit.prompt.md` L21、`ledger-topology-reconcile.prompt.md` L18 加入 A1；同檔「不要依賴 session memory」的句子分類為 active 且符合新契約，不改 | §5 A1 |
| §6-2 | heredoc fixture 的 `EOF)"` 與「結束行獨占整行」的自訂契約不一致 | 改為多行 fenced fixture，`EOF` 與 `)"` 分行；重導負例改成 `cat > out.txt <<'EOF'` | §7 |
| §6-3 | 規則 9 對 `\d*` 一邊放行一邊要求首字為 SELECT | 刪除 `\d*` 豁免，任何 backslash 指令一律 deny | §7 規則 9 |
| §6-4 | 缺「exit 0 但 decision JSON 無效」的負向 fixture | launcher 驗證 guard 在 exit 0 時的 stdout（只能為空或合法 decision JSON），否則轉 exit 2；host 端 schema 改版列殘餘風險 | §7 fail-closed、C-R3 |
| §6-5 | psql 未帶 `-X` 時會執行 psqlrc | 依既有「不可檢查的輸入 → deny」原則，psqlrc 視為不可檢查輸入：無 `-X`／`--no-psqlrc` → deny；must-allow 改為 `psql -X -c "SELECT 1"`（此項為 rev.4 自行補充，不在 runbook 清單內） | §7 規則 9、驗收 |
| §6-6 | 敏感路徑邊界未明列 | 明列不涵蓋：只給父目錄的遞迴內容搜尋、未帶敏感名稱的 symlink／alias；寫入覆蓋聲明與殘餘風險，**不新增規則** | §7 規則 7、C-R8、§8 |
| §6-7 | C-R9 只驗一種情境；C-R10「repo 外依 §7 policy」無對應政策 | B-0(2)(3)、C-0(3)、C-R9 一律分 `--agent` 主執行緒與 subagent；C-R10 明定 planner 只允許 `~/.claude/plans/`、tester 全拒、比對前先正規化路徑 | §2、§6 B-0、§7 C-0 |
| §6-8 | 過期文字 | 存檔清單補 critique-4（及 critique-5）；Closer 列參照改 C-R7；surface matrix 與 §7 的 permissions 肯定句改為待 B-0(6)；刪 §8 的 Q8 待裁決句；tasks.md 移除已由規則 7 涵蓋的直接 `.env` 存取 | §4、§6、§7、§8 |
| §2 預算 | 「tokenizer 與規則合計 ≤250 行（僅指 tokenizer）」自相矛盾 | 統一為：`_tokenizer.py` 單檔 ≤250 行；規則不設行數上限，但每條規則都要有 fixture | §7 |
| 裁決 11（2026-10-06 追加） | 使用者確認 R4-1 的解讀 | §1 的「若原意為全 campaign 不改」替代方案移除，改記為已確認 | §1、§8.1 |
| 裁決 12（2026-10-06 追加） | 使用者預先核准：C-R7 證明 Closer 需要 Write 時授予 | 定義「證明需要」的判準、授予範圍（只加 Write）、連帶修改與重測步驟 | C-R7、§6 角色表與判準段、§8.1 |
| 裁決 13（2026-10-06 追加） | 使用者預先選擇 H-C1 (i)：角色辨識失敗時接受殘餘風險、繼續進行 | §2 規則 5 改為依裁決 13 標示後繼續（H-C1 改為呈報點）；只涵蓋角色辨識，ask 失效仍在 H-C1 決定 | §2 規則 5、C-R9、§7 核准點、§8、§8.1、§8.2 #11 |
| §8.2（2026-10-06 追加） | 使用者詢問 NOT TESTED 的後續處理 | 新增 NOT TESTED 處理表：只彙整既有項目的時機、執行者、方法與失敗分流，不新增要求 | §8.2 |

> 本版所有修訂均重新查證 repo（2026-10-06，唯讀）：`tester.agent.md` L4–8 Copilot tools 為 read／search／execute／web；`grep -l '^tools:' .github/agents/**` 只命中 closer、lianbu、tester、vmd（plan-critic 未宣告）；`token-rotation.instructions.md` L125、L196 模板與 critique-4 相符；`git.instructions.md` L87 明文「never `git stash`」；runbook L366–375 的 must-allow 不含 psql。與 handoff 2026-10-05 裁決衝突時，以使用者裁決為準；本版未重開任何已核准選項。

## 1. 本次交付 vs runbook 完整完成（部分 hardening 聲明）

使用者裁決 2 讓 reviewer／researcher／architect／scraper-expert 四個 agent 的**權限投影**延期，所以本 campaign 結束時**不能宣稱 runbook 三缺口全部完成**。對照 runbook：

| runbook 項目 | 本 campaign 結果 | 處理 |
|---|---|---|
| L403 Phase A negative search 通過 | 可達成 | PASS 後勾選 |
| L404「Phase B 權限矩陣已投影並有 negative tests」 | **部分**：12 個受管 agent 已投影；4 個 UNDECIDED | 不勾選，加註「部分（X1–X4 延期）」 |
| L315「Architect 無 Edit／Write」 | **未達成／待裁決**（X1） | 不勾選 |
| L296 Reviewer 禁止修改檔案（矩陣列） | 未投影（延期）；事實上 reviewer 本身不寫檔 | 不勾選，註記證據 |
| L317「Engineer 不能自行 push」 | **部分**：純 `git push` 提示（B）；`-C`／`env`／`bash -c` 變體（C） | B 標部分；C 通過後才勾 |
| L318 V-M-D push 前人工核准 | prose＋`ask`；需使用者實測提示 | PASS-pending-user |
| L405 Phase C hooks 有 positive／negative tests | 可達成（第一批 10 類） | PASS 後勾選，並註明覆蓋聲明 |
| production DB 全面受保護 | **不宣稱**：prod-db 為啟發式；researcher 的 `update_source.py` 與所有「腳本介面的寫入」不在範圍 | 殘餘風險 |
| 「最終切換判定」中「唯讀邊界已由工具限制驗證」 | Architect 不成立；Tester 部分 | 不勾選 |

**四角色的修改範圍（R4-1 統一，全文以本段為準）**：

| 階段 | 對 architect／reviewer／researcher／scraper-expert 的 canonical agent 檔 | 權限 metadata（`tools`、`agents`、`claude-role`、`user-invocable`、`disable-model-invocation`、handoff `label`／`agent`） | 驗證 |
|---|---|---|---|
| A | **只遷移 legacy state 的 prose 與 handoff `prompt`**（依 §5 A1：architect、researcher、scraper-expert 有命中；reviewer 經 2026-10-06 `rg` 無命中，不改） | 全部不變 | A-R3 frontmatter-diff；四檔每個 hunk 記入 `notes.md` 分類帳 |
| B | 不修改 | 不加 `claude-role`；wrapper 不輸出 `tools:`（維持繼承全部） | B-R5 擴充：四檔 canonical 與 generated 相較 A commit 零 diff |
| C | 不修改 | 不變 | C-R12：相較 B commit 零 diff |

依據：裁決 2 的字面是「**B、C 不動這四個 agent 檔**」，並未禁止 A 的 legacy 路徑遷移；裁決 10 的「四角色 agent 檔與權限投影仍不動」以「仍」承接裁決 2，範圍相同。rev.4 把它寫成全 campaign 禁改，與 A1 衝突，本版更正。**使用者已於 2026-10-06 確認此解讀（裁決 11）**。

**共用防線與四角色的關係（R3-5，維持）**：
- **延期的是「權限投影」**：四個 UNDECIDED agent 的 `claude-role`、wrapper `tools:` 本 campaign 都不動，仍繼承全部工具；agent 檔的修改範圍見上表。
- **共用防線不是權限投影**：`.claude/settings.json` 的 `permissions.ask`（B）與 hooks（C）是 project-wide 設定。官方 hooks 文件（code.claude.com/docs/en/hooks，2026-10-05 查證）聲明：settings 來源的 hooks 在 subagent 內同樣執行，stdin 含 `agent_id`／`agent_type`（此為文件聲明，兩種執行情境的實際行為待 C-0(3)／C-R9 實測）；**但文件未明確說明 permissions 規則對 subagent 內 Bash 的適用方式**，此點須由 B-0(6) 實測，未實測前不得宣稱「permissions 對 subagent 生效」。不改四個 agent 檔，不代表其 runtime 行為不受影響。
- **Q8 已裁決：共用防線對四角色生效**（使用者 2026-10-05 確認）。理由：push 閘門與危險命令攔截屬安全底線，且「排除四角色」需要 agent 識別能力，C-0(3) 尚未證實。若使用者要求排除，須先證實 hook 能識別 agent，並另列 C-R 條件；未證實前不得宣稱排除成立。
- 不得用本設計宣稱「B、C 都不影響四角色」。

## 2. Gate 契約

**狀態語意**
- **PASS**：有可重現的命令或測試輸出作為證據。
- **PARTIAL**：僅對列名的子集成立；剩餘子集明列並指定由哪個階段負責。
- **NOT TESTED**：沒有證據（需使用者操作或環境不可用）。不得改寫成 PASS。
- **PASS-pending-user**：自動檢查已 PASS，等使用者貼證據。

**規則**
1. 階段 N 的每個 *Required* 必須屬於下列之一，才能開始階段 N+1：(a) PASS；(b) PASS-pending-user，且使用者證據已補；(c) **僅限下方「合法 carry-over 分支」表列名的項目與條件**：記為 PARTIAL＋Carry-over，並在階段 N+1 成為表中指定的 Required。其他 PARTIAL／NOT TESTED 的 Required 一律阻擋，不得自行比照 carry-over。
2. 未標 Required 的 PARTIAL／NOT TESTED（例如 A 的「資訊性」列、B 的「設計上 PARTIAL」列）為 informational，不阻擋。
3. 本機 commit 可在自動檢查通過後先建立（不 push）；「phase 通過」的宣告等 H-x2 與使用者證據。
4. runbook checkbox 只在 PASS 時勾選；PARTIAL 只加註不勾。
5. Phase C 結束時，所有承接的 carry-over 項必須 PASS。唯一例外：C-R9 在某情境實測證實「不可辨識」或無法完成實測時，該情境的 C-R9／C-R10 無法 PASS，此時依**裁決 13（使用者 2026-10-06 預先選擇 (i) 接受殘餘風險）**處理：受影響情境的 B-R7／B-R8／C-R9／C-R10 記為「PARTIAL－裁決 13 接受」，對外聲明依 C-R11，不得宣稱該情境有工具層寫入限制，Phase C 其餘 Required 照常判定後繼續。Engineer 仍須在 H-C1 呈報哪些情境不可辨識、實際標示與 AGENTS.md 聲明的措辭，供使用者檢視；這不再是停下等待裁決的點。裁決 13 只涵蓋角色辨識；§8.2 #13（ask 完全不生效）仍在 H-C1 依實測結果決定。

**合法 carry-over 分支（B → C）**

| B 項 | 允許記為 PARTIAL＋Carry-over 的條件 | 在 C 成為 Required 的項目 |
|---|---|---|
| B-R6 | 純 `git push` 的 `ask` 已 PASS-pending-user 補證；`git -C … push`、`env X=1 git push`、`bash -c 'git push'` 變體依設計由 C 處理 | C-R5 |
| B-R7 | 情境 P1（某執行情境下 `tools:` 未生效）或 P2（plan mode 需要 Write 才能寫私有 plan 檔），見 B-R7 | C-R9（兩情境）＋C-R10 planner 分支；聲明依 C-R11 |
| B-R8 | 情境 T1（某執行情境下 `tools:` 未生效），見 B-R8 | C-R9（兩情境）＋C-R10 tester 分支；聲明依 C-R11 |

B-R4 為 PASS-pending-user，不屬 carry-over；使用者未補證據前不得開始 C。

**Phase A 必要通過條件**

| ID | 條件 |
|---|---|
| A-R1 | 三條 negative search（**另加語意同義詞補查**：`session memory`、`memories`、`copilot-tracking`、`session plan`、`plan.md`，並涵蓋被連結且仍作 normative guidance 的 history）的每個命中都分類為 active 或 historical；分類帳寫入 `notes.md` |
| A-R2 | active guidance 目標檔無「要求寫入 Copilot-only state」的命中（剩餘僅限標 legacy 的行） |
| A-R3 | **frontmatter-diff**：每個被改動的 `.agent.md`，frontmatter 與 HEAD 相比，除 `handoffs[*].prompt` 外逐 key 相等（B1） |
| A-R4 | `.claude/agents/*.md` 的「建議提示」不含 legacy path（generated 同步證據） |
| A-R5 | `sync` 生成後 `--check` exit 0；**兩次生成的完整檔案集合與內容相同**（B6，見 §5） |
| A-R6 | 範圍檢查：generated 變動的路徑集合 ⊆ 預期集合（`.claude/agents/{architect,plan-critic,designer}.md`；Phase 0 以 `rg` 掃全部 agent frontmatter 確認集合） |
| A-R7 | 5 個 active spec 的「權威計畫」句已依 §5 A3 表改寫 |
| A-R8 | `git diff --check` 通過；diff 路徑 ⊆ 已核准的 Allowed paths（含 §4 擴充） |
| A-R9 | runbook 措辭表已套用（以 `rg` 驗證舊句消失） |
| 資訊性 | R1 `/context` 取證若缺，標 NOT TESTED，**不阻擋** B |

**Phase B 必要通過條件**

| ID | 條件 |
|---|---|
| B-R1 | B-0 spike 結果全數記入 `notes.md`，每項 PASS 或 NOT TESTED＋所選 fallback |
| B-R2 | `scripts/tests/test_sync_ai_adapters.py` 全過（見 §6 測試清單） |
| B-R3 | **靜態**：`.claude/agents/*.md` 數量 = 16 = `len(agent_sources)`，名稱唯一（腳本） |
| B-R4 | **載入**：使用者在 worktree 新 session 執行 `/agents`（或等價列表），16 個皆列出，且**每個來源路徑為 worktree 內的 `.claude/agents/` 檔**（非主工作樹）（PASS-pending-user）。名稱數量不能證明來源 |
| B-R5 | `.claude/skills`、`.claude/commands`、`.agents` 相較 HEAD **零 diff**；**另（R4-1）**`.github/agents/{architect,reviewer,researcher,scraper-expert}.agent.md` 與 `.claude/agents/{architect,reviewer,researcher,scraper-expert}.md` 相較 A commit **零 diff**（證明 B 的 generator 修改沒有改到 UNDECIDED wrapper 輸出） |
| B-R6 | 最小 push `ask`：settings 測試通過＋使用者實測 `git push --dry-run` 出現提示（PASS-pending-user）；變體 → **Carry-over C**（見合法分支表） |
| B-R7 | **planner（plan-critic）工具層無 Edit／Write／NotebookEdit**（不是「無 repo 寫入能力」，Bash 寫入見 C-R11）。PASS 條件：B-0(2) 證實 `tools:` 在 **(a) `claude --agent` 主執行緒** 與 **(b) subagent** 兩種情境都生效，**且** B-0(4) 證實 plan mode 在 `tools:` 不含 Write 時仍可寫 `~/.claude/plans/*.md`。不成立時依情境分流：**P1**＝某情境 `tools:` 未生效 → 該情境 PARTIAL；**P2**＝plan mode 需要 Write → planner 投影改採 fallback-P（白名單加入 Write；plan-critic 未宣告 Copilot `tools:`，不違反 §6 類別子集判準）→ PARTIAL。P1／P2 皆 **Carry-over C**：C-R9＋C-R10 planner 分支成為 Required |
| B-R8 | **Tester 工具層無 Edit／Write／NotebookEdit**。Tester 的投影**在任何情況都不加入 Edit／Write／NotebookEdit**（Copilot 宣告為 read／search／execute／web，加入即違反類別子集判準，`--check` 會失敗；Tester 也沒有 plan mode 需求，不適用 fallback-P）。PASS 條件：B-0(2) 兩種情境 `tools:` 都生效。**T1**＝某情境未生效 → 該情境 PARTIAL＋**Carry-over C**：C-R9＋C-R10 tester 分支成為 Required |
| B-R9 | `claude doctor` 摘要記入 `notes.md` |
| B-R10 | 注入 `model:` 的 tmp 副本 → `--check` 非 0 |
| 設計上 PARTIAL | X1–X4：四個 UNDECIDED 角色的權限投影，不阻擋 |

**Phase C 必要通過條件**

| ID | 條件 |
|---|---|
| C-R1 | C-0 spike 結果記錄（見 §7） |
| C-R2 | 每個阻擋類 ≥3 變體、每個允許案例 ≥1 positive；must-allow 清單（§7）全過 |
| C-R3 | fail-closed 矩陣（§7）全過，**含 output protocol 列：guard exit 0 但 stdout 不是空字串、也不是合法 decision JSON → launcher 轉 exit 2**；host timeout 與 host 端 decision schema 改版為已記錄的殘餘風險 |
| C-R4 | 必測三項：例外→exit 2＋固定訊息；路徑含空格並執行 settings 內完整 command 字串；假 token 不出現在 stderr |
| C-R5 | push 閘門變體（`git -C … push`、`env X=1 git push`、`bash -c 'git push'`）回 ask；force 系列 deny；含 B-R6 的 Carry-over。ask JSON 是否實際觸發提示，以 C-0(5) 與使用者實測為準，未實測標 NOT TESTED |
| C-R6 | settings 加入 hooks 後再跑 `claude doctor` |
| C-R7 | 使用者新 session smoke test：Architect、Engineer、Tester、V-M-D、**Closer（含實際結案寫檔；第三輪 critique §5 要求）**（PASS-pending-user）。若 Closer 結案寫檔證明需要 Write，依裁決 12 授予並重測 Closer（見 §6 判準段） |
| C-R8 | AGENTS.md 有「hooks 與 permissions 為 Claude Code 專屬防線」＋覆蓋聲明（prod-db 為啟發式；未涵蓋清單，**含 §7 規則 7 的敏感路徑邊界：只給父目錄的遞迴內容搜尋、未帶敏感名稱的 symlink／alias 不涵蓋**；共用防線依 Q8 對四角色生效，實際生效範圍待 B-0(6)、C-0(3) 實測） |
| **C-R9（R3-4 新增；R4-3／§6-7 修訂）** | **角色辨識，分兩情境實測**：(a) `claude --agent <name>` 主執行緒；(b) 經 Agent 工具呼叫的 subagent。官方 hooks 文件（2026-10-05 查證）稱 `agent_type` 可標示兩種情境、`agent_id` 只在 subagent 出現，**這只是文件聲明，必須由 C-0(3) 在已安裝版本逐情境實測**，不得只驗 (b) 就套用到 planner 的標準啟動 (a)。**某情境可辨識**：該情境的 C-R10 以辨識結果為依據。**某情境不可辨識**：該情境的 C-R10 無法實作，B-R7／B-R8 該情境維持 PARTIAL，本 campaign **不得宣稱**該情境有工具層寫入限制，依 §2 規則 5 與裁決 13 記為「PARTIAL－裁決 13 接受」後繼續。辨識無法證實時不得宣告該項 PASS |
| **C-R10（R3-4 新增；R4-3／§6-7 修訂）** | **role-conditional 寫入拒絕**（只在 B-R7 或 B-R8 記為 carry-over 時 Required，且只對 carry-over 的情境 Required）。比對前先正規化目標路徑：展開 `~`、轉絕對路徑、`os.path.realpath`（檔案尚不存在時取父目錄 realpath 再接檔名）。**planner 分支**：`Write`／`Edit`／`NotebookEdit` 的目標 ∈ `realpath(~/.claude/plans/)` 之下 → allow；**其他任何路徑（repo 內或 repo 外）→ deny**。**tester 分支**：`Write`／`Edit`／`NotebookEdit` 不論路徑一律 deny，無例外。其他角色不受此規則影響。測試：fixture 專案內 planner Write 被拒；planner 寫 plan 私有路徑允許；planner 寫 repo 外非 plan 路徑（例如 tmp）被拒；`../`、symlink 指向 repo 的 plan 路徑被拒；tester 任一路徑被拒；Engineer Write 在 fixture 專案允許（正向） |
| **C-R11（R3-4 新增；R4-3 擴大適用）** | **能力聲明必須準確**：保留 Bash 的角色，計畫、runbook、proposal、AGENTS.md 一律**不得**寫「無 repo 寫入（能力）」，只能寫「工具層禁用 Edit／Write／NotebookEdit（或 C-R10 hook 拒絕）；Bash 重導寫入為已接受殘餘風險」。「planner 不寫 repo 檔」（Q2／裁決 1）是角色行為規則，與工具層能力聲明分開陳述。規則 7 對敏感路徑的寫入重導拒絕與此獨立，仍 Required |
| **C-R12（R4-1 新增）** | **範圍**：C commit 相較 B commit，`.github/agents/{architect,reviewer,researcher,scraper-expert}.agent.md` 與對應 `.claude/agents/*.md` **零 diff** |

## 3. Context 與風險

Copilot Enterprise 可能被撤銷。repo 已有單一權威（`.github/**`）加 adapter（`scripts/sync_ai_adapters.py`），仍缺：(1) active guidance 仍要求寫 Copilot-only state；(2) 角色權限只在自然語言，sync 不輸出 `tools:`；(3) 無危險操作 hooks（`.claude/settings.json`、`scripts/claude/` 不存在）。三階段依序、各一 atomic commit、獨立驗證。

| ID | 風險 | 緩解 |
|---|---|---|
| R1 | `/context` 載入的是**主工作樹**的 CLAUDE.md／AGENTS.md，不是 worktree 版本（handoff 已知事項），Phase A 後可能矛盾 | Phase A 前後由使用者各跑 `/context` 取證；不改主樹；merge 後收斂；未實測標 NOT TESTED |
| R2 | 主樹舊 `.claude/agents` 與 worktree 同名優先序不明 | B 的 B-R4 用 `/agents` 確認來源路徑（須為 worktree 檔） |
| R3 | hook command 相對路徑解析到主樹 | 一律 `"$CLAUDE_PROJECT_DIR"/…` 加引號；spike 先印解析路徑 |
| R4 | fixture 依賴主樹路徑 | fixture 只用 tmp 目錄與字串 |
| R6 | `tools:`／`--agent`／hook agent 識別欄位未實測 | B-0 無副作用 spike；未證實標 NOT TESTED |
| R7 | 5 個 active spec 各有自己的 worktree／分支，本 campaign 改其行會在日後 merge 產生文字衝突 | 只改指定的「權威句」與相鄰標註（約 8 處）；不改 `notes.md`／`changes-log.md` 這類 append-only 證據檔 |
| R8 | 共用防線對四角色生效，與「四角色不動」的既有理解可能不一致（R3-5） | Q8 已裁決為生效；B-push 與 Phase C 的行為變更須明載於 proposal.md；四檔的修改範圍以 §1 表為準（R4-1） |

## 4. Phase 0：spec 骨架與 Allowed paths（Engineer；需核准）

**Worktree & Spec Tracking**：spec slug `ai-portability`，路徑 `docs/specs/active/ai-portability/`（目前不存在，自 `docs/specs/_template/` 建立）；worktree `ttr-ai-portability-worktree`、branch `feat/ai-portability`，**CONTINUING**（handoff 已登記；Phase 0 第一步以 `git worktree list --porcelain` 再核對）。Engineer 須先讀 `.github/instructions/git.instructions.md § Isolated worktree`，不得假設 worktree 狀態。

1. 新增 `docs/specs/active/ai-portability/{proposal,tasks,notes}.md`；`proposal.md` 以 runbook 為操作基準，記 campaign base SHA。
   - **Base SHA 固定 `ed09bece`**（Q4 裁決）。Phase 0 以 `git merge-base HEAD origin/main` 取證作為佐證，並另記執行當時的 remote baseline（需先 `git fetch origin`；未 fetch 前不得宣稱「最新」）。
2. 通過複審的最終版計畫（目前為 rev.6）存為 `plan.md`；`critique-1-opus.md`、`critique-2-gpt.md`、`critique-3-codex.md`、`critique-4-codex.md`、`critique-5-codex.md` 分別存為 `plan-critique-1.md`～`plan-critique-5.md`；第六輪確認報告 `critique-6-codex.md` 若在 Phase 0 開始時存在，存為 `plan-critique-6.md`（planner 與 Plan Critic 自身不寫 repo 檔，裁決 1）。
2a. **實作 worktree 確認閘門**（SKILL § Worktree 確認閘門、git.instructions § Worktree confirmation gate）：Phase 0 開工前須先向使用者確認實作落在 `ttr-ai-portability-worktree`（CONTINUING），取得明確答覆後才動工；並以 `git --no-pager status --short` 取證主工作樹，若帶他人 WIP 則導回 owning worktree，不在主樹落地。
2b. **Step 0 漂移檢查**：執行開始時 re-confirm HEAD（應為 `565c1479`），`git fetch origin` 後記錄 origin/main 與 `ed09bece` 的關係；偵測到非預期漂移即 STOP 回報，不靜默改 base。
2c. **Engineer 紀律（R4-4 修訂）**：本 worktree 流程**禁止任何形式的 `git stash`**，包含具名的 `git stash push -u -m …` 與以 SHA 還原；依據為 worktree mechanics 的單一權威 `.github/instructions/git.instructions.md` § Work inside the worktree（L87：preview／build／rebase 前工作樹必須乾淨，「If dirty, commit — never `git stash`」）。需要乾淨工作樹時：
   - 變更屬於本工作、且該 phase 已到 commit 核准點（H0／H-A2／H-B3／H-C2）→ 依該閘門整理成 commit。
   - 尚未到核准點、無法合法整理成 commit，或工作樹含他人 WIP → **STOP 回報**；不替他人 stash、commit 或清除，也不以「清理」為由提前 commit 繞過核准點。
   spec 建立後，session／handoff 須記錄 spec slug（對應 architect.agent.md 的 Worktree & Spec Tracking 第 4 項，resumed session 以 `tasks.md` rehydrate）。
3. `proposal.md` 必含：**Surface matrix**（下表）；**衝突紀錄 X1–X4**（標「待使用者另行裁決」）；**本版部分 hardening 聲明**（§1）；**四角色修改範圍表**（§1，R4-1）；**Q8 裁決結果**；**Q2 內容**（= 使用者裁決 1：planner 不寫 repo 檔；plan／critique 由 Engineer 或使用者落檔。此為角色行為規則，工具層能力聲明依 C-R11 另述）。
4. `tasks.md` 後續項目：把 `sync --check` 與新 pytest 接進 CI／githook（目前無）；字元層混淆偵測（`$'\x67it'`、`g''it`、變數拼接）；`xargs`／`env VAR=… git` 深層遞迴；裸 `git stash`；`--no-verify`；經變數間接引用的 `source "$F"`／`. "$f"`；`$VAR` 在 guarded 命令參數位置；敏感路徑的父目錄遞迴搜尋與 symlink／alias 偵測（§7 規則 7 邊界）；script 介面的 production 寫入（`update_source.py`、`qa_auto_fix.py` 等）；X1–X4 裁決後的 Phase B′／C′；reviewer 改投影為 readonly（見 §6 X2）；SQL 函式副作用偵測（見 §7 規則 9 殘餘風險）。（直接寫的 `source .env`／`. .env` 由規則 7 層 3 拒絕，`Edit`／`Write` 寫 `.env*` 由規則 7 工具層拒絕，皆已在第一批範圍內，不列後續項。）

### Allowed paths 擴充（N1，Q5 已核准）

handoff 的 Allowed paths 取自 runbook 範例，不含下列本計畫**必須修改**的檔案：

| 新增路徑 | 用途 | 階段 |
|---|---|---|
| `scripts/tests/`（新目錄） | `test_sync_ai_adapters.py` | B |
| `scripts/campaign-closeout-audit.sh` | legacy 掃描標籤改 `legacy_tracking_plans` | A |
| `docs/evaluation/campaigns/README.md` | 同上說明 | A |
| `docs/specs/security-hardening-plan-RECOVERED.md` | 歷史標註 | A |
| `docs/evaluation/annotator/2026-05-18-baseline-v2.md` | 歷史標註 | A |
| `docs/specs/active/{authoritative-venue-repair,publication-policy,admin-reports-204-cleanup,admin-qa-cleanup,spec-architecture-dashboard}/` | 僅改「權威計畫」句與相鄰標註（§5 A3 表） | A |

其餘（`.github/**`、`.claude/**`、`.agents/**`、`scripts/claude/**`、`scripts/sync_ai_adapters.py`、`AGENTS.md`、`CLAUDE.md`、runbook、spec 目錄）已在原 Allowed paths 內。`.gitignore` 不需改（`.claude/settings.local.json` 與 `.copilot-tracking/` 已在其中）。

### Surface matrix（Copilot／Claude／Codex）

| Surface | Canonical | Copilot（VS Code） | Claude Code | Codex | 本 campaign 影響 |
|---|---|---|---|---|---|
| 專案規則 | `AGENTS.md`、`.github/copilot-instructions.md`、`.github/instructions/*` | 自動注入（`applyTo`） | `CLAUDE.md`→`@AGENTS.md`；instructions 依路徑表手動讀 | 讀 `AGENTS.md`；instructions 手動讀 | A：`AGENTS.md`、`git.instructions.md` |
| Agents | `.github/agents/*.agent.md` | 原生 persona | `.claude/agents/*.md`（generated，16 個） | 無 persona，讀原始檔 | A：3 個 wrapper 的 handoff 建議提示＋§5 A1 的 prose 遷移（含三個 UNDECIDED 檔，權限 metadata 不變）；B：12 個受管角色新增 `tools:`，四個 UNDECIDED 零 diff |
| Skills | `.github/skills/**/SKILL.md` | 原生 | `.claude/skills/*`（generated pointer） | `.agents/skills/*`（generated pointer） | 無 diff（B-R5） |
| Prompts／commands | `.github/prompts/*.prompt.md` | prompt files | `.claude/commands/*`（generated pointer） | 無等價 | A：prompt 內 state 文字改；wrapper 預期零 diff |
| Handoff | agent frontmatter `handoffs` | 按鈕 | 文字建議（adapter 把 `prompt` 原樣輸出） | 文字 | **A：`handoffs[*].prompt` 的 path** |
| State／plan 路徑 | `docs/specs/active/<slug>/`、`~/.ai-notes/ttr/` | 舊：`/memories/session/*`、`.copilot-tracking/` | 同 canonical；plan mode 內部 `~/.claude/plans/` 為工具私有，非權威 | 同 canonical | **A 主題** |
| 工具限制 | frontmatter `claude-role` → sync `ROLE_TOOLS` | `tools:` 別名（不動） | wrapper `tools:` 白名單 | 無工具層限制，僅 prose | **B 主題** |
| Hooks／permissions | `.claude/settings.json`、`scripts/claude/` | 無等價 | PreToolUse hooks（官方文件稱 settings hooks 在 subagent 內執行，待 C-0(3) 實測）、`permissions.ask`（對 subagent 內 Bash 的適用性待 B-0(6) 實測） | 無等價 | B：最小 `ask`；C：hooks；Copilot／Codex 不受保護 |
| Git hooks | `.githooks/pre-commit`、`pre-push` | 共用 | 共用 | 共用 | 不動 |

### Runbook 措辭修訂（併入 Phase A commit）

| 位置 | 現文 | 改為 |
|---|---|---|
| L293 表頭 | 「修改檔案」 | 「repo 寫入（角色規則）」；表下加註：「此欄是角色行為規則。工具層實際限制以 Phase B 投影為準；保留 Bash 的角色不宣稱沒有寫入能力（C-R11）」 |
| L295 Architect／Plan Critic | 修改檔案：禁止 | 禁止（角色規則，裁決 1；plan mode 工具私有的 `~/.claude/plans/` 不計；產出以文字回傳，由 Engineer 或使用者落檔）。工具層：Plan Critic 禁用 Edit／Write／NotebookEdit；Architect 未投影（X1） |
| L296 Reviewer | 修改檔案：禁止 | 禁止（角色規則）；本 campaign 未投影工具限制（X2） |
| L299 Researcher | 只寫研究輸出 | 維持；加註「研究輸出落 `docs/specs/active/<slug>/research/`；是否可寫 production `research_sources` 待使用者裁決（X3）」 |
| L315 驗收 | Architect agent 無法使用 Edit／Write 類工具 | planner 角色在工具層無法使用 Edit／Write／NotebookEdit（Bash 重導寫入為已接受殘餘風險，C-R11）；Architect 因 X1 暫列 UNDECIDED，此項標「部分達成／待裁決」 |
| L316 驗收 | Tester 可執行測試，但不能修改產品程式碼 | Tester 可執行測試；工具層無 Edit／Write／NotebookEdit（Bash 寫入為已接受殘餘風險，C-R11） |
| L333 Negative test | Architect 嘗試建立檔案時被拒絕 | planner 角色以 Write／Edit 在 repo 內建立檔案時被拒絕（plan mode 私有 plan 檔不計；Bash 重導不在此負向測試範圍，列殘餘風險） |
| L334 Negative test | Tester 嘗試編輯 source file 時被拒絕 | Tester 以 Edit／Write 編輯 source file 時被拒絕（Bash 寫入同上，列殘餘風險） |
| L125–126 步驟 5 | Phase 0 建立 spec | 加「plan／critique 由 Engineer 或使用者落檔」 |
| L241–243、L268 | 列舉被移除路徑 | 加註「此為被移除對象清單，非現行規範」 |
| L317 | Engineer 不能自行 push | 加註「B 階段為部分（純 `git push` 提示）；變體由 C 驗證」 |

## 5. Phase A：移除 legacy state path

**契約**：大型跨 session → `docs/specs/active/<slug>/`；小型本機不可提交 → `~/.ai-notes/ttr/`；對話暫時推理 → Claude session（不得為唯一權威）；歷史 Copilot scratch → grandfather、只讀、不新增。

### A1 active guidance（canonical，必改）

**修改邊界**：agent 檔的 frontmatter 內，**允許改** `handoffs[*].prompt` 字串；**禁止改**所有權限與可見性 metadata（`tools`、`agents`、`claude-role`、`user-invocable`、`disable-model-invocation`）以及 handoff 的 `label`／`agent`。理由：adapter 會把 handoff `prompt` 原樣輸出到 `.claude/agents/*.md` 的「建議提示」（`scripts/sync_ai_adapters.py:236-249`），不改則 active legacy guidance 必然殘留。

**四個 UNDECIDED agent（R4-1）**：本邊界同樣適用於 architect、researcher、scraper-expert 三檔，A 只做下表列出的 legacy state 遷移（prose 與 handoff `prompt`），其他段落一字不改；reviewer 經 2026-10-06 `rg -n -i "/memories|copilot-tracking|session memory|memory tool"` 無命中，A 不改。B／C 對四檔的限制見 §1 表與 B-R5、C-R12。

已查證的 frontmatter 內命中：architect L7、L10；plan-critic L7、L10；designer L7（皆為 handoff `prompt`）。Phase 0 以 `rg` 掃全部 agent frontmatter 確認是否還有其他。

| 檔案 | 命中 | 處理 |
|---|---|---|
| `.github/agents/architect.agent.md`（UNDECIDED，僅 A 遷移） | frontmatter L7、L10；本文 L80、L1168、L1173、L1175（2026-10-06 `rg` 重驗） | handoff prompt 改新路徑；「save plan」改為「回傳計畫全文，並指示接手者存入 `docs/specs/active/<slug>/plan.md`（無 slug 則 `~/.ai-notes/ttr/plan.md`）」；L1175 的 `runSubagent` 編排與 L1160 的 `vscode_askQuestions` 不屬 legacy state，不改（X1 範圍） |
| `.github/agents/plan-critic.agent.md` | frontmatter L7、L10；本文 L21、L31、L37、L101、L105 | 讀 plan 改新路徑或由使用者貼入；L105「允許寫入」改「不寫檔，以文字回報」 |
| `.github/agents/designer.agent.md` | frontmatter L7；本文 L115、L120 | design.md 改 spec 目錄或 `~/.ai-notes/ttr/` |
| `.github/agents/researcher.agent.md`（UNDECIDED，僅 A 遷移） | L19、L103、L142、L156 | `.copilot-tracking/research/**` 改 `docs/specs/active/<slug>/research/` 或 `~/.ai-notes/ttr/research/`；僅 prose；`update_source.py` 相關段落（X3）不改 |
| `.github/agents/campaign-closer.agent.md` | L88 | 改「spec tasks.md 未勾選項」；舊 scratch 列 legacy 唯讀檢查 |
| `.github/agents/scraper-expert.agent.md`（UNDECIDED，僅 A 遷移） | L192 | 保留 `.copilot-tracking/` staging 排除，標 legacy；僅 prose |
| `.github/skills/agents/{designer,researcher}/SKILL.md` | L506／L51 | 同上 |
| `.github/instructions/git.instructions.md` | L136–149 | 整段改為新契約表，保留一句 legacy gitignored 說明 |
| `.github/prompts/{authoritative-venue-repair,admin-qa-cleanup,weekly-review}.prompt.md` | 2026-10-05 實測命中：authoritative-venue-repair L13–14、L361；admin-qa-cleanup L36；weekly-review L125 | 去 `/memories/session/*` 與 session memory 寫入要求；weekly-review Step 3「Session Memory」依 Q1 **刪除**，後續 Step 4 **重新編號為 Step 3**，並同步檔內交叉引用。admin-qa-cleanup L38、L138 是「舊 session memory 只能當線索」的限制句，分類為 active 且符合新契約，不改 |
| `.github/prompts/{workstream-audit,ledger-topology-reconcile}.prompt.md`（§6-1 新增） | 2026-10-06 語意掃描：workstream-audit L21、ledger-topology-reconcile L18，授權邊界都含「更新 session memory」 | 授權邊界的「更新 session memory」改為「跨 session 交接寫入 `~/.ai-notes/ttr/`（本機、不提交），不得以 session memory 為唯一權威」；`docs/specs/active/workstream-tracking/` 兩份檔案的授權不變。workstream-audit L16、ledger-topology-reconcile L47 是「不得依賴 session memory」的限制句，分類為 active 且符合新契約，不改 |
| `AGENTS.md` | L54 | 保留對照表，補註「legacy 路徑，僅供閱讀舊檔」 |
| `scripts/campaign-closeout-audit.sh`、`docs/evaluation/campaigns/README.md` | L283–296／L286 | 保留為 legacy 唯讀掃描，標籤改 `legacy_tracking_plans`（N1 已核准） |
| `docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md` | — | 套用 §4 措辭表 |

> `.github/skills/agents/architect/SKILL.md` 不改（2026-10-06 以 `rg -n "/memories|\.copilot-tracking|session memory"` 重驗無命中；Phase 0 仍一併 `rg`）。

### A2 generated

`.claude/agents/{architect,plan-critic,designer}.md` 只經 sync 更新。預期集合以 Phase 0 的 frontmatter `rg` 為準。

### A3 historical 與 active spec 權威文件

不能只補籠統標籤：下列句子**宣稱**某個已不可取得的檔案是「唯一權威」，屬 active 矛盾。逐一改寫為指向 checked-in 權威文件，並保留舊路徑為 historical。

| Spec | 現句（位置） | 改寫後的權威 |
|---|---|---|
| `publication-policy` | `tasks.md` L8–9「`/memories/session/plan.md` 是需求與設計的唯一 authoritative plan」；`proposal.md` L118「Authoritative execution plan」 | 本 spec 的 `proposal.md`（需求與設計）＋ `tasks.md`（進度）＋ `changes-log.md`（交付紀錄）；舊路徑標 historical |
| `authoritative-venue-repair` | `proposal.md` L50「Full execution truth」；L183 閱讀清單 | `proposal.md`＋`tasks.md`；舊路徑標 historical |
| `admin-reports-204-cleanup` | `tasks.md` L8「權威計畫」；`proposal.md` L18「authoritative design lives at」 | `proposal.md`；`notes.md` 為歷史 critique 證據，**其 bytes 不得變動**（proposal L18 已明示，故不改 notes） |
| `admin-qa-cleanup` | `proposal.md` L237 描述「以本 spec 取代 ephemeral 權威指標」 | Phase 0 先讀全文；若該句已是「已完成取代」則**不改**，否則補狀態 |
| `spec-architecture-dashboard` | `proposal.md` L51「詳細計畫：`/memories/session/plan.md`（session 內）」 | `proposal.md`＋`tasks.md`；舊路徑標 historical |

其他 historical 處理：
- `security-hardening-plan-RECOVERED.md`、`annotator/2026-05-18-baseline-v2.md`：加 `Historical／superseded：Copilot session 路徑，已不可取得；以 checked-in 檔案為準`，原文不改。
- `engineer/history.md`（6 處）：原文不改；L1822–1832「執行前先 view /memories/session/」旁加 superseded 註記。
- `scraper-expert/history.md`（實際位置 `.github/skills/scraper-expert/history.md`）L102、L116：行尾「來源」引用，判 historical、非規範；來源括號後補「（Copilot session 路徑，已不可取得；非規範）」。
- `session-analytics/tests/**` 與 fixtures：不動。

**Backward compat**：舊路徑不可取得時，agent 詢問使用者提供 slug 或貼上內容；不靜默 fallback、不雙寫。`.gitignore` 的 `.copilot-tracking/` 保留。

### 驗證

```bash
# negative search（每個命中須可分類）
rg -n "/memories/session|\.copilot-tracking" AGENTS.md .github .claude .agents docs
rg -n -i "session memory|memory tool|/memories/" AGENTS.md .github/agents .github/prompts .github/instructions .github/skills/agents
rg -n "/memories/session|\.copilot-tracking" .github/agents .github/prompts .github/instructions .claude .github/skills/agents/*/SKILL.md   # 僅允許標 legacy 的行
python3 scripts/sync_ai_adapters.py && python3 scripts/sync_ai_adapters.py --check
git diff --check
```

**frontmatter-diff 檢查（A-R3）**：對每個 `git diff --name-only -- .github/agents` 的檔案，以 `sync_ai_adapters.parse_frontmatter` 讀 HEAD 版與工作版，移除各自 `handoffs[*].prompt` 後 dict 必須相等。一次性驗證腳本，結果記入 `notes.md`（不新增進 repo 測試，B 階段的 pytest 才納入長期檢查）。

**冪等檢查（A-R5，B6）**：不使用 `git diff --exit-code`（它比的是「相對 HEAD」，預期修改尚未 commit 時必失敗，且不涵蓋未追蹤新檔）。做法：
1. 第一次生成 → 以 Python 對 `.claude/{agents,commands,skills}` 與 `.agents/skills` 遍歷全部檔案，記錄 `{相對路徑: sha256}`。
2. 第二次生成 → 同樣記錄。
3. 兩份字典必須完全相等（含檔案集合）。
4. `git status --porcelain -- .claude .agents` 的路徑集合另作**範圍檢查**（A-R6），不當冪等證據。

**Rollback**：`git revert <A-commit>`。**核准點**：**H-A1**＝確認標註措辭、runbook 措辭表、§4 Allowed paths 擴充（已由 Q5 核准）；**H-A2**＝commit 前檢視 diff stat、分類帳與 negative search。

## 6. Phase B：角色權限轉成 Claude 工具限制

**範圍（裁決 2＋R3-5＋R4-1）**：`architect`、`reviewer`、`researcher`、`scraper-expert` 四個 agent 的**權限投影**本 phase 不動：不加 `claude-role`、wrapper 不輸出 `tools:`（維持繼承全部）；其 canonical agent 檔在 B 不做任何修改（A 已完成的 legacy 遷移除外，見 §1 表），以 B-R5 擴充驗證零 diff。sync script 以常數 `UNDECIDED_AGENTS` 明列這四者；`--check` 規則：每個 agent 必須有 `claude-role` 或在 `UNDECIDED_AGENTS`，防止新 agent 無聲繼承全權限。**共用防線（§6 B-push、§7 C）對這四者 runtime 生效，見 Q8。**

### B-0 Spike（無副作用；結果入 `notes.md`，先記 `claude --version`）

1. subagent frontmatter 支援欄位（`tools`、`disallowedTools`、`permissionMode`、`hooks`）。
2. **`tools:` 是否生效，分兩情境記錄**（§6-7）：(a) `claude --agent <fixture-role>` 主執行緒；(b) 主 session 經 Agent 工具呼叫同一 fixture 為 subagent。每個情境各記 PASS／NOT TESTED，作為 B-R7（P1）、B-R8（T1）的依據。
3. hook stdin 是否帶 agent 識別欄位，**同樣分 (a)(b) 兩情境記錄**（**C-R9 的前置條件**；C-0(3) 為正式實測）。
4. **plan mode 相容性（只針對 planner）**：disposable tmp 專案，`claude --agent <fixture-planner> --permission-mode plan`：(a) `tools:` 不含 Write 時能否寫 `~/.claude/plans/*.md`；(b) `ExitPlanMode` 是否需明列；(c) 缺一時 runbook 標準啟動是否中斷。決定 planner 白名單是否加 `ExitPlanMode`；不相容則 planner 採 fallback-P（B-R7 的 P2：白名單加 Write，由 C-R10 planner 分支補）。**Tester 不適用此 fallback**（R4-3）。
5. Copilot 對未知欄位 `claude-role` 是否僅警告（無 VS Code 可測則 NOT TESTED，改走 role 表放 sync script）。
6. `permissions.ask` 規則語法：`Bash(git push:*)` 與 `Bash(git push *)` 哪個在已安裝版本有效；deny／ask／allow 優先序；**subagent 內的 Bash 呼叫是否受專案 permissions 約束**（R3-5 的實證基礎）。
7. 無法證實者標 NOT TESTED，改用「settings permissions＋hooks」保守方案。
8. **（新，B-R4）** 同名 wrapper 的來源優先序：新 session `/agents` 列表中，每個 `.claude/agents/*.md` 的來源路徑是否為 worktree 內檔案（R2）。

### 設計

`claude-role` 為**唯一權威**；Copilot `tools:` 只做一致性檢查。全權限角色**省略 `tools:`**，只有受限角色寫白名單。

| claude-role | 對應 agent | Claude `tools:` | 備註 |
|---|---|---|---|
| planner（工具層無 Edit／Write） | plan-critic | Read、Grep、Glob、WebFetch、WebSearch、Bash（唯讀診斷）、AskUserQuestion；ExitPlanMode 依 B-0(4)；**無** Edit／Write／NotebookEdit | Bash 重導寫入屬殘餘風險（C-R11）；若 B-0(4) 不成立，改採 fallback-P（白名單加 Write），由 C-R10 planner 分支補 |
| tester | tester | Read、Grep、Glob、Bash、WebFetch、WebSearch、AskUserQuestion；**無 Edit／Write／NotebookEdit，任何情況都不加入** | 與 Copilot `[read, search, execute, web]` 對齊；**不適用 planner 的 fallback-P**（R4-3）；`tools:` 未生效的情境由 C-R10 tester 分支補 |
| full（省略 `tools:`） | engineer、designer、history-teller、update-history-skill-agent、3 個 scraper subagent | 繼承全部 | push 由 `permissions.ask`（B-push）管 |
| vmd | validate-merge-deploy | Read、Grep、Glob、Bash、WebFetch、WebSearch、AskUserQuestion；**無 Edit** | 對齊 Copilot `[read, search, execute, web]`；push 走 ask（Q6 已核准） |
| closer | close-campaign-retire-worktree | Read、Grep、Glob、Bash、AskUserQuestion；**無 Write**（C-R7 證明需要時依裁決 12 加 Write） | 對齊 Copilot `[read, search, execute]`（Q6 已核准）；結案寫檔可行性見 C-R7 的 smoke test |
| readonly（Q3 已裁決） | lianbu-spokesperson | Read、Grep、Glob、WebFetch | Copilot 用舊名 `read_file`／`semantic_search`／`grep_search`／`fetch_webpage`，需對照 |
| UNDECIDED（不輸出 tools） | architect、reviewer、researcher、scraper-expert | — | 見衝突紀錄；共用防線對其生效（Q8） |

> **對齊 Copilot 的理由（N4，Q6 已核准）**：V-M-D 無 Edit、Closer 無 Write，與 Copilot `tools:` 一致。Closer 本文要求寫結案紀錄與 recovery capsule（`.github/agents/campaign-closer.agent.md:116、121、146`），因此 smoke test 必須實際驗證結案寫檔可完成（見 C-R7，已納入 Closer）。Phase B **不預先放寬**；C-R7 時依下方判準段的 Closer 項與裁決 12 處理：證明需要 Write 時直接授予並重測，Bash 能完成時不授予，兩者都不需停下等待新決定（R5-1）。

**Copilot 一致性判準**：採「能力類別對照」，不是工具名稱逐一相等。

| Copilot token | 類別 | Claude 工具 |
|---|---|---|
| `read`、`read_file` | read | Read |
| `search`、`semantic_search`、`grep_search` | search | Grep、Glob |
| `execute` | execute | Bash |
| `web`、`fetch_webpage` | web | WebFetch、WebSearch |
| `edit` | edit | Edit、Write、NotebookEdit |
| `agent`／`runSubagent` | agent | Agent |

判準：對**有宣告 Copilot `tools:`** 的 agent（目前為 tester、closer、vmd、lianbu；2026-10-06 `grep -l '^tools:'` 重驗），Claude `tools:` 的類別集合必須 ⊆ Copilot 類別集合，另允許通用的 AskUserQuestion。Copilot 出現對照表以外的 token → `--check` 失敗並指出該 token（強迫補表，不靜默略過）。沒有宣告 `tools:` 的 agent 不受此限。

**本判準對 fallback 的效果（R4-3）**：
- planner 的 fallback-P（加 Write）不違反判準：plan-critic 未宣告 Copilot `tools:`。
- Tester 若加入 Write／Edit／NotebookEdit（edit 類別）必定違反判準，`--check` 失敗。這正是 Tester 不得套用 fallback-P 的原因，也是 B-R2 的負向測試之一。
- **Closer（裁決 12，2026-10-06 使用者預先核准 H-C3）**：Phase B 仍依 Q6 投影為無 Write，不預先放寬。C-R7 時依下列判準處理：
  - **「證明需要」的判準**：Closer 依 agent 本文執行一次結案（disposable fixture campaign），因工具層沒有 Write 而無法完成結案紀錄或 recovery capsule 的寫入（被拒、中斷或回報做不到），並把該次輸出記入 `notes.md`。若 Closer 改用 Bash 完成寫入，記為「不需 Write」，**不授予**。兩種結果都記入 `notes.md` 並在 H-C3 呈報，不需等待新決定（R5-1）。
  - **授予範圍**：只在 closer 的 `ROLE_TOOLS` 加 `Write`；不加 Edit、NotebookEdit。
  - **連帶修改（必要）**：`campaign-closer.agent.md` 的 Copilot `tools:` 由 `[read, search, execute]` 改為 `[read, search, execute, edit]`，否則類別子集判準讓 `--check` 失敗。副作用：Copilot 版 Closer 也會取得 Copilot 的 edit 工具；本版採此做法以維持單一一致性規則。若使用者不希望改動 Copilot，替代方案是在 sync script 為 closer 設一個具名、受測試的例外，需在 H-C3 另行指示。
  - **重測**：以獨立 commit 修改（`ROLE_TOOLS`、Copilot `tools:`、generated wrapper），重跑 `sync`、`--check`、B-R2 pytest（closer 投影測試同步更新）、B-R3、B-R5 擴充、C-R12，再重跑 C-R7 的 Closer smoke test。
  - **殘餘風險**：Write 沒有路徑限制，Closer 可寫 repo 內任何路徑；與它原本就有的 Bash 能力同級，不另加規則。

### 衝突紀錄（寫入 `proposal.md`，待使用者另行裁決；B、C 不動這四個 agent 檔）

| ID | runbook 規定 | 現行行為（證據） | 狀態 |
|---|---|---|---|
| X1 architect | 唯讀、無 repo 寫入 | `architect.agent.md` L1175–1180 以 `runSubagent` 編排 Engineer→Tester；L1160 用 `vscode_askQuestions`（需 Agent、AskUserQuestion） | 維持全權限；runbook 驗收「Architect 無寫入」= **未達成／待裁決** |
| X2 reviewer | 唯讀 | `reviewer.agent.md` L35 明文「這是一個**唯讀**的分析 Agent，不修改任何檔案」；`docs/skill_scan/` 報告由 workflow `monthly_health_check.yml`（「Commit scan report」步驟，L118–125）以 `skill_scanner.py` 產出並 commit，不是 reviewer 寫檔。**首輪批評的「reviewer 會寫檔」是事實錯誤，衝突不存在。** | 依裁決 2 本 campaign 仍不動；建議列後續項（改投影為 readonly），使用者可在 H-B1 選擇提前 |
| X3 researcher | 「只寫研究輸出」 | L30、L67–84 執行 `scraper/update_source.py`，對 `research_sources` 做 `.update()`（`update_source.py` L253）＝ **⚠ production DB 寫入** | 維持現況；C 的 prod-db 規則**不涵蓋**此路徑，須明標為未保護的 production 寫入面 |
| X4 scraper-expert | 矩陣無此列 | 以 `agents:` 分派 3 個來源 subagent、寫 scraper | 維持現況；建議歸 full，待裁決 |

### B-push（最小 push 閘門移入 B）

- 新增 `.claude/settings.json`，**只含** `permissions.ask: ["Bash(git push:*)"]`（語法以 B-0(6) 結果為準）。C 階段在同一檔加 `hooks`，不得移除 `permissions`。
- `.claude/settings.json` 不含 MARKER，sync 不會覆寫（`generated_files()` 只掃含 MARKER 的 `.md`）；以測試鎖定。
- 測試：`scripts/tests/` 或 `scripts/claude/tests/test_settings.py` 驗證 JSON 有效、含 ask 規則、無任何 `allow` 命中 `git push`、無 bypass 模式。
- 使用者實測（disposable 專案，本機 bare remote，路徑含空格）：以 Engineer 身分執行 `git push --dry-run`，必須出現核准提示。不對本 repo `origin` 做任何 push。
- **如實標示**：這只涵蓋純 `git push` 前綴。`git -C … push`、`env X=1 git push`、`bash -c 'git push'` 可能繞過前綴規則，**由 C 的 hook 補**。因此 runbook L317 在 B 結束時為 **PARTIAL**。

### 檔案與測試

- 改：`scripts/sync_ai_adapters.py`（`ROLE_TOOLS`、Copilot→Claude 類別對照、`UNDECIDED_AGENTS`、輸出 `tools:`；保留 `pinned_models` 檢查與 MARKER）。
- 改（canonical）：僅「受管」的 12 個 agent frontmatter 加 `claude-role`（4 個 UNDECIDED 不改）；`AGENTS.md` 加角色權限說明（Codex 無工具層限制）。說明的措辭依 C-R11：寫「工具層禁用 Edit／Write／NotebookEdit」，不寫「無 repo 寫入」。
- generated：`.claude/agents/*.md`（16 個；僅受管者多 `tools:`）；`.claude/skills`、`.claude/commands`、`.agents/skills` **零 diff**。
- 新增 `scripts/tests/test_sync_ai_adapters.py`：
  1. role→tools 投影；未知 role 失敗；agent 缺 role 且不在 `UNDECIDED_AGENTS` 失敗。
  2. Copilot 類別一致性（正、負向，含未知 token 失敗）。負向 fixture 必含「tmp 副本把 Write 加進 tester 投影 → `--check` 失敗」（R4-3）；正向 fixture 含「planner 投影加 Write（fallback-P）→ 不違反判準」。
  3. tmp 副本注入 `model:` → `--check` 非 0。
  4. 手改 wrapper（加 `Write`）→ `--check` 報 `changed`。
  5. **冪等（B6）**：在 tmp 副本連跑兩次生成，比對兩次的完整 `{路徑: sha256}` 字典（含檔案集合）相等，且 `check()` 回 0；非生成檔不被改動；stale 的 MARKER 檔被移除。
  6. **wrapper 數**：`len(wrappers) == len(agent_sources) == 16`、名稱唯一（對應 B-R3；與「載入」分開）。
  7. 重用 `agent_outputs()`、`expected_outputs()`、`check()`、`pinned_models()`，不另建第二套 generator。

### 驗收

```bash
python3 scripts/sync_ai_adapters.py && python3 scripts/sync_ai_adapters.py --check
python3 -m pytest scripts/tests/test_sync_ai_adapters.py -q          # 含冪等（檔案集合）與 wrapper 數
git diff --stat -- .agents .claude/skills .claude/commands           # 必須為空（B-R5）
git diff --exit-code <A-commit> -- \
  .github/agents/{architect,reviewer,researcher,scraper-expert}.agent.md \
  .claude/agents/{architect,reviewer,researcher,scraper-expert}.md   # 必須 exit 0（B-R5 擴充，R4-1）
claude doctor                                                        # 摘要記入 notes.md（B-R9）
```

**Negative test**：手改 wrapper → `--check` 報 `changed`（tmp 副本）；plan-critic 於 fixture 專案以 Write／Edit 建檔被拒（只對 B-0(2)＋B-0(4) 已證實的情境宣告；未證實情境標 NOT TESTED，B-R7 為 PARTIAL，由 C-R9／C-R10 planner 分支接手）；Tester 以 Edit／Write 改 source → 不可用（只對 B-0(2) 已證實的情境宣告；否則 B-R8 為 PARTIAL，由 C-R9／C-R10 tester 分支接手）。Bash 重導寫入不在這兩項負向測試範圍（C-R11）。

**如實標示**：Architect 無寫入（X1）＝未達成；Reviewer 唯讀＝未投影（事實上成立）；planner／Tester＝只聲明「工具層無 Edit／Write／NotebookEdit」且只限已證實的情境，Bash 寫入為殘餘風險；Engineer 不自行 push＝部分（B-push）；V-M-D 人工核准＝PASS-pending-user；Closer 結案寫檔 smoke test＝NOT TESTED 直到使用者實測。

**核准點**：**H-B1**＝角色表、是否提前處理 X2；**H-B2**＝B-0 結果、B-R4／B-R6 的使用者證據；**H-B3**＝commit 前 diff。X1–X4 的最終裁決不在本 campaign。**Rollback**：`git revert`。

## 7. Phase C：危險操作 hooks（第一批 10 類）

**檔案**：在 B 已建立的 `.claude/settings.json` 加 `hooks`；新增 `scripts/claude/{run_hook.sh,pretooluse_bash_guard.py,pretooluse_file_guard.py,_policy.py,_tokenizer.py}`、`scripts/claude/tests/{test_bash_guard,test_file_guard,test_settings,test_launcher}.py`＋fixtures；`AGENTS.md` 加「hooks 與 permissions 為 Claude Code 專屬防線」＋覆蓋聲明。

**Q8 的時序**：Q8 已於 2026-10-05 裁決為「生效」，因此 B-push 與 Phase C 皆可依計畫進行。依 Q8，共用防線**預期**對四角色生效，這是已接受的行為變更，須在 proposal.md 明載；但 `permissions.ask` 是否實際約束 subagent 內的 Bash 待 B-0(6) 實測，hooks 在兩種執行情境的實際行為待 C-0(3)／C-R9 實測，未實測前不得寫成已生效。

### C-0 Spike（無副作用，disposable 專案）

1. **退出碼語意**：hook 回 exit 2 是否阻擋工具；回 exit 1、127、逾時是否**不**阻擋（critique 引官方文件稱非 2 的非零碼為非阻擋；以已安裝版本實測，結果不符則 STOP 回報）。
2. matcher 名稱（`Bash`、`Read`、`Grep`、`Write`、`Edit`、`NotebookEdit`）與 stdin JSON 欄位（`tool_input.command`、`file_path`、`path`、`glob`）。
3. **agent 識別欄位，分兩情境**（**C-R9 依據**）：(a) `claude --agent <fixture-role>` 主執行緒；(b) 經 Agent 工具呼叫的 subagent。逐情境記錄 PreToolUse stdin 是否含 `agent_type`／`agent_id` 及其值；無則記錄該情境不可辨識。
4. `Grep` 工具是否遍歷 gitignored 的 dotfile（決定規則 7 對 `Grep` 目錄搜尋的殘餘風險）。
5. hook JSON 輸出回 `ask` 的格式與是否生效；把實測得到的 decision JSON 形狀寫成 `_policy.py` 常數，供 launcher 的 output protocol 驗證使用（§6-4）。
6. B-0(6) 的結果沿用（permissions 語法、subagent 是否受約束）。

### Push 閘門

1. B-push 的 `permissions.ask` 保留。
2. bash guard 對 parser 找到的任何 `git push` 段（含 `git -C … push`、`bash -c` 內層、`env X=1 git push`）回 `ask`；force 系列仍 deny。
3. 測試沿用 B-push 的 disposable 專案，補三個變體（C-R5）。

### 語法契約（先定義支援範圍，再談規則）

**不用 `shlex.split` 當 shell parser**（它是詞法分析器，不提供 shell 語意）。使用專用小型 tokenizer；`shlex` 只可用於「已確認不含 substitution 的單一 word」。

| 類別 | 處理 |
|---|---|
| 引號 | `'…'` 為 inert data；`"…"` 內掃描 `$(…)`、反引號、`${…}`；`\` 跳脫 |
| 分隔 | `;`、`&&`、`\|\|`、`\|`、`&`、換行；**不要求空格**（`a;b`、`a&&b`、`a\|b` 都須分段） |
| 群組 | `( … )`、`{ …; }`、`$(…)`、反引號、`<( )`／`>( )`：遞迴；與 `bash -c` 共用**深度上限 3**，超過 → deny |
| 控制字 | `if then elif else fi for while until do done case esac in !` 當分隔／空操作，其內命令照常分段檢查（不解釋語意） |
| heredoc | **quoted 分隔符（`<<'EOF'`）= inert data**；unquoted（`<<EOF`）內容掃描 substitution 後遞迴。結束行為「與開頭分隔符完全相同的整行」（bash 語意）；之後的文字重新解析為命令 |
| 重導 | `<`、`<<<`、`>`、`>>`、`>|`、`<>`、`&>`、`2>&1` 切成 redirect token（規則 7 需要目標） |
| 包裝動詞 | 解包 `env [-u VAR] [VAR=x]…`、`command`、`builtin`、`exec`、`time`、`nohup`、`git -C <dir>`／`git -c k=v`、`bash\|sh\|zsh -c` |
| **不支援 → deny `unsupported-syntax`** | 括號／引號不平衡、深度 > 3、NUL 或異常控制字元、無法確定 heredoc 結束。**不**因「看不懂」而放行 |
| 明確**不在**第一批 | 字元層混淆（`$'\x67it'`、`g''it`、變數拼接）→ `tasks.md`（裁決 3）；殘餘風險列出 |

**substitution 規則**：
1. **所有** `$(…)`、反引號的內層，一律走同一套規則引擎遞迴檢查；內層命中任一規則 → deny。**沒有「外層動詞安全就整體安全」的捷徑**（但見下方 R3-1 受限例外，它是明列的窄例外，不是捷徑）。
2. **動詞位置**的 substitution（`$(echo git) reset --hard`）→ deny `dynamic-verb`。
3. **guarded 命令（git、psql、supabase）的參數位置**若出現 substitution，只放行內層屬於 `{git rev-parse …, git branch --show-current, pwd}` 的形式，以及下方 R3-1 受限 heredoc 例外；其他 → deny `dynamic-args`。
4. 非 guarded 命令的參數位置：內層通過規則引擎即放行。

**受限 heredoc commit 例外（R3-1，N3）**

日常 commit 寫法（`git commit -m "$(cat <<'EOF'`、訊息、獨占一行的 `EOF`、獨占一行的 `)"`，見下方正向 fixture）必須放行，但不能因此泛化成「任何 cat substitution 都放行」。只有同時滿足以下全部條件才放行，任一不符即依一般規則（內層 `cat` 位於 guarded 參數位置 → `dynamic-args` deny）：

1. 外層命令恰為 `git commit`，其引數中**唯一的** substitution 是 `-m` 或 `--message` 的值（不得出現在其他旗標值、路徑或動詞位置）。
2. 內層命令恰為 `cat`，**無其他引數、無額外重導**；唯一的輸入來源為 `<<'DELIM'`（分隔符為 quoted）。
3. heredoc 結束行為與開頭分隔符**完全相同的一整行**（無前後空白）；body 視為 inert data，不掃描、不解析。
4. 結束行之後到 `)` 之前**不得有任何命令文字**；若有，內容依一般規則遞迴檢查（即使只是 `git reset --hard`，亦因 #4 不符而落入一般規則，並被 deny）。
5. 整個 commit 命令的其餘段（`&&`、`;` 串接的其他命令）各自獨立檢查，不因前段通過而豁免。

**R3-1 fixture（§6-2 改為多行 fenced 形式，與條件 #3「結束行獨占整行」一致）**

fixture 以下列逐字多行字串存入測試檔（建議放 `scripts/claude/tests/fixtures/heredoc/*.txt`，一案一檔，保留換行與行首空白）；不得再用單行加 ⏎ 的簡寫表示。

正向 HP1（必須 allow；body 含危險字串為 inert data）：

```text
git commit -m "$(cat <<'EOF'
docs: why git reset --hard is blocked
EOF
)"
```

負向（必須全部 deny）：

HN1 結束行後、`)` 前仍有命令（#4）：

```text
git commit -m "$(cat <<'EOF'
x
EOF
git reset --hard
)"
```

HN2 unquoted 分隔符，body 的 substitution 會展開（heredoc 規則）：

```text
git commit -m "$(cat <<EOF
$(git reset --hard)
EOF
)"
```

HN3 內層 `cat` 有額外引數，且為敏感路徑（#2、規則 7）：

```text
git commit -m "$(cat .env <<'EOF'
x
EOF
)"
```

HN4 內層 `cat` 有額外重導（#2）：

```text
git commit -m "$(cat > out.txt <<'EOF'
x
EOF
)"
```

HN5 串接段各自檢查，force 段 deny（#5）：

```text
git commit -m "$(cat <<'EOF'
x
EOF
)" && git push --force
```

HN6 結束行有尾隨空白，不等於分隔符（#3）→ tokenizer 無法確定 heredoc 結束 → deny `unsupported-syntax`：

```text
git commit -m "$(cat <<'EOF'
x
EOF␠
)"
```

（`␠` 代表一個實際空白字元；測試檔中寫真正的空白，不寫符號。）

HN7 結束分隔符與 `)"` 同行（`EOF)"`）→ 不符合條件 #3，例外不適用；tokenizer 不支援此形式 → deny `unsupported-syntax`。第四輪評審已以 Bash 語法檢查確認此形式**不一定是** bash syntax error，因此這是本 guard 的保守選擇，fixture 只斷言 guard 結果，不斷言 bash 行為：

```text
git commit -m "$(cat <<'EOF'
x
EOF)"
```

**複雜度預算（§2 預算修正）**：`_tokenizer.py` 單檔目標 ≤ 250 行（不含註解與空行）。規則（`_policy.py`）不設行數上限，但每條規則都必須有對應的正向與負向 fixture。只有當 must-allow 清單中的 fixture 失敗時才擴充 tokenizer 語法；否則「不支援 → deny」。若 tokenizer 預算將被超過，**停下回報使用者**，不自行補成完整 interpreter。

**fixture（B3，節錄；完整表在 `tasks.md`）**

| 阻擋 | 允許 |
|---|---|
| `printf '%s' "$(git reset --hard)"` | `echo 'git reset --hard'`（單引號 inert） |
| `echo $(git clean -fdx)`、``echo `git reset --hard` `` | `git commit -m "docs: why git reset --hard is blocked"` |
| `echo $(echo $(git reset --hard))`（巢狀） | 受限 heredoc commit 正向 fixture（見上） |
| `echo hi;git reset --hard`、`echo hi&&git reset --hard` | `echo "a;b"`（引號內分隔符） |
| `git reset --hard\|cat`、換行串接 | `git log "$(git rev-parse HEAD)"`、`printf '%s' "$(git rev-parse HEAD)"` |
| `(git reset --hard)`、`{ git reset --hard; }`、`if true; then git reset --hard; fi` | `echo "\$(git reset --hard)"`（跳脫後為字面） |
| `bash -c "echo $(git reset --hard)"` | `git diff --check`、`git fetch origin main` |
| `$(echo git) reset --hard`（動詞位置） | `git push origin $(git branch --show-current)`（走 ask，非 deny） |
| `git push origin $(echo --force)`（guarded 動態參數） | |
| 上列 R3-1 負向 fixture HN1–HN7 | |

### fail-closed（B5）

**問題**：`main()` 外層 `try/except` 抓不到進入 handler 前的 syntax error 或頂層 import failure；這類失敗讓 Python 以 exit 1 結束，屬**非阻擋**，工具會照常進入正常權限流程。

**設計**：settings 內 command 為一個**最小 inline 外殼**，把一切非預期失敗轉成 exit 2：

```
[ -f "$CLAUDE_PROJECT_DIR/scripts/claude/run_hook.sh" ] && exec bash "$CLAUDE_PROJECT_DIR/scripts/claude/run_hook.sh" <guard-name> || exit 2
```

`run_hook.sh`（launcher）：
- `command -v python3` 失敗 → exit 2＋固定訊息。（缺 python3 為 **fail-closed**，不是 fail open。）
- 執行 guard；**exit 0 才放行**；exit 2 → 轉發 guard 的 stderr（規則 id＋簡短原因＋安全替代）；**任何其他退出碼**（syntax／import error、未捕捉例外）→ 丟棄 guard 的 stderr，只輸出固定訊息 `ttr-hook: internal error, blocked`，exit 2。
- **output protocol（§6-4）**：guard exit 0 時，launcher 擷取其 stdout。空字串 → 放行（launcher 不輸出任何東西）。非空 → 以 python3 驗證：必須是單一合法 JSON，且形狀等於 `_policy.py` 中由 C-0(5) 實測得出的 decision 常數（只允許 guard 會產生的 `ask`／`deny` 形狀；欄位缺失、值不在允許集合、有多餘輸出都算不合法）。合法 → 原樣轉發 stdout、exit 0；不合法 → 丟棄 stdout，輸出固定訊息，exit 2。理由：官方文件把 exit 0 的無效 JSON 視為非阻擋，若不驗證，push 變體的 `ask` 會靜默失效。
- launcher 的驗證只能保證輸出符合本專案常數；**host 改版使該形狀不再被辨識**時，`ask` 會退化為非阻擋，這是殘餘風險，以 C-0(5) 與 C-R5 使用者實測偵測。
- guard 內部：`main()` 外層 `try/except BaseException` → exit 2；內部 `signal.alarm(N)` watchdog（N < host timeout）逾時 → exit 2。
- guard 絕不把命令原文放進例外訊息或 stderr。

**邊界表**

| 失敗情境 | 結果 | 測試 |
|---|---|---|
| guard 有 syntax error | exit 2（launcher 轉換） | ✔ 注入 fixture |
| guard import 失敗（缺 `_policy.py`） | exit 2 | ✔ |
| stdin 非法 JSON／欄位缺失 | exit 2＋固定訊息 | ✔ |
| policy 載入拋例外 | exit 2 | ✔ |
| `python3` 不在 PATH | exit 2 | ✔（PATH 只含 bash） |
| launcher 檔案缺失 | exit 2（inline `\|\| exit 2`） | ✔ |
| `CLAUDE_PROJECT_DIR` 未設 | exit 2（路徑不存在） | ✔ |
| guard 內部 watchdog 逾時 | exit 2 | ✔（sleep fixture） |
| **guard exit 0，stdout 不是合法 JSON**（§6-4） | exit 2（launcher 轉換） | ✔ 注入 fixture（例：輸出 `{"decision":`） |
| **guard exit 0，JSON 合法但形狀不符**（缺欄位、未知 decision 值、多一段輸出） | exit 2 | ✔ |
| guard exit 0，stdout 為空 | 放行 | ✔（正向） |
| **host timeout 先到** | **fail open（非阻擋）** | ✘ 殘餘風險；watchdog < host timeout 降低機率 |
| **host 改版，本專案 decision 常數不再被辨識** | `ask` 退化為非阻擋 | ✘ 殘餘風險；C-0(5)、C-R5 實測偵測 |
| 使用者以 settings.local 或 `disableAllHooks` 停用 | 不在邊界內 | ✘ 殘餘風險 |

`stderr` 只含規則 id、簡短原因、安全替代；不回顯命令原文；無 bypass flag；production write 一律阻擋（見規則 9 的範圍），使用者親自在終端執行。

### 規則矩陣（對應 runbook L351–364；第一批 10 類）

| # | 規則 id | 阻擋 | 明確允許 |
|---|---|---|---|
| 1 | git-force-push | `git push` 含 `--force`、`-f`（含短旗標群組如 `-fu`）、`--force-with-lease`、`+refspec`、`--delete`、`origin :<ref>`、`--mirror` | 一般 push（走 ask，不 deny） |
| 2 | git-reset-hard | `git reset --hard` | `--soft`、`--mixed`、`reset <path>` |
| 3 | git-clean | `git clean` 含 `-f`／`--force`（`-fd`、`-fdx`、`-xdf`、`-d -f`）**且無** `-n`／`--dry-run` | `-n`、`-nd`、`--dry-run` |
| 4 | git-branch-D | `-D`、`--delete --force`、`-d -f`、`-df` | `-d` |
| 5 | worktree-remove-force | `git worktree remove -f/--force`（含 `-ff`） | 無 force 的 remove |
| 6 | worktree-add-force | `git worktree add -f/--force` | 一般 add |
| 7 | **env-file-access**（路徑導向，三層） | 見下 | 見下 |
| 8 | env-dump | 無參數 `env`、任何 `printenv`、`export -p`、`declare -x`、無參數 `set` | `env -u VAR cmd`、`env VAR=x cmd`（含 `env -u ANTHROPIC_API_KEY claude …`） |
| 9 | prod-db-mutation（啟發式） | 見下 | 見下 |
| 10 | dynamic-shell | `eval`；`base64 … \| sh/bash/zsh`；**stdin 餵入的 shell**（`… \| sh`、`sh -s`、`bash <<EOF` 無 `-c`）；`bash/sh -c` 內層命中任一規則；動詞位置 substitution | 無危險動詞的 `bash -c` |

**規則 7（R3-2 寫入先判；R4-2 修正例外順序）**

敏感路徑定義：任一 token 或重導目標的 basename 符合 `^\.env(\..+)?$`，**排除** `.env.example`、`.env.sample`、`.env.template`。含 glob 字元者以 fnmatch 檢查是否可能匹配（`.env*`、`.e*`、`.*`；比照 bash 預設 dotglob 關閉，`*` 不匹配前導點）。

**判定單位**：tokenizer 先依 `;`、`&&`、`||`、`|`、`|&`、`&`、換行，以及群組／substitution／`bash -c` 遞迴，把命令切成 simple command。**每個 simple command 各自獨立**走下列三層；任何一個 simple command 得到 deny，整條命令即 deny。某段通過不會豁免其他段。

**判定順序**（同一個 simple command 內，前一層有結論即定案，後層不得推翻前層）：

- **層 1 敏感寫入／重導 → deny `env-file-write`（永遠先判；層 2 的任何例外都不能推翻）**：敏感路徑出現在下列任一位置：
  - 重導目標：`>`、`>>`、`>|`、`<>`、`&>`（含 `&>>`）。
  - 會寫入的動詞之引數：`tee`、`cp`／`mv` 的目的端、`sed -i`、`awk -i inplace`、`dd of=`、`install`、`touch`、`rm`、`truncate`、`ln`。
  - 例：`wc .env > .env`、`git check-ignore .env > .env`、`<masked awk 模板> > .env` 在此層即 deny。
- **層 2 精確例外 → allow**（只在層 1 未命中、且該 simple command **完全沒有重導**時評估；不符合任何一項即進入層 3）：
  - **2a metadata 白名單**（完整參數形式，不接受額外旗標或多路徑）：
    - `git check-ignore -v <path>`、`git check-ignore --no-index <path>`。
    - `git ls-files --error-unmatch <path>`。
    - `test -f|-e|-s|-r <path>`、`[ -f|-e|-s|-r <path> ]`、`[[ … ]]` 同形式。
    - `stat <path>`、`ls -l <path>`、`wc -l <path>`。
  - **2b masked awk 模板（N2）**：該 simple command 去除前導空白後，**逐字等於** `token-rotation.instructions.md` 規定的模板。2026-10-06 查證：L125 為 `cd scraper && ` 加模板，L196 為縮排後的同一模板；模板本體為
    `awk -F= '/^GITHUB_TOKEN=/{print "GITHUB_TOKEN present, len="length($2)", prefix_ok="(($2 ~ /^github_pat_/)?"yes":"no")}' .env`
    另須同時滿足：(i) 無 `-f`、無任何其他引數；(ii) 無重導；(iii) **不在 pipeline 內**：與相鄰命令只能以 `&&`、`;` 或換行連接，前後出現 `|`、`|&` 或背景 `&` 都不適用例外。
    - 模板以常數放在 `_policy.py`；guard 執行時**不讀** instructions 檔。
    - `cd scraper && <模板>` 不需特例：`cd scraper` 是另一個 simple command，獨立判定，不涉及敏感路徑；模板段走 2b。之後若再串接 `&& cat .env`，該段在層 3 deny。
- **層 3 其他敏感存取 → deny `env-file-access`**：敏感路徑出現在任何其他引數，或作為 `<`、`<<<` 的輸入，且未被層 2 放行。例：`cat`、`rg`、`grep`、`cp` 的來源端、`git add`、`source .env`、`. .env`、任何非模板的 `awk`。

**masked awk fixture（R4-2）**
- 正向（必須 allow）：AP1 `cd scraper && <模板>`；AP2 `  <模板>`（前導空白，對應 L196）；AP3 `<模板>; git status --short`（`;` 串接，後段獨立判定通過）。
- 負向（必須 deny，括號內為預期規則 id）：(a) 模板程式字串改一個字元（`env-file-access`）；(b) 追加 `-f script.awk`（`env-file-access`）；(c) `<模板> > out.txt`（有重導，層 2 不適用 → `env-file-access`）；(d) `<模板> | tee x`（pipeline → `env-file-access`）；(e) `<模板> > .env`（層 1 `env-file-write`）；(f) `cd scraper && <模板> && cat .env`（第三段 `env-file-access`）；(g) `<模板> scraper/.env`（多引數 → `env-file-access`）；(h) `<模板> &`（背景 → `env-file-access`）。
- **漂移測試**：測試讀取 instructions 檔，抽出所有對 `.env` 的 `awk` 行，去除 `cd scraper && ` 前綴與前導空白後，斷言 (1) 每一行都被放行，(2) 抽出集合與 `_policy.py` 常數集合相等。instructions 改了而 hook 沒跟（或反之），測試即失敗。

- **工具層**：`Read`、`Grep` 的 `file_path`／`path`／`glob` 指向敏感路徑 → deny；`Write`、`Edit`、`NotebookEdit` 指向敏感路徑 → deny（不論 role）。
- 其他允許（不命中上述時）：`git check-ignore -v scraper/.env`、`git ls-files --error-unmatch scraper/.env`、`[ -n "$VAR" ]`、`${#VAR}`。
- 涵蓋：`rg '^' scraper/.env`、`grep . < scraper/.env`、`cat < .env`、`cp .env /tmp/x`、`git add scraper/.env`、`while read l; do …; done < .env` → 皆 deny。
- 與 rev.2 的差異：範圍從「讀內容」擴為「除層 2 精確例外外的任何存取，寫入層無豁免」，因此 `rm`、`>` 覆寫 `.env` 也被擋。**Q7 已核准此擴大**；rev.5 只調整例外的評估順序，未改變 Q7 的範圍。
- 測試：fixture 的 `.env` 只放假值 `FAKE_TOKEN=sk-TESTONLY-…`；policy 對 `.env*` 做 open 的 spy／monkeypatch 必須零次呼叫（hook 本身不得讀 secret）。
- **邊界（§6-6；不涵蓋，列殘餘風險，不新增規則）**：本規則是**字面路徑檢查**，只看 token 與重導目標本身，不是完整的資料外洩防線。下列情形不涵蓋：
  - 只給父目錄、由工具遞迴讀到 `.env` 的內容搜尋，例如 `grep -r TOKEN scraper/`、`rg -uu TOKEN scraper/`（`rg` 預設尊重 `.gitignore` 並略過隱藏檔，加 `-uu`／`--hidden --no-ignore` 後才會讀到）。
  - 不含敏感 basename 的別名路徑：事先存在的 symlink、hard link，或其他指向 `.env` 的路徑。
  - 工具層 `Grep` 以父目錄為 `path` 的遞迴搜尋：依 C-0(4) 實測結果記錄，不預先宣稱已涵蓋。
  - 上述邊界寫入 AGENTS.md 覆蓋聲明（C-R8）與 §8 殘餘風險；偵測列為 `tasks.md` 後續項，本 campaign 不做全檔案系統追蹤。

**規則 9（prod-db，明確為啟發式；R3-3 修正）**

- 阻擋：`supabase db push`（所有形式，**唯一例外**為精確命令 `supabase db push --dry-run`）；Phase 0 以 `supabase --help` 列舉的其他寫入型子命令（如 `db reset`、`migration up`）。
- `python -c`／`python3 -c` 同時含 `create_client` 與 `.insert(`／`.update(`／`.upsert(`／`.delete(` → deny。`.rpc(` 為殘餘風險（見下）。
- **`psql` 的 SQL 來源必須可檢查，否則 deny**：
  - 無法檢查的輸入（`-f <file>`、`--file`、`< file`、`… | psql`、heredoc 餵入 `psql`）→ deny `unverifiable-sql-input`。
  - **啟動檔（§6-5）**：未帶 `-X`／`--no-psqlrc` 時，psql 會先讀系統與使用者的 psqlrc（PostgreSQL 官方 psql 文件），其內容不在命令字串中、無法檢查 → 依同一原則 deny `unverifiable-sql-input`。支援形式一律帶 `-X` 或 `--no-psqlrc`。這是既有「不可檢查 → deny」原則的套用，不是新規則類別。
  - **每一個** SQL 命令形式都必須通過檢查，任一不通過即 deny。形式包括：`-c SQL`、`-cSQL`、`--command SQL`、`--command=SQL`。
- **單一 SQL 字串通過條件**（全部成立才放行）：
  1. 去除首尾空白與**單一**結尾分號後，不含其他分號 → 否則 deny `multi-statement`。
  2. 不含任何 backslash 指令（`\d`、`\!`、`\i`、`\copy`、`\o` 等一律）→ 否則 deny `psql-meta`。**§6-3：刪除 rev.4 的 `\d*` 列表型豁免**，避免與條件 3 矛盾；需要查 schema 時改用 `SELECT … FROM information_schema.…`。字串常值內的反斜線也會被拒絕，誤殺可接受（失敗方向為安全）。
  3. 首個關鍵字為 `SELECT`、`SHOW`、或不含 `ANALYZE` 的 `EXPLAIN` → 否則 deny `non-readonly-keyword`。
  4. 整段**不含**下列整字（大小寫不敏感）：`INTO`、`INSERT`、`UPDATE`、`DELETE`、`MERGE`、`CREATE`、`ALTER`、`DROP`、`TRUNCATE`、`GRANT`、`REVOKE`、`COPY`、`CALL`、`DO`、`VACUUM`、`REINDEX`、`CLUSTER`、`LOCK`、`SET`、`WITH`、**`FOR`（`SELECT … FOR UPDATE／SHARE` 取得列鎖，複核新增）** → 否則 deny `write-keyword`。`INTO` 涵蓋 `SELECT INTO`；`WITH` 保守拒絕 data-modifying CTE（`WITH x AS (DELETE …) SELECT …`）。字串內出現這些字也會被拒絕，誤殺可接受（失敗方向為安全）。
- **`--dry-run`**：只對精確 `supabase db push --dry-run` 放行；任意字串中出現 `--dry-run`（例如 `python -c` 的程式碼內）不豁免。
- 其他允許：`psql -X -c "SELECT …"`（通過上述檢查者）、`supabase db diff`（Phase 0 以 `supabase --help` 確認其為只讀）。
- **殘餘風險（明列，不改寫為 PASS）**：
  - `SELECT` 呼叫有副作用的使用者函式（如 `SELECT some_write_fn()`）不被偵測。
  - `python -c` 內的 `.rpc(` 呼叫不被偵測。
  - 字串拼接、變數展開造成的 SQL 內容不可見者，依「不可檢查 → deny」處理，但 python 腳本內部的拼接不在本規則範圍。
- **覆蓋聲明（寫入 AGENTS.md，C-R8）**：此規則只涵蓋 `psql`、`supabase` CLI、內嵌 `python -c` 三條路徑的**直接 SQL 寫入語句與 SELECT INTO**；**所有經由專案腳本的 production 寫入**（`update_source.py`、`qa_auto_fix.py`、`annotator.py` 等，執行時載入 `scraper/.env`）**不在保護範圍**。不得宣稱 production write 全面受保護。

**規則 10（dynamic-shell）**：見規則矩陣。stdin 餵入的 shell（`… | sh`、`sh -s`、無 `-c` 的 `bash <<EOF`）一律 deny，即使 heredoc 內容看似無害。

### 驗收（C）

- 每個阻擋類 ≥3 變體（短旗標、組合旗標、`bash -c` 嵌套、引號、換行串接、substitution 內層），每個允許案例 ≥1 positive；fixture 不執行任何破壞性命令。
- **must-allow 清單**（runbook L366–375＋本版補充）：`git status --short`、`git diff --check`、`git log --oneline`、`git fetch origin main`、clean worktree 上的 `git rebase origin/main`、targeted tests／lint／type-check／build、`python3 scripts/sync_ai_adapters.py --check`、**token-rotation 的 masked awk 精確模板（規則 7 正向 AP1–AP3）**、**受限 heredoc commit（多行正向 HP1）**、`psql -X -c "SELECT 1"`、`supabase db diff`。（runbook 的 must-allow 不含 psql；`psql` 一項是 rev.4 自行補充，rev.5 依 §6-5 收斂為帶 `-X`。）
- must-deny 清單：R3-1 的 HN1–HN7；規則 7 masked awk 負向 (a)–(h)；`wc .env > .env`；`git check-ignore .env > .env`；`psql -c "SELECT 1"`（無 `-X`）；`psql -X -c '\d events'`；`psql -X -c 'SELECT 1; DELETE FROM events'`；`psql -X -c 'SELECT * INTO t FROM events'`；`psql -X -f x.sql`。帶 `-X` 的負例確保每一案都卡在預期的檢查，而不是被「缺 `-X`」提前攔下。
- 必測三項（C-R4）；fail-closed 矩陣（C-R3，含 output protocol 三列）。
- **角色相關（C-R9、C-R10）**：見 §2。planner、tester 的寫入拒絕只在 C-R9 於對應情境證實可辨識時宣告通過；兩種執行情境分開記錄。
- **範圍（C-R12）**：`git diff --exit-code <B-commit> -- .github/agents/{architect,reviewer,researcher,scraper-expert}.agent.md .claude/agents/{architect,reviewer,researcher,scraper-expert}.md` 必須 exit 0。
- 使用者新 session 載入 settings；Architect、Engineer、Tester、V-M-D、Closer（含結案寫檔）smoke test（C-R7）。

**Rollback**：`git revert`，或停用單一 rule id＋補 positive test；不用 `--dangerously-skip-permissions`。
**核准點**：**H-C0**＝Q8（已裁決：生效）；**H-C1** 規則矩陣（特別 #7 三層與 #9 邊界、#10 stdin-fed shell）、push 閘門（含 §8.2 #13：ask 完全不生效時的處理）、C-R9 辨識結果與標示的呈報（不可辨識時的分流已由裁決 13 預先決定為接受殘餘風險，見 §2 規則 5）；**H-C2** `settings.json` 逐行；**H-C3** 使用者新 session smoke test。

## 8. 全域核准、範圍與殘餘風險

**核准點順序**：H0（起點 ed09bece、Allowed paths 擴充已由 Q5 核准、實作 worktree 確認）→ H-A1／H-A2 → H-B1／B2／B3 → H-C1／C2／C3 → **H-PUSH**（H-C0 = Q8 已於 2026-10-05 裁決，不再阻擋）（交 V-M-D，由使用者明確核准、僅 linear fast-forward、驗證 pushed SHA 等於 GitHub main）。任一階段 Required 未過即停止回報。

**In**：三 phase 檔案、`docs/specs/active/ai-portability/`、`scripts/sync_ai_adapters.py`、`scripts/tests/`、`scripts/claude/`、`.claude/settings.json`、§4 擴充清單、runbook 措辭與勾選（實測後）。
**Out**：push、production DB 寫入、secret 旋轉、清理其他 worktree、修改主樹、網站／scraper runtime LLM、重新命名 agent、改寫 history 原文、**四個 UNDECIDED agent 的權限投影（`tools`／`claude-role`）變更，以及 B／C 對這四個 agent 檔的任何修改**（R4-1；A 依 A1 對其中三檔做的 legacy prose／handoff `prompt` 遷移屬 In，權限 metadata 不變，見 §1 表）。注意：**共用防線（permissions、hooks）對這四個 agent 的 runtime 行為生效，不在 Out 之內**，依 Q8 處理（R3-5）。
**不屬本 campaign 但需知**：九月月報 A3／A4 列有 NDL 首次正確率與 kokuchpro 修復延遲（critique 引用，未獨立核實數字）。本 campaign 是開發環境延續，不直接改善資料品質；「目前沒有紅燈爬蟲」不能推論為資料品質無待辦，這些項目仍由其他工作線處理。

**殘餘風險（不改寫為 PASS）**
- R1／R2 NOT TESTED 至使用者實測。
- 「Architect 無寫入」未達成／待裁決；Reviewer 未投影（事實上唯讀）；Tester、planner 的工具層寫入限制視 B-0(2)(4) 與 C-R9 的兩情境結果，可能某情境為 PARTIAL；C-R9 不可辨識時依裁決 13 接受殘餘風險：該情境 planner／Tester 不寫檔只靠角色規則（裁決 1）約束，寫入會出現在 worktree 的 git diff，未經使用者核准不會 push。
- Engineer／V-M-D 的 push 閘門：B 為部分，C 通過後才完整。
- researcher 的 `update_source.py` 與所有腳本介面的 production 寫入**未受保護**。
- prod-db hook 為啟發式，僅涵蓋 `psql`／`supabase`／`python -c`；SELECT 有副作用函式、`.rpc()` 不偵測。
- host timeout 為 fail open；host 改版使本專案 decision 常數不再被辨識時 `ask` 退化為非阻擋；`disableAllHooks`／settings.local 覆蓋不在邊界內；字元層混淆、`$VAR` 拼接，以及**經變數間接引用的** `source "$F"`、`. "$f"` 未涵蓋。（直接寫 `source .env`、`. .env` 由規則 7 層 3 拒絕，非本條殘餘。）
- 規則 7 是字面路徑檢查：只給父目錄的遞迴內容搜尋（`grep -r`、`rg -uu`）、symlink／hard link 等別名路徑、工具層 `Grep` 的父目錄遞迴（待 C-0(4)）不涵蓋。
- Bash 重導寫入對 planner／tester 無工具層防護（C-R11）。
- Codex 只受 Phase A 影響；Copilot 不受任何 hook 保護。
- 四角色的共用防線行為變化已依 Q8 裁決接受；`permissions.ask` 對 subagent 內 Bash 的實際約束待 B-0(6)，hooks 兩情境的實際行為待 C-0(3)／C-R9 實測。

## 8.1 裁決狀態（handoff 2026-10-05；2026-10-06 新增裁決 11～13）

- **Q1** weekly-review Session Memory 段：**已裁決 — 刪除**（handoff 2026-10-05）。執行時須同步後續步驟編號與交叉引用（見 §5 A1）。
- **Q2（已釐清，無需再裁決）**：rev.2 的決議「planner 不寫 repo 檔」（plan-rev2 L11、critique-1 L44），與 handoff 使用者裁決 1 相同。rev.3 §4 的「Q2 決議」即指此項；rev.3 未重述內容，本版補上。
- **Q3** lianbu-spokesperson：**已裁決 — 改 readonly**（handoff）。
- **Q4** ahead=1（runbook commit）：**已裁決 — 視為 campaign 起點，base SHA = `ed09bece`**（handoff）。
- **Q5** Allowed paths 擴充：**已裁決 — 核准**（handoff）。
- **Q6** V-M-D 無 Edit／Closer 無 Write：**已裁決 — 核准**（handoff）。Closer 部分由裁決 12 加上條件式例外。
- **Q7** 規則 7、10 擴大：**已裁決 — 核准**（handoff）。rev.4 依 R3-2 修正豁免漏洞、依 R3-1 補 N3 例外；rev.5 依 R4-2 調整例外評估順序、依 §6-3／§6-5 收斂規則 9 的 psql 支援形式。皆**未改變 Q7 的範圍決定**。
- **Q8（R3-5）**：**已裁決 — 共用危險操作防線（`permissions.ask`、hooks）對 architect、reviewer、researcher、scraper-expert 生效**（使用者 2026-10-05 確認，採推薦方案，理由見 §1）。**B／C** 不修改四角色的 agent 檔與權限投影（tools／claude-role）；**A** 只依 A1 遷移 legacy prose 與 handoff `prompt`，權限 metadata 不變（R4-1，見 §1 表）。若日後要求排除，須先證實 C-R9 的 agent 辨識，並另立裁決。
- **裁決 11（2026-10-06）**：確認 R4-1 的解讀。A 可依 A1 遷移 architect、researcher、scraper-expert 的 legacy 說明文字與 handoff `prompt`（權限設定不變）；B、C 不修改這四個 agent 檔。
- **裁決 12（2026-10-06）**：預先核准 H-C3。C-R7 依 §6 判準證明 Closer 寫結案紀錄需要 Write 時，授予 Write，並連帶修改 Copilot `tools:`、重測；Bash 能完成時不授予。
- **裁決 13（2026-10-06）**：預先選擇 H-C1 (i)。C-R9 在某情境不可辨識（或無法完成實測）時，接受殘餘風險、繼續進行：該情境的 B-R7／B-R8／C-R9／C-R10 標「PARTIAL－裁決 13 接受」，聲明依 C-R11。只涵蓋角色辨識；§8.2 #13 的 ask 失效仍於 H-C1 依實測決定。
- X1–X4：另行裁決，不阻擋本 campaign 的 Phase A／B。X2 已更正，可選擇提前把 reviewer 改投影為 readonly。

## 8.2 NOT TESTED 處理表（2026-10-06 追加；只彙整既有項目）

Phase 0 時由 Engineer 原樣搬進 `tasks.md`，作為實測追蹤清單。

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

## 9. 下一步

1. ~~第五輪複審 rev.5~~：已完成（`critique-5-codex.md`），結論 1 項阻擋（R5-1），由本版修正。
2. **Plan Critic 第六輪窄範圍確認 rev.6**（GPT／Codex；prompt 見 `~/.ai-notes/ttr/critique-6-prompt.md`）：只確認 R5-1 已關閉、`diff -u plan-rev5.md plan-rev6.md` 只含 §0 表列的變動、且這些變動沒有引入新矛盾。其餘部分第五輪已審過，不重審。第一行輸出「rev.6 可進 Phase 0」或「rev.6 有 N 項阻擋」。
3. 若結論為「可進 Phase 0」：Engineer 先過 §4 2a 的 worktree 確認閘門與 2b 的 Step 0 漂移檢查，再以 `plan-rev6.md` 為基礎執行 Phase 0。
4. 若仍有阻擋：只在阻擋屬於「rev.6 引入的新矛盾」或「R5-1 未關閉」時再修訂；其餘建議留到 Phase 0／spike 實測後依證據處理，避免治理文件繼續自我增殖（第四輪 §3 的反兔子洞提醒）。
5. Phase 0 通過前，不 commit、不 push、不操作 production DB。
