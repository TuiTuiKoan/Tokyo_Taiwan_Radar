---
slug: source-jposa-ja
title: TaipeiFukuoka + Yebizo 爬蟲 + Admin inactive 修正
status: archived
branch: feat/source-jposa-ja（已 merge）
created: 2026-04-15
archived: 2026-05
tags: [scraper, web]
---

## 完成內容

- `sources/jposa_ja.py`（`JposaJaScraper`）或同等命名：日本台灣関係協会相關
- `TaipeiFukuoka` 爬蟲：台北福岡交流相關活動
- `YebizoScraper`：惠比壽ガーデンプレイス活動
- Admin 修正：inactive 事件詳情頁可被 admin 訪問
- 前台修正：is_active=inactive 時時間篩選器自動切換至 'all'
- Scraper Expert skill commit gate 文件更新

## 影響範圍

- 新增 scraper 2-3 個
- Admin / 前台 UX 修正
- Skill 文件更新
