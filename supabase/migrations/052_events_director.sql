-- 052: events_director
-- Add director column to events table for Schema.org and UI display.
-- Admin must run in Supabase Dashboard → SQL Editor.

ALTER TABLE events ADD COLUMN IF NOT EXISTS director TEXT;
