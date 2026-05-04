-- 039_research_sources_default_organizer.sql
-- Add default_organizer / default_organizer_type to research_sources.
-- When annotator.py produces organizer=null for an event, it falls back to
-- these values if the event's source_name matches a research_sources row.
-- Also used by --propagate-source-organizer to backfill existing events.

ALTER TABLE research_sources
  ADD COLUMN IF NOT EXISTS default_organizer text,
  ADD COLUMN IF NOT EXISTS default_organizer_type text
    CHECK (
      default_organizer_type IS NULL OR
      default_organizer_type IN (
        'government','semi_official','cultural_institution','academic',
        'commercial_brand','independent_venue','civic_group','media','unknown'
      )
    );
