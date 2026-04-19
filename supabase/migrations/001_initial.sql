-- ============================================================
-- Tokyo Taiwan Radar — Initial Database Migration
-- Run this in Supabase → SQL Editor
-- ============================================================

-- Enable UUID generation
create extension if not exists "pgcrypto";

-- ============================================================
-- Table: events
-- ============================================================
create table if not exists public.events (
  id                uuid primary key default gen_random_uuid(),

  -- Source info (used for deduplication)
  source_name       text not null,
  source_id         text not null,
  source_url        text not null,
  original_language text not null default 'ja',  -- 'ja' | 'zh' | 'en'

  -- Trilingual content
  name_ja           text,
  name_zh           text,
  name_en           text,
  description_ja    text,
  description_zh    text,
  description_en    text,

  -- Classification
  category          text[] default '{}',   -- e.g. ['culture', 'movie']

  -- Schedule
  start_date        timestamptz,
  end_date          timestamptz,

  -- Location
  location_name     text,
  location_address  text,
  business_hours    text,

  -- Pricing
  is_paid           boolean,
  price_info        text,

  -- Status
  is_active         boolean not null default true,

  -- Timestamps
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),

  -- Prevent duplicate scrapes from the same source
  unique (source_name, source_id)
);

-- Full-text search index (Japanese + Chinese + English combined)
create index if not exists events_search_idx
  on public.events
  using gin(
    to_tsvector('simple',
      coalesce(name_ja, '') || ' ' ||
      coalesce(name_zh, '') || ' ' ||
      coalesce(name_en, '') || ' ' ||
      coalesce(description_ja, '') || ' ' ||
      coalesce(description_zh, '') || ' ' ||
      coalesce(description_en, '')
    )
  );

-- Index for common filter queries
create index if not exists events_start_date_idx on public.events (start_date);
create index if not exists events_category_idx   on public.events using gin (category);
create index if not exists events_is_paid_idx    on public.events (is_paid);
create index if not exists events_is_active_idx  on public.events (is_active);

-- Auto-update updated_at on any row change
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace trigger events_updated_at
  before update on public.events
  for each row execute procedure public.set_updated_at();

-- ============================================================
-- Table: saved_events  (user favourites)
-- ============================================================
create table if not exists public.saved_events (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  event_id   uuid not null references public.events (id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (user_id, event_id)
);

create index if not exists saved_events_user_idx  on public.saved_events (user_id);
create index if not exists saved_events_event_idx on public.saved_events (event_id);

-- ============================================================
-- Table: user_roles  (admin flag)
-- ============================================================
create table if not exists public.user_roles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  role    text not null default 'user'   -- 'user' | 'admin'
);

-- ============================================================
-- Row Level Security (RLS)
-- ============================================================

alter table public.events        enable row level security;
alter table public.saved_events  enable row level security;
alter table public.user_roles    enable row level security;

-- events: anyone can read active events
create policy "Public read events"
  on public.events for select
  using (is_active = true);

-- events: only the service role (scraper / admin API) can insert/update/delete
-- (the service role key bypasses RLS automatically — no policy needed for it)

-- saved_events: users can only see and modify their own saved events
create policy "Users manage their own saved events"
  on public.saved_events for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- user_roles: users can read their own role
create policy "Users read own role"
  on public.user_roles for select
  using (auth.uid() = user_id);

-- ============================================================
-- Helper function: is the current user an admin?
-- (Used in Next.js API routes via RPC call)
-- ============================================================
create or replace function public.is_admin()
returns boolean language sql security definer as $$
  select exists (
    select 1 from public.user_roles
    where user_id = auth.uid() and role = 'admin'
  );
$$;
