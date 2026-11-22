# Plan Critic 批評：coverage-audit Phase B（proposal.md v2）— plan-critique-2

> 這份批評和 Architect 用的是同一個模型家族（Claude），由 fallback 的 Claude plan-critic 執行，不是 Codex，所以不算取得第二家族的視角。
> 依據：
> - 計畫：`ttr-coverage-audit-worktree/docs/specs/active/coverage-audit/proposal.md` v2
> - Phase A 程式碼：`ttr-coverage-keywords-worktree`（branch `feat/compound-taiwan-keywords`，HEAD `aa2206f`）
> - 唯讀查詢：用 `gh api` 確認 repo 是 **public**，label `coverage-audit` 已存在（說明是 "Weekly keyword coverage audit report"），目前有 0 張 issue。
> - 沒有連 DB，事件筆數沿用 plan-critique-1 的數字。
> - plan-critique-1 是我同一家族寫的。這一輪發現的 blocker，有一部分是 critique-1 M8 建議的 job 結構造成的，下面直接修正。

## 結論先講

**Phase B 還不能進入實作。** 有一個 blocker：probe 與 report 的資料相依方向寫反了，照字面做不出來。另有四個 major。修法很單純：job 順序反過來，google_news 探測延後。修完後 Phase B 會比 v2 更小，複雜度大約 medium-low，屆時不需要第三輪評審，Architect 改完就可以交 Engineer。

---

## Blocker

### PB1. probe 拿不到 DB，卻被要求只處理「DB 沒有的項目」

- 證據：
  - proposal L110 寫 `coverage-probe` 不帶 secrets。
  - L118 卻要它對「prtimes 標題通過、**DB 又沒有**的項目（最多 20 筆）」抓正文。
  - L119 要它「只對報表列出的候選（最多 20 筆）解碼」。報表候選是 report job 比對 DB 之後才產生的。
  - L122 的 report job 排在 probe 之後。
  - 結論：probe 不知道哪些已收錄，「最多 20 筆」沒有依據可以挑。
- 後果：Engineer 只能二選一。
  - 把 secrets 給 probe，等於破壞信任邊界。
  - 或在 report job 抓外部正文，讓持有 service role key 的 job 解析外部 HTML，跟 L110 想做的切分正好相反。
  - 不管選哪一個，安全邊界都是 Engineer 臨場決定，計畫沒有定義。
- 修正（必須）：**job 順序反過來，外部內容永遠不進持有 DB 金鑰的 job。**
  1. `coverage-db`：`environment: production`，權限 `contents: read`，只做 select，不碰任何外部內容。輸出 artifact `known.json`，內容是：
     - prtimes 已知鍵集合，見 PM2。
     - 亂抓計數 x/y。
     - 只靠複合詞通過的事件的累計下架數。
  2. `coverage-probe`：`needs: coverage-db`，不帶 secrets，權限 `contents: read` + `issues: write`，`persist-credentials: false`。它負責：
     - 下載 `known.json`。
     - 打 prtimes API。
     - 只對「標題通過、不在 known、超過 48 小時」的項目抓正文，上限 20 筆。
     - 組報表，寫 run summary，最後一步才留言。`GH_TOKEN` 只放在留言那個 step 的 `env`。
- 效益：
  - service role key 不碰外部內容。
  - 處理外部內容的 job 只有限於 issues 的 `GITHUB_TOKEN`。這個 token 就算被濫用，用它貼 `url-intake:approved` 時 sender 是 Bot，而且不觸發 workflow，所以碰不到 url-intake 的寫入路徑（url-intake.yml L54-56、L102-106）。
  - 不再有「不受信任的 artifact 流進特權 job」，L124 的 artifact 驗證可以整段刪掉。`ingest_url.validate_payload`（L233-256）綁死 url-intake 的 `PAYLOAD_KEYS`（L52），本來就不能直接沿用。
  - `known.json` 由 DB 產生，屬於受信任資料。不過 repo 是 public，artifact 登入的 GitHub 使用者都能下載，所以內容只放公開的 URL、ID 與計數，加上 `retention-days: 1`。

---

## Major

### PM1. 「探測沒有自己的過濾邏輯」（L116）仍不成立

- **prtimes**：Phase A 只抽出標題鏈 `title_verdict`（prtimes.py L322-337，scrape() 在 L443 呼叫）。以下兩段還是寫在 scrape() 裡：
  - LOOKBACK 判斷（L449-457）。
  - 正文鏈 `_fetch_detail` → `_extract_venue_from_body` → `_should_skip_taiwan_venue`（L465-474）。
  - L118 寫的「套用 `_should_skip_taiwan_venue`」不夠：這個函式需要 `venue` 參數，venue 要先經 `_extract_venue_from_body` 才拿得到。探測勢必複製這段順序，又回到 critique-1 B2-2 的靜默分歧。
- **google_news_rss**：`taiwan_verdict`（L169-173）只包住 `_is_taiwan`。Yahoo 聚合（L289）與 `_STALE_DAYS=21`（L82、L300）都還寫在 scrape() 裡。L117 只排除超過「prtimes LOOKBACK_DAYS」的項目，對 google 來說是錯的窗口（21 天，不是 90 天），也沒有排除 Yahoo，兩者都會變成假漏抓。
- 修正：
  - Phase B 的 PR 在 prtimes 新增公開函式 `body_verdict(title, body_text) -> (bool, reason)`，內部做 venue 抽取與場地判斷，scrape() 的 L469-474 改成呼叫它。
  - 探測可以 import I/O helper 與常數（`_fetch_detail`、`_parse_released_at`、`_API_URL`、`_HEADERS`、`LOOKBACK_DAYS`），但**判斷**一律走公開的 verdict 函式。計畫要寫明這條規則。
  - google 的部分依 PM3 延後，這一版不需要 `item_verdict`。

### PM2. 「已收錄」用 normalize_url 比對，在兩個來源上都不夠

- **prtimes**：
  - `normalize_url`（ingest_url.py L73-104）會保留 path 與 query，`/rd/p/…html` 和 `/rd/amp/p/…html` 會被當成兩個 URL。
  - DB 的 `source_url` 存的是未正規化的原值（prtimes.py L462 的 `_PR_BASE + release_url_path`），用 eq 查正規化後的值會漏配。
  - DB 裡不合規格的 URL 會讓 `normalize_url` 拋出 `IntakeError`。
  - 修正：prtimes 的比對鍵改成 `_RELEASE_PATH_IDS_RE`（L174）從 `urlsplit(url).path` 抽出的 `(release_id, company_id)`，再加上 `source_id` 集合（含 legacy 的 `prtimes_{rid}`，見 L299-319）。`normalize_url` 只當備援，個別例外要接住。
- **google_news_rss**：
  - DB 的 `source_url` 存的是**解碼後**的原文 URL（L323），`source_id` 才是 gnews 轉址 URL 的 md5（L311）。不解碼就只能比 `source_id`，L125 的「以 URL 為主、source_id 為輔」對 google 剛好相反。
  - 跨來源判斷要解碼後再查一次 DB，可是 probe 沒有 DB（PB1）。
  - L142 的「限定在探測來源的 host」對 google 沒有定義，解碼後可能是任何發布者的網域。
  - 這幾點都是延後 google 探測的理由（PM3）。
- `secondary_source_urls`：merger 會把次要事件停用但不刪除（merger.py L5、L31-33），所以「不分 is_active」已經涵蓋這些列。為了和 `find_existing`（ingest_url.py L280-299）一致，可以再撈一份 `secondary_source_urls is not null` 的列，屬於 minor。

### PM3. google_news_rss 探測應延後；第一版的價值不足以抵它的複雜度

- 理由：
  1. A3 已經決定 google **不加查詢詞**（proposal L95）。探測拿新詞打 RSS，查到的「漏抓」只能回答「要不要加查詢詞」，這個問題 M3 已經以 LLM 成本與政治新聞為由否決，四週內不會有可執行的結論。
  2. google 沒有活動詞過濾。L116 只好讓 google 候選借用 prtimes 的活動詞，這本身就是探測自己的邏輯。
  3. 要讓它正確運作，得補 Yahoo／stale 的 verdict（PM1）、解碼後二次查 DB（PM2），還要裝 `googlenewsdecoder` 與 `selectolax`。沒裝的話 L37-43 的 fallback 會**靜默**把解碼關掉，解碼必定失敗，也就永遠不會附一鍵連結。
  4. 成本：L147 估最多 20 次解碼，每次 sleep 1 秒（L315），還有被限速的風險。
- google 這一版只做 DB 端的亂抓 x/y 與「只靠複合詞」的下架數。這是 Phase A 對 google 唯一真正的改動（`TAIWAN_KEYWORDS_RE = TAIWAN_TITLE_RE`，L79），也是唯一需要量的東西。

### PM4. 合併前沒有驗證路徑；失敗也沒人會發現

- 新 job 只在 schedule 或 dispatch 時跑（L108），PR 上完全不會執行。
- 在 feature branch 上 dispatch 有兩個副作用：
  - 會連同既有的 `report` job 一起跑，因為它的條件是 `if: github.event_name != 'pull_request'`（scraper-quality.yml L55）。
  - 會在真正的滾動 issue 上留言。
  - 另外，在 branch 上 dispatch 等於讓 branch 的程式拿到 production secrets，就是 critique-1 m1 的問題。
- 失敗不可見：`Scraper Quality Report` 不在 workflow-failure-notify.yml 的監看清單（L9-25）。L139 的「0 或超過 1 張就失敗」只會讓 run 變紅，使用者收不到 LINE 通知。
- 修正：
  - 核心邏輯放在 `scraper/coverage_audit.py`，寫成純函式，輸入是 API 回應、`known.json` 與正文文字的 fixture，由 `Scraper Tests` 跑 pytest（scraper-tests.yml 的 paths `scraper/**` 會觸發）。scraper-quality.yml 的 `unit-tests` job 有 `-k` 過濾（L52），不會跑到新測試；這不需要改，但 PR 裡要寫明。
  - `coverage_audit.py` 提供 `--no-post`：只寫 run summary，不留言。
  - 第一次真正執行（M5）由 agent 在合併後對 `main` dispatch。這只讀 production，不是人類關卡。
  - 失敗通知二選一：把 `Scraper Quality Report` 加進 workflow-failure-notify.yml 的清單（改一行，同屬 Tier 2）；或在計畫寫明「失敗只看 run 紅燈，M5／M6 時人工檢查」。不可以不寫。

---

## Minor

- m1. **job 層權限**：job 一宣告 `permissions:`，就會整組覆蓋頂層的 `contents: read`（L28-29），未列的權限一律變成 none。
  - `coverage-probe` 必須明列 `contents: read` 與 `issues: write`；`coverage-db` 明列 `contents: read`。
  - 同一個 run 內 `actions/download-artifact@v4` 不需要 `actions: read`。
  - 兩個新 job 的 `if` 與既有的 `unit-tests`、`report` 互相獨立。既有 job 不加 `needs`，所以不受影響。
  - 唯一的連動是整個 run 的結論：新 job 失敗，整個 run 就標成 failure。
  - artifact 名稱不能和既有的 `scraper-quality`（L86）重複。
- m2. **probe 的安裝**：照 url-intake.yml 的做法。
  - checkout 用 `sparse-checkout: scraper` 加 `persist-credentials: false`（L64-69）。
  - 安裝只裝 `requests|beautifulsoup4`，用 grep 從 requirements 抽出（L74-76）。
  - 這個集合確定夠用：`sources/__init__.py` 是空檔；`base.py` 只 import requests、bs4，urllib3 是在 L54 延遲 import，而且 requests 會帶進來；`prtimes.py` L22-33 只用到 stdlib、requests、bs4 與 `taiwan_keywords`（純 stdlib）；`ingest_url.py` 頂層只有 stdlib（L22-35），requests、bs4、database 都是函式內才 import。
  - 這幾個模組 import 時都不需要 secrets 或 DB。
  - 要在 `working-directory: scraper` 下執行，`from taiwan_keywords import`（prtimes.py L31）才找得到模組。
  - `coverage-db` 照既有 `report` job 安裝完整的 requirements.txt（L68-69，有 cache）。
- m3. **DB 查詢**用固定幾次分頁查詢就能完成，不需要逐筆查。一律用 `db_paging.fetch_all`（L21-29），加 `.order("id")`；不要複製 eval_scraper_quality.py L434 那份自己的 `_fetch_all`。
  1. prtimes 已知集合：`select id,source_name,source_id,source_url,official_url,is_active`，條件是 `.or_("source_url.ilike.*prtimes.jp*,official_url.ilike.*prtimes.jp*,source_name.eq.prtimes")`。不加時間條件：數量在數百筆等級（prtimes 全期 291 筆），而且 120 天窗口反而會漏掉「先由其他來源收錄」的舊列。
  2. 亂抓：`source_name in (prtimes, google_news_rss)` 且 `created_at >= now-28d`，欄位 `id,source_name,raw_title,is_active,deactivated_reason,parent_event_id`。
  3. 只靠複合詞的子集合：同一組欄位，改成 `created_at >= PHASE_A_MERGED_AT`，在 Python 端用 `taiwan_keywords.compound_only()` 篩選，不要另寫 regex。#724 還沒合併，這個日期常數要在 Phase B 的 PR 填入 #724 的 merge commit 日期。
- m4. **deactivated_reason 字串**：
  - `RELEVANCE_GATE_REASON` 寫成字面值，不 import annotator.py。annotator.py L43-44 在 import 時就會載入 playwright 與 supabase。
  - 另加一個測試斷言字面值等於 `annotator.RELEVANCE_GATE_REASON`（L2442）；測試環境本來就 import annotator（tests/test_annotator_relevance_gate.py）。
  - `out_of_scope: non-Japan audience — admin confirmed`（web/lib/reportActionsCore.ts L274）會落在 `out_of_scope:` 前綴裡，計入沒問題。
  - repo 是 public，「未分類」桶印出原字串時只印 distinct 值與計數，每個截到 80 字，因為 run summary 與 issue 都公開。
- m5. **滾動 issue**：設計合理，保留。要補三點：
  - 搜尋用 `gh issue list --label coverage-audit --state open --json number`。不要用 REST 的 `issues?labels=`：它會把 PR 一起算進去，Phase B 的 PR 若誤貼 `coverage-audit` 就會變成 2 張。
  - 判斷 0 或超過 1 張之前，先把報表寫進 run summary，報表才不會因為失敗而遺失。
  - `coverage-audit` 和 `spec:coverage-audit` 名稱很像，計畫應寫明 `coverage-audit` 只能貼在那一張週報 issue 上。
  - 只有 triage 以上權限才能貼 label，所以外人無法用同名 issue 搶位。
- m6. **留言大小**：GitHub issue 留言上限是 65536 字元，`issues/new` 的 URL 實務上限約 8 KB。
  - 日文 percent-encoding 每個字約 9 個字元。20 筆候選，若標題完整編碼進 `title=`、URL 放進 `body=`，每筆約 2 到 3 KB，接近上限。
  - 硬限制：顯示用標題截到 120 字；`title=` 參數截到 60 字；`body=` 只放目標 URL。
  - 整則留言超過 60000 字元時截斷，附上 run summary 的連結（`${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}`）。
  - 移除標題中的 URL 時，直接用 `ingest_url._URL_IN_TEXT`（L57），不要另寫 regex。
- m7. **有效窗口**：prtimes 每個詞只抓 2 頁共 80 筆。「台湾」對照組的 80 筆大約只涵蓋最近數天，扣掉 48 小時之後，有效窗口可能只剩 2 到 4 天。報表每個詞都要列出實際涵蓋的 `released_at` 範圍，否則四週後比較的數字沒有可比性。
- m8. 選擇性的改進：一鍵連結可以帶 `labels=url-intake`（只觸發 preview，不寫 DB，url-intake.yml L52-53），讓使用者少貼一次 label。只有 triage 以上的人帶入的 label 才會生效，外人點了也觸發不了。要不要採用由 Architect 決定，但計畫裡要寫明理由。

---

## 對 plan-critique-1 處理情形的確認

| 項目 | 判定 | 說明 |
| --- | --- | --- |
| B2 探測假陽性 | 部分處理 | 標題鏈已抽出（prtimes.py L322-337，並在 L443 呼叫）。48 小時寬限與 LOOKBACK 已寫入。剩下三個缺口：正文鏈與 google 的 Yahoo／stale 仍在 scrape() 裡（PM1）；跨來源比對方法不足（PM2）；新引入的 PB1 |
| M4 成本與轉址 | 方向正確，但做不出來 | 「只對候選解碼」要先知道 DB 結果（PB1）。解碼後要再比一次 DB，host 限制對 google 沒有定義（PM2）。google 延後後整項消失 |
| M5 跳脫與搶位 | 已處理 | L141-143 正確：URL 不經 escape_md，body 第一行是 URL，不帶 labels。剩 m6 的長度上限 |
| M6 分類與樣本量 | 已處理 | x/y 計數與分類正確。剩 m4 的字面值與公開輸出 |
| M8 過度設計 | 已處理，但留下 blocker | 併入 scraper-quality.yml、刪掉月報與網域彙總都正確。critique-1 建議的「probe 無 secrets → report 有 DB」順序是 PB1 的來源，本輪修正為「db → probe」 |

新引入的問題：PB1、PM2 的 google 部分、PM4。

---

## 六段評估

1. **商業主軸對齊**：🟢 對齊。對應「爬蟲覆蓋率／資料品質」，也是量測 Phase A 效益的唯一手段（proposal L19）。
2. **複雜度與價值**：
   - v2：2 個 job、google 解碼、artifact 驗證、跨來源 URL 比對、2 個來源的探測，複雜度 medium-high。
   - 依本批評縮小後：新檔 1 個（`coverage_audit.py`）、測試 1 個、prtimes 加 1 個公開函式、workflow 加 2 個 job，沒有 migration，沒有 LLM。複雜度降為 medium-low，約 3 個 level。
   - 價值 medium：可以判斷 Phase A 要保留還是回退，也能量出 prtimes 查詢詞的缺口。
   - 縮小後比例合理。
3. **優先順序**：🟢。C → A → B 的順序正確，A（#724）已經推送。B 必須等 #724 合併後才能開始，因為 B 要 import `title_verdict` 與 `compound_only`。
4. **架構整合**：
   - 可以復用的：`taiwan_keywords.compound_only`、`prtimes.title_verdict`、`_RELEASE_PATH_IDS_RE`、`db_paging.fetch_all`、`ingest_url.escape_md`、`_URL_IN_TEXT`，以及 url-intake.yml 的 sparse-checkout 與最小安裝模板。
   - 不應復用 `validate_payload`（只適用 url-intake 的 payload）與 eval_scraper_quality 的 `_fetch_all`（重複實作）。
   - 不涉及 Category Sync、Event Form Sync、i18n、Manual Translation Fix、SCRAPERS List 這幾個 Guard。不新增 scraper，所以 ZERO_EVENT_OK 與 source_id 唯一性的檢查不適用。
5. **復用率**：🟢 充分復用，前提是 PM1 的 `body_verdict` 讓 scrape() 與探測共用同一段判斷。
6. **建議修訂（只標 diff 點，不重寫計畫）**：
   - L108-110、L122：job 改成 `coverage-db`（production、select）→ `coverage-probe`（無 secrets、`issues: write`、`GH_TOKEN` 只在留言 step）。
   - L112-114、L119：刪除 google 探測，google 只保留 DB 端計數。
   - L116、L118：新增 `prtimes.body_verdict`，scrape() 也要呼叫它；寫明「判斷走公開函式，I/O helper 可以 import 私有名稱」。
   - L117：寫明「prtimes 用 LOOKBACK_DAYS」，google 延後後這句不需要再提 google。
   - L124：刪除 artifact 驗證，改寫 `known.json` 的內容與 `retention-days: 1`。
   - L125：prtimes 比對鍵改成 `(release_id, company_id)` 加 `source_id`；寫明 m3 的三次分頁查詢。
   - L136：`PHASE_A_MERGED_AT` 常數與 `compound_only()`。
   - L139：搜尋用 `gh issue list --state open`；先寫 run summary 再判斷；失敗通知依 PM4 二選一。
   - L143：加上 m6 的長度上限。
   - L147：成本改成「prtimes 4 詞 × 2 頁、最多 20 次正文抓取，無解碼」。
   - 新增「驗證」小節：fixture 測試、`--no-post`、合併後在 main dispatch 一次作為 M5。
   - 風險表 L158：「跨來源 URL 比對」改成「release 鍵比對」。

---

## 對六個問題的直接回答

1. **critique-1 各項處理情形**：見上表。M5、M6 已處理；B2、M4 只處理一部分；M8 處理了，但它建議的 job 順序造成新的 blocker PB1。
2. **併入 scraper-quality.yml 是否可行**：可行。
   - 既有 `unit-tests` 只在 PR 跑（L35），`report` 在非 PR 的事件跑（L55），包括 push 到 main（L14-20）。
   - 新 job 用 `schedule || workflow_dispatch` 的條件，不會在 push 或 PR 時執行。
   - job 層權限只影響該 job，但必須明列 `contents: read`（m1）。
   - artifact 在同一個 run 內用 upload-artifact／download-artifact v4 傳遞，不需要 `actions: read`。
   - 已知的連動有兩個：dispatch 會連同既有 report 一起跑（PM4）；新 job 失敗會讓整個 run 標成 failure。
3. **probe 不帶 secrets 時的最小安裝**：`requests` + `beautifulsoup4` 就夠，import 時不需要任何 secrets 或 DB（m2）。google 只有在要解碼時才需要 `googlenewsdecoder` 與 `selectolax`；沒裝會靜默降級，這是延後 google 的理由之一。
4. **DB 查詢設計**：三次 `fetch_all` 分頁查詢（m3），不需要逐筆查。prtimes 不加時間條件，數量在數百筆等級。PostgREST 每次上限 1000 筆，由 `db_paging` 處理。
5. **滾動 issue**：設計合理。需補上排除 PR 與 closed、先寫 summary 再判斷、失敗通知（m5、PM4）。留言 65536 字元的上限，用 m6 的截斷規則就守得住。
6. **最小可行範圍**：見下一節。

## 是否可以進入實作

**還不行。** Architect 依 PB1、PM1 到 PM4 修訂後就可以交 Engineer，不需要 plan-critique-3，因為修訂都是縮小或改順序，沒有新增設計。前提條件：#724（Phase A）已經合併。

**建議的最小範圍（Phase B v3）**：

- 做：
  - `coverage-db`：prtimes 已知鍵集合；prtimes 與 google_news_rss 過去 28 天的亂抓 x/y；只靠複合詞的累計下架數。
  - `coverage-probe`：prtimes 的 `日台`、`日中台`、`台日` 加 `台湾` 對照組，各 2 頁；48 小時寬限與 LOOKBACK；正文用 `body_verdict` 判斷，最多 20 筆；附 prtimes 候選的一鍵 url-intake 連結。
  - run summary、滾動 issue 留言、`--no-post`、fixture 測試。
- 延後到四週盤點（M6）再決定：google_news 探測與解碼、城市名與其他探測詞、`secondary_source_urls` 比對、門檻警示。
- 建議模型：實作用 Sonnet medium，與 proposal L33 相同；Tier 2，因為新增了 `issues: write`。

---

### 建議下一步

- 回 Architect 修改計畫：請 Architect 根據 `docs/specs/active/coverage-audit/plan-critique-2.md` 修訂 proposal.md 的 Phase B（PB1、PM1 到 PM4，加上 minor 的 diff 點），並回傳修訂後全文。
- Engineer：等 #724 合併、proposal 修訂完成後再交付。

### 給主 session 的備註（是否要寫進記憶由主 session 決定）

- 本次唯讀查詢確認：repo `TuiTuiKoan/tokyo_taiwan_radar` 是 public；label `coverage-audit` 已存在，目前 0 張 issue；這個環境呼叫 GraphQL 會被擋（`gh repo view` 回傳 403），REST 可以用。
- 自我修正（給 plan-critic 的 history 參考）：critique-1 M8 建議「probe 無 secrets → report 有 DB」，但沒有檢查 probe 的工作是否依賴 DB 結果。教訓：建議切分信任邊界時，要先畫出 job 之間的資料相依方向。我是唯讀角色，沒有寫入任何檔案；這條教訓需要交 Update History, Skill, Agent 或使用者寫進 `.github/skills/agents/plan-critic/history.md`。
