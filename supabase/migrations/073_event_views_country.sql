-- 073_event_views_country.sql
-- Add country code column for geo analytics in admin dashboard.
-- Run in Supabase Dashboard -> SQL Editor

alter table public.event_views
  add column if not exists country text;

create index if not exists event_views_country_idx
  on public.event_views (country);
