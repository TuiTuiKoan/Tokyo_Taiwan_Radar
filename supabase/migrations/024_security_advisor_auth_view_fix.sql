-- 024_security_advisor_auth_view_fix.sql
-- Security Advisor fixes:
-- 1) Remove authenticated exposure from public.admin_users_view
-- 2) Provide admin-only RPC for user listing
-- 3) Mark analytics view as security_invoker

-- Keep the existing view for backward compatibility, but revoke API access.
revoke all on table public.admin_users_view from anon, authenticated;

-- Prefer RPC for admin user listing to avoid exposing auth.users through public views.
create or replace function public.admin_list_users()
returns table (
  id uuid,
  email text,
  created_at timestamptz,
  last_sign_in_at timestamptz,
  role text
)
language sql
security definer
set search_path = public, auth
as $$
  select
    u.id,
    u.email,
    u.created_at,
    u.last_sign_in_at,
    r.role
  from auth.users u
  left join public.user_roles r on r.user_id = u.id
  where (select public.is_admin())
  order by u.created_at desc;
$$;

revoke all on function public.admin_list_users() from public;
grant execute on function public.admin_list_users() to authenticated;

-- Avoid SECURITY DEFINER view warning for analytics aggregation view.
alter view public.event_view_counts set (security_invoker = true);

-- Harden admin view as invoker too (it remains inaccessible to anon/authenticated).
alter view public.admin_users_view set (security_invoker = true);
