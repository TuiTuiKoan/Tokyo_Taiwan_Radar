-- 083_event_views_country_region.sql
-- Add visitor subdivision (ISO 3166-2 region) code for JP prefecture-level geo analytics.
-- Run in Supabase Dashboard -> SQL Editor

alter table public.event_views
  add column if not exists country_region text;

create index if not exists event_views_country_region_idx
  on public.event_views (country_region);
