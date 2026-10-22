# 0 產出來源盤點（2026-10-22，#327）

2026-10-18 週報有 55／128 個來源一週產出為 0，成功率卻都是 100%。本次逐一判斷 #327 列出的 17 個來源（19 個 run key）。

## 方法

1. 唯讀 SQL：`scraper_runs` 最近 120 天每個來源的執行次數、產出量、最後一次有產出的日期；`events` 中各來源歷來入庫的月份。
2. 本機 dry-run：`python main.py --dry-run --source <key>`，不寫資料庫，記錄 log 與解析出的事件數。
3. 對照正式環境 log：2026-10-22 的 scraper run 39717601254（每日來源），以及 2026-10-19 的 run 39192650984（週一來源）。

## 結論

### 故障（5 個來源，已開 issue）

| run key | 證據 | issue |
|---|---|---|
| tokyo_art_beat | 08-19 前 90 天產出 567 筆，之後全是 0；本機崩潰：錯誤處理用了不存在的 `self.logger`；CI 0.3 秒回報 0 筆 | #375 |
| tokyo_now | 本機：events REST API 回 404；最後一次產出 09-14 | #376 |
| bookandbeer | 本機：「Page 1 had cards but yielded 0 events」；最後一次產出 09-04 | #377 |
| mot | 本機抓到 2 筆，含台灣主題展「共時的星叢」（9/5–12/13）；CI 被 403 擋；最後一次產出 07-12 | #378 |
| taipei_fukuoka | 本機抓到 2 筆，含「台湾映画祭 in Kumamoto 2026」（10/31–11/1）；CI「0 posts to process」 | #378 |
| jposa_ja | 本機抓到 3 筆；CI 0.08 秒回報 0 筆 | #378 |
| tiff | 4 個放映場館未登錄，10 部台灣片全部被略過 | #341（既有） |

### 列表正常，目前沒有台灣內容（季節性或零星）

| run key | 證據 | 預期 |
|---|---|---|
| oaff | 列表正常，0 筆台灣片 | 大阪アジアン映画祭，每年 3 月；2–4 月應有產出 |
| waseda_taiwan | 抓到 40 篇文章，全部是已過去的活動（scraper 只收未來的活動）；CI 與本機相同 | 學期中不定期公告，120 天內應有產出 |
| ifi | 3 個即將舉行的活動，0 個與台灣相關 | 零星，180 天 |
| tokyo_city_i | 5 個進行中的活動，0 個與台灣相關 | 零星，180 天 |
| transit_store | 31 個商品，0 個與台灣相關；最後一次產出 10-11 | 零星，90 天 |
| kawade_rss | RSS 解析正常，0 筆台灣相關；120 天內從未產出 | 低產出，365 天 |
| ginsee_hikariza、ginsee_roble | 0 部台灣片 | 戲院，取決於上映片單，180 天 |
| kino_cinema_shinsaibashi、kbc_cinema | 0 部台灣片；最後一次產出 09-03、09-12 | 同上 |
| ttcg_umeda、cinelibre_kobe | 列表 19、12 部片，0 部台灣片 | 同上 |

上述預期寫進 `scraper/source_expectations.json`，週報據此把「預期中的 0」與「原因未知的 0」分開。

## 附帶觀察

- 故障的 6 個來源在 `scraper_runs` 都記為 `success = true`。被擋、API 404、解析 0 筆都沒有讓執行失敗，這是 #319 要處理的部分。
- `tokyo_art_beat` 在 `scraper_runs` 的 key 與 events 的 `source_name`（`tokyoartbeat`）不同；週報以 `main.py` 新寫入的 `event_sources` 對應，歷史資料則去掉底線比對。
- 2026-10-22 的每日排程曾因 GitHub runner 換成 Ubuntu 26.04、Playwright 不支援而失敗。`scraper.yml` 已固定 `ubuntu-24.04`，當天手動重跑成功，不影響本盤點。
