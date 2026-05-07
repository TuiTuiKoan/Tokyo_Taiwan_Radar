-- ============================================================
-- 059: organizer_multilingual
-- Add organizer_zh / organizer_en for locale-aware display
-- Admin must run in Supabase Dashboard → SQL Editor
-- ============================================================

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS organizer_zh TEXT,
  ADD COLUMN IF NOT EXISTS organizer_en TEXT;
