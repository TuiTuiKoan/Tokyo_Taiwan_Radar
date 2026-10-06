---
title: TTR 2.0 三份 Architect spec 的 Plan Critic 評審（複雜度優先）
created: 2026-10-06
critic: Plan Critic
reviewed:
  - docs/specs/active/taiwan-relevance-scoring/（proposal.md、tasks.md）
  - docs/specs/active/intent-homepage/（proposal.md、tasks.md）
  - docs/specs/active/person-topic-entities/（proposal.md、tasks.md）
baseline: TTR strategy/2.0/TTR-2.0-pivot-requirements.md（D1–D5 已定案，本報告不重議）
---

# TTR 2.0 Plan Critique

> **模型註記**：本次批評與撰寫三份 spec 的 Architect 使用**同一模型家族**（Claude）。本環境無法切換到其他供應商的模型，照常執行。這份報告不能當成「已取得第二家模型視角」。
>
> **證據限制**：本次沒有 DB 存取權（環境中沒有 Supabase 憑證）。以下凡是需要 live 數字的主張，都標成「待量化」，不會當成事實。程式碼、migration、CI 執行紀錄（`gh run list`）與 `docs/weekly_review/` 都已實際讀過並引用。

---

## 0. 結論先講（前 5 個最重要的批評）

1. **🔴 每日爬蟲已經停擺 15 天以上，三份 spec 都沒有提到。** `gh run list --workflow scraper.yml` 顯示 `Daily Scraper` 從 **2026-09-21 起每天 failure**（最後一次成功是 09-20）。失敗的步驟是 `Run scraper`，之後的 annotate、merger、auto-QA 全部被 skip。`docs/weekly_review/2026-09-27.md`、`2026-10-04.md` 的本週新增事件是 **0 件與 1 件**，OpenAI 費用是 **$0.0000**（8 月時每週新增 60–122 件）。Plan Critic SKILL 的商業主軸第 1 名是資料完整性，「修壞掉的爬蟲」屬於 high value。**2.0 的任何實作都必須排在修復之後**；否則 relevance scorer 是在替一個不再更新的資料庫評分，首頁「今週の台湾」也會沒有本週活動。
2. **🔴 三份 spec 合計約 40–52 個工程日，需求文件 §9 的 Phase 0＋1 只有 6 週。** 三份都自評為 L，合計 17 個 phase、5 個 migration、約 13 張新表或新欄位群。若每週能投入 2.5 個工程日，全部做完需要 4–6 個月，還不包括 A/B 實驗至少 4–12 週的日曆時間。這個規模與 Q7「個人專案，精力有限」不相容。建議的最小可行 2.0（§5）約 15–25 個工程日。
3. **🔴 「公開可見性 gate」被拆成三套抽象，排除規則重複寫在 5 個地方，而且定義互相矛盾。** relevance 的 `web/lib/relevance.ts`（`applyHomeFeed`／`applyRadarFeed`，另有 Python 版）、person-topic 的 `web/lib/eventVisibility.ts`（`publicEventFilter()`，內含暫時排除規則）、homepage 的 `web/lib/homepage/eligibility.ts`（`homeQuery()`＋請求 `isHomeFeed(e)`），再加上 homepage 的意圖「共通排除」與 person-topic 的「relevance 上線前暫時排除」。例如對 `report` 的判斷：relevance 只把「`report` 且 event_form 全為 `other`」視為 article（`web/lib/types.ts:485-492`），homepage 則把所有含 `report` category 的活動排除。這正是 relevance 自己列為高風險的 R3（多個公開面不一致）。**必須合併成單一模組。**
4. **🔴 人工佇列已經處理不完，三份 spec 還要再加 6 種。** auto-QA pending 從 179 件（2026-08-02）成長到 348 件（2026-10-04），9 週增加約 19 件／週，從未下降（`docs/weekly_review/`）。三份 spec 新增的人工負荷包括：200 筆 ground truth 加 30 筆重標、relevance queue、每週 20 筆抽檢、新來源 precision 抽樣、`person_link_candidates`、Person 發布檢查清單（每人一份）、撤除 72 小時 SLA、`taiwan_connection` 證據確認、stale 連結審查，以及每週實驗報表。現有的佇列都清不掉，新佇列必須先砍到只剩「做了會直接改變公開結果」的那幾種。
5. **🟡 有兩個大型子系統可以延後，而且延後幾乎不損失決策品質：首頁 live A/B 實驗基礎設施，以及「個人」Person 實體。** homepage 的 D-8 自己算出，偵測 +10pt 需要每格約 360 名首次造訪者，LINE 轉換「幾乎不可能顯著」。即使如此，它仍然排了自建事件表、anon insert RLS、proxy cookie 指派、變體路由、kill switch 與隱私段落。person-topic 新增 9 張表、1 個 view 與 1–2 張指標表，但 §9 Phase 2 的種子供給方（早大日台留学生会、東京台湾の会、日本台湾学会）**全部是組織**，而既有的 `organizers`（206 列、公開 SELECT、`events.organizer_id` FK 在 upsert 時就會寫入，見 `scraper/database.py:290-320`）已經能支撐 Organizer 頁。

---

## 1. 商業主軸對齊與優先順序

| 項目 | 評分 | 理由 |
|---|---|---|
| 商業對齊 | 🟢 對齊 | 三份都直接對應需求文件 §7 的 P0，沒有偏離「全日本台灣相關活動聚合」 |
| 優先順序 | 🔴 應暫停到爬蟲修好 | 爬蟲停擺（見上方第 1 點）屬於 SKILL 定義的最高優先項目「修壞掉的爬蟲（事件斷流）」 |

**目前未完成、但比 2.0 更優先的事項（有證據）：**

| 事項 | 證據 | 與 2.0 的關係 |
|---|---|---|
| Daily Scraper 連續失敗 | `gh run list --workflow scraper.yml`：09-21 到 10-05 全部 failure；失敗步驟是 `Run scraper`，其後的 17 個步驟都是 skipped | relevance scorer 的 CI 步驟（tasks T2.9）排在 `Fix reviewed events…` 之後，在現況下**根本不會執行**；homepage 的「今週の台湾」依賴每週的新活動 |
| `Run scraper` 是單點故障 | `.github/workflows/scraper.yml:42-170`：annotate 到 auto-QA 之間的步驟都沒有 `if: always()` | 2.0 新增的任何 pipeline 步驟都會繼承這個脆弱性 |
| auto-QA 積壓持續成長 | 179 → 348 件（`docs/weekly_review/2026-08-02.md` → `2026-10-04.md`）；其中 `missing_organizer` 有 118 件 | person-topic 的 resolver 以 `organizer` 欄位為主要候選池；缺 organizer 的活動越多，Person 連結的覆蓋率越低 |
| LINE 分類偏好是「已承諾但沒有實作」的功能 | `web/app/api/line-webhook/route.ts:318-331` 回覆「每週推播將包含這些分類的精選活動」，但 `scraper/` 中沒有任何程式讀取 `category_preferences` | 這是現有使用者已經看得到的承諾。修好它，比在網站上另做一套需要登入的 follow Topic 更早觸及真實用戶（見 §3.3） |

---

## 2. 每份 spec 的複雜度評分

依 Plan Critic SKILL 的啟發式評分（每 +1 level 約等於半天工程量；≥ 3 為 high，≥ 5 為 very-high）。工程日的估算以「一個專注工作日，含 AI agent 協作與驗證」為單位。

| Spec | 複雜度訊號 | Level | 複雜度 | 業務價值 | 比值 | 全量估算 |
|---|---|---|---|---|---|---|
| taiwan-relevance-scoring | 2 個 migration（+2）、跨 3 個以上檔案（+1）、新 GPT 呼叫路徑（+1）、觸發 Database Safety／Policy supersession／Supabase 分頁等 Guard（+1）、i18n（+0.5）、新 CI workflow | 5.5 | very-high | high（資料品質 P0） | 🟡 瘦身後可接受 | 11–14 天，另需創辦人 5 小時 |
| intent-homepage | 1 個 migration（+1）、新 anon insert RLS 表（+2）、跨 3 個以上檔案（+1）、i18n（+0.5）、Design System／i18n Regression Guard（+1）、proxy rewrite＋ISR＋cookie（+1） | 6.5 | very-high | 首頁 IA：medium-high；A/B 基礎設施：low（流量不足） | 🔴 實驗部分失衡 | 13.5–16.5 天，另加 4–12 週日曆時間 |
| person-topic-entities | 2 個以上 migration（+2）、9 張表的 RLS 與 GRANT（+2）、GPT 呼叫路徑（+1）、修改 `merger.py`（雖然不動 `_normalize`，+1）、跨 3 個以上檔案（+1）、i18n（+0.5）、多個 Guard（+1） | 8.5 | very-high | Topic＋follow：medium；個人 Person：medium-low（H2、H3 都還沒驗證） | 🔴 失衡 | 15.5–21.5 天，另加持續的人工審核 |

三份合計約 **40–52 個工程日**。

### 2.1 taiwan-relevance-scoring

這份 spec 的盤點品質高：它正確指出 `annotator.py:1051-1071` 的 gate 只寫在 prompt 裡，而寫入點 `annotator.py:2743` 固定設 `annotation_status="annotated"`，不輸出任何結構化的關聯度訊號（已查證）。scorer 不寫 `is_active`、不改 annotator，這兩點都正確。問題出在「v1 的範圍」太大。

| # | 批評 | 證據 | 修改點 |
|---|---|---|---|
| RS-1 | **確定性規則可以先做，不需要 LLM，大約 1 天就能交付 R-QA-3 與 R-QA-4 的大部分。** content_type 判定順序的前 3 步（publication exact invariant、broadcast、pure report）以及 `geopolitics` 排除，都只用既有欄位就能判斷。現行首頁沒有任何這類排除（`web/app/[locale]/page.tsx:54-61` 只過濾 `is_active` 與 `annotation_status`；`EventListClient.tsx` 只用 `getPublicationPresentationFlags` 調整顯示，不做過濾） | 已查證 | 把「確定性 home 排除」拆成 Phase 0.5，不需要 migration，先上線 |
| RS-2 | **先量 S1 基準，再決定是否需要 LLM scorer。** Architect SKILL 的「規模量化先於工具化」要求先量化，但 spec 把量化（T0.2、T0.7）和工具建置（T0.4 的完整 golden 工具）綁在同一個 phase。只標 S1 的 80 筆（約 1.5 小時），就能得知首頁雜訊率，以及雜訊的成因分布（非台灣／非活動／政治）。如果 RS-1 的規則已經把雜訊降到 ≤ 5%，Phase 1–2 的 LLM scorer 可以延後 | 需求文件 §14 也承認「報告 B 的雜訊範例來自某一時點的首頁快照，需要以 DB 抽樣確認比例」 | Phase 0 改成兩段：S1 標註 → 套用 RS-1 → 重算雜訊率 → go／no-go |
| RS-3 | **三訊號加權並在 140 筆 dev 上做 grid search，會過度擬合。** 這會產生 5 個自由參數（w1、w2、w3、T_HOME、T_RADAR），還要加上 `relevance_rules.py` 的 5 個特徵、`relevance_source_priors.json`，以及 Phase 4 的每月重新校準。140 筆資料撐不起這個參數量 | D-1 的合成公式 | v1 只用「LLM centrality＋evidence 驗證＋確定性 caps」直接對應到 tier，門檻固定；source prior 與 rule score 延到 v2，有資料證明需要時再加 |
| RS-4 | **Ground truth 的統計設計不能支撐它自己設的 gate。** (a) holdout 只有 60 筆，被分到 home 的大約 20–30 筆；即使 0 筆錯誤，95% 信賴區間上界仍有約 10–14%，所以「holdout 雜訊率 ≤ 5%」這個 gate 沒有鑑別力。(b) 雜訊率是在**混合 strata** 上計算，但 S3（30 筆已知負例）與 S4（30 筆政治邊界）是刻意過採樣，算出的數字不代表首頁的實際分布。(c) レーダー召回率 ≥ 95% 在大約 30–40 筆正例上，錯 2 筆就會失敗，gate 會隨機翻轉 | D-5 | 首頁雜訊率只用 S1（或依 strata 加權）；召回率用全部 200 筆並做 k-fold，不用單一 holdout；gate 改成「點估計 ≤ 5%，且信賴區間上界 ≤ 創辦人設定的值」 |
| RS-5 | **`queue` 若在公開面完全隱藏，就同時製造出 R1（過度過濾）與一個新的人工佇列。** spec 自己把 R1 列為最高風險，緩解方式卻是「人工依分數由高到低審 queue」，這又加重了 Q7 的負擔 | D-3、D-8、F1 | 建議 F1 採「低分＝radar 可見，只是不上首頁」。`queue` 只作為 AdminEventTable 的一個篩選器，不新增動作按鈕（「不相關」已經有既有路徑：`web/lib/reportActionsCore.ts:203-208`）。這樣就不需要 `feed_tier` 的 FC 鎖與兩個新動作。注意：這和 R-QA-2「低分進人工佇列」的字面意思不完全一致，需要創辦人裁決（見 §6 的 FD-4） |
| RS-6 | **Phase 4 的 migration 098（`research_sources` 的 precision 三欄）不需要。** 需求文件 R-QA-5 的驗收是「Researcher 的來源評估加入 precision 欄位」，寫進 profile 的 markdown 就能滿足。加上週報顯示 researcher/slot0–3 本週都產出 0 件，新來源的流量本來就很低 | `docs/weekly_review/2026-10-04.md` | 保留 SKILL 政策替換與 `auto_research` 不再自動升級（約 0.5 天）；刪除 migration 098 與 `update_source.py` 的新旗標；每週 20 筆抽檢改成每月 |
| RS-7 | **Surface matrix 有遺漏。** 沒有列入：`web/app/[locale]/announcements/[slug]/page.tsx:68`（公告連結的活動清單）、`events/[id]/page.tsx:381-385`（同 work 的其他場次）、person-topic 的 Topic 頁與 `/saved` 追蹤區塊，以及 homepage 的 `/radar` 意圖結果 | 已用 grep 查證 `from("events")` 的呼叫點 | 補進 D-7；跨 spec 的部分改由 §3 的單一可見性模組處理 |
| RS-8 | **CI 步驟位置。** 在 `scraper.yml` 中，`Run scraper` 失敗時後續步驟全部被 skip（目前每天都是這樣）。T2.9 的 scorer 步驟需要 `if: always()`，否則爬蟲一旦部分失敗，評分就會靜默停止 | `gh api …/jobs` 的步驟結果 | T2.9 加上 `if: always()` |

### 2.2 intent-homepage

這份 spec 的盤點很紮實（寫死的「100+」位置、`BackToListButton`、`_hp` private folder 陷阱、`filterEvents` 用 UTC 判斷今天，都已查證）。`/radar` 搬遷與舊 URL 308 是必要且正確的設計。問題集中在實驗基礎設施，以及多張映射表。

| # | 批評 | 證據 | 修改點 |
|---|---|---|---|
| IH-1 | **Live A/B 的成本最高、資訊量最低。** Phase A 的事件表、Phase D 的 proxy cookie 指派、變體路由、ISR spike、kill switch、報表腳本、隱私段落，以及 E-3 的資料清理，合計約 6–8 個工程日，再加 4–12 週的日曆時間。spec 自己的樣本量表已經說明 LINE 轉換「幾乎不可能顯著」。D4 的文字是「用原型測試決定」；§9 Phase 1 第 1 項本來就有 8–10 人訪談，first-click 測試可以直接在訪談中完成 | D-8 樣本量表 | 預設路徑改成「訪談 first-click＋5 秒測試」。live 實驗只有在 Phase A 量到的流量通過 gate **之後**才建置，不要預先蓋好。若仍想取得 live 證據，可用「前後期比較」（先上 L4 兩週，再換 L3 兩週），不需要 cookie 與變體路由 |
| IH-2 | **R-HP-4 的 IP 推定地區價值低、成本不低。** 需要 proxy 讀 header、47 個都道府縣的對照表與測試，以及第二個 cookie。首頁本身是 ISR，地區只能在 client 端套用，而且 spec 也決定「不過濾、只排序」，5–8 筆中真正受到影響的很少 | D-5 | P0 只保留「記住上次選擇」的 cookie，IP 推定延後 |
| IH-3 | **映射表過多。** 4 個意圖、3 個模式、8 個チャンネル，各自有一份 Category 映射，再加一份「共通排除」。整個網站的分類法因此有 6 套：40 個 Category、5 個 `CATEGORY_GROUPS`、LINE 的 8 個分組（`route.ts:80-85` 的五感／文藝／生活／體驗／學術／社會／科技／旅遊）、8 個 Topic、4 個意圖、3 個模式 | `web/lib/types.ts:356-383`、`route.ts:80-85` | 意圖改成「Topic slug 的聯集」，不直接列 Category；模式（觀／學／話）只用 `event_form`。這樣只剩一張 Topic → Category 映射表，而且它的擁有者是 person-topic |
| IH-4 | **「今週の台湾」的資料來源和 spec 的假設不同。** `weekly_line_broadcast.py` 要求 GPT 選出「exactly 10」個 weekly（未來 21 天內開始）與 10 個 monthly 活動，並把兩組**一起**寫進 `announcement_events`（`weekly_line_broadcast.py:202, 221, 758-762`）。`announcement_events` 沒有 section 或排序欄位（`030_announcements.sql:31-35`），所以下個月的活動也會流進「今週」。如果 `auto_publish=true`，整份清單就沒有任何人工挑選 | 已查證 | picks 只取 start_date 落在本週（JST）的連結活動；「人工挑選」的文案要依 `auto_publish` 的實際設定修正 |
| IH-5 | **首頁上線被綁在 relevance 回填完成之後**（C-12a）。如果改用 RS-1 的確定性規則作為 home 的 v0 定義，首頁就可以先上線，之後 LLM scorer 上線時，只需在同一個 helper 內部切換，不必等待 | D-6 | C-12a 的閘門改成「單一可見性模組已套用」，不再要求 `feed_tier IS NULL = 0` |
| IH-6 | `when` 使用 JST，但同一個 `filterEvents()` 的 `today` 是 UTC（`web/lib/eventFilter.ts:53`）。同一個函式裡會有兩種日期語意 | 已查證 | 順手把既有的 `today` 改成 JST，不要讓兩套並存 |
| IH-7 | 季節の台湾フェス（D-4b）屬於「選做」，但它在 tasks 中仍然佔 C-14 與一個 feature flag | — | 直接移出本 spec |

### 2.3 person-topic-entities

這份 spec 的倫理設計（不設國籍欄位、未認領的個人預設 noindex、不寫 AI bio、tombstone）以及對三套既有人／組織結構的盤點都很好，已查證 `020_creators.sql:15` 確實有 `nationality`。問題在於：這是三份裡最重、驗證最少，而且需求文件本身時程定位就不一致的一份。

| # | 批評 | 證據 | 修改點 |
|---|---|---|---|
| PT-1 | **需求文件內部不一致，spec 選了比較早的那一邊。** §7 把 Person 與 Topic 列為 P0，但 §9 路線圖把「Person／Organizer 頁、follow Topic」放在 **Phase 2（1–3 個月）**，Phase 1 只有訪談、A/B、relevance 與試標。spec 以「越早上線越好（H2 計時）」為理由前移。這個時程衝突應該由創辦人裁決，而不是由 spec 自行決定 | 需求文件 §7、§9 | 列為 FD-6 |
| PT-2 | **Organizer 頁可以直接建在既有的 `organizers` 上。** `organizers` 已經有 `canonical_name_*`、`aliases`（GIN index）、`homepage`、`organizer_type`、公開 SELECT（`050_entity_tables.sql:15-26`）；`events.organizer_id` FK 在 upsert 時就會寫入（`scraper/database.py:290-320`），歧義的情況也已經有處理。只要加上 `slug`、`status`、`external_links`、`description_*` 欄位，再做一個頁面，就能涵蓋 §9 Phase 2 種子供給方（全部是組織）。spec 的 Q3 也建議 P0 只做 civic group 與學會 | 已查證 | P0 的「Organizer」改用 `organizers` 擴欄；`people` 系列整組延後 |
| PT-3 | **個人 Person 是隱私、同名異人、撤除流程與 resolver 成本的來源。** `person_aliases`、`person_link_candidates`、`person_admin_meta`、`event_people`、`link_people.py`（5 階比對＋LLM 分類）、stale 偵測、撤除 SLA、`merger.py` 改指，全部都是為了「個人」而存在。只要等到 `organizer-submission-v2` 的認領流程（R-SP-3）上線後，改成「由投稿者或認領者建立」，同意就內建在流程裡，resolver 與大部分撤除流程也就不需要了 | proposal §3.3–3.6 | 延後到 R-SP-3 之後，改成由供給端建立 |
| PT-4 | **Topic 不需要 DB 表。** 8 個固定頻道，映射修改「在 P0 走 SQL／migration」，因此 `topics` 與 `topic_categories` 這兩張表加上唯讀的 `admin/topics` 頁，換到的只是 `user_follows.topic_id` 的 FK。用一份 TS＋Python 共用的常數，加上 `user_follows.topic_slug text CHECK (…)`，就能達到同樣效果。homepage 本來就打算用常數作為 fallback | proposal §2.1、§6 | Topic 改成程式常數；刪除 `admin/topics` |
| PT-5 | **網站上的 follow Topic 需要登入，但已登入的使用者規模不明（待量化）。** 需要先量 `auth.users` 數與近 90 天有 `saved_events` 寫入的使用者數。如果只有個位數，H2 的 4 週回訪率不會有任何統計意義。另一方面，LINE 好友已經能設定分類偏好，只是推播從來沒有讀取（§1） | `022_line_subscribers.sql:12`、`route.ts:318-331` | 創辦人先看這兩個數字，再決定 follow 要先做 web 還是 LINE（FD-7） |
| PT-6 | **沒有消費者的介面。** `event_person_signals` view：relevance spec 的 `tw_org` 特徵讀的是 organizer 字串與機構詞表，並沒有引用這個 view。`entity_views` 與 `user_active_days` 是為了量 H2，但它們依賴的使用者基數還沒確認 | relevance D-1；person §5.1、§8 | 三者都刪除或延後 |
| PT-7 | **9 張表、5 種 RLS 模式、10/30 的 GRANT 政策**，代表 migration 本身就需要 1–2 天的逐行驗證（V1–V8）。這是 Plan Critic SKILL 中「修改 RLS / Supabase 權限 +2 level」的典型情況 | tasks Phase A | 縮到 MVP 後只剩：`organizers` 加欄位（沿用既有 policy）＋`user_follows` 一張表 |

---

## 3. 跨 spec 衝突清單（依嚴重度排序）

| # | 嚴重度 | 衝突 | 涉及 | 建議處置 |
|---|---|---|---|---|
| X1 | 🔴 高 | **可見性 gate 有三套抽象，排除規則寫了 5 份。** `web/lib/relevance.ts`（`applyHomeFeed`／`applyRadarFeed`，另有 Python 版）、`web/lib/eventVisibility.ts`（`publicEventFilter()`，含 base 條件與暫時排除）、`web/lib/homepage/eligibility.ts`（`homeQuery()`）＋`isHomeFeed(e)`、意圖「共通排除」、person-topic 的暫時排除。**定義互相矛盾**：relevance I-1 說 base 條件「由各查詢自行帶上」，person-topic 的 `publicEventFilter` 則把 base 條件包在裡面；`report`、`tv_program`、`business` 在 relevance 與 homepage 中的判準不同（見 §0 第 3 點） | 三份 | 只保留**一個**模組（建議沿用 `web/lib/eventVisibility.ts` 這個名稱），擁有者是 relevance spec，匯出：`applyPublicBase(q, {includeSubEvents})`、`applyFeed(q, 'home' \| 'radar')`、`isFeed(e, tier)`（client 用），以及排除規則常數。Python 版放在 `scraper/visibility.py`，用 parity test 保證一致。homepage 的 `eligibility.ts` 與意圖「共通排除」都刪除；person-topic 的暫時排除改成直接呼叫 `applyFeed` |
| X2 | 🔴 高 | **三份都依賴「每日有新活動」，但爬蟲已經停擺**，而且沒有任何一份把它列為前置條件 | 三份 | 在三份的 Phase 0 加上閘門：「`Daily Scraper` 連續 3 天 success」 |
| X3 | 🟠 中高 | **Migration 序號重複宣告。** relevance：`097_event_relevance`、`098_research_sources_precision`；person-topic：`097_person_topic_entities`、`098_user_follows`；homepage：`<next>_homepage_experiment_events`。三份也都會修改 `.github/instructions/database.instructions.md` 同一段「Latest／next」 | 三份 | 現在就分配號碼。依 §5 的 MVP，只剩 3 個以內的 migration：`097` relevance（若 M7 成立）、`098` `organizers` 擴欄、`099` `user_follows`。homepage 的事件表在 MVP 中刪除 |
| X4 | 🟠 中高 | **熱點檔案。** `web/app/[locale]/page.tsx`（relevance T3.3 加 predicate；homepage B-1 搬到 `radar/`，C-12 重寫）；`web/app/sitemap.ts`（三份都改）；`events/[id]/page.tsx`（relevance：queue noindex；person：:1065-1125 加連結）；`about/page.tsx`（relevance：編輯方針；homepage：動態數字與アクセス解析）；`web/lib/types.ts`、`web/messages/{ja,zh,en}.json`、`database.instructions.md`（三份都改） | 三份 | **合併順序**：homepage Phase B（純搬遷）先合併 → 可見性模組（X1）→ 新首頁 → 其餘。`/radar` 與首頁共用同一個 server fetcher（例如 `getRadarEvents()`），讓 predicate 只存在一個地方，不受路由搬遷影響。三個 worktree 不要同時改這些檔案 |
| X5 | 🟠 中 | **分類法增生**：40 Category ／ 5 `CATEGORY_GROUPS` ／ LINE 8 分組 ／ 8 Topic ／ 4 意圖 ／ 3 模式 ／ R-FL-3 的 4 個頻道 | 三份＋既有 LINE | Topic slug 是唯一的使用者層分類；意圖＝Topic 的聯集；LINE 偏好改用 Topic slug（交給 `line-segmented-digest`） |
| X6 | 🟠 中 | **Topic feed 的可見性語意沒有對齊。** relevance I-2：follow 的 Topic feed 用 radar predicate；homepage F-2：請求 helper 接受 `feed: 'home' \| 'radar'`；person-topic 的 `publicEventFilter` 沒有 tier 參數；`/saved` 的追蹤區塊不在 relevance 的 surface matrix 中（matrix 寫「`/saved` 不過濾」，但追蹤區塊不是使用者主動收藏的內容） | 三份 | 由 X1 的 `applyFeed(q, tier)` 統一處理；在 surface matrix 補上「Topic 頁＝radar」「`/saved` 追蹤區塊＝radar」「首頁 Topic 區塊＝home」 |
| X7 | 🟠 中 | **週報同時當作首頁選題來源，以及「LINE 只取 home」。** relevance T3.3 讓週報只取 `home`；週報的 GPT 選題要求「exactly 10＋10」（`weekly_line_broadcast.py:202, 221`），候選池變小時可能湊不滿。homepage 又以週報作為「今週の台湾」的來源（見 IH-4） | relevance、homepage | relevance 的 F6 預設改成「home 優先，不足時用 radar 補」；homepage 只取本週的子集 |
| X8 | 🟡 低中 | **命名與介面漂移。** person-topic §5.1 舉例 gate 欄位叫 `relevance_tier`，relevance 的實際命名是 `feed_tier`；`event_person_signals` 沒有消費者 | person、relevance | person-topic 改用 `feed_tier`；刪除 view |
| X9 | 🟡 低 | `filterEvents()` 的 `today` 是 UTC，homepage 的 `when` 是 JST | homepage | 統一改成 JST |
| X10 | 🟡 低 | About 頁同時被兩份 spec 加段落（編輯方針、アクセス解析） | relevance、homepage | 若刪除 A/B 事件表，就不需要アクセス解析段落；只保留編輯方針 |

---

## 4. 建議砍掉、延後、合併的項目

### 4.1 砍掉（MVP 不做，也不預留程式碼）

| 項目 | 來源 | 理由 | 估計省下 |
|---|---|---|---|
| `homepage_experiment_events` 表、proxy 變體指派與 rewrite、變體路由、kill switch、報表腳本、アクセス解析段落、E-3 資料清理 | homepage A-5〜A-11、D-1〜D-8、E-3 | 流量不足（IH-1）；改用訪談 first-click 測試 | 6–8 天 |
| IP 推定地區（`ttr_region_guess`、47 縣對照表） | homepage C-8 | IH-2 | 1 天 |
| 季節の台湾フェス | homepage C-14 | 選做項目 | 0.5–1 天 |
| `research_sources` migration 098、`update_source.py` 的新旗標 | relevance T4.3、T4.4 | RS-6 | 1 天 |
| source prior JSON、權重 grid search、每月重新校準 | relevance T1.3、T1.7（部分）、D-1 | RS-3 | 1.5–2 天 |
| `topics`、`topic_categories` 表、`admin/topics` | person B | PT-4 | 1–1.5 天 |
| `event_person_signals` view、`entity_views`、`user_active_days` | person §5.1、§8、Phase E | PT-6 | 1–1.5 天 |
| `web/lib/homepage/eligibility.ts`、意圖「共通排除」、person 的暫時排除 | homepage C-4、D-3；person B | X1 | 合併後減少維護面 |

### 4.2 延後（有明確的觸發條件）

| 項目 | 觸發條件 |
|---|---|
| LLM relevance scorer（relevance Phase 1–2） | S1 基準套用 RS-1 規則後，雜訊率仍然 > 5% |
| relevance 的 hidden `queue`＋admin 動作 | FD-4 決定要隱藏，而且 dry-run 量出的 queue 數量是人工可以處理的 |
| 個人 Person 全套（`people`、`person_admin_meta`、`person_aliases`、`person_topics`、`event_people`、`person_link_candidates`、`link_people.py`、`merger.py` 改指、撤除流程、`person_claims`） | `organizer-submission-v2` 的認領流程上線，而且 Organizer 頁與 follow 的使用數據支持 H2 |
| Live A/B | Phase A 的流量量測顯示 ≤ 6 週可以達到 +10pt 偵測 |
| 每週 20 筆抽檢 | 改成每月 20 筆，直到 auto-QA 積壓開始下降為止 |

### 4.3 合併

| 合併 | 結果 |
|---|---|
| relevance `relevance.ts`＋person `eventVisibility.ts`＋homepage `eligibility.ts` | 單一 `web/lib/eventVisibility.ts`（X1） |
| homepage 的 4 套映射＋person 的 Topic 種子映射＋LINE 分組 | 單一 Topic 常數（TS＋Python，各一份，有 parity test） |
| relevance 的 About 編輯方針＋homepage 的頁尾連結 | 編輯方針段落只寫一次，由 relevance 負責 |
| person 的「Person／Organizer」＋既有 `organizers` | P0 只做 Organizer（擴充 `organizers`） |

---

## 5. 最小可行 2.0（建議實作順序與工時）

原則：每一步都能獨立上線；先做確定性、零 LLM、零新表的部分；LLM 與新實體只在有量化證據時才加。

| 步驟 | 內容 | 工程日 | 創辦人時間 | 交付的需求 | 對應路線圖 |
|---|---|---|---|---|---|
| **M0** | 修好 `Daily Scraper`（`Run scraper` 從 09-21 起失敗），並讓 annotate 之後的步驟在部分來源失敗時仍然執行 | 0.5–2 | 0.5 小時（若需要輪換 secrets） | 資料完整性 | Phase 0 |
| **M1** | S1 基準：從現行首頁 payload 抽 80 筆，用 TSV 標註（OK／非台灣／非活動／政治），算出雜訊率與成因分布 | 0.5 | 1.5 小時 | H5 前測 | Phase 0 |
| **M2** | 單一可見性模組 `web/lib/eventVisibility.ts`＋`scraper/visibility.py`：base 條件＋v0 的 home 排除規則（publication invariant、pure report、broadcast／tv／radio、`geopolitics`），只用既有欄位，不需要 migration；套用到現行首頁、LINE 週報與 X 自動貼文。完成後重算 M1 的雜訊率 | 1–1.5 | 0.5 小時（重算） | R-QA-3、R-QA-4（大部分） | Phase 0 |
| **M3** | R-HP-5 動態來源數（homepage A-1〜A-4） | 0.5 | — | R-HP-5 | Phase 0 |
| **M4** | `/radar` 搬遷、舊 URL 308、Navbar 與 BackToList、sitemap；首頁與 `/radar` 共用 `getRadarEvents()` | 2–3 | — | R-HP-1（一半） | Phase 1 |
| **M5** | 新首頁：L4＋A 案預設；意圖＝Topic slug 的聯集；模式 chip；`when=week`（JST）；只記住上次選擇的地區；「今週の台湾」只取週報中的本週子集；LINE 與投稿 CTA。全部透過 M2 的 `applyFeed(q,'home')` 取資料 | 4–5 | 1 小時（Designer 視覺審閱） | R-HP-1、R-HP-2、R-HP-4（簡化版） | Phase 1 |
| **M6** | 訪談 8–10 人，在 preview 上做 first-click 與 5 秒測試（三選一 vs 四意圖、A／B／C 文案）；裁決記錄在 Decision Log | 0.5（preview 參數） | 8–10 小時 | R-HP-3（質性路線）、D4 | Phase 1 |
| **M7**（條件式） | 只有在 M2 之後雜訊率仍 > 5% 時才做：migration `097`（`feed_tier`、`relevance_score`、`relevance_version`、`relevance_signals`、`content_type`）；LLM centrality＋evidence 驗證＋確定性 caps，固定門檻；ground truth 補到約 200 筆（S1 再加負例與邊界例）；回填；每日 CI（`if: always()`）；低分＝radar 可見＋admin 篩選器。tier 的計算放進 M2 模組內部，呼叫端不用改 | 5–7 | 3 小時 | R-QA-1、R-QA-2 | Phase 1 後段到 Phase 2 |
| **M8** | Topic（常數）＋follow：先依 FD-7 擇一。(a) LINE：讓週報讀取偏好，改用 Topic slug（2 天，兌現既有承諾）；或 (b) Web：`099_user_follows`（`topic_slug`）＋Topic 頁（多 category 列表，重用分類頁元件）＋`/saved` 追蹤區塊（3–4 天） | 2–4 | — | R-FL-1（或 R-FL-3 的前身） | Phase 2 |
| **M9** | Organizer 頁：`098` 擴充 `organizers`（`slug`、`status`、`external_links`、`description_*`）；只發布 civic group 與學會（種子供給方約 10–20 個）；活動頁透過既有的 `organizer_id` 連結 | 3–4 | 2–3 小時（逐一確認） | R-EN-2（組織部分） | Phase 2 |
| | **合計** | **約 15–25**（不含 M7）／**20–32**（含 M7） | 約 17–20 小時 | | |

和全量的 40–52 天相比，約可省下一半工程量。省下的主要是 A/B 基礎設施、個人 Person 子系統、LLM scorer 的參數化，以及三套可見性 helper。MVP 只新增 2–3 個 migration、1 張新表（`user_follows`）。新增的固定人工佇列只有一種：每月 20 筆抽檢（M7 成立時）。

**路線圖對照**：需求文件 §9 的 Phase 0（0–2 週）對應 M0–M3，可以達成。Phase 1（2–6 週）對應 M4–M6，若每週投入 2.5 天，約需 3–4 週，可以達成。原本三份 spec 的 Phase 1 範圍（relevance 上線＋A/B 的 4–12 週日曆時間），在 6 週內**不可能**完成。

---

## 6. 需要創辦人決定的事項（已與三份 spec 的 F／Q 去重合併）

以「FD」編號；括號內是原始編號。依「會擋住 MVP 的順序」排列。

| ID | 決定事項 | 建議 | 擋住 |
|---|---|---|---|
| **FD-1** | 是否同意「先修爬蟲，2.0 實作暫停到 `Daily Scraper` 連續 3 天 success」？ | 同意 | 全部 |
| **FD-2** | 是否接受 §5 的 MVP 範圍（砍掉 A/B 基礎設施、延後個人 Person 與 LLM scorer 的條件式啟動）？ | 接受 | M2 之後 |
| **FD-3** | 每週可投入的人工時間上限（小時／週），以及哪些既有佇列（auto-QA 348 件）可以降級或關閉 | 先定上限，所有新佇列都必須排進這個額度 | M7、M9 |
| **FD-4**（relevance F1） | 低分活動在公開面要隱藏（queue），還是在レーダー可見、只是不上首頁？ | 可見＋admin 篩選器（RS-5）。注意：這和 R-QA-2 的字面意思不同，需要明確裁決 | M7 |
| **FD-5**（relevance F2、F3；homepage 共通排除） | home 的排除集合：`geopolitics` 之外，是否加入 `human_rights`？`business`、`report`、`tv_program` 要用「整個 category 排除」還是 relevance 的 content_type 判準？非 event 類型在レーダー預設顯示還是隱藏？ | `geopolitics` 必排；`report` 只排 pure report；`business` 先不排，等 M1 的成因分布 | M2 |
| **FD-6**（新；person 的時程） | Person／Topic 依 §7 列為 P0，還是依 §9 放到 Phase 2？ | 依 §9：Phase 2 | M8、M9 |
| **FD-7**（新；與 person H2 相關） | follow Topic 先做 LINE（讀取既有的 `category_preferences`）還是 web（需要登入）？決定前先量：`auth.users` 數、近 90 天的 `saved_events` 使用者數、`line_subscribers` 數 | 先看數字；預設 LINE 優先 | M8 |
| **FD-8**（homepage Q1、Q2、Q4、Q5） | 文案預設案；實驗路線改為訪談 first-click（live A/B 只有在流量通過 gate 時才建置）；Vercel 自訂事件與 LINE「友だち追加経路」是否可用 | A 案；質性路線為預設 | M5、M6 |
| **FD-9**（homepage Q3、Q8、Q9；relevance F6） | 「今週の台湾」與週報共用選題（只取本週子集）？公告列是否保留？週報只取 home 還是 home 優先、radar 補位？目前 `auto_publish` 是否開啟（若開啟，就沒有人工挑選）？ | 共用；保留 3 筆；home 優先＋radar 補位 | M5 |
| **FD-10**（person Q1；homepage 的 music 映射） | 音楽頻道：新增 `music` Category，還是暫用「音楽・舞台」？ | 暫用「音楽・舞台」 | M5、M8 |
| **FD-11**（person Q3） | Organizer 頁的範圍：只做 civic group 與學會，政府與半官方機構不做 | 同意 | M9 |
| **FD-12**（relevance F4、F5、F7、F8） | 由誰標註 ground truth（建議創辦人）；R-QA-5 的 precision 門檻；編輯方針文字由誰寫；scorer 的模型 | 創辦人標；0.6／0.3；先放精簡版；gpt-4o-mini 常數化 | M7 |
| **FD-13**（homepage Q6、Q7；person Q2、Q4–Q7） | 關西是否拆區；隱私告知；未認領的個人 noindex；撤除管道與 SLA；`organizers` 的台灣欄位；`user_active_days`；「台湾人主催」標籤 | **全部延後**：在 MVP 中，這些問題都不再阻擋任何步驟（個人 Person 與實驗表都已延後） | 無 |

---

## 7. 必檢查項

- [x] **Guard 觸及**：Database Safety（scorer 不寫 `is_active`，✅ 已遵守）、Policy supersession（relevance D-9，✅）、Design System Guard（homepage D-10，✅）、i18n Regression Guard（三份都有，✅）、Merger `_normalize()` Guard（person 動 `merger.py` 的合併後處理，延後即可避開）、Manual Translation Fix Persistence（本次沒有觸及）、SCRAPERS List Completeness（沒有新增 scraper，不適用）。**新發現的 Guard 缺口**：沒有一份 spec 檢查 pipeline 健康，這是 X2。
- [x] **新 component**：homepage 有 8 個 `web/components/home/*`，已列出要重用的 `CARD_LINK`、`PillButton`、`DesignSelect`、`FilterChip`、`Badge`（已查證存在）。person 的 `FollowButton` 沿用 `SaveButton` 的模式。🟡 部分新增，可接受。
- [x] **新 DB 欄位／migration**：全量共 5 個，序號衝突（X3）；MVP 縮成 2–3 個。
- [x] **新 i18n key**：三份都要求三語同步，且不刪除既有 key，✅。
- [ ] **新 scraper**：不適用。

**復用率評估**：🟡 部分新增。relevance 正確重用了 `build_event_user_content`、golden 目錄慣例、irrelevant 下架路徑；homepage 正確重用了週報選題；person 則**重造了** Organizer（`organizers` 已經存在）與 Topic 表（常數就夠了）。

---

## 8. 給 Architect 的修改 diff 點（不重寫計畫）

1. 三份的 Phase 0 都加上「`Daily Scraper` 連續 3 天 success」閘門。
2. relevance：新增 Phase 0.5（RS-1 確定性規則＋單一可見性模組）；Phase 1–2 改成條件式（RS-2）；D-1 刪除 source prior 與 grid search（RS-3）；D-5 改統計設計（RS-4）；D-7 補上遺漏的 surface（RS-7）；T2.9 加 `if: always()`（RS-8）；刪除 migration 098（RS-6）；成為 `eventVisibility.ts` 的唯一擁有者（X1）。
3. homepage：刪除 Phase D 與 A-5〜A-11，D-8 的預設改成質性路線（IH-1）；刪除 C-8 的 IP 推定與 C-14（IH-2、IH-7）；意圖改成 Topic 聯集（IH-3）；picks 只取本週子集（IH-4）；C-12a 改用可見性模組作為閘門（IH-5）；刪除 `eligibility.ts`（X1）。
4. person-topic：拆成「P0：Topic 常數＋follow（依 FD-7）＋Organizer 頁（擴充 `organizers`）」，以及「P1 之後：個人 Person 全套」（PT-2〜PT-4）；刪除 `event_person_signals`、`entity_views`、`user_active_days`（PT-6）；gate 欄位名稱改為 `feed_tier`（X8）。
5. 三份統一 migration 號碼分配（X3），並寫明合併順序：homepage B → 可見性模組 → 新首頁 → 其他（X4）。

**整體建議**：🔴 **暫停三份 spec 的實作，先修爬蟲（FD-1）**；接著 ↩️ 回 Architect，依 §8 的 diff 點修訂，並把三份的共用部分（可見性模組、Topic 常數、migration 分配）寫成一份共同的介面附錄。修訂後的 relevance Phase 0–0.5 與 homepage Phase B 可以直接交給 Engineer。
