-- 104_account_ai_quota.sql
-- Daily per-user and site-wide limits for the two account AI routes
-- (llm-cost-reset spec, #322).
--
-- /api/account/annotate-event (gpt-4o-mini) and /api/account/extract-from-image
-- (gpt-4o Vision) let any signed-in organizer trigger OpenAI calls. A quota gate
-- existed until 2026-06-05 (removed in 4da6dede): both routes went through
-- increment_account_usage(), which has a single annotate_count, so annotations
-- used up the 5-per-day image allowance. This migration gives each route its own
-- counter:
--
--   - account_usage.extract_count: image extractions per user per day
--     (annotate_count keeps counting annotations).
--   - consume_account_ai_quota(user, kind, per-user limit, site-wide limit):
--     locks the user's row for the day, checks the site-wide sum, then the user's
--     count, and increments. Returns the new count, -1 when the user is at the
--     limit, -2 when the site is. The day is the Japan date, so limits reset at
--     midnight JST (increment_account_usage used CURRENT_DATE, the UTC date).
--
-- The site-wide check is not serialised across users: concurrent requests from
-- different users can overshoot it by the number in flight. It is a cost ceiling,
-- not an exact count.
--
-- SECURITY INVOKER: only the web routes' service-role client calls it, and the
-- service role bypasses RLS. EXECUTE is revoked from PUBLIC, anon and
-- authenticated explicitly, because Supabase grants anon/authenticated directly
-- (see 100_rpc_execute_lockdown.sql). increment_account_usage() is left as is;
-- nothing calls it since 4da6dede, and 100 already restricted it to service_role.
-- Run in Supabase Dashboard → SQL Editor. Idempotent.

alter table public.account_usage
  add column if not exists extract_count integer not null default 0;

create or replace function public.consume_account_ai_quota(
  p_user_id uuid,
  p_kind text,
  p_limit_per_user integer,
  p_limit_system integer
)
returns integer
language plpgsql
security invoker
set search_path = pg_catalog
as $$
declare
  v_day date := (now() at time zone 'Asia/Tokyo')::date;
  v_user_count integer;
  v_system_count integer;
begin
  if p_kind not in ('annotate', 'extract') then
    raise exception 'unknown quota kind: %', p_kind using errcode = '22023';
  end if;

  insert into public.account_usage (user_id, usage_date)
  values (p_user_id, v_day)
  on conflict (user_id, usage_date) do nothing;

  select case when p_kind = 'annotate' then annotate_count else extract_count end
    into v_user_count
    from public.account_usage
   where user_id = p_user_id and usage_date = v_day
     for update;

  select coalesce(sum(case when p_kind = 'annotate' then annotate_count else extract_count end), 0)
    into v_system_count
    from public.account_usage
   where usage_date = v_day;

  if v_system_count >= p_limit_system then
    return -2;
  end if;
  if v_user_count >= p_limit_per_user then
    return -1;
  end if;

  update public.account_usage
     set annotate_count = annotate_count + (p_kind = 'annotate')::integer,
         extract_count = extract_count + (p_kind = 'extract')::integer
   where user_id = p_user_id and usage_date = v_day;

  return v_user_count + 1;
end;
$$;

revoke execute on function public.consume_account_ai_quota(uuid, text, integer, integer)
  from public, anon, authenticated;
grant execute on function public.consume_account_ai_quota(uuid, text, integer, integer)
  to service_role;

do $$
begin
  if has_function_privilege('anon', 'public.consume_account_ai_quota(uuid, text, integer, integer)', 'execute')
     or has_function_privilege('authenticated', 'public.consume_account_ai_quota(uuid, text, integer, integer)', 'execute') then
    raise exception 'consume_account_ai_quota must be executable by service_role only';
  end if;
end;
$$;
