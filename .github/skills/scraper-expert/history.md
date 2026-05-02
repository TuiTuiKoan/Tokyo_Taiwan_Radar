# Scraper Expert Error History

<!-- Append new entries at the top -->

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

## 2026-04-28 — 日泰食堂 [cine_marine] — user report confirmed
**Report types:** wrongSelectionReason, selectionReason:這部電影以香港的食堂為背景，描繪了面對社會變遷的人們，由台湾・香港・法國共同製作。
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
## 2026-04-29 — taiwan_cultural_center: month-only date range caused publish-date fallback

**Error:** `期間：2026 年5 月～10 月(全10 回)` was matched by `_BODY_DATE_LABELS` regex, but `_parse_date("2026 年5 月")` returned `None` (no day component). `start_date` fell back to publish date `2026-04-27`, `end_date = 2026-04-27` — would have been archived that evening.

**Fix:** (1) `_parse_date()`: added month-only `YYYY年M月` → day 1 of that month. (2) `_extract_event_dates_from_body()`: detect month-only `end_raw`, inject year from start, advance to last day of month via `calendar.monthrange`. (3) DB record manually corrected to `2026-05-16 / 2026-10-24`. Scraper will upsert `2026-05-01 / 2026-10-31` on next run (acceptable).

**Lesson:** `_parse_date()` must handle `YYYY年M月` (no day). Multi-month series often use month-only ranges in the structured `期間：` label. Always verify end_date won't trigger same-day archival.

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
