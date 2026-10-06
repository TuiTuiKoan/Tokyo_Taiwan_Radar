---
spec: taiwan-relevance-scoring
---

# Tasks

每完成一步，就把 `- [ ]` 改成 `- [x]` 並 commit（即使只改這一行）。
設計細節以 `proposal.md` 為準；本檔只列可執行的步驟與驗收方式。

> **人工 gate**：G1（創辦人完成標註）、G2（創辦人核准 backfill dry-run）、G3（push 前取得使用者同意）。沒有通過的 gate 不得跳過。

## Phase 0：Worktree、量化與 Ground Truth（S + 創辦人 3–4 小時）

- [ ] T0.0 **Worktree 確認閘門**：向使用者確認要在 `ttr-taiwan-relevance-scoring-worktree` 實作，取得明確答覆後才動工
- [ ] T0.1 依 `.github/instructions/git.instructions.md` § Isolated worktree 的 state matrix 建立 `ttr-taiwan-relevance-scoring-worktree`（branch `feat/taiwan-relevance-scoring`）；以 idempotent 方式把 `ttr-taiwan-relevance-scoring-worktree/` 加入 `.git/info/exclude`；確認路徑與 branch 都正確
- [ ] T0.2 **規模量化**（唯讀 SQL，結果記錄在 `docs/evaluation/relevance/phase0-sizing.md`）：
  - active parent 總數（`is_active AND parent_event_id IS NULL AND annotation_status IN ('annotated','reviewed')`）
  - 子活動總數；每日平均新增數（近 30 天 `created_at`）
  - 逐來源的 active 數；`sources.type` 涵蓋率（有多少 `source_name` 在 `sources` 中查不到）
  - `deactivated_reason = 'admin confirmed irrelevant'` 的筆數；`source_exclusion_hits` 近 30 天的筆數
  - category 含 `geopolitics`、`human_rights` 的筆數；`event_form = '{publication}'` 與 `gguide_tv` 的筆數
- [ ] T0.3 撰寫 `scraper/tests/golden_relevance/LABELING_GUIDE.md`：四級定義（core／related／incidental／none）、content_type 定義（academic 指「不可參加的學術公告」）、Geographic Scope 規則（依活動對象判斷；Japan→Taiwan 商業展開不屬於範圍）、各級正反例各 5 個
- [ ] T0.4 實作 `scraper/build_relevance_golden.py`：
  - `--sample --seed N`：依 S1（80）／S2（60）／S3（30）／S4（30）分層抽樣，匯出 `label_sheet.tsv`（標籤欄留空），並以 7:3 標記 dev／holdout
  - `--import label_sheet.tsv`：驗證 enum 與完整性後寫入 `cases.jsonl` 與 `manifest.json`（內含抽樣 SQL 的 hash 與指南版本）
  - 唯讀 DB；分頁要全量載入（不得被 1000 筆截斷）
- [ ] T0.5 測試：`scraper/tests/test_build_relevance_golden.py`（分層數量、seed 可重現、import 拒絕非法 enum）
- [ ] T0.6 **G1**：創辦人依指南標註 200 筆 → import → commit `cases.jsonl`
- [ ] T0.7 計算 **S1 基準雜訊率**（H5 前測），寫入 `docs/evaluation/relevance/YYYY-MM-DD-baseline.md`（附 95% 信賴區間）
- [ ] T0.8 （一週後）重標 30 筆，計算同一標註者的一致性；低於 0.8 時先修訂指南，並重新檢視有爭議的案例

## Phase 1：Scorer（offline）與校準（M）

- [ ] T1.1 `scraper/relevance_config.py`：`RELEVANCE_VERSION`、`RELEVANCE_MODEL`、權重、`T_HOME`／`T_RADAR`、`POLITICAL_CATEGORIES={'geopolitics'}`（等 F2 決定）、`compute_feed_tier()`、`min_tier`／`max_tier`、Python 版 home／radar predicate
- [ ] T1.2 `scraper/relevance_rules.py`：`title_tw`、`desc_density`、`incidental`、`tw_org`、`neg_topic`，以及 deterministic 的 content_type 判定（publication exact invariant → broadcast → pure report → 交給 LLM）。台灣詞表重用 `annotator._TAIWAN_PLACE_RE`
- [ ] T1.3 `scraper/relevance_source_priors.json`，依 `sources.type` 給預設值並逐來源覆寫；查不到的來源設為 0.5
- [ ] T1.4 `scraper/relevance_scorer.py` 的核心：compact prompt、用 `build_event_user_content` 包裝、JSON 輸出、`evidence` 子字串驗證（不符就降一級並設 `evidence_unverified`）、合成公式與 caps、子活動繼承；`asyncio.Semaphore(5)`；`--dry-run` 為預設
- [ ] T1.5 單元測試：
  - `test_relevance_rules.py`：列舉型附帶提及、片假名人名、台灣機構主辦、Japan→Taiwan B2C 反例
  - `test_relevance_tier.py`：FC 鎖優先；非 event 最高只到 radar；政治類最高只到 radar；reviewed 最低為 radar；門檻邊界值
  - `test_relevance_scorer.py`：mock LLM，驗證 evidence 不符時降級、子活動繼承、prompt 使用 untrusted 包裝
  - parity test：`POLITICAL_CATEGORIES` 與 `web/lib/relevance.ts` 一致，且是 `VALID_CATEGORIES` 的子集
- [ ] T1.6 `scraper/eval_relevance.py`：frozen 模式，以 `cases.jsonl` 呼叫 scorer（不寫 DB），輸出首頁雜訊率、レーダー召回率、首頁召回率、混淆矩陣、逐來源錯誤、`evidence_unverified` 比例與信賴區間到 `docs/evaluation/relevance/YYYY-MM-DD.md`；同時提供 `--json-output`
- [ ] T1.7 校準：在 dev split 上 grid search 權重與 (T_HOME, T_RADAR)，條件是雜訊率 ≤ 5% 且レーダー召回率 ≥ 95%，再取首頁召回率最高的組合；在 holdout 確認後寫回 `relevance_config.py`，版本定為 `r1`
- [ ] T1.8 **Phase 1 gate**：holdout 雜訊率 ≤ 5% 且レーダー召回率 ≥ 95%。沒有達標時，**不得進入 Phase 2**；回報差距與錯誤案例，交 Architect 檢討

## Phase 2：Schema、回填與每日 CI（M）

- [ ] T2.1 `supabase/migrations/097_event_relevance.sql`（內容見 proposal D-2；使用 `ADD COLUMN IF NOT EXISTS`、CHECK、partial index；不新增資料表，所以不需要 GRANT）
- [ ] T2.2 **手動 migration**：在 Supabase SQL Editor 執行，並以驗證 SQL 確認六個欄位、CHECK 與 index 都存在：
  ```sql
  SELECT column_name, data_type FROM information_schema.columns
  WHERE table_schema='public' AND table_name='events'
    AND column_name IN ('relevance_score','relevance_version','relevance_signals',
                        'relevance_scored_at','content_type','feed_tier');
  ```
- [ ] T2.3 同一個 commit 內更新 `.github/instructions/database.instructions.md`：Latest 改為 097、next 改為 098、events schema 表加入六個欄位、Query conventions 加入 home／radar predicate 與 NULL 語意
- [ ] T2.4 scorer 寫入模式：`--backfill`、`--pending`（`relevance_version` 不同或 `relevance_scored_at < annotated_at`）、`--retier`（不呼叫 LLM）、`--apply`、`--batch`、`--limit`；FC（`feed_tier`／`content_type`）**分頁全量載入**；寫入白名單只包含六個新欄位（測試斷言 payload 不含 `is_active`／`annotation_status`）
- [ ] T2.5 回填 dry-run → `docs/evaluation/relevance/backfill-dryrun-YYYY-MM-DD.md`（分數直方圖、逐來源 tier 分布、queue 樣本 30 筆附活動連結 `https://tokyotaiwanradar.com/ja/events/<id>`、content_type 分布）
- [ ] T2.6 **G2**：創辦人審閱 dry-run 報表，核准門檻與 queue 數量
- [ ] T2.7 回填 apply，分批執行（可續跑）
- [ ] T2.8 驗證 SQL（每一項都必須為預期值）：
  - active parent 中 `feed_tier IS NULL` 的數量 = 0
  - 子活動與 parent 的 tier 不一致的數量 = 0
  - `annotation_status='reviewed' AND feed_tier='queue'` 的數量 = 0
  - `feed_tier='home' AND (content_type <> 'event' OR category && ARRAY['geopolitics'])` 的數量 = 0
  - 回填前後 `is_active` 的分布相同
- [ ] T2.9 `.github/workflows/scraper.yml`：在「Fix reviewed events missing translations」之後新增 `python relevance_scorer.py --pending --apply --limit 500`，設定 `continue-on-error: true`；摘要寫入 `GITHUB_STEP_SUMMARY`
- [ ] T2.10 `scraper/daily_quality.py`：在 JSON 摘要加入 `feed_tier` 計數與當日新增的 queue 數（不改 schema）
- [ ] T2.11 更新 `docs/SCRAPER_PIPELINE.md`，加入 relevance scoring layer（依 Docs Update Rule，不寫會變動的數字）

## Phase 3：公開面套用、Admin Queue 與編輯方針（M）

- [ ] T3.1 `web/lib/types.ts`：加入 `FeedTier`、`ContentType` 型別，以及 `Event` 的 `relevance_score`／`content_type`／`feed_tier`（選填）
- [ ] T3.2 `web/lib/relevance.ts`：`applyHomeFeed`、`applyRadarFeed`、`POLITICAL_CATEGORIES`；NULL 語意寫在註解中；加上單元測試
- [ ] T3.3 依 surface matrix 逐一套用（所有 `.select()` 都要包含 predicate 所需的欄位；遵守 Predicate projection contract）：
  - [ ] `web/app/[locale]/page.tsx:54-61`（radar predicate；同時套用到 Shelf 與 ItemList JSON-LD）
  - [ ] `web/app/[locale]/categories/[category]/page.tsx:202-210, 239-245`
  - [ ] `web/app/[locale]/cities/[city]/page.tsx:108-112`
  - [ ] `web/app/sitemap.ts:36-41`
  - [ ] `web/app/[locale]/events/[id]/page.tsx`：`feed_tier='queue'` 時設 noindex，頁面仍可開啟
  - [ ] `scraper/weekly_line_broadcast.py:152-158`（home predicate；等 F6 決定）
  - [ ] `scraper/x_post.py:115-122`（home predicate）
- [ ] T3.4 負向 fixture 與測試：每個 surface 都不回傳 `queue` 活動；home predicate 不回傳 NULL 或 radar
- [ ] T3.5 `web/components/AdminEventTable.tsx`：顯示 tier 與 score 欄、新增「Relevance queue」篩選（依分數由高到低）、顯示 `reason_zh`／`evidence`；動作包括「相關→radar」「相關→home」（寫入 FC 鎖並更新 `feed_tier`）與「不相關」（重用既有 irrelevant 下架路徑）；使用既有 design system 元件
- [ ] T3.6 `web/lib/adminEventMutationsCore.ts`／`fieldCorrections.server.ts`：若有 FC 欄位 allowlist，加入 `feed_tier`、`content_type`；確認 maintenance lock 啟用時，操作會正確失敗並顯示訊息
- [ ] T3.7 `web/app/[locale]/about/page.tsx`：加入三語的「編輯方針：政治與時事內容」段落（等 F7 決定），新增 `about.*` key，三語 `messages/*.json` 同步更新，且不得刪除任何既有 key（i18n Regression Guard）
- [ ] T3.8 `cd web && npm run build && npm run lint`；執行硬編碼 CJK 檢查
- [ ] T3.9 本地預覽（先 `git fetch origin && git rebase origin/main`）：比對首頁列表、分類頁、城市頁、sitemap 中 queue 活動確實消失，並抽 5 筆 queue 活動確認詳情頁可開啟且帶 noindex

## Phase 4：R-QA-5 Researcher 治理與持續量測（S–M）

- [ ] T4.1 **Policy supersession audit**：對 `.github/agents/researcher.agent.md`、`.github/skills/agents/researcher/SKILL.md`、`.github/skills/agents/researcher/history.md`、`scraper/auto_scraper/auto_research.py`、`.github/skills/**/scraper-dev*` 做 exact 搜尋（`coverage over precision`、`Low-Signal`、`0.70`、`assessed`）與 semantic 搜尋，逐條把命中標為 active 或 historical
- [ ] T4.2 Researcher SKILL：以「Precision-First Source Policy（R-QA-5）」取代 Low-Signal Policy；history 中的相關條目就地加上 `superseded（2026-10，R-QA-5）` 標註；agent 的 profile 格式加入 `Precision: x/N`、`Estimated precision`
- [ ] T4.3 `supabase/migrations/098_research_sources_precision.sql`（`estimated_precision`、`precision_sample_size`、`precision_evaluated_at`）；手動執行並驗證；同一個 commit 更新 `database.instructions.md`
- [ ] T4.4 `scraper/update_source.py`：新增 `--precision` 與 `--precision-sample` 旗標
- [ ] T4.5 `scraper/auto_scraper/auto_research.py`：停止自動升級為 `researched`（一律 `assessed`）；docstring 同步更新；auto-generate 是否整個暫停，依 F5 決定
- [ ] T4.6 `eval_relevance.py --source-report`：逐來源的 tier 分布與 queue 比例 → `docs/evaluation/relevance/sources-YYYY-MM.md`
- [ ] T4.7 `eval_relevance.py --weekly-sample 20`：產生每週待標清單，並在 LINE 週報附一行摘要（被動 push，不新增 admin 頁面）
- [ ] T4.8 `.github/workflows/eval-relevance.yml`：PR 觸及 `scraper/relevance_*.py` 或 `scraper/tests/golden_relevance/**` 時執行；holdout 雜訊率 > 5% 或レーダー召回率 < 95% 時失敗
- [ ] T4.9 `python3 scripts/sync_ai_adapters.py`，再執行 `--check` 確認沒有漂移

## Verification

- [ ] `cd scraper && python -m pytest tests/test_relevance_*.py tests/test_build_relevance_golden.py`
- [ ] `cd web && npm run build && npm run lint`
- [ ] Phase 1 gate 與 Phase 2 驗證 SQL 全部通過（結果貼進 `docs/evaluation/relevance/`）
- [ ] 每日 CI 第一次執行後，`feed_tier IS NULL` 的 active parent 只有當日的新增項目，且下一輪就會補齊
- [ ] 回報 `intent-homepage` 前置條件已滿足（active parent 中 NULL 數 = 0，`applyHomeFeed` 可以使用）
- [ ] **G3**：rebase 到 `origin/main` → 交給 V-M-D；push 前取得使用者明確同意
- [ ] 上線後 4 週：用每週抽樣計算滾動首頁雜訊率，與 T0.7 的基準比較（H5 後測的品質面；點擊與信任面由 `intent-homepage` 的 A/B 量測）
