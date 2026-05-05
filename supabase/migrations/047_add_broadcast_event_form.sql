-- Migration 047: Add 'broadcast' and 'tasting' to events_event_form_check constraint
-- Required by: annotator.py VALID_EVENT_FORMS, gguide_tv batch fix

ALTER TABLE events DROP CONSTRAINT IF EXISTS events_event_form_check;

ALTER TABLE events
  ADD CONSTRAINT events_event_form_check
  CHECK (
    event_form <@ ARRAY[
      'exhibition','screening','lecture','performance','market','workshop',
      'conference','networking','screening_with_talk','tour','competition',
      'tasting','broadcast','other'
    ]::text[]
  );
