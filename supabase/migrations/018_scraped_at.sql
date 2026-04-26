-- 018: Add scraped_at column to record when an event was last fetched by the scraper
-- distinct from updated_at (which also changes on annotator runs)

alter table public.events
  add column if not exists scraped_at timestamptz null;

comment on column public.events.scraped_at is
  'Timestamp of the most recent scraper upsert for this event. Null for events pre-dating this migration.';
