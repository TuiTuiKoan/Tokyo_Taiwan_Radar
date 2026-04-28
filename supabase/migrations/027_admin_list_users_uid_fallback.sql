-- 027_admin_list_users_uid_fallback.sql
-- Fix admin_list_users false-deny on web requests.
-- Strategy:
-- 1) Prefer auth.uid() for real PostgREST requests
-- 2) Fallback to request.jwt.claim.sub for SQL Editor simulation

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
  -- Prefer auth.uid() for real PostgREST requests.
  -- Fallback to request.jwt.claim.sub for SQL Editor simulation.
  v_user_id := auth.uid();
  
  if v_user_id is null then
    v_sub := nullif(current_setting('request.jwt.claim.sub', true), '');
    if v_sub is not null then
      begin
        v_user_id := v_sub::uuid;
      exception
        when invalid_text_representation then
          raise exception 'admin privileges required'
            using errcode = '42501';
      end;
    end if;
  end if;

  if v_user_id is null then
    raise exception 'admin privileges required'
      using errcode = '42501';
  end if;

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
  'Admin-only RPC; uses auth.uid() first, then request.jwt.claim.sub fallback for SQL Editor testing.';
