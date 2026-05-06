---
slug: report-prototype-gap-fix
title: 商業報告 Prototype 資料缺口修補（Entity 表 + Backfill + 媒體聚合 view）
status: active
branch: feat/report-prototype-gap-fix
created: 2026-05-06
tags: [data, report, business, tier2, backfill]
---

## What（做什麼）

為產出第一份可賣的 **Product A 月度趨勢報告 v0.1** 補齊三類資料缺口：
1. **填充率拉滿** — `location_prefectures` 從 37.4% → ≥85%（重跑 backfill），其他 Tier 1 欄位確認穩定。
2. **Tier 2 entity 表** — 新增 `organizers` / `venues` 兩張正規化表，解決同一主辦方/場地的多種寫法（例：`日本台湾交流協会` ≡ `日台交流協会` ≡ `Japan-Taiwan Exchange Association`）。
3. **媒體聚合 view** — 從 `secondary_source_urls` 派生 `event_media_coverage` view，提供「該活動被 N 家媒體報導」的單一查詢端點。

完成後即可生成「主辦方 Top 10」「場地 Top 10」「媒體曝光 Top 10」三個報告區塊。

## Why（為什麼）

當前實際填充率盤點（2026-05-06，286 件 active+annotated 事件）：

| 欄位 | 實際 | 目標 | 缺口影響 |
|------|------|------|---------|
| `location_prefectures` | **37.4%** | ≥85% | 城市 × 類別 cross-tab 做不出來，roadmap 顯示 68.2% 是過時數字 |
| `organizer`（純文字） | 88.1% | — | 文字相同但寫法不同 → 無法聚合「主辦方排行榜」 |
| `location_name`（純文字） | 100% | — | 同上，「場地 ROI 排行」無法生成 |
| 媒體 mention 聚合 | 散在 `secondary_source_urls` | view 化 | 「最受媒體關注 Top 10」需手寫 SQL，不可重複利用 |

**為什麼現在做**：
- Product A v0.1 需要這三個區塊作為核心賣點；缺一個就少一條 selling point。
- `location_prefectures` 低填充率是 [Product C 機會雷達](../product-c-opportunity-radar/proposal.md) 的城市維度阻斷點。
- Entity 表是 [Tier 1+1.5 資料完成](../tier1-data-completion/proposal.md) 的延續，但範圍收斂到「報告 prototype 必需」而非完整 Tier 2。

## Non-Goals（不做什麼）

- ❌ **不做** performer entity 表（演出者去重）— 留待 `performer-entity` 獨立 spec。
- ❌ **不做** capacity / venue size 欄位 — 只有 10/286 raw_desc 含關鍵字，覆蓋率太低不值得做。
- ❌ **不做** 票價分析欄位擴充（`price_amount` 26.2% 太低，留待 v0.2）。
- ❌ **不做** YoY 趨勢圖 — 歷史資料不足（2025 僅 15 件、2024 僅 4 件），v0.2 報告才考慮。
- ❌ **不做** GA4 / Search Console 整合（另開 `report-analytics-integration` spec）。
- ❌ **不做** 報告 PDF 渲染管線（另開 `report-rendering-pipeline` spec）。

## Design（設計摘要）

### Phase 1: location_prefectures backfill（1 天）

**Root cause**: `location_prefectures` 欄位於 migration 後對舊資料漏處理。`backfill_location_prefectures.py` 已存在但未對全表跑過。

**動作**：
1. 在 `scraper/backfill_location_prefectures.py` 確認 query filter：`location_address.not.is.null AND location_prefectures.is.null`（不限 active）。
2. Dry-run 驗算預期觸動筆數（預期 ~150 筆）。
3. 全量執行；驗證填充率提升至 ≥85%。
4. 更新 `/admin/roadmap` 頁面的靜態數字 → 改為從 DB 動態查詢（避免再過時）。

**驗證**：執行後查詢 `SELECT COUNT(*) FROM events WHERE is_active AND annotation_status IN ('annotated','reviewed') AND location_prefectures IS NOT NULL` 應 ≥ 243（286 × 85%）。

### Phase 2: Migration 041 — `organizers` + `venues` entity 表

```sql
-- supabase/migrations/041_entity_tables.sql

CREATE TABLE organizers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_name_ja TEXT NOT NULL UNIQUE,
  canonical_name_zh TEXT,
  canonical_name_en TEXT,
  organizer_type TEXT,  -- mirrors events.organizer_type enum
  aliases TEXT[] DEFAULT '{}',  -- 同一主辦方的所有寫法
  homepage TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE venues (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_name_ja TEXT NOT NULL UNIQUE,
  canonical_name_zh TEXT,
  canonical_name_en TEXT,
  address TEXT,
  prefecture TEXT,
  city TEXT,
  latitude DECIMAL(9,6),
  longitude DECIMAL(9,6),
  aliases TEXT[] DEFAULT '{}',
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE events
  ADD COLUMN organizer_id UUID REFERENCES organizers(id) ON DELETE SET NULL,
  ADD COLUMN venue_id UUID REFERENCES venues(id) ON DELETE SET NULL;

CREATE INDEX idx_events_organizer_id ON events(organizer_id);
CREATE INDEX idx_events_venue_id ON events(venue_id);

-- RLS: 只有 admin 可寫，公開可讀
ALTER TABLE organizers ENABLE ROW LEVEL SECURITY;
ALTER TABLE venues ENABLE ROW LEVEL SECURITY;
CREATE POLICY organizers_read ON organizers FOR SELECT USING (true);
CREATE POLICY venues_read ON venues FOR SELECT USING (true);
-- write policies 透過 service_role bypass
```

**Backfill 策略**（`scraper/backfill_entities.py`，新建）：
1. 從 events 抽出所有 `organizer` 字串，按精準字串去重 → 建立第一輪 organizers 列。
2. 用 `_normalize()` 同款規則（merger.py 已有）做模糊聚類，相似度 ≥ 0.92 合併為 alias。
3. 人工審核 cluster（產出 `_oneoff_review_organizer_clusters.py` 列出疑似合併候選 → admin/roadmap 顯示）。
4. 對 events 寫回 `organizer_id`（保留原 `organizer` 字串作 audit trail）。
5. 同樣流程處理 venues（用 `location_name` + `location_address` 雙鍵）。

**保留原始欄位**：`events.organizer` / `events.location_name` 不刪除——entity 表是補強，不是取代。報告層用 `organizer_id` 聚合，但事件詳情頁仍顯示原始字串。

### Phase 3: 媒體聚合 view

```sql
-- supabase/migrations/042_event_media_coverage_view.sql

CREATE OR REPLACE VIEW event_media_coverage AS
SELECT
  e.id AS event_id,
  e.name_ja,
  e.start_date,
  e.location_prefectures,
  COUNT(DISTINCT s.source_name) AS media_count,
  ARRAY_AGG(DISTINCT s.source_name ORDER BY s.source_name) AS media_sources,
  MIN(s.first_seen) AS first_media_mention,
  MAX(s.first_seen) AS latest_media_mention
FROM events e
LEFT JOIN secondary_source_urls s ON s.event_id = e.id
WHERE e.is_active = true
  AND e.annotation_status IN ('annotated', 'reviewed')
GROUP BY e.id;

GRANT SELECT ON event_media_coverage TO anon, authenticated;
```

**用途**：
- Product A 報告「媒體曝光 Top 10」：`SELECT * FROM event_media_coverage ORDER BY media_count DESC LIMIT 10`
- `/admin/roadmap` 新增「媒體覆蓋率」section（多少活動被 ≥2 家媒體報導）

### Phase 4: 報告生成器骨架（最小可動）

新建 `scraper/report_generator.py`：
- 輸入：`year_month`（例 `2026-05`）、`output_format`（先支援 markdown，PDF 留 v0.2）。
- 輸出：`reports/<year_month>_taiwan_japan_events.md`，包含 5 個區塊：
  1. 月度總覽（活動數、新增 source 數、有效活動數）
  2. 類別分布（用 `category` array unnest）
  3. 都道府縣分布（用 `location_prefectures` array unnest）
  4. 主辦方 Top 10（用 `organizer_id` 聚合）
  5. 媒體曝光 Top 10（用 `event_media_coverage` view）
- 不支援：YoY 對比、票價分析、規模分析（資料不足）

**驗證**：手動跑 2026-04 月報告，輸出 markdown，人工檢查無欄位錯亂、無 GPT 幻覺。

## 影響到哪些檔案

| 路徑 | 動作 |
|------|------|
| `supabase/migrations/041_entity_tables.sql` | 新建 |
| `supabase/migrations/042_event_media_coverage_view.sql` | 新建 |
| `scraper/backfill_location_prefectures.py` | 全量重跑 |
| `scraper/backfill_entities.py` | 新建 |
| `scraper/_oneoff_review_organizer_clusters.py` | 新建（一次性審核工具） |
| `scraper/report_generator.py` | 新建 |
| `web/app/[locale]/admin/roadmap/page.tsx` | 改為動態查詢填充率（不再 hardcode） |
| `scraper/database.py` | upsert 時自動 lookup organizer_id / venue_id（如已存在 alias） |

## Verification

依序執行：
```bash
# Phase 1
cd scraper && python backfill_location_prefectures.py --dry-run
python backfill_location_prefectures.py
# Expect: location_prefectures 填充率 ≥ 85%

# Phase 2
# Run migration 041 in Supabase Dashboard SQL Editor
python backfill_entities.py --type organizers --dry-run
python _oneoff_review_organizer_clusters.py  # 人工審核 cluster
python backfill_entities.py --type organizers
python backfill_entities.py --type venues

# Phase 3
# Run migration 042 in Supabase Dashboard SQL Editor
psql -c "SELECT COUNT(*) FROM event_media_coverage WHERE media_count >= 2"

# Phase 4
python report_generator.py --month 2026-04 --format markdown
# 開啟 reports/2026-04_taiwan_japan_events.md 人工 review
```

## Architect Guards 連動

需新增至 `.github/skills/agents/architect/SKILL.md`：
- **Entity Table FK Sync Guard**：審核 events 寫入時，必須同步維護 `organizer_id` / `venue_id`（透過 `database.py` upsert 邏輯，不可只更新文字欄位）。
- **Roadmap Static Data Guard**：禁止在 `/admin/roadmap` hardcode 填充率數字——必須從 DB 即時查詢，避免「資料變了但頁面沒變」。

## References

- [tier1-data-completion](../tier1-data-completion/proposal.md) — 上游 spec，本 spec 是其報告層延伸
- [product-c-opportunity-radar](../product-c-opportunity-radar/proposal.md) — 下游 spec，依賴 location_prefectures ≥85%
- [market-positioning-strategy](../market-positioning-strategy/proposal.md) — 商業定位北極星
- 2026-05-06 數據盤點對話（Architect agent）
