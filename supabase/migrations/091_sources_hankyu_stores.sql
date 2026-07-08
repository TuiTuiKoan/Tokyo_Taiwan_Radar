-- ============================================================
-- 091: register Hankyu Hakata & Kobe department stores in sources registry
-- ------------------------------------------------------------
-- Follows the multi-store hankyu scraper refactor (scraper/sources/hankyu.py).
--   - Adds hankyu_hakata (博多阪急, Fukuoka) and hankyu_kobe (神戸阪急, Hyogo).
--   - Uses type='department_store' (migration 067 split 'official' and removed it
--     from the sources_type_check constraint; 'official' would now fail the CHECK).
--   - Corrects existing hankyu_umeda frequency 'daily' -> 'weekly' to match runtime:
--     main.py WEEKLY_SOURCES runs all three hankyu stores weekly, not daily.
-- Non-breaking: registry rows only affect the admin /sources report; scraping is
-- driven by SCRAPERS in main.py, not by this table.
-- Run via Supabase Dashboard -> SQL Editor.
-- ============================================================

-- New Hankyu branch stores (idempotent upsert; sort_order slots between
-- hankyu_umeda=900 and daimaru_matsuzakaya=910).
INSERT INTO sources (id, name, type, frequency, official_url, sort_order) VALUES
  ('hankyu_hakata','博多阪急','department_store','weekly','https://www.hankyu-dept.co.jp/hakata/', 901),
  ('hankyu_kobe','神戸阪急','department_store','weekly','https://www.hankyu-dept.co.jp/kobe/', 902)
ON CONFLICT (id) DO UPDATE SET
  name         = EXCLUDED.name,
  type         = EXCLUDED.type,
  frequency    = EXCLUDED.frequency,
  official_url = EXCLUDED.official_url,
  sort_order   = EXCLUDED.sort_order,
  updated_at   = NOW();

-- Correct existing umeda frequency to match runtime (weekly, per WEEKLY_SOURCES).
UPDATE sources SET frequency = 'weekly', updated_at = NOW()
WHERE id = 'hankyu_umeda' AND frequency <> 'weekly';
