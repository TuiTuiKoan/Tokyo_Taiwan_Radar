-- ============================================================
-- 101: rpc_lockdown_followup
-- Follow-up to 100: two more helpers from the 2026-10-22 security advisor run.
--
--   public.db_size_summary()
--     042 revoked PUBLIC and anon, then granted EXECUTE to authenticated as
--     well as service_role. The body has no caller check, so any signed-in
--     user could read the database size and the public table names and sizes.
--     Its only caller is scraper/quota_monitor.py, which uses service_role.
--     EXECUTE is therefore restricted to service_role.
--     search_path is deliberately NOT pinned to pg_catalog: the body casts an
--     unqualified table name to regclass, which needs `public` to resolve.
--
--   public.admin_list_users_debug()
--     A leftover debug helper with no caller in web/, scraper/, scripts/ or
--     any migration (it was created outside the migration files). It only
--     echoes the caller's own JWT subject. Dropped.
--
-- Idempotent: safe to run more than once. Run as postgres in the
-- Supabase Dashboard SQL Editor; the trailing DO block fails the
-- transaction if the end state is not what is described above.
-- ============================================================

begin;

revoke execute on function public.db_size_summary()
  from public, anon, authenticated;
grant execute on function public.db_size_summary()
  to service_role;

drop function if exists public.admin_list_users_debug();

do $$
declare
  fn regprocedure := 'public.db_size_summary()'::regprocedure;
begin
  if has_function_privilege('anon', fn, 'EXECUTE')
     or has_function_privilege('authenticated', fn, 'EXECUTE') then
    raise exception '101_rpc_lockdown_followup: % still executable by anon/authenticated', fn;
  end if;
  if not has_function_privilege('service_role', fn, 'EXECUTE') then
    raise exception '101_rpc_lockdown_followup: % lost service_role EXECUTE', fn;
  end if;
  if exists (
    select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname = 'admin_list_users_debug'
  ) then
    raise exception '101_rpc_lockdown_followup: admin_list_users_debug still exists';
  end if;
end;
$$;

commit;
