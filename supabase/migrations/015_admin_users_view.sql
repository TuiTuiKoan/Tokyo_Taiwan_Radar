-- 015_admin_users_view.sql
-- Secure admin-only view of all registered users + their roles.
-- Returns data only when the calling session passes is_admin() = true.
-- Run in Supabase Dashboard → SQL Editor

create or replace view public.admin_users_view as
select
  u.id,
  u.email,
  u.created_at,
  u.last_sign_in_at,
  r.role                   -- null when user has no user_roles entry
from auth.users u
left join public.user_roles r on r.user_id = u.id
where (select public.is_admin())
order by u.created_at desc;

comment on view public.admin_users_view is
  'Admin-only view of all auth users joined with their roles. '
  'Returns 0 rows for non-admins. Do not expose to public.';

grant select on public.admin_users_view to authenticated;

-- Verification (run as service role to confirm view works):
-- select count(*) from admin_users_view;
