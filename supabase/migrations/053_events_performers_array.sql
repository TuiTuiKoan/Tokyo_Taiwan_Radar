-- 053: events_performers_array
-- Add performers TEXT[] column for multi-speaker support.
-- Will replace performer TEXT in a future migration once all data is backfilled.
ALTER TABLE events ADD COLUMN IF NOT EXISTS performers TEXT[];
COMMENT ON COLUMN events.performers IS 'Array of performer/speaker names (multi-speaker support). Replaces performer TEXT in a future migration.';
