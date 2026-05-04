---
slug: source-prtimes
title: PRTimes + OAFF 爬蟲 + 全日本地理範圍擴展
status: archived
branch: feat/source-prtimes（已 merge）
created: 2026-04-10
archived: 2026-05
tags: [scraper]
---

## 完成內容

- `sources/prtimes.py`：PRTimes 台灣關鍵字新聞稿爬蟲
- `sources/oaff.py`（`OaffScraper`）：大阪アジアン映画祭
- `taiwan_matsuri` 來源擴展至全日本活動
- **地理範圍政策擴展**：東京限定 → 全日本（`copilot-instructions.md`、`docs/ARCHITECTURE.md` 更新）
- 相關文件更新

## 影響範圍

- 新增 scraper 2 個
- 修改 `main.py` SCRAPERS 列表
- 修改地理範圍政策文件
