---
slug: admin-report-workflow
title: 後台報告 Workflow（Daily / Weekly / Admin Dashboard）
status: active
branch: main
created: 2026-04-20
tags: [infra, admin, ci, reporting]
---

## What（做什麼）

讓開發者每天早上不用手動查 Supabase 就能掌握：
- 昨日爬蟲結果（成功/失敗/事件數/費用）
- Annotation backlog 健康度
- 待處理事項（WIP、auto-scraper PR、auto-QA 報告）
- 安全日誌（新登入/admin 操作）

輸出管道：**每日 Email（02:00 JST）+ 每週 LINE 通知 + Admin 後台頁面**

## Why（為什麼）

- 爬蟲靜默失敗（scraper 跑了但 0 件）難以察覺
- Annotation backlog 累積到數百件才發現
- WIP 項目容易忘記（`.github/wip.md` 追蹤）
- auto-scraper 生成的 PR 需要 review

## Non-Goals（不做什麼）

- ❌ 不做 real-time alerting（延遲 24h 可接受）
- ❌ 不做 PagerDuty / Slack（LINE + Email 已足夠）

## Design（設計摘要）

### 報告觸發鏈
```
GitHub Actions scraper.yml (09:00 JST)
  → scraper runs → events → annotator → backlog_health
  → notify.py (LINE)

GitHub Actions daily-dev-report.yml (02:00 JST)
  → daily_report.py (查 Supabase + GIT_COMMITS env)
  → Gmail SMTP 寄 Email

每週日 weekly_report.py + weekly_line_broadcast.py
  → LINE: 爬蟲健康 + 週報活動推送
```

### WIP 追蹤
`.github/wip.md` → `daily_report.py` 解析 `## ` 區塊 → 出現在 Email「待處理事項」

### Admin Dashboard
- `/admin/stats`：scraper_runs 歷史（費用、成功率）
- `/admin/aeo`：AEO bot visits + GSC 數據
- `/admin/reports`：event_reports 佇列

## References

- `scraper/daily_report.py`（Email）
- `scraper/weekly_report.py`（LINE 週報）
- `scraper/weekly_line_broadcast.py`（LINE 活動週報）
- `scraper/backlog_health.py`（Annotation backlog 監控）
- `.github/wip.md`（WIP 追蹤）
- `.github/workflows/daily-dev-report.yml`
