---
slug: organizer-source-subevents
title: 主辦方連結優先＋場次子事件
status: active
branch: feat/organizer-source-subevents
created: 2026-11-22
tags: [scraper, annotator]
---

> v2（2026-11-22）：依 `plan-critique-1.md` 修訂（評審與撰寫同一模型家族，本環境無 Codex）。處理結果見本檔末表。

## What（做什麼）

1. **主辦方連結優先**：轉述型來源（第一版只做 `tiff_jp` 新聞）的文章正文裡若有指向外部主辦方的連結，HTML 頁就抓正文放在 `raw_description` 最前面並寫入 `official_url`；只有 PDF 傳單時，記一行 `チラシ:` 並以該 PDF 當 `official_url`。
2. **場次子事件**：排程表裡每一個「日期＋時間＋作品」時段、每一場研討會，各成一個子事件。
3. **順帶修掉造成錯誤的兩條規則**：選單文字注入 `report`、括號附註的「会場：」被當成主會場。

## Why（為什麼）

2026-11-22 使用者回報 [407a033b](https://tokyotaiwanradar.com/ja/events/407a033b-0b1d-49ec-be56-6ad1ddcb1b10)（台湾語映画誕生70周年特集，主辦頁 https://athenee.net/culturalcenter/program/ta/taiwanese_language_cinema.html）。

| 症狀 | 根因（已對照程式碼與 DB 原文） |
| --- | --- |
| `start_date` = 11/15（新聞發布日），實際 12/2〜12/9 | `TiffJpScraper._extract_cards` 以列表卡片的發布日當 `start_date`；annotator 以 scraper 日期為優先 |
| 類別多了 `report` | `_inject_keyword_categories` 用 `_REPORT_TRIGGER_RE` 掃整段 `raw_description`；網站選單「イベントレポート」與側欄「新着ニュース」的 `[イベントレポート]` 一定觸發。tiff_jp 63 筆中 43 筆帶 report，41 筆標題沒有 report 字樣 |
| 地點寫成「地下1階カフェテリア」 | `_VENUE_LABEL_RE` 抓到 `交流会（会場：…カフェテリア）` 的括號附註，且 `_pre_location_name` 優先於模型 |
| 原文有 10 場放映＋1 場研討會，子事件 0 筆 | 無法重現（DB 沒有存模型回應）。原文 2000 字內排程完整，`max_tokens` 截斷會變成 JSON 錯誤而非 0 筆，故排除。較可能是模型套用了「單片多時段不拆」的 EXCEPTION，加上前後選單雜訊 |
| `official_url` 空 | tiff_jp 新聞沒有找外部連結的邏輯 |

資料已於 2026-11-22 手動修正（使用者核准）：父事件改日期、地點、`official_url`，補 11 個子事件，並設 `annotation_status='reviewed'` 防止 movie-extend 把日期改回發布日。

## 設計

### A. `tiff_jp` 新聞爬蟲（`scraper/sources/tiff.py` 的 `build_news_fields()`）

1. **只留正文**：從第一個 `YYYY.MM.DD [分類]` 行開始，到 `前の記事`／`次の記事`／`ニュース一覧へもどる`／`新着ニュース` 之前結束；上限 6000 字（原本 2000，預防更長的文章）。找不到標記時保留原文。
2. **活動日期**：從正文的 `M月D日` 與 `M/D(曜)` 收集日期，年份以發布日推定（發布日前 180 天內視為過去提及並忽略，更早的推成隔年），只保留發布日前 7 天到後 365 天；`start`=最小、`end`=最大，`raw_description` 前加 `開催日時:` 行。文章分類是 `[イベントレポート]`／`[インタビュー]` 時不抽日期（那些日期是拍攝或已放映日）。找不到時沿用發布日並記 warning。
3. **主辦方連結**：只看錨點文字出現在正文裡的 `<a>`（排除選單、AD、側欄），交給 `pick_organizer_link()`：排除自身網域、SNS、地圖、售票平台、圖片。HTML 頁用同一個 Playwright context 抓正文（上限 6000 字），文字必須含台灣關鍵字才採用，放在 TIFF 正文前面並寫入 `official_url`；只有 PDF 時不下載，記 `チラシ: url`，`official_url` 填 PDF。正文內所有外部連結寫進 log，當作 CI dry-run 證據。

純函式放在 `scraper/sources/_organizer_link.py`（見評審處理表 S3）。

### B. annotator（`scraper/annotator.py`）

1. **prompt**：只在既有「單片多時段不拆」EXCEPTION 後補一句：排程裡有兩部以上不同作品時不適用此例外。
2. **覆蓋率守門** `_should_retry_sub_events()`：來源白名單 `{"tiff_jp"}`；排除純出版、本身是子事件、被停用、標題含報導字樣；`count_schedule_slots()` 數到 ≥3 個時段且 ≥3 個不同作品名（支援全形空白）、模型回 0 個子事件時，再請求一次。提示（`_sub_event_retry_hint()`）寫明時段數、`＋` 合映、研討會帶講者、交流會併入研討會，只加在這次重試；`max_tokens` 8000（11 個三語子事件約需 4–5k token）。**只採用重試回來的 `sub_events`**，其他欄位沿用第一次；token 用量累加；重試失敗或仍為 0 只記 warning。
3. **`_VENUE_LABEL_RE`**：前一個字是 `（`／`(` 時不匹配（全來源適用，全套測試通過）。

### 對既有資料的影響（預期行為）

`upsert_events` 的 movie-extend 路徑會讓既有、未 reviewed、類別含 movie 的 tiff_jp 列在下次排程時被更新 `raw_description` 並轉回 `pending` 重新標註。2026-11-22 查詢有 7 筆（評審時是 19 筆，範圍隨時間變動），多數是 `[イベントレポート]`／`[インタビュー]`：

- 日期：這兩類不抽日期，`start_date` 維持；公告類若抽到活動日，會改成活動日（修正舊錯誤）。
- 類別：新正文不再含選單文字，報導類仍由自己的 `[イベントレポート]` 分類行觸發 `report`，公告類不再誤標。
- 子事件重試：報導標題通常含報導字樣，且多數沒有排程表，預期不觸發。

這取代 v1 Non-Goals 的「回填另行核准」：這是既有 movie-extend 行為，不需要另寫回填工具；dry-run 證據會比對前後差異。

## Non-Goals（不做什麼）

- 其他轉述型來源（peatix、eplus、Google News…）：兩週後依 log 與資料決定是否擴大。
- PDF 文字抽取。
- scraper 端直接產生子事件（ks_cinema 有 first-run race 問題，不擴散）。
- 其他來源的 `report` 誤標（google_news_rss、prtimes）：另開 issue。

## 驗收

- 以 fixture（407a033b 原文）：`start_date`=2026-12-02、`end_date`=2026-12-09；正文不含選單與側欄；`report` 不被注入；括號附註不被當地點；時段計數 11。
- 下一篇同類 TIFF 公告：子事件數＝時段數（研討會含交流會算 1）。CI dry-run 留言要能看到 `external links in article` 那行。

## 建議模型

- 規劃／評審：Opus high。實作與測試：Sonnet medium。

## 評審處理表（plan-critique-1）

| # | 處理 |
| --- | --- |
| M1 | 採納。根因表改寫；`_VENUE_LABEL_RE` 用 (b) 排除括號內標籤（只加 lookbehind，未改成行首限定，影響面較小）；report 由 A.1 正文切割解決 |
| M2 | 採納。刪除 max_tokens 根因；8000 的理由改為預留空間 |
| M3 | 採納。加尾端切割。DOM 正文容器因無法連到 tiff-jp.net 確認 selector，改用文字標記，找不到就保留原文 |
| M4 | 採納。改為「錨點文字出現在正文裡的連結」，並加 AD／側欄反例測試 |
| M5 | 採 (b)：留在本 PR，因使用者明確要求「以後改用主辦方資訊」。驗收寫明 407a033b 型預期只產生 チラシ 行；只有 PDF 時 `official_url` 填 PDF；外部連結寫 log 當證據 |
| M6 | 採納。改寫為預期行為並列出影響；另加「報導／訪談不抽日期」避免把拍攝日當活動日 |
| M7 | 採納。白名單、沿用既有過濾、只合併 sub_events、token 累加、全形空白 |
| S1 | 採納。SYSTEM_PROMPT 只加一句，細節放重試提示 |
| S2 | 採納跨年與窗口外測試；naive datetime 與既有 tiff 程式一致（存成 UTC midnight）；`記事配信日` 錨點由 annotator 加在最前面，與 `開催日時:` 不衝突，未另寫順序測試 |
| S3 | 不採納。使用者要求的是通用規則（「未來這種」），純函式模組很小、已有 14 個測試；第二個來源接上時不必再搬 |
| S4 | 採納，寫進驗收與測試 |
| S5 | 採納。統一寫「11 個子事件」 |
| R2 | 部分：重試資格與 `_annotate_one` 的 `max_tokens` 有單元測試；整段 annotate 流程的重試接線沒有 fake Supabase 測試，列為 NOT TESTED |
| R6（測試 6） | 不另寫：movie-extend 是既有行為且已有測試，本 PR 未修改 |
