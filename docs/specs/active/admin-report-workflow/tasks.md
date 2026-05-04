# Tasks

## Daily Email Report（daily_report.py）

- [x] 查詢 scraper_runs：昨日各來源結果（事件數、費用、成功/失敗）
- [x] 查詢 events：昨日新增活動數、待審核數
- [x] 查詢 event_reports：待處理報錯數
- [x] 查詢 research_sources：待研究候選來源數
- [x] `GIT_COMMITS` env var 注入：顯示昨日 git commits
- [x] `.github/wip.md` 解析：顯示進行中項目
- [x] 30 天持續 0 件來源監控（`check_persistent_zero_sources`）
- [x] 待 review auto-scraper PR 列表（`auto_scraper_pr_url IS NOT NULL`）
- [x] Gmail SMTP 寄送（CI secrets: GMAIL_USER / GMAIL_APP_PASSWORD / DEV_REPORT_EMAIL）
- [x] `.github/workflows/daily-dev-report.yml`（每日 02:00 JST cron）

## Weekly LINE Report（weekly_report.py）

- [x] 7 天爬蟲統計（成功率、事件數、費用）
- [x] annotation backlog 健康度
- [x] auto-QA 類型分布（簡繁混雜 / 地址缺失 / 翻譯缺失）
- [x] `scraper.yml` 整合（每週日觸發）

## Weekly LINE Broadcast（weekly_line_broadcast.py）

- [x] 未來 35 天活動推送（zh/en/ja 三語，依訂閱者語言）
- [x] 只推送 `annotation_status IN (annotated, reviewed)`（排除 pending）
- [x] 排除 `gguide_tv`（電視節目非直播活動）
- [x] Taiwan relevance 過濾（TAIWAN RELEVANCE RULE in AI prompt）
- [x] 去重規則（每個 id 在 weekly+monthly 最多出現一次）

## Admin Dashboard

- [x] `/admin/stats`：scraper_runs 歷史（最近 100 筆，費用、成功率）
- [x] `/admin/aeo`：AEO bot visits + GSC 整合（GscSection）
- [x] `/admin/reports`：event_reports confirm/dismiss UI
- [x] `/admin/quality`：auto-QA findings 頁面
- [x] Backlog health badge（CI 觸發，warn/critical alert）

## Annotation Backlog 監控（backlog_health.py）

- [x] active_pending > 150 → warn；> 250 → critical
- [x] old_pending_over_7d > 30 → warn；> 80 → critical
- [x] 子事件 pending（parent_event_id IS NOT NULL）= 0 監控
- [x] notify.py 整合（LINE 即時通知）

## 待改善（可選）

- [ ] `/admin/stats` 顯示 YTD 累積費用 vs 月度預算（$20/月）進度條
- [ ] 月度健檢自動化：把 `MONTHLY_FEEDBACK_LOOP_HEALTH_CHECK.md` 的 SQL 查詢加入 CI
- [ ] `.github/wip.md` 在 admin 頁面顯示（目前只在 Email 中可見）

## Verification

- [ ] `python daily_report.py --dry-run` 輸出正確（含 WIP 段落）
- [ ] `python weekly_report.py --dry-run` 輸出正確
- [ ] `python weekly_line_broadcast.py --dry-run` pool 只含 annotated/reviewed 事件
- [ ] `/admin/stats` 正確顯示最近 100 筆 scraper_runs
