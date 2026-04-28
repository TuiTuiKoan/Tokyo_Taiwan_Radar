-- 027_smoke_test.sql
-- Smoke test for admin_list_users() RPC function
-- Execute in Supabase Dashboard → SQL Editor

-- STEP 1: Verify function exists
select proname, prosrc from pg_proc 
where proname = 'admin_list_users' 
  and pronamespace = (select oid from pg_namespace where nspname = 'public');

-- STEP 2: No claim → should raise 42501
select set_config('request.jwt.claim.sub', '', true);
select admin_list_users();
-- Expected: ERROR 42501: admin privileges required
-- Context: PL/pgSQL function public.admin_list_users()

-- STEP 3: Admin user → should return rows
-- First, get an admin user_id
with admin_user as (
  select user_id from public.user_roles where role = 'admin' limit 1
)
select
  (select user_id from admin_user) as test_user_id,
  admin_user.user_id as config_value
from admin_user
into temp table admin_test_user;

-- Apply admin user_id to claim and execute
select set_config('request.jwt.claim.sub', (select config_value::text from admin_test_user), true);
select count(*) as user_count from admin_list_users();
-- Expected: INTEGER >= 1 (number of users in auth.users table)

-- STEP 4: Non-admin user → should raise 42501
with non_admin_user as (
  select u.id from auth.users u 
  left join public.user_roles r on r.user_id = u.id and r.role = 'admin'
  where r.user_id is null limit 1
)
select
  (select id from non_admin_user) as test_user_id,
  (select id::text from non_admin_user) as config_value
from non_admin_user
into temp table non_admin_test_user;

-- Apply non-admin user_id to claim and execute
select set_config('request.jwt.claim.sub', (select config_value from non_admin_test_user), true);
select admin_list_users();
-- Expected: ERROR 42501: admin privileges required

-- STEP 5: Return type validation
-- Reset to admin user and verify column types
select set_config('request.jwt.claim.sub', (select config_value::text from admin_test_user), true);
select
  id::text as id_type_text,
  email::text as email_type_text,
  created_at::timestamptz as created_at_type_ts,
  last_sign_in_at::timestamptz as last_sign_in_at_type_ts,
  role::text as role_type_text
from admin_list_users() limit 1;
-- Expected: All columns present with correct types (uuid→text, text, timestamptz×2, text)

-- Cleanup temp tables
drop table if exists admin_test_user;
drop table if exists non_admin_test_user;
