-- Migration 047: Add 'broadcast', 'tasting', 'study_abroad', 'publication' to events_event_form_check constraint
-- Required by: annotator.py VALID_EVENT_FORMS, gguide_tv batch fix
-- Note: 'study_abroad' added because 1 existing row had this value (DB diagnostic 2026-05-15)

ALTER TABLE events DROP CONSTRAINT IF EXISTS events_event_form_check;

ALTER TABLE events
  ADD CONSTRAINT events_event_form_check
  CHECK (
    event_form <@ ARRAY[
      'exhibition','screening','lecture','performance','market','workshop',
      'conference','networking','screening_with_talk','tour','competition',
      'tasting','broadcast','study_abroad','publication','other'
    ]::text[]
  );
