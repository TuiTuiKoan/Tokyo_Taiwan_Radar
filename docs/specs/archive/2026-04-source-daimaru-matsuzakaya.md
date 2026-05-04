---
slug: source-daimaru-matsuzakaya
title: DaimaruMatsuzakaya + GguideTV 爬蟲 + Web Report UI
status: archived
branch: feat/source-daimaru-matsuzakaya（已 merge）
created: 2026-04-20
archived: 2026-05
tags: [scraper, web]
---

## 完成內容

- `sources/daimaru_matsuzakaya.py`（`DaimaruMatsuzakayaScraper`）：大丸松坂屋 11 店 JSON API
- `sources/gguide_tv.py`（`GguideTvScraper`）：番組表Gガイド（bangumi.org）
- Web：admin report section 新增 wrongDetails 欄位的 editable textarea
- Engineer history：ReportSection wrongDetails textarea 記錄

## 影響範圍

- 新增 scraper 2 個（1 個 JSON API 型，1 個 TV 節目型）
- Web admin UI：report 修正 UI 強化
