-- migration 057: add image_url column to events
ALTER TABLE events ADD COLUMN IF NOT EXISTS image_url TEXT;

COMMENT ON COLUMN events.image_url IS
  'Primary event image URL (poster/OGP). Populated by scrapers and used by enrich_poster.py for Vision OCR enrichment.';
