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
- [ ] 健檢結果自動化：把 3 組查詢加入 `weekly_report.py` 或月度 CI job
  （目前：完全手動，每月 1 號 Supabase Dashboard SQL Editor）

## 閉環品質改善（待評估）

- [ ] `field_protect_hits` 指標追蹤（確認保護機制有被使用）
- [ ] 同類報錯月度重複率追蹤（確認 AI 有在學習）
- [ ] irrelevant 報錯 → 自動建 `source_exclusions` 規則（目前手動）

## Verification（月度）

- [ ] `wrong_category_n > 0` 且 `category_corrections.rows_30d ≈ wrong_category_n`
- [ ] `wrong_details_n > 0` 且 `field_corrections.rows_30d ≥ wrong_details_n`
- [ ] `field_protect_hits`（從 annotator log 看）隨時間上升
- [ ] 同類錯誤（例：某來源 category 錯誤）不在次月重複出現
