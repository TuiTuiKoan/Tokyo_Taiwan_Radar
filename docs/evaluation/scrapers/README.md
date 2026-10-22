# Scraper 品質週報

`scraper/eval_scraper_quality.py` 每週日 09:00 JST 由 `.github/workflows/scraper-quality.yml` 產生（#354）。報表放在 workflow 的 summary 與 artifact（`scraper/reports/` 不進 git）；第一份基準與重大變動才另存到本目錄。

## 五個區塊

| 區塊 | 資料 | 判讀 |
|---|---|---|
| 產出健康 | `scraper_runs` 最近 7／28／120 天 | 依 `scraper/source_expectations.json` 分辨「預期中的 0」與「原因未知的 0」 |
| 欄位完整度 | 最近 90 天建立的有效母事件 | `quality_fields.TRACKED_FIELDS` 的填寫比例；純出版紀錄不計政策上留空的欄位 |
| 修正率 | 最近 90 天的 `field_corrections` | 人工（`corrected_by` 有值，即後台編輯）與腳本寫入分開。只有 `report_id` 的列來自 qa_auto_fix 處理 auto-QA 回報，算腳本。腳本寫入不代表錯誤（#373） |
| DOM drift | `scraper_runs.notes` 的 `parsed_fields_median` | 最近 3 次都比先前中位數低 30% 以上才告警；需要至少 6 次紀錄 |
| Annotator 補填 | 入庫事件的追蹤欄位中位數 − scraper 當下的中位數 | 越大代表 scraper 抽得越少 |

`parsed_fields_median` 與 `event_sources` 由 `main.py` 在每次 scraper 執行後寫入 `scraper_runs.notes`（#354 起）。`event_sources` 用來對應 run key 與 events 的 `source_name`，兩者不一定相同（例：`tokyo_art_beat` → `tokyoartbeat`）。

## 狀態

| 狀態 | 條件 |
|---|---|
| 🟢 有產出 | 最近 7 天有任何一次產出 > 0 |
| 🟡 本週 0，28 天內有 | 沒有預期設定，28 天內有產出 |
| 🔵 季節外 | `seasonal`，本月不在 `active_months` |
| 🔵 零星來源，仍在預期內 | `sporadic`，距上次產出未超過 `max_quiet_days` |
| 🟠 零星來源，安靜過久 | `sporadic`，超過 `max_quiet_days` |
| 🔴 已知故障 | `broken`，附 issue 編號；issue 結案時從設定移除 |
| 🔴 最近一次執行失敗 | 最後一列 `success = false` |
| 🔴 28 天以上 0，原因未知 | 以上皆非 |

「需要處理」列出原因未知的 0、安靜過久、執行失敗、DOM drift 告警，以及完整度最低的 3 個來源（90 天內至少 10 筆事件）。已知故障由各自的 issue 追蹤，不重複列出。

## 維護 `source_expectations.json`

- 新的 0 產出來源先 dry-run 判斷：列表抓得到但沒有台灣項目 → `sporadic` 或 `seasonal`；解析失敗或被擋 → 開 issue 並設為 `broken`。
- 2026-10-22 的初始設定來自 #327 的盤點，結論見 `2026-10-22-zero-output-triage.md`。
