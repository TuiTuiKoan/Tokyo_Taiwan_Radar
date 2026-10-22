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

## 量測結果

（Phase B 完成後填入：各候選規則的 recall、N 移除率、被丟掉的 R 逐筆清單、holdout 結果。）

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
