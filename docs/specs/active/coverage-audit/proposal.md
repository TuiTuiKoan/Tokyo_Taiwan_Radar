---
slug: coverage-audit
title: 關鍵字覆蓋稽核：url-intake 核准防線、複合詞關鍵字、每週漏抓／亂抓稽核
status: active
branch: docs/coverage-audit-spec
created: 2026-11-22
revised: 2026-11-22 (v2, plan-critique-1)
tags: [scraper, prtimes, google_news_rss, evaluation, guard]
issues: ["#701", "#702"]
---

# 關鍵字覆蓋稽核

## Why

2026-11-22 查證 #701 時發現兩件事：

1. 共同通信 PR Wire 的寫真展「日中台：交錯するまなざし」沒有被收錄。**主因是來源缺口**：這篇稿子沒有發到 PR TIMES。要補上它，得新增 `kyodo_prwire` 來源，交由 researcher 另外評估，不在本 spec 範圍。
2. 標題過濾有預防性的漏洞：`prtimes` 的 `_TAIWAN_KW = 台湾|Taiwan|台灣|臺灣`，以樣本實測，「日中台：…開催のお知らせ」「日台交流イベント開催」「台日友好フェア」都不通過（#701 留言）。至於有多少真實稿子因此被漏掉，**還沒有證據**。Phase A 屬於預防性修正，效益要靠 Phase B 量測。

更根本的問題是，漏抓與亂抓都沒有被量測。`scraper-quality.yml` 每週只看產出量、欄位完整度與 DOM drift。

另外，Claude Code 的 `gh` 是以擁有者 `TuiTuiKoan`（User）的身分運作（plan-critique-1 實測 `gh api user`）。`url-intake.yml` 只檢查 `sender == repository_owner && sender.type == 'User'`，所以 agent 可以自己貼 `url-intake:approved`，直接寫入 production（#702）。這個風險現在就存在。

## What

分三個 PR，依序做：

| 順序 | Phase | 內容 | Tier（預期） | 建議模型 |
| --- | --- | --- | --- | --- |
| 1 | C | url-intake 核准防線：`url-intake.yml` 加上 `run_attempt == 1`，hook 對 agent 的核准類操作要求核准 | Tier 2（權限與防線） | Sonnet medium |
| 2 | A | 抽出 `title_verdict()` 純函式；複合詞用帶前後文限制的正則；正負例測試 | Tier 1 | Sonnet medium |
| 3 | B | 在 `scraper-quality.yml` 加入覆蓋稽核 job；先試做四週 | Tier 2（workflow 權限） | Sonnet medium |

- C 先做，因為它的風險已經實證存在（M1）。
- A 在 B 之前，因為 B 的探測要呼叫 A 抽出的 `title_verdict()`（B2）。
- 「權限與防線」的交付方式：以 PR 交付，使用者審核後自己按合併。PR 本身就是 AGENTS.md 所說的 patch（m2）。

## Not（不做）

- 不新增 `kyodo_prwire` 來源（#701 待辦第一項，交 researcher）。
- 不加「中台」，也不加城市名（台北、高雄等）作為台灣判斷詞。
- 稽核**不自動收錄**活動。候選是否收錄屬「活動範圍判斷」，由使用者透過 url-intake 決定。
- 稽核不呼叫 LLM，不寫入 production DB。
- 只處理 prtimes 與 google_news_rss。`daily_report._TAIWAN_KW`、`wuext_waseda.py` 的同類關鍵字另開 issue（m4）。
- 不整合月報、不做 url_intake 網域彙總（M8：後者已在 url-intake M5）。
- production environment 限制在 main 分支的問題，另開 issue 交使用者決定（m1，repo 設定屬人類關卡）。

## Design

### C. url-intake 核准防線（#702）

**C1. workflow 層（對 Codex、Copilot 也有效）**

`url-intake.yml` 的 MODE 判斷加上 `github.run_attempt == 1`（M7-6）。重跑一個舊的 run 時，`event.sender` 會沿用原始值，所以先前失敗的 apply 只要重跑就會寫入；加了這個條件後，重跑一律走 preview。要重試，就請使用者移除 label 後重新貼上。結構測試 `scripts/tests/test_url_intake_workflow.py` 增加對應斷言。

**C2. Claude Code hook**

在 `scripts/claude/_policy.py` 新增 ask 原因 `url-intake-approval`。下列操作一律**要求核准**，不阻擋：

| 類別 | 比對 |
| --- | --- |
| `gh issue edit`／`gh issue create`／`gh pr edit` | `--add-label`、`--add-label=`、`--label`、`-l` 的值依逗號拆開，casefold 並 strip 後等於 `url-intake:approved`；值含變數（`$`）時也要求核准 |
| `gh api` REST | 端點含 `issues`，且 `-f`／`-F`／`--raw-field`／`--field` 的值含 `url-intake:approved`（casefold），或使用 `--input`（內容看不到） |
| `gh api graphql` | query 含 `addLabelsToLabelable`、`createIssue`、`updateIssue`，或 query 來自檔案或變數 |
| workflow dispatch | `gh workflow run`，參數含 `url-intake`、`URL Intake`（casefold），或 workflow 參數是數字 ID 或變數；`gh api` 的端點含 `/dispatches` |
| environment 核准 | `gh api` 的端點含 `pending_deployments`（保留，不當主要防線，M7-7） |
| GitHub MCP | `mcp__github__*` 的 `tool_input` 遞迴掃描所有字串值，只要有一個值 casefold 後等於 `url-intake:approved` 就要求核准。不列舉工具名稱（M7-1） |

- 放行的負例：`--add-label url-intake`、`--add-label spec:url-intake`、`--remove-label url-intake:approved`、`gh workflow run scraper.yml`、`gh api …/issues/N/comments`。
- 殘餘風險（寫進 AGENTS.md）：claude.ai 帳號層的 GitHub 連接器（前綴不是 `mcp__github__`）、`curl` 帶 token、`gh run rerun`（由 C1 處理）。
- AGENTS.md「Hooks 與 permissions」表與 `.github/copilot-instructions.md` 的對應段落同步更新。

### A. 複合詞關鍵字

**A1. 抽出純函式**（B2）

- `prtimes.title_verdict(title) -> tuple[bool, str]`：依序判斷 placeholder → 台灣詞 → 活動詞 → 台灣當地舉辦。回傳 `(True, "ok")`，或 `(False, "placeholder" | "no_taiwan" | "no_event" | "taiwan_based")`。`scrape()` 改成呼叫這個函式，行為不變。
- `google_news_rss.taiwan_verdict(title, description) -> tuple[bool, str]`：包住 `_is_taiwan()`，`scrape()` 改成呼叫它。
- 兩個模組共用同一條台灣詞正則，放在新檔 `scraper/taiwan_keywords.py`（`TAIWAN_TITLE_RE`）。

**A2. 帶前後文限制的複合詞**（B1）

`TAIWAN_TITLE_RE` = `台湾|台灣|臺灣|Taiwan|taiwan` 加上以下三個複合詞，每個都帶前後文限制：

- `日中台`：後面不能接「風」「頭」。
- `日台`：前面不能接「今本毎昨明前翌当連終平休祝曜土」與數字，後面不能接「数風所帳車本詞」。
- `台日`：前面不能接「舞屋灯高演」，後面不能接「本」。

確切寫法以測試為準。google_news_rss 的 `TAIWAN_KEYWORDS` 改用同一條 regex。

**A3. 搜尋詞**（M3、m5）

- prtimes：增加 `"日台 イベント"`。PR TIMES API 是否做全文搜尋未知；`日中台` 不加搜尋詞，是否會被其他詞帶出，由 dry-run 確認。不加 `"日台交流"`，因為它帶回的多半是在台灣舉辦的商務稿。
- google_news_rss：**只加判斷詞，不加查詢詞**（M3 方案 a）。新聞語境的「日台交流」多半是外交報導，而且每筆都會進 annotator 的 LLM 標註。

**A4. 測試**

- 新檔 `scraper/tests/test_taiwan_keywords.py`：
  - 正例：「報道写真展「日中台：交錯するまなざし―写真でたどる100年の歩み―」 開催のお知らせ」「日台交流イベント開催」「台日友好フェア」。
  - 負例：「ミュージカル舞台日本公演 開催決定」「本日台数限定セール開催」「1日台数限定 体験イベント」「今日台風接近によりイベント開催中止」「屋台日本一決定戦 開催」「毎日台所から 料理教室イベント」「日中台風の影響でフェス中止」「中台禅寺 特別拝観 開催」。
- `test_prtimes_filters.py` 補上 `title_verdict` 整條鏈的測試。「日台ビジネス交流会を台北で開催」列為已知缺口（`xfail`，附 issue 連結，M2）：`_TAIWAN_BASED_TITLE_RE` 的分支都以字面「台湾」開頭，標題層只擋得住 `in 台北` 這種形式。這類稿子主要靠正文場地過濾與 annotator 兩層擋。
- 新檔 `scraper/tests/test_google_news_rss_filters.py`：`taiwan_verdict` 的正負例。
- PR 的 dry-run 證據：prtimes 列出新增搜尋詞帶回的筆數、只靠複合詞通過的筆數，以及正文抓取次數。

### B. 每週覆蓋稽核（試做四週）

**位置**：不新增 workflow，在 `scraper-quality.yml` 加兩個 job（M8），都加 `if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'`，權限在 job 層宣告。排程沿用該檔的週日 09:00 JST。

**B1. `coverage-probe` job**（不帶 secrets、`contents: read`、`persist-credentials: false`）

- 探測詞：
  - prtimes：`日台`、`日中台`、`台日`，加上 `台湾` 對照組。
  - google_news_rss：`日台`、`日中台`、`台日`。
  - 城市名、金曲、故宮等詞，四週後再評估。
- 每筆結果用 A1 的 `title_verdict` 或 `taiwan_verdict` 判斷，記錄 `(ok, reason)`。探測**沒有自己的過濾邏輯**；唯一例外是 google_news_rss 的候選也要求標題通過 prtimes 的活動詞判斷，這一點在報表上註明。
- 排除發布不到 48 小時的項目，避免把每日 scraper 還沒跑到的稿子算成漏抓（B2-3）。也排除超過 prtimes `LOOKBACK_DAYS` 的項目。
- prtimes 標題通過、DB 又沒有的項目（最多 20 筆）：抓正文，套用 `_should_skip_taiwan_venue`。抓不到正文的列為「未判定」。
- google_news_rss 不解碼轉址，用 `gnews_`+md5 比對。只對報表列出的候選（最多 20 筆）解碼，解碼失敗的不附一鍵連結（M4）。
- 輸出 JSON artifact。

**B2. `coverage-report` job**（`environment: production`、`issues: write`、只執行 select）

- 驗證 artifact 的 schema、筆數上限與字串長度（沿用 `ingest_url.validate_payload` 的作法，m1）。
- 「已收錄」的判定：跨所有 `source_name`、不分 `is_active`，以 `normalize_url` 正規化後的 `source_url`／`official_url` 比對，source_id 只作輔助（B2-4）。
- 漏抓的分類：
  - 已收錄。
  - 被標題過濾，依原因分組。`taiwan_based`（台灣當地舉辦）只報數字，不列清單（m6）。
  - 通過但未收錄：正文判定為台灣當地舉辦的，歸到「被正文過濾」，不列清單。
  - 未判定。
- 亂抓：prtimes、google_news_rss 過去 28 天新增的事件，用「x / y」計數，不用百分比（M6）。
  - 計入：`out_of_scope:`、`admin confirmed irrelevant`、`auto-deactivated: annotator Taiwan relevance gate`。
  - 待人工歸因：`manually deactivated by admin`。
  - 不計入：合併類、`pre_migration_044_legacy`、空白標題、孤兒子活動、`admin reported wrong …`（暫時停用）。
  - 其他值：歸到「未分類」並印出原字串。
  - 只靠複合詞通過的事件（標題不含台湾等字，但符合複合詞），從 Phase A 合併日起累計下架數。
- 輸出：
  - run summary 放完整報表。
  - 一張滾動 issue「覆蓋稽核週報」：由 agent 在合併前手動建好，貼 label `coverage-audit`。report job 以 label 搜尋，找到 0 張或超過 1 張就讓 job 失敗，不自動建立。每週留一則摘要。
- 外部內容寫進 issue 時（M5）：
  - 標題：摺疊換行、移除其中的 URL，再套用 `escape_md`。
  - URL：用 `normalize_url` 驗證，並限定在探測來源的 host。
  - 一鍵開 url-intake 的連結：`issues/new?title=…&body=…`，參數以 `urllib.parse.quote` 編碼，body 的第一行固定是目標 URL。不帶 `labels=`，所以不會觸發 url-intake。repo 也沒有 issue template。

**門檻**：前四週只出報告。四週後依數字決定警示門檻、是否擴大探測詞，以及是否改成月報。結論寫進 `notes.md`。

**成本**：無 LLM 呼叫。每週的 HTTP 請求包括：prtimes 4 個詞 × 最多 2 頁、google_news 3 個請求、最多 20 次正文抓取、最多 20 次轉址解碼（每次 sleep 1 秒）。

**修訂後再評審**：依 plan-critique-1 的結論，Phase B 實作前再評審一次（plan-critique-2）。

## 風險

| 風險 | 處理 |
| --- | --- |
| 複合詞誤收（舞台日本、本日台数等） | A2 帶前後文限制，A4 列入 8 個負例；Phase B 追蹤只靠複合詞收進來的事件下架數 |
| 「日台」標題常是在台灣舉辦的日本企業活動 | 標題層只擋得住 `in 台北`。主要靠正文場地過濾與 annotator 兩層擋。已知缺口以 xfail 記錄 |
| 探測與 scraper 的判斷分歧 | 共用 `title_verdict`；scraper 自己也呼叫它 |
| 「通過但未收錄」假陽性 | 48 小時寬限、LOOKBACK、正文場地過濾、跨來源 URL 比對 |
| hook 的比對形式繞過 | casefold、拆逗號、變數一律 ask、`--input` 一律 ask、MCP 遞迴掃描；C1 處理重跑 |
| hook 誤擋 | 只比對 `url-intake:approved` 與 url-intake 的 dispatch，決策是 ask 不是 deny |
| 週報沒人看 | 滾動 issue 會出現在看板；四週後檢討 |

## 評審紀錄

plan-critique-1（Claude plan-critic，與撰寫者同一模型家族；Codex 在本環境不可用）的處理方式：

| 項目 | 處理 |
| --- | --- |
| B1 子字串誤收 | 採納：A2 加前後文限制，A4 列入 8 個負例，google 改用共用 regex |
| B2 探測假陽性 | 採納：A1 抽出 verdict 函式；B1、B2 加入寬限、LOOKBACK、正文判斷與跨來源 URL 比對 |
| M1 C 先做；A 不補 #701 本身的漏抓 | 採納：順序改為 C→A→B；Why 段改寫 |
| M2 `_TAIWAN_BASED_TITLE_RE` 只認台湾 | 採納：已知缺口以 xfail 記錄，風險敘述改寫 |
| M3 google 新查詢引進政治新聞 | 採納方案 a：只加判斷詞，不加查詢詞 |
| M4 探測成本與轉址 | 採納：不預先解碼，只對候選解碼 |
| M5 跳脫與 URL 搶位 | 採納 |
| M6 deactivated_reason 分類與樣本量 | 採納 |
| M7 hook 覆蓋面 | 採納 1～6；7 保留但不當主要防線 |
| M8 過度設計 | 採納：併入 scraper-quality.yml，不做月報整合與網域彙總，探測詞縮減，滾動 issue 改為手動建立 |
| m1 production 限制在 main | 另開 issue；artifact 驗證採納 |
| m2 交付方式 | 寫明：以 PR 交付，使用者審核合併 |
| m3 測試 | 採納 |
| m4 其他關鍵字表 | 另開 issue |
| m5 搜尋詞 | 採納：不加「日台交流」，dry-run 列出數字 |
| m6 排除 taiwan_based | 採納 |
| m7 A 先做的理由 | 改寫為「B 要呼叫 A 的函式」 |

## 參考

- #701、#702
- `plan-critique-1.md`
- `docs/specs/active/url-intake/`
- `docs/specs/active/evaluation-framework/`
- `.github/workflows/scraper-quality.yml`
