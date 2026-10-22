**結論：rev.2 尚未通過；應先修訂，再進入 Phase 2。** 六項先前意見中，3 項 CLOSED、3 項 PARTIAL。

本次以 Codex 評審 Claude Opus 撰寫的 rev.2，屬不同模型家族視角。已完整讀取指定角色、skill、四份 spec，並核對相關程式與官方文件；全程唯讀，未修改檔案，也未重跑 notes 所列測試。

### 六項先前意見的判定

| 項目 | 判定 | 理由與位置 |
|---|---|---|
| **(a) 不複製 secrets，不以 hooks 作安全依據** | **CLOSED** | [plan §3 Phase 2，第 134 行][p134] 已明確禁止複製兩個 `.env`，也撤回 hooks 作為安全理由。但 dry-run 的證據被過度推廣，見必修 B3。 |
| **(b) 進度與裁決同步** | **PARTIAL** | D4'、D8、D6、D7 已同步；但 [tasks Phase 1，第 23 行][t23] 的兩項待辦未反映到 plan，proposal 仍使用實作前的現況敘述，見 B4。 |
| **(c) 來源只寫 tier，保留 NOT TESTED** | **CLOSED** | [plan §1.3，第 78 行][p78] 與 [notes §2，第 43 行][n43] 符合要求；`pinned_models()` 仍攔截來源 frontmatter 的所有 `model:`。另有過期的 Haiku 預設說明，見 B4。 |
| **(d) 54 個來源 skill 不合併** | **CLOSED** | [plan Phase 4，第 170 行][p170]、tasks、proposal 與 notes 結論一致。2.6k 是估算，不能稱為逐 skill 實測。 |
| **(e) Phase 3 釘選、責任流程、安裝缺口驗收** | **PARTIAL** | [plan Phase 3，第 153 行][p153] 已提出流程與六項條件；但釘選只覆蓋 checkout，未覆蓋實際載入版本，缺失／停用狀態的處理也未完整定義，見 B2、B5。 |
| **(f) 配額與使用端驗證作為 go/no-go** | **PARTIAL** | [plan §3.1，第 184 行][p184] 已區分搬遷與配額效益；但 Phase 2 沒有配額門檻，Phase 3 的比較條件目前也無法執行，見 B1。 |

### 阻擋項：必修

**B1．配額門檻未完整落地，且缺少可執行的量測方式。**

位置：[plan §3.1，第 188 行][p188]、[tasks Phase 2，第 32 行][t32]、[notes §5，第 116 行][n116]。

- Phase 2 只要求 commit、四項使用端驗證或明確接受、D4'；**沒有要求配額曲線**。這與先前意見要求配額成為繼續平行工作的門檻仍有落差。
- Phase 3 要求一週紀錄「與之前沒有退步」，但文件同時承認沒有之前的配額基準。第一週結束仍無法完成這項比較。
- notes 尚未確認 cc-statusline 會保存配額歷史；「開始記錄」缺少採集方式、存放位置與比較尺度。
- [plan §6，第 226 行][p226] 又要求「上兩項就緒」才進 Phase 2，與 §3.1 的條件不同。

**必修修改：**統一 plan、tasks、下一步的門檻；指定最簡單可行的紀錄方式，例如人工記錄配額百分比、重置時間、完成任務與返工情況。第一週只能建立觀測基準，不能判定「沒有退步」。若 Phase 2 先做有限 spike，應明確區分 spike 與正式平行開發的准入條件。

---

**B2．D8 的 SHA 檢查沒有釘住實際執行的 harness。**

位置：[plan Phase 3，第 155 行][p155]、[tasks Phase 3，第 44 行][t44]。

`sync --check` 只比對本機 checkout 的 `HEAD`，仍會漏掉：

- checkout 有未提交修改，但 HEAD 相同；
- TTR adapter 已更新，Claude plugin 仍載入舊版本；
- user scope plugin 更新後，其他 worktree／專案仍釘在舊 SHA；
- 執行中的 session 尚未重新載入；
- Codex 安裝到使用者層的檔案與 lock 不一致。

官方文件也區分磁碟更新與 session 已載入版本；更新 plugin 不代表執行中 session 已切換。[Claude plugin 更新文件](https://code.claude.com/docs/en/discover-plugins#keep-plugins-updated)

**必修修改：**定義 lock 管理的是哪些產物，補上乾淨 checkout／內容一致性、plugin 安裝與載入版本、Codex 安裝結果的驗收，以及更新與回退責任。CI 必須有依 lock 取得 harness 的步驟；只規定「沒有 checkout 就失敗」會讓乾淨 CI 無法運作。

D8 可以採 lock，但**目前只能稱為來源版本紀錄，不能稱為完整版本釘選機制**。

---

**B3．D4' 使用了超出證據範圍的 dry-run 保證。**

位置：[plan Phase 2，第 137 行][p137]、[proposal D4'，第 47 行][pr47]、[notes §5，第 113 行][n113]。

notes 證明的是：**TCC 來源在該環境沒有 scraper/.env 時成功執行。**這不等於所有 scraper dry-run 都不需要 secrets，也不等於完全不呼叫 DB／AI。

程式存在直接反例：

- [main.py，第 433 行][main433] 先執行各來源的 `scrape()`，之後才處理 dry-run 輸出。
- [cinemaclair.py，第 343 行][cin343] 在 `scrape()` 中呼叫 OCR；[第 175 行][cin175] 讀取 API key，並在存在時呼叫 OpenAI。
- [gguide_tv.py，第 39 行][gg39] 的來源補查會建立 Supabase client。
- [tokyoartbeat.py，第 25 行][tab25] 使用 Contentful token；缺少設定會影響來源驗證。

**必修修改：**把結論限縮為已測的 TCC 路徑，並明確寫成「dry-run 跳過 orchestrator 的寫入與後續 annotation；來源內部行為另行確認」。其他來源的完整性及無憑證行為保留 **NOT TESTED**。

**D4' 不複製正式 secrets 的原則成立。**更簡單的做法是先限定已確認的驗證來源；其餘用 fixture、mock 或使用者自行驗證，不必為此立即另建 secrets 系統。

---

**B4．進度與模型描述仍有具體漂移。**

位置：[plan Phase 1，第 123 行][p123]、[tasks 第 23 行][t23]、[proposal Why，第 18 行][pr18]、[plan §1.3，第 81 行][p81]。

- tasks 尚待更新 Architect 範本與 handoff 的模型評估規則，plan 卻只寫「程式碼完成」，沒有列出這項未完成交付。
- tasks 的 `ANTHROPIC_DEFAULT_OPUS_MODEL` 評估未在 plan 中交代去留；不應默默消失。
- proposal 仍稱模型政策「沒有分級」，但 Phase 1 已實作。
- plan 稱 X1–X4 四角色沒有 tier，會由 Haiku 預設接手；[notes 第 29 行][n29] 明載十五個來源 agent 全部已有 tier。生成的 architect wrapper 是 Opus，其餘三者是 Sonnet。**未投影權限不等於未投影模型。**
- §0 的十三個 agent 是歷史盤點；應標明不可代表 Phase 1 後的現況。
- 「各 phase 各自一個 worktree」的 [plan §3 標題][p113] 與 [proposal D1][pr43]「Phase 1、2 共用」矛盾。

**必修修改：**依 tasks 與 notes 列出實作、文件、runtime 驗證各自的未完成項；移除錯誤的 X1–X4 預設模型說明。每個尚待執行的 phase 也應標示建議模型與 effort，目前只有 Phase 2 下一步有寫。

---

**B5．Phase 3 的安裝缺口尚未形成完整驗收契約。**

位置：[plan Phase 3，第 151 行][p151]、[六項驗收，第 161 行][p161]。

目前條件處理「未安裝」，但沒有覆蓋「已安裝但停用、載入失敗、版本錯誤」。此外：

- 缺失警告必須由 **TTR 保留的設定與腳本**執行，不能依賴缺失的 plugin；位置尚未明寫。
- `permissions.ask` 保留直接 push 規則，不等於保留 guard 對包裝命令與破壞性操作的涵蓋。
- 第二專案只實測 force push，不足以證明檔案 guard 與 launcher 的失敗處理也接線正確。
- 把正常根目錄 session 新增的 plugin 依賴，稱為與「從子目錄啟動」同級殘餘風險，沒有比較依據。

**必修修改：**列出上述狀態的預期行為、警告來源，以及缺少防線時仍允許哪些操作。若接受只有警告、仍繼續執行，須在 D8 裁決中明確呈現這個取捨。移除本地 hooks 前，至少驗證 Bash guard、file guard、launcher 失敗與單次觸發。

---

**B6．「已查證／實測」標示混淆文件查閱與本機驗證。**

位置：[plan §1.2，第 48 行][p48]、[§4 標題，第 195 行][p195]、[notes 第 118 行][n118]。

- 「相容性實測依據（Orca 文件）」實際是文件推論；Orca 中 hooks、push ask、跨 session 可見性仍列在未來驗證步驟。應改為「文件描述，本機整合 NOT TESTED」。
- §4 將整段稱為「已查證」，但 Orca 記憶體、release 頻率與整合行為沒有 notes 證據或逐項來源。
- notes 第 118 行僅因命令曾 `cd` 到 scraper，就斷定那次 hooks 沒有保護。這混淆了 session 啟動目錄與命令工作目錄。官方文件指出 `CLAUDE_PROJECT_DIR` 保持 session 起點，`cwd` 才隨 `cd` 改變。[Claude hooks 路徑文件](https://code.claude.com/docs/en/hooks#reference-scripts-by-path)

**必修修改：**逐項標示「文件支援／程式靜態核對／本機實測／NOT TESTED」。notes 為追加式紀錄，應追加更正，保留原觀察；該次 hooks 是否執行，沒有 debug 紀錄就維持未知。

### 非阻擋建議

**N1．Phase 3 應先縮小試裝，再決定是否搬走 hooks。**

位置：[plan §2，第 92 行][p92]、[Phase 3，第 147 行][p147]。

商業對齊評為 **🟡 弱對齊**：主要價值是開發成本與維護效率，沒有直接改善活動資料。Phase 3 複雜度 **high**、已證明價值 **low**、預期價值 **medium**：它同時新增 repo、marketplace、plugin、Codex installer、版本同步與第二專案驗證。

更簡單的試點是：第二專案只載入一個 agent、一個 skill，先用本地 `--plugin-dir`；保留 TTR 現有 hooks。確認實際復用收益後才推進發布與防線搬遷。這不撤回 D2 的方向，只縮小第一個交付。

**N2．解除 Phase 4 瘦身對 Phase 3 的強制依賴。**

位置：[plan Phase 4，第 171 行][p171]、[go/no-go，第 190 行][p190]。

量測、刪除重複說明與必要的 AGENTS 精簡，可以獨立完成；不必等 plugin 化。也不要為了 context 數字，把 Codex 仍需直接遵循的行為規則全部移成連結。

**N3．縮小平行工具 spike，設定一次性的停止條件。**

位置：[plan Phase 2，第 143 行][p143]。

同時測 Orca orchestration 與 agent teams、各開三個 agent 做治理研究，會擴大本計畫正在處理的配額問題。先完成一個具體工作流；無明確收益即停止，不繼續疊加治理。

優先順序評為 **🟡 可延後**。例如 [tier1-data-completion/tasks.md，第 3 行][business3] 仍列資料完整性工作。這只是待辦證據，未證明目前 production 缺口仍存在，因此不能據此宣稱爬蟲正在斷流。

**N4．沿用現有生成器與測試，避免再造平行 adapter 系統。**

位置：[plan Phase 3，第 147 行][p147]、[sync 既有生成流程][sync300]、[settings 測試][settings88]。

應延伸 `agent_outputs()`、`expected_outputs()`、`check()`，並明確拆分通用 guard 測試與 TTR 接線測試。現有 `test_settings_exact_shape` 在 `scripts/tests/`，僅搬 `scripts/claude/tests` 不會涵蓋它。

本計畫沒有新增 UI component、DB migration、分類、event_form 或 i18n key；已核對的 Category、Event Form、i18n、FC 與 SCRAPERS guards，目前沒有直接觸發點。

**N5．補上提交後的進度紀錄。**

位置：[tasks 第 16 行][t16]、[notes 第 120 行][n120]。

rev.2 四份文件已包含於本地 commit `dfb40b6b`，tasks 仍列「等待核准後 commit」。tasks 應更新；notes 保留歷史敘述，再追加提交結果。此處不代表已推送或已取得部署核准。

### 不確定與必須保留 NOT TESTED 的事項

| 項目 | 證據界線／位置 |
|---|---|
| Codex agent effort、plan profile、Claude plan-critic Opus/high、opusplan 切換 | 四項仍為 **NOT TESTED**。[notes 第 43 行][n43]。官方文件支援設定形式與限制，但不能替代本機生效證據。[OpenAI custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents)、[profiles](https://learn.chatgpt.com/docs/config-file/config-basic) |
| Haiku wrapper 的 effort 與任務品質 | notes 只證明 tester 的 `modelUsage` 是 Haiku；未證明 low effort 已生效，也未證明輸出品質。[notes 第 41 行][n41] |
| web 佔位值 build、來源完整性 | web 已正確標 **NOT TESTED**；其他 scraper 不能由 TCC 一次成功推廣。[plan 第 138 行][p138] |
| Orca 整合、plugin 防線與版本一致性 | 都尚未實測；不能列為已完成的相容性。[plan 第 144 行][p144]、[Phase 3][p147] |
| 專案 skill 2.6k、Memory files 歸因 | 2.6k 是 bytes 換算估算；8.7k 未逐檔拆解。保留不合併結論，但精簡收益待重量。[notes 第 70 行][n70] |
| 配額是否改善 | 無 Phase 1 前基準，也無已確認的歷史採集流程，目前不能作因果結論。[notes 第 116 行][n116] |
| rev.1 批評是否完整落實 | 原批評全文未提供；只能核對本次使用者列出的六項，不能宣稱原報告全部結案。[notes 第 101 行][n101] |

[p48]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:48
[p78]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:78
[p81]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:81
[p92]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:92
[p113]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:113
[p123]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:123
[p134]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:134
[p137]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:137
[p138]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:138
[p143]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:143
[p144]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:144
[p147]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:147
[p151]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:151
[p153]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:153
[p155]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:155
[p161]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:161
[p170]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:170
[p171]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:171
[p184]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:184
[p188]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:188
[p190]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:190
[p195]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:195
[p226]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/plan.md:226
[t16]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/tasks.md:16
[t23]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/tasks.md:23
[t32]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/tasks.md:32
[t44]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/tasks.md:44
[pr18]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/proposal.md:18
[pr43]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/proposal.md:43
[pr47]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/proposal.md:47
[n29]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/notes.md:29
[n41]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/notes.md:41
[n43]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/notes.md:43
[n70]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/notes.md:70
[n101]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/notes.md:101
[n113]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/notes.md:113
[n116]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/notes.md:116
[n118]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/notes.md:118
[n120]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/ai-harness/notes.md:120
[main433]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/scraper/main.py:433
[cin343]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/scraper/sources/cinemaclair.py:343
[cin175]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/scraper/sources/cinemaclair.py:175
[gg39]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/scraper/sources/gguide_tv.py:39
[tab25]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/scraper/sources/tokyoartbeat.py:25
[business3]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/docs/specs/active/tier1-data-completion/tasks.md:3
[sync300]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/scripts/sync_ai_adapters.py:300
[settings88]: /Users/flyingship/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree/scripts/tests/test_claude_settings.py:88