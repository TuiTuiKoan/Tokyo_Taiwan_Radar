---
slug: person-topic-entities
title: Person／Organizer 與 Topic 實體、follow Topic（TTR 2.0 資料模型擴張 P0）
status: proposed
branch: feat/person-topic-entities
created: 2026-10-06
tags: [data-model, ttr-2.0, entity, follow, web, scraper, seo, privacy]
---

## What（做什麼）

在既有 `events`／`works` 之上新增兩種**產品層實體**與一個使用者關係：

1. **Topic（次領域頻道）**：`topics` 加上 `topic_categories` 映射表。Topic 是使用者看得到、可以 follow 的頻道（§6.4 的八個：音楽／映画／原住民／ことば／茶と食／文学／学術／親子）。40 個 `Category` 保留為 AI 標註層，不取代。
2. **Person／Organizer**：`people`（公開安全欄位）、`person_admin_meta`（僅限管理員的內部欄位）、`person_aliases`（別名）、`person_topics`、`event_people`（event↔person 多對多，帶角色）、`person_link_candidates`（entity resolution 的人工確認佇列）。
3. **Follow**：`user_follows`（`target_type: topic | person`，日後可加 community／place）。P0 只開放 follow Topic 的 UI（R-FL-1）；follow Person（R-FL-2）在 schema 先支援，UI 列為 P1。

並交付：`/[locale]/topics/[slug]`、`/[locale]/people/[slug]` 兩種公開頁（三語、schema.org JSON-LD）、`/saved` 增加「フォロー中」區塊、活動詳情頁的主辦者與演出者連到 Person 頁、最小 Admin（people CRUD、候選佇列、topic 映射唯讀檢視），以及供 `taiwan-relevance-scoring`、`intent-homepage`、`line-segmented-digest` 使用的資料介面。

## Why（為什麼）

- 需求文件 §4.2 Q4：目前只有 Event 實體，無法形成「event → person → topic → community → next event」的關係圖譜與回訪理由。Q5：留存只靠 LINE 週報，沒有 follow。
- §7 P0 明列「Person／Organizer 與 Topic 實體、follow Topic（§6.2、§6.5）」。§11 **H2**（使用者願意 follow Topic／Person，並因此回訪）要等 follow 上線 4 週後才能驗證，所以越早上線越好。
- §3「長期威脅」：AI 搜尋讓「找活動」商品化，護城河要從索引升級為「經人工校正的關係圖譜」。Person／Topic 是這張圖譜的前兩個節點。
- §10 的「關係」指標（每位使用者平均 follow 的 Topic／Person 數、從活動頁跳到 Person 的比例）沒有這份 spec 就無從量測。

## 現況盤點（2026-10-06，主工作樹 `main` 讀取）

### A. 已存在、和本 spec 重疊的實體（最重要的發現）

repo 裡已經有**三套**「人／組織」相關結構，都不能直接當作 2.0 的 Person：

| 既有結構 | 位置 | 現況 | 為什麼不能直接當 Person |
|---|---|---|---|
| `organizers` | `supabase/migrations/050_entity_tables.sql:95-106`；`095_organizer_authority.sql:304-322` | 正規化主辦方 registry：`canonical_name_ja` UNIQUE、`aliases TEXT[]`、`homepage`、`organizer_type`（10 值）、`is_authoritative`。095 註記 live 有 206 列、4 列 authoritative。public SELECT（050:143-144）＋ anon GRANT（`069_explicit_grants.sql:51-54`） | 它是**標註層**：服務報表彙整與 annotator 的 `organizer_type` 權威判定（`scraper/organizer_registry.py:1-24`、`scraper/database.py:290-320,479-480`、`scraper/annotator.py:1959-1976,2054-2056`）。大部分是機構（交流協會、文化中心、政府）。沒有 slug、SNS、頁面狀態或同意狀態；不收演出者與講者。 |
| `creators` | `020_creators.sql:6-22`；`086_account_profiles.sql`（加 `user_id`、`user_handle`、`social_*`、`avatar_url`）；`088_rls_perf_account.sql:51-63` | 兩種用途混在一起：(1) admin-only 的「在日台灣創作者情報」；(2) 投稿者帳號的 profile（`web/app/actions/profile.ts:109-150`、`web/app/[locale]/account/profile/page.tsx:62-64`）。**含 `nationality` 欄位**（020:15） | 不公開，而且 `nationality` 直接違反 §6.11「不做國籍標籤」。它是**帳號層**，適合作為 R-SP-3 認領時的「帳號端」，不適合當公開頁。 |
| `creator_events` | `020_creators.sql:29-34` | `(creator_id, event_id, relationship)`，admin-only | 綁在 `creators` 上，沒有信心分數、證據欄位或確認者。本 spec 不遷移它（見 Non-Goals）。 |

`events` 上的人名欄位全是**自由文字**：`organizer`／`organizer_zh`／`organizer_en`（035、059）、`co_organizers[]`＋`co_organizer_types[]`（035、058，095 加 cardinality CHECK）、`sponsors[]`、`performer`、`performers[]`／`performers_zh[]`／`performers_en[]`（053、054、056）、`performer_url`／`performer_urls[]`（078、079）、`organizer_url`、`organizer_id`（050:126-127，FK→organizers）。

### B. 「不捏造主辦方」規則（Person 自動化必須繼承）

- Prompt：`scraper/annotator.py:1256`（NEVER fabricate organizer names…）。
- 寫入守衛：`annotator.py:2703-2715`（GPT organizer 不在原文就丟棄）、`annotator.py:2843-2856`（`_org_name not in _source_text` → 清空 organizer 與翻譯）。
- 譯名覆寫：`_KNOWN_ORGANIZER_MAP`（`annotator.py:703`）、`_KNOWN_PERSON_MAP`（`annotator.py:684`）。
- Alias 歧義時不寫入：`database.py:300-320`（alias 命中多列 → 不設 `organizer_id`）、`organizer_registry.py:18-23`（重複的 key 全部拒絕）。
- `merger.py` 只在 `_normalize()` 去掉標題尾端的【主辦者註記】（`merger.py:113`），不合併 organizer 欄位。merger 把 secondary 設為 `is_active=false` 時，secondary 上的連結會留著（見 Design §3.6）。
- 既有群集工具：`scraper/backfill_entities.py:43-94`、`scraper/_oneoff_review_organizer_clusters.py`（用 `merger._normalize`＋SequenceMatcher 做群集，交人工審核）。本 spec 的 resolver 沿用這套方法。

### C. Category（標註層）

- `web/lib/types.ts:186-226` `Category` union（40 個值）、`:228-269` `CATEGORIES`、`:356-383` `CategoryGroup`／`CATEGORY_GROUPS`（arts／lifestyle／knowledge／society／archive）。
- **缺口**：沒有 `music`。`performing_arts` 的 ja 標籤是「音楽・演劇」（`web/messages/ja.json` categories.performing_arts），所以「音楽」頻道沒辦法只靠 Category 精準算出來（見未決問題 Q1）。
- 既有公開分類頁：`web/app/[locale]/categories/[category]/page.tsx`（`generateStaticParams` 在 :172-176，用 `.contains("category", [...])` 查詢，JSON-LD 在 :295），已列入 sitemap（`web/app/sitemap.ts:82-88`）。`events.category` 已有 GIN index（`001_initial.sql:72`）。
- `.github/copilot-instructions.md`、`web.instructions.md`、`scraper.instructions.md` 的 Categories 段落仍寫舊的 18 值清單，和 `types.ts` 的 40 值不一致（屬既有文件漂移，本 spec 只記錄，不處理）。

### D. 收藏、auth 與 LINE

- `saved_events`：`001_initial.sql:92-101`（`unique(user_id,event_id)`）；RLS 用 `(select auth.uid()) = user_id`（`088_rls_perf_account.sql:44-49`）；GRANT 給 authenticated 與 service_role（`069_explicit_grants.sql:98-99`）。
- `/saved`：`web/app/[locale]/saved/page.tsx:50-67`（server 端 `supabase.auth.getUser()`，未登入時 redirect 到 `/auth/login?next=`；嵌入 events join）。`web/components/SaveButton.tsx:22-61`（client 端直接 insert／delete，未登入時導向登入頁）。`web/app/[locale]/account/page.tsx:39` 也讀 `saved_events`。
- Auth：Supabase Auth，Google OAuth（`web/app/[locale]/auth/login/page.tsx:60-61`）＋ email OTP（`:94`）。Admin 判定用 `public.is_admin()`（STABLE，`088:20-30`），`user_roles.role='admin'`。
- LINE：`line_subscribers` 以 `line_user_id` 為鍵，偏好是 `category_preferences text[]`（Category 值，`022_line_subscribers.sql:12`；寫入點在 `web/app/api/line-webhook/route.ts:318-325`）。**它和 auth user 沒有連結**，這是 R-FL-3 的介面重點。

### E. SEO 現況

- 活動 JSON-LD（`web/lib/publicationStructuredData.ts:138-157`）：organizer 是只有 `name`／`url` 的 `Organization`，沒有 organizer 時退回成「Tokyo Taiwan Radar」；performer 是只有 `name` 的 `Person`。都沒有 `@id`，也沒有 `sameAs`。
- 活動詳情頁的主辦者與演出者是純文字（`web/app/[locale]/events/[id]/page.tsx:1049-1125`），ISR `revalidate = 3600`（:39）。

### F. Migration 序號

`database.instructions.md` 記載 latest = `096`、next = `097`；`ls supabase/migrations` 共 97 檔，最大號是 096。**教訓（works spec）**：它計畫用 `046`，實際落在 `048`。實作開始時必須重新 `ls supabase/migrations | sort | tail -5`，不可沿用本文件的號碼。

## Non-Goals（不做什麼）

- **不做** R-EN-4 Community 與 R-EN-5 Place 實體。只在 `user_follows` 和 topic 映射預留擴充點（加欄位＋改 CHECK 就能擴充）。
- **不重新上傳作品**（R-EN-2）：Person 頁只放外部連結（IG／YouTube／X／官網）與 TTR 已收錄的活動，不抓取、不轉存對方的圖片、影片、貼文或作品。
- **不做**國籍、族裔、政治立場、「台灣人經營」等標籤（§6.11、§1.2）。`people` 沒有 `nationality` 欄位，也**不得**從 `creators.nationality` 複製資料。
- **不做** AI 自動產生人物簡介（bio）：避免幻覺與名譽風險。bio 只能由管理員撰寫或由認領者提供。
- **不改 annotator 的 organizer 抽取邏輯**，也不讓 LLM 寫 `events.organizer*`。Person 連結是**下游、唯讀**於 events 的步驟。
- **不取代 `organizers` registry 與 `organizer_type` 權威機制**，不取代 `creators`（帳號 profile），不遷移 `creator_events`。三者的整併另開 spec。
- **不做** R-FL-3 LINE 分眾推播本體（另一份 spec `line-segmented-digest`）。本 spec 只提供資料介面。
- **不做** R-SP-3 認領流程本體（P1）。本 spec 只定義 schema 欄位與介面契約。
- **不做** follow 的公開人數、追蹤者名單或任何社交圖公開（追蹤關係屬隱私）。
- **不做** Topic 對活動的手動 include／exclude 覆寫，也不做 `/topics`、`/people` 索引頁（首頁由 `intent-homepage` 負責）。
- **不做** `work_people`（作品↔人）連結；`works.director` 維持文字。
- **不新增 Category**。若創辦人決定新增 `music`（Q1），走既有 `add-category` skill，作為獨立的小變更。

## Design（設計摘要）

### 1. 分層原則

| 層 | 用途 | 誰寫 | 公開？ |
|---|---|---|---|
| 標註層：`events.category`、`events.organizer*`、`performers[]`、`organizers` registry | AI 與爬蟲產生的結構化事實 | scraper／annotator（含既有守衛） | 依 events RLS |
| **產品層**：`topics`、`people` | 使用者看到、可 follow、可索引的實體 | **只有人**（admin；P1 起加上認領者） | `status='published'` 才公開 |
| 關係層：`topic_categories`、`event_people`、`person_topics` | 標註層 → 產品層的映射 | admin 確認；或確定性 exact-alias 自動連結 | 跟隨產品層的可見性 |
| 使用者層：`user_follows` | 個人化 | 使用者本人 | 只限本人 |

**原則：產品層不做分類。** 如果某個頻道無法用 Category 表達（例如「音楽」），應該修正標註層（新增 Category），而不是在 Topic 層塞關鍵字規則。

### 2. Topic

#### 2.1 Schema（migration A，序號實作時再確認，預計 `097`）

- `topics(id uuid pk, slug text unique CHECK '^[a-z0-9]+(-[a-z0-9]+)*$', name_ja/zh/en NOT NULL, description_ja/zh/en, is_channel bool default false, sort_order int, status text CHECK in ('active','hidden') default 'active', created_at, updated_at)`
- `topic_categories(topic_id fk→topics on delete cascade, category text, PRIMARY KEY(topic_id, category))`。`category` 不設 DB CHECK（避免和 40 值 union 產生第二份清單一起漂移），改用 admin 頁的 drift 警示加上 Verification 查詢。
- Topic 成員**由查詢推導**：`events.category && <該 topic 的 categories>`（用既有 GIN index）。不存 event↔topic 實體表。

#### 2.2 八個頻道的種子映射（預設建議，創辦人可改）

| slug | ja／zh／en | 映射的 `Category` | 備註 |
|---|---|---|---|
| `music` | 音楽／音樂／Music | `performing_arts`（暫時） | **Q1**：`performing_arts` 包含演劇。預設方案是頻道標籤暫用「音楽・舞台」，等 `music` Category 新增後再改成只映射 `music` |
| `film` | 映画／電影／Film | `movie`, `documentary` | `drama`（連續劇）、`tv_program` 不放進來 |
| `indigenous` | 原住民／原住民族／Indigenous | `indigenous` | |
| `language` | ことば／語言／Language | `taiwan_mandarin` | §6.10 的華語／台語／客語細分，留給 `social-affordance-tags` |
| `tea-food` | 茶と食／茶與食／Tea & Food | `tea_alcohol`, `lifestyle_food`, `herbal` | |
| `literature` | 文学／文學／Literature | `literature`, `books_media` | 純出版紀錄（`event_form=['publication']`）是否算「活動」，交給 relevance 的 R-QA-3 分流 |
| `academic` | 学術／學術／Academic | `academic` | `lecture` 範圍太廣，不放；`scholarship`／`study_abroad` 不是活動 |
| `family` | 親子／親子／Family | `parenting` | P1 時加上 social-affordance 的「親子OK」標籤 |

`geopolitics` 不映射到任何頻道（R-QA-4）。

#### 2.3 Topic 頁 `/[locale]/topics/[slug]`

- 內容：名稱與說明、Follow 按鈕、近期活動（共用的 `publicEventFilter()`，見 §5）、相關 Person（`person_topics`，只列 published）、底層 Category 頁的連結。
- SEO：`generateMetadata` 三語、`alternates.languages` 含 `x-default: /ja/...`、canonical；JSON-LD 用 `CollectionPage` 加 `ItemList`（Event 的 `url`）。和 Category 頁內容會部分重疊：Topic 頁是聚合頁，Category 頁保留。兩者互相連結，不互設 canonical。
- `revalidate = 3600`，`generateStaticParams` 從 `topics` 讀取（只取 active）。加入 `sitemap.ts`。

### 3. Person／Organizer

#### 3.1 Schema（migration A）

**`people`（公開安全欄位，anon 可讀 published 列）**

```
id uuid pk
slug text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$')   -- 發布後不可變
kind text NOT NULL CHECK (kind IN ('individual_creator','band','researcher','group'))
name_original text NOT NULL            -- 原文名，必須和活動原文逐字一致
name_ja, name_zh, name_en text         -- 三語顯示名；翻譯遵守 Known Person Map Guard（藝名不靠 GPT 音譯）
bio_ja, bio_zh, bio_en text            -- 只能由人撰寫；AI 不寫
external_links jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(external_links)='array')
                                        -- [{platform:'instagram'|'youtube'|'x'|'website'|'note'|'facebook'|'threads'|'other', url}]
avatar_url text                         -- 只接受認領者自行提供的圖片；P0 一律 NULL
status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','hidden','removed'))
index_policy text NOT NULL DEFAULT 'noindex' CHECK (index_policy IN ('index','noindex'))
claim_status text NOT NULL DEFAULT 'unclaimed' CHECK (claim_status IN ('unclaimed','pending','claimed'))
published_at timestamptz
created_at, updated_at
CHECK (status <> 'published' OR published_at IS NOT NULL)
```

**`person_admin_meta`（1:1，只限 admin 與 service_role；把敏感或內部欄位和公開表分開）**

```
person_id uuid pk fk→people on delete cascade
organizer_id uuid UNIQUE fk→organizers on delete set null     -- 橋接標註層 registry
creator_id   uuid UNIQUE fk→creators   on delete set null      -- 橋接帳號 profile（認領用，P1）
claimed_by_user_id uuid fk→auth.users on delete set null
claimed_at timestamptz
consent_basis text NOT NULL DEFAULT 'public_activity'
  CHECK (consent_basis IN ('public_activity','claimed','explicit_consent'))
taiwan_connection text[] NOT NULL DEFAULT '{}'
  CHECK (taiwan_connection <@ ARRAY['taiwan_based','taiwan_origin_works','taiwan_focused_activity','japan_taiwan_exchange']::text[])
taiwan_connection_evidence text        -- 原文引用或 URL；沒有證據就留空陣列
taiwan_connection_confirmed_by uuid fk→auth.users on delete set null
taiwan_connection_confirmed_at timestamptz
do_not_recreate boolean NOT NULL DEFAULT false   -- 撤除後的 tombstone：resolver 不再建議建立此人
removal_reason text, removed_at timestamptz
reviewed_by uuid fk→auth.users on delete set null, reviewed_at timestamptz
notes text
```

`taiwan_connection` 描述的是**活動與作品的事實**（據點在台灣／作品是台灣作品／活動以台灣為主題／日台交流團體），**不是國籍**。它不在公開頁顯示，只作為 relevance 訊號（見 §6.1）。

**`person_aliases`**：`(id, person_id fk cascade, alias text, alias_normalized text, source CHECK in ('manual','resolver_confirmed','claimant','organizer_registry'), created_at, UNIQUE(person_id, alias_normalized))`，另建 `alias_normalized` 的 index。同一個 normalized alias **允許**對應多個 person（同名異人），resolver 碰到這種情況一律不自動連結，送人工佇列。這和 `database.py:300-320` 的 alias 歧義處理一致。admin-only（不公開別名）。

**`person_topics`**：`(person_id fk cascade, topic_id fk cascade, PK)`，由人指定。

**`event_people`（只存「已確認」的連結）**

```
event_id  uuid fk→events on delete cascade
person_id uuid fk→people on delete cascade
role text CHECK (role IN ('hosted_by','co_hosted_by','performer','speaker','director','exhibitor','curator','moderator','guest'))
evidence_field text CHECK (evidence_field IN ('organizer','co_organizers','performer','performers','director','submission','manual'))
evidence_name text                       -- 連結當下欄位裡的原字串（之後檢查是否過期）
link_source text CHECK (link_source IN ('alias_exact','admin_confirmed','submission','claimant'))
link_batch_id uuid                       -- backfill 的批次 ID，用於 rollback
confirmed_by uuid fk→auth.users on delete set null
confirmed_at timestamptz NOT NULL DEFAULT now()
PRIMARY KEY (event_id, person_id, role)
INDEX (person_id)
```

**`person_link_candidates`（admin-only 佇列）**：`id, event_id fk cascade, evidence_field, raw_name, raw_name_normalized, suggested_person_id fk→people on delete cascade NULL, suggested_role, score numeric(4,3) CHECK 0..1, method CHECK in ('alias_ambiguous','normalized','fuzzy','llm_classify'), llm_entity_kind text CHECK in ('individual','band','researcher','group','institution','noise') NULL, status CHECK in ('pending','accepted','rejected','new_person','stale') default 'pending', batch_id uuid, reviewed_by, reviewed_at, created_at`。去重用 unique index `(event_id, evidence_field, raw_name_normalized, COALESCE(suggested_person_id,'00000000-0000-0000-0000-000000000000'::uuid))`。`rejected` 的 `(raw_name_normalized, suggested_person_id)` 組合在全域範圍內不再重新建議。

#### 3.2 RLS 與 GRANT（10/30 explicit GRANT 政策；本 migration 預計在 10/30 前後套用，一律明寫）

| 表 | RLS policy | GRANT |
|---|---|---|
| `topics` | SELECT `USING (status='active')`；admin ALL `USING ((select public.is_admin())) WITH CHECK ((select public.is_admin()))` | anon: SELECT；authenticated, service_role: SELECT/INSERT/UPDATE/DELETE |
| `topic_categories` | SELECT `USING (true)`；admin ALL | 同上 |
| `people` | SELECT `USING (status='published')`；admin ALL | 同上 |
| `person_topics`, `event_people` | SELECT `USING (EXISTS (SELECT 1 FROM public.people p WHERE p.id = person_id AND p.status='published'))`；admin ALL | 同上 |
| `person_admin_meta`, `person_aliases`, `person_link_candidates` | 只有 admin ALL | **anon 不給**；authenticated, service_role: SELECT/INSERT/UPDATE/DELETE（實際由 admin-only RLS 限制，和 `069` 中 `creators` 的模式一致） |

所有 policy 中的 `auth.uid()`／`is_admin()` 都包成 `(select …)`（`088` 的效能教訓）。新表**不加入** decision-16a 的維護鎖（`094`）範圍；這些表沒有 Admin Reports cleanup 的寫入面。

#### 3.3 Entity resolution（AI 建議＋人工確認）

新增腳本 `scraper/link_people.py`（dry-run 為預設，`--apply` 才寫入；輸出 manifest JSON）。它**只讀** events，寫入 `person_link_candidates`／`event_people`／`person_aliases`：

1. **候選字串池**：`organizer`、`co_organizers[]`、`performers[]`（沒有陣列時才用 `performer`）、`director`（低優先）。範圍：`is_active=true AND annotation_status IN ('annotated','reviewed')`。以 `(event_id, evidence_field, raw_name)` 為單位。
2. **正規化**：NFKC → 重用 `merger._normalize()` → 去掉敬稱（氏／さん／先生／教授／様）和外層括號【】「」。**不用 `・` 切分**（片假名人名裡的 `・` 是名字的一部分，見 Mixed-Script Performer Name Guard）。`、`／`,` 只在 `performer`（單值欄位）出現時視為污染並跳過（Performer Multi-Value Field Pollution Guard）。
3. **比對階梯**：
   - (a) `alias_normalized` exact 命中**唯一**一個 `status IN ('published','draft')` 且 `do_not_recreate=false` 的 person，**而且**該 alias 的 `source` 是人工確認過的（manual／resolver_confirmed／claimant）→ 確定性自動連結（`link_source='alias_exact'`）。這是確定性比對，沒有 AI 判斷，和 `database.py` 的 organizer_id FK lookup 同一級別。
   - (b) exact 命中多個 → candidate `alias_ambiguous`（score 1.0），送人工。
   - (c) 用 `people.organizer_id` 橋接 `organizers.aliases` 命中 → candidate（score 0.95）。
   - (d) SequenceMatcher(normalized) ≥ 0.85 → candidate `fuzzy`，score＝相似度。門檻沿用 merger 的 0.85，不得再調低（Merger `_normalize()` Guard 的精神）。
   - (e) 沒有命中，而且同一 normalized 名稱出現在 ≥ 2 筆活動 → candidate `new_person`，並用 gpt-4o-mini（沿用 scraper 既有 stack）只做**分類**：`llm_entity_kind`（individual／band／researcher／group／institution／noise）。LLM **不得**產生名字、翻譯、URL 或 SNS handle。
4. **人工確認**（Admin 候選佇列）：接受、改連到另一位、建立新 person（建成 draft）、拒絕。接受時寫入 `event_people`（`admin_confirmed`）並把 raw_name 加進 `person_aliases`（`resolver_confirmed`），讓下次可以走 (a)。
5. **過期偵測**：admin 用 `field_corrections` 修正 `organizer`／`performers` 之後，原連結可能失效。`link_people.py --check-stale` 會把 `link_source IN ('alias_exact','admin_confirmed')` 中 `evidence_name` 已不在該活動任何人名欄位的連結，標成 candidate `stale` 並送人工處理，**不自動刪除**。
6. **不捏造**：resolver 只連結**逐字出現在 events 人名欄位**的名字（這些欄位本身已經過 annotator 原文驗證）。`external_links` 只能由人工從原文或官方頁面填入。

**排程**：依 Architect SKILL「規模量化先於工具化」。Phase 0 先量化，然後決定：每月新增候選 < 20 → 只在 admin 手動觸發；20–100 → 每週一次手動執行；> 100 且持續累積 → 才接進 `scraper.yml`（獨立 step，失敗不阻擋爬蟲）。

#### 3.4 Person 建立門檻（隱私優先的 backfill 策略）

- 只為**有公開職業活動**的對象建立 Person：滿足以下任一條件 ——(i) 在 ≥ 2 筆公開活動中出現；(ii) 原文附有對方公開經營的專業 SNS 或網站；(iii) 是 §9 Phase 2 的種子供給方並同意；(iv) 自行投稿或認領。
- 預設**排除** `organizer_type` 屬於 `government`／`semi_official`／`commercial_brand`／`media` 的機構（它們留在 `organizers` registry；是否另外做機構頁見 Q3）。
- 只出現在 1 筆活動、身分是一般私人（例如小型聚會的個人主辦者、學生）→ 不建立頁面。
- 新建一律是 `draft`。發布前人工逐項檢查：名稱與原文一致、連結經人工驗證、沒有私人資訊（住址、私人電話、未公開的工作單位）、kind 正確、`index_policy` 已設定。
- Backfill 先做前 50–100 位（依活動數排序）加上種子供給方。腳本是 one-off（`scraper/_oneoff_seed_people.py`），帶 `link_batch_id`，rollback 方式是 `DELETE FROM event_people WHERE link_batch_id = $1`，再把該批建立的 draft people 刪除。

#### 3.5 Person 頁 `/[locale]/people/[slug]`

- 只顯示 `status='published'`；其他狀態一律 `notFound()`。
- 內容：三語顯示名（fallback：locale → ja → name_original）、kind、相關 Topic、外部連結（圖示＋文字，`rel="noopener"`；不嵌入對方的貼文或圖片）、**下一場活動**、近期活動、過去活動（摺疊，上限 N 筆）、「このページについて」區塊（資料來源與 AI 使用說明、**削除・訂正の依頼**連結；P1 加「このページの本人ですか？（認領）」）。
- 活動查詢**包含 sub-event**（演出者常常連在單場 sub-event 上），並標示主活動（Works Entity vs `parent_event_id` Guard：person 連結是 event 層級，和 `work_id`、`parent_event_id` 互不取代）。
- 被 merger 停用的活動（`is_active=false`）不會出現（events RLS 會擋掉）。merger 與手動合併工具應該把 secondary 的 `event_people` 改指到 primary（Manual Merge Completeness Guard；見 tasks Phase C）。
- **SEO**：`index_policy='noindex'` 時輸出 `robots: { index: false }`。預設規則：`band`／`group`，或已認領，或 `consent_basis='explicit_consent'` → `index`；未認領的 `individual_creator`／`researcher` → `noindex`（Q2）。只有 `index` 的頁面進 sitemap。
- **JSON-LD**：`kind` 對應到 `Person`（individual_creator、researcher）、`MusicGroup`（band）、`Organization`（group），欄位有 `@id = <page url>#entity`、`name`、`alternateName`（只放 name_ja/zh/en 中和 `name` 不同的值，**不放** admin-only 的 aliases）、`url`、`sameAs`（`external_links` 的 url）、`subjectOf`／`event`（近期 Event 的 url）。不輸出 `nationality`、`image`（除非已認領並自行提供）、`birthDate`、`address`。
- **活動 JSON-LD 回鏈**：`publicationStructuredData.ts:138-157` 的 organizer／performer 在有 confirmed `event_people` 時加上 `@id`／`url` 指向 Person 頁；沒有連結時維持現狀。
- 活動詳情頁（`events/[id]/page.tsx:1065-1125`）：主辦者與演出者名稱在有連結時改成 `Link` 到 Person 頁，沒有連結時維持純文字。使用既有 design system 的連結樣式（Design System Guard）。

#### 3.6 撤除流程（倫理）

1. 任何人都可以從 Person 頁的「削除・訂正の依頼」提出請求。P0 先用既有回報管道（mailto／表單，見 Q4），admin 收到後**先隱藏、再審查**：`status='hidden'`，目標是收到請求後 72 小時內處理（SLA 由創辦人決定）。
2. 本人確認要求刪除 → `status='removed'`、`do_not_recreate=true`、`removed_at`、`removal_reason`。清空 `bio_*`、`external_links`、`avatar_url`，保留 `name_original` 與 aliases 作為 tombstone，讓 resolver 不再建議建立；`event_people` 保留（RLS 已經不公開）。若本人要求連名字一起刪除 → 刪掉 people 列（cascade 會刪除連結），並在 `person_admin_meta` 之外另存不可逆的 normalized-name hash 作為 tombstone（Q4 決定是否需要）。
3. 活動本身（公開的主辦資訊）**不會**因此下架；只是不再連到 Person 頁。
4. 同名異人造成的誤連結 → 從活動頁的既有錯誤回報（`event_reports`）也能觸發，admin 在候選佇列把該連結改成 rejected。

#### 3.7 認領介面（R-SP-3，P1，只定義契約）

- P1 migration 新增 `person_claims(id, person_id, user_id, evidence_type CHECK in ('sns_code','official_email','manual'), evidence_value, status CHECK in ('pending','approved','rejected'), reviewed_by, reviewed_at, created_at)`，RLS：本人 INSERT 與 SELECT 自己的列，admin ALL。
- 驗證方式：在本人公開 SNS 的 bio 或貼文放 TTR 產生的一次性代碼，或用官方網域的 email。不接受只有截圖的證明。
- 核准後：`people.claim_status='claimed'`；`person_admin_meta.claimed_by_user_id`、`creator_id`（連到該帳號的 `creators` profile 列）、`consent_basis='claimed'`。認領者透過 **server action**（不是直接 table UPDATE）只能修改 `bio_*`、`external_links`、`avatar_url`、`name_*`；`slug`、`kind`、`status`、`taiwan_connection` 仍然由 admin 管理。
- 投稿流程（`organizer-submission-v2`）在投稿完成時呼叫 `findOrSuggestPersonForCreator(creatorId)`：只建立 candidate，不自動發布。

### 4. Follow

#### 4.1 Schema（migration B，預計 `098`）

```
user_follows(
  id uuid pk default gen_random_uuid(),
  user_id uuid NOT NULL fk→auth.users on delete cascade,
  target_type text NOT NULL CHECK (target_type IN ('topic','person')),
  topic_id  uuid fk→topics on delete cascade,
  person_id uuid fk→people on delete cascade,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT user_follows_target_check CHECK (
    (target_type='topic'  AND topic_id  IS NOT NULL AND person_id IS NULL) OR
    (target_type='person' AND person_id IS NOT NULL AND topic_id  IS NULL))
)
UNIQUE INDEX (user_id, topic_id)  WHERE topic_id  IS NOT NULL
UNIQUE INDEX (user_id, person_id) WHERE person_id IS NOT NULL
INDEX (topic_id) WHERE topic_id IS NOT NULL; INDEX (person_id) WHERE person_id IS NOT NULL
```

- 擴充點：未來加 `community_id`／`place_id` 欄位，並把 `target_type` 與 target CHECK 改成 DROP 後重新 ADD（和 095 的 CHECK 交換手法相同）。用具名 FK 欄位而不是 polymorphic `target_id`，是為了得到 cascade 刪除與參照完整性。
- RLS：`FOR ALL TO authenticated USING ((select auth.uid()) = user_id) WITH CHECK ((select auth.uid()) = user_id AND (person_id IS NULL OR EXISTS (SELECT 1 FROM public.people p WHERE p.id = person_id AND p.status='published')))`。
- GRANT：authenticated → SELECT, INSERT, DELETE；service_role → SELECT, INSERT, UPDATE, DELETE；**anon 不給**。
- 寫入：partial unique index 不能當 supabase-js `upsert` 的 `onConflict` 目標，所以用 `insert`，並把 `23505` 視為「已追蹤」。
- 隱私：追蹤者名單與人數不公開；admin 指標一律在 server 端用 service role 聚合。

#### 4.2 UI

- `FollowButton`（client component，模式和 `SaveButton.tsx:22-61` 相同：掛載時自行讀取狀態、未登入時導向 `/auth/login?next=`），放在 Topic 頁；P1 再放到 Person 頁。使用既有 design system 的按鈕元件，不另做原生樣式。
- `/saved` 頁：保留 `saved_events` 不動，在頁首新增「フォロー中のトピック」chips，以及「フォロー中トピックの近日イベント」列表（最多 N 筆，套用 `publicEventFilter()`）。URL 維持 `/saved`（已有連結與 OG 圖）。`account/page.tsx` 可以加上追蹤數，但非必要。

### 5. 共用查詢與跨 spec 介面（只定義契約）

新增 `web/lib/eventVisibility.ts` 的 `publicEventFilter(query)`：套用 `is_active=true`、`annotation_status IN ('annotated','reviewed')`、`parent_event_id IS NULL`（列表類用途）＋**relevance gate hook**（目前是 no-op）。Topic 頁、`/saved` 追蹤區塊、homepage helpers 全部經過這裡，讓 relevance spec 只需要改一處。

#### 5.1 → `taiwan-relevance-scoring`（R-QA-1「主辦者是否台灣相關」訊號）

- 本 spec 提供 view `public.event_person_signals`（`WITH (security_invoker = true)`，只 GRANT 給 service_role；relevance 計算在 scraper 端用 service role 執行）：

  | 欄位 | 意義 |
  |---|---|
  | `event_id` | |
  | `linked_host_count` | role ∈ (hosted_by, co_hosted_by) 的已確認連結數 |
  | `taiwan_connected_host_count` | 上述連結中，`taiwan_connection` 非空**且** `taiwan_connection_confirmed_at IS NOT NULL` 的數量 |
  | `taiwan_connected_participant_count` | performer／speaker 等其他角色中，符合同一條件的數量 |
  | `taiwan_connection_kinds` | 出現過的 `taiwan_connection` 值（去重後的陣列） |

  只計入 `people.status IN ('draft','published')`；`hidden`／`removed` 不計（尊重撤除）。
- 機構類主辦者（不建 Person 的那些）由 relevance spec 直接讀 `organizers`／`events.organizer_type`，本 spec 不在 `organizers` 加台灣欄位（Q5）。
- relevance spec 回饋：relevance spec 決定 gate 欄位名稱（例如 `events.relevance_tier`），並在 `publicEventFilter()` 實作 gate。本 spec 不預設欄位名稱。

#### 5.2 → `intent-homepage`（次領域チャンネル區塊、「いま日本で活動する台湾の人」區塊）

`web/lib/topics.ts`／`web/lib/people.ts` 提供 server-only helpers（anon client，RLS 公開讀取）：

```ts
getTopicChannels(locale): Promise<{ slug; name; upcomingCount /* 未來 30 天 */ }[]>          // is_channel=true, status=active, 依 sort_order
getTopicUpcomingEvents(slug, opts: { limit; from?; to?; prefecture?: string[] }): Promise<Event[]>
getFeaturedPeople(opts: { limit; topicSlug?; withinDays?: number /* 預設 30 */ }): Promise<{
  slug; displayName; kind; topicSlugs: string[];
  nextEvent: { id; name; startDate; prefecture: string | null } | null }[]>              // 只回傳有近期活動的 published people
getFollowedTopicSlugs(userId): Promise<string[]>                                              // 「あなたの今週の台湾」個人化用
```

人工挑選的「あなたの今週の台湾」與首頁版面由 homepage spec 負責；本 spec 只保證上面這些 helper 的回傳形狀穩定。

#### 5.3 → `line-segmented-digest`（R-FL-3）

- 本 spec 提供：`topics`／`topic_categories`（頻道 → Category 映射，對應 `line_subscribers.category_preferences` 的值域）、`user_follows`（web 使用者的 Topic 追蹤）、`getTopicCategories(slugs): Promise<Category[]>`。
- LINE spec 負責：`line_user_id` 和 auth `user_id` 的連結（例如在 `line_subscribers` 加 `user_id`）、通知開關與頻率、R-FL-3 先開的 4 個頻道（電影、音樂、語言交流、學術講座）和本 spec slug 的對應（`film`／`music`／`language`／`academic`）。
- 本 spec **不**在 `user_follows` 加通知偏好欄位，避免兩份 spec 擁有同一欄位。

### 6. Admin（最小需求）

| 頁面 | 功能 | 備註 |
|---|---|---|
| `/[locale]/admin/people` | 列表、搜尋（名稱與別名）、篩選 status／kind／index_policy；新增與編輯（名稱、kind、links、topics、aliases、organizer_id 橋接、taiwan_connection＋evidence＋確認、status 轉換、撤除） | 參考 `admin/works` 的列表加 `[id]` 編輯結構；寫入走 `/api/admin/people/*` route handler（server 端用 service role 加 `is_admin()` 檢查） |
| `/[locale]/admin/people/candidates` | 依 `raw_name_normalized` 分組並顯示活動數；每組可以「連結到既有 person／改連其他人／建立新 draft／拒絕」，支援批次接受 | 依活動數排序，誤連結影響最大的先審 |
| `/[locale]/admin/topics` | 唯讀：topic 列表、映射的 categories、每個 topic 近 30 天活動數；不在 `CATEGORIES` 中的 category 標紅 | 映射修改在 P0 走 SQL／migration，降低範圍 |
| 既有 AdminEventTable | 不改（P0）。活動層級的 person 連結在 people 編輯頁與候選佇列處理 | 避免 Admin Table Column Width 與 globalIndexMap 類問題 |

所有新 UI 字串加到 `web/messages/{ja,zh,en}.json` 的 `admin.people.*`、`admin.topics.*`。

### 7. i18n namespaces（三語同步新增）

`topic.*`（頁面標題、說明、近期活動、相關人物、空狀態）、`person.*`（kind 標籤、下一場、過去活動、外部連結、このページについて、削除依頼、認領〔P1〕）、`follow.*`（follow／following／未登入提示）、`saved.following*`、`admin.people.*`、`admin.topics.*`。不得刪除既有 key（i18n Regression Guard）。

### 8. 指標（§10 關係、§11 H2）

| 指標 | 資料來源 | 本 spec 提供 |
|---|---|---|
| 每位使用者平均 follow 的 Topic／Person 數 | `user_follows` | admin stats 卡片（service role 聚合） |
| Topic／Person follow 總數與每週新增 | `user_follows.created_at` | 同上 |
| 活動頁 → Person 頁的點擊比例 | 新的聚合表 `entity_views(target_type, target_id, day, locale, referrer_kind, count)`，不存 user_id | P0 只記錄 Person／Topic 頁的瀏覽與 referrer 種類（event／topic／home／external） |
| H2：follow 後 4 週回訪率 | 需要使用者層級的活動紀錄 | **Q6**：預設建議加 `user_active_days(user_id, day)`（admin-only、180 天後刪除），在已登入使用者載入頁面時 upsert；若創辦人不同意，就以「follow 者再次 follow 或開啟 `/saved` 的比例」作為代理指標 |

### 9. 影響檔案（預計）

- 新增：`supabase/migrations/097_person_topic_entities.sql`、`098_user_follows.sql`（序號實作時重新確認）、P1：`0xx_person_claims.sql`
- 新增：`scraper/link_people.py`、`scraper/_oneoff_seed_people.py`、`scraper/tests/test_link_people.py`
- 修改：`scraper/merger.py`（停用 secondary 時改指 `event_people`；只動合併後處理，不動 `_normalize`／threshold）、手動合併工具（若有）
- 新增：`web/lib/eventVisibility.ts`、`web/lib/topics.ts`、`web/lib/people.ts`、`web/components/FollowButton.tsx`、`web/components/PersonLinks.tsx`
- 新增：`web/app/[locale]/topics/[slug]/page.tsx`（＋`opengraph-image.tsx`、`loading.tsx`）、`web/app/[locale]/people/[slug]/page.tsx`（＋`opengraph-image.tsx`：只用文字，不放肖像）
- 新增：`web/app/[locale]/admin/people/page.tsx`、`admin/people/[id]/page.tsx`、`admin/people/candidates/page.tsx`、`admin/topics/page.tsx`、`web/app/api/admin/people/**/route.ts`
- 修改：`web/lib/types.ts`（`Topic`、`Person`、`PersonKind`、`EventPersonRole` 型別；**不動** `Category` union）、`web/lib/publicationStructuredData.ts`（:138-157 的 `@id`／`url`）、`web/app/[locale]/events/[id]/page.tsx`（:1065-1125 加連結）、`web/app/[locale]/saved/page.tsx`、`web/app/sitemap.ts`、`web/app/[locale]/admin/page.tsx`（導覽入口）、`web/messages/{ja,zh,en}.json`
- 文件：`.github/instructions/database.instructions.md`（latest／next、Other tables、RLS）、`docs/ARCHITECTURE.md`（新 API endpoint）、`.github/agents/architect.agent.md` 新 Guard「Person Entity vs Organizer Registry vs Creators Guard」、`.github/skills/agents/engineer/SKILL.md`（person 連結慣例）

### 10. 風險與緩解

| # | 風險 | 嚴重度 | 緩解 |
|---|---|---|---|
| R1 | **未經同意建立個人頁**：讓一般人或小型創作者的名字被 TTR 索引，造成隱私、肖像或名譽問題 | 高 | §3.4 建立門檻（公開職業活動、≥ 2 筆、排除私人）、預設 draft＋人工發布、未認領個人預設 `noindex`、不放照片與 AI bio、§3.6 先隱藏再審查加 tombstone、每頁都有削除依頼連結 |
| R2 | **同名異人或錯誤連結**，把 A 的活動掛到 B 的頁面 | 高 | 唯一且經人工確認的 alias 才自動連結；歧義一律走佇列；SequenceMatcher 門檻不低於 0.85；stale 偵測；活動頁錯誤回報可撤銷連結 |
| R3 | **三套「人」結構並存**（organizers／creators／people），讓 Engineer 或後續 agent 寫錯表 | 中高 | §1 分層表；新 Architect Guard；`person_admin_meta` 用明確的 FK 橋接，不複製資料；Non-Goal 寫明不遷移 |
| R4 | `taiwan_connection` 被誤用成國籍標籤或公開顯示 | 中 | 放在 admin-only 表；值域只描述活動事實；需要證據與確認者；只透過 view 給 relevance 使用；JSON-LD 不輸出 |
| R5 | 音楽頻道混入演劇（Category 缺口） | 中 | Q1；暫用「音楽・舞台」標籤 |
| R6 | 個人專案精力（§4.2 Q7）：人工審核佇列堆積 | 中 | Phase 0 量化後才決定 backfill 規模；先上 Topic＋follow（不依賴 Person），Person 分批發布；候選依影響排序 |
| R7 | Topic 頁和 Category 頁內容重疊，造成 thin／duplicate content | 低中 | Topic 頁加上人物與說明作為差異化內容；活動數 < 3 的 topic 頁設 noindex |
| R8 | 10/30 GRANT 政策、RLS 子查詢效能 | 低 | 明寫 GRANT；policy 用 `(select …)`；`event_people(person_id)` index |
| R9 | relevance gate 尚未存在，Topic 頁可能出現雜訊 | 中 | `publicEventFilter()` 單點 hook；relevance spec 上線前，Topic 頁先排除 `geopolitics`、`report` 與純出版紀錄 |

### 11. 未決問題（需要創辦人決定）

- **Q1 音楽頻道**：(a) 新增 `music` Category（走 `add-category` skill，並重新標註 `performing_arts` 事件，有成本），或 (b) 長期用「音楽・舞台」。**建議**：P0 先用 (b) 上線，(a) 另開小變更，完成後只改 `topic_categories`。
- **Q2 未認領個人頁是否給搜尋引擎索引**：**建議**：band／group 索引；未認領的個人預設 `noindex`，認領或明確同意後才索引。
- **Q3 機構（文化中心、TECO、學會、大學研究室）要不要做 Person 頁**：**建議**：P0 只做 civic group、學會、獨立團體（kind=`group`）；政府與半官方機構不做頁面，只留在 registry。
- **Q4 撤除管道與 SLA**：P0 用 mailto／Google Form 還是新增 `person_takedown_requests` 表？SLA 72 小時是否可行？完全刪除時是否保留 normalized-name hash tombstone？
- **Q5 機構的台灣關聯**：relevance 是否需要在 `organizers` 加 `taiwan_connection`？**建議**：交給 relevance spec 決定，本 spec 不動 `organizers`。
- **Q6 H2 回訪量測**：是否同意新增 `user_active_days`（admin-only、180 天保留）？
- **Q7 §6.3「台湾人主催」標籤和 §6.11 的關係**：這個標籤若存在，是否只能由本人自行申報（claimant self-declared），而不是由 AI 或 admin 推定？本 spec 預設 Person 不承載這個標籤，由 `social-affordance-tags` spec 處理。

### 12. 複雜度與分 phase

整體：**L**（P0 新增 9 張表＋1 個 view、P0 指標表 1–2 張、2 個主要 migration、1 個 resolver、2 種新公開頁＋/saved 擴充＋3 個 admin 頁、跨 3 份 spec 的介面）。拆成可各自獨立上線的 phase：

| Phase | 內容 | 對應需求 | 複雜度 | 依賴 |
|---|---|---|---|---|
| 0 | Worktree、baseline 量化（唯讀 SQL）、創辦人回答 Q1–Q4 | — | S | — |
| A | Migration 097（topics＋people 系列）、098（user_follows）、TS 型別 | R-EN-2、R-EN-3 schema | M | Phase 0 |
| B | Topic 頁、FollowButton、`/saved` 追蹤區塊、`publicEventFilter()`、sitemap、admin/topics | **R-EN-3、R-FL-1（P0 可獨立上線）** | M | A |
| C | `link_people.py`、候選佇列、admin/people、種子 backfill、merger 改指 | R-EN-2 資料 | L | A |
| D | Person 頁、活動頁連結、JSON-LD、homepage helpers、`event_person_signals` view | R-EN-2 頁面＋§5 介面 | M | C |
| E | 指標（`entity_views`、admin stats）、文件與 Guards | §10、H2 | S | B、D |
| F（P1） | Person follow UI、`person_claims` 與認領流程、LINE 介面交接 | R-FL-2、R-SP-3、R-FL-3 | M | D |

**建議上線順序**：0 → A → B（先上 Topic follow，盡早開始 H2 的 4 週計時）→ C → D → E；F 等 P1。

## Worktree & Spec Tracking

1. **Spec**：`docs/specs/active/person-topic-entities/`（`proposal.md`＋`tasks.md`，由 `_template/` 建立）。slug＝`person-topic-entities`。
2. **Worktree**：`ttr-person-topic-entities-worktree`，branch `feat/person-topic-entities`。**NEW**：2026-10-06 執行 `git worktree list --porcelain` 只看到主工作樹（`/home/user/Tokyo_Taiwan_Radar`，branch `claude/elegant-einstein-ypujar`），`git branch -a` 也沒有 `feat/person-topic-entities`，所以適用 state matrix 的「branch missing」列。
3. **Phase 0**：Engineer 必須先讀 `.github/instructions/git.instructions.md` § Worktree confirmation gate 與 § Isolated worktree，**實作前先向使用者確認要使用這個新 worktree**（不得自行推定，主工作樹不是選項），依 state matrix 建立，並用 idempotent 方式把 `ttr-person-topic-entities-worktree/` 加進 `.git/info/exclude`。不得假設 worktree 已存在。
4. Session 計畫檔（Claude Code／Codex 對應 `/memories/session/plan.md`）必須寫上 slug `person-topic-entities`，讓恢復的 session 從 `tasks.md` 接續。
5. 本 spec 是本規則上線後新建的 spec，適用 spec ⟺ worktree 1:1。

## Acceptance criteria

- [ ] Migration A／B 套用後，`tasks.md` 的 Verification V1–V8 全部通過；anon 讀不到 `person_admin_meta`、`person_aliases`、`person_link_candidates`、`user_follows`；anon 讀不到 draft、hidden、removed 的 people。
- [ ] 8 個 topics 與映射已建立；`/ja|zh|en/topics/<slug>` 三語可瀏覽，JSON-LD 驗證通過，已列入 sitemap。
- [ ] 登入使用者可以 follow／unfollow Topic；`/saved` 顯示追蹤中的 topics 與近期活動；未登入時點 follow 會導向登入頁，登入後回到原頁。
- [ ] 至少 20 位 published people（含種子供給方）；每位都有 ≥ 1 筆已確認的 `event_people`；Person 頁三語可瀏覽；`noindex` 規則生效；JSON-LD `@type` 和 kind 對應正確，不含 nationality／image（未認領時）。
- [ ] 活動詳情頁中有連結的主辦者與演出者可以點到 Person 頁；沒有連結時維持原樣（負向 fixture）。
- [ ] resolver：唯一 exact alias → 自動連結；同名多人 → 進佇列（負向 fixture）；fuzzy < 0.85 → 不產生候選；LLM 只寫 `llm_entity_kind`。
- [ ] 撤除演練：把 1 位測試 person 設為 hidden → 頁面 404、活動頁連結消失、`event_person_signals` 不再計入。
- [ ] `intent-homepage` 與 `taiwan-relevance-scoring` 的介面（§5）已實作，並附 smoke test。
- [ ] `npm run build`、`npx tsc --noEmit`、lint 通過；scraper 測試通過；`web/messages/*.json` 無 key 被刪除。

## References

- 需求文件：`TTR strategy/2.0/TTR-2.0-pivot-requirements.md` —— §6.2（R-EN-2 Person／Organizer、R-EN-3 Topic；R-EN-4／R-EN-5 只預留擴充點）、§6.4（八個次領域頻道）、§6.5（R-FL-1 P0、R-FL-2 P1、R-FL-3 介面）、§6.6 R-SP-3（P1 介面）、§6.11（不做國籍與政治標籤）、§7、§10 關係指標、§11 **H2**；§11 決策 **D1–D5 已定案**（D1 選項 2：2.0 重做表層 B2C，中層與深層暫緩但保留；D2：核心族群是「台湾に少し踏み込みたい日本語話者」；D3：暫不擴大到台灣當地；D4：主標用原型測試決定；D5：2.0 期間不設變現目標）。
- 同類型實體擴張的先例：`docs/specs/active/works-entity-for-films-and-tours/`（沿用：獨立實體表＋FK、admin 維護、annotator 不寫實體表、新增 Guard；教訓：migration 序號會漂移，要在實作時重新確認）。
- 既有 entity registry 的來源 spec：`docs/specs/active/report-prototype-gap-fix/proposal.md`（organizers／venues，Tier 2）。
- 相關（尚未建立）spec：`taiwan-relevance-scoring`、`intent-homepage`、`organizer-submission-v2`、`social-affordance-tags`、`line-segmented-digest`、`community-directory`、`place-and-collections`（需求文件 §15）。
- Architect Guards：Works Entity vs `parent_event_id` Guard、Organizer Non-Hallucination Guard、Known Person Map Guard、Performer Multi-Value Field Pollution Guard、Merger `_normalize()` Guard、Manual Merge Completeness Guard、RLS Cross-Status Query Guard、SQL Privilege Syntax Guard、規模量化先於工具化、Design System Guard、i18n Regression Guard。
- 規則：`.github/instructions/database.instructions.md`（Explicit GRANT requirement、Migration checklist）、`.github/instructions/web.instructions.md`（SEO、i18n）、`.github/instructions/scraper.instructions.md`、`.github/instructions/git.instructions.md`（Worktree confirmation gate、Isolated worktree）。
