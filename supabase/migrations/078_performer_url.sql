-- Migration 078: performer_url
-- Adds a URL field for the performer's official page (SNS, portfolio, etc.)
-- Distinct from official_url (event page) and organizer_url (organizer site).

ALTER TABLE events ADD COLUMN IF NOT EXISTS performer_url TEXT;

COMMENT ON COLUMN events.performer_url IS
  'URL for the performer''s official page (Instagram, YouTube, portfolio, etc.). '
  'Shown as a platform icon next to the performer name on the event detail page. '
  'Distinct from official_url (event-specific page) and organizer_url (organizer site).';
