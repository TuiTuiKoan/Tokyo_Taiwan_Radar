-- 031_location_url.sql
-- Add location_url column to store the official website URL of the venue.
-- Used to hyperlink venue names on the event detail page.

ALTER TABLE events ADD COLUMN IF NOT EXISTS location_url text;
