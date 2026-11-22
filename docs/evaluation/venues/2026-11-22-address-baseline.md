# 場地地址基準（2026-11-22）

spec `venue-ground-truth` Phase A 的第一份基準。以 `scraper/audit_venue_addresses.py` 對 2026-11-22 13:10 JST 前後的 production 唯讀匯出執行（`--events-json`／`--venues-json`；匯出用 Supabase MCP 的唯讀 `SELECT`，匯出檔不入庫）。等級定義見 `scraper/address_quality.py`，母體定義見稽核腳本開頭。抽查樣本見 [`2026-11-22-address-grade-sample.md`](./2026-11-22-address-grade-sample.md)。

## 讀法

- 「待補」是町名、僅行政區、空白、非地址四級的合計。日本以外的地址不算待補，也不在街道級比率的分母裡。
- 現行 `auto_qa_missing_address` 只在地址空白時回報。QA 範圍內的 258 筆待補中，空白 138 筆，另外 120 筆（町名、僅行政區、非地址）目前沒有任何 QA 報告。
- auto_qa 排除場地 QA 的來源（`note_creators`、`prtimes`、`google_news_rss`、`walkerplus`）另有 323 筆具名場地的事件，其中 148 筆待補。這些來源是否需要地址由使用者決定，所以兩種分母都列出。
- 待補的 258 筆集中在少數場地名：前 10 個場地名佔 96 筆。
- 登記簿的回填候選 101 筆是上限：同一個 `venue_id` 下只出現一種街道級地址寫法就算，一筆事件也算，沒有查地址的出處。另有 9 筆衝突，多數只是同一地址的不同寫法（有無建物名、`3-1-1` 與 `3丁目1-1`），少數是真的不同地點（早稲田大学的兩個校區、Spotify O-nest）。
- 「青山 月見ル君想フ」的同名事件裡有一個京都地址，是既有資料的錯誤。事件之間的一致不能直接當成事實。
- `kokuchpro` 的 80 筆待補幾乎都是地址空白、場地名正常（例：「居酒屋しいちゃんの家」26 筆空白，同名另有 6 筆有街道級地址）。scraper 已經在抓 hCard 地址，空白的原因待查。
- 這份基準取代 `notes.md` 裡以近似 SQL 估的數字（1,668／484／76%／71%）。那組數字把 auto_qa 排除的來源算進分母，也把日本以外的地址算成不合格。

以下為腳本輸出。

產生時間：2026-11-22T05:22:30.355969+00:00。唯讀；等級定義見 `scraper/address_quality.py`。

### 應有實體場地的事件

| 母體 | 事件 | 街道級 | 待補 | 街道級比率 | 町名 | 僅行政區 | 空白 | 非地址 | 日本以外 |
|---|---|---|---|---|---|---|---|---|---|
| 全部 | 1387 | 1094 | 258 | 80.9% | 25 | 61 | 138 | 34 | 35 |
| 即將舉辦 | 131 | 103 | 24 | 81.1% | 2 | 8 | 5 | 9 | 4 |
| 近 60 天新進 | 395 | 330 | 61 | 84.4% | 2 | 10 | 35 | 14 | 4 |
| auto_qa 排除場地 QA 的來源 | 323 | 134 | 148 | 47.5% | 16 | 78 | 43 | 11 | 41 |
| 全部＋上列排除來源 | 1710 | 1228 | 406 | 75.1% | 41 | 139 | 181 | 45 | 76 |

街道級比率的分母不含日本以外的地址（在台灣舉辦的活動屬於收錄範圍，本量尺不評其地址）。

- `venue_id` 為空：704 筆。
- 不需要場地（純出版、線上、電視）而未計入：576 筆。
- 場地名含線上或電視字樣、但地址是街道級（混合活動，#364）：6 筆。
- `enrich_addresses.is_vague()` 視為具體、量尺判為待補：72 筆（`enrich_addresses` 改用量尺後會新增的候選）。

### 各來源

| 來源 | 範圍 | 事件 | 待補 | 街道級比率 |
|---|---|---|---|---|
| note_creators | QA 排除 | 107 | 72 | 28.7% |
| kokuchpro | QA 範圍內 | 100 | 70 | 22.2% |
| google_news_rss | QA 排除 | 75 | 39 | 44.3% |
| prtimes | QA 排除 | 139 | 35 | 67.9% |
| rti_jp | QA 範圍內 | 35 | 26 | 3.7% |
| bigromanticrecords | QA 範圍內 | 48 | 22 | 53.2% |
| iwafu | QA 範圍內 | 124 | 16 | 87.1% |
| tsutaya_portal | QA 範圍內 | 36 | 15 | 58.3% |
| eplus | QA 範圍內 | 21 | 14 | 33.3% |
| ftip | QA 範圍內 | 17 | 10 | 41.2% |
| taiwan_cultural_center | QA 範圍內 | 100 | 10 | 89.9% |
| artistcafe | QA 範圍內 | 14 | 9 | 25.0% |
| go_taiwan | QA 範圍內 | 13 | 9 | 0.0% |
| onariza | QA 範圍內 | 8 | 6 | 25.0% |
| tiff_jp | QA 範圍內 | 10 | 6 | 40.0% |
| koryu | QA 範圍內 | 19 | 5 | 61.5% |
| jats | QA 範圍內 | 14 | 4 | 71.4% |
| taiwan_matsuri | QA 範圍內 | 8 | 4 | 50.0% |
| asahiculture | QA 範圍內 | 42 | 3 | 92.9% |
| livepocket | QA 範圍內 | 23 | 3 | 87.0% |
| taioan_dokyokai | QA 範圍內 | 9 | 3 | 66.7% |
| bookandbeer | QA 範圍內 | 3 | 2 | 33.3% |
| fukuoka_now | QA 範圍內 | 2 | 2 | 0.0% |
| hakusuisha | QA 範圍內 | 22 | 2 | 90.9% |
| midland_cinema | QA 範圍內 | 2 | 2 | 0.0% |
| peatix | QA 範圍內 | 50 | 2 | 96.0% |
| walkerplus | QA 排除 | 2 | 2 | 0.0% |
| jinf | QA 範圍內 | 6 | 1 | 83.3% |
| jposa_ja | QA 範圍內 | 1 | 1 | 0.0% |
| nagoya_tcs | QA 範圍內 | 1 | 1 | 0.0% |
| startup_terrace | QA 範圍內 | 5 | 1 | 50.0% |
| taipei_fukuoka | QA 範圍內 | 5 | 1 | 80.0% |
| taiwan_festa | QA 範圍內 | 21 | 1 | 95.2% |
| taiwan_festival_tokyo | QA 範圍內 | 1 | 1 | 0.0% |
| taiwan_kyokai | QA 範圍內 | 4 | 1 | 75.0% |
| taiwanbunkasai | QA 範圍內 | 1 | 1 | 0.0% |
| tokyonow | QA 範圍內 | 5 | 1 | 80.0% |
| transit_store | QA 範圍內 | 2 | 1 | 50.0% |
| uedaeigeki | QA 範圍內 | 1 | 1 | 0.0% |
| waseda_icl | QA 範圍內 | 1 | 1 | 0.0% |

### 場地缺口（149 個場地名，列出前 25 個）

依即將舉辦的缺地址事件數、再依缺地址事件數排序。

| 場地名 | 缺地址事件 | 其中即將舉辦 | 同名事件已有的街道級地址 | 例 |
|---|---|---|---|---|
| コザ･ミュージックタウン音楽広場 および周辺 | 4 | 4 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/1b2cea88-3e49-477d-89ed-406061720f43) |
| 青山 月見ル君想フ | 4 | 2 | 京都府京都市中京区木屋町通三条下ル大黒町71；東京都港区南青山3-2-2 | [活動頁](https://tokyotaiwanradar.com/ja/events/04977c7e-d230-4653-a8ae-615950968490) |
| 横浜教室 | 2 | 2 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/02fa3ad5-a1c1-4a36-ba44-d46921257024) |
| 清和文楽館 (熊本県) | 2 | 2 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/00bd7dc6-b6da-4a96-a188-4ec0971450ff) |
| 代官山T-SITE | 8 | 1 | 東京都渋谷区猿楽町17-5 | [活動頁](https://tokyotaiwanradar.com/ja/events/0636f613-6fca-4165-b10b-48e6bf229017) |
| Artist Cafe Fukuoka | 3 | 1 | 福岡県福岡市中央区天神2丁目3-10；福岡県福岡市博多区下川端町3-1 | [活動頁](https://tokyotaiwanradar.com/ja/events/0dee9d8e-0b78-4a4b-8f4e-523ea3ad6837) |
| ミッドランドシネマ 名古屋空港 | 2 | 1 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/0bcdb858-5121-4baa-8c68-036026fcb387) |
| 本屋 B&B | 2 | 1 | 〒155-0033 東京都世田谷区代田2-36-15 BONUS TRACK 2F | [活動頁](https://tokyotaiwanradar.com/ja/events/7090a387-3c39-47eb-b0bc-9098622837f8) |
| アテネ・フランセ地下1階カフェテリア） | 1 | 1 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/407a033b-0b1d-49ec-be56-6ad1ddcb1b10) |
| 京都府立府民ホールアルティ | 1 | 1 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/71e2f336-3bc2-43fa-bba2-cdd4efe19f4d) |
| 平川市役所本庁舎ピロティ、平賀駅前通り、平賀駅前広場、ふらっと広場、中央公園南口 | 1 | 1 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/922a2acd-fc26-4eb1-9a78-875138129864) |
| 新宿教室 | 1 | 1 | 〒163-0210 東京都新宿区西新宿2-6-1 新宿住友ビル10階 | [活動頁](https://tokyotaiwanradar.com/ja/events/8f08bac0-2cc0-4ed4-8593-047db5f09395) |
| 日経ホール | 1 | 1 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/7f6c68ac-cb3e-40b1-bdb4-8c21e42c5701) |
| 早稲田大学3号館3階305教室 | 1 | 1 | 東京都新宿区西早稲田1-6-1 | [活動頁](https://tokyotaiwanradar.com/ja/events/a9ad6e1f-79cd-4de7-b38f-cfa8f6da4fa3) |
| 早稲田大学早稲田キャンパス3号館605教室 | 1 | 1 | 東京都新宿区西早稲田1-6-1 | [活動頁](https://tokyotaiwanradar.com/ja/events/1315f3d4-190d-4710-bd60-b5cf975aff60) |
| 春水堂 代官山店 春水堂 表参道店 春水堂 横浜ポルタ店 春水堂 藤沢湘南台店 春水堂 銀座店 春水堂 東京ドームシティラクーア店 春水堂 ルミネ大宮店 | 1 | 1 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/2b1b7514-428c-4f51-befe-75d01eca0866) |
| 杉並公会堂 小ホール | 1 | 1 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/58db3fd2-6340-455e-8a71-377329080e7f) |
| 美山かやぶきの里 | 1 | 1 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/1d776b95-b9fe-4822-aac2-7e067266f88e) |
| RTI台湾国際放送（日本語部門） | 26 | 0 | 東京都港区虎ノ門1-1-1 | [活動頁](https://tokyotaiwanradar.com/ja/events/091812e5-8c41-4951-8ee1-228d93cea1b3) |
| 居酒屋しいちゃんの家/Izakaya Shiichan's House | 26 | 0 | 東京都 新宿区西新宿7-5-12 岡田ビルB1 | [活動頁](https://tokyotaiwanradar.com/ja/events/0a908463-3b0b-4c79-9878-a87215e1bc2d) |
| 台湾原住民族との交流会 | 9 | 0 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/2577d328-68ab-49d1-a37e-b6ad8b88fcc8) |
| アジアンスパイスキング | 7 | 0 | 東京都 渋谷区猿楽町2-12 相野谷ビル 1F | [活動頁](https://tokyotaiwanradar.com/ja/events/0ea62053-9d99-48b0-a5c5-9a7e3b3723a0) |
| 御成座（おなり座） | 6 | 0 | 秋田県大館市御成町1-11-22 | [活動頁](https://tokyotaiwanradar.com/ja/events/3ecb4ece-b41a-4a5c-a084-cabbc20fb5f5) |
| rental lounge御茶ノ水 | 3 | 0 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/91a36935-b68b-45c3-83b7-37c1b3fc874d) |
| 丸の内ピカデリー2 | 3 | 0 | — | [活動頁](https://tokyotaiwanradar.com/ja/events/4d83da6f-30df-41cf-b799-2edc8a903c67) |

### 場館登記簿

- 場館 429 筆，權威 62 筆，沒有地址 367 筆。
- 沒有地址、但旗下事件只出現一種街道級地址寫法：101 筆（回填候選的上限；只有一筆事件也算，未查地址的出處）。
- 沒有地址、旗下事件有兩種以上街道級地址：9 筆（需人工判斷）。
- 沒有地址、旗下事件也沒有街道級地址：257 筆。
- 權威場館中沒有地址的 4 筆：横浜国際舞台芸術ミーティング（多會場）、東京国際映画祭（多會場）、台灣國際紀錄片影展（多會場）、大阪アジアン映画祭（多會場）。
