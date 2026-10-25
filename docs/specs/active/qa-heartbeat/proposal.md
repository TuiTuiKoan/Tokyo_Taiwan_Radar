---
slug: qa-heartbeat
title: QA Heartbeat 自修復 Pipeline
status: active
branch: feat/qa-heartbeat
created: 2026-05-25
tags: [scraper, infra]
---

## What（做什麼）

把使用者回報與 `auto_qa.py` 偵測到的資料品質問題，經 R-class 分類後交給確定性的 handler 修復，並在 `field_corrections` 與 `field_corrections_audit` 留下可回溯紀錄。人工判斷的案件不自動修，只留 audit 供 rollback。

## Why（為什麼）

- 手動修正的欄位會在下一次 AI 重標注或爬蟲更新時被覆蓋；修正必須「寫入後重新上鎖」。
- 修復要可稽核、可還原，才能放心讓 CI 自動執行。

## Non-Goals（不做什麼）

- 不處理需要人類判斷的案件（範圍判斷、分類定義）。
- admin/quality 的 audit trail 檢視屬 backlog，另見 issue #109。

## Design（設計摘要）

```
auto_qa.py（偵測） → event_reports（pending）
  → qa_heartbeat.py（先 _classify_by_rule，不足才 GPT 分類）
  → _dispatch() → qa_auto_fix.HANDLER_MAP
      auto_qa_simplified_zh / auto_simplified_chinese → handle_simplified_zh
      auto_qa_performer_ai_translation_marker → handle_performer_ai_translation_marker
      auto_qa_performer_multi_value_pollution → handle_performer_multi_value_split
      auto_qa_location_url_is_event_url → handle_location_url_is_event_url
  → unlock_and_write()
      events UPDATE
      field_corrections UPSERT（重新上鎖；corrected_value TEXT NOT NULL）
      field_corrections_audit UPSERT（JSONB before/after；migration 075）
      event_reports.status = 'confirmed'
  → rollback() — 依 audit 的 before 值還原
```

關鍵檔案：`scraper/qa_heartbeat.py`、`scraper/qa_auto_fix.py`、`.github/workflows/qa-heartbeat.yml`、`.github/workflows/qa-auto-fix.yml`、`supabase/migrations/075_field_corrections_audit.sql`。Guard：`.github/skills/agents/architect/SKILL.md` § QA Heartbeat 自修復 Guard。

## References

- Issue #108、#106、#107、#109、#111
