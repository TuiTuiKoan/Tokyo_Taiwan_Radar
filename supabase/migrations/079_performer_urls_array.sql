-- Migration 079: performer_urls array
-- Per-performer URL array, parallel to performers[].
-- performer_urls[i] corresponds to performers[i].
-- Distinct from performer_url (single field for single-performer events).

ALTER TABLE events ADD COLUMN IF NOT EXISTS performer_urls TEXT[];

COMMENT ON COLUMN events.performer_urls IS
  'Per-performer URLs (Instagram, YouTube, etc.), parallel index to performers[]. '
  'performer_urls[i] is the URL for performers[i]. '
  'Use performer_url (singular) for single-performer events.';
