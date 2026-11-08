# Tasks

本檔只放不超過十條里程碑。細項開 GitHub issue，貼 `spec:sentry-stacktrace` label。

- [ ] PR A：Python 統一初始化（`scraper/observability.py`）合併
- [ ] PR B：workflow step 補 `SENTRY_DSN` 合併（人類關卡：secrets）
- [ ] PR C：`except` 內 `logger.error` → `logger.exception` 與防退化測試合併
- [ ] PR D：Web instrumentation（server／edge／client／global-error、source map）合併
- [ ] Sentry 後台：code mapping 設定（人類關卡）
- [ ] 驗收：Python 與 web 各至少一筆新 event 有 Stack Trace 且能點到 GitHub
