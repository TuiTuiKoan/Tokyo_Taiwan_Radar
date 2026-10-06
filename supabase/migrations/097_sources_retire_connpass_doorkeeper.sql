-- ============================================================
-- 097: sources_retire_connpass_doorkeeper
-- The Connpass and Doorkeeper scrapers were deleted from scraper/sources/.
--
--   1. sources: mark both rows inactive so /sources and /admin/sources stop
--      listing them. Rows are kept (existing events still carry these
--      source_name values and merger.py still ranks them).
--   2. events: soft-disable every still-active Doorkeeper event. Manual
--      review (2026-10-06) found none fit Tokyo Taiwan Radar's scope.
--      Rows are kept for audit; reverse with the query at the bottom.
--   3. research_sources: move both platforms from implemented to not-viable
--      so researcher.py keeps treating their domains as known/blocked.
--      (scraper/research_exclusions.py additionally blocks subdomains.)
--
-- Idempotent: re-running changes nothing once applied.
-- Admin must run in Supabase Dashboard → SQL Editor.
-- APPLY STATUS: NOT YET APPLIED.
-- ============================================================

BEGIN;

UPDATE sources
SET is_active = FALSE
WHERE id IN ('connpass', 'doorkeeper')
  AND is_active = TRUE;

UPDATE events
SET is_active           = FALSE,
    deactivated_at      = NOW(),
    deactivated_reason  = 'source_retired_doorkeeper',
    deactivated_by_pass = 'admin_manual'
WHERE source_name = 'doorkeeper'
  AND is_active = TRUE;

UPDATE research_sources
SET status = 'not-viable',
    reason = 'Retired 2026-10: scraper removed; events were almost all unrelated to Taiwan.'
WHERE scraper_source_name IN ('connpass', 'doorkeeper')
  AND status <> 'not-viable';

COMMIT;

-- Verify (expect 0 rows each):
--   SELECT id FROM sources WHERE id IN ('connpass','doorkeeper') AND is_active;
--   SELECT id FROM events  WHERE source_name = 'doorkeeper' AND is_active;
--   SELECT id FROM research_sources
--     WHERE scraper_source_name IN ('connpass','doorkeeper') AND status <> 'not-viable';
--
-- Reverse step 2 for a single event if it should come back:
--   UPDATE events SET is_active = TRUE, deactivated_at = NULL,
--          deactivated_reason = NULL, deactivated_by_pass = NULL
--   WHERE id = '<event_id>' AND deactivated_reason = 'source_retired_doorkeeper';
