---
slug: source-cinemart-shinjuku
title: CinemartShinjuku 爬蟲 + _loc_zh() 簡繁字對應修正
status: archived
branch: feat/source-cinemart-shinjuku（已 merge）
created: 2026-04-20
archived: 2026-05
tags: [scraper]
---

## 完成內容

- `sources/cinemart_shinjuku.py`（`CinemartShinjukuScraper`）：シネマート新宿 電影場次
- `_loc_zh()` char map 擴展：加入 9 組簡繁字對應（解決 Simplified → Traditional 轉換 bug）
- Kokuchpro source SKILL.md + history.md
- Scraper Expert SKILL.md：加入 doc-omission mistake 教訓（Step 0 檢查清單）

## 影響範圍

- 新增 scraper 1 個
- `annotator.py` 或相關模組 `_loc_zh()` 修正
- Skill 文件更新
