-- Migration 090: submission_url for manual/owner event registration links
ALTER TABLE events
  ADD COLUMN IF NOT EXISTS submission_url TEXT;
COMMENT ON COLUMN events.submission_url IS
  '申込/registration URL from manual/owner intake. Distinct from official_url (announcement) and source_url (provenance).';
