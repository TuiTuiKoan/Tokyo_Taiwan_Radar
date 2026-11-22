# Plan Critique 1 — organizer-source-subevents / proposal.md v1

> 評審者：Claude 的 plan-critic 角色（Plan subagent，依 `.github/agents/plan-critic.agent.md`）。**與 Architect 同一模型家族**：本環境沒有 `codex`，無法取得不同家族的視角。2026-11-22。以下為評審全文。

---

# Plan Critic 評審：organizer-source-subevents / proposal.md v1

> **本次評審和 Architect 用的是同一個模型家族（Claude）。Codex 不可用，不能算是取得第二視角。**
>
> 我這次對 production Supabase（`cjtndektjjpvvjofdvzr`）跑了幾個唯讀 `SELECT`，拿到 407a033b 存下來的 `raw_description` 原文，也統計了 tiff_jp 的資料分佈。沒有做任何寫入。這些實測結果推翻了提案根因表裡的三項判斷，所以列在最前面。

## 0. 關鍵實測證據

| 查證項目 | 結果 |
|---|---|
| 407a033b `raw_description` | 長度 2000。**10 個放映場次、シンポジウム、入場料都完整在內**。截斷不是原因。 |
| 正文前段 | `…ニュース\nすべて トピック イベントレポート イベント＆キャンペーン…` → 接著 `2026.11.15 [更新／お知らせ]`，正文從這裡開始 |
| 正文**後段** | `前の記事` → `ニュース一覧へもどる` → `AD` → `新着ニュース`，其中有 `2026.11.06 [イベントレポート]`（出現兩次），還有別篇文章的標題 |
| 唯一一個 `会場：` 標籤 | `18:30　交流会（会場：アテネ・フランセ地下1階カフェテリア）` |
| tiff_jp 全部 63 筆 | 43 筆帶 `report` 類別，其中 41 筆的標題沒有任何 report 關鍵字。22 筆 active；**其中 19 筆是 active、未 reviewed、category 含 movie** |
| 407a033b 現況 | `reviewed`，已有 11 個手動子事件，`official_url` 已填 |
| GPT 原始回應紀錄 | DB 沒有這類表（只有 `field_corrections_audit`），0 子事件的原因無法從資料重現 |

---

## 必改

### M1. 根因表有兩項判錯：`report` 和地點都是規則程式碼產生的，不是模型判斷
- **report 類別**：`annotator.py` L3276 呼叫 `_inject_keyword_categories(categories, raw_title + " " + raw_desc)`，L2583 再用 `_REPORT_TRIGGER_RE`（L2404，含 `レポート`）掃全文。網站選單的「イベントレポート」**一定**會加上 `report`，不管模型怎麼回。tiff_jp 43/63 筆帶 report 就是這個原因，不是單一事件的問題。
- **地點「地下1階カフェテリア」**：`_VENUE_LABEL_RE = r'(?:会場|場所)[：:]\s*(.+)'`（L788）在 `_extract_venue_from_raw`（L823）抓到括號裡交流会那行。L3152 存成 `_pre_location_name`，L3402 它的優先序高於 GPT。換句話說，**模型其實沒有決定權**。
- 提案寫「同上，模型從交流會那行抓地點」是錯的。設計 A、B 也都沒處理這個 regex，**照原計畫實作，這個症狀不會消失**。下一篇正文只要有 `（会場：…）` 的附註就會重現。
- 處理方式（二選一，計畫必須寫明）：
  - (a) tiff 爬蟲在清理後的正文前面補一行 `会場：<主會場>`。這需要有可靠的資料來源，tiff 新聞沒有，所以不建議。
  - (b) 收緊 `_VENUE_LABEL_RE`：只接受行首（`re.M` + `^\s*`），排除前面是 `（`／`(` 的匹配。這會影響所有來源，必須補全域回歸測試，例如 `scraper/tests/test_annotator_sub_event_location_fallback.py` 以及所有用到 `_extract_venue_from_raw` 的測試。

### M2. 「max_tokens 逼近」這個假說已被程式碼反駁，應該刪掉
`_annotate_one`（L1977–2016）用的是 `response_format=json_object`。輸出被 4000 截斷時會得到不合法的 JSON，程式會自動用 6000 重試一次；再失敗就丟例外，事件會變成 `error`，**不會**悄悄變成「annotated＋0 子事件」。407a033b 當時是 annotated，所以模型回的就是空的 `sub_events`。比較可能的原因有兩個：
- 模型過度套用 L1158 的 EXCEPTION（movie 類別、多時段 → 不建子事件）；
- 前後段選單與「新着ニュース」的雜訊。

B.2 把 `max_tokens` 提到 8000 的理由應改寫成「11 筆三語子事件大約需要 4–5k token 的預留空間」，不能再當成根因。

### M3. A.1 只切前段不夠，尾端也必須切
實測顯示尾端的「新着ニュース」裡也有 `[イベントレポート]`，還有其他文章的標題與日期。只「從第一個 `YYYY.MM.DD [分類]` 行開始取」的話：
- `report` 照樣會被 L2583 注入（M1 的問題沒解決）；
- A.2 的日期收集會吃到側欄其他文章標題裡的 `M/D`；
- 如果 A.3 收集「所有 `<a href>`」，會撿到 `AD` 廣告與側欄連結。

必改內容：正文結束點切在 `前の記事`／`ニュース一覧へもどる`（以先出現的為準）。比較好的做法是改用 DOM 選正文容器，文字切割只當備援。上限從 2000 提高到 6000 可以接受，但清理後這篇本身只有約 1500 字，提高上限的理由應寫成「預防更長的文章」。

### M4. A.3 的連結範圍前後矛盾，必須統一定義成「正文容器內的 `<a>`」
- 設計 A.3 寫「在詳細頁收集所有 `<a href>`」；
- 風險表寫「只取文章正文內的第一個合格外部連結」。

兩者衝突，而 tiff 頁面上有 `AD` 區塊。必須定義成「正文容器（或 M3 切出的區間）內的 `<a>`」，而且測試要有一個「側欄或 AD 的外部連結不得被選中」的反例。

### M5. 第一個需求在這次的觸發事件上，大概率完全不會生效
正文裡跟主辦方有關的只有兩句：
- 「チラシダウンロード：アテネ・フランスHPにて、コチラから（PDF・4.7MB）」：文字明寫是 PDF，href 幾乎一定直接指向 athenee.net 上的 `.pdf`。
- 「作品解説はアテネ・フランセ文化センターHPにてご確認ください。」：**有沒有超連結不知道**。

照提案規則，「只有 PDF → 不下載、不推測目錄頁、只加 `チラシ: url`」，所以 407a033b 這種案例 `official_url` 仍然是空的，也不會讀到主辦頁。而觸發事件的三個症狀（日期、子事件、地點）所需的資料**全部已經在 TIFF 正文裡**（見 §0），本來就不需要主辦頁。

結論：A.3 和本次事件的修復沒有因果關係，屬於「為單一事件設計通用機制」（plan-critic SKILL 反鑽牛角尖訊號 #3）。必須二選一：
- (a) **把 A.3 拆到下一個 PR**（建議）：本 PR 先在 dry-run log 印出正文內所有外部 href，取得真實證據後再設計；
- (b) 留在本 PR，但驗收標準要誠實寫「407a033b 型案例預期只產生 チラシ 行」，同時決定只有 PDF 時 `official_url` 要不要填 PDF URL。目前提案什麼都不填，`official_url` 欄位的價值是零。

### M6. 「只對新文章生效」是錯的：movie-extend 路徑會自動重標註 19 筆既有資料
`database.py` 的 `upsert_events` L955–964：已存在、category 含 movie、未 reviewed、active 的列，會走 `_build_movie_extend_row`（L795）。
- A.1 改變了 `raw_description` → `desc_changed` → `raw_description` 被覆寫，`annotation_status` 改成 `pending`；
- A.2 改變了 `start_date` → L823 `merged_start = new_start` → **發布日會被換成活動日**；`end_date` 取 MAX。

實際影響：下次 tiff_jp 排程跑完，只要這 19 筆還在 `?keyword=台湾` 前 5 頁內，就會被**自動重寫日期並重新標註**。這和 Non-Goals 的「既有活動的回填另行交使用者核准」直接衝突。

計畫必須：
- 明寫這是預期行為（我認為是好事：19 筆的發布日誤當活動日會一起被修好），或在 Non-Goals 刪掉矛盾的那一句；
- 列出 19 筆清單與預期的日期差異，dry-run 時必須比對；
- 說明這 19 筆大多是真的「活動報導」，重新標註後子事件守門（B.2）會不會被觸發。

407a033b 本身是 reviewed（L951），會被完全跳過，不受影響，這點正確。

### M7. 覆蓋率守門與重試必須限定來源，並和 EXCEPTION 劃清界線
B.2 沒有限定來源，會套用到所有來源。電影院來源（eurospace、cine_marine、ks_cinema 等）的 raw 常常含有多部作品的週排程。「≥3 個不同作品名＋0 子事件」會在這些來源觸發重試，提示文字「偵測到 N 個場次」又會把模型推去建子事件。這和既有的 Cinema Series Sub-Event Guard（Architect SKILL L1079）與 L1158 EXCEPTION 的意圖正面衝突，屬於新的 GPT 污染路徑。

必改：
- 第一版加來源白名單（`{"tiff_jp"}`），和 Non-Goals 的範圍一致；
- 重試必須放在既有過濾之後：`_is_pure_publication`、`parent_event_id`、`is_active False`、標題 `_REPORT_RE`、ks_cinema race（L3926–3964）。這些條件下都不得重試；
- 寫明重試結果的合併規則：**只採用重試回來的 `sub_events`**，其他欄位沿用第一次結果。否則日期、類別、翻譯會被第二次回應整批換掉，難以除錯；
- 重試的 token 用量要累加到 `total_tokens_in/out`（L3268 附近）；
- 計數 regex 要接受全形空白：原文是 `17:10　シンポジウム：`。

---

## 建議

### S1. B.1 的 prompt 規則應該縮減，以程式守門為主
Architect SKILL 的「LLM 分類 prompt 修正 Guard」（L341–349）指出：「可確定的規則改寫成程式後處理，不要一直加 prompt 輪次」，而且點名式規則會產生副作用。L1152 本來就寫了「film screening series with individual dates → sub_events」，模型還是沒照做，再加一段長規則不一定有效。建議 B.1 只加一句對 EXCEPTION 的澄清：「同一排程裡有 2 部以上不同作品時，不屬於單片多時段」。`＋` 合映、交流会併入研討會這類細節，放在重試的提示裡就好，不要放進全域 SYSTEM_PROMPT，這樣影響面最小。

### S2. A.2 日期收集要補跨年與標題格式
- 年份推定：12 月發布的文章提到「1月10日」，應推成隔年。用 ±7/365 天的窗口過濾之前要先做這一步，否則跨年日期會被丟掉。
- 標題 `12/2(水)～4(金)、8(火)～9(水)` 裡的 `～4(金)`、`8(火)` 只有日沒有月，用 `M/D` 抓不到。這篇有正文 `12月N日` 補足，所以沒問題，但測試要固定這個行為。
- 必須遵守 Scraper Date Timezone Guard（SKILL L994）：用 UTC midnight，不能傳 JST-aware 值。
- `開催日時:` 前綴行和 `（記事配信日: …）` 錨點（L3229）會同時存在。順序要寫進測試，確認模型拿到的錨點是發布年。

### S3. `_organizer_link.py` 共用模組延後
這次只有一個來源要用，而且 href 未知。先寫成 tiff.py 內的私有函式，等第二個來源要用時再抽出來（rule of three）。iwafu 的 `_fetch_official_organizer_info`（iwafu.py L672）是「已知 official_url → 抓主辦單位資訊」，和「挑選連結」不同職責，不必硬合併。但如果 A.3 保留，抓取部分應參考它的 `domcontentloaded`＋失敗回傳空值的模式。

### S4. 順手修 tiff_jp 既有 43 筆 report 污染的根源
M3 切掉前後段之後，新抓的資料就不會再被選單注入 report。正文自己的 `YYYY.MM.DD [イベントレポート]` 分類行還在，真正的報導照樣會被標成 report，這是正確訊號。建議在驗收標準加一條：dry-run 後 407a033b 型公告文 `'report' not in category`，報導文仍有 report。

### S5. 驗收要寫具體數字
以 407a033b 清理後的文字為準：子事件應為 11 個（10 個放映時段＋1 場研討會，交流会併入），`start_date=2026-12-02`、`end_date=2026-12-09`、地點是アテネ・フランセ文化センター。背景段寫「10 個場次＋研討會」，和手動建的 11 筆一致，建議寫成「11 個子事件」，避免混淆。

---

## 可接受的風險

### R1. 重試的成本可以忽略
gpt-4o-mini 每次輸入約 6–8k token。限定 tiff_jp 以後，一年觸發不到兩位數次。log 記次數加上兩週後盤點就足夠，不需要另做成本守門。

### R2. 0 子事件的真正原因無法重現
DB 沒有 GPT 回應紀錄。這是已知限制，不必為此擋下計畫。只要測試用 mock LLM 涵蓋「第一次回 `[]` → 重試回 11 筆」以及「重試仍回 `[]` → 只記 warning、照樣寫入」，行為就是可驗證的。

### R3. 子事件 source_id 漂移
既有的 `_find_existing_sub_event` 和 `_allocate_sub_source_id`（L3966–4037）已符合 Sub-event source_id drift guard（SKILL L68）。同一天的兩個合映時段標題不同，不會互相誤配。這個 PR 不需要再動。

### R4. tiff-jp.net 從本環境連不上
§0 已經取得真實 raw 文字，可以直接當 fixture，正文解析不需要連線。只有 A.3 的 href 需要 CI dry-run 證據，見 M5。

---

## 測試策略（對應第 6 點）

1. **fixture**：把 §0 的 407a033b `raw_description` 原文存成 `scraper/tests/fixtures/tiff_jp_70779_body.txt`，包含前段選單和後段「前の記事／新着ニュース」。這是最有價值的回歸素材。另外造一份最小 HTML，含正文容器、正文內 PDF 連結、側欄外部連結、AD 連結，用來測 M4。
2. **tiff 純函式**：正文切割（開頭是 `2026.11.15`，結尾在 `前の記事` 之前）；切割後不含 `イベントレポート`；日期 2026-12-02 到 2026-12-09，含跨年與窗口外丟棄案例；無日期時回退發布日並記 warning。
3. **annotator 規則層**：清理後的 fixture 經 `_inject_keyword_categories` 不得出現 `report`，未清理原文會出現（對照）；`_extract_venue_from_raw` 對 `（会場：…カフェテリア）` 不得匹配，其他既有正向案例不變。
4. **`_count_schedule_slots`**：fixture 計數 11、處理全形空白；單片多時段反例不足 3 個不同作品名；電影院週排程反例在非白名單來源上不觸發重試。
5. **重試流程**（mock `LLMClient`）：只觸發一次、`max_tokens=8000`、只合併 `sub_events`；出版品、`parent_event_id`、`is_active False`、標題含 report 時不重試；token 用量累加。
6. **upsert 影響**：用 fake client 測 `_build_movie_extend_row`：舊 `start_date` 是發布日、新的是活動日 → 回傳列的 `start_date` 是新值、`annotation_status` 是 pending；reviewed 的列被跳過。
7. **dry-run 證據**：列出 19 筆 extend 候選的前後日期與類別差異，以及 A.3（如果保留）實際選到的 href。

---

## 附：plan-critic 固定六段摘要

1. **商業主軸對齊**：🟢 對齊。修的是資料正確性（日期、子事件、地點、類別污染），屬優先級 1。
2. **複雜度 vs 價值**：原案約 high（跨 3 個以上檔案＋SYSTEM_PROMPT＋新 GPT 呼叫路徑＋新模組＋第二頁抓取）。價值是 medium-high，但價值集中在 A.1、A.2、B.2 和 M1 的地點修正；A.3 的價值在本案接近零（M5）。⚠ 照原案做，複雜度高於價值。
3. **優先順序**：🟡。A.3 應該延後。M1 的 regex 與 report 注入問題影響其他來源，比 A.3 更優先（google_news_rss 有 70 筆、prtimes 有 12 筆帶 report 但標題沒有 report 關鍵字，可另開 issue 調查）。
4. **架構整合**：會碰到 Cinema Series Sub-Event Guard（M7）、Annotator Scraper-Priority Guard（M1 的地點優先序）、Scraper Date Timezone Guard（S2）、LLM prompt 修正 Guard（S1）。Sub-event drift guard 既有程式碼已經涵蓋。
5. **復用**：🟡。可復用 `_build_movie_extend_row` 的既有日期更新路徑（不需要另寫回填工具）和 iwafu `_fetch_official_organizer_info` 的抓取模式。`_organizer_link.py` 屬於過早抽象（S3）。
6. **建議**：修正後再交給 Engineer。具體修改點：根因表改寫（M1、M2）；加上正文尾端切割與正文容器限定（M3、M4）；A.3 拆出或改寫驗收標準（M5）；承認並驗證 19 筆自動重標註（M6）；守門加來源白名單與合併規則（M7）；新增 `_VENUE_LABEL_RE` 的修正項（M1）。
