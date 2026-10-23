# Notes — ndl-relevance-publication

證據、基準快照、待決定與 Plan Critic 交接。設計見 [`proposal.md`](proposal.md)，
進度見 [`tasks.md`](tasks.md)。

## 基準快照（2026-10-22，live DB 唯讀 SELECT，Supabase 連接器）

這些是規劃時的快照，會被並行 session 改變；Engineer 在 Phase 0 Step 0 必須重查，漂移就停下。

| 項目 | 值 |
|------|----|
| events 總列數 | 3318 |
| 有效頂層活動（`is_active` 且 `parent_event_id IS NULL`） | 2070 |
| ndl 頂層記錄 | 499（全部有效，0 筆停用） |
| ndl 的 `event_form` | 499 筆全為 `{publication}` |
| ndl `annotation_status` | annotated 497、reviewed 2 |
| ndl 空分類 | 2 |
| ndl 單一 `["senses"]` | 66（另有 `{senses,report}` 6、`{senses,geopolitics}` 3 等複合） |
| 全站有效頂層單一 `["senses"]` | 121 |
| 全站有效頂層空分類 | 96（ndl 只占 2；kokuchpro 約 89） |
| ndl 標題含台灣字樣（台湾／臺灣／台灣／Taiwan） | 460；不含的 39 |
| ndl 有 FC 的記錄 | 499（全部）；`category`／`is_active` FC 0；`category_corrections` 0 |
| ndl 被其他事件併入（合併目標） | 40 筆（hanmoto 39、google_news_rss 1） |
| 10-13 之後新進 ndl | 24 筆，空分類 2 筆 |
| hanmoto pure publication（頂層） | 78 筆：有效 40、因併入 ndl 而停用 38；全數帶 7 個空 sentinel（F9 重查） |

### Phase 0 Step 0 重查（2026-10-22，Engineer，live DB 唯讀 SELECT）

`git fetch origin` 後 `origin/main` ＝ `b78510bb`（規劃起點），沒有新 commit；worktree HEAD 在其上多一個
只勾 tasks 的 commit，base 相同。

| 項目 | 規劃快照 | 重查 | 判定 |
|------|---------|------|------|
| events 總列數 | 3318 | 3327 | 自然增長 |
| 有效頂層活動 | 2070 | 2078 | 自然增長 |
| ndl 頂層（有效／停用） | 499／0 | **505／0** | 預期增長（+6，24 小時內新進 6 筆） |
| ndl `event_form=['publication']` | 499 | 505 | 全數 pure |
| ndl 單一 `["senses"]` | 66 | **66** | 不變 |
| 全站有效頂層單一 `["senses"]` | 121 | 121 | 不變 |
| ndl 空分類 | 2 | 2 | 不變 |
| 全站有效頂層空分類 | 96 | 94 | 小幅變動（並行 session 處理） |
| ndl annotation_status | annotated 497、reviewed 2 | annotated 503、reviewed 2 | +6 |
| ndl 標題含台灣字樣／不含 | 460／39 | 466／39 | +6 都含台灣字樣 |
| ndl `category_corrections` | 0 | 0 | 不變 |
| hanmoto pure（有效／停用） | 78（40／38） | 78（40／38） | 不變 |

三個必須比對的數字（ndl 有效頂層、`["senses"]` 單標、ndl 停用）：只有 ndl 筆數由 499 增為 505，
其餘不變，沒有非預期漂移。

**F9 更正（不改設計）**：F9 與 proposal 2.3 寫「ndl 與 hanmoto 沒有 `annotated_at` 為空的既有記錄」，重查發現各有 1 筆：

| 來源 | id（前 8 碼） | `annotation_status` | FC 數 | 為何仍不會進 gate |
|------|--------------|---------------------|-------|-------------------|
| hanmoto | `3187dc1b` | `error` | 0 | 條件 6 不成立（FC 不是恰好 7 個空 sentinel） |
| ndl_opensearch | `5a51bd60` | `reviewed` | 15 | 條件 5（reviewed）與條件 6 都不成立 |

proposal 2.3 本來就要求六個條件全部成立，所以結論不變；但「條件 4 不會誤中既有出版物」要讀成
「條件 4 誤中的記錄會被條件 5、6 擋下」。C2 測試把這兩筆的形狀
（`annotated_at` 為 None 且 `reviewed`、`annotated_at` 為 None 且無 FC）列為負向案例。

## 與交接提示的出入

- 交接提示寫「ndl 約占全部事件的 27%」。實測為 499／2070＝24%（有效頂層）或
  499／3318＝15%（全部列）。量級一致，不影響設計。
- 交接提示與 10-13 結案紀錄寫「ndl 是空分類最大的來源」。以存量看已不成立：有效頂層
  空分類 96 筆中 ndl 只有 2 筆，最大來源是 kokuchpro。以改版後的新進流量看，ndl 仍是
  空分類的來源之一（24 筆中 2 筆）。
- 交接提示舉的三個例子（網路廣告對策、台灣旅遊排名、薩拉米戰術）目前都是 `["senses"]`
  （舊 fallback），屬於 66 筆之內：
  [台湾の悪質ネット広告対策がすごい!](https://tokyotaiwanradar.com/ja/events/880214e4-3bc2-46e2-9689-be9af95be509)、
  [台湾ランキング&お得な旅テク!](https://tokyotaiwanradar.com/ja/events/ce52d099-d643-4fa1-800f-a623c699840a)、
  [台湾流「サラミ戦術」](https://tokyotaiwanradar.com/ja/events/5e022abc-a431-4ada-8d22-1b8a8f828010)。
  「回空分類」是新 prompt 下的預期行為，要在 P6 重標前由本 spec 修掉。

## Findings

### F1：客戶端過濾形同虛設

`NDL_API` 以 `title=台湾` 查詢，NDL 的 title 檢索也比對系列名（シリーズ名、特集名）。
`_is_taiwan(f"{title_raw} {description_raw}")` 的 `description_raw` 是 RSS 的 HTML 書目
清單，本身就含系列名，所以凡是 NDL 回傳的記錄幾乎都會通過。標題不含台灣字樣的 39 筆
全部是靠系列名命中，例如：

- 系列「特集 台湾有事を起こさせないために」裡談日中關係的文章
- 系列「半導体関連で外資投資が急伸 マレーシア、韓国、台湾」裡只談韓國或馬來西亞的文章

範圍限制（Plan Critic P1-1）：這只說明「系列名命中的記錄會通過」，不代表 DB 的 499 筆
等於 NDL 回傳全集。scraper 另有期刊號略過（`-i\d+$`）、`_MAX_RESULTS=500`、90 天視窗與
去重，DB 又是歷史累積。所以量測母體 P 定義為「目前 scraper 已收錄的歷史候選集」，
結論不外推到入口召回或未來流量。

### F2：不相關是語意問題，位置規則分不開

39 筆系列名命中的記錄裡，相關與不相關大約各半：

- 相關：美術手帖特集「いま出会う台湾の現代美術」的藝術家專訪，例如
  [李奥森](https://tokyotaiwanradar.com/ja/events/6da3d4d5-0199-4c45-be36-a5b4413b7394)、
  [頼依欣（台中市立美術館館長）](https://tokyotaiwanradar.com/ja/events/ab964e18-a3e3-467d-8426-b7012648f8d9)；
  台灣現代詩人系列的譯詩集 [金色のからす](https://tokyotaiwanradar.com/ja/events/18a240fc-a903-4241-9ccb-62bca4e3da84)；
  台灣高校生日本留學報告 [一歩踏み出す勇気](https://tokyotaiwanradar.com/ja/events/c412b960-5db0-45ec-9dfc-6afb4ca333c1)。
- 不相關：[朝鮮半島有事に備えよ](https://tokyotaiwanradar.com/ja/events/62e3aa08-4e0c-40ed-92fc-167d433fd9b0)、
  [外国企業の投資額…：韓国](https://tokyotaiwanradar.com/ja/events/94ceddfe-1005-4cec-bdb0-55970ccf6c05)、
  [日本企業の実行投資額…：マレーシア](https://tokyotaiwanradar.com/ja/events/1a132f06-27fe-43ba-b463-0ed85524fdbe)、
  [米中関係の本質](https://tokyotaiwanradar.com/ja/events/5459f6ff-4816-4ab5-a696-cf1bb92d0a68)、
  [民族抹殺した朝鮮支配](https://tokyotaiwanradar.com/ja/events/7f2003f1-e064-4c6c-b339-27c54795bc1d)。

標題含台灣的 460 筆裡，另有一群多國比較或國名清單的標題（約 40 筆），例如
[アジア主要国における化学物質登録制度の比較研究：中国・韓国・台湾・フィリピン](https://tokyotaiwanradar.com/ja/events/3650a120-9249-4c3c-948a-23eded453073)、
[半導体関連で外資投資が急伸：マレーシア、韓国、台湾](https://tokyotaiwanradar.com/ja/events/bb2ddb0b-0ad8-4f05-81ca-3a775bee5b6e)。
這一群算不算「台灣是主題」需要使用者定義（D1）。

### F3：annotator 的 relevance gate 對出版物從未生效

`_relevance_gate_update()` 在 `human_protected` 非空時直接回傳 `None`。`human_protected`
來自 `_load_human_field_map()`，載入**所有** `field_corrections` 列，不分是誰寫的。

- 10-14 之後新進的 ndl，首次標註時的 FC 正好是 writer 寫入的 7 個
  `PUBLICATION_NULL_FIELDS` empty sentinel（`corrected_by` 為空）；部分記錄之後才多出
  `description_zh`（簡轉繁修正）。
- 既有 ndl 另有 name／description／organizer 等由 backfill 寫入的鎖，`corrected_by`
  也是空。全表 2381 列 FC 中只有 20 列有 `corrected_by`，所以這個欄位不能用來區分人工。
- 結果：gate 自 2026-10-12 上線以來，對 ndl 與 hanmoto 一次都沒有作用；ndl 停用數為 0。
- ndl 與 hanmoto 沒有 `annotated_at` 為空的記錄，可以用它界定「首次標註」。

### F4：新進空分類的量很小

10-13 之後新進 ndl 24 筆，空分類 2 筆，兩筆都是相關的：
[AI景気で40年ぶり高成長](https://tokyotaiwanradar.com/ja/events/2214af0e-564a-44ab-bdb4-42ee9a0fb3f0)（台灣經濟）、
[台湾系顧客100社突破で包括支援を拡充](https://tokyotaiwanradar.com/ja/events/1c582f85-3433-4c38-bbaa-4b615352554a)。
各有一張待審 `wrongCategory` 報告。依 Architect SKILL 的規模規則（< 20 筆用 prompt
修法），不做每日 CI 步驟，也不建議加 fallback 程式碼（D2）。

### F5：scraper 給的分類會被丟掉

ndl scraper 設 `category=["books_media"]`，annotator 以 `_validate_categories(annotation["category"])`
取代，不保留 scraper 的值。

### F6：停用路徑已存在且可逆

- Admin 活動表的批次隱藏（`setAdminEventsActive` → `adminEventMutationsCore.ts`）寫入
  `is_active=false`、`deactivated_reason="manually deactivated by admin (bulk)"`、
  `deactivated_by_pass="admin_manual"`；批次顯示會清回。
- `database.upsert_events()` 規則 1：Admin 停用的列一律跳過、永不重新啟用。

### F7：ndl source SKILL 過期

`.github/skills/sources/ndl_opensearch/SKILL.md` 寫 `q=台湾`、`mediatype=1`、180 天 client
過濾，實際程式為 `title=台湾`、90 天 server `from=` 視窗。

### F8：並行分支改同一段 prompt

`feat/japan-scope-gate`（worktree 已掛載，領先 `origin/main` 11 個 commit，最新一則是
2026-08-06 的「record scope gate PR readiness」）把 `LOCATION GATE` 改成輸出
`scope_decision` 並送人工審核，也改了 `TAIWAN RELEVANCE GATE` 的一行。它比 10-12 的
relevance gate 更早分出，日後 rebase 本來就會衝突；本 spec 會再增加一處相鄰改動。

### F9：首次標註時的 FC 狀態（2026-10-22，回應 Plan Critic P0-3）

- `PUBLICATION_NULL_FIELDS` 的 7 個欄位是 `location_address`、`location_address_zh`、
  `location_address_en`、`business_hours`、`business_hours_zh`、`business_hours_en`、
  `location_prefectures`（`scraper/publication_rules.py`）。
- 最近 12 筆新進 ndl（10-21、10-22）在 `annotated_at` 之前的 FC 正好是這 7 個，值全為空；
  其中 3 筆在標註後約 5 小時多了 1 個 FC。annotator 在記錄建立後約 2 到 5 分鐘標註。
- 既有的 ndl 與 hanmoto 出版物另有 `description_zh`（256）、`name_*`（251）、`organizer`（244）、
  `location_name*`（約 225）等 FC，`corrected_by` 全為空（自動流程寫入）。
- 以正確的 7 個欄位重查（同日稍晚，ndl 已增為 505 筆）：ndl 有 7 個空 sentinel 的 363 筆、
  6 個的 50 筆、1 到 3 個的 4 筆、完全沒有的 88 筆；hanmoto 78 筆全數 7 個。既有記錄
  的 `annotated_at` 都非空，而且多數另有其他 FC，都不會滿足 gate 條件。
- P_h 的 78 筆含 38 筆已併入 ndl 而停用的 hanmoto 記錄。它們只用於量測 gate 在 hanmoto
  資料上的行為，不進處置批次。
- `field_corrections` 有 `UNIQUE (event_id, field_name)`，所以 `_load_human_field_map()`
  回傳的 map 不會因重複列失真，可以用欄位集合比對。
- `_load_human_field_map()` 失敗時主流程退回空 map（`annotator.py` 約 2452 行）。只要求
  「恰好 7 個」就會在空 map 時不成立；計畫另加 `fc_loaded` 旗標讓意圖明確。
- `_annotate_one()` 目前只收標題與描述（約 1553 行），主流程（約 2700 行）與
  `eval_annotator.py` 都沒有傳 `event_form`；原計畫的 `RECORD_TYPE` 若只改
  `build_event_user_content()` 不會送到模型（Plan Critic P0-1 屬實）。

## 待決定

| # | 問題 | 選項 | 建議 |
|---|------|------|------|
| D1 | 邊界記錄算不算「台灣是主題」：多國比較中的一國、台灣特集裡但本文談別的題目 | (a) 算相關，保留；(b) 不算，停用；(c) 依國數切：≤3 國算、≥4 國不算 | (a)。量測時 B 計為應保留（丟掉算 recall 損失），處置時 B 不停用，等使用者看過量測結果再決定要不要第二輪 |
| D2 | pure publication 改 prompt 後仍空分類時，是否保留 scraper 的 `books_media` | (a) 不加，交 `wrongCategory` 佇列；(b) 加 fallback，不開報告；(c) 加 fallback 並開報告 | (a)。量小（約兩週 1 筆）；只有 R 類空分類率 > 2% 才回頭考慮 (b) |
| D3 | gate 通過門檻後，新進出版物被判不相關時怎麼處理 | (a) 自動停用（與其他來源一致）；(b) 送人工審核；(c) 不啟用 | (a)，但只在 G 於 P 與 P_h 都通過門檻時；不過門檻就 (c)，不另做審核路徑 |
| D4 | 既有記錄的停用由誰執行 | (a) 使用者用 Admin 批次隱藏；(b) 一次性腳本＋不可變清單 | (a)。不需新程式碼，符合「`is_active` 只由 Admin 手動與 merger 寫入」；候選若超過約 80 筆再考慮 (b)，(b) 需要明確核准該規則的例外 |
| D5 | 合併目標（40 筆）若被判不相關 | (a) 排除，另列清單個別處理；(b) 一併停用 | (a)。停用合併目標會讓已併入的 hanmoto 記錄轉址到停用頁 |
| D6 | 標註 CSV 是否提交到 spec 目錄 | (a) 提交；(b) 只留本機 | (a)。內容是公開的 NDL 書目，且是 recall 數字的唯一證據 |
| D7 | `feat/japan-scope-gate` 是否仍要合併 | (a) 仍要，P5 先合併，該分支日後 rebase；(b) 已放棄，可退役 | 請使用者確認該分支狀態；無論哪個，P5 都不碰 `LOCATION GATE` 段落 |
| D8 | holdout 的長度 | (a) 最先 30 筆新 ndl 或 3 週，先到者為準；(b) 固定 2 週 | (a)。新進約每週 15 筆，30 筆約 2 週 |

### 使用者決定（2026-10-22）

| # | 決定 | 對計畫的影響 |
|---|------|--------------|
| D1 | (a) 邊界記錄算相關、保留 | 標籤 B 計為應保留；丟掉 B 算 recall 損失；處置批次不含 B，看過量測結果再決定要不要第二輪 |
| D2 | (a) 不加 `books_media` fallback | 空分類交 `wrongCategory` 佇列；R 類空分類率 > 2% 才回頭重議 |
| D3 | (a) 有條件自動停用 | G 在 P 與 P_h 都過門檻才讓 gate 作用於新進出版物；沒過門檻就不啟用，不另做審核路徑 |
| D4 | (a) Admin 批次隱藏 | 使用者在 Admin 執行，每批 ≤ 20 筆，需明確核准字句；不寫一次性停用腳本 |
| D5 | (a) 合併目標排除 | 40 筆合併目標不進處置批次，另列清單個別處理 |
| D6 | (a) 標註 CSV 提交；評審後補充為**精簡欄位** | 提交 event_id、連結、標題、分層、`blind_label`、`final_label`、裁決理由、各候選規則判定、seed 與快照 SHA；不含描述全文與模型理由。盲標表與模型輸出留在 `~/.ai-notes/ttr/p5-eval/` |
| D7 | (a) `feat/japan-scope-gate` 仍要合併，P5 先合併 | P5 不碰 `LOCATION GATE` 段落；該分支日後 rebase 到含 P5 的 main 時，要解 `TAIWAN RELEVANCE GATE` 相鄰區塊的文字衝突，並在 rebase 後重跑 P5 的 prompt 測試與非出版物對照 |
| D8 | (a) 最先 30 筆新 ndl 或 3 週，先到者為準 | Phase G 照此執行 |
| D9 | gate 先關，holdout 通過才開（評審 P1-3） | C2 加 `PUBLICATION_RELEVANCE_GATE_ENABLED = False`；C1–C4 部署時 gate 不停用任何出版物；H 離線執行並通過後，C6 單獨 PR 開啟。仍符合 D3「過門檻才自動停用」，holdout 成為門檻之一 |
| D10 | 盲標，事後揭盲裁決（評審 P1-4） | 標註表不含模型判定；只裁決不一致的列；同時報盲標版與裁決版指標。總標註量約 260 到 290 列，分四次 |

## Plan Critic 評審處置（2026-10-22）

評審：Codex（`codex exec -s read-only`，與撰寫者不同模型家族），報告存於
`~/.ai-notes/ttr/plan-critic-p5-report.md`。總評「🟡 暫不接受目前版本」。Architect 逐項對照
程式碼與 live DB 查證後處置如下。

| # | 評審意見 | 查證 | 處置 | 改在哪 |
|---|---------|------|------|--------|
| P0-1 | `RECORD_TYPE` 沒接到實際 LLM 呼叫鏈 | 屬實（F9 末項） | 採納：`record_type_for()`，主流程、掃描、`eval_annotator.py`、量測腳本同一條路；測試比對送出內容 | proposal 2.1；tasks Phase A C1 |
| P0-2 | 「只掃不受信任部分」破壞「掃描＝送出」契約；原始文字可偽造閉標記 | 屬實（`annotator.py` 1414–1442、2690；現行未處理標記） | 採納：前置行納入回傳字串一起掃描；標題與描述中的標記改寫；負向測試 | proposal 2.1；C1 |
| P0-3 | gate 條件缺查詢契約與 fail-closed | 部分屬實：重複列不可能（UNIQUE 約束），但載入失敗退回空 map 屬實 | 採納：純函式＋原因代碼、恰好 7 個空 sentinel、`fc_loaded`、缺鍵不成立、projection fake client 測試 | proposal 2.3；C2；F9 |
| P1-1 | P 不能代表 NDL 回傳全集或未來流量 | 屬實 | 採納：P 改稱「已收錄的歷史候選集」，入口召回列為 Non-Goal | proposal 1.1、Non-Goals；F1 |
| P1-2 | S1–S4 不保證所有被 G 丟掉的都標過；分母未加權 | 屬實（S3 依候選 prompt，prompt 會變） | 採納：凍結後再全標 A 區（任一候選規則丟掉的）、K 區抽樣，Clopper–Pearson 下界 | proposal 1.3、1.4 |
| P1-3 | 門檻是點估計，小樣本下精確感錯誤；建議影子模式 | 屬實 | 採納：通過／樣本不足／未通過三態；門檻明列為風險偏好；gate 旗標先關（D9） | proposal 1.6；D9 |
| P1-4 | LLM 預標造成錨定；同資料調 prompt 過度擬合 | 屬實 | 採納：盲標（D10）；P_dev／P_seal 切分，凍結 SHA 由腳本強制 | proposal 1.2、1.3 |
| P1-5 | hanmoto 驗收不完整 | 屬實 | 採納：P_h 全量跑新 prompt，A 區全標，分類品質抽 20 | proposal 1.1、1.6、2.5 |
| P1-6 | Admin 批次缺 CAS／逐列讀回 | 屬實（UI 無法 CAS） | 採納：核准前逐列重讀、停用 id 集合前後比對；UI 本身不改 | proposal 4 |
| P1-7 | C3 的 `_is_taiwan()` 重構價值低 | 同意 | 採納：刪除；SKILL 過期修正併入 C4；只有 R1 通過才另開 commit | proposal Non-Goals、1.7；tasks Phase D |
| P2-1 | 自我差異基準不宜當通過條件 | 同意 | 採納：刪除自我差異；改為逐筆判讀＋5 筆負向案例 | proposal 2.5 |
| P2-2 | S4 60 筆不足以證明 98% | 同意 | 採納：K 區 60 筆，可加抽 40 一次，以下界判定 | proposal 1.3、1.6 |
| P2-3 | 完整 CSV 不必提交 | 部分同意 | 交使用者決定：D6 補充為精簡欄位 | D6 |
| P2-4 | C1 量測工具過度 | 部分同意 | 採納：三個子命令、不承諾通用；唯讀改以原始碼掃描測試證明。保留 6 美元上限與快照 | proposal 6；tasks Phase B |

評審沒提到、修訂時順帶修正的錯誤：原計畫 C1（量測工具）排在 C2（`RECORD_TYPE`）之前，
量測工具在 C1 時無法送出 `RECORD_TYPE`。修訂後 payload 與 gate 條件（C1、C2）先做，
量測工具（C3）在後。

### 第二輪處置（2026-10-22）

第二輪評審（Codex）總評「🟡 小修後可交 Engineer」：P0-1、P0-3 已解決，P0-2 基本解決。
報告由使用者貼回對話（未另存檔）。處置如下，全部採納，都只是把規格寫明確，不改設計。

| # | 評審意見 | 處置 | 改在哪 |
|---|---------|------|--------|
| P0-2 殘餘 | 標記改寫沒定義變體與「其餘內容保留」 | NFKC 後比對、不分大小寫、容許空白；只換命中字串的角括號，其餘一字不改；變體與相近字串測試 | proposal 2.1 第 2 點與測試 |
| P1 切分 | P_dev／P_seal 的分層取整不可重現 | 新增 1.1a：三層、固定 seed、`sha256(seed+id)` 排序、`floor(0.6n+0.5)`、每層兩邊至少 1 筆、筆數寫入 metadata | proposal 1.1a；tasks Phase B、C |
| P1 A／K | 結論只對本次候選規則成立；CP 參數與邊界未定 | 明寫 `x`、`n`、`Beta⁻¹` 公式與 `x=0`、`x=n`、`n=0`、分母 0 的輸出；加「適用範圍」段落 | proposal 1.4 |
| P1 停止規則 | 加抽有選擇性停下的疑慮；第二次抽樣可能重複 | 明寫為固定停止規則（產品決策）；加抽只從未抽中的記錄取，不足 40 就全取 | proposal 1.3 ⑦、1.6 |
| P1 C6 時序 | 部署驗收與 C6 驗收的原因代碼混在一起 | Tester 第 4 點只驗旗標關閉；第 5 點驗旗標開啟，不應再出現「旗標關閉」 | proposal 6 Tester 4、5；tasks Phase E、G |
| P1 標記改寫 | 對所有來源的影響沒有回歸案例 | C1 加含標記的非出版物回歸測試 | proposal 2.1 測試；tasks C1 |
| P2 非出版物對照 | 與其他驗收重疊 | 限定為差異筆數＋有差異的列逐筆看，不擴充 | proposal 2.5 |
| P2 eval_annotator | 只保留介面改動 | 明寫只多收 `record_type` 並轉給共用函式，不另寫 helper | proposal 2.1 第 4 點；tasks C1 |

## 標籤定義（定稿，2026-10-22）

> 狀態：**定稿**（2026-10-22，使用者回覆 L1／L2／L3 照建議）。標註期間不改（proposal 1.2 第 4 點）。

### 判斷對象與依據

- 判斷的是**作品本身**（一本書、一篇論文、一篇雜誌文章）：**台灣是不是這件作品的主題**。
  不看它「像不像活動」、文章好不好、是否有趣；論文與雜誌文章都在收錄範圍內（已決定）。
- 依據是盲標表上看得到的內容：標題與描述前 500 字。描述是 NDL 的書目清單，常含**系列名、
  特集名、刊名**——這些是判斷的重點，不是證據：它們出現台灣字樣不代表作品談台灣。
- 看不出來時，**不要點進連結去查**（會讓不同列的判斷依據不一致）；歸 `B`。

### 三個標籤

| 標籤 | 意義 | 量測時的處理 |
|------|------|-------------|
| `R` | 台灣（或台灣的人物、作品、地點、組織）是作品的主題，或主要主題之一 | 應保留 |
| `N` | 台灣只出現在系列名、特集名、刊名，或只是順帶一提；作品本身談別的題目 | 應丟 |
| `B` | 邊界：以下情況之一，或在 R 與 N 之間猶豫 | **計為應保留**（D1）；丟掉算 recall 損失 |

### 判定規則

1. **標題與摘要直接指向台灣的人、事、物、地**（台灣的藝術家、作家、政策、產業、歷史、
   語言、旅遊、社群）→ `R`。台日關係、台灣的對外關係，只要台灣是被分析的對象 → `R`。
2. **台灣字樣只在系列名／特集名／刊名**，而標題與摘要談的是別的國家或別的題目 → `N`。
   例：特集「台湾有事を起こさせないために」底下談朝鮮半島或日中關係的文章。
3. **多國比較或國名清單**（例：中国・韓国・台湾・フィリピン）→ `B`。D1：台灣是其中一國、
   有被實際處理，算相關。若摘要明示台灣只是名單上的一個名字、沒有任何台灣內容 → `N`。
4. **台灣特集裡、但本文談別的題目**，且從表上看不出本文與台灣有關 → `B`。
   能看出本文明確談台灣 → `R`；能看出明確不談台灣 → `N`。
5. **地緣政治分析**（美中、日中、區域安保）：台灣（海峽、安全、地位）是被分析的對象 → `R`；
   台灣只是背景提到一句 → `N`；兩者之間 → `B`。
6. **只有「台灣出身」這個屬性**（作者或人物是台灣人，但作品談別的）：算 `B`，不算 `R`。
7. 猶豫時一律標 `B`，不要硬選 `R` 或 `N`（`B` 計為保留，所以猶豫標 `B` 不會製造 recall 損失，
   但會增加之後裁決與 N 移除率的不確定性——這是有意識的取捨）。

### 例子（Architect 依 F1、F2 的暫定讀法，使用者可推翻）

| 暫定標籤 | 記錄 | 理由 |
|---------|------|------|
| R | [李奥森](https://tokyotaiwanradar.com/ja/events/6da3d4d5-0199-4c45-be36-a5b4413b7394) | 台灣藝術家專訪 |
| R | [頼依欣（台中市立美術館館長）](https://tokyotaiwanradar.com/ja/events/ab964e18-a3e3-467d-8426-b7012648f8d9) | 台灣的美術館與人物 |
| R | [金色のからす](https://tokyotaiwanradar.com/ja/events/18a240fc-a903-4241-9ccb-62bca4e3da84) | 台灣現代詩人譯詩集 |
| R | [一歩踏み出す勇気](https://tokyotaiwanradar.com/ja/events/c412b960-5db0-45ec-9dfc-6afb4ca333c1) | 台灣高校生赴日留學報告 |
| N | [朝鮮半島有事に備えよ](https://tokyotaiwanradar.com/ja/events/62e3aa08-4e0c-40ed-92fc-167d433fd9b0) | 談朝鮮半島，台灣只在特集名 |
| N | [外国企業の投資額…：韓国](https://tokyotaiwanradar.com/ja/events/94ceddfe-1005-4cec-bdb0-55970ccf6c05) | 只談韓國 |
| N | [日本企業の実行投資額…：マレーシア](https://tokyotaiwanradar.com/ja/events/1a132f06-27fe-43ba-b463-0ed85524fdbe) | 只談馬來西亞 |
| N | [民族抹殺した朝鮮支配](https://tokyotaiwanradar.com/ja/events/7f2003f1-e064-4c6c-b339-27c54795bc1d) | 談朝鮮統治 |
| N 或 B | [米中関係の本質](https://tokyotaiwanradar.com/ja/events/5459f6ff-4816-4ab5-a696-cf1bb92d0a68) | 規則 5：要看摘要裡台灣是否被分析；notes F2 暫列不相關 |
| B | [アジア主要国における化学物質登録制度の比較研究：中国・韓国・台湾・フィリピン](https://tokyotaiwanradar.com/ja/events/3650a120-9249-4c3c-948a-23eded453073) | 規則 3：多國比較 |
| B | [半導体関連で外資投資が急伸：マレーシア、韓国、台湾](https://tokyotaiwanradar.com/ja/events/bb2ddb0b-0ad8-4f05-81ca-3a775bee5b6e) | 規則 3：多國比較（系列名同為這三國） |

這些例子**不進標註樣本的答案**，只是校準用；它們同時可能出現在盲標表裡，標註時仍照表上
內容獨立判斷，不要回頭查這張表。

### 標註與裁決流程（重述 proposal 1.2）

1. 盲標表欄位：`event_id`、`url`、`title`、`description_500`、`label`；`label` 只填 `R`／`N`／`B`。
   表內沒有任何模型判定、理由或候選規則輸出。
2. 標完一批後才揭盲。只有「使用者標籤與模型判定不一致」的列需要裁決；裁決時保留原始盲標
   （`blind_label`），另記 `final_label` 與一句理由。
3. 指標同時以 `final_label` 與 `blind_label` 計算；結論不同時以較保守者為準。

### 使用者已確認的三個點（2026-10-22，全部照建議）

| # | 問題 | Architect 建議（Engineer 同意） |
|---|------|------|
| L1 | 規則 5：地緣政治文章台灣只是「重要背景」時算 `N` 還是 `B` | 算 `B`。這類文章在台灣語境下常被使用者視為相關，`N` 會讓 recall 風險落在最有價值的一群；代價是 N 移除率的分母變大 |
| L2 | 規則 6：台灣出身的作者／人物但作品談別的，算 `B` 還是 `R` | 算 `B`。proposal 1.2 的 `R` 含「台灣的人物」，但那是指作品以該人物為對象，不是作者的屬性 |
| L3 | 看不出來時只憑盲標表判斷，不點進連結 | 同意。否則 90 列的判斷依據不一致，裁決時也無法重現 |

## 快照紀錄（2026-10-22，Phase C，`snapshot` 唯讀）

| 項目 | 值 |
|------|----|
| 快照時間 | 2026-10-22T08:21:46Z（UTC） |
| 快照 SHA-256（排序後 event id 以換行相連） | `0cb812da20cefa01d73dd623752ecd29a53500077f99394778f0f18b8555588a` |
| seed | `p5-ndl-2026-10` |
| ndl 頂層 | 505（`count='exact'` 與讀取筆數一致） |
| hanmoto 純出版物 | 78（停用 38）（`count='exact'` 與讀取筆數一致） |
| S1（標題無台灣字樣） | n=39：P_dev 23、P_seal 16 |
| S2（標題含台灣＋≥3 國名清單） | n=11：P_dev 7、P_seal 4 |
| S3（其餘） | n=455：P_dev 273、P_seal 182 |
| P_dev／P_seal 合計 | 303／202 |
| 開發集盲標表 | 70 列＝S1 dev 23＋S2 dev 7＋S3 dev 隨機 40 |

工作檔在 repo 外：`~/.ai-notes/ttr/p5-eval/snapshot.json`、`blind_dev.csv`（不提交）。

與規劃的出入（不影響設計）：
- S1 的 39 筆與基準相符。S2 只有 11 筆，不是規劃時估的「約 40 筆」：當時的估計含兩國並列與
  「國名＋台灣」之外的各式多國標題；現行判定式要求標題內連續 ≥3 個國名。另有 6 筆
  「兩國並列」標題落在 S3，會由 S3 隨機 40 筆與日後的 A 區涵蓋。
- 開發集因此是 70 列，不是規劃的約 90 列。
- 描述欄多為短書目（樣本 154 字），開發集中 39 筆有系列名／刊名欄位，全部在 500 字內可見。

## 量測結果

2026-10-23，`metrics`（凍結 cand1 的輸出：`out_dev_cand1`、`out_seal`、`out_hanmoto`；標籤：`blind_dev`、`blind_a`、
`adjudication_dev`）。精簡 CSV：[`labels_metrics.csv`](labels_metrics.csv)（86 列，D6 欄位）。
A／K 劃分只適用本次候選規則 R1、G。「未通過」＝依 1.6 固定停止規則不開啟，不是統計證明。

| 指標 | R1（只看標題） | G（cand1 gate） |
|------|------|------|
| P_seal 丟掉 | 16 筆：R 8、B 8、N 0 | 0 筆 |
| P_seal recall | **未通過**。工具回報 `insufficient_sample`（K 區 186 筆未標，D 決定不做），但即使 K 區 186 筆全是 R，recall 上限 186／194 ≈ 95.9% < 98%，結論不受 K 區影響 | 丟 0 筆，recall 不受影響 |
| P_seal N 移除率 | 丟掉的 16 筆無 N | **未通過**：G 不丟任何記錄，P_seal 只要有 N，移除率就是 0% < 60% |
| P_h（78 筆） | 不適用 | **通過**：丟 0 筆（cand6 在 P_h 也丟 0 筆） |
| H | 未進行 | 未進行 |
| P_dev（僅參考） | 丟 21：R 12、B 5、N 4 | 丟 0；已知 4 筆 N 一筆都沒丟 |

**判定**：R1 未通過，scraper 關鍵字規則不動（與 1.6 預期一致）。G 不會誤殺，但也幾乎不移除 N，
不值得開啟：`PUBLICATION_RELEVANCE_GATE_ENABLED` 維持 `False`，Phase G 的 C6 不進行。

注意：出貨的 prompt 是 cand6，P_seal 是以 cand1 量測；cand6 未對 P_seal 執行（成本上限）。G 的結論不變，
因為 gate 本來就不開；cand6 與 cand1 在 P_dev 只有 1 筆 gate 差異（仙台灣，cand6 保留）。

P_seal 被 R1 丟掉的 R（8 筆，逐筆）：
- [李亦凡 : コンピュータと人が影響を及ぼし合う関係を表現し…](https://tokyotaiwanradar.com/ja/events/1ba7b3a3-08bb-4117-bb49-3897037d53a7)
- [張恩満 : 未来とはすなわち過去である…](https://tokyotaiwanradar.com/ja/events/46881947-a00b-466b-9613-75168be7ef95)
- [李奥森 : 歴史や人間の複雑な状況に対峙し…](https://tokyotaiwanradar.com/ja/events/6da3d4d5-0199-4c45-be36-a5b4413b7394)
- [黄亜紀(「Each Modern」創設者) : アジアから描き直す美術史](https://tokyotaiwanradar.com/ja/events/739994ff-2852-44fc-97e1-af3feb8a5871)
- [アジア最大のICT見本市で見た"覇者"の戦略と新潮流](https://tokyotaiwanradar.com/ja/events/894cfd50-8227-4b9b-bbd2-cf377b513f84)
- [INTERVIEW 李登輝元総統秘書が直言! 日台はもっと切磋琢磨できる](https://tokyotaiwanradar.com/ja/events/d726716a-6487-4d8f-9000-1f200cb47c7a)
- [レジェンド・アーティスト](https://tokyotaiwanradar.com/ja/events/e19a6a8c-bf4a-4f8a-8433-a019809d9c99)
- [「東アジア共同体」構想を進めよう](https://tokyotaiwanradar.com/ja/events/f5fa0c7a-c9e7-49c5-b86b-97af5efec1c3)

P_seal 被 R1 丟掉的 B（8 筆）：
[危険な世界にいかに備えるか](https://tokyotaiwanradar.com/ja/events/4d3ad22c-80d5-45fa-88fb-9c60131997fa)、
[米中関係の本質](https://tokyotaiwanradar.com/ja/events/5459f6ff-4816-4ab5-a696-cf1bb92d0a68)、
[拡大抑止の崩壊と米同盟諸国](https://tokyotaiwanradar.com/ja/events/782ecb32-cba4-4986-a6c8-273de48cc6c2)、
[マラッカとホルムズ](https://tokyotaiwanradar.com/ja/events/7f2add04-a1b9-4ab5-bb50-3d46afb105fa)、
[各国研究者との学術交流から学ぶ](https://tokyotaiwanradar.com/ja/events/89139014-891b-4d03-861e-19df79aced22)、
[米中対立の外縁で戦争する無意味](https://tokyotaiwanradar.com/ja/events/ae9951d6-cd0f-4e87-a8b0-1aeaa9354094)、
[ゴンチャ・ジャパンCOO インタビュー](https://tokyotaiwanradar.com/ja/events/b1538e37-a65d-4561-989f-e02cb9fd23ce)、
[戦後最悪の日中関係からの脱却をめざして](https://tokyotaiwanradar.com/ja/events/ff0c05b4-8607-470e-9af4-aadc621a2540)。

G 沒丟掉任何 R 或 B，無逐筆清單。

## Prompt 寫入與 dry-run（2026-10-23，Phase D／C4）

- 凍結 cand6 的兩段（`PUBLICATION RECORDS` 相關性判準、`PUBLICATION RECORDS — FIELD RULES`）逐字寫入
  `annotator.py` 的 `SYSTEM_PROMPT`。寫入後（taxonomy 替換後的）`annotator.SYSTEM_PROMPT` SHA-256 =
  `b722d4b8ee16ce29fdbb9bf6b6ff98f6b4a59fe399baf64f20acca01292bc5a2`，與凍結檔一致。
- 接著依 proposal 3 合併 Decision guides 的兩條 `publication` 規則為「Never output "publication"…」。
  **出貨 prompt SHA-256 = `e34cd478f74859906b72e00d1b6985742b7cb9f4f3f13f390b58cb0007cbedf2`**；與凍結版的差異只有這一處
  event_form 導引（出版物的 event_form 本來就由 `_finalize_publication_update()` 覆寫）。
- 測試：`tests/test_annotator_publication_prompt.py`（候選清單不含 `publication`、新句存在、舊句不存在、兩段凍結文字存在）。

dry-run 表（proposal 2.5）：

| 列 | 結果 | 說明 |
|----|------|------|
| 新 prompt 對出版物（R 類空分類 ≤ 2%、`senses` 單標逐筆看） | **部分**：cand1 在 P_seal 空分類 0、`senses` 單標 0。cand6 未對 P_seal 執行（約 $0.56，超過剩餘成本上限） | cand6 代理數字（經程式規則後）：P_dev 303 筆空分類 3（1.0%）、P_h 78 筆空分類 2（2.6%），`senses` 單標皆 0，已標記錄中無 R 類空分類。空分類全來自自創 slug：`education`、`engineering`、`law`、`travel`×2（[中間淳太の満福台湾ガイド](https://tokyotaiwanradar.com/ja/events/1b5fa355-2e2e-47f7-a59b-0c4a15cad759)、[＆TRAVEL 台湾2027](https://tokyotaiwanradar.com/ja/events/bd10e2e5-83c5-4b12-b27a-da70fd7d8437)），會進人工審核佇列；對照修正見 #422 |
| 分類品質 | 第一輪未通過（11／39）；第二輪改門檻後**通過**（N 6 vs 27） | 見「分類品質檢查」 |
| 非出版物 60 筆 | 通過 | 見「非出版物新舊對照與負向案例」（以 cand1 量測；cand6 新增段落只在 `RECORD_TYPE: publication` 時適用） |
| 負向案例 5 筆 | 通過 | 同上；非出版物 payload 不含 `RECORD_TYPE` 由 C1 單元測試保證 |

Decision guides 合併後沒有重跑非出版物 60 筆（只刪除一條要求「不得選 publication」的矛盾句，`publication` 本來就不在候選清單）。

## 處置批次

（Phase F 每批填入：批次編號、核准字句與時間、完整 event id 與連結、讀回驗證結果。）

## P6 交棒

（Phase G 填入：66 筆 ndl `["senses"]` 的「已停用」與「待重標」名單、prompt 的 exact SHA 證據。）

## Plan Critic 交接提示（Codex，`codex exec -s read-only`）

第一輪已於 2026-10-22 執行，處置見上方「Plan Critic 評審處置」。以下保留原始提示詞備查。

```text
你是 Plan Critic。請完整讀取 .github/agents/plan-critic.agent.md 與
.github/skills/agents/plan-critic/SKILL.md 後照做；Copilot 專屬工具依 AGENTS.md 的
「Copilot 對照表」轉換。你是唯讀角色：不寫檔、不改 code、不寫資料庫，批評以文字回傳。
回覆用繁體中文。你和計畫撰寫者是不同模型家族，這正是請你評審的原因。

評審對象：
- docs/specs/active/ndl-relevance-publication/proposal.md（設計）
- docs/specs/active/ndl-relevance-publication/tasks.md（步驟）
- docs/specs/active/ndl-relevance-publication/notes.md（證據、待決定 D1–D8）

計畫依據的程式碼：scraper/sources/ndl_opensearch.py、scraper/annotator.py
（SYSTEM_PROMPT 約 1080–1395 行、_validate_categories、_queue_missing_category_report、
_relevance_gate_update 約 1979 行、_load_human_field_map、build_event_user_content）、
scraper/publication_rules.py、scraper/taxonomy.md、scraper/sources/iwafu.py、
scraper/tests/test_iwafu_relevance.py、scripts/check_enum_parity.py、
scraper/database.py 的 upsert_events。

已由使用者決定、不要重新討論的事項：論文與雜誌文章要收，只看台灣是不是主題；
senses 變稀少可以接受；既有不相關記錄只能經使用者逐批核准停用；不新增 migration。

請特別回答：
1. 可以砍掉的範圍。逐項說明 C1–C4、Phase A–G 哪些可以刪或縮，刪了會失去什麼。
   尤其是：量測工具是否過度、C3 是否該整個拿掉、非出版物 60 筆對照與自我差異基準
   是否必要、holdout 是否值得等。
2. recall 量測站不站得住：
   - 母體 P（現有 499 筆）能不能代表未來的 NDL 流量？計畫說客戶端過濾形同虛設，
     所以 P 近似 NDL 的回傳全集，這個推論對嗎？
   - 「被丟掉的 R 是全數計數、只有分母靠 S4 外推」這個設計是否成立？
     S1–S4 的切法有沒有漏掉會被丟掉卻沒被標註的記錄？
   - 98% recall、60% N 移除率、holdout 丟掉 R ≤ 1 這三個門檻是否合理，
     在 N 只有幾十筆的情況下統計上有沒有意義？
   - LLM 預標會不會讓使用者的標註被錨定，進而高估 recall？要怎麼避免？
   - 在同一份資料上設計 prompt 措辭再量測，過度擬合的風險多大？
3. gate 生效條件（pure publication、annotated_at 為空、FC 只有 7 個 sentinel）
   有沒有漏洞：會不會誤中既有記錄、會不會被其他寫入路徑繞過、hanmoto 是否該納入。
4. 在不受信任區塊外加 RECORD_TYPE 受信任行的做法，有沒有 prompt injection 或
   掃描範圍上的問題。
5. 你認為計畫沒看到的風險或錯誤假設。

輸出格式：先給一句總評，再依「必改（P0）／應改（P1）／可選（P2）」列出問題，
每項附檔案路徑與行號或 spec 段落、理由、建議改法。最後單獨列出「建議砍掉的範圍」。
```

## Plan Critic 第二輪提示（選用，複審修訂版）

```text
你是 Plan Critic。請完整讀取 .github/agents/plan-critic.agent.md 與
.github/skills/agents/plan-critic/SKILL.md 後照做。你是唯讀角色：不寫檔、不改 code、
不寫資料庫，批評以文字回傳。回覆用繁體中文。

這是第二輪。第一輪報告在 ~/.ai-notes/ttr/plan-critic-p5-report.md；Architect 的逐項處置在
docs/specs/active/ndl-relevance-publication/notes.md「Plan Critic 評審處置」，修訂後的設計在
同目錄 proposal.md、tasks.md。D1–D10 已由使用者決定，不要重新討論。

只回答：
1. 第一輪的 P0 三項是否真的解決？逐項指出 proposal 的段落，仍有漏洞就說明情境。
2. 修訂引入的新問題：P_dev／P_seal 切分、A 區／K 區與 Clopper–Pearson 下界的計算、
   「樣本不足」加抽一次、gate 旗標與 C6 的時序、標記改寫對所有來源的影響。
3. 還有哪些可以砍。

輸出：一句總評（🟢 可交 Engineer／🟡 小修後可交／🔴 需重做），再列 P0／P1／P2。
不要重複第一輪已處置且沒有新問題的項目。
```

## 開發集盲標回收（2026-10-22，Phase C ①）

使用者完成 `blind_dev.csv` 70 列盲標，回收時僅有 69 列（編輯時不慎刪除一列），使用者補判該列為 B：
`68f08388`（S2「アジア主要国における化学物質登録制度の比較研究 : 中国・韓国・台湾・フィリピンを中心に」，
多國比較→B，符合標籤定義）。補列內容由快照重建，未經模型欄位。

| 標籤 | 筆數 |
|------|------|
| R（應保留） | 55 |
| B（邊界，計為應保留） | 10 |
| N（應丟） | 5 |
| 合計 | 70 |

N 僅 5 筆：開發集的負例很少，候選 prompt 的 N 移除率在開發階段只能粗看，正式判定靠封存集。
原始 69 列存檔備份在 `~/.ai-notes/ttr/p5-eval/blind_dev.user_69rows.csv`（不提交）。

## Prompt 開發紀錄（2026-10-22，Phase C ②，只用 P_dev）

模型 gpt-4o-mini；每輪對 P_dev 全部 303 筆執行，與正式流程相同的 feedback prompt。候選檔在
`~/.ai-notes/ttr/p5-eval/prompts/`，輸出在 `out_dev_cand*.jsonl`（皆不提交）。指標只用開發集
70 列盲標，**僅供參考，不能用來判定通過**（proposal 1.6）。prompt 內的例子一律自編，不引用開發集
的真實標題或系列名：開發集與封存集逐筆切分，同一系列的文章兩邊都有，引用會灌水封存集。

| 輪 | 候選（SHA-256 前 12 碼） | 改了什麼 | R＋B 保留 | N 丟掉 | 保留記錄空分類 | 花費 |
|----|------|------|------|------|------|------|
| 基準 | cand0 `cc755186b3b4` | 現行 SYSTEM_PROMPT（含 C1 的 RECORD_TYPE 說明） | 58／65 | 2／5 | 0 | $0.80 |
| 1 | cand1 `cec390cd7a4e` | gate 加出版物判準＋`PUBLICATION RECORDS — FIELD RULES` | 65／65 | 0／5 | 0 | $0.83 |
| 2 | cand2 `e8a8879ef2b0` | 判準改為三步驟（自身標題 → 系列脈絡 → 不明保留） | 65／65 | 0／5 | 0 | $0.83 |
| 3 | cand3 `32af023d1ecd` | `taiwan_relevance` 加 `own_title`／`basis` 欄位強制先分類 | 63／65 | 0／5 | **11 筆輸出整個壞掉** | $0.85 |
| 4 | cand4 `addeacdbb01e` | cand2＋prompt 結尾 FINAL CHECK | 64／65 | 0／5 | 0 | $0.85 |

觀察：
- 基準 prompt 以「不是活動」「沒有台灣文化元素」為由丟掉 R（例：台湾夜市大全、台中垃圾焚燒 BOT）。
  cand1 起修好，分類也不再空白。
- 5 筆 N 全部是「台灣只出現在系列名」：多國並列系列中這篇講別國（`: マレーシア`、`: 韓国`、朝鮮、
  日本國防產業），以及台灣飲料系列中的新光合纖（該筆待揭盲裁決，可能應為 B）。四輪都沒有讓
  gpt-4o-mini 把系列名與作品內容分開；它的 selection_reason 直接把系列名當成內容。
- cand3 改輸出欄位後，11 筆只回 `taiwan_relevance` 的欄位，標題、分類等全部遺失：出版物不改輸出 schema。
- 開發集外（未標註）各輪 gate 都只穩定丟掉 `仙台湾`（NDL 關鍵字誤中，正確丟掉）。

## 凍結（2026-10-22，Phase C ③）

使用者選定凍結 cand1（開發集 R＋B 65／65 保留、保留記錄 0 空分類；N 0／5）。

- 凍結檔：`~/.ai-notes/ttr/p5-eval/prompts/frozen_cand1.txt`（唯讀，與 `cand1.txt` 相同內容）
- **凍結 SHA-256：`cec390cd7a4e981990394e0e04ae517eef3912d41d0777360fc7efe7652c9a64`**
- 之後 `run --split seal|hanmoto|holdout` 必須帶這個 `--frozen-sha`。C4 寫入 `SYSTEM_PROMPT` 後，
  `annotator.SYSTEM_PROMPT` 的 SHA-256 必須等於此值。
- 預期（開發集僅供參考）：G 的 recall 可能過門檻，但 N 移除率很可能低於 60%，依固定停止規則不開 gate；
  分類修正（問題 2）不受影響，照常進 C4。此預期不影響封存集的判定方式。

## 全量執行（2026-10-22，Phase C ④）

凍結 prompt（`cec390cd…`）以 `--frozen-sha` 執行：P_seal 202 筆 $0.552、P_h 78 筆 $0.228；P_dev 沿用
cand1 開發輪的輸出（同一 SHA）。R1 不呼叫模型，由 `metrics` 依標題計算。

| 集合 | 筆數 | R1 丟掉 | G 丟掉 | G 保留記錄空分類 |
|------|------|------|------|------|
| P_seal | 202 | 16（即 S1 封存部分） | **0** | 0 |
| P_h | 78 | — | **0** | 0 |

- A 區＝16 筆，全部來自 R1；盲標表 `~/.ai-notes/ttr/p5-eval/blind_a.csv`（不提交）。
- G 在封存集與 hanmoto 都沒有丟任何記錄：G 的 recall 與 P_h 條件必然成立，N 移除率只要封存集
  有任一 N 就是 0%，依停止規則不開 gate。
- 量測腳本修正：`load_outputs`／`_done_ids` 原用 `str.splitlines()`，會在 JSON 字串內的 U+2029 切斷
  記錄（封存集有 1 筆）；改以 `\n` 切分並補測試（commit「fix(scraper): read eval jsonl by newline」）。
  磁碟上的資料本來就完整。

## A 區盲標與 K 區決定（2026-10-22，Phase C ⑤⑥）

使用者盲標 A 區 16 筆（全為 R1 丟掉的封存集 S1）：**R 8、B 8、N 0**。`metrics` 在 K 區未標時回報
「樣本不足」（n＝0），以下判定不依賴 K 區：

- **R1 未通過（可證）**：丟掉的 R＋B＝16。即使 K 區 186 筆全為 R，recall 上限＝186／202≈92.1% < 98%。
  被丟掉的多為台灣特集內、標題無台灣字樣的人物專訪與安全保障文章，符合 proposal 1.6 的預期。
  scraper 關鍵字規則不動（proposal 1.7）。
- **G 不開 gate（產品判斷）**：凍結 prompt 在 P_seal 與 P_h 丟掉 0 筆；開發集 N 也是 0／5 丟掉。
  G 的 N 移除率只可能是 0%（封存集有任何 N）或「不適用」（完全沒有 N），都達不到上線目的
  （≥ 60%）。
- **偏離計畫**：proposal ⑥ 的 K 區 60 筆**不標**（使用者 2026-10-22 決定）。理由：K 區結果只會把 G 從
  「樣本不足」改成「未通過」或「不適用」，不改變不開 gate 的結論，也不影響 R1 的判定。
  因此本次不產生 recall 的點估計與下界，只記錄 R1 的上限。⑦ 加抽一併不做。
- P_h：G 丟 0 筆，條件（丟掉的 R＋B ≤ 1）成立，但因 G 不開而無實質意義。
- 後續影響：Phase G 的 C6（開 gate 旗標）不進行；`PUBLICATION_RELEVANCE_GATE_ENABLED` 維持 False。
  C1／C2 的程式碼與分類修正（C4）照常上線。

## 非出版物新舊對照與負向案例（2026-10-22，Phase C）

樣本：最近標註、有效、頂層、`event_form` 不含 publication 的 60 筆＋負向 5 筆（mixed form 1、出版記念／
刊行記念類 4）。花費：新 $0.196＋舊 $0.189。腳本為 scratchpad 一次性唯讀腳本（不提交，只 SELECT）。

**偏離計畫**：proposal 2.5 寫「現行 prompt 的分類結果直接用 DB 裡已有的值」。實跑後發現 DB 值是經過
後處理的結果（關鍵字補分類、`report` 偵測、人工修正），與模型原始輸出無法直接比對：凍結 prompt 對 DB
的分類差異 37／60、event_form 差異 12／60，多為 DB 多出 `report`／`history`／`lecture`。因此改為以現行
prompt（cand0）對**同一批 id** 各跑一次，比對兩者的原始輸出。這不是 proposal 刪掉的「舊 prompt 跑兩次」
自我差異基準。

| 比較（舊 cand0 → 新 cand1，同批 65 筆） | 差異筆數 |
|------|------|
| category | 13 |
| event_form | 5 |
| gate 判定（is_relevant=false 且 confidence ≥ 0.8） | 2 |

逐筆判讀（engineer）：差異都在合理替代選項之間來回，方向不一致，沒有出版物規則外溢到活動的跡象（沒有
因此新增 `books_media`、沒有空分類、沒有 `RECORD_TYPE`）。判為非退步；較明顯的幾筆：
- 改善：「台湾巨匠傑作選2026」exhibition→movie；gguide 節目的無效 slug `broadcast`→`tv_program`；
  台湾華語講座 study_abroad→workshop；負向案例「台湾に1か月住んでみた」出版記念イベント，舊 prompt
  gate 會丟、新 prompt 保留。
- 同一場羊毛フェルト工作坊（eslite／peatix 兩筆重複）舊 prompt 丟 1 筆、新 prompt 丟 2 筆：屬模型
  不穩定，非 prompt 修改造成（新段落只對 `RECORD_TYPE: publication` 生效）。
- 兩版都會輸出無效 slug（例：category `performance`、`music`、`screening_with_talk`，event_form
  `interview`），屬既有行為，由正式流程的白名單過濾，不在本計畫範圍。

負向 5 筆：`record_type_for()` 全為 None、payload 區塊前沒有 `RECORD_TYPE` 行；新 prompt 沒有對任何一筆
輸出 `publication` event_form（mixed form 那筆輸出 `["lecture"]`）。全數符合。

## 揭盲裁決（2026-10-22）

不一致只有開發集 5 筆（使用者標 N、凍結 prompt 保留）；A 區 16 筆 G 全保留，與 R／B 一致。使用者裁決
（`~/.ai-notes/ttr/p5-eval/adjudication_dev.csv`，保留 `blind_label`）：

| event | blind | final | 理由 |
|------|------|------|------|
| [10fcb5ab](https://tokyotaiwanradar.com/ja/events/10fcb5ab-90a1-4cbf-a03a-398bee20fabd) 新光合成繊維 | N | **B** | 台灣企業，台灣飲料系列內，依 L2 |
| [1a132f06](https://tokyotaiwanradar.com/ja/events/1a132f06-27fe-43ba-b463-0ed85524fdbe) …: マレーシア | N | N | 多國系列中講馬來西亞 |
| [7f2003f1](https://tokyotaiwanradar.com/ja/events/7f2003f1-e064-4c6c-b339-27c54795bc1d) 民族抹殺した朝鮮支配 | N | N | 講朝鮮，台灣只在系列名 |
| [94ceddfe](https://tokyotaiwanradar.com/ja/events/94ceddfe-1005-4cec-bdb0-55970ccf6c05) …: 韓国 | N | N | 多國系列中講韓國 |
| [ccb2e6e1](https://tokyotaiwanradar.com/ja/events/ccb2e6e1-8e6c-4d78-8a07-02220423f3b4) 防衛産業をどう再建するか | N | N | 講日本防衛產業 |

裁決後 R1 與 G 的結論不變。final N 的 4 筆是 Phase F 處置清單的候選（仍需逐批核准）。

## 分類品質檢查（2026-10-23）

樣本：P_seal 保留記錄 20 筆、P_h 保留記錄 20 筆（`order_key(SEED+"category-check")`），
檔案 `~/.ai-notes/ttr/p5-eval/category_check.csv`。使用者填 39 筆（#37 未填）：
**Y 28、N 11**（P_seal N 6、P_h N 5）。門檻是 N ≤ 2，**未通過**。

| # | event | 模型分類 | 使用者意見 |
|---|------|------|------|
| 5 | [8fc460e3](https://tokyotaiwanradar.com/ja/events/8fc460e3-adc7-4627-8aa9-be895fbb6d7c) 台湾と中国の新しい関係を | geopolitics taiwan_japan | 講中台，與台日無關 |
| 6 | [5dd278e4](https://tokyotaiwanradar.com/ja/events/5dd278e4-caab-420e-b164-20e1c3ebc204) 台湾 | books_media | 應為 tourism |
| 9 | [bf20ecb1](https://tokyotaiwanradar.com/ja/events/bf20ecb1-74d2-4dc8-98d9-f68a2abc853e) 台湾に渡った歌舞伎役者たち | history books_media | 不是 books_media，應有 performing_arts |
| 10 | [fd3e32dc](https://tokyotaiwanradar.com/ja/events/fd3e32dc-03c3-4dba-8482-82bcd07e78aa) 台湾妖怪探索珍道中 | books_media | 應為 folklore |
| 16 | [038d4cef](https://tokyotaiwanradar.com/ja/events/038d4cef-dd1f-4a70-84f9-8404419070a1) 台湾飲料事情 | business taiwan_japan | 不是 taiwan_japan，應加 tea_alcohol |
| 17 | [880214e4](https://tokyotaiwanradar.com/ja/events/880214e4-3bc2-46e2-9689-be9af95be509) 台湾の悪質ネット広告対策がすごい! | geopolitics academic | 應為 books_media、tech |
| 21 | [ddec8c24](https://tokyotaiwanradar.com/ja/events/ddec8c24-3dd7-4d6e-a26d-8a2962aa84ac) 熱烈台湾ファン語辞典 | books_media travel | 應為 taiwan_mandarin |
| 25 | [1da205f6](https://tokyotaiwanradar.com/ja/events/1da205f6-1064-45ca-bec0-fb5d42e08a17) 続　台湾は台湾 | books_media history | 應為 senses |
| 26 | [d1f877cc](https://tokyotaiwanradar.com/ja/events/d1f877cc-8421-4637-a178-7c7b54961349) 台湾夜市大全 | books_media taiwan_japan | 應為 folklore、urban、tourism |
| 29 | [09295b17](https://tokyotaiwanradar.com/ja/events/09295b17-0d36-44c6-9779-f6065c8c6e05) 台湾白魚…SATOYAMAイニシアティブ | geopolitics academic | 應為 nature、urban |
| 40 | [36f57e45](https://tokyotaiwanradar.com/ja/events/36f57e45-c26d-41c0-b8c1-9194aca5556e) やんばると台湾 | books_media academic | 應為 taiwan_japan |

錯誤型態：

- **`books_media` 被當成萬用標籤**：40 筆中 15 筆有 `books_media`。N 的 11 筆有 7 筆涉及它，
  其中 2 筆（#6、#10）只有 `books_media`、沒有主題分類。另有 7 筆判 Y 但註明「books_media
  不相關」（#11、22、33、34、35、36、39）。根源在凍結 prompt 的 FIELD RULES 寫了「Books may
  additionally get books_media」。
- **`taiwan_japan` 過度使用**：#5、#16、#26。
- **漏掉次要主題**（多數判 Y）：geopolitics（#1）、taiwan_mandarin（#8）、human_rights（#14）、
  tech（#15）、herbal／healthcare（#27、#30）、lifestyle_food（#31）。
- 無效 slug `travel` 出現 1 次（#21），正式流程的白名單會濾掉。

與正式 DB 現行分類對照（同 40 筆，2026-10-23 唯讀 SELECT）：現行值有 `["senses"]` 單標 6 筆、
含 `lecture` 9 筆、只有 `["books_media"]` 9 筆；凍結 prompt 的輸出對應為 0、0、2 筆。新 prompt 未達
門檻，但比現況明顯好。

使用者提出 `books_media` 對書目記錄的新定義：只用在以媒體生態、出版環境、媒體與出版產業、
假新聞、後真相、媒體研究為主題的作品。使用者決定在本案修正 prompt（成本上限 6 → 6.50 美元），
並另開 [#406](https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/issues/406) 處理網站的「所有新書」入口。
cand5 以後的措辭參考了 P_seal／P_h 的分類錯誤，P_seal 的分類結果因此不再是獨立驗證；第二輪分類檢查
改用 P_dev 與 P_h 未檢查過的記錄。

## 分類修正輪次（2026-10-23，只用 P_dev）

| 候選 | 相對 cand1 的改動 | SHA-256 前 12 碼 | 保留記錄 302 筆中：books_media／taiwan_japan／白名單後空分類／無效 slug | gate 變動 | 花費 |
|------|------|------|------|------|------|
| cand1 | — | `cec390cd7a4e` | 57／36／1／7 | — | — |
| cand5 | books_media 新定義、taiwan_japan 專用規則、不得空分類 | `856554b6b1c2` | 34／**99**／4／8 | 0 | $0.836 |

cand5 退步：點名 `taiwan_japan` 的限制規則反而觸發它（中台關係、美中會談都被標上）；`books_media`
仍留在寫真集、書評、雜誌、旅遊書；「必須有主題分類」讓模型自創 `travel`、`sports`、`education`、
`technology`、`architecture` 等 slug，白名單濾掉後變空。70 筆已標記錄的相關性判定與 cand1 完全相同。

cand6：拿掉 taiwan_japan 專用規則，也從主題範例清單移除 `taiwan_japan`；明訂只能用允許清單的 slug
並給對應（travel → tourism 等）；`books_media` 改為「作品在講媒體或出版」，列出不構成理由的格式
（書、旅遊書、寫真集、教科書、辭典、雜誌、報紙、專欄、書評），不確定時不加。SHA-256 前 12 碼
`b722d4b8ee16`。使用者同意成本上限再提高到 7.50 美元（執行前累計 $6.153）；cand6 未通過數字檢查
（taiwan_japan ≤ 36、books_media 明顯低於 57、白名單後空分類 ≤ 1、gate 不變）就停下，不再加輪。

cand6 結果（P_dev，$0.836）：books_media 33、taiwan_japan **8**、白名單後空分類 3、無效 slug 10；
70 筆已標記錄判定不變；gate 變動 1 筆：[仙台湾沿岸海岸防災林](https://tokyotaiwanradar.com/ja/events/2cbef058-b4eb-4468-95b7-7e6a3bc040aa)
（仙台灣，與台灣無關）cand1 正確丟掉、cand6 保留。**未通過**數字檢查（空分類、gate），依規則停下。
剩下的 books_media 正是 prompt 明列「不構成理由」的格式（寫真集、書評、旅遊書、雜誌），gpt-4o-mini 不照做；
人工修正回饋區塊不含 books_media，排除為成因。

使用者決定（2026-10-23）：
- 出貨 **cand6＋程式規則**。凍結 `prompts/frozen_cand6.txt`，SHA-256
  `b722d4b8ee16ce29fdbb9bf6b6ff98f6b4a59fe399baf64f20acca01292bc5a2`；對 P_h 執行（$0.230，累計 $7.219）。
- 程式規則（`annotator.py`，只作用於純出版物）：
  1. `_drop_format_only_books_media`：還有其他分類時移除 `books_media`；只剩它時保留，避免進空分類審核佇列。
     真正講媒體研究、又有其他主題分類的書會失去這個標籤，已接受。
  2. `_inject_keyword_categories(..., record_type)`：出版物不補 `lecture`／`report`／`tv_program`，
     `history`／`geopolitics` 照補。cand6 的 P_dev 保留記錄中原本會被補 report 18、lecture 12 筆。
- 第二輪門檻改為「比現況好」：同 40 筆盲測 A／B（正式 DB 現行分類 vs cand6＋程式規則），使用者各判 Y／N；
  新版 N 明顯少於現行就出貨，剩下的錯誤型態開 issue。第一輪 11／39 仍記為未達 ≤ 2。

第二輪檢查表（`~/.ai-notes/ttr/p5-eval/`）：`category_check2.html`（閱讀）、`category_check2.csv`（填 `ok_A`／`ok_B`）、
`category_check2_key.csv`（揭盲用，A 是 new 或 old）。樣本：cand6 在 P_dev 的保留記錄隨機 20
（`order_key(SEED+"category-check-2-dev")`）＋ P_h 未在第一輪出現的保留記錄隨機 20；40 筆中 9 筆 A=B。
P_dev 已用於 cand5／cand6 的開發，這 20 筆不是獨立驗證；P_h 的 20 筆沒有在開發時看過。

### 第二輪結果（2026-10-23，揭盲）：**通過**（新版 N 明顯少於現行）

| 集合 | 新版 N | 現行 N | 新 Y／舊 N | 新 N／舊 Y | 兩者皆 N | 符號檢定（雙尾） |
|------|------|------|------|------|------|------|
| P_dev 20 | 2 | 16 | 14 | 0 | 2 | p ≈ 1.2×10⁻⁴ |
| P_h 20 | 4 | 11 | 8 | 1 | 3 | p ≈ 0.039 |
| 合計 40 | **6** | **27** | 22 | 1 | 5 | p ≈ 5.7×10⁻⁶ |

已含裁決（#25 新版 N→Y，見下）。裁決前為新版 N 7、P_h p ≈ 0.070。P_dev 非獨立；P_h 單獨在 0.05 下顯著。

現行分類被判 N 的主因：`books_media` 當萬用標籤（11 筆只有它或以它為主）、出版物帶 `lecture`／`report`（8 筆）、
`senses` 當補位（4 筆）。這些在新版都消失。

新版仍為 N 的 6 筆（剩下的錯誤型態，另開 issue；#25 已裁決為 Y，保留在表中供對照）：

| # | 記錄 | 新版 | 使用者意見 | 型態 |
|---|------|------|------|------|
| 16 | [台湾ハイテクが抱えるインフラの制約](https://tokyotaiwanradar.com/ja/events/5ebaa745-d174-438c-95ae-99dbebb87cdd) | geopolitics academic | tech geopolitics | 漏 tech；期刊文章多加 academic |
| 19 | [2025年の台湾 好景気のなか深まる不安](https://tokyotaiwanradar.com/ja/events/15d0cf60-f2cf-4fd6-a326-2578a76fe312) | geopolitics academic | geopolitics | 期刊文章多加 academic |
| 22 | [奇天烈老画家と軟弱娘の台湾妖怪探索珍道中](https://tokyotaiwanradar.com/ja/events/eebeba83-1d24-4f78-aaad-912335ff67d5) | art | folklore | 漏 folklore |
| 24 | [台湾で待ち合わせ 気ままに食べたい中年旅](https://tokyotaiwanradar.com/ja/events/c4167080-278e-4700-989c-8da22618301c) | literature | tourism | 旅遊書漏 tourism |
| 25 | [台湾有事、日本の決断](https://tokyotaiwanradar.com/ja/events/b437abd9-3512-4d34-a4f4-58d4fc59acbd)（hanmoto） | geopolitics history | geopolitics | ~~多加 history~~ 裁決改 Y |
| 35 | [最新版 台湾 旅人地図帳](https://tokyotaiwanradar.com/ja/events/4cd09525-2661-451d-b053-0c12b939d5d5) | history | tourism | 旅遊書漏 tourism、誤標 history |
| 39 | [旅して学ぶ台湾](https://tokyotaiwanradar.com/ja/events/f1095b88-5b13-4973-9f9f-dada6c3c53ea) | history geopolitics academic | （現行 tourism study_abroad 為 Y，建議再加 history） | 旅遊書漏 tourism；唯一新版退步的一筆 |

判為 Y 但附建議的：#2、#12、#18 建議加 geopolitics，#8 建議加 art（漏次要主題）。

同一本書兩筆判定不同：#15（ndl，[d6d80433](https://tokyotaiwanradar.com/ja/events/d6d80433-5be8-466c-8a99-4f3e2ae2c2b8)）新版 geopolitics history academic 判 Y，
#25（hanmoto）新版 geopolitics history 判 N。使用者裁決（2026-10-23）：#25 新版改 Y，與 #15 一致；
理由是 `academic` 常有曖昧性，期刊文章乍看難判斷是否具學術性。盲標原值保留在 `category_check2.csv`。
#16、#19 的 N 判定不變（使用者未改判；#16 另漏 tech），但其中的 academic 可能同屬邊界情況。

剩下的錯誤型態已開 issue [#422](https://github.com/TuiTuiKoan/Tokyo_Taiwan_Radar/issues/422)。

