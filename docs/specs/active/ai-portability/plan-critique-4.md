rev.4 有 4 項阻擋

評審：GPT（Codex），與計畫作者 Claude 不同家族。審查於 2026-10-05 至 2026-10-06（Asia/Tokyo）完成。
對象：`~/.ai-notes/ttr/plan-rev4.md`；依第四輪 prompt、Plan Critic agent／skill、專案總規則與 handoff 裁決執行。
本報告的 CLOSED 指「計畫層面的缺口已補齊」，不代表尚未實作的 hooks／權限已通過 runtime 驗收。
僅依使用者要求儲存本報告；未改計畫、handoff 或 repo，未 commit、push、fetch 或操作 production DB。

## 1. 商業主軸對齊（Business Alignment）

**🟡 弱對齊。** 本計畫保障 Copilot 退出後的開發延續、指令可攜性與部分危險操作防護，間接支持全日本台灣相關活動聚合；不直接改善爬蟲覆蓋率、資料品質或 i18n。範圍說明已承認此點（[rev.4:112](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:112)、[rev.4:538](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:538)）。

三個交付階段仍有合理目的：A 清除 active Copilot-only 指令，B 投影已裁決角色權限，C 增加有限命令防護。不得把完成本 campaign 等同於「唯讀角色無任何寫入能力」或「production DB 全面受保護」。

## 2. 複雜度 vs 價值評估

**複雜度 high；業務價值 medium。複雜度高於直接業務價值，應凍結功能範圍。**

- Phase 0 加 A／B／C；12 個已決角色、16 個 canonical agents／wrappers；計畫列出 5 個 hook 模組、4 個測試檔與 10 類規則，阻擋案例至少 30 個，另有 positive fixtures、角色 smoke tests、fail-closed 與 carry-over gates。
- 無 DB migration、i18n key、新 scraper、網站 UI 或 runtime LLM 變更；風險主要來自 shell 語法辨識、權限投影與跨階段驗收相依。
- 沿用單一 adapter 是正確方向。保持有限啟發式防護；不擴建完整 shell／SQL interpreter，也不以行數壓縮取代清楚的 coverage 聲明。
- [rev.4:406](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:406)「tokenizer 與規則合計 ≤250 行（僅指 tokenizer）」互相矛盾，應統一預算對象。這是非阻擋文字修正。

## 3. 優先順序提醒（Anti-Rabbit-Hole）

**🟡 可排程；🔴 已出現反覆修訂同一治理功能的訊號。** 四輪複審已符合 Plan Critic skill 所警示的治理工作自我增殖風險。下一輪應限於下列四個確定衝突與驗收文字修正，不重開 Q1–Q8、不新增防護類別。

[docs/monthly_review/2026-09.md:51](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/monthly_review/2026-09.md:51>) 與 [docs/monthly_review/2026-09.md:66](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/monthly_review/2026-09.md:66>) 分別記錄 NDL 首次正確率／修正情況與 kokuchpro 修復延遲。這些是資料品質工作優先序的歷史訊號；本次未取得目前 health 或 open issues，不能把月報直接當作現存故障清單，也不能宣稱當前沒有待辦。

建議先完成一次定點修訂，再交 Engineer 做 Phase 0／spikes；只有實測發現新矛盾才重新評審。現在停止的是「按此版本直接開工」，不是取消可攜性工作。

## 4. 全站架構整合分析

### 阻擋項

**R4-1 — Phase A 必改檔案，又被列為整個 campaign 禁改。**

- 位置：[rev.4:44](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:44)、[rev.4:537](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:537)、[rev.4:560](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:560)，對照 [rev.4:185](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:185)、[rev.4:191](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:191)、[rev.4:194](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:194)、[rev.4:196](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:196)。
- 理由：全域文字禁止四個 UNDECIDED agent 的「agent 檔」任何變更；A1 同時要求修改 architect 的 handoff／prose、researcher 的 legacy 路徑、scraper-expert 的 legacy 標註。Engineer 無法同時完成 A-R2 與全域 Out。[rev.4:253](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:253) 限定「本 phase」反而正確。
- 修正：統一寫成「B／C 不修改四角色 agent 檔或權限投影；A 依 A1 僅遷移 prose／handoff prompt，所有權限 metadata 保持不變」。若原意確為全 campaign 禁改檔案，必須刪除衝突的 A1 任務並承認 active guidance 未清完；不能同時保留兩套驗收。
- 不重開 Q8：共用防線對四角色生效的裁決已明確；本項只修正 Phase A 檔案範圍。

**R4-2 — masked awk 的第三層例外永遠到不了。**

- 位置：[rev.4:475](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:475)、[rev.4:481](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:481)、[rev.4:487](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:487)、[rev.4:523](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:523)。
- 理由：規則要求前層命中立即 deny，第二層只豁免 metadata 白名單。masked awk 帶 `.env` 引數且不在該白名單，會先得到 `env-file-access`，不會進入第三層。兩種正確模板都無法通過 must-allow／漂移測試。
- 修正：判定改為「敏感寫入／重導先 deny → 精確 metadata 或精確 masked awk 例外 → 其他敏感存取 deny」。保留所有串接段獨立檢查，不能因 `cd scraper && awk …` 整段匹配而跳過後續命令。
- 模板引用本身正確：[.github/instructions/token-rotation.instructions.md:125](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/instructions/token-rotation.instructions.md:125>) 是 `cd scraper && awk …`；[.github/instructions/token-rotation.instructions.md:196](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/instructions/token-rotation.instructions.md:196>) 是有縮排的 `awk …`。缺口在判定順序，不在來源內容。

**R4-3 — Tester fallback 無法通過同一計畫的權限一致性檢查；carry-over 契約仍須對齊。**

- 位置：[rev.4:88](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:88)、[rev.4:260](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:260)、[rev.4:272](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:272)、[rev.4:273](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:273)、[rev.4:290](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:290)、[rev.4:293](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:293)。
- 理由：Tester 被指定套用 planner 的「保留 Write」fallback；但 [.github/agents/tester.agent.md:4](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/tester.agent.md:4>) 只有 read／search／execute／web，沒有 edit。依 rev.4 的能力類別對照，Write 屬 edit，必定違反 Claude 類別必須為 Copilot 子集的規則，導致 B-R2／`--check` 失敗。Tester 不需要因 planner 私有 plan 相容性而增加 Write。
- 修正：分開 planner 與 Tester 的 fallback。Tester 保持不含 Edit／Write 的投影；若已安裝版本不執行 tools 限制，記 PARTIAL，交 C-R9／C-R10 驗證 hook 的實際限制，不將 Write 加入其白名單。planner 私有 plan 的 fallback 另外列出。
- 同步修正 [rev.4:58](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:58)：「Required 全 PASS 才能進下一階段」要明列 B-R6／7／8 的合法 carry-over 分支，避免另一條規則要求它們先 PASS 才能執行補救的 Phase C。
- [rev.4:106](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:106) 至 C-R11 已補角色辨識與寫入拒絕，方向正確；但 [rev.4:88](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:88) 與 runbook 措辭表中的「無 repo 寫入」應依 C-R11 改為準確的工具限制聲明。保留 Bash 時不能宣稱沒有 repo 寫入能力；Q2「不寫 repo」仍是角色行為規則。
- C-R9 未證實時維持 PARTIAL／NOT TESTED，不得靠文件或 fallback 名稱判 PASS。

**R4-4 — Phase 0 的具名 stash fallback 違反 worktree 權威規則。**

- 位置：[rev.4:133](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:133)，對照 [.github/instructions/git.instructions.md:59](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/instructions/git.instructions.md:59>) 與 [.github/instructions/git.instructions.md:87](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/instructions/git.instructions.md:87>)。
- 理由：rev.4 只禁止裸 stash，卻指示需要暫存時使用具名 `git stash push -u -m …`。worktree mechanics 的單一權威要求 preview／build／rebase 前髒檔先 commit，明確寫「never git stash」。具名與 SHA 還原並未解除這項禁止。
- 修正：刪除本 worktree 流程的 stash fallback。對已授權且屬本工作的變更依閘門整理成 commit；無法合法整理、或存在他人 WIP 時停止並回報，不替他人 stash／commit。Phase 0 的禁止 commit 條件仍有效，不能以清理為由繞過。
- worktree 確認、Step 0 漂移檢查、固定 base 與 spec slug 記錄本身已補齊（[rev.4:126](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:126)、[rev.4:129](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:129)、[rev.4:131](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:131)、[rev.4:132](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:132)）。

### R3-1～R3-5 關閉狀態

| 前輪項目 | 狀態 | rev.4 證據與判定 |
| --- | --- | --- |
| R3-1 heredoc／dynamic-args 衝突 | CLOSED | [rev.4:381](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:381) 明列受限例外；[rev.4:388](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:388) 起限定 commit message、quoted delimiter、無額外參數／重導、其他段獨立檢查。fixture 格式尚有非阻擋修正，見 §6。 |
| R3-2 metadata 白名單豁免寫入 | PARTIAL | [rev.4:477](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:477) 起先拒絕敏感寫入，堵住 `wc .env > .env` 等原始漏洞；但新的三層順序阻斷 masked awk，見 R4-2。 |
| R3-3 SQL 首字判斷 | CLOSED | [rev.4:504](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:504) 涵蓋四種 -c／--command 形式並逐一檢查；L506 多語句拒絕，L509 拒 INTO／DML／DDL／WITH／FOR，L513 起明列函式／RPC 殘餘風險。只在聲明的啟發式範圍內關閉。 |
| R3-4 fallback／後續 gate 缺漏 | PARTIAL | [rev.4:106](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:106) 新增 C-R9～11，含辨識失敗及 Bash 殘餘風險；但 Tester fallback、B→C gate 與能力聲明仍不一致，見 R4-3。 |
| R3-5 四角色與共用防線作用域 | CLOSED | [rev.4:43](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:43)、[rev.4:46](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:46)、[rev.4:560](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:560) 明確落實 Q8：共用防線適用四角色；不再宣稱 B／C 不影響 runtime。Phase A 檔案範圍回歸另列 R4-1。 |

### 裁決與新增內容核對

| 項目 | 判定 |
| --- | --- |
| Q1 | 已落實計畫：[rev.4:199](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:199) 明定刪除 weekly-review Session Memory，Step 4 改 Step 3 並修引用。 |
| Q2 | 已釐清：[rev.4:130](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:130)、[rev.4:554](/Users/flyingship/.ai-notes/ttr/plan-rev4.md:554) 重述 planner 不寫 repo；勿再當未決問題。能力聲明依 R4-3 修正。 |
| Q3／Q4／Q5 | lianbu readonly（L277）、base 固定 ed09bece（L129）、Allowed paths 擴充（L137）均已列入。 |
| Q6 | V-M-D 無 Edit、Closer 無 Write（L275～280）；C-R7 已增加 Closer 實際結案寫檔（L104），可行性留待 smoke test。 |
| Q7 | 規則 7／10 擴大已保留，未改裁決；規則 7 的例外順序須修 R4-2。 |
| Q8 | 已定案為共用防線適用四角色；permissions 對 subagent 的實際適用性仍待 B-0(6)，不能提前判 PASS。 |
| 規則 9 | -c SQL、-cSQL、--command SQL、--command=SQL 四形均列入；FOR 整字拒絕也涵蓋 FOR SHARE／KEY SHARE 等形式。屬保守判斷，非 SQL 語意解析器。 |
| C-R9 文件聲明 | 明確標示「文件聲明、待實測」，正確。實測要分主執行緒 --agent 與 subagent。 |

官方 hooks 文件說明 project settings hooks 也在 subagent 執行；`agent_type` 可標示 `--agent` 主執行緒或 subagent，`agent_id` 則是 subagent 欄位。這些文件敘述不能替代已安裝版本的 stdin／permissions 實測。[Claude Code hooks](https://code.claude.com/docs/en/hooks)

### Guard 檢查

已瀏覽 Architect skill 的 Category Sync、Event Form Sync、i18n Regression、Manual Translation Fix Persistence、SCRAPERS List Completeness Guards。本計畫不改相應 runtime／DB／UI，均不觸發；適用的是 Worktree／Spec Tracking 與工作樹確認規則，R4-4 為具體違反。沒有新增網站 component，不需將 UI 元件檢查擴大成網站重構。

## 5. 既有 Component 復用與已驗證證據

**🟢 充分復用。** 繼續由現有 adapter 產生 wrappers；新 runtime hook 與 adapter 目的不同，可以新增，不應另造第二份角色權威。

| 既有程式 | 可復用內容 |
| --- | --- |
| [scripts/sync_ai_adapters.py:128](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/scripts/sync_ai_adapters.py:128>) | `parse_frontmatter`；沿用 canonical agent metadata 解析。 |
| [scripts/sync_ai_adapters.py:166](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/scripts/sync_ai_adapters.py:166>)、[scripts/sync_ai_adapters.py:210](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/scripts/sync_ai_adapters.py:210>) | `agent_sources`／`agent_outputs`；來源盤點與 wrapper 生成。 |
| [scripts/sync_ai_adapters.py:302](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/scripts/sync_ai_adapters.py:302>)、[scripts/sync_ai_adapters.py:315](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/scripts/sync_ai_adapters.py:315>) | `expected_outputs`／`generated_files`；生成集合與漂移驗證。 |
| [scripts/sync_ai_adapters.py:334](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/scripts/sync_ai_adapters.py:334>)、[scripts/sync_ai_adapters.py:364](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/scripts/sync_ai_adapters.py:364>) | `check`／`pinned_models`；延伸既有一致性與模型政策檢查。 |

**已驗證的 repo 證據：**

- `git --no-optional-locks status --porcelain` 無輸出；HEAD=`565c1479642761d35162e76a7f337b377596a56d`，branch=`feat/ai-portability`。本機 origin/main=`ed09beceb5004bc8025958c0b752075ed92dd448`；未 fetch，不宣稱是最新遠端。
- canonical agents=16、Claude wrappers=16。`python3 -B scripts/sync_ai_adapters.py --check` exit 0。這只驗證現有 adapter，非未實作 rev.4 的驗收。
- `docs/specs/active/ai-portability/`、`.claude/settings.json`、`scripts/claude/` 尚不存在。
- A1 的 literal legacy 命中清單已用 `rg` 核對；[.github/agents/architect.agent.md:7](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/architect.agent.md:7>)、[.github/agents/researcher.agent.md:19](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/researcher.agent.md:19>)、[.github/agents/scraper-expert.agent.md:192](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/scraper-expert.agent.md:192>) 與計畫引用相符。
- [.github/prompts/weekly-review.prompt.md:123](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/prompts/weekly-review.prompt.md:123>) 為 Session Memory 段；L125 舊路徑、L129 Step 4，支持 Q1 的刪除／重編號。
- 額外語意命中：[.github/prompts/workstream-audit.prompt.md:21](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/prompts/workstream-audit.prompt.md:21>)、[.github/prompts/ledger-topology-reconcile.prompt.md:18](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/prompts/ledger-topology-reconcile.prompt.md:18>) 都要求「更新 session memory」。沒有 literal 舊路徑，不代表沒有 active 依賴。
- [.github/agents/campaign-closer.agent.md:116](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/campaign-closer.agent.md:116>)、同檔 L121／146 確實要求結案紀錄／capsule 寫入，C-R7 的新增有實際用途。
- [scripts/campaign-closeout-audit.sh:283](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/scripts/campaign-closeout-audit.sh:283>) 起與 [docs/evaluation/campaigns/README.md:286](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/evaluation/campaigns/README.md:286>) 的 legacy 掃描引用相符。
- A3 抽查相符：[docs/specs/active/publication-policy/proposal.md:118](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/specs/active/publication-policy/proposal.md:118>)、[docs/specs/active/authoritative-venue-repair/proposal.md:50](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/specs/active/authoritative-venue-repair/proposal.md:50>)、[docs/specs/active/admin-reports-204-cleanup/proposal.md:18](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/specs/active/admin-reports-204-cleanup/proposal.md:18>)、[docs/specs/active/admin-qa-cleanup/proposal.md:237](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/specs/active/admin-qa-cleanup/proposal.md:237>)、[docs/specs/active/spec-architecture-dashboard/proposal.md:51](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/specs/active/spec-architecture-dashboard/proposal.md:51>)。仍應依各段語境改寫，不能機械替換全部歷史字串。
- plan-rev4 SHA-256：`5ab1ecca3c4804704a6a313e79e9042d1dc2395f760136afde216a5723504a5f`；複審前後相同。

## 6. 建議更新後的計畫

**交回 Architect 定點修 rev.5；目前不宣告「rev.4 可進 Phase 0」。**

### 必改四項

1. R4-1：統一 Phase A prose／handoff 遷移與 B／C 四角色權限延期的範圍。
2. R4-2：將精確 masked awk 例外放在一般敏感讀取拒絕之前，敏感寫入仍永遠優先拒絕。
3. R4-3：拆開 planner／Tester fallback，對齊 capability check、carry-over gate 與能力聲明。
4. R4-4：移除 worktree 的具名 stash fallback，依權威 worktree 規則處理髒檔。

### 非阻擋建議與實作驗收補充

- **A1 語意掃描已有結果。** 將 §5 列出的兩個 session memory prompt 加回 Phase A 修改清單；這是完成既有 A-R1／A-R2，不是新增範圍。
- **Heredoc fixtures 要對齊自訂契約。** L390 要求 delimiter 獨占整行，L404 正向示例卻用 `EOF)"`。改成真正的多行 fenced fixture，將 `EOF` 與 `)"` 分行；負向重導改放在 `cat > out.txt <<'EOF'`。本次以 Bash 語法檢查及常數 printf／cat 替身確認 `EOF)"` 並非可直接斷言的 Bash syntax error；問題是計畫自訂限制與例子不一致，不能誤報為 shell 語法必錯。未執行含 git 的負向命令。
- **SQL meta 指令二選一。** L507 允許列表型 `\d*`，L508 又只接受 SELECT／SHOW／EXPLAIN；實作時要設獨立明確白名單分支，或刪掉列表型豁免。它不在 must-allow 清單，故不另列阻擋。
- **補 output protocol 負向 fixture。** C-R3／C-R5 應測「exit 0，但 ask JSON 無效／schema 錯誤」。launcher 的 exit-code 對映不能保證有效 decision；官方將此類錯誤視為 non-blocking。須檢查輸出，或明列為未覆蓋失效模式；host timeout 已列殘餘風險，不能混為同一項。[Claude Code hooks](https://code.claude.com/docs/en/hooks)
- **補 psql 啟動檔邊界。** `psql -c 'SELECT 1'` 未使用 `-X` 時仍會處理系統／使用者 psqlrc，內含指令不受 -c SQL 字串掃描約束。可將支援形式及 must-allow 一起收斂為帶 `-X`；或明列啟動檔副作用為殘餘風險。本次未讀真實 psqlrc、未連 DB。[PostgreSQL psql](https://www.postgresql.org/docs/current/app-psql.html)
- **補敏感路徑邊界。** 明列「只有父目錄引數的遞迴內容搜尋」與未帶敏感名稱的 symlink／alias 路徑是否涵蓋。例如僅檢查引數 basename 不會辨識指向 scraper 目錄的遞迴搜尋會讀到 .env。不要將字面敏感路徑檢查宣稱為完整資料外洩防線；不要求本輪增加全檔案系統追蹤。
- **C-R9 測兩種執行情境。** 同時驗證 `--agent` 主執行緒與 subagent，不能只驗後者就用於 planner 標準啟動。C-R10 的「repo 外依 §7 policy」也應說清楚：§7 目前只定義敏感路徑處理，沒有一般 repo 外寫入政策。
- **清理過期文字。** L130 補存 critique-4；L276 smoke test 參照改 C-R7；L163／L345 對 permissions 的肯定句改成待 B-0(6) 實測；L549 的 Q8 待裁決句刪除；L135 後續項目移除已在 L492／L546 涵蓋的直接 .env 存取，保留間接引用。

上述補充落在既有 fixtures／coverage 聲明範圍，不增加本輪阻擋數，也不要求全面 shell 或 SQL 安全沙箱。

### 未驗證項目

- Claude 已安裝版本、`--agent` tools 生效、私有 plan 寫入、ExitPlanMode、Copilot 未知 frontmatter 欄位相容性。
- project permissions 對 subagent Bash 的適用性、實際 ask 提示、主樹／worktree settings 與同名 agent 載入來源。
- 真實 hook stdin 的角色與各工具路徑欄位、NotebookEdit schema、路徑正規化及私有 plan 例外行為。
- hook crash／invalid JSON／timeout／interpreter 缺失的端到端表現；含空格路徑、假 token 不外洩等新測試尚未實作。
- Architect／Engineer／Tester／V-M-D／Closer 新 session smoke tests，以及 Closer 實際結案寫檔。
- 遠端最新 baseline、目前爬蟲 health、production DB 行為；本輪限制不允許 fetch 或正式資料操作。

下一步建議提示：

> 請完整讀取 ~/.ai-notes/ttr/critique-4-codex.md 與 plan-rev4.md，以 Architect 角色定點修為 rev.5。修正 R4-1～R4-4，納入既有範圍內的 fixture／coverage 文字補充；不重開 Q1～Q8、不新增規則類別。逐項列出修改位置與關閉理由，保留所有尚未實測的 NOT TESTED／PARTIAL；此輪不實作、不 commit、不 push。

