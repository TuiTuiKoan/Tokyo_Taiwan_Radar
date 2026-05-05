# Tasks

> ⚠️ 本 spec **依賴 `tier1-data-completion` spec 的 Phase A（location_prefectures backfill）完成**。
> 在 location_prefectures 填充率達 ≥85% 之前，**不要啟動 Phase B 之後的任務**。

## Phase A：訊號偵測模組（可獨立開發）

- [ ] A1：建立 `scraper/opportunity_signals.py`
  - [ ] `detect_new_organizer(events, lookback_weeks=12)` → list of organizer names
  - [ ] `detect_first_city_activity(events, lookback_weeks=8)` → list of prefecture
  - [ ] `detect_high_frequency_organizer(events, threshold=3)` → list of (organizer, count)
  - [ ] `detect_price_anomaly(events, multiplier=2.0)` → list of event_id
  - [ ] `detect_series_activity(events, min_consecutive_days=3)` → list of (organizer, day_range)
- [ ] A2：每個函數附 unit test，使用 mock event list
- [ ] A3：在 `weekly_line_broadcast.py --dry-run` 末尾印出當週偵測結果

## Phase B：weekly_line_broadcast 訊息升級（依賴 Phase A）

- [ ] B1：依城市圈分組（東京圈 / 關西圈 / 福岡圈 / 其他）
- [ ] B2：在訊息頂部加「📡 本週值得注意」section（呼叫 Phase A 偵測函數）
- [ ] B3：訊息底部加「升級 Pro 解鎖」CTA（連到 `/subscribe`）
- [ ] B4：保留既有 `annotation_status IN (annotated, reviewed)` 過濾（見 SKILL.md）
- [ ] B5：dry-run 三語版本（zh/en/ja）並人工 review

## Phase C：訂閱頁 `/subscribe`

- [ ] C1：建立 `web/app/[locale]/subscribe/page.tsx`
- [ ] C2：頁面包含
  - [ ] 產品說明（三層級對照表）
  - [ ] LINE 加好友 QR + URL
  - [ ] Pro / Pro+ 升級表單（v1.0 為「我有興趣」按鈕，連到 contact form）
- [ ] C3：i18n 三語翻譯
- [ ] C4：加入 `Navbar` 導航
- [ ] C5：加入 `sitemap.xml`

## Phase D：使用者反應追蹤（v1.0 上線後 4 週）

- [ ] D1：每週統計 LINE 訂閱數變化（既有 `line_users` 表）
- [ ] D2：人工抽查 5 條訊號的真實性
- [ ] D3：記錄主動詢問升級的使用者（Manual log in `notes.md`）
- [ ] D4：4 週後 review，決定是否啟動 v1.1（付費層級）

## Phase E（v1.1，待 Phase D 結果）：付費層級

- [ ] E1：定義 Pro 與 Pro+ 的具體內容差異
- [ ] E2：選擇金流（LINE Pay / Stripe）
- [ ] E3：使用者帳號或 LINE userId 升級狀態管理
- [ ] E4：每日推播 cron job

## Verification

- [ ] Phase A：`python -m pytest scraper/tests/test_opportunity_signals.py` 全綠
- [ ] Phase B：`python weekly_line_broadcast.py --dry-run` 輸出含 5 種訊號 section
- [ ] Phase C：`pnpm --filter web build` 成功，`/subscribe` 頁面三語可訪問
- [ ] 第一週實測：訊息送達率 100%、訊號真實率 ≥80%、用戶詢問升級 ≥3 人（4 週內）
