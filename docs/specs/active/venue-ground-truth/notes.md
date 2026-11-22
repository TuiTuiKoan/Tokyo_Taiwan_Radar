# Notes

## 2026-11-22 初步估計（已被基準取代）

以下是寫 proposal 第一版時用近似 SQL 估的數字，保留作紀錄。**不要引用**：它把 auto_qa 排除的來源算進分母，把日本以外的地址算成不合格，「街道級」的規則也與量尺不同（把只有丁目、只有郵遞區號的字串算成街道級，又漏掉漢數字與京都式番地）。正式數字見 `docs/evaluation/venues/2026-11-22-address-baseline.md`。

母體：`events` 中 `is_active` 且 `merged_into_event_id IS NULL` 且 `location_name` 非空。「實體場地」再排除 `source_name IN ('gguide_tv','ndl_opensearch')` 與 `location_name` 符合 `(オンライン|online|配信|zoom|テレビ|チャンネル|youtube|放送|BS|NHK)`。

「街道級」的近似 SQL 規則：地址非空、含數字，且符合 `(丁目|番|号|[0-9０-９]+[-－‐ー−][0-9０-９]+)`。這是量級估計，精確值以 `audit_venue_addresses.py` 為準。

| 量測 | 值 |
|---|---|
| 實體場地事件 | 1,668 |
| 其中沒有街道級地址 | 484（空白 155、非空但無效 329） |
| 對應的不同場地名 | 280 |
| 即將舉辦 | 149，其中 43 筆不合格 |
| 近 60 天新進 | 466，其中 113 筆不合格 |
| `venue_id` 為空 | 945 |
| `venues` 總數／權威／非權威 | 429／62／367 |
| 權威場館有地址／有官網 | 58／62 |
| 非權威場館有地址／有官網 | 0／0（掛 452 筆事件） |
| 有座標的場館 | 0 |
| 無地址場館中，旗下事件已有唯一街道級地址 | 111 |

不合格筆數較多的來源（不合格／總數）：`kokuchpro` 80／100、`note_creators` 79／108、`prtimes` 56／139、`google_news_rss` 43／82、`iwafu` 33／124、`rti_jp` 32／37、`bigromanticrecords` 27／48、`koryu` 15／23。其中 `note_creators`、`prtimes`、`google_news_rss` 目前在 `auto_qa._NO_VENUE_QA_SOURCES`，被排除在場地類 QA 之外。

`event_reports` 中 `auto_qa_missing_address` 的歷史：confirmed 126、dismissed 89、pending 45。

## 2026-11-22 查證

- `field_corrections` 的欄位（production `information_schema.columns`）：`id, event_id, field_name, original_value, corrected_value, corrected_by, created_at, report_id, last_override_attempted_at, override_attempted_value, override_attempt_count, first_override_attempted_at`。沒有 `source_id`。`geocode_events._has_field_correction_lock()` 以 `source_id` 過濾，所以只要事件有 `venue_id` 且地址能定位，回寫場館那一步就會出錯。該 workflow 步驟是 `continue-on-error: true`。
- `kokuchpro` 的待補事件依等級與場地名分組：幾乎都是地址空白、場地名正常。「居酒屋しいちゃんの家」26 筆空白、同名 6 筆有街道級地址；「アジアンスパイスキング」6 筆空白。

## 評審處置（plan-critique-1.md）

| 編號 | 處置 |
|---|---|
| A1 非日本判定順序 | 已修。地名只在字串開頭才算日本以外；日本地址含「台湾」「高雄町」的案例進測試。線上判定移到街道級之後 |
| A2 三個 street 定義 | 已修。proposal 的定義改成與程式一致；驗收基準改用稽核腳本的數字；舊估計標為不可引用 |
| D1 機器驗證的寫入路徑 | 寫進 proposal「後段設計」，Phase D 前定案並再送評審 |
| D2 事件共識不是獨立證據 | 同上；稽核的回填候選改標「上限」。基準裡找到一個實例（月見ル君想フ的京都地址） |
| M1 假的 street | 已修。漢數字只在丁目、番地與丁目之後的番、号轉換；時間、日期、「第N」、展館編號、計數詞列為雜訊；一位數番號只在「町」之後才算；建物名裡的數字不算。評審列的案例全部進測試 |
| M2 線上判定有多套 | 量尺只評字串；稽核沿用 `auto_qa._is_online_or_tv`，另報混合活動的筆數（6）。收斂成一份留給 #364 |
| M3 精度沒有方法 | 稽核輸出分層樣本；Phase A 驗收改為使用者抽查 |
| M4 Phase B 的影響面 | 稽核輸出 `is_vague()` 與量尺不一致的筆數（72）。刪除逐事件的 `auto_qa_vague_address`；「場地名不是場地」只列清單 |
| M5 排除來源的範圍 | 列為使用者決定；稽核分開報兩種分母 |
| M6 geocoding 回寫 | 已查證欄位不存在，另開 issue；不放進本 spec |
| M7 kokuchpro | proposal 的描述已更正；提前到 Phase C，另開 issue |
| M8 順序 | 出處欄位排在任何機器寫入之前；#369／#482 不再是前置 |
| M9 不鎖如何撐過重新 annotate | 列為後段設計的未決問題 |
| 刪除 Phase F、annotator 建候選、官網步驟、candidate 狀態 | 已刪 |
| m1 #111 | 措辭已改 |
| m2、m3、m4、m6 | 已修並進測試 |
| m5 兩地並列 | 等級不變，docstring 與測試註明不可當單一場館的證據；排除規則寫進後段設計 |
| m7 沒有地址的權威場館 | 稽核列出：4 筆都是多會場 |
| m8 札幌條丁目 | 定為 town，寫在 docstring、proposal 與測試 |
| 復用 `extract_prefecture` | 未做：量尺需要完整的都道府縣清單做正規表示式，驗證閘（後段）再用既有函式 |

## 決定紀錄

- slug `venue-ground-truth`、主題「資料修復」：與 `authoritative-venue-repair` 同領域。
- 第一個 PR 只做 Phase A：先量量尺的精度，再讓它驅動 QA 報告與寫入。
- 場地層級的缺口不逐事件開報告：`event_reports` 以事件為鍵，修復單位是場地；逐事件開報告的審核負擔與修復單位不符。
- 量尺錯的方向偏向「待補」：假的 street 會把缺陷藏起來，也會成為之後回填的證據，代價高於多看一筆。
- Plan Critic 由 Claude 執行：本環境沒有 `codex` 指令。

## 2026-11-22 #339 的 6 筆場館：現況與原計畫的差異

唯讀比對：production 現況（Supabase MCP `SELECT`）對照 `_oneoff_seed_authoritative_venues.py` 的 seed 經 `_desired_payload()` 算出的目標值。只有別名順序不同的不列。

| 場館 | 原計畫要改 | 備註 |
|---|---|---|
| 八丁座 | 別名移除「サロンシネマ」「サロンシネマ1・2」；官網補結尾斜線 | #482 的別名互撞就是這一筆 |
| サロンシネマ | 地址 `八丁堀16-10 タカタビル8F` → `八丁堀16-10 広島東映プラザビル8階`；官網補結尾斜線 | |
| センチュリーシネマ | 地址 `栄3-15-13 スカイルビル地下2F` → `栄3-29-1 名古屋パルコ東館8F`；官網改為 `eiga.starcat.co.jp` 的場館頁 | 掛 4 筆活動 |
| 台湾文化センター（權威） | 官網 `taiwanembassy.org/...` → `jp.taiwan.culture.tw` | 掛 50 筆活動 |
| 東京国際映画祭 | 別名移除「東京国際映画祭2026」 | 這個別名是 8 月之後加的，**不應移除**；原計畫不知道它 |
| 高田世界館 | 無差異 | 但現值官網 `shintomiza.whitesnow.jp` 疑似是別的影院，原待辦「以官方證據複核」仍成立 |

重複場館 `e87b461e`「台湾文化センター」（非權威）仍掛 19 筆活動、`124ca4f6`「台灣文化中心」掛 1 筆。
