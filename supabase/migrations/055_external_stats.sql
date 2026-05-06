-- 055: external_stats — government open data reference tables
-- Three tables for external government statistics:
--   1. external_stats_taiwan_visitors  — JNTO 訪日台湾人月別
--   2. external_stats_resident_taiwanese — MOJ ISA 在留台湾人都道府県別
--   3. external_stats_population       — e-Stat 都道府県別総人口（年更）
-- Run in Supabase Dashboard → SQL Editor.

-- ---- 1. JNTO 訪日外客月別 ----
CREATE TABLE IF NOT EXISTS external_stats_taiwan_visitors (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  year_month       TEXT NOT NULL,          -- 'YYYY-MM'
  source           TEXT NOT NULL,          -- 'jnto'
  total_visitors   INTEGER,               -- 該月台湾訪日人数
  yoy_change_pct   NUMERIC(6,2),          -- 前年同月比（%）
  raw_data         JSONB,                 -- 原始データ
  fetched_at       TIMESTAMPTZ DEFAULT NOW(),
  source_url       TEXT,
  license_code     TEXT NOT NULL,         -- 'jp-gov-pdl-1.0'
  UNIQUE(year_month, source)
);

-- ---- 2. MOJ ISA 在留台湾人（都道府県別、正規化）----
-- One row per prefecture per survey period
CREATE TABLE IF NOT EXISTS external_stats_resident_taiwanese (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  year_month       TEXT NOT NULL,          -- 'YYYY-MM' (June/December)
  prefecture       TEXT NOT NULL,          -- '東京都' etc.
  pref_code        TEXT NOT NULL,          -- '13' etc. (2-digit JIS code)
  count            INTEGER NOT NULL,       -- 在留台湾人数
  source           TEXT NOT NULL DEFAULT 'moj-isa',
  license_code     TEXT NOT NULL DEFAULT 'jp-gov-pdl-1.0',
  fetched_at       TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(year_month, pref_code, source)
);

-- ---- 3. e-Stat 都道府県別総人口（年更、正規化）----
-- One row per prefecture per year; unit = 千人
CREATE TABLE IF NOT EXISTS external_stats_population (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  year             INTEGER NOT NULL,       -- e.g. 2024
  prefecture       TEXT NOT NULL,          -- '東京都' etc.
  pref_code        TEXT NOT NULL,          -- '13' etc.
  population_1000  INTEGER NOT NULL,       -- 総人口（千人単位）
  source           TEXT NOT NULL DEFAULT 'estat-population',
  license_code     TEXT NOT NULL DEFAULT 'CC-BY-4.0',
  fetched_at       TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(year, pref_code, source)
);

-- ---- RLS: public read, service_role write ----
ALTER TABLE external_stats_taiwan_visitors       ENABLE ROW LEVEL SECURITY;
ALTER TABLE external_stats_resident_taiwanese    ENABLE ROW LEVEL SECURITY;
ALTER TABLE external_stats_population            ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ext_visitors_read"
  ON external_stats_taiwan_visitors    FOR SELECT USING (true);
CREATE POLICY "ext_residents_read"
  ON external_stats_resident_taiwanese FOR SELECT USING (true);
CREATE POLICY "ext_population_read"
  ON external_stats_population         FOR SELECT USING (true);
