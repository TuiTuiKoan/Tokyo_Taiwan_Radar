# 實作計畫 v2：Phase B 到 E（2026-11-22）

> **已依 `plan-critique-2.md` 修訂，修訂後的版本與結果見文末「v2.1」。** 上半部保留為評審時的原文。

使用者 2026-11-22 要求「全部規劃、批評、開發 PR」。本檔是 `proposal.md`「後段設計（未定案）」的定案版本，拆成五個 PR。每個 PR 可以單獨合併；production 寫入一律只做到 dry-run 與 manifest，寫入是人類關卡。

建議模型：規劃與評審 Opus；實作 Sonnet 等級即可（本 session 由 Opus 一併執行）。

## 先查到的事實（2026-11-22，production 唯讀）

1. **re-annotate 不會清掉事件地址。** `annotator.py` 合併時以事件現值優先（`_loc(event.get("location_address")) or …`），只有權威場館命中時才以場館地址覆寫。`database.upsert_events()` 對已存在的事件預設跳過，新事件才寫入並自動鎖定地點欄位（`_auto_lock_location`，`corrected_by` 與 `report_id` 皆為空）。所以評審 M9 的「不鎖會被清空」不成立：機器驗證地址寫進事件後不需要鎖。
2. **`field_corrections` 裡的「腳本鎖」有兩種來源，欄位上分不出來。** 新事件寫入時的自動鎖（等於 scraper 原值，是獨立證據）與 `enrich_addresses` 同名複製後的鎖（是複本）。可用的區分：自動鎖的 `created_at` 與事件的 `created_at` 相差在數秒內；複製鎖晚得多。
3. **#707 kokuchpro 不是現行 bug。** 2026-08 以後新進的 kokuchpro 事件全部有地址。67 筆空白全是過去的活動：60 筆是 2026-04-28 一次匯入的舊活動（開始日早於 cutoff，scraper 不抓詳情頁），另有一批在 2026-09-13 03:15 UTC 被同一個動作清成空白（65 筆，`updated_at` 完全相同），其中 7 筆的 `field_corrections` 仍鎖著正確地址。即將舉辦的空白是 0 筆。
4. **事件值與鎖定值不一致**：`location_address` 有鎖定值、事件卻是空白的，排除出版品後是 kokuchpro 7 筆、peatix 1 筆。這是一般性的資料錯誤，值得當 QA 項目。
5. **#706 geocoder**：候選每天取前 50 筆（沒有排序），定位失敗的地址每天重試；回寫場館時查不存在的 `field_corrections.source_id` 會丟例外並中斷整個執行。

## PR 1：修 geocoder（#706）

範圍：`scraper/geocode_events.py` 與測試。不加 migration。

- 不再寫 `venues.address`。場館只回寫座標，而且只在場館是權威、非多會場、場館地址與事件地址的比較鍵相同時才寫。
- 拿掉查詢 `field_corrections.source_id` 的鎖定檢查（該表以事件為鍵，沒有場館層級的鎖；場館座標只在為空時寫入，等同不覆寫）。
- 只定位 `street` 級地址；町名、行政區級的地址定位到區中心，沒有用處。
- 候選依「即將舉辦優先、再依開始日」排序，分頁取足再篩，避免每天卡在同一批失敗的地址。
- 每筆事件獨立 try/except，一筆出錯不中斷整批。

驗證：單元測試用假的 Supabase client 與假的 geocoder，覆蓋：場館地址不被寫、非權威場館不寫座標、地址不同不寫、street 以外不送 API、例外不中斷。

## PR 2：Phase B，讓現有流程用同一把尺

範圍：`scraper/address_quality.py`、`scraper/enrich_addresses.py`、`scraper/audit_venue_addresses.py`、`.github/workflows/scraper.yml`、測試。

1. **地址比較鍵 `address_key()`**：NFKC、拿掉郵遞區號與「日本」、漢數字丁目、把 `丁目`／`番地`／`番`／`号`／`の` 與各種連字號統一成 `-`、去空白，並截到番地為止（建物名與樓層不算）。`3-1-1` 與 `3丁目1-1`、有無建物名，會得到同一個鍵。
2. **`enrich_addresses` 改用量尺**：
   - 候選：量尺判為待補（town、region、empty、not_address）的即將舉辦事件；日本以外的地址不動。
   - 權威場館：地址判為 `street` 或 `town` 都接受（公園、無番地的校園是人工確認過的地址）；`region` 以下不接受。
   - 同名事件共識：只計 `street` 級；以比較鍵分組；**至少 2 筆獨立事件**（排除同名複製留下的複本，判定見事實 2）；出現兩個以上不同鍵就不猜；一個欄位裡寫了兩個都道府縣的值不計。
   - 同名複製**不再寫鎖**（事實 1：不需要；而且鎖會擋住之後的修正）。既有的複製鎖不動，交 PR 4 的 planner 列出。
3. **稽核加兩個數字**：事件值與鎖定值不一致的筆數（事實 4）；`enrich_addresses` 新舊規則的候選差異（量尺上線後實際影響面）。
4. **每日報告**：`scraper.yml` 在 `enrich_addresses` 之後加一個只讀步驟，跑 `audit_venue_addresses.py`，寫進 job summary 並上傳 JSON（保留 90 天，當作趨勢紀錄）。`continue-on-error: true`，不改 workflow 權限、不新增 secrets。

`auto_qa` 不改：逐事件的模糊地址報告維持不做（proposal Non-Goals）。

驗證：`enrich_addresses` 的純函式測試（候選篩選、權威接受等級、共識規則、複本排除、衝突）；對 2026-11-22 唯讀匯出跑新舊兩套候選的差異並寫進 PR。依 Venue QA Skip Source Registration Guard，`detect()` 沒有動，不需要前後比較。

## PR 3：場館欄位修正工具與 #733 的 manifest

範圍：新增 `scraper/venue_field_fix.py`、`docs/evaluation/campaigns/2026-11-venue-field-fixes.json`（目標值與官方出處）、測試。

- 三個模式：`--capture`（唯讀，讀現值、與目標值比對，輸出 manifest 與 SHA-256）、`--apply MANIFEST`（逐筆 CAS：`update … where` 修改前的每個欄位都相等；寫後讀回）、`--rollback MANIFEST`。預設 dry-run。另可 `--before-json` 離線產生 manifest。
- 只改 `venues` 的指定欄位，不碰事件。事件會在下一次 annotate 時經權威場館路徑更新；PR 說明列出受影響的事件數。
- 目標值檔逐欄附官方出處 URL 與確認日期。內容：八丁座別名、サロンシネマ地址、センチュリーシネマ地址與官網、台湾文化センター官網、兩筆官網結尾斜線。不含東京国際映画祭的別名刪除與高田世界館（#733 已說明）。
- 新增權威場館候選「台湾華語文学習センター（大阪弁天町）」（#732）：只列在檔案的 `proposed_new_venues`，工具不寫入；是否成為權威場館由使用者決定（ground truth 關卡）。

人類關卡：`--apply` 前使用者核准 manifest 的 SHA-256。

## PR 4：Phase D，出處欄位與回填 planner

範圍：`supabase/migrations/111_venue_address_provenance.sql`（只提交檔案，套用是人類關卡）、新增 `scraper/plan_venue_address_backfill.py`（唯讀 planner）、測試、`proposal.md` 後段設計定案。

**migration**：`venues` 加 `address_source`（`manual`、`event_consensus`、`source_page`、`web_search`，可為空）、`address_evidence_url`、`address_checked_at`。既有權威場館的地址標 `manual`。

**機器驗證的寫入路徑（定案）**
- 機器驗證地址存在非權威場館列上（`is_authoritative = false`、`address_source` 非空）。
- `venue_registry` 的快取與 `database.py` 的場館比對**維持只讀權威場館**；加一個測試鎖住「非權威列有地址也不會被解析」。
- 事件只透過 `enrich_addresses` 的新步驟取用：事件的 `location_name` 與該場館的 `canonical_name_ja` 正規化後完全相同，才寫事件的 `location_address` 一欄；不改名稱、都道府縣、官網、`venue_id`；不寫鎖（事實 1）。

**planner 的類別**（全部只輸出 manifest，不寫入）

| 類別 | 條件 | 寫入什麼 |
|---|---|---|
| `venue_backfill` | 殘樁場館沒有地址；旗下或同名事件至少 2 筆、來自 2 個以上來源，或 1 筆但地址逐字出現在該事件原文；只計 street 級、以比較鍵比對、排除複本與兩地並列；名稱對不到權威場館 | `venues.address` 與出處 |
| `attach_authoritative` | #371 第 1 類：事件名稱唯一解析到權威場館、`venue_id` 為空、事件的地點欄位沒有人工鎖 | 事件 `venue_id` |
| `merge_duplicate` | #371 第 2 類：3 個非權威重複場館（`e87b461e`、`bd8f93a6`、`20a97518`）的事件改掛權威場館；之後該場館的參照數為零才可刪 | 事件 `venue_id`；刪除另列 |
| `fc_mismatch` | 事實 4：事件的地址空白、鎖定值非空，且鎖定值是 street 級 | 事件 `location_address` = 鎖定值 |
| `copy_locks` | 同名複製留下的鎖 | 只列出，不動 |
| `org_as_venue` | #371 第 3 類與 #732 的團體名 | 只列出，交人工 |

每類附 before、after 與證據；manifest 有 SHA-256。apply 工具在 migration 套用、使用者核准 manifest 後另開 PR，沿用 PR 3 的 CAS 寫法。

驗證：planner 的純函式測試；對 2026-11-22 唯讀匯出產生 manifest，數字寫進 PR。

## PR 5：#370 registry 召回，低風險的部分

範圍：`scraper/venue_registry.py`、`scraper/tests/golden/venues_manifest.json`、測試。

- 比對前做 NFKC，並忽略「・」「･」與空白的差異（r042、r048）。
- 不放寬前綴與後綴規則（r043、r044、r045、r047 的誤中風險高，留在 #370）。r046 是補別名，屬資料修正，併入 PR 3 的目標值檔。
- `eval-venues` 的解析段錯配必須仍為 0；正確數提高後調高 `min_correct`。

## 不做

- **web search（#366）**：PR 2 與 PR 4 都完成、回填套用之後，量測兩週內每天剩多少筆查不到的即將舉辦事件；平均每天 3 筆以上才評估。
- **daily_quality_metrics 加欄位**：要 migration；每日稽核 JSON artifact 已能看趨勢。
- **kokuchpro 舊活動重抓詳情頁**：全是過去的活動，價值低；7 筆可由 `fc_mismatch` 恢復。

## 順序與人類關卡

PR 1、PR 2、PR 3、PR 5 彼此獨立。PR 4 的 planner 不依賴 migration 已套用（離線產生 manifest），但 apply 依賴。

| 步驟 | 關卡 |
|---|---|
| 合併 PR 1–5 | 使用者合併 |
| PR 3 `--apply` | 使用者核准 manifest |
| PR 4 migration 套用 | 使用者 |
| PR 4 manifest 的 apply（另開 PR） | 使用者核准 manifest |
| 新權威場館（台湾華語文学習センター） | 使用者確認 ground truth |
| 團體名、連鎖店、串流的歸類 | 使用者判斷 |


---

## v2.1：評審後的修訂與結果（2026-11-22）

評審全文 `plan-critique-2.md`，結論是「修訂後進行，範圍要縮」。處置見 `notes.md`「評審處置（plan-critique-2）」。修訂前先做了評審要求的唯讀查證：

| 查證 | 結果 |
|---|---|
| 帶 JSON 引號的事件地址／地址鎖 | 3／20 筆（M2 成立）→ #756 |
| #732 台湾華語文学習センター的事件有沒有地址鎖 | 42 筆中 41 筆有（B1 成立：升成權威場館也改不到這些事件） |
| 掛在權威場館下、鎖的值與場館現址不同 | 字串比 40 筆、比較鍵比 1 筆（多數只是寫法不同）；這 1 筆是鎖成 `null` 的線上活動，不算過時 |
| 2026-09-13 03:15 UTC 的動作 | 落在當天 Daily Scraper 執行期間（02:52 開始），步驟未查明 → #757 |

### PR 對照

| 計畫 | PR | 內容 |
|---|---|---|
| PR 1 | #752 | geocoder 不再寫 `venues` 表（評審 M7：場館座標沒有讀取者，刪掉回寫），只定位 street 級、即將舉辦優先、單筆例外不中斷 |
| B1 根因（新增） | #754 | 自動鎖只鎖 scraper 給的地點值，不鎖場館傳播的值 |
| PR 2 | #755 | `enrich_addresses` 改用量尺；同名證據改成正向認定（原文逐字出現的 1 筆，或 scraper 原值 2 筆且 2 個來源）；不寫複製鎖；稽核加鎖定計數；每日 workflow 跑稽核 |
| PR 3 | #758 | 改成既有 CAS 引擎的 planner（評審 M6），只有 `venue_update`；回報每個場館的事件有幾筆會跟著更新 |
| PR 4 → 4a | 本 PR | 唯讀 planner `plan_venue_address_backfill.py`，沒有 migration；刪除 `fc_mismatch` |
| PR 4 → 4b | 不做 | 見下 |
| PR 5 | #753 | registry 寬鬆比對放在上層場館規則之後（評審 M9），加 snapshot 不失鍵的測試 |

### 4a 的結果：不做 4b

對 2026-11-22 唯讀匯出（殘樁場館同名事件 541 筆含原文、全部場館、1,396 筆地址鎖）執行 planner：

- 有獨立證據、可回填地址的殘樁場館 **38 個**，但它們**能修到的即將舉辦事件是 0 筆**：同名的事件全是過去的活動。另有 2 個殘樁與權威場館同名，是重複場館（#371），不回填。
- 過時的自動鎖 0 筆；帶引號的複製鎖 20 筆（#756）；場地名與主辦單位相同 23 個（多是電視頻道與團體名，交 #732 與 #371 由使用者判斷）。

驗收指標是即將舉辦與近 60 天新進事件的街道級比率，回填 38 個殘樁對這兩個數字沒有影響。所以 **migration、傳播步驟與 apply 工具（4b）不做**。之後若每日稽核顯示殘樁場館又有即將舉辦的事件，再以 planner 的門檻（4 筆）重新判斷。

### 沒有做、留在 issue 的

- #371 第 1、2 類（`venue_id` 回填、重複場館改掛）：評審 M5 指出要沿用舊工具的分組邏輯、不可整批改掛，需要重新擷取現況後另做，屬 production 寫入。
- センチュリーシネマ即將舉辦的 3 筆事件地址被鎖在舊址：#758 apply 之後，以既有的 `qa_auto_fix` 解鎖工具處理（需核准）。
- web search（#366）：維持不做，條件不變。
