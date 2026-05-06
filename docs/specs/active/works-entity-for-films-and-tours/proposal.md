---
slug: works-entity-for-films-and-tours
title: Works 實體 — 同一作品跨場館/巡演的 1:N 關聯
status: done
branch: feat/works-entity
created: 2026-05-05
tags: [data-model, scraper, web, deduplication]
---

## What（做什麼）

新增 `works`（作品）表作為 `events` 的上層實體。一部電影、一齣舞台劇、一場巡演（同名多城市）都對應一筆 `work`，多場放映/演出則為多筆 `events.work_id` 指向同一 work。

詳情頁顯示「同作品的其他場次」區塊，列出該 work 旗下所有 active events（依 start_date 排序）。

## Why（為什麼）

### 觸發 incident（2026-05-05）

電影《月老 / 赤い糸 輪廻のひみつ》在 DB 內出現 2 筆 active 事件：

- `f970e4e3` shin_bungeiza（新文芸坐）2026/5/8~14
- `4a8772ec` cinemart_shinjuku（シネマート新宿）2026/5/28

兩筆 `name_ja` 100% 相同，merger Pass 1 相似度 = 1.000，**會被自動合併**——但實務上不該合併，因為是同一電影在**不同電影院**的**不同檔期**。臨時對策只能在 merger 加「電影類事件 venue 不同則跳過」規則，但這只是治標。

### 治本：作品實體

- 使用者在詳情頁應該能看到「這部電影還在哪裡上映」
- merger 不該再為「同名跨 venue」案例煩惱——它們是同一作品的不同場次，本就該各自獨立但互相連結
- 巡演（同一展覽/演唱會在多城市）天然適用同一模型
- 為未來「依作品查詢上映史」、「給作品評論/評分」等功能鋪路

## Non-Goals（不做什麼）

- **不做** 自動偵測 `work_id`——首版由 admin 手動建立 work 並指派 events
- **不取代** `parent_event_id`（後者用於 master ↔ sub-event 場次拆分，例：影展中的單場放映）。`work_id` 與 `parent_event_id` 互不影響，可同時存在
- **不做** 跨 work 的「系列」（例：『あの頃、君を追いかけた』與『月老』同導演）——留給 Phase F
- **不引入**外部資料庫 ID（IMDb / TMDB / Wikidata）——首版只用內部 work
- **不做** work 的多語譯名自動同步——work 的 name 欄位獨立，避免被個別 event 翻譯覆寫

## Design（設計摘要）

### 資料模型

```sql
CREATE TABLE works (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  work_type       TEXT NOT NULL,          -- 'film' | 'stage' | 'exhibition' | 'concert_tour' | 'other'
  original_title  TEXT NOT NULL,          -- 原文片名 (e.g. '月老')
  title_ja        TEXT,                   -- 日譯
  title_zh        TEXT,                   -- 中譯
  title_en        TEXT,                   -- 英譯
  director        TEXT,                   -- 導演 / 主創
  cast_summary    TEXT,                   -- 主演摘要
  release_year    INT,                    -- 原作年份
  country         TEXT DEFAULT 'TW',      -- 創作國
  description     TEXT,                   -- 作品簡介（與 event description 區分）
  poster_url      TEXT,
  external_links  JSONB,                  -- {imdb, wikidata, official_site, ...}
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE events ADD COLUMN work_id UUID REFERENCES works(id) ON DELETE SET NULL;
CREATE INDEX idx_events_work_id ON events(work_id) WHERE work_id IS NOT NULL;
```

### Merger 行為調整

- Pass 1（name similarity ≥ 0.85）新增條件：若兩 candidate 都有 `work_id` 且不同 → 跳過合併（明確不同作品）
- 若 candidate 來自 `category in ('movie', 'performing_arts')` 且 `location_name` 不同 → 不自動合併，改寫入 `merger_candidates`（Phase E）併附建議 `same_work_different_venue` 標籤
- Admin review UI 在 approve 時可選擇「指派為同 work」而非「合併為 secondary」

### Web 變更

- 詳情頁 `web/app/[locale]/events/[id]/page.tsx` 增加「同作品其他場次」區塊
- 新 admin 頁 `web/app/[locale]/admin/works/page.tsx`：列表 / 建立 / 編輯 work
- AdminEventTable 增加「指派 work」action

### 影響檔案

- `supabase/migrations/046_works_entity.sql`（新）
- `scraper/merger.py` Pass 1 條件擴充
- `web/app/[locale]/events/[id]/page.tsx`（詳情頁同作品區塊）
- `web/app/[locale]/admin/works/page.tsx`（新）
- `web/app/[locale]/admin/works/[id]/page.tsx`（新）
- `web/components/AdminEventTable.tsx`（指派 work action）
- `web/lib/types.ts`（Work type）
- `web/messages/{zh,en,ja}.json`（i18n）
- `.github/agents/architect.agent.md`（新 Guard：work_id 不取代 parent_event_id）
- `.github/skills/agents/engineer/SKILL.md`（works 慣例）

### 風險與緩解

| 風險 | 緩解 |
|---|---|
| Admin 忘記指派 work_id，影響詳情頁「同作品場次」區塊體驗 | 在 events 列表為缺 work_id 的 movie/stage 事件加紅色標籤；月度 health check 統計缺指派率 |
| GPT 翻譯把 work-level title 與 event-level title 混淆 | annotator 不可寫 works 表；works 內容只由 admin 維護 |
| 未來需求要「以 work 為單位通知訂閱者」 | 預留 `work_subscriptions` 表，本 spec 不實作 |

### Acceptance criteria

- [ ] `works` 表建立，月老/赤い糸 work 已建立，f970e4e3 與 4a8772ec 都已指派 work_id
- [ ] 詳情頁顯示「同作品其他場次」區塊，列出另一場次的卡片連結
- [ ] AdminEventTable 顯示 work_id 欄位 + 指派 action
- [ ] merger Pass 1 對「同名 movie + 不同 venue」不自動合併，改寫入 merger_candidates
- [ ] i18n 三語言皆有 `work.relatedScreenings` 等 keys
- [ ] `npm run build` pass

## References

- 觸發 incident：2026-05-05 月老（f970e4e3 / 4a8772ec）跨電影院場次處理討論
- 相關 spec：[merger-multi-signal-pass4](../merger-multi-signal-pass4/proposal.md)（Phase E 候選對 review UI 將承接 same_work_different_venue 案例）
- 相關 Architect Guard：`Merger _normalize() Guard`（合併規則總則）
