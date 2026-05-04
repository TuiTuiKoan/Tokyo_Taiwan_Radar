---
title: 報錯閉環健檢 — 每月儀式
description: 每月 1 號在 Supabase Dashboard SQL Editor 執行的儀式，驗證使用者報錯是否正確流入 corrections 表並被 AI 學到，避免閉環有洞。
ms.date: 2026-05-04
---

## 目的

整套 feedback pipeline（使用者報錯 → admin 確認 → corrections 表 → annotator
few-shot / human_field_map → AI 不再犯）涵蓋 5 張表 + 3 個 prompt 注入點。
任何一處斷鏈都不會報錯，但 AI 就學不到。每月一次健檢能確保：

1. 報錯數 ≈ corrections 數（沒有報錯被吃掉）
2. `field_protect_hits` 隨時間上升（保護機制真的有被使用）
3. 同類報錯不會月月重複出現

---

## 執行時機

每月 **1 號** 09:00 JST（手動，配合月初例行檢查）。
建議排進 Google Calendar 重複事件。

---

## 健檢步驟（按順序執行）

進入 **Supabase Dashboard → SQL Editor**，依序執行以下三組查詢，記下結果。

---

### 步驟 1：上個月有多少報錯被確認？

```sql
SELECT
  count(*) FILTER (WHERE 'irrelevant' = ANY(report_types))         AS irrelevant_n,
  count(*) FILTER (WHERE 'wrongCategory' = ANY(report_types))      AS wrong_category_n,
  count(*) FILTER (WHERE 'wrongDetails' = ANY(report_types))       AS wrong_details_n,
  count(*) FILTER (WHERE 'wrongSelectionReason' = ANY(report_types)) AS wrong_sr_n,
  count(*)                                                          AS total_confirmed
FROM event_reports
WHERE status = 'confirmed'
  AND confirmed_at >= now() - interval '30 days';
```

**判讀**：

* 記下四種報錯類型的當月數量。
* `total_confirmed = 0` 表示沒人在用回報功能 → 應檢查前台 ReportSection 是否壞掉。

---

### 步驟 2：報錯是否流入 corrections 表？（核心驗證）

```sql
SELECT 'field_corrections' AS table_name,
       count(*) AS rows_30d
  FROM field_corrections WHERE created_at >= now() - interval '30 days'
UNION ALL
SELECT 'category_corrections', count(*)
  FROM category_corrections WHERE created_at >= now() - interval '30 days'
UNION ALL
SELECT 'selection_reason_corrections', count(*)
  FROM selection_reason_corrections WHERE created_at >= now() - interval '30 days';
```

**理想對照**（與步驟 1 比對）：

| 步驟 1 計數 | 應對應到 |
|------------|---------|
| `wrong_details_n` | `field_corrections.rows_30d` ≥ 此值（單筆報錯可能對應多欄位）|
| `wrong_category_n` | `category_corrections.rows_30d` ≈ 此值 |
| `wrong_sr_n` | `selection_reason_corrections.rows_30d` ≈ 此值 |
| `irrelevant_n` | 不對應 corrections 表（直接 `is_active=false` 或建 `source_exclusions` 規則）|

**警訊**：若 `wrong_category_n > 0` 但 `category_corrections.rows_30d = 0` →
confirm-report.ts 的 corrections upsert 區塊有 bug，立即排查。

---

### 步驟 3：AI 是否真的學到了？看保護機制使用率

```sql
SELECT
  date_trunc('day', ran_at) AS day,
  sum(
    COALESCE(
      (regexp_match(notes, 'field_protect_hits=(\d+)'))[1]::int,
      0
    )
  ) AS protected_today
FROM scraper_runs
WHERE source = 'annotator'
  AND ran_at >= now() - interval '30 days'
GROUP BY 1
ORDER BY 1;
```

**判讀**：

* 30 天趨勢應**緩慢上升**或穩定 — 表示人工修正逐月累積，annotator 持續用到。
* 若**每天都是 0** → `field_corrections` 沒被讀進 `human_field_map`，annotator 啟動邏輯壞了。
* 若**突然歸零** → 可能某次 commit 把 startup load 邏輯破壞，須回看 git history。

---

### 步驟 4：source_exclusions 命中趨勢（搭配 P4.4-A）

```sql
SELECT
  date_trunc('day', matched_at) AS day,
  count(*) AS hits
FROM source_exclusion_hits
WHERE matched_at >= now() - interval '30 days'
GROUP BY 1
ORDER BY 1;
```

**判讀**：

* 規則命中數穩定 → 規則仍在抓無關內容
* 全部 0 → 規則表為空（待新增）或所有規則都被停用
* 突然爆增 → 來源端可能改版，應檢查相關 source scraper 是否抓到大量無關活動

---

## 異常處理流程

| 觀察到 | 可能原因 | 行動 |
|--------|---------|------|
| 步驟 1 總數 = 0，但前台正常 | 沒有使用者回報 | 不需處理；可考慮加引導文案 |
| 步驟 1 > 0，但步驟 2 對應表 = 0 | confirm-report.ts 流程有 bug | 立即看 `web/app/actions/confirm-report.ts` 對應區塊 |
| 步驟 3 連續 7 天 = 0 | annotator startup 載入失敗 | 看最近一次 annotator 跑的 scraper_runs.notes |
| 步驟 3 數字遞減 | corrections 被誤刪或 force_rescrape 蓋掉 | 對照 P3.2 邏輯，檢查 force_rescrape 行為 |
| 步驟 4 持續 0 但封鎖規則存在 | 規則 pattern 太特殊不命中 | 用 [SOURCE_EXCLUSIONS_QUERIES.md](SOURCE_EXCLUSIONS_QUERIES.md) 查詢 2 review |

---

## 月報模板

健檢執行後，把結果填入以下模板，存放於團隊內部文件或 GitHub issue：

```markdown
## 報錯閉環健檢 — YYYY-MM

### 步驟 1：報錯確認數
- irrelevant: __
- wrongCategory: __
- wrongDetails: __
- wrongSelectionReason: __
- 合計: __

### 步驟 2：corrections 落地數
- field_corrections: __ （對 wrongDetails ___ 筆）
- category_corrections: __ （對 wrongCategory ___ 筆）
- selection_reason_corrections: __ （對 wrongSR ___ 筆）
- 閉環是否完整：✅ / ❌（理由：___）

### 步驟 3：保護機制使用
- 30 天 field_protect_hits 趨勢：上升 / 穩定 / 下降
- 異常天數：___

### 步驟 4：source_exclusions 命中
- 30 天總命中：___
- 活躍規則數：___

### 本月行動
- [ ] 異常項目處理：___
- [ ] 新增封鎖規則：___
```

---

## 相關文件

* 每日封鎖規則查法：[SOURCE_EXCLUSIONS_QUERIES.md](SOURCE_EXCLUSIONS_QUERIES.md)
* Pipeline 全景：[SCRAPER_PIPELINE.md](SCRAPER_PIPELINE.md)
* Architecture 概覽：[ARCHITECTURE.md](ARCHITECTURE.md)
