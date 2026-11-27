---
slug: no-event-reports
title: 不再收錄活動報導：收錄閘門、移除 report 分類、下架既有報導
status: active
branch: feat/no-event-reports
created: 2026-11-22
tags: [scope, scraper, annotator, web, data]
---

## What（做什麼）

使用者 2026-11-22 裁決：TTR 往後**不收錄任何活動報導**；**過去已收錄的也下架**，並**刪除相關標籤**（`report` 分類，zh 標籤「活動紀錄」，名稱前綴【レポート】／【活動報導】／[Report]）。

三件事，一個 PR：

1. **收錄閘門（往後）**：scraper 遇到明確的報導頁面就不產出；annotator 對其餘來源判定為活動報導時自動停用（`is_active=false`）。
2. **移除 `report` 分類**：types、i18n、annotator、classifier、taxonomy、各來源的 seed 分類、LINE 廣播、月報、前端 motif 與 noindex 邏輯、文件與 skill 規則全部拿掉。
3. **既有資料下架**：一次性腳本 `scraper/_oneoff_retire_event_reports.py`，預設 dry-run；`--apply` 由使用者執行（production 寫入是人類關卡）。

## 定義：什麼是「活動報導」

**是**：內容主體是在報告一場**已經結束**的活動，讀者無法再參加。例：`トークイベント レポート`、`開催報告`、`活動記録｜…鑑賞会`、`〜が閉幕`、`現地レポート`、`行ってきた`、比賽 `結果発表`。

**不是**（保留活動、只拿掉 `report` 標籤）：

- 即將舉辦的 `報告会`、`成果報告会`、研究會的 `報告`（講者發表）——這是可參加的活動。
- 純出版紀錄（`event_form == ['publication']`）：`調査研究報告書`、`視察報告` 等論文或書，屬於出版，不是活動報導。
- 電視節目（gguide_tv 的 `報道`／`教養` 類型）：是即將播出的節目。
- 介紹即將舉辦活動的新聞稿（例：`甲府北口で「超級台湾屋台祭」`）。

## Why（為什麼）

- 使用者 2026-11-22 的指示（見上）。
- 現況：`report` 標籤雜訊很大。2026-11-22 唯讀盤點，active 且帶 `report` 的頂層活動約 150 筆，其中真正的活動報導只是一部分（台灣文化中心「トークイベント レポート」11 筆、Cinem@rt 報導 4 筆、prtimes 開催報告 3 筆等）；其餘是 `ndl_opensearch` 標題含「報告」的論文、即將舉辦的 `報告会`、被 GPT 誤標的上映與展覽。直接把帶標籤的都下架會誤殺大量正常活動，所以下架用「活動報導判定」，標籤則全部移除。

## Non-Goals（不做什麼）

- 不退役 `google_news_rss`、`nhk_rss`、`tiff_jp` 等新聞型來源；逐筆由閘門判定。整個來源是否保留另案決定（開 issue）。
- 不改 Supabase schema（`category` 是 `text[]`，沒有 enum 或 check constraint 參照 `report`）。
- 不刪除任何列；下架一律是 `is_active=false` 加 `deactivated_reason`，可逆。
- 不處理 Admin Reports（`report_types`、i18n 的 `report` namespace），那是 QA 回報，與活動報導無關。

## Design（設計摘要）

### D1. 共用判定 `scraper/event_report.py`

`is_event_report(title, event_form=None, description=None) -> bool`，純函式、可測：

- 強訊號 regex（標題）：`レポート`、`イベントレポ`、`開催報告`、`実施報告`、`活動報告`、`活動記録`、`開催記録`、`鑑賞記録`、`閉幕`、`行ってきた|観てきた|見てきた`、`結果発表`、`recap`、`活動紀錄`、`活動報導`、`開催レポ`。
- 排除：`報告会`（即將舉辦）、`報告書`、純出版、`event_form` 只有 `broadcast`。
- `EVENT_REPORT_REASON = "auto-deactivated: event report (post-event recap)"`。

### D2. 收錄閘門（往後）

- **Scraper 層**（確定性、零成本）：`taiwan_cultural_center` 標題命中時不產出（原本是加 `report`）；`taioan_dokyokai` 移除 `/category/活動記録/` 路徑；`google_news_rss`、`nhk_rss`、`gguide_tv` 不再 seed `report`。
- **Annotator 層**：在既有 relevance gate 後加 report gate，只用確定性的 `is_event_report(raw_title, event_form)`，`event_form` 取 annotator 剛產出的值。命中就寫 `is_active=false`、`deactivated_reason=EVENT_REPORT_REASON`，不產生 sub_events。沿用 relevance gate 的保護：人工鎖定（field_corrections）、`user_submission`、`url_intake`、純出版不動；另豁免 `gguide_tv`、`ndl_opensearch`、`hanmoto`、`kawade_rss`（首次標註時 `event_form` 常為空）。
- GPT prompt：拿掉 `report` 分類定義；sub_events 的報導例外改寫成新政策。**不加** GPT 判定欄位（見 plan-critique-1 B1／S1）。

### D3. 移除 `report` 分類

`web/lib/types.ts`（`Category`、`CATEGORIES`、`group_archive` 群組、`isPureReportEvent`）、`web/app/sitemap.ts` 與活動頁 noindex、`web/messages/{ja,zh,en}.json`（`categories.report`、`group_archive`、分類說明）、`web/lib/design/organicMotifs.tsx`、`web/app/api/line-webhook/route.ts`；`scraper/annotator.py`（`VALID_CATEGORIES`、keyword 注入、前綴注入、`backfill_report_prefix`）、`classifier.py`、`taxonomy.md`、`peatix.py`、`note_creators.py`、`weekly_line_broadcast.py`、`report_generator.py`、`database.py` 父活動查詢；文件：`copilot-instructions.md`、`scraper.instructions.md`、`tester.agent.md`、相關 SKILL.md、`add-category.prompt.md`。

### D4. 既有資料下架 `scraper/_oneoff_retire_event_reports.py`

- 選取所有 `category` 含 `report` 的列（active 與 inactive）。
- 每一列：從 `category` 移除 `report`；名稱去掉【レポート】／【活動報導】／[Report] 前綴；field_corrections 裡 `category` 與名稱鎖定值同步改寫，否則人工鎖會把舊值寫回。
- active、非純出版、`is_event_report()` 命中 → 停用。
- 其餘 active 的新聞型來源（google_news_rss、nhk_rss、tiff_jp、prtimes、note_creators）列入「待覆核」清單，只拿掉標籤；使用者可用 `--deactivate-ids` 追加停用。
- 輸出 markdown 清單（停用／只拿標籤／待覆核三組，附 `https://tokyotaiwanradar.com/ja/events/<id>` 連結）。預設 dry-run；`--apply` 才寫入。

## 決定紀錄（agent 採建議值）

- slug `no-event-reports`；一個 PR 做完三件事，因為移除分類與下架必須同時上線，否則 annotator 會把標籤加回來。
- 判定只用確定性標題規則（plan-critique-1 S1）：盤點到的真實報導都能由標題判定；GPT 軌會因 merger Pass 2 把回顧新聞接到正式活動而誤殺真活動（B1）。標題看不出的新聞型條目（主要是 `tiff_jp` 訪談）列入 dry-run 的「待覆核」，由使用者決定，另開 issue 追蹤語意判定。
- 標題規則加整句否決（`報告会`、`募集`、`のお知らせ` 等）；`結果発表` 只認開頭的 `【結果発表】`（B3）。
- 防止標籤回流：`category_feedback.build_feedback_prompt` 過濾退役分類；一次性腳本同步改寫 `field_corrections` 與 `category_corrections`；annotator 在 FC restore 後再剝一次 `report`（B4）。
- 刪除沒有呼叫者的 `database.find_parent_event_id` 與 `backfill_report_prefix`（S2）；`/[locale]/categories/report` 301 導回首頁。
- golden fixtures 的期望分類同步拿掉 `report`，重算 `frozen_corrections` sha256；這是使用者「刪除標籤」裁決的直接結果，不是新的人工判斷。
- 新聞型來源不整個退役：其中有介紹即將舉辦活動的新聞，整源退役會漏掉活動。
- 模型：規劃與評審 Opus；實作 Sonnet 等級即可。

## Dry-run 預覽

2026-11-22 以唯讀 SQL 快照跑規劃函式：255 列帶 `report`（active 140）；停用 20、待覆核 36、拿掉後分類變空 2、只拿標籤 82。清單見 `dryrun-2026-11-22.md`。正式執行前請以腳本重跑 dry-run，以當下資料為準。

## 人類關卡

- 合併 PR（Tier 2：動到 annotator、web、多個來源）。
- 執行 `_oneoff_retire_event_reports.py --apply`（production 寫入）；先看 dry-run 清單，特別是「待覆核」組。
