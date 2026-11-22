-- ============================================================
-- 110: register tufs_aa (東京外国語大学 AA研) in sources registry
-- ------------------------------------------------------------
-- Follows scraper/sources/tufs_aa.py (#726). Daily, academic.
-- Non-breaking: registry rows only affect the admin /sources report; scraping is
-- driven by SCRAPERS in main.py, not by this table.
-- Run via Supabase Dashboard -> SQL Editor.
-- ============================================================

INSERT INTO sources (id, name, type, frequency, official_url, sort_order) VALUES
  ('tufs_aa','東京外国語大学 アジア・アフリカ言語文化研究所（AA研）','academic','daily','https://www.aa.tufs.ac.jp/events/', 355)
ON CONFLICT (id) DO UPDATE SET
  name         = EXCLUDED.name,
  type         = EXCLUDED.type,
  frequency    = EXCLUDED.frequency,
  official_url = EXCLUDED.official_url,
  sort_order   = EXCLUDED.sort_order,
  updated_at   = NOW();
