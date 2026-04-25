-- Migration 011: Add force_rescrape flag to events table
--
-- When force_rescrape = true, the next scraper run will:
--   1. Fully overwrite ALL fields for that event (bypassing the "skip existing" guard)
--   2. Reset annotation_status → 'pending' so the annotator re-processes it
--   3. Reset force_rescrape → false automatically
--
-- Usage:
--   UPDATE events SET force_rescrape = true WHERE id = '...';
--   Then run: python main.py  (or wait for the daily cron)

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS force_rescrape boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN events.force_rescrape IS
  'When true the next scraper run will fully overwrite this event and reset the flag. '
  'Set to true via admin UI or SQL to trigger a forced re-scrape.';
