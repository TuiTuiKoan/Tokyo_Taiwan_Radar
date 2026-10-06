# Plan Critique — ai-portability hardening rev.3（第三輪）

日期：2026-10-05  
評審模型：OpenAI GPT（Codex），與計畫標示的 Claude 作者屬不同模型家族。

**結論：rev.3 仍有五項必修阻擋，退回 Architect 定點修訂為 rev.4。Phase 0 的 spec 骨架可準備，但目前不能將 rev.3 標為「已通過評審」交付實作。**

本次完整讀取指定 Plan Critic agent、其 skill、專案總規則、rev.3、handoff 與相關程式證據。評審期間唯讀，未執行 adapter generation、實作測試、commit、push 或 production DB 操作。本檔依使用者後續要求保存；不修改 repository。

## 1. 商業主軸對齊（Business Alignment）

**🟡 間接對齊。** 計畫支援開發環境遷移與營運延續，符合全日本台灣相關活動聚合的使命；不直接改善活動覆蓋率、annotation 品質或使用者觸達。

「部分 hardening」聲明正確。四角色延期、腳本介面的 DB 寫入、Codex／Copilot 未受 hooks 保護，均須保留為明確邊界，不得將此次交付描述成全面保護。[rev.3 §1](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:29)

## 2. 複雜度 vs 價值評估

**複雜度 high／業務價值 medium，複雜度高於直接業務價值。**

範圍包括三階段、12 個 canonical agent 權限投影、16 個 wrapper、五個 hook／launcher 模組、四個 hook 測試檔，以及十類規則至少 30 個阻擋變體；沒有 migration 或新增 i18n key。[Phase B](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:302)、[Phase C](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:333)

250 行 tokenizer 預算與「超限停止」方向合理；行數不是安全性證據。以明確支援語法、拒絕未知語法與正負向 fixtures 控制範圍，不擴張成完整 shell interpreter。

## 3. 優先順序提醒與修訂追蹤

**🟡 可繼續，但必須維持有限交付。** 九月月報記錄 NDL 40／40 件在 24 小時內被報錯、kokuchpro 修復延遲中位數 138 天。這些是資料品質調查訊號，不能直接當成目前缺陷已確認，也不能忽略。由其他工作線確認報錯定義、根因與現況。[九月月報](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/monthly_review/2026-09.md:47>)

以下為計畫修訂狀態，**不是實測 PASS**。

| 項目 | 判定 |
|---|---|
| B1 handoff 修改邊界 | 已解決；frontmatter 除 prompt 外逐 key 比對可行 |
| B2 B 的 push 閘門 | 已解決原階段依賴；最小 ask 移入 B，變體留 C |
| B3 substitution 檢查 | 核心方向已修正；與 N3 仍衝突，見 R3-1 |
| B4 .env 路徑防護 | 已補 rg、Grep、stdin；metadata 豁免仍有漏洞，見 R3-2 |
| B5 啟動 fail-closed | launcher 可涵蓋列出的 process failure；尚未實測，另補輸出協定測試 |
| B6 冪等 | 已解決；完整路徑集合＋內容雜湊比對正確 |
| N1 Allowed paths | 發現成立；Q5 已核准 |
| N2 masked awk | 發現成立；精確模板與漂移測試可行，須補負向測試 |
| N3 heredoc commit | 需求成立；目前 guarded 動態參數規則仍會拒絕 |

[rev.3 修訂表](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:9)、[語法契約](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:365)

Q1、Q3–Q7 已在 handoff 的 2026-10-05 裁決中定案，**不需重問**。[已定裁決](/Users/flyingship/.ai-notes/ttr/handoff.md:23)

| 裁決 | 可行性與落實要求 |
|---|---|
| Q1 刪除 Session Memory | 可行；刪除 weekly-review Step 3 並同步編號 |
| Q3 Lianbu readonly | 可行；與現有 Copilot 工具類別一致 |
| Q4 保留 ahead=1 起點 | 可行；固定保存 campaign base ed09bece，後續 rebase 不重算歷史 base |
| Q5 擴充 Allowed paths | 可行；其他 active spec 僅改核准的權威句與相鄰標註 |
| Q6 V-M-D／Closer 無 Edit／Write | 可行；補 Closer 實際結案寫檔驗證 |
| Q7 擴大規則 7、10 | 可行；須修正豁免漏洞與釐清共用防線作用域 |

## 4. 全站架構整合分析：五項必修阻擋

### R3-1 — N3 被 guarded 動態參數規則拒絕

rev.3 第 368 行只允許 rev-parse、目前分支、pwd；heredoc commit 的內層是 cat，因此必須被判 dynamic-args，與 must-allow 相衝突。[規則](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:368)、[fixture](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:380)

**修正：**只為 git commit 的 -m／--message 定義受限 quoted-heredoc cat 例外，不泛化為任何 cat substitution。補負向 fixtures：額外命令、unquoted heredoc、cat .env、輸出重導。所有可執行 substitution 仍須遞迴檢查。

### R3-2 — metadata 動詞豁免會放行 .env 寫入

目前整個 segment 只要動詞在白名單就豁免，因此字串案例 `wc .env > .env`、`git check-ignore .env > .env` 會被允許，shell 卻會先截斷 .env，違反 Q7 已核准的防覆寫範圍。這些案例僅作靜態推導，未執行。[規則 7](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:440)

**修正：**敏感路徑的寫入重導優先拒絕，不受 metadata 或 masked-awk 例外豁免。例外限定完整參數形式。N2 補修改 awk program、追加 -f、追加重導的負向測試；保留 instructions 漂移測試與假 secret fixtures。

### R3-3 — SQL 首關鍵字不能證明唯讀

`psql -c 'SELECT 1; DELETE FROM events'` 首字是 SELECT，仍包含寫入；SELECT INTO 本身會建表，-c 也能重複出現。這些案例未執行。[規則 9](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:454)、[psql 官方說明](https://www.postgresql.org/docs/current/app-psql.html)、[SELECT INTO 官方說明](https://www.postgresql.org/docs/current/sql-selectinto.html)

**修正：**檢查每一個 -c，拒絕未支援的多語句及 SELECT INTO。若保留一般 SELECT 放行，明列函式副作用仍未受保護，並收窄「production write 一律阻擋」的措辭。維持啟發式邊界，不為此新增 migration 或完整 SQL interpreter。

### R3-4 — B-R7／B-R8 Carry-over 未完整接入 C

B 將 planner／Tester 的限制延期至 C，但 C-R1–C-R8 只明確承接 push；file guard 的具體契約僅涵蓋 Read／Grep 敏感路徑。plan-mode fallback 又保留 Write，缺少 repo 寫入拒絕的實作與驗收。[B gate](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:86)、[C gate](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:92)、[fallback](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:251)

**修正：**新增條件式 C Required，明列角色辨識、Write／Edit／NotebookEdit 的 repo 路徑拒絕、工具私有 plan 路徑例外及負向測試。辨識無法證實時不得宣告通過。保留 Bash 時不能宣稱「無 repo 寫入能力」；gate 必須區分工具禁用與已接受的 Bash 殘餘風險。這是既有 Carry-over 的落實，不是另增危險操作規則類別。

### R3-5 — 全域 settings 與四角色「hook 不動」作用域不一致

計畫排除四角色的權限與 hook 變更，卻加入 project-wide permissions／hooks，沒有定義四角色的處置。官方文件明定 settings hooks 同樣會在 subagent 內執行；不改 wrapper 不代表行為不受影響。[排除範圍](/Users/flyingship/.ai-notes/ttr/plan-rev3.md:474)、[官方 hook scope](https://code.claude.com/docs/en/hooks#hook-locations)

**修正：**明確區分「四角色專屬權限延期」與「共用危險操作防線適用範圍」，核對既有裁決能支持哪種解讀。若要求四角色行為完全維持現況，須先證實角色識別與排除方案。不能用目前設計宣稱 B、C 都不影響它們，也不能直接將缺失識別當成全面豁免。

已查核 Category、Event Form、i18n、FC persistence、SCRAPERS completeness Guards，本案不修改其業務鏈。治理計畫須遵守「政策與實際 consumer 一致」及 baseline 漂移檢查；本次尚未 fetch，不能將缓存 origin/main 當遠端最新證據。

## 5. 既有 Component／工具復用建議

**🟢 充分復用。** 沿用 scripts/sync_ai_adapters.py 的 parse_frontmatter()、agent_sources()、agent_outputs()、expected_outputs()、check()、pinned_models()；新增角色投影與 fixtures，不另建第二套 generator。

Q6 不必重新授予 Write：Closer 保留 Bash，可用定向寫檔完成既有職責。但其流程明確要求結案記錄與 recovery capsule，必須補入 smoke test，不能只驗證工具清單。依據：.github/agents/campaign-closer.agent.md:116、121、146。

B5 另補「exit 0 但 ask JSON 無效」的測試與處置契約。官方將此類錯誤視為非阻擋；僅轉換 process exit code 不足以涵蓋輸出協定失敗。[官方 JSON 處理](https://code.claude.com/docs/en/hooks#exit-code-0)

## 6. 建議更新後的計畫與交接

交回 Architect，只修改五個必修契約點，保留三階段、四角色延期、第一批十類規則與已定 Q1／Q3–Q7 裁決；不重開已核准選項。

落檔整理：

- rev.4 將 Q1、Q3–Q7 改為「已裁決」，引用 handoff 證據。
- Phase 0 一併保存第三輪 critique；目前清單只有前兩輪。
- B-R4 除列出 16 個 agent，還須核對來源路徑；名稱數量不能證明載入 worktree wrapper。
- campaign base 固定 ed09bece；將它與每次執行時的最新 remote baseline 分開記錄。

第三輪審查時的唯讀證據：

- registered worktree：/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree。
- branch：feat/ai-portability；HEAD：565c1479642761d35162e76a7f337b377596a56d。
- working tree clean；現有 `python3 -B scripts/sync_ai_adapters.py --check` exit 0。
- 本機缓存 origin/main 與 merge-base：ed09beceb5004bc8025958c0b752075ed92dd448；未 fetch。
- 新權限、hooks、載入來源與使用者 smoke test 均未實測，不能標 PASS。

**下一步：Architect 回傳 rev.4 完整計畫與修改對照表 → Plan Critic 核對阻擋項是否關閉 → Engineer 建立 Phase 0 spec。修正前不標記 rev.3 評審通過。**

本次使用者要求的存檔僅授權保存評審結論，未授權 repo 實作、commit、push 或 production DB 操作。
