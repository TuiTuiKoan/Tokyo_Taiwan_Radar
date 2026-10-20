rev.5 有 1 項阻擋

## 阻擋項

**R5-1｜Closer 的 Write 授權流程互相矛盾**

- 位置：[plan-rev5.md:320](/Users/flyingship/.ai-notes/ttr/plan-rev5.md:320)、[plan-rev5.md:338-342](/Users/flyingship/.ai-notes/ttr/plan-rev5.md:338)、[plan-rev5.md:706](/Users/flyingship/.ai-notes/ttr/plan-rev5.md:706)
- 理由：§6 判準段規定，Closer 若能以 Bash 寫入就不授予 Write；若無法完成寫入且符合「證明需要」判準，就只加 Write 並重測。這符合裁決 12。但同一角色表註解仍要求「回報使用者決定是否授予 Write」，使 Engineer 無法確定該按預先核准的條件直接執行，還是停下等待新決定。
- 最小修正：將 L320 改為引用 §6 判準段與裁決 12：按判準確認需要 Write 時依裁決授予並重測；Bash 能完成時不授予。刪除「回報使用者決定是否授予 Write」。

## R4-1～R4-4 關閉狀態

| 項目 | 狀態 | 證據 |
|---|---|---|
| R4-1 四角色修改範圍 | **CLOSED** | §1 表（L52–60）允許 A 遷移三個 agent 的 legacy prose／handoff prompt、保護權限 metadata，並限制 B／C 不改四檔；§5 A1（L222–235）列明修改邊界；B-R5（L116）、C-R12（L139）和 §8 Out（L680）一致。未見「整個 campaign 不改四個 agent 檔」的殘句。A-R3（L99）仍要求除 handoff prompt 外 frontmatter 逐 key 不變。裁決 11 已確認解讀。 |
| R4-2 masked awk 例外順序 | **CLOSED** | §7 規則 7（L602–621）為敏感寫入先 deny、精確例外次之、其他敏感存取最後 deny；層 1 不可被層 2 推翻（L606–610）。每個 simple command 獨立判定，串接段不互相豁免（L602、L620）；AP1–AP3 和負向 (a)–(h) 的預期規則 id 列於 L623–626。模板與 repo 的 [token-rotation.instructions.md:125](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/instructions/token-rotation.instructions.md:125)、[token-rotation.instructions.md:196](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/instructions/token-rotation.instructions.md:196) 逐字相符。 |
| R4-3 planner／Tester fallback 與 carry-over | **CLOSED** | §2 規則 1 與合法 carry-over 表（L77–91）指定 B-R6／7／8 的條件與 C 端 Required；B-R7、B-R8（L118–119）拆開 planner 與 Tester fallback。Tester 明文永不加入 Edit／Write／NotebookEdit。repo 的 [tester.agent.md:4–8](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/tester.agent.md:4) 僅宣告 read／search／execute／web；`grep -l '^tools:'` 列出的 agent 也不含 plan-critic，因此 planner fallback-P 不觸發類別子集判準。C-R9～C-R11（L136–138）、C-R10 路徑政策（L137）、§8.2 #4–5、#11（L719–720、L726）互相銜接。`無 repo 寫入` 搜尋的命中只在 §0 引述舊問題、B-R7 的否定限定和 X1 runbook 原文；沒有新能力聲明。 |
| R4-4 stash fallback | **CLOSED** | §4 2c（L164–167）明確禁止任何形式的 stash；合規 commit 與 STOP 條件已寫明，與 [git.instructions.md:87](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/instructions/git.instructions.md:87) 一致。其餘提到裸 `git stash` 的地方是 §4 後續 hook 偵測項（L169），依要求不算 stash 指示。 |

§4 runbook 措辭表的 L293、L295、L296、L315、L316、L333、L334，分別對應 runbook 的角色矩陣與驗收／negative test 行；內容引用相符。

## §6-1～§6-8 與「§2 預算」處理核對

| 項目 | 處理 | 判斷 |
|---|---|---|
| §6-1 | 已納入 | §5 A1（L239）新增兩個 session memory 寫入命中；rg 命中的限制句（workstream-audit L16、ledger-topology-reconcile L47）有理由保留；weekly-review 與 admin-qa 的舊路徑命中也列出處理。 |
| §6-2 | 已納入 | 多行 HP1、HN1–HN7 fixture（L447–525）令 delimiter 獨占一行；重導負例使用 `cat > out.txt`。 |
| §6-3 | 已納入 | 規則 9（L649–653）刪除 `\d*` 豁免，拒絕所有 backslash 指令；`-X`／`--no-psqlrc` 和首字條件一致。各個 psql must-deny 負例帶 `-X`，只有無 `-X` 的案例用來測 psqlrc 檢查（L665–666），不會被缺少 `-X` 提前攔下。 |
| §6-4 | 已納入 | launcher output protocol 和 fail-closed 邊界表（L557–578）加入 exit 0 但 stdout JSON 無效／形狀不符的測試列，條件可落實。 |
| §6-5 | 已納入 | psqlrc 被列為不可檢查輸入，要求啟動時帶 `-X`／`--no-psqlrc`（L643–653）；清單使用帶 `-X` 的 allow 與負例。 |
| §6-6 | 已納入 | 規則 7（L633–637）、C-R8（L135）、§8 殘餘風險（L690）皆明列父目錄遞迴搜尋及別名路徑不涵蓋，沒有宣稱已保護。 |
| §6-7 | 已納入 | B-0 與 C-0 分別記錄 `--agent` 主執行緒及 subagent（L298–299、L404）；C-R10 規定 planner 僅允許 plans 私有路徑、Tester 全拒，並要求先正規化路徑（L137）。 |
| §6-8 | 已納入 | §4 存檔清單補 critique-4／critique-5（L161）；Closer 參照改 C-R7（L320）；permissions 適用性標待測（L64、L197、L398）；tasks 後續項保留間接引用並移除直接 `.env` 操作（L169）。 |
| §2 預算 | 已納入 | §7（L527）將 ≤250 行限制限定為 `_tokenizer.py`，規則需有 fixture 但不設行數上限。 |

## 非阻擋建議

- 修正 R5-1 後，保留「不新增規則類別、不擴建 shell／SQL interpreter」的範圍；現有修訂已將其他事項留給 Phase 0／spike 實測。

## 需使用者確認的解讀問題

無。R4-1 已由裁決 11 確認。

## 已驗證的 repo 證據

- [token-rotation.instructions.md:125](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/instructions/token-rotation.instructions.md:125)、[token-rotation.instructions.md:196](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/instructions/token-rotation.instructions.md:196)：masked awk 模板一致。
- [git.instructions.md:87](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/instructions/git.instructions.md:87)：dirty worktree 規則明確寫明 never stash。
- [tester.agent.md:4](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/tester.agent.md:4)：Copilot tools 為 read／search／execute／web；`grep -l '^tools:'` 命中 closer、lianbu、tester、validate-merge-deploy，未命中 plan-critic。
- [architect.agent.md:7](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/architect.agent.md:7)、[architect.agent.md:80](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/architect.agent.md:80)、[architect.agent.md:1168](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/architect.agent.md:1168)、[architect.agent.md:1173](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/architect.agent.md:1173)、[architect.agent.md:1175](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/architect.agent.md:1175)：引用位置與內容相符。
- [workstream-audit.prompt.md:16](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/prompts/workstream-audit.prompt.md:16)、[workstream-audit.prompt.md:21](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/prompts/workstream-audit.prompt.md:21)、[ledger-topology-reconcile.prompt.md:18](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/prompts/ledger-topology-reconcile.prompt.md:18)、[ledger-topology-reconcile.prompt.md:47](/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/prompts/ledger-topology-reconcile.prompt.md:47)：新增／保留位置與命中內容一致。
- runbook 對應行：L293–300 角色矩陣、L315–318 驗收、L333–336 negative tests；plan 的 L204–214 引用對應正確。

## 未驗證項目

本輪未執行 repo 測試或 fixture，以下仍須在 Phase 0／spike 實測：Claude `tools:` 對 `--agent` 與 subagent 的實際限制、hook stdin 欄位、permissions 對 subagent Bash 的適用性、ask JSON 實際提示。§8.2 #13 的 ask 完全不生效時，依計畫留待 H-C1 決定。

## 審查前後 SHA-256

| 檔案 | 審查前 | 審查後 |
|---|---|---|
| `plan-rev4.md` | `5ab1ecca3c4804704a6a313e79e9042d1dc2395f760136afde216a5723504a5f` | `5ab1ecca3c4804704a6a313e79e9042d1dc2395f760136afde216a5723504a5f` |
| `plan-rev5.md` | `fb6b547630d503a1aecbca9712563b42c87039664bbc3de1aca0a8b3d1549ff3` | `fb6b547630d503a1aecbca9712563b42c87039664bbc3de1aca0a8b3d1549ff3` |