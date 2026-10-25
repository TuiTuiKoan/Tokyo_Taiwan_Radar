---
slug: scraper-zero-output
title: Scraper Zero Output
description: Make scrapers that return 0 events fail loudly, and move the sources GitHub Actions cannot reach to a home-IP weekly run
status: archived
branch: fix/scraper-zero-output
created: 2026-10-22
updated: 2026-10-25
tags:
  - scraper
  - ci
  - observability
---

## What（做什麼）

六個來源（mot、taipei_fukuoka、jposa_ja、tokyo_art_beat、tokyo_now、bookandbeer）在 `scraper_runs` 一直是「success、0 筆」，其實是各自壞掉。本 spec 做三件事：

1. 查出每個來源 0 筆的真正原因（不靠猜測，從 GitHub Actions 實測）。
2. 列表／API 層失敗一律 raise，讓 `main.py` 記 `success=False`；單一詳細頁失敗仍只跳過那一筆。
3. 被 GitHub Actions IP 封鎖的來源改由家用 IP 每週跑一次，其餘依各自原因修復或下架。

## Why（為什麼）

- 「success、0 筆」讓 health check 與 `source_expectations` 都看不出來源壞了；taipei_fukuoka 與 jposa_ja 在 CI 取得的是 CloudFront 的錯誤頁（200 HTML），scraper 把它當成沒有文章。
- 這些來源是台灣相關活動的重要官方管道（駐日代表處、東京都現代美術館），漏抓會直接少活動。

## 根因（2026-10-22 從 ubuntu-24.04 runner 實測）

| 來源 | 結論 | 處理 |
| --- | --- | --- |
| mot | 對所有路徑與 UA 回 403（含 robots.txt），為 IP 封鎖 | 家用 IP 每週 |
| taipei_fukuoka、jposa_ja | roc-taiwan.org 的 CloudFront 把 data-center IP 302 到 `/Embassy_Error/`，requests 跟隨後回 200 HTML。推測是 WAF／IP 信譽封鎖（未取得官方說明） | 家用 IP 每週 |
| tokyo_art_beat | 不是 token 問題。`cdn.contentful.com` 的 space 已凍結（event 只剩 18 筆）；即時資料在 `cdn.prod.tabdev.net` 的 CDA proxy | 改讀 proxy，space 凍結時 raise |
| tokyo_now | 網站已轉成娛樂新聞／PR 站，Events Calendar 已移除，沒有可改寫的列表 | 下架（使用者決定） |
| bookandbeer | 選擇器仍有效（26 張卡片）；只有 2 篇詳細頁各提一次台灣，低於相關性門檻，0 筆是正確結果 | 只加列表失敗 raise |

## Non-Goals（不做什麼）

- 不改 `BaseScraper`、不新增框架。
- 不把爬蟲整體搬離 GitHub Actions；只處理被封鎖的三個來源。
- 不處理場館資料清理（#369、#371，另一個 worktree）。
- 不收緊 jposa_ja 的外交官出席報導過濾；列為後續討論。

## Design（設計摘要）

- **Fail loudly**：mot `_fetch_json` raise；taipei_fukuoka 列表沒有 `.news-item` 就 raise；jposa_ja 第 1 頁失敗或沒有 `<item>` 就 raise（第 2 頁起 404 只代表分頁結束）；bookandbeer 第 1 頁沒卡片或逾時 raise；tokyo_art_beat 錯誤訊息不含 token，且 upcoming 少於 `_MIN_UPCOMING_EVENTS`（100）就 raise。測試集中在 `scraper/tests/test_scraper_list_failure_raises.py`。
- **家用 IP 排程**：`main.py` 的 `HOME_IP_ONLY_SOURCES` 在 `GITHUB_ACTIONS=true` 且未指定 `--source` 時略過；`--source` 接受逗號清單。`scripts/launchd/` 提供週一 15:00 JST 的 launchd 排程。三個來源列入 `health_check.py`、`qa_triage.py` 的 `NON_DAILY_SOURCES`。
- **單一來源補充範圍**（#395）：`_enrichment_scope()` 讓 `--source` 只補充自己新入庫的活動，家用排程從 25 分鐘以上縮到約 2 分鐘。
- 影響檔案：`scraper/main.py`、`scraper/annotator.py`、`scraper/health_check.py`、`scraper/qa_triage.py`、`scraper/source_expectations.json`、各來源檔與 SKILL、`scripts/launchd/`。

## 驗證結果

- 家用排程首次執行（2026-10-23 02:16 JST）：rc=0、2 分 18 秒；jposa_ja 3、taipei_fukuoka 2、mot 2 筆，`scraper_runs` 17515–17517 皆 success。
- Daily Scraper 2026-10-23：tokyo_art_beat 10 筆 success；bookandbeer 0 筆 success；三個家用來源未在 CI 執行；tokyo_now 無紀錄。整個 run 因 #424（別的 session 的回歸）標為 failure，與本 spec 無關。

## References

- 相關 issue：#375、#376、#377、#378（已關）、#394、#395、#404、#424
- 技術債：jposa_ja 的外交官出席報導會變成公開活動（既有行為）
