# Tasks

## 核心閉環建立

- [x] `event_reports` 表 + 前台 ReportSection（wrongCategory / wrongDetails / irrelevant / wrongSelectionReason）
- [x] `/admin/reports` confirm/dismiss UI（`AdminReportsTable`）
- [x] `category_corrections` 表 + upsert on confirm
- [x] `field_corrections` 表 + upsert on confirm（多欄位）
- [x] `selection_reason_corrections` 表 + upsert on confirm
- [x] `category_feedback.py`：load_corrections() → few-shot examples → SYSTEM_PROMPT 注入
- [x] `selection_reason_feedback.py`：load_sr_corrections() → few-shot → SYSTEM_PROMPT 注入
- [x] `annotator.py` human_field_map：field_corrections 保護已確認的欄位值不被覆寫
- [x] `source_exclusions` + `source_exclusions.py`：irrelevant 報錯建規則

## Auto-QA（自動品質檢測 → event_reports）

- [x] `auto_qa.py`：auto_qa_simplified_zh / auto_qa_missing_address / auto_qa_untranslated
- [x] auto_qa 寫入 `event_reports`（`auto_*` 前綴，去重邏輯 ALL statuses）
- [x] `/admin/quality` 頁面顯示 auto_qa 報告
- [x] `auto_qa_address_is_venue_name` 偵測器（地址 = 場地名稱的異常）

## 月度健檢

- [x] `docs/MONTHLY_FEEDBACK_LOOP_HEALTH_CHECK.md`（3 組 SQL 查詢 + 判讀指引）
- [x] 健檢結果自動化：`scraper/monthly_health_check.py` + `.github/workflows/monthly_health_check.yml`（每月 1 日 09:00 JST，commit `759f537`，2026-05-05）

## 閉環品質改善

- [x] `source_exclusions` admin UI（`/admin/exclusions`）取代 SQL Editor 操作（commit `6867344`，2026-05-05）
- [x] irrelevant 報錯 → 一鍵建 `source_exclusions` 規則（`AdminReportsTable` 內 `ExclusionSuggest` 抽 katakana ≥4 / kanji ≥3 候選詞，commit `6867344`）
- [x] `source_exclusions` TTL + 90 天 staleness 自動停用（migration 045 + `exclusions_maintenance.py`，commit `25be89c`，2026-05-05）
- [x] `daily_quality_metrics` 表 + `precision_rate` 14 天趨勢（migration 046 + `daily_quality.py` + `/admin/stats` 區塊，commit `46210d9`，2026-05-05）
- [ ] `field_protect_hits` 指標追蹤（確認 corrections 保護機制有被使用 → P1 corrections.applied_at 計畫，目前延後）
- [ ] 同類報錯月度重複率追蹤（確認 AI 有在學習）
- [x] precision_rate < 0.85 時自動發 LINE alert（`notify.py` `quality_alert` 參數 + CI 串接，commit `ebdaa5b`，2026-05-05）

## Verification（月度）

- [ ] `wrong_category_n > 0` 且 `category_corrections.rows_30d ≈ wrong_category_n`
- [ ] `wrong_details_n > 0` 且 `field_corrections.rows_30d ≥ wrong_details_n`
- [ ] `field_protect_hits`（從 annotator log 看）隨時間上升
- [ ] 同類錯誤（例：某來源 category 錯誤）不在次月重複出現
