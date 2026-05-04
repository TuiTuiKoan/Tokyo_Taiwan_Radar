---
slug: artist-cafe-scraper
title: Artist Cafe 爬蟲（台東藝文咖啡廳活動）
status: parked
branch: ~
created: 2026-05-02
tags: [scraper]
---

## What

為 Artist Cafe（台東區藝文類咖啡廳 / 藝廊咖啡空間）建立爬蟲，抓取活動資訊。

## 現況

- Phase 0/3 完成：POC 測試完成，確認頁面結構可爬，事件格式可解析
- 尚未建立正式 `sources/artistcafe.py`，未 commit

## 下一步（Phase 1）

1. 建立 `scraper/sources/artistcafe.py`（繼承 BaseScraper）
2. 產生正確的 Event 格式（`source_name = "artist_cafe"`，穩定的 `source_id`）
3. 在 `scraper/main.py` SCRAPERS 列表新增
4. `python main.py --dry-run --source artist_cafe` 驗證
5. Commit（同一 commit 必須含 `artistcafe.py` + `main.py` 兩個檔案）

## 暫存原因

其他 scraper 工作優先；POC 結果有效，可隨時繼續。

## References

- `.github/wip.md`（WIP 追蹤）
- `scraper/sources/base.py`（BaseScraper 介面）
