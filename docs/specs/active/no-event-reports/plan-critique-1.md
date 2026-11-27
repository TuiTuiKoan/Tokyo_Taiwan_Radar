# Plan Critique 1 — no-event-reports

> 這次評審用的是和 Architect 同一個模型：本 session 沒有安裝 Codex，所以這不是第二視角。
> 行號以 `af82793` 為準。worktree 已經有 Engineer 的未提交修改，部分行號已經位移。

**總評**：方向正確，屬於資料正確性，優先序合理。但有 4 個阻斷點，GPT 軌也過度設計。

## 阻斷（必須修）

**B1. GPT `event_report` 軌會誤殺真活動**
- 位置：`merger.py:1120-1220`（Pass 2）、`annotator.py:3800` 之後。
- 問題：Pass 2 會把漏網的回顧新聞 `raw_description` 接到正式活動後面（`別来源補足`），再把 primary 設成 `pending`。下一輪 annotator 看到的是一段過去式的內文，GPT 會以高信心判定 `is_report`，結果停用的是正式活動本身。已結束、官網改寫成「盛況のうちに終了」的活動，重新標註時也會遇到同樣的問題。
- 修正：本 PR 拿掉 GPT 軌（見 S1）。如果要保留，必須同時滿足三個條件才判定：
  - 首次標註（`annotated_at is None`）；
  - `secondary_source_urls` 為空；
  - `source_name` 屬於新聞型來源：`_NEWS_SOURCES`、`tiff_jp`、`note_creators`。

**B2. 判定時 `event_form` 還不存在，電視節目會被誤殺**
- 位置：`event_report.py`（`is_event_report`）、annotator gate。
- 問題：首次標註時 DB 的 `event_form` 多半是空的，`broadcast`／`publication` 排除不會生效。例如 gguide_tv 的「台湾旅レポート」節目會被停用。
- 修正：
  - gate 必須傳入 `update_data["event_form"]`，也就是 GPT 剛產出的值，不能用 `event` 上的舊值；
  - 再加一道來源豁免：`gguide_tv`、`ndl_opensearch`、`hanmoto`、`kawade_rss`；
  - 補一條測試：`event_form=[]` 的 gguide_tv 標題。

**B3. regex 的排除邏輯只看單一命中**
- 位置：`event_report.py`（`_RECAP_RE` 的迴圈）。
- 問題：迴圈遇到任何一個命中就回傳 True，`報告会` 的排除只套用在同一個命中上。會誤判的例子：
  - 「台湾に行ってきた！視察報告会」會被判成活動報導；
  - `結果発表` 會誤殺徵件活動，例如「フォトコンテスト（結果発表：3月）」、「結果発表会」；
  - `行ってきた`／`見てきた` 會誤殺講座標題，例如「台湾で見てきたもの」。
- 修正：
  - 加「整個標題層級」的否決：標題含 `報告会|発表会|説明会|のお知らせ|募集|開催決定|参加者募集|申込` 就直接判定為非報導；
  - `結果発表` 改成只在標題開頭的 `【結果発表】` 才算；
  - 各補一條反例測試。
- 另外，以下說法 regex 抓不到，應該補進去或列入待覆核：`終了しました`、`【ご報告】`、`振り返り`、`活動側記`。

**B4. CI 會紅，標籤也會從其他路徑回來**
- `scripts/tests/test_check_enum_parity.py:111`：測試用字面值 `'  "market",\n  "report",\n];'` 定位 types.ts，`replace_in` 的斷言要求它恰好出現一次。拿掉 `report` 後 ci-checks 會失敗。修正：fixture 改用 `"healthcare",\n  "market",\n];`。
- `category_feedback.py:41`（`build_feedback_prompt`）：最新 15 筆 `category_corrections` 原樣放進 prompt，裡面的 `"report"` 會繼續當成「正確答案」教給 GPT。proposal 的 D4 只處理 field_corrections。修正兩件事：
  - `build_feedback_prompt` 依 `VALID_CATEGORIES` 過濾；
  - 一次性腳本同步改寫 `category_corrections.corrected_category` 與 `ai_category`。

  `annotator.py:2982` 雖然會剝掉 `human_category_map` 裡的 `report`，但每跑一次就留一筆 warning。
- 分類變空的情況：如果某列的 `category` 只剩 `report`，拿掉後會變成 `[]`，觸發 `_queue_missing_category_report`，Admin Reports 會湧入 `wrongCategory`。修正：dry-run 把「拿掉後為空」單獨列成一組，決定要停用還是設回 pending。
- `taiwan_cultural_center.py:103` 的 `_REPORT_KEYWORDS` 涵蓋 `報告|記録|アーカイブ`，範圍太寬。D2 寫「標題命中就不產出」，必須改成用 `is_event_report()`，否則會丟掉 TCC 的 `報告会`。
- `taioan_dokyokai`：WordPress 文章可以同時屬於 `/category/event/`。只移除活動記録路徑擋不住，scraper 也應該對標題跑 `is_event_report()`。
- 一次性腳本必須用 `raw_title` 判定，不能用 `name_ja`：name 已經被注入【レポート】前綴，用 name 判定會全部命中。
- 被停用的報導如果有 active 的子活動（`parent_event_id`），要一起停用。

## 簡化（過度設計）

**S1. 這個 PR 拿掉 GPT 軌**
- 正式盤點的真實報導中，TCC、Cinem@rt、prtimes、taioan 全部可以用標題 regex 加 scraper 判定處理。只有 tiff_jp 的訪談需要語意判斷。
- 為了一個來源去動 SYSTEM_PROMPT、JSON schema、eval baseline，複雜度 +2 level，還會引出 B1。
- 建議：tiff_jp 放進待覆核清單，另開 issue。

**S2. `database.find_parent_event_id`（`database.py:580`）沒有任何呼叫者**
- 建議直接刪除，不要只改裡面的 `report` 判斷。
- `backfill_report_prefix`（`annotator.py:5841`）及其 CLI flag 也一起刪掉。

**S3. 不要把 note_creators 的 `_is_media_or_report` 併進 `event_report`**
- 兩者語意不同：前者包含媒體露出，而且已經有測試覆蓋（`test_note_creators_filter.py`）。維持現狀。

## Nits

- `annotator.py:1159`：prompt 寫「Treat the report as one event」，這和新政策矛盾。改成「報導會被系統移除，sub_events 回傳 []」，或直接刪掉這行。
- `annotator.py:3929`：`_REPORT_RE` 含裸 `報告|記録`，會連帶擋掉 `報告会` 研討會的多場次 sub_events，和 1157 行互相矛盾。改用 `is_event_report`。
- golden fixtures 要同步更新，否則 eval-annotator 會掉分：
  - `tests/golden/cases.jsonl` 的 case `83f0723a` 期望值含 `report`；
  - `frozen_corrections.json:174` 同樣含 `report`；
  - 兩者更新後，`manifest.json` 的 sha256 也要重算。
- `/[locale]/categories/report` 會變成 404。在 next.config 加 301 導到 `/events`。
- 拿掉 `isPureReportEvent` 的 noindex 後，留在線上的新聞型條目會變成可索引。確認這是預期行為。
- `guard_detections` 的 `report_prefix_injected`：一次性腳本 `--apply` 之後應該是 0 筆，下一輪可以把這條偵測整個刪掉。
- TCC 原本就 seed `"culture"`，這不是有效分類，可以順手拿掉。

## 結論

🟡 需修正後再交給 Engineer。必修 B1–B4，並建議採用 S1。
