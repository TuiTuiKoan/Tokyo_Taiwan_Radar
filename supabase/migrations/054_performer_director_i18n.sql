-- 054: performer_director_i18n
-- Add performer_zh/en and director_zh/en for multilingual display.
-- Admin must run in Supabase Dashboard → SQL Editor.

ALTER TABLE events ADD COLUMN IF NOT EXISTS performer_zh TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS performer_en TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS director_zh TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS director_en TEXT;
