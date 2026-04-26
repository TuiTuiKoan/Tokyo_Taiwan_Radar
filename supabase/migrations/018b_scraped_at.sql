-- 018b_scraped_at.sql
-- NOTE: renamed from 018_scraped_at.sql because 018_official_url.sql was created first.
-- Both are 018; this file uses the 'b' suffix per the naming convention.
--
-- Add scraped_at column to record when an event was last fetched by the scraper
-- distinct from updated_at (which also changes on annotator runs)

alter table public.events
  add column if not exists scraped_at timestamptz null;

comment on column public.events.scraped_at is
  'Timestamp of the most recent scraper upsert for this event. Null for events pre-dating this migration.';
