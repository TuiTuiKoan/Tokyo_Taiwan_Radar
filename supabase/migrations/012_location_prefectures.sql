-- Migration 012: Add location_prefectures column for multi-city parent events
-- This column stores the aggregated list of Japanese prefecture names extracted
-- from sub-events' location_address fields (e.g. {'東京','大阪','京都'}).
-- Populated by: scraper/annotator.py (after sub-event creation) and backfill script.
-- Used by: FilterBar location filter (OR logic alongside location_address ilike).

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS location_prefectures text[] DEFAULT NULL;

COMMENT ON COLUMN events.location_prefectures IS
  'Aggregated prefecture names from sub-events for multi-city parent events (e.g. {東京,大阪,京都}). NULL for single-city or non-parent events.';
