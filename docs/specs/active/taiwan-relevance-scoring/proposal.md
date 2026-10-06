---
slug: taiwan-relevance-scoring
title: Taiwan Relevance Scoring — 台灣關聯度評分、內容類型分流與首頁去雜訊（P0）
status: proposed
branch: feat/taiwan-relevance-scoring
created: 2026-10-06
tags: [quality, precision, scraper, annotator, evaluation, web, db, researcher, ttr-2.0, p0]
---

> 本 spec 對應 `TTR strategy/2.0/TTR-2.0-pivot-requirements.md` §6.1（R-QA-1〜5）、§4.2 Q2、§9 Phase 0/1、§10 品質指標、§11 H5。
> §11 的 D1–D5 已定案，本 spec 不重新討論，只在 References 中引用。
> 註：`status: proposed` 不在 spec dashboard 的 `SpecStatus`（`parked | active | archived`）之內，`web/scripts/build-specs-snapshot.ts:270-271` 會退回目錄推導的 `active`。創辦人核准後，請改為 `active`。

## What（做什麼）

替每一筆活動計算 **Taiwan relevance score**（0–1）與 **content_type**，再由兩者加上政治類規則，算出單一的公開分層欄位 **`feed_tier`**（`home` / `radar` / `queue`）：

- `home`：可以進首頁與推薦（由 `intent-homepage` 消費）
- `radar`：只在「レーダーを見る」、搜尋、分類頁與城市頁出現
- `queue`：不在任何公開列表出現，進管理員人工佇列

同時要完成五件事：建立 200 筆 relevance ground truth 並量測 precision、回填既有資料、加入每日 CI、讓所有公開查詢面統一套用分層，以及在 Researcher 的來源評估中加入 precision 欄位（R-QA-5）。

## Why（為什麼）

- **Q2 high recall／low precision**（需求文件 §4.2）：非台灣內容與政治內容混進 feed，傷害信任，也稀釋台灣特色。這是 2.0 的 P0（§0 決策 2、§7）。
- **根本技術原因（盤點結果）**：目前的台灣關聯判斷**沒有任何結構化輸出**。`scraper/annotator.py:1051-1061` 的 `TAIWAN RELEVANCE GATE` 只要求模型「set is_active=false **in your mind**」並寫進 `selection_reason` 的文字。JSON schema（`annotator.py:1314-1391`）沒有 relevance 欄位，annotator 寫入時固定設 `annotation_status="annotated"`（`annotator.py:2743`），不會留下任何關聯度訊號。所以下游無法依關聯度過濾。
- **現有的品質訊號都是事後的**：`daily_quality.py:87-119` 的 `precision_rate` 依賴使用者回報的 `irrelevant`；`source_exclusions.py` 是逐來源人工維護的 pattern；`auto_qa.py:158-177` 的 18 種 QA 類型都在檢查欄位缺漏，沒有一種判斷關聯度。
- **首頁就是 database view**：`web/app/[locale]/page.tsx:54-61` 會取出所有 `is_active=true` 且已標註的活動（包含子活動），再交給 client-side 的 `filterEvents`（`web/lib/eventFilter.ts:40-106`）處理，中間沒有任何關聯度門檻。
- **時序**：`intent-homepage` 必須有「只取高分活動」的查詢契約才能開工，所以本 spec 是 2.0 路線圖 Phase 1 第 3 項的前置條件（§9）。

## Non-Goals（不做什麼）

- **不設計新首頁 UI**、意圖入口、「あなたの今週の台湾」的選品與排序，以及 A/B 測試。這些屬於 `intent-homepage`，本 spec 只提供查詢契約（見 §Interfaces）。
- **不設計 Topic／Person 實體**，也不設計 follow 機制。這些屬於 `person-topic-entities`，本 spec 只定義政治類別集合的介面。
- **不做 §6.3 的社交門檻標籤**（交流強度、語言可及性等）。這屬於 `social-affordance-tags`；本 spec 的 ground truth 工具可供它沿用，但標註 schema 不同。
- **scorer 不寫 `is_active`**。依 Architect SKILL「Database Safety Rules」，`is_active` 只有兩個合法寫入來源：admin 手動與 merger。低分只會讓活動進入 `feed_tier='queue'`（公開列表不顯示）；是否下架，仍由 admin 走既有的 `irrelevant` 流程決定（`web/lib/reportActionsCore.ts:203-208`）。
- **不重新標註既有活動**，也不修改 annotator 寫入的任何既有欄位（name/description/category/dates 等）。scorer 只寫本 spec 新增的欄位。
- **不移除也不改寫** `annotator.py` SYSTEM_PROMPT 中既有的 relevance gate 文字。兩者共存，等 v2 再評估是否合併。
- **不更換網站與爬蟲的 LLM 供應商**。依 `AGENTS.md`〈模型政策〉，`scraper/`、`web/` 內的 LLM 另案規劃；本 spec 只把模型名稱集中成一個設定常數。
- **不做 fine-tuning、embedding 或向量相似度模型**，也不在前台公開分數本身。
- **不修改 merger 合併邏輯**。merger 停用的 secondary 不評分。
- **不做逐使用者的個人化排序**。

## 現況盤點（Inventory）

| 層 | 檔案與行號 | 現況 | 與本 spec 的關係 |
|---|---|---|---|
| Annotator 模型呼叫 | `scraper/annotator.py:1546-1579` | `gpt-4o-mini`、`temperature=0.1`、`json_object` | scorer 沿用相同 client 與呼叫模式，模型名稱改為常數 `RELEVANCE_MODEL` |
| Relevance gate（文字） | `scraper/annotator.py:1051-1071` | 只有 prompt 文字，沒有結構化輸出 | 根因；scorer 的 rubric 沿用 gate 與 `.github/copilot-instructions.md` 的 Geographic Scope 判準 |
| Untrusted 包裝 | `scraper/annotator.py:1422-1434` `build_event_user_content` | 防 prompt injection 的 delimiter | scorer 的 user content **必須**重用這個函式 |
| Category 列表 | `scraper/annotator.py:605-610` `VALID_CATEGORIES`；`web/lib/types.ts:186-226`、`228-268`、`361-382` | 40 個 category，`geopolitics`、`human_rights` 在 `group_society` | R-QA-4 的政治集合以 category 表達 |
| 政治關鍵字注入 | `scraper/annotator.py:1681-1686` `_GEOPOLITICS_KEYWORDS`、`1885-1904` | 以關鍵字補 `geopolitics` | 政治判定的上游，準確度直接影響 R-QA-4 |
| 人工欄位鎖 | `field_corrections`；`annotator.py:4133` `_load_human_field_map`、`1871-1883` `_NON_TEXT_FC_FIELDS` | admin 修正的欄位不會被覆寫 | `feed_tier`／`content_type` 的人工覆寫沿用 FC 鎖 |
| Golden set | `scraper/tests/golden/{cases.jsonl,manifest.json,frozen_corrections.json}`、`scraper/build_golden_dataset.py`、`scraper/eval_annotator.py`、`.github/workflows/eval-annotator.yml` | 50 筆欄位級 golden，沒有 relevance 標籤 | 重用目錄慣例、frozen 模式、報表路徑與 CI 模式；**另建**資料集（標註 schema 不同） |
| 事後 precision | `scraper/daily_quality.py:1-20, 38, 87-119, 189-194` | `precision_rate = 1 - irrelevant_reports/upserted`，低於 0.85 時發 LINE | 保留；新增分層計數輸出 |
| 人工判定不相關 | `web/lib/reportActionsCore.ts:203-208`（`deactivated_reason='admin confirmed irrelevant'`，migration 044） | admin 確認後下架 | ground truth 的已知負例來源；queue 的「不相關」動作重用這條路徑 |
| 來源排除 | `scraper/source_exclusions.py`、`source_exclusions`／`source_exclusion_hits` 表 | 逐來源 pattern | 負例來源；不修改 |
| 新聞類來源 | `scraper/merger.py:79` `_NEWS_SOURCES` | 5 個來源 | content_type 判定與 source prior 的輸入 |
| 純出版 invariant | `.github/instructions/scraper.instructions.md` § Publication Policy；`event_form == ['publication']` | 既有 exact invariant | content_type=`publication` 必須用這個 invariant 判定 |
| 純報導 | `web/lib/types.ts:485-492` `isPureReportEvent` | `report` 且 event_form 全為 `other` | content_type=`article` 的既有判準 |
| 首頁／レーダー | `web/app/[locale]/page.tsx:54-61`（取全部，含子活動）、`EventShelf`、`EventListClient.tsx:72, 181-183`、ItemList JSON-LD `page.tsx:101-115` | 沒有關聯度門檻 | 過渡期改為排除 `queue` |
| 分類頁 | `web/app/[locale]/categories/[category]/page.tsx:202-210, 239-245` | 沒有門檻 | 套用 radar predicate |
| 城市頁 | `web/app/[locale]/cities/[city]/page.tsx:108-112` | 沒有門檻 | 套用 radar predicate |
| Sitemap | `web/app/sitemap.ts:36-41` | 沒有門檻 | 排除 `queue` |
| 活動詳情 | `web/app/[locale]/events/[id]/page.tsx:178, 206` | pure report 設 noindex | `queue` 也設 noindex（直接連結仍可開啟） |
| LINE 週報 | `scraper/weekly_line_broadcast.py:152-158` | 沒有門檻 | 只取 `home`（必要時加 `radar`，見未決問題） |
| X 自動貼文 | `scraper/x_post.py:115-122` | 沒有門檻 | 只取 `home` |
| 來源評估 | `scraper/auto_scraper/auto_research.py:8-14, 49-74`、`assessment_schema.json`（來源層級的 `taiwan_relevance_score`）、`.github/skills/agents/researcher/SKILL.md:92-123`（Low-Signal Policy：「coverage over precision」）、`.github/agents/researcher.agent.md:144-160` | 只有頻率導向的分數，沒有 precision | R-QA-5 改寫範圍；**命名衝突**：來源層級已經用了 `taiwan_relevance_score` |
| CI | `.github/workflows/scraper.yml:63-87`（annotate → fix-reviewed）、`203-215`（daily quality） | — | scorer 插在 fix-reviewed 之後 |
| Migration | `supabase/migrations/` 最新是 `096_maintenance_lock_search_path.sql` | 下一號是 `097` | 本 spec 使用 `097`（Phase 2）與 `098`（Phase 4） |

**規模（尚未量化）**：本次盤點沒有 DB 存取權。依 Architect SKILL「規模量化先於工具化」，Phase 0 的第一步就是跑量化 SQL（見 tasks.md T0.2），結果決定 backfill 分批大小與 queue 的人工負擔。目前已知：`scraper/sources/` 下有 122 個來源檔。

## Design（設計摘要）

### D-1. 計算方式：混合式（規則特徵＋獨立 LLM 判斷＋來源先驗），**不嵌進 annotator**

| 方案 | 優點 | 缺點 | 結論 |
|---|---|---|---|
| A. 只用規則 | 零成本，可解釋 | 抓不到「附帶提及」；片假名人名（台灣藝人）沒有「台湾」字樣 | 只作為特徵 |
| B. 嵌進 annotator 的 SYSTEM_PROMPT | 不必多一次呼叫 | 回填既有資料要重新標註（會改寫欄位，也碰到 reviewed 保護）；relevance prompt 改版時無法單獨重算；annotator 是 5,249 行的高風險檔 | 不採用 |
| **C. 獨立 scorer（`scraper/relevance_scorer.py`）** | 與 annotator 解耦；可版本化、可只重算 relevance；回填不碰既有欄位 | 每筆多一次精簡的 LLM 呼叫 | **採用** |

**輸入**：`raw_title`、`raw_description`（截斷到 2,000 字）、`organizer`、`co_organizers`、`source_name`、`sources.type`、`category`、`event_form`。內容一律透過 `build_event_user_content` 包裝。**不使用** `selection_reason` 作為輸入，因為它是 LLM 寫的「台灣關聯理由」，會造成循環論證。

**三類訊號**：

1. **規則特徵**（`scraper/relevance_rules.py`，純函式，不呼叫網路）
   - `title_tw`：標題（raw_title／name_ja）是否含台灣詞表。詞表重用 `annotator.py:1694` 的 `_TAIWAN_PLACE_RE` 並擴充（原住民族名、台語、客家、灣生等）。
   - `desc_density`：描述中台灣詞每千字的出現次數，以及前 200 字內是否出現。
   - `incidental`：台灣只出現在列舉中（例如「韓国・台湾・香港」、「アジア各国」、「台湾など」，或連續 3 個以上國名、地區名）。
   - `tw_org`：主辦或協辦單位符合台灣機構詞表（台北駐日経済文化代表処、台湾文化センター、台湾協会、在日台湾同郷会、日本台湾交流協会等），或來源的 `default_organizer` 是台灣機構。
   - `neg_topic`：只提中國、沒有台灣的近現代史；保險、投資、IR 公告等商業新聞語彙。這個特徵同時作為 content_type 的提示。
2. **LLM 判斷**（compact prompt，`RELEVANCE_MODEL`，預設與 annotator 相同的 `gpt-4o-mini`，`temperature=0`）。輸出 JSON：
   ```json
   {"centrality": "primary|substantial|incidental|none",
    "evidence": "原文中逐字擷取、60 字以內",
    "content_type": "event|article|academic|business_news|publication|broadcast",
    "audience_in_scope": true,
    "political_hint": false,
    "reason_zh": "一句話"}
   ```
   - rubric 沿用 `annotator.py:1051-1071` 的 gate，加上 `.github/copilot-instructions.md` § Geographic Scope 的「依活動對象判斷」：Japan→Taiwan 的 B2C／B2B 商業展開不屬於範圍。
   - **防捏造規則**：`evidence` 必須是輸入文字的逐字子字串（正規化空白後比對）。不符合就把 centrality 降一級，並在 signals 記錄 `evidence_unverified=true`。這和 §6.3「必須有原文依據」的規則一致。
   - `political_hint` **v1 只記錄、不參與分層**（見 D-4）。
3. **來源先驗** `source_prior`：依 `sources.type` 給預設值，例如台灣專門的 `organizer`／`government`（台灣機構）較高、`event_platform` 中等、`news_media` 較低，再以 `scraper/relevance_source_priors.json` 逐來源覆寫。Phase 1 用 ground truth 加 admin 確認的 irrelevant 平滑校準；之後每月由逐來源的 tier 分布重算（Phase 4）。

**合成**（版本 `r1`，常數集中在 `scraper/relevance_config.py`）：

```
llm_c   = {primary: 0.95, substantial: 0.75, incidental: 0.30, none: 0.05}[centrality]
rule_s  = f(title_tw, desc_density, incidental, tw_org, neg_topic) ∈ [0,1]
score   = w1*llm_c + w2*rule_s + w3*source_prior        # 初值 w = (0.60, 0.25, 0.15)
cap     : incidental 且 not title_tw 且 not tw_org → score ≤ 0.50
cap     : audience_in_scope == false               → score ≤ 0.30
```

權重與門檻在 Phase 1 用 ground truth 的 dev split 做 grid search 校準（不引入 sklearn），再用 holdout 驗證。之後只要 prompt、權重或門檻任一項改變，就 bump `RELEVANCE_VERSION`。

**子活動**不獨立評分，直接繼承 parent 的 `relevance_score`、`content_type` 與 `feed_tier`，並在 signals 記錄 `inherited_from`。這是因為首頁目前會取出子活動並以 ↳ 顯示（`EventListClient.tsx:181-183`），所以子活動一定要有 tier。

**成本與每日 CI 影響（估算，實際數字依 Phase 0 量化結果與 OpenAI 當時的價目）**：

- 每筆約 1,000 input tokens 加 150 output tokens。以 gpt-4o-mini 公開價（約 $0.15/1M input、$0.60/1M output）估算，約 $0.00024／筆。回填 1 萬筆約 $2.4；每日新增 50–300 筆，每日不到 $0.1。
- 用 `asyncio.Semaphore(5)`，與 `eval_annotator.py` 相同的模式。每日 300 筆約 1–2 分鐘。
- CI 步驟設為 `continue-on-error: true`（**fail-open**）。沒評分的活動是 `feed_tier IS NULL`，依契約視為 `radar`，所以會出現在レーダー，但不會上首頁。

### D-2. 儲存欄位（migration `097_event_relevance.sql`）

```sql
ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS relevance_score     numeric(4,3)
      CHECK (relevance_score IS NULL OR (relevance_score >= 0 AND relevance_score <= 1)),
  ADD COLUMN IF NOT EXISTS relevance_version   text,
  ADD COLUMN IF NOT EXISTS relevance_signals   jsonb,        -- {rule:{...}, llm:{centrality,evidence,evidence_unverified,political_hint,reason_zh}, source_prior, weights, inherited_from}
  ADD COLUMN IF NOT EXISTS relevance_scored_at timestamptz,
  ADD COLUMN IF NOT EXISTS content_type        text
      CHECK (content_type IS NULL OR content_type IN
             ('event','article','academic','business_news','publication','broadcast')),
  ADD COLUMN IF NOT EXISTS feed_tier           text
      CHECK (feed_tier IS NULL OR feed_tier IN ('home','radar','queue'));

CREATE INDEX IF NOT EXISTS idx_events_feed_tier_active
  ON public.events (feed_tier)
  WHERE is_active = true AND parent_event_id IS NULL;
```

- 不新增資料表，所以不需要新的 GRANT（`events` 既有的 grant 與 RLS 照常適用）。注意：anon 可以讀到 `relevance_signals`。內容只有 LLM 理由與特徵，不屬於敏感資料，但 web 端查詢依「最小欄位原則」不要 select 它。
- Migration 094 的 maintenance lock：`events` 的 RESTRICTIVE policy 會在鎖啟用時擋下 authenticated 寫入。admin 的 queue 操作會受影響（這是預期行為）；scorer 用 service role，不受影響。
- **content_type 判定順序**（deterministic invariant 優先於 LLM）：
  1. `event_form == ['publication']`（exact）→ `publication`
  2. `source_name == 'gguide_tv'`，或 category 含 `tv_program`／`radio_program`，且 event_form 含 `broadcast` → `broadcast`
  3. `isPureReportEvent` 等價判準 → `article`
  4. 否則採用 LLM 的 `content_type`，再以 `neg_topic` 與 `_NEWS_SOURCES` 交叉檢查（新聞來源而且沒有可參加的日期與地點時，偏向 `article`）。
  - `academic` 是指**不可參加的學術公告**（CFP、研究公募、獎學金公告、研究成果新聞）。公開的學術講座仍然是 `event`，category 為 `academic`。
- 依 `database.instructions.md` 的 Migration checklist 第 6 步，**同一個 commit 內**更新該檔的「Latest／next」、schema 表與 Query conventions。

### D-3. 分層規則（單一真實來源：`relevance_config.compute_feed_tier()`）

```
def compute_feed_tier(score, content_type, categories, annotation_status, fc_lock):
    if fc_lock is not None:                    return fc_lock          # 人工決定，永遠優先
    tier = 'home' if score >= T_HOME else 'radar' if score >= T_RADAR else 'queue'
    if content_type != 'event':                tier = min_tier(tier, 'radar')   # R-QA-3
    if categories ∩ POLITICAL_CATEGORIES:      tier = min_tier(tier, 'radar')   # R-QA-4
    if annotation_status == 'reviewed':        tier = max_tier(tier, 'radar')   # 人工看過且保留者不進 queue
    return tier
```

- 初始門檻（Phase 1 校準後定案）：`T_HOME = 0.75`、`T_RADAR = 0.45`。門檻只存在 Python 端，web 只讀 `feed_tier`。
- 只改門檻時，執行 `relevance_scorer.py --retier`：從既有的 `relevance_score` 重算 tier，不呼叫 LLM。
- 重新評分的觸發條件：`relevance_version` 不等於目前版本，或 `relevance_scored_at < annotated_at`（重新標註、`force_rescrape` 之後）。
- **人工覆寫**：admin 在 queue 或活動表上確認「相關」時，寫入 `field_corrections(field_name='feed_tier')`（以及需要時的 `content_type`）。scorer 讀取 FC 時**必須分頁全量載入**（Architect SKILL「Supabase 分頁完整性先驗證」）。

### D-4. 政治類預設不進首頁（R-QA-4）

- `POLITICAL_CATEGORIES` v1 = `{'geopolitics'}`。是否納入 `human_rights` 列為未決問題 F2。集合同時定義在 `scraper/relevance_config.py` 與 `web/lib/relevance.ts`，由一個 parity test 保證兩邊一致（比照 `annotator.py:615` `_check_category_sync` 的做法）。
- 規則：命中的活動最高只到 `radar`，所以仍會出現在レーダー、搜尋、分類頁，以及（日後）使用者主動 follow 的 Topic feed。
- 以 category 判定（而不是 LLM 的 `political_hint`），是因為 category 已經有 admin 修正管道（`category_corrections`），可稽核、可修正。`political_hint` 先累積資料，v2 再評估 recall。
- **編輯方針公開說明**（R-QA-4 驗收條件）：在 `web/app/[locale]/about/page.tsx` 加一段三語的「編輯方針：政治與時事內容」說明，新增 `about.*` key，三語檔同步更新。完整的 §6.11 信任頁不在本 spec 範圍內；日後若有 trust spec，由它吸收這一段。

### D-5. Ground truth 200 筆與 precision 量測

**資料集**：`scraper/tests/golden_relevance/`（與 annotator golden 分開，因為標註 schema 不同；目錄慣例與 frozen 模式沿用 evaluation-framework）

- `cases.jsonl`：`{case_id, event_id, source_name, source_type, stratum, split: dev|holdout, input:{raw_title, raw_description(≤2000), organizer, co_organizers, category, event_form}, label:{relevance: core|related|incidental|none, content_type, is_political, homepage_ok}, labeler, labeled_at, notes}`
- `manifest.json`：版本、抽樣 SQL 的 hash、各 stratum 數量、labeler、標註指南版本。
- `LABELING_GUIDE.md`：四級定義、各級 5 個正例與 5 個反例、Geographic Scope 規則、content_type 定義。

**抽樣（分層，總數 200）**：

| Stratum | 數量 | 來源 | 目的 |
|---|---|---|---|
| S1 首頁現況 | 80 | 目前首頁 payload（`page.tsx:54-61` 的等價查詢，`timeMode=active`），隨機抽樣 | 量測**首頁雜訊率基準**（H5 前測） |
| S2 來源分層 | 60 | 依 `sources.type` 與 `_NEWS_SOURCES` 分層，各層等量 | 校準 source prior |
| S3 已知負例 | 30 | `deactivated_reason='admin confirmed irrelevant'` 加上 `source_exclusion_hits.raw_title` 對應的事件 | 負例覆蓋 |
| S4 政治與邊界 | 30 | category 含 `geopolitics`／`human_rights`／`taiwan_japan`，加上 Japan→Taiwan 商業展開的疑似案例 | R-QA-4 與 Geographic Scope 邊界 |

- 以 seed 固定 7:3 切分 dev／holdout（140／60）。
- **標註流程**：`scraper/build_relevance_golden.py --sample` 匯出 `label_sheet.tsv`（標籤欄留空）→ 創辦人在試算表標註（預估 3–4 小時）→ `--import label_sheet.tsv` 驗證 enum 與完整性後寫入 `cases.jsonl`。一週後**重標其中 30 筆**，量測同一標註者的一致性（agreement 低於 0.8 就先修訂指南）。
- **指標**（`scraper/eval_relevance.py`，frozen 模式，不寫 DB；報表輸出到 `docs/evaluation/relevance/YYYY-MM-DD.md`）：
  - **首頁雜訊率**（主指標，§10 目標 ≤ 5%）= 被分到 `home` 的案例中，`homepage_ok = false` 的比例。`homepage_ok = false` 的定義是：relevance ∈ {incidental, none}，或 content_type ≠ event，或 is_political。
  - **レーダー召回率**（防過濾，目標 ≥ 95%）= relevance ∈ {core, related} 的案例中，沒被分到 `queue` 的比例。
  - **首頁召回率**（觀察指標，不設門檻）= `homepage_ok = true` 的案例中，被分到 `home` 的比例。
  - 混淆矩陣、逐來源錯誤清單、`evidence_unverified` 比例。
- **門檻選擇**：在 dev split 上，**先滿足**雜訊率 ≤ 5% 與レーダー召回率 ≥ 95%，再取首頁召回率最高的 (T_HOME, T_RADAR)，最後在 holdout 確認。報表必須附上 95% 信賴區間（樣本少，例如 80 筆中錯 4 筆，雜訊率 5%，上界約 12%），以免被誤讀為已達標。
- **持續量測**（§6.3「每週抽檢」）：`eval_relevance.py --weekly-sample 20` 每週抽 20 筆 home tier 活動，產生待標清單，標完後併入滾動雜訊率。只做被動 push：產出 markdown 並在 LINE 週報附一行，不建新的 admin 頁面（遵循 Architect SKILL「Admin UI Dashboard Necessity Check」）。
- **CI**：新增 `.github/workflows/eval-relevance.yml`，在 PR 觸及 `scraper/relevance_*.py` 或 `scraper/tests/golden_relevance/**` 時執行（比照 `eval-annotator.yml`）。holdout 雜訊率 > 5% 或レーダー召回率 < 95% 時判定失敗。

### D-6. 回填既有資料

1. `relevance_scorer.py --backfill --dry-run --limit N`：範圍是 `is_active=true`、`parent_event_id IS NULL`、`annotation_status IN ('annotated','reviewed')` 的活動。輸出分數直方圖、逐來源的 tier 分布、queue 清單樣本與 content_type 分布到 `docs/evaluation/relevance/backfill-dryrun-YYYY-MM-DD.md`。**不寫 DB。**
2. **創辦人審閱 dry-run 報表**（gate）：確認 queue 數量是人工負擔得起的，必要時調整門檻。
3. `--backfill --apply --batch 200`：可續跑（只處理 `relevance_version IS DISTINCT FROM 當前版本` 的列），子活動同步繼承。只寫 D-2 的六個欄位，**不寫 `is_active`、`annotation_status` 或任何既有欄位**。
4. 驗證 SQL：tier 計數、`feed_tier IS NULL` 的 active parent 數為 0、子活動與 parent 的 tier 一致、reviewed 活動沒有任何一筆是 `queue`。
5. **回滾**：`UPDATE events SET feed_tier = NULL, ...`。查詢契約把 NULL 視為 `radar`，所以回滾後會回到「全部都在レーダー、首頁沒有內容」的安全狀態。

### D-7. 公開查詢面 surface matrix（Domain-policy surface audit）

| Surface | 檔案 | 新規則 | Phase |
|---|---|---|---|
| 現行首頁（＝日後的レーダー）列表、Shelf、ItemList JSON-LD | `web/app/[locale]/page.tsx:54-61, 101-115` | radar predicate（排除 `queue`） | 3 |
| 新首頁 | `intent-homepage` | home predicate | 由對方 spec 處理 |
| 分類頁（兩段查詢） | `categories/[category]/page.tsx:202-210, 239-245` | radar predicate | 3 |
| 城市頁 | `cities/[city]/page.tsx:108-112` | radar predicate | 3 |
| Sitemap | `web/app/sitemap.ts:36-41` | radar predicate | 3 |
| 活動詳情 | `events/[id]/page.tsx:178, 206` | `feed_tier='queue'` 時設 noindex；頁面仍可開啟 | 3 |
| 收藏 `/saved` | `web/app/[locale]/saved/page.tsx` | **不過濾**（使用者主動收藏的活動） | — |
| LINE 週報 | `scraper/weekly_line_broadcast.py:152-158` | home predicate（見 F6） | 3 |
| X 自動貼文 | `scraper/x_post.py:115-122` | home predicate | 3 |
| Admin 活動表 | `web/components/AdminEventTable.tsx` | 新增 tier／score 欄、queue 篩選與動作 | 3 |
| Admin、帳號頁、OG 圖 | 其他 `from("events")` | 不過濾 | — |

**Predicate 與 NULL 語意**（PostgREST 的 `.neq()` 會排除 NULL，所以必須明寫）：

- home：`.eq("feed_tier", "home")`
- radar：`.or("feed_tier.is.null,feed_tier.in.(home,radar)")`
- queue（admin）：`.eq("feed_tier", "queue")`

上述 predicate 集中在 `web/lib/relevance.ts`（`applyHomeFeed(q)`、`applyRadarFeed(q)`）與 `scraper/relevance_config.py`（Python 版）。每個 surface 只能呼叫 helper，不得自行手寫條件。每個 surface 都要有負向 fixture：queue 事件不出現。

### D-8. 人工佇列

- 依「Admin UI Dashboard Necessity Check」，**不新增 admin 頁面**，改在既有的 `AdminEventTable` 擴充（有動作按鈕的欄位）：
  - 篩選器「Relevance queue」（`feed_tier='queue'`），並依 `relevance_score` 由高到低排序（先看最可能誤殺的）。
  - 動作「相關 → radar」與「相關 → home」：透過既有的 `adminEventMutationsCore`／`fieldCorrections.server.ts` 寫入 FC 鎖並更新 `feed_tier`。若有欄位 allowlist，同步擴充。
  - 動作「不相關」：重用既有的 irrelevant 下架路徑（admin 手動屬於 `is_active` 的合法寫入來源）。
  - 顯示 `relevance_signals.llm.reason_zh` 與 `evidence`。
- UI 優先使用既有的 design system 元件（Architect Design System Guard）。新字串三語同步，且不得刪除 `categories` namespace 的 key（i18n Regression Guard）。
- **不**為 queue 建立 `event_reports`，以免像 #204 那樣灌爆報表，也避免 auto_qa 的 `updated_at` dedup 陷阱（Architect SKILL「QA Keyword Precision Guard」第 3 點）。
- 被動通知：`daily_quality.py` 的 JSON 摘要加入 `feed_tier` 計數（不改 schema）；當 queue 的新增量超過門檻時，在 LINE 週報附上一行。

### D-9. R-QA-5：Researcher 來源評估加入 precision

- **政策取代**：`.github/skills/agents/researcher/SKILL.md:92-123` 的「Low-Signal Source Policy（coverage over precision）」被 R-QA-5「新來源必須先估 precision」取代。依 Architect SKILL「Policy supersession contradiction audit」，必須對 `researcher.agent.md`、researcher `SKILL.md`、researcher `history.md`（第 67、282、412 行為 historical，就地標註 superseded）、`scraper/auto_scraper/auto_research.py:8-14, 49-55` 的 docstring 與門檻、`scraper-dev` skill 做 exact 與 semantic 搜尋，逐條把命中標為 active 或 historical 並處理。
- **新欄位**：
  - Researcher profile（`researcher.agent.md:147-160` 的格式）加入 `Precision: x/N (sample method)`、`Estimated precision: 0.xx`。
  - `research_sources` 加 `estimated_precision numeric(3,2)`、`precision_sample_size int`、`precision_evaluated_at timestamptz`（migration `098_research_sources_precision.sql`，只 ALTER，不需 GRANT）。
  - `update_source.py` 加 `--precision` 與 `--precision-sample` 旗標。
- **量測方法**：Researcher 從該來源 lookback 期間的列表中抽 N 筆（N = min(20, 全部)），逐筆依 `LABELING_GUIDE.md` 判定 core／related 的比例。
- **門檻**：precision ≥ 0.6 → 可 `researched`；0.3–0.6 → 必須先在 scraper 端設計關鍵字 gate 或 `source_exclusions`，才可實作；< 0.3 → `not-viable`。具體數字列為未決問題 F5。
- **暫停無差別擴充**：`auto_research.py` 不再自動升級為 `researched`（全部降為 `assessed`，交人工依 precision 決定）。auto-generate 是否整個暫停，列為 F5。
- **既有來源的 precision**：每月由 `eval_relevance.py --source-report` 從 DB 的 tier 分布（queue 比例），產出逐來源 precision 報表 `docs/evaluation/relevance/sources-YYYY-MM.md`，排出「最該加 exclusion 或下線」的來源。
- 改完 skill／agent 後執行 `python3 scripts/sync_ai_adapters.py`，提交前跑 `--check`。

### D-10. 影響檔案清單

- 新增：`scraper/relevance_rules.py`、`scraper/relevance_config.py`、`scraper/relevance_scorer.py`、`scraper/relevance_source_priors.json`、`scraper/build_relevance_golden.py`、`scraper/eval_relevance.py`、`scraper/tests/golden_relevance/{cases.jsonl,manifest.json,LABELING_GUIDE.md}`、`scraper/tests/test_relevance_rules.py`、`scraper/tests/test_relevance_tier.py`、`scraper/tests/test_relevance_scorer.py`、`supabase/migrations/097_event_relevance.sql`、`supabase/migrations/098_research_sources_precision.sql`、`web/lib/relevance.ts`、`.github/workflows/eval-relevance.yml`、`docs/evaluation/relevance/`
- 修改：`.github/workflows/scraper.yml`、`scraper/daily_quality.py`（只改 JSON 輸出）、`scraper/weekly_line_broadcast.py`、`scraper/x_post.py`、`scraper/update_source.py`、`scraper/auto_scraper/auto_research.py`、`web/lib/types.ts`（`FeedTier`、`ContentType` 型別與 `Event` 欄位）、`web/app/[locale]/page.tsx`、`web/app/[locale]/categories/[category]/page.tsx`、`web/app/[locale]/cities/[city]/page.tsx`、`web/app/sitemap.ts`、`web/app/[locale]/events/[id]/page.tsx`、`web/app/[locale]/about/page.tsx`、`web/components/AdminEventTable.tsx`、`web/lib/adminEventMutationsCore.ts`（必要時）、`web/messages/{ja,zh,en}.json`、`.github/instructions/database.instructions.md`、`.github/agents/researcher.agent.md`、`.github/skills/agents/researcher/SKILL.md`、`.github/skills/agents/researcher/history.md`、`docs/SCRAPER_PIPELINE.md`（新增 pipeline layer，依 Docs Update Rule）

## Interfaces（與其他 spec 的介面；只定義介面，不設計對方內容）

### I-1. `intent-homepage`：首頁只取高分活動的查詢契約

| 項目 | 本 spec 提供（owner） | `intent-homepage` 負責 |
|---|---|---|
| 欄位 | `events.feed_tier ∈ {home, radar, queue, NULL}`、`events.content_type`、`events.relevance_score` | — |
| 首頁 predicate | `applyHomeFeed(q)`（`web/lib/relevance.ts`）＝ `feed_tier='home'`。`home` 本身已保證 content_type=`event`、非政治類，且分數 ≥ T_HOME | 在這個集合**之內**做意圖篩選、選品（5–8 筆）、排序與 A/B |
| レーダー predicate | `applyRadarFeed(q)` ＝ `feed_tier IS NULL OR feed_tier IN ('home','radar')` | 「レーダーを見る」頁的 UI 與篩選，包括是否提供 content_type 篩選 |
| NULL 語意 | NULL（尚未評分）= radar：可見，但**不上首頁** | 首頁不得自行把 NULL 當成 home |
| 穩定性 | 調整門檻與版本**不改變**契約；新增 tier 值必須同步修改兩份 spec | 不得在 web 端用 `relevance_score` 自訂門檻（避免兩套真實來源） |
| 前置條件 | Phase 2 回填完成，且 active parent 中 `feed_tier IS NULL` 的數量 = 0 | 上線前確認這個前置條件 |
| 共用的基本條件 | `is_active=true`、`annotation_status IN ('annotated','reviewed')` 仍由各查詢自行帶上；`parent_event_id` 的處理由各 surface 決定 | — |

### I-2. `person-topic-entities`：Topic 與 Category 的對應

- 本 spec **不定義 Topic**，只讀 `events.category`。
- **輸出**：`POLITICAL_CATEGORIES`（Python／TS 兩份常數，有 parity test）。Topic 如果對應到政治或時事主題，對應表必須映射到這個集合裡的 category，R-QA-4 的排除才會一致生效。
- **R-QA-4 的 follow 例外**：使用者主動 follow 的 Topic feed 應使用 `applyRadarFeed`（而不是 home predicate），這樣政治類活動在 follow 後才會出現。這個行為由 `person-topic-entities` 實作，本 spec 只保證 radar predicate 會包含政治類活動。
- relevance score 是逐活動的分數，不是逐 Topic；Topic 頁若要依分數排序，直接讀 `relevance_score`。
- Topic ↔ Category 對應表的位置、資料結構與命名，全部由 `person-topic-entities` 決定。

### I-3. 其他（只列依賴關係）

- `social-affordance-tags`：可以沿用 `build_relevance_golden.py` 的匯出與匯入流程，以及 `eval_relevance.py` 的報表骨架，但標註 schema 獨立。
- `organizer-submission-v2`：`user_submission` 活動同樣會被評分。是否讓投稿活動在人工審核前固定進 `queue`，由該 spec 決定。如需要，可透過 FC 鎖或 `compute_feed_tier` 新增一條分支，修改時要同步本 spec。
- `evaluation-framework`：在目錄、frozen 模式與 CI 模式上對齊，但不修改 annotator golden set。

## Worktree & Spec Tracking

1. **Spec**：slug `taiwan-relevance-scoring`，路徑 `docs/specs/active/taiwan-relevance-scoring/`（由 `_template/` 建立）。
2. **Worktree**：`ttr-taiwan-relevance-scoring-worktree`，branch `feat/taiwan-relevance-scoring`，屬於 **NEW**。2026-10-06 執行 `git worktree list` 時，只有主工作樹（`/home/user/Tokyo_Taiwan_Radar`，目前在 `claude/elegant-einstein-ypujar`），沒有同名 branch 或 worktree。
3. **Phase 0 指示**：Engineer 必須先讀 `.github/instructions/git.instructions.md` § Isolated worktree，依 state matrix 建立（branch 不存在時用 `git worktree add ttr-taiwan-relevance-scoring-worktree -b feat/taiwan-relevance-scoring`），並以 idempotent 方式把 `ttr-taiwan-relevance-scoring-worktree/` 加入 `.git/info/exclude`。不得假設 worktree 已經存在；路徑存在但沒有註冊時，必須 **STOP** 並詢問。
4. **Worktree 確認閘門**：**實作前必須先向使用者確認要使用這個 worktree**，得到明確答覆才可以動工。主工作樹只供治理用途，不得在主工作樹實作。
5. Session 的 plan（Codex／Claude 是 `~/.ai-notes/ttr/plan.md`；Copilot 是 `/memories/session/plan.md`）必須引用 slug `taiwan-relevance-scoring`，resume 時從 `tasks.md` 還原進度。
6. 本 spec 跨 scraper、DB、web 與 agent 治理，需要多個 session，**分類為 Large feature**。合併時依 trunk-based 流程，rebase 到 `origin/main` 後交給 V-M-D；push 前必須取得使用者明確同意。

## Phases 與複雜度

| Phase | 內容 | 主要產出 | 估計 | 阻擋條件 |
|---|---|---|---|---|
| 0 | Worktree、規模量化、標註指南、抽樣、創辦人標註 200 筆 | `golden_relevance/`、基準雜訊率（H5 前測） | S（工程）＋創辦人 3–4 小時 | 創辦人的標註時間 |
| 1 | 規則特徵、scorer（offline）、eval 與校準 | `relevance_*.py`、`eval_relevance.py`、校準報表 | M | holdout 雜訊率 ≤ 5% 且レーダー召回率 ≥ 95% |
| 2 | Migration 097、回填 dry-run 到 apply、每日 CI | DB 欄位、全量 tier | M | 創辦人審閱 dry-run 報表後核准 |
| 3 | Surface matrix 套用、admin queue、編輯方針、LINE／X | 公開面去雜訊（R-QA-2/3/4） | M | Phase 2 驗證 SQL 通過 |
| 4 | R-QA-5 Researcher 政策、migration 098、逐來源 precision、每週抽檢、eval CI | 治理閉環 | S–M | — |

**整體複雜度：L**（新 pipeline layer，跨 scraper、DB、web 與 agent 治理，需要人工 ground truth 與兩個人工 gate）。Phase 0–2 是 `intent-homepage` 的前置條件；Phase 3 和 Phase 4 可以與 `intent-homepage` 並行。

## Risks（風險）

| # | 風險 | 影響 | 緩解 |
|---|---|---|---|
| R1 | **過度過濾（召回損失）**：小眾但真正相關的活動（例如台灣藝人只以片假名出現、沒有「台湾」字樣）掉進 `queue`，等於從公開面消失，最先傷害到切入族群「深掘的美咲」 | 高 | レーダー召回率 ≥ 95% 是硬性 gate；reviewed 活動的下限是 radar；台灣專門來源有較高的 source prior；queue 依分數高到低排序，先處理最可能誤殺的；queue ≠ 下架 |
| R2 | **Ground truth 太小，且只有單一標註者**：200 筆、一個人標，門檻容易過擬合；5% 雜訊率的信賴區間很寬 | 高 | 分層抽樣加 holdout；報表一律附信賴區間；同一標註者重標 30 筆量一致性；每週抽 20 筆滾動累積 |
| R3 | **多個公開面不一致或洩漏**：查詢點多達 8 處以上（首頁、分類、城市、sitemap、JSON-LD、LINE、X、詳情頁 noindex），漏掉一處就會洩漏 queue 活動；PostgREST 的 `.neq()` 會靜默排除 NULL | 高 | 集中 helper；surface matrix 逐列都有負向 fixture；明確定義 NULL 語意；只有 Phase 2 驗證 NULL 數 = 0 後，才進入依賴 home 的上線 |
| R4 | LLM 漂移、`evidence` 捏造、模型下架（gpt-4o-mini） | 中 | evidence 子字串驗證；`RELEVANCE_VERSION`；eval CI；模型名稱集中成常數 |
| R5 | 回填後 queue 數量超出創辦人能處理的量（Q7 精力有限） | 中 | dry-run 先量化；調門檻前由創辦人核准；queue 不建 event_reports；只做被動通知 |
| R6 | 政治判定依賴 `geopolitics` category 的準確度；漏標會讓政治活動上首頁，誤標會讓文化活動被降級 | 中 | 以 S4 stratum 量測；`political_hint` 先累積資料，v2 評估是否納入；admin 可透過 category_corrections 修正 |
| R7 | 命名混淆：來源層級已有 `taiwan_relevance_score`（`assessment_schema.json`） | 低 | 事件層級一律用 `relevance_*`，並在文件中明確區分 |
| R8 | 每日 CI 多一步，失敗時影響 tier | 低 | `continue-on-error`，fail-open（NULL = radar）；`--limit` |

## Open Questions（未決問題；需要創辦人決定的列為 F*）

- **F1**：`queue` 是否「公開列表完全不顯示」（本 spec 的預設，對應 R-QA-2 的「低分進人工佇列」），還是改為「レーダー可見但加上低信心標記」？這決定 R1 的嚴重程度。
- **F2**：`POLITICAL_CATEGORIES` 只放 `geopolitics`，還是也納入 `human_rights`（例如轉型正義相關電影）？
- **F3**：非 `event` 的 content_type（article／academic／business_news／publication／broadcast）在レーダー中預設顯示，還是預設隱藏、需要篩選才出現？`business_news` 是否直接降為 `queue`？（本 spec 只提供資料；UI 呈現由 `intent-homepage` 實作，但方針需要創辦人決定。）
- **F4**：200 筆 ground truth 由創辦人親自標註（建議，因為定義權在創辦人），還是另找第二位標註者？請同時核准 `LABELING_GUIDE.md` 的四級定義。
- **F5**：R-QA-5 的 precision 門檻（建議 0.6／0.3），以及是否暫停整個 `auto-generate.yml` 的自動建立 scraper（本 spec 的預設只停止 auto_research 的自動升級）。
- **F6**：LINE 週報只取 `home`，還是取 `home` 加上高分的 `radar`？只取 `home` 時，週報可能變短。
- **F7**：編輯方針的文字由誰撰寫、是否現在就放進 About 頁（本 spec 的預設：放一段精簡版，日後由 trust spec 吸收）。
- **F8**：scorer 繼續用 gpt-4o-mini（與 annotator 一致，預設），還是等網站 LLM 的另案規劃？本 spec 只保留常數化的切換點。
- 技術問題（Engineer 在 Phase 0 確認）：`sources.type` 在現行 DB 中是否已涵蓋全部 122 個來源（migration 060／067 的 seed 只有 104 筆）？沒有涵蓋的來源，source prior 退回中性值 0.5。

## Success Criteria（驗收）

- [ ] R-QA-1：每筆 active parent 都有 `relevance_score`、`relevance_version`、`content_type`、`feed_tier`；200 筆 ground truth 存在；holdout 首頁雜訊率 ≤ 5%（附信賴區間），且レーダー召回率 ≥ 95%
- [ ] R-QA-2：所有公開面套用 helper；首頁 predicate 不會回傳 `queue`／`radar`；每個 surface 都有負向 fixture 通過
- [ ] R-QA-3：`home` 只含 `content_type='event'`；非 event 的類型只在レーダー出現或不顯示
- [ ] R-QA-4：`POLITICAL_CATEGORIES` 的活動不在 `home`，但在レーダー與搜尋中可見；About 頁有三語的編輯方針
- [ ] R-QA-5：Researcher profile 與 `research_sources` 有 precision 欄位；Low-Signal Policy 已標註為 superseded；`auto_research` 不再自動升級來源
- [ ] H5 前測：S1 stratum 的基準雜訊率已記錄在 `docs/evaluation/relevance/`；後測方法（每週抽樣）已上線
- [ ] scorer 從未寫入 `is_active`；所有 reviewed 活動都不在 `queue`（驗證 SQL 為 0 筆）

## References

- **需求文件**：`TTR strategy/2.0/TTR-2.0-pivot-requirements.md`
  - §6.1 R-QA-1〜5（本 spec 主體）；§4.2 Q2；§7 P0；§9 Phase 0／Phase 1 第 3 項；§10 品質指標（首頁雜訊率 ≤ 5%）；§11 H5；§15 第 1 項
  - **§1.5 與 §11 D1（已決定）**：選項 2，2.0 重做 B2C 表層，中層與深層暫緩但保留。本 spec 的分數與 tier 屬於資料品質基礎設施，也會強化日後的資料服務。
  - **§11 D2（已決定）**：核心族群是「台湾に少し踏み込みたい日本語話者」，已入坑者是切入點。這是 R1（過度過濾會傷害已入坑者）列為最高風險的理由。
  - **§11 D3（已決定）**：暫不擴大到台灣當地內容。scorer 的 `audience_in_scope` 沿用現行 Geographic Scope。
  - **§11 D4（已決定）**：文案與入口以原型測試決定，屬於 `intent-homepage`，本 spec 不涉及。
  - **§11 D5（已決定）**：2.0 期間不設變現目標，所以本 spec 不考慮付費曝光或排序權重。
- 規則：`AGENTS.md`、`.github/copilot-instructions.md`（Geographic Scope）、`.github/instructions/{scraper,database,web,git,token-rotation}.instructions.md`、`.github/skills/agents/architect/SKILL.md`（Database Safety Rules、規模量化先於工具化、Supabase 分頁完整性、Domain-policy surface audit、Policy supersession audit、Admin UI Dashboard Necessity Check、QA Keyword Precision Guard、Predicate projection contract guard）
- 參考 spec：`docs/specs/active/evaluation-framework/`（golden set、frozen 模式、CI 模式）、`docs/specs/active/works-entity-for-films-and-tours/`（格式參考）、`docs/specs/active/autoresearch-auto-scraper/`（R-QA-5 影響的 pipeline）
- 相關 spec（介面）：`intent-homepage`、`person-topic-entities`（尚未建立）
