-- 011_secondary_source_urls.sql
-- Add secondary_source_urls to store alternative source URLs when the same event
-- appears on multiple platforms. Populated by scraper/merger.py.
ALTER TABLE events
ADD COLUMN IF NOT EXISTS secondary_source_urls text[] DEFAULT '{}';
