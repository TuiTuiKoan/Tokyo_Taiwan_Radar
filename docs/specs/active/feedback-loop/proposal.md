---
slug: feedback-loop
title: 使用者報錯 → AI 學習閉環（Feedback Loop）
status: active
branch: main
created: 2026-04-15
tags: [scraper, ai, admin, infra]
---

## What（做什麼）

建立「使用者報錯 → admin 確認 → corrections 表 → AI few-shot 注入 → AI 不再犯」的完整學習閉環。

覆蓋三種報錯類型：
- **wrongCategory** → `category_corrections` → `category_feedback.py` few-shot
- **wrongDetails** → `field_corrections` → `annotator.py` human_field_map
- **wrongSelectionReason** → `selection_reason_corrections` → `selection_reason_feedback.py` few-shot
- **irrelevant** → `is_active=false` 或 `source_exclusions` 規則

## Why（為什麼）

- AI annotator 每天標記數百個事件，若沒有學習閉環，同類錯誤會重複出現
- 任何一處斷鏈（表斷裂、prompt 未注入）都**不會報錯**，只能透過月度健檢發現

## Non-Goals（不做什麼）

- ❌ 不做 auto-accept corrections（人工確認永遠必要）
- ❌ 不做 corrections ML 訓練（few-shot 注入已足夠）

## Design（設計摘要）

### 閉環流程
```
前台 ReportSection（使用者）
  → event_reports（status: pending）
  → /admin/reports confirm（admin）
  → corrections 表 upsert（3 張表）
  → annotator.py 啟動時 load_corrections()
  → GPT-4o-mini SYSTEM_PROMPT 注入 few-shot / human_field_map
  → AI 預測改善
```

### 5 張核心表
- `event_reports`：原始報錯佇列（含 auto_qa_* 自動報錯）
- `category_corrections`：分類修正 few-shot
- `selection_reason_corrections`：選取理由修正 few-shot
- `field_corrections`：欄位值修正（human_field_map 保護）
- `source_exclusions`：來源/規則排除

### 月度健檢
- 文件：`docs/MONTHLY_FEEDBACK_LOOP_HEALTH_CHECK.md`
- 執行時機：每月 1 號，Supabase Dashboard SQL Editor

## References

- `scraper/category_feedback.py`
- `scraper/selection_reason_feedback.py`
- `scraper/annotator.py`（load_corrections + human_field_map）
- `docs/MONTHLY_FEEDBACK_LOOP_HEALTH_CHECK.md`
