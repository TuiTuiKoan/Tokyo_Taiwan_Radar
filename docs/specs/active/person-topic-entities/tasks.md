# Tasks — person-topic-entities（Person／Organizer＋Topic＋follow Topic）

每完成一步把 `- [ ]` 改 `- [x]`，並 commit（即使只改這一行）。設計與理由見 `proposal.md`；各 Phase 可以獨立上線，建議順序：0 → A → B → C → D → E（F 是 P1）。

> **全程禁止**：在主工作樹實作；讓 LLM 寫 `events.organizer*`／`people.*` 的名稱、翻譯或 URL；從 `creators.nationality` 複製任何資料；在 `user_follows` 加通知欄位（那是 LINE spec 的範圍）。

## Phase 0: Worktree Setup、baseline 與決策（S）

- [ ] **Worktree 確認閘門**：執行 `git worktree list --porcelain` 並把結果給使用者看，**向使用者確認**要在新的 `ttr-person-topic-entities-worktree`（branch `feat/person-topic-entities`）實作。得到明確答覆前不得動工，主工作樹不是選項（`.github/instructions/git.instructions.md` § Worktree confirmation gate）。
- [ ] 依 § Isolated worktree 的 state matrix 建立（規劃時是 branch missing → `git worktree add ttr-person-topic-entities-worktree -b feat/person-topic-entities`；執行前重新判斷狀態，path 已存在但不是 worktree → STOP）。
- [ ] idempotent 地把 `ttr-person-topic-entities-worktree/` 加進 `.git/info/exclude`：`grep -qxF 'ttr-person-topic-entities-worktree/' .git/info/exclude || echo 'ttr-person-topic-entities-worktree/' >> .git/info/exclude`
- [ ] 在 worktree 內 `git fetch origin && git rebase origin/main`；Session 計畫檔寫上 slug `person-topic-entities`。
- [ ] **Migration 序號重新確認**：`ls supabase/migrations | sort | tail -5`。規劃時 next＝`097`；若已被使用，就往後順延並同步修改本檔與 proposal（works spec 的教訓：計畫寫 046，實際落在 048）。
- [ ] **Baseline 量化（唯讀，service role，記錄到本檔下方的 Baseline 區）**：
  ```sql
  -- B1 主辦者字串規模（只算 active＋annotated/reviewed）
  SELECT count(DISTINCT organizer) AS distinct_org,
         count(*) FILTER (WHERE organizer IS NOT NULL) AS events_with_org
  FROM events WHERE is_active AND annotation_status IN ('annotated','reviewed');
  -- B2 演出者／講者字串規模
  SELECT count(DISTINCT p) FROM events, unnest(performers) AS p
  WHERE is_active AND annotation_status IN ('annotated','reviewed');
  -- B3 出現在 >=2 筆活動的名字（Person 候選池上限）
  WITH names AS (
    SELECT id, organizer AS n FROM events WHERE is_active AND organizer IS NOT NULL
    UNION ALL SELECT id, unnest(co_organizers) FROM events WHERE is_active
    UNION ALL SELECT id, unnest(performers) FROM events WHERE is_active)
  SELECT count(*) FROM (SELECT n FROM names GROUP BY n HAVING count(DISTINCT id) >= 2) t;
  -- B4 每月新增人名量（決定 link_people.py 的排程，依「規模量化先於工具化」）
  SELECT date_trunc('month', created_at) m, count(*) FROM events
  WHERE created_at > now() - interval '6 months'
    AND (organizer IS NOT NULL OR cardinality(performers) > 0) GROUP BY 1 ORDER BY 1;
  -- B5 每個種子 topic 的近 30 天活動數（用 proposal §2.2 的映射）
  SELECT count(*) FROM events WHERE is_active AND parent_event_id IS NULL
    AND annotation_status IN ('annotated','reviewed')
    AND start_date BETWEEN now() AND now() + interval '30 days'
    AND category && ARRAY['movie','documentary'];  -- 每個 topic 各跑一次
  -- B6 organizers registry 現況
  SELECT count(*), count(*) FILTER (WHERE is_authoritative) FROM organizers;
  ```
- [ ] Step 0 drift 檢查（Pre-flight Baseline-Drift Guard）：每個 Phase 開始時重新確認 HEAD == origin/main，並重新執行 B1–B3，若和記錄值差距 > 10% 就先回報。
- [ ] **創辦人決策**（proposal §11）：Q1 音楽頻道、Q2 未認領個人 noindex、Q3 機構頁範圍、Q4 撤除管道與 SLA 是 Phase B／C 的前置條件；Q5–Q7 可以延後。把答覆記錄在本檔 Decisions 區。

## Phase A: Schema（M）

> 套用方式：Supabase Dashboard → SQL Editor（沒有 CLI）。每個 migration 用 `BEGIN; … COMMIT;` 包起來，並寫明 rollback 註解。新表**必須**明寫 GRANT（10/30 政策）。

- [ ] 撰寫 `supabase/migrations/097_person_topic_entities.sql`：
  - [ ] `topics`、`topic_categories`（proposal §2.1），並 seed 8 個 topics 與 §2.2 的映射（依 Q1 決定 `music` 的標籤）
  - [ ] `people`、`person_admin_meta`、`person_aliases`、`person_topics`、`event_people`、`person_link_candidates`（proposal §3.1；含所有 CHECK、unique index 與 `event_people(person_id)` index）
  - [ ] `updated_at` triggers 重用既有的 `public.set_updated_at()`（050）
  - [ ] trigger：`AFTER INSERT ON public.people` 自動建立 `person_admin_meta` 列（`INSERT … ON CONFLICT DO NOTHING`；function 設 `SET search_path = pg_catalog`，所有物件都寫 schema 名稱）
  - [ ] RLS 與 GRANT（已逐行做過語法檢查，見下方 SQL 片段）
  - [ ] view `public.event_person_signals`（proposal §5.1）
- [ ] 撰寫 `supabase/migrations/098_user_follows.sql`（proposal §4.1）
- [ ] **SQL Privilege Syntax Guard 逐行檢查**：所有 view 的權限語句都用 `ON TABLE <view>`（沒有 `ON VIEW`）；沒有 `ALTER VIEW`；policy 中的 `auth.uid()`／`is_admin()` 都包在 `(select …)` 裡。
- [ ] 在 SQL Editor 套用 097 → 執行 Verification V1–V6 → 套用 098 → 執行 V7–V8
- [ ] `web/lib/types.ts` 新增 `Topic`、`Person`、`PersonKind`、`EventPersonRole`、`UserFollow` 型別（**不動 `Category` union**），然後 `cd web && npx tsc --noEmit`
- [ ] 同一個 commit 更新 `.github/instructions/database.instructions.md`（Latest／next、Other tables、RLS policies 段）

### SQL 片段（GRANT／RLS／view；Architect 已逐行人工審查語法，Engineer 仍須在 SQL Editor 確認）

```sql
-- ── RLS enable（所有新表） ─────────────────────────────────────────────
ALTER TABLE public.topics                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.topic_categories       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.people                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.person_admin_meta      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.person_aliases         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.person_topics          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.event_people           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.person_link_candidates ENABLE ROW LEVEL SECURITY;

-- ── 公開讀取 policy ─────────────────────────────────────────────────────
DROP POLICY IF EXISTS topics_public_read ON public.topics;
CREATE POLICY topics_public_read ON public.topics
  FOR SELECT TO anon, authenticated USING (status = 'active');

DROP POLICY IF EXISTS topic_categories_public_read ON public.topic_categories;
CREATE POLICY topic_categories_public_read ON public.topic_categories
  FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS people_public_read ON public.people;
CREATE POLICY people_public_read ON public.people
  FOR SELECT TO anon, authenticated USING (status = 'published');

DROP POLICY IF EXISTS person_topics_public_read ON public.person_topics;
CREATE POLICY person_topics_public_read ON public.person_topics
  FOR SELECT TO anon, authenticated
  USING (EXISTS (SELECT 1 FROM public.people p
                 WHERE p.id = person_topics.person_id AND p.status = 'published'));

DROP POLICY IF EXISTS event_people_public_read ON public.event_people;
CREATE POLICY event_people_public_read ON public.event_people
  FOR SELECT TO anon, authenticated
  USING (EXISTS (SELECT 1 FROM public.people p
                 WHERE p.id = event_people.person_id AND p.status = 'published'));

-- ── admin policy（8 張表都要；以 topics 為例，其餘把表名換掉） ──────────────
DROP POLICY IF EXISTS topics_admin_all ON public.topics;
CREATE POLICY topics_admin_all ON public.topics
  FOR ALL TO authenticated
  USING ((select public.is_admin()))
  WITH CHECK ((select public.is_admin()));
-- 同樣建立：topic_categories_admin_all, people_admin_all, person_admin_meta_admin_all,
--           person_aliases_admin_all, person_topics_admin_all, event_people_admin_all,
--           person_link_candidates_admin_all

-- ── GRANT（Tier A：公開讀取） ───────────────────────────────────────────
GRANT SELECT ON TABLE public.topics, public.topic_categories, public.people,
                      public.person_topics, public.event_people
  TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE
  ON TABLE public.topics, public.topic_categories, public.people,
           public.person_topics, public.event_people
  TO authenticated, service_role;

-- ── GRANT（Tier B：admin-only；anon 不給） ───────────────────────────────
GRANT SELECT, INSERT, UPDATE, DELETE
  ON TABLE public.person_admin_meta, public.person_aliases, public.person_link_candidates
  TO authenticated, service_role;

-- ── relevance 訊號 view（只給 service_role） ─────────────────────────────
CREATE OR REPLACE VIEW public.event_person_signals
WITH (security_invoker = true) AS
SELECT
  ep.event_id,
  count(*) FILTER (WHERE ep.role IN ('hosted_by','co_hosted_by'))                     AS linked_host_count,
  count(*) FILTER (WHERE ep.role IN ('hosted_by','co_hosted_by')
                     AND m.taiwan_connection_confirmed_at IS NOT NULL
                     AND cardinality(m.taiwan_connection) > 0)                         AS taiwan_connected_host_count,
  count(*) FILTER (WHERE ep.role NOT IN ('hosted_by','co_hosted_by')
                     AND m.taiwan_connection_confirmed_at IS NOT NULL
                     AND cardinality(m.taiwan_connection) > 0)                         AS taiwan_connected_participant_count,
  ARRAY(
    SELECT DISTINCT k
    FROM public.event_people ep2
    JOIN public.people p2            ON p2.id = ep2.person_id AND p2.status IN ('draft','published')
    JOIN public.person_admin_meta m2 ON m2.person_id = p2.id AND m2.taiwan_connection_confirmed_at IS NOT NULL
    CROSS JOIN LATERAL unnest(m2.taiwan_connection) AS k
    WHERE ep2.event_id = ep.event_id
    ORDER BY k
  )                                                                                    AS taiwan_connection_kinds
FROM public.event_people ep
JOIN public.people p            ON p.id = ep.person_id AND p.status IN ('draft','published')
JOIN public.person_admin_meta m ON m.person_id = p.id
GROUP BY ep.event_id;

REVOKE ALL ON TABLE public.event_person_signals FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.event_person_signals TO service_role;

-- ── 098: user_follows ───────────────────────────────────────────────────
ALTER TABLE public.user_follows ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_follows_own ON public.user_follows;
CREATE POLICY user_follows_own ON public.user_follows
  FOR ALL TO authenticated
  USING ((select auth.uid()) = user_id)
  WITH CHECK (
    (select auth.uid()) = user_id
    AND (person_id IS NULL OR EXISTS (
          SELECT 1 FROM public.people p
          WHERE p.id = user_follows.person_id AND p.status = 'published'))
  );

GRANT SELECT, INSERT, DELETE ON TABLE public.user_follows TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.user_follows TO service_role;
```

語法審查紀錄（2026-10-06，Architect 人工逐行審查；本機沒有可用的 Postgres 可以實跑，Engineer 必須在 SQL Editor 實際驗證）：`GRANT … ON TABLE a, b TO r1, r2` 可以一次列多個物件；view 的權限語句用 `ON TABLE`；`CREATE VIEW … WITH (security_invoker = true)` 需要 PG15 以上（Supabase 符合，並和 `084_fix_security_invoker_views.sql` 一致）；`CREATE POLICY … FOR ALL TO authenticated USING (…) WITH CHECK (…)` 的順序正確；correlated `ARRAY(SELECT …)` 引用的是 GROUP BY 欄位 `ep.event_id`，合法；`REVOKE … FROM PUBLIC, anon, authenticated` 合法。

## Phase B: Topic＋follow Topic（M，R-EN-3、R-FL-1，可以獨立上線）

- [ ] `web/lib/eventVisibility.ts`：`publicEventFilter(query, { includeSubEvents?: boolean })`，套用 is_active、annotation_status、parent_event_id，加上 relevance hook（no-op）。在 relevance spec 上線前暫時排除 `geopolitics`、`report` 與純出版紀錄（`event_form` 正規化後等於 `['publication']`；判定方式要依 Publication Policy Invariant，**不得**用 category 或 source 代替）。
- [ ] `web/lib/topics.ts`：`getTopicBySlug`、`getTopicChannels`、`getTopicUpcomingEvents`、`getTopicCategories`、`getFollowedTopicSlugs`（形狀依 proposal §5.2／§5.3）。查詢的 `.select()` 必須包含 predicate 用到的欄位（Predicate projection contract guard）。
- [ ] `web/app/[locale]/topics/[slug]/page.tsx`（＋`loading.tsx`、`opengraph-image.tsx`）：`generateStaticParams`、`generateMetadata`（三語、canonical、`x-default`）、`revalidate = 3600`、JSON-LD `CollectionPage`＋`ItemList`（用 `serializeJsonLd`）、活動數 < 3 時 noindex。
- [ ] `web/components/FollowButton.tsx`：沿用 `SaveButton` 的模式（掛載時自讀狀態、未登入時導向 `/auth/login?next=`、`try/finally` 重置 loading——Loading State Try/Finally Guard），`insert` 遇到 `23505` 視為成功；使用 design system 的按鈕元件。
- [ ] `/saved` 頁：「フォロー中のトピック」chips＋近期活動列表（不改 `saved_events` 的查詢）。
- [ ] `web/app/sitemap.ts` 加入 active topics（三語＋`x-default`）。
- [ ] `web/app/[locale]/admin/topics/page.tsx`：唯讀映射檢視、近 30 天活動數、不在 `CATEGORIES` 中的 category 標紅。
- [ ] i18n：`topic.*`、`follow.*`、`saved.following*`、`admin.topics.*` 三語同時新增；執行 hardcoded CJK grep（web.instructions.md）。
- [ ] Topic 頁 OG 圖：英文長標題與日文短標題各驗證一組（OG Image Multi-Language Truncation Rules）。
- [ ] Commit：`feat(web): topic pages and follow-topic (person-topic-entities phase B)`

## Phase C: Entity resolution＋Admin people＋種子 backfill（L）

- [ ] `scraper/link_people.py`（預設 dry-run，`--apply` 才寫入；輸出 manifest JSON）：
  - [ ] 候選池與正規化依 proposal §3.3-1/2（重用 `merger._normalize`；不用 `・` 切分；`performer` 含 `、`／`,` 時跳過）
  - [ ] 比對階梯 (a)–(e)；(a) 只接受唯一、且 `source` 是人工確認的 alias；`do_not_recreate=true` 的 person 永不建議
  - [ ] LLM 只寫 `llm_entity_kind`（gpt-4o-mini，結構化輸出），不產生名稱、翻譯或 URL
  - [ ] `--check-stale`：`evidence_name` 已不在該活動任何人名欄位 → 建立 `stale` candidate，不刪除連結
  - [ ] Supabase 分頁：所有載入都用 `.range()` 迴圈並核對 `count='exact'`（Supabase 分頁完整性規則）
- [ ] `scraper/tests/test_link_people.py`：唯一 exact → 自動連結；同名兩人 → 進佇列（負向）；相似度 0.84 → 不產生候選（負向）；片假名 `・` 名不被切開；`do_not_recreate` 不被建議；LLM 輸出含 URL 時丟棄。
- [ ] Admin：`web/app/api/admin/people/**/route.ts`（server 端 `is_admin()` 檢查＋service role；只 select 需要的欄位）、`admin/people/page.tsx`、`admin/people/[id]/page.tsx`、`admin/people/candidates/page.tsx`。表單元件遵守 Admin Form Component Prop Completeness Guard 與 Design System Guard；i18n `admin.people.*` 三語。
- [ ] Person 發布檢查清單（寫進 admin 編輯頁，status 切成 `published` 前必須逐項勾選）：名稱和原文一致／連結由人工驗證／沒有私人資訊／kind 正確／index_policy 已依 Q2 設定／`taiwan_connection` 有證據或留空。
- [ ] `scraper/_oneoff_seed_people.py`：依 B3 排序，取前 50–100 位＋種子供給方，建立 draft 並產生候選，帶 `link_batch_id`；rollback 指令寫在腳本 docstring。依 Phase 0 量化結果決定是否需要分批。
- [ ] `scraper/merger.py`：停用 secondary 時，把 secondary 的 `event_people` 改指到 primary（衝突的 PK 跳過）；**不動** `_normalize()`／`_SIMILARITY_THRESHOLD`。執行 Merger `_normalize()` Guard 的 sanity test，確認沒有回歸。手動合併工具同步處理（Manual Merge Completeness Guard）。
- [ ] 依 B4 決定 `link_people.py` 排程（< 20／月 → 手動；20–100 → 每週手動；> 100 → 在 `scraper.yml` 加獨立 step，失敗不阻擋爬蟲）。
- [ ] 人工審核並發布 ≥ 20 位 people（含種子供給方），每位都有 ≥ 1 筆已確認的 `event_people`。
- [ ] Commit：`feat(scraper,web): person entity resolution and admin (phase C)`

## Phase D: Person 頁＋活動頁連結＋SEO＋跨 spec helpers（M）

- [ ] `web/lib/people.ts`：`getPersonBySlug`、`getPersonEvents`（包含 sub-event 並附上主活動）、`getFeaturedPeople`、`getEventPeople(eventId)`。
- [ ] `web/app/[locale]/people/[slug]/page.tsx`（＋`opengraph-image.tsx`，只用文字，不放肖像）：非 published → `notFound()`；`index_policy` → robots；JSON-LD 的 `@type` 依 kind 對應、`@id`、`sameAs`；不輸出 nationality、image（未認領時）、address。
- [ ] 「このページについて」區塊：資料來源與 AI 使用說明、削除・訂正の依頼（管道依 Q4）。
- [ ] `web/app/[locale]/events/[id]/page.tsx`（約 :1065-1125）：有已確認連結的 organizer／performer 改成 Link；沒有連結時維持原樣（負向 fixture）。被 anon 擋掉的連結（person 未發布）**不得**改用 service role 繞過。
- [ ] `web/lib/publicationStructuredData.ts:138-157`：有連結時 organizer／performer 加上 `@id`＋`url`；沒有連結時維持原樣。
- [ ] `web/app/sitemap.ts`：只加入 `status='published' AND index_policy='index'` 的 people。
- [ ] i18n：`person.*` 三語。
- [ ] 跨 spec smoke test：`getTopicChannels`／`getTopicUpcomingEvents`／`getFeaturedPeople`／`getFollowedTopicSlugs`／`getTopicCategories` 的回傳形狀符合 proposal §5；用 service role 查 `event_person_signals` 能看到 seed 資料，用 anon 查必須被拒（42501）。
- [ ] 撤除演練：把測試 person 設為 hidden → 頁面 404、活動頁連結消失、`event_person_signals` 不計入；再恢復。
- [ ] Commit：`feat(web): person pages, event links and structured data (phase D)`

## Phase E: 指標＋文件＋Guards（S）

- [ ] 依 Q6：`entity_views` 聚合表（Tier C：只有 service_role 寫入，admin 讀取）＋在 Topic／Person 頁記錄瀏覽與 referrer 種類；（若 Q6 同意）`user_active_days`。新表一樣要明寫 GRANT。
- [ ] Admin stats 卡片：follow 總數、每週新增、每位使用者平均 follow 數、活動頁 → Person 的點擊比例。
- [ ] `docs/ARCHITECTURE.md`：新 API endpoint（`/api/admin/people/**`）與 entity 分層圖（Docs Update Rule）。
- [ ] `.github/agents/architect.agent.md` 新 Guard「Person Entity vs Organizer Registry vs Creators Guard」（三套結構的職責；LLM 不寫產品層；不建國籍欄位；撤除 tombstone）。
- [ ] `.github/skills/agents/engineer/SKILL.md`：person 連結與 `publicEventFilter()` 慣例。
- [ ] 若有修改 agent、skill 或 prompt：執行 `python3 scripts/sync_ai_adapters.py`，再用 `--check` 確認。
- [ ] H2 計時開始日（Phase B 上線日）記錄到本檔；4 週後產出回訪報告。

## Phase F（P1，另行排程）

- [ ] Person 頁的 follow UI（R-FL-2；schema 已支援）
- [ ] `person_claims` migration＋認領流程（proposal §3.7；server action 只開放可改欄位；驗證用 SNS 代碼或官方網域 email）
- [ ] `organizer-submission-v2` 介接 `findOrSuggestPersonForCreator(creatorId)`（只建立 candidate）
- [ ] 和 `line-segmented-digest` 交接：頻道 slug 對應、`getTopicCategories`、LINE 帳號連結由 LINE spec 負責

## Verification

- [ ] **V1** 8 個 topics 與映射：`SELECT t.slug, array_agg(tc.category ORDER BY tc.category) FROM topics t LEFT JOIN topic_categories tc ON tc.topic_id = t.id GROUP BY t.slug;`
- [ ] **V2** 映射裡沒有未知的 category（在 web 端和 `CATEGORIES` 比對；admin/topics 頁沒有紅色項目）
- [ ] **V3** anon（`SET ROLE anon;`）：`SELECT count(*) FROM person_admin_meta;`、`person_aliases`、`person_link_candidates`、`user_follows`、`event_person_signals` → 全部 permission denied（42501）
- [ ] **V4** anon 只看得到 published：插入 draft、hidden 測試列後，`SELECT count(*) FROM people WHERE status <> 'published';` → 0
- [ ] **V5** `event_people` 對 draft person 的連結 anon 看不到
- [ ] **V6** CHECK：`people.status='published'` 但 `published_at` 為 NULL → 拒絕；`taiwan_connection` 填不合法的值 → 拒絕；`user_follows` 同時有 topic_id 和 person_id → 拒絕
- [ ] **V7** 已登入的 A 使用者讀不到 B 使用者的 `user_follows`；follow 未發布的 person → WITH CHECK 拒絕；同一個 topic 重複 follow → 23505
- [ ] **V8** RLS 效能：`EXPLAIN ANALYZE` 讀取 Topic 頁的 people 與 `/saved` 追蹤區塊，確認看到 InitPlan（沒有逐列執行 `is_admin()`）
- [ ] `cd web && npx tsc --noEmit && npm run lint && npm run build` 通過
- [ ] `cd scraper && python -m pytest tests/test_link_people.py` 通過；`python link_people.py`（dry-run）manifest 合理
- [ ] i18n：`git diff origin/main -- 'web/messages/*.json' | grep '^-'` 沒有非預期的刪除；`categories` namespace 完整（i18n Regression Guard）
- [ ] Rich Results Test：Topic 頁、Person 頁（band 一例、individual 一例）、一個有連結的活動頁
- [ ] Vercel preview 驗證三語路由，再交給 V-M-D；**push 需要使用者明確同意**

## Baseline（Phase 0 填寫）

| 項目 | 值 | 查詢時間 |
|---|---|---|
| B1 distinct organizer／events_with_org | | |
| B2 distinct performers | | |
| B3 出現 ≥ 2 筆活動的名字數 | | |
| B4 每月新增含人名的活動數 | | |
| B5 各 topic 近 30 天活動數 | | |
| B6 organizers 總數／authoritative | （095 記載：206／4，2026-08-01） | |

## Decisions（Phase 0 填寫）

| Q | 決定 | 日期 |
|---|---|---|
| Q1 音楽頻道 | | |
| Q2 未認領個人 noindex | | |
| Q3 機構頁範圍 | | |
| Q4 撤除管道／SLA／tombstone | | |
| Q5 organizers 台灣關聯 | | |
| Q6 user_active_days | | |
| Q7 台湾人主催標籤 | | |
