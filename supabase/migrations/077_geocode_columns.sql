-- Migration 077: Add geocoding columns to events table
-- Apply via Supabase Dashboard > SQL Editor

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS latitude  DECIMAL(9,6),
  ADD COLUMN IF NOT EXISTS longitude DECIMAL(9,6);

CREATE INDEX IF NOT EXISTS events_lat_lng_idx
  ON events (latitude, longitude)
  WHERE latitude IS NOT NULL;
