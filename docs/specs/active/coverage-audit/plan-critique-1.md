# Plan Critic 批評：coverage-audit（proposal.md）

> 本次批評與 Architect 使用同一模型家族（Claude）。我是 fallback 的 Claude plan-critic，不是 Codex，所以這份不算第二家族的視角。
> 依據：worktree `/home/claude/tokyo_taiwan_radar/ttr-coverage-audit-worktree` 的程式碼、#701／#702 的 issue 內文，以及兩項唯讀實測：用 python 跑 regex 樣本、用 `gh api user` 確認身分。prtimes API 被 proxy 擋下，沒能實測。

## 結論先講

**不可以照原計畫進入實作。** Phase A 與 Phase B 各有一個 blocker，修訂後才能交 Engineer。Phase C 方向正確，但規則覆蓋面不足，而且優先順序應該提到最前面。

---

## Blocker

### B1. Phase A 照 proposal 寫的子字串正則會誤收大量常見日文（已實測）

- 證據：proposal.md L51 寫 `_TAIWAN_KW = 台湾|Taiwan|台灣|臺灣|日中台|日台|台日`。我用這條正則配上現行 `_EVENT_KW`（prtimes.py L83-89）與 `_TAIWAN_BASED_TITLE_RE`（L117-133）跑樣本，下列標題全部「通過三層標題過濾」：
  - 「ミュージカル舞台日本公演 開催決定」（舞**台日**本）
  - 「本日台数限定セール開催」、「1日台数限定 体験イベント」（本**日台**数）
  - 「今日台風接近によりイベント開催中止」（今**日台**風）
  - 「屋台日本一決定戦 開催」（屋**台日**本）
  - 「毎日台所から 料理教室イベント」（毎**日台**所）
  - 「日中台風の影響でフェス中止」（**日中台**風）
- proposal L67 的負例只有「中台禅寺」，完全沒涵蓋這一類。google_news_rss 的 `_is_taiwan()`（L160-161）是 list 子字串比對，又沒有活動詞過濾，誤收會更嚴重：每筆都以 `category=["report"]` 入庫，交給 annotator 的 LLM 處理，增加成本。
- 修正（必須）：
  1. 改成帶前後文限制的正則。例：`日中台(?![風頭])|(?<![今本毎昨明前翌当連終平休祝曜土0-9０-９])日台(?![数風所帳車本詞])|(?<![舞屋灯高演])台日(?!本)`。確切寫法由 Engineer 定，但上面六個樣本必須列為負例測試。
  2. google_news_rss 的 `TAIWAN_KEYWORDS` 不能再用子字串 list 加詞，改成共用同一條 compiled regex。
  3. 負例清單擴充到至少這六個樣本加「中台禅寺」，正例保留 proposal L66 的三個。

### B2. Phase B 的「通過但未收錄」照現在的定義，會被假陽性淹沒

proposal L80 說這一類「是最該看的」，但有四個結構性原因會讓它充滿雜訊：

1. **google_news_rss 沒有活動詞過濾。** scrape() 只做 `_is_taiwan`、Yahoo、stale 三項檢查（L272-289）。對照組探測詞「台湾」（proposal L76）回傳的 RSS（約 100 筆）幾乎都是政治、半導體新聞，全部會「通過」，DB 卻都沒有，每週報出約 100 筆假漏抓。「台北／高雄／金曲／故宮」這幾個詞，標題沒有「台湾」就被判「被過濾」。要判斷是不是漏抓候選，得套 prtimes 的 `_EVENT_KW`，這已經是探測自己的邏輯，和 proposal L135「探測沒有自己的過濾邏輯」矛盾。
2. **prtimes 的過濾鏈是寫在 scrape() 裡的 inline 程式碼，不是可 import 的函式。** 順序是 placeholder → `_TAIWAN_KW` → `_EVENT_KW` → `_TAIWAN_BASED_TITLE_RE`（L420-433）→ LOOKBACK cutoff（L436-443）→ 抓正文 → `_should_skip_taiwan_venue`（L455-460）。探測只 import 三個 regex 的話：
   - 標題通過但正文在台灣舉辦的稿子，會被報成「通過但未收錄」。現況亂抓的大宗正是這類，scraper 擋下的應該更多。
   - 90 天以外的舊稿也會出現。
   - scraper 之後若在 inline 加新過濾，探測不會跟著改，靜默分歧。proposal L135 的風險處理因此不成立。
3. **排程在每日 scraper 之前。** proposal L72 排在週日 08:31 JST，但 scraper.yml 是每天 `0 0 * * *`（09:00 JST），所以前一次 scraper 跑完後約 24 小時內發的稿子，一定會被報成漏抓。L72 寫「在 scraper-quality 之前」，但沒有說明兩者有什麼相依。
4. **DB 比對規則不足。** prtimes 的 source_id 有三種格式（`_build_source_id` L295-315，含 legacy `prtimes_{rid}`），只比 source_id 會漏配。同一篇稿子可能經由 google_news_rss 或 url_intake 已經收錄（source_id 是 `url_<sha1>`，見 ingest_url.py L117）。下架、合併的列也算「已收錄」。
- 修正（必須）：
  - Phase A 先把標題判斷抽成公開的純函式，例如 `prtimes.title_verdict(title) -> (ok, reason)`，並讓 `scrape()` 自己也呼叫它。google_news_rss 同樣處理。探測只呼叫這兩個函式，不 import 私有 regex。
  - prtimes 標題通過的項目，探測要抓正文、套 `_should_skip_taiwan_venue`（設上限，例如 20 筆），並套 `LOOKBACK_DAYS`。抓不到正文的列為「未判定」，不算漏抓。
  - google_news_rss 的「通過但未收錄」只對複合詞探測詞計算，並且要求標題含活動詞。「台湾」對照組只報總數，不列清單。
  - 排程移到每日 scraper 之後（例如週日 13:31 JST），或排除發佈不到 48 小時的項目。
  - 「已收錄」判定：不分 `is_active`、跨所有 source_name，以 `normalize_url`（ingest_url.py L73）正規化後的 source_url 比對，source_id 只當輔助。

---

## Major

### M1. 優先順序：Phase C 應該最先做；Phase A 修不到 #701 本身那篇稿子

- #702 的風險現在就存在。我在本 session 執行 `gh api user` 得到 `TuiTuiKoan User`：Claude Code 的 gh 正是以擁有者 User 身分運作，而 url-intake.yml L54-56、L103-106 只檢查 `sender.login == repository_owner && sender.type == 'User'`。proposal L34 把 C 列為「可以並行」，應改成「C 先做」。
- #701 本文寫得很清楚：「這篇稿子沒有發到 PR TIMES」，來源是 kyodonewsprwire。Phase A 的 prtimes 改動是預防同類標題，不會補到這次的漏抓。google_news_rss 新增的查詢 `"日台 交流 イベント"`（proposal L61）也不含「日中台」。proposal 的 Why（L15-18）應該如實寫明 A 的預期效益：未實證、預防性質；實際的缺口由 researcher 評估 kyodo_prwire 補上。

### M2. `_TAIWAN_BASED_TITLE_RE` 只認「台湾」，對「日台」標題的保護被高估（已實測）

- `_TAIWAN_BASED_TITLE_RE` 除了 `in 台北／IN 高雄` 之外，各分支都以字面「台湾」開頭（L117-133）。實測「日台ビジネス交流会を台北で開催」「日台企業マッチング商談会、台北にて開催」都**不會**被擋下。proposal L67 選的負例「日台ビジネス交流会 in 台北」剛好命中 `in 台北` 分支，給了錯誤的安心感。
- 另外 `_JAPAN_VISITOR_KW` 含「日台交流ツアー」（L159-168），會讓正文的台灣場地過濾直接放行。
- proposal L133 的風險處理「兩層擋」應改成「標題層只擋 `in 台北` 形式，主要靠正文場地過濾與 annotator 這兩層」。
- 修正：把「…を台北で開催」列為已知缺口測試（`xfail` 加 issue 連結），不要用剛好通過的樣本。

### M3. google_news_rss 新增的查詢會引進政治外交新聞

- 「日台 交流」在新聞語境下大多是外交、議員往來的報導。google_news_rss 沒有活動詞過濾，又每筆入庫給 annotator（L337-347），每週會多出不少 LLM 標註。現況亂抓已經有約 20 筆（proposal L91）。
- 修正：二選一。(a) 本 Phase 只加關鍵字、不加查詢詞；(b) 改成活動導向的查詢，例如含「写真展」「展覧会」。不論選哪一個，PR 都要以 pr-dryrun-evidence 的 dry-run 數字（只靠複合詞通過的筆數）當證據。

### M4. 探測成本與 Google News 轉址

- proposal L111 估「9 詞 × 2 來源 × 2 頁 ≈ 40 個請求」，漏算三件事：
  - Google News RSS 沒有分頁，一個詞就是一個請求。
  - Google News 轉址解碼：`_decode_gnews_url` 每次後面固定 sleep 1 秒（L302-303），9 個詞 × 約 100 筆就是約 15 分鐘，還有被限速的風險。
  - B2 要求的 prtimes 正文抓取。
- Google News 的「一鍵開 url-intake」若帶的是 news.google.com 轉址 URL，url-intake 抓到的是 Google 的中介頁，不是原文。
- 修正：比對時先用 `gnews_`+md5 加上標準化標題，不解碼；只對報表列出的 ≤20 筆候選解碼，解碼失敗的不附一鍵連結。

### M5. 外部內容寫進 issue：escape_md 不適用於 URL；一鍵連結有 URL 搶位問題

- `escape_md`（ingest_url.py L376-382）會跳脫 `- _ ( ) [ ]` 等字元，直接套在 URL 上會把連結弄壞。它也不處理換行。
- url-intake 的 `extract_url` 取的是 issue body 裡**第一個**合法 URL（L107-114）。外部標題若含 URL（惡意或意外都有可能），而預填 body 把標題放在 URL 前面，url-intake 會抓到標題裡的那個 URL。
- 一鍵連結本身不會觸發 url-intake：repo 沒有 `.github/ISSUE_TEMPLATE`，不帶 `labels=` 參數也就沒有 labeled 事件。報表 job 用 GITHUB_TOKEN 貼 label，也不會觸發其他 workflow。這兩點可以在 proposal 寫明。
- 修正：
  - URL 先用 `normalize_url` 驗證並限定 host，然後百分比編碼，不用 escape_md。
  - 標題要摺疊換行、移除其中的 URL，再套 escape_md。
  - 預填 body 的固定格式是「第一行目標 URL，標題放在之後」。
  - 預填參數一律用 `urllib.parse.quote` 編碼。

### M6. 亂抓率的 deactivated_reason 分類不精確，樣本量也太小

- `manually deactivated by admin` 是後台通用的啟用切換（web/lib/adminEventMutationsCore.ts L419-421），停用原因不限於「不相關」。
- `admin reported wrong category; awaiting re-annotation` 與 `admin reported wrong details (…)`（reportActionsCore.ts L223、L265）是暫時停用，必須排除。
- `deleted_by_admin`（admin-events.ts L355）、`closed_by_owner`、`source_retired_*`（migration 097）在計畫裡沒有歸類。
- `report_or_article:`、`news_article:` 在現行程式碼裡找不到寫入點。應該是 DB 裡的歷史值，要先以 DB 實際的 distinct 值確認。
- 樣本量：prtimes 全期間 291 筆。28 天的新增大約只有數十筆，只靠複合詞的子集合只有 0 到數筆。proposal L102 的「下架率 > 30%」門檻在這種 n 下沒有統計意義。
- 修正：
  - 計入清單只保留 `out_of_scope:`、`admin confirmed irrelevant`、`RELEVANCE_GATE_REASON`（annotator.py L2442）。
  - `manually deactivated by admin` 另列「待人工歸因」。
  - 其餘值放進一個「未分類」桶並印出原字串。
  - 報表用「x / y」計數，不用百分比；複合詞子集合從 Phase A 合併日起累計。

### M7. Phase C 的規則覆蓋面不足

架構上可以做：`Decision("ask", rule)`、`ASK_REASONS`、`combine` 都已存在（_policy.py L31-42、L138-170），新增 `url-intake-approval` 的 ask 原因即可。缺口在比對範圍：

1. **MCP guard 完全不看參數。** `mcp_decision` 把 `tool_input` 丟成 `_data`（L254-261），要擴充。工具名稱會隨 github-mcp-server 版本改變（`issue_write`、`update_issue`、`create_issue`），claude.ai 帳號層的 GitHub 連接器前綴也不是 `mcp__github__`，matcher 抓不到。修正：對所有 `mcp__github__*` 遞迴掃描 `tool_input` 的字串值，不列舉工具名稱；連接器前綴列為殘餘風險。
2. **比對形式。** `--add-label a,url-intake:approved`、`--add-label=…`、`gh issue create -l …` 可重複、一次編輯多個 issue、大小寫不同、前後空白。GitHub label 名稱不分大小寫，Actions 的 `==` 也不分大小寫，所以比對要先做 casefold 加 strip。
3. **變數值。** `_dynamic_args` 只擋命令替換（L591-594），`--add-label "$L"` 會被放行。label、workflow 參數含變數時要 ask。
4. **`gh api` 路徑。** 除了 `issues/N/labels`，還有：
   - `issues/N` 的 PATCH 帶 `labels[]`
   - `POST issues` 建立時帶 labels
   - 這些端點的 `--input`：內容看不到，一律 ask
   - GraphQL 的 `addLabelsToLabelable`、`createIssue`、`updateIssue`：用的是不透明的 label ID，看不到名稱，這幾個 mutation 一律 ask
5. **dispatch。** workflow 可以用名稱「URL Intake」或數字 ID 指定，inputs 也可以從 stdin 以 `--json` 傳入，`dispatches` 端點的 workflow 段也可以是數字 ID。修正：凡是 url-intake 的 dispatch 一律 ask，不只 `apply=true`；workflow 參數無法判斷時也 ask。
6. **重跑繞道（計畫漏掉）。** `gh run rerun <id>`，或 `POST actions/runs/N/rerun`、`rerun-failed-jobs`，會沿用原始的 `event.sender` 重新算出 MODE（url-intake.yml L102-108）。之前失敗的 apply 執行一重跑就會寫入。hook 無法得知 run ID 屬於哪個 workflow。修正：在 url-intake.yml 的 MODE 加上 `github.run_attempt == 1` 條件，代價很低，而且 Codex、Copilot 同樣受到保護。要重試就讓使用者重新貼 label。
7. `pending_deployments` 只在 production environment 設了 required reviewers 時才有意義。目前有 35 個 workflow 用 `environment: production` 跑排程，實際上應該沒有設。保留沒有壞處，但不要當成主要防線。

### M8. 過度設計：Phase B 應該再縮小

- 月報整合（proposal L98）：monthly_health_check.yml 只有 `contents: write`（L21-22），沒有 `actions: read`，讀取 artifact 要再擴權限。刪除；四週後真的需要，再直接用 SQL 算。
- url_intake 依網域彙總（proposal L82）和 url-intake spec 的 M5 兩週盤點（docs/specs/active/url-intake/tasks.md L9）重複。刪除，留在 M5。
- 探測詞：prtimes 留複合詞三個加「台湾」對照組。城市名、金曲、故宮改成四週後再評估。google_news_rss 只探測複合詞。
- workflow：建議不新增 `coverage-audit.yml`，改在 `scraper-quality.yml` 加兩個 job，`coverage-probe` 不帶 secrets，`coverage-report` 用 production 並開 `issues: write`。兩者都加 `if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'`，避開該檔的 push／pull_request 觸發（L13-26），權限在 job 層宣告。這樣使用者只看一個地方、一個 cron。如果改用這種結構，排程就跟著 scraper-quality 走（週日 09:00 JST，和每日 scraper 同時），B2 的 48 小時寬限就是必要條件。
- 滾動 issue：保留，這是不熟軟體的使用者唯一看得到的地方。但要改成「agent 合併前先手動建好一張，report job 以 label 搜尋；找到 0 張或超過 1 張就 job 失敗」，不自動建立。

---

## Minor

- m1. 信任邊界：report job 用的是 service role key，「唯讀」只是程式慣例。`workflow_dispatch` 可以選任意分支，該分支的 workflow 會拿到 production secrets。這是全 repo 35 個 workflow 共有的問題，不是本計畫造成的，但應另開 issue，請使用者評估把 production environment 限制在 main 分支（repo 設定屬人類關卡）。report job 也要像 `ingest_url.validate_payload` 那樣，對 artifact 做 schema、筆數與長度檢查。
- m2. 交付方式：AGENTS.md 的人類關卡表對「權限與防線」寫的是「做成 patch 交使用者套用」，proposal L127 寫的是「PR 由使用者審核與合併」。兩者擇一，並在 proposal 寫明。
- m3. 測試：
  - scraper/tests 目前沒有 google_news_rss 的測試，要新建一個檔。模組 import googlenewsdecoder 失敗時有 fallback（L37-43），CI 可以跑。
  - 現有的 `test_prtimes_filters.py`（136 行）完全沒有測 `_TAIWAN_KW`。新測試應該透過 B2 抽出的 `title_verdict` 測整條鏈。
  - 擴充 `_TAIWAN_KW` 不會改變過濾順序，也不影響 `_TAIWAN_BASED_TITLE_RE`：四層各自獨立、依序判斷，既有測試會照常通過。
- m4. 其他關鍵字表：`daily_report._TAIWAN_KW`（daily_report.py L44）會少算只靠複合詞的事件。`wuext_waseda.py` L44 已經用子字串 `日台`、`台日`，有 B1 同一類誤收風險。不在本 spec 範圍，開一張 issue 記錄即可。
- m5. prtimes 新增搜尋詞「日台交流」（proposal L54）會帶回大量在台灣舉辦的商務交流稿，正文抓取次數會增加。dry-run 證據要列出「新增詞帶來的正文抓取數」。「日中台」只靠其他搜尋詞帶出來，前提是 prtimes API 做全文搜尋，這點未驗證，要寫成待 dry-run 確認。
- m6. 漏抓候選（proposal L81）應排除拒絕原因為「台灣當地舉辦」的項目，或分開列出；否則候選會被刻意排除的稿子佔滿。
- m7. proposal L34 說 A 先做是為了「比較現行規則與擴充後規則」，但 L34 後半又說 A 已合併時 B 直接用新規則當基準，比較就不存在了。這個理由應刪除，或讓探測同時帶新舊兩條 regex，任選其一。

---

## 六段評估（精簡）

1. **商業主軸對齊**：🟢 對齊。對應「資料完整性：爬蟲覆蓋率與亂抓」。Phase C 對應「production 寫入」這個人類關卡，同樣對齊。
2. **複雜度與價值**：
   - 原計畫：3 個 PR、6 個以上檔案、1 個新 workflow、1 張滾動 issue、月報整合、guard 擴充 4 類。複雜度 high。
   - 價值：Phase C 高（風險已實證存在）；Phase B medium；Phase A low-medium（未實證）。
   - 依 M8 縮小後的 B 降為 medium，比例可以接受。
3. **優先順序**：🟡。應改為 C → A（含 B2 要求的函式抽取）→ B。
4. **架構整合**：
   - 可以復用 `ingest_url.normalize_url`、`escape_md`（只用於標題）、`validate_payload` 的模式，以及 scraper-quality.yml。
   - B2 的 inline 過濾鏈是會導致重複邏輯的主因。
   - 本計畫不涉及 Category Sync、i18n、SCRAPERS List 這幾個 Guard。
5. **復用率**：🟡 部分新增。月報整合與網域統計是重造輪子，刪除。
6. **建議修訂（diff 點，不重寫）**：
   - L51、L60：改用 B1 的限制式正則，google 改用共用 regex。
   - L66-67：負例改依 B1、M2。
   - L61：依 M3 二選一。
   - L72：依 B2 改排程或加寬限。
   - L76-82：依 B2、M8 縮小，並定義 `title_verdict`。
   - L86-91：依 M6 重新分類，改用計數。
   - L95-98：刪除月報整合。
   - L105-109：補上 M5 的 URL 處理，以及 m1。
   - L113-127：補上 M7 的 1 到 6 項（含 url-intake.yml 的 `run_attempt` 條件）。
   - L34：C 先做。
   - L135、L133 的風險處理依 B2、M2 改寫。

## 是否可以進入實作

**不可以。** 先回 Architect 修訂 B1、B2、M1 到 M8。Phase C 規格補齊 M7 後可以第一個實作。Phase A 修好 B1 後可以實作，同時一併抽出 B2 要的 `title_verdict`。Phase B 依 B2 與 M8 縮小範圍後再評審一次。

---

### 建議下一步
- 回 Architect 修改計畫：請 Architect 根據這份批評（存檔後的 `docs/specs/active/coverage-audit/plan-critique-N.md`）修訂 `docs/specs/active/coverage-audit/proposal.md`，並回傳修訂後全文。
- Engineer：目前不建議交付，等修訂通過後再交。

### 給主 session 的備註（是否要寫進記憶由主 session 決定）
- 本 session 實測：Claude Code（web）的 `gh` 以擁有者 `TuiTuiKoan`（type User）身分運作。GraphQL 與 `environments` API 被 proxy 擋下。來源是本次執行的 `gh api user` 與錯誤訊息，可以當 #702 的佐證。
- 我是唯讀角色，沒有寫入任何檔案。
