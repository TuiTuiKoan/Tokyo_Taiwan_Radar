---
slug: venue-ground-truth
title: 場地地址 QA 與場地 ground truth
status: active
branch: feat/venue-ground-truth
created: 2026-11-22
tags: [scraper, supabase, evaluation]
---

## What（做什麼）

把「有場地名、沒有有效詳細地址」納入 QA，並讓修好的地址以場地為單位累積，同一個場地不必每次重查。

分兩層，第二層要等第一層的數字才定案：

1. **量尺與稽核（Phase A，本 spec 第一個 PR）**：一把共用的地址量尺，一支唯讀稽核腳本，一份基準。
2. **修復（Phase B 以後）**：依稽核結果，由集中度最高、成本最低的缺口做起。場地層級的機器回填與生命週期欄位放在最後，設計在「後段設計（未定案）」一節，Phase A 的抽查通過且使用者做完決定後再修訂。

名詞：本 spec 的 **ground truth 只指使用者確認過的權威場館**（`venues.is_authoritative`）。腳本找到並通過檢查的地址叫「機器驗證」，不是 ground truth。

與既有工作線的關係：

| 既有項目 | 在本 spec 的位置 |
|---|---|
| issue #111：缺地址偵測的精度評估 | Phase A 提供量尺與各等級的數量；駁回原因的分析仍在 #111 |
| issue #366：是否加有上限的 web search | Phase E，依前面各步之後的剩餘量決定 |
| issue #370：registry 召回缺口 | 仍由該 issue 追蹤；#366 的原條件要求先扣掉它修好後能命中的筆數 |
| issue #371 第 2、3 類：重複殘樁、團體當場館 | Phase D 的前置 |
| issue #369、#482：八丁座／サロンシネマ alias 互撞 | 不是前置；Phase D 排除這兩個名稱。修正本身屬 #339 |
| issue #372：地址 → 座標 eval | 不在本 spec |
| issue #339：暫停中的 authoritative-venue-repair | 2026-11-22 使用者決定拆開：6 筆既有場館修正改由 #733 單獨做；活動修正與刪除重複場館併入本 spec 的 Phase D。#339 關閉 |
| issue #364：混合活動（實體加線上）是否補地址 | Phase A 量出有幾筆；決定仍在 #364 |

## Why（為什麼）

2026-11-22 的基準（`docs/evaluation/venues/2026-11-22-address-baseline.md`，production 唯讀匯出）：

- 應有實體場地的事件 1,387 筆，街道級地址 1,094 筆（80.9%），待補 258 筆。即將舉辦的 131 筆中待補 24 筆；近 60 天新進 395 筆中待補 61 筆。
- **QA 只抓空白。** 258 筆待補中空白 138 筆；另外 120 筆是「有填但不夠」（只到町名、只到行政區、或根本不是地址），`auto_qa_missing_address` 看不到。
- **兩處判定不一致。** `enrich_addresses.is_vague()` 把町名級地址當成具體；有 72 筆事件它認為不必補、量尺判為待補。
- **缺口很集中。** 258 筆落在 149 個場地名，前 10 個場地名就佔 96 筆。`kokuchpro` 一個來源佔 80 筆，幾乎都是地址空白。
- **登記簿只有兩種狀態。** `venues` 429 筆：62 筆權威（其中 58 筆有地址，沒有地址的 4 筆都是多會場影展），367 筆是沒有地址、沒有官網的殘樁。新場地只能靠一次性腳本加人工關卡進來（#339、#341）。
- **另有 323 筆在 auto_qa 排除場地 QA 的來源**（`note_creators`、`prtimes`、`google_news_rss`、`walkerplus`），其中 148 筆待補。使用者決定納入目標（見「使用者決定」），合併後的街道級比率是 75.1%。
- **修復路徑中斷。** web search 路徑在 #318 移除後沒有替代，查不到的事件只印在 log（#366 的評估已過期）。

## Non-Goals（不做什麼）

- 地圖模式與前台顯示。
- geocoding 寫回與定位 eval：留在 #372。現有 `geocode_events.py` 的缺陷另開 issue。
- 改寫 `venue_registry` 的解析規則：#370。
- 純出版、電視、純線上事件的地址：依既有政策不需要。
- 抽取段把區域填進場館欄的 prompt 修正：本 spec 只量測。
- 新增逐事件的模糊地址 QA 報告類型：`auto_qa_missing_address` 過去有 66% 被駁回且沒有修復 handler（#111），再加一個同性質的類型只會增加審核量。
- annotator 遇到新場地名時自動建場館列：只有名稱、沒有其他資訊的列就是現在那 367 筆殘樁；稽核腳本隨時能列出同一份清單。
- 自動把場地升為 `is_authoritative`：一律人工確認。
- 自動判斷「這個名稱是團體還是場館」並修正：只能列出，交人工。

## Design（設計摘要）

### 1. 地址量尺（Phase A）

`scraper/address_quality.py`，純函式、不連網。只評地址字串；「這筆事件需不需要地址」由稽核腳本另行判斷。

| 等級 | 定義 | 例 |
|---|---|---|
| `street` | 有番地：丁目後面還有番號、番地、号、`1-2-3`，或町名後直接接番號 | 東京都港区虎ノ門1-1-12、長野市権堂町2255 |
| `town` | 有町名或丁目，沒有番地；或有番地但缺市區 | 東京都新宿区新宿3丁目、神田神保町、銀座4-6-16 |
| `region` | 只到都道府縣、市、區、郡町村，或其並列與泛稱 | 福岡県福岡市、東京都内、東京・大阪 |
| `empty` | 空白或佔位字 | |
| `non_japan` | 日本以外的地址 | 台北市信義區… |
| `not_address` | 不是地址：場地名、句子、電話、純線上、URL | |

只有 `street` 合格。`non_japan` 不算待補（在台灣舉辦的活動屬於收錄範圍，量尺不評其地址）。

刻意的取捨，都寫在測試裡：只有丁目沒有番號是 `town`，札幌的「北1条西2丁目」也是；「栄3」這種丁目的省略寫法是 `town`；日本地址裡出現「台湾」「台北」「高雄町」不會被判成日本以外；混合活動的地址只要有番地仍是 `street`。量尺錯的方向偏向「待補」：寧可多看一眼，不把不合格的地址當成合格。

量尺是文字判定，`street` 不代表地址存在或正確。

### 2. 稽核腳本（Phase A）

`scraper/audit_venue_addresses.py`，唯讀。母體用 `auto_qa.py` 的同一組判定（純出版、線上或電視、排除來源），數字能與 QA 報告對上。輸出：

- 各等級的數量與街道級比率：全部、即將舉辦、近 60 天新進；auto_qa 排除的來源單獨一列，也給合併後的比率。
- 各來源的待補數。
- 以場地名為單位的缺口清單，依即將舉辦的待補事件數排序，附活動頁連結。
- `is_vague()` 與量尺不一致的事件數（Phase B 的影響面）；場地名含線上字樣但地址是街道級的事件數（#364 的規模）。
- 登記簿：沒有地址的場館數、回填候選的上限、衝突數、沒有地址的權威場館。
- 給人工抽查的分層樣本（每等級最多 30 個不重複地址）。

### 3. 量尺的精度由人工抽查確認

單元測試是作者挑的案例，量不出精度。Phase A 的完成條件是使用者看過抽查樣本（`docs/evaluation/venues/2026-11-22-address-grade-sample.md`）：`street` 那 30 筆不應有沒有番地的地址。判錯的列回報後補進測試。這是 ground truth 的判斷，屬人類關卡。

### 4. Phase B：讓現有流程用同一把尺

- `enrich_addresses.is_vague()` 改用量尺（候選增加約 72 筆事件的量級）。權威場館的地址即使量尺判為 `town`（公園、沒有番地的校園）仍視為合格：人工確認高於量尺。
- `auto_qa_missing_address` 的偵測條件不變。
- 每週審核摘要加一段場地缺口清單（一個場地一列，附影響事件數），取代逐事件報告。
- `daily_quality_metrics` 加街道級比率。
- 依 Venue QA Skip Source Registration Guard，任何動到偵測條件的改動要直接跑 `detect()` 做前後比較。

### 5. Phase C：先處理集中的缺口

- 查明 `kokuchpro` 80 筆地址空白的原因並修正。scraper 已經在抓 hCard 地址（`sources/kokuchpro.py`），原因可能是頁面沒有 hCard、`_normalize_online()` 把地址換掉，或 annotator 清空。一個來源、不需要 migration。
- 缺口清單前幾名的場地（「RTI台湾国際放送」是廣播、「台湾原住民族との交流会」是活動名）屬於「場地名不是場地」，列給使用者判斷。

### 後段設計（2026-11-22 定案，見 `plan-2.md` v2.1）

評審 `plan-critique-2.md` 之後的定案：

- **不在 `venues` 加出處欄位，不做機器驗證地址的傳播與 apply（原 Phase D 的 4b）。** 唯讀 planner 顯示，有證據可回填的 38 個殘樁場館，能修到的即將舉辦事件是 0 筆，對驗收指標沒有影響。條件改變時以 planner 的門檻重新判斷。
- **自動鎖只鎖 scraper 原值**（#754）。原本會鎖住入庫當下的場館地址，讓之後的場館修正流不到事件。
- **同名證據採正向認定**（#755）：事件自己的原文含有該地址；或是 scraper 原值（與事件同時寫入、不是 JSON 字串、比較鍵相同）且至少 2 筆、2 個來源。沒有鎖的地址多是模型輸出或複本，不算證據。
- **不寫複製鎖。** annotator 以事件現值優先；force rescrape 清掉的地址，隔天 `enrich_addresses` 會補回即將舉辦的事件。
- **場館欄位修正用既有引擎**（#758）：只有 `venue_update`，不碰事件與鎖，所以沒有 R1 的回滾問題。
- **geocoder 不寫 `venues` 表**（#752）。

## 第一個 PR 的範圍

只做 Phase A：量尺、唯讀稽核腳本、單元測試、基準與抽查樣本（PR #709，已合併）。

## 使用者決定（2026-11-22，issue #708）

1. **量尺抽查：street 合格。** Phase A 驗收通過。
2. **auto_qa 排除的四個來源納入目標。** 目標改用合併後的母體（全部 1,710 筆，街道級 75.1%）。
   - 不把這四個來源加回逐事件的場地 QA：過去那樣做曾讓待處理報告由 22 暴增到 506，這次的決定是「納入目標」，不是「納入逐事件報告」。它們只進每週的場地缺口清單。
   - 148 筆待補很集中：「台湾華語文学習センター（大阪弁天町）」一個場地 40 筆，地址都只寫到「大阪府大阪市西区」，以場地為單位修一次即可；「NPO法人埼玉県日台親善協会」18 筆是團體名，不是場地；其餘多是連鎖店、串流平台與新聞提到的地名。148 筆中即將舉辦的只有 6 筆。處理方式見 issue #732。
3. **#339 拆開做。** 6 筆既有場館修正抽成 issue #733，先單獨做（唯讀比對、使用者核准後寫入）；59 個活動修正與 2 筆重複場館刪除併入 Phase D；R1（完整回滾卡在第 37 步）隨原工具一起退場，Phase D 不沿用那份 70 個動作的計畫。
4. **地址不顯示郵遞區號。** 資料庫保留郵遞區號（定位與後台合併會用到），活動頁顯示時拿掉，結構化資料改放在 `postalCode` 欄。網站原本只拿掉地址表格那一格、而且只認 `〒NNN-NNNN` 開頭的寫法；改成共用的 `web/lib/addressDisplay.ts`，活動頁所有顯示地址的地方都用它。

剩下的決定：web search 是否花錢，等 Phase C、D 之後看剩餘量。

## 評審紀錄

- `plan-critique-2.md`：對 `plan-2.md` 的評審（Claude plan-critic，同一模型家族）。結論是修訂後進行、範圍要縮；處置見 `notes.md`。
- `plan-critique-1.md`：Claude plan-critic（Codex 在本環境無法啟動，與撰寫者同一模型家族）。結論是修訂後進行。處置見 `notes.md`「評審處置」。

## References

- `docs/evaluation/venues/README.md`、`docs/evaluation/venues/2026-10-22-baseline.md`（#325、PR #368）
- `docs/evaluation/venues/2026-11-22-address-baseline.md`、`2026-11-22-address-grade-sample.md`
- `docs/evaluation/campaigns/2026-10-22-authoritative-venue-repair.md`、`docs/specs/parked/authoritative-venue-repair-followups.md`（#339）
- `docs/specs/active/people-ground-truth/proposal.md`（#392）
- `scraper/enrich_addresses.py`、`scraper/auto_qa.py`、`scraper/venue_registry.py`、`scraper/geocode_events.py`
