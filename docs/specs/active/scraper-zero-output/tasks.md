---
title: Scraper Zero Output Tasks
description: Milestones for the scraper zero-output fix
status: active
updated: 2026-10-23
---

本檔只放里程碑。細項與 bug 開 issue，貼 `spec:scraper-zero-output` label。

## Phase A: 查明與修復

- [x] 從 GitHub Actions 實測各來源可達性，確認根因（#375–#378）
- [x] 列表／API 失敗一律 raise，補測試（#375、#377、#378）
- [x] tokyo_now 下架（#376）
- [x] 被封鎖的三個來源改家用 IP 每週執行，單一來源補充範圍縮小（#378、#395）

## Phase B: 驗證與收尾

- [x] 家用排程首次執行成功（2026-10-23）
- [x] Daily Scraper 驗證 tokyo_art_beat、bookandbeer（2026-10-23）
- [x] 修好 #424（push 後 Daily Scraper 才會回到 success）
- [x] `source_expectations.json`：三個家用來源與 bookandbeer 改為 sporadic，移除 tokyo_art_beat
- [ ] 關閉 #375、#376、#377、#395，spec 歸檔

## Verification

- [x] `pytest scraper/tests`：1270 passed、1 skipped
- [x] `python3 scripts/sync_ai_adapters.py --check` 無漂移
- [ ] 一次完整 success 的 Daily Scraper
