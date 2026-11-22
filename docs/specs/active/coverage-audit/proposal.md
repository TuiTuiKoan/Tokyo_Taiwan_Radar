---
slug: coverage-audit
title: 關鍵字覆蓋稽核：url-intake 核准防線、複合詞關鍵字、每週漏抓／亂抓稽核
status: active
branch: docs/coverage-audit-spec
created: 2026-11-22
revised: 2026-11-22 (v3, plan-critique-1, plan-critique-2)
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

### B. 每週覆蓋稽核（v3，試做四週）

**前提**：#724（Phase A）已合併，因為 B 要 import `title_verdict` 與 `compound_only`。

**範圍（最小可行版，plan-critique-2）**

- 漏抓探測**只做 prtimes**。google_news_rss 只做 DB 端的亂抓計數（PM3）：A3 已決定 google 不加查詢詞，探測回答不了可執行的問題，又要解碼、二次查 DB，還得補 Yahoo／stale 判斷。
- 延後到四週盤點（M6）：google 探測與解碼、城市名等探測詞、`secondary_source_urls` 比對、門檻警示。

**位置**：在 `scraper-quality.yml` 加兩個 job。兩個都加 `if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'`，並在 job 層明列權限（宣告後會覆蓋頂層權限，m1）。排程沿用該檔的週日 09:00 JST。

**信任邊界：先查 DB，再碰外部內容**（PB1）

持有 DB 金鑰的 job 永遠不處理外部內容。

1. `coverage-db`：`environment: production`，權限 `contents: read`，只做 select。輸出 artifact `coverage-known`（`retention-days: 1`；repo 是 public，所以只放公開的 URL、ID 與計數）。用三次 `db_paging.fetch_all` 加 `.order("id")`（m3）：
   - **prtimes 已知鍵**：`source_url` 或 `official_url` 含 prtimes.jp，或 `source_name = prtimes`，不分 `is_active`，不加時間條件。比對鍵是 `_RELEASE_PATH_IDS_RE` 從 URL path 抽出的 `(release_id, company_id)`，加上 `source_id` 集合（含 legacy `prtimes_{rid}`）。`normalize_url` 不用，因為 `/rd/amp/` 等變體會對不上（PM2）。
   - **亂抓**：prtimes 與 google_news_rss 過去 28 天新增的事件，計數為「x / y」（分類見下）。
   - **只靠複合詞的事件**：`created_at >= PHASE_A_MERGED_AT`（Phase B 的 PR 填入 #724 的合併時間），在 Python 端用 `taiwan_keywords.compound_only()` 篩選，累計下架數。
2. `coverage-probe`：`needs: coverage-db`，不帶 secrets，權限 `contents: read` 與 `issues: write`。
   - checkout 用 `sparse-checkout: scraper` 與 `persist-credentials: false`，只安裝 `requests` 與 `beautifulsoup4`（m2）。
   - `GH_TOKEN` 只放在最後的留言 step。這個 token 就算被濫用，貼 label 的 sender 也是 Bot，碰不到 url-intake 的寫入路徑。
   - 由 DB 產生的 artifact 屬於受信任資料，不需要另外驗證。

**探測（prtimes）**

- 探測詞：`日台`、`日中台`、`台日`，加上 `台湾` 對照組，各 2 頁。
- **判斷一律走公開的 verdict 函式**（PM1）：
  - 標題用 `title_verdict`。
  - Phase B 的 PR 新增 `body_verdict(title, body_text) -> (ok, reason)`，內部做 venue 抽取與 `_should_skip_taiwan_venue`；`scrape()` 改成呼叫它。
  - 探測可以 import I/O helper 與常數（`_fetch_detail`、`_parse_released_at`、`_API_URL`、`_HEADERS`、`LOOKBACK_DAYS`），但不自己寫判斷。
- 排除發布不到 48 小時的項目，以及超過 `LOOKBACK_DAYS` 的項目。
- 只對「標題通過、不在已知鍵、時間窗內」的項目抓正文，最多 20 筆。抓不到正文的列為「未判定」。
- 每個探測詞都列出實際涵蓋的 `released_at` 範圍（m7），四週後的數字才能比較。

**報表分類**

- 漏抓：
  - 已收錄。
  - 被標題過濾，依原因分組。`taiwan_based` 只報數字，不列清單。
  - 被正文過濾，只報數字。
  - **漏抓候選**：標題與正文都通過、DB 沒有。列出清單，附一鍵連結。
  - 未判定。
- 亂抓（x / y）：
  - 計入：`out_of_scope:` 前綴、`admin confirmed irrelevant`、`auto-deactivated: annotator Taiwan relevance gate`。最後這一項寫成字面值，並用測試斷言它等於 `annotator.RELEVANCE_GATE_REASON`（m4）。
  - 待人工歸因：`manually deactivated by admin`。
  - 不計入：合併類、`pre_migration_044_legacy`、空白標題、孤兒子活動、`admin reported wrong …`。
  - 未分類：只印 distinct 值與計數，每個截到 80 字。

**輸出**

- 先寫 run summary，再處理 issue（m5）。
- 滾動 issue「覆蓋稽核週報」：
  - 由 agent 在合併前手動建好。label `coverage-audit` 只貼在這一張上（不要和 `spec:coverage-audit` 混用）。
  - 用 `gh issue list --label coverage-audit --state open --json number` 搜尋。找到 0 張或超過 1 張就讓 job 失敗。
  - 每週留一則摘要。
- 外部內容的處理：
  - 標題：摺疊換行，用 `ingest_url._URL_IN_TEXT` 移除其中的 URL，套用 `escape_md`，顯示時截到 120 字。
  - URL：限定 host 為 `prtimes.jp`，不經 `escape_md`。
  - 一鍵連結：`issues/new?title=…&labels=url-intake&body=<URL>`，`title=` 截到 60 字，參數用 `urllib.parse.quote` 編碼。
    - 帶 `labels=url-intake` 只會觸發 preview，不會寫 DB（m8，採用）。它的好處是使用者少貼一次 label，而且只有 triage 以上權限的人建立時這個 label 才會生效。
    - 核准仍然要使用者自己貼 `url-intake:approved`。
  - 整則留言超過 60000 字元時截斷，並附上 run 的連結（m6）。
- 失敗通知：把 `Scraper Quality Report` 加進 `workflow-failure-notify.yml` 的監看清單，這只要改一行（PM4）。

**驗證**（PM4）

- 核心邏輯放在 `scraper/coverage_audit.py`，寫成純函式，用 fixture（API 回應、已知鍵、正文文字）測試，由 `Scraper Tests` 執行。`scraper-quality.yml` 的 `unit-tests` 有 `-k` 過濾，不會跑到這些測試，PR 裡要寫明。
- 「只寫 run summary、不留言」：以 workflow_dispatch 的 `no_post` 輸入實作（留言 step 在 workflow 裡，`GH_TOKEN` 只放在那一步，所以開關放在 workflow 而不是 `coverage_audit.py`）。
- 不在 feature branch 上 dispatch，因為會連既有的 report 一起跑，還會讓 branch 的程式拿到 production secrets。合併後由 agent 對 main dispatch 一次，作為 M5。這只讀 production，不是人類關卡。

**門檻**：前四週只出報告。四週後決定警示門檻、探測詞、google 探測，以及是否保留 `日台 イベント` 搜尋詞（#724 的 dry-run 顯示它帶回 0 筆）。結論寫進 `notes.md`。

**成本**：無 LLM 呼叫，不解碼轉址。每週的請求是 prtimes 4 個詞 × 2 頁，加上最多 20 次正文抓取。

## 風險

| 風險 | 處理 |
| --- | --- |
| 複合詞誤收（舞台日本、本日台数等） | A2 帶前後文限制，A4 列入 8 個負例；Phase B 追蹤只靠複合詞收進來的事件下架數 |
| 「日台」標題常是在台灣舉辦的日本企業活動 | 標題層只擋得住 `in 台北`。主要靠正文場地過濾與 annotator 兩層擋。已知缺口以 xfail 記錄 |
| 探測與 scraper 的判斷分歧 | 共用 `title_verdict` 與 `body_verdict`；scraper 自己也呼叫它們 |
| 持有 DB 金鑰的 job 解析外部內容 | job 順序是 `coverage-db` → `coverage-probe`，外部內容只進不帶 secrets 的 job |
| 「通過但未收錄」假陽性 | 48 小時寬限、LOOKBACK、`body_verdict` 正文判斷、release 鍵比對 |
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

plan-critique-2（同上，只評 Phase B）的處理方式：

| 項目 | 處理 |
| --- | --- |
| PB1 probe 需要 DB 結果 | 採納：job 順序改為 `coverage-db` → `coverage-probe`，外部內容只進不帶 secrets 的 job；刪除 artifact 驗證 |
| PM1 正文判斷仍在 scrape() 內 | 採納：新增 `body_verdict`；寫明「判斷走公開函式，I/O helper 可以 import」 |
| PM2 normalize_url 比對不足 | 採納：prtimes 改用 `(release_id, company_id)` 與 `source_id` |
| PM3 google 探測延後 | 採納：google 只做 DB 端計數 |
| PM4 驗證與失敗通知 | 採納：純函式加 fixture 測試、`--no-post`、合併後對 main dispatch、加進 workflow-failure-notify |
| m1～m7 | 採納 |
| m8 一鍵連結帶 `labels=url-intake` | 採納，理由寫在 B 段 |

依 plan-critique-2 的結論，修訂只有縮小與改順序，不需要第三輪評審。plan-critic 自述的教訓（建議切分信任邊界前，先畫出資料相依方向）已寫入 `.github/skills/agents/plan-critic/history.md`。

## 參考

- #701、#702
- `plan-critique-1.md`、`plan-critique-2.md`
- `docs/specs/active/url-intake/`
- `docs/specs/active/evaluation-framework/`
- `.github/workflows/scraper-quality.yml`
