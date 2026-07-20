# Scraper Expert Error History

<!-- Append new entries at the top -->

---

## 2026-07-20 - Taiwan Expo Japan annual Wix SSR source

### Context

Taiwan Expo Japan publishes one official annual event on a Wix homepage. The server-rendered HTML contains reliable visible headings but only generated container IDs and generic rich-text classes. The same page also contains previous-year material and a detailed daily schedule that could trigger unintended annotator sub-events.

### Implementation

Added a requests-based scraper with retry adapters, strict title-year and complete-date-year agreement, timezone-aware UTC-midnight dates, semantic description boundaries, NUL stripping, and one stable `taiwan_expo_japan_<year>` ID. Focused tests rename every Wix ID, class, and test ID, cover compact and cross-month date variants, and verify fail-closed behavior. The live orchestrator dry-run produced one 2026 event and excluded schedule sessions.

The mandatory audit exposed two older gate defects. Commit `25fc2bbd` had documented `scraper/audit_post_build.py` without ever adding the file, while the remaining inline copy treated abstract bases and intentionally removed `ConnpassScraper` as production omissions. Added an AST-based audit with explicit intentional-disable handling and repaired six `peatix_organizer` rows to use their owning `scraper_source_name=peatix`. Independent DB reads confirmed all six values and row 709 before the combined audit printed `ALL CLEAR`.

### Lesson

Annual Wix pages need semantic text anchors and a year-consistency guard, not generated selectors or current-year inference. A one-event source must bound its description before the program schedule so downstream annotation cannot invent a multi-session event tree.

## 2026-07-11 - publication phase 3: exact pure invariant and mixed negative lock

**問題：** publication 規則在多處被舊 placeholder 語意覆蓋，造成 `books_media`/source 名被誤當 pure，進而影響 QA/admin 判讀。

**修正：** 統一為 exact pure invariant（正規化後 `event_form == ['publication']`），pure 只保留 metadata，七欄保持 intentional null + sentinel；publisher 保持必填；`['publication', 'lecture']` 這類 mixed rows 維持 physical 行為。

**教訓：** publication 判定只能看 `event_form`，不能再用 category/source/title 代判。source skill、agent skill、QA 規則要同批同步，不然會在不同入口出現互斥判定。

## 2026-07-10 — 阪神候補三分店（西宮／御影／尼崎）：同集團分店純 config 一行擴充

**背景：** 阪神本店（`hanshin_umeda`）上線後追加三個兵庫県分店。實測三店 event 頁（`/nishinomiya/event/`、`/mikage/event/`、`/amagasaki/event/`）與阪神本店/阪急 100% 同構（`o-event` selector 齊全、marker 皆 `●`），皆小店（4–16 件）、目前 0 台灣活動；兩層 filter 仍會接住偶發催事，成本極低故順手納入。

**實作：** 純 config 擴充、零解析程式碼改動——`_HANSHIN_STORES` 加 3 筆 `_Store` + 3 個 concrete class（`HanshinNishinomiyaScraper`/`HanshinMikageScraper`/`HanshinAmagasakiScraper`，命名讓 `_scraper_key()` 推出正確 source_name），全部複用 `_HanshinBase`。同步 4 清單（`main.py` SCRAPERS+import+`WEEKLY_SOURCES`、`health_check.py NON_DAILY_SOURCES`+`ZERO_EVENT_OK_SOURCES`、`qa_triage.py NON_DAILY_SOURCES`）+ migration 093 註冊三店（`department_store`/`weekly`, sort_order 904/905/906）。

**教訓：** `display_name` 一定要從頁面 `<title>`/`og:title` 核對，勿信計畫暫定值——實測西宮/御影官方表記是「阪神・にしのみや」「阪神・御影」（中黑點分隔），非暫定的「阪神西宮」「阪神御影」；尼崎「あまがさき阪神」才符合暫定。base（`_HanshinBase`/`_HankyuBase`）既已完全參數化，加同集團分店 = 1 config row + 1 class + 4 清單同步，零 regression。

## 2026-07-10 — 阪神百貨 hanshin：繼承 `_HankyuBase` 複用 H2O CMS（姊妹百貨零重寫）

**背景：** 新增阪神百貨爬蟲。阪神與阪急同屬 H2O Retailing 集團，實測 event 頁（`www.hanshin-dept.jp/hshonten/event/`）與阪急 100% 同構（`article > div.o-event > p.o-event__title` + `p.o-event__desc` + `div.o-event__detail`，日期 marker 同為 `[◎●]`），只有 domain 不同（`hanshin-dept.jp` vs `hankyu-dept.co.jp`）。

**決策：** 不抽 `_h2o_dept.py` base 重構已上線的 `hankyu.py`（工程量大、需重測阪急），改用「繼承 `_HankyuBase` + 只覆寫 `_store`」——`hankyu.py` 的 `_parse_event(div, today, store)` 已完全參數化（`store: _Store` 帶 base_url/display_name/source_name/address/prefectures），唯一模組耦合是 `_store` property 查模組層級 `_STORES`。`hanshin.py` 覆寫 `_store` 指向阪神 registry 即複用全部解析（date parser、two-tier Taiwan filter、`_fetch_taiwan_detail_evidence`、`_build_source_id`），零 regression。

**實作：** 新建 `scraper/sources/hanshin.py`（`_HanshinBase(_HankyuBase)` + `HanshinUmedaScraper`，`source_name=hanshin_umeda`，`_Store.base_url` 吃不同 domain）；同步 4 清單（`main.py WEEKLY_SOURCES`、`health_check.py NON_DAILY_SOURCES`+`ZERO_EVENT_OK_SOURCES`、`qa_triage.py NON_DAILY_SOURCES`）+ SCRAPERS + import；migration 092 註冊 `hanshin_umeda`（`department_store`/`weekly`）；在 `hankyu.py` 的 `_Store`/`_HankyuBase` 加「shared by hanshin.py」註解降低 private-import 耦合（未動任何解析邏輯）。

**教訓：** 同集團姊妹品牌（H2O 的阪急→阪神）常共用同一套 CMS → 先驗證 listing 頁 selector/marker 同構，再用「繼承既有 base + 覆寫最小耦合點（`_store`）」複用，比抽新 base 重構已上線 code 更安全。複用他模組 private symbol（`_HankyuBase`/`_Store`）時，務必在被引用端加 shared 註解，避免日後 refactor 改名靜默壞。

## 2026-07-10 - johakyu UTF-8 mojibake 與 ZERO_EVENT_OK 長尾來源噪音

**問題：** `johakyu` scraper 成功執行但連續多日 0 件，沒有 traceback；`nhk_rss`、`walkerplus`、`bookandbeer`、`internet_museum` 四個長尾來源每天被 `health_check` 誤標為 selector concern。

**根本原因：** `johakyu.co.jp/schedule.html` 的 HTTP `Content-Type` 沒有 charset，HTML 才有 `<meta charset="UTF-8">`。`requests` 對 `text/html` 無 charset 的 `resp.text` fallback 到 `ISO-8859-1`，導致 `月` / `日` / `台湾` mojibake，讓 `_WEEK_RE` 與 `_TAIWAN_KEYWORDS` 全部失效。`ZERO_EVENT_OK_SOURCES` 原規則偏向 cinema/galleries，漏掉 keyword-filtered feed / aggregator / listing 類來源。

**修復：** `scraper/sources/johakyu.py` 將主 schedule page 的 parser 改為 `BeautifulSoup(resp.content, "html.parser")`，讓 BeautifulSoup 依 `<meta charset="UTF-8">` 解碼 bytes；`scraper/health_check.py` 新增 `nhk_rss`、`walkerplus`、`bookandbeer`、`internet_museum` 到 `ZERO_EVENT_OK_SOURCES`；`johakyu` 本次未加入，保留監控。

**驗證：** dry-run 從 0 件恢復，抓到 `ギデンズ・コーの功夫(カンフー)`，`raw_description` 正常含 `開催日時: 2026年7月3日〜2026年7月9日`，未見 mojibake / `�`；`ZERO_EVENT_OK_SOURCES` 以 frozenset 正負向檢查確認新增四來源，且 `johakyu` / `taipei_fukuoka` / `jinf` / `morc_asagaya` 未加入。已 push commits：`1cc92bd`、`abc913e`。

**教訓：** 先修 selector / encoding bug，再決定是否加入 `ZERO_EVENT_OK_SOURCES`；keyword-filtered long-tail sources 在 scraper logic 已驗證後可以加入零事件豁免；跨天等待 push 的修復不可裸留工作區，至少 commit 到 branch 或 safety branch。

## 2026-07-08 — 單店 hankyu_umeda 一般化為多店 hankyu（梅田／博多／神戸）

**問題：** 舊 `hankyu_umeda` 爬蟲只涵蓋阪急梅田本店（`honten`），漏掉博多店與神戸店的台灣相關活動；且博多店「アジアンフェスティバル 台湾特集」的 listing 標題只寫「アジアンフェスティバル」不含「台湾」，被泛亞洲 filter 漏抓。

**根本原因：** ① 來源設計綁死單一分店 subdomain（`honten`），未考慮阪急百貨其他分店（博多／神戸）有同構的活動頁；② 泛亞洲活動（アジア／Asian）的台灣信號常只出現在 detail page（`<meta name="description">` 或 台湾 `<img alt>`），listing 標題／desc 不一定命中，單層 title/desc filter 會漏。

**修復：**
- 新建 `scraper/sources/hankyu.py`，用 `_Store` config 表把單店一般化為多店：concrete class `HankyuUmedaScraper`（梅田本店/大阪）、`HankyuHakataScraper`（博多/福岡）、`HankyuKobeScraper`（神戸/兵庫），source_name = `hankyu_umeda`/`hankyu_hakata`/`hankyu_kobe`；三店共用同一組 selector（`article > div.o-event > p.o-event__title` + `p.o-event__desc` + `div.o-event__detail`）與 URL pattern `https://www.hankyu-dept.co.jp/{store}/event/`。刪除舊 `hankyu_umeda.py`。
- 日期 marker 一般化：梅田用 `◎`、博多／神戸用 `●` → regex 改用 `_MARK = r"[◎●]"`，並支援 `前半|後半` 前綴。
- 兩層 Taiwan filter：L1 標題／desc 直接命中；L2 泛亞洲活動（`_ASIA_RE`）無直接命中時，`_fetch_taiwan_detail_evidence()` 抓 detail page 的 `<meta name="description">` + 台湾 `<img alt>`，把證據 append 到 `raw_description`（meta 優先、alt 去重、~2500 字上限）讓 annotator 看到台湾特集脈絡；抓取失敗回 `(False, "")` 保守跳過。這解決博多アジアンフェスティバル漏抓。
- migration 091 註冊 `hankyu_hakata`／`hankyu_kobe`（`department_store`/`weekly`）並修 `hankyu_umeda` frequency=weekly；三店同步登錄 `main.py WEEKLY_SOURCES`、`health_check.py NON_DAILY_SOURCES`+`ZERO_EVENT_OK_SOURCES`、`qa_triage.py NON_DAILY_SOURCES`。

**教訓：** 連鎖百貨（阪急／大丸松坂屋等）的各分店通常有**獨立 subdomain／路徑但同構的頁面**；新增或重構這類來源時，先確認是否有姊妹分店可用同一 selector 一併涵蓋，用 config 表（一列一店）取代複製爬蟲。泛亞洲／跨區活動的台灣信號可能只藏在 detail page metadata，要用「listing 直接命中 + detail 證據補抓」兩層 filter，並把證據寫回 `raw_description` 供 annotator 判讀，而非在 scraper 端硬判 in/out scope。

---

## 2026-07-04 — PR TIMES 第三個 Japan-brand-held-in-Taiwan 先例（漏洞 C／event 4e558c1c）

**問題：** `prtimes` 事件 `4e558c1c-c796-42a6-968c-7caf08175d26`（日本高級日本酒品牌 HENGE／株式会社Cypher）在**台北・台中・高雄**辦「進出記念ディナーイベント」，「初の海外輸出先として台湾を選定」，對象為台灣的日本酒愛好家／餐飲業者／buyer（Japan→Taiwan 商業拓展、輸出／進出），卻被收為 active event（annotator 已把 `location_address='台北'` 卻仍 active）。此為 2026-06-29 Rental819（`22eae44b`）、2026-07-04 b90f0b77（ハミガキドッグ）之後**第三個 Japan-brand-held-in-Taiwan 先例**。已於本次手動停用（`deactivated_reason` 記 out_of_scope、raw_* 保留）並補 root-cause title guard。

**根本原因（漏洞 C，兩層 guard 皆漏過）：**

- **C-title（title 句式未涵蓋）：** `_TAIWAN_BASED_TITLE_RE` 既有四分支皆不匹配「台湾3都市で…開催」——分支 1 要「台湾国内/現地/本島/の地」（「3都市」不符）、分支 4（b90f0b77 新增）要「台湾にて/において」（本 PR 用「で」）、分支 3 要「台湾」緊接「進出/輸出」（本 PR 是「初の海外輸出先として台湾」「海外進出」，前面不是「台湾」）。
- **C-body（body 無 venue label）：** body **完全沒有** `開催地：`/`会場：`/`場所：` 等 `_VENUE_LABELS`；台灣信號（台北・台中・高雄、台湾進出）全散在敘述文 → `_extract_venue_from_body` 回 None、`_TAIWAN_HELD_BODY_RE`（需 label+：+台湾）也不命中 → body guard 完全失效。

**修復（title guard-only，治本 + 治標）：**

- 2a — `_TAIWAN_BASED_TITLE_RE` 新增第 5 分支「台湾 + 地點量詞（`[\d０-９]+都市`/`各地`/`主要都市`/`複数都市`/`全土`…）+ `で`/`にて` + 活動動詞」。negative lookahead 同時排除兩類誤殺：(1) Japan-pivot（`日本上陸/各地/初/進出`，如「台湾で人気→日本上陸」）；(2) Japan-venue（`東京/大阪…で・にて`，如「台湾3都市で人気の…を東京で開催」= 東京主辦）。**不排「日本酒」**（「日本」後接「酒」不在 lookahead 清單，目標 title 中段含「日本酒」仍正常命中）。
- 精準 `source_exclusions` 規則：`raw_title` regex `台湾[\d０-９]+都市で`（即時雙保險，下次 scrape 立即生效，範圍刻意窄於 code guard——只攔 numeric N都市で）。
- 手動停用 event `4e558c1c`。

**決定不動 body guard 的理由：** 目標事件用 title guard（在 detail fetch 前先跑）即可攔截，body guard 不會執行到。對「body 無 label 的敘述文」做廣泛台灣信號偵測風險高（易誤殺「東京で台湾フェア、台北の名店が出店」型），且**無其他樣本**支持 → 違反「不為單一事件過度抽象」。同理不加「海外進出／海外輸出」廣義 title signal（台灣企業進軍日本的「海外進出」可能 in scope，誤殺風險高）。

**教訓：** Japan→Taiwan 商業拓展（輸出／進出／販路開拓）在台灣舉辦、面向台灣受眾的 PR 為 out of scope，即使 title 同時含「台湾」與「開催」。title guard 除「台湾国内/現地」「台湾にて/において」外，還要涵蓋「台湾 + 地點量詞（N都市/各地/主要都市…）+ で/にて…開催」寫法；並用 Japan-venue negative lookahead 鎖住「台灣N都市有人氣、實際在日本開催」的誤殺。沿用 Rental819／b90f0b77 的 title guard + `source_exclusions` 雙保險做法。

---

## 2026-07-04 — PR TIMES 第二個 Japan-brand-held-in-Taiwan 先例（event b90f0b77）

**問題：** `prtimes` 事件 `b90f0b77-3d1a-4864-bc5d-1282f488faf7`（大阪的日本寵物口腔護理品牌 ハミガキドッグ）2026/7/3 在**台灣**辦「台湾にて海外初となる…合宿講座」，對象是台灣美容沙龍／寵物店／動物醫院業者（Japan→Taiwan 商業／教育拓展），卻被收為 active event。此為 2026-06-29 Rental819（`22eae44b`）之後**第二個 Japan-brand-held-in-Taiwan 先例**。admin 已於 2026-07-03 手動停用（`deactivated_reason='admin confirmed irrelevant'`、raw_* 保留），本次補 root-cause guard。

**根本原因 A（title guard 太窄）：** `_TAIWAN_BASED_TITLE_RE` 第一分支硬性要求「台湾」後緊跟 `国内|現地|本島|の地`。本 PR 用「台湾**にて**…開催」（無修飾詞）→ 漏過。

**根本原因 B（body venue guard 缺國名）：** `_TAIWAN_VENUE_RE` 只列城市名（台北／台中…）+ 英文 Taiwan，**缺日文國名「台湾」**。本 PR body 寫「開催地：台湾」（只寫國名），`_is_taiwan_venue_context` 檢查不含「台湾」→ False → 漏過。

**修復：**

- 2a — `_TAIWAN_BASED_TITLE_RE` 新增分支 `台湾(?:にて|において)(?:(?!日本).){0,40}?(?:開催|実施|開講|スタート)`，中間負向排除「日本」避免「台湾にて人気→日本上陸」型誤殺。
- 2b — 新增 `_TAIWAN_HELD_BODY_RE`（body-level held-in-Taiwan guard，命中「開催地：台湾」國名寫法，terminator 含全形／半形括號涵蓋「開催地：台湾（新北市）」），整合進 `_should_skip_taiwan_venue`；抽 `_VENUE_LABEL_ALT` 讓 `_VENUE_LABELS` 與新 guard 共用同一 label 集合（杜絕漂移）。
- 精準 `source_exclusions` 規則：`raw_title` substring `台湾にて海外初`（即時雙保險，下次 scrape 立即生效，不必等 CI 部署）。

**教訓：** Taiwan-held PR 只有在**明確面向日本人**（日本人向け／日本から参加／ファムトリップ／日台交流ツアー 等）才收；日本品牌把課程／商品拓展到台灣、面向台灣業者或消費者的 PR，即使標題同時含「台湾」與「開催」仍 out of scope。title guard 要涵蓋「台湾にて／において…開催」無修飾詞寫法，body guard 要涵蓋只寫國名「台湾」的 venue label。沿用 Rental819 的 scraper guard + `source_exclusions` 雙保險做法。

---

## 2026-06-29 — Peatix detail text blocks for location and business_hours

**問題：** Peatix detail pages can expose the authoritative venue and time range only in rendered text blocks such as `LOCATION` / `場所` and `DATE AND TIME` / `日時`. CSS selectors alone can miss Japanese pages, online-event markers, and body-level time labels, leaving `location_name`, `location_address`, or `business_hours` empty.

**根本原因：** The scraper treated English DOM selectors as the primary source and did not model Peatix's text-block structure as a first-class contract. Address fallback could then run without knowing whether the event was already confirmed online, and vague labels such as `Japan`, `東京都`, or ward-only fragments could be written as if they were precise addresses.

**修復：** Promote text-block extraction into explicit helpers: `_extract_peatix_location_from_text(page_text)` handles English and Japanese venue blocks, detects online events before any physical fallback, and rejects generic or vague address candidates; `_extract_peatix_business_hours(page_text, date_text)` reads English/Japanese date blocks, body labels, and CSS fallback date text. Add focused extractor tests for the text cases.

**教訓：** For Peatix, detail-page text blocks are the owning abstraction for venue and time. Parse `LOCATION` / `場所` and `DATE AND TIME` / `日時` before CSS fallback, treat online detection as a terminal state, and reject generic address labels instead of letting annotator preserve bad scraper values. This uses existing missing-location / missing-hours QA categories and does not require a new R-class.

---

## 2026-06-29 — auto_scraper `generate.py` `run_batch` 永久跳過 `llm-error`（30 天 0 產出，commit `e194fda`）

**問題：** Layer B auto_scraper Phase 2 codegen cron 連續 30 天 `0 success`，但 GitHub Actions run 全部 `conclusion=success`、無報錯。

**根本原因：** `generate.py` `run_batch()`（L861）的批次查詢 `.or_(...)` 只取 `auto_scraper_status` 為 `null` 或 `sandbox-failed` 的來源，**漏掉 `llm-error`**。2026-06-03~06 CI OpenAI 金鑰 401 期間有 13 個來源被標 `llm-error`；金鑰 06-25 恢復後，這些來源因查詢排除而永遠不再進入批次 → 暫時故障變永久。這是 2026-05-04 `auto_research.py` 漏 `pending` DEFAULT 值（commit `5d2585d`）的同型復發。

**修復（commit `e194fda`）：** 在 `run_batch()` 查詢補上 `,auto_scraper_status.eq.llm-error`，使金鑰恢復後 `llm-error` 來源可重試；同步清理 4 筆不可行來源（324/325/355/359 → not-viable）。Tester 驗證：舊查詢撈 0 筆、新查詢撈 7 筆。

**教訓：**
1. **診斷 0 產出先別信 `conclusion=success`**：`generate.py` 會吞 401、標 `llm-error` 後正常退出，CI 仍顯示成功。要直接驗 OpenAI 金鑰，用單來源 dry-run（`gh workflow run auto-generate.yml -f source_id=<id> -f dry_run=true`，走 `run()` 繞過批次查詢）。
2. **批次查詢必須涵蓋所有「暫時失敗/未處理」狀態**：`llm-error`、`sandbox-failed`、`null`、DEFAULT 值都要列入 OR 條件，否則暫時故障會被永久排除。
3. **同型 bug 會跨 pipeline 復發**：auto_research 的 `pending` 漏網教訓沒擴及 generate.py，導致同一錯誤重演。修一處批次查詢時，檢查所有同類查詢（auto_research + generate）是否一致。

---

## 2026-06-29 — PR TIMES Rental819 Taiwan trade-show PR exclusion

**問題：** `prtimes` 事件 `22eae44b-65c5-4140-a485-e694fe89858d` 是日本租車企業在台北商展面向台灣騎士的訪日促銷 PR，卻被收為 active event。

**根本原因：** `_extract_venue_from_body()` 先把 `会場：南港展覽館 二館（台湾・台北市）` 的括號內容剝掉，Taiwan venue guard 只看到 `南港展覽館 二館`，因此漏過 `台湾・台北市` 訊號。

**修正：**
- 新增 raw venue-context guard，在清洗 display venue 前檢查會場 label 的完整內容。
- 新增精準 `source_exclusions` 規則：`raw_description` substring `訪日台湾ライダー`。
- 將既有 out-of-scope event 停用並保留原始欄位供稽核。

**教訓：** Taiwan venue checks must inspect raw labeled venue context, not only cleaned display venue. Taiwan-held PRs targeting Taiwanese inbound consumers are not Rule 4 unless they explicitly target Japanese participants/audience.

---

## 2026-06-07 — Hybrid venue (Physical + Online) marking rule

**問題：** 音樂/表演活動（如 `380c0ab2-1713-4bc9-86c5-6101d8ec741a`）同時有現場與線上時，常被誤標為純線上。

**修復：**
1. **兩個都標**：確立 `location_name` 必須並列（如 `D-Bop / オンライン`）。
2. **保留地址**：必須保留實體地址與都道府縣，不可因線上選項而抹除。
3. **加鎖**：此類複合型場地務必鎖定 `field_corrections`。
4. **系統提示**：已更新 `annotator.py` 的 `SYSTEM_PROMPT` 以自動處理此邏輯。

**教訓：** 複合型活動的地址對於區域過濾至關重要，不要讓線上屬性完全覆蓋實體屬性。記得現場名稱與線上都要標。

---

## 2026-06-04 — `location_url` 誤寫成主辦/活動頁：venue homepage provenance guard 補強

**問題：** 多筆事件的 `location_url` 被誤寫成 `source_url` / `official_url` / `organizer_url`，導致前端把主辦單位頁或活動頁誤顯示成場地網頁。

**根本原因：** `location_url` 的來源定義在 scraper、annotator、admin/auto-fix 三處沒有完全一致：上游把「找到一個 URL」誤當「找到場地官方頁」，而下游又缺少對 event/organizer URL 的 collision 驗證。

**修正：** 在 QA auto-fix 新增 `auto_qa_location_url_is_event_url`，只允許經驗證的 venue homepage 回填；找不到明確場地首頁時保留 pending，不再默認升級成 event/organizer URL。

**教訓：** `location_url` 不能被當成「任意可用網站」欄位。只要來源不是場地自己的官方首頁，就應保留 null 或待人工確認，否則後台會反覆把主辦單位頁當成場地頁。

---

## 2026-06-04 — 出版相關 pending QA 批次清理：來源級 one-off 收斂與 eslite_spectrum 保守分流

**問題：** 出版相關來源（`ndl_opensearch`、`hanmoto`、`kawade_rss`、`eslite_spectrum`）累積大量 pending `event_reports`，後台數字無法靠既有安全 auto-fix 自然下降。

**根本原因：** 這批 backlog 的性質不是單一 selector drift，而是出版型語意與一般場館型 QA 的不一致；其中 `eslite_spectrum` 還混有宣傳講座、展覽與新書刊行訊號，不能用一刀切規則處理。

**修正：** 新增單用途 one-off 批次腳本，僅處理出版來源 pending 報告，透過既有 `confirmed` / `dismissed` 狀態流收斂；`eslite_spectrum` 只處理明顯出版語境事件，宣傳講座與展覽保留人工判斷。最後 pending 由 373 降至 153，出版範圍歸零。

**教訓：** 出版型 backlog 要以「來源級、單次、可追溯」方式清理，不應抽象成新的通用 QA 引擎；混合型來源（尤其 `eslite_spectrum`）必須保守分流，不能把宣傳講座與新書刊行事件硬綁成同一批次規則。

---

## 2026-06-03 — 灣生藝術家個展時間與背景優化 (Wansei Artist Background & Date Correction)

**問題：** 事件 `f8100bd2-e95d-4047-b98e-ad41da2c3f1d`（多田美波個展）展期錯誤（標註為單日）、選案理由說明不足，且未提及藝術家關鍵的「灣生」身分與台日淵源。

**根本原因：**
- 官網 `2026年8月29日（土）～12月6日（日）` 的範圍被 `mot` scraper 誤判為單日。
- Annotator 生成的選案理由僅為通用的「促進藝術交流」，缺乏針對性。

**修正：**
- DB 手動更新 `end_date` 至 `2026-12-06`。
- 重寫三語 `description` 與 `selection_reason`：明確標註多田美波出生於「台灣高雄」的灣生背景，並加入 `taiwan_japan` 分類。
- 使用 `field_corrections` 對上述欄位上鎖。

**教訓：**
- **「灣生」背景是極高的台灣相關性訊號**。Scraper Expert 與 Researcher 在遇到日本藝術家/文化人時，應主動確認其出生地及與台灣的生命軌跡連結。
- 選案理由應具體化：應說明「為什麼這個日本活動與台灣有關」（例如：灣生背景、台日合作、台灣主題作品、在台長期活動經歷），而非使用「促進友好」等空泛辭令。

## 2026-06-03 — 預設收費政策 & 時間空白回退規則實作 (Cinema Default Pricing & Empty Business Hours Fallback)

**問題：**
- Midland Cinema Nagoya Airport 等電影院來源，由於動態架構原因其時間及收費資訊無法直接靜態爬取，在入庫時因資訊留空會造成前端顯示 `"—"`。
- Amayaza 等電影院也存在部分票價或營業時間落空的現象。

**修正與對策：**
1. **空白時間超連結回退 (Empty Business Hours Fallback)**：
   在前端 [web/app/[locale]/events/[id]/page.tsx](web/app/[locale]/events/[id]/page.tsx) 進行時間顯示修補。若活動 `business_hours` 為空且 `official_url` 或 `source_url` 存在，會渲染超連結且各語言顯示為 `「請參照原始來源」`（ja: `"公式情報を参照してください"`, en: `"Please refer to the original source"`），引導使用者前往原始排程頁面。
2. **電影院類的預設有料 (Cinema Default Pricing Fallback)**：
   在 `scraper/annotator.py` 的 AI annotation 流程中自動寫入。若為電影院類別（包含「影展」、分類為 `movie`、或來源在 `cinema` 等電影院清單內），且排除免費上映為常態的「台灣文化中心」後：
   - 當 `is_paid` 為空時，自動設為 `is_paid = True`（有料）。
   - 當 `is_paid` 為 `True` 但價格說明欄位為空時，自動補上 `"有料"`，避免前台破圖。
3. **場館基本資料種入 (Ground Truth seeding)**：
   將「ミッドランドシネマ 名古屋空港」基本資料及首頁與 business_hours 註冊至 `scraper/_oneoff_seed_authoritative_venues.py` 中並進行庫內資料種入，確保關聯對齊。

**教訓：**
- 企業網站架構經常將核心排程與價目表拆分到獨立外鏈，靜態爬蟲宜使用 "showtime window" 來標誌起迄，再由前端配合 hyperlinked fallbacks 與全域 default 進行優雅降級，可降低對動態爬蟲的依維度與頻寬損耗。

---

## 2026-06-02 — google_news_rss（TVGuide 配信記事）頻道/價格/演員欄位漏填，前端資訊不完整

**問題：** 事件 `c768b418`（source: `google_news_rss`）原文明確包含「BS11+」「見放題・単品レンタル配信」「演じたのは、ウー・ピンチェン / ホアン・リーフォン」，但 DB 的 `location_name` / `business_hours` / `is_paid` / `price_info` / `performers` 皆為空，前端只顯示泛標題與最小資訊。

**根本原因：** `google_news_rss` 為二手聚合來源，`raw_description` 為長段落新聞文本。annotator 對「配信平台 + 料金 + 出演者」的結構化抽取在此類文本上並不穩定，導致事件欄位落空。

**修正：**
- DB 直接回填：
  - `location_name = BS11+`
  - `business_hours = 2026年5月25日から配信中`（單行）
  - `is_paid = true`
  - `price_info = 見放題・単品レンタル配信`
  - `event_form = ["broadcast"]`
  - `performers = ["ウー・ピンチェン", "ホアン・リーフォン"]`
- 對上述欄位建立 `field_corrections` lock，防止後續 annotation 覆蓋。

**教訓：**
- `google_news_rss` 的影視配信新聞屬於薄結構文本來源。若原文有平台/價格/演員而欄位為空，需以「手動回填 + FC lock」作為標準修復流程。
- `business_hours` 在配信型事件應保持單行可讀（例如 `YYYY年M月D日から配信中`），避免把長段原文直接塞入造成 UI 雜訊。
- `field_corrections.corrected_by` 在此環境常為 UUID 欄位；手動 upsert 若填入任意字串會觸發 `22P02`。不確定型別時先只寫 `event_id/field_name/corrected_value`。

## 2026-06-02 — gguide_tv 劇情文案「報告」觸發 report 誤判，標題被加上【レポート】

**問題：** 事件 `808da4b5`（source: `gguide_tv`）前端顯示 `【レポート】台湾ドラマ...`。`raw_title` 原始值沒有 `レポート`，但 `name_ja` 被 annotator 加上接頭辭。

**根本原因：** `annotator.py` 的 generic `_REPORT_TRIGGER_RE` 包含關鍵字 `報告`。該事件 `raw_description` 劇情摘要含有「交際の報告を済ませた」，被誤判為活動報導，導致自動注入 `category: report`，並由 `_inject_report_prefix()` 加上 `【レポート】`。

**修正：** 在 agent / skill 規則新增 `gguide_tv` 防護：`gguide_tv` 不可僅因 `報告` 一詞觸發 `report`。此來源的 `report` 必須以 TV genre/context（`報道`、`ドキュメンタリー`）判定。

**教訓：** generic report keyword 規則不可直接套用到 TV 劇情來源。若來源文本是節目摘要，`報告`、`記録` 等字詞需先判斷語境，避免把劇情敘述當成活動報導。

---

## 2026-06-02 — waseda_taiwan 漏抓主催/講師導致前端主辦資訊區塊不顯示

**問題：**
- 事件 `19aecffd-0c07-4b72-9617-d83667c89664`（source: `waseda_taiwan`）在前端看不到主辦單位與主講人資訊。
- DB 實際狀態為 `organizer=null`、`performer/performers=null`，前端區塊採「欄位有值才顯示」策略，因此整段不渲染。
- 對應 QA 訊號為 `auto_qa_missing_organizer`、`auto_qa_missing_performers`（目前歸類到 `R-UNCLASSIFIED` 路由）。

**根本原因：**
- `scraper/sources/waseda_taiwan.py` 只抽 `講演者`，未覆蓋來源頁常見標籤變體 `講師`。
- 同時未抽取 `主催`，也未把主辦/講師資訊寫入 `raw_description` 提供 annotator 使用。

**修正：**
- 擴充講者 fallback：`講演者` → `講師` → `登壇者` → `司会` → `報告者`。
- 新增 `主催` / `共催` 抽取，並追加到 `raw_description`（`主催:`、`共催:`、`講師:`）。
- 針對目標事件補寫 `raw_description` 並重跑單筆 annotate，最終回填 `organizer=早稲田大学台湾研究所`、`performer=石原忠浩`。

**教訓：**
- WordPress 活動頁的欄位標籤不可只靠單一 key。任何「人名/主辦」欄位都必須使用 label fallback。
- 對 annotator 依賴的 scraper，結構化欄位（日期、會場、主催、講師）要顯式寫入 `raw_description`，不可僅依賴正文語意推斷。

---

## 2026-06-01 — TCC sub-event: タイムゾーンバグ / location_name_zh 機械翻訳 / google_news_rss 誤配監督名 / 11b4e1d2 work_id 未紐付け

**問題：** 4 件の問題が同時発生:
1. **タイムゾーンバグ**: 台湾映画上映会2026（親 `51f7cd44`）の全 14 件の子イベントで JST 時刻が UTC として保存されていた（例: `12:00 JST` → `12:00 UTC` 誤、正: `03:00 UTC`）。TCC スクレイパーの `_parse_date()` は naive datetime を返し、caller 側に UTC 変換なし。
2. **location_name_zh 機械翻訳**: ユーロライブ → `'歐洲直播'`（「欧州ライブ放送」の直訳）。5 件に影響（fb0468b3, efc14238, 9c36f36d, 2f50b8fd, 401bc0fa）。固有名詞の会場名は翻訳せず日本語をそのまま保持すべき。
3. **google_news_rss 誤配監督名**: `fb0468b3`（余燼）の raw_description に同日別作品（うなぎ）の google_news_rss 補足が誤配され、チュウ・ジュンタン（うなぎ監督）が余燼の監督として annotator に登録された。余燼の正しい監督は **鍾孟宏（チョン・モンホン）**。
4. **11b4e1d2（湯德章）work_id 未紐付け**: `work_id=None`、name_ja 空、name_zh/en が GPT ハルシネーション値、director が一人のみ（連名 2 名中 1 名欠落）、director_zh が誤文字（`黃敏貞` → 正: `黃明川`）。works テーブルに正しい `dc8f1d36`（title_zh='尋找湯德章', director='黃明川、連楨惠'）が存在していたが未紐付け。

**根本原因：**
- TCC スクレイパーの datetime naive 問題は scraper コードに残存（修正は別タスク）。
- annotator の `location_name_zh` 生成が固有名詞（劇場名）を一般名詞として翻訳してしまう。
- merger.py の google_news_rss 補足マッチが同日開催の別作品記事と同じイベントに誤配される。
- amayaza の 湯德章 は works テーブルにレコードが存在したにもかかわらず、annotator が自力で work_id を解決できなかった（手動 FC 紐付けが必要なケース）。

**修正：**
- 全 14 件 sub-event: `start_date/end_date` を DB 直接 -9h 補正
- 5 件の `location_name_zh='歐洲直播'` → `'ユーロライブ'`
- `fb0468b3`: director/director_zh/director_en + name_en を FC lock 修正、works.director='鍾孟宏'・title_en='The Embers' 更新、annotation_status=pending
- `11b4e1d2`: work_id・name_ja/zh/en・director 全 3 フィールドを FC lock + DB 更新、annotation_status=pending

**教訓：**
- TCC sub-event に時刻が含まれる場合、scraper コードを修正するまで毎回再発する。次スクレイプ前にコード修正が必要（SKILL.md に注記追加）。
- 会場固有名詞（ユーロライブ等）の `location_name_zh` が機械翻訳されていたら FC lock で元の日本語名に戻す。
- google_news_rss 補足が追加されたイベントの director/performer は出所を必ず確認すること（同日別作品の記事が混入し得る）。
- works テーブルに正しいレコードが存在しても annotator が work_id を紐付けられない場合は手動で FC lock + `annotation_status=pending` を設定する。

---

## 2026-05-31 — 手動マージ後 primary event: annotation_status=error + FC locked 誤値 + 片名翻訳未適用

**問題：** XiXi (`dd792b98`) と 赤い糸 (`e4516272`) の手動マージ後、両 primary event で 3 点の問題が同時発生:
1. `annotation_status=error`（annotator が過去に失敗したまま）→ `enrich_movie_titles()` がスキップ → 片名翻訳未適用
2. `name_ja` に `【ＮＰＯ松本シネマセレクト】` suffix が残留（annotator が error 状態のため未処理）
3. `e4516272` の `name_zh` が FC locked で `'電影《赤い糸 輪廻のひみつ》...'`（日本語タイトル）のまま、`works.title_zh='月老'` が未反映

**根本原因：** `annotation_status=error` のイベントは `annotate_pending_events()` も `enrich_movie_titles()` もスキップする。手動マージで primary を指定しても、その primary が error 状態であれば enrichment パイプラインは動かない。

**修正：**
- 両 primary の `name_ja` から `【ＮＰＯ松本シネマセレクト】` を除去 + FC lock
- `dd792b98` `name_en`：`works.title_en='XiXi, Let Me Dance'` を使った正式イベント名に更新 + FC lock
- `e4516272` `name_zh`：FC lock を `upsert on_conflict` で `'電影《月老》松本電影選擇放映會'` に上書き
- `e4516272` `name_en`：`works.title_en='Till We Meet Again'` を使った正式名 + FC lock
- 両 primary の `annotation_status` を `error` → `pending` にリセット（次回 CI で他フィールドを補完）

**教訓：**
- 手動マージ後は primary の `annotation_status` を必ず確認。`error` ならば name_ja/zh/en を手動修正 + FC lock + `pending` リセットが必要。
- FC locked フィールドに誤値が格納されていた場合は `field_corrections.upsert(on_conflict='event_id,field_name')` で上書き可能（DELETE 不要）。
- 映画 primary の `name_zh` が日本語タイトルのままになっていたら `works.title_zh` を確認して FC 値を更新する。

---

## 2026-05-31 — gguide_tv false positive "仙台湾 (Sendai Bay)" bypassed `_is_taiwan_title` filter

- **Incident**: G-Guide TV 抓到「宮城・仙台湾」電視節目，因標題含「台湾」子字串，誤入庫為台灣活動。`_is_taiwan_title` 過濾函式雖已定義，但在 `scrape()` 主迴圈中從未被呼叫，導致靜默漏洞。
- **Fix**: 在 `GguideTvScraper.scrape()` 清理標題後，立即呼叫 `if not _is_taiwan_title(title_clean): continue`。
- **Lesson**: Utility 過濾函式若未在業務主流程中呼叫，等於沉默代碼（dead code）。新增任何過濾函式時，必須同步確認有對應的調用點，否則過濾規則永遠不會生效。

---

## 2026-05-31 — merger._normalize(): 末尾 【主催者名】 アノテーション strip の順序バグ（commit `e53c106`）

**問題：** `matsumoto_cinema_select` が全タイトルに `【ＮＰＯ松本シネマセレクト】` を末尾付加するため、`iwafu` 同一イベントとの merger Pass 1 類似度が **0.764** に低下、閾値 0.85 を下回り自動マージ失敗。2 ペアが重複として表示された（XiXi dd792b98/e910d7f2・赤い糸 ff15eb1d/e4516272）。

**根本原因：** `_normalize()` の wrapping bracket strip `re.sub(r"[」』》\"')）\]】]+$", ...)` が末尾の `】` を先に消費。その後に `【[^】]*】\s*$` パターンを適用してもマッチ対象が消えているため、`【ＮＰＯ松本シネマセレクト` が残留したまま類似度が低下。

**修正（commit `e53c106`）：** `re.sub(r"【[^】]*】\s*$", "", name)` を wrapping bracket strip の**前**に実行する順序に変更。4 ケーススポットチェック全 PASS（bracket-annotation 1.000 新規追加）。

**データ修正：**
- Pair-A (dd792b98/e910d7f2): iwafu を deactivate、matsumoto を primary に。`work_id=651ae313`（XiXi，請讓我跳舞）・`location_prefectures=['長野県']`・`name_zh='電影《XiXi，請讓我跳舞》松本電影選擇放映會'` を FC ロック付きで設定。iwafu の `organizer='ワールドリカーインポーターズ株式会社'`（ハルシネーション）は deactivate で無効化。
- Pair-B (ff15eb1d/e4516272): 前セッションで手動マージ済み・work_id=fd225042（赤い糸）設定済み。

**教訓：**
- `_normalize()` で strip パターンを追加する際は**実行順序が重要**。末尾 `】` を消費するパターンが先に走ると `【...】` 全体マッチが永遠に失敗する。
- `_normalize()` 変更後は必ず 4 ケーススポットチェックを実行（year-suffix / dash+quote / false-positive / bracket-annotation）。
- `matsumoto_cinema_select` は全タイトルに `【ＮＰＯ松本シネマセレクト】` を末尾付加。他の teket.jp グループ来源も同パターンの可能性がある。

---

## 2026-05-31 — `a4442567` `business_hours` 二次訂正：推測値を公式サイト確認値に上書き

**問題：** 同日（前エントリ）で `business_hours` を `"11:00〜22:30"` に FC 修正したが、これは公式確認なしの推測値だった。ルミネエスト新宿公式サイト（`lumine.ne.jp/est/`）を取得すると、実際は **ショッピング: 平日 11:00〜21:00 / 土日祝 10:30〜21:00**（22:30 は存在しない）。

**根本原因：** Venue の `business_hours` を手動 FC 修正する際に公式 venue サイトを確認せず、一般的なショッピングモール像から推測で値を設定した。

**修正：** `business_hours` → `"平日 11:00〜21:00 / 土日祝 10:30〜21:00"`（公式サイト確認値）＋ FC lock 上書き（`field_corrections` upsert）

**教訓：**
- **Venue `business_hours` の手動 FC 修正は必ず公式 venue サイトを確認してから設定**。推測・常識での設定は誤りの原因。
- ルミネエスト新宿の正確な営業時間（2026-05）: ショッピング 平日 11:00〜21:00 / 土日祝 10:30〜21:00、レストラン 11:00〜22:00。

---

## 2026-05-31 — iwafu `a4442567` (QUEEN SHOP): `organizer_zh/en` に英語ブランド名が AI 翻訳マーカー付きで格納、`organizer_url`・`business_hours` null

**問題：** `a4442567`（QUEEN SHOP ルミネエスト新宿初登場）の `organizer_zh = 'QUEEN SHOP（AI翻譯）'`、`organizer_en = 'QUEEN SHOP (AI translated)'`が格納。QUEEN SHOP は英語固定商標名で翻訳不要。また `organizer_url`（QUEEN SHOP 公式サイト）・`business_hours`（ルミネエスト新宿の営業時間）が共に null。

**根本原因：**
1. annotator GPT が英語ブランド名を繁体中文に翻訳しようとして `（AI翻譯）` マーカー付きで格納。`performer_zh` と同様の問題だが `organizer_zh` は自動検出対象外。
2. iwafu scraper は `organizer_url` をソースページから抽出しない設計。外部ブランドの公式サイトは enrichment パイプラインがなければ null。
3. `venues` テーブルに `business_hours` カラムなし（ショッピングモール・でぱートの定常営業時間は venue-level データだが DB に格納先がない）。

**修正：**
- `organizer_zh/en` → `"QUEEN SHOP"`（AI マーカー除去、英語固定商標なので翻訳不要）
- `organizer_url` → `https://www.queenshop.com.tw/`（QUEEN SHOP 台湾公式）
- `business_hours` → `"11:00〜22:30"`（※この値は推測誤り。同日の二次訂正で `"平日 11:00〜21:00 / 土日祝 10:30〜21:00"` に上書き）
- FC lock: 4 フィールド全て

**教訓：**
- **英語固定商標周の `organizer_zh/en`**: `organizer` 値が英語ブランド名の場合、`organizer_zh/en` は翻訳不要—同じ値を FC lock。null や AI 翻訳値にするのは誤り（performer_zh/en と同じルール）。
- **`organizer_url` enrichment ギャップ**: iwafu ・ peatix 等のブランド B2C イベントは `organizer_url` が空になりやすい。`raw_description` 内の `extract_first_party_url()` や外部検索で補充すること。事後に発見した場合は手動 FC 修正。
- **小売 / ショッピングモールイベントの `business_hours`**: ルミネ・マルイ・高島屋等の定常営業時間はイベント固有ではなく venue-level データ。`venues` テーブルに `business_hours` カラムがないため現状は手動 FC 修正。将来的には migration で追加して `enrich_location.py` から返す設計。

---

## 2026-05-31 — note_creators.py: 三層根因修復（truncation guard endswith 漏判 / embedded official_url 未萃取 / 投稿者 location 套到外部活動）

**問題：** `147c5dde` 「🌏 2026年夏 台湾華語サマーキャンプのご紹介」（source=note_creators）DB raw_description = 42 字截斷、official_url=None、location=大阪弁天町（投稿者教室，非開催地台北）。

**根本原因（3 層）：**
1. `_parse_item()` L~378 truncation guard `plain_desc.strip() in ("続きをみる","")` 只比對完全等於。實際 RSS preview 為 `'...ご案内です。 続きをみる'`（endswith）→ guard False → `_fetch_article_content` 永不呼叫 → 只拿到 42 字 RSS preview。
2. 全文含「🔗 詳細・申込み https://clec.ntue.edu.tw/...」但無 embedded official_url 萃取邏輯。
3. 投稿者 `tcml_osaka` CREATOR_META 的 `location_name="台湾華語文学習センター（大阪弁天町）"` 直接套用到「代為宣傳的他機構活動」，且 `database.py._auto_lock_location` 會自動 FC 鎖定此錯誤地點。

**SSL 發現：** `clec.ntue.edu.tw` 用 `verify=True` 失敗（Missing Subject Key Identifier，台灣 .edu.tw/.gov.tw 常見），`verify=False` 成功（755 字，含兩梯次日程/早鳥費用/報名連結）。

**修復：**
- A1: `_is_truncated(text)` = `text.endswith("続きをみる") or len(text) < 120`；改 guard 為 `if _is_truncated(plain_desc) and link:` → 取較長者。
- A2: `base.py.extract_first_party_url(body, exclude_hosts)` 共用 helper，regex 優先 🔗/詳細/申込 signal 附近 URL，排除 note.com + signup platforms。
- A2b: `official_url` 為外部機構域時 → `effective_location_name=None`，`_auto_lock_location` 因 `if not event.location_name: continue` 跳過上鎖。
- A3: `base.py.fetch_ref_text(url, verify_ssl=True)` 新增 `verify_ssl` 參數；`tw_insecure_domain(url)` helper 偵測 .edu.tw/.gov.tw → `verify_ssl=False`。fail-safe：ref < 200 字 → fallback 回 note 全文，永不阻斷活動建立。
- Phase B: FC 先鎖 7 結構欄位（category/event_form/official_url/organizer/location_*）→ 寫入 enriched raw_description → annotator 自動生成三語。

**教訓：**
- **二手聚合源 truncation guard 必須用 `endswith`**，not `== "続きをみる"`。RSS preview 幾乎都有 prose prefix。
- **投稿者 metadata location 不得直接套用到他機構主辦活動**。當 official_url 指向外部機構域時，須清空 location 讓 annotator 或 FC 修復。
- **台灣 .edu.tw/.gov.tw SSL 白名單**：`verify=False` 僅限此域，唯讀公開資訊，不可全域停用。
- **annotator LOCATION GATE 不停用主事件**：`update_data` 完全不含 `is_active`，LOCATION GATE 僅影響 `selection_reason`。

---

## 2026-05-31 — iwafu aggregator 重複：merger.py の dedup ロジックがアグリゲーター来源に未対応（commit `c407a71`）

**問題：** `iwafu` アグリゲーター来源から取得したイベントが `merger.py` で重複候補として複数生成され、誤った merge ペアが作られていた。

**根本原因：** `merger.py` の重複検出は title/date 近似マッチで候補を生成するが、iwafu は同一イベントを複数エントリで返すアグリゲーター来源のため、**来源内部の重複**（同一来源の複数エントリ）と**来源横断の重複**（異なる来源の同一イベント）を区別できなかった。

**修正（commit `c407a71`）：** `merger.py` に iwafu 来源向け前処理（+192 lines）を追加。同一 `source_name` + `source_id` prefix の複数エントリを merge 候補生成前にまとめる。

**教訓：** アグリゲーター来源（同一イベントを複数エントリで返す来源）を merger に追加する際は、merge 候補生成前に来源内 dedup ステップを設ける。新規アグリゲーター追加時は `merger.py` の前処理リストへの登録を確認すること。

---

## 2026-05-31 — kokuchpro 薄文本：GPT が泛稱「語学スクール」を organizer に誤填（手動 DB 修正）

**問題：** `kokuchpro` 来源イベント `fb12bfa7` の `organizer` が泛稱「語学スクール」で、真実の主催者「Asao Language School」が欠落していた。

**根本原因：** `kokuchpro` は薄文本来源（raw_description が短い・構造が少ない）であり、GPT が組織名を特定できず泛稱をそのまま organizer に充てた。`note_creators` と同様、薄文本来源では GPT が「最もそれらしい一般名詞」を捏造しやすい。

**修正：** kokuchpro ページを fetch して真実の主催者名を確認後、DB 直接更新・`field_corrections` ロック。

**教訓：** `kokuchpro` / `note_creators` 等の薄文本来源で `organizer` が「語学スクール」「イベント会社」「主催者」のような泛稱になっている場合は、元ページを fetch して実名を確認してから FC ロックする。

---

## 2026-05-31 — note_creators 泛標題が内文の顕著主題（二二八国家記念館）を欠落（prompt/code 不同步）

**問題：** `note_creators` 来源の事件 `cceca5a2` が、部落格の泛標題「台湾のポスター展」を `name_ja` にそのまま照抄し、内文中で最も顕著な主題「二二八国家記念館」を欠落していた。タイトルだけでは活動の焦点（228 国家紀念館のポスター展）が読者に伝わらなかった。

**根本原因：** `note_creators` は code 側の `_HEADLINE_REWRITE_SOURCES` frozenset に含まれていたが、SYSTEM_PROMPT の NEWS HEADLINE REWRITE RULE「applies only to: ...」来源清单には記載されていなかった。そのため当該ソースは書き換え許可されているのに GPT は書き換え指示を受け取らず、泛標題を silent に照抄した。さらに「泛標題は内文の顕著主題を取り込む」という SALIENT SUBJECT ルール自体が存在しなかった。

**修正：** (A) `annotator.py` SYSTEM_PROMPT の NEWS HEADLINE REWRITE RULE 来源清单に `note_creators` を追加し、新たに SALIENT SUBJECT RULE（泛標題 + 内文の顕著主題 → name_ja に取り込む、228 範例付き）を追加。(B) `scraper-expert/SKILL.md` の Headline Rewrite セクションに SALIENT SUBJECT rule と code↔prompt 同步注意を追記。事件 `cceca5a2` は Architect が DB タイトルを手動修正し FC をロック済み（再 annotation 不要）。

**教訓：** (1) headline-rewrite 来源清单は code（`_HEADLINE_REWRITE_SOURCES`）↔ prompt（SYSTEM_PROMPT「applies only to: ...」）を必ず同步させる。どちらか一方の更新時、もう一方も同じソースを含めること。不同步は silent な泛標題照抄を招く。(2) 泛標題が内文の顕著主題（著名機関名・歴史/人権テーマ・具体的作品名）を欠落している場合は、その主題を取り込むよう name_ja を書き換える。

---

## 2026-05-30 — annotator: `location_prefectures` が `location_address` FC 修正後にサイレント drift → auto-sync 実装（commit `eb94bb9`）

**問題：** 4 件のイベント（`7b37604e`、`9de63ffc`、`10a4ee5d`、`5e5ff363`）が `location_address` を FC 修正されていたが `location_prefectures` は null のまま。フロントエンドの都道府縣チップが表示されなかった。

**根本原因：** `annotate_pending_events()` はアノテーション時に `location_prefectures` を venue_registry lookup かサブイベント集計でしか設定しない設計だった。`field_corrections` で `location_address` を手動パッチしても `location_prefectures` は自動連動しないため、再アノテーションを回しても drift が解消されなかった。

**修正（commit `eb94bb9`）：** `annotate_pending_events()` の末尾に auto-sync ステップを追加。`location_prefectures` が FC ロックされておらず・venue lookup 未設定・`fix_reviewed` 非フラグの場合、`_PREFECTURE_RE` で `location_address` 先頭をマッチし `location_prefectures` を自動付与（単一都道府縣のみ、`オンライン` スキップ）。Architect Guard 文書（`.github/agents/architect.agent.md`）に Sync Guard ルール 5 条と検出 SQL を追記。

**教訓：**
- **`location_address` を手動 FC 修正した後は `location_prefectures` も確認**：auto-sync は次の annotator 実行時まで遅延するため、即時反映が必要な場合は `location_prefectures` も同時に FC 修正する。
- **auto-sync は単一都道府縣のみ**: 複数都道府縣イベントは multi-city de-anchor フローで `location_prefectures` が設定されるため、auto-sync は `len(cur_prefectures) <= 1` の場合のみ発動。
- **FC ロックの null 制約**: `location_prefectures` を null に FC 保護したい場合は `field_corrections` では不可（NOT NULL 制約）。`annotation_status = 'annotated'` を維持して再アノテーション対象外にする方法を使う。

---

## 2026-05-30 — hakusuisha.py: `../news/n*.html` 相対 URL がそのまま DB 格納 → `urljoin` 修正 + f6ccf6bf/06d080a3 DB 直接修正（commit `c099bcb`）

**問題：** `hakusuisha.py` の `detail_url` が `../news/n64013.html` 形式の相対パスのまま DB に格納され、フロントエンドの「詳細 ↗」リンクが 404。影響イベント：`f6ccf6bf`（及川茜・台湾文学翻訳講演）、`06d080a3`（同スクレイプ）。さらに `f6ccf6bf` は `start_date = 2026-05-25`（公開日）・`description` に「台湾との直接的な関連性はありません」という誤記述・`location_name/address` null という複合不具合があった。

**根本原因：**
1. `hakusuisha.py` の URL 補完が `startswith("/")` のみを処理していたため、`../` 形式の document-relative パスが素通りして DB 格納された。
2. annotator が `raw_description`（記事公開日しか読まず）から `start_date` を「イベント開催日」ではなく「公開日」として抽出。
3. annotator が「台湾との直接的な関連性はありません」と誤判定 — 及川茜氏は台湾作家（呉明益・何致和・鯨向海・唐捐）の日本語翻訳者として知られる。

**修正：**
- `hakusuisha.py`：`startswith("/")` → `not startswith(("http://", "https://"))` + `urljoin(page.url, detail_url)`
- `f6ccf6bf` DB 直接修正（7 FC locks）：`source_url`（絶対 URL）、`official_url`、`start_date`（2026-06-06）、`end_date`、`location_name`（白水社）、`location_address`（東京都新宿区）、`location_prefectures`
- `06d080a3`：`source_url` 絶対化 + FC lock

**教訓：**
- **Auto-generated scraper の detail_url 補完**: `startswith("/")` だけでは `../` パスを取り逃す。`urljoin(page.url, href)` が唯一の正解（`BASE_URL +` 文字列結合は `../` 解決不可）。
- **`scraper/sources/hakusuisha.py` の相対パス形式**: Hakusuisha はリスト ページから見た相対パス `../news/n*.html` を使う。将来の白水社系スクレイパーは `urljoin(page.url, ...)` を必ず使うこと。
- **公開日 vs. 開催日の混同**：annotator がアーカイブ記事ページの日付を `start_date` に使う場合がある。イベント告知記事の場合は `raw_description` 本文内の「開催日」記述と照合すること。
- **「台湾との関連性なし」誤判定**：人物名と翻訳者実績は `raw_description` に直接記載されないケースがある（Hakusuisha の著者ページ等）。公式ページ参照で台湾作家との繋がりを確認してから `selection_reason` + `description` を補完すること。

---

## 2026-05-30 — event `fb12bfa7`: `organizer_zh` に無関係な組織名が幻覚（`上田村振興会・普門寺` 再発 → null クリア + FC 鎖定）

**問題：** `fb12bfa7`（台湾茶・ゲームイベント / kokuchpro）の `organizer_zh = '上田村振興会・普門寺（AI翻訳）'` が格納されており、フロントエンド zh 表示が汚染されていた。`organizer_en = 'Ueda Village Revitalization Association - Fumonji (AI translated)'` も同様。`location_name = '三軒茶屋'`（地区名のみ）・`location_address = '東京都世田谷区三軒茶屋'`（門牌番号欠落）も不正確。

**根本原因：** annotator.py の few-shot context に前回 FC 汚染値（2026-05-08 `fe03288b` と同一の `上田村振興会・普門寺`）が混入し、GPT が再利用。`raw_description` には「語学スクール開催のイベントです」しかなく、組織名は一切登場しない。`（AI翻訳）` サフィックス付きで格納されたが、`auto_qa.py _detect_performer_ai_marker` は `performer_zh/en + category=movie` 限定のため **`organizer_zh` の AI マーカーは検出対象外**（検出ギャップ）。

**修正（DB 直接修正）：**
- `organizer_zh = null`・`organizer_en = null`（信頼できる中国語名なし → 幻覚より null が安全）
- `location_name = 'ふれあい貸し会議室 三軒茶屋A'`（kokuchpro 構造フィールド `会場:` から）
- `location_address = '東京都世田谷区三軒茶屋1-35-5'`（同上 `住所:` から）
- FC lock: 4 フィールド（+ 既存 `category` 含め計 5 ロック）

**教訓：**
- **`organizer_zh` 汚染検出の早期サイン**: `（AI翻訳）` サフィックス付き + 組織名が `raw_description` に不在 → 即 null クリア + FC lock。
- **null fix が正解のケース**: 信頼できる中国語名がソースに存在しない場合は幻覚値を保持するより `null` の方が安全（UI は `organizer`（ja）へ fallback する）。
- **`R-ANN-AI-MARKER` の scope 不足**: `organizer_zh/en` の AI マーカーは現在自動検出されない。定期的な SQL スキャンで補完が必要。
- **kokuchpro の構造フィールド**: `会場:`・`住所:`・`事務局:` は annotator より信頼度が高い。将来的に scraper 側で直接マッピング推奨。

---

## 2026-05-30 — performer_urls[] 追加 + c52caa6e (THE SILENCE) URL フィールド修正

**問題：** `c52caa6e`（THE SILENCE / livepocket）に演者3名（DIGI NOA・樹・肆舞藝-451-）それぞれ Instagram があるが、単一フィールド `performer_url` では1名分しか設定できなかった。また `location_url` にイベントページ URL が誤設定されていた。

**根本原因：**
1. `performer_url` は単一フィールド設計のため、multi-performer イベントの全演者 URL をカバーできなかった。
2. `location_url` に `https://www.diginoa.net/silencepuppet`（イベントページ）が格納されており、会場 URL（`https://theater-green.com/theater/base/`）と混同されていた。`location_url` の語義は「会場の公式サイト」だが、annotator / scraper が description 中のイベント URL を `location_url` に誤帰属することがある。

**修正：**
- migration 079: `events.performer_urls TEXT[]` 追加（`performers[]` と並行インデックス）
- `base.py` / `database.py` / `types.ts`: `performer_urls` フィールド追加
- `page.tsx`: `performer_urls[]` に値がある場合、各演者名の横に個別アイコンリンクを表示（`performer_url` 単一フィールドは fallback として継続）
- DB patch `c52caa6e`:
  - `location_url = 'https://theater-green.com/theater/base/'`（venue URL に修正）
  - `official_url = 'https://www.diginoa.net/silencepuppet'`（イベントページ）
  - `organizer_url = 'https://x.com/silence_puppet'`（主催者 X）
  - `performer_urls = ['digi_noa', 'tatsuki_magic', '451_tw'] Instagram`
  - FC locked: 4 フィールド全て

**教訓：**
- **multi-performer イベント** → `performer_urls TEXT[]` を使い `performers[]` と同じインデックスで URL を設定する。`performer_url`（単一）は単一演者イベント専用 fallback。
- **`location_url` \≠ イベントページ URL**: `location_url` は「会場の公式サイト」のみ。イベントページ URL は `official_url` へ。scraper / DB パッチ時に `location_url` に `diginoa.net/silencepuppet` のようなイベント固有 URL が入っていたら要修正。
- **演者の Instagram/SNS URL の設定先**: `performer_url` または `performer_urls[]`（`official_url` は ❌）。

---

## 2026-05-30 — peatix `ee17c509`: `performers=['夫婦']`（一般名詞）→ ユニット固有名・performer_zh/en 補完・official_url(Instagram)・organizer_url 設定

**問題：** `ee17c509`（Floti Studio 似顔絵ワークショップ）の `performers = ['夫婦']`（一般名詞）が残留し、`performer_zh/en` が null のまま。フロントエンドで多言語表示不可かつ「公式サイト」「主催者」リンクも非表示。

**根本原因：** annotator が `raw_description`「台湾と日本の作家夫婦によるユニット Floti Studio」から `夫婦` を performers に設定（一般名詞を固有名詞と誤認）。英語ブランド名 "Floti Studio" は GPT 翻訳生成の対象にならず `performer_zh/en = null` のまま。`official_url` と `organizer_url` は annotator が自動設定しないフィールドのため未設定。

**修正（DB 直接修正）：**
- `performers = ['Floti Studio']`（`'夫婦'` → 正式ユニット名）
- `performer_zh = performer_en = 'Floti Studio'`（英語ブランド名は翻訳不要、そのまま設定）
- `official_url = 'https://www.instagram.com/flotistudio/'`（専用イベントページ非存在 → 創作者公式 Instagram）
- `organizer_url = 'https://www.eslitespectrum.jp/'`（誠品生活日本橋公式サイト）
- FC lock: `performer_zh`, `performer_en`, `official_url`, `organizer_url`

**教訓：**
- **performers の一般名詞ガード**: `performers` に「夫婦」「ユニット」「グループ」等の一般名詞が入っていたら固有名詞（ユニット名・人名）に修正 + FC lock。
- **英語ブランド名 → performer_zh/en は翻訳不要**: 英語固定名称は `_zh`/`_en` も同じ値を設定。GPT が null を返す場合は手動補完 + FC lock。
- **イベント専用ページ非存在時の official_url**: Peatix が `source_url` の場合、創作者の公式 Instagram/SNS を `official_url` に設定することで「公式サイト ↗」リンクを表示できる。
- **organizer_url の店舗専用 URL は不安定**: `https://www.eslitespectrum.jp/nihonbashi/` → 404。ルートドメインを優先（`https://www.eslitespectrum.jp/`）。

---

## 2026-05-30 — peatix: React SPA の遅延レンダリングで `raw_description` が空になり全フィールド欠落（DB 直接修正 + annotator 再実行）

**問題：** peatix イベント `ee17c509`（Floti Studio 似顔絵ワークショップ）の `raw_description` が `開催日時: 2026年06月20日\n\n` のみ。2日間開催・会場・時間・出演者情報が全欠落。

**根本原因：** Peatix は React SPA。CI スクレイプ時に `networkidle` が発火した直後のタイミングで `.event-description` のコンテンツがまだレンダリングされておらず、CSS セレクタが空文字列を返した。`page_text` は取得できた（台湾キーワードチェック通過）が `description_ja = None` → 日付 prefix のみが `raw_description` に格納された。annotator も全フィールドを `null` 出力。

**副作用：** 薄い `raw_description` から annotator が `performer = '夫婦'`（一般名詞）・`organizer = 'Floti Studio'`（実際は主催者 = 誠品生活日本橋）と逆転設定。

**修正（DB 直接修正）：**
- Playwright で再取得し完全な `raw_description` + `end_date=2026-06-21` + `location_name` + `location_address` + `location_prefectures` を手動パッチ。
- `annotation_status = 'pending'` にリセット → `annotator.py --source-ids 4d588dee68c88e15` で手動再実行。
- `performer = 'Floti Studio'`・`organizer = '誠品生活日本橋'` に手修正し FC lock。

**教訓：**
- **Peatix SPA 遅延レンダリング**: `networkidle` 後も `.event-description` 内容が数十ms 遅延してレンダリングされる場合がある。`raw_description` が日付 prefix のみの場合は認識して手動対処が必要。次回 CI スクレイプで後から修正される可能性もあるが、発見次第 DB 手動パッチ。
- **performer vs organizer 区別**: Peatix ページの「By ‹名前›」= `organizer`（主催者）。イベントを実施するアーティスト/動作者 = `performer`。GPT が両者を入れ替える可能性があるので、日本語淡化語（「夫婦」「ユニット」など一般名詞）が performer に入っていたら手修正 + FC lock。
- **raw_description 汚薄イベント対処フロー**: 日付 prefix のみ → Playwright 再取得 → `raw_description` パッチ → `annotation_status = 'pending'` → `annotator.py --source-ids <source_id>` で手動再実行。

---

## 2026-05-30 — iwafu: 主催者 URL が `location_url` に誤設定、`official_url` vs `source_url` 表示区別を確認（DB 直接修正）

**問題：** iwafu イベント `c61470db`（赤城で台湾さんぽ）の `location_url` が `https://gunma-taiwan-association.studio.site/`（群馬台湾総会 = 主催者サイト）に設定されており、会場リンクが主催者サイトに誤誘導。また公式サイト `https://gunma-kanko.jp/events/290` が未設定のため「公式サイト」として表示されていなかった。

**根本原因：**
1. iwafu の `raw_description` 末尾に主催者 URL が含まれており、scraper が `location_url` に誤設定（会場 URL ではなく主催者 URL）。
2. `official_url` フィールドが未設定 → frontend が `source_url`（iwafu URL）を「原始資訊」として表示し、「公式サイト」として認識されなかった。

**修正（DB 直接修正）：**
- `location_url = null`（会場リンクを削除）
- `organizer = '群馬台湾総会'`、`organizer_url = 'https://gunma-taiwan-association.studio.site/'`（主催者フィールドへ移動）
- `official_url = 'https://gunma-kanko.jp/events/290'`（「公式サイト ↗」として表示）
- `source_url = 'https://www.iwafu.com/jp/events/1140344'`（iwafu URL に戻す = 「原始資訊 ↗」として表示）
- FC lock: `organizer`、`organizer_url`、`official_url`（`null` は FC の NOT NULL 制約で保存不可）

**教訓：**
- **フロントエンド表示区別**：`official_url` → 「公式サイト ↗」、`source_url` → 「原始資訊 ↗」。公式イベントページを「公式サイト」として表示させるには `source_url` ではなく `official_url` に設定すること。
- **`field_corrections.corrected_value` は NOT NULL**：`null` 値を FC で保存・ロックすることは不可能。null にしたフィールドを保護するには `annotation_status = 'annotated'` を維持するか、scraper が再設定しないことを確認する。
- iwafu の `raw_description` 末尾 URL は主催者サイトである可能性が高い。`location_url` ではなく `organizer_url` に設定すること。

---

## 2026-05-30 — annotator: `enrich_movie_titles()` が `work_id` を自動付与しない → kyoto_cinema 新規 movie_id ごとに `work_id=None`（commit `7e5b124`）

**問題：** `kyoto_cinema_341456`（霧のごとく / 大濛）に `work_id=None`。`works` テーブルには同作品のレコード（`0d69a88f`）が存在するにもかかわらず紐付けされていなかった。

**根本原因：**
1. `_query_works()` の `.select()` に `id` が含まれていなかった → `w_row.get("id")` が `None` を返し `works_id` が伝播されなかった。
2. `enrich_movie_titles()` は works テーブルで名前照合しても `work_id` を更新しない設計だった（`_oneoff_fix_movies.py` による手動バッチのみ）。
3. kyoto_cinema サイトはスクレイプ期間ごとに新しい movie_id を URL に割り当てる → `source_id` が毎回変わる → movie-extend が一切発動しない → 常に新規 INSERT → `work_id` が引き継がれない。

**修正（commit `7e5b124`）：**
- `_query_works()` の `.select()` に `"id"` を追加（両方のクエリ分岐）。
- `_resolve_movie_titles_for_event()` を 6-tuple → **7-tuple** 化：`(name_zh, name_en, official_url, works_performer, works_director, works_id, title_used)`。
- `enrich_movie_titles()` に `if works_id and not event.get("work_id"): update["work_id"] = works_id` を追加。`work_id` は FC 保護外なので `_lock_fields_via_corrections()` フィルタから除外。
- `eval_annotator.py` の呼び出し元を 7-tuple アンパックに対応。
- DB 直接パッチ：`kyoto_cinema_341360`・`kyoto_cinema_341456` に `work_id=0d69a88f` を設定。

**教訓：**
- `enrich_movie_titles()` は **works テーブルとの照合に成功した時点で `work_id` も自動付与**する。`_resolve_movie_titles_for_event()` の戻り値は 7-tuple であり、6-tuple に変更してはいけない。
- `work_id` フィールドは `field_corrections` による FC lock の対象外。`_lock_fields_via_corrections()` 呼び出し時に `{k: v for k, v in update.items() if k != "work_id"}` でフィルタすること。
- **ソースが毎回新しい movie_id を URL に生成するシネマ系スクレイパー**（kyoto_cinema など）では `source_id` が変わるため movie-extend も merger Pass 1 も発動しない。`work_id` は annotator の自動付与に委ねるしかない。

---

## 2026-05-30 — annotator: `_extract_hours_from_raw()` が `－`（U+FF0D）を認識せず終了時刻を欠落（commit `b3b32b3`）

**問題：** `waseda_taiwan` イベント `75a46729`（早稲田大学講演会）の `business_hours` が `15:05` のみで、原文 `15:05－17:00` の終了時刻 `17:00` が欠落。

**根本原因：** `_extract_hours_from_raw()` の時間レンジ正規表現 `[〜~～\-]` に `－`（U+FF0D, FULLWIDTH HYPHEN-MINUS）が未収録。waseda-taiwan 系の原文は全角ハイフン `－` を区切りに使用しており、マッチ失敗 → fallback の「`日時` ラベル後の最初の時刻」パターンで `15:05` のみ返していた。

**修正（commit `b3b32b3`）：**
- `annotator.py` L427: `[〜~～\-]` → `[〜~～\-－]`（U+FF0D 追加）
- DB 直パッチ：event `75a46729` に `business_hours = '15:05〜17:00'`、`annotation_status = 'pending'`

**教訓：**
- 日本語テキストの時間レンジ区切り文字は **5 種類** ある：`〜`(U+301C)・`~`(U+007E)・`～`(U+FF5E)・`-`(U+002D)・`－`(U+FF0D)。正規表現は全種類を含めること。
- `_extract_hours_from_raw` を新規作成・修正する際は 5 種類全てに対してテストケースを実行すること。
- waseda-taiwan 系・学術イベント系サイトは `－`（U+FF0D）を多用する。

---

## 2026-05-30 — waseda_taiwan: `_STOP_LABELS` 欠如で venue_raw に発表者情報が混入、performers にモデレーター未収録（commits `0604a6f`, `b3be645`）

**問題：** `location_name` に `早稲田大学...教室 講演者：郭智輝氏... モデレーター：久保克行...` と発表者情報が混入。かつ `performers = ['郭智輝']` のみで モデレーター未収録。

**根本原因：**
1. `_STOP_LABELS` に `講演者`/`モデレーター`/`対象` が未登録 → `_extract_after_label()` が会場ラベル後の全行を取り込んだ。`raw_description` の `会場:` 行に発表者情報が混入 → annotator が全テキストを `location_name` に格納。
2. `raw_desc_parts` に `講演者`/`モデレーター` が含まれていなかった → annotator が `performers` に複数人を収録できなかった。

**修正：**
- `_STOP_LABELS` に 3 語追加（venue 抽出の truncate boundary）。
- `raw_desc_parts` に `f"講演者: {speaker_raw}"` / `f"モデレーター: {moderator_raw}"` を追加（各々 `_extract_after_label()` で boundary 付き抽出）。
- DB 直接修正 + FC lock（`location_name`、`performers`、`performer_zh/en`）。

**教訓：**
- `_extract_after_label()` を使うスクレイパーは、**ソース同一行に現れうる全ラベルを `_STOP_LABELS` に登録**すること。
- 学術イベント系スクレイパーで `講演者`/`モデレーター` を使う場合、`raw_description` に**独立した構造化エントリとして追加**する。`会場:` 行に混ぜると annotator は performers を抽出できない。
- 多人イベント: `performers.length ≥ 2` になったら `performer_zh/en = null` に設定する（多人 Guard）。

---

## 2026-05-30 — seed script 住所衝突チェックが NFKC 非正規化 + exact 比較のため false positive（commit `b32aad2`）

**問題：** `_oneoff_seed_authoritative_venues.py` dry-run で TCC・FAAM 2 件が毎回 SKIP。DB 住所バリアント（全形スペース `\u3000`、全形数字、都道府縣前綴欠如、大樓名有無の違い）が全て「衝突」と誤判定されていた。例：`港区虎ノ門1-1-12 虎ノ門ビル2階`（都道府縣なし）vs seed `東京都港区虎ノ門1-1-12 虎ノ門ビル2階` → 完全不一致でSKIP。

**根本原因：** `_has_conflict()` が `a != seed_address`（exact string 比較）を使っていた。Unicode 正規化も、建物名・フロアの detail level の違いも考慮なし。

**修正（commit `b32aad2`）：**
- `_normalize_addr()`: `unicodedata.normalize("NFKC", ...)` で全形文字・全形スペースを半角に統一。
- `_street_prefix()`: 番地（`1-1-12` / `3-1` 等）末尾までの street-level prefix を抽出し、大樓名・フロアを捨てる。
- `_addresses_compatible()`: street prefix が一致、または一方が他方の suffix になっている（都道府縣前綴の有無）場合を compatible と判定。
- `_has_conflict()` の比較を `not _addresses_compatible(a, seed_address)` に変更。
- 結果：dry-run が `skip=0 conflict=0`（全 11 件 update）に改善。

**教訓：**
- **住所の衝突チェックは exact 比較禁止**。最低限 NFKC 正規化 + 番地レベルのトランケートが必要。
- `unicodedata.normalize("NFKC", addr)` 一発で全形スペース・全形数字・全形英字が全て半角化される。
- 都道府縣前綴の有無（`港区…` vs `東京都港区…`）は `pa.endswith(pb) or pb.endswith(pa)` で吸収可。
- seed pre-flight の衝突ログには必ず event_id sample を出力しておくこと。事後調査が格段に速くなる。

---

## 2026-05-27 — authoritative venue registry 導入：inactive イベント汚染住所が pre-flight conflict を誤発火（PR-2 + commit `31e1493`）

**問題：** migration 076 + `venue_registry.py` + seed script で authoritative venues を確立しようとしたが、seed pre-flight で 6 件が SKIP。原因は inactive gnews イベントが古い住所（省略形）を持っており、active 扱いで衝突判定に混入していた。

**根本原因：** `_get_event_rows_for_seed()` が `is_active` カラムを select しておらず、`_has_conflict()` も active/inactive を区別していなかった。inactive gnews イベントは二次情報であり、住所が不完全なケースが多い（例：`東京都港区虎ノ門1-1-12` — 大樓名なし）。

**修正（commit `31e1493`）：**
- `_get_event_rows_for_seed()`: select に `is_active` を追加。
- `_has_conflict()`: `active_rows = [r for r in event_rows if r.get("is_active", True)]` でフィルタリング。

**教訓：**
- **seed pre-flight の衝突チェックは active イベントのみを対象にする**。gnews / secondhand ソースの inactive イベントは住所品質が低く、seed を誤ブロックする。
- authoritative venue registry の導入時は migration の compatibility fallback を実装しておくこと（migration 未套用の staging 環境でスクリプトがクラッシュしない）。`venues` テーブルの `is_authoritative` カラム存在チェックを先行実行し、欠如なら `SystemExit(2)` で明示的にエラーを出す。

---

## 2026-05-26 — `main.py --source X` を本地 staging 用ループで使い、annotator/merger が 27 回フル DB 走査されコスト膨張

**問題：** 29 個の新規 scraper 登録（commit `bfad6e9`）後、明日 09:00 JST cron 前に「quota を打ち破らないか」を確認するため、27 source を `for s in SOURCES: python main.py --source $s --timeout 420s` で順に流した。結果 20 source が 420s timeout（実 scrape は数秒で完了、残り全部 annotator phase で消費）。OpenAI コール量は本来の 27 倍規模。

**根本原因：** `scraper/main.py` L443–444 は `--source` 指定の有無に関わらず、scrape 完了後に **無条件で** `annotate_pending_events()` + `enrich_movie_titles()` + `enrich_person_names()` を実行する。これらは DB 全体の `annotation_status='pending'` 行を対象とするため、`--source X` を呼ぶたびに全 pending queue が再走査される。設計上「scrape + annotate is one indivisible pipeline」であり、daily cron（`python main.py` 引数なし）では 1 回しか走らないため正しい挙動。問題は **本地 staging スクリプトの使い方**。

**修正：** コード変更なし（生産挙動は正しい）。`SKILL.md` に「本地で多 source の scrape 妥当性だけ見たい時は必ず `--dry-run --source X` を使う」ルールを追記。`--dry-run` は DB 書き込みも annotator/merger 起動もスキップする。

**教訓：**
- **`--source X` ≠ cost-bounded**：`--source` は「どの scraper を走らせるか」のフィルタであり、annotator/merger phase はスキップしない。本地で N source × 個別 `--source` 呼び出しを行うと、annotator が **N 倍** 走る。
- **本地多 source staging は `--dry-run` 一択**：DB 書き込みと OpenAI コール両方を回避するのは `--dry-run` だけ。Quota 検証や registration audit は dry-run で十分。
- **production cron は無影響**：`python main.py`（引数なし）は全 114 scraper → merger → annotator 1 回、というのが正しい設計。今回観察したコスト膨張は staging 側ループの誤用が原因。

---

## 2026-05-20 — kyoto_cinema: end_date が初日のまま固定、movie-extend パスが発動しなかった（database.py + kyoto_cinema.py 修正）

**問題：** kyoto_cinema スクレイパーが毎日走っているのに、イベントの `end_date` が最初にスクレイプした日で固定された。`business_hours` も初日の 1 タイム（例: `14:50`）のまま更新されなかった。

**根本原因：**
1. `database.py` movie-extend 条件に `and "movie" in (e.category or [])` が含まれていた。スクレイパーが生成する Event は annotator 実行前のため `category=[]` → 条件が常に False → extend パス発動なし。
2. `kyoto_cinema.py` は「終映日」が見つからない場合 `end_date = None` を設定。movie-extend の MAX ロジックは `new_end=None` 時に `old_end` をそのまま返すため、日付が進まない。

**修正：**
1. `database.py` L538: `and "movie" in (e.category or [])` を削除（`existing_movie_state` 自体が DB 側 movie 確認済み）。
2. `kyoto_cinema.py` L163: `if end_date is None and start_date is not None: end_date = start_date` を追加（毎日 MAX で end_date が前進する）。

**教訓：**
- **映画スクレイパーで end_date 未取得の場合は `start_date` をフォールバックにする**。MAX ロジックが機能するために非 None の新しい日付が必要。
- movie-extend の発動条件は DB 行のカテゴリだけで判定する。スクレイパーの Event.category を確認しても意味がない（常に空）。

---

## 2026-05-20 — performers[] 言語違反（繁体字→カタカナ）+ performers_zh[] ステージネーム GPT ハルシネーション（DB 直接修正）

**問題：** 霧のごとく（映画 大濛）11 件の `performers[]` に繁体字（`['范少勳', '區偉', '9m88', '曾敬驊']`）が格納されており、日本語ロケールで日本の映画サイトのカタカナ表記ではなく漢字が表示された。また `performers_zh[]` に `9m88 → 'Ju 88轟炸機'`（WW2 ユンカース爆撃機）という GPT ハルシネーションが混入し、`field_corrections` でロックされ固定化していた。

**根本原因：** annotator が繁体字 film DB（`works.cast_summary`）から performers[] を補完する際、日本語ソースページのカタカナ形を参照しなかった。`performers_zh[]` 生成時に GPT がステージネーム `9m88` を軍用機型番「Ju 88」と誤一致させた。

**修正：** 京都シネマ公式ページ（`出演：ケイトリン・ファン、ウィル・オー、9m88、ツェン・ジンホア、リウ・グァンティン、ビビアン・ソン`）のカタカナを権威ソースとして参照。全 11 件を更新し FC 再ロック。`works.cast_summary` もカタカナ 6 名に更新。

**教訓：**
- `performers[]` は **日本語（カタカナ）ソースページから取得した名前** が正しい値。繁体字 film DB のデータは `performers_zh[]` に入れること。
- `performers_zh[]` 生成時、英数字・記号含むステージネーム（`9m88` 等）は **翻訳・変換禁止**。元の表記をそのままコピーする。
- `field_corrections` を手動修正する際は `corrected_value` NOT NULL 制約に注意（`None` → `""` で null 表現）。

---

## 2026-05-20 — performers[]: 繁体字が入り日本語（カタカナ）が消失 + performers_zh に 'Ju 88轟炸機' ハルシネーション（DB 直接修正）

**問題：** 霧のごとく（大濛）11 件の `performers[]` が繁体字（`['范少勳', '區偉', '9m88', '曾敬驊']`）で格納されており、日本語モードでカタカナ名が表示されなかった。`performers_zh[]` には `'Ju 88轟炸機'`（WW2 爆撃機名）というハルシネーションが入っており、GPT が `9m88`（台湾ミュージシャンの芸名）を爆撃機名に誤変換していた。加えて `field_corrections` に旧来の悪い値がロックされており、FC 削除なしには修正できない状態だった。

**根本原因：** (1) `performers[]` 言語規約が annotator SYSTEM_PROMPT に明記されておらず、GPT が繁体字をそのまま格納した。(2) アーティスト芸名（英数字混じり）は翻訳不可だが GPT へその指示がなかった。

**修正：** 京都シネマ公式ページから正確なカタカナ（`ケイトリン・ファン`、`ウィル・オー`、`9m88`、`ツェン・ジンホア`、`リウ・グァンティン`、`ビビアン・ソン`）を確認。全 11 件の `performers[]` をカタカナに更新、`performers_zh[]` を正しい繁体字 6 名に修正、FC 削除・再ロック、`works.cast_summary` 更新。

**教訓：** (1) `performers[]` は日本語ソースのカタカナ名が入る。`performers_zh[]` が繁体字。(2) アーティスト芸名（`9m88` 等）は翻訳不可 — GPT に `performers_zh` を生成させる場合は「芸名はそのまま転記」の指示を SYSTEM_PROMPT に追加する。(3) performers データを手動修正する場合は必ずソースページをフェッチしてカタカナを確認してから FC をロックする。

---

## 2026-05-19 — eplus: scraper 層で `ev.performer` を直接セット — SKILL.md performer ルール違反（commit `fe72ea2`）

**問題：** `_fetch_detail_info()` が `<dt>出演</dt><dd>…</dd>` から取得した performer 文字列を `ev.performer = info["performer"]` と直接セット。SKILL.md `## performer / performers[] 注解規則` に「scraper 層では performer を直接セットしない。raw_description に書き込むこと」という既存ルールが存在していたが、実装前に確認されなかった。

**根本原因：** 機能追加前に SKILL.md の performer ルールを検索しなかった。「performer フィールドを扱う際のルール確認」ステップがチェックリストに入っていなかった。

**修正（commit `fe72ea2`）：** `ev.performer = info["performer"]` を削除。performer と program の両方を `raw_description` に `出演: …\n曲目・演目: …` 形式で追記。annotator GPT が raw_description から performer を自動抽出する（`SKILL.md § performer/performers[] 注解規則` 準拠）。

**教訓：** performer / performers[] / performer_zh/en 関連フィールドを scraper で扱う場合、必ず SKILL.md の `## performer / performers[] 注解規則` を事前確認する。「**Scraper 層用不到**」 — scraper は raw_description に `出演: …` 形式で書き込むだけ。直接セットは FC ロックとの整合性も崩す。

---

## 2026-05-19 — enrich_addresses: 市区レベルアドレス（`'福岡市'` 等）が VAGUE 判定されずスキップ + FC ロック二重ブロック（commit `113fceb`）

**問題：** eplus スクレイパーが H1 fetch で取得した `'福岡市'`（市区レベル）は `VAGUE_ADDRESS_VALUES` に含まれず、`enrich_addresses.py` の候補フィルタを通過できなかった。さらに `field_corrections` に `location_address: '福岡県'` が 2026-05-16 時点でロックされており、eplus の `'福岡市'` 更新も毎回 FC で上書きされる二重ブロック状態（event `7cdd06cb` — アクロス福岡シンフォニーホール）。

**根本原因：** `VAGUE_ADDRESS_VALUES` は固定 frozenset（`'東京'`・`'大阪府'` 等）のみカバー。市区名（`'福岡市'`・`'渋谷区'`）は未収録。また eplus（都道府県→市区）と enrich_addresses（市区→街路）は 2 段階補完パイプラインだが、前段が市区まで補完しても後段が市区を VAGUE と見なさなければ街路補完に進めない構造上の穴があった。

**修正（commit `113fceb`）：**
1. `_VAGUE_GEO_RE = re.compile(r'^[^\s]{2,10}[都道府県市区]$')` を追加。
2. 候補フィルタに `or bool(_VAGUE_GEO_RE.match(...))` を追加。
3. 対象イベントの FC ロック削除 + `location_address = NULL` にリセット後、`enrich_addresses.py --source eplus` 実行 → `'福岡県福岡市中央区天神1-1-1'`（conf=high）で補完・FC 再ロック。

**教訓：**
- `enrich_addresses.py` の候補判定は `VAGUE_ADDRESS_VALUES`（固定 set）と `_VAGUE_GEO_RE`（正規表現）の**両方**で行う。
- `field_corrections` に `location_address` ロックがあるイベントは enrich_addresses の FC batch check で**常にスキップ**。手動で街路補完を取得する場合は FC 削除 + `location_address = NULL` が必要。
- eplus の 2 段階補完パイプライン：`_PREF_ONLY_RE`（都道府県→市区）→ `enrich_addresses`（市区→街路）。後段は前段の出力（市区）を VAGUE と認識できなければパイプラインが詰まる。

---

## 2026-05-19 — Peatix: Playwright `inner_text()` がページ全体テキストを返し `organizer_name` が数千文字になる（commit `f839508`）

**問題：** Playwright の `inner_text()` がグループアンカー要素に対して、期待どおりの組織名（数十文字）ではなく「Translate this page...」から始まるページ全体テキスト（数千文字）を返すケースがあった。`organizer_name` がページ全体テキストになり、ブロックリスト照合が誤動作する可能性があった。

**根本原因：** Playwright `inner_text()` は live DOM テキストを返すが、DOM の構造や SPA レンダリング状態によって要素が期待以上のコンテンツを含む場合がある。「主催者名は短い文字列」という暗黙の前提を検証するガードがなかった。

**修正（commit `f839508`）：** 主パスと fallback パス両方に `len(_txt) <= 100` ガード追加。100 文字超のテキストは organizer_name として無効と判断し空文字扱い。

**教訓：** Playwright `inner_text()` を短い文字列フィールド（組織名・タイトル・地名等）に使う場合は `if _txt and len(_txt) <= 100` の長さガードを必ず設ける。長さガードなしでは「全ページテキストが返る」ケースが静默通過する。

---

## 2026-05-19 — Peatix: `organizer_name` を抽出しながら `Event()` に渡していなかった（commit `24198d0`）

**問題：** Peatix イベントの `ev.organizer` が常に null。`organizer_name` は `BLOCKED_ORGANIZER_PATTERNS` ブロックリスト照合のために抽出されていたが、`Event()` コンストラクタには渡されていなかった。

**根本原因：** フィールドが「ブロックリスト照合」目的として追加されたとき、「DB 保存」という第 2 の用途が見落とされた。「データを取るが書かない（Extract but not store）」anti-pattern。

**修正（commit `24198d0`）：** `Event()` の引数に `organizer=organizer_name or None` を追加。

**教訓：** 新しいフィールドをスクレイパーに追加するとき (1) 抽出ロジック (2) `Event()` コンストラクタへの代入 (3) DB migration の 3 点が揃っているか確認する。ブロックリスト照合のために抽出した変数は必ず `Event()` にも渡す。

---

## 2026-05-19 — eplus: 詳細ページを既に fetch していたが `dt/dd` フィールドを無視（commit `e897d29`）

**問題：** eplus イベントの `ev.performer` が常に null。詳細ページには `<dt>出演</dt><dd>…</dd>`・`<dt>曲目・演目</dt><dd>…</dd>` で出演者・プログラム情報が構造化されていたが取得していなかった（event `7cdd06cb` — ナショナル･シンフォニー･ユース･オーケストラ）。

**根本原因：** `_fetch_city_from_detail()` は都市抽出のみを目的として設計されており、同一 HTTP レスポンスに含まれる他のフィールド（`dt/dd` ペア）を完全に無視していた。「1 リクエスト 1 フィールド」の設計。

**修正（commit `e897d29`）：** `_fetch_city_from_detail()` → `_fetch_detail_info()` に拡張。`_WANTED_LABELS = {"出演": "performer", "曲目・演目": "program"}` で dt/dd を一括取得し `ev.performer` と `ev.raw_description` に反映。

**教訓：** 詳細ページを fetch しているなら、同一リクエストで取れる全フィールドを一括抽出する。「1 リクエスト 1 フィールド」は追加要件発生のたびにリクエスト数が増加する。

---

## 2026-05-19 — eplus: 詳細ページ fetch による都道府県→市区レベルアドレス補完（commit `0cfd07f`）

**問題：** eplus.jp 検索結果カードには会場名が `（福岡県）` 形式（都道府県レベル）でしか含まれない。`location_address = "福岡県"` がそのまま DB に保存されるが、`enrich_location.py` は `location_address IS NULL OR ''` のみ処理するためスキップされ続けた（event `7cdd06cb` — アクロス福岡シンフォニーホール）。

**根本原因：** `_parse_card()` はカードテキストから `（都道府県）` パターンを抽出する設計。詳細ページ H1 には `(福岡市・2026/8/1(土))` という市区名が含まれるが、カードスクレイプではアクセスされない。

**修正（commit `0cfd07f`）：** Playwright セッション終了後、`_PREF_ONLY_RE = re.compile(r"^[^\s]+[都道府県]$")` にマッチした各イベントに対して `requests.get()` + `BeautifulSoup` で詳細ページ H1 を fetch。`r"\(([^・)]+[市区])\s*・"` パターンで市区名を抽出し `ev.location_address = city` に更新。

**教訓：**
- eplus.jp（および同様のチケットプラットフォーム）では詳細ページ H1 の `(市名・日付)` パターンから市区名が取得できる。
- `enrich_location.py` に頼らず、スクレイパー自身でアドレス精緻化を完結させる設計のほうが確実（後段スクリプトは null/空のみ処理するため）。
- regex に特定 Unicode 文字を使う場合は literal 文字を直接埋め込む（raw string 内の `\u30fb` は Unicode 文字として解釈されない）。

---

## 2026-05-19 — Peatix URL 正規化を URL 収集段階に拡張（7 件 DB 修正、commit `8b901ec`）

**問題：** 2026-05-17 の `_scrape_detail()` 入口修正（`e9c6f80b`）後も、DB に `/us/event/` URL が 7 件蓄積されており `55d766ae`（台湾家庭料理会in亀有）で再発。`peatix.com/us/event/4994536` → 302 → トップへリダイレクト。

**根本原因：** `_scrape_group_events` と `_search_events` でも locale prefix 付き URL が取得されていた。`_scrape_detail()` 入口の修正は detail scrape 時のみ有効で、URL 収集リストへの混入を防げなかった。正規 URL でスクレイプ済みの重複レコードが存在する場合、`/us/event/` 版は `source_id`（md5 ハッシュ）が異なる別レコードとして重複していた。

**修正（commit `8b901ec`）：** `_normalize_peatix_url()` をモジュールレベルに追加。`_scrape_group_events` と `_search_events` の URL 収集ループで適用。DB 7 件：5 件は `merged_into_event_id` で merge soft-delete、1 件は `source_url`/`source_id` 正規化、1 件（inactive）skip。

**教訓：** URL 正規化は収集段階（`_search_events`・`_scrape_group_events`）で行う。detail 入口修正は後段のため収集済みリストの汚染を防げない。DB 修正は「重複チェック → DUP: merge soft-delete / NO-DUP: update in place」の 2 分岐で設計する。

---

## 2026-05-19 — annotator Phase C: 地域名｜会場名 prefix が location_name に混入（commit `2b328e1`）

**問題：** eplus 等のプラットフォームが `東京六本木｜EX THEATER ROPPONGI`・`大阪梅田｜Zepp Osaka Bayside` 形式で会場を表示する。`｜` 前の地域ナビゲーションラベルが `location_name` に丸ごと混入していた。

**根本原因：** annotator SYSTEM_PROMPT Rule 6 に `｜` 形式への指示がなく、GPT が `｜` を含む全文字列を会場名として採用していた。

**修正（commit `2b328e1`）：** SYSTEM_PROMPT Rule 6 に VENUE NAME PREFIX NOTE を追加。`地域名｜会場名` 形式を検出し `｜` 以降のみを `location_name` とするルール。

**教訓：** eplus / livepocket など `地域名｜会場名` 形式のプラットフォームを扱う場合は annotator SYSTEM_PROMPT にこのルールが適用されているか確認する。

---

## 2026-05-19 — enrich_addresses: location_address_zh が SC のまま DB に書き込まれていた（commit `2b328e1`）

**問題：** `enrich_addresses.py` が gpt-4o-search-preview から取得した `location_address_zh` を `_to_trad()` なしで DB に直接書き込んでいた。dry-run では `东京都涩谷区圆山町2-3 6楼`（簡体字）が表示され DB に SC が混入するバグ。

**根本原因：** `_to_trad()` は `annotator.py` の `annotate()` 内でのみ呼ばれており、外部スクリプト `enrich_addresses.py` はこの処理が漏れていた。

**修正（commit `2b328e1`）：** `from annotator import _to_trad` を追加し、`patch["location_address_zh"] = _to_trad(result["location_address_zh"])` に変更。

**教訓：** annotator 外部のスクリプト（バックフィル、`enrich_*` 系）が `_zh` フィールドを直接 DB に書き込む場合は必ず `_to_trad()` を通すこと。

---

## 2026-05-19 — eplus: scraper 層で `ev.performer` 直接セット — SKILL.md performer ルール違反（commit `fe72ea2`）

**問題：** `_fetch_detail_info()` が performer を `ev.performer = info["performer"]` と直接セット。SKILL.md「Scraper 層用不到」ルール違反（performer は annotator GPT が raw_description から抽出する）。

**根本原因：** 機能追加前に SKILL.md performer ルールを確認しなかった。

**修正（commit `fe72ea2`）：** `ev.performer` 直接セットを削除し、`raw_description` に `出演: …\n曲目・演目: …` 形式で追記。

**教訓：** performer 関連フィールドを scraper で触る場合は必ず SKILL.md `## performer / performers[] 注解規則` を確認する。scraper は raw_description に書くだけ。

---

## 2026-05-19 — enrich_addresses: 市区レベルアドレス（`'福岡市'`）が VAGUE 未判定 + FC ロック二重ブロック（commit `113fceb`）

**問題：** `VAGUE_ADDRESS_VALUES` に市区名が含まれず候補フィルタ通過不可。加えて FC に古い `'福岡県'` がロックされ eplus の補完も毎回上書き（event `7cdd06cb`）。

**根本原因：** VAGUE は固定 set のみで正規表現カバレッジなし。eplus（都道府県→市区）と enrich_addresses（市区→街路）の 2 段階パイプラインで後段が市区を VAGUE と見なさなかった。

**修正（commit `113fceb`）：** `_VAGUE_GEO_RE = re.compile(r'^[^\s]{2,10}[都道府県市区]$')` 追加。FC 削除 + NULL リセット後に enrich_addresses 実行 → `'福岡県福岡市中央区天神1-1-1'` に補完。

**教訓：** enrich_addresses に FC ロックがあるイベントは常にスキップ。街路補完を強制する場合は FC 削除 + `location_address = NULL` が必要。

---

## 2026-05-17 — `ftip`: Peatix チャンネル URL がイベント URL より先に HTML に現れ、チャンネルページが source_url に設定された（event `eeb5b12e`）

**問題:** `source_url` / `official_url` が `https://nerimaokinawaeigasai.peatix.com`（主催者チャンネルページ）に設定され、個別イベントページ `https://peatix.com/event/4572285/view` が使われなかった。

**根本原因:** `_extract_peatix_url_from_html` が HTML アンカーを先頭から走査して**最初の** `peatix.com` リンクを返す設計。ftip 記事ではバナーのチャンネルリンク（`nerimaokinawaeigasai.peatix.com`）が個別イベントリンク（`peatix.com/event/4572285/view`）より先に出現するため、チャンネルページが返された。

**修正（commit `34368e3`）:** `_extract_peatix_url_from_html` を全アンカーを走査し `peatix.com/event/NNN` 形式を即時返却するよう改修。`/event/` が存在しない場合のみチャンネル URL を fallback として返す。

**教訓:** Peatix には `peatix.com/event/NNN`（個別イベント）と `org.peatix.com`（チャンネル）の 2 種類の URL がある。HTML 内で両方が出現する場合は `/event/NNN` を優先すること。「最初に見つかった URL を返す」実装は URL 種別の優先度を無視するため誤りを招く。

---

## 2026-05-17 — Peatix: ロケール付き URL（/us/event/）が source_url に保存される → broken link（event e9c6f80b）

**問題**
Peatix は訪問者のブラウザロケール設定によって `https://peatix.com/us/event/{id}` 形式（または `/jp/event/` 等）にリダイレクトする。Playwright が group ページから取得した `<a href>` がこのロケールプレフィックス付き形式だったため、`source_url=url` がそのまま保存され 404 になっていた。

**修復（commit ece9d33）**
`_scrape_detail()` の先頭で `re.sub(r"^(https://peatix\.com)/[a-z]{2}/event/", r"\1/event/", url)` を実行しロケールプレフィックスを除去。DB の event `e9c6f80b` も直接 update + `field_corrections` でロック済み。

**教訓**
- **Playwright が redirect 後の URL を `href` に反映することがある**：`page.goto(url)` 前にロケールプレフィックスを除去する。Peatix 以外でも `/en/`、`/us/`、`/jp/` 付き URL が `source_url` に混入しないかスクレイパーテスト時に確認する。
- **broken source_url の発見は user レポートに依存しがち**：`source_url` に `/us/`、`/en/`、`/jp/` が入っていないか dry-run ログで確認する習慣をつける。

---

## 2026-05-17 — `ftip`: WordPress RSS CDATA の `<a href>` が `.get_text()` で消え Peatix URL が未設定

**問題:** `scraper/sources/ftip.py` で Peatix URL が `official_url` / `source_url` に設定されなかった。ftip 記事ページには「Peatixからご購入」という記載はあったが、Peatix URL はプレインテキストではなく `<a href="https://xxx.peatix.com/...">` アンカーとして WordPress 記事本文（RSS CDATA）に埋め込まれていた。

**根本原因:** `content_html = content_el.get_text()` → `content_text = BeautifulSoup(content_html, "html.parser").get_text()` の二段階テキスト変換で `href` 属性が消える。既存の `_extract_peatix_url(content_text)` は正規表現でプレインテキストを検索するため URL を検出できなかった。

**修正:** `_extract_peatix_url_from_html(html_text)` を追加（commit `ee870f7`）。生の CDATA HTML 文字列（`content_html`）を BeautifulSoup で再パースし `find_all("a", href=True)` を走査。テキスト検索と HTML anchor 検索を OR で組み合わせ: `_extract_peatix_url(content_text) or _extract_peatix_url_from_html(content_html)`.

**教訓:** WordPress RSS CDATA にはリンクが `<a href>` として埋め込まれる。URL 抽出には `.get_text()` だけでなく、生 HTML 文字列を別途 BS4 でパースして `find_all("a", href=True)` を走査する関数が必要。テキスト検索と HTML 検索の両方を試みること。

---

## 2026-05-17 — `ftip`: `location_name` フォールバックに組織名定数を使用 → 会場欄に組織名が誤表示

**問題:** 会場抽出に失敗した全イベントで `location_name = "台湾原住民族との交流会"`（組織名）が設定されていた。event `eeb5b12e` では実際の会場「Coconeri３階 練馬区民・産業プラザ研修室１」ではなく組織名が会場として表示されていた。

**根本原因:** `LOCATION_NAME = "台湾原住民族との交流会"` 定数を venue フォールバックに使う設計。`location_name = venue_name if venue_name else LOCATION_NAME` というコードが原因。

**修正:** `location_name = venue_name if venue_name else None`（commit `278e6d8`）。

**教訓:** 組織名定数を `location_name` のフォールバックに使わない。会場が不明なら `None` を設定し、annotator や手動修正に委ねること。

---

## 2026-05-17 — Peatix: ロケール付き URL（/us/event/）が source_url に保存 → broken link（event e9c6f80b）

**根因：** Peatix group ページで取得した `<a href>` が `/us/event/{id}` 形式（ブラウザロケール起因のリダイレクト先）。`source_url=url` がそのまま保存されるため、ロケールプレフィックス付き URL が DB に入り 404 になる。

**教訓：**
- `_scrape_detail()` 入口で `re.sub(r"^(https://peatix\.com)/[a-z]{2}/event/", r"\1/event/", url)` を実行し、ロケールプレフィックスを除去してから `page.goto()` する。
- Peatix に限らず、ロケール別 URL（`/en/`、`/us/`、`/jp/`）が `source_url` に混入していないかスクレイパーテスト時に確認。

---

## 2026-05-16 — `wuext_waseda` 多重セッション講座: `performer` が片假名+漢字複合名で截斷 + `business_hours` 不完整

**問題：** event `1be67e0f-36a3-4299-b178-9a6f13de98ee`（沖縄現場学, source=wuext_waseda）で 2 つの不具合：
1. `performer` = `吉田`（截斷）。本来は `カベルナリア 吉田`（片假名筆名 + 漢字姓）。
2. `business_hours` = `19:00〜20:30`（曜日・全N回・個別開講日が脱落）。詳細頁の `(日程詳細) 07/09, 07/16, 07/23, 07/30, 08/20, 08/27, 09/03` から構成すべき。

**根本原因：**
1. `scraper/sources/wuext_waseda.py` が `Event.performer=` を設定していなかった。Annotator の `_PERFORMER_INTRO_RE` は `[\u4e00-\u9fff]{2,5}` 純漢字パターンを使うため、`カベルナリア 吉田` は漢字部分 `吉田` のみ抽出されて DB に書き込まれた。
2. Scraper が `business_hours=` を設定していなかった。Annotator は単一の時間範囲（`19:00〜20:30`）しか抽出できず、曜日・全7回・跳週日付（08/06, 08/13 抜け）を保存できない。

**修正：**
1. `wuext_waseda.py` に `_SESSION_DATES_RE`、`_WEEKDAY_LISTING_RE`、`_KAISU_RE` regex と `_build_business_hours()` helper を追加。`Event(performer=instructor, performers=[instructor], business_hours=bh, ...)` を構造化欄から直接設定。
2. DB 直接 fix（`scraper/_oneoff_*` 不要、admin が手動で行う）。`field_corrections` で `performer` / `performers` / `business_hours` 3 件 lock。

**Lesson：**
- **Annotator の regex は構造化フィールドの代替ではない。** Source page に instructor / 講師 / 登壇者 / 時間表 のような structured field があるなら、scraper で `Event(...)` に直接設定。Annotator は raw text からの fallback 抽出のみ。
- 多重セッション講座（wuext_waseda、asahiculture 等）は `business_hours` を scraper で組み立てる必要がある。曜日 + 時間範囲 + 全N回 + 個別開講日逐項列出 を含める。

---

## 2026-05-16 — `tokyoartbeat` aggregator が `official_url=source_url` フォールバックでイベント詳細ページの「公式サイト」リンクを汚染

**問題：** event `74ee6d89`（共時的星叢―時を共にした星たち　越境する芸術のまなざし）の `official_url` が `https://www.tokyoartbeat.com/events/-/Synchronic-Constellation-...`（aggregator 自身）になっており、UI の「公式サイト」ボタンが東京都現代美術館の展覧会ページではなく tokyoartbeat に戻ってしまっていた。

**根本原因：** `scraper/sources/tokyoartbeat.py` line 124 の `or source_url` フォールバック。Contentful CMS の `showsWebpage` フィールドが空のとき、`official_url = source_url` となり tokyoartbeat URL に汚染される。

```python
# ❌ 汚染源
official_url = (
    self._loc(f.get("showsWebpage", {}), "en-US")
    or self._loc(f.get("showsWebpage", {}), "ja-JP")
    or source_url  # ← aggregator URL に汚染
)
```

**修復：**
1. DB レベル — event `74ee6d89` の `official_url` を `https://www.mot-art-museum.jp/exhibitions/Constellation/#section1` に修正し `field_corrections` にロック
2. scraper レベル — `or source_url` を `or None` に変更（aggregator は first-party ではないため null が正しい）
3. SKILL.md — 既存の「聚合站 scraper」ルールに `or source_url` フォールバックを「反パターンの第二形（CMS / API 系 aggregator 用）」として追記

**教訓：**
- Aggregator scraper（tokyoartbeat、peatix、doorkeeper、connpass、eplus、livepocket、kokuchpro 等）は **`source_url ≠ official_url`** が原則。CMS フィールドが空のときは `or None` でフォールバックを止め、annotator や手動 enrichment に委ねる。
- First-party scraper（taiwan_cultural_center、taiwan_matsuri、koryu、asahiculture、各シネマ等）は `official_url=url` / `official_url=detail_link` を明示的に設定してよい——`source_url` 自体が主催者の公式ページだから。
- 監査コマンド：`grep -rn "official_url.*or source_url\|official_url=source_url" scraper/sources/` → 0 件であるべき。

---

## 2026-05-15 — annotator が静的会場データを上書き → `database.py` に `_auto_lock_location()` を追加（commit `435d68a`）

**問題：** `cinemaclair`・`ks_cinema`・`hakusuisha` など固定会場を持つ cinema scraper では、`Event(location_name=..., location_address=...)` をスクレイパーが正確に設定していても、annotator 再実行時に GPT が `location_name` を書き換えることがあった（例：`シネマ・クレール` → `岡山市`）。

**根本原因：** 新規イベントが `upsert_events()` で挿入された後、`field_corrections` にロックレコードが存在しなかったため、annotator の `_ai_or_existing()` が DB 値を null とみなして上書きした。

**修復（commit `435d68a`）：** `database.py` に `_auto_lock_location(client, eid_to_event)` helper を追加。`upsert_events()` が新規イベントを挿入した直後に呼ばれ、`location_name`・`location_address`・`location_prefectures` を `field_corrections` に `ignore_duplicates=True`（DO NOTHING on conflict）で自動挿入する。既存イベントには影響しない。

**教訓：**
1. **固定会場 scraper は新規挿入時に自動ロックされる**：`location_name` を持つ新規イベントは `upsert_events()` 経由で挿入されると同時に FC にロックされる。手動 `field_corrections` 挿入は不要。
2. **既存イベントへの適用は手動**：既存イベントは自動ロックされない。`field_corrections` に手動挿入するか、`_lock_fields_via_corrections()` を使う。
3. **`ignore_duplicates=True` パターン**：FC upsert は常に DO NOTHING on conflict にする。既存の管理者修正値を上書きしないためのセーフガード。

---

## 2026-05-15 — cinemaclair: GPT-4o Vision OCR でスケジュール画像から上映時刻を取得（commit `33dc715`）

**背景：** シネマ・クレールの上映時刻は HTML に存在せず週次 JPEG スケジュール画像にのみ記載されている。通常の BeautifulSoup パースでは `business_hours` を取得できなかった。

**解決パターン（2-pass scrape + Vision OCR）：**
1. **1st pass**: 上映中台湾映画の候補を収集（`candidates` リスト）
2. **OCR step**: `_fetch_schedule_image_url()` でスケジュールページから週次 JPEG URL を動的取得 → `_ocr_schedule_showtimes(image_url, taiwan_titles)` で GPT-4o Vision に JSON 返答を要求 → `{title: "HH:MM / HH:MM"}` dict を返す
3. **2nd pass**: `_match_schedule(schedule_map, title)` で完全一致→部分一致の順でマッチング → `Event()` 生成

**Graceful fallback：** `OPENAI_API_KEY` 未設定時・例外時は `{}` を返し、`business_hours` は `NULL`（または `１週間限定上映` ラベルのフォールバック）になる。CI が Vision API なしでも動作する。

**コスト：** gpt-4o Vision 1回/実行 ≈ \$0.005/日。

**教訓：**
1. **HTML にない情報は Vision OCR で取得できる**：スケジュール画像・海報・掲示板など。2-pass パターン（候補収集 → OCR 1回 → Event 生成）でバッチコストを最小化する。
2. **Vision OCR は常に graceful fallback 付きで実装**：`OPENAI_API_KEY` 未設定時は `{}` を返す。例外を握り潰す（`except Exception: return {}`）のが正しいパターン。
3. **週次変更 URL は動的取得**：`_SCHEDULE_URL` を HTML パースして最新 JPEG href を取得する。ハードコードした URL は週替わりで 404 になる。

---

## 2026-05-15 — `lookup_movie_titles()` の戻り値が 2-tuple から 3-tuple に変更 → 16 call site で `ValueError` 発生（commit `c8bf85d`）

**問題：** `lookup_movie_titles(name_ja)` の返り値が `(name_zh, name_en)` 2-tuple から `(name_zh, name_en, official_url)` 3-tuple に変更された。既存の 13 ファイル・16 call site がすべて `a, b = lookup_movie_titles(...)` のまま残っており、実行時に `ValueError: too many values to unpack (expected 2)` が発生した。

**影響：** CinemartShinjuku, UplinkCinema, ShinBungeiza, CineMarine, GguideTV, RightsCube, CineswitchGinza, HumanTrustCinema, Johakyu, KsCinema, MorcAsagaya, TtcgKansai（12 scraper + eurospace logger 修正）。

**修復（commit `c8bf85d`）：** 全 16 call site を `a, b, _ = lookup_movie_titles(...)` に一括更新。`eurospace.py` の `self.logger` → モジュール level `logger` も同時修正。

**教訓：**
1. **`lookup_movie_titles()` の戻り値は 3-tuple `(name_zh, name_en, official_url)`**：`official_url` が不要な場合は `name_zh, name_en, _ = lookup_movie_titles(name_ja)` と書く。
2. **API signature 変更時は全 call site を同一 commit で一括更新する**。`grep -rn "lookup_movie_titles" scraper/sources/` で全件確認してから変更する。
3. **`official_url` は `lookup_movie_titles()` から自動取得できる**：eiga.com で映画が見つかった場合、その映画ページ URL が `official_url` として返される。scraper で `official_url=url` を別途取得する手間が省ける。

---

## 2026-05-15 — 電影院 scraper に `organizer` 未設定で admin イベントカードに場所名が表示されない（cinemaclair / human_trust_cinema）

**問題：** admin イベント一覧で `cinemaclair`（シネマ・クレール）や `human_trust_cinema`（ヒューマントラストシネマ有楽町）のイベントに対し、event card 内に 🏢 venue 行が表示されず、`kyoto_cinema`（🏢 京都シネマ表示）と比較して「場所なし」に見えた。

**根因：** `cinemaclair.py` と `human_trust_cinema.py` が `Event()` 生成時に `organizer=` を設定していなかった。`AdminEventTable` の event card は `organizer` フィールドを使って 🏢 行を表示する。`location_name` は venue column（右端 td）では表示されるが、event card 内には表示されない。一方 `kyoto_cinema.py`・`kino_shinsaibashi.py`・`sakurazaka.py` はいずれも `organizer=` を設定済みだったため表示されていた。

**修復：**
- `cinemaclair.py`: `organizer="シネマ・クレール"`, `organizer_type=["commercial_brand"]` 追加（commit `b7243a6` で実施済み）
- `human_trust_cinema.py`: `organizer="ヒューマントラストシネマ有楽町"`, `organizer_type=["commercial_brand"]` 追加

**教訓：**
1. **専用施設（映画館・劇場・ギャラリー等）の固定会場 scraper は必ず `organizer=` と `organizer_type=["commercial_brand"]` を設定する。** `location_name` は DB に保存されるが admin event card には表示されない。`organizer` が venue name の唯一の card 内表示手段。
2. **新規 scraper の動作確認チェックリスト**: `--dry-run` 結果に `organizer` フィールドが含まれているかを確認する。`location_name` が設定されていても admin UI 上で「場所なし」に見えることがある。
3. **参照 scraper**: `kyoto_cinema.py`・`kino_shinsaibashi.py`・`sakurazaka.py` は正しいパターンの例。

---

## 2026-05-15 — tsutaya_portal: span.place が venue 名に化ける + end_date 年なしパース失敗（event 7b37604e）

**問題 A — location_name に店内エリア名が入る**
イベントページの `div.date > span.place` には「スターバックス横平台」（店内の棚エリア名）が格納されていた。スクレイパーはこれを `location_name` として採用し、`card_store`（genre span から取得した「六本松 蔦屋書店」）へフォールバックしなかった。

**問題 B — end_date が start_date と同日になる**
詳細ページの `div.date` テキスト「2026年05月08日(金) - 06月07日(日)」において、end_date の「06月07日」は年を含まない。`_DETAIL_DATE_RE`（年必須パターン）のみでは 1 件しかマッチせず `end = start` になっていた。

**修復（commit 5f247c1）**
- `_DETAIL_END_DATE_SHORT_RE = re.compile(r"-\s*(\d{1,2})月(\d{1,2})日")` を追加、start_date の年から補完して end_date を算出。
- `location_name = card_store or location_name or None` — store 名を常に優先、`span.place`（店内エリア名）は venue として使わない。
- DB 手動修正（end_date / location_name / location_address を 3 件 FC ロック済み）

**教訓**
1. **詳細ページの「場所」フィールドは venue 名ではなく店内エリア名の場合がある**：`span.place` を `location_name` に使う前に、それが建物名（「〇〇 蔦屋書店」）か店内エリア名（「スターバックス横平台」）かを確認する。蔦屋書店系サイトでは genre span の店名（`card_store`）を優先するのが正しい。
2. **年なし end_date は short regex で補完する**：`YYYY年MM月DD日 - MM月DD日` 形式（年省略）は蔦屋書店ポータルでよく出現する。`start_date.year` から補完し、`end_month < start_month` の場合は翌年として処理する。

---

## 2026-05-15 — 台湾映画イベントの片名・人名 3 重誤り（cinemaclair 莎莉/Salli）

**イベント**: `6a0dbfb3` cinemaclair — 映画「サリー」（2023 年台湾）

**問題 A — 片名の誤り（薩莉 → 莎莉 / Sally → Salli）**

scraper が eiga.com に登録のない台湾映画を処理した際、GPT が漢字片名と英語片名を誤生成した。
- `name_zh = '薩莉'`（誤）→ `'莎莉'`（正）
- `name_en = 'Sally'`（誤）→ `'Salli'`（正）
- `works.title_zh`, `works.title_en`, `description_zh/en` も同様に誤り

**問題 B — 導演名の誤り（連建宏 → 練建宏 / Chien-hong → Chien-hung）**

導演名の漢字が 1 文字違い（`連` vs `練`）、ローマ字も誤り。
- `director_zh = '連建宏'`（誤）→ `'練建宏'`（正）
- `director_en = 'Lien Chien-hong'`（誤）→ `'Lien Chien-hung'`（正）
- `works.director` も同様

**問題 C — performers_zh[0] が片假名音訳（艾絲特·劉 → 劉品言）**

annotator が `performers[]` の片假名 `エスター・リウ` を機械的に音訳して `performers_zh[0] = '艾絲特·劉'` とした。エスター・リウの本名 `劉品言` とは一致しない。

**発覚経緯**: 金馬獎（GHFF）公式ページ `goldenhorse.org.tw/film/about/archive/detail/3913` を参照。

**修正**:
- `events`: `name_zh`, `name_en`, `director_zh`, `director_en`, `description_zh`, `description_en` 修正
- `works`: `original_title`, `title_zh`, `title_en`, `director` 修正
- `performers_zh[0]`: `'艾絲特·劉'` → `'劉品言'`
- `field_corrections` で 4 フィールド FC lock（re-annotation 上書き防止）

**規則**:
1. **台湾映画の権威ソース優先順位: GHFF > eiga.com > GPT**。金馬獎ページには正式な中文・英文片名と監督名が記載される。eiga.com に登録のない台湾映画は必ず GHFF を確認する。
2. **performers_zh[] は片假名音訳禁止**。エスター・リウ(`エスター・リウ`) → `艾絲特·劉` は機械音訳であり本名ではない。`_KNOWN_PERSON_MAP` に登録するか GHFF/eiga.com で本名を確認してから設定する。
3. **漢字 1 文字違いの人名を GPT に信頼しない**。`練建宏` vs `連建宏` のような近似漢字の誤りは視覚的に気づきにくい。人名は必ず信頼ソースで確認する。
4. **works 作成時は description_zh/en 内の片名参照も同時修正する**。`name_zh` だけ修正すると説明文内に旧片名が残る。

---

（セパレーター量詞 `*`→`+` / `get_text("\n")` 切替）

**A. `場所` キーワードが本文の一般名詞にマッチ（量詞 `*` → `+` 修正）**

**問題：** `_VENUE_RE = re.compile(r"(?:会場|場所|開催場所)[　\s：:]*([^\n]{3,60})")` が、文章中の「自由と多様性を称揚する**場所**」にマッチし、`location_name` が `」となるまでには、長く険しい道があったのです。 台湾の高校、そして...` というゴミテキストになった。

**根因：** `[　\s：:]*`（0 回以上）はセパレーターなしでもマッチする。`場所` の直後が `」` であっても通過し、後続 60 文字を venue として取得してしまう。

**修復：** `[　\s：:]*` → `[　\s：:]+`（1 回以上必須）。セパレーターのない `場所」` 形式はマッチしなくなる。

```python
# BEFORE (wrong)
_VENUE_RE = re.compile(r"(?:会場|場所|開催場所)[　\s：:]*([^\n]{3,60})")
# AFTER (correct)
_VENUE_RE = re.compile(r"(?:会場|場所|開催場所)[　\s：:]+([^\n]{3,60})")
```

**教訓：** venue / 日時ラベル後のセパレーター文字クラスは `+`（必須）で書く。`*` を使うと本文中の同名の一般名詞にマッチする。

**B. `get_text(" ")` で会場名にプログラム情報が混入**

**問題：** `+` 修正後も `location_name` が `早稲田大学早稲田キャンパス 3号館305教室 プログラム 司会　許仁碩（北海道大学 助教） 14:00-14:15　趣旨` となり、会場名以降のプログラム情報が混入した。

**根因：** `soup.get_text(" ", strip=True)` は HTML の全ブロックをスペース区切りで 1 行に結合する。会場行と次のセクションの間に改行がなく、`[^\n]{3,60}` が 60 文字まで取り込んでしまう。

**修復：** 会場抽出用に改行区切りのテキストを別途取得する：

```python
full_text    = soup.get_text(" ",  strip=True).replace("\x00", "")  # 既存（日付等）
full_text_nl = soup.get_text("\n", strip=True).replace("\x00", "")  # NEW（venue 専用）

mv = _VENUE_RE.search(full_text_nl)  # [^\n] がブロック境界で停止
```

**教訓：**
- `[^\n]` を使う regex の検索テキストには改行が必要 → `get_text("\n")` を使う。
- `get_text(" ")` は日付・概要など改行不要な場合に使い、構造依存の抽出（venue・日時）では `get_text("\n")` を使うこと。
- 二つのバリアントを変数として保持するのが安全：`full_text`（スペース区切り）と `full_text_nl`（改行区切り）。

---

## 2026-05-15 — annotator.py に `結果発表` パターンを追加 + `_inject_report_prefix` の ja 二重括弧バグを修正（commit `d0eb93e`）

**問題：** `【結果発表】台湾教育旅行プランニング大賞2023`（event `83f0723a`）が `report` カテゴリに分類されず、通常の学術イベントとして表示されていた。また、既存の `_inject_report_prefix` は ja 名称がすでに `【...】` で始まっていても `【レポート】` を前置し、`【レポート】【結果発表】xxx` という二重括弧を生成していた。

**根因：** `_REPORT_TRIGGER_RE` に `結果発表` が含まれていなかった。`_inject_report_prefix` は `name.startswith(p)` のみチェックし、`p = 【レポート】` 以外の任意の `【...】` 前置を考慮していなかった。

**修復（commit `d0eb93e`）：**
1. `_REPORT_TRIGGER_RE` に `結果発表` を追加 — 今後の re-annotation で自動的に `report` カテゴリが付与される。
2. `_inject_report_prefix` に `lang == "ja" and name.startswith("【")` ガードを追加 — ja 名称がすでに任意の `【...】` で始まる場合は prefix を注入しない。
3. Follow-up 作業：Supabase SQL で `raw_title LIKE '%結果発表%'` の既存 events に `report` を追加し、`python annotator.py --backfill-report-prefix` で name 接頭辞を注入。

**教訓：**
- `report` カテゴリの自動注入範囲を拡張する際は `_REPORT_TRIGGER_RE` を更新する（レポート・レポ・報告・記録・アーカイブ・recap・行ってきた・観てきた・見てきた・鑑賞レポ・**結果発表**）。
- `_inject_report_prefix` は「このプレフィックスで始まるか」だけでなく「任意の `【...】` ブラケット接頭辞がすでにあるか」も確認すること。単純な `startswith(p)` では不十分。
- 既存の annotated events は annotator の自動フローでは更新されない。バルク修正には Supabase SQL + `--backfill-report-prefix` を組み合わせる。

---

## 2026-05-15 — annotator が講座イベントに performers=['記'] を誤設定（手動 DB 修正）

**問題：** asahiculture イベント `1334fc96`（村山秀太郎講師の台湾現代史講座）で `performers=['記']`・`performer_zh='記'`・`performer_en='Ki'` という誤値が存在。`performer='村山 秀太郎'`（FC 済み）は正しいのに `performers[]` が単一漢字「記」で汚染されていた。

**根因：** annotator の GPT（または `enrich_person_names()` の B1 ロジック）が `performer` フィールドから `performers[]` を導出する際、テキスト断片の単一文字「記」を performer 名と誤解析した。その後 `enrich_person_names()` がその誤値をそのまま翻訳し `performer_zh='記'` → `performer_en='Ki'` になった。

**修復（手動 DB 修正、2026-05-15）：**
```python
EID = '1334fc96-6dac-4862-afbb-6b95b78c1abc'
updates = {
    'performers':   ['村山 秀太郎'],
    'performer_zh': '村山秀太郎',      # 中国語表記：スペースなし
    'performer_en': 'Murayama Hidetaro',  # ローマ字：姓→名順
}
sb.table('events').update(updates).eq('id', EID).execute()
# + field_corrections FC lock（3フィールド全て）
```

**教訓：**
- `performers[]` に単一漢字・単一記号が含まれる場合は annotator の誤解析シグナル。現行 `auto_qa_performer_multi_value_pollution` は検出しない（1 要素のため）。
- 手動修正パターン：`performer` FC が正しい → `performers[0]` に sync → `performer_zh/en` はソース確認後に設定。
  - 日本人名の Chinese 表記：漢字そのまま、スペースなし（例：`村山秀太郎`）
  - 日本人名の English 表記：ローマ字、姓→名順（例：`Murayama Hidetaro`）
- 修正後は必ず `field_corrections` FC ロックを 3 フィールド（`performers`, `performer_zh`, `performer_en`）に適用する。

---

## 2026-05-15 — `event_form="film_screening"` 誤設定 revert（DB constraint 不存在）

**問題**: Cinema scraper 全稽核修復シリーズで `event_form=["film_screening"]` を4ファイルに設定したが、DB check constraint（migration 047）に `"film_screening"` は存在しない。有効値は `"screening"`。次回 CI 実行時に constraint エラーで upsert が全件失敗するところだった。

**根本原因**: SKILL.md に「`"screening"` は無効値 → `"film_screening"` が正解」と誤記した。実際の constraint を確認せずに文書化・実装した。

**発覚経緯**: cinemaclair イベント `6a0dbfb3` の performers_zh 修正時に `film_screening` で UPDATE を試みたところ `events_event_form_check` constraint エラーが返った。

**修正**:
- `human_trust_cinema.py`, `sakurazaka.py`, `kino_shinsaibashi.py`, `kyoto_cinema.py`: `["film_screening"]` → `["screening"]`
- `SKILL.md § 共通禁止事項 #5`: 誤記を訂正（`film_screening` → `screening`）
- `engineer.agent.md rule #10`: 同様に訂正

**教訓**: event_form の valid 値を変更・追加する場合は必ず migration 047 の check constraint を確認すること。SKILL.md に valid 値を明記して constraint 一覧と照合する。

---

## 2026-05-15 — Cinema scraper 全稽核修復シリーズ（13 scraper、4コミット）

**問題**: Cinema scraper 稽核表の作成後、実際の修復作業を実施。13個の scraper が UTC datetime 未対応・`event_form` 未設定・SINGLE-DAY RULE 未防護のいずれか（または複数）の問題を抱えていた。

**修復コミット**:
- `23e417f`: ks_cinema — `business_hours` 提取追加
- `544bbc4`: cinemadict UTC + business_hours / kino_shinsaibashi `film_screening` + prefix
- `e91f5cd`: 9 scraper 一括 — event_form×2（`"screening"` → `"film_screening"`）、SINGLE-DAY RULE prefix×3、UTC×7
- `7849021`: human_trust_cinema UTC + SINGLE-DAY RULE 防護 + event_form

**発見した bug パターン**:
1. **`event_form=["screening"]` 無効値**: `kyoto_cinema`・`sakurazaka`・`kino_shinsaibashi` が `"screening"` を使用。有効値は `"film_screening"`。DB check constraint エラーを引き起こす。
2. **naive datetime（UTC 未設定）**: 7ファイルで `datetime(y, m, d)` が naive。一般規則はあったが cinema scraper では徹底されていなかった。
3. **JST ISO datetime 誤変換**: `human_trust_cinema` が `.replace("+09:00", "")` で naive datetime を生成。正解: `datetime.fromisoformat(data_date)` → JST-aware → `datetime(y, m, d, tzinfo=timezone.utc)`。
4. **Type 3 SINGLE-DAY RULE 誤発動**: `end_date=None`（サイト情報なし）のとき、`raw_description` に単日付 prefix を入れると annotator が `end_date=start_date` に設定する。Type 3 で end_date 取得不可の場合は date prefix を入れない。start_date はフィールドに格納済みなので raw_description に繰り返す必要はない。
5. **稽核表の ghost エントリ**: `ciemarine` がファイル不存在なのに稽核表に記載されていた → 削除。

**規則（→ SKILL.md § Cinema scraper 共通禁止事項に追加）**:
- 全 cinema scraper は `event_form=["film_screening"]` 必須（`"screening"` は無効）
- Type 3 で end_date 取得不可の場合、raw_description に単日付 prefix を入れない
- JST ISO datetime: `.replace("+09:00", "")` パターン禁止 → fromisoformat + UTC midnight 変換
- 稽核表に新行追加前に `ls scraper/sources/<name>.py` でファイル存在を確認する

---

## 2026-05-15 — Cinema scraper `end_date` / `business_hours` 全体標準化（稽核表作成）

**問題**: 18個の cinema scraper のうち完全準拠は3個のみ（cinemart_shinjuku, shin_bungeiza, starcat_cinema）。15個が `business_hours = None` で、1個（human_trust_cinema）は `end_date` も None。

**根本原因**: `business_hours` と `end_date` の実装基準が文書化されておらず、新規 scraper 作成時の標準として伝達されていなかった。

**修正（commit `e24023c` + 今次 commit）**:
1. SKILL.md の重複セクション（`## Cinema scraper — business_hours`）を削除・統合
2. 3タイプ分類（Type 1: 票務平台分離型 / Type 2: 排片表嵌入型 / Type 3: 上映中リスト型）を定義
3. 共通禁止事項（`end_date=start_date`, 空 `business_hours=""`, 推測 `end_date`）を明記
4. annotator SINGLE-DAY RULE 防護規則（`raw_description` 前綴に期間範囲必須）を追記
5. 18 scraper 稽核表を SKILL.md に追加（新規 scraper 作成時に更新義務）
6. `engineer.agent.md` に Cinema scraper rule #10 を追加（3タイプ要約 + SKILL.md 参照）

**要対応リスト（`business_hours = None`）**:
ks_cinema, kino_shinsaibashi, kyoto_cinema, cineswitch_ginza, theater_enya, cinewind, ciema, cinemadict, ycam_cinema, sakurazaka, ciemarine, uedaeigeki, theater_kino

**緊急対応（`end_date = None` かつ `business_hours = None`）**:
- human_trust_cinema: TTCG CMS からの場次取得方法を調査必要

**規則**: Cinema scraper は Type 1/2/3 に従い `end_date` + `business_hours` を実装すること。新規作成時は SKILL.md § Cinema scraper 完全規則 + 稽核表を必ず参照。

---

## 2026-05-15 — starcat_cinema end_date 錯誤（SINGLE-DAY RULE 覆寫）

**問題：** `end_date = start_date`（兩者均為 2026-05-15）。電影實際上映至 5/21（木），但 annotator SINGLE-DAY RULE 把 end_date 覆寫成開始日。

**根本原因：**
1. scraper 設 `end_date=None` → annotator GPT 讀 raw_description 中的「2026年5月15日(金)より公開」 → 只有單一日期 → SINGLE-DAY RULE → `end_date = start_date`
2. scraper 沒有實作從票務排片推導 end_date 的邏輯

**修正（commit `3b40cb5`）：**
- `_build_ticket_schedule()` 改回傳 `(business_hours_str, last_date_utc)` tuple
- 新增 `_lookup_schedule_entry()` / `_lookup_end_date()` helpers
- `scrape()` 從 ticket schedule 最後一日取 `end_date`（= 當週木曜）
- `raw_description` 前綴改為「上映期間: YYYY年M月D日〜YYYY年M月D日」— 防止 annotator SINGLE-DAY RULE 覆寫
- `_parse_date()` 加 `tzinfo=timezone.utc`

**規則：** 日本電影院每週四公布排片（金曜〜木曜）。Cinema scraper 必須從票務 schedule 取 `last_dt` 作為 `end_date`，並在 `raw_description` 前綴中同時標明開始與結束日期。→ 新增至 SKILL.md § Cinema scraper — `end_date` 每週排片末日（木曜）規則

---

## 2026-05-15 — asahiculture 4 欄位同時抓錯（venue / end_date / performer / organizer）

**根本原因分析（事件 `asahiculture_8759178`，立川サテライト教室）：**

### A — `location_name` 讀搜尋卡片 branch，非實際場地
搜尋結果 `li.text-school` 顯示**行政管轄教室**（新宿教室），而衛星課程的實際場地（立川サテライト教室）只在 detail 頁`備考`表格以`「会場名」`括弧呈現。爬蟲直接用 card branch，導致 `location_name` 永遠是管理端教室。
**修正：** `_fetch_detail()` 讀 `備考` `th/td` row，以 `r"「([^」]+)」"` 提取真實場地；fallback 才使用 card branch。

### B — `end_date` 只取第一個日期（`re.search`）
`_parse_date()` 用 `re.search()` 只回傳第一個 match。`2026/04/07火～2026/06/16火` 兩個完整日期，只抓 `04/07`，`06/16` 永遠遺失。
**修正：** 替換為 `_parse_date_range()`，用 `re.findall()` 取所有日期，`[0]` 為 `start_date`，`[-1]` 為 `end_date`。

### C — `performer` 被「台湾キーワード」篩選遮蔽
`_fetch_detail_description()` 只撈含「台湾/Taiwan」的 `<p>` 段落。講師介紹區塊（`<h3>` heading）不含台灣關鍵字，完全被略過。annotator 後來從 `raw_description` 結尾的「（講師・記）」截出「記」作為 performer。
**修正：** `_fetch_detail()` 獨立掃所有 `<h3>`，用漢字姓名 regex `r"([\u4e00-\u9fff]{1,6}[\s\u3000]+[\u4e00-\u9fff]{1,6})[\s\u3000]*[（(]"` 提取姓名。

### D — `organizer` 從未提取
爬蟲完全沒有 organizer 提取邏輯，交給 annotator 推斷，annotator 缺線索也留 None。
**修正：** 加入模組級常數 `ORGANIZER = "朝日カルチャーセンター"`，Event constructor 直接設定。

**修正 commit：** `da3ac31`

---

## 2026-05-15 — tsutaya_portal: span.place 店内エリア名 + end_date 年なしパース失敗

**根因（2件）：**
1. `div.date > span.place` は店内棚エリア名（例: 「スターバックス横平台」）で、venue 名ではない。`card_store`（genre span）が正しい店名だが、`span.place` が存在すると card_store にフォールバックしなかった。
2. `YYYY年MM月DD日 - MM月DD日`（end-date に年なし）形式を `_DETAIL_DATE_RE`（年必須）で検出できず `end = start` になった。

**教訓：**
- 蔦屋書店系サイトでは `card_store`（genre span）を `location_name` に優先し、`span.place` は venue として使わない。
- 年省略 end-date は `_DETAIL_END_DATE_SHORT_RE` で捕捉し `start_date.year` から補完（end_month < start_month なら翌年）。

---

## 2026-05-15 — 台湾文化センター海報 OCR で co_organizer 発見 + location_name 幻覚修正（剪花・綻放 切り絵展）

**問題：** イベント `dbfac7c9`（剪花・綻放 切り絵アート展）の `location_name` が `東京・京都`（誤）、`co_organizers` が空。

**根因（2件）：**
1. **location_name 幻覚**：annotator GPT が東京のみの TCC 会場を `東京・京都` と誤設定。`raw_description` に「台湾文化センター(東京都港区虎ノ門1-1-12 2階)」と明記されているにも関わらず、GPT が京都を付け加えた（ツアー展の記憶汚染と推定）。
2. **co_organizers 欠落**：`共催：遼江市政府` と `企画運営：日青創藝有限公司` は海報画像（`image_url`）にしか記載されておらず、HTML テキストには `主催：台湾文化センター` のみ → annotator は HTML テキストしか参照しないため空になる。

**修復（直接 DB update）：**
- GPT-4o Vision で `image_url` の海報 JPEG を OCR → `co_organizers=['遼江市政府']`、`sponsors=['日青創藝有限公司']`、`image_url` を設定
- `location_name='台湾文化センター'` に修正（`location_name_zh`、`location_name_en` も修正）
- 6 フィールドを `field_corrections` にロック（再 annotation で上書きされない）

**教訓：**
- **TCC（台湾文化センター）の `location_name` は annotator が稀に幻覚する**。`東京・京都` は TCC の典型的な誤設定パターン（ツアー展記憶の汚染）。`raw_description` に京都への言及がないのに `location_name` に京都が入っていれば幻覚を疑う。
- **海報画像（`image_url`）は共催者情報の最終参照元**。HTML テキストに `共催:` がなくても海報には記載されることが多い。admin OCR フロー（GPT-4o Vision）で `image_url` を OCR すれば、スクレイパーが取れない共催者・企画運営を補完できる。
- **修正後は必ず `field_corrections` にロック**。`co_organizers`、`sponsors`、`location_name` は re-annotation で上書きされる可能性がある。`field_corrections` にロックすることで annotator の上書きを防ぐ。

---

## 2026-05-15 — asahiculture オンライン受講コースに物理住所が入る

**問題：** `台湾映画最前線2026（オンライン受講）` (d617e8c4) の `location_name = 川西教室`、`location_address = 〒666-0033 川西市栄町25-1 アステ川西3階` — 物理住所が FC ロックされていた。

**根因：** `scrape_card()` 内の location 解決ロジックが `CLASSROOM_ADDRESS_MAP.get(location_name)` で川西教室の住所を補填。raw_title に「（オンライン受講）」と明記されているが、スクレイパーがそれを見ていなかった。

**修正：**
- `asahiculture.py` scrape_card() に「オンライン」検出を追加：
  ```python
  _is_online = "オンライン" in raw_title or "オンライン" in (detail["location_name"] or "")
  if _is_online:
      location_name, location_address = "オンライン", None
  else:
      location_name = detail["location_name"] or card_branch
      location_address = detail["location_address"] or CLASSROOM_ADDRESS_MAP.get(location_name)
  ```
- DB: `location_name='オンライン'`, `location_address=None`, `location_name_zh='線上'`, `location_name_en='Online'`, `location_prefectures=None` に更新。
- FC: 旧 `location_address` FC を削除し、5 フィールド全て FC ロック。

**教訓：** **課程タイトルに「オンライン」が含まれる場合、物理的な教室情報より title が優先される。** 教室名・住所 MAP の前に title による `_is_online` チェックを挟むこと。この pattern は他の多教室型カルチャースクール scraper（shinjuku 系、hankyu 系など）にも適用可能。

---

## 2026-05-15 — iwafu.py `location_address` が取れない（公式サイト body_text 未活用）

**問題：** `屋台湾フェス2026 in 芝公園` (iwafu_1137442) の `location_address`・`location_prefectures` が共に `None` のまま入庫。DB に手動で `東京都港区芝公園3-2` を設定 + FC ロック済み。

**根因（3層）：**
1. **`_ADDR_RE` が都道府県プレフィックス必須** — iwafu ページの `場所：都立芝公園4号地（御成門駅前広場）` には住所がなく、公式サイトには `港区芝公園3-2`（`東京都` なし）があったが regex が不一致。
2. **公式サイトは既に fetch 済み**（`_fetch_official_organizer_info`）だが、`body_text` を返さずローカル変数で捨てていた。
3. **`_fetch_official_organizer_info` の戻り値が `(organizer, supplemental)` の 2-tuple** だったため、住所フォールバックとして再利用できなかった。

**修正（`scraper/sources/iwafu.py`）：**
- `_ADDR_RE`：都道府県プレフィックスを `(?:...)?`（省略可能）に変更、代わりに `[市区町村]` を必須アンカーに追加 → `港区芝公園3-2` がマッチするようになる。
- `_fetch_official_organizer_info`：戻り値を `(organizer, supplemental, body_text)` の 3-tuple に変更（全 return 箇所修正）。
- `_scrape_detail`：`place_m` マッチ後、`main_text` で住所が取れない場合に `official_body_text` をフォールバック検索するよう追加。

**教訓：**
- **公式サイトを fetch する scraper は、住所抽出のフォールバックとして `body_text` を保持すること。** iwafu 形式のイベントは公式サイトの方が詳細な住所を持つ場合が多い。
- **`_ADDR_RE` に都道府県のない住所（`港区...`、`中央区...`）が入ることは正常。** プレフィックスは省略可能にし、`[市区町村]` を必須アンカーとする。
- **正規表現の「必須プレフィックス」はサイレントミスの温床。** マッチしなくても例外を投げず `None` が入るだけなので、CI では気づきにくい。

---

## 2026-05-15 — matsumoto_cinema_select.py 建立後未同步登錄 main.py（Promotion Checklist 遺漏）

**問題：** `matsumoto_cinema_select.py` 建立並修正完畢，但 V-M-D 流程中 `git status` 顯示為 `??`（untracked），且 `scraper/main.py` 無對應 import 與 SCRAPERS 登錄。CI 無法執行此 scraper。

**根因：** 實作 matsumoto_cinema_select 時，session 聚焦在修正 3 個 dry-run 錯誤（class 名稱、回傳值解包、非法欄位），修正後直接結束 session，未執行 Promotion Checklist Step 2（main.py 登錄）與 Step 5（Combined Post-Build Audit）。

**修正：** V-M-D 流程中補齊 `scraper/main.py` import + `SCRAPERS` 登錄，確認 SCRAPERS audit ALL CLEAR 後一起 commit。

**教訓：**
- **Scraper 實作 session 結束前，必須確認 `git status` 中 `scraper/sources/` 無 `??` 未 tracked 檔案。** 若有，代表 Promotion Checklist 未完成。
- **`main.py` 登錄要和 scraper 檔案在同一個 commit**。分開 commit 會造成 CI 執行期間 import error。
- **每次 debug 循環（fix → dry-run）結束後，立即跑 SCRAPERS audit 確認登錄狀態**，不要等到 V-M-D 才發現。

---

## 2026-05-15 — starcat_cinema end_date 被 annotator SINGLE-DAY RULE 覆寫

**問題：** `starcat_cinema` 事件的 `end_date` 設為每週排片最後一天（木曜），但 annotator SINGLE-DAY RULE 將其覆寫為 `start_date`，導致存檔時所有事件都變成「單日活動」。

**根因：** annotator 的 `_get_end_date()` 邏輯中，SINGLE-DAY RULE 檢查 `description` 是否含「單日」關鍵詞，但 starcat `raw_description` 起始為 `"上映日: YYYY年M月D日"` (含空格，只標單日)，被誤判為單日活動。即使 `start_date != end_date`，RULE 也會強制覆寫 `end_date = start_date`。

**修正：**
1. `_build_ticket_schedule()` 改為回傳 tuple：`(business_hours_str, last_date_utc)`。
2. 新增 `_lookup_end_date()` helper，從 schedule 取得最後一天。
3. `_parse_date()` 加入 `tzinfo=timezone.utc`（符合 SKILL.md 規則）。
4. `raw_description` 前綴改為 `"上映期間: YYYY年M月D日〜YYYY年M月D日"` → annotator 不再誤判為單日。
5. `scrape()` 中 `Event()` 的 `end_date = _lookup_end_date(schedule, start_date)` 確保日期跨度。

**驗證：** `python main.py --dry-run --source starcat_cinema` 輸出顯示 `"start_date": "2026-05-19T00:00:00", "end_date": "2026-05-30T00:00:00"` ✅。

**教訓：**
- **scraper raw_description 的措辭會影響 annotator 決策：** 「上映日」(単日含意) vs 「上映期間」(期間含意) 的字眼差異導致 SINGLE-DAY RULE 觸發。
- **Scraper 改動時要考慮 annotator 層級的副作用：** 日期改動不只是改 code，還要確保 raw_description 前綴不會被 SINGLE-DAY RULE 誤判。
- **多日排片的 end_date 應由 scraper 負責取得，不應仰賴 annotator 推導：** annotator 的 SINGLE-DAY RULE 是為了處理資訊不足的情況，不能用來處理 scraper 本應產出的完整日期跨度。

---

## 2026-05-15 — matsumoto_cinema_select (teket.jp) 初回 dry-run 0 件 — sitemap timeout

**問題：** `matsumoto_cinema_select.py` の初回 dry-run で 0 件取得。サイトマップ fetch で `ReadTimeout` 発生。

**根因：** teket.jp の `sitemap.xml` は 34,000+ URL を含む大容量ファイルで、応答完了に 15〜20 秒かかる。`timeout=15` では完了前に打ち切られた。

**修正：** `requests.get(SITEMAP_URL, timeout=30)` に変更（15 → 30）。

**教訓：**
- **teket.jp sitemap.xml は timeout=30 以上を使うこと。** teket.jp の全プラットフォームイベントが詰まった大容量 sitemap のため、デフォルト 15s では失敗する。
- **サイトマップ取得 0 件 → 第一確認: timeout を 30s 以上に引き上げる。** その後エラーログで `ReadTimeout` を確認する。
- **teket.jp の `/api/events?group_id=` は使用不可**: group フィルタが無効で全プラットフォーム (34,000+ 件) を返す。グループ別列挙には sitemap.xml が唯一の手段。
- **teket.jp JSON-LD `description` はフェスタ名のみ**: 台湾フィルタを JSON-LD に適用しても無意味。full page text (script/style 除去後) に `2021年｜台湾｜カラー` / `台湾映画社` 等のキーワードが含まれる。
- **teket.jp JSON-LD `location.name` は常に `その他のホール`**: page title の `| venue` 部分または OG description の `[venue_name address]` ブラケットから取得する。

---

## 2026-05-15 — starcat_cinema business_hours 場次資訊需從 starcat-ticket.com 抓取

**問題：** `starcat_cinema.py` 爬取的事件缺少 `business_hours`（每日場次時間），無法讓使用者知道實際放映時刻。

**根因：** 台灣電影資訊（スターキャット・シネマ）主頁面不包含每週詳細場次，場次資料存放在 `starcat-ticket.com`（票務平台），需另外查詢。

**修正：**
1. 新增 `TICKET_SCHEDULE_URLS` dict，映射電影片名 → 票務頁面 URL。
2. `_build_ticket_schedule(url)` 從票務頁解析每日放映時段，回傳 `dict[date_str, list[time_str]]`。
3. `_lookup_business_hours(title, start_date, end_date)` 依日期範圍格式化成：
   ```
   5/15(金): 12:05〜13:49
   5/16(土): 12:05〜13:49
   …
   ```
4. `scrape()` 在建立 Event 時呼叫 `_lookup_business_hours()`，填入 `business_hours`。

**教訓：**
- **場次時間（business_hours）與主要活動資訊常分散在不同頁面**（主頁 vs 票務平台）。實作時需判斷主頁是否含場次，若無則需額外爬取票務頁。
- `TICKET_SCHEDULE_URLS` 應作為 scraper 內的 dict，避免每次 dry-run 都重新 fetch 票務頁（可考慮加 TTL cache）。
- `business_hours` 格式統一為 `M/DD(曜): HH:MM〜HH:MM`，多天用 `\n` 分隔。

---

## 2026-05-14 — rti_jp.py dry-run で 0 件（RSS `&amp;` 二重エンコード）

**問題：** `rti_jp` の dry-run が RSS フェッチ成功（HTTP 200）にも関わらず常に 0 件。DEBUG ログで全 3 番組が 200 OK を受信していることは確認済み。

**根因：** RSS の `<link>` テキストノードが HTML エンティティ `&amp;` を保持したまま配信されていた。例:
```
<link>https://www.rti.org.tw/jp/programnews?uid=4&amp;pid=103701</link>
```
`xml.etree.ElementTree` は XML パース時に `&amp;` → `&` を復元するが、実際に配信されていたのは既に `&amp;` がリテラル文字列として埋め込まれた二重エンコード状態だった。つまり `.text` は `"...&amp;pid=103701"` を返す。`_extract_pid()` の正規表現 `[?&]pid=(\d+)` は `&amp;` にマッチしないため、全エピソードが `pid=None` → skip。

追加因子:
- `LOOKBACK_DAYS=14` — ミュージックステーションは月1配信（33日前）のため全件 cutoff 外れ。
- `PROGRAMS` dict に廃番プログラム 4 件（363/367/375/382、2025年7月以降更新なし）が含まれ、そもそも有効エピソードが 0 件だった。

**修正：**
- `_extract_pid(link)` と link URL 構築の両方で `.replace("&amp;", "&")` を適用:
  ```python
  link = link_raw.replace("&amp;", "&")
  normalised = link.replace("&amp;", "&")
  m = re.search(r"[?&]pid=(\d+)", normalised)
  ```
- `LOOKBACK_DAYS`: 14 → 60（月次配信番組対応）
- `STALE_DAYS = 90`: 最新エピソードがこれより古い番組はスキップ（廃番自動検出）
- `PROGRAMS` dict: 廃番 4 件削除、`文化の台湾`（id=378、15d）追加

**教訓：**
- **RSS `<link>` テキストノードは `&amp;` を二重エンコードして配信する場合がある。** XML パーサーは本来 `&amp;` → `&` を変換するが、ソースが既に `&amp;` リテラルを持つ場合は二重エンコード状態が残る。リンク URL を正規表現で処理する前に必ず `.replace("&amp;", "&")` を適用すること。
- **Python の XML Element `if element:` は常に `True`**（DeprecationWarning）。`element is not None and element.text` と書くこと。
- **Podcast/RSS 型 scraper には `STALE_DAYS` チェックを入れる**: 最新エピソードの `pubDate` が `STALE_DAYS` より古ければ廃番扱いでスキップし、無駄な全件フェッチを防ぐ。
- **RSS 型 scraper の `LOOKBACK_DAYS` は配信頻度に合わせる**: 週次なら 14d、月次なら 60d 以上。

---

## 2026-05-14 — wuext_waseda オンデマンド講座の日付が term fallback になる

**問題：** 早稲田エクステンション（wuext_waseda）のオンデマンド講座は、一覧表の「日時」列に
`2025年度 冬期 全4回` のように期間名のみが書かれており、具体的な日付範囲がない。
スクレイパーが listing column からの日付抽出（Tier 1）に失敗し、
term fallback（冬期 → `2026-01-01`）を返した。
ユーザーから「日期沒抓到」と報告：`start_date=2026-01-01` が表示されていた。

**根因：** 実際の視聴期間（`(2025/11/26)から(2026/04/30)まで`）は詳細ページ本文に
`(YYYY/MM/DD)` 形式で書かれていたが、scraper がその情報を参照していなかった。
fallback 優先順位が Tier 1（listing）→ Tier 3（term）で、詳細ページ参照（Tier 2）がなかった。

**修正：** `_extract_detail_dates()` 関数を追加（`(YYYY/MM/DD)` と `YYYY年MM月DD日` を抽出）。
listing 日付失敗時に detail page 日付を Tier 2 として試みてから term fallback（Tier 3）へ進む。
DB の該当イベント `30bdfc30` を `start=2025-11-26`、`end=2026-04-30` に修正・FC ロック済み（commit `bacd4cd`）。

**教訓：**
- オンデマンド / 録画配信コースは listing に日付がない場合でも、detail page 本文に `(YYYY/MM/DD)` 形式で視聴期間が書かれていることが多い。**term fallback より前に detail page を参照すること。**
- term fallback が返す `YYYY-01-01` や `YYYY-04-01` はユーザーに「日期未定」として表示される誤情報。最後の手段として使い、可能な限り具体的な日付を優先する。
- 汎用ルールを `scraper-expert/SKILL.md § On-Demand / Viewing Period — detail page date extraction` に追加済み。

---

## 2026-05-14 — cine_gallery 相對路徑未加 BASE_URL → source_url 損壞 + raw_description = None

**問題：** auto-generated `cine_gallery.py` 只處理以 `/` 開頭的相對路徑（`detail_url.startswith("/")`），但 cine-gallery.jp 部分 detail link 為 `cinema/2026/event/shinotenshi/shinotenshi_2026.html`（無前導 `/`）。此 URL 被直接存入 `source_url`，detail page 無法開啟，`raw_description = None`，annotator 缺乏資料可用。

**根因：** spec_to_code / template 生成的相對路徑補全邏輯只考慮 absolute-from-root（`/xxx`），未考慮 document-relative（`xxx/yyy`）路徑。

**修正：**
```python
if detail_url and detail_url.startswith("/"):
    detail_url = f"{BASE_URL}{detail_url}"
elif detail_url and not detail_url.startswith("http"):
    detail_url = f"{BASE_URL}/{detail_url}"
```

**連帶效應：** 事件 `cdf5e555`（フィシスの波文 ゲストトーク）因資料損壞且無台灣關聯，設為 `is_active=False` + `deactivated_reason`。

**教訓：**
- auto-generated scraper 的相對路徑補全必須同時處理：`/` 前導（absolute-from-root）和無前導 document-relative 路徑。
- `raw_description = None` 是 detail URL 損壞的診斷訊號：annotator 只輸出「details will be announced later」類型的佔位翻譯。
- 資料損壞且無台灣關聯的事件：直接 `is_active=False`，不嘗試資料補齊。

---

## 2026-05-14 — SNET台湾スクレーパー：WP REST `content` 空 + タイトルフィルタ設計パターン（commit `64034ec`）

### A — Elementor WP サイトで REST API `content` フィールドが空になる

**問題：** `/wp-json/wp/v2/accomplishment?_fields=content` の `content.rendered` が `""` で返る。Elementor テーマが JavaScript 側でレンダリングするため、静的 HTML レスポンスには本文が存在しない。

**修正：** `content` フィールドは使わず、`link` フィールドで取得した URL に対して `requests.get` → `BeautifulSoup` で HTML を直接スクレーピング。`get_text()` でプレーンテキスト化してから日付・会場・本文を正規表現で抽出。

**教訓：** WP REST API を使うソースで `content.rendered` が空の場合、Elementor / Gutenberg blocks ベースのテーマが原因。`link` URL を直接 fetch することで解決できる。詳細ページ取得のコストを抑えるため、**API 段階でタイトルフィルタを先に適用し、対象投稿のみ fetch する（後述 B）**。

### B — 低頻度ソース（年 3〜5 件）のタイトルベースフィルタ設計

**問題：** 66 投稿のうちイベント募集は約 5 件。YouTube アカデミー動画（27 本）・過去活動報告・B2B 講師派遣報告が混在。全件を詳細ページ fetch すると不要な HTTP コスト・レート制限リスクが発生。

**設計：**
```python
_INCLUDE_RE = re.compile(r"開催のお知らせ|申込|プランニング大賞|作品募集|ツアー.*ご案内|…")
_EXCLUDE_RE = re.compile(r"アカデミー.*第\d+回|受賞作品が決定|講師.*派遣|事前学習|事後学習")

for post in posts:
    if not _INCLUDE_RE.search(title): continue   # 非イベント除外
    if _EXCLUDE_RE.search(title):    continue   # 明示除外
    event = fetch_and_parse(post["link"])        # ここで初めて HTTP fetch
```

**教訓：** 投稿数が多い（50+）のに真のイベントが少ないソースは、**詳細ページ fetch 前に API 取得タイトルだけで 2 段階 INCLUDE/EXCLUDE フィルタ**を入れる。フィルタ条件は `scraper/__doc__` または docstring に記録しておくこと。

### C — 複数形式混在ソースの日付 cascade（5 段階）

**問題：** シンポジウム（`日時　2025年7月19日`）・ツアー募集（`（2026年2月25日`）・コンテスト（`締切：2026年11月13日`）で日付の文脈が異なる。単一パターンでは取れない。

**設計（優先順位付き cascade）：**
1. `日時[　\s：:]*YYYY年M月D日` — シンポジウム系イベント開催日
2. `[（(]YYYY年M月D日` — ツアー開始日（括弧内）
3. `締切[：:]\s*YYYY年M月D日` — コンテスト締切（開催日代理）
4. 本文中最初の `YYYY年M月D日`
5. WP publish date（最終フォールバック）

**教訓：** 同一ソース内で「開催日・ツアー出発日・締切日」が混在する場合、1 つの正規表現でまとめようとせず **優先順位を明示した cascade** にする。SKILL.md に「イベント日付 cascade テンプレート」として汎用化済み。

---

## 2026-05-13 — wuext_waseda スクレイパー実装（POST 検索・本文コンテナ・関数消失・日付フォールバック・台湾本文フィルタ）

**A. POST 検索 + 302 リダイレクト**
**問題：** `https://www.wuext.waseda.jp/course/search-list/` は GET パラメータでなく POST body で検索し、Cookie なしで 302 リダイレクトを返す。`?keyword=台湾` 形式の GET パラメータは無視される。
**根因：** サイトの `<form method="post">` を確認せず GET アクセスした。
**修復：** `requests.post(url, data={"keyword": "台湾", ...}, allow_redirects=True)` に変更。セッション Cookie 不要。
**教訓：** 大学・機関サイトの検索フォームは POST + 302 パターンが多い。`form[method]` 属性を必ず確認すること。

**B. 本文コンテナの特定（`id="course"`）**
**問題：** `soup.find('main')` / `soup.find('body')` でナビゲーションリンクが大量混入し、台湾キーワード判定が不正確になった。
**修復：** ブラウザ devtools / curl + grep で `id="course"` を特定し使用。
**教訓：** 本文コンテナは必ずソース確認で id/class を特定する。`find('main')` は万能ではない。

**C. `multi_replace_string_in_file` による関数消失**
**問題：** 複数箇所を一括置換した際、`def _get_detail_price(soup)` が `_is_taiwan_content()` の末尾に docstring のみとして混入し関数本体が消えた。実行時に `NameError: name '_get_detail_price' is not defined` が発生。
**根因：** 2 つの `newString` に `def _get_detail_price` が含まれ、2 回目の置換で関数定義行が孤立した。
**修復：** `read_file` でファイルの実際の内容を確認後、`replace_string_in_file` 1 回で正しく挿入。
**教訓：** `multi_replace_string_in_file` 後は必ず `read_file` で各関数境界（空行 2 行）を確認する。新しいヘルパー関数を追加する際は、空行 2 行の境界を明確にした `newString` を書くこと。

**D. オンデマンド講座の日付フォールバック（学期 → 月初）**
**問題：** オンデマンド講座の `日時` 列に日付範囲がなく `_parse_dates()` が `(None, None)` を返し、イベントがスキップされた。
**修復：** 3 段階（明示日付 → detail body 日付 → 学期フォールバック）の優先順位を実装。`_TERM_MONTH = {"年間":(4,1,False), "春期":(4,1,False), "夏期":(7,1,False), "秋期":(10,1,False), "冬期":(1,1,True)}`（`True` = 翌暦年）
**教訓：** オンデマンド・アーカイブ型コンテンツには学期・学年度から日付を導出するフォールバックを用意する。`None` でスキップするより近似値のほうが有用。→ SKILL.md § On-Demand / Viewing Period 参照

**E. タイトル非台湾コースの台湾本文フィルタ**
**問題：** 「緊迫する世界状勢と現代地政学」「沖縄現場学」など、タイトルに「台湾」を含まないが内容で台湾を扱うコースがスキップされた。
**修復：** 詳細ページ `id="course"` 本文を常に取得（価格取得と兼用）し、台湾キーワード（台湾・台北・台中・高雄・台南・日台・台日・中華民国）を検索。タイトルまたは本文のどちらかに含まれれば収録。
**教訓：** 大学講座では「台湾有事」「日台関係」のみ言及するコースが多い。台湾フィルタはタイトルだけでなく詳細ページ本文も検索すること。

---

## 2026-05-12 — nittai_toumonkai / tsudoi_osaka scrapers + frontend UTC date fix

### A — WordPress `<strong>` strip 後空格 → `\s*` regex

**問題：** WordPress RSS 的 `<description>` 中，`<strong>` 標籤 strip 後數字之間出現空格：`"2026 年 1 月 31 日"`（本文無空格，但 BeautifulSoup strip 後插入）。
**根因：** `BeautifulSoup.get_text()` 在移除 inline 標籤時會在 tag 邊界插入隱性空格。
**修正：** 日期 regex 改用 `\s*`：`r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"` — 通用於所有 WordPress 來源。
**教訓：** 所有 WordPress `raw_description` 的日期 regex 必須用 `\s*` 取代固定空格，以應對 tag-strip artifact。

### B — venue regex 負向前瞻 `(?!受付)` 防誤匹配

**問題：** `会場受付` 誤匹配 `会場` venue 偵測 regex，導致後綴詞被截成場地名。
**修正：** `r"会場(?!受付)"` — 負向前瞻阻止 `会場受付` 命中。
**教訓：** venue regex（`会場`、`場所`、`開催場所` 等）必須加上 `(?!<後綴詞>)` 防止誤匹配常見複合詞。

### C — 全形數字轉換 `unicodedata.normalize("NFKC")`

**問題：** nittai_toumonkai 網頁含全形數字（`２０２６年`），直接比對 `\d` 失敗。
**修正：** 在 parse 前呼叫 `unicodedata.normalize("NFKC", text)` 統一轉換為半形。
**教訓：** 任何日本網頁的文字 parse 前，應先 NFKC normalize。輔助函式可命名 `_fw_to_ascii()`。

### D — Jimdo URL 日語路徑編碼不一致 → `unquote(href)`

**問題：** Jimdo CMS 的 `href` 屬性有時使用 URL-encoded 日語路徑（`%E3%83%96%E3%83%AD%E3%82%B0`），有時直接為日語字元，導致比對/去重失敗。
**修正：** 收集所有 `<a>` href 時先 `from urllib.parse import unquote; unquote(href)` 正規化，再進行比對。
**教訓：** Jimdo / WordPress 等 CMS 的 href 需 unquote 後再比對，避免同一 URL 在不同頁面出現兩種編碼。

### E — Frontend client component UTC/本地時間不一致 → `getUTCDate()` + `timeZone:"UTC"`

**問題：** `EventListClient.tsx`（client component）使用 `getDate()` 和 `toLocaleDateString`（無 `timeZone` 參數）。DB 的 timestamp 以 UTC 儲存，JST 瀏覽器將 `UTC 15:00` 解讀為隔天，導致日期顯示比 SSR 多一天（如顯示 14 而非 13）。`MovieWorksList.tsx` 的 `fmtDate()` 有相同問題。
**根因：** 爬蟲將 JST 時間儲存時未附 `+09:00` offset，Supabase 解讀為 UTC，實際時間變為 JST 深夜（`2026-06-13T00:00:00+00:00` → JST `2026-06-13 09:00` 無問題；但 `2026-06-13T15:00:00+00:00` → JST `2026-06-14 00:00`，跨日）。
**修正：** `getDate()` → `getUTCDate()`；`toLocaleDateString` 加上 `{ timeZone: "UTC" }` 參數。兩個 client component 同步修正。
**教訓：** DB 儲存的 timestamp 是 UTC；client component 一律使用 `getUTCDate()` / `{ timeZone: "UTC" }` 才能與 SSR（UTC Node.js 環境）一致。

---

## 2026-05-11 — Shopify サイトの `<a href>` は絶対 URL / `update_source.py` は既存行専用 / `feasibility` 列非存在（placebymethod 実装）

**問題①：** `placebymethod.com`（Shopify）の展覧会一覧ページで `soup.find_all("a", href=re.compile(r"^/pages/"))` を試みたところ 0 件返却。

**根因①：** Shopify は `<a href>` に**フル絶対 URL**（`https://placebymethod.com/pages/slug`）を出力する。相対パス `^/pages/` にはマッチしない。

**修正①：**
```python
# ❌ 相対パス前提 — Shopify では 0 件
soup.find_all("a", href=re.compile(r"^/pages/"))

# ✅ フル URL にマッチ
soup.find_all("a", href=re.compile(r"placebymethod\.com/pages/"))
```

**問題②：** `python update_source.py --url https://placebymethod.com/pages/contact --status researched` → `ERROR: No row found in research_sources for URL`。

**根因②：** `update_source.py` の UPDATE 処理は**対象 URL の行が既に `research_sources` に存在する場合のみ**動作する。新規ソース（DB 未登録）には使えない。

**修正②：** 新規ソースは Supabase SDK で直接 `insert()` する:
```python
sb.table("research_sources").insert({
    "url": "https://placebymethod.com/pages/contact",
    "name": "(PLACE) by method",
    "status": "implemented",
    "scraper_source_name": "placebymethod",
    "url_verified": True,
    "source_profile": {"feasibility": "medium"},
}).execute()
```

**問題③：** `insert()` に `"feasibility": "medium"` をトップレベルで指定 → `PGRST204: Could not find the 'feasibility' column`。

**根因③：** `research_sources` のトップレベル列名は `scraping_feasibility`（`feasibility` ではない）。または `source_profile` JSONB 内に `"feasibility"` キーで格納する。

**教訓：**
- **Shopify サイトは `<a href>` に絶対 URL を出力する。** 相対パス regex は必ず 0 件になる。`href=re.compile(r"{domain}/pages/")` パターンを使うこと。
- **`update_source.py` は既存行の UPDATE 専用。** 新規ソースを `research_sources` に登録するには Supabase SDK で `insert()` を使う（行が存在する場合は `upsert(on_conflict="url")`）。
- **`research_sources` の feasibility 列名は `scraping_feasibility`**（`feasibility` ではない）。または `source_profile` JSONB 内に `"feasibility"` キーで格納する。

---

## 2026-05-11 — Shopify 絶対 URL / `update_source.py` 既存行専用 / `feasibility` 列非存在（placebymethod）

**根因：**
1. Shopify `<a href>` はフル絶対 URL を出力 → 相対パス `r"^/pages/"` で 0 件
2. `update_source.py` は UPDATE 専用（行が存在しない場合は `No row found` で失敗）
3. `research_sources` に `feasibility` 列は存在しない（`scraping_feasibility` または `source_profile` JSONB 内に格納）

**教訓：**
- Shopify の `<a href>` は `href=re.compile(r"example\.com/pages/")` でマッチ
- 新規ソース登録は `insert()` または `upsert(on_conflict="url")` で直接 SDK 操作
- 列名は `scraping_feasibility`（`feasibility` は PGRST204 エラー）

---

## 2026-05-11 — SC→TC 偵測/修復不一致 + `fix_simplified()` 掃描範圍不足

### A — `SC_ONLY` 假陽性 + `_SIMP_TO_TRAD_RAW` 缺映射（commit `aa24400`）

**問題：** `_detect_simplified_chinese()` 的 `SC_ONLY` 集合含 4 個假陽性字元（征/蹈/零/蒙——SC/TC 共用字），導致正常 TC 文本被誤報為含 SC。同時 `_SIMP_TO_TRAD_RAW` 缺 3 個映射（见→見、从→從、库→庫），`fix_simplified()` 無法修復真正的 SC 字元，造成無限 dismiss→reappear 循環。

**修正：**
1. 移除 `SC_ONLY` 中 4 個假陽性：征、蹈、零、蒙
2. 新增 3 個映射到 `_SIMP_TO_TRAD_RAW`：见→見、从→從、库→庫
3. Data fix：2 筆 gguide_tv 事件 `description_zh`（智库→智庫、见解→見解）
4. Dismissed 7 筆 stale pending 報告

**教訓：**
- **SC_ONLY 字元驗證規則**：加入前必須確認該字元在 TC 中**不存在或字形不同**。共用字元（征=征伐、蹈=舞蹈、零=零、蒙=蒙古）不可加入 SC_ONLY。
- **偵測與修復字元集必須同步**：從 `_SIMP_TO_TRAD_RAW` 的 keys 衍生 `SC_ONLY`，或至少確保 `SC_ONLY ⊆ _SIMP_TO_TRAD_RAW.keys()`。

### B — `fix_simplified()` 僅掃描 2 個欄位（commit `f7790a2`）

**問題：** `fix_simplified()` 僅修復 `name_zh` 和 `description_zh`，但 `_detect_simplified_chinese()` 掃描全部 6 個 `_zh` 欄位。`location_name_zh`、`location_address_zh`、`business_hours_zh`、`organizer_zh` 中的 SC 字元被偵測到但無法自動修復。

**修正：** `fix_simplified()` 擴展到掃描全部 6 個 `_zh` 欄位。

**教訓：** 偵測範圍與修復範圍必須完全一致。每次擴展偵測範圍時，同步擴展修復範圍。

---

## 2026-05-11 — `_lock_fields_via_corrections()` 缺 SC→TC guard 導致 SC 永久鎖定

**問題（commit `f7790a2`）：** `_lock_fields_via_corrections()` 使用 `str(fvalue)` 寫入 FC 表，未經 `_to_trad()` 轉換。backfill 腳本將日文漢字複製到 `organizer_zh` 時（kanji copy），日文漢字（`会`=SC `会`）被永久鎖入 FC，annotator P1 保護阻止後續修正。39 筆事件 `organizer_zh` 受影響。

**修正：** `_lock_fields_via_corrections()` 對 field name 以 `_zh` 結尾的值自動呼叫 `_to_trad()` 後再寫入 FC。13 筆 taiwan_prism `location_name_zh` + 2 筆 inactive `name_zh` + 39 筆 `organizer_zh` 批量修正。

**教訓：** `field_corrections` 表是資料的永久閘門。任何寫入 FC 的路徑（`_lock_fields_via_corrections()`、手動 upsert、backfill 腳本）都必須對 `_zh` 欄位過 `_to_trad()`，否則 SC 值一旦進入便永久免疫於自動修復。

---

## 2026-05-10 — ftip.py `source_url` vs `official_url` 分離修正

**問題（commit `7c34788`）：** 先前修正（`ab771e2`）讓 `_OFFICIAL_URL_RE` 提取的官方 URL 直接覆寫了 `source_url`，導致 FTIP 聚合站 URL audit trail 遺失。事件 `023dcbec` 的 `source_url` 被改為 `www.taiwanprism.com`，ftip-japan.org 溯源連結中斷。

**修正：**
- `source_url` = 永遠是 FTIP RSS 項目 URL（`https://www.ftip-japan.org/NNN`）— 聚合站次要連結保留
- `official_url` = 提取的第一方主辦方 URL（活動官網、Facebook event 頁等）
- DB 事件 `023dcbec` 手動修正：`source_url=ftip-japan.org/699`、`official_url=taiwanprism.com`，FC×2 鎖定

**教訓：** 聚合站 scraper（ftip、prtimes、gnews、walkerplus）的 `source_url` 必須**永遠保留**聚合站自身的 URL；提取的第一方 URL 存入 `official_url`。`source_url` 的語義是「我從哪裡找到此資料」，覆寫它等同破壞 Second-hand Source URL Guard。SKILL.md 的「RSS 聚合站」section 已同步修正。

---

## 2026-05-10 — note_creators レポート記事の三重問題パターン

**問題（event `a7a05be6`、台湾薬膳文化体験レポート）：** note_creators 來源的レポート記事存在三個固定問題：

1. **`start_date` = 記事公開日（2026-05-08）**：實際活動日期為 2026-04-21（相差 17 天）
2. **`location` = 主催者の日本拠点**（台湾華語文学習センター大阪弁天町）：實際為台灣場地（台北医学大学）；`location_address` / `location_prefectures` 需設 null（活動在台灣，非日本）
3. **接頭辭缺失 + `report` category 缺失**：需加 `【レポート】`/`【活動報導】`/`[Report]` 前綴

**修正：** 9 個 FC 鎖定（start_date、location_name、location_address、location_prefectures、name_ja、name_zh、name_en、categories）

**後續自動化（commit `1e00933`）：** annotator.py 的 `_REPORT_TRIGGER_RE` 自動注入 `report` category + 三語接頭辭；但 **`start_date`（記事日 ≠ 活動日）** と **`location`（主催者拠点 ≠ 活動場所）** の修正は依然として人工必須。

---

## 2026-05-10 — TaiwanPrism scraper 三重 bug（null byte + organizer_type + parent_event_id）

**問題（commits `a3d67fc`, `c7e9b73`）：** 新建的 `taiwan_prism.py` scraper dry-run 成功但 DB 寫入失敗，出現三個獨立 bug：

**Bug 1 — `\u0000` null byte（Postgres `22P05`）：**
- 根因：speaker 清單中含 `×\u0000栖来ひかり`（`×` 為 Unicode cross mark，後接 null byte），直接拼入 `description_ja`。
- 修正：在 speakers join 後立即 `.replace("\x00", "")`，清除源頭。

**Bug 2 — `organizer_type=["npo"]`（check constraint violation）：**
- 根因：`npo` 不在 DB 允許清單；正確值為 `civic_group`。
- 修正：兩處（父事件 + 子事件）改為 `["civic_group"]`。

**Bug 3 — `parent_event_id=f"taiwan_prism_{year}"`（`22P02` uuid 語法錯誤）：**
- 根因：`parent_event_id` 欄位型別為 `uuid`，不能傳 source_id 字串。
- 修正：改用 `get_event_id_by_source(SOURCE_NAME, parent_source_id)` 查真實 UUID；首次執行因父事件尚未入庫而回傳 `None`，第二次起正確解析。首次執行後手動 patch 12 筆子事件 `parent_event_id`。

**教訓：**
1. `parent_event_id` 必須是 DB UUID，不可傳 source_id；需在 `scrape()` 中 import `database.get_event_id_by_source` 解析。
2. 任何 scraper 在寫入 `raw_description` 之前，必須對所有外部文字 `.replace("\x00", "")` 防護。
3. `organizer_type` 只允許 8 個值；NPO 型組織統一使用 `civic_group`。

---

## 2026-05-10 — Peatix scraper `_extract_peatix_dates` 缺 return 靜默丟棄事件

**問題（commit `2a9540c`）：** Peatix 連續 7 天 0 新事件。原因不明，無任何 ERROR log。

**根因：** `_extract_peatix_dates()` 在事件有日期但無時間範圍時，`if`-`else` 所有分支執行完畢後直接 fall-through，隱式返回 `None`。呼叫端嘗試 unpack `None`（`start, end = ...`），拋出 `TypeError: cannot unpack non-iterable NoneType object`，該頁面的所有事件被靜默丟棄。

**修正：** 新增明確 `return start, None` 確保所有路徑都有回傳值。

**教訓：** 拆解日期的 helper 函式必須有 exhaustive return path。任何 `if/elif/else` 的 date-parser 函式都應加 `assert False, "unreachable"` 或明確 `return None, None` 作為 fallback，防止隱式 `None` 傳播造成靜默丟棄。

---

## 2026-05-10 — ftip.py `start_date` 回退 / `source_url` 指向聚合站 / `location_address` 硬編碼

### A — `M/D~D` 範圍未識別 → start_date 落到 pubDate（commit `ab771e2`）

**問題：** 事件 `023dcbec`（台湾光譜 taiwan prism）`start_date` 為文章發布日，因為 `8/30~31` 模式未被任何 DATE_PATTERNS 匹配。
**根因：** `ftip.py` 僅有 `M/D` 全日期 patterns，無 `M/D~D` 多日範圍的結束日提取。`~D` 後的數字被忽略，start_date 靜默回退到 RSS pubDate。
**修正：** 新增 `DATE_PATTERNS[4]`（`M/D` fallback）+ `_END_DAY_RE`（提取 `M/D~D` 的結束日，附 `(?![/])` 跨月防護）。
**教訓：** 凡含 `~` 的日期字串（`8/30~31`）應同時解析 start 和 end。若 `~` 後接 `/`（跨月，如 `3/10~5/31`），不提取 end_date 以防假匹配。

### B — `source_url` 指向聚合站而非官方站

**問題：** `source_url = "ftip-japan.org/..."` — 但 raw_description 已明確標示 `公式サイト www.taiwanprism.com`。
**根因：** scraper 直接把 RSS 的 `<link>` 存為 source_url，未嘗試提取 `公式サイト` URL。
**修正：** 新增 `_OFFICIAL_URL_RE`，從 content 提取 `公式サイト www.xxx.com` 或 `公式サイト https://...`，優先作為 `source_url`。
**教訓：** RSS 聚合站 scraper（如 FTIP）應優先提取 `公式サイト` URL 作為 `source_url`；僅當不存在時才使用 RSS link。此為**通用模式**，不限於 ftip。

### C — `location_address` 硬編碼為 `東京都`

**問題：** 台湾光譜活動實際在京都（`〒603-8163 京都府...`），但 `location_address` 被寫死為 `"東京都"`。
**根因：** ftip.py 使用 `location_address = "東京都"` 作為全組織 fallback，錯誤假設所有活動都在東京。
**修正：** 新增 `_VENUE_NAME_RE` / `_VENUE_ADDR_RE` 從 `会場は VENUE（...）` 模式提取真實場地與地址；無法提取時 `location_address = None`。
**教訓：** 以城市名（`東京都`、`大阪`）作為全國性組織的 `location_address` fallback 是反模式——GPT 會信任它並造成錯誤標注。未知時必須設 `None`。

---

## 2026-05-09 — `_KNOWN_PERSON_MAP` 藝名/筆名 GPT 翻譯覆寫 + performers_zh/en 多語言陣列

### A — GPT 片假名藝名翻譯失敗 → `_KNOWN_PERSON_MAP` hardcoded 解法

**問題：** `backfill_performer_i18n()` 用 GPT 翻譯片假名名，對藝名/筆名產生錯誤音譯：`ギデンズ・コー` → `基登斯·高`（正確：`九把刀` / `Giddens Ko`）。
**根因：** 藝名與片假名無語音對應關係，GPT 語音推測必然失敗。
**修正：** `annotator.py` 新增 `_KNOWN_PERSON_MAP`（14 筆已驗證名人），三個整合點（annotation loop、performers[] 逐元素、backfill Layer 0）。11 筆 DB 事件修正。
**教訓：** 藝名/筆名不可靠 GPT 翻譯。已知名人必須收錄 `_KNOWN_PERSON_MAP`，新增時三語同時驗證（eiga.com / 官方 / Wikipedia）。

### B — `performers_zh[]` / `performers_en[]` 多語言陣列新增

**問題：** 多人事件只有 `performers[]`（日文），中英頁面顯示日文名。
**修正：** migration 056 新增 `performers_zh TEXT[]`、`performers_en TEXT[]`；Event dataclass / database.py 同步更新；getEventPerformer() 多人分支優先使用語言對應陣列。178 筆 backfill。
**教訓：** 多語言陣列欄位新增後，前端 locale 優先序和 array 長度判斷需同步更新。

### C — 翻譯規則嚴格化

**確立規則：** (1) 拉丁字母名原樣保留 (2) CJK 漢字名無驗證來源不翻譯 (3) 片假名僅有驗證來源時翻譯 (4) `backfill_performer_i18n()` 不可限定 `is_active=True`
**教訓：** 翻譯規則必須在 SKILL.md 明文記載，否則每次 backfill 都會重複犯錯。

---

## 2026-05-08 — SC→TC 映射表缺字靜默通過 + organizer 多語言欄位新增

### A — `_SIMP_TO_TRAD_RAW` 缺 9 字（commit `95b79ef`）

**問題：** GPT-4o-mini 輸出含 `诗`/`禅`/`图`/`猎`/`过`/`员`/`剧`/`别`/`于`，`_to_trad()` 無法轉換，SC 字直接寫入 DB `description_zh` 和 `selection_reason`。
**根因：** `_SIMP_TO_TRAD_RAW`（292 筆）手動維護不完整，每次 GPT 用到新 SC 字就靜默通過。
**修正：** 新增 9 字 + 3 筆活躍事件 DB 修正 + FC 鎖定。
**教訓：** 映射表方式是打地鼠（表已從 ~50 成長到 300+ 筆仍不完整）。長期應考慮 OpenCC 等完整 SC→TC 庫。每次新增字後必須同步更新 `auto_qa.py` 的 `SIMP_RE`。

### B — `organizer_zh` / `organizer_en` 多語言欄位（migration 059, commit `95c7ad8`）

**問題：** 日文 organizer 名稱直接顯示在 zh/en 頁面。
**修正：** annotator.py 新增 `_KNOWN_ORGANIZER_MAP`（10 筆高頻主辦方） + GPT 翻譯邏輯 + 子事件繼承 organizer_zh/en。scraper infra（base.py + database.py）同步更新。
**教訓：** 文字欄位多語言化已成標準流程：KNOWN_MAP → kanji copy → GPT batch。`_KNOWN_ORGANIZER_MAP` 設計模式同 `_KNOWN_PERSON_MAP`，高頻主辦方必須 hardcode 確保翻譯品質。

---

## 2026-05-08 — 湾.味(ワンウェイ) organizer 污染 + performer job title 假陽性

**Error:** 事件 `fe03288b` / `b8621ee9`（台湾料理体験会 1部・2部）出現兩類問題：
1. `organizer` hallucinated 為 `語学スクール`（真實主辦方：湾.味(ワンウェイ)）
2. `organizer_zh` / `organizer_en` 被另一個完全不同事件（上田村振興会・普門寺）的 `field_corrections` 資料污染
3. `performer = シェフ`（職稱，非人名）→ 應為 null

**Root cause:**
1. GPT 在 organizer Non-Hallucination Guard 不足時，從 few-shot context 中其他事件的資料推斷 organizer（few-shot pollution 模式）。
2. `organizer_zh`/`organizer_en` 欄位內容來自不同事件的 FC 表格——跨事件 FC 污染，`annotation_status = annotated` 不觸發重新驗證，無法自動偵測。
3. `_extract_performer_from_raw` 未過濾純職稱（`シェフ`/`講師`/`先生` 等），job title 被誤認為人名。

**Fix:** 8 筆 `field_corrections` 鎖定（兩件事各 4 欄）；`performer` 設 null；`organizer_zh/en` 更正後鎖定。

**Lesson:**
1. **Performer Job Title Guard**：`performer` 只能填人名，不能填職稱（`シェフ`、`講師`、`先生`、`料理人` 等）。regex 應使用 negative filter 過濾純職稱。
2. **FC 跨事件污染偵測**：若 `organizer_zh`/`organizer_en` 含有在 `raw_title + raw_description` 中找不到的內容，即為 FC 污染。偵測指令：`SELECT id, organizer_zh FROM events WHERE organizer_zh IS NOT NULL AND raw_description NOT ILIKE '%' || split_part(organizer_zh, ' ', 1) || '%'`。
3. **few-shot pollution**：GPT 從 few-shot examples 的其他事件推斷欄位。annotator 的 Non-Hallucination Guard 在 organizer 文本極短（< 2 字）時效果有限；thin content 事件 organizer 應設 null。

---

## 2026-05-08 — WhitestoneGallery 新 scraper + ZERO_EVENT_OK_SOURCES 模式確立

**Event:** 新增 `whitestone_gallery.py`（Whitestone Gallery Ginza / Karuizawa，台灣藝術家展覽）。

**Design decisions:**
- 爬取 `/tagged/current` 靜態 HTML listing，不需 JS
- 過濾日本地點（Ginza、Karuizawa、Tokyo）
- 在 detail page main content 中檢查台灣關鍵字（避免 footer country dropdown 假陽性）
- `source_id = whitestone_gallery_{url-slug}`
- 0 events 是正常結果（台灣藝術家展覽為偶發性），加入 `ZERO_EVENT_OK_SOURCES`

**Lesson:**
- **ZERO_EVENT_OK_SOURCES 模式**：定期舉辦但大多時候無台灣相關活動的場館（藝廊、部分影院），應加入 `health_check.py` 的 `ZERO_EVENT_OK_SOURCES`，避免每日 CI 觸發假警告。加入標準：(a) scraper 邏輯正確；(b) 台灣內容為偶發性（年 0–3 次）；(c) 0 events 是預期行為。
- 0 events 且未在 `ZERO_EVENT_OK_SOURCES` → health check 觸發「missing」警告，每次 CI 都需人工確認 → 雜訊過多。

---

## 2026-05-08 — note_creators 薄文本：organizer hallucination + 非活動文章入庫（commit b589fbb）

**Error:** `note_creators` 來源的 4 個事件出現問題：(1) `name_ja` 為部落格文章標題（如 `大阪で開催される無料の映画上映イベント`），非活動名稱；(2) `organizer='埼玉県日台親善協会'`（note 發文者，非主辦方）；(3) 2 件純介紹文章/觀影心得報導被識別為活動，應 `is_active=false`。

**Root cause:** `note_creators` 的 `raw_description` 通常只有「続きをみる」截斷文字（< 50 字）。GPT 在無法從 raw_description 識別主辦方時，從 note 發文者背景知識推斷 organizer。Non-Hallucination Guard 在文本極短時保護有限。`_HEADLINE_REWRITE_SOURCES` 未包含 `note_creators`，故 raw_title（文章標題）直接被用作 `name_ja`。

**Fix (commit b589fbb):**
- `note_creators` 加入 `_HEADLINE_REWRITE_SOURCES`（GPT 可改寫 name_ja）
- 4 件 DB 修正 + `field_corrections` 鎖定
- `4180ad0f`（台灣電影介紹文）、`4ebc8a35`（觀影心得報導）設 `is_active=false`

**Lesson:**
1. `note_creators` 等部落格來源 `raw_description` 通常只有截斷文字 → organizer 必然為 null，不可從 note 發文者推斷。
2. 純介紹文章（標題含「おすすめ」「紹介」等）與觀影心得報導不是活動資料 → `is_active=false`。
3. `_HEADLINE_REWRITE_SOURCES` 必須包含所有部落格/聚合類來源（`note_creators`、`note.com` 等）。

---

## 2026-05-08 — news headline 標題未改寫 + 學術場次識別碼（commit 47f8184）

**Error:** `e166878a`（gnews）：`name_ja='日本の植民地支配へ抵抗描く 台湾映画 17日那覇で上映会'`（新聞標題，非活動名稱）。`12e375da`（taiwanshi）：`name_ja='第1報告'`（學術會議場次識別碼，非發表題目）。

**Root cause:** (1) `_HEADLINE_REWRITE_SOURCES` 未完整涵蓋所有新聞/聚合來源，gnews 事件的 raw_title 直接被用作 `name_ja`。(2) 學術會議的場次識別碼（`第N報告`/`基調講演`/`招待講演` 等）沒有對應的 `_SLOT_TITLE_RE` 偵測，未觸發改寫邏輯。

**Fix (commit 47f8184):**
- `_HEADLINE_REWRITE_SOURCES` 常數正式涵蓋 `gnews`/`nhk`/`prtimes`/`walkerplus`
- `_SLOT_TITLE_RE` 正規表示式偵測學術場次識別碼
- SYSTEM_PROMPT 加 NEWS HEADLINE REWRITE RULE + ACADEMIC SLOT REWRITE RULE

**Lesson:** 新聞標題是記者寫作，不是活動名稱。學術會議的「第N報告」是場次識別碼，不是論文題目。新增來源時，凡是 raw_title 非活動正式名稱的來源，都必須加入 `_HEADLINE_REWRITE_SOURCES`。

---

## 2026-05-08 — MUKAE_RE 缺少 をゲストに迎え，一青窈未被捕捉（commit 6c2f1ab）

**Error:** `一青窈氏をゲストに迎え` 無法被 `_MUKAE_RE` 捕捉，performer 返回 null。`をゲストに迎え` 是日式正式邀嘉賓慣用語，與 `をお迎え`/`を迎え` 語義相同，但不在 lookahead 清單中。

**Root cause:** `_MUKAE_RE` lookahead 只列舉 `をお?迎え|による|が登壇|がトーク|にご登場`，缺少 `をゲストに迎え`。

**Fix (commit 6c2f1ab):** Lookahead 加入 `をゲストに迎え`：`(?:をお?迎え|をゲストに迎え|による|が登壇|がトーク|にご登場)`。

**DB impact:** 受影響事件 e0521671（ようこそ物語の島へ）、1d741522（絵本朗読×トーク），以 DB 手動設定 `performer='林廉恩、一青窈'` + `field_corrections` 鎖定。

**Lesson:** MUKAE lookahead 必須涵蓋所有「邀請演出者」語義的日語慣用語：`をお迎え`、`を迎え`、`をゲストに迎え` 三者缺一不可。每次新增邀嘉賓用語時，同步補全。

---

## 2026-05-08 — PERFORMER_INTRO_RE separator `+` 導致 絵本作家林廉恩 無法捕捉（commit fe8b273）

**Error:** `絵本作家林廉恩氏` 無法被 `_PERFORMER_INTRO_RE` 捕捉。`作家` 在 role list 中，但 `[・：:\s]+`（1+ 個分隔符必填）阻斷了角色與名字直接連接的寫法。

**Root cause:** separator `[・：:\s]+` 要求至少 1 個分隔符，而 `絵本作家林廉恩` 角色詞與人名直連（無任何分隔符）。MUKAE 路徑也無法命中（缺 `をゲストに迎え` 且不含 `と` 連接結構）。

**Fix (commit fe8b273):** `[・：:\s]+` → `[・：:\s]*`（separator 改為 optional，0 個或多個）。

**DB impact:** Event e0521671（ようこそ物語の島へ）文本為 `作家の林廉恩氏`（`の` 不在 `*` 範圍），仍以 DB 手動修正 + lock 處理。Event 1d741522 同上。

**Lesson:** 日語中角色詞與人名直接連接是常見寫法（如 `絵本作家林廉恩`、`料理人鈴木一郎`）。`_PERFORMER_INTRO_RE` separator 必須用 `*`，而非 `+`，否則直連寫法靜默失敗。Sanity check 三種情況：直連、點號分隔（`・`）、冒號分隔（`：`/`:`）均應命中。

---

## 2026-05-08 — performer regex 假陽性：INTRO `{2,6}` + MUKAE 缺 lookbehind

**Error:** `_PERFORMER_INTRO_RE` 在 `歌手・翻訳者一青窈氏による` 中擷取出 `翻訳者一青窈`（6 字）。`_MUKAE_RE` 則從 `訳者一青窈氏による` 中間開始匹配出 `訳者一青窈`。兩者均為假陽性，真實姓名為 `一青窈`（3 字）。

**Root cause:** (1) `{2,6}` 上限過寬——role 詞（`翻訳者`=3 字）+ 真名（`一青窈`=3 字）共 6 字符合上限。(2) `_MUKAE_RE` 無 negative lookbehind，從字串中間任意位置開始匹配。

**Fix (本 commit):**
- INTRO + MUKAE：max 6 → 5，防止 6 字 role+name 組合被捕獲
- MUKAE：加入 `(?<![一-鿿])` negative lookbehind
- INTRO：role list 新增 `翻訳者`

**DB impact:** 215 筆 null-performer 事件掃描後，4 筆命中。INTRO 命中 2 筆（真陽性）已鎖 field_corrections；MUKAE 命中 2 筆（多人講者）保持 null。

## 2026-05-08 — bookandbeer: server-side keyword param silently ignored + author bio false positives

**Error:** `bookandbeer.py` の初版は `?keyword=台湾` URL パラメータを頼りにしていたが、bookandbeer.com サーバーはこのパラメータを完全に無視し全件返却。結果として多数の非台湾関連イベントが DB に登録された。さらに、著者略歴に「台湾大学 客員教授」「淡江大学」という記述があるだけで `_is_taiwan_relevant()` が True を返す問題があった。

**Fix (commits 7df9f56, e1ab468):**
1. keyword param をドキュメントコメントにだけ残し、クライアントサイドの `_is_taiwan_relevant()` を追加。
2. `_AUTHOR_BIO_RE` で大学名マッチングを除外。
3. タイトル優先 + description 冒頭 500 字で ≥ 2 matches + 大学名除去後も keyword 残存の三段ロジック。

**Lesson:** Before relying on a URL keyword parameter, empirically verify it filters — request with vs without keyword and compare response counts. Also, author biographies are NOT event content; always strip them before counting Taiwan occurrences.

---

## 2026-05-08 — tokyoartbeat: Contentful placeholder dates use entire January (month == 1, not day == 1)

**Error:** `tokyoartbeat.py` の Contentful 佔位符ガードが `start_date.day == 1` だったため、`2026-01-15` の佔位符日付 (events `977da793`, `e7cf2a51`) を見逃した。Contentful は財年未定の系列展に `YYYY-01-xx`（1 月いっぱい）を使う。

**Fix (commit 7df9f56):** ガード条件を `start_date.month == 1` に変更。DB events `977da793` と `e7cf2a51` を直接修正。

**Lesson:** Contentful 佔位符は Jan 1 限定ではない。整 1 月が佔位符として使われる可能性を常に考慮し、`month == 1` でガードする。

---

## 2026-05-07 — KG+ Kyotographie scraper 新規実装 + 4 scrapers 復元（commit `de6c31d`）

### A — KgplusKyotographieScraper 実装

**新規 scraper**: `kgplus_kyotographie` — KYOTOGRAPHIE International Photography Festival の衛星プログラム KG+ の台湾関連展示を取得。

**設計**:
- **WP REST API で CPT 名を動的検出**：`/wp-json/wp/v2/types` から `exhibitions_plus{YEAR}` を探し、フェスティバル年度を自動判定（ハードコード不要）
- **全展示スラグ列挙**：`/wp-json/wp/v2/exhibitions_plus{YEAR}?per_page=100&page=N` でページネーション（2026年: 213件 × 3ページ）
- **個別HTML取得 + 台湾フィルタ**：各展示ページを fetch し `台湾/Taiwan/臺灣/台南/台北/Taiwanese` でフィルタリング
- **日付パース**：`<p class="-openclose">` の `"Open: M.D Weekday–M.D Weekday"` 形式、年度は CPT 名から推定
- Playwright 不要（WP REST API + requests のみ）

**2026年実績**: 4件の台湾関連展示を検出（makoto-lin, chan-man-ching, naoki-miyashita, sean-tseng-asano-tsutsumi-sara-wu）

**教訓**:
- WordPress CPT 名に年度を含むサイト（`exhibitions_plus2026` 等）は `/wp-json/wp/v2/types` で動的に名前を取得すること — ハードコードすると翌年に silent failure する
- 全件スキャン + クライアントサイドフィルタが最も確実。API 側の台湾フィルタが存在しなくても問題ない（`_REQUEST_DELAY = 0.5s` でレート制限）

### B — 4 scrapers 復元（johakyu, stranger, tsutaya_portal, tsudoi_osaka）

**問題**: 前回のコミットで `main.py` の import/SCRAPERS が再編成され、4 つの scraper が誤ってドロップされていた。

**復元内容** (commit `de6c31d`):
- `JohakyuScraper` — 浄化湯（映画館）
- `StrangerScraper` — Stranger（東京墨田区の映画館）
- `TsutayaPortalScraper` — 蔦屋書店ポータル（`_is_taiwan_relevant()` 偽陽性修正済み）
- `TsudoiOsakaScraper` — 大阪のコミュニティイベント

**教訓**: SCRAPERS リスト audit を main.py に変更を加える**全コミット前**に実行すること。新規 scraper 追加コミットでも既存 scraper が誤ってドロップされることがある。Audit コマンド:
```bash
python3 -c "import re, glob; registered=set(re.findall(r'(\w+Scraper)\(\)', open('main.py').read())); [print('UNREGISTERED:', re.search(r'class (\w+Scraper)\b', open(f).read()).group(1), f) for f in glob.glob('sources/*.py') if re.search(r'class (\w+Scraper)\b', open(f).read()) and re.search(r'class (\w+Scraper)\b', open(f).read()).group(1) not in registered and re.search(r'class (\w+Scraper)\b', open(f).read()).group(1) != 'BaseScraper']"
```

---

## 2026-05-07 — note_creators full-article fetch + Vision OCR pipeline 実装（commit `a52f5b2`）

### A — note_creators.py full-article fetch + og:image

**Problem**: `note_creators.py` が RSS の「続きをみる」truncated text（39 字以下）しか取得できなかった。結果として：
- `start_date` が記事発布時間（`pub_date` + non-midnight timestamp）にフォールバック（`2cae572a` start_date=2026-03-17 が実際は 2026-04-06 だった問題の根本原因）
- `raw_description` が薄すぎて annotator が organizer/venue/date を正確に抽出できない
- `image_url` が未取得

**Fix**: `_fetch_article_content(url, session) → (body_text, image_url | None)` を実装：
1. JSON-LD `articleBody` → `description` → BS4 `<p>` タグ連結の 3 段階フォールバックで本文取得
2. `og:image` メタタグで画像 URL 抽取 → `Event.image_url` にセット
3. `_BODY_DATE_RE` パターン（`📅 2026年4月6日`、`日時：4/6`、`◎ MM月DD日` 等）で本文から直接日時抽出
4. thin content 検知（`len(body) < 40`）時は `time.sleep(1)` 後に自動 detail fetch を実行

**Lesson**: RSS-based scraper で `raw_description` が短い（「続きをみる」「Read more」等）場合は、scrape 段階で detail page を fetch して本文を取得するべき。`pub_date` フォールバックを debug するより根本的に thin content を解消することで start_date 問題も同時に解決できる。

### B — Vision OCR pipeline `enrich_poster.py` 新規作成

**Feature**: `scraper/enrich_poster.py` — GPT-4o Vision でイベントポスター画像から情報を抽出する enrichment pipeline。

**Design**:
- `_fetch_candidates(sb, max_events)`: `image_url IS NOT NULL` かつ `annotation_status IN ('pending', 'annotated')` のイベントを選択
- `_extract_from_poster(image_url)`: GPT-4o Vision で JSON 出力（date, venue, organizer, confidence）
- `_apply_if_confident(sb, event, result, dry_run)`: `confidence ≥ 0.8` のフィールドのみ適用 + `field_corrections` でロック
- **Thin Content Guard**: `raw_description < 100 字` の場合は `organizer` フィールドを non-apply（date/venue のみ）
- CLI: `python enrich_poster.py [--dry-run] [--event-id UUID] [--max N]`
- migration 057 適用済み：`events.image_url TEXT`; `Event` dataclass + `database.py` に `image_url` フィールド追加
- CI: `scraper.yml` の annotator ステップ直後に `Run Vision OCR enrichment` ステップ追加

**Lesson**: Vision OCR のような外部知識依存 enrichment では Organizer Non-Hallucination Guard と同様のリスクがある。thin content 時は organizer を適用しない Thin Content Guard を組み込み、GPT の hallucination リスクを抑制すること。confidence threshold（≥ 0.8）による自動適用は一見安全だが、画像から読み取れない情報は GPT が「知っている知識」で補完してしまう点に注意。

---

## 2026-05-07 — auto_research.py Playwright 逾時導致整批中止（commit `8029b74`）

**Error**: `_fetch_sample_html()` 呼叫 `page.goto(url, timeout=30_000)` 無 try/except。`note.com/swi0881` 逾時 → 未捕獲 `PlaywrightTimeoutError` → 整個 auto-research CI job exit code 1，所有後續來源全部跳過。

**Fix**:
1. `_fetch_sample_html` 捕獲 `playwright.sync_api.TimeoutError` → log warning → return `""`
2. `run()` 將空 `sample_html` 視為 `AssessError("error", ...)` → 該來源標記 `error` in DB → batch 繼續到下一列

**Lesson**: CI 批次腳本中，每個 `page.goto()` 都必須包裝 `TimeoutError` 捕獲。任何單一慢速 / 被封鎖 URL 都不得中止整個批次。

→ Added to SKILL.md §「Playwright CI 批次容錯規則」

---

## 2026-05-07 — AdminEventTable performers[] 顯示修正（commit 9b84d98）

**Error**: 父事件 `b90afe3c`（台湾史研究会3月例会）有 `performers=['陳志剛', '福田真郷']` 但 `performer=null`，`AdminEventTable` 只讀取 `performer` 欄位，導致顯示空白。`getEventPerformer()` helper 也未優先使用 `performers[]`，多人學術事件的表演者一律不顯示。

**Fix**:
1. `web/lib/types.ts` — `getEventPerformer()` 重寫：優先序 `performers[]`（join「、」）→ `performer_zh/en` → `performer`（legacy fallback）。
2. `web/components/AdminEventTable.tsx` — 顯示邏輯改用 `performers.join('、')`，全文搜尋也加入 `performers[]` spread。
3. `web/app/[locale]/events/[id]/page.tsx` — 移除複雜三段式條件，統一呼叫 `getEventPerformer()`。

**Lesson**: `performer`（TEXT）是 legacy 單人欄位，`performers[]`（TEXT[]）是正確的多人欄位。UI 所有使用 performer 的地方都必須改為 `performers[]` 優先，並統一透過 `getEventPerformer()` helper 讀取，不可直接存取 `event.performer`。

→ Updated architect.agent.md §「Performer Multilingual Fields Guard」Rule 2

---

## 2026-05-07 — 0d97e51c（2025年台湾史研究会3月例会）5 件 DB 手動修正

**Error 1 — performers[] 跨年度混入**：`performers=['陳志剛', '福田真郷']`（2026年3月例会成員）被錯填進 2025年3月例会。根本原因：performers[] 批次回填時按 source_name + 月份比對，不同年份的相同月份事件互相污染。
**Fix 1**: `performers=['やまだあつし', '下岡友加']`（raw_description 明記）+ `field_corrections` 鎖定。

**Error 2 — event_form 不正確**：`['lecture']` 應為 `['conference']`（兩場報告的學術例会 = conference，非單場 lecture）。
**Fix 2**: `event_form=['conference']` + FC 鎖定。

**Error 3 — location_name 不完整**：`関西大学千里山キャンパス 経商研究棟` 漏掉子場地後綴（6階 大会議室）。
**Fix 3**: `関西大学千里山キャンパス 経商研究棟6階 大会議室`，多語言欄位（zh/en）同步更新。

**Error 4 — location_url 誤填申込表單 URL**：`https://forms.gle/...`（申込 Google Form）填入 `location_url`。`location_url` 應為會場 URL，不應填入申込表單。
**Fix 4**: `location_url=null`。

**Error 5 — sub-events 未啟用**：子事件 a8702ec8（第1報告）和 d85547af（第2報告）`is_active=False`。
**Fix 5**: `is_active=True`（兩件）。

**Lessons**:
- **performers[] 批次回填**必須對照 raw_description 確認姓名，不可只靠 source_name + 月份比對——不同年份同月份事件會互相污染。
- **event_form 區分**：單場演講 = `['lecture']`；多位報告者的學術例会（2 報告以上）= `['conference']`。taiwanshi 等研究会月例会通常是 `['conference']`。
- **location_url 語義**：只填會場官方 URL（e.g. 大学キャンパスページ）；申込表單（Google Forms 等）屬於 `source_url` / `official_url` 責任範圍，不填 `location_url`。

→ Added to SKILL.md §「performers[] 批次回填驗證規則」、§「event_form — lecture vs conference 區分」、§「location_url 語義規則補充」

---

## 2026-05-07 — google_news_rss: RSS snippet used as start_date fallback when article fetch fails

**Error:** `google_news_rss.py` は article_text の取得に失敗した場合、RSS description snippet を fallback として `_extract_start_date(description_plain, pub_date)` に渡していた。snippet は通常 200 字未満で年月日情報が不完全なため、annotator が誤った start_date を推定していた。

**Fix (commit 1c0f69a):**
```python
start_date = _extract_start_date(article_text, pub_date) if article_text else None
```
article_text が None の場合は start_date も None にし、annotator の universal year-anchor に委ねる。

**Lesson:** RSS snippets are marketing truncations, not structured event data. Never use them for date extraction. If the full article is unavailable, set start_date = None.

---

## 2026-05-06 — bookandbeer: keyword= URL パラメータがサーバー側でフィルタされない（100% ノイズ問題）

**問題：** `bookandbeer.com/event/?keyword=台湾` というURLをフェッチしていたが、サイト側でキーワードフィルタが**全く機能していない**（全イベントが返される）。スクレイパーにクライアント側チェックがなく、active 19 件の全てが非台湾イベントだった（台湾関連ヒット率 0%）。

**根因：** auto_scraper で生成されたスクレイパーは、URLの keyword= パラメータが実際にフィルタされているかどうかを検証しない。生成時に 1 件でも台湾イベントが返れば「動いた」と判定して登録してしまう。

**修復（commit e1ab468）：**
- `_is_taiwan_relevant(title, description)` を 3 段階で実装：
  1. タイトル（name_ja）に台湾キーワードがあれば即通過
  2. 説明文冒頭 500 字に台湾キーワードが 2 回以上出現
  3. 著者略歴の大学名パターン（`_AUTHOR_BIO_RE`：台湾大学・淡江大学等）を除去してから再判定 → false positive 防止
- DB の既存 active 19 件を `is_active=False` に更新

**教訓：**
1. **keyword= は信用しない**：サイトによっては keyword URL パラメータがサーバー側でフィルタされず、全件返す。新規 scraper 追加時は `dry-run` で取得結果に台湾キーワードが含まれるか必ず確認。
2. **著者略歴の false positive**：書店イベントは著者の大学名・所属に「台湾大学」が出やすい。タイトルに台湾がない場合は 500 字冒頭チェック + 大学名パターン除去が有効。
3. **auto_qa の盲点**：`auto_qa_address_is_venue_name` 等の detector は台湾関連性チェックをしない。keyword フィルタ有効性は人間による定期確認が必要。

---

## 2026-05-06 — 《中村地平上映会》business_hours 亂碼字元 U+3016（DB 手動修正）

**Error**: `business_hours='13:30〖16:30'`。`〖`（U+3016 LEFT BLACK LENTICULAR BRACKET）在 kokuchpro scraper 字元轉換過程中出現，導致時間字串顯示異常（非全形波浪號 ～）。

**Fix**: DB 直接修正 → `business_hours='13:30～16:30'`。

**Lesson**: kokuchpro 頁面的時間分隔符可能含非標準 Unicode（〖 U+3016 等），抓取後需驗證分隔符是否為正確字元（全形波浪號 U+FF5E）。新增「〖 U+3016 偵測」至 scraper 字元正規化流程。

→ Added to SKILL.md §「DB 手動修正 — business_hours 亂碼字元偵測」

---

## 2026-05-06 — 《造山者》片名局部錯誤（DB 手動修正）

**Error**: `name_ja='映画『造山者 ― 世紀の賭け』大阪上映会'`（正式日文片名應為「チップ・オデッセイ 台湾の賭け」）；`name_zh='電影《造山者─世紀的賭注》大阪放映會'`（副標題不正確）。note_creators 薄文本（「続きをみる」截斷），GPT 從截斷文字推出錯誤片名。

**Fix**: `name_ja='映画『チップ・オデッセイ 台湾の賭け』大阪上映会'`；`name_zh='電影《造山者》大阪放映會'`。

**Lesson**: note_creators 薄文本案例中 GPT 可能根據截斷文字推出錯誤片名；修正時應以 `works.title_ja` 為可信基準，優先參照 works 表記錄，而非依賴 GPT 推斷。

---

## 2026-05-06 — 《第2報告》學術子事件未啟用且標題為 slot 識別符（DB 手動修正）

**Error**: 子事件 `97f11903`：`is_active=False`（未啟用）、`name_ja='第2報告'`（slot 識別符，非活動題目）。正確題目 `台湾の「雲南菜」から見る「孤軍」と東南アジア（仮題）` 與 `performer='福田真郷'` 存在於 `raw_description` 中卻未被提取。

**Fix**: `is_active=True`；`name_ja='台湾の「雲南菜」から見る「孤軍」と東南アジア（仮題）'`；`performer='福田真郷'`（手動從 raw_description 提取）。

**Lesson**: 學術 slot 子事件啟用時必須同步更新標題，不得保留 slot 識別符（「第2報告」等）；raw_description 往往含有正確題目，需人工提取，不可依賴 annotator 自動補全。

→ Added to SKILL.md §「Sub-event 啟用 — 標題同步規則」

---

## 2026-05-06 — 《大濛/霧のごとく》主辦誤填 + 導演被填入 performer（DB 手動修正）

**Error**: `organizer='台北駐日経済文化代表処 台湾文化センター'`（商業院線映畫不應有主辦方）；`performer='チェン・ユーシュン'`（導演被誤填至 performer 欄）；`director` 欄為 null；主演（`performers`）也缺漏。

**Fix**: `organizer=null`；`director='チェン・ユーシュン'`；`director_zh='陳玉勳'`；`director_en='Chen Yu-hsun'`；`performer=null`；`performers=['ケイトリン・ファン', 'ウィル・オー']`（主演）。`works` 表同步更新 `director` + `cast_summary`。

**Lesson**: 商業院線映畫 `organizer` 應為 `null`（院線不是主辦方）。**導演（director）≠ 表演者（performer）**：導演必須填入 `director` 欄位，主演填入 `performer` / `performers[]`，兩者嚴禁混填。works 表 `director` / `cast_summary` 需與 events 表同步更新。

→ Added to SKILL.md §「Annotator — Performer / Director Field Rules」

---

## 2026-05-06 — performer/director multilingual fields + performers[] array（commits 3822fb8, 65a50b9, 191d939）

**Change**: migration `054_performer_director_i18n.sql`（performer_zh/en, director_zh/en）+ migration `053_events_performers_array.sql`（performers text[]）+ base.py / database.py / web 多語言 helpers。

**Lesson**:
1. **performer_zh / performer_en 手動修正必須同時 upsert `field_corrections`**: 未鎖定時 re-annotation 會覆蓋修正值。
2. **UI helper `getEventPerformer(event, locale)` 必須使用**: 不可直接取 `event.performer`；locale 優先序：zh → `performer_zh`，en → `performer_en`，fallback → `performer`。
3. **performers[] 回填命令**：`scraper/backfill_location_prefectures.py` 模式可複製——批次讀 performer 欄位拆分成 array，寫入 performers 欄位。

→ Added to SKILL.md §「Annotator — Performer / Director Field Rules」

---

## 2026-05-06 — AI translation marker 語言不一致污染 performer_en（commit f07c170）

**Error**: `performer_en` / `director_en` 被填入 `（AI翻譯）`（中文後綴），正確應為 `(AI Translation)`（英語後綴）。DB event `bf783b90` 已被錯誤標記。

**Fix**: annotator.py 依欄位語言分別追加：`performer_zh` → `（AI翻譯）`；`performer_en` → `(AI Translation)`；`performer` / `name_ja` → `（AI翻訳）`（日語）。DB 手動修正 + `field_corrections` 鎖定。

**Lesson**: 多語言 AI 翻譯 marker 必須語言別分開指定；跨語言後綴靜默污染資料，肉眼不易察覺。

→ Added to SKILL.md §「Annotator — Performer / Director Field Rules」

---

## 2026-05-06 — note_creators thin content + blog source headline rewrite guard（commit b589fbb）

**Error**: `note_creators` 的 `raw_description` 通常只有截斷文字「続きをみる」——純介紹文章/觀影報導被誤收錄為活動資料，organizer 欄位被 GPT 幻想填充。

**Fix**: `note_creators` 加入 `_HEADLINE_REWRITE_SOURCES` frozenset；4 件 note_creators 事件設 `is_active=false` 或清空 organizer。

**Lesson**:
1. `_HEADLINE_REWRITE_SOURCES` 必須涵蓋所有部落格/創作平台來源（note_creators、google_news_rss、nhk_rss、prtimes、walkerplus）。
2. 純介紹文/觀影報告不是活動資料，應設 `is_active=false`，不依賴 annotator 過濾。

→ Added to SKILL.md §「Annotator — Headline Rewrite Sources & Blog Source Guard」

---

## 2026-05-06 — collection attribution 誤填 location_name（commit 47f8184）

**Error**: Annotator 將 `〇〇美術館蔵` 識別為 `location_name`（e.g. yebizo event `e37db12e` → `location_name='高雄市立美術館'`）。`〇〇蔵` 是作品所蔵機關標記，非活動場地。

**Fix**: SYSTEM_PROMPT 新增 COLLECTION ATTRIBUTION NOTE。DB 手動修正 `location_name='東京都写真美術館'`（Yebisu Garden Cinema）。固定場地 scraper 直接設定靜態 `location_name`。

**Lesson**: `〇〇美術館蔵` / `〇〇所蔵` 是作品借展標記，不是活動場地。固定場地的 scraper 應在程式碼層設靜態 `location_name`，避免依賴 GPT 判斷。

→ Added to SKILL.md §「Annotator — Collection Attribution Guard」

---

## 2026-05-06 — performer regex：`_MUKAE_RE` lookahead 缺漏 + `_PERFORMER_INTRO_RE` separator `+`→`*`（commits 6c2f1ab, fe8b273）

**Error 1**: `_MUKAE_RE` lookahead 只覆蓋 `をお迎え` / `を迎え`，未包含 `をゲストに迎え`，導致 `一青窈氏をゲストに迎え` 無法捕捉。

**Fix 1**: `_MUKAE_RE` 追加 `をゲストに迎え` pattern。

**Lesson 1**: `_MUKAE_RE` 必須完整覆蓋所有敬語形式。目前三種：`をお迎え` / `を迎え` / `をゲストに迎え`。新出現形式需立即補充。

**Error 2**: `_PERFORMER_INTRO_RE` separator 為 `+`（1個以上），導致 `絵本作家林廉恩氏`（角色詞直連人名，0個分隔符）無法匹配。

**Fix 2**: separator 從 `+` 改為 `*`（0個以上）。

**Lesson 2**: 日語角色詞與人名直連無分隔符是常見寫法，separator 必須為 `*`（0個以上）而非 `+`（1個以上）。

→ Added to SKILL.md §「Annotator — Performer / Director Field Rules」

---

## 2026-05-06 — Add StrangerScraper (Eigaland JSON API)

**Source**: Stranger cinema (東京墨田区) — stranger.jp
**Strategy**: Loop 90-day window via `listByDomainAndDate`, filter `movieDetail.countries == 台湾`, one Event per movieId.
**Key lesson**: `synopsis` field is base64-encoded HTML — always decode via `base64.b64decode → HTMLParser`. `openDate` in list API is the release date, not the screening date; use the query date as screening date.
**Dry-run result**: 1 Taiwan movie found (「霧のごとく」 / 大濛, 2026-05-08〜05-14).

---

## 2026-05-06 — gnews start_date RSS snippet fallback + tokyoartbeat slug guard 擴大（commits 7df9f56, 1c0f69a）

### google_news_rss — RSS snippet 作為 start_date fallback（commit 1c0f69a）
- `_extract_start_date(article_text or description_plain, pub_date)`：article fetch 失敗時 `article_text=None`，`or description_plain` 使 RSS snippet（< 200 字）成為 fallback 輸入，GPT 從稀少文字猜出錯誤日期
- 修復：改為 `start_date = _extract_start_date(article_text, pub_date) if article_text else None`
- 教訓：RSS snippet 不可用作日期提取來源；article fetch 失敗時直接 `start_date = None`，由 annotator 的 `（記事配信日: YYYY-MM-DD）` 前綴確保年份正確

### tokyoartbeat — Contentful 佔位符 slug fallback 條件過嚴（commit 7df9f56）
- Contentful `scheduleStartsOn` 佔位符不只 `YYYY-01-01`，也有 `YYYY-01-15`（events `977da793`、`e7cf2a51`）
- `month == 1 and day == 1` 的 slug fallback 條件漏掉 day 2–31，造成 DB 日期錯誤
- 修復：條件改為 `month == 1`（Contentful 使用整個 1 月作佔位，不限 Jan 1）
- 教訓：審核所有 Contentful 系列展 scraper 的 slug fallback 條件，正確用 `start_date.month == 1`

---

### 2026-05-05 — auto_qa TAIWAN_VENUE_KEYWORDS 子字串假陽性：新北 ⊂ 新北島（commit 6b7174a）
- `'新北'` 是 `'新北島'`（大阪市住之江区）的子字串，`auto_qa_taiwan_venue` 對 event `371cf624`（GRAFFYHALL venue）反覆誤觸
- 每次 scraper upsert 更新 `updated_at` → dedup 重新觸發 → 即使 dismissed 仍再建立新報告
- 修復：移除裸字串 `'新北'`，保留更精確的 `'新北市'`；dismiss 當時 pending 的假陽性報告
- 教訓：台灣地名關鍵字需完整行政單位名稱（市/縣），禁用縮寫裸字串；新增前需 grep 日本地名清單

---
### 2026-05-05 — tokyoartbeat 三連 bug：slug 日期佔位符 / GPT organizer 幻覺 / event_form 缺失（commit a1e58a9）
- scheduleStartsOn=YYYY-01-01 是 Contentful 年度系列展佔位符，需從 slug 末尾提取實際日期
- scraper 未設 organizer → GPT 從 "works from our collection" 幻想出橫浜美術館
- 設 organizer=venue_name；raw_description 加 主催: 行作為 GPT 明確信號
- reviewed 事件的 event_form 永遠不被 annotator 修補，需 scraper 層設定

---

## 2026-05-05 — event 82a106db 手動修正：location_name 誤填 organizer + 子場地地址（note_creators）

### 問題
`note_creators` source 事件 `82a106db`：`location_name` 欄位被誤填為 organizer 名稱（`NPO法人埼玉県日台親善協会`），`organizer` = null，`location_address` 只有「埼玉県」（過度省略）。

### 修復
直接 DB 更新三欄位：
- `organizer` = `NPO法人埼玉県日台親善協会`
- `location_name` = `台湾カフェ「茶と菓」（四萬部寺内）`（子場地 + 親設施標記）
- `location_address` = `埼玉県秩父市栃谷418`（四萬部寺官網查得）

### 教訓
1. 子場地（寺内カフェ）的地址應使用**親設施地址**，`location_name` 格式建議 `「子場地」（親設施内）`。
2. `note_creators` 不走 annotator 主流程，此修正未寫入 `field_corrections`（影響有限）。
3. `organizer` 與 `location_name` 若值互調，辨別線索：法人後綴（協会・団体・財団）→ organizer；設施詞（カフェ・ホール・スペース）→ location_name。

---

## 2026-05-05 — tsutaya_portal.py 建立 + scraper_source_name 再度漏填（第 3 件）

### 問題
`tsutaya_portal.py` 新增、`main.py` 登錄、dry-run 確認後に task_complete を呼んだが、`research_sources.scraper_source_name` が NULL のまま残った。ユーザーが管理後台を確認して発見し、手動で補完。

### 根因
同じ問題が walkerplus（2026-05-05）でも発生済みにもかかわらず、Combined Post-Build Audit が存在しなかったため（SCRAPERS 専用 audit しかなかった）、`scraper_source_name` は肉眼チェックに依存していた。

### 修復
```python
sb.table('research_sources').update({
    'scraper_source_name': 'tsutaya_portal',
    'scraping_feasibility': 'easy',
    'status': 'implemented',
}).eq('id', 229).execute()
```

### 教訓 / 対策
1. **Combined Post-Build Audit を新設**（SKILL.md `## ⚡ Combined Post-Build Audit`）：main.py SCRAPERS + `research_sources.scraper_source_name` を同時検査するワンコマンド。
2. **agent.md Phase 3 Step 4 を差し替え**：SCRAPERS-only audit → Combined audit に更新。「🎉 ALL CLEAR が出るまで Phase 4 に進むな」と明記。
3. **agent.md Phase 5 pre-commit gate 更新**：新規ソース・バグ修正とも Combined audit を必須チェックボックスに追加。
4. **SKILL.md Promotion checklist 更新**：「auto_generate 限定」の表記を削除、すべての新規 scraper に適用と明記し、ステップ 5 を「Combined audit で ALL CLEAR 確認」に変更。

---

## 2026-05-05 — walkerplus.py 建立 + Promotion checklist 遺漏 research_sources 登錄

### 問題
walkerplus.py 新增後，Promotion checklist 的步驟 3/4（`research_sources` 登錄 + `scraper_source_name` 填寫）被遺漏。使用者提醒後才補做。
另外，`update_source.py` 不支援 `implemented` 狀態，需直接寫 DB。

### 根因
Promotion checklist（5 步驟）在 scraper 建立時沒有完整執行，只做了 main.py 登錄就結束了 session。

### 修復
直接 upsert `research_sources` 表：`status='implemented'`、`scraper_source_name='walkerplus'`、`scraping_feasibility='medium'`、`agent_category='event_listing'`。

### 教訓
1. **Promotion checklist 5 步驟必須在同一個 session/commit 全部完成**，不能分段做。
2. **`update_source.py` 只支援 `researched`/`not-viable`**；`implemented` 狀態需直接寫 DB（Supabase SDK upsert）。
3. walkerplus HTML 解析注意事項：`m-articleset--3` 有 3 個實例，必須用 `.m-detail__contents` 限定範圍取說明文；場地 link 順序是 [地域, 都道府縣, 市区町村, 施設名]，最後一個 link = `location_name`，中間 links 組合 = `location_address`；無關鍵字搜尋 API，只能用分類頁 + title 過濾。

---

## 2026-05-05 — note.com creator 追加 4 件（commit `d7da54a`）

### 問題
nittaisinzen、vectortw、taiwanryugaku、tcml_osaka を note.com クローラーに追加。

### 修復
- `note_creators.py` の `CREATOR_META` に 4 行追加
- `research_sources` の status を `implemented` に同時更新
- 事前に RSS dry-run（28 → 122 件）で件数確認

### 教訓
**note.com creator 追加は 2 ステップをセットで実行**：
1. `CREATOR_META` に `{slug: ..., category: ..., location: ...}` を 1 行追加
2. DB の `research_sources` を `status=implemented` に更新
どちらか片方だけでは `/admin/sources` の件数表示や次回 researcher.py の重複排除が狂う。

---

## 2026-05-05 — location_address = location_name 全 scraper 稽核修正（commits `9d6e0fc`、`f7a8a71`）

### 問題
多個 scrapers 將 `location_address` 設為與 `location_name` 相同的值。受影響 scrapers：iwafu、jposa_ja、kokuchpro、koryu、prtimes、taioan_dokyokai、taiwan_festa、waseda_taiwan。

### 根因
Scrapers 取得 combined "location" 欄位時，直接複製到兩個欄位。iwafu 的 `場所：` 文字同時包含場地名稱和地址，但未分開解析。

### 修復
- **iwafu（commit `f7a8a71`）**：從 `場所：` 後方文字中用 `_ADDR_RE` 提取真實地址，venue name 和 address 分開設值
- **其他 7 個 scraper（commit `9d6e0fc`）**：逐一稽核，有地址可解析時拆分；無實際地址時 `location_address = None`

### 教訓
- **`location_address ≠ location_name` 是全 scraper 通用規則**——不只是 iwafu 特定
- Combined location 欄位必須解析：venue name → `location_name`，street address → `location_address`
- `_ai_or_existing()` 對非 null DB 值不覆寫，所以 scraper 端寫入錯誤值後 annotator 無法修正
- `auto_qa_address_is_venue_name` 偵測器會持續監控此 anti-pattern

---

## 2026-05-05 — enrich_location GPT 回傳 venue name 作為 address + sub-venue 規則（commit `628e3e7`）

### 問題
`enrich_location.py` GPT 從 `会場：仙六屋カフェ` 直接提取 `仙六屋カフェ` 作為 `location_address`，造成 `location_address == location_name`（失敗標誌）。

### 修復
1. SYSTEM_PROMPT Rule 6（identical → return null）：address == venue_name 時回傳 null。
2. SYSTEM_PROMPT Rule 7（子場地親設施地址）：子場地（如 `○○ビル2階`）需用親設施地址，不得用子場地名。
3. 程式碼 guard：寫入前 `if addr.strip() == venue: skip + log warning`（雙重保護）。
4. SELECT 加入 `location_name` 供 guard 使用。

### 教訓
- `address == venue_name` 是地址抽取失敗的確定標誌，不得寫入 DB。
- **雙層防護**：SYSTEM_PROMPT 規則（GPT 層）+ 程式碼 guard（程式碼層）——不能只靠 GPT 自律。
- Sub-Venue Parent Address Rule 需同步套用至 enrichment pipeline，不只 scraper 端。

---

## 2026-05-05 — Sub-event annotation with parent inheritance（commit `38f4f3a`）

### 問題
Scraper 直接建立的 sub-events（如 rightscube 各戲院子活動）有 `annotation_status='pending'`，但 annotator 只處理 GPT-generated sub-events。Scraper-created sub-events 缺少 category、description 等欄位。

### 修復
`annotator.py` 修改為也 pick up scraper-created sub-events（有 `parent_event_id` 且 `annotation_status='pending'`），從 parent event 繼承 category 和 context。

### 教訓
- Annotator 必須處理 **所有** pending sub-events，不只 GPT 產生的
- Sub-event annotation 從 parent 繼承 category 是合理預設——子活動通常與 parent 同分類

---

## 2026-05-05 — location_address = location_name 跨 9 scraper 大範圍擴散

### 問題
修復 iwafu.py 後，對全體 scraper 執行 grep 掃描，發現以下 8 個 scraper 有相同模式：
- `kokuchpro`：初始值 `location_address = card["venue_card"]`；detail page 無 address 時 `elif venue: address = venue`
- `taiwan_matsuri`：`elif location_name: location_address = location_name`
- `taioan_dokyokai`：`if location_name and not location_address: location_address = location_name`
- `koryu`：`_extract_location_address(body_text) or (venue if venue else None)`
- `taiwan_festa`、`prtimes`、`jposa_ja`：直接 `location_address=venue`
- `peatix`：fallback chain 末端無 guard，某些情況下 address 等於 name
- `waseda_taiwan`：`elif venue: location_address = venue`

DB 受影響：65 件 `location_address = location_name`（kokuchpro 43、peatix 13、google_news_rss 3、koryu 3 等）

### 根因
annotator `_ai_or_existing()` 保護：非 null 的 `location_address` 不被覆蓋。Scraper 寫入錯誤值後永久鎖定，auto_qa 持續報告 `auto_qa_address_is_venue_name` 但無法自動修復。

### 修復（commit `9d6e0fc`）
- 9 scraper：移除所有 venue-as-address fallback；找不到真實地址 → `None`
- peatix：Canonicalize 前加 guard
- DB：65 件 bulk-update

### 教訓
1. **每次修 location 相關 bug 後，必須 grep 全體 scraper**：`grep -rn 'location_address.*=.*venue\|location_address.*location_name' scraper/sources/`
2. **通用 guard 模式**（peatix 已採用，其他 scraper 可選）：
   ```python
   if location_address and location_address == location_name:
       location_address = None
   ```
3. **DB 掃描命令**（每次懷疑有 address=venue 問題時執行）：
   ```python
   r = sb.table('events').select('id,source_name,location_name,location_address').execute()
   same = [e for e in r.data if e['location_address'] and e['location_address'] == e['location_name']]
   from collections import Counter; print(Counter(e['source_name'] for e in same))
   ```

---

## 2026-05-05 — artistcafe: auto-generated scraper had no Taiwan filter + wrong description selector

**Error:** `artistcafe.py` は `?keyword=台湾` URL パラメータを使っていたが、artistcafe.jp はこのパラメータを無視しサイト全体のイベントを返す。結果として 12 件中 8 件（後に 14/17 件と判明）が台湾無関係のイベントとして DB に登録された。また `raw_description` に `body.inner_text()` を使っていたため、ナビゲーションヘッダー（`OPEN 11:00 - 19:00 アクセス …`）が格納されていた。

**Root cause:** auto-generated scraper はサイトが keyword 検索をサポートすると仮定したが、実際には client-side でもなく完全に無視されていた。詳細ページ取得に `article` セレクターではなく `body` を使っていたため、コンテンツが汚染された。

**Fix:**
1. `SEARCH_KEYWORD` と `?keyword=` URL パラメータを削除
2. `_TAIWAN_KEYWORDS` + `_is_taiwan()` 関数を追加
3. 詳細ページ取得で `article` セレクター優先、fallback `body`
4. `_is_taiwan()` チェックをイベント作成前に追加（非台湾はスキップ）
5. DB の非台湾イベント 14 件を `is_active=false` に更新

**Result:** dry-run で 12 件→4 件（台湾関連のみ）に正常フィルタリング。

**Lesson:** auto-generated scraper の `?keyword=` フィルターは必ずローカルで検証すること。「keyword あり」と「keyword なし」の URL を両方試して返件数が同じなら、サイトがパラメータを無視している。その場合は `_is_taiwan()` をスクレイパー内に実装する。

---

## 2026-05-05 — 24 scrapers lost in SCRAPERS when 045d1fa rewrote main.py [multiple]

**Error:** Commit `045d1fa`（add WasedaIclScraper）で `main.py` が書き直され、既存の 24 個の scraper が import と SCRAPERS から消えた。同日に `8a9dcd7` で ArtistcafeScraper を追加したが audit を実行せず、24 個の欠落は発見されなかった。

**Affected scrapers (24):** LivepocketScraper, FukuokaNowScraper, PrtimesScraper, MaruhiroScraper, EurospaceScraper, TokyoArtBeatScraper, HankyuUmedaScraper, DaimaruMatsuzakayaScraper, CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper, GoogleNewsRssScraper, NhkRssScraper, GguideTvScraper, MotScraper, TransitStoreScraper, GoTaiwanScraper, TaiwanFestaScraper, TiffJpScraper, RightscubeScraper

**Fix:** 24 個の import + SCRAPERS エントリを復元（commit `6a83c64`）。audit で 66 scrapers 確認。

**Detection:** `grep -i "shin_bungeiza" scraper/main.py` が exit 1 → 手動調査 → audit で 24 個の UNREGISTERED 判明。

**Lesson:** `main.py` を ANY 理由で編集した後は、必ず SCRAPERS audit を実行。特に「新しい scraper を 1 個追加」する際に既存のリストを書き直すと、既存のすべての登録が消えるリスクがある。

---

## 2026-05-05 — ArtistcafeScraper: ファイル存在・POC完了・commit済みなのに SCRAPERS 未登録で 3 日間無視された

**Error:** `scraper/sources/artistcafe.py` はファイルとして存在し、feature branch にも commit されていたが、`main.py` への `import` と `SCRAPERS` 登録が一度も実施されなかった。CI は 3 日以上この scraper を完全に無視した。

**Root cause:** 「POC 完成 → spec を parked → feature branch に commit」という flow で、「import + SCRAPERS 登録」ステップが別タスクに先送りされ、そのまま見落とされた。spec に「Phase 1: import + SCRAPERS 追加」と書いてあったが、実行されなかった。

**Fix:** `from sources.artistcafe import ArtistcafeScraper` と `ArtistcafeScraper()` を同一コミット（`8a9dcd7`）で追加。dry-run で 12 events 確認。

**Lesson:** scraper ファイルと `main.py` への登録は **atomic** でなければならない。spec の「次のステップ」として書いた時点で、すでに登録漏れのリスクがある。POC → spec parked → 後で登録、というパターンは禁止。

**Protocol fix:** agent.md Phase 5 と SKILL.md Documentation Protocol の両方に、コミット前に確認すべき numbered checklist（import・SCRAPERS・per-source SKILL・history・DB）を追加。ファイルの存在だけでなく、登録の完了を明示的に確認するまで commit しない。

---

## 2026-05-04 — hakusuisha 三連 bug：char limit / regex 欠缺 / self-prefix 干擾（commit `a0292a2`）

### 問題
hakusuisha.py 修正後もなお `location_name`、`business_hours`、`organizer` が null。三つの連鎖バグ。

### 根因
A. **char limit 4000**：nav/menu ノイズが予算を消費し、`■日時：`・`会場：`・`主催：` が切断点の外にある。
B. **`_KAIJO_RE`・`_SHUKAI_RE`・`_TIME_RE` 未定義**：会場・主催・時間の regex が存在しなかった。
C. **Self-prefix interference**：`raw_description` 先頭に `開催日時: YYYY年MM月DD日\n\n` を prepend した後で `_JITSU_RE.search(raw_description)` を実行すると、自己注入したプレフィックスの `開催日時:` にマッチし、`_TIME_RE` が本文の `HH:MM〜HH:MM` を永遠に見つけられなくなる。

### 修復（commit `a0292a2`）
- char limit 4000 → 8000（nav ノイズ消費分を確保）
- `_KAIJO_RE`、`_SHUKAI_RE`、`_TIME_RE` を追加
- `business_hours` 抽出：`_JITSU_RE.search(raw_description)` → `_TIME_RE.search(full_description)` に変更（プレフィックス回避）

### 教訓
1. **Self-prefix interference**：`raw_description` に prefix を prepend する **前に** すべての regex 抽出を完了させること。または prefix にマッチしない専用 pattern を使用。
2. **char 予算検証**：detail-page scraper は HTMLParser 適用後の実際のテキスト長とキーワード位置を確認してから上限を設定すること。
3. **SKILL.md 参照**：「Self-injected Prefix Interference」セクションを参照。

---

## 2026-05-04 — auto_research: pending ステータス候補が永久スキップ（commit `5d2585d`）

### 問題
migration 033 で `auto_research_status DEFAULT 'pending'` が設定されているが、
batch クエリが `NULL or error` しか条件に入れていなかった。
→ 新規候補 14 件が 2 日間まったく評価されなかった。

### 根因
`research_sources.auto_research_status` に DEFAULT 'pending' が設定されており、
INSERT 時に明示的な NULL 指定がなければ 'pending' が入る。
しかし `auto_research.py` の batch クエリが `.or_("auto_research_status.is.null,auto_research_status.eq.error")` のみ → 'pending' は永遠にマッチしない。

### 修復
`.or_()` に `auto_research_status.eq.pending` を追加。
DB で 14 件を NULL にリセット → 翌夜再評価。

### 教訓
**migration で DEFAULT 値を追加した場合、batch クエリの `NULL` 条件に DEFAULT 値も含めること**。
`DEFAULT 'pending'` を設定したなら `.or_("...is.null,...eq.pending")` の両方が必要。

---

## 2026-05-04 — researcher.py: 重複提案バグ 2 件（commit `7554002`）

### 問題
GPT が Shibuya Eggman、DjangoGirls Japan、Raycast Community 等を毎日再提案し続けた。

### 根因
1. `url_verified=False` のソース（URL 疎通確認失敗）が DB に保存されなかった → `known_urls` に含まれず、GPT に「未知」として渡り続けた
2. `known_urls` に渡す前に `[:30]` でリストを切り詰め → 186 件中 156 件が GPT に見えていなかった

### 修復
1. `url_verified=False` の初回提案を `status=not-viable` として DB 保存
2. `[:30]` 制限を削除（全件渡す）

### 教訓
- **GPT に渡す既知 URL リストは全件渡す**。ソート後の先頭 N 件に切り詰めると、後半の URL が毎日「新規候補」として再提案される
- **検証失敗ソースも DB に記録**。`url_verified=False` でも `not-viable` として保存しなければ、GPT は翌日も同じ URL を提案する

---

## 2026-05-04 — auto-scraper branch 長期放置によるマージ衝突（commit `7cedc68`）

### 問題
`feat/auto-scraper-artistcafe` と `main` の両方で `main.py` の同じ行（import + SCRAPERS リスト）に
別々の scraper が追加されており、マージ時に conflict。
HEAD（NoteCreatorsScraper）と branch（ArtistcafeScraper）を両方保持して手動解決。

### 根因
feature branch が数日放置され、その間 main 側に複数の scraper 追加コミットが積まれた。

### 教訓
**auto-scraper feature branch は生成後 24 時間以内にマージする**。
`SCRAPERS` リストは全員が同じ行/ブロックを編集する → 放置するほど conflict が深刻化。

---

## 2026-05-04 — taiwan-filmake 全國上映子活動手動插入 + シアターセブン 上映資料更新

### taiwan-filmake 全國上映館子活動手動插入（source_name=rightscube）
- **內容**：以 `source_name="rightscube"` 手動插入 4 館子活動（札幌・神奈川・神戸・大阪），全部設 `parent_event_id = 995801cc`（K's cinema 系列父事件）
- **annotator**：執行完成，全部 `annotation_status = 'annotated'`
- **source_id 命名不一致問題**：手動插入前發現存量 DB 資料的 source_id 格式有誤（`taiwan-filmake_jack-betty` 而非 `taiwan-filmake_jackandbetty`），需先修正再插入，否則 scraper 後續 upsert 無法對應到正確記錄
- **教訓**：手動插入 DB 記錄前，必須先用 `--dry-run` 確認 scraper 實際會產生的 source_id 格式，格式須完全一致；`parent_event_id` 必須使用 UUID，不可使用 source_id 字串

### シアターセブン 上映資料更新
- **來源**：`https://www.theater-seven.com/mv/mv_s1030.html`（戲院詳細時刻表頁）
- **更新欄位**：`end_date = 2026-05-15`（之前為 NULL）；`business_hours` 補入每日詳細上映時間
- **教訓**：`end_date = NULL` 的戲院放映事件，通常在戲院個別詳情頁有完整場次期間，值得直接查詢並手動修正

---

## 2026-05-04 — performer 欄位 + Tier 1.5 annotator SYSTEM_PROMPT 擴展

### performer 欄位新增（commit `edd101e`）
- **Migration 038：** `events` 新增 `performer text` 欄位
- **base.py：** Event dataclass 新增 `performer: str | None = None`
- **Annotator SYSTEM_PROMPT：** 新增 PERFORMER EXTRACTION RULES——bare personal name，去除敬稱（氏、先生、さん 等），非人物事件回傳 null
- **Detail page：** Rich Results JSON-LD 注入 `performer` property，修復 4 個 Google Rich Results warnings

### Tier 1.5 annotator 新增 price / organizer_url / event_status 規則（commit `0d4a0de`）
- **SYSTEM_PROMPT 新增區塊：** PRICE PARSING RULES、ORGANIZER URL RULES、EVENT STATUS RULES
- **新增 validators：** `_validate_organizer_url`、`_validate_price_amount`、`_validate_price_currency`、`_validate_event_status`
- **Price parsing：** 支援 `1500円`、`¥1,500`、`無料`、`free` 等格式
- **教訓：** 新增 annotator schema 欄位時，必須同步加 SYSTEM_PROMPT 規則 + validator 函數 + migration

### hakusuisha 相對 URL 修正（commit `1b344f7`）
- **問題：** hakusuisha.py 的新聞連結使用相對路徑 `../news/xxx`，未正確解析為完整 URL
- **修正：** 改用 `urljoin(base_url, relative_path)` 解析相對 URL
- **教訓：** 所有 scraper 解析 `<a href>` 時，一律使用 `urljoin()` 處理，不假設 URL 為絕對路徑

### bookandbeer + hakusuisha auto-generated scrapers 上線（commit `db48ad3`）
- 兩個新 scraper 透過 auto_generate pipeline（Phase 2）產生並 promote
- bookandbeer：書店＋啤酒吧活動平台
- hakusuisha：白水社出版社新聞（需上述 urljoin 修正）

### P0/P1 admin correction protection 與 annotator 整合（commits `9eab3aa`、`c393e93`）
- **`_ai_or_existing()` 函數：** 在 re-annotation 中保護既有非 null 值（P0）和 `field_corrections` 表中的明確修正（P1）
- **`human_field_map` 載入：** annotator 啟動時查詢 `field_corrections` 表，建立 event_id → protected columns set
- **Few-shot context：** 過去修正紀錄注入 SYSTEM_PROMPT，讓 GPT 學習
- **irrelevant status bug fix：** `--fix-reviewed` 不再誤處理 `irrelevant` 事件
- **教訓：** annotator 的欄位保護必須有兩層——隱性（保留非 null）+ 明確（field_corrections 永久保護）

---

## 2026-05-04 — gguide_tv 電視節目被錯標為 movie（annotator.py VALID_CATEGORIES 未同步 types.ts）
- **問題**：事件 3d835d19（ジーンちゃん 台湾・台北 食旅 TV 節目）被標為 movie 而非 tv_program
- **根本原因**：types.ts 已新增 10 個分類（tv_program 等），但 annotator.py VALID_CATEGORIES 和 SYSTEM_PROMPT 從未同步；GPT 無法選用 tv_program，被迫改選 movie
- **修正**：VALID_CATEGORIES 同步 types.ts；SYSTEM_PROMPT 加 tv_program/drama/documentary 定義；_inject_keyword_categories 加 TV 廣播標記注入（放送:/ジャンル: → tv_program）；DB 直接修正 7 筆 gguide_tv 事件
- **教訓**：每次 types.ts 新增 Category → 必須同步更新 annotator.py VALID_CATEGORIES + SYSTEM_PROMPT 分類列表 + 分類定義（三處同步）。驗證命令見 SKILL.md § Three-Location Sync Rule。

---

## 2026-05-04 — annotator.py SYSTEM_PROMPT 新增「日本→台灣單向事件排除規則」
- **背景**：3 筆事件（IMAGINE JAPAN in 台湾 f40980a8、Perxona AI 73981453、CLIP STUDIO PAINT 928aa003）被收錄，但其性質是「日本產品/企業進入台灣市場」，與台日文化交流無關
- **修正**：
  - DB 直接 deactivate 3 筆事件（`is_active = false`）
  - annotator SYSTEM_PROMPT 新增 TAIWAN-VENUE EVENTS 區塊：明確 INCLUDE（共同組織/演出/交流/學習）vs EXCLUDE（日本向台灣銷售/贊助/產品發表）
  - auto_qa 新增 `auto_qa_taiwan_venue` 偵測器：flags 台灣地址事件供人工審核
- **教訓**：「Taiwan 在 location_address」不等同「Taiwan-relevant」。日本企業在台灣市場的商業行為不是台日文化活動，需 SYSTEM_PROMPT 明確區分。

---

## 2026-05-04 — rightscube.co.jp 新增爬蟲（台灣電影戲院放映）
- **設計決策**：
  - parent event = 全國上映概覽（source_id: `rightscube_{slug}`）
  - child events = 各戲院放映（source_id: `rightscube_{slug}_{venue_key}`），venue_key 從戲院 URL 推導（deterministic、穩定）
  - venue_key 規則：SNS（x.com/twitter/instagram）→ URL path component；CDN host（jimdofree/thebase）→ subdomain；一般網域 → domain minus TLD，lowercased，非英數字替換為 `-`
  - 靜態 HTML，不需 Playwright；`movie_title_lookup` 自動補充官方中英文片名
- **首次執行 DB 修復**：手動修正 source_id（`taiwan-filmake_jack-betty` → `jackandbetty`），建立 parent UUID，更新 4 筆 child 的 parent_event_id
- **HTML 結構 — Unicode Bold Math section 標題**：section 標題（如 `𝗧𝗛𝗘𝗔𝗧𝗘𝗥`）使用 Unicode Mathematical Bold Sans-Serif 字元（U+1D5D4+），無法直接與 ASCII 字串比對，必須以 `_normalize_bold_math()` 轉換後再做 section 識別
- **HTML 結構 — `<span><a>` 包裝下的 sibling 日期**：劇場連結結構為 `<span><a href="...">劇場名</a></span>｜5/17(日)・5/24(日)`，日期文字是 `a.parent.next_sibling`（`<span>` 的兄弟節點），而非 `a.next_sibling`（= None）
- **Homepage 必要性**：`/movies/` 目錄頁只列常規放映作品；特集上映系列（如 taiwan-filmake）只出現在 homepage → 爬蟲必須同時爬 homepage + /movies/ 目錄
- **教訓**：首次加入新爬蟲時，若已有存量 DB 資料（格式錯誤），必須執行一次性修正 script 補齊 parent_event_id；rightscube venue_key 推導規則是 production contract，勿修改

---

## 2026-05-04 — main.py pipeline 補齊 enrich 步驟 + ks_cinema DB 修正

### main.py 新增 enrich_movie_titles / enrich_person_names 呼叫
- **問題**：手動 `python main.py --source ks_cinema` 執行後，電影片名得到直譯（`循環的面影`）而非官方片名（`車頂上的玄天上帝`）。`enrich_movie_titles()` / `enrich_person_names()` 只在 CI 以獨立步驟執行，`main.py` 未呼叫。
- **修正**：`main.py` 新增 `from annotator import enrich_movie_titles, enrich_person_names`，在 `annotate_pending_events()` 之後呼叫。enrich 為 idempotent，CI 二次執行無影響。
- **教訓**：新增 enrichment 函數時，必須同時加到 `main.py`（手動）和 `scraper.yml`（CI）。Pipeline 完整順序：scrape → merger → annotate → enrich_movie_titles → enrich_person_names → IndexNow。

### ks_cinema 電影片名 DB 手動修正
- 6 筆事件 `name_zh` / `name_en` 直譯修正為官方片名（`車頂上的玄天上帝`、`阿嬤的夢中情人`、`導演你有病`）

### ks_cinema sub-event hierarchy 修正
- 3 筆 sub-event 設正確 `parent_event_id`；2 筆舊版 `_sub1` 記錄 deactivate

---

## 2026-05-04 — hakusuisha body text 截斷 + `開催日時:` 前綴誤匹配（commit `a0292a2`）

**問題**：`scraper/sources/hakusuisha.py` 詳情頁的 `location_name`、`business_hours`、`organizer` 全部為 `null`。

**根本原因（兩個 bug）**：

**Bug 1 — body text 截斷**：Playwright `body.inner_text()[:4000]` 與 HTTP fallback `[:4000]` 截斷，導航列（nav menu）佔去大量字元，把 `■日時：` 推到截斷點之後，導致日時/会場/主催 label 全部被截掉。

**Bug 2a — 缺少 会場:/主催: 提取邏輯**：auto-generated scraper 只有日期提取，沒有 `会場:`/`主催:` regex，`_KAIJO_RE`、`_SHUKAI_RE`、`_TIME_RE` 都不存在。

**Bug 2b — `開催日時:` 前綴誤匹配（最重要）**：scraper 自身在 `raw_description` 開頭加了 `開催日時: 2026年4月26日\n\n` 前綴。之後用 `_JITSU_RE.search(full_description)` 找 `日時:` 時，**先匹配到此前綴**（`開催日時:` 包含 `日時:`），group(1) = `2026年4月26日`（無時間），`_TIME_RE` 永遠找不到時間。

**修正**：
- Bug 1：截斷上限提高至 8000 字元
- Bug 2a：新增 `_KAIJO_RE`、`_SHUKAI_RE`、`_TIME_RE`，在 `_extract_cards()` 末段提取 location / hours / organizer
- Bug 2b：改為直接 `_TIME_RE.search(full_description)` 繞過前綴問題

**教訓**：
- auto-generated scraper body text 上限 4000 不夠，nav/header 噪音吃掉預算；**最低建議 8000 字元**
- **Self-injected Prefix Interference**：scraper 自加的前綴（如 `開催日時:`）若包含 field label 關鍵字，後續 regex 的 `re.search()` 會先匹配前綴而非正文；解法是在加前綴前完成提取，或用更具體的 pattern（如 `_TIME_RE`）直接搜索全文

---

## 2026-05-04 — `scraper_runs` source 名查詢陷阱：`_scraper_key()` 轉換規則

**Error:** 調查「未執行的 6 個爬蟲」時，用 `cinemarine`、`moonromantic`、`tiff`、`tokyoartbeat` 等 class 前綴查詢 `scraper_runs.source`，全部回傳 NO RUNS FOUND，誤判為未執行。

**Root cause:** `scraper_runs.source` 儲存的是 `_scraper_key()` 的輸出，規則是把 class name 的 CamelCase 邊界加底線並轉小寫：`CineMarineScraper → cine_marine`、`MoonRomanticScraper → moon_romantic`、`TiffJpScraper → tiff_jp`、`TokyoArtBeatScraper → tokyo_art_beat`。手動輸入時省略底線或 suffix 就會對不到任何記錄。

**Fix:** 查詢前執行：
```bash
cd scraper && python3 -c "
import sys; sys.path.insert(0, '.')
from main import SCRAPERS, _scraper_key
for s in SCRAPERS:
    print(_scraper_key(s))
" | sort
```
找到精確 key 名後再查 DB。

**Lesson:** 永遠不要從記憶中猜測 `scraper_runs.source` 的 key — 必須從 `_scraper_key(scraper)` 輸出取得正確名稱。常見陷阱：含縮寫（`Jp`→`_jp`）、多字複合（`ArtBeat`→`art_beat`）、連寫縮寫（`Ssff`→`ssff`，但 `TaipeiTCC`→`taipei_t_c_c`）。

---

## 2026-05-04 — `scraper_runs.notes` 現在記錄例外類型與訊息（commit `7e9f617`）

**Change:** `main.py` 的 scraper 失敗處理改為：`"notes": f"{type(exc).__name__}: {exc}"[:500]`

**Before:** `scraper_runs.notes` 在失敗時為 `None` 或空字串，無法從 DB 判斷失敗原因。

**After:** `notes` 欄位現在包含例如 `"PlaywrightTimeoutError: Timeout 30000ms exceeded."` 或 `"AttributeError: 'NoneType' object has no attribute 'get_text'"`，直接從 DB 就能診斷，不需再翻 CI log。

**Lesson:** 調查失敗 scraper 時，先查 `scraper_runs.notes`：
```python
sb.table('scraper_runs').select('ran_at,notes').eq('source','<key>').eq('success', False).order('ran_at',desc=True).limit(5).execute()
```

---

## 2026-05-04 — gguide_tv schedule 解析缺 separator、hakusuisha 相對路徑 URL（commits `a895e07`、`1b344f7`）

### gguide_tv schedule 文字解析缺 `separator="\n"`（commit `a895e07`）
- **問題**：`gguide_tv.py` 用 `.get_text(strip=True)` 提取排程文字，各節點文字直接拼接無分隔，時間資訊擠在一起（例：`09:00映画『…』台湾10:00映画『…』`）
- **根本原因**：BeautifulSoup `get_text()` 預設無分隔符；多行資訊應用 `separator="\n"` 換行分隔
- **修復**：改為 `get_text(separator="\n", strip=True)`
- **教訓**：任何需要保留行結構的 BeautifulSoup 文字提取，**必須**使用 `separator="\n"`；預設行為會讓連續 inline 元素的文字擠在一起，造成下游解析失敗

### hakusuisha 相對路徑 URL 未轉換為絕對路徑（commit `1b344f7`）
- **問題**：`hakusuisha.py` 詳情連結 `href="../news/n*.html"` 直接存入 `source_url`；DB 中 10 筆事件的 `source_url` 為相對路徑，點擊連結 404
- **根本原因**：`a["href"]` 對相對路徑 href 直接賦值，未處理相對 URL 轉換
- **修復**：改用 `from urllib.parse import urljoin`；`source_url = urljoin(page.url, detail_url)`；DB 中 10 筆事件直接 patch
- **教訓**：**所有 `a["href"]` 值在存入 `source_url` 前必須通過 `urljoin(base_url, href)` 轉換**，不論 href 看起來是否已是絕對路徑

---

## 2026-05-03 — 本屋B&B / 白水社 scraper プロモーション（commit `1c4f4f8`）

### 問題
`auto_scraper/runs/169`（白水社）、`170`（本屋B&B）の `generated.py` を `sources/` にプロモーション。
`meta.json` に `source_name` / `class_name` が含まれていなかったため、クラス名が不明だった。

### 根因
auto_scraper の runs ディレクトリに保存される `meta.json` は `source_name` を含まない場合がある。

### 修復
`auto_scraper/runs/{id}/generated.py` の先頭数行（`class XxxScraper(BaseScraper):`）を直接確認してクラス名を取得。
DB: id=169/170 → `status=implemented`, `auto_scraper_status=deployed-manually`

### 教訓
**`meta.json` に `source_name` / `class_name` がない場合は `generated.py` 先頭を直接確認する**。
`class (\w+Scraper)\(BaseScraper\):` パターンで 1 行目付近に必ず存在する。

---

## 2026-05-03 — ks_cinema sub-event parent_event_id UUID 型別錯誤（commit `263e333`）
- **問題**：`ks_cinema.py` sub-event 中，`parent_event_id` 被設為 source_id 字串（`"ks_cinema_taiwan-filmake"`）而非 UUID，每次 upsert 出現 `invalid input syntax for type uuid` 錯誤，CI 連續 5 天失敗（`scraper_runs.success = false`）
- **根本原因**：直接將 source_id 字串賦值給 `parent_event_id` 欄位，未透過 `get_event_id_by_source()` 查詢 DB UUID
- **修正**：改用 `get_event_id_by_source(SOURCE_NAME, f"ks_cinema_{url_slug}")` 查詢 parent UUID，與 `taiwanshi.py` 模式相同；初次執行（parent 尚未寫入 DB）回傳 `None`
- **教訓**：`parent_event_id` 是 UUID 欄位，**絕不可**直接放 source_id 字串；必須透過 `get_event_id_by_source()` 查詢，回傳 `None` 時 sub-event 不設 parent

---

## 2026-05-02 — annotator.py 擴展 google_news_rss 薄內容 fetch 觸發（事件 2d77c2c4）
- **錯誤**：2d77c2c4（チップ・オデッセイ 熊本上映）raw_description 只有 80 chars 標題，但 start_date 非 null，Playwright fetch 被跳過，GPT 無法取得正確日期與地點
- **根本原因**：fetch 觸發條件只看 `not start_date`，不考慮 raw_description 是否足夠長
- **修正**：新增 `_gnews_needs_article_fetch()` helper — `not start_date` OR `len(raw_desc) < 400 chars`；`gnews_needs_fetch` 計數與 per-event trigger 都改用此函數
- **教訓**：薄內容偵測（koryu 模式）應同時套用到 annotator 的 fetch trigger — 「start_date 有值」不代表「描述足夠豐富」

---

## 2026-05-02 — fetch_ref_text() 提升至 BaseScraper 通用工具函數
- **背景**：koryu 後援指引文修正（32d66fc7）使用了 `_fetch_ref_text()`，但該函數只存在 koryu.py 中
- **重構**：將 `fetch_ref_text(ref_url, max_chars=3000)` 移至 `base.py`；koryu.py 改從 base import（移除 `requests`、`BeautifulSoup` import 及 `_REF_MAX_CHARS`、`_REF_HEADERS` 常數）
- **意義**：任何 scraper 遇到薄內容指引文時可直接呼叫，不需複製貼上實作
- **教訓**：通用爬蟲工具函數應放在 base.py，不應在各 scraper 中重複

---

## 2026-05-02 — koryu 後援指引文缺乏 ref URL 抓取（事件 32d66fc7）
- **錯誤**：後援公告「指引文」只有短短幾行 + 外部 URL。start_date=2025-12-15（文章刊登日），category 缺少 competition，location_name 誤填後援機構名
- **根本原因**：`_extract_event_date()` fallback 匹配到 DNN CMS 在 body 頂部渲染的文章發布日；scraper 未跟進外部 URL 抓取實際活動資訊；`開催日時:` 標籤誤導 GPT
- **修正**：koryu.py 新增薄內容偵測（< 600 chars + 外部 URL）→ 自動抓取 ref URL → 追加到 raw_description；pointer 文章改用 `記事投稿日:` 標籤
- **教訓**：若 body_text 薄且含外部 URL，scraper 必須主動抓取；`開催日時:` 標籤應只在確認為活動日期時使用

---

## 2026-05-02 — google_news_rss 年份推斷錯誤（事件 2d77c2c4）
- **錯誤**：標題「4月に熊本で上映」，GPT 推斷年份 2024，正確應為 2026
- **根本原因**：`raw_desc` 中無任何年份錨點；`_extract_start_date` 無法提取日期（只有「4月」無日期），GPT 無上下文依據
- **修正**：`google_news_rss.py` → `raw_desc` 嵌入 `（記事配信日: YYYY年MM月DD日）`
- **教訓**：任何無法從文章提取完整日期的 google_news_rss 事件都必須在 raw_desc 中包含 pub_date 作為年份錨點

## 2026-05-02 — ide_jetro date_prefix 省略 end_date → SINGLE-DAY RULE 誤觸（事件 86efda2a）
- **錯誤**：配信期間 2025-11-25〜2026-03-13，end_date 被設為 2025-11-25（等同 start_date）
- **根本原因**：`date_prefix` 只寫入 start_date；GPT 只看到一個日期 → 套用 SINGLE-DAY RULE；annotator fallback `or event.get("end_date")` 對**非 null 的錯誤值**無效
- **修正**：`ide_jetro.py` → 當 end_date ≠ start_date 時，date_prefix 改為 `開催日時: A日〜B日`
- **教訓**：date_prefix convention 必須包含 end_date。任何 scraper 知道 end_date 時，raw_description 的 `開催日時:` 行必須同時寫出 `開催日時: A日〜B日`

## 2026-05-02 — prtimes「6日間」duration 被 GPT SINGLE-DAY RULE 忽略（事件 e45d4022）
- **錯誤**：「盛りだくさんの6日間」活動 start_date=2026-02-25，end_date 應為 2026-03-02，但被設為 2026-02-25
- **根本原因**：prtimes.py 硬寫 `end_date=start_date`；SYSTEM_PROMPT 無「N日間」duration 規則，GPT 套用 SINGLE-DAY RULE
- **修正**：`annotator.py` SYSTEM_PROMPT 新增 Rule 10：「N日間」→ end_date = start_date + (N-1)天
- **教訓**：GPT 需要明確的 duration keyword 規則；scraper 本身應嘗試解析 end_date 而不是硬寫等於 start_date

---

## 2026-05-02 — koryu: 後援公告の `start_date` が文章刊登日に誤設定（Event `5104a6fe`）

- **問題**：Event `5104a6fe-ab70-4ec6-bf58-87232fb252a7`（source: `koryu`）の `start_date` が `2025-10-14`（文章刊登日）になっており、正しくは `2025-11-06` であるべき。
- **根本原因**：`koryu.or.jp` の「後援（こうえん）」公告ページには `日時:` ラベルがない。`_extract_event_date()` の Level 1 が失敗し、Level 2 fallback `re.search(r'(20\d{2}年\d{1,2}月\d{1,2}日)', body_text)` が DNN CMS のページ先頭に描画された**文章刊登日**（`2025年10月14日`）にマッチした。真の活動日 `11月6日（木）` は年号なし (`MM月DD日（曜日）`) で書かれていたため `\d{4}年...` の正規表現に引っかからなかった。さらにこの誤った日付が `開催日時: 2025年10月14日` として `raw_description` の先頭に前置され、GPT がその日付を優先してしまった。
- **修正**：`_scrape_detail()` の Level 1 失敗後・pub_date fallback 前に中間層を追加。`r'(\d{1,2})月(\d{1,2})日[（(][月火水木金土日祝][）)]\s*に開催'` で prose パターンを検索し、年号は pub_date から推定。
- **教訓①**：後援公告（title が `（後援）` 始まり）には `日時:` ラベルがない。正しい日付は body 内の `MM月DD日（曜日）に開催` prose パターンにある。
- **教訓②**：`開催日時:` を `raw_description` の先頭に前置するのは annotator への強烈なシグナル。Scraper が誤日付を前置すると GPT は body 中の正確な日付を無視する。
- **教訓③**：日付 fallback 優先順序：`日時：` ラベル → `時間：` ラベル → DOW-qualified `MM月DD日（曜日）` → **`に開催` prose** → generic `YYYY年MM月DD日`（最後手段）。

---

## 2026-05-02 — CI に `--enrich-person-names` ステップを追加（commit `85fd475`）

- **変更内容**：`.github/workflows/scraper.yml` に `python annotator.py --enrich-person-names` ステップを追加（`--enrich-movie-titles` の直後）。
- **背景**：`person_name_lookup.py`（eiga.com + zh.wikipedia）と `annotator.py` の `enrich_person_names()` は実装済みだったが、CI から呼ばれていなかった。全 `category=movie` イベントの出演者・スタッフ名中英訳が毎日 CI で自動補完されるようになった。
- **CI フロー（更新後）**：`--fix-reviewed` → `--enrich-movie-titles` → `--enrich-person-names` → `summarize_run.py`
- **教訓**：新しい enrichment 関数を実装したら、CI（`scraper.yml`）への追加を忘れずに確認する。実装済みでも CI に追加しなければ本番で動かない。

---

## 2026-05-02 — eurospace.py に `lookup_movie_titles` を追加、SKILL.md 更新

- **変更内容**：`eurospace.py` に `from movie_title_lookup import lookup_movie_titles` を追加し、`_scrape_detail()` 内で `name_zh, name_en = lookup_movie_titles(title)` を呼び出し `Event()` に渡すよう修正。
- **背景**：`lookup_movie_titles` は eiga.com 経由で日本語映画タイトルの中/英訳を取得するモジュール。eurospace は唯一の未適用スクレイパーだった。
- **SKILL.md 更新（2点）**：
  1. `scraper-expert/SKILL.md`（canonical: `.github/skills/agents/scraper-expert/SKILL.md`）: `movie_title_lookup` セクションに導入状況テーブルを追加、`name_ja_locked` セクションを old path から canonical に移植。
  2. `sources/cinemart_shinjuku/SKILL.md`：Phase 2 週次スケジュール（`_parse_schedule_page`、`_normalize_title`）と `lookup_movie_titles` 統合説明を追加。
- **教訓**：cinema scraper 追加時は **必ず `lookup_movie_titles` を追加**。採用状況テーブルをメンテナンスする（`## movie_title_lookup` セクション）。

---

## 2026-05-02 — record_links JSONB bug（`json.dumps()` 雙重編碼）、name_ja_locked 機制設計

### record_links JSONB bug
- **問題**：`database.py` `_event_to_row()` 對 `record_links` 欄位呼叫 `json.dumps()`，Supabase JSONB 欄位收到字串而非陣列；前端 `.map()` crash → HTTP 500。
- **修復**：移除 `json.dumps()`，直接傳 Python `list`。
- **教訓**：Supabase Python SDK 的 JSONB 欄位（`jsonb`、`jsonb[]`）**必須傳 Python `list`/`dict`，不可用 `json.dumps()` 先序列化**。SDK 自動序列化 native types；手動序列化造成雙重編碼。

### name_ja_locked 機制設計
- **問題**：annotator GPT 覆寫了 `taiwanshi.py` 從 `題目:` 欄位精準抓取的學術論文標題，截斷副標題並加「に関する講演会」後綴。
- **修復**：設計並實作 `name_ja_locked` boolean flag（migration 034 / Event dataclass / database.py / annotator.py）。
- **`annotator.py` 行為**：`name_ja_locked=True` 時直接使用 DB 現有 `name_ja`（`name_ja = event.get("name_ja")`），翻譯/分類/其他欄位照常生成。
- **適用場景**：`题目:` 欄位、官方片名 PDF、其他精確結構化來源 → `name_ja_locked=True`。
- **禁用場景**：標題只有通用詞（如「イベント」）、或是自由文字推斷的場景 → 讓 annotator 改善。
- **DB fix 指令**（已誤標注時）：
  ```python
  events = sb.table('events').select('id,name_ja,raw_title').like('source_id','<source>_%_sub%').eq('is_active', True).execute().data
  for e in [x for x in events if x['name_ja'] != x['raw_title']]:
      sb.table('events').update({'name_ja': e['raw_title']}).eq('id', e['id']).execute()
  ```

---

## 2026-05-02 — google_news_rss: `_extract_original_url()` 全回 None，因 RSS description href 也是 Google News URL

**問題：** `_extract_original_url(description_html)` 對所有事件返回 `None`，導致 `source_url` 停留在 Google News URL、`raw_description` 無法取得原始文章內容。

**根本原因：** 假設 RSS `<description>` 的 `<a href>` 指向真實文章 URL；實際上該 href 也是 `news.google.com/rss/articles/CBMi...?oc=5` 格式（另一層 Google News URL），無法用「非 google.com」過濾找到原始文章。base64 解碼 path 也不可行（是加密 protobuf，非單純 base64）；requests 直接 GET 亦無效（JavaScript redirect，requests 停在 400）。

**修復：** 移除 `_extract_original_url()`，改用 `googlenewsdecoder` PyPI 套件（`new_decoderv1`）對 RSS `<link>` URL 直接解碼。新增 `_decode_gnews_url(gnews_url)` 函數（帶 `interval=0`，自行控制 `_DECODE_SLEEP = 1.0` 間隔）。`requirements.txt` 新增 `googlenewsdecoder>=0.1.6`。

**教訓：** Google News RSS URL 唯一可靠解碼方案是 `googlenewsdecoder.new_decoderv1`。base64 解碼與 requests 繞過均無效。`raw_description` 應包含 500–4000 字元原始文章內容，供 annotator 標注 location/date。

---

## 2026-05-02 — taiwanshi: 「第N報告」子活動未解析；database.py 缺 `get_event_id_by_source` helper

**問題：** taiwanshi 台湾史研究会定例研究会的「第N報告」（sub-events）未存入 DB；設定 `parent_event_id` 時缺少按 `source_name + source_id` 查詢父事件 UUID 的方法。

**根本原因：** 原 scraper 只抓頂層活動，未解析 sub-events 結構（時間、題目、報告者、評論者）；`database.py` 無對應的 UUID lookup helper。

**修復：** `sources/taiwanshi.py` 新增 `_parse_reports()` 函數解析「第N報告」結構；`database.py` 新增 `get_event_id_by_source(source_name, source_id) -> str | None` helper，供 scraper 查詢父事件 UUID 後再設定 `parent_event_id`。

**教訓：** 建立 sub-events 時，必須透過 `get_event_id_by_source(source_name, source_id)` 查詢父事件 UUID 再設定 `parent_event_id`，不可在 scraper 內假設 UUID 或依賴執行順序。

---

## 2026-05-02 — merger Pass 1/3 相同 SOURCE_PRIORITY 時遍歷順序決定 primary（資料空洞）

**問題：** 兩個相同 `SOURCE_PRIORITY` 的來源配對時，merger 用「先遇到的」當 primary，可能選到 `start_date`、`location_address` 等欄位皆為 NULL 的事件。

**根本原因：** Pass 1 的 priority 比較使用 `<=`（而非嚴格 `<`），導致 priority 相同時無差別選第一個；沒有豐富度評估機制。

**修復：** 新增 `_richness_score()` helper（0–10 分）：`official_url`(+1) + `start_date`(+1) + `end_date`(+1) + `location_address`(+1) + `location_name`(+1) + `raw_description` 每 200 字 +1（上限 5）。Pass 1/3 的 priority 比較改為嚴格 `<` / `>`；priority 相同時比 richness score，高分者為 primary。`location_address` 同步加入 SELECT 查詢欄位。

**同步新建：** `docs/MERGER_WORKFLOW.md`——完整記錄四個 Pass 規則、SOURCE_PRIORITY 表、`_richness_score` 評分、Primary 選擇決策流程、幂等性保證、手動指令、CI 排程、FAQ。

**教訓：** SOURCE_PRIORITY 相同的兩個來源配對時，**一定要用豐富度判斷 primary**，不能依賴遍歷順序。新增來源若屬官方主辦方，應加入 SOURCE_PRIORITY 並設定低數值（高優先）。

---

## 2026-05-02 — google_news_rss 同活動多文章造成重複，merger Pass 1 跳過同來源

**問題：** DB 中出現多筆完全相同的 `google_news_rss` 活動（如「台湾屋台祭in海老名2026」3筆重複）。

**根本原因：** Google News RSS 對同一活動可能透過不同 query 或不同天產生多篇文章。每篇文章的 `source_id` 是 URL 的 MD5 hash，互不相同，in-scraper `dedup_events` 用 `raw_title`（帶 `- Source Name` 後綴）比對也無法命中。`merger.py` Pass 1 明確跳過同 `source_name` 的配對，故重複全部入庫。

**修復：**
1. `merger.py` — 新增 Pass 0（在 Pass 1 之前執行）：查詢所有 active `google_news_rss` 事件（含 `start_date=NULL`），對 `name_ja` 做相似度比對（≥ 0.85），超過門檻則合併；Primary 選擇規則：non-null `start_date` 優先，相同則選 `raw_description` 較長者；print 改為 `Pass 0+1+2+3`。
2. `sources/google_news_rss.py` — 新增 `_clean_title_for_dedup()`：strip RSS 標題後綴 `- Source Name` / `｜Source Name`；`Event.name_ja` 改用清洗後標題，`raw_title` 保留原始完整標題。
3. 手動合併 3 筆「台湾屋台祭in海老名2026」重複（Primary: f9709bb1，Secondary: e823ac41, ff4d9b6d deactivated；Primary `start_date` reset to NULL 等待 annotator 重新標注）。

**教訓：** debug `google_news_rss` 重複事件時，**先確認 merger.py Pass 0 log** 是否偵測到同名事件。annotator 可能用文章發布日（pubDate）填入 `start_date`——合併後若 `start_date` 疑似是文章發布日，應 reset to NULL 並重跑 annotator。

---

## 2026-05-02 — Promotion 後 `scraper_source_name` 缺失，後台來源關聯斷裂

**問題：** auto_generate 完成、PR merge 後，`/admin/sources` 顯示 0 筆活動且無法觸發 Run Scraper。

**根本原因：** `research_sources.scraper_source_name` 為 NULL。後台 API 靠此欄位 JOIN `scraper_runs`；auto_generate pipeline 只產生 scraper 檔案，不自動填此欄位。

**修復：** Supabase UPDATE — id=151 → `taiwan_festa`、id=150 → `tiff_jp`。

**教訓：** Promotion 最後一步必須手動填寫 `scraper_source_name`。已加入 SKILL.md § BaseScraper Contract 的 Promotion checklist。

---

## 2026-05-02 — taiwan_festa: auto_generate 失敗（Playwright 403），改用 requests + BeautifulSoup

**問題：** auto_generate 對 `taiwanfesta.com`（WordPress/UIkit 主題）失敗——Playwright headless 返回 403，`card_selector .uk-card-default` 在渲染後 DOM 中找不到。

**根本原因：** 部分 WordPress/UIkit 網站對 headless browser 返回 403；靜態 HTML 可直接取得，不需要 JS 渲染。

**修復：** 改用 `requests + BeautifulSoup` 手動撰寫 scraper（`scraper/sources/taiwan_festa.py`）。

**教訓：** auto_generate sandbox 顯示 0 events 時，立即嘗試 `requests.get()` 靜態抓取驗證。若靜態 HTML 完整，直接手寫 scraper，不必等 Playwright 重試。此類網站 `requests.Session` 須掛載 Retry adapter（參見 SKILL.md §requests.Session retry）。

---

## 2026-05-02 — TIFF: auto_generate 成功，promotion 後需修正年度 URL 與 Taiwan 過濾

**問題 1（年度 URL）：** auto_generate 產生 `BASE_URL = "https://2026.tiff-jp.net"`，每年需手動更新。

**修復 1：** 加入動態年份解析——follow `www.tiff-jp.net` redirect 取得 Location header，提取年份；fallback `datetime.now().year`。

**問題 2（Taiwan 過濾缺失）：** keyword 搜尋結果可能混入非台灣電影。

**修復 2：** 加入 `_TAIWAN_KW` client-side regex 過濾。

**教訓：** 對「每年換子網域」型網站（如 `YYYY.tiff-jp.net`），promotion 時必須將寫死年份改為動態解析。Architect/Scraper Expert 在 planning 時應標記此型 URL 為「需年度更新 review」。

---

## 2026-05-02 — auto_generate eligibility check 未接受 `recommended` 狀態

**問題：** `generate.py` 的 `_check_eligibility()` 只接受 `status == 'researched'`，但 recommended 來源為 `status = 'recommended'`，執行 `--source-id` 時直接 abort。

**修復：** `scraper/auto_scraper/generate.py` 改為接受 `('researched', 'recommended')` 兩種狀態。

**教訓：** `recommended` 是可信度最高的狀態，本應是 auto_generate 的優先對象。eligibility check 從設計時就應涵蓋此狀態。

---

## 2026-05-02（深夜 2）— tokyoartbeat venue 資料擴充、annotator scraper 優先序統一、location_url、PR Times 日期幻覺、IDE JETRO 線上活動（commits `c747484`、`eaab464`、`fb568c4`）

### tokyoartbeat venue 資料擴充（commit `c747484`）
- **問題**：`raw_description` 沒有場地資訊 → GPT 從訓練資料猜知名場館（東京都現代美術館等）→ 幻覺。
- **修復**：`_parse_event()` 從 Contentful venue linked entry 新增讀取 `openingHoursOpens`、`openingHoursCloses`、`closedDays`、`admissionFee`；組合成 `biz_hours`；`raw_description` 前綴加入結構化 header（`開催日時:`、`会場:`、`住所:`、`開場時間:`、`入場料:`）；`is_paid` 改由 `admissionFee` 數值推斷（`"0"` → False；非零數字 → True；非數字 → None）。
- **教訓**：GPT 場地幻覺的根本原因是 raw_description 沒有場地資訊。預防方法：在 raw_description prepend structured header，讓 GPT 有明確文字可抽取，而非依賴訓練資料。

### annotator scraper 優先序統一（commits `c747484` + `eaab464`）
- **問題**：annotator 對 `location_name/address`、`business_hours`、`is_paid`、`start_date`/`end_date` 都是 GPT 優先，會蓋掉 scraper 取得的正確資料。
- **修復**：翻轉上述欄位為 scraper 值優先，GPT 只補空值。翻譯欄位（name_zh/en、description_*）仍由 GPT 生成。
- **教訓**：scraper 提供的結構化資料比 GPT 從自由文字推斷的更可靠。統一原則：factual fields → scraper 優先；translation fields → GPT 生成。

### annotator location_url 條件式寫入（commit `fb568c4`）
- **問題**：`location_url` 不在 annotator `update_data` 內 → GPT 提取結果永遠丟失；若直接加入且不 null guard → 蓋掉 Admin 手填值。
- **修復**：GPT prompt schema 新增 `location_url` 欄位（指示「僅從文字提取，禁止推測」）；`update_data` 條件式寫入，僅在非 null 時才寫入。
- **教訓**：兼具 GPT 提取 + Admin 手填的欄位，寫入時**必須**加 null guard（僅在有值時寫入），否則 GPT null 輸出會蓋掉人工設定值。`location_url` 是場地官方網站，不是 Google Maps；scraper 通常無此欄位。

### name_ja_locked language note（commit `eaab464`）
- **問題**：有人以為 `name_ja_locked` 標題必須是日文（field name 含「ja」）。
- **修復**：SKILL.md 加入 Language note。
- **教訓**：`name_ja` 是欄位識別符，不是語言限制。`name_ja_locked=True` 的標題可能是中文（`台灣...`）或英文（`Taiwan...`），來源語言由活動頁面決定。不應因 field name 含「ja」就強制改為日文。

### PR Times 日期幻覺（DB fix，無 commit）
- **活動**：`e45d4022`（台湾＆沖縄フードイベント）
- **問題**：`start_date=2026-02-25`（PR Times 發布日），實際活動 `3月11日→16日` 在 raw_description 正文中。
- **根本原因**：`prtimes.py` 用文章發布日作為 `start_date`；raw_description 無 `開催日時:` header，GPT 無法從散落的日期字串正確推斷。
- **修復**：直接 DB update（`start_date=2026-03-11`、`end_date=2026-03-16`），補充 raw_description header，設 `annotation_status='reviewed'`。
- **教訓**：PR Times scraper 應嘗試從正文 regex 提取活動日期（`\d月\d+日` pattern）而非使用發布日；或在 raw_description 標記「プレスリリース発信日: YYYY年MM月DD日」以讓 GPT 區分。高風險 source：`prtimes`、`google_news_rss`、`nhk_rss`。

### IDE JETRO 線上活動 location_name=null（DB fix，無 commit）
- **活動**：`86efda2a`（オンデマンド講座）
- **問題**：`location_name=null`；GPT annotation 未識別為線上活動，前端無場地顯示。
- **修復**：直接設 `location_name='オンライン（オンデマンド）'`（含 zh/en），設 `reviewed`。
- **教訓**：線上活動 scraper 應主動判斷活動形式並設 `location_name='オンライン'`（細分：オンデマンド / ライブ配信 / ウェビナー）。Annotator SYSTEM_PROMPT 需補規則：活動明確為線上時，`location_name` 應設相應詞彙，不應留 null。

---

## 2026-05-02（下午）— デニス・リン展 場地幻覺：tokyoartbeat raw_description 缺少場地資訊

- **活動**：`1e375d6c`（デニス・リン展, source=`tokyoartbeat`）
- **問題**：網站顯示場地名稱、地址、開放時間全部錯誤。GPT 猜測場地為「東京都現代美術館，東京都江東区冬木7-2-1，10:00〜18:00」；正確為「Yukikomizutani，東京都品川区東品川1-32-8 TERRADA ART COMPLEX II 1F，12:00〜18:00（月・日・祝 休廊）」。
- **根本原因**：`raw_description` 只含英文藝術家簡介，完全沒有場地資訊（venue name、address、hours）。GPT 從訓練知識猜測知名大型美術館，對高知名度場館（東京都現代美術館、森美術館）特別容易過度自信。
- **修復**：直接呼叫 Contentful API 取得正確場地資料（`GET /entries/{event_id}` → 取得 venue link id → `GET /entries/{venue_id}`），執行 DB update 覆蓋。
- **教訓**：tokyoartbeat scraper 的 `raw_description` **必須**在開頭附加結構化場地資訊 header，否則 annotator GPT 會用訓練知識猜測並產生錯誤場地。Contentful API 提供完整欄位：`fullName`、`address`、`openingHoursOpens/Closes`、`closedDays`、`admissionFee`。格式範例：
  ```
  開催日時: YYYY年MM月DD日 〜 YYYY年MM月DD日
  会場: {fullName}
  住所: {address}
  開場時間: {openingHoursOpens}〜{openingHoursCloses}
  休廊日: {closedDays}
  入場料: {admissionFee}円（0 = 無料）
  ```

---

## 2026-05-02 — 5 件修復：HTTPAdapter retry、子活動欄位、get_event_id_by_source、health_check Check 4/5、annotator 日期覆蓋

### 修復 1：taiwanbunkasai — HTTPAdapter retry 補強
- **問題**：網路暫時性失敗（transient errors）無法重試，造成 Sentry 報警。
- **修復**：加入 `HTTPAdapter(max_retries=Retry(total=3, backoff_factor=2, status_forcelist=[429,500,502,503,504]))`。
- **教訓**：所有 scraper 對外 HTTP 呼叫都應加 retry，尤其目標站台有限流（rate limit）的情況。

### 修復 2：taiwanshi — 子活動欄位錯誤
- **問題**：爬蟲沒有子活動解析邏輯，子活動資料被錯誤放在父活動欄位。
- **修復**：新增 `_parse_reports()` 函數與 4 個 regex；`scrape()` 建立父活動後查 UUID 再建子活動。
- **教訓**：當一個 source 頁面包含多個獨立 programme items，需在爬蟲層建立子活動（`parent_event_id`），不能全塞在父活動。

### 修復 3：database.py — 新增 `get_event_id_by_source()`
- **問題**：子活動需要查詢父活動的 UUID，但原本沒有 helper 函式。
- **修復**：新增 `get_event_id_by_source(source_name, source_id) -> str | None`。
- **教訓**：跨事件 UUID 查詢是子活動建立的必要基礎建設，應在開始撰寫含子活動邏輯的 scraper 前確認此 helper 存在。

### 修復 4：health_check.py — 新增 Check 4 & Check 5
- **Check 4**：偵測 gnews 活動有 `start_date` 但原始 description 未實際抓取文章（只有 fallback pub_date）。
- **Check 5**：偵測 tokyoartbeat 活動 DB 日期與 `source_url` 中的日期不符。
- **教訓**：日期異常很難用肉眼發現，需要系統性健康檢查（health_check.py）定期偵測。

### 修復 5：annotator 日期覆蓋問題（重要）
- **問題根因**：annotator 第 581-582 行：
  ```python
  "start_date": annotation.get("start_date") or event.get("start_date"),
  "end_date": annotation.get("end_date") or event.get("end_date"),
  ```
  手動修正 `start_date` 後，若同時把 `annotation_status` 設為 `'pending'`，annotator 重跑時 GPT 若能從 `raw_description` 找到任何日期字串（甚至是錯誤的），就會覆蓋掉手動修正的值。
- **案例**：デニス・リン展（id: `1e375d6c`）的 `raw_description` 沒有 `開催日時:` header，GPT 輸出了 `2026-01-15`（舊錯誤值），覆蓋掉了修正後的 `2026-04-10`。
- **正確修法（已驗證）**：
  1. 直接更新 `start_date`/`end_date`
  2. 同時在 `raw_description` 前面加入 `開催日時: YYYY年MM月DD日 〜 YYYY年MM月DD日\n\n` header
  3. 才能安全地設 `annotation_status='pending'` 讓 annotator 重跑
  - **或者（更安全）**：手動修正後，設 `annotation_status='annotated'`（不設 `'pending'`），讓 annotator 不再重跑。
- **教訓**：手動修正日期時，**絕對不要**單獨設 `annotation_status='pending'` 而不更新 `raw_description`。`raw_description` 的 `開催日時:` header 是防止 GPT 猜錯日期的關鍵保護機制。

---

## 2026-05-02 — CI 加入 `--enrich-person-names` 步驟（commit `85fd475`）

**問題：** `person_name_lookup.py`（eiga.com + zh.wikipedia）與 `annotator.py` 的 `enrich_person_names()` 已實作，但 CI 從未呼叫它，全 `category=movie` 活動的演職員姓名中英文補完功能形同虛設。

**修復：** `.github/workflows/scraper.yml` 在 `--enrich-movie-titles` 之後加入新步驟：
```yaml
- name: Enrich cast/crew names from eiga.com + Wikipedia
  run: python annotator.py --enrich-person-names
```

**CI 流程（更新後）：** `--fix-reviewed` → `--enrich-movie-titles` → `--enrich-person-names` → `summarize_run.py`

**教訓：** 新的 enrichment 函式實作完後，必須同步確認已加入 `scraper.yml`。已在 `scraper-expert/SKILL.md` 的 `## person_name_lookup` 區段記錄此規則。

---

## 2026-05-02 — go_taiwan.py / prtimes.py：台灣地點活動日本訪客例外（commit `012ec72`）

**問題：** `go_taiwan.py` 的 `_is_japan_event()` 和 `prtimes.py` 的台灣地點過濾把所有地點在台灣的活動都排除，導致日台交流旅遊活動（ファムトリップ、日台交流ツアー）漏掉。

**根本原因：** 過濾邏輯的目標是「只收日本活動」，但正確目標應是「收與日本受眾相關的活動」——地點在台灣但以日本訪客為目標的活動兩者判斷不同。

**修復：**
- `go_taiwan.py`：新增 `TAIWAN_FOR_JAPANESE_KW` 清單（`日本人向け`、`日本語対応`、`日本から参加`、`日本から`、`日本発`、`ファムトリップ`、`日台交流ツアー`）；`_is_japan_event()` 在 Stage 2 台灣地點判斷後加例外：含上述關鍵字則 return True。
- `prtimes.py`：`_TAIWAN_VENUE_RE.search(venue)` 過濾區塊加入同樣例外，`body_text` 或 `title` 含 `_JAPAN_VISITOR_KW` 則不 skip。
- `annotator.py`：Location Address Rule 第 6 條補充：台灣地點不強制轉換格式，保留原始台灣地址，適用 `tourism` category。

**教訓：** 台灣在地舉辦但以日本人為目標的活動（訪台旅遊、日台交流）是 Radar 核心價值之一。任何 source 若有台灣地點過濾，都應審視是否需要加日本訪客例外。

---

## 2026-05-02 — Auto-scraper Phase 2 batch e2e：6 候選 1 成功（17%）

**結果分布：**
- ✅ Artist Cafe Fukuoka（id 提供 `li.article-list` hint） → success（detail_url fallback 修復後 0→12 events）
- ❌ Zepp Tokyo（id=148）→ batch1 sandbox-failed、batch2 spec-invalid（fast-fail，selector validation 擋下）
- ❌ Fukuoka Now（id=140）→ 同上
- ❌ SSFF / Blue+ / TAP-NY → LLM 幻覺 selector + 1 站點 timeout

**根本原因：**
1. **LLM CSS selector 幻覺**（最大宗）：GPT-4o 編造看似合理但不存在的 class，如 `.event-card`、`.event-list-item`、`.c-event-list__item-title`。每次 30s Playwright + ~$0.04 浪費。
2. **Researcher 沒填 `--card-selector-hint`**：6 個只有 1 個有 hint。其餘等於把 LLM 丟進無 grounding 的猜謎題。
3. **OpenAI 月度額度耗盡**：batch 中段觸發 429 `insufficient_quota`，後續所有呼叫直接 0 美金 abort。

**修復鏈（Phase 2.1/2.2/2.3，commits `b6e1768`/`f9eff43`/`d23be68`）：**
- Phase 2.1：注入 `spec_schema.json` 進 SYSTEM_PROMPT；失敗路徑補 forensic artifacts（prompt/sample/meta）
- Phase 2.2：detail_url fallback（template 端遇到 `DETAIL_LINK_SELECTOR == ""` 抓 card 內首個 `<a href>`）；sandbox-failed 補 spec+generated+dry_run
- Phase 2.3：SYSTEM_PROMPT 加 grounding 硬規則（只准用 sample HTML 中 verbatim 出現的 class/ID，列出常見幻覺）；BeautifulSoup pre-sandbox `_validate_selectors_against_html()`（~50ms 快速失敗，省下 30s Playwright）；違規結果回灌 LLM retry 訊息

**Phase 2.4 TODO（Tester 發現）：** 失敗路徑 `meta.cost_usd` 與 `meta.retries` 都被低估為 0，需把 cost 累計移到 `finally` 區塊。

**教訓：** Researcher 的 `--card-selector-hint` 在 production 是「實質必要」而非 optional——已寫入 `researcher.agent.md`。

---

## 2026-05-02 — google_news_rss: 修正 start_date fallback to pubDate 規則（commit `9510a05`）
**修改：** scraper-expert/SKILL.md `## google_news_rss-specific` 第 2 條
**內容：**
- 舊規則「 fallback to pubDate 」已賢正為「絕對不可 fallback pubDate，返回 None」
- RSS description 總是文章摘要（不含活動日期）；pubDate = 文章發布日，跟活動日期無關
- 40 筆日期錯誤事件已下架
**來源：** daily-skills-review（Step 4 建議）

---

## 2026-05-01 — 批次依 end_date 誤關 342 筆事件（is_active 語意誤用）

**問題：** 在 terminal 執行臨時批次腳本，將所有 `end_date < today AND is_active = True` 的事件設為 `is_active = False`。首頁大量歷史事件瞬間消失，用戶立即察覺，需緊急復原。

**根本原因：** `is_active` 表示「管理員是否主動隱藏」，與活動是否過期無關。過期事件應保持 `is_active = True`，由前端 `FilterBar` 的「顯示已結束活動」選項控制能見度。

**修正：** 反向 patch — 將所有 `end_date < today AND is_active = False` 的事件復原為 `is_active = True`，共復原 342 筆。

**教訓：** `is_active` 的合法寫入來源只有兩個：① 管理員在 admin 頁面手動關閉；② `merger.py` 合併重複事件。任何其他批次 UPDATE 都是錯誤。→ [Added to SKILL.md: DB Operations Safety Rules]

---

## 2026-05-01 — 映画 COMING SOON 期間的 start_date 錯誤（ナギ日記）

**問題：** 映画《ナギ日記》在 starsands.com 尚未公布正式上映日時，爬蟲在 4 月初抓到 `start_date = 2026-05-01`（應為 `2026-09-25`）。

**根本原因：** 電影類活動在正式公布上映日期前，官網可能只有「COMING SOON」或新聞稿，此時頁面上的任何日期都可能是「製作公告日」而非「上映日」。

**修正：** 直接 DB patch — `start_date → 2026-09-25`，`end_date = null`。

**教訓：** 電影類活動應優先從 `raw_description` 中查找「○月○日（曜日）公開」等明確上映格式；若找不到，設 `start_date = null` 而非使用頁面上模糊的日期。

---

## 2026-05-01 — gguide_tv business_hours fallback 到 detail page

**問題：** list page `schedule_raw` 為單行格式（只有開始時間，無結束時間），`end_time_str = None`，即使 detail page 已有完整播出時段，`business_hours` 仍為 `None`。

**修正：** 當 `end_time_str = None` 時，fallback 到 detail page 文字，用 `r"(\d{1,2}:\d{2})\s*\n[-−]\s*\n(\d{1,2}:\d{2})"` 提取結束時間。

**教訓：** list page 欄位不完整時，優先 fallback 到 detail page，而非直接設 `None`。此 pattern 適用於任何「list page 資訊精簡、detail page 資訊完整」的爬蟲。

---

## 2026-05-01 — gguide_tv schedule 文字提取須加 separator="\n"（commit `a895e07`）

**問題：** `ps[2].get_text(strip=True)` 把多行 HTML 子節點合併成 `"23:450:00 歌謡ポップス"`（無換行），導致 `_parse_schedule()` 無法識別多行格式，`business_hours = None`。

**修正：** 改為 `ps[2].get_text(separator="\n", strip=True)` — 加入 `separator` 後產生 `"23:45\n-\n0:00 歌謡ポップス"` 格式，多行解析正確。

**教訓：** BeautifulSoup `get_text()` 預設無 separator，多個子元素會直接串接。**當 HTML 結構中各欄位分別位於不同子元素時，必須加 `separator="\n"` 才能保留欄位邊界。**

---

## 2026-05-01 | gguide_tv channel name 改版（location_name 改為實際頻道名稱）

**問題：** `location_name="電視頻道"` 是虛設標籤，缺乏資訊量；23 件事件無法顯示正確頻道名稱。web 地址欄以 `event.location_name === "電視頻道"` 作判斷，`location_name` 語意一旦改變邏輯就失效。

**修正：** `gguide_tv.py` 改為 `location_name=channel`（如「歌謡ポップス」）。`web/app/[locale]/events/[id]/page.tsx` 地址欄判斷由 `event.location_name === "電視頻道"` 改為 `event.source_name === "gguide_tv"`。DB backfill 23 件事件。

**教訓：** UI 渲染的條件判斷應依賴 `source_name`（結構性欄位、永遠不變），而非 `location_name`（可變內容欄位）。依賴內容欄位做邏輯判斷，欄位修正後必須同步更新 UI 邏輯，容易出現 sync 問題。

---

## 2026-05-01 | i18n 標籤統一（event vs admin namespace 必須同步修改）

**問題：** `event.location`（場地・頻道）和 `event.address`（地點）標籤在前台詳情頁（`event` namespace）與後台管理頁（`admin` namespace）使用不同 JSON key，修改其中一個不會自動同步到另一個。

**修正：**
- `event.location`：zh「場地・頻道」/ en「Venue / Channel」/ ja「会場・チャンネル」
- `event.address` + `admin.address`：zh「地點」/ en「Location」/ ja「場所」

**教訓：** `event` namespace（前台）與 `admin` namespace（後台）是獨立的 JSON 命名空間。任何 UI 標籤修改必須同時更新三個 `messages/*.json` 的**兩個** namespace。

---

## 2026-05-01 | gguide_tv business_hours 修復（end_time fallback from detail page）

**根本原因：** list 頁的 `ps[2].get_text(strip=True)` 把 `<br>` 換行壓扁，多行格式 `23:45\n-\n0:00` 變成 `23:45-0:00`，導致 `\n-\n` regex 無法匹配，`end_time_str=None`，`business_hours` 無法計算。

**修復：** 當 `end_time_str=None` 時，fallback 從 `detail_text` 用 `r"(\d{1,2}:\d{2})\n-\n(\d{1,2}:\d{2})"` 補抓 end_time。DB backfill 從 `start_date`/`end_date` 反推 `business_hours`（格式 `21:00〜22:00`）。

**教訓：** BeautifulSoup `get_text(strip=True)` 會吃掉 `<br>` 結構，有跨行結構的欄位應改用 `get_text(separator="\n")` 保留換行。gguide_tv 的 `end_time` 在 detail 頁，不在 list 頁的 `schedule_raw`。

---

## 2026-05-01 | go_taiwan + transit_store スクレイパー実装

**go_taiwan (`scraper/sources/go_taiwan.py`):**
- サイト: 台湾観光庁 Japan 公式 (go-taiwan.net/ikutabi) — WordPress 静的 HTML、REST API 401 blocked
- **90-day pre-filter**: `<time datetime>` をリストページで先読みし 90 日超の記事をスキップ。フェッチ数 220 → 6
- **三段階フィルター**: Stage 2（`TAIWAN_VENUE_KW`）を Stage 3（`JAPAN_LOCATION_KW`）より**必ず先に**適用。逆順にすると台湾開催イベントが日本企業名テキストで誤通過する（野柳石光事例）
- **日付抽出優先順位**: `日時：` ラベル → 曜日注釈付き範囲 → ラベル付き単日 → 曜日注釈付き単日 → 平文範囲 → 本文最初の平文日付（公開日を拾うリスク大 — 最終手段）
- Issue #35 作成、DB status → recommended

**transit_store (`scraper/sources/transit_store.py`):**
- Shopify JSON API: `/collections/event/products.json?limit=20&page={n}`
- 台湾キーワードを `title` + `body_html` の両方でフィルタリング
- 日付: `body_html` 内の `日程[：:][^\d]*(\d{4})年(\d{1,2})月(\d{1,2})日` 正規表現
- Issue #34 作成、DB status → recommended

**DB 手動挿入ワークフロー:** `update_source.py --create-issue` は UPDATE 専用（INSERT しない）。`researcher.py` 経由でない手動発見ソースは先に `research_sources` に INSERT してから実行すること。`notes` カラムは存在せず、`reason` に記載する。

---

## 2026-05-01 | merger.yml 加排程 3× daily + annotator 步驟

**修改：** `.github/workflows/merger.yml` 新增 3 個 cron（`01:00 / 09:00 / 16:00 UTC`，對應 JST 10:00 / 18:00 / 01:00），每次 merger 跑完後接著執行 `python annotator.py` 和 `python annotator.py --fix-reviewed`。

**原因：** 原本 merger 只能手動觸發，合併後的事件要等到隔天 CI 才會被重新標註。

**教訓：** merger 結束後必須立刻重新標註，避免合併事件以 `pending` 狀態長時間滯留。一天三次 merger 確保跨來源重複在數小時內被處理。

---

## 2026-05-01 | merger.py Pass 3 — 孤兒 sub-event 清理

**修改：** `merger.py` 新增 Pass 3：掃描所有 `is_active=True` 但 `parent is_active=False` 的 sub-events（孤兒）。
邏輯：
1. 找出孤兒 sub（parent 已被 deactivate）
2. 查找 primary parent（via `secondary_source_urls` contains 查詢）
3. 若 primary parent 下有 name_ja 相似度 ≥85% + 相同 start_date 的 sub → 合併（按 SOURCE_PRIORITY）
4. 若找不到對應 sub → 直接 deactivate 孤兒

**原因：** Pass 1/2 合併後，舊 parent 被 deactivate，但其 sub-events 仍為 active，成為孤兒顯示在前台。

**教訓：** Pass 3 必須在 Pass 1/2 之後執行（確保 parent 合併結果已就緒）。Print 訊息格式：`Done: N pair(s)/orphan(s) merged (Pass 1+2+3).`

→ 已更新 `SKILL.md` § merger.py — Pass 3

---

## 2026-05-01 | Node.js 24 opt-in（scraper.yml + merger.yml）

**修改：** `scraper.yml` 和 `merger.yml` top-level 加入 `env: FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`。

**原因：** `actions/checkout@v4`、`actions/setup-python@v5` 在 Node.js 20 下出現 deprecation warning；GitHub 將於 2025-06-02 強制遷移。

**教訓：** 任何使用 `actions/checkout@v4` 或 `actions/setup-python@v5` 的 workflow 都需在 top-level `env:` 加入此 opt-in 環境變數，提前消除 warning。

→ 已更新 engineer SKILL.md § GitHub Actions Workflow Rules

---

## 2026-05-01 | merger.yml 新建 + scraper.yml 插入 merger 步驟

**修改：**
- 新建 `.github/workflows/merger.yml`：支援 `workflow_dispatch` 手動觸發，只跑 `python merger.py`
- `scraper.yml`：在 `main.py` 後、`annotator.py --fix-reviewed` 前插入 "Run merger" 步驟

**原因：** 每日 CI 跑完爬蟲後缺少自動去重步驟，跨來源重複事件要等手動執行或下次 CI 才被清理。

**教訓：** 每日爬蟲管道的步驟順序應為：`main.py` → `merger.py` → `annotator.py` → `annotator.py --fix-reviewed`。

---

## 2026-05-01 — annotator NAME WRITING RULES 新增

**Error:** Annotator produced self-referential titles like「東京オフ会」and「神戸オフ会」— users could not understand what the events were without reading the description.

**Fix:** Added NAME WRITING RULES to the `annotator.py` system prompt. Generic terms (`オフ会`, `ライブ`, `上映会`, `展示`, `イベント`, `セミナー`, `勉強会`) must not appear alone in a title; they must be prefixed with the organiser, topic, or series context. Two events were re-annotated: 「東京オフ会」→「台湾系YouTuber copochanの東京オフ会」and「神戸オフ会」→「台湾系YouTuber copochanの神戸オフ会」.

**Lesson:** Titles must be self-contained. A reader who sees only the title must understand the event without reading the description. → Added to `SKILL.md` § Annotator NAME WRITING RULES

---

## 2026-05-01 — google_news_rss Yahoo 集約過濾 & _STALE_DAYS 短縮

**Error:** (1) Yahoo!ニュース aggregation articles were included — they are duplicates of the source article and their redirect URLs expire faster. (2) `_STALE_DAYS = 60` was too long; Google News redirect URLs expire in ~2–3 weeks, so 60-day-old entries were always dead links. (3) Query `"台湾映画 上映"` returned pure news articles about release dates that are not event listings.

**Fix:** Added `_is_yahoo_aggregation()` to skip titles ending with `「- Yahoo!ニュース」`. Changed `_STALE_DAYS` from 60 → 21. Changed query from `"台湾映画 上映"` → `"台湾映画 上映会"` to target event listings specifically.

**Lesson:** Google News redirect URLs (`news.google.com/rss/articles/...`) CANNOT be resolved server-side — `requests` returns HTTP 400 and Playwright is blocked by bot detection. They work correctly in real browsers. Do not attempt server-side redirect resolution; do not exclude the entire scraper. Use `_STALE_DAYS = 21` for Google News RSS. → Added to `SKILL.md` § google_news_rss-specific

---

## 2026-05-01 — migrations/ 資料夾污染 (非 migration 檔案混入)

**Error:** A previous agent placed test/documentation files (`027_smoke_test.sql`, `027_VALIDATION.md`, `027_VERIFICATION_REPORT.md`) inside `supabase/migrations/` with sequence-number prefixes, polluting the migration history.

**Fix:** Deleted all three non-migration files from `supabase/migrations/`.

**Lesson:** `supabase/migrations/` must contain ONLY real SQL migration files (`.sql` format, sequential numbered). Test scripts, validation reports, and documentation files must NEVER be placed in this directory. → No SKILL.md update needed (see `database.instructions.md`).

---

## 2026-05-01 — sub-events missing scraped_at (クロール日時 = —)

**Error:** `annotator.py` builds `sub_row` without a `scraped_at` field. All 128 existing sub-events had `scraped_at = NULL`, causing the admin table `クロール日時` column to display `—` for every sub-event.

**Fix:**
1. Added `"scraped_at": event.get("scraped_at")` to `sub_row` in `annotator.py` — sub-events now inherit the parent's scrape timestamp at creation time.
2. Backfilled all 128 existing sub-events: 34 inherited parent's `scraped_at`; 94 used parent's `created_at` as fallback (parent also predated migration 018b).

**Lesson:** When `annotator.py` builds a sub-event row, it must explicitly carry over any field from the parent that is meaningful for operations/admin — `scraped_at` is a key example. Fields omitted from `sub_row` default to `NULL` and are not inherited automatically.

→ Added to `SKILL.md` § Annotator sub-event row fields

---

## 2026-05-01 — taiwan_cultural_center: 多城市巡迴活動誤錨定東京 HQ 地址（commit `a2d6eea`）

**問題：** 台湾文化センター發佈的部分活動會跨多個日本城市巡迴（如「台湾映画上映会2026」走 5 個城市）。scraper 對此 source 寫死 HQ 地址（東京港區），導致多城市巡迴活動全被打成「東京」，前台地區篩選 / 多城市顯示完全錯誤。

**修正（`scraper/sources/taiwan_cultural_center.py`）：**
- 新增 regional keyword 偵測：description 含 ≥ 2 個 `北海道|大阪|京都|神奈川|福岡|名古屋|仙台` 等地名 → 判定為多城市巡迴。
- 多城市時：`location_name = '台湾文化センター（全國巡迴）'`、`location_address = None`（清掉 HQ 地址，由 annotator/`location_prefectures` 流程聚合）。
- 單一地點時維持原本 HQ 預設行為。

**教訓：** Scraper 對單一機構錨定固定地址時（HQ pattern），必須加「多城市描述去錨定」守門。可推廣的 rule：任何 hardcoded address scraper（taiwan_cultural_center / koryu / 其他駐日機構）→ description 偵測 ≥ 2 個地區關鍵字時，清空 `location_address`、改寫 `location_name` 為「<機構>（全國巡迴）」，讓下游 annotator 透過子活動聚合 `location_prefectures`。

---

## 2026-05-01 — annotator: 多地點子活動規則 + `--id` CLI + `location_prefectures` 自動聚合

**背景：** 台東祭有東京/京都/大阪三城市各自地址，但 annotator prompt 無「多地點建子活動」規則，且無法對單一 event 強制重新標注。

**修正（`scraper/annotator.py`）：**
- Prompt rule 1 擴充：新增「3+ 個不同城市各自有地址的多地點活動，每個地點建立一個子活動」規則
- 新增 `--id <uuid>` CLI 選項：可對單一 event 強制重新標注（不限 `annotation_status`，但 `reviewed` 除外）
- 新增 `_extract_prefecture()` helper：從 `location_address` 提取都道府縣名，regex 涵蓋 北海道/東京都/大阪府・市/京都府・市/其他縣
- 子活動 loop 結束後自動計算 `location_prefectures`：≥ 2 個不同都道府縣時寫入父事件；單城市不寫入

**`location_prefectures` 欄位（Migration 012）：**
- DB 欄位：`location_prefectures text[]`（nullable）
- 由 `annotator.py` 在子活動建立後自動聚合並更新父事件
- backfill script（`scraper/backfill_location_prefectures.py`）可補填現有多城市母活動
- 前台/後台篩選加入 `location_prefectures.cs.{"X"}` OR 條件，讓多城市母活動也命中地區篩選

**教訓：**
- `_extract_prefecture()` regex 需同時覆蓋「府」省略格式：`大阪府`/`大阪市` 和 `京都府`/`京都市` 都必須納入，否則「大阪市中央区...」地址無法提取都道府縣
- `--id` 選項必須略過 `annotation_status` 檢查（除 reviewed 外），以支援重新標注已 annotated 的事件

---

## 2026-05-01 — gguide_tv: `_parse_schedule` 多行格式解析錯誤（business_hours 空白）

**問題：** bangumi.org 的 schedule_str 有兩種格式：
- 單行：`"12:00 テレ東"`
- 多行：`"23:45\n-\n0:00 歌謡ポップス"`

原本 regex 為單行設計，遇到多行格式時把 `-` 誤抓為 channel 名，且無法提取 end_time，導致 `business_hours` 欄位空白，詳細頁面無放送時間。

**修正（`scraper/sources/gguide_tv.py`）：**
- `_parse_schedule()` 回傳值從 `(datetime, channel)` 改為 `(datetime, channel, end_time_str)`
- 多行格式：開始時間從第一行 `HH:MM` 提取；結束時間與 channel 從第三行 `H:MM <channel>` 提取
- `Event()` 加入 `business_hours=business_hours`（格式：`"23:45〜0:00"`）
- DB backfill：15 個無 business_hours 的 gguide_tv 事件全數補齊

**測試結果：**
```
Test 1 (multi-line): 23:45 歌謡ポップス 0:00  ✅
Test 2 (single-line): 12:00 テレ東 None       ✅
Test 3 (midnight): 00:00 NHK-BS 0:55          ✅
```

**教訓：**
- bangumi.org schedule 格式必須區分單行（`HH:MM channel`）與多行（`HH:MM\n-\nH:MM channel`）；單行 regex 在多行格式下把 `-` 行誤判為 channel，且漏取 end_time
- 修完後立即執行 `python main.py --source gguide_tv`（非 dry-run）寫入 DB；再對舊資料做 backfill UPDATE

---

## 2026-05-01 — prtimes: 多城市活動漏建子活動（raw_description 固定截斷過早）

**問題：** `_fetch_detail()` 固定截斷 `text[:3000]`。PR 文章前半是商品介紹時，東京/大阪行程被截掉，Annotator 無法生成 sub_events。1 篇含東京（5/2）+ 大阪（5/9）兩場的 PR，只建出 1 個 Event。

**根本原因：** 固定長度截斷對「商品介紹先於活動行程」的 PR 文章失效。

**修正（commit `ecd2bb8`）：**
- 新增 `_MULTI_CITY_SECTION_RE`：偵測 `(東京|大阪|京都|...|日期)` 多城市行程模式
- 無多城市：`text[:3000]`（不變）
- 偵測到多城市：`text[:2000]` + `---[イベント開催情報]---` 分隔符 + 行程區塊 4,000 字（合計上限 8,000 字）

**驗證結果：**
- `_MULTI_CITY_SECTION_RE.search(body_text)` 成功偵測「東京｜2026年5月2日」
- raw_desc 4,312 字（vs 原本 3,000）
- Annotator 自動生成 2 個 sub_events：東京 5/2（TOKYO FAMILY RESTAURANT）、大阪 5/9（TOBI SHOP / KITTE 大阪）

**多城市子活動補建標準流程：**
1. 手動建子活動確認資料正確
2. 刪除手動建的子活動（不可保留）
3. 修正 scraper raw_description 邏輯
4. 重新抓取 + 更新 DB + 重置 `annotation_status = pending`
5. 執行 `annotator.py` → 自動生成正確 sub_events

**教訓：**
- 偵測式延長（用正則選擇性延長）比單純增大全域截斷上限更精準，不影響其他 PR 效能。
- 多城市活動的正確修正流程必須走完整五步驟；跳過「刪除手動建的子活動」會導致重複資料。

---

## 2026-05-01 — auto_qa anomaly detection writes into event_reports queue (commit `2ae731b`)

**Feature:** `scraper/auto_qa.py` scans `is_active` events from the past 14 days and inserts pending rows into `event_reports` for two anomaly types: `auto_qa_simplified_zh` (simplified chars in any `*_zh` field) and `auto_qa_missing_address` (has `location_name` but empty `location_address`; skips online/TV/zoom/youtube + `gguide_tv` source). Dedups against existing pending `auto_qa_*` rows per `event_id`. Inserts in chunks of 100. Runs 3×/day in `merger.yml` after `--fix-reviewed`. Production dry-run found 2 real findings (永旺夢乐城太田 simplified `乐`; 一石三鳥グループ missing address).

**Lesson 1 — `SIMP_RE` / `_LOC_ZH_SIMP_TO_TRAD` char addition rule:** Only add a char when its Trad/JP form is **a different glyph**. Counter-example: `亮` is identical in Trad and Simp (`照亮` is valid Traditional) — including it produced a false positive in production dry-run. Verify each candidate via CC-CEDICT or kanji.jitenon.jp before adding.

**Lesson 2 — auto-QA via shared `event_reports` queue:** New automated content-quality checks should write findings into `event_reports` with an `auto_*` prefix in `report_types[]` rather than building a separate admin queue. Admin checks one URL; the existing confirm/dismiss flow handles auto-detected and user-submitted findings the same way; `report_types text[]` supports multiple anomaly types per row.

---

## 2026-05-01 — 8 scrapers not registered in research_sources (silent CI gap)

**Error:** Architect review discovered 8 active scrapers were present in `main.py SCRAPERS` but had no corresponding row in `research_sources`. The gap was silent — no warning, no CI failure — so it accumulated undetected.

**Affected scrapers:** `prtimes`, `maruhiro`, `hankyu_umeda`, `daimaru_matsuzakaya`, `google_news_rss`, `nhk_rss`, `mot`, `transit_store`

**Root cause:** The "add new scraper" workflow had only 3 steps (create file → register in SCRAPERS → dry-run). Step 4 ("register in research_sources") did not exist in any checklist. The `research_sources` table is used by `researcher.py` to skip already-known sources, so unregistered scrapers caused the researcher to re-report them as new candidates.

**Fix:**
- Manually inserted all 8 missing rows into `research_sources` with `status='implemented'` and `scraper_source_name` set.
- Added `_warn_unregistered_scrapers()` to `main.py`: on every non-dry-run, it compares `SCRAPERS` keys against `research_sources.scraper_source_name`. Any gap emits a `⚠️ WARNING` in CI logs — immediately visible on next daily run.
- Added step 3 ("Register in research_sources") to the **New scraper checklist** in this SKILL.md.

**Lesson:** Whenever you add a scraper to `SCRAPERS`, you MUST also insert a row in `research_sources` with `status='implemented'` and `scraper_source_name=<key>`. Without this, `researcher.py` will keep re-discovering and re-reporting the same source. The CI warning added to `main.py` makes any future omission visible within 24 hours.

---

## 2026-04-30 — 天燈體驗 [prtimes] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food
**After (corrected):** workshop
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-30 — 海濱派對 [prtimes] — user report confirmed
**Report types:** irrelevant
**Admin notes:** —
**Action:** Event hidden (is_active=false). Irrelevant content.
---

---

## 2026-04-30 — 橫濱國際電影節 特拉維斯·佩恩舞蹈比賽 [prtimes] — user report confirmed
**Report types:** irrelevant
**Admin notes:** —
**Action:** Event hidden (is_active=false). Irrelevant content.
---

---

## 2026-04-30 — 親愛的陌生人／ディア・ストレンジャー（字幕版） [gguide_tv] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** movie
**After (corrected):** tv_program, movie
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-30 — 圍棋焦點 女子世界第一是？世界圍棋女子最強戰2026 [gguide_tv] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** competition
**After (corrected):** tv_program, competition
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-30 — 來自台灣的考察團參加國際研討會 [google_news_rss] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** academic, taiwan_japan, lecture
**After (corrected):** report, taiwan_japan, healthcare
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-30 — Beginning ZERO [prtimes] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** performing_arts, lifestyle_food
**After (corrected):** performing_arts
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-30 — 台灣博覽會 [maruhiro] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:台灣園遊會, fieldEdit:name:en:Taiwan Fair, fieldEdit:name:ja:台湾フェア
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---

## 2026-04-30 — 同步星座：藝術中的跨界視角 [tokyoartbeat] — user report confirmed
**Report types:** wrongDetails, wrongCategory, fieldEdit:name:zh:共時星座：藝術中的跨界視角, fieldEdit:name:en:Synchronic Constellation: Cross-boundary Perspectives in Art, fieldEdit:name:ja:シンクロニック・コンステレーション：アートにおける境界を越えた視点
**Before (AI category):** senses, art
**After (corrected):** movie, literature, art, senses, history, taiwan_japan
**Wrong fields:** name
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-30 — 台東祭 [prtimes] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan
**After (corrected):** nature, lifestyle_food, indigenous
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-30 — 精巡（しょうじん）料理～巡迴、調整。台灣藥膳健康講座～ [prtimes] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan, lecture
**After (corrected):** senses, lifestyle_food, lecture
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-30 — 私人租借 [moonromantic] — user report confirmed
**Report types:** irrelevant
**Admin notes:** —
**Action:** Event hidden (is_active=false). Irrelevant content.
---

---

## 2026-04-30 — 橫濱市中高生管樂團電影音樂節 [prtimes] — user report confirmed
**Report types:** irrelevant
**Admin notes:** —
**Action:** Event hidden (is_active=false). Irrelevant content.
---

---

## 2026-04-30 — 造山者－世紀的賭注 [google_news_rss] — user report confirmed
**Report types:** wrongDetails, fieldEdit:start_date:zh:2026-03-17T00:00:00+00:00, fieldEdit:start_date:en:2026-03-17T00:00:00+00:00, fieldEdit:start_date:ja:2026-03-17T00:00:00+00:00, fieldEdit:end_date:zh:2026-03-17T00:00:00+00:00, fieldEdit:end_date:en:2026-03-17T00:00:00+00:00, fieldEdit:end_date:ja:2026-03-17T00:00:00+00:00
**Wrong fields:** start_date, end_date
**⚠ Scraper fix needed:** Fields [start_date, end_date] can only be fixed in the scraper source, not by re-annotation.
**Admin notes:** —
**Action:** Event deactivated — re-annotation triggered (annotation_status=pending).
---

---

## 2026-04-30 — 《晴天時空豆撒20周年紀念》三浦透子×近藤康平 [eplus] — user report confirmed
**Report types:** irrelevant
**Admin notes:** —
**Action:** Event hidden (is_active=false). Irrelevant content.
---

---


---

## 2026-04-29 — Peatix 三層爬取架構固化（daily review）
**新增/修改：**
- `## Peatix-specific` 新增 Three-layer organizer architecture 表格（Layer 1 keyword / Layer 2 hardcode / Layer 3 DB-driven）
- 記錄 `_load_db_organizers()` 的 `agent_category='peatix_organizer'` 查詢條件
- 記錄「Never remove Layer 2」規則（DB status 意外變更時的 backup）
**來源：** daily-skills-review（Step 4 建議）

## 2026-04-29 — iwafu docstring 誤記（東京限定と表記されていた全国スクレイパー）[iwafu]
**Error**: `iwafu.py` モジュール docstring に「Filter to events where prefecture == 東京」と記載されていたが、実コードは `cards = all_cards`（フィルターなし）で全国カバー済み。
DB candidate id=97（iwafu EN `/en/events/`）も「福岡拡張が必要」と判断されていたが、JP スクレイパーで既に全国カバーされているため重複。
**Fix**: docstring を「No prefecture filter — all regions included」に修正。DB id=97 を not-viable に更新（理由付き）。
**Lesson**: 「機能を追加する前にコードを読む」。scraper の実際の挙動（cards フィルター有無）を確認してから「拡張が必要か」を判断する。docstring とコードが乖離するリスクを防ぐため、prefecture フィルターの有無は SKILL.md に明記しておく。

---

## 2026-04-29 — SCRAPERS リスト未登録スクレイパー 8 件発見（pipeline 監査）[main.py]
**Error**: CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper, ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper の 8 件が `sources/*.py` として存在するが `SCRAPERS` リストに未登録のまま本番稼働していた。DB ステータスは `implemented` だったが CI では一度も実行されていなかった。
**Discovery**: `research_sources` DB の `implemented` 件数 vs `sources/` ファイル一覧と `SCRAPERS` リストの三者クロスチェックで発見。
**Fix**: `scraper/main.py` に 8 件の import と `SCRAPERS` 追記。全件 dry-run で動作確認後にコミット。
**Lesson**: DB `implemented`、ファイル存在、`SCRAPERS` 登録の三者は独立して管理される。新規スクレイパー作成時は必ず同一コミットで `SCRAPERS` に追加する。定期監査コマンド:
```bash
python3 -c "
import re, glob
registered = set(re.findall(r'(\w+Scraper)\(\)', open('main.py').read()))
for f in glob.glob('sources/*.py'):
    c = open(f).read()
    m = re.search(r'class (\w+Scraper)\b', c)
    if m and m.group(1) not in registered and m.group(1) != 'BaseScraper':
        print('UNREGISTERED:', m.group(1), f)
"
```

---

## 2026-04-29 — 8 Unregistered Scrapers Found in SCRAPERS List Gap [main.py]
**Error**: CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper, ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper all had `.py` source files but were NOT included in the `SCRAPERS = [...]` list in `scraper/main.py`. This caused them to be skipped by the daily CI run despite being ready for production.

**Discovery**: Audit found via manual inspection and confirmed via `python main.py --dry-run`.

**Fix**: Added all 8 to `SCRAPERS` list and validated dry-run output:
- CineMarineScraper: 1 event (横浜シネマリン)
- EsliteSpectrumScraper: 2 events (誠品生活日本橋)
- MoonRomanticScraper: 1 event (Moon Romantic)
- MorcAsagayaScraper: 0 events (正常 — no Taiwan films today)
- ShinBungeizaScraper: 1 event (新文芸坐)
- SsffScraper: 6 events (SSFF)
- TaiwanFaasaiScraper: 1 event (台湾發祭)
- TokyoFilmexScraper: 0 events (正常 — festival in October)

**Lesson**: The sources directory and `SCRAPERS` list can drift silently. Implement monthly audit: `comm -23 <(find sources/ -name '*.py' ... ) <(grep 'Scraper()' main.py ...)`. After creating any new scraper file, registration in `SCRAPERS` must happen at commit time, not rely on CI discovery.

---

## 2026-04-29 — Google search fallback used wrong locale title [web]
**Error**: Detail page Google search URL used `name` (locale-specific) as query text. In `zh` locale, the query became `大濛 公式サイト` instead of `霧のごとく 公式サイト`, causing the Japanese official site to not appear in results.
**Fix**: Changed query to prefer `event.name_ja || event.raw_title || name` so the Japanese title is always used regardless of the viewing locale.
**Lesson**: When building Japanese-language search URLs, always use `name_ja` (or `raw_title`) as the source of the search term — never the locale-resolved display name.
---

## 2026-04-29 — Existing DB records not updated after adding official_url to cinema scrapers [cinemart_shinjuku, ks_cinema]
**Error**: After adding `official_url` extraction to `cinemart_shinjuku.py`, the existing DB event `cinemart_shinjuku_002491` (「大濛」) still had `official_url = null` because the upsert only runs on the next scraper cycle.
**Fix**: Ran a targeted Supabase UPDATE: `update({'official_url': 'https://www.afoggytale.com/'}).eq('source_id', 'cinemart_shinjuku_002491')`.
**Lesson**: When adding a new field extraction to an existing scraper, always manually update currently-active DB records or set `force_rescrape=True` for affected events. Dry-run only confirms the code works — it does NOT write to DB.
---

## 2026-04-29 — taiwan_cultural_center: month-only date range caused publish-date fallback

**Error:** `期間：2026 年5 月～10 月(全10 回)` was matched by `_BODY_DATE_LABELS` regex, but `_parse_date("2026 年5 月")` returned `None` (no day component). `start_date` fell back to publish date `2026-04-27`, `end_date = 2026-04-27` — would have been archived that evening.

**Fix:** (1) `_parse_date()`: added month-only `YYYY年M月` → day 1 of that month. (2) `_extract_event_dates_from_body()`: detect month-only `end_raw`, inject year from start, advance to last day of month via `calendar.monthrange`. (3) DB record manually corrected to `2026-05-16 / 2026-10-24`. Scraper will upsert `2026-05-01 / 2026-10-31` on next run (acceptable).

**Lesson:** `_parse_date()` must handle `YYYY年M月` (no day). Multi-month series often use month-only ranges in the structured `期間：` label. Always verify end_date won't trigger same-day archival.

---

## 2026-04-29 — eurospace / tokyoartbeat: category="string" instead of category=["string"]

**Error:** `malformed array literal: "movie"` (PostgreSQL code 22P02) on upsert.
The `category` column is `text[]` in Supabase. Both `eurospace.py` and `tokyoartbeat.py`
passed a bare string (`category="movie"`, `category="art"`), causing the DB to reject it.

**Fix:** Changed to list literals: `category=["movie"]`, `category=["art"]`.

**Lesson:** `Event.category` is typed `list[str]` (see `base.py` line 30). Any scraper that
hard-codes a single category must use `["value"]` not `"value"`. Bare strings silently compile
but fail at DB write time with a cryptic PostgreSQL array literal error.

---

## 2026-04-29 — maruhiro: datetime.date vs datetime.datetime type error + 15 scrapers lost from SCRAPERS

**Part 1 — Type error in dedup_events:**
`_parse_dates` in `maruhiro.py` returned `datetime.date` objects. `dedup_events` in `base.py`
calls `.date()` on `start_date`, expecting a `datetime.datetime`. Error:
`AttributeError: 'datetime.date' object has no attribute 'date'`.
Fix: changed `_parse_dates` to return `datetime.datetime(y, m, d)` instead of `date(y, m, d)`.

**Lesson:** All scrapers must return `datetime.datetime` for `start_date`/`end_date`, not bare `date`.
`dedup_events` contract requires `.date()` to be callable on the value.

**Part 2 — 15 scrapers deleted from SCRAPERS by 7aecfef:**
SCRAPERS audit (run after implementing maruhiro) revealed 15 scrapers present in `sources/` but
absent from `SCRAPERS` in `main.py`. Root cause: commit `7aecfef` ("chore: tighten workflow guards
and restore admin filters") rewrote `main.py` and omitted the imports and registrations for:
EurospaceScraper, TokyoArtBeatScraper, HankyuUmedaScraper, DaimaruMatsuzakayaScraper,
CineMarineScraper, EsliteSpectrumScraper, MoonRomanticScraper, MorcAsagayaScraper,
ShinBungeizaScraper, SsffScraper, TaiwanFaasaiScraper, TokyoFilmexScraper,
GoogleNewsRssScraper, NhkRssScraper, GguideTvScraper.
All 15 were restored, total SCRAPERS count: 56.

**Lesson:** SCRAPERS audit must run after ANY commit touching `main.py`, not only when
adding new scrapers. Run `python3 -c "import re, glob; ..."` (see SKILL.md) before `git push`.

---

## 2026-04-29 — prtimes: 川越台湾フェア and all non-Tokyo events missed (3 bugs)

**Trigger:** User reported https://prtimes.jp/main/html/rd/p/000000015.000127081.html (丸広百貨店川越店「台湾フェア」) not captured.

**Root cause 1 — Geographic restriction in `_SEARCH_KEYWORDS`:**
All 5 keywords contained `東京` (e.g. `"台湾 イベント 東京"`). The prtimes search API
only returns articles matching the full keyword string, so articles from Saitama (川越),
Osaka, Nagoya, etc. were **never returned**. Violates the project rule: "Never restrict
geographic scope".
Fix: Removed `東京` from all keywords → `["台湾 イベント", "台湾フェア", "台湾フェス", "台湾 開催", "台湾 夜市", "台湾 祭"]`.

**Root cause 2 — `_EVENT_KW` missing `フェア`:**
`_EVENT_KW` regex did not include `フェア`. A title like「台湾フェア」would have no
_EVENT_KW match and be rejected. Fix: added `フェア` to `_EVENT_KW`.

**Root cause 3 — `_TAIWAN_BASED_TITLE_RE` false positive:**
Pattern `台湾.*?で` matched `台湾フェア」で` (a Japan-held Taiwan fair) as if the event
were held IN Taiwan, causing it to be skipped. The intended purpose was to exclude
events held inside Taiwan (not Japan). Fix: tightened the regex to require explicit
Taiwan-location context only:
- `台湾国内|現地|本島|の地.*?で`
- `in 台湾 / in Taiwan`
- `台湾出展|輸出|進出|販路|海外展示|海外販売`

**Result:** dry-run: 20 → 30 events; 川越台湾フェア now first in list.

**Lesson:**
- `_SEARCH_KEYWORDS` must NEVER contain city/region names — geographic scope is all-Japan.
- `_TAIWAN_BASED_TITLE_RE` patterns must be precise; `台湾.*?で` is too broad and matches Japan-based Taiwan fairs.
- When a PR article is missing, check: (1) search keyword geography, (2) `_EVENT_KW`, (3) `_TAIWAN_BASED_TITLE_RE`, (4) venue filter `_TAIWAN_VENUE_RE`.

---

## 2026-04-29 — movie_title_lookup + PrtimesScraper registration + FukuokaNow scope fix [multiple]

**Changes (commit 3286522):**

1. **`movie_title_lookup.py`** (NEW): `lookup_movie_titles(name_ja)` → `(name_zh, name_en)` via eiga.com search. In-memory cache `_cache`; returns `(None, None)` silently on any error. Used by 8 cinema scrapers + annotator `--enrich-movie-titles` flag.

2. **`prtimes.py` geographic filter removed**: `_SEARCH_KEYWORDS` previously included `東京` scope restriction. Removed — project scope is all of Japan. Added `フェア` to `_EVENT_KW`. `PrtimesScraper` was also NOT in `SCRAPERS` — now registered.

3. **`fukuoka_now.py` scope**: Correct from the start — no regional filter added.

**Lessons:**
- Cinema scrapers should call `lookup_movie_titles(title)` before constructing `Event()` and pass `name_zh`/`name_en`. Annotator GPT fallback still applies if `(None, None)`.
- PR TIMES keywords must NEVER include city names (e.g. `東京`) — project covers 全日本.
- Every new scraper file must be added to `SCRAPERS` in the same commit. Do not defer.

---

## 2026-04-29 — Fukuoka Now scraper implemented [fukuoka_now]

**New source**: `FukuokaNowScraper` — Fukuoka's major English-language event calendar.

**Key decisions:**
- Static HTML (WordPress) — used `requests` + BeautifulSoup, no Playwright needed
- Taiwan filter on card title + tags + short description before detail page fetch
- `_is_taiwan()` only; no false-positive guard needed (site uses "Taiwan" in actual Taiwan events only)
- Venue extracted via line-by-line keyword match (City Hall, Fureai, Tenjin, etc.) — no structured `場所:` label
- 0 events in dry-run is correct: 台湾祭 in 福岡 2026 ended Feb 23; next event not yet listed

**Lesson**: For seasonal event scrapers, 0 dry-run output is valid when the annual event is between seasons. Verify by unit-testing `_parse_detail()` on the archived event URL directly.

---

## 2026-04-29 — research_sources status not updated after scraper implementation [livepocket]

**Error:** After implementing and committing `LivepocketScraper`, the `research_sources` row (id=106) was left with `status = 'researched'` instead of `implemented`. The admin Sources table showed「已深度研究」badge and a「建立爬蟲 Issue」button — implying the scraper had NOT been built.

Additionally, `scraper_source_name` was left as `null`, so the "scraper_source_name → source mapping" used by `AdminSourcesTable` to link event counts to sources could not resolve the source.

**Fix:** Manual DB update:
```python
sb.table('research_sources').update({
    'status': 'implemented',
    'scraper_source_name': 'livepocket'
}).eq('id', 106).execute()
```

**Lesson:** The new source checklist must include **both** DB fields as a single atomic step:
- `status = 'implemented'`
- `scraper_source_name = '<source_name>'` (matches `SOURCE_NAME` constant in the scraper)

Neither field alone is sufficient. Omitting `scraper_source_name` breaks event-count display in AdminSourcesTable. This step must be done in the same session as the scraper commit — not deferred.

---

## 2026-04-29 — LivePocket scraper: wrong dl selector + class name conflict [livepocket]

**Error 1: dl selector class mismatch**
Assumed `dl` class was `event-detail-info` based on the docstring in the research profile. Actual class is `event-detail-info__list`. Additionally, `dt`/`dd` pairs are wrapped in `div.event-detail-info__block` inside the `dl` — they are NOT direct children. Using `dt.find_next_sibling("dd")` returned nothing. All 14 events had `start_date = null` on first dry-run.

**Fix:** Changed selector to `soup.select_one("dl.event-detail-info__list")` and rewrote `_get_dd_text()` to iterate `dl.select("div.event-detail-info__block")` → `block.select_one("dt")` / `block.select_one("dd")`.

**Error 2: CamelCase class name `_scraper_key` conflict**
Named the class `LivePocketScraper`. The `_scraper_key()` function in `main.py` splits on CamelCase boundaries, producing `live_pocket` — which does NOT match `source_name = "livepocket"`. Running `--source livepocket` reported "Unknown source".

**Fix:** Renamed class to `LivepocketScraper` (lowercase `p`) → `_scraper_key = livepocket`.

**Result:** 14 Taiwan events found after both fixes. `start_date` populated for all.

**Lessons:**
- Always verify `dl` class name from live HTML before writing selectors — research profiles can have stale assumptions.
- For platform names with no natural CamelCase split (e.g. "livepocket"), always use `Livepocket` (not `LivePocket`) to ensure `_scraper_key` matches `source_name`.
- Duplicate `dl` blocks exist (desktop + mobile) — always use `select_one()`.

---

## 2026-04-29: Peatix organizer Layer 3 + discovery_accounts.py daily rotation

**變更：**
- peatix.py: `_load_db_organizers()`, `_scrape_group_events()`, `scrape()` DB loop
- discovery_accounts.py: 4-slot rotation, `_run_note_task()`, `_run_peatix_task()`, `_verify_peatix_group()`
- discovery-accounts.yml: Mon-Thu daily cron, `DISCOVERY_SLOT` env var

**規則新增：**
- Layer 3 擴充到新平台時，`agent_category` 必須是平台獨立的值（`peatix_organizer` 而非通用名稱）
- `source_profile` 結構須包含 `platform` 欄位以區分來源
- discovery_accounts.py 的 `--dry-run --slot N` 組合是必要的驗證入口

**Skills folder convention（同日修正）：**
- `jats/` 和 `waseda_taiwan/` 移入 `.github/skills/sources/` 子目錄（原放在頂層，屬錯誤）
- 任何新的 per-source skill **必須** 放在 `sources/` 子目錄下

---

## 2026-04-29 — annotator: truncation limit 12K→20K でも GPT が sub-events を 2 件しか生成しない

**発見：** 台湾文化センター「台湾映画上映会2026」（16 場上映）の sub-events が 2 件しか DB に存在しない。annotator の truncation limit を 12,000→20,000 に引き上げたが、GPT-4o-mini は依然 2 件の sub-events しか返さなかった（output: 1,191 tokens）。

**根本原因：** description が 13,492 文字（旧 12,000 char truncation で切断されていた）→ truncation 修正後も GPT-4o-mini は全 16 件を抽出しなかった。入力が長く密度が高い場合、GPT が自律的に生成を打ち切る傾向がある。

**修正：** 
1. `annotator.py` truncation limit 12,000→20,000 chars（commit `ff2a2ac`）
2. `_insert_sub_events.py` で 16 件の sub-events を手動挿入（一時スクリプト、削除済み）
3. Sub-events：10 正片（5月〜10月）＋ 6 アンコール（6/7, 9/19, 10/4 @ ユーロライブ/シネ・ヌーヴォ）

**教訓：** GPT が全 sub-events を確実に生成しない場合、scraper 層で直接 sub-events を生成するほうが信頼性が高い。連続上映シリーズ（映画祭等）は scraper で各回を `Event` として生成し `parent_event_id` を設定するべき。

---

## 2026-04-28 — 日泰食堂 [cine_marine] — user report confirmed
**Report types:** wrongSelectionReason, selectionReason:この映画は香港の食堂を舞台に、社会の変化に直面する人々の姿を描いており、台湾、香港、フランスの共同制作です。
**Admin notes:** —
**Action:** Event deactivated — re-annotation triggered (annotation_status=pending).
---

---

## 2026-04-28 — 赤色的線 輪迴的秘密 [shin_bungeiza] — user report confirmed
**Report types:** wrongSelectionReason, selectionReason:這部電影是台灣製作，反映了台灣的文化和故事。
**Admin notes:** —
**Action:** Event deactivated — re-annotation triggered (annotation_status=pending).
---

---

## 2026-04-28 — 霧的如同 [cinemart_shinjuku] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:大濛, fieldEdit:name:en:A Foggy Tale, fieldEdit:name:ja:霧のごとく
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---

## 2026-04-28 — 台灣發祭 Taiwan Faasai 2026 [taiwan_faasai] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan
**After (corrected):** lifestyle_food
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-28 — 身體化巴索里尼 - 吸引力法則 [ssff] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** performing_arts
**After (corrected):** movie
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-28 — 品嚐台灣茶，享受台灣遊戲的聚會 [kokuchpro] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan
**After (corrected):** taiwan_mandarin, lifestyle_food, taiwan_japan, workshop
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-28 — 台灣電影上映會《海をみつめる日》上映暨座談會 [taiwan_cultural_center] — user report confirmed
**Report types:** wrongDetails, wrongCategory, fieldEdit:name:zh:台灣電影放映會《看海的日子》上映暨座談會, fieldEdit:name:en:Taiwan Film Screening of 'A Flower in the Raining Night' and Talk Event, fieldEdit:name:ja:台湾映画上映会『海をみつめる日』上映＆トークイベント
**Before (AI category):** movie, lecture
**After (corrected):** movie, literature, history
**Wrong fields:** name
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-28 — 阿嬤的夢中情人 [eiga_com] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** movie, lecture
**After (corrected):** movie, history
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-28 — 甘露水 [taiwan_cultural_center] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** movie
**After (corrected):** movie, art, history
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-28 — 看海的日子（數位修復版） [taiwan_cultural_center] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** movie
**After (corrected):** movie, history, literature
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---


---

## 2026-04-28 — 台灣文化祭2026春 [arukikata] — user report confirmed
**Report types:** wrongCategory
**Before (AI category):** lifestyle_food, taiwan_japan, lecture
**After (corrected):** lifestyle_food, tourism, lecture, retail
**Admin notes:** —
**Action:** Category corrected inline — event remains active (is_active=true, annotation_status=annotated).
---

---

## 2026-04-28 — 電影《大濛》上映 [taioan_dokyokai] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:電影《大濛》上映, fieldEdit:name:en:Screening of the Movie 'A Foggy Tale', fieldEdit:name:ja:映画『霧のごとく』上映
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---

## 2026-04-28 — 映画『霧のごとく（大濛）』東京貸切上映会＆トークショー [taioan_dokyokai] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:電影《大濛》東京包場 x 映後座談, fieldEdit:name:en:Private screening & talk of the film 'A Foggy Tale' in Tokyo, fieldEdit:name:ja:映画『霧のごとく（大濛）』東京貸切上映会＆トークショー
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


---

## 2026-04-28 — 8 個爬蟲 source 檔案存在但未加入 SCRAPERS 列表

**Error:** CineMarineScraper、EsliteSpectrumScraper、MoonRomanticScraper、MorcAsagayaScraper、ShinBungeizaScraper、SsffScraper、TaiwanFaasaiScraper、TokyoFilmexScraper 已有 source 檔案但未加入 `scraper/main.py` 的 `SCRAPERS = [...]`。CI 從未執行這些爬蟲。
**Fix:** 補充 8 個爬蟲的 import 及 SCRAPERS 列表項目。以 `--dry-run` 確認各爬蟲能執行（CineMarineScraper 1件、EsliteSpectrumScraper 2件、MoonRomanticScraper 1件、ShinBungeizaScraper 1件、SsffScraper 6件、TaiwanFaasaiScraper 1件；MorcAsagayaScraper 和 TokyoFilmexScraper 0件屬正常——當日無台灣活動）。
**Lesson:** 建立新爬蟲 source 檔案後必須在同一 commit 確認已加入 SCRAPERS。定期比對 `ls sources/*.py` 與 SCRAPERS 列表，source 檔案不在 SCRAPERS 中將被 CI 靜默略過。→ Updated "Registration" in SKILL.md.

---

## 2026-04-28 — 映画『霧のごとく（大濛）』東京貸切上映会＆トークショー [peatix] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:電影《大濛》東京電影包場 x 映後座談, fieldEdit:name:en:Private Screening & Talk of the Movie 'A Foggy Tale' in Tokyo, fieldEdit:name:ja:映画『霧のごとく』プライベート貸切上映会＆トークショー
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---

## 2026-04-28 — 電影《霧的如同（大濛）》東京包場上映會暨映後座談 [peatix] — user report confirmed
**Report types:** wrongDetails, fieldEdit:name:zh:電影《大濛》東京包場上映會暨映後座談, fieldEdit:name:en:Private Screening & Talk of the Movie 'A Foggy Tale' in Tokyo, fieldEdit:name:ja:映画『霧のごとく』プライベート貸切上映会＆トーク
**Wrong fields:** name
**Admin notes:** —
**Action:** Annotatable fields nulled out — re-annotation triggered. Will auto-reactivate after annotator runs.
---

---


---

## 2026-04-28 — merger.py Pass 2: pre-event press release not matched (start_date before event)

**Error:** `c1ba79b6` (google_news_rss, gnews_c5e4ad11f794) pointed to a prtimes.jp press release about 台湾祭in群馬太田2026 published **2026-01-15** — two months BEFORE the event start (2026-03-14). Merger Pass 2 uses `_date_in_range(news.start_date, official.start_date, official.end_date)` which returned False (`2026-01-15 < 2026-03-14`). Event was not merged; remained is_active=False with empty secondary_source_urls and prtimes content never incorporated.

**Fix:**
1. `merger.py`: Added `_PRESS_RELEASE_LOOKBACK_DAYS = 90` constant; changed `_date_in_range` to accept `lookback_days` parameter; Pass 2 now calls `_date_in_range(..., lookback_days=_PRESS_RELEASE_LOOKBACK_DAYS)` → range becomes `[start_date - 90d, end_date]`.
2. DB: Manually merged c1ba79b6 into primary `taiwan_matsuri_202603-gunmaota`:
   - Added google_news URL + direct prtimes.jp URL to `secondary_source_urls`
   - Fetched prtimes article body → appended as `別来源補足 (prtimes)` in `raw_description`
   - Set `annotation_status = 'pending'` for re-annotation with enriched content

**Lesson:** Pre-event press releases (prtimes, PR WIRE) are published weeks or months BEFORE the event start date. Merger Pass 2 must use a lookback window (currently 90 days) on `official.start_date` — NOT a strict lower bound. Also: when a google_news_rss entry links to a prtimes article, the ACTUAL rich content is at prtimes.jp — fetch that URL for the merger's raw_description supplement, not the google_news headline.

---

**Error:** `google_news_rss` 的「イオン太田で台湾グルメと台南ランタン祭イベント」（id: 1c766979）和 `taiwan_matsuri_202603-gunmaota` 是同一個活動，但 `merger.py` Pass 1 未偵測到，原因有二：
1. 名稱相似度太低（新聞報導標題 vs 官方活動名稱），不達 0.85 閾值。
2. `start_date` 不同（報導發布日 2026-03-16 vs 開幕日 2026-03-14），不在同一 `date_group`。

**Fix:**
1. 手動合併 DB：將 google_news_rss source_url 加入 `taiwan_matsuri_202603-gunmaota` 的 `secondary_source_urls`；設 google_news_rss 事件 `is_active=False`。
2. 同時發現スカイツリー2026 也有相同問題（`a5d24992`），一併合併。
3. `merger.py` 新增 **Pass 2 — News-report matching**：對 `_NEWS_SOURCES = {google_news_rss, prtimes, nhk_rss}`，以「日期在範圍內 + 地點 token 重疊」取代名稱相似度，並新增 `_location_overlap()` / `_date_in_range()` helpers。DB select 同步補加 `end_date,location_name`。

**Lesson:** 新聞/報導來源（google_news_rss、prtimes、nhk_rss）的文章標題和官方活動名稱結構不同，無法用名稱相似度合併。發現此類重複時，應先 `python merger.py --dry-run` 確認 Pass 2 能偵測，再正式執行。 → Added `## merger.py` section and Pass 2 rules to SKILL.md.

---

## 2026-04-28 — taiwan_matsuri: geographic filter + dry-run-only fix caused missed events

**Error 1 (initial version):** `_TOKYO_KANTO_KEYWORDS` filter limited scraping to venues matching `東京|スカイツリー|横浜|幕張|千葉|埼玉`. Gunma (群馬), Kumamoto (熊本), Fukuoka (福岡), Nara etc. were silently dropped — even though the project scope is all of Japan.

**Error 2 (fix commit):** The fix commit (`1d3cd1c`, April 26) removed the filter and ran `--dry-run` to confirm both Tokyo and Kumamoto were found. However, **no non-dry-run was executed after the fix.** The newly discovered events (`202603-gunmaota`, `202604-kumamoto`) were never written to DB. They remained missing until a manual run on April 28.

**Fix:** Removed `_TOKYO_KANTO_KEYWORDS` entirely. After confirming with dry-run, ran `python main.py --source taiwan_matsuri` (non-dry-run) to actually write to DB.

**Lesson 1:** Never restrict a scraper's geographic scope to a subset of Japan. The project covers all of Japan（全日本）. If the initial implementation needs a filter for testing, remove it before the first production run.

**Lesson 2:** A dry-run fix commit is incomplete. After removing a scraper bug (especially a filter bug), always follow up with a real run (`python main.py --source <name>`, no `--dry-run`) before the next CI cycle. Otherwise the fix is verified but the data gap persists until the next CI run.

---

## 2026-04-28 — eiga_com: 原題から name_zh / name_en を直接抽出する

**発見：** 映画.com の映画詳細ページ（例：`/movie/82162/`）の `p.data` に「原題または英題：阿嬤的夢中情人 Forever Love」という行が存在する。スクレイパーは `name_ja`（日本語配給タイトル）しか設定していなかったため、中文・英語タイトルは AI アノテーターの推測に頼っていた。

**根本原因：** `_fetch_movie_detail()` は `p.data` から製作年・上映時間・国情報のみ使用し、`原題` 行を無視していた。

**修正：** `_ORIG_TITLE_RE` regex と `_parse_original_title()` helper を追加。
- 非 ASCII ブロック（CJK）→ `name_zh`、ASCII ブロック（英語）→ `name_en` に分離
- `_fetch_movie_detail()` の返り値を `(title, pub_date, raw_description, name_zh, name_en)` に拡張
- fallback Event と `_scrape_area_page()` の両方に `name_zh`, `name_en` を渡す

**例：**
- `原題または英題：阿嬤的夢中情人 Forever Love` → `name_zh="阿嬤的夢中情人"`, `name_en="Forever Love"`

**Lesson：**
- 映画系ソースには必ず詳細ページの「原題」「英題」「原題または英題」フィールドを確認すること。
- 原タイトルは AI より高精度 — スクレイパーで確定できる情報は AI に任せない。
- ルールを SKILL.md `## eiga_com-specific` に追記済み。

---

## 2026-04-27 — eiga_com: per-theater redesign (3 address extraction bugs)

**Error 1:** `a.more-schedule a[href*='/movie-theater/']` selected the first matching link which was `/movie-theater/{id}/{pref}/{area}/{theater_id}/mail/` (the copy-to-clipboard link), not the theater detail page. `theater_id` was extracted correctly, but `_fetch_theater_address()` fetched the mail page which has no `theater-table`.

**Fix 1:** Use `a.icon.arrow[href*='/movie-theater/']` to get the "all schedule" detail link specifically.

**Lesson 1:** When multiple links share the same `href` pattern (copy/print/all-schedule), always target by CSS class (e.g. `a.icon.arrow`) not by href pattern alone. → Added to `eiga_com-specific` in SKILL.md.

**Error 2:** Page-wide regex `r'東京都[^\s<>]{5,50}'` on the area page matched JS-embedded `東京都"};params_ga4.login_status=...` instead of the actual address.

**Fix 2:** Switched to structured extraction: `table.theater-table th:contains("住所") + td` on the theater detail page.

**Lesson 2:** Never use page-wide address regex on pages with embedded JS/JSON. Use structured HTML selectors (`th`/`td` pairs) for reliable address extraction. → Added to `eiga_com-specific` in SKILL.md.

**Error 3:** `td.get_text()` included `<a>` link text "映画館公式ページ" appended to the address string.

**Fix 3:** Call `a_tag.decompose()` on all `<a>` children inside `td` before `get_text()`.

**Lesson 3:** When a `<td>` contains both text nodes and `<a>` child elements, always decompose unwanted children before `get_text()` to avoid mixing link text into field values. → Added to `eiga_com-specific` in SKILL.md.

---

## 2026-04-27 — taipei_fukuoka / yebizo: scrapers written but not registered or dry-run verified

**Error:** `taipei_fukuoka.py` and `yebizo.py` were fully written (270 and 255 lines respectively, complete `scrape()` + `Event()` return) but were left as untracked files with no entry in `scraper/main.py` → `SCRAPERS`. Running `python main.py --dry-run --source taipei_fukuoka` returned `Unknown source` — the scrapers had never been tested.

**Fix:** Added imports and class instantiations to `main.py`. Ran dry-run for both (exit 0, 3 events each). Then committed all files together.

**Lesson:** Writing a source file without registering it in `main.py` and running a dry-run means the scraper will never execute in CI, and the work is invisible until discovered manually. The commit gate is: **source file + main.py registration + dry-run pass must all be in the same commit.** Never leave an untracked source file without a companion `main.py` edit.

---

## 2026-04-26 — scope expanded to all of Japan（全日本）

**Change:** Removed `prefecture=tokyo` from Connpass API params; updated docstrings for Doorkeeper and Connpass; updated agent descriptions and community-platforms subagent.

**Root cause:** Scrapers were unintentionally limited to Tokyo by an API parameter. The project scope is all of Japan — Osaka, Kyoto, Fukuoka, Sapporo, etc. are all in scope.

**Fix:** `connpass.py` no longer passes `prefecture=tokyo`; `doorkeeper.py` has never had a location filter and should stay that way.

**Lesson:** Never add a prefecture/region filter to API scrapers unless the *source itself* is geographically bounded. Taiwan relevance (`_TAIWAN_KEYWORDS`) is the only required filter. → Added `## Geographic Scope` to SKILL.md.

---

## 2026-04-26 — スコープ拡張：東京限定 → 全日本

**変更内容**: ユーザー指示により対象スコープを東京から全日本（全国）に拡張。

**背景**: プロジェクト名は「Tokyo Taiwan Radar」だが、台湾関連イベントは大阪・京都・福岡・札幌等でも開催される。スクレイパーが地理フィルターで東京以外のイベントを除外することは意図しない動作。

**適用した変更**:
- `copilot-instructions.md` — プロジェクト概要を「in Japan（全日本）」に更新、Geographic Scope 注記追加
- `scraper-expert.agent.md` — description + `> **Scope**` 注記追加
- `.github/skills/agents/scraper-expert/SKILL.md` — `## Geographic Scope` セクション追加
- `.github/skills/agents/scraper-expert/SKILL.md` — `## Geographic Scope` セクション追加

**教訓**: 地理的スコープは SKILL.md の冒頭に専用セクションとして明示すること。東京以外を除外する地理フィルターを追加する前に Geographic Scope セクションを必ず確認すること。

---

## 2026-04-26 — cine_marine + taiwan_faasai: two new scrapers implemented

**cine_marine (横浜シネマリン):**
- Listing page structure: each film entry is `<h2>` (date) + `<h3><a>` (title+URL) + `<div class="content_block">` (details) within a single `.entry-content` article.
- Taiwan filter applied only to `content_block` text (not full film page) to avoid false positives from sidebar that lists all current films.
- Source name: `cine_marine` (from `CineMarineScraper` via `_scraper_key`).

**taiwan_faasai (台湾發祭 Taiwan Faasai):**
- Annual 3-day free outdoor festival in Ueno Park.
- TLS issue: `verify=False` required, `InsecureRequestWarning` suppressed.
- Source ID: `taiwan_faasai_{year}` — stable per year.

---


**Error (morc_asagaya):** All 24 film pages matched Taiwan filter because every page contains a site-wide `section#tp_info` with "台湾巨匠傑作選2024" promotion links. Initial implementation applied `get_text()` to the entire page including this section.

**Fix (morc_asagaya):** Added `soup.select('#tp_info')[...].decompose()` before keyword search. Result: 0 events (correct — no Taiwan films on screen).

**Error (shin_bungeiza):** `_parse_nihon_date_only` used `p.find_previous("h2")` to find the start date. Because `p.nihon-date` is the first child in its container, `find_previous` returned an h2 from a prior film block → wrong date (e.g. 5/6 instead of 5/8).

**Fix (shin_bungeiza):** Rewrote to iterate `parent.children`, collecting h2 elements that appear after the `p`. First h2 → start date (M/D format). Last h2 → end date (day-only, same month with wrap guard).

**Lesson (generalizable):** When an element is the first sibling in its container, `find_previous()` crosses container boundaries. Always iterate `parent.children` for sibling-relative navigation. Also: site-wide banners can pollute keyword filters — inspect false-positive pages to identify the offending section and exclude it.

---

## 2026-04-26 — workflow: push step was missing from post-change checklist

**Error:** After implementing cinemart_shinjuku scraper (Phase 4 docs complete), task_complete was called without committing or pushing. The feature branch had to be created and pushed manually in a follow-up turn.

**Fix:** Added Step 5 (git commit & push) to `## Mandatory Post-Change Checklist` in `SKILL.md`, and added Phase 5 (Commit & Push) to `scraper-expert.agent.md`.

**Lesson:** Every scraper session must end with a commit + push to a feature branch before calling task_complete. → Added to SKILL.md Step 5 and agent.md Phase 5.

---

## 2026-04-26 — taiwanshi: date/venue regex misses non-standard separators

**Error:** 2 posts had `date parse failed` warnings; 1 post had `venue=None`. Affected: `場所：` label, `会場　` (full-width space only, no colon), and `日時： 2025 年10月4 日` (spaces within date).

**Root cause:** Initial regex assumed `日時[：:]` (colon required) and `会場[：:]` (colon required), missing: (a) full-width space separator `日時　`, (b) `場所：` label instead of `会場：`, (c) OCR/copy-paste spacing within the date `2025 年10月4 日`.

**Fix:** Extended date regex separator to `[：:\s\u3000]*` and date component matches to `\s*年\s*...\s*月\s*...\s*日`. Extended venue regex to `(?:会場|場所)[\uff1a:\u3000 \t]+`.

**Lesson:** Japanese blog posts use inconsistent separators after label words. Always allow `[：:\s\u3000]*` (colon or any whitespace) as the separator between a label (`日時`, `会場`, `場所`) and its value. Also allow `\s*` between digit groups and kanji connectors in date fields. → Added to `## taiwanshi-specific` in SKILL.md.

---

## 2026-04-26 — ifi: URL injected into location_address from venue map link

**Error:** `location_address` contained `https://www.u-tokyo.ac.jp/campusmap/...` appended after the venue name.

**Root cause:** IFI appends a campus map URL on the line immediately after the venue name in `inner_text`. `_extract_info()` captured it as part of the venue value.

**Fix:** Filter venue lines with `not ln.strip().startswith("http")` before building `location_name`/`location_address`.

**Lesson:** Academic sites frequently append map/registration URLs directly below venue names without a visual separator. Always filter HTTP lines from venue extraction.

---

## 2026-04-26 — tokyonow: API keyword search returns 0 for Japanese terms

**Error:** `GET /wp-json/tribe/events/v1/events?search=台湾` returns 0 results even when Taiwan events exist on the site.

**Root cause:** The Tribe Events v1 WordPress plugin `search` parameter only matches English title/slug fields — it does not index Japanese text.

**Fix:** Full-page scan strategy — paginate all future events with `start_date=<today>&per_page=50`, apply local `_TAIWAN_KEYWORDS = ["台湾", "Taiwan", "臺灣"]` filter on stripped title + description.

**Lesson:** Do not assume REST API `search` parameters support Japanese full-text search. Always test a known Japanese keyword against a known Japanese event before relying on server-side filtering. Fall back to full-scan + local filter when the API returns 0 unexpectedly.

---

## 2026-04-25 — iwafu: Conan events re-appeared (direct URL accessible + card title bypass)

**Error (1 — direct URL accessible):** Deactivated events (`is_active=False`) were still accessible via direct URL. The event detail page had no `is_active` check — it fetched by ID regardless of status.

**Error (2 — card title truncation bypass):** `_BLOCKED_TITLE_PATTERNS` only checked `card_title` from search-result card text. If the card title was truncated and didn't contain both "リアル脱出ゲーム" AND "名探偵コナン", the filter would pass. No second check was done on the actual h1 title after loading the detail page.

**Fix:**
1. Hard deleted all 7 Conan events from DB (iwafu_1133807, 1133810, 1134057–1134061).
2. `web/app/[locale]/events/[id]/page.tsx`: Added `if (!event.is_active) notFound()` — inactive events now return HTTP 404.
3. `scraper/sources/iwafu.py`: Added `_BLOCKED_SERIES = re.compile(r"名探偵コナン")` checked on both card title (pre-load) and h1 title (post-load). Extended `_BLOCKED_TITLE_PATTERNS`.

**Lesson:**
- Inactive events remain accessible by direct URL unless detail page returns `notFound()` for `!is_active`. Always add this guard.
- Title blocks must check BOTH card title (pre-load) AND h1 title (post-load). Card titles can be truncated.
- For permanently blocked IP series, use `_BLOCKED_SERIES` with just the IP name. Simpler and catches all title variants.
- When an IP series is confirmed non-Taiwan-themed, prefer hard delete over deactivation to prevent URL resurrection.

---

## 2026-04-25 — iwafu/koryu/peatix: location_address stored as generic prefecture name ("東京") instead of real venue

**Error:** Three scrapers were writing useless generic values to `location_address`:
- **iwafu**: `_scrape_detail()` set `location_address = card.get("prefecture")` which was always `"東京"` (or `"東 京"` with space). The detail page contains `場所：中野区役所…` but was never parsed.
- **koryu**: `_extract_location_address()` only finds `所在地/住所` sections; when absent, `location_address` stayed `None` even though `_extract_venue()` had already extracted a useful venue name.
- **peatix**: CSS selectors `.venue-address` / `[class*='address']` miss the address on many events. No regex fallback existed.

**Fix:**
- `iwafu.py` `_scrape_detail()`: Added `re.search(r'場所[：:]\s*(.+?)(?:\n|交通手段|Q&A|https?://|$)', main_text)` regex before the `card.prefecture` fallback. Sets both `location_name` and `location_address` to the captured venue.
- `koryu.py` `_scrape_detail()`: Changed `location_address = _extract_location_address(body_text)` → `_extract_location_address(body_text) or (venue if venue else None)`.
- `peatix.py` location block: Added regex fallback on `page_text` — `LOCATION\n<name>` for venue name, `〒NNN-NNNN` or `東京都...` for address.
- `scraper/backfill_locations.py` (new): One-off script to re-visit iwafu/koryu source URLs and apply the new extraction logic to existing DB rows. Supports `--dry-run`.

**Lesson:**
- When a detail page contains a structured `場所：` or `会場：` label, always prefer that over the card-level prefecture. Parse it with a regex before falling back to coarser data.
- For scrapers where the main location field may be absent, use the venue name as an `or` fallback for `location_address` — partial info is better than `None` or a bare prefecture.
- CSS selectors on JS-heavy pages (Peatix) are unreliable for location; always add a `page_text` regex fallback.
→ Added to SKILL.md (`iwafu-specific`, `koryu-specific`) and `peatix/SKILL.md` (Location Extraction section).

---

## 2026-04-25 — location/address/hours displayed in Japanese on zh/en locale

**Error:** `location_name`, `location_address`, and `business_hours` had no localized variants in the DB schema. The event detail page always showed the Japanese original regardless of the visitor's locale (e.g., "高知県立牧野植物園", "午前9時から午後5時" displayed to English/Chinese visitors).

**Root cause:** DB schema had only single-language columns for these three fields. The annotator extracted them from Japanese source text and stored only Japanese. No `_zh`/`_en` variants existed.

**Fix:**
1. `supabase/migrations/010_localized_location.sql` — Added 6 new columns: `location_name_zh`, `location_name_en`, `location_address_zh`, `location_address_en`, `business_hours_zh`, `business_hours_en`.
2. `scraper/annotator.py` — Updated GPT schema in `SYSTEM_PROMPT` to request the 6 new fields. Updated `update_data` and sub-event rows to populate them.
3. `web/lib/types.ts` — Added 6 fields to `Event` interface. Added three helper functions: `getEventLocationName(event, locale)`, `getEventLocationAddress(event, locale)`, `getEventBusinessHours(event, locale)` — all fall back to the Japanese original.
4. `web/app/[locale]/events/[id]/page.tsx` — Import and use the three new helpers instead of raw `event.location_name`, `event.location_address`, `event.business_hours`.
5. DB fix: reset `f463ad3d` (iwafu_1062563) to pending and re-annotated after migration.

**Lesson:**
- Any field that a non-Japanese visitor reads should have `_zh`/`_en` variants. Apply the same `_ja/_zh/_en` pattern to location, address, and hours — not just name and description.
- Always check: does the event detail page display anything sourced from Japanese-only source text without a locale helper?
- When adding new localized columns, the annotator's `update_data` must include ALL new fields (with `_str()`/`_loc()` cleaning). The GPT schema must explicitly request them.

---

## 2026-04-25 — AdminEditClient: null name_zh/name_en converted to "" on save → title disappears

**Error:** When an event has `name_zh = null` (or GPT returned `null`), the admin edit form initializes the field with `event.name_zh ?? ""`, converting `null` to `""`. On save, `""` is written to the DB. The `getEventName` function used `??` which does NOT fall back on empty strings (`"" ?? fallback → ""`), so the event title disappeared in the zh/en locale.

Additionally, events with `annotation_status = 'annotated'` but empty strings in `name_zh`/`name_en`/`description_zh`/`description_en` (e.g. `iwafu_1062563` — 【高知県立牧野植物園】こんこん山花さんぽ) showed no title or description because the DB contained `""` instead of `null`.

**Root causes (two bugs interacting):**
1. `AdminEditClient.tsx`: `const payload = { ...form }` sends `""` for every empty name/description field, converting `null → ""` in the DB.
2. `web/lib/types.ts` `getEventName`/`getEventDescription`: used `??` instead of `||`, so `""` did not trigger fallback to next locale.

**Fix:**
1. `web/lib/types.ts`: Changed `??` → `||` in `getEventName` and `getEventDescription` so empty strings fall back to the next locale.
2. `web/components/AdminEditClient.tsx`: Added `nullify` helper in `handleSave` — converts `""` to `null` for name/description fields before PATCH. `name_ja` falls back to `event.raw_title` if empty.
3. Direct DB fix for `f463ad3d` (iwafu_1062563): cleared `""` → `null`, reset `annotation_status = 'pending'`, re-ran `annotator.py` → produced proper `name_zh = '春花漫步'`, `name_en = 'Spring Flower Walk'`.

**Lesson:**
- Admin form fields that represent nullable DB columns should send `null` (not `""`) when empty. Wrap empty strings with `|| null` in the save payload.
- `??` and `||` have different semantics: `??` only catches `null`/`undefined`; `||` also catches `""` and `0`. Use `||` for locale fallback chains where GPT might return empty string.
- After annotator bugs produce empty strings for existing events, you must manually reset those events to `pending` and re-run `annotator.py`. The `_str()` helper in annotator prevents recurrence for future runs only.

---

## 2026-04-25 — iwafu: 6 more Conan events survived after _GLOBAL_TOUR_PATTERNS fix

**Error:** When `_GLOBAL_TOUR_PATTERNS` was added to `iwafu.py`, it only prevented **future** scraper runs from re-inserting matching events. The 6 existing DB rows (`iwafu_1134057` through `iwafu_1134061` + `iwafu_1133807`) were already in the DB with `is_active=True` and were unaffected. They continued to appear in the admin backend.

**Fix:**
1. Queried for all `%コナン%` events, deactivated all 6 remaining ones via targeted `update().eq("id", ...)` calls.
2. Added `_BLOCKED_TITLE_PATTERNS` regex in `iwafu.py` with pattern `リアル脱出ゲーム.*名探偵コナン` — checked in `_scrape_detail` **before** the page load (fast-reject). This blocks any new source_id variants of the same series (e.g. new tour stops) regardless of description wording.

**Lesson:**
- Fixing the scraper filter does NOT retroactively remove existing DB records. After adding a filter, always run a DB audit to deactivate any already-stored events that match the new rule.
- For well-known IP series that run global tours (anime collabs, game IPs), add the series name to `_BLOCKED_TITLE_PATTERNS` so all future venue variants are blocked at title level — before the detail page is fetched. Description-only filters can miss series with identical descriptions.
- Pattern for querying all events from a false-positive series: `sb.table("events").select("id,source_id").ilike("raw_title", "%<keyword>%")`.

---

## 2026-04-25 — taiwan_kyokai: end_date always null; publish-date used instead of event date

**Error (1 — end_date null):** `_extract_event_fields` in `taiwan_kyokai.py` never set `result["end_date"]`, leaving a comment "we keep only start_date for now". All single-day events had `end_date=None`, causing them to remain in "active" listings indefinitely (the web filter keeps events where `end_date IS NULL` OR `end_date >= today`).

**Error (2 — wrong start_date):** For pages where the event date lacks a year (e.g. `今年は5月16日（土）に執り行われます`), the generic fallback regex `YYYY年MM月DD日` found the page's **publish date** at the top of the body (`2026年4月20日`) instead of the actual event date (`5月16日`). The publish date appears prominently on taiwan-kyokai.or.jp pages just below the title.

**Fix:**
1. Added DOW-qualified date extraction step in `_extract_event_fields` — searches for `\d{1,2}月\d{1,2}日（[月火水木金土日][曜]?[日]?）` and infers year from nearest `20XX年` in text. Runs BEFORE the generic fallback, so `今年は5月16日（土）` is preferred over the bare `2026年4月20日` publish date.
2. Added single-day end_date rule at the bottom of `_extract_event_fields`: `if result["start_date"] and not result["end_date"]: result["end_date"] = result["start_date"]`. Taiwan Kyokai events are all single-day.
3. Direct DB fixes: `taiwan_kyokai_news-260420-2` start/end → 2026-05-16; `taiwan_kyokai_news-260217` end_date → 2026-04-12.

**Lesson:**
- **Always set `end_date = start_date` at end of `_extract_event_fields` for single-day sources.** Never leave it with a "for now" comment.
- On japan-kyokai-style sites, the page body starts with the **publish date** (`YYYY年MM月DD日`) before the actual event body. Never rely on the generic year-qualified date fallback alone.
- Dates with day-of-week markers `（土）（日）etc.` are almost always actual event dates. Prioritize these over bare `YYYY年MM月DD日` patterns when no structured `日時：` field is present.

---

## 2026-04-25 — annotator: leading ：colon included in location_name

**Error:** GPT extracted `会場：台北世界貿易センター１F（...）` and included the label separator `：` as the first character of `location_name`, producing `：台北世界貿易センター１F（...）` in the DB and on the web UI.

**Fix:** Added `_loc()` helper in `annotator.py` that calls `.lstrip("：；:; \u3000")` on all `location_name` and `location_address` values before writing to DB. Also did a direct DB fix for `koryu_4899`.

**Lesson:** Always strip leading `：；:;` and full-width space (`　`) from GPT-extracted location strings. GPT occasionally includes the Japanese label separator when the source text uses `会場：〇〇` or `場所：〇〇` patterns. Apply `_loc()` to both `location_name` and `location_address`.

---

## 2026-04-25 — iwafu: global-tour event passed Taiwan filter (コナン脱出ゲーム)

**Error:** `iwafu_1133810` (リアル脱出ゲーム×名探偵コナン) was collected because the description contained `台湾など世界各地で開催`. The event is a Japan/world-wide tour and has no Taiwan theme; the Tokyo instance is culturally identical to the Osaka and Nagoya instances.

**Fix:** Added `_GLOBAL_TOUR_PATTERNS` regex in `iwafu.py`. Any detail page whose `title + description` matches patterns like `台湾など世界各地|全国各地.*台湾` is rejected in `_scrape_detail()` before an Event is returned. Set `iwafu_1133810` to `is_active=False` in DB.

**Lesson:** "Being held in Taiwan (among many other cities)" does NOT make an event Taiwan-related. Only accept events where Taiwan is the theme or a primary focus, not just one venue on a global tour. Add `_GLOBAL_TOUR_PATTERNS` reject guard wherever iwafu full-text is searched by keyword 台湾.

---

## 2026-04-25 — arukikata: duplicate class caused old code to shadow new code

**Error:** `replace_string_in_file` on docstring-only line caused the old class body to remain appended after the new class in the same file. Python silently uses the **last** definition, so the old (broken) `_parse_article` ran instead of the new one. Symptoms: dry-run returned old buggy results even after editing.

**Fix:** Used `wc -l` to detect the file was 615 lines instead of ~292; used `head -n 292 > /tmp && mv` to truncate to the correct end.

**Lesson:** After a large structural rewrite using `replace_string_in_file`, always verify the file has the expected line count with `wc -l`. If it's unexpectedly large, a duplicate class body is likely still present.

---

## 2026-04-25 — arukikata: keyword search strategy misses articles

**Error:** `?s=台湾+東京+イベント` search only returned 29 results; articles 362618 and 323275 were not among them — each requires a different keyword combination.

**Fix:** Switched to **WordPress sitemap monitoring**: `wp-sitemap-posts-webmagazine-2.xml` (605 entries) contains both target articles with `lastmod` timestamps. Filter by `lastmod >= today - 90 days`.

**Lesson:** For WordPress editorial sites, always check for `wp-sitemap-posts-{type}-{page}.xml` first. Sitemap monitoring is more comprehensive and stable than keyword search for low-frequency sources. The sitemap with the highest page number contains the newest articles.

---

## 2026-04-25 — Doorkeeper Tokyo filter false positive (中央区)

**Error:** `中央区` was included in `_TOKYO_MARKERS` in `doorkeeper.py`.
This matched 神戸市中央区, causing a Kobe event to pass the Tokyo location filter.

**Fix:** Removed all ward names that are not geographically unique to Tokyo from `_TOKYO_MARKERS`.
Kept only `東京都`, `東京`, and 23-ward names that are exclusive to Tokyo prefecture.

**Lesson:** Never add bare ward names like `中央区`, `南区`, `北区`, `西区` to a Tokyo marker set —
they appear in Osaka, Kobe, Nagoya, and many other cities.
The safest Tokyo markers are `東京都` and `東京` as substring matches.
Individual ward names are only safe if they are provably unique to Tokyo (e.g. `渋谷区`, `豊島区`).

---

## 2026-04-25 — Connpass API v1 → v2 migration (403 on v1)

**Observation:** Connpass API v1 (`/api/v1/event/`) now returns HTTP 403 for all requests,
including those from fixed IPs. The platform has fully migrated to v2 which requires an `X-API-Key` header.

**Implementation decision:** Built `ConnpassScraper` against v2 API.
If `CONNPASS_API_KEY` is not set, scraper logs a WARNING and returns `[]` — pipeline continues uninterrupted.

**Lesson:** API v1 is dead. Do not reference v1 endpoints in any future Connpass code.
The v2 key must be obtained via the Connpass help page: https://connpass.com/about/api/
Their ToS also explicitly prohibits non-API scraping (Playwright/curl), so the API key is mandatory.

## 2026-04-25 — koryu: Taiwan-office events leaking into DB (wrong location_address)

**Error:** `_scrape_detail()` never called `_is_tokyo_venue()`. The function existed but was dead code. As a result, events organised by koryu’s Taiwan offices (台北・台中・高雄) were ingested alongside Tokyo events. One event showed `location_address='台北'` even though the title clearly said 台中. 8 bad events accumulated in the DB.

**Root cause:** The koryu.or.jp DNN CMS renders a breadcrumb in the `<main>` inner text as a run-on string: `お知らせイベント・セミナー情報台北`. The trailing kanji (`台北`, `台中`, `東京`) is the office/category tag assigned in the CMS. Taiwan-office events were not filtered because no code checked this tag.

**Fix:**
1. Added `_TAIWAN_OFFICE_TAGS = {'台北', '台中', '高雄', '台南', '桃園', '新竹', '基隆', '嘉義'}` constant.
2. Added `_extract_office_tag(body_text)` that regex-extracts the tag after `イベント・セミナー情報\s*([\u4e00-\u9fa5]{1,6})`.
3. In `_scrape_detail`: if `office_tag in _TAIWAN_OFFICE_TAGS` → return None.
4. DB: hard-deactivated (`is_active=False`) all 8 Taiwan-location koryu events.

**Lesson:**
- After adding a geographic filter, ALWAYS audit existing DB rows with `eq('source_name','koryu')` and deactivate any that would have been blocked.
- DNN CMS breadcrumb text is part of `main.inner_text()` — location/office tags from the breadcrumb can pollute venue/address extraction if not stripped or checked first.
- `_is_tokyo_venue()` was defined but never called — dead utility functions should either be wired up or deleted. Prefer wiring them up and adding a test to confirm.

---

**Error (1 — direct URL accessible):** Deactivated events (`is_active=False`) were still accessible via direct URL. The event detail page had no `is_active` check — it fetched by ID regardless of status.

**Error (2 — card title truncation bypass):** `_BLOCKED_TITLE_PATTERNS` only checked `card_title` from search-result card text. If the card title was truncated and didn't contain both "リアル脱出ゲーム" AND "名探偵コナン", the filter would pass. No second check was done on the actual h1 title after loading the detail page.

**Fix:**
1. Hard deleted all 7 Conan events from DB (iwafu_1133807, 1133810, 1134057–1134061).
2. `web/app/[locale]/events/[id]/page.tsx`: Added `if (!event.is_active) notFound()` — inactive events now return HTTP 404.
3. `scraper/sources/iwafu.py`: Added `_BLOCKED_SERIES = re.compile(r"名探偵コナン")` checked on both card title (pre-load) and h1 title (post-load). Extended `_BLOCKED_TITLE_PATTERNS`.

**Lesson:**
- Inactive events remain accessible by direct URL unless detail page returns `notFound()` for `!is_active`. Always add this guard.
- Title blocks must check BOTH card title (pre-load) AND h1 title (post-load). Card titles can be truncated.
- For permanently blocked IP series, use `_BLOCKED_SERIES` with just the IP name. Simpler and catches all title variants.
- When an IP series is confirmed non-Taiwan-themed, prefer hard delete over deactivation to prevent URL resurrection.

---
