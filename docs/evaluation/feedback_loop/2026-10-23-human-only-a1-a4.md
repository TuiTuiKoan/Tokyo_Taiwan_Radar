# A1／A4 只計人工修正：前後差異（2026-10-23，#373）

`monthly_health_check.py` 的 A1 重犯率與 A4 修復延遲，原本把所有 `field_corrections` 都當成修正。改動後只計 `corrected_by` 有值的列（後台人工編輯），腳本寫入只另列總數。判斷方式與 `eval_scraper_quality.is_human_correction()` 相同：只有 `report_id` 的列來自 qa_auto_fix 處理 auto-QA 回報，不算人工。

數字來自 2026-10-23 的唯讀 SQL。

## 2026-09 月窗口（`docs_report.py` 月報）

| 指標 | 改動前 | 改動後 |
|---|---|---|
| field_corrections 列數 | 698 | 人工 0、腳本 698 |
| A1 重犯組合（≥ 2 次） | 58 對，前幾名是 kokuchpro／location_name 77 次、ndl_opensearch 七個出版政策欄位各 40 次、gguide_tv／location_name 31 次 | 0 對 |
| A4 修復延遲 | 以腳本批次鎖定的時間差排名（kokuchpro 中位數 138 天） | 無人工修正，表格為空 |

2026-09 沒有任何後台人工修正，所以 A1、A4 為空是正確結果。

## 排程窗口（`run()`：A1 90 天、A4 180 天，截至 2026-10-23）

| 指標 | 改動前 | 改動後 |
|---|---|---|
| A1 90 天 | 196 對（4532 列） | 3 對（人工 10 列；腳本 4522 列另列） |
| A4 180 天 | 99 個來源（11803 列） | 11 個來源（人工 58 列） |

A4 改動後的前幾名（人工修正，中位數天）：iwafu 19.2、asahiculture 16.7、google_news_rss 8.4、matsumoto_cinema_select 5.5、note_creators 3.0。

## 附帶修正

舊查詢一次取回整個窗口、沒有分頁。90 天有 4532 列，超過 Supabase PostgREST 預設的 1000 列上限，所以舊數字可能只算到前 1000 列。現在改成在伺服器端篩選人工列（目前 10～58 列），腳本列只用 `count=exact` 計數，不受這個上限影響。
