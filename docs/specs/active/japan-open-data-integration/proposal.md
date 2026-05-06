---
slug: japan-open-data-integration
title: 日本政府公開資料整合路線圖（e-Stat / JNTO / 法務省 在留統計）
status: active
branch: feat/japan-open-data-integration
created: 2026-05-06
tags: [data, external, government, business, report]
---

## What（做什麼）

建立一條從日本政府公開資料來源拉取統計數據、寫入獨立 reference 表、供報告生成器交叉引用的 pipeline。第一波鎖定三個來源：
1. **e-Stat（政府統計総合窓口）** — 訪日客數 / 都道府縣別人口 / 文化消費支出（API + appId）
2. **JNTO 訪日外客統計** — 台灣訪日客月別、目的別、地域別（CSV 月更）
3. **法務省 出入国在留管理庁** — 在留台灣人縣別人口（PDF + 月更）

完成後 Product A 月度報告即可放入「對標數據」區塊，例：「東京活動量 vs 在留台灣人口」「台灣訪日客 vs 月度活動數相關性」。

## Why（為什麼）

**目前報告無對照組** — 我們只有「自己的爬蟲資料」，無法回答：
- 「東京 75 件活動相對於在留台灣人口 X 萬，是多還是少？」
- 「2026 年台灣訪日客數成長 Y%，活動量是否同步成長？」
- 「大阪只有 5 件活動，是因為在留人口少還是市場未開發？」

**為什麼現在做**：
- Product A v0.1 已有「主辦方 / 場地 / 媒體」內部 Top 10；下一步要的就是「對外比較基準」。
- 日本政府資料 95% 為 CC-BY 4.0 / 公共データ利用規約 → **商業使用無虞**，付費報告可放心引用。
- 現在不做，未來要回頭重建歷史月份對標數據成本更高。

**為什麼是這三個來源（不是更多）**：
- 三個來源覆蓋「人口（存量）」「客流（流量）」「消費（質量）」三維度，已能支撐 v0.1 報告。
- 都有穩定 API/CSV，不需手動爬 PDF → 一週可完成。
- 都道府縣 / 都府県級資料剛好對齊現有 `location_prefectures` 維度。

## Non-Goals（不做什麼）

- ❌ **不做** 都道府縣級開放資料 portal 接入（東京/大阪/福岡 各自獨立 API，留待第二波 spec）。
- ❌ **不做** 文化庁補助金資料（PDF 解析複雜，留待第三波）。
- ❌ **不做** JETRO 貿易統計（B2B 商業活動報告才需要，v0.1 不必）。
- ❌ **不做** 即時 dashboard（先做月度 batch pull，即時化留待 Product C）。
- ❌ **不做** 國際交流基金 / JICA 事業實績（資料更新頻率低，手動年更即可）。
- ❌ **不做** 自動報告生成（本 spec 只負責資料入庫，報告渲染由 `report-prototype-gap-fix` 處理）。

## Design（設計摘要）

### Phase 1: Schema — `external_stats` 系列表

```sql
-- supabase/migrations/043_external_stats.sql

CREATE TABLE external_stats_taiwan_visitors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  year_month TEXT NOT NULL,  -- 'YYYY-MM'
  source TEXT NOT NULL,  -- 'jnto' | 'estat'
  total_visitors INTEGER,  -- 該月台灣訪日客總數
  purpose_leisure INTEGER,
  purpose_business INTEGER,
  prefecture_breakdown JSONB,  -- {"tokyo": 12345, "osaka": ...}
  raw_data JSONB,  -- 原始回應，避免日後欄位增補要重抓
  fetched_at TIMESTAMPTZ DEFAULT NOW(),
  source_url TEXT,
  license_code TEXT NOT NULL,  -- 'CC-BY-4.0' | 'jp-gov-pdl-1.0'
  UNIQUE(year_month, source)
);

CREATE TABLE external_stats_resident_taiwanese (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  year_month TEXT NOT NULL,
  source TEXT NOT NULL,  -- 'moj-isa'（出入国在留管理庁）
  total_residents INTEGER,
  prefecture_breakdown JSONB,  -- {"東京都": 12345, ...}
  visa_breakdown JSONB,  -- {"留学": ..., "技術人文知識": ...}
  raw_data JSONB,
  fetched_at TIMESTAMPTZ DEFAULT NOW(),
  source_url TEXT,
  license_code TEXT NOT NULL,
  UNIQUE(year_month, source)
);

CREATE TABLE external_stats_population (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  year INTEGER NOT NULL,  -- 年更，無 month
  source TEXT NOT NULL,  -- 'estat'
  prefecture TEXT NOT NULL,  -- '東京都' / '大阪府' ...
  total_population INTEGER,
  raw_data JSONB,
  fetched_at TIMESTAMPTZ DEFAULT NOW(),
  source_url TEXT,
  license_code TEXT NOT NULL,
  UNIQUE(year, source, prefecture)
);

-- 公開讀（報告用），管理寫入透過 service_role
ALTER TABLE external_stats_taiwan_visitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE external_stats_resident_taiwanese ENABLE ROW LEVEL SECURITY;
ALTER TABLE external_stats_population ENABLE ROW LEVEL SECURITY;
CREATE POLICY allow_read_visitors ON external_stats_taiwan_visitors FOR SELECT USING (true);
CREATE POLICY allow_read_residents ON external_stats_resident_taiwanese FOR SELECT USING (true);
CREATE POLICY allow_read_population ON external_stats_population FOR SELECT USING (true);
```

**設計重點**：
- **獨立 schema 命名空間**（`external_stats_*`）— 不污染 events 表 RLS。
- **license_code 必填** — 付費報告法務查得到。
- **raw_data JSONB** — 保留原始回應，避免欄位增補時要重新拉取。
- **UNIQUE constraint** — `(year_month, source)` 保證重跑 idempotent。

### Phase 2: Pull pipelines

新建 `scraper/external_stats/` 目錄：

```
scraper/external_stats/
  __init__.py
  base.py                 # ExternalStatsBase ABC（fetch / parse / upsert）
  jnto_visitors.py        # JNTO 月別 CSV
  estat_population.py     # e-Stat 都道府縣別人口（年更）
  moj_residents.py        # 法務省在留外国人 PDF
  pull_all.py             # orchestrator
```

**JNTO pipeline 範例**：
- URL pattern: `https://www.jnto.go.jp/statistics/data/visitor_trends/<year>/<month>.csv`（待實際確認）
- License: 公共データ利用規約 1.0（`jp-gov-pdl-1.0`）
- Cadence: 月更，每月 20 號左右公布前月數據

**e-Stat pipeline**：
- 需註冊 [appId](https://www.e-stat.go.jp/api/api-info/api-guide)（免費，個人帳號即可）。
- Token 存 `scraper/.env` → `ESTAT_APP_ID`。
- 寫入 `.github/instructions/token-rotation.instructions.md` 的 secret 清單。
- License: CC-BY 4.0。

**法務省 PDF pipeline**：
- URL: `https://www.moj.go.jp/isa/policies/statistics/toukei_ichiran_touroku.html`
- 解析方式：用 `pdfplumber` 抽特定表格（在留資格別 × 国籍別）
- License: 公共データ利用規約 1.0

### Phase 3: CI 排程

新建 `.github/workflows/external-stats-pull.yml`：
```yaml
schedule:
  - cron: '0 22 25 * *'  # 每月 25 日 22:00 UTC（隔月初開始有資料）
```
- 跑 `python scraper/external_stats/pull_all.py`
- 失敗時 LINE 通知（重用 `notify.py`）
- 成功時寫入 `scraper_runs`（source_name='external_stats'）

### Phase 4: 報告生成器整合

修改 `scraper/report_generator.py`（從 [report-prototype-gap-fix](../report-prototype-gap-fix/proposal.md) 來）：
- 新增 section 「對標數據」：
  - 該月台灣訪日客總數（from `external_stats_taiwan_visitors`）
  - 在留台灣人主要分布縣（from `external_stats_resident_taiwanese`）
  - 「東京活動數 / 東京在留台灣人」密度指標
- 每張圖表標註 `Data source: JNTO（CC-BY 4.0）` / `Data source: 法務省（公共データ利用規約）`

## 影響到哪些檔案

| 路徑 | 動作 |
|------|------|
| `supabase/migrations/043_external_stats.sql` | 新建 |
| `scraper/external_stats/base.py` | 新建（ABC） |
| `scraper/external_stats/jnto_visitors.py` | 新建 |
| `scraper/external_stats/estat_population.py` | 新建 |
| `scraper/external_stats/moj_residents.py` | 新建 |
| `scraper/external_stats/pull_all.py` | 新建 |
| `scraper/requirements.txt` | 新增 `pdfplumber>=0.11` |
| `scraper/.env` | 新增 `ESTAT_APP_ID` |
| `.github/workflows/external-stats-pull.yml` | 新建 |
| `.github/instructions/token-rotation.instructions.md` | 新增 ESTAT_APP_ID 至 secret 清單 |
| `scraper/report_generator.py` | 新增「對標數據」section |
| `docs/ARCHITECTURE.md` | 新增 external_stats 區塊說明 |

## Verification

```bash
# Phase 1
# Run migration 043 in Supabase Dashboard SQL Editor

# Phase 2 — JNTO（最簡單，先做）
cd scraper
python -m external_stats.jnto_visitors --year-month 2026-04 --dry-run
python -m external_stats.jnto_visitors --year-month 2026-04
psql -c "SELECT COUNT(*) FROM external_stats_taiwan_visitors WHERE year_month='2026-04'"
# Expect: 1 (one row per source per month)

# Phase 2 — e-Stat（需 appId）
python -m external_stats.estat_population --year 2025 --dry-run

# Phase 2 — 法務省 PDF
python -m external_stats.moj_residents --year-month 2025-12 --dry-run

# Phase 3
# CI workflow 觸發後檢查 GitHub Actions log

# Phase 4
python report_generator.py --month 2026-04 --format markdown
# 確認 markdown 含「對標數據」section + license 標註
```

## Architect Guards 連動

需新增至 `.github/skills/agents/architect/SKILL.md`：

### External Stats License Metadata Guard

審核**任何** external stats pull pipeline 或報告引用外部資料的 PR 前，**必須**確認：

1. **license_code 必填**：所有寫入 `external_stats_*` 表的資料列必須有 `license_code`，禁止 NULL。
2. **公開來源白名單**：第一波只接受三個來源（`jnto` / `estat` / `moj-isa`）。新增來源前先確認商業使用無虞，更新本 Guard 白名單。
3. **付費報告引用必標註**：報告 generator 的「對標數據」section 每張圖表必須標 `Data source: <name>（<license>）`，違者 PR 拒收。
4. **raw_data 不可省略**：節省空間移除 `raw_data` JSONB 是反 pattern——欄位增補時無法回填歷史。

Reference incident: 2026-05-06 — Architect 規劃 spec 時要求保留 raw_data 與 license metadata 作為付費報告法務基底。

## 來源優先級評估（為何選這三個）

| 來源 | 報告價值 | 取得難度 | License | 第一波 |
|------|---------|---------|---------|--------|
| JNTO 訪日外客統計 | ⭐⭐⭐ | 低（CSV） | jp-gov-pdl-1.0 | ✅ |
| e-Stat 人口統計 | ⭐⭐⭐ | 中（API + appId） | CC-BY-4.0 | ✅ |
| 法務省在留統計 | ⭐⭐⭐ | 中（PDF 解析） | jp-gov-pdl-1.0 | ✅ |
| 観光庁観光経済 | ⭐⭐ | 高（PDF + Excel 混合） | jp-gov-pdl-1.0 | 第二波 |
| 文化庁補助金 | ⭐⭐ | 高（PDF 表格） | jp-gov-pdl-1.0 | 第三波 |
| JETRO 貿易投資 | ⭐⭐ | 中 | jp-gov-pdl-1.0 | Product B 才需 |
| 都道府縣 open data | ⭐ | 高（每縣 API 不同） | 各府県獨立 | 第二波 |

## References

- [report-prototype-gap-fix](../report-prototype-gap-fix/proposal.md) — 下游 spec，整合進報告 generator
- [market-positioning-strategy](../market-positioning-strategy/proposal.md) — 商業定位北極星
- [e-Stat API ガイド](https://www.e-stat.go.jp/api/api-info/api-guide)
- [JNTO 統計データ](https://www.jnto.go.jp/statistics/)
- [法務省 出入国在留管理庁 統計](https://www.moj.go.jp/isa/policies/statistics/)
- [政府標準利用規約 2.0](https://www8.cao.go.jp/cstp/tyousakai/openscience/index.html)
