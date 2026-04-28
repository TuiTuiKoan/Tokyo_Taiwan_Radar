-- 025_harden_admin_list_users_function.sql
-- Harden function permissions/search_path for admin user listing RPC.
-- Goals:
-- 1) Keep only authenticated callers (already granted) but enforce admin gate inside function
-- 2) Use hardened search_path to reduce object shadowing risk
-- 3) Preserve existing return schema used by admin pages

create or replace function public.admin_list_users()
returns table (
  id uuid,
  email text,
  created_at timestamptz,
  last_sign_in_at timestamptz,
  role text
)
language plpgsql
security definer
set search_path = pg_catalog
as $$
begin
  -- Explicit privilege gate even though caller already checks role in app.
  if not public.is_admin() then
    raise exception 'admin privileges required'
      using errcode = '42501';
  end if;

  return query
  select
    u.id,
    u.email,
    u.created_at,
    u.last_sign_in_at,
    r.role
  from auth.users u
  left join public.user_roles r on r.user_id = u.id
  order by u.created_at desc;
end;
$$;

revoke all on function public.admin_list_users() from public;
grant execute on function public.admin_list_users() to authenticated;

comment on function public.admin_list_users() is
  'Admin-only RPC for listing auth users and roles. Hardened with explicit admin gate and search_path=pg_catalog.';
