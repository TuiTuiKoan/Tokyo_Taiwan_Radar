# Venue Pipeline Eval

`scraper/eval_venues.py` 把「地點 → 場館」管線拆段評估（#325）。每段有自己的 ground truth 與計分，失分能直接對應到該修哪一段。

| 階段 | 輸入 → 輸出 | ground truth | 計分 | 狀態 |
|---|---|---|---|---|
| 抽取 extract | raw 文字 → `location_name` | 人工標註（`venues.jsonl` 的 `x*` case） | 正規化後 fuzzy ≥ 0.85，可列多個可接受寫法 | 上線，僅報表 |
| 解析 resolve | `location_name` → 權威場館 | 人工標註的期望場館（`r*` case）＋凍結的權威場館快照 | venue id 完全相同 | 上線，CI 有基準門檻 |
| 定位 geocode | 地址 → 座標 | — | — | 延後：權威場館目前沒有座標，`geocode_events.py` 沒有正式執行紀錄 |

## 檔案

- `scraper/tests/golden/venues.jsonl`：解析 61 筆、抽取 38 筆。
- `scraper/tests/golden/venue_registry_snapshot.json`：2026-10-22 的權威場館快照（58 筆），附 md5 與計算方式。
- `scraper/tests/golden/venues_manifest.json`：解析段的基準門檻。
- `.github/workflows/eval-venues.yml`：PR 動到 `venue_registry.py`、`annotator.py`、eval 程式或 golden 檔時執行。

## 執行

```bash
cd scraper
python eval_venues.py --stage resolve --output /tmp/venues.md     # 不需 secrets，不連網
python eval_venues.py --stage resolve --live-registry ...         # 改用正式資料庫的 venues 表（唯讀）
python eval_venues.py --stage all --output /tmp/venues.md         # 需要 OPENAI_API_KEY 與 Supabase 讀取權
```

## 解析段

### case 類型

| kind | 意義 |
|---|---|
| canonical | 權威場館的正式名稱，防止迴歸 |
| alias | 已登錄的別名 |
| sub_space | 場館名稱＋分隔符號＋子空間（例：`誠品生活日本橋 expo`）。場館要解析成功，且保留原標籤 |
| variant | 真實事件中出現、但目前登錄資料接不到的寫法。這些 case 失敗代表召回缺口，不是 eval 錯誤 |
| negative | 不該解析到任何權威場館的寫法（同系列戲院、相近機構、線上、多城市） |

### 計分

- `correct`：解析結果與期望相同（negative 期望無結果）。
- `missed`：應解析卻沒有結果。
- `wrong_venue`：解析到另一個場館。
- `false_positive`：不該解析卻解析到某個場館。

錯配比漏判嚴重：錯配會把別的場館的地址與營業時間寫進事件。CI 門檻因此是「正確數不少於基準，且錯配加誤中為 0」。

### 快照更新

快照不會自動跟著資料庫變動，這是刻意的設計：CI 驗的是 `venue_registry.py` 的邏輯，不受資料變動影響。登錄資料修正後（例如補 alias），流程如下：

1. 以唯讀 SQL 匯出權威場館，更新 `venue_registry_snapshot.json`，並重算 md5（計算方式寫在檔內）。
2. 重跑解析段；若正確數上升，同步調高 `venues_manifest.json` 的 `min_correct`。
3. `max_wrong` 不調高。

## 抽取段

### 標註規則

- 期望值以 raw 文字中寫明的場館為準，不參考 scraper 結構化欄位或資料庫目前的值。
- 寫到設施名稱為止；樓層、教室等若原文寫在場館名稱中可保留，並把較短的設施名列入 `accepted`。
- 地址、交通方式、票價不屬於場館名稱。
- 原文只寫城市、區域、街道地址，或根本沒有地點時，期望值為 null。這類 case 檢查 LLM 是否自行編出地點（`hallucinated`）。
- 純線上活動的期望值是「オンライン」。

### 漂移

case 只凍結 `event_id`、`raw_md5` 與期望值，raw 文字在執行時從資料庫讀取。md5 不符（raw 被改寫）或事件已刪除時，該 case 列為 drifted 並跳過，不計分。漂移的 case 要重新標註或移除。

## 已知範圍外

- 地點的結構化欄位（例如 asahiculture 的教室、kokuchpro 的會場欄）由各 scraper 直接寫入，不經過 LLM，不在抽取段範圍內。
- 解析段只測 `lookup_venue_for_location()`；annotator 何時呼叫它、FC 鎖定如何覆蓋結果，不在本 eval 範圍。
