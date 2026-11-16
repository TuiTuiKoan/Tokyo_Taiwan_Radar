-- 108_guide_events.sql
-- spec guide-analytics: visitor journey, dwell time and search terms for the static
-- guide tools under /YYYYMM/* (first: /202611/synchronic-constellation).
-- Run in Supabase Dashboard → SQL Editor. Apply BEFORE merging the PR that adds
-- /api/guide/track; until then the endpoint returns 500 and the guide tracker fails silently.
--
-- Access model: Tier C + admin read.
--   * writes only through /api/guide/track with the service role (no anon INSERT)
--   * admins read through RLS (is_admin()) and the SECURITY INVOKER guide_stats() RPC

begin;

set local lock_timeout = '5s';

create table if not exists public.guide_events (
  id              bigint generated always as identity primary key,
  occurred_at     timestamptz not null default now(),
  guide_slug      text        not null check (guide_slug ~ '^[0-9]{6}/[a-z0-9-]{1,80}$'),
  session_id      text        not null check (session_id ~ '^[A-Za-z0-9_-]{8,40}$'),
  event_type      text        not null check (event_type in ('view', 'leave', 'search', 'outbound', 'lang')),
  seq             integer     check (seq between 0 and 10000),
  view_kind       text        check (view_kind in ('home', 'chapter', 'work', 'doc')),
  view_id         text        check (char_length(view_id) <= 40),
  lang            text        check (lang in ('ja', 'en', 'zh')),
  dwell_ms        integer     check (dwell_ms between 0 and 1800000),
  search_query    text        check (char_length(search_query) <= 100),
  result_count    integer     check (result_count between 0 and 10000),
  target          text        check (char_length(target) <= 300),
  traffic_source  text        check (char_length(traffic_source) <= 32),
  referrer_host   text        check (char_length(referrer_host) <= 120),
  utm_source      text        check (char_length(utm_source) <= 64),
  utm_medium      text        check (char_length(utm_medium) <= 64),
  utm_campaign    text        check (char_length(utm_campaign) <= 64),
  device          text        check (device in ('mobile', 'tablet', 'desktop')),
  browser         text        check (char_length(browser) <= 32),
  in_app          text        check (char_length(in_app) <= 32),
  country         text        check (country ~ '^[A-Z]{2}$'),
  region          text        check (region ~ '^[A-Z0-9]{1,8}$')
);

create index if not exists guide_events_slug_time_idx
  on public.guide_events (guide_slug, occurred_at desc);
create index if not exists guide_events_session_idx
  on public.guide_events (session_id, seq);

comment on table public.guide_events is
  'Guide tools (/YYYYMM/*) analytics: one row per view/leave/search/outbound/lang event. Written by /api/guide/track (service role). No IP, no raw UA. spec guide-analytics.';

alter table public.guide_events enable row level security;

revoke all on public.guide_events from anon, authenticated;
grant select on public.guide_events to authenticated;
grant select, insert on public.guide_events to service_role;
grant usage on sequence public.guide_events_id_seq to service_role;

drop policy if exists guide_events_admin_select on public.guide_events;
create policy guide_events_admin_select
  on public.guide_events for select
  to authenticated
  using ((select public.is_admin()));

-- ── Aggregation RPC ─────────────────────────────────────────────────────────
-- SECURITY INVOKER: RLS on guide_events applies, so a non-admin caller sees empty stats.
create or replace function public.guide_stats(p_slug text, p_since timestamptz)
returns jsonb
language sql
stable
security invoker
set search_path = pg_catalog, public
as $$
  with ev as (
    select *
    from public.guide_events
    where guide_slug = p_slug
      and occurred_at >= p_since
  ),
  views as (
    select session_id, seq, view_kind, view_id, occurred_at
    from ev where event_type = 'view'
  ),
  dwell as (
    -- one view can have several leave segments (tab hidden / shown); sum them first
    select session_id, seq, max(view_kind) as view_kind, max(view_id) as view_id,
           sum(dwell_ms)::bigint as dwell_ms
    from ev where event_type = 'leave' and seq is not null
    group by session_id, seq
  ),
  sessions as (
    select session_id, count(*) as n_views
    from views group by session_id
  ),
  first_ev as (
    select distinct on (session_id) session_id, traffic_source, device, browser, in_app, country, lang,
           utm_source
    from ev order by session_id, occurred_at, id
  ),
  entries as (
    select distinct on (session_id) session_id, view_kind, view_id
    from views order by session_id, seq, occurred_at
  ),
  transitions as (
    select a.view_kind || ':' || coalesce(a.view_id, '') as from_view,
           b.view_kind || ':' || coalesce(b.view_id, '') as to_view
    from views a
    join views b on b.session_id = a.session_id and b.seq = a.seq + 1
  ),
  searches as (
    select lower(btrim(search_query)) as q, result_count, target
    from ev where event_type = 'search' and search_query is not null and btrim(search_query) <> ''
  )
  select jsonb_build_object(
    'summary', jsonb_build_object(
      'sessions', (select count(*) from sessions),
      'views', (select count(*) from views),
      'avg_views_per_session', (select round(avg(n_views)::numeric, 2) from sessions),
      'median_dwell_ms', (select percentile_cont(0.5) within group (order by dwell_ms) from dwell),
      'searches', (select count(*) from searches),
      'outbound', (select count(*) from ev where event_type = 'outbound')
    ),
    'top_views', coalesce((
      select jsonb_agg(r order by r.views desc) from (
        select v.view_kind, v.view_id, count(*) as views,
               count(distinct v.session_id) as sessions,
               (select percentile_cont(0.5) within group (order by d.dwell_ms)
                  from dwell d where d.view_kind = v.view_kind
                    and d.view_id is not distinct from v.view_id) as median_dwell_ms
        from views v
        group by v.view_kind, v.view_id
        order by count(*) desc
        limit 30
      ) r), '[]'::jsonb),
    'entries', coalesce((
      select jsonb_agg(r order by r.sessions desc) from (
        select view_kind, view_id, count(*) as sessions
        from entries group by view_kind, view_id
        order by count(*) desc limit 10
      ) r), '[]'::jsonb),
    'transitions', coalesce((
      select jsonb_agg(r order by r.n desc) from (
        select from_view, to_view, count(*) as n
        from transitions group by from_view, to_view
        order by count(*) desc limit 15
      ) r), '[]'::jsonb),
    'session_lengths', (
      select jsonb_build_object(
        '1', count(*) filter (where n_views = 1),
        '2-3', count(*) filter (where n_views between 2 and 3),
        '4-9', count(*) filter (where n_views between 4 and 9),
        '10+', count(*) filter (where n_views >= 10))
      from sessions),
    'top_searches', coalesce((
      select jsonb_agg(r order by r.n desc) from (
        select q, count(*) as n, round(avg(result_count)::numeric, 1) as avg_results
        from searches group by q order by count(*) desc limit 30
      ) r), '[]'::jsonb),
    'zero_result_searches', coalesce((
      select jsonb_agg(r order by r.n desc) from (
        select q, count(*) as n
        from searches where result_count = 0
        group by q order by count(*) desc limit 20
      ) r), '[]'::jsonb),
    'search_targets', coalesce((
      select jsonb_object_agg(coalesce(target, 'unknown'), n) from (
        select target, count(*) as n from searches group by target
      ) r), '{}'::jsonb),
    'traffic_source', coalesce((select jsonb_object_agg(coalesce(k, 'unknown'), n) from (
        select traffic_source as k, count(*) as n from first_ev group by 1) r), '{}'::jsonb),
    'device', coalesce((select jsonb_object_agg(coalesce(k, 'unknown'), n) from (
        select device as k, count(*) as n from first_ev group by 1) r), '{}'::jsonb),
    'browser', coalesce((select jsonb_object_agg(coalesce(k, 'unknown'), n) from (
        select browser as k, count(*) as n from first_ev group by 1) r), '{}'::jsonb),
    'in_app', coalesce((select jsonb_object_agg(coalesce(k, 'none'), n) from (
        select in_app as k, count(*) as n from first_ev group by 1) r), '{}'::jsonb),
    'country', coalesce((select jsonb_object_agg(coalesce(k, 'unknown'), n) from (
        select country as k, count(*) as n from first_ev group by 1) r), '{}'::jsonb),
    'first_lang', coalesce((select jsonb_object_agg(coalesce(k, 'unknown'), n) from (
        select lang as k, count(*) as n from first_ev group by 1) r), '{}'::jsonb),
    'utm_source', coalesce((select jsonb_object_agg(k, n) from (
        select utm_source as k, count(*) as n from first_ev where utm_source is not null group by 1) r), '{}'::jsonb),
    'outbound', coalesce((
      select jsonb_agg(r order by r.n desc) from (
        select target, count(*) as n from ev
        where event_type = 'outbound' and target is not null
        group by target order by count(*) desc limit 15
      ) r), '[]'::jsonb),
    'lang_switch', coalesce((select jsonb_object_agg(k, n) from (
        select target as k, count(*) as n from ev
        where event_type = 'lang' and target is not null group by 1) r), '{}'::jsonb)
  );
$$;

revoke execute on function public.guide_stats(text, timestamptz) from public, anon;
grant execute on function public.guide_stats(text, timestamptz) to authenticated, service_role;

-- Read-back checks: abort the transaction if the access model is not as intended.
do $$
begin
  if has_table_privilege('anon', 'public.guide_events', 'select')
     or has_table_privilege('anon', 'public.guide_events', 'insert')
     or has_table_privilege('authenticated', 'public.guide_events', 'insert') then
    raise exception '108: unexpected table grant on guide_events';
  end if;
  if has_function_privilege('anon', 'public.guide_stats(text, timestamptz)', 'execute') then
    raise exception '108: anon can execute guide_stats';
  end if;
  if not (select relrowsecurity from pg_class where oid = 'public.guide_events'::regclass) then
    raise exception '108: RLS not enabled on guide_events';
  end if;
end $$;

commit;

-- Verification (after apply):
-- select count(*) from guide_events;                                   -- 0
-- select public.guide_stats('202611/synchronic-constellation', now() - interval '30 days');
