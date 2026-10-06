# Plan Critique — ai-portability hardening 計畫 rev.2

**結論：退回修訂。** Phase 0 可準備；Phase A 需小修；Phase B、C 尚不能依 runbook 判定通過。

本次模型：**OpenAI GPT-6（Codex）**，與首輪 Claude Opus 5.5 不同家族。rev.2 未標示 Architect 的確切模型。本次完整讀取指定 agent、skill、AGENTS.md 與總規則，全程唯讀，未執行生成、測試、commit 或其他寫入指令。

> 本報告原於唯讀審查中回傳；依使用者後續要求，保存至 `~/.ai-notes/ttr/critique-2-gpt.md`。本次存檔不修改 repository。

**1. 商業主軸對齊：🟡 間接對齊**

計畫支援開發環境遷移與營運延續，沒有偏離全日本台灣活動聚合的使命；但它不直接改善資料品質、覆蓋率或使用者觸達。應以完成有限、可驗證的遷移防護為終點，避免擴張成通用 shell 安全框架。

**2. 複雜度與價值：high／medium**

rev.2 已收斂混淆偵測，但仍包含三階段、12 個 canonical agent 權限修改、16 個 wrapper、adapter 測試，以及 10 類 hook 規則、至少 30 個阻擋變體。[計畫：149](</Users/flyingship/.ai-notes/ttr/plan-rev2.md:149>)、[計畫：203](</Users/flyingship/.ai-notes/ttr/plan-rev2.md:203>)

主要成本仍在 shell 解析及權限整合。應明確定義支援的語法與拒絕未知語法的處置，避免工程師自行補成完整 interpreter。

**3. 優先順序與首輪批評追蹤**

以下都是「計畫已補」，不是「實測通過」。

| 首輪批評 | rev.2 判定 |
|---|---|
| planner 以文字回傳，由接手者落檔 | 已解決職責矛盾；handoff 修改限制仍衝突 |
| plan mode 的 Write／ExitPlanMode 相容性 | 已補 spike，尚未證實 |
| 四角色權限與職責衝突 | 已記錄並延期，**沒有解決原驗收** |
| surface matrix、pinned-model 負向測試、CI 後續項 | 已補 |
| push ask、路徑含空格、Phase C doctor | 已補；階段依賴仍未修正 |
| hook 例外、誤傷與 force-push 家族 | 有改善，仍有入口失敗與漏攔問題 |
| scraper-expert history 兩處分類 | 判定正確；實際位置是 `.github/skills/scraper-expert/history.md` |

**首輪對 Reviewer 的批評有事實錯誤。** Reviewer 明文「不修改任何檔案」，報告生成與 commit 是 workflow 的職責。[Reviewer：35](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/reviewer.agent.md:35>)、[workflow：119](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/workflows/monthly_health_check.yml:119>)。rev.2 的 X2 應直接更正，不必繼續列「證據待核實」。

另外，首輪「沒有紅燈爬蟲，因此沒有更高優先事項」的推論不足。九月月報列出 NDL 40／40 件在 24 小時內被報錯，以及 kokuchpro 修復延遲中位數 138 天；這不能直接證明當前斷流，但不能被當成資料品質無待辦的證據。[月報：47](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/monthly_review/2026-09.md:47>)、[月報：62](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/monthly_review/2026-09.md:62>)

**4. 架構整合：六個阻擋項**

**B1 — Phase A 同時要求修改、禁止修改 Architect handoff。**  
[A1：75](</Users/flyingship/.ai-notes/ttr/plan-rev2.md:75>) 寫「handoff prompt 同步」，又寫「不動 frontmatter」。舊路徑就在 frontmatter，而且 adapter 會把它原樣輸出成 Claude handoff。[Architect：7](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/.github/agents/architect.agent.md:7>)、[adapter：236](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/scripts/sync_ai_adapters.py:236>)

**修正：**禁止修改的範圍應限定為權限 metadata；允許修改 `handoffs[*].prompt`。否則 Phase A 必然留下 active legacy guidance。

**B2 — B 的通過依賴 C，違反既定階段順序。**  
runbook 規定前階段未通過不得進下一階段，且把 Engineer push 核准列在 B 驗收；rev.2 卻明確延到 C。[runbook：232](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md:232>)、[runbook：317](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/CLAUDE_CODE_MIGRATION_RUNBOOK.md:317>)、[計畫：166](</Users/flyingship/.ai-notes/ttr/plan-rev2.md:166>)

**修正：**把最小 push ask 設定與驗證移入 B；或明確修訂階段驗收契約。四角色延期裁決可保留，但本次應標為「部分 hardening」，不得宣稱原 runbook 三缺口全部完成。

**B3 — 參數位置的 command substitution 被錯誤視為安全。**  
[計畫：183](</Users/flyingship/.ai-notes/ttr/plan-rev2.md:183>) 明確允許參數位置的 `$(…)`。例如字串 fixture `printf '%s' "$(git reset --hard)"`，內層仍會執行；外層動詞無危險不構成安全證明。**這也是首輪批評開出的錯誤修正方向。**

**修正：**所有可執行 substitution 都須檢查內層；只允許已確認安全的形式，如 `$(git rev-parse HEAD)`。並補引號內分隔符、無空格串接的正負向 fixture。`shlex` 是詞法分析器，不提供完整 shell 語意驗證。[Python 官方文件](https://docs.python.org/3/library/shlex.html)

**B4 — `.env` 防護漏掉正常讀取工具。**  
[規則 #7](</Users/flyingship/.ai-notes/ttr/plan-rev2.md:197>) 列 `grep` 與 `Read`，沒有 `rg` 或 `Grep` 工具；`rg '^' scraper/.env` 就符合「直接輸出全文」，卻不在列出的阻擋面內。

**修正：**納入 `rg`、`Grep` 的敏感路徑內容讀取，以及 stdin 重導等形式；使用假 secret fixtures。這屬第一批既定需求，不是追加字元混淆防禦。

**B5 — hook 的 fail-closed 尚未涵蓋啟動階段。**  
[計畫：184](</Users/flyingship/.ai-notes/ttr/plan-rev2.md:184>) 的 `main()` 外層捕捉不能保證攔住進入 handler 前的 syntax error 或頂層 import failure。其非阻擋退出會讓工具繼續正常權限流程；timeout 也不是阻擋保證。[Claude 官方 hooks 文件](https://code.claude.com/docs/en/hooks#other-exit-codes)

**修正：**定義啟動器如何把非預期失敗轉成阻擋，並測試 syntax/import failure。釐清 [殘餘風險：225](</Users/flyingship/.ai-notes/ttr/plan-rev2.md:225>)「缺 python3 為 fail open」與第 174 行 `exit 2` 的矛盾；timeout 防護須另列邊界。

**B6 — 冪等驗收混淆了「相對 HEAD 有修改」與「第二次生成有新增修改」。**  
[計畫：107](</Users/flyingship/.ai-notes/ttr/plan-rev2.md:107>)、[計畫：159](</Users/flyingship/.ai-notes/ttr/plan-rev2.md:159>) 的 `git diff --exit-code`，在預期修改尚未 staged／commit 時就會失敗；反之，未追蹤的新檔不會因此被完整驗證。

**修正：**在 fixture 比較第一次與第二次生成後的完整檔案集合及內容。repo 的 scoped diff 用來檢查範圍，不能取代冪等測試。

另有兩項必須釐清：

- **Production DB 防護只是有限啟發式。** `psql -f patch.sql` 的 SQL 不在命令文字內，[規則 #9](</Users/flyingship/.ai-notes/ttr/plan-rev2.md:199>) 未定義如何判定。應明確拒絕無法檢查的 SQL 輸入，並避免把任意 `--dry-run` 字串當安全豁免。依既有裁決，X3 可延期，但不能宣稱 production write 全面受保護。
- **Copilot 一致性檢查缺判準。** rev.2 給 V-M-D `Edit`、Closer `Write`，其 Copilot tools 卻沒有對應編輯項。[計畫：128](</Users/flyingship/.ai-notes/ttr/plan-rev2.md:128>) 應定義一致性是工具對照還是職責能力對照，否則 `--check` 的預期結果不明。

已查核 Category、Event Form、i18n、FC persistence、SCRAPERS completeness Guards；本計畫不修改其業務鏈，均不觸發。

**5. 既有資產復用：🟢 方向正確**

應沿用 `agent_outputs()`、`expected_outputs()`、`check()` 與 `pinned_models()`，新增角色投影與 fixture，不另建第二套 generator。[adapter：210](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/scripts/sync_ai_adapters.py:210>)

新增 hook 模組合理；Phase A 對 active spec 的標註則必須指定實際可用的權威文件。仍有「唯一 authoritative plan」的現行文字，不能只籠統補上 historical 標籤。[publication tasks：8](</Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-portability-worktree/docs/specs/active/publication-policy/tasks.md:8>)

**6. 建議修正與交接**

請 Architect 修訂 B1–B6，並完成以下三件事：

- 更正 X2，保留其餘已裁決的延期範圍。
- 分別列出 A、B、C 的必要通過條件；`NOT TESTED` 或「部分達成」不能默認解除下一階段 gate。
- 將「wrapper 檔案數為 16」與「16 個 wrapper 實際載入成功」分開驗證。

建議交接提示：**「依本次六個阻擋項修訂 rev.3，保留四角色延期裁決，明確區分本次部分交付與 runbook 完整完成；只修訂計畫，不實作。」**
