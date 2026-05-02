-- 034_name_ja_locked.sql
-- Add name_ja_locked column so scrapers can protect a precisely-extracted
-- Japanese title from being overwritten by the annotator GPT pipeline.
--
-- When name_ja_locked = true:
--   - annotator preserves the scraper-set name_ja (= raw_title) unchanged
--   - translations (name_zh, name_en, description_*, category) are still generated
--
-- Primary use case: academic sub-events where name_ja comes from a structured
-- source field (e.g. taiwanshi 題目:, JATS paper titles) and is already the
-- definitive, precise title including full subtitle.

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS name_ja_locked boolean NOT NULL DEFAULT false;

-- Existing rows default to false → no behaviour change for current data.
-- SELECT id, name_ja, name_ja_locked FROM events LIMIT 3;  -- verify column added
