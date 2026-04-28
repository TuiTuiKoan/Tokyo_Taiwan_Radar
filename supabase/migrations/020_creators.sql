-- 020_creators.sql
-- Community Intelligence: tracks Taiwan-related creators/voices active in Japan.
-- Admin-only internal database — not publicly exposed.
-- Run in Supabase Dashboard → SQL Editor

create table if not exists public.creators (
  id               uuid primary key default gen_random_uuid(),
  name             text not null,
  name_zh          text,
  platform         text not null,    -- 'note'|'youtube'|'twitter'|'instagram'|'blog'|'substack'|'other'
  handle           text,
  profile_url      text not null,
  category         text,             -- 'researcher'|'traveler'|'writer'|'activist'|'food'|'art'|'business'|'media'
  base_location    text,             -- 'tokyo'|'osaka'|'fukuoka'|'nationwide'|'other'
  nationality      text,             -- 'taiwanese_in_japan'|'japanese'|'other'
  is_active        boolean not null default true,
  approx_followers integer,
  last_post_at     date,
  notes            text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index if not exists creators_platform_idx  on public.creators (platform);
create index if not exists creators_category_idx  on public.creators (category);
create index if not exists creators_is_active_idx on public.creators (is_active);

-- creator <-> event relationship (speaker, organizer, covered, etc.)
create table if not exists public.creator_events (
  creator_id   uuid not null references public.creators(id) on delete cascade,
  event_id     uuid not null references public.events(id)   on delete cascade,
  relationship text not null,  -- 'organizer'|'speaker'|'participant'|'covered'
  primary key (creator_id, event_id, relationship)
);

create index if not exists creator_events_event_id_idx on public.creator_events (event_id);

-- auto-update updated_at on row change
create or replace function public.set_creators_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger creators_updated_at
  before update on public.creators
  for each row execute function public.set_creators_updated_at();

-- RLS: admin-only read/write
alter table public.creators       enable row level security;
alter table public.creator_events enable row level security;

create policy "Admins manage creators"
  on public.creators for all
  using (
    exists (
      select 1 from public.user_roles
      where user_id = auth.uid() and role = 'admin'
    )
  );

create policy "Admins manage creator_events"
  on public.creator_events for all
  using (
    exists (
      select 1 from public.user_roles
      where user_id = auth.uid() and role = 'admin'
    )
  );

comment on table public.creators is
  'In-Japan Taiwan-related creators and voices. Admin-only. Not publicly exposed.';
comment on table public.creator_events is
  'Links creators to events they organized, spoke at, participated in, or covered.';

-- Verification:
-- select count(*) from creators;        -- should be 0 after migration
-- select count(*) from creator_events;  -- should be 0 after migration
