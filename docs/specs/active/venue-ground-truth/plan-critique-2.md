# Plan Critique 2：venue-ground-truth 實作計畫 v2（`plan-2.md`，五個 PR）

> 評審者：Claude plan-critic（與撰寫者同一模型家族；Codex 在本環境無法啟動）
> 評審日期：2026-11-22。全程唯讀：沒有修改、建立或刪除任何檔案，沒有 git 寫入，沒有連 production。
> 評審對象：`docs/specs/active/venue-ground-truth/plan-2.md`。背景讀了同資料夾的 `proposal.md`、`plan-critique-1.md`、`notes.md`、`tasks.md`，以及 `docs/evaluation/venues/2026-11-22-address-baseline.md`。

## 查證範圍與限制

- 「先查到的事實」裡的 production 數字（67、65、7、8 筆等）**沒有重查**。我只對照程式檢查這些事實背後的推論。
- 程式路徑已逐一讀過：`annotator.py`、`database.py`、`enrich_addresses.py`、`enrich_location.py`、`geocode_events.py`、`venue_registry.py`、`address_quality.py`、`audit_venue_addresses.py`、`backfill_entities.py`、`merger.py`、`qa_auto_fix.py`、`_oneoff_repair_authoritative_venues.py`、`_oneoff_plan_tiff_venue_inserts.py`、`.github/workflows/scraper.yml`，另外 grep 了 `web/`。
- 實測：`grade_address('"東京都港区虎ノ門1-1-12"')` 回傳 `street`（見 M2）。
- **PR 1、PR 2 在評審前已經開工**：`ttr-geocode-fix-worktree` 的 `fix/geocode-venue-writeback` 已有 commit `aec8060`，`ttr-venue-phase-b-worktree` 的 `scraper/address_quality.py` 有未提交的修改。下面的修訂要改在這兩個 worktree。

## 結論（先講）

**修訂後進行，但範圍要縮。** PR 1、PR 2、PR 5 可以修訂後繼續。PR 3 應改成既有 CAS 引擎的 planner。PR 4 要拆開：planner 先做，migration 等 planner 的數字出來再決定。

兩個 Blocker 都出在「先查到的事實」的推論上，不是實作細節：

| 編號 | 嚴重度 | 一句話 |
|---|---|---|
| B1 | Blocker | 新事件的自動鎖鎖住的是**場館傳播過來的值**，不只是 scraper 原值。所以修場館地址不會流到這些事件；PR 3 的效果說明、#732「以場地為單位修一次即可」、PR 4 的傳播範圍都建立在不成立的前提上 |
| B2 | Blocker | 「排除複本」不等於「只留獨立證據」：沒有鎖的事件地址大多是 LLM 產物。而且 PR 2 的自動寫入規則比 PR 4 須人工核准的規則還寬 |
| M1–M10 | Major | 見下 |
| m1–m9 | Minor | 見下 |

---

## 1. 商業主軸對齊

- 對應主軸第 1 項「資料完整性與正確性」。沒有偏離專案使命。
- 但驗收指標是**即將舉辦**與**近 60 天新進**事件的街道級比率（`tasks.md` Verification：78.8% → 90%、76.3% → 88%）。計畫沒有寫出每個 PR 預計讓這兩個數字移動多少。見 M3。
- 評分：🟢 對齊（PR 1、2、3、5）；🟡 弱對齊（PR 4：主要修的是過去的活動）。

## 2. 複雜度 vs 價值

| 範圍 | 複雜度 | 依據 |
|---|---|---|
| 全計畫 | very-high | migration（+1）；跨 10 個以上檔案（+1）；改 workflow（+0.5）；新寫 production CAS 工具（+1）；碰 FC 鎖語意與 Entity Normalization Guard（+1）；動 registry 解析，影響錯配 0 的 eval（+1） |
| PR 1、PR 2、PR 5 | medium | 不加 migration，各 2–4 個檔案 |
| PR 3 | 新寫：medium；復用引擎：low | 見 M6 |
| PR 4 | high | migration、6 個 planner 類別、一條新的事件寫入路徑、之後再一個 apply PR |

業務價值，以基準數字看（`2026-11-22-address-baseline.md`）：

- QA 範圍內**即將舉辦**的待補只有 **24 筆**（131 筆中，空白 5、僅行政區 8、非地址 9、町名 2）。排除來源的 148 筆中，即將舉辦的只有 6 筆（`proposal.md` 使用者決定 2）。
- 近 60 天新進 395 筆中有 61 筆待補，約每天新增 1 筆。這是持續流入的缺口，由 PR 2 處理。
- PR 4 的事件傳播只走 `enrich_addresses`，而它只看即將舉辦的事件（`enrich_addresses.py:77`）。所以回填對過去的活動沒有效果（M3）。

**比值警示**：PR 4 的複雜度高於它能移動的指標。PR 1、2、3、5 的比值可以接受。

## 3. 優先順序提醒（Anti-Rabbit-Hole）

- 🔴 **PR 4 是「為少量事件造通用機制」**：migration、出處欄位、6 個類別、apply 工具，最後能影響的即將舉辦事件以 24 筆為上限，還要扣掉 B1 的鎖。planner 應該先回答「實際能修好幾筆即將舉辦的事件」，再決定 migration。
- 🟡 **PR 1 把 critique-1 移出去的 Phase F 又帶回來了**：排序、只送 street 級、場館座標回寫都是定位改進。`web/` 完全沒有讀 `latitude`／`longitude`（grep 為 0 筆），座標目前沒有使用者。PR 1 該做的只有三件事：停寫 `venues.address`、拿掉壞掉的鎖查詢、單筆例外不中斷。見 M7。
- 🟡 B1 是根因：只要自動鎖照現況運作，所有「修場館」的工作對已入庫的事件都只能部分生效。這一項優先於 PR 4。
- 評分：PR 2 🟢；PR 1、3、5 🟢（修訂後）；PR 4 🟡 拆開並延後 migration。

## 4. 全站架構整合分析

### Blocker B1：自動鎖鎖住場館傳播的值，場館修正流不到已入庫的事件

證據鏈：

1. `database.py:1027` 先組 `all_rows = new_rows + force_rows`（同一批 dict 物件），`:1034` 接著呼叫 `_populate_entity_fks(client, all_rows)` 就地改寫這些物件：只要名稱解析到權威場館，`location_name`、`location_address`、`location_prefectures` 都會換成場館的值（`:546-552`）。
2. `:1125-1137` 從**已經被改寫的** `new_rows` 建立 `eid_to_row`，交給 `_auto_lock_location()`（`:667-693`）。後者把 `location_name`、`location_address`、`location_prefectures` 寫進 `field_corrections`，`corrected_by` 為空。
3. 所以，凡是入庫當下名稱就解析到權威場館的事件，自動鎖的值就是**當時的場館地址**，不是 scraper 原值。
4. 之後場館地址改了（PR 3 改サロンシネマ與センチュリーシネマ），annotator 的權威路徑遇到受保護欄位會直接跳過（`annotator.py:2872-2874`）。force 路徑會寫回 FC 的舊值並記錄覆寫嘗試（`database.py:524-532` 附近的 `_record_fc_override_attempt`）。`enrich_addresses` 會跳過任何有 `location_address` 鎖的事件（`enrich_addresses.py:170-189`）。
5. annotator 預設也只處理 `pending` 事件（`annotator.py:3082`），`reviewed` 永遠不處理。

後果：

- **PR 3**：「事件會在下一次 annotate 時經權威場館路徑更新」不成立，原因有兩個：已標註的事件不會再跑，而且多數事件的地址被鎖住了。
- **#732**：「台湾華語文学習センター 40 筆……以場地為單位修一次即可」（`proposal.md` 使用者決定 2）。如果這 40 筆入庫時 scraper 就給了「大阪府大阪市西区」，它們已經被自動鎖凍結，升成權威場館也改不到。**需要一次唯讀查證**：這 40 筆的 `location_address` 有沒有 `corrected_by IS NULL AND report_id IS NULL` 的鎖。
- **事實 2**：「自動鎖等於 scraper 原值，是獨立證據」，對入庫時就解析到權威場館的事件不成立。
- **PR 2**：候選擴大到 `town` 級之後，scraper 給的町名級值大多已經被自動鎖，會被 FC skip 擋掉。基準量到的「72 筆新候選」（`is_vague` 與量尺不一致）是上限，實際能寫的數字要扣掉有鎖的事件。

修訂：

- **根因修正**（小 PR，或併入 PR 2）：`_auto_lock_location` 只鎖 **scraper 提供的值**。在 `_populate_entity_fks` 之前先保存 scraper 的原始地點欄位，被場館傳播改寫過的欄位不鎖。這也讓事實 2 變成真的。不鎖並不會讓 annotator 清掉地址，因為 annotator 以事件現值優先（`annotator.py:3403`）。同時改 `test_database_venue_fks.py` 的對應期望值。
- **既有的鎖**：PR 4 planner 加一類 `stale_auto_locks`，列出「自動鎖的值等於某權威場館的舊地址，或等級低於該權威場館地址」的事件。解鎖是 production 寫入，屬人類關卡。
- PR 3 的 PR 說明改寫成：把受影響事件分成「沒鎖、會在重新 annotate 時更新」「有鎖、不會更新」「reviewed」三類，各列筆數。
- 稽核（PR 2 第 3 點）加一個數字：有權威 `venue_id`、地址被鎖、而且鎖的值與場館現址比較鍵不同的事件數。這才是「場館修正被擋住」的實際規模。

### Blocker B2：「獨立證據」的定義錯，自動路徑比人工路徑還寬

1. **沒有鎖的地址大多不是 scraper 原值。** 入庫時有 `location_name` 的事件，scraper 給的地址都會被自動鎖（`database.py:667-693`）。反過來說，有地址卻沒有 `location_address` 鎖的事件，地址來自下列幾處：
   - annotator 的 GPT 抽取（`annotator.py:3403` 的第三順位）；
   - 每天執行的 `enrich_location.py`，用 gpt-4o-mini、不上鎖（`enrich_location.py:193`；`scraper.yml:86-97`）。它的 prompt 第 2 條還允許回傳城市名；
   - registry 填值（`enrich_location.py:133`）；
   - force rescrape。
   計畫的做法是「排除複本，其餘都算」，會把這些 LLM 值當成獨立證據。
2. **腳本鎖不只兩種。** 2026-10 之前的 `enrich_addresses` 用 GPT 網搜查地址，寫入事件後以 `json.dumps` 上鎖（`git show c82e7e3:scraper/enrich_addresses.py` 第 197-201 行）。這是第三種來源，事實 2 沒有列。
3. **PR 2 的自動規則比 PR 4 寬。** PR 2 的同名共識只要求「至少 2 筆獨立事件」，拿掉了 proposal 後段設計的「來自 2 個以上來源，或地址逐字出現在原文」。PR 2 每天自動寫 production、沒有人工關卡；PR 4 要使用者核准。自動路徑的門檻必須至少和人工路徑一樣嚴。
4. **用 `created_at` 時間差判別有兩個陷阱。**
   - 必須逐欄位比（`field_name = 'location_address'`）。地址空白的事件仍有 `location_name` 的自動鎖，以事件為單位比會誤判。
   - `enrich_addresses` 在同一個 workflow 裡、入庫後幾十分鐘內就會寫複製鎖，所以「晚得多」其實只差幾分鐘。門檻要定在 60 秒以內，並用測試鎖住。

**對第 2 題的回答：有更好的判別。**

- `enrich_addresses` 的複製鎖（現行 `:215`）與舊 GPT 網搜鎖都是 `json.dumps(str)`，`corrected_value` 以 `"` 開頭與結尾。自動鎖寫的是原字串（`database.py:682`）。這是確定性的判別，不靠時間。
- 建議的「獨立證據」改成**正向認定**，四個條件全部成立才算：
  1. 有 `location_address` 自動鎖，值不是 JSON 字串；
  2. 自動鎖的 `created_at` 減事件 `created_at` 在 60 秒內；
  3. 事件現值的比較鍵等於鎖的值的比較鍵；
  4. 入庫時沒有解析到權威場館（近似條件：`venue_id` 為空，或不是權威場館）。
- 沒有鎖的地址只有在「逐字出現在 `raw_description`」時才算。
- `llm_cache` 裡 step 為 `location_extract`、outcome 為 `applied` 的事件一律排除（`enrich_location.py:183`；只涵蓋 migration 099 之後）。
- 時間差與 JSON 引號兩種判別都跑，分歧的筆數寫進稽核報告。

### Major

**M1：事實 1 只在 annotator 路徑成立（第 1 題）。**

| 路徑 | 會不會清掉沒鎖的事件地址 |
|---|---|
| annotator 一般標註 | 不會（`annotator.py:3403`） |
| annotator 權威命中 | 覆寫成場館地址；多會場或場館沒有地址時寫成 None（`:2856`、`:2870`）。屬預期行為 |
| merger | 不會；只補空白欄位（`merger.py:764-766`） |
| qa_auto_fix | 不寫日文地址（只動 `FIX_FIELDS` 的 zh 欄位與 `location_url`） |
| **force_rescrape** | **會**。管理介面可以批次設定（`web/components/AdminEventTable.tsx:535`、`:621`），`--rescrape-ids` 也會觸發。整列以 scraper 值覆寫，scraper 給 None 就寫 None（`database.py:1027-1111`）。有鎖的欄位只在 FC 查詢成功時才會被剔除；查詢失敗只記 debug 就繼續（`:1105-1106`） |
| 純出版品政策 | 會（預期行為） |
| `backfill_locations.py` 與 `_oneoff_*` | 手動執行，直接寫 |

事實 3 的「2026-09-13 03:15 UTC 清成空白」不在每日排程時間（`scraper.yml:6` 是 00:00 UTC）。而且其中 7 筆有鎖仍被清空，表示那條路徑無視 FC。計畫沒有找出是哪個動作。

影響：PR 2「同名複製不再寫鎖」與 PR 4「不寫鎖」的**結論可以保留**，但理由要改。正確的理由是「會被 force_rescrape 等路徑清掉，但每天的 `enrich_addresses` 會把即將舉辦的事件補回來；過去的活動不補」，不是「不會被清掉」。另外要開一張 issue 查 2026-09-13 的動作（Actions 日誌、管理介面的批次 force），否則它還可能再發生。

**M2：JSON 引號鎖會把引號寫進事件地址；PR 4 的 `fc_mismatch` 會把它當成 street 寫入。**

- `enrich_addresses.py:215` 寫入 `json.dumps(addr)`，值是 `"東京都…"`，含字面上的引號。
- annotator 還原 FC 時直接用文字值（`annotator.py:3831-3843`）；`location_address` 不在 `_NON_TEXT_FC_FIELDS`（`:2423-2431`），所以不會解碼。
- `database._field_correction_value`（`database.py:64-82`）同樣不解碼。
- 推論：有複製鎖、之後又被重新 annotate 的事件，地址會帶引號。**未連 production 查證**。需要一次唯讀計數：`location_address LIKE '"%"'` 的事件數，以及 `field_name='location_address' AND corrected_value LIKE '"%'` 的 FC 數。
- 實測 `grade_address('"東京都港区虎ノ門1-1-12"') == "street"`，所以 PR 4 的 `fc_mismatch`（「鎖定值是 street 級」→ 把事件寫成鎖定值）會原樣寫進引號。PR 2 的共識比對也會把帶引號與不帶引號的寫法當成兩個鍵，然後判定「不猜」。

修訂：

- `address_key()` 與 planner 讀 FC 值時先 JSON 解碼。
- PR 2 停止寫鎖的同時，稽核加上述兩個計數。
- 若 production 確有帶引號的事件地址，另開 bug issue。修正 annotator 與 database 的還原邏輯屬 annotator 變更，要列 Guard。

**M3：PR 4 的傳播只到即將舉辦的事件，計畫沒有量它能移動多少指標。**

「事件只透過 `enrich_addresses` 的新步驟取用」，而 `enrich_addresses` 的候選只有即將舉辦的事件（`:77`），還會跳過有鎖的事件（`:170-189`）。所以 `venue_backfill` 對過去的活動沒有效果，對有鎖的即將舉辦事件也沒有效果。

修訂：

- 拆成兩個 PR：**4a** 是唯讀 planner，不含 migration，輸出「每個 `venue_backfill` 場館實際能寫到幾筆即將舉辦事件（扣掉有鎖的）」。**4b** 是 migration 加傳播步驟加 apply，等 4a 的數字超過明訂門檻才做（建議：能讓即將舉辦的街道級比率至少提升 3 個百分點）。
- 另外評估一個替代方案，可以省掉 migration：把核准過的機器驗證地址存成 repo 內的 JSON（附出處 URL 與日期），由 `enrich_addresses` 讀取。人工核准就等於 PR 合併，回滾就是 `git revert`，也不必寫 `venues.address`。這會推翻 proposal「出處欄位在 `venues`」的決定，要寫進 proposal 的決定紀錄。

**M4：PR 4 的傳播步驟若在 migration 套用前上線，會讓每日 job 的後段全部跳過。**

`scraper.yml:99-106` 的「Enrich venue addresses」步驟**沒有** `continue-on-error`。查不存在的 `address_source` 欄位會丟例外，之後沒有 `if: always()` 的步驟（`backfill_location_prefectures`、geocode、第二次 merger、auto_qa）全部不會執行。計畫沒寫這個步驟放在哪個 PR。

修訂：傳播步驟只能放在 migration 套用後的 PR（4b）。或者欄位不存在時記一行 warning 就跳過，並用測試鎖住。

**M5：`merge_duplicate` 與 `attach_authoritative` 會重犯舊工具已經處理過的錯。**

- 舊工具把 `e87b461e` 底下的事件分成 migrate、attach、historical、**false**、multi 五組（`_oneoff_repair_authoritative_venues.py:90-123`）。「false」組是錯掛的、不在台湾文化センター的活動。計畫寫「3 個非權威重複場館的事件改掛權威場館」，整批改掛會把 false 組也掛上去。
- 計畫列的 ID 是 `e87b461e`、`bd8f93a6`、`20a97518`。舊工具與 `notes.md:80` 寫的是 `e87b461e` 與 `124ca4f6`。兩邊必須對齊並說明差異。
- 只改 `venue_id` 會讓事件的 `venue_id` 指向權威場館，名稱、地址、官網卻是別的值。

修訂：

- 重新擷取現況後，沿用舊工具的分組邏輯（每筆依地址、線上與否、多會場分類），不整批改掛。
- apply 要寫的欄位集合比照 `_apply_venue_registry`，並遵守 FC。
- 刪除殘樁另列一個動作，屬不可逆關卡。

**M6：PR 3 不該新寫 CAS 工具（第 5 題）。**

- 已有先例：`_oneoff_plan_tiff_venue_inserts.py`（#341，206 行）只產出 `venue_insert` 動作的 plan，交給既有引擎的 preview、`--capture`、`--apply` 執行（該檔 `:1-10`）。引擎本身已經具備：
  - 整列 CAS（`_venue_update`，`_oneoff_repair_authoritative_venues.py:2226-2269`，底層是 `qa_auto_fix.apply_cas_filter`，`qa_auto_fix.py:514-520`）；
  - manifest SHA-256 封存與驗證（`:1698-1728`）；
  - 唯讀 proxy（`ReadOnlyProxy`）；
  - 執行前確認 repo SHA 在 `origin/main`（`:1737`）；
  - journal 與 rollback；
  - 測試（`tests/test_authoritative_venue_repair.py`）。
- 「R1 隨原工具退場」指的是那份 70 個動作的計畫，以及其中 FC 狀態不一致的 `event_fc` 動作（`ONLINE_GRANT_EVENT_ID`）。PR 3 只有 `venue_update`，碰不到 R1。
- 這個解讀要寫進 PR 說明，讓使用者確認。若使用者認定引擎本身也退場，就把引擎裡的 CAS、封存與 proxy 抽成共用模組（例如 `scraper/cas_manifest.py`），不要第三次重寫。
- 注意：PR 4 的 `fc_mismatch` 正是 R1 那類「事件與 FC 不一致」的 before 狀態，rollback 會重現 R1。這是刪掉 `fc_mismatch` 的另一個理由（見第 6 段）。
- PR 3 還要補三點：
  1. 改了地址的場館（サロンシネマ、センチュリーシネマ），同一個動作要把 `latitude`／`longitude` 清空（見 M7）；
  2. 新增別名（r046）前，先檢查與所有權威場館的正式名稱與別名都不衝突。`_register` 遇到衝突會**把雙方的鍵都拒絕**（`venue_registry.py:23-42`）。可用舊工具的 `_fetch_venue_key_holder_ids`；
  3. 拿掉八丁座的「サロンシネマ」別名後，「サロンシネマ」由歧義變成可解析。用更新後的 snapshot 跑 `eval-venues`，前後數字寫進 PR。

**M7：PR 1 的場館座標回寫沒有使用者，而且會過期（第 4 題）。**

- 嚴或鬆：比對條件（權威、非多會場、正規化後地址相同；已實作為 `venue_matches_event`）不鬆。cache hit 也已受同一條件限制，這點比計畫文字更好。
- 問題在**過期**：`write_venue_coords` 只在座標都為空時寫入。センチュリーシネマ現址 `栄3-15-13` 是另一棟建物（`notes.md` 的 #339 對照表）。PR 1 如果先於 PR 3 apply 執行，場館會存下錯誤建物的座標，PR 3 改址之後也永遠不會被覆寫。
- 不一致：PR 2 對權威場館接受 `town` 級地址（公園、校園），PR 1 只定位 `street`，這些場館永遠沒有座標。
- 座標目前沒有任何消費者（`web/` 沒有讀取）。
- 修訂（擇一）：刪掉 `write_venue_coords` 與場館 cache，場館座標留給 #372，等有消費者時再對權威場館地址直接定位一次（58 次 API 呼叫）；或者保留，但 PR 3 必須清空改址場館的座標。建議前者：少一條寫 `venues` 的路徑。

**M8：`address_key()` 的規則會誤切，必須復用量尺的番地判定。**

「把 `丁目`／`番地`／`番`／`号`／`の` 與各種連字號統一成 `-`，並截到番地為止」，套在 `丸の内`（變成 `丸-内`）、`三番町`、`麻布十番`、`一番町` 上，會把町名的一部分當成番地分隔，截斷點也會錯。critique-1 的 M1 已經在量尺裡修過同一類問題。

修訂：先用 `address_quality.normalize_address` 與 `_STREET_RES`／`_BARE_LOT_RE` 找出番地的範圍，只在「數字＋記號＋數字」的位置替換記號。測試至少涵蓋 `丸の内三丁目5番1号`、`三番町`、`一番町3-11-15`、`1の14の30`、`3-1-1` 對 `3丁目1-1`。

**M9：PR 5 的「忽略・與空白」會破壞上層場館加子空間的判定。**

`lookup_venue_for_location` 用 `_PARENT_SUFFIX_BOUNDARIES`（含空白與「・」，`venue_registry.py:20`）判斷「場館名＋分隔字元＋子空間」（`:148-160`）。如果正規化把分隔字元刪掉，`東京芸術劇場 シアターイースト` 這類標籤就找不到上層場館，召回反而下降，`preserve_label` 也會失效。另外，NFKC 可能讓兩個原本不同的鍵變成同一個，`_register` 會把兩邊都拒絕，原本正確的命中就消失了。

修訂：

- 精確比對時用正規化後的鍵，上層場館的分隔判定保留原字串。
- 加一個測試：用 `tests/golden/venue_registry_snapshot.json` 比較正規化前後的歧義鍵數，數字不得增加。
- 註明 `database._populate_entity_fks` 在資料庫端做精確比對（`database.py:356-372`），不受 PR 5 影響，入庫與 annotator 的命中率會不同。這是已知差異，不算回歸。

**M10：PR 2「新舊候選差異」要在 FC skip 之後計算。**

見 B1：只算量尺差異的話，數字會高估實際能寫的筆數。PR 說明要分開列「新增候選」與「其中被鎖擋住」。

### Minor

- **m1**：事實 3 的數字對不上：67 筆空白 = 60 筆（04-28 匯入）+「另一批 65 筆」？兩組必然重疊，要寫清楚。另外 `updated_at` 相同只能證明同一個動作碰過這些列，不能證明是那個動作把地址清空。
- **m2**：`tasks.md` Phase B 寫的是「每週摘要加場地缺口清單；`daily_quality_metrics` 加街道級比率」。plan-2 改成每日 artifact，也不改 `daily_quality_metrics`。合併前同步 `tasks.md` 的里程碑文字。
- **m3**：`audit_venue_addresses.py:41` 依賴 `enrich_addresses.is_vague`。PR 2 要保留 `is_vague`（標成舊規則，只供比較），否則稽核會壞，「新舊差異」也算不出來。
- **m4**：PR 2 的稽核步驟要加 `if: always()`（比照 `scraper.yml:183-201` 的 Daily quality metrics）。`enrich_addresses` 失敗時，最需要這份報告。
- **m5**：`backfill_entities.py:183-206` 重跑時會以 `canonical_name_ja` upsert，覆寫**權威場館**的 `aliases`，也會把事件的 `venue_id` 連到機器驗證列。它不在 workflow 裡，但要加防呆（有權威列或 `address_source` 非空時拒絕執行），或在檔頭標明退役。這是第 3 題唯一的漏洞。其他讀 `venues` 的路徑都只讀權威列：`venue_registry.py:57`、`database.py:363-381` 與 `:406-411`、`qa_auto_fix` 經 `lookup_venue_for_location`；`web/` 不讀 `venues`；`geocode_events` 在 PR 1 之後只讀座標。
- **m6**：機器驗證列之後被升成權威場館時（例如 #732），`address_source` 必須同時改成 `manual` 或重新驗證。新權威場館必須有地址，或者標成 `is_multi_venue`。否則 annotator 會把命中事件的地址寫成 None（`annotator.py:2856`、`:2870`）。
- **m7**：PR 1 沒有失敗的負向快取，每天會重試同一批定位失敗的即將舉辦事件。數量小，可以接受，但要在 PR 說明註明。
- **m8**：`enrich_location.py:35`、`:127` 也呼叫 `registry_address`。PR 2 放寬權威場館接受的等級，會同時改變這個 GPT 步驟的行為，範圍要列進 PR 2。
- **m9**：PR 4 `venue_backfill` 的證據「旗下或同名事件」裡，「旗下」要刪掉。非權威列的 `venue_id` 來自模糊聚類（`backfill_entities.py:40`、`:199-206`），只能計同名事件。

### Guard 檢查

| Guard | 是否觸及 | 計畫是否遵守 |
|---|---|---|
| Manual Translation Fix Persistence（FC 鎖） | 是：B1、M2 | 否：沒有分析自動鎖鎖住場館值，以及 JSON 引號還原的問題 |
| Entity Normalization Guard | 是：PR 4、PR 5 | 部分：見 M5、M9、m5 |
| Venue QA Skip Source Registration Guard | 是 | 遵守：`detect()` 不變 |
| auto_qa False Positive Guard | 否 | 不新增逐事件類型，符合 |
| Sub-Venue Parent Address Guard | 是：`address_key`、PR 5 | 部分：見 M8、M9 |
| Category／Event Form／i18n／SCRAPERS List | 否 | 不適用 |

## 5. 既有 Component 復用建議

| 需求 | 復用 |
|---|---|
| PR 3 的 CAS、manifest、rollback | 交給 `_oneoff_repair_authoritative_venues.py` 引擎的 `--plan` 執行，照 `_oneoff_plan_tiff_venue_inserts.py` 的寫法；或把 `_venue_update`、`seal_manifest`、`verify_manifest`、`ReadOnlyProxy`、`verify_repo_sha_on_origin_main` 抽成共用模組 |
| CAS 條件 | `qa_auto_fix.apply_cas_filter`（`:514-520`） |
| 別名衝突檢查 | `_oneoff_repair_authoritative_venues._fetch_venue_key_holder_ids` |
| TCC 殘樁的事件分組 | 同檔 `:90-123` 的分組邏輯（依現況重新擷取） |
| 地址比較鍵 | `address_quality.normalize_address` 與番地判定的正規表示式（M8） |
| 排除 LLM 填的地址 | `llm_cache.seen(sb, "location_extract", …)`，outcome 為 `applied` |
| 分頁、出版品排除 | `db_paging.fetch_all`、`publication_rules.partition_pure_publications` |

復用率：PR 3 依原計畫是 🔴 重造輪子；改成 planner 後是 🟢。其餘 🟡。

## 6. 建議更新後的計畫（diff 點）

### 對七個指定問題的回答

1. **事實 1、2**：事實 1 只在 annotator 路徑成立，force_rescrape 與未辨識的 09-13 動作會清空（M1）。事實 2 有兩處錯：腳本鎖至少有三種來源，而且自動鎖對解析到權威場館的事件鎖的是場館值（B1、B2）。PR 2 與 PR 4 的「不寫鎖」結論仍然可行，因為即將舉辦的事件每天會補回來。但「排除複本即獨立」這個判定必須重做。
2. **時間差判別**：可用，但要逐欄位比、門檻 ≤ 60 秒。JSON 引號是更可靠的確定性判別。兩者都比不上「正向認定 scraper 原值」（B2）。
3. **非權威列是否會被當成權威**：正常解析路徑不會。漏洞在 `backfill_entities.py` 重跑（m5）、升成權威時沒有重設出處（m6）、傳播步驟在 migration 前上線（M4）。
4. **PR 1 座標規則**：比對條件不鬆，但場館座標會過期，而且沒有使用者。建議刪掉場館座標回寫（M7）。
5. **PR 3**：復用既有引擎，不新寫（M6）。
6. **刪、合、延**：見下表。五個 PR 改成四個 PR 加一個條件式 PR。
7. **人類關卡**：見最後一張表。

### PR 調整

| PR | 處置 |
|---|---|
| PR 1 | 保留已實作的部分（停寫地址、拿掉鎖查詢、單筆例外）。刪掉場館座標回寫，或者由 PR 3 清座標（M7）。排序與 street 限制可以留，但不再擴大 |
| PR 2 | 保留，是最有價值的一個 PR。共識規則改成 B2 的正向認定，並加上「2 個來源或原文逐字出現」。理由改寫（M1）。保留 `is_vague`（m3）。稽核加 B1、M2、M10 的數字。步驟加 `if: always()`（m4）。列出 `enrich_location` 連帶受影響（m8） |
| 新增（併入 PR 2，或獨立的小 PR） | `_auto_lock_location` 只鎖 scraper 原值（B1 根因） |
| PR 3 | 改成既有引擎的 planner（M6）。補座標清空、別名衝突檢查、`eval-venues` 前後比較。改寫「事件會更新」的說明（B1） |
| PR 4 | 拆開。**4a**：唯讀 planner，沒有 migration。類別為 `venue_backfill`（只計同名事件，m9；要算實際能寫到的即將舉辦筆數，M3）、`attach_authoritative` 與 `merge_duplicate`（沿用舊工具的分組，M5）、`stale_auto_locks`（新增，B1）、`copy_locks`、`org_as_venue`。**刪除 `fc_mismatch`**：8 筆、7 筆是過去的活動，鎖的值可能帶 JSON 引號（M2），rollback 還會重現 R1。稽核只保留計數。**4b**：migration、傳播步驟、apply，等 4a 的數字過門檻才開（M3、M4），並一併評估 repo JSON 替代方案 |
| PR 5 | 保留。修 M9 的分隔字元與碰撞問題 |

### 順序

PR 1（改好）→ PR 2 與 B1 根因 → PR 3 planner（apply 時一併清座標）→ PR 5 → PR 4a → 依 4a 的數字決定 4b。PR 3 apply 與 PR 1 不是彼此獨立的（M7），計畫的「彼此獨立」要改。

### 人類關卡

| 項目 | 判定 |
|---|---|
| 合併 PR 1–5 | 列了 |
| PR 2 合併卡片 | **要補說明**：合併後每天自動寫 production 的範圍會改變（候選加入 `town`、權威場館接受 `town`） |
| PR 3 `--apply` | 列了 |
| PR 3 `--rollback` | **漏列**；同屬 production 寫入 |
| migration 111 | 列了。要註明 migration 內含資料更新（既有權威場館標 `manual`） |
| PR 4 apply | 列了 |
| 刪除重複殘樁 | **漏列**；屬不可逆動作，要獨立一列 |
| `stale_auto_locks`、`copy_locks` 的解鎖 | **漏列**；屬 production 寫入 |
| PR 3 復用引擎時「R1 隨原工具退場」的解讀 | **新增**；請使用者確認（M6） |
| 新權威場館（#732） | 列了。要補：升格時出處重設，地址必須非空或標多會場（m6） |
| 團體名、連鎖店、串流 | 列了 |
| 2026-09-13 清空動作的查明 | 不是關卡，開 issue 即可 |

### 建議下一步

- 回 Architect 修改計畫：請依本批評修改 `docs/specs/active/venue-ground-truth/plan-2.md`。重點是 B1、B2，PR 4 拆成 4a／4b，PR 3 改成引擎 planner；並同步 `ttr-geocode-fix-worktree`（commit `aec8060`）與 `ttr-venue-phase-b-worktree` 的已實作部分。
- 修訂前要先做的唯讀查證（沒連 production，所以都未驗證）：
  1. 帶 JSON 引號的事件地址與 FC 鎖各有幾筆（M2）；
  2. #732 那 40 筆有沒有自動鎖（B1）；
  3. 有權威 `venue_id`、地址被鎖、鎖值與場館現址不同的事件數（B1）；
  4. 2026-09-13 03:15 UTC 的 Actions 或管理介面紀錄（M1）。

## 本次批評自身的限制

- 沒有連 production，B1、M2 的實際規模都未驗證。B1 的程式路徑是確定的；受影響的筆數取決於事件入庫的時間，以及當時該場館是否已經是權威場館。
- `gh` 在本環境無法取得 PR 清單，所以沒有核對 open issue 的優先順序。第 3 段只引用 repo 內的文件。
