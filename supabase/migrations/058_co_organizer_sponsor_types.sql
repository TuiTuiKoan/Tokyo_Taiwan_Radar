-- migration 058: add co_organizer_types and sponsor_types columns
-- These are parallel arrays to co_organizers and sponsors respectively,
-- storing organizer_type classification for each entry at the same index.

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS co_organizer_types text[],
  ADD COLUMN IF NOT EXISTS sponsor_types      text[];

COMMENT ON COLUMN events.co_organizer_types IS 'organizer_type values parallel to co_organizers array (same index)';
COMMENT ON COLUMN events.sponsor_types      IS 'organizer_type values parallel to sponsors array (same index)';
