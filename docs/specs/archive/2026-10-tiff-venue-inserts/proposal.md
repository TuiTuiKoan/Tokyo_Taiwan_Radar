---
slug: tiff-venue-inserts
title: TIFF 2026 權威場館新增（4 筆）
status: archived
branch: feat/tiff-venue-inserts
created: 2026-10-25
tags: [scraper, venue, data-repair, cas, production]
---

# TIFF 2026 權威場館新增（4 筆）

看板卡：[#341](https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/issues/341)。過程中的細項沿用
`spec:authoritative-venue-repair` label（使用者指定）。暫停中的完整 repair 見
[#339](https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/issues/339) 與
`docs/specs/parked/authoritative-venue-repair-followups.md`。

## 為什麼

`TiffScraper` 只把台灣片綁到唯一的權威實體場館；找不到就跳過整部片。2026-10-19 的排程（run
`39192650984`）10 部台灣片全被跳過，`source_name='tiff'` 在 production 是 0 筆。TIFF 2026 已開幕。

## 範圍

只新增 4 筆 `venues`（`is_authoritative = true`、`is_multi_venue = false`）：

| canonical_name_ja | 地址 | homepage | 官方來源（2026-10-25 複核） |
| --- | --- | --- | --- |
| ヒューリックホール東京 | 東京都千代田区有楽町2-5-1 有楽町マリオン11F | https://hulic-theater.com/access/ | 同頁 |
| TOHOシネマズ シャンテ | 東京都千代田区有楽町1-2-2 | https://www.tohotheater.jp/theater/041/access.html | 同頁；TOHO 2026-08-25 起把シャンテ從日比谷（081）頁分離 |
| TOHOシネマズ 日比谷 スクリーン12・13 | 東京都千代田区有楽町1-1-3 東京宝塚ビル地下 | https://www.tohotheater.jp/theater/081/access.html | 同頁「＜スクリーン12･13＞」 |
| 丸の内ピカデリー | 東京都千代田区有楽町2-5-1 有楽町マリオン9F | https://www.smt-cinema.com/site/marunouchi/access.html | 同頁「【丸の内ピカデリー１・2】」 |

TIFF 2026 venues API（`https://api-2026.tiff-jp.net/api/venues`）的 cinema `name_ja`：前兩筆與丸の内ピカデリー
和 canonical 名完全相同；日比谷是「TOHOシネマズ 日比谷 スクリーン12、13 (東京宝塚ビル地下)」，由既有的
`_TIFF_CINEMA_NAME_OVERRIDES` 對應。丸の内ピカデリー不需要 override。

10 部台灣片另外用到ヒューマントラストシネマ有楽町（3 部）與シネスイッチ銀座（1 部），兩者在 production
已是權威場館（2026-10-25 唯讀查詢），所以 4 筆寫入後 10 部都能解析。

## 不做

完整 70-action repair、6 筆既有場館 update、event／FC 修改、TCC duplicate 刪除、R1 都留在 #339。
不執行 `build_production_plan()`。不改 `supabase/**`、`web/**`、`scraper/main.py`、`sources/tiff.py`。

## 設計

- `scraper/_oneoff_seed_authoritative_venues.py`：シャンテ homepage 改 041、日比谷 12・13 地址對齊官方日文、
  新增丸の内ピカデリー seed。
- `scraper/_oneoff_plan_tiff_venue_inserts.py`（新）：唯讀讀取全部 `venues`，檢查 live 欄位等於引擎的
  `VENUE_REQUIRED_FIELDS`、4 個 canonical 名與 aliases 不和任何既有場館（含非權威）的 canonical／alias 碰撞、
  新 UUID 不存在；以 `uuid4` 產生 4 個 UUID，輸出只含 4 筆 `venue_insert` 的 immutable plan（git-ignored
  `tmp/`）。`created_at`／`updated_at` 用整秒 UTC，讓 insert 後的 exact read-back 可比對。HEAD 必須已在
  `origin/main`。
- 沿用 `_oneoff_repair_authoritative_venues.py` 引擎：preview → `--capture`（UUID absence + canonical-name
  absence，manifest SHA-256）→ Gate 2 → `--apply`（逐筆 CAS insert 與讀回）→ 第二次 `--apply` 必須 noop。
  抽出 `new_venue_row()` 共用，`build_production_plan()` 行為不變。

## 驗收

- 程式：focused tests（plan、STOP 條件、apply／第二次 noop、drift 零寫入、CLI、2026 fixture 10 部片全部解析）＋
  完整 `pytest tests`，經 Tester PASS。
- production：4 筆讀回與 manifest after image 完全一致；`scrape-now.yml`（`sources: tiff`）補跑後
  `tiff` 入庫台灣片數 > 0，`location_*` 與場館一致。

## 每階段建議模型

實作與測試：Sonnet · medium。Gate 2 manifest 複核與 production apply：Opus · high。
