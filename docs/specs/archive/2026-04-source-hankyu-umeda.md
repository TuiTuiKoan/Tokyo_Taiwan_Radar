---
slug: source-hankyu-umeda
title: HankyuUmeda 爬蟲 + tv_program 分類 + Admin is_active toggle
status: archived
branch: feat/source-hankyu-umeda（已 merge）
created: 2026-04-20
archived: 2026-05
tags: [scraper, web, admin]
---

## 完成內容

- `sources/hankyu_umeda.py`（`HankyuUmedaScraper`）：阪急うめだ本店活動
- `tv_program` 新分類（`group_knowledge` 知識交流群組下）
- Admin：事件詳情頁新增 `is_active` toggle button
- Admin table 清理：移除 sourceLink、annotationStatusLabel、isPaid 欄位
- Category group picker paired-file rule 文件更新

## 影響範圍

- 新增 scraper 1 個
- `web/lib/types.ts` 新增 `tv_program` category
- Admin UI 修改
- Skill 文件更新
