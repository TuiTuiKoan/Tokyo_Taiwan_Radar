-- 026_admin_list_users_claim_gate.sql
-- Fix potential empty-result/false-deny behavior in SECURITY DEFINER context
-- by using request JWT claims directly for admin gating.

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
declare
  v_sub text;
  v_user_id uuid;
begin
  v_sub := nullif(current_setting('request.jwt.claim.sub', true), '');

  if v_sub is null then
    raise exception 'admin privileges required'
      using errcode = '42501';
  end if;

  v_user_id := v_sub::uuid;

  if not exists (
    select 1
    from public.user_roles r
    where r.user_id = v_user_id
      and r.role = 'admin'
  ) then
    raise exception 'admin privileges required'
      using errcode = '42501';
  end if;

  return query
  select
    u.id::uuid,
    u.email::text,
    u.created_at::timestamptz,
    u.last_sign_in_at::timestamptz,
    r.role::text
  from auth.users u
  left join public.user_roles r on r.user_id = u.id
  order by u.created_at desc;
end;
$$;

revoke all on function public.admin_list_users() from public;
grant execute on function public.admin_list_users() to authenticated;

comment on function public.admin_list_users() is
  'Admin-only RPC for listing auth users and roles. Uses request.jwt.claim.sub gate in SECURITY DEFINER context.';
