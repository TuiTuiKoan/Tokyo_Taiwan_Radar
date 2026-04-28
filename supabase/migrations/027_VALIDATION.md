# 027 Migration Validation — Four-Step Test

## Overview
驗證 `admin_list_users()` RPC 函式在四種場景下的行為：
1. ✅ No claim → 42501 (已驗證 2026-04-29)
2. ✅ Admin user → success (已驗證 2026-04-29)
3. ✅ Non-admin user → 42501 (已驗證 2026-04-29：ERROR 42501: admin privileges required)
4. ⏳ Return type validation (awaiting Step 5 test execution)

---

## Step 3: Non-Admin User Should Fail

執行以下 SQL 在 Supabase Dashboard → SQL Editor：

```sql
-- Get a non-admin user ID
select u.id from auth.users u 
left join public.user_roles r on r.user_id = u.id and r.role = 'admin'
where r.user_id is null limit 1;
```

複製查詢結果的 UUID，然後執行：

```sql
select set_config('request.jwt.claim.sub', '<NON_ADMIN_UUID>', true);
select admin_list_users();
```

**預期結果：** `ERROR 42501: admin privileges required`

---

## Step 4: Return Type Validation

取用 Step 3 中的 admin UUID，執行：

```sql
select set_config('request.jwt.claim.sub', '<ADMIN_UUID>', true);
select 
  id,
  email,
  created_at,
  last_sign_in_at,
  role
from admin_list_users() limit 1;
```

**預期結果：**
| Column | Type |
|--------|------|
| id | uuid |
| email | text |
| created_at | timestamp with time zone |
| last_sign_in_at | timestamp with time zone |
| role | text |

---

## Summary

| Step | Status | Result |
|------|--------|--------|
| 1. Function exists | ✅ | Function found in pg_proc |
| 2. No claim → 42501 | ✅ | ERROR 42501 raised |
| 3. Admin user → success | ✅ | Row count returned |
| 4. Non-admin → 42501 | ⏳ | Awaiting test |
| 5. Return type check | ⏳ | Awaiting test |

**Next:** Execute Step 3 test, report result.
