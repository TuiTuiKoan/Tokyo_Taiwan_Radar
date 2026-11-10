-- ============================================================
-- 106: advisor_security_hardening
-- Fixes the security findings of the 2026-11-10 Supabase advisor run that can
-- be fixed without changing behaviour (spec: docs/specs/active/
-- supabase-advisor-hardening/proposal.md, tracked in #627).
--
--   1. public.admin_list_users()   SECURITY DEFINER, reads auth.users.
--        REVOKE EXECUTE from PUBLIC and anon. authenticated and service_role
--        keep it: web/app/[locale]/admin/page.tsx and admin/users/page.tsx call
--        it with the signed-in user's session. The body still raises 42501 for
--        non-admins; the ACL is the second line of defence.
--   2. public.rls_auto_enable()    event-trigger function created by the
--        Supabase Dashboard (event trigger ensure_rls). REVOKE EXECUTE from
--        PUBLIC, anon, authenticated; service_role keeps it. PostgreSQL does
--        not check EXECUTE when it fires an event trigger, so ensure_rls keeps
--        working (verified on PostgreSQL 16 in
--        scraper/tests/test_advisor_hardening.py).
--   3. search_path (lint 0011): ALTER FUNCTION ... SET search_path = pg_catalog
--        on public.is_admin() and the four *_updated_at trigger functions.
--        Their bodies only use pg_catalog objects (and public.user_roles,
--        schema-qualified, in is_admin). No function is dropped or replaced, so
--        OIDs and every dependent policy/trigger stay bound.
--
-- NOT CHANGED ON PURPOSE:
--   public.is_admin() and public.admin_reports_maintenance_active() keep
--   EXECUTE for anon. Policies that apply to PUBLIC call them (events:
--   "Admins read all events"; the RESTRICTIVE *_maint_block_* policies on
--   event_reports, works, ...). EXECUTE is checked against the calling role
--   while the policy expression runs, so revoking anon would turn anonymous
--   reads of events and anonymous report submissions into 42501. Both return
--   only a boolean. Revoking them needs every is_admin() policy moved to
--   TO authenticated first (tracked in #628).
--
-- WHY ALTER FUNCTION AND NOT CREATE OR REPLACE:
--   CREATE OR REPLACE FUNCTION resets proconfig, so a later body edit of
--   is_admin() would silently drop the search_path again (088 did exactly
--   that). Anyone who rewrites these bodies must repeat
--   SET search_path = pg_catalog. The COMMENTs below say so.
--
-- APPLY: Supabase Dashboard -> SQL Editor as postgres. Self-contained
-- begin; ... commit;. The dry-run copy lives in docs/specs/active/
-- supabase-advisor-hardening/dryrun/ (same text, trailing rollback;).
-- Idempotent: safe to run more than once. The trailing DO block fails the
-- whole transaction if any ACL or proconfig differs from the list above.
-- APPLY STATUS: NOT YET APPLIED.
-- ============================================================

begin;

-- 1. admin_list_users(): authenticated + service_role only.
revoke execute on function public.admin_list_users() from public, anon;
grant execute on function public.admin_list_users() to authenticated, service_role;

-- 2. rls_auto_enable(): service_role only (event trigger needs no EXECUTE).
revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
grant execute on function public.rls_auto_enable() to service_role;

-- 3. Fixed search_path. ALTER FUNCTION keeps OID, owner, ACL and dependents.
alter function public.is_admin() set search_path = pg_catalog;
alter function public.set_creators_updated_at() set search_path = pg_catalog;
alter function public.set_updated_at() set search_path = pg_catalog;
alter function public.update_announcements_updated_at() set search_path = pg_catalog;
alter function public.works_set_updated_at() set search_path = pg_catalog;

comment on function public.admin_list_users() is
  'Admin-only RPC; uses auth.uid() first, then request.jwt.claim.sub fallback for SQL Editor testing. EXECUTE: authenticated and service_role only (migration 106); PUBLIC and anon are revoked.';

comment on function public.is_admin() is
  'RLS helper. EXECUTE is intentionally kept for anon: policies that apply to PUBLIC call it, and EXECUTE is checked against the calling role, so revoking anon breaks anonymous reads of events (see #628). Rewriting the body must use CREATE OR REPLACE ... SET search_path = pg_catalog, because CREATE OR REPLACE resets proconfig (migration 106).';

comment on function public.admin_reports_maintenance_active() is
  'Decision-16a maintenance-lock predicate. EXECUTE is intentionally kept for anon: the RESTRICTIVE *_maint_block_* policies apply to PUBLIC, and anonymous event_reports INSERT evaluates it. Returns only a boolean. Keep SET search_path = pg_catalog when rewriting the body (migration 106).';

comment on function public.rls_auto_enable() is
  'Event-trigger function behind ensure_rls, managed by the Supabase Dashboard (auto-enable RLS). Not callable through the API: EXECUTE is service_role only (migration 106). Toggling the Dashboard feature may recreate it with default grants; if the advisor lists it again, rerun migration 106.';

do $$
declare
  fn regprocedure;
  cfg text[];
begin
  -- admin_list_users: signed-in users and service_role only.
  fn := 'public.admin_list_users()'::regprocedure;
  if has_function_privilege('anon', fn, 'EXECUTE') then
    raise exception '106: % still executable by anon/PUBLIC', fn;
  end if;
  if not has_function_privilege('authenticated', fn, 'EXECUTE')
     or not has_function_privilege('service_role', fn, 'EXECUTE') then
    raise exception '106: % lost authenticated/service_role EXECUTE', fn;
  end if;

  -- rls_auto_enable: service_role only.
  fn := 'public.rls_auto_enable()'::regprocedure;
  if has_function_privilege('anon', fn, 'EXECUTE')
     or has_function_privilege('authenticated', fn, 'EXECUTE') then
    raise exception '106: % still executable by anon/authenticated/PUBLIC', fn;
  end if;
  if not has_function_privilege('service_role', fn, 'EXECUTE') then
    raise exception '106: % lost service_role EXECUTE', fn;
  end if;

  -- Policy helpers must stay executable by every API role.
  foreach fn in array array[
    'public.is_admin()'::regprocedure,
    'public.admin_reports_maintenance_active()'::regprocedure
  ] loop
    if not has_function_privilege('anon', fn, 'EXECUTE')
       or not has_function_privilege('authenticated', fn, 'EXECUTE')
       or not has_function_privilege('service_role', fn, 'EXECUTE') then
      raise exception '106: % must stay executable by anon/authenticated/service_role', fn;
    end if;
  end loop;

  -- Every function in scope has the fixed search_path.
  foreach fn in array array[
    'public.is_admin()'::regprocedure,
    'public.set_creators_updated_at()'::regprocedure,
    'public.set_updated_at()'::regprocedure,
    'public.update_announcements_updated_at()'::regprocedure,
    'public.works_set_updated_at()'::regprocedure,
    'public.admin_list_users()'::regprocedure,
    'public.admin_reports_maintenance_active()'::regprocedure,
    'public.rls_auto_enable()'::regprocedure
  ] loop
    select p.proconfig into cfg from pg_proc p where p.oid = fn;
    if cfg is null or not ('search_path=pg_catalog' = any (cfg)) then
      raise exception '106: % proconfig is %, expected search_path=pg_catalog', fn, cfg;
    end if;
  end loop;
end;
$$;

commit;
