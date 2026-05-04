---
title: Source Exclusions — 每日封鎖規則查法
description: Supabase Dashboard SQL Editor 查詢集，用於監控 source_exclusions 封鎖規則的命中狀況、發現過廣規則，以及新增/停用規則。
ms.date: 2026-05-04
---

## 背景

`source_exclusions` 機制在 scraper 的 `upsert_events()` 執行前，依 admin 定義的
模式（substring 或 regex）過濾掉無關活動，讓這些事件**連進 DB 都不進**，
節省 GPT annotator token 也防止使用者再次回報相同類型的無關內容。

每次命中都記錄在 `source_exclusion_hits` 表（保留 30 天），供以下查詢使用。

---

## 每日查詢（Daily Monitoring）

### 查詢 1：今日封鎖了什麼？

每天執行一次，確認沒有誤殺。

```sql
SELECT
  r.source_name,
  r.pattern,
  r.pattern_type,
  count(*)                                                AS hits_today,
  array_agg(h.raw_title ORDER BY h.matched_at DESC)[1:3] AS sample_titles
FROM source_exclusion_hits h
JOIN source_exclusions r ON r.id = h.rule_id
WHERE h.matched_at > now() - interval '1 day'
GROUP BY r.id, r.source_name, r.pattern, r.pattern_type
ORDER BY hits_today DESC;
```

**看什麼**：哪條規則今天封了幾個、封的是什麼標題（前 3 筆樣本）。
若 `sample_titles` 出現台灣相關活動標題 → 規則過廣，立即停用（見查詢 4）。

---

### 查詢 2：最近 7 天哪條規則最活躍？

每週一次，找出過廣或已失效的規則。

```sql
SELECT
  r.source_name,
  r.pattern,
  r.match_count            AS lifetime_hits,
  count(h.id)              AS hits_7d,
  min(h.raw_title)         AS sample_title,
  max(h.matched_at)        AS last_hit,
  r.is_active
FROM source_exclusions r
LEFT JOIN source_exclusion_hits h
  ON h.rule_id = r.id
  AND h.matched_at > now() - interval '7 days'
GROUP BY r.id
ORDER BY hits_7d DESC NULLS LAST;
```

**判讀標準**：

| `hits_7d` | 判斷 |
|-----------|------|
| 0 | 死規則 — 可能來源已停更，考慮停用 |
| 1–5 | 正常範圍 |
| > 20 | 可能過廣，看 `sample_title` 確認 |

---

### 查詢 3：某條規則具體封了哪些活動？

懷疑某條規則誤殺時使用，將 `pattern` 換成要查的關鍵字。

```sql
SELECT
  h.raw_title,
  h.source_name,
  h.matched_at
FROM source_exclusion_hits h
JOIN source_exclusions r ON r.id = h.rule_id
WHERE r.pattern = 'スピリチュアル'   -- 換成你要查的 pattern
  AND r.source_name = 'peatix'       -- 可省略以查全來源
ORDER BY h.matched_at DESC
LIMIT 30;
```

---

## 規則管理

### 查詢 4：停用一條過廣規則

```sql
UPDATE source_exclusions
SET is_active = false
WHERE pattern = 'スピリチュアル'
  AND source_name = 'peatix';
```

停用後**下次 scrape 立即生效**（`load_exclusions()` 只取 `is_active=true`）。

---

### 查詢 5：新增一條規則

```sql
INSERT INTO source_exclusions (source_name, pattern, reason)
VALUES (
  'peatix',
  'スピリチュアル',
  '心靈成長類——與台灣文化無關，持續出現'
);
```

**欄位說明**：

| 欄位 | 必填 | 預設 | 說明 |
|------|------|------|------|
| `source_name` | ✅ | — | 限定來源，不允許 NULL 全域規則 |
| `pattern` | ✅ | — | 子字串或 regex |
| `reason` | 建議填 | NULL | 說明封鎖理由，方便日後審查 |
| `pattern_type` | — | `substring` | `substring`（不分大小寫）或 `regex` |
| `match_field` | — | `raw_title` | `raw_title` / `raw_description` / `raw_title_or_description` |
| `is_active` | — | `true` | 建立後立即生效 |

---

### 查詢 6：列出所有現行規則

```sql
SELECT
  source_name,
  pattern,
  pattern_type,
  match_field,
  match_count,
  last_matched_at,
  is_active,
  reason
FROM source_exclusions
ORDER BY source_name, pattern;
```

---

## LINE 通知對照

`backlog_health.py` 每日執行後，`notify.py` 的 LINE 訊息在 Backlog Health 段落會顯示：

```
🚫 今日封鎖：3 件（2 條規則）
```

若收到此行，可用**查詢 1** 確認封鎖內容是否正確。

---

## 相關程式碼

| 檔案 | 說明 |
|------|------|
| `scraper/source_exclusions.py` | `load_exclusions()` / `event_matches_exclusion()` / `record_hits()` |
| `scraper/database.py` | `upsert_events()` 前置過濾區塊 |
| `scraper/backlog_health.py` | `exclusion_hits_today` 計算 + 30d 清除 |
| `supabase/migrations/041_source_exclusions.sql` | 建表 migration |
