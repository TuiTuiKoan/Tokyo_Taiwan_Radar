<!-- 第一份報表，PR #379 的 CI run 39767960420 產生，原樣保存。之後的週報只放在 workflow summary 與 artifact。 -->

> 讀這份報表時要注意：
> - 「需要處理」中 30 個「原因未知的 0」在 #381 盤點；prtimes 的「執行失敗」是 NUL 字元讓整批寫入失敗，09-14 起沒有新活動入庫（#380）。
> - 修正率：90 天內建立的事件沒有任何人工修正（同期 10 筆人工修正都在更早的事件上），腳本寫入不代表錯誤。在 #374 補上人工訊號之前，「錯填率」只能看腳本寫入量。
> - DOM drift 與 annotator 補填需要 `main.py` 寫入 `parsed_fields_median` 後的執行紀錄，合併後約一週開始有數字。

# Scraper 品質週報 — 2026-10-22

- 來源：123 個 scraper；產出看最近 7／28 天，欄位與修正看最近 90 天建立的有效母事件
- 狀態：🟢 有產出 72、🟡 本週 0，28 天內有 1、🔵 季節外 1、🔵 零星來源，仍在預期內 11、🔴 已知故障 7、🔴 最近一次執行失敗 1、🔴 28 天以上 0，原因未知 30

## 需要處理

| source | 原因 |
|---|---|
| acros_fukuoka | 🔴 28 天以上 0，原因未知 |
| ciema | 🔴 28 天以上 0，原因未知 |
| cine_gallery | 🔴 28 天以上 0，原因未知 |
| cineplaza | 🔴 28 天以上 0，原因未知 |
| cineswitch_ginza | 🔴 28 天以上 0，原因未知 |
| faam_fukuoka | 🔴 28 天以上 0，原因未知 |
| hankyu_hakata | 🔴 28 天以上 0，原因未知 |
| hankyu_kobe | 🔴 28 天以上 0，原因未知 |
| hankyu_umeda | 🔴 28 天以上 0，原因未知 |
| hanshin_amagasaki | 🔴 28 天以上 0，原因未知 |
| hanshin_mikage | 🔴 28 天以上 0，原因未知 |
| hanshin_nishinomiya | 🔴 28 天以上 0，原因未知 |
| hanshin_umeda | 🔴 28 天以上 0，原因未知 |
| human_trust_cinema | 🔴 28 天以上 0，原因未知 |
| internet_museum | 🔴 28 天以上 0，原因未知 |
| livepocket | 🔴 28 天以上 0，原因未知 |
| maruhiro | 🔴 28 天以上 0，原因未知 |
| midland_cinema | 🔴 28 天以上 0，原因未知 |
| nagano_aioiza | 🔴 28 天以上 0，原因未知 |
| nhk_rss | 🔴 28 天以上 0，原因未知 |
| otto | 🔴 28 天以上 0，原因未知 |
| prtimes | 🔴 最近一次執行失敗 |
| stranger | 🔴 28 天以上 0，原因未知 |
| taiwanshi | 🔴 28 天以上 0，原因未知 |
| theater_kino | 🔴 28 天以上 0，原因未知 |
| tokyo_filmex | 🔴 28 天以上 0，原因未知 |
| tuat_global | 🔴 28 天以上 0，原因未知 |
| united_cinemas | 🔴 28 天以上 0，原因未知 |
| us_cinema_chiba_gekijo | 🔴 28 天以上 0，原因未知 |
| walkerplus | 🔴 28 天以上 0，原因未知 |
| whitestone_gallery | 🔴 28 天以上 0，原因未知 |
| ndl_opensearch | 欄位完整度最低前 3（38%，203 筆） |
| google_news_rss | 欄位完整度最低前 3（42%，57 筆） |
| rti_jp | 欄位完整度最低前 3（45%，19 筆） |

## 1. 產出健康

| source | 狀態 | 7 天執行 | 7 天產出 | 28 天產出 | 最後有產出 | 說明 |
|---|---|---|---|---|---|---|
| kgplus_kyotographie | 🟡 本週 0，28 天內有 | 7 | 0 | 24 | 2026-10-10 |  |
| oaff | 🔵 季節外 | 1 | 0 | 0 | 120 天內沒有 | 大阪アジアン映画祭，每年 3 月舉行 |
| cinelibre_kobe | 🔵 零星來源，仍在預期內 | 7 | 0 | 0 | 120 天內沒有 | 戲院，列表 12 部片，取決於台灣片上映 |
| ginsee_hikariza | 🔵 零星來源，仍在預期內 | 7 | 0 | 0 | 120 天內沒有 | 戲院，取決於台灣片上映 |
| ginsee_roble | 🔵 零星來源，仍在預期內 | 7 | 0 | 0 | 120 天內沒有 | 戲院，取決於台灣片上映 |
| ifi | 🔵 零星來源，仍在預期內 | 1 | 0 | 0 | 120 天內沒有 | 活動列表正常，台灣相關活動少 |
| kawade_rss | 🔵 零星來源，仍在預期內 | 7 | 0 | 0 | 120 天內沒有 | RSS 只含最新書目，台灣相關新書少；120 天內 0 筆 |
| kbc_cinema | 🔵 零星來源，仍在預期內 | 7 | 0 | 0 | 2026-09-12 | 戲院，取決於台灣片上映 |
| kino_cinema_shinsaibashi | 🔵 零星來源，仍在預期內 | 7 | 0 | 0 | 2026-09-03 | 戲院，取決於台灣片上映 |
| tokyo_city_i | 🔵 零星來源，仍在預期內 | 1 | 0 | 0 | 120 天內沒有 | 活動列表正常，台灣相關活動少 |
| transit_store | 🔵 零星來源，仍在預期內 | 7 | 0 | 7 | 2026-10-11 | 商品列表正常，台灣商品不定期上架 |
| ttcg_umeda | 🔵 零星來源，仍在預期內 | 7 | 0 | 0 | 120 天內沒有 | 戲院，列表 19 部片，取決於台灣片上映 |
| waseda_taiwan | 🔵 零星來源，仍在預期內 | 7 | 0 | 0 | 2026-09-11 | 只收未來的活動；學期中不定期公告 |
| bookandbeer | 🔴 已知故障 | 7 | 0 | 0 | 2026-09-04 | #377 卡片在，解析 0 筆 |
| jposa_ja | 🔴 已知故障 | 1 | 0 | 0 | 120 天內沒有 | #378 GitHub Actions 上 0 events；本機正常 |
| mot | 🔴 已知故障 | 7 | 0 | 0 | 2026-07-12 | #378 GitHub Actions 上 403；本機正常 |
| taipei_fukuoka | 🔴 已知故障 | 7 | 0 | 0 | 120 天內沒有 | #378 GitHub Actions 上 0 posts；本機正常 |
| tiff | 🔴 已知故障 | 1 | 0 | 0 | 120 天內沒有 | #341 4 個放映場館未登錄為權威場館，台灣片全部被略過；東京国際映画祭 10–11 月 |
| tokyo_art_beat | 🔴 已知故障 | 7 | 0 | 0 | 2026-08-19 | #375 08-19 起 0；錯誤處理用了不存在的 self.logger |
| tokyo_now | 🔴 已知故障 | 1 | 0 | 0 | 2026-09-14 | #376 events REST API 404 |
| prtimes | 🔴 最近一次執行失敗 | 7 | 0 | 0 | 2026-09-14 |  |
| acros_fukuoka | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 2026-08-01 |  |
| ciema | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 2026-09-20 |  |
| cine_gallery | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 120 天內沒有 |  |
| cineplaza | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 120 天內沒有 |  |
| cineswitch_ginza | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 2026-07-20 |  |
| faam_fukuoka | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 2026-08-30 |  |
| hankyu_hakata | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 2026-07-13 |  |
| hankyu_kobe | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 120 天內沒有 |  |
| hankyu_umeda | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 120 天內沒有 |  |
| hanshin_amagasaki | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 120 天內沒有 |  |
| hanshin_mikage | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 120 天內沒有 |  |
| hanshin_nishinomiya | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 120 天內沒有 |  |
| hanshin_umeda | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 2026-08-17 |  |
| human_trust_cinema | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 120 天內沒有 |  |
| internet_museum | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 120 天內沒有 |  |
| livepocket | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 2026-07-12 |  |
| maruhiro | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 120 天內沒有 |  |
| midland_cinema | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 120 天內沒有 |  |
| nagano_aioiza | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 2026-09-07 |  |
| nhk_rss | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 2026-07-31 |  |
| otto | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 120 天內沒有 |  |
| stranger | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 2026-08-06 |  |
| taiwanshi | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 120 天內沒有 |  |
| theater_kino | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 120 天內沒有 |  |
| tokyo_filmex | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 120 天內沒有 |  |
| tuat_global | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 120 天內沒有 |  |
| united_cinemas | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 120 天內沒有 |  |
| us_cinema_chiba_gekijo | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 120 天內沒有 |  |
| walkerplus | 🔴 28 天以上 0，原因未知 | 7 | 0 | 0 | 2026-09-20 |  |
| whitestone_gallery | 🔴 28 天以上 0，原因未知 | 1 | 0 | 0 | 120 天內沒有 |  |

有產出的來源（72）：amayaza, artistcafe, arukikata, asahi_culture, big_romantic_records, cine_marine, cinema_clair, cinemadict, cinemart_shinjuku, cinewind, daimaru_matsuzakaya, eiga_com, eplus, eslite_spectrum, eurospace, ftip, fukuoka_now, gguide_tv, go_taiwan, google_news_rss, hakusuisha, hanmoto, ide_jetro, iwafu, jats, jinf, johakyu, kawasaki_ac, kokuchpro, koryu, ks_cinema, kyoto_cinema, matsumoto_cinema_select, moon_romantic, morc_asagaya, nagoya_tcs, ndl_opensearch, nittai_toumonkai, note_creators, onariza, peatix, placebymethod, rightscube, rti_jp, sakurazaka, shin_bungeiza, snet_taiwan, ssff, starcat_cinema, startup_terrace, taioan_dokyokai, taiwan_cultural_center, taiwan_expo_japan, taiwan_faasai, taiwan_festa, taiwan_festival_tokyo, taiwan_kyokai, taiwan_matsuri, taiwan_prism, taiwanbunkasai, theater_enya, tiff_jp, tobunken, tsudoi_osaka, tsutaya_portal, ueda_eigeki, uplink_cinema, waseda_icl, wuext_waseda, ycam_cinema, yebizo, zinbun_kyoto

## 2. 欄位完整度

只列 90 天內有 ≥ 10 筆事件的來源，依平均完整度由低到高。純出版紀錄不計地址、營業時間與場館名稱。

| source | 事件 | 平均 | start_date | end_date | location_name | location_address | business_hours | price_info | is_paid | official_url | organizer | image_url | performers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ndl_opensearch | 203 | 38% | 46% | 46% | — | — | — | 8% | 8% | 0% | 100% | 7% | 85% |
| google_news_rss | 57 | 42% | 79% | 79% | 56% | 58% | 26% | 39% | 40% | 0% | 47% | 0% | 37% |
| rti_jp | 19 | 45% | 100% | 100% | 100% | 26% | 11% | 16% | 16% | 5% | 95% | 0% | 32% |
| gguide_tv | 131 | 48% | 100% | 100% | 100% | 16% | 100% | 2% | 2% | 0% | 29% | 0% | 78% |
| kokuchpro | 10 | 51% | 100% | 100% | 100% | 100% | 10% | 50% | 50% | 0% | 20% | 0% | 30% |
| ueda_eigeki | 11 | 53% | 100% | 100% | 9% | 18% | 0% | 100% | 100% | 9% | 64% | 0% | 82% |
| tsutaya_portal | 21 | 58% | 100% | 100% | 100% | 52% | 67% | 29% | 52% | 0% | 76% | 0% | 57% |
| ks_cinema | 41 | 62% | 83% | 83% | 100% | 100% | 0% | 100% | 100% | 100% | 2% | 0% | 15% |
| prtimes | 47 | 63% | 100% | 100% | 94% | 77% | 100% | 38% | 64% | 0% | 98% | 0% | 26% |
| note_creators | 54 | 63% | 93% | 93% | 98% | 89% | 33% | 24% | 48% | 20% | 72% | 100% | 26% |
| iwafu | 39 | 64% | 100% | 100% | 100% | 97% | 64% | 36% | 59% | 85% | 41% | 0% | 23% |
| eplus | 10 | 66% | 100% | 100% | 100% | 100% | 100% | 30% | 100% | 0% | 0% | 0% | 100% |
| hakusuisha | 10 | 66% | 100% | 100% | 100% | 70% | 80% | 40% | 50% | 0% | 100% | 0% | 90% |
| eslite_spectrum | 43 | 78% | 100% | 100% | 100% | 100% | 95% | 95% | 93% | 0% | 98% | 0% | 77% |
| taiwan_cultural_center | 19 | 78% | 100% | 100% | 100% | 100% | 100% | 26% | 63% | 100% | 95% | 0% | 79% |
| asahi_culture | 13 | 81% | 100% | 100% | 100% | 92% | 100% | 100% | 100% | 100% | 0% | 0% | 100% |

## 3. 修正率（每 100 筆事件）

人工：`corrected_by` 有值（後台編輯）。腳本：annotator、qa_auto_fix、publication-policy 等自動寫入，只有 `report_id` 的列也屬此類，不代表錯誤（#373）。

| source | 事件 | 人工 | 人工／100 | 腳本 | 腳本／100 |
|---|---|---|---|---|---|
| ndl_opensearch | 203 | 0 | 0.0 | 1447 | 712.8 |
| ks_cinema | 41 | 0 | 0.0 | 155 | 378.0 |
| gguide_tv | 131 | 0 | 0.0 | 133 | 101.5 |
| note_creators | 54 | 0 | 0.0 | 113 | 209.3 |
| eslite_spectrum | 43 | 0 | 0.0 | 97 | 225.6 |
| taiwan_cultural_center | 19 | 0 | 0.0 | 72 | 378.9 |
| iwafu | 39 | 0 | 0.0 | 66 | 169.2 |
| nagano_aioiza | 5 | 0 | 0.0 | 42 | 840.0 |
| google_news_rss | 57 | 0 | 0.0 | 39 | 68.4 |
| ueda_eigeki | 11 | 0 | 0.0 | 29 | 263.6 |
| hanmoto | 4 | 0 | 0.0 | 28 | 700.0 |
| morc_asagaya | 5 | 0 | 0.0 | 27 | 540.0 |
| asahi_culture | 13 | 0 | 0.0 | 25 | 192.3 |
| rti_jp | 19 | 0 | 0.0 | 25 | 131.6 |
| tsutaya_portal | 21 | 0 | 0.0 | 25 | 119.0 |
| matsumoto_cinema_select | 4 | 0 | 0.0 | 24 | 600.0 |
| johakyu | 4 | 0 | 0.0 | 23 | 575.0 |
| cinemadict | 3 | 0 | 0.0 | 21 | 700.0 |
| theater_enya | 3 | 0 | 0.0 | 21 | 700.0 |
| eplus | 10 | 0 | 0.0 | 20 | 200.0 |

## 4. DOM drift

比較最近 3 次執行的解析欄位數中位數與先前的中位數，全部下降超過 30% 才告警。
資料來自 main.py 寫入 `scraper_runs.notes` 的 `parsed_fields_median`；目前有足夠紀錄的來源：0 個。

_紀錄累積中：每個來源需要至少 6 次帶有欄位數的執行。_

## 5. Annotator 補填

已入庫事件的追蹤欄位中位數，減去 scraper 當下解析出的中位數。數字越大，代表 scraper 抽得越少、越依賴 annotator。

_紀錄累積中：需要 main.py 寫入 `parsed_fields_median` 後的執行紀錄。_
