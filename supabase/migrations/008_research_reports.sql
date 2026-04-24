-- 008_research_reports.sql
-- Stores daily research reports from the automated researcher.
-- Run in Supabase Dashboard → SQL Editor

create table if not exists research_reports (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  report_type text        not null,  -- 'source_discovery' | 'news_digest' | 'category_suggestion'
  content     jsonb       not null,
  status      text        not null default 'pending'  -- 'pending' | 'reviewed' | 'implemented'
);

alter table research_reports enable row level security;

create policy "Admins read research_reports"
  on research_reports for select
  using (
    exists (
      select 1 from user_roles
      where user_id = auth.uid() and role = 'admin'
    )
  );