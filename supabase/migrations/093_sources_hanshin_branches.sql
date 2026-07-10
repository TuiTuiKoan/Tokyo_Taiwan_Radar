-- ============================================================
-- 093: register Hanshin Hyogo branch stores in sources registry
-- ------------------------------------------------------------
-- Follows the hanshin scraper (scraper/sources/hanshin.py), which reuses the
-- H2O CMS parser from hankyu.py (subclasses _HankyuBase, overrides _store).
--   - Adds the three Hyogo branches that share the identical H2O CMS as the
--     阪神梅田本店 main store (migration 092):
--       hanshin_nishinomiya  阪神・にしのみや  (西宮市, 兵庫県)
--       hanshin_mikage       阪神・御影        (神戸市東灘区, 兵庫県)
--       hanshin_amagasaki    あまがさき阪神    (尼崎市, 兵庫県)
--   - Uses type='department_store' (same as the hankyu / hanshin_umeda stores;
--     migration 067 removed 'official' from the sources_type_check constraint).
--   - frequency='weekly' matches runtime: main.py WEEKLY_SOURCES runs them weekly.
-- Non-breaking: registry rows only affect the admin /sources report; scraping is
-- driven by SCRAPERS in main.py, not by this table.
-- Run via Supabase Dashboard -> SQL Editor.
-- ============================================================

-- Three Hanshin Hyogo branches (idempotent upsert; sort_order 904/905/906 slot
-- right after the hanshin_umeda main store (903) and before
-- daimaru_matsuzakaya=910).
INSERT INTO sources (id, name, type, frequency, official_url, sort_order) VALUES
  ('hanshin_nishinomiya','阪神・にしのみや','department_store','weekly','https://www.hanshin-dept.jp/nishinomiya/', 904),
  ('hanshin_mikage','阪神・御影','department_store','weekly','https://www.hanshin-dept.jp/mikage/', 905),
  ('hanshin_amagasaki','あまがさき阪神','department_store','weekly','https://www.hanshin-dept.jp/amagasaki/', 906)
ON CONFLICT (id) DO UPDATE SET
  name         = EXCLUDED.name,
  type         = EXCLUDED.type,
  frequency    = EXCLUDED.frequency,
  official_url = EXCLUDED.official_url,
  sort_order   = EXCLUDED.sort_order,
  updated_at   = NOW();
