# Tasks

## Phase A：location_prefectures backfill（最高優先）

- [ ] A1：在 `scraper/backfill_location_prefectures.py` 加 `--mode single` flag
- [ ] A1：dry-run 驗證輸出（預期 141 筆候補）
- [ ] A1：執行實寫，確認填充率 ≥85%
- [ ] A2：在 `annotator.py` 的 `update_data` 構造階段加 prefecture 自動衍生
- [ ] A2：對 5 筆 sample event 跑 annotator dry-run 驗證
- [ ] A3：（暫不執行）對 20 件「有場地名無地址」事件——記錄在 `notes.md`，待 enrich_addresses 流程處理

## Phase B：performer Tier 2 backfill

- [ ] B1：實作 `annotator.py --backfill-performer-tier2` flag
  - 篩選 `performer IS NULL AND event_form ∈ {lecture, performance, screening_with_talk, workshop, conference}`
- [ ] B2：dry-run 預估候選筆數（預期 ~44 件）
- [ ] B3：執行 GPT-4o-mini patch（只更新 performer 欄位）
- [ ] B4：對結果做 sanity check（過長 / 含敬語 / 含日期 → 標記為可疑）
- [ ] B5：通過驗證的 performer 寫入 `field_corrections` 鎖住
- [ ] B6：驗證 performer 填充率 ≥45%（針對 lecture/performance 類）

## Phase C：P4.1–4.4 缺口認領

- [ ] C1：用戶 review P4.1 內容並標記 (a) 合併 / (b) 廢棄 / (c) 仍需做
- [ ] C1：用戶 review P4.2 內容並標記
- [ ] C1：用戶 review P4.3 內容並標記
- [ ] C1：用戶 review P4.4 內容並標記
- [ ] C2：將結論寫入 `notes.md`
- [ ] C3：若有 (c) 項，建立 `feedback-loop-p4-residual` spec

## Phase D：Architect SKILL.md 防回退

- [ ] 加 Tier 1 Fill Rate Guard：每月 1 號自動檢核 `location_prefectures ≥85%` 與 `organizer ≥90%`
- [ ] 加 `daily_quality.py` 監控（已有此腳本，加一個 `metric_type=fill_rate` 行）

## Verification

- [ ] `python backfill_location_prefectures.py --mode single --dry-run` 顯示 141 筆候選
- [ ] backfill 後 SQL 驗證：`SELECT count(*) FROM events WHERE is_active AND location_prefectures IS NOT NULL` ≥ 140
- [ ] `python annotator.py --backfill-performer-tier2 --dry-run` 顯示 44 筆候選
- [ ] backfill 後 SQL 驗證：lecture/performance 類事件中 performer 填充率 ≥45%
- [ ] `daily_quality.py` 跑出當日的 fill_rate 指標並寫入 `daily_quality_metrics`
- [ ] `/admin/stats` 顯示新的 fill_rate 趨勢卡片（若 D 步驟完成）
