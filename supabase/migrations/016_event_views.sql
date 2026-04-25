-- 016_event_views.sql
-- Records each event detail page visit for click analytics.
-- Run in Supabase Dashboard → SQL Editor

create table if not exists public.event_views (
  id         bigint generated always as identity primary key,
  event_id   uuid        not null references public.events(id) on delete cascade,
  viewed_at  timestamptz not null default now(),
  locale     text        not null default 'zh'
);

create index if not exists event_views_event_id_idx  on public.event_views (event_id);
create index if not exists event_views_viewed_at_idx on public.event_views (viewed_at);

-- Aggregated view: total click count per event
create or replace view public.event_view_counts as
select event_id, count(*) as view_count
from public.event_views
group by event_id;

-- RLS
alter table public.event_views enable row level security;

-- Anyone (including anonymous visitors) can insert a view record
create policy "Anyone can insert event_view"
  on public.event_views for insert
  with check (true);

-- Only admins can read view records
create policy "Admins read event_views"
  on public.event_views for select
  using (
    exists (
      select 1 from public.user_roles
      where user_id = auth.uid() and role = 'admin'
    )
  );

grant select on public.event_view_counts to authenticated;

comment on table public.event_views is
  'One row per event detail page visit. Used for click analytics in admin dashboard.';

-- Verification:
-- select count(*) from event_views;   -- should be 0 after migration
