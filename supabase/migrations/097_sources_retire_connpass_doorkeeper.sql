-- ============================================================
-- 097: sources_retire_connpass_doorkeeper
-- The Connpass and Doorkeeper scrapers were deleted from scraper/sources/.
-- Mark both rows inactive so /sources and /admin/sources stop listing them.
-- Rows are kept (not deleted): existing events still carry these
-- source_name values and merger.py still ranks them.
-- Admin must run in Supabase Dashboard → SQL Editor.
-- APPLY STATUS: NOT YET APPLIED.
-- ============================================================

UPDATE sources
SET is_active = FALSE
WHERE id IN ('connpass', 'doorkeeper');
