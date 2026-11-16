-- ── Migration: 109_event_views_visitor_class ────────────────────────────────
-- Spec: docs/specs/active/view-bot-filter
--
-- event_views is written by a Server Action fired from ViewTracker's useEffect,
-- so crawlers that execute JS (Googlebot, Applebot, Bingbot, …) were counted as
-- visitors. 2026-11-16: 7,447 of 8,934 US rows matched a known-bot request in
-- aeo_visits on the same path within seconds; JP matched 2 of 1,524.
--
-- 1. visitor_class: human | known_bot | suspected_bot | unclassified
--    (default 'unclassified' = written before this migration / old code).
-- 2. bot_name: aeo_visits-compatible bot name, or 'generic'.
-- 3. Backfill: an unclassified row becomes known_bot when aeo_visits has a bot
--    request on '/{locale}/events/{event_id}' between viewed_at - 30 s and
--    viewed_at + 5 s (closest one wins). Unmatched rows stay unclassified.
--
-- ORDER: apply BEFORE merging the PR. The new record-view.ts inserts these
-- columns; without them every insert fails (and the action swallows errors).
-- Idempotent: re-running adds nothing and the backfill only touches
-- 'unclassified' rows that still have a match (0 on the second run).
-- No new table, RLS or GRANT change: columns inherit event_views privileges.

begin;
set local lock_timeout = '5s';

alter table public.event_views
  add column if not exists visitor_class text not null default 'unclassified',
  add column if not exists bot_name text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'event_views_visitor_class_check'
      and conrelid = 'public.event_views'::regclass
  ) then
    alter table public.event_views
      add constraint event_views_visitor_class_check
      check (visitor_class in ('human', 'known_bot', 'suspected_bot', 'unclassified'));
  end if;
end $$;

comment on column public.event_views.visitor_class is
  'human | known_bot | suspected_bot (classified from request headers by web/lib/analytics/botDetect.ts) | unclassified (pre-109 rows not matched to aeo_visits). Spec view-bot-filter.';
comment on column public.event_views.bot_name is
  'known_bot: aeo_visits.bot_name or ''generic:<token>''; suspected_bot: ''suspect:no_ua'' / ''suspect:no_accept_language''; human: null.';

-- Backfill from aeo_visits (same path, -30 s … +5 s, closest match). The same
-- statement lives in docs/specs/active/view-bot-filter/backfill.sql, to be
-- re-run after the deploy for rows the old code wrote in between. One
-- aeo_visits row may match several event_views rows; that is allowed.
-- Depends on aeo_visits history still being present (see spec: the monthly
-- cleanup in scraper/monthly_health_check.py must not be fixed before this runs).
update public.event_views v
set visitor_class = 'known_bot',
    bot_name      = m.bot_name
from public.event_views ev
cross join lateral (
  select a.bot_name
    from public.aeo_visits a
   where a.visit_type = 'bot'
     and a.visited_at between ev.viewed_at - interval '30 seconds'
                          and ev.viewed_at + interval '5 seconds'
     and a.path = '/' || ev.locale || '/events/' || ev.event_id::text
   order by abs(extract(epoch from a.visited_at - ev.viewed_at))
   limit 1
) m
where v.id = ev.id
  and ev.visitor_class = 'unclassified'
  and m.bot_name is not null;

-- Read-back guard: abort if the schema is not as expected.
do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'event_views'
      and column_name = 'visitor_class' and is_nullable = 'NO'
  ) then
    raise exception '109: event_views.visitor_class missing or nullable';
  end if;
  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'event_views' and column_name = 'bot_name'
  ) then
    raise exception '109: event_views.bot_name missing';
  end if;
  if exists (
    select 1 from public.event_views
    where visitor_class = 'known_bot' and bot_name is null
  ) then
    raise exception '109: known_bot rows without bot_name';
  end if;
end $$;

commit;

-- Verification (read-only, after commit):
-- select visitor_class, country, count(*) from public.event_views
--  group by 1, 2 order by 3 desc limit 20;
-- Expected on 2026-11-16 data: US known_bot ≈ 7,450; JP known_bot ≈ 2.
