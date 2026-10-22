-- ============================================================
-- 100: rpc_execute_lockdown
-- Restrict two SECURITY DEFINER functions to service_role.
--
-- NUMBERING: 099 is reserved by feat/llm-cost-reset (099_llm_usage.sql),
-- which is not on main yet. 100 avoids a collision; 099 is not skipped.
--
-- WHY THIS EXISTS:
--   The 2026-10-22 security advisor run and a live ACL check showed that
--   anon and authenticated both hold EXECUTE on:
--     public.archive_event_related_data(uuid[], text)
--       013 ran `revoke ... from public`, but Supabase's default privileges
--       had already granted EXECUTE to anon and authenticated directly.
--     public.increment_account_usage(uuid, integer, integer)
--       087 granted EXECUTE to authenticated; PUBLIC and anon also hold it.
--       It also has no fixed search_path (lint 0011).
--   No caller exists in web/, scraper/ or scripts/; both are server-side
--   helpers only, so service_role is the only role that needs EXECUTE.
--
-- Idempotent: safe to run more than once. Run as postgres in the
-- Supabase Dashboard SQL Editor; the trailing DO block fails the
-- transaction if any API role except service_role can still execute.
-- ============================================================

begin;

revoke execute on function public.archive_event_related_data(uuid[], text)
  from public, anon, authenticated;
grant execute on function public.archive_event_related_data(uuid[], text)
  to service_role;

-- All table references in the body are schema-qualified (public.account_usage).
alter function public.increment_account_usage(uuid, integer, integer)
  set search_path = pg_catalog;
revoke execute on function public.increment_account_usage(uuid, integer, integer)
  from public, anon, authenticated;
grant execute on function public.increment_account_usage(uuid, integer, integer)
  to service_role;

do $$
declare
  fn regprocedure;
begin
  foreach fn in array array[
    'public.archive_event_related_data(uuid[], text)'::regprocedure,
    'public.increment_account_usage(uuid, integer, integer)'::regprocedure
  ] loop
    if has_function_privilege('anon', fn, 'EXECUTE')
       or has_function_privilege('authenticated', fn, 'EXECUTE') then
      raise exception '100_rpc_execute_lockdown: % still executable by anon/authenticated', fn;
    end if;
    if not has_function_privilege('service_role', fn, 'EXECUTE') then
      raise exception '100_rpc_execute_lockdown: % lost service_role EXECUTE', fn;
    end if;
  end loop;
end;
$$;

commit;
