---
slug: ndl-relevance-publication
title: ndl_opensearch 相關性過濾與出版物歸類（P5）
status: active
branch: feat/ndl-relevance-publication
created: 2026-10-22
revised: 2026-10-22（依 Plan Critic 評審修訂，見 notes.md § Plan Critic 評審處置）
tags: [scraper, annotator, publication, data-quality]
---

## What（做什麼）

先量測、再收緊 `ndl_opensearch` 的台灣相關性判斷，讓「台灣是主題」的論文與雜誌文章
得到依主題的分類而不是空分類，修掉 prompt 裡 `publication` 規則的矛盾，並為既有不相關
記錄建立「列單 → 逐批人工核准 → 停用 → 可回復」的流程。完成後交棒 P6 重標 ndl 的
66 筆 `["senses"]`。

## Why（為什麼）

- ndl 占有效頂層活動 499／2070（24%），沒有任何一筆被停用過，但樣本裡看得到明顯
  不相關的文章（朝鮮半島有事、馬來西亞投資、韓美同盟等）。
- 這些不相關記錄不是「沒提到台灣」，而是「台灣不是主題」：NDL 的 `title=台湾` 查詢
  會命中系列名或特集名，客戶端 `_is_taiwan()` 又把含系列名的 HTML 描述一起比對，
  擋不下這類記錄（證據見 `notes.md` F1、F2）。
- annotator 已有的 Taiwan relevance gate（2026-10-12 加入）對 ndl 從未生效：每筆 ndl
  寫入時就帶出版物的 7 個 empty sentinel FC，gate 把任何 FC 都當成「人工審過」而跳過
  （F3）。
- P6 要重標的 66 筆 ndl `["senses"]` 必須等相關性與歸類規則先定案，否則重標只會產生
  空分類或把不相關記錄重新標好。

## 已決定（沿用，不重新討論）

- 論文、雜誌文章要收。過濾只看「台灣是不是主題」，不依資料類型排除。
- `senses` 變稀少、由人工策展：接受。
- 既有不相關記錄要停用，必須經使用者逐批核准；不得自動停用。
- 不新增 migration（本計畫的所有步驟都不需要，見 Design）。
- `docs/specs/active/publication-policy/` 的出版物政策不變：pure publication 只由
  `event_form == ["publication"]` 判定，scraper 指派 `publication` 的設計不變。
- 使用者決定 D1–D10（`notes.md` § 使用者決定）：邊界記錄保留、不加 fallback、gate 過門檻
  才自動停用且 holdout 通過後才開啟、Admin 批次隱藏、合併目標排除、提交精簡欄位 CSV、
  `feat/japan-scope-gate` 仍要合併且 P5 先合併、holdout 30 筆或 3 週、盲標。

## Non-Goals（不做什麼）

- 不重標任何既有記錄的分類（那是 P6）。
- 不處理 ndl 以外來源的 `["senses"]`（P6 的 55 筆）與 kokuchpro 的 89 筆舊空分類。
- 不新增 report 類型、不改 Admin UI、不改 `event_reports` 結構。
- 不把 `publication` 加進 prompt 的 event_form 候選清單。
- 不改 NDL 的 server-side 查詢（`title=台湾`、90 天 `from=` 視窗）。
- **不評估入口召回**：NDL 沒回傳的、被期刊號規則（`-i\d+$`）略過的、超出
  `_MAX_RESULTS=500` 或 90 天視窗的記錄，都不在量測範圍。結論只適用於「目前 scraper
  已收錄的候選集」。
- 不重構 `_is_taiwan()`（評審 P1-7：R0 下改寫不提升 recall，只增加維護成本）。
- 不碰 `LOCATION GATE` 段落（`feat/japan-scope-gate` 分支正在改那段，D7）。
- 不做每日 CI 的新步驟；量測工具是一次性腳本，不承諾成為 P6 或其他來源的通用工具。

## Design（設計摘要）

### 1. 篩選怎麼收緊，以及怎麼量 recall（回答問題 1）

**原則：盲標先行、開發集與封存集分開、prompt 凍結後才看封存集；門檻是產品的風險偏好，
不是統計保證，所以結果分成「通過／未通過／樣本不足」三種。**

#### 1.1 母體與切分

| 集合 | 內容 | 用途 |
|------|------|------|
| 快照 S | Phase C 開始時以唯讀 SELECT 固定的 ndl（規劃時 499 到 505 筆）＋hanmoto 78 筆頂層 pure publication（event id、標題、描述、`updated_at`）；記錄快照時間、筆數、id 清單的 SHA-256 | 之後所有量測都以 S 為準，不再讀 live 資料 |
| P | S 中的 ndl 部分＝「目前 scraper 已收錄的歷史候選集」，**不是** NDL 回傳全集，也不代表未來流量 | recall 與 N 移除率 |
| P_dev／P_seal | P 依 1.1a 的規則切成約 60%／40% | P_dev 用來開發 prompt；P_seal 在 prompt 凍結前不得產生或查看模型輸出 |
| P_h | S 中的 hanmoto 部分（含 38 筆已併入 ndl 而停用的記錄，只用於量測，不進處置） | gate 依 pure-publication 判定，hanmoto 新進記錄也會受影響，必須另驗（評審 P1-5） |
| H | prompt 凍結後最先進來的 30 筆新 ndl，或 3 週，先到者為準（D8） | 上線前的漂移檢查（D9），不當作統計證明 |

**1.1a 切分規則（可重現）**：

1. 分層：S1（標題不含 `台湾`／`臺灣`／`台灣`／`Taiwan`）、S2（標題含台灣且含以 `・`、`、`
   分隔的國名清單；判定式寫在腳本裡並有單元測試）、其餘。每筆只屬一層，S1 優先。
2. seed 固定為字串 `p5-ndl-2026-10`，寫進快照的 metadata。
3. 每層內依 `sha256(seed + event_id)` 的十六進位字串排序；前 `floor(0.6 × n + 0.5)` 筆進
   P_dev，其餘進 P_seal。某層 n ≥ 2 時，兩邊至少各 1 筆（必要時從 P_dev 移 1 筆到 P_seal）。
4. 快照 metadata 記錄每層的 n、P_dev 筆數、P_seal 筆數，並同步寫進 `notes.md`。
   任何人用同一份快照與 seed 都能重現切分。

#### 1.2 標籤與盲標流程（D10）

| 標籤 | 意義 |
|------|------|
| `R` | 台灣（或台灣的人物、作品、地點、組織）是作品本身的主題 |
| `N` | 台灣只出現在系列名、特集名、刊名，或只是順帶一提 |
| `B` | 邊界：多國比較中的一國、台灣特集裡但本文談別的題目。依 D1 **計為應保留**，丟掉 B 算 recall 損失 |

1. 標註表只含 event id、可點連結、標題、描述前 500 字與空白的標籤欄，列順序打亂；
   **不含**任何模型判定、理由或候選規則輸出。模型輸出另存成檔，標完才合併。
2. 使用者標完一批後才揭盲。只有使用者標籤與模型判定不一致的列需要裁決；裁決時保留
   原始盲標（`blind_label`），另記最終標籤（`final_label`）與一句理由。
3. 指標以 `final_label` 計算，同時報出以 `blind_label` 計算的數字；兩者對門檻的結論
   不同時，以較保守者為準，並在 `notes.md` 說明。
4. 標籤定義在開始標註前定稿（上表加 D1），標註期間不改。

#### 1.3 分層與標註順序

| 步驟 | 範圍 | 標註 | 約略筆數 |
|------|------|------|---------|
| ① 開發集 | P_dev 中的 S1（標題無台灣字樣，只靠系列名命中）全數、S2（多國清單標題）全數、其餘隨機 40 | 盲標 | 約 90 |
| ② 開發 prompt | 只用 P_dev 的標籤與模型輸出調整候選 prompt 措辭 | — | — |
| ③ 凍結 | 候選 prompt 檔的 SHA-256 寫入 `notes.md`。看過 P_seal 結果後若再改 prompt，P_seal 就用掉了：其數字降為參考，C6 的開啟改以 H 判定，且 H 擴大為 60 筆 | — | — |
| ④ 全量執行 | 凍結的 prompt 對 S 全部（P_dev、P_seal、P_h）執行；R1 對 P 執行 | — | — |
| ⑤ A 區全標 | 任一候選規則（R1、G）在 P_seal 或 P_h 丟掉的記錄，尚未標過的全數盲標 | 盲標 | 依 ④ 結果，預估 40 到 70 |
| ⑥ K 區抽樣 | P_seal 中沒被任何候選規則丟掉的記錄，隨機 60 | 盲標 | 60 |
| ⑦ 樣本不足時 | 從 K 區**尚未抽中**的記錄再抽 40（不重複抽）；剩不到 40 筆就全取。只能加抽一次 | 盲標 | 0 到 40 |

S2 只在開發集全標（幫助 prompt 處理多國比較標題），封存集不另外全標：它們若被丟掉會
落在 A 區，否則落在 K 區的抽樣範圍。

#### 1.4 指標與計算

對每個候選規則 X，P_seal 分成兩區：A＝被任一候選規則丟掉的記錄（全數已標），
K＝沒被任何候選規則丟掉的記錄（抽樣 n＝60 或 100）。令 `N_K` 為 K 區筆數、
`n` 為 K 區抽樣筆數、`x` 為樣本中標為 R 或 B 的筆數、`p̂ = x / n`。
`p_LB` 是 Clopper–Pearson 單側 95% 下界：成功數 `x`、試驗數 `n`，
`p_LB = Beta⁻¹(0.05; x, n − x + 1)`；`x = 0` 時 `p_LB = 0`，`x = n` 時 `p_LB = 0.05^(1/n)`。

- 丟掉的 R＝A 區中 X 丟掉、標為 R 或 B 的筆數（**全數計數**）。
- 保留的 R 估計＝A 區中 X 保留的 R＋B 筆數＋`N_K × p̂`。
- recall＝保留的 R ÷（保留的 R＋丟掉的 R）；recall 下界以 `p_LB` 取代 `p̂` 計算。
  這只涵蓋抽樣誤差，不涵蓋標註錯誤，所以同時報出 1.2 第 3 點的盲標版本。
- N 移除率＝A 區中 X 丟掉的 N ÷（A 區的 N＋`N_K ×（1 − p̂）`）；同樣報出以
  `1 − p_LB` 的上界換算的保守值。

邊界輸出：`n = 0` 時不產生估計，結果為「樣本不足」；recall 或 N 移除率的分母為 0 時
結果為「不適用」，不輸出數字。

指標函式是純函式，有單元測試：`x = 0`、`x = n`、`n = 0`、分母為 0、全 R、全 N、空 A 區，
以及 `p_LB` 與 SciPy（或已知表值）對照。

**適用範圍**：A 區由「本次所有候選規則」共同決定。日後新增或修改候選規則，A／K 的
母體就會改變，本次的抽樣與數字不能沿用，必須重新劃分與抽樣。量測紀錄要寫明這一點。

#### 1.5 候選規則

| 代號 | 規則 |
|------|------|
| R0 | 現狀：標題或整段描述含 `TAIWAN_KEYWORDS`（＝不丟任何 P 中的記錄，作為對照） |
| R1 | 只看標題 |
| G | R0 加上修正後的 annotator relevance gate（凍結的 prompt；判定沿用 `_relevance_gate_update()` 的 confidence ≥ 0.8 規則） |

不再增加候選。量測腳本計算 G 時必須呼叫正式流程的 gate 判定函式（見 2.3），不得另寫
一份判斷。

#### 1.6 門檻（產品風險偏好）

| 指標 | 通過 | 樣本不足 | 未通過 |
|------|------|---------|--------|
| P_seal recall | 點估計 ≥ 98% 且單側 95% 下界 ≥ 96% | 點估計 ≥ 98% 但下界 < 96%：做 1.3 ⑦ 後重算，仍不足就視為未通過 | 點估計 < 98% |
| P_seal N 移除率 | ≥ 60% | — | < 60%（不值得上線） |
| P_h | G 丟掉的記錄全數盲標，丟掉的 R＋B ≤ 1 | — | > 1 |
| H（D9） | 30 筆全數盲標，G 丟掉的 R＋B ≤ 1，且逐筆檢視 | — | > 1 |

- 被丟掉的 R 與 B 一律逐筆列給使用者看，不只報比例。
- H 只有 30 筆，丟掉 ≤ 1 是早期警訊，不能證明低誤殺率；`notes.md` 必須照這樣描述。
- P_dev 的數字只當參考，不能用來判定通過。
- 這是**固定停止規則**，屬於產品決策：點估計未達 98% 就不上線，不再加抽來區分真實
  低 recall 與抽樣波動。「未通過」的意思是「依停止規則不開啟 gate」，不是統計上證明
  recall 低於 98%；`notes.md` 照這樣描述。

**預期（假說，以量測為準）**：S1 約一半是相關的，R1 會丟掉約 20 筆 R，約占 4%，
過不了 recall 門檻。若如此，scraper 的關鍵字規則不動，精確度改由 G 負責。

#### 1.7 關鍵字位置與 iwafu

- 只看標題：精確度上升有限（多國比較標題仍會通過），recall 損失集中在台灣特集裡的
  單篇文章，正好是最有價值的一群。
- 標題或描述：等於現狀。兩者都要：在 ndl 的資料形狀下等同只看標題。
- 位置規則分不出「主題」與「提及」，這是語意問題，只有 LLM 判斷做得到。
- iwafu 只能借形式（負向樣式的結構、用真實字串寫的 regression test、不放裸片假名
  タイワン的教訓），不能借規則：iwafu 擋的是完全沒提到台灣的活動，ndl 的記錄全都提到。
- 只有 R1 通過門檻時才改 scraper，並同時處理 `原住民`、`客家`、`台中`（`舞台中`）的
  假陽性與 regression test；那會是另一個 commit，現在不排。

### 2. 台灣為主題的文章怎麼歸類（回答問題 2）

**根因**：annotator 的 system prompt 全以「活動」為框架，模型收不到「這是書目記錄」的
訊號，看到雜誌文章就判為「不是活動」而回空分類。scraper 給的 `category=["books_media"]`
會被模型輸出取代（F5）。

#### 2.1 payload 契約（評審 P0-1、P0-2）

現行契約：`build_event_user_content()` 是送給 GPT 的 user message 與 injection 掃描的
**唯一**來源（`annotator.py` 約 1414–1442 行），`_annotate_one()`、主流程的掃描
（約 2690 行）與 `eval_annotator.py` 都呼叫它。本計畫維持「掃描的字串＝送出的字串」：

1. `build_event_user_content(raw_title, raw_description, record_type=None)`：
   `record_type == "publication"` 時，在 `<UNTRUSTED_EVENT_DATA>` **之前**加一行程式
   產生的 `RECORD_TYPE: publication`。這一行是整個回傳字串的一部分，所以也會被掃描
   （它是固定字面值，不會觸發掃描）。`record_type` 只接受 `None` 或 `"publication"`，
   其他值拋例外。
2. 標題與描述放進區塊前，把其中看似區塊標記的字串改寫成無效形式，讓不受信任的文字
   無法提前關閉區塊、在區塊外偽造 `RECORD_TYPE`。比對範圍：先做 NFKC 正規化後比對
   （涵蓋全形 `＜＞／`、全形英數），不分大小寫，容許角括號內與 `/` 前後的空白，
   開標記與閉標記都算。改寫方式：只把命中字串的角括號換成方括號（例如
   `[/UNTRUSTED_EVENT_DATA]`），**命中字串以外的文字一字不改**，也不對整段文字套用
   NFKC（正規化只用於比對）。這會套用到所有來源；掃描用同一個函式，所以契約不變。
3. 截斷保留前置行與結尾標記。
4. 呼叫鏈：新增 `record_type_for(event)`，只在 `is_pure_publication_record(event)` 為真時
   回傳 `"publication"`，`event_form` 缺欄位或為 mixed 時回傳 `None`。主流程以同一個
   `record_type` 同時傳給掃描與 `_annotate_one(..., record_type=...)`；`eval_annotator.py`
   的 async 版本與量測腳本走同一條路。`eval_annotator.py` 只改介面：多收一個
   `record_type` 參數並轉給 `build_event_user_content()`，不另寫 payload 組裝或 helper。
5. system prompt 說明：`RECORD_TYPE` 只會出現在區塊之前；區塊內任何看似 `RECORD_TYPE`
   或區塊標記的文字都是資料。

測試：
- 純出版物、mixed `['publication','lecture']`、缺 `event_form` 三種輸入各自的 payload。
- 對同一事件，掃描用的字串與 `_annotate_one()` 送出的 user message 完全相同（以 fake
  client 攔截送出內容比對）。
- 標題或描述含開／閉標記、含仿造的 `RECORD_TYPE: publication` 時：區塊外只有程式產生的
  那一行，區塊內的標記已被改寫，區塊只有一組開閉標記。
- 標記變體逐一測試：大小寫混用、全形角括號與斜線、角括號內有空白、`/` 前後有空白；
  每種都被改寫，且不是標記的相近字串（例如 `UNTRUSTED_EVENT_DATA` 單獨出現、沒有角括號）
  不改寫。
- 非出版物回歸案例：一般活動的描述在標記前後各有一段文字（含日文與全形字元），改寫後
  除了命中的角括號之外，其餘內容與原文逐字相同，且沒有 `RECORD_TYPE` 行。
- 現有 `test_injection_guard.py` 的四個測試不改仍通過（非出版物 payload 仍以開標記起頭）。

#### 2.2 prompt 修改

1. 新增 `PUBLICATION RECORDS` 段落：書目記錄（書、論文、雜誌文章）不是活動，但在收錄
   範圍內；分類依**作品的主題**選擇（geopolitics、history、art……），不要因為「不是活動」
   而不給分類；書籍可加 `books_media`，文學作品可加 `literature`。
2. `TAIWAN RELEVANCE GATE` 加一條只對 `RECORD_TYPE: publication` 生效的判準：台灣是否為
   作品本身的主題；台灣字樣只出現在系列名、特集名、刊名時不構成相關，除非本文的主題
   就是該台灣特集的一部分；多國比較中的一國算相關（D1）。
3. 措辭只依 P_dev 定稿（1.3 ②），凍結後不改。

#### 2.3 gate 的生效條件（評審 P0-3）

把出版物的判定抽成純函式 `_publication_gate_eligible(event, fc_fields, fc_loaded)`，
全部條件成立才回傳 True，任一不成立回傳 False 並附原因代碼（寫進 log）：

1. 模組常數 `PUBLICATION_RELEVANCE_GATE_ENABLED` 為 True（C2 預設 False，見 D9）。
2. `fc_loaded` 為 True：`_load_human_field_map()` 成功。主流程現在在載入失敗時退回
   空 map（約 2452 行）；改為同時記錄 `fc_loaded=False`，此時出版物一律不進 gate。
3. `is_pure_publication_record(event)` 為真。
4. `event` 含 `annotated_at` 鍵且值為 None。缺鍵視為不成立。
5. `annotation_status != "reviewed"`（沿用現有 `fix_reviewed` 檢查）。
6. 該事件的 FC 欄位集合**完全等於** `PUBLICATION_NULL_FIELDS` 的 7 個欄位，且 7 個值
   都是空字串。`field_corrections` 有 `UNIQUE (event_id, field_name)`，所以 map 不會
   因重複列失真；空 map 或少一個欄位都不成立，等於 fail closed。

條件成立時，gate 沿用現有判定（confidence ≥ 0.8 → 停用並寫 `RELEVANCE_GATE_REASON`）。
不成立時維持現狀（跳過）。非出版物的 gate 行為完全不變。

2026-10-22 唯讀查證（`notes.md` F9）：新進 ndl 首次標註時的 FC 正好是這 7 個空值
sentinel；ndl 與 hanmoto 沒有 `annotated_at` 為空的既有記錄，所以條件 4 不會誤中既有
出版物。

projection：主流程與 `--event-ids` 路徑目前都用 `select("*")`。測試用會解析 `.select()`
參數的 fake client，斷言查詢結果含 `event_form` 與 `annotated_at`；若日後改成明列欄位而
漏掉任一欄，測試必須失敗。

測試矩陣：首次＋恰好 7 個空 sentinel → eligible；已標註、多一個 FC、少一個 sentinel、
sentinel 非空、`fc_loaded=False`、缺 `annotated_at` 鍵、reviewed、mixed form、旗標關閉
→ 各自不 eligible 且原因代碼正確。

#### 2.4 不做空分類 fallback（D2）

改 prompt 後若 R 類空分類率 ≤ 2%，現有 `wrongCategory` 審核佇列足以承接。只有超過 2%
才回頭重議。

#### 2.5 dry-run 怎麼做、怎麼看

量測腳本呼叫正式流程的 `_annotate_one(..., record_type=record_type_for(event))`，帶與
正式流程相同的 `feedback_prompt`、`sr_feedback_prompt`；候選 prompt 從檔案讀入，只在
腳本行程內替換 `annotator.SYSTEM_PROMPT`，不改 repo 裡的常數。現行 prompt 的分類結果
直接用 DB 裡已有的值，不重跑。

| 比較 | 樣本 | 看什麼 | 通過條件 |
|------|------|--------|---------|
| 新 prompt 對出版物 | S 全部 | R 類空分類率、`senses` 單標、gate 判定 | P_seal 的 R 類空分類 ≤ 2%；新出現的 `senses` 單標逐筆人工看過 |
| 新 prompt 的分類品質 | P_seal 保留記錄隨機 20、P_h 保留記錄隨機 20 | 分類是否合理 | 使用者判定不合理的 ≤ 2 筆 |
| 新舊 prompt 對非出版物 | 近 60 筆非 publication 活動 | 各欄位（category、event_form、taiwan_relevance）的差異筆數；只有出現差異的列才逐筆看 | 有差異的列經人工判讀，沒有被判為退步的；不做其他統計，不擴充成通用工具 |
| 針對性負向案例 | 固定 5 筆：出版記念トーク、書店サイン会、mixed form 等 | 沒有 `RECORD_TYPE` 行、不套出版物規則 | 全數符合 |

不再跑「舊 prompt 跑兩次」的自我差異基準（評審 P2-1）。

### 3. prompt 中 `publication` 規則的矛盾（回答問題 3）

現況：`EVENT FORM RULES` 的候選清單刻意不含 `publication`（`check_enum_parity.py` 也把
它宣告為例外），但 Decision guides 第 1291 行寫「"publication" is ONLY for publication
metadata…」，讀起來像模型可以選它；第 1292 行又要求實體出版活動「must not include
"publication"」。

修法：把這兩行合併成一條明確的禁止加導引：

> Never output "publication": the pipeline assigns it to bibliographic records.
> 出版記念, 刊行記念, book launch, talk, signing, lecture or workshop with physical
> participation must use the matching physical form (lecture / networking / workshop / …).

候選清單不動，`check_enum_parity.py` 的例外宣告不動。新增測試：清單不含 `publication`、
「Never output "publication"」存在且舊句不存在。對 pure publication，模型輸出的
event_form 仍由 `_finalize_publication_update()` 覆寫為 `["publication"]`。

### 4. 既有不相關記錄的處置（回答問題 4）

1. **列單（唯讀）**：以 `final_label` 為 N 的記錄產生處置清單，存於 `notes.md` 的
   「處置批次」段落；每列含完整 event id、可點連結、標題、標籤、一句理由、`updated_at`、
   `is_active`、`annotation_status`、是否為合併目標。只有被標過的記錄能進清單；
   未標的不停用。
2. **排除**：`annotation_status='reviewed'`；合併目標（D5）另列；`category_corrections`
   有紀錄者；標為 B 的（D1）。
3. **分批**：每批 ≤ 20 筆，固定清單後給批次編號。
4. **核准前重讀（評審 P1-6）**：使用者執行前，以唯讀 SELECT 重讀該批每一列的
   `is_active`、`updated_at`、`annotation_status`、合併關係、FC 與 `category_corrections`，
   逐列與清單比對。任何一列不同就移出該批，改過的清單重新核准。同時記下 ndl 與 hanmoto
   目前所有 `is_active=false` 的 id 集合，作為事後比對的基準。
5. **核准**：複述清單，取得明確核准字句（例如「核准停用第 2 批，20 筆」）；「好」
   「繼續」不算。
6. **執行（D4）**：使用者在 Admin 活動表勾選該批後按批次隱藏。它寫入
   `is_active=false`、`deactivated_reason="manually deactivated by admin (bulk)"`、
   `deactivated_by_pass="admin_manual"`，符合「`is_active` 只有 Admin 手動與 merger 兩個
   寫入來源」，不需新程式碼。
7. **逐列讀回**：Tester 以唯讀 SELECT 確認該批每個 id 都是 `is_active=false` 且
   `deactivated_by_pass='admin_manual'`；ndl 與 hanmoto 的停用 id 集合＝執行前集合 ∪
   該批 id，多一筆或少一筆都要回報。不以總數差額代替逐列比對。勾錯的列由使用者以 Admin
   批次顯示復原，並在 `notes.md` 記錄。
8. **停用而非刪除，可逆**：Admin 批次顯示會把 `is_active` 改回 true 並清空停用欄位；
   `database.upsert_events()` 對 Admin 停用的列一律跳過、永不重新啟用。回復依據是
   `notes.md` 裡已提交的批次清單。

### 5. 與 P6 的先後與介面（回答問題 5）

順序：C1–C4 合併部署（gate 旗標關閉）→ 第一次 CI 以該 commit 執行並查證（exact SHA）
→ 66 筆中標為 N 的完成處置批次 → P6 重標剩下的 ndl。C6（開啟 gate）與 P6 互不依賴。

| 介面 | 內容 |
|------|------|
| 名單 | 66 筆 ndl `["senses"]` 依標籤分成「已停用」「待重標」「未標註」，存在 `notes.md` |
| 規則 | 新 prompt 已在 production（附 exact SHA 證據） |
| 約束 | 重標用 `--event-ids` 指定 id，不用 `--all`；既有記錄的 `annotated_at` 非空，gate 條件 4 不成立，所以 P6 不會造成未經核准的停用 |

66 筆中不在任何標註範圍的記錄列為「未標註」，P6 重標前由使用者決定要不要先補標。
P6 的 dry-run 對照與寫入核准、`--event-ids` 是否覆寫 reviewed，屬於 P6 的範圍。

### 6. Worktree、commit 與 Tester 驗證點（回答問題 6）

**Worktree & Spec Tracking**

1. Spec：`docs/specs/active/ndl-relevance-publication/`。
2. Worktree：`ttr-ndl-relevance-publication-worktree`，branch
   `feat/ndl-relevance-publication`，**新建**（2026-10-22 以
   `git worktree list --porcelain` 確認不存在）。本次只規劃，不建立。
3. Phase 0：Engineer 先讀 `.github/instructions/git.instructions.md` § Isolated worktree，
   依 state matrix 建立，並 idempotent 補 `.git/info/exclude`；不得假設 worktree 已存在。
4. 進度以 `tasks.md` 為準，續接的 session 從那裡恢復。
5. 標註表、模型輸出與快照等工作檔放在 repo 外的 `~/.ai-notes/ttr/p5-eval/`，不進 worktree；
   只有精簡欄位 CSV（D6）提交。

**Commit 切分**

| # | Commit | 內容 | 何時寫 |
|---|--------|------|--------|
| C1 | `fix(annotator): carry the publication record type in the GPT payload` | 2.1 的 payload 契約、標記改寫、呼叫鏈、測試 | 動工即可 |
| C2 | `fix(annotator): gate only first-pass publication records, behind a flag` | 2.3 的 `_publication_gate_eligible()`、`fc_loaded`、旗標（預設關閉）、projection 測試 | 動工即可 |
| C3 | `test(scraper): add ndl relevance evaluation harness` | `scraper/_oneoff_eval_ndl_relevance.py`：`snapshot`／`run`／`metrics` 三個子命令、盲標表、凍結 SHA 檢查、6 美元上限；1.4 指標純函式與測試 | C1、C2 之後 |
| C4 | `fix(annotator): classify publication records by subject` | 2.2 的 prompt 修改（凍結版本）、3 的 `publication` 規則合併與測試、gate 被 sentinel 靜默停用的教訓、ndl source SKILL 過期內容修正 | 1.3 ③ 凍結之後 |
| C5 | `docs(specs): record ndl relevance measurement and disposal batches` | `notes.md` 量測結果、精簡 CSV、處置批次、P6 名單 | 可分多次 |
| C6 | `feat(annotator): enable the relevance gate for new publication records` | 旗標改為 True，單獨一個 PR | 1.6 四列全部通過之後（D9） |

C1–C5 在同一個 branch，合併部署前 production 不受影響；C6 另開 PR。

**量測腳本的唯讀保證**（評審 P2-4 縮減）：腳本不 import 任何寫入函式；新增一個測試掃描
腳本原始碼，出現 `.insert(`、`.update(`、`.upsert(`、`.delete(`、`.rpc(` 就失敗。不再要求
Tester 以前後 `max(updated_at)` 證明唯讀。`run --split seal` 必須帶 `--frozen-sha`，且與
候選 prompt 檔的 SHA-256 相同，否則拒絕執行。

**Tester 驗證點**

1. C1、C2 後：`python -m pytest scraper/tests -q`（含 `test_injection_guard.py`、
   `test_annotator_relevance_gate.py`、`test_annotator_publication.py`）。
2. C4 後：同上，加 `python3 scripts/check_enum_parity.py`、
   `python3 scripts/sync_ai_adapters.py --check`，以及 2.5 的四列 dry-run 表。
3. 每個處置批次：4 的第 4 點（核准前重讀）與第 7 點（逐列讀回）。
4. C1–C4 部署後（旗標關閉期間）：第一次 Daily Scraper run 的 `headSha` 等於推送的 commit
   且 conclusion=success（`gh run list --workflow=scraper.yml --json headSha,conclusion`）；
   log 中新進出版物的 gate 原因代碼應為「旗標關閉」，且沒有任何出版物被 gate 停用。
   這一步只驗旗標關閉的行為。
5. C6 部署後（旗標開啟期間）：以 C6 的 exact SHA 查證；新進的首次標註出版物，原因代碼
   應為 eligible，或其他具體的不成立原因，**不應再出現「旗標關閉」**；被 gate 停用的
   出版物逐筆列給使用者看。

### 不需要 migration 的理由

所有改動都在 prompt、annotator 判斷式與文件；停用用既有欄位 `is_active`、
`deactivated_reason`；標註結果存在 spec 目錄的檔案，不進 DB。

## 風險

- **LLM gate 誤殺**：防線是 P_seal 門檻、P_h、H 與旗標；C6 之前 gate 不會停用任何出版物。
- **門檻的統計強度有限**：K 區抽樣 60 到 100 筆、H 只有 30 筆。門檻是風險偏好，
  `notes.md` 報數字時一律附下界與「樣本不足」判定，不寫成保證。
- **標註錯誤**：盲標可避免錨定，但無法消除個人判斷差異；同時報出盲標版與裁決版。
- **prompt 是共用的**：改動會影響所有來源。以非出版物 60 筆逐筆差異與 5 筆負向案例把關。
- **標記改寫影響所有來源**：只改寫兩個標記字串，真實活動文字幾乎不會出現；C1 的測試
  確認其他內容不變。
- **分支衝突**：`feat/japan-scope-gate` 改寫同一段 system prompt。P5 先合併（D7），
  該分支日後 rebase 要解 `TAIWAN RELEVANCE GATE` 相鄰區塊的衝突，並重跑 P5 的 prompt
  測試與非出版物對照。
- **標註成本**：開發集約 90 列、凍結後約 100 到 130 列、分類品質 40 列、H 30 列；
  總計約 260 到 290 列，分四次進行。
- **OpenAI 成本**：開發迭代約 4 輪 × 90 筆、全量約 580 筆、非出版物 120 次、H 30 筆，約
  1100 次 gpt-4o-mini 呼叫，估 3 美元上下；腳本累計實際 usage，超過 6 美元即停止。
  repo 的成本報告曾低估約 4 倍，以腳本累計值與 OpenAI 後台為準。
- **過度擬合**：prompt 只用 P_dev 開發；P_seal 在凍結前不產生模型輸出，由腳本強制。

## 待決定

D1–D10 已全部決定，見 `notes.md` § 使用者決定。目前沒有未決項目。

## References

- 交接提示：`~/.ai-notes/ttr/architect-p5-ndl-prompt.md`；資料品質線：
  `~/.ai-notes/ttr/data-quality-line-2026-10-22.md`
- Plan Critic 評審：`~/.ai-notes/ttr/plan-critic-p5-report.md`（Codex，2026-10-22）
- `docs/evaluation/campaigns/2026-10-13-senses-taxonomy.md`（Known risks、Deferred work 1–2）
- `docs/specs/active/publication-policy/proposal.md`
- `scraper/sources/ndl_opensearch.py`、`scraper/annotator.py`、`scraper/eval_annotator.py`、
  `scraper/publication_rules.py`、`scraper/taxonomy.md`、`scraper/tests/test_injection_guard.py`、
  `scraper/sources/iwafu.py`、`scraper/tests/test_iwafu_relevance.py`
- 進度：[`tasks.md`](tasks.md)；證據與決定：[`notes.md`](notes.md)
