-- 014_scraper_runs_v2.sql
-- Adds success flag and wall-clock duration to scraper_runs.
-- Run in Supabase Dashboard → SQL Editor

alter table scraper_runs
  add column if not exists success          boolean not null default true,
  add column if not exists duration_seconds int     not null default 0;

comment on column scraper_runs.success is
  'false if the scraper raised an unhandled exception during this run';
comment on column scraper_runs.duration_seconds is
  'Wall-clock seconds from scraper start to finish for this run';
