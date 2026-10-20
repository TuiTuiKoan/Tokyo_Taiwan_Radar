---
slug: ai-portability
title: AI 工具可攜性三階段 hardening（legacy state、角色工具限制、危險操作 hooks）
description: 移除 Copilot-only legacy state path、把角色權限轉成 Claude 工具限制、建立危險操作 hooks；本版為部分 hardening
status: active
branch: feat/ai-portability
created: 2026-10-06
tags: [tooling, governance, ai, hardening]
---

## What（做什麼）

以 `docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md` 為操作基準，處理 runbook「六、目前最值得處理的三個缺口」。三個 phase 依序執行，各自一個 atomic commit、各自驗證：

| Phase | 主題 | 範圍摘要 |
|---|---|---|
| A | 移除 legacy state path | active guidance 不再要求寫入 Copilot-only state（`/memories/session/*`、`.copilot-tracking/`）；改用新的 state 契約；歷史文件只加標註 |
| B | 角色權限轉成 Claude 工具限制 | frontmatter `claude-role` 為唯一權威，`scripts/sync_ai_adapters.py` 為 12 個受管 agent 投影 Claude `tools:`；新增最小 push 閘門 `permissions.ask` |
| C | 危險操作 hooks | `.claude/settings.json` 加 PreToolUse hooks（`scripts/claude/`），第一批 10 類規則 |

本 commit 為 **Phase 0（spec 骨架）**：只新增本目錄的檔案，並原樣存檔計畫與評審，不修改任何其他檔案。

## Why（為什麼）

Copilot Enterprise 可能被撤銷。repo 已有單一權威（`.github/**`）加 adapter（`scripts/sync_ai_adapters.py`），但仍有三個缺口：

1. active guidance 仍要求寫入 Copilot-only state。
2. 角色權限只寫在自然語言裡，sync 不輸出 `tools:`。
3. 沒有危險操作 hooks（`.claude/settings.json`、`scripts/claude/` 不存在）。

## 權威文件

| 檔案 | 內容 | 來源（原樣複製） | SHA-256 |
|---|---|---|---|
| [plan.md](./plan.md) | 執行計畫 rev.6 | `~/.ai-notes/ttr/plan-rev6.md` | `6943c073620e29530581988a79c47e8da84ee34f6ce3edecf2e7511695487bbc` |
| [plan-critique-1.md](./plan-critique-1.md) | 第一輪評審（Opus） | `critique-1-opus.md` | `a10a07adaf6fd96e63918e30d2d52d2b09f37cebd990b348fb63326b89ab62bc` |
| [plan-critique-2.md](./plan-critique-2.md) | 第二輪評審（GPT） | `critique-2-gpt.md` | `13be5c6592e27608fbd64c5f0fb845ac3284e8c4d7525da6c0cfcd378be6de82` |
| [plan-critique-3.md](./plan-critique-3.md) | 第三輪評審（Codex） | `critique-3-codex.md` | `c23fe3daf793a759c7f3c34b589b5b50c56241f64bc9c2ecebfb162dc5f54f5e` |
| [plan-critique-4.md](./plan-critique-4.md) | 第四輪評審（Codex） | `critique-4-codex.md` | `12111755a90f9afc817e3bc71df0de839fb36f7b2bf716f67084445b245193cd` |
| [plan-critique-5.md](./plan-critique-5.md) | 第五輪評審（Codex） | `critique-5-codex.md` | `0fa3fa0b576adf0dee57358d7f4526644f8ae8f7bc7cfc4063869873f69d88f5` |
| [plan-critique-6.md](./plan-critique-6.md) | 第六輪窄範圍確認（Codex） | `critique-6-codex.md` | `7909a88a683a641ad8c3f2c2a0fa537648f4ee58044753ec0af815d5f06b78b3` |

- `plan.md` 是本 campaign 的執行權威；與使用者裁決衝突時，以使用者裁決為準。
- `plan.md` 檔頭第 5 行「尚未通過 Plan Critic 複審」是 rev.6 撰寫當時的狀態。依原樣存檔規則不改寫；第六輪確認（`plan-critique-6.md` 第 1 行「rev.6 可進 Phase 0」，R5-1 CLOSED）之後，規劃階段已結束。
- 依裁決 1，planner 與 Plan Critic 不寫 repo 檔；上列檔案由 Engineer 在 Phase 0 落檔。
- [tasks.md](./tasks.md) 是跨 session 進度的真值；[notes.md](./notes.md) 記錄執行證據與分類帳。

## Campaign base 與 remote baseline

| 項目 | 值 |
|---|---|
| Campaign base SHA（固定，裁決 6／Q4） | `ed09beceb5004bc8025958c0b752075ed92dd448` |
| Phase 0 起點 HEAD | `565c1479642761d35162e76a7f337b377596a56d`（runbook commit，未 push） |
| `git merge-base HEAD origin/main`（佐證） | `ed09beceb5004bc8025958c0b752075ed92dd448` |
| Phase 0 remote baseline（`git fetch origin` 於 2026-10-06T03:08:21Z） | origin/main = `3087f6abd14953fe57f2d002a506e9cecc27ce1d`；`ed09bece` 為其祖先（fast-forward）；HEAD ahead 1／behind 2 |

Campaign base 與 remote baseline 分開記錄；之後每次執行都另記當時的 remote baseline。Phase 0 判定：`ed09bece..origin/main` 的 2 個 commit 只改 `docs/weekly_review/` 與 `web/` 依賴，沒有碰本 campaign 的任何路徑，屬於主幹正常前進，**不是非預期漂移**。base 維持不變，未 rebase。證據見 `notes.md` §2。

## Worktree

- 實作 worktree：`ttr-ai-portability-worktree`，branch `feat/ai-portability`，狀態 CONTINUING（使用者已指定；Phase 0 以 `git worktree list --porcelain` 核對）。
- 主工作樹（`Tokyo Taiwan Radar`／`main`）僅供治理與盤點，不在其中實作。
- 本 worktree 流程**禁止任何形式的 `git stash`**（plan §4 2c）。需要乾淨工作樹時，若屬於本工作且已到核准點，依閘門整理成 commit；否則 STOP 回報。

## Allowed paths

runbook「ai-portability 範例」：

- `CLAUDE.md`、`AGENTS.md`
- `.github/agents/`、`.github/skills/`、`.github/prompts/`、`.github/instructions/`
- `scripts/sync_ai_adapters.py`
- `.claude/`、`.agents/`、`scripts/claude/`
- `docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md`
- `docs/specs/active/ai-portability/`

plan §4 擴充（N1，裁決 7／Q5 已核准）：

| 新增路徑 | 用途 | 階段 |
|---|---|---|
| `scripts/tests/`（新目錄） | `test_sync_ai_adapters.py` | B |
| `scripts/campaign-closeout-audit.sh` | legacy 掃描標籤改 `legacy_tracking_plans` | A |
| `docs/evaluation/campaigns/README.md` | 同上說明 | A |
| `docs/specs/security-hardening-plan-RECOVERED.md` | 歷史標註 | A |
| `docs/evaluation/annotator/2026-05-18-baseline-v2.md` | 歷史標註 | A |
| `docs/specs/active/{authoritative-venue-repair,publication-policy,admin-reports-204-cleanup,admin-qa-cleanup,spec-architecture-dashboard}/` | 僅改「權威計畫」句與相鄰標註（plan §5 A3 表） | A |

`.gitignore` 不需要改（`.claude/settings.local.json` 與 `.copilot-tracking/` 已在其中）。

## 使用者裁決

| # | 裁決 | 對應 | 日期 |
|---|---|---|---|
| 1 | planner 不寫 repo 檔；plan／critique 由 Engineer 或使用者落檔到本目錄 | Q2 | 2026-10-05 前 |
| 2 | reviewer、researcher、architect、scraper-expert 的權限衝突只記錄、延期裁決；B、C 不動這四個 agent 檔 | X1–X4 | 2026-10-05 前 |
| 3 | Phase C 第一批只做 runbook 表格列出的 10 類；字元層混淆列為後續項目 | — | 2026-10-05 前 |
| 4 | weekly-review 的 Session Memory 段：刪除 | Q1 | 2026-10-05 |
| 5 | lianbu-spokesperson：改 readonly | Q3 | 2026-10-05 |
| 6 | ahead=1（runbook commit）視為 campaign 起點，base SHA = `ed09bece` | Q4 | 2026-10-05 |
| 7 | Allowed paths 擴充：核准 | Q5 | 2026-10-05 |
| 8 | V-M-D 無 Edit、Closer 無 Write：核准 | Q6 | 2026-10-05 |
| 9 | 規則 7、10 擴大：核准 | Q7 | 2026-10-05 |
| 10 | 共用危險操作防線（`permissions.ask`、hooks）對 architect、reviewer、researcher、scraper-expert 生效 | Q8 | 2026-10-05 |
| 11 | 確認 R4-1 解讀：A 可遷移三個 UNDECIDED 檔的 legacy 說明文字與 handoff `prompt`（權限設定不變）；B、C 不修改這四個 agent 檔 | R4-1 | 2026-10-06 |
| 12 | 預先核准 H-C3：C-R7 證明 Closer 寫結案紀錄需要 Write 時授予 | C-R7 | 2026-10-06 |
| 13 | 預先選擇 H-C1 (i)：角色辨識失敗或無法實測時接受殘餘風險、繼續進行 | C-R9 | 2026-10-06 |

### Q2 內容（= 裁決 1）

planner 不寫 repo 檔；plan／critique 由 Engineer 或使用者落檔。**這是角色行為規則**，與工具層能力聲明分開陳述。工具層能力聲明依 C-R11：保留 Bash 的角色只能寫「工具層禁用 Edit／Write／NotebookEdit（或 C-R10 hook 拒絕）；Bash 重導寫入為已接受殘餘風險」，不得寫成「無 repo 寫入（能力）」。

Q2 的來源是 rev.2 的「planner 不寫 repo 檔」決議（plan-rev2 L11、`plan-critique-1.md` L44），與裁決 1 相同，不需要再裁決。

### Q8 裁決結果（= 裁決 10）與已接受的行為變更

- **共用防線對四角色生效**：`.claude/settings.json` 的 `permissions.ask`（Phase B）與 hooks（Phase C）是 project-wide 設定，architect、reviewer、researcher、scraper-expert 的 runtime 行為也會受影響。這是已接受的行為變更。
- 延期的是**權限投影**：四個 UNDECIDED agent 本 campaign 不加 `claude-role`，wrapper 不輸出 `tools:`（仍繼承全部工具）。
- 實際生效範圍待實測：`permissions.ask` 是否約束 subagent 內的 Bash 待 B-0(6)；hooks 在 `claude --agent` 主執行緒與 subagent 兩種情境的實際行為待 C-0(3)／C-R9。未實測前不得寫成「已生效」。
- 若日後要求排除四角色，須先證實 C-R9 的 agent 辨識，並另立裁決。
- 不得用本設計宣稱「B、C 都不影響四角色」。

### 裁決 11（R4-1）

A 依 plan §5 A1 遷移 architect、researcher、scraper-expert 的 legacy 說明文字與 handoff `prompt`，權限 metadata 全部不變；reviewer 經 2026-10-06 `rg` 無命中，A 不改。B、C 不修改這四個 agent 檔與權限投影，以 B-R5 擴充與 C-R12 的零 diff 驗證。

### 裁決 12（Closer Write，預先核准 H-C3）

Phase B 仍依 Q6 把 Closer 投影為無 Write，不預先放寬。C-R7 時：

- **證明需要**：Closer 在 disposable fixture campaign 依 agent 本文執行一次結案，因工具層沒有 Write 而無法完成結案紀錄或 recovery capsule 的寫入，並把該次輸出記入 `notes.md`。若 Closer 改用 Bash 完成寫入，記為「不需 Write」，不授予。兩種結果都記入 `notes.md` 並在 H-C3 呈報，**不需等待新決定**。
- **授予範圍**：只在 closer 的 `ROLE_TOOLS` 加 `Write`，不加 Edit、NotebookEdit。
- **連帶修改**：`campaign-closer.agent.md` 的 Copilot `tools:` 由 `[read, search, execute]` 改為 `[read, search, execute, edit]`，否則類別子集判準會讓 `--check` 失敗。若使用者不希望改動 Copilot，替代方案是在 sync script 為 closer 設一個具名、受測試的例外，需在 H-C3 另行指示。
- **重測**：以獨立 commit 修改，重跑 `sync`、`--check`、B-R2 pytest、B-R3、B-R5 擴充、C-R12，再重跑 C-R7 的 Closer smoke test。
- **殘餘風險**：Write 沒有路徑限制，與 Closer 原有的 Bash 能力同級，不另加規則。

### 裁決 13（角色辨識，預先選擇 H-C1 (i)）

C-R9 在某情境實測證實「不可辨識」或無法完成實測時，接受殘餘風險、繼續進行：受影響情境的 B-R7／B-R8／C-R9／C-R10 標「PARTIAL－裁決 13 接受」，對外聲明依 C-R11，不得宣稱該情境有工具層寫入限制。Engineer 仍須在 H-C1 呈報哪些情境不可辨識、實際標示與 AGENTS.md 聲明的措辭。**只涵蓋角色辨識**；plan §8.2 #13（ask 完全不生效）仍在 H-C1 依實測結果決定。

## 本版部分 hardening 聲明

裁決 2 讓四個 agent 的**權限投影**延期，所以本 campaign 結束時**不能宣稱 runbook 三缺口全部完成**。

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

## 四角色修改範圍表（R4-1）

| 階段 | 對 architect／reviewer／researcher／scraper-expert 的 canonical agent 檔 | 權限 metadata（`tools`、`agents`、`claude-role`、`user-invocable`、`disable-model-invocation`、handoff `label`／`agent`） | 驗證 |
|---|---|---|---|
| A | **只遷移 legacy state 的 prose 與 handoff `prompt`**（依 plan §5 A1：architect、researcher、scraper-expert 有命中；reviewer 經 2026-10-06 `rg` 無命中，不改） | 全部不變 | A-R3 frontmatter-diff；四檔每個 hunk 記入 `notes.md` 分類帳 |
| B | 不修改 | 不加 `claude-role`；wrapper 不輸出 `tools:`（維持繼承全部） | B-R5 擴充：四檔 canonical 與 generated 相較 A commit 零 diff |
| C | 不修改 | 不變 | C-R12：相較 B commit 零 diff |

## 衝突紀錄 X1–X4（待使用者另行裁決）

以下四項**待使用者另行裁決**，不阻擋本 campaign 的 Phase A／B；B、C 不動這四個 agent 檔。

| ID | runbook 規定 | 現行行為（證據） | 狀態 |
|---|---|---|---|
| X1 architect | 唯讀、無 repo 寫入 | `architect.agent.md` L1175–1180 以 `runSubagent` 編排 Engineer→Tester；L1160 用 `vscode_askQuestions`（需 Agent、AskUserQuestion） | 維持全權限；runbook 驗收「Architect 無寫入」= **未達成／待裁決** |
| X2 reviewer | 唯讀 | `reviewer.agent.md` L35 明文「這是一個**唯讀**的分析 Agent，不修改任何檔案」；`docs/skill_scan/` 報告由 workflow `monthly_health_check.yml`（「Commit scan report」步驟，L118–125）以 `skill_scanner.py` 產出並 commit，不是 reviewer 寫檔。**首輪批評的「reviewer 會寫檔」是事實錯誤，衝突不存在。** | 依裁決 2 本 campaign 仍不動；建議列後續項（改投影為 readonly），使用者可在 H-B1 選擇提前 |
| X3 researcher | 「只寫研究輸出」 | L30、L67–84 執行 `scraper/update_source.py`，對 `research_sources` 做 `.update()`（`update_source.py` L253）＝ **⚠ production DB 寫入** | 維持現況；C 的 prod-db 規則**不涵蓋**此路徑，明標為未保護的 production 寫入面 |
| X4 scraper-expert | 矩陣無此列 | 以 `agents:` 分派 3 個來源 subagent、寫 scraper | 維持現況；建議歸 full，待裁決 |

## Surface matrix（Copilot／Claude／Codex）

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

## Non-Goals（不做什麼）

- push、production DB 寫入、secret 旋轉、清理其他 worktree、修改主工作樹。
- 網站與 scraper runtime 內呼叫的 LLM（`scraper/`、`web/` 中的 `gpt-4o*`）。
- 重新命名 agent、改寫 history 原文。
- 四個 UNDECIDED agent 的權限投影（`tools`／`claude-role`）變更，以及 B／C 對這四個 agent 檔的任何修改。A 依 A1 對其中三檔做的 legacy prose／handoff `prompt` 遷移屬範圍內，權限 metadata 不變。
- 注意：共用防線（permissions、hooks）對這四個 agent 的 runtime 行為生效，**不在** Non-Goals 之內（Q8）。

## 核准點

H0（起點 `ed09bece`、Allowed paths 擴充已由 Q5 核准、實作 worktree 確認）→ H-A1／H-A2 → H-B1／H-B2／H-B3 → H-C1／H-C2／H-C3 → **H-PUSH**（交 V-M-D；使用者明確核准、僅 linear fast-forward、驗證 pushed SHA 等於 GitHub main）。H-C0 = Q8 已於 2026-10-05 裁決，不再阻擋。任一階段 Required 未通過即停止回報。Gate 契約（PASS／PARTIAL／NOT TESTED／PASS-pending-user 與合法 carry-over 分支）見 `plan.md` §2。

## 殘餘風險

完整清單見 `plan.md` §8「殘餘風險」。重點：

- prod-db hook 為啟發式；researcher 的 `update_source.py` 與所有腳本介面的 production 寫入**未受保護**。
- 保留 Bash 的 planner／tester 對 Bash 重導寫入沒有工具層防護（C-R11）。
- Codex 只受 Phase A 影響；Copilot 不受任何 hook 保護。

## References

- `docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md`（操作基準）
- [plan.md](./plan.md)、[tasks.md](./tasks.md)、[notes.md](./notes.md)
- `.github/instructions/git.instructions.md` § Worktree confirmation gate、§ Isolated worktree
- [Spec lifecycle](../../README.md)
