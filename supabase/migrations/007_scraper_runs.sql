-- 007_scraper_runs.sql
-- Tracks each scraper / annotator run for cost and throughput monitoring.
-- source: 'peatix' | 'taiwan_cultural_center' | 'annotator'
-- Run in Supabase Dashboard → SQL Editor

create table if not exists scraper_runs (
  id                 bigint generated always as identity primary key,
  ran_at             timestamptz not null default now(),
  source             text        not null,
  events_processed   int         not null default 0,
  openai_tokens_in   int         not null default 0,
  openai_tokens_out  int         not null default 0,
  deepl_chars        int         not null default 0,
  -- GPT-4o-mini pricing as of 2025: $0.15/1M in, $0.60/1M out
  cost_usd           numeric(10, 6) not null default 0,
  notes              text
);

alter table scraper_runs enable row level security;

-- Only admins can read
create policy "Admins read scraper_runs"
  on scraper_runs for select
  using (
    exists (
      select 1 from user_roles
      where user_id = auth.uid() and role = 'admin'
    )
  );

-- Service-role key (used by Python scraper) bypasses RLS,
-- so no insert policy is needed — it writes via service role.
