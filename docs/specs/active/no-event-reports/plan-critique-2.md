# Plan Critique 2 — report-leads（#726）

> 本次批評和 Architect 用的是同一個模型（Claude，plan-critic subagent）：本 session 沒有安裝 Codex，所以沒有不同模型家族的第二視角。對象：`report-leads.md` v1。以下為 subagent 回覆全文。

## 總評

這個計畫照 #726 的需求走，和「資料完整性與找出來源缺口」的主軸一致，但成本和效益明顯不相稱：
- **成本（high）**：新增一個模組、在 annotator 迴圈裡掛點、一個 migration（RLS 與 grant）、一份 digest、改週報，另加一道 migration 人類關卡。
- **效益（low）**：觸發點是標題 regex gate，**#726 自己的案例根本不會觸發**（B1）。計畫裡兩個核心前提和程式碼不符：「Pass 2 接過的新聞列不經 annotator」（B2），以及「用 `has_future_date` 分流」（B3）。

結論：🔴 先不交給 Engineer。建議改成本文最後那種「週審時唯讀查詢」的做法，不需要 migration，也不必在 annotator 掛點。

## 阻斷（必須修）

**B1. 觸發條件 1 漏掉 #726 自己的案例，也漏掉 36 筆人工確認的報導**
- 位置：計畫 L1 的觸發條件 1；`scraper/annotator.py:2537-2560`（`_event_report_gate_update` 只呼叫 `is_event_report(raw_title, forms)`）。
- 問題：
  - 實際跑了 `is_event_report("AA研の歴史的資料「浅井・小川台湾原住民資料」を国家図書館（台湾）へ寄贈：記念式典とシンポジウムを開催 | 研究 | TOPICS - tufs.ac.jp")`，結果是 **False**。
  - 這筆 `facb933a` 在 `dryrun-2026-11-22.md` 列在「待覆核」，是由 `_oneoff_retire_event_reports.py --deactivate-ids-file` 停用的（`review-confirmed-2026-11-22.txt` 第 17 行），根本不經 annotator gate。
  - dry-run 裡 regex 命中的 20 筆，屬於新聞型來源的只有 7 筆：prtimes 3 筆（其中「にゃんこ大戦争」在台灣舉辦，不在範圍內）；google_news_rss 4 筆，全部是 Cinem@rt 的 TCC 上映會報導，原始活動 TTR 已經由 TCC／cinemart 收錄。
  - 這 7 筆是整個資料庫累積至今的數量，所以穩定狀態下，annotator 掛點每月產出的有用線索大概接近 0（推測）。
- 修正：不要用「gate 在這次標註中觸發」當入口。改成在讀取時篩選 `deactivated_reason = EVENT_REPORT_REASON`。annotator gate 和一次性腳本（`_oneoff_retire_event_reports.py:107,124`）都寫入它，這樣才涵蓋得到 #726 這類標題看不出來是報導的列。

**B2. 「Pass 2 接過的新聞列不經 annotator」這個說法是錯的**
- 位置：計畫「與 merger Pass 2 的關係」一節、L1 的條件 3。
- 程式碼事實：`main.py:518-525` 先跑 `run_merger()` 再跑 `annotate_pending_events()`；merger 的 `_deactivate_payload`（`merger.py:180-193`）只寫 `is_active`、`deactivated_at`、`deactivated_reason`、`deactivated_by_pass`，不動 `annotation_status`；annotator 預設查詢是 `annotation_status = pending`，不管 `is_active`（`annotator.py:3088-3095`）；Pass 2 只把 URL 寫進 **primary** 的 `secondary_source_urls`（`merger.py:1206`），新聞列自己的這欄仍是空的。
- 後果：標註前就被 Pass 2 接走的新聞列，五個條件全部成立，會產生線索；它的原始活動其實就是 TTR 裡的 primary，`find_existing` 的完全 URL 比對通常擋不下來 → 假線索。
- 修正：加 `event.get("is_active") is not False` 與 `event.get("merged_into_event_id") is None`（migration 049）。
- 附帶發現（屬於 PR #717）：report gate 和 relevance gate 都不檢查 `is_active`，會把 merger 寫的 `deactivated_reason`（"news article merged into …"）覆寫成 `EVENT_REPORT_REASON`。`merged_into_event_id` 和 `deactivated_by_pass` 會保留。建議在 #717 的 gate 開頭加 `if event.get("is_active") is False: return None`。

**B3. `has_future_date` 分流不可靠，還會把列表頁推進 url-intake**
- 位置：L1 步驟 3、L3 的「可能還能參加」。
- 問題：事後報導的原始活動幾乎都已結束；打分規則讓 `/events/` 列表頁或導覽連結很容易 ≥ 1 分，列表頁幾乎一定有未來日期（加上 © 年份、側欄），「可能還能參加」會被列表頁佔滿；使用者若核准，`ingest_url.build_event` 會把整個列表頁寫成一筆活動。抓候選頁也是 SSRF 第二跳（S2）。
- 修正：拿掉候選頁抓取與 `has_future_date`。分流改看報導列自己的 `end_date`/`start_date`：不早於今天才附 url-intake 連結，其餘歸「來源缺口」；能否收錄交給 url-intake 預覽（`ingest_url.py:393-431`）。

## 建議（應該修）

**S1. annotator 迴圈裡的網路請求沒有總時間上限**：`fetch_html` 的 `timeout=20` 是每次連線／讀取，最多 5 次轉址，`iter_content` 無總期限；`scraper.yml` scrape job 未設 `timeout-minutes`（預設 360 分）；同一段 annotator 也跑在 `annotate-now.yml`、`enrich-and-annotate.yml`、`refetch-thin-events.yml`。若保留掛點：每輪總預算（例 60 秒），`IntakeError`／`LookupFailed` 逐候選捕捉。

**S2. 帶憑證的程序去抓任意 URL**：url-intake 刻意把無 secrets 的 fetch job 和帶憑證的 db job 分開（`url-intake.yml` 11-15 行）；annotator 程序環境有 `SUPABASE_SERVICE_ROLE_KEY` 與 OpenAI key（`scraper.yml:45-57`）。第一跳（抓報導）有前例（`annotator.py:563` 用 Playwright 抓 gnews 文章）；第二跳的網址由報導作者決定，是新增風險。`assert_public_host` 與 requests 連線各解析一次 DNS，存在 rebinding 時間差（推測：GitHub-hosted runner 上可利用程度低）。照 B3 拿掉第二跳即消失。

**S3. prompt injection**：digest 會被 weekly-review 的 agent 讀、可能提交進 repo；`candidate_url` 可長達 2000 字、報導標題外部可控。修正：標題經 `ingest_url.escape_md`；URL 只顯示 host 加截短 path（≤120 字）；比照 `render_preview` 用 `scan_for_injection` 加註；段首標明「以下是外部資料」。

**S4. 預填 issue 連結**：已確認 issue #718 建立時帶 label，事件紀錄 `labeled url-intake`，url-intake 跑了 2 次 success、1 次 cancelled，所以「建立時帶 label」會觸發 `issues: labeled`。瀏覽器 `?labels=` 需 triage 權限，擁有者有，這條路徑沒單獨測過（推測行為相同）→ PR 驗證時手點一次。多個 label 會跑多次 → 只預填 `url-intake`。`extract_url` 只取正文第一個 URL（`ingest_url.py:107-114`）→ body 第一行必須是候選網址，補測試鎖順序。

**S5. 重複與過時線索**：digest 依 `candidate_url` 合併；產生時再跑 `find_existing`；`normalize_url` 不去 `www.` 與結尾 `/`，用 `same_host_count` 或 `find_similar` 補強。

**S6. 若保留 migration 111**：照 108 寫法（`begin`、`set local lock_timeout`、`comment on table`、sequence grant、尾端 DO block）；advisor 會報 INFO `rls_enabled_no_policy`（預期）；`database.instructions.md` 第 11 行要補 110、111；目前沒有別的分支佔用 111。

**S7. 文件位置**：沒有 `weekly-review` skill；實際是 `.github/prompts/weekly-review.prompt.md`（wrapper `.claude/commands/weekly-review.md`）；自動週報是 `weekly-docs-report.yml` → `docs_report.py`。要寫明接哪一個。

**S8. dry-run**：annotator 參數叫 `dry_run`（`annotator.py:2970`），CLI `--dry-run`（5897 行）；`main.py --dry-run` 在標註前就返回（`main.py:504-515`）。與其 dry-run 完全不呼叫，不如抽取並記錄候選、不寫入，才拿得到第一份證據。

## 可忽略的小事

- 新聞型來源實際只有 prtimes 與 google_news_rss 有作用：note_creators 爬取階段就丟掉報導（`note_creators.py:499`）；tiff_jp 訪談不會命中 regex；nhk_rss、walkerplus dry-run 0 筆。
- google_news_rss 的 `source_url` 多半已由 googlenewsdecoder 解出原文（`google_news_rss.py:301-311`），略過 news.google.com 只是退路。
- `MAX_REPORTS_PER_RUN = 10` 依 B1 命中率實際碰不到。
- PR tier：動到 `scraper/` 非 sources 檔案即 Tier 2（`scripts/ci/pr_tier.py:75-92`），改做法也一樣。

## 更簡單的做法

週審時唯讀執行 `scraper/report_leads.py --days 7`，不需 migration、不改 annotator：
1. 查詢：`deactivated_reason = EVENT_REPORT_REASON`、`source_name` 屬新聞型、`merged_into_event_id is null`、`annotated_at >= now() - 7d`（gate 在同一次 update 寫 `annotated_at`）。第一次用 `--all` 掃一次性腳本停用的 56 筆，#726 的 `facb933a` 在其中。
2. 「來源缺口」區：列報導本身的 host（排除新聞平台）；#726 是 `tufs.ac.jp`，不必抓頁面。用 `ingest_url.same_host_count` 標出 TTR 是否已收錄該網域，同網域 ≥ 2 次建議交 Researcher。
3. 「候選連結」區：每篇報導只抓一次 `source_url`，抽最多 3 個候選，跑 `find_existing`；只有報導列 `end_date` 不早於今天才附 url-intake 預填連結（S4 格式）。
4. 輸出經 `escape_md` 與 injection scan，貼進 `weekly-review.prompt.md` 的一段。

效果：檔案數降到「腳本＋測試＋prompt 一段」；拿掉 B2、B3、S1、S2、S6 的風險；第一週就能用既有資料驗證 #726 正例。驗證幾週後若有穩定產出，再考慮即時掛點與建表。

## 建議的下一步

- 依本批評修訂 `report-leads.md`。建議模型：Opus。
- B2 附帶發現（gate 覆寫 merger 的 `deactivated_reason`）在 PR #717 或另開 issue 處理，貼 `spec:no-event-reports`。
