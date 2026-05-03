-- 035_organizer_form_language.sql
-- Tier 1 expansion for consulting-grade analytics:
-- organizer / organizer_type / event_form / language fields.

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS organizer text,
  ADD COLUMN IF NOT EXISTS co_organizers text[] DEFAULT '{}'::text[],
  ADD COLUMN IF NOT EXISTS sponsors text[] DEFAULT '{}'::text[],
  ADD COLUMN IF NOT EXISTS organizer_type text[] DEFAULT '{}'::text[],
  ADD COLUMN IF NOT EXISTS event_form text[] DEFAULT '{}'::text[],
  ADD COLUMN IF NOT EXISTS primary_language text,
  ADD COLUMN IF NOT EXISTS has_japanese_support boolean,
  ADD COLUMN IF NOT EXISTS has_english_support boolean;

ALTER TABLE events
  ADD CONSTRAINT events_organizer_type_check
  CHECK (
    organizer_type <@ ARRAY[
      'government','semi_official','cultural_institution','academic',
      'commercial_brand','independent_venue','civic_group','media','unknown'
    ]::text[]
  );

ALTER TABLE events
  ADD CONSTRAINT events_event_form_check
  CHECK (
    event_form <@ ARRAY[
      'exhibition','screening','lecture','performance','market','workshop',
      'conference','networking','screening_with_talk','tour','competition','other'
    ]::text[]
  );

ALTER TABLE events
  ADD CONSTRAINT events_primary_language_check
  CHECK (primary_language IS NULL OR primary_language IN ('ja','zh','en','mixed'));

CREATE INDEX IF NOT EXISTS idx_events_organizer_type
  ON events USING GIN (organizer_type);

CREATE INDEX IF NOT EXISTS idx_events_event_form
  ON events USING GIN (event_form);

CREATE INDEX IF NOT EXISTS idx_events_primary_language
  ON events (primary_language)
  WHERE primary_language IS NOT NULL;
