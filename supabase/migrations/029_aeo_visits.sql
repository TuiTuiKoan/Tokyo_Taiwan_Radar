-- 029_aeo_visits.sql
-- AEO (AI Engine Optimization) monitoring: tracks AI bot crawls + AI engine referrals.
-- Run in Supabase Dashboard → SQL Editor.

create table if not exists public.aeo_visits (
  id          bigint generated always as identity primary key,
  visited_at  timestamptz not null default now(),
  visit_type  text        not null check (visit_type in ('bot', 'ai_referral')),
  bot_name    text,        -- e.g. 'GPTBot' | 'PerplexityBot' (null for ai_referral)
  ai_source   text,        -- e.g. 'Perplexity' | 'ChatGPT' (null for bot)
  user_agent  text,
  path        text        not null,
  referer     text,
  country     text         -- from x-vercel-ip-country header (best effort)
);

create index if not exists aeo_visits_visited_at_idx
  on public.aeo_visits (visited_at desc);
create index if not exists aeo_visits_visit_type_idx
  on public.aeo_visits (visit_type, visited_at desc);
create index if not exists aeo_visits_bot_name_idx
  on public.aeo_visits (bot_name, visited_at desc)
  where bot_name is not null;
create index if not exists aeo_visits_ai_source_idx
  on public.aeo_visits (ai_source, visited_at desc)
  where ai_source is not null;

-- RLS
alter table public.aeo_visits enable row level security;

-- Anyone (anonymous middleware) can insert — log-only, no PII besides UA
create policy "Anyone can insert aeo_visit"
  on public.aeo_visits for insert
  with check (true);

-- Only admins can read
create policy "Admins read aeo_visits"
  on public.aeo_visits for select
  using (
    exists (
      select 1 from public.user_roles
      where user_id = auth.uid() and role = 'admin'
    )
  );

comment on table public.aeo_visits is
  'AEO monitoring: AI bot crawl visits + AI engine referrals. Populated by edge middleware (proxy.ts).';

-- Verification:
-- select count(*) from aeo_visits;   -- should be 0 after migration
