# Plan Critique：venue-ground-truth（場地 ground truth 生命週期與地址 QA）

> 評審者：Claude plan-critic（與撰寫者同一模型家族；Codex 在本環境無法啟動）
> 評審日期：2026-11-22。唯讀；未修改任何檔案，未連 production。
> 評審對象：`docs/specs/active/venue-ground-truth/` 的 `proposal.md`、`tasks.md`、`notes.md`，以及 worktree 內已存在、尚未提交的草稿 `scraper/address_quality.py`。

## 查證範圍與限制

- production 數字（1,668／484／329／111／429 等）**未查證**：本次不連 production。以下所有批評都以 repo 內的程式與文件為證據。
- 量尺草稿已實際執行：我用 160 個左右的日本地址寫法呼叫 `grade_address()`，下面列的誤判都是實測結果，不是推論。
- `git status` 顯示 `scraper/address_quality.py` 已存在但沒有測試檔、沒有 `audit_venue_addresses.py`。草稿 docstring 寫「Known limits are listed in the tests」（`address_quality.py:17`），測試檔不存在。

## 結論（先講）

**修訂後進行。** 第一個 PR 只做 Phase A 的範圍正確，但必須先修 2 個 Blocker（A1、A2）再記基準，否則基準數字是錯的。Phase D、E 有 2 個 Blocker（D1、D2），不擋第一個 PR，但必須在 Phase D 開工前回 Architect 修訂，而且其中一項要使用者決定。Phase F 與 Phase G 的「annotator 即時建候選」應從本 spec 刪除。

| 編號 | 嚴重度 | 一句話 |
|---|---|---|
| A1 | Blocker（第一個 PR） | 量尺先判「非日本」再看日本地址，`…虎ノ門1-1-12 台湾文化センター` 被判成 `non_japan` |
| A2 | Blocker（第一個 PR） | `street` 的定義在 proposal、notes 的 SQL、草稿程式三處不同；驗收目標的基準值用的是另一把尺 |
| D1 | Blocker（Phase D 前） | 「機器驗證地址寫入事件」沒有定義路徑；現有路徑全部只認權威場館，照字面實作會繞過 fail closed |
| D2 | Blocker（Phase D 前） | 事件共識不是獨立證據：一筆事件也算「一致」，而且被複製並鎖定的地址會自己投自己一票 |
| M1–M9 | Major | 見下 |
| m1–m8 | Minor | 見下 |

---

## 1. 商業主軸對齊

- 對應主軸第 1 項「資料完整性與正確性」。實體活動沒有可用地址，使用者到不了現場，價值明確。
- 沒有偏離專案使命。
- 評分：🟢 對齊。

## 2. 複雜度 vs 價值

| 範圍 | 複雜度 | 依據 |
|---|---|---|
| Phase A 單獨 | low | 2 個新檔加 1 個測試檔，無 migration，不改既有行為 |
| 整份 spec（A–G） | very-high | migration（+1）、跨 8 個以上檔案（+1）、新增付費呼叫路徑 web search（+1）、動 annotator（+1）、觸發 3 個 Guard（+1）、新增 2 個 `auto_qa_*` 類型與其 5 處同步點（+1）。合計 6 級 |

業務價值：high，但集中度很高，計畫沒有利用這一點：

- `notes.md:23` 列的不合格來源中，`note_creators` 79、`prtimes` 56、`google_news_rss` 43，合計 178 筆，佔 484 筆的 37%。這三個來源在 `scraper/auto_qa.py:1041-1043` 被宣告為「本質沒有實體場地」。見 M5。
- `kokuchpro` 80 筆是單一來源、單一原因。見 M7。
- 兩項合計 258 筆，超過缺口的一半，都不需要生命週期、migration 或 web search。

**比值警示**：整份 spec 的複雜度高於目前證據支持的價值。Phase A 的稽核結果出來之前，D 以後的設計不應定案。

## 3. 優先順序提醒（Anti-Rabbit-Hole）

- 🔴 **「為單一問題設計通用機制」**：三狀態生命週期、5 個新欄位、負向快取、四階修復階梯，是在還不知道缺口組成時設計的。`proposal.md:100` 自己說「先確認量尺的精度，再讓它決定」，那麼 D 以後的設計現在就寫死是順序顛倒。
- 🟡 **相鄰先例的結論相反**：`docs/specs/active/people-ground-truth/proposal.md:34` 明寫第一版**不**把現有事件的值寫進 `people`，理由是 `:47-49` 查到 732 筆鎖定全部是腳本產物、沒有一筆人工確認，回填延後到 #408。本 spec 把同性質的「事件共識回填」排成修復階梯第一步（`proposal.md:81`），卻沒有做同樣的來源盤點。見 D2。
- 🟡 現有的每日 geocoding 步驟疑似每天失敗而無人知道（M6）。這是已上線管線的缺陷，優先於任何新 Phase。
- 評分：Phase A 🟢；Phase D 以後 🟡 可延後，等 Phase A 數字。

## 4. 全站架構整合分析

### Blocker A1：量尺判定順序錯，台灣相關字會把日本地址判成非日本

證據：`scraper/address_quality.py:152-157` 先判 URL／線上，再判 `_NON_JAPAN_RE`（`:56-61`，含 `台湾`、`新竹`、`高雄`、`香港`），之後才看都道府縣與番地。實測：

| 輸入 | 實際 | 應為 |
|---|---|---|
| 東京都港区虎ノ門1-1-12 台湾文化センター | non_japan | street |
| 東京都港区白金台5-20-2 台北駐日経済文化代表処 | non_japan | street |
| 東京都豊島区西池袋1-8-26 台湾料理 新竹 | non_japan | street |
| 京都市右京区梅ケ畑高雄町5 | non_japan | street |
| 神奈川県横浜市中区山下町 横浜中華街 香港路 | non_japan | town |
| 東京都港区六本木6-10-1（オンライン配信あり） | not_address | street |

本專案的活動幾乎都帶「台湾」「台北」字樣，這是最常見的輸入，不是邊角案例。`non_japan` 在稽核裡會被當成「不適用」，等於把最核心的場館從母體移除。

修訂：有日本都道府縣或「市＋区」證據時，日本判定優先；`_NON_JAPAN_RE` 只在沒有任何日本行政區證據時生效。線上判定只在整個字串就是線上標記時成立（比照 `scraper/auto_qa.py:149` 的 `_ONLINE_ADDR_RE` 用錨定）。

### Blocker A2：`street` 有三個定義，驗收基準用的不是 Phase A 的尺

| 位置 | 定義 | 「新宿3丁目」 | 「〒105-0001」 | 「東京大学駒場キャンパス18号館」 |
|---|---|---|---|---|
| `proposal.md:58` | 有番地（丁目／番／号，或 1-2-3） | street | 未定義 | 未定義 |
| `notes.md:7` 的 SQL | 含數字且符合 `丁目\|番\|号\|數字-數字` | street | **street** | **street** |
| `address_quality.py:8-10,79,177` | 丁目後面還要有番號 | town | not_address | not_address |

SQL 規則另外漏掉漢數字（`丸の内三丁目五番一号`）、京都無連字號番地（`天性寺前町523`）、`1の14の30`（實測全部為否）。所以 484、329、111 三個數字既有高估也有低估。

問題在 `tasks.md:15-16`：驗收目標「由 76% 提到 90%」「由 71% 提到 95%」的起點是 SQL 規則算的，終點卻規定用稽核腳本的定義量。兩把尺不同，這個目標無法驗收。

修訂：
1. proposal 的等級表改成與程式一致的單一定義，明寫「只有丁目、沒有番號是 `town`」。
2. `tasks.md` 的 76%／71% 改成「Phase A 稽核腳本量到的基準值」，Phase A 合併後回填實數，目標值同時重訂。
3. `notes.md` 的 111（可零成本回填場館數）標成「舊規則估計，上限」。

### Blocker D1：機器驗證地址「寫入事件」沒有路徑，照字面做會繞過 fail closed

`proposal.md:74` 說機器驗證的地址可以寫入事件，`:12` 說「事件經 `venue_id` 繼承」。現況四條場館到事件的路徑全部只認權威場館：

- `scraper/venue_registry.py:51-58`：快取只載入 `.eq("is_authoritative", True)`。
- `scraper/database.py:363-381`：upsert 時的場館比對同樣加這個條件，歧義時留空（`:399-404`）。
- `scraper/annotator.py:2841-2862`：經 `lookup_venue_for_location()` 寫入地址、都道府縣、官網、`venue_id`、正式名稱。
- `scraper/enrich_addresses.py:90-99`：`registry_address()` 也走同一個 lookup。

所以 Engineer 只有兩種實作法，計畫都沒有選：

1. **把機器驗證場館放進 registry 快取**：直接破壞 fail closed。`docs/evaluation/venues/README.md:46` 明訂錯配比漏判嚴重，CI 門檻是錯配 0；該 eval 用的是凍結的權威場館快照（`:14`），**不會**偵測到這個破壞。同名鍵衝突時 `_register()`（`venue_registry.py:23-42`）還會把權威場館的鍵一起拒絕，機器列能讓權威場館失效。
2. **用 `venue_id` 繼承**：非權威場館的 `venue_id` 連結不是 fail closed 解析產生的，而是 `scraper/backfill_entities.py:40,200-207` 以 SequenceMatcher ≥ 0.92 模糊聚類後整批寫入。實測「TOHOシネマズ 日比谷 スクリーン12」與「…スクリーン13」0.944、「早稲田大学早稲田キャンパス3号館」與「…8号館」0.938 會併成同一場館。#371 已記錄後果：團體掛 38 筆事件、其中至少一筆實際在 ユーロスペース；另有 3 個重複殘樁佔用權威場館的事件。

修訂（Phase D 開工前必須寫進 proposal）：
- 明訂「機器驗證場館**永不**進入 `venue_registry` 的快取與 `database.py` 的比對」，並加一個測試鎖住。
- 另立獨立函式處理機器驗證地址，**只寫 `location_address` 一欄**，不改名稱、都道府縣、官網、營業時間、`venue_id`。
- 事件是否適用，以 `location_name` 與場館 `canonical_name_ja` NFKC 後完全相同為準，不以 `venue_id` 為準。
- 權威場館的地址即使量尺判為 `town`（公園、無番地的校園），仍視為合格：人工確認高於量尺。見 M4。

### Blocker D2：事件共識不是獨立證據

1. **一筆也算一致**。`scraper/enrich_addresses.py:118` 的條件是 `len(addrs) == 1`，只有一筆事件有地址也成立。`proposal.md:81` 的「一致」沒有定義最少幾筆、幾個來源。
2. **複製品自己投票**。現行 sibling 路徑把地址複製到其他事件後鎖進 `field_corrections`（`enrich_addresses.py:208-216`）。五筆事件地址相同，可以是一筆原始值加四筆複製。
3. **原始值可能是 LLM 產物**。`.github/skills/agents/engineer/history.md:3881` 記錄早期 `enrich_addresses.py` 用 gpt-4o-mini 查地址後寫入；`:1022` 記錄 `gpt-4o-search-preview` 的結果。`scraper/annotator.py:1205` 的 prompt 自己寫著 LLM 的地址知識不可靠、會產生看似合理但錯誤的番地。這些值現在都在 `events.location_address` 裡，無法從欄位分辨。
4. **現行「具體」的門檻比 `street` 低**。`is_vague()`（`enrich_addresses.py:51-57`）只擋「以都道府県市区結尾」的字串；`東京都千代田区神田神保町`、`東京都港区六本木` 都算具體，可被複製並鎖定。
5. **同名不同館**。現行保護只有「同名有兩個不同地址就不猜」（`:105-106`）。連鎖店只有一家分店出現過時，這個保護無效。
6. **寫進重複殘樁會固化重複**。#371 第 2 類的 `e87b461e`「台湾文化センター」掛 19 筆事件，地址必然一致；回填會讓這個應該被合併掉的殘樁變成「有地址的機器驗證場館」。

修訂：
- 共識的最低條件寫進 proposal：至少 2 筆事件、來自至少 2 個不同 `source_name`，或 1 筆但地址字串逐字出現在該事件的 `raw_description`。
- 排除 `location_address` 有腳本鎖定的事件（`corrected_by IS NULL AND report_id IS NULL`，分類法沿用 `people-ground-truth/proposal.md:181-183`）。
- 排除名稱能解析或模糊比對到權威場館的殘樁；這類交給 #371。
- Phase D 的產出先只是 manifest，寫入照 `tasks.md:8` 交使用者核准。核准卡片必須逐場館列出證據筆數、來源數、是否出現在原文。

### Major

**M1：量尺會把不是番地的數字判成 `street`（錯在代價高的方向）。** 假的 `street` 會隱藏缺陷，也會成為 Phase D 的合格證據。實測：

| 輸入 | 實際 | 應為 | 原因 |
|---|---|---|---|
| 東京都千代田区三番町／二番町／一番町 | street | town | `:99,117` 把漢數字轉成 `3番町`，再被 `:86-88` 當成町名後的番號 |
| 宮城県仙台市青葉区一番町 | street | town | 同上（仙台市中心的地名） |
| 東京都港区麻布十番 | street | town | 轉成 `10番`，符合 `:80` 的字尾規則 |
| 愛知県名古屋市中区栄3／東京都港区南青山5 | street | town | 丁目的省略寫法被當番號 |
| 東京都渋谷区道玄坂 第2会場 | street | town | 「第2」 |
| 東京都江東区有明 東京ビッグサイト 東1ホール | street | town | 「東1」 |
| 東京都新宿区戸山 早稲田大学戸山キャンパス33号館3階第1会議室 | street | town | 「第1」 |
| 東京都千代田区 3331 Arts Chiyoda | street | region | 建物名裡的數字 |
| 東京都渋谷区 14:00-16:00／11/22-11/24 | street | region | `:82` 的連字號規則；`:74` 只去掉年月日 |

修訂：漢數字只在後面是「丁目、番地、番＋數字、号」時轉換，並排除「番町」「十番」；「町名＋數字」規則限定數字在字串結尾或後面是空白；雜訊清單加時間、斜線日期、「第N」。

**M2：線上／電視的排除規則有三套，notes 的基準用的是第四套。** `enrich_addresses.py:42`、`auto_qa.py:69-74`、`address_quality.py:63` 各一份；`notes.md:5` 的 SQL 再加 `BS|NHK`，會把「NHKホール」這種實體場館排除。annotator 對混合活動的規定是 `location_name = "場館 / オンライン"` 且要填實體地址（`scraper/annotator.py:1235`），四套規則都會把它排除。`proposal.md:25` 說「沿用現行行為」，但現行行為不只一個。
修訂：量尺只評地址字串；「這筆事件需不需要地址」另立一個函式，稽核報告把混合活動獨立列一桶。#364 的決定留給使用者，但 Phase A 要量出這一桶有多大。

**M3：「先確認量尺的精度」沒有方法。** 單元測試的案例是作者自己想的，量不出精度。
修訂：稽核腳本輸出「不重複地址字串＋等級」；Phase A 的完成條件加一條：分層抽樣（每等級至少 30 筆），由使用者抽查（這是 ground truth，屬人類關卡），假 `street` 比例低於明訂門檻才算通過。

**M4：Phase B 不是「改用量尺」，是行為變更，影響面沒有列。** 現行 `is_vague()` 把町名級地址當成具體。換成只認 `street` 之後：
- `enrich_addresses` 的候選擴大到所有町名級的未來活動。
- `registry_address()`（`enrich_addresses.py:97`）會拒絕地址沒有番地的權威場館（`東京都渋谷区代々木神園町`、`東京都台東区上野公園`、札幌的條丁目地址實測都是 `town`）。這些場館的事件永遠修不好，又會被新的 `auto_qa_vague_address` 每天舉報。
- `proposal.md:89` 新增逐事件的 `auto_qa_vague_address`，`:90` 又說場地層級的缺口不逐事件開報告。兩句互相矛盾。
- 新類型的同步點沒有列：`QA_TYPES`（`auto_qa.py:160`）、`_DETECT_TYPES`（`:1431-1437`）、`qa_heartbeat.py:69,85`、`guard_detections.py`、`qa_history_miner.py`。
- #111 顯示 `missing_address` 有 66% 被駁回且沒有 handler（`qa_heartbeat.py:85`）；`notes.md:25` 的歷史是確認 126、駁回 89、待處理 45。再加一個沒有 handler 的類型是複製同一個問題，違反 auto_qa False Positive Guard 第 4 點「寧可少報，不可誤報」（`.github/skills/agents/architect/SKILL.md:901-908`）。
修訂：Phase A 的稽核腳本加一個數字「`is_vague()` 為否但等級不是 `street` 的事件數」，這就是 Phase B 的影響面。Phase B 不新增逐事件類型，只做每週摘要的場地清單。`auto_qa_location_not_venue` 只保留一個確定性規則（`location_name` 等於 `organizer` 或命中 `organizers` 表），其餘刪除。

**M5：37% 的缺口落在專案已宣告「沒有實體場地」的來源，計畫沒有處理這個矛盾。** `notes.md:23` 自己指出 `note_creators`、`prtimes`、`google_news_rss` 在 `_NO_VENUE_QA_SOURCES`；Venue QA Skip Source Registration Guard（`architect/SKILL.md:2205-2218`）記錄了把這些來源納入場地 QA 的事故：待處理報告由 22 暴增到 506。計畫卻把它們算進分母，Phase G 還要替 `prtimes` 加地址欄契約。這三個來源算不算「實體場地事件」會讓 90% 的目標變成做不到或不用做。
修訂：這是「活動範圍判斷」，屬人類關卡，加進「需要使用者決定」。稽核腳本必須分開報兩個比率（含與不含這 6 個來源）。

**M6：現有的 geocoding 回寫是未受管控的 `venues.address` 寫入者，而且疑似每天失敗。**
- `scraper/geocode_events.py:140-170` 的 `_opportunistic_venue_backfill()` 會把事件的 `location_address` 原樣寫進 `venues.address`（只要該欄為空），不看等級、不看是否權威，每天執行（`.github/workflows/scraper.yml:115-122`）。`proposal.md:74` 的「只能被等級相同或更高的證據覆蓋」管不到它。
- 它的鎖定檢查（`geocode_events.py:128-137`）查 `field_corrections.source_id`。這個欄位在 `supabase/migrations/038b_field_corrections.sql:12-20` 與之後的 040、060、080 都不存在；該表以 `event_id` 為鍵，沒有場館層級的鎖。查詢會出錯，例外沒有被接住，而該步驟是 `continue-on-error: true`（`scraper.yml:122`）。這與 #372「429 個場館 0 筆座標、只有 30 筆事件有座標」的現象吻合。**我沒有連 production 確認**，需要一次唯讀檢查（Actions 日誌或 `information_schema.columns`）。
- 推論：`proposal.md:33` 把「全部沒有座標」當成背景事實，Phase F 假設 geocoding 管線能用。兩者都不成立。
修訂：另開一張 bug issue，不放進本 spec。Phase D 之前必須先讓這個函式停止寫 `venues.address`。

**M7：kokuchpro 的描述與程式不符，最高報酬的一步被排在最後。** `proposal.md:95` 說 kokuchpro「該站有 hCard 地址」，暗示還沒抓。實際上 `scraper/sources/kokuchpro.py:308-321` 已經在抓 `.adr`，`:264-265` 寫入 `location_address`。100 筆中 80 筆不合格代表原因在別處：hCard 只有都道府縣、`_normalize_online()`（`:96-100,270-271`）把地址整個換成「オンライン」、或被 annotator 的 DEFAULT-NULL 規則（`annotator.py:1205`）清空。
修訂：把「查明 kokuchpro 80 筆的原因」從 Phase G 移到 Phase A 之後立刻做。這是一個來源、80 筆、不需要 migration。

**M8：Phase 順序。**
- Phase D 寫 `venues.address` 排在 Phase E 的 migration 之前，寫入時沒有 `address_status`、`address_source` 可填。之後無法分辨哪些地址是機器回填，也無法回滾。出處欄位必須先於任何 `venues.address` 的機器寫入。
- Phase C 把 #369／#482 列為前置。#482 明寫這兩筆 alias 修正屬於 #339 暫停中的 6 筆 update。`proposal.md:104` 又說使用者決定前不碰 #339。結果是 Phase D 被一個未決的使用者決定卡住，計畫沒有講明。這兩個廣島場館與共識回填無關，Phase D 排除這兩個名稱即可，不必當前置。
- #371 第 2 類（重複殘樁）確實必須先於 Phase D，理由見 D2 第 6 點。這個順序是對的。
- #366 的原條件是先扣掉 #370 修好後能命中的筆數，Phase E 排在 C 之後符合。

**M9：「不鎖 `field_corrections`」與現行設計的理由衝突，既有鎖定也沒有處理。** 現行 sibling 路徑鎖定的理由寫在 `enrich_addresses.py:208-210`：不鎖的話重新 annotate 會把地址清空。機器驗證地址若不鎖又不經 annotator 的場館階段，會每天被清空再補回。反過來，已經被 sibling 路徑鎖住的事件收不到之後修正的場館地址（`engineer/history.md:1025`：鎖定會完全擋住 `enrich_addresses`）。
修訂：proposal 要回答「不鎖的地址如何撐過重新 annotate」；Phase D 的 planner 要列出既有的腳本鎖定筆數。解鎖是 production 寫入，交使用者核准。

### Guard 檢查

| Guard | 是否觸及 | 計畫是否遵守 |
|---|---|---|
| Venue QA Skip Source Registration Guard | 是 | 否，見 M5；第 4 點要求收緊 detector 必須直接跑 `detect()` 做 before/after，Phase B 沒有列 |
| auto_qa False Positive Guard | 是 | 否，見 M4 |
| Entity Normalization Guard | 是 | 部分；`venue_id` 的來源見 D1 |
| Sub-Venue Parent Address Guard | 是 | 未提；共識回填遇到「場館＋子空間」標籤時要用母場館地址 |
| Category／Event Form／i18n Guard | 否 | 不適用 |

## 5. 既有 Component 復用建議

- `scraper/db_paging.py` 的 `fetch_all`、`scraper/publication_rules.py` 的 `partition_pure_publications`：稽核腳本直接用，不要重寫分頁與出版品排除。
- `scraper/backfill_location_prefectures.py` 的 `extract_prefecture`（`:330-332` 有自測）：量尺草稿另建了一份 47 都道府縣清單（`address_quality.py:34-45`），驗證閘的都道府縣比對要用既有函式，不要第三份。
- `scraper/auto_qa.py:149` 的 `_ONLINE_ADDR_RE`、`:145-147` 的 `_TAIWAN_ADDR_RE`：量尺的同類規則要與它們收斂成一份（Phase B），Phase A 至少加測試記錄差異。
- `scraper/eval_venues.py` 與 `scraper/tests/golden/`：量尺的人工抽查樣本放這裡，比照 `venues.jsonl`。
- `people-ground-truth` 的三種查詢狀態（found／not_found／error，error 不寫快取，`proposal.md:103-109`）：Phase E 若保留負向快取，必須沿用，否則暫時性錯誤會被記成查不到。計畫只說「沿用做法」，沒有列這條。
- 復用率：🟡 部分新增。量尺本身必須新增，合理。

## 6. 建議更新後的計畫

### 第一個 PR 的範圍：正確，補四點、減一點

範圍不算太小：沒有稽核腳本就無法驗證量尺，兩者不能再拆。也不算太大。修改點：

1. 修 A1、A2、M1 之後才記基準。
2. 加 M3 的抽查樣本與通過門檻。
3. 稽核腳本多輸出三個數字：M4 的 Phase B 影響面、M5 的兩種分母、M2 的混合活動桶。
4. PR 說明明寫 `is_vague()` 與 `grade_address()` 暫時並存，並用測試記錄兩者不一致的案例。
5. **減**：`proposal.md:67` 的「可零成本回填的場地數」拿掉或標成上限。它依賴尚未定義的共識規則（D2），放進第一個 PR 等於把 Phase D 的邏輯夾帶進來。

### 應刪除或移出的部分

| 項目 | 處置 | 理由 |
|---|---|---|
| Phase F（geocoding 寫回、定位 eval） | 移出，留在 #372 | 與本 spec 的目標（地址）無關；現有管線有 M6 的缺陷 |
| Phase G「annotator 即時建候選」 | 刪除 | 候選列除了名稱沒有任何資訊，等於量產 `notes.md:19` 抱怨的那 367 筆殘樁；稽核腳本隨時能算出同一份清單 |
| 階梯第 3 步「場地官網」 | 刪除 | `notes.md:19` 自己寫非權威場館有官網的是 0 筆；權威場館 62 筆中 58 筆已有地址。這一步的對象最多 4 筆 |
| `candidate` 狀態 | 刪除 | 等同「非權威且地址為空」，不需要欄位值 |
| `address_retry_after` | 延後 | 只有採用 web search 才需要，而那是未決的花錢決定 |
| `auto_qa_vague_address` | 刪除 | 見 M4 |

修訂後的順序：A（量尺、稽核、抽查）→ 查 kokuchpro → 使用者決定 M5 的範圍 → 出處欄位 migration → #371 第 2 類 → 共識回填 manifest → 依剩餘量決定 #366。

### 人類關卡檢查

| 項目 | 判定 |
|---|---|
| 權威一律人工（`proposal.md:48`） | 符合 |
| Phase D、migration、web search 標為需核准 | 符合 |
| #339 交使用者決定（`proposal.md:104`） | 符合，但要補上「Phase C 的 #369／#482 因此被卡住」這個後果 |
| 無場地來源是否納入（M5） | **漏列**，屬活動範圍判斷 |
| 量尺抽查樣本的標註（M3） | **漏列**，屬 ground truth |
| `auto_qa_location_not_venue` 判斷「是團體還是場館」 | 只能舉報，不得自動修正；proposal 沒有寫明 |
| spec 名稱叫 ground truth，內容大半是機器驗證值 | 文件要寫明機器驗證不是 ground truth，避免之後被當成已確認資料 |

### Minor

- **m1**：`proposal.md:18` 說 Phase A「直接回答」#111。#111 要的是駁回原因的型態分析與 confirmed 樣本的可查性，量尺基準不回答這個。稽核腳本加「被駁回報告依等級與來源的交叉表」，否則改寫這句。
- **m2**：`岐阜県高山市上三之町` 實測為 `region`。`address_quality.py:93-95` 把市後面的「町」當成自治體；只有郡後面的町村才是。兩者都不合格，影響小。
- **m3**：`東京都内`、`東京都内各所` 實測為 `town`，`全国`、`日本・東京` 為 `not_address`。應為 `region`，與現行 `VAGUE_ADDRESS_VALUES`（`enrich_addresses.py:44-48`）一致。
- **m4**：`銀座4-6-16`、`虎ノ門1-1-12`（沒有市區）實測為 `not_address`。它們是不完整的地址，不是非地址。定為 `town` 並寫進測試。
- **m5**：`東京都港区六本木6-10-1 / 大阪府大阪市北区梅田1-1-3` 實測為 `street`。含兩個都道府縣的字串要另外標記，不能當單一場館的證據。
- **m6**：六個等級混了兩個軸（精確度與種類）。不必改結構，但判定優先順序要寫進 docstring 並用測試鎖住。
- **m7**：`annotator.py:2845,2859-2860` 在權威場館地址為空時仍把 `location_address` 寫成 None。62 筆權威場館有 4 筆沒有地址（`notes.md:18`）；稽核腳本要列出這 4 筆是否都是 `is_multi_venue`。
- **m8**：札幌條丁目與京都通り名的等級是定義問題，見下表建議值。

### 應放進單元測試的案例

期望值是我的建議；標「現況錯」的是草稿目前判錯的。

| 類別 | 輸入 | 期望 | 草稿現況 |
|---|---|---|---|
| 標準 | 東京都港区虎ノ門1-1-12 | street | 對 |
| 全形 | 東京都港区虎ノ門１－１－１２ | street | 對 |
| 郵遞區號開頭 | 〒105-0001 東京都港区虎ノ門1-1-12 | street | 對 |
| 只有郵遞區號 | 〒105-0001 | not_address | 對 |
| 郵遞區號＋區 | 〒105-0001 東京都港区 | region | 對 |
| 漢數字番地 | 東京都千代田区丸の内三丁目五番一号 | street | 對 |
| 漢數字只到丁目 | 東京都千代田区丸の内三丁目 | town | 對 |
| 「の」寫法 | 東京都渋谷区神宮前1の14の30 | street | 對 |
| 番号 | 大阪市北区角田町8番7号 | street | 對 |
| 丁目＋番號 | 高知県高知市本町4丁目1-37 | street | 對 |
| 只到丁目 | 東京都新宿区新宿3丁目 | town | 對 |
| 地名含「番」 | 東京都千代田区三番町 | town | **現況錯** |
| 地名含「番」 | 宮城県仙台市青葉区一番町 | town | **現況錯** |
| 地名含「番」＋番地 | 仙台市青葉区一番町3-11-15 | street | 對 |
| 地名含「十番」 | 東京都港区麻布十番 | town | **現況錯** |
| 丁目省略 | 愛知県名古屋市中区栄3 | town | **現況錯** |
| 札幌條丁目 | 北海道札幌市中央区北1条西2丁目 | street（該市的街區單位；若定為 town 須在文件註明） | **現況錯**（town） |
| 札幌條丁目＋番 | 北海道札幌市中央区北1条西2丁目1 | street | 對 |
| 札幌只到條 | 札幌市中央区南1条西 | town | 對 |
| 京都通り名無番地 | 京都府京都市中京区烏丸通御池上ル | town | 對 |
| 京都通り名＋番地 | 京都市中京区寺町通三条上る天性寺前町523 | street | 對 |
| 京都地名撞台灣 | 京都市右京区梅ケ畑高雄町5 | street | **現況錯** |
| 大字 | 茨城県つくば市大字小野川16番地2 | street | 對 |
| 大字＋字 | 長野県北佐久郡軽井沢町大字長倉字横吹2140 | street | 對 |
| 大字無番地 | 長野県北佐久郡軽井沢町大字長倉 | town | 對 |
| 郡＋町 | 神奈川県足柄下郡箱根町 | region | 對 |
| 市＋町名 | 岐阜県高山市上三之町 | town | **現況錯**（region） |
| 市名含「市」 | 千葉県市川市／広島県廿日市市 | region | 對 |
| 只有建物 | 渋谷ヒカリエ 8F | not_address | 對 |
| 區＋建物 | 東京都千代田区 3331 Arts Chiyoda | region | **現況錯** |
| 番地＋建物樓層 | 東京都中央区日本橋室町3-2-1 COREDO室町テラス 2F | street | 對 |
| 校園無番地 | 東京都目黒区駒場 東京大学駒場キャンパス18号館 | town | 對 |
| 校園無番地＋教室號 | 東京都新宿区戸山 早稲田大学戸山キャンパス33号館3階第1会議室 | town | **現況錯** |
| 只有校園名 | 東京大学駒場キャンパス18号館 | not_address | 對 |
| 公園無番地 | 東京都渋谷区代々木神園町 | town | 對 |
| 會場編號 | 東京都渋谷区道玄坂 第2会場 | town | **現況錯** |
| 展館編號 | 東京都江東区有明 東京ビッグサイト 東1ホール | town | **現況錯** |
| 時間混入 | 東京都渋谷区 14:00-16:00 | region | **現況錯** |
| 日期混入 | 東京都渋谷区 11/22-11/24 | region | **現況錯** |
| 交通說明 | JR新宿駅東口徒歩5分 | not_address | 對 |
| 電話 | 090-1234-5678 | not_address | 對 |
| 區域泛稱 | 東京都内 | region | **現況錯** |
| 區域泛稱 | 全国 | region | **現況錯** |
| 多地並列 | 東京・大阪・福岡 | region | 對 |
| 缺市區 | 銀座4-6-16 | town | **現況錯** |
| 日本地址含台灣字 | 東京都港区虎ノ門1-1-12 台湾文化センター | street | **現況錯** |
| 日本地址含台灣字 | 東京都港区白金台5-20-2 台北駐日経済文化代表処 | street | **現況錯** |
| 台東区 | 東京都台東区上野公園7-7 | street | 對 |
| 台灣地址 | 台北市信義區松高路11號 | non_japan | 對 |
| 混合活動 | 東京都港区六本木6-10-1（オンライン配信あり） | street | **現況錯** |
| 純線上 | オンライン | not_address | 對 |
| 與場館名相同 | 誠品生活日本橋（location_name 相同） | not_address | 對 |
| 羅馬字 | 6-10-1 Roppongi, Minato-ku, Tokyo | street | 對 |
| 兩地並列 | 東京都港区六本木6-10-1 / 大阪府大阪市北区梅田1-1-3 | 不得作為單一場館證據 | **現況錯**（street） |
| 佔位字串 | null／未定／調整中 | empty／not_address | 對 |

### 需要使用者決定（建議補進 proposal）

1. `note_creators`、`prtimes`、`google_news_rss` 的事件算不算「需要地址的實體活動」。這決定目標值，也決定要不要做 Phase G 的 `prtimes`。
2. 量尺抽查樣本的確認方式與通過門檻。
3. 既有兩項：#339 的去向、web search 是否花錢。

### 給主對話的備註

- 本報告沒有使用記憶中的任何資料。
- 草稿 `scraper/address_quality.py` 尚未提交；A1 與 M1 的修正是程式層級，交 Engineer。
- M6（`geocode_events.py` 查不存在的欄位）是既有缺陷，與本 spec 是否進行無關，值得單獨開 issue。production 端是否真的沒有 `field_corrections.source_id`，我沒有確認。
