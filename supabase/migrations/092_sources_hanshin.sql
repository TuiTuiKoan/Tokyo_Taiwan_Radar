-- ============================================================
-- 092: register Hanshin Umeda main store in sources registry
-- ------------------------------------------------------------
-- Follows the hanshin scraper (scraper/sources/hanshin.py), which reuses the
-- H2O CMS parser from hankyu.py (subclasses _HankyuBase, overrides _store).
--   - Adds hanshin_umeda (阪神梅田本店, Osaka) — H2O Retailing sister store of
--     阪急, hosts the large 「阪神の台湾展」 Taiwan fair.
--   - Uses type='department_store' (same as the hankyu stores; migration 067
--     removed 'official' from the sources_type_check constraint).
--   - frequency='weekly' matches runtime: main.py WEEKLY_SOURCES runs it weekly.
-- Non-breaking: registry rows only affect the admin /sources report; scraping is
-- driven by SCRAPERS in main.py, not by this table.
-- Run via Supabase Dashboard -> SQL Editor.
-- ============================================================

-- New Hanshin main store (idempotent upsert; sort_order 903 slots right after
-- the hankyu stores umeda=900 / hakata=901 / kobe=902 and before
-- daimaru_matsuzakaya=910).
INSERT INTO sources (id, name, type, frequency, official_url, sort_order) VALUES
  ('hanshin_umeda','阪神梅田本店','department_store','weekly','https://www.hanshin-dept.jp/hshonten/', 903)
ON CONFLICT (id) DO UPDATE SET
  name         = EXCLUDED.name,
  type         = EXCLUDED.type,
  frequency    = EXCLUDED.frequency,
  official_url = EXCLUDED.official_url,
  sort_order   = EXCLUDED.sort_order,
  updated_at   = NOW();
