-- 018_official_url.sql
-- Add official_url to store the authoritative organiser URL for an event.
-- Set by official-source scrapers (taiwan_matsuri, taiwan_cultural_center, etc.).
-- Takes display priority over source_url in the event detail page.
-- NULL = no official URL known (show source_url instead).
ALTER TABLE events
ADD COLUMN IF NOT EXISTS official_url text;

COMMENT ON COLUMN events.official_url IS
  'Authoritative organiser URL. Set by official-source scrapers (taiwan_matsuri, taiwan_cultural_center, etc.).
   Takes display priority over source_url in the event detail page.
   NULL = no official URL known (show source_url instead).';
