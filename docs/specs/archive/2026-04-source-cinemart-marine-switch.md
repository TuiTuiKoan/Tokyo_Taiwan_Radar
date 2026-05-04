---
slug: cinemart-marine-switch
title: Cinemarine + CineswitchGinza 爬蟲
status: archived
branch: feat/source-cinemart-shinjuku 或更早（已 merge）
created: 2026-04-20
archived: 2026-05-05
tags: [scraper]
---

## 完成內容

- `sources/cinemarine.py`（`CinemartScraper`）：横浜シネマリン（WordPress static HTML）
- `sources/cineswitch_ginza.py`（`CineswitchGinzaScraper`）：シネスイッチ銀座（Tokyo）
- 兩館各自獨立 scraper，未共用 `cinemart_shinjuku.py` 邏輯

## 備註

原本以為尚未實作（在 parked 清單），確認後兩個 scraper 已完整實作並 merge 進 main。
