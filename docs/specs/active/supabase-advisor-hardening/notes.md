# Notes — production before-image（2026-11-10，Supabase MCP 唯讀查詢）

## Advisor 摘要（2026-11-10 11:03 UTC）

Security：
- WARN 0011 `function_search_path_mutable` ×5：`is_admin`、`set_creators_updated_at`、`update_announcements_updated_at`、`works_set_updated_at`、`set_updated_at`
- WARN 0028 `anon_security_definer_function_executable` ×4、WARN 0029 `authenticated_security_definer_function_executable` ×4：`admin_list_users`、`admin_reports_maintenance_active`、`is_admin`、`rls_auto_enable`
- WARN `auth_leaked_password_protection` ×1
- INFO 0008 `rls_enabled_no_policy` ×3：`field_corrections_audit`、`line_subscribers`、`llm_cache`（刻意 service-role-only）

Performance：
- WARN 0003 `auth_rls_initplan` ×21（下表）
- WARN 0006 `multiple_permissive_policies` ×37
- INFO 0001 `unindexed_foreign_keys` ×7（下表）
- INFO 0005 `unused_index` ×18（本 spec 不處理）

## 函式（改前）

| 函式 | owner | prosecdef | proconfig | proacl |
| --- | --- | --- | --- | --- |
| `admin_list_users()` | postgres | true | `search_path=pg_catalog` | `{postgres=X, anon=X, authenticated=X, service_role=X}` |
| `admin_reports_maintenance_active()` | postgres | true | `search_path=pg_catalog` | `{postgres=X, anon=X, authenticated=X, service_role=X}` |
| `is_admin()` | postgres | true | NULL | `{=X, postgres=X, anon=X, authenticated=X, service_role=X}` |
| `rls_auto_enable()` | postgres | true | `search_path=pg_catalog` | `{=X, postgres=X, anon=X, authenticated=X, service_role=X}` |
| `set_creators_updated_at()` | postgres | false | NULL | `{=X, postgres=X, anon=X, authenticated=X, service_role=X}` |
| `set_updated_at()` | postgres | false | NULL | 同上 |
| `update_announcements_updated_at()` | postgres | false | NULL | 同上 |
| `works_set_updated_at()` | postgres | false | NULL | 同上 |

- `is_admin()` 本體：`select exists (select 1 from public.user_roles where user_id = (select auth.uid()) and role = 'admin')`，`LANGUAGE sql STABLE SECURITY DEFINER`。
- `admin_list_users()` 本體先檢查 `coalesce(auth.uid(), request.jwt.claim.sub)` 與 `user_roles.role = 'admin'`，不符時 `raise 42501`；既有 comment 為 "Admin-only RPC; uses auth.uid() first, then request.jwt.claim.sub fallback for SQL Editor testing."。
- `rls_auto_enable()` 回傳 `event_trigger`，由 event trigger `ensure_rls`（`ddl_command_end`，enabled `O`）呼叫；repo 裡沒有建立它的 migration（Dashboard 建立）。
- 4 個 trigger 函式本體只有 `NEW.updated_at = now()`。

呼叫者：
- `admin_list_users`：`web/app/[locale]/admin/page.tsx:146`、`web/app/[locale]/admin/users/page.tsx:48`，都用 `@/lib/supabase/server` 的使用者 session client（authenticated）。
- `is_admin()` 被 policy 引用：`events`（Admins read all/insert/update/delete）、`category_corrections`、兩張 archive 表、`creators`、`daily_quality_metrics`、`llm_pricing`、`llm_usage`、`source_exclusion_hits`、`source_exclusions`。其中多條是 `TO public`。
- `admin_reports_maintenance_active()` 被 6 張寫入表的 RESTRICTIVE `*_maint_block_*` policy 引用，`TO public`。`anon` 送 `event_reports` 時會執行它。

## 21 條 initplan policy（改前）

`ADMIN` = `EXISTS (SELECT 1 FROM user_roles WHERE user_roles.user_id = auth.uid() AND user_roles.role = 'admin')`。全部是 PERMISSIVE。

| # | 表 | policy | cmd | roles | USING | WITH CHECK | 本 spec 處理 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | user_roles | Users read own role | SELECT | public | `auth.uid() = user_id` | — | 改寫，roles 不變 |
| 2 | account_usage | Users read own account usage | SELECT | authenticated | `auth.uid() = user_id` | — | 改寫 |
| 3 | event_reports | Admins can view reports | SELECT | public | ADMIN | — | 改寫，TO authenticated |
| 4 | event_reports | Admins can update reports | UPDATE | public | ADMIN | — | 改寫，TO authenticated |
| 5 | scraper_runs | Admins read scraper_runs | SELECT | public | ADMIN | — | 改寫，TO authenticated |
| 6 | research_reports | Admins read research_reports | SELECT | public | ADMIN | — | 改寫，TO authenticated |
| 7 | research_reports | Admins can update research_reports | UPDATE | public | ADMIN | — | 改寫，TO authenticated |
| 8 | research_reports | Admins update research_reports | UPDATE | public | ADMIN | — | **刪除**（與 #7 相同） |
| 9 | research_sources | Admins can read research_sources | SELECT | public | ADMIN | — | 改寫，TO authenticated |
| 10 | research_sources | Admins can update research_sources | UPDATE | public | ADMIN | — | 改寫，TO authenticated |
| 11 | research_sources | Service role can write research_sources | ALL | public | `auth.role() = 'service_role'` | — | **刪除**（service_role 略過 RLS） |
| 12 | event_views | Admins read event_views | SELECT | public | ADMIN | — | 改寫，TO authenticated |
| 13 | creator_events | Admins manage creator_events | ALL | public | ADMIN | — | 改寫，TO authenticated |
| 14 | aeo_visits | Admins read aeo_visits | SELECT | public | ADMIN | — | 改寫，TO authenticated |
| 15 | announcements | announcements_admin_all | ALL | public | ADMIN | ADMIN | 改寫，TO authenticated |
| 16 | announcement_events | announcement_events_admin_all | ALL | public | ADMIN | ADMIN | 改寫，TO authenticated |
| 17 | field_corrections | Admin full access on field_corrections | ALL | authenticated | ADMIN | ADMIN | 改寫 |
| 18 | selection_reason_corrections | admin_full_src | ALL | authenticated | ADMIN | ADMIN | 改寫 |
| 19 | quota_snapshots | Admins can view quota_snapshots | SELECT | authenticated | ADMIN | — | 改寫 |
| 20 | works | Admins can manage works | ALL | public | ADMIN | ADMIN | 改寫，TO authenticated |
| 21 | app_settings | Admin full access on app_settings | ALL | authenticated | ADMIN | ADMIN | 改寫 |

另外刪除 `source_exclusions.source_exclusions_admin_select`（SELECT、authenticated、`is_admin()`），它被同表 `source_exclusions_admin_all`（ALL、authenticated、`is_admin()`／`is_admin()`）涵蓋。

不動：所有 RESTRICTIVE policy（`*_maint_block_*`、`app_settings_lock_key_immutable`、`event_reports_machine_tokens_block_insert`）、公開讀取與 INSERT policy。

## 7 個未建索引的外鍵

| 表 | 外鍵 | 欄位 | 參照 |
| --- | --- | --- | --- |
| announcements | announcements_author_id_fkey | author_id | auth.users |
| app_settings | app_settings_updated_by_fkey | updated_by | auth.users |
| category_corrections | category_corrections_corrected_by_fkey | corrected_by | auth.users |
| field_corrections | field_corrections_corrected_by_fkey | corrected_by | auth.users |
| field_corrections_audit | field_corrections_audit_report_id_fkey | report_id | event_reports |
| selection_reason_corrections | selection_reason_corrections_corrected_by_fkey | corrected_by | auth.users |
| source_exclusions | source_exclusions_created_by_fkey | created_by | auth.users |

## 補充證據（2026-11-10，回應 plan-critique-1 必改 1 與建議 3、5）

- 正式環境版本：`PostgreSQL 17.6`（aarch64）。本機測試用 PostgreSQL 16；Plan Critic 依賴的行為（EXECUTE 在 executor 初始化時檢查、不相關子查詢成為 InitPlan、`ALTER POLICY`、event trigger 不檢查 EXECUTE）在 15–17 相同。
- 角色屬性：

| 角色 | super | bypassrls | inherit | login |
| --- | --- | --- | --- | --- |
| postgres | f | **t** | t | t |
| service_role | f | **t** | t | f |
| supabase_admin | t | t | t | t |
| anon | f | f | t | f |
| authenticated | f | f | t | f |
| authenticator | f | f | **f** | t |
| dashboard_user | f | f | t | f |
| supabase_privileged_role | f | f | t | f |

- `authenticated` 的成員：`authenticator`（inherit=false）、`postgres`（inherit=true）。`postgres` 有 BYPASSRLS，不經過 policy；`authenticator` 不繼承，只在 PostgREST `SET ROLE authenticated` 後才套用。
- 結論：刪除 `Service role can write research_sources` 不改變 `service_role` 的權限（BYPASSRLS）；改 `TO authenticated` 對 `postgres`、`service_role`、`supabase_admin` 沒有影響。
- `user_roles` 的 SELECT：`anon=t`、`authenticated=t`。所以 Plan Critic 第 4 點的「anon 報錯變成 0 列」在正式環境不會發生：改前 anon 在 inline EXISTS 只看到 0 列（`user_roles` 的 RLS），改後 policy 不套用，同樣 0 列。測試 fixture 要給 anon 這個 SELECT，行為矩陣應**完全相等**。
- 沒有任何 public 表設了 FORCE ROW LEVEL SECURITY。
- `reltuples`（估計列數；-1 表示從未 analyze，實際很少）：

| 表 | reltuples |
| --- | --- |
| announcements | 37 |
| app_settings | -1（2 列） |
| category_corrections | 282 |
| field_corrections | 12601 |
| field_corrections_audit | 1416 |
| selection_reason_corrections | -1（2 列） |
| source_exclusions | 35 |
| user_roles | 2 |
| aeo_visits | 112117 |
| event_views | 12434 |

  七個外鍵索引中最大的是 `field_corrections`（約 1.3 萬列），一般 `CREATE INDEX` 的 ShareLock 只會維持很短的時間。
- `rls_auto_enable()` 完整定義見本檔「函式（改前）」一節與 106 的測試 fixture；event trigger `ensure_rls` 監聽 `ddl_command_end`。

## 逐字 policy（engineer 查詢，2026-11-10）

來源：Supabase MCP 唯讀 `select … from pg_policies`（PostgreSQL 17.6）。17 張表共 43 條 policy；`roles` 是 `roles::text`；`USING`／`WITH CHECK` 保留 `pg_policies` 輸出的換行與縮排。107 的 `DO` 區塊把空白收成單一空格再比對，並把 `( SELECT auth.uid() AS uid)` 視為 `@UID@`。

轉錄驗證：用同一個正規化在 production 與本檔資料各算 `md5(string_agg(t|p|pm|c|r|qual|with_check order by t,p))`，都是 `bba798042ca5853f9dfb37be41f90a50`（43 列）。


### account_usage

**Users read own account usage** — PERMISSIVE, SELECT, roles `{authenticated}`

```sql
-- USING
(auth.uid() = user_id)
-- WITH CHECK
NULL
```


### aeo_visits

**Admins read aeo_visits** — PERMISSIVE, SELECT, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
NULL
```

**Anyone can insert aeo_visit** — PERMISSIVE, INSERT, roles `{public}`

```sql
-- USING
NULL
-- WITH CHECK
true
```


### announcement_events

**announcement_events_admin_all** — PERMISSIVE, ALL, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
```

**announcement_events_public_read** — PERMISSIVE, SELECT, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM announcements a
  WHERE ((a.id = announcement_events.announcement_id) AND (a.published_at IS NOT NULL) AND (a.published_at <= now()))))
-- WITH CHECK
NULL
```


### announcements

**announcements_admin_all** — PERMISSIVE, ALL, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
```

**announcements_public_read** — PERMISSIVE, SELECT, roles `{public}`

```sql
-- USING
((published_at IS NOT NULL) AND (published_at <= now()))
-- WITH CHECK
NULL
```


### app_settings

**Admin full access on app_settings** — PERMISSIVE, ALL, roles `{authenticated}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
```

**app_settings_lock_key_immutable** — RESTRICTIVE, ALL, roles `{authenticated}`

```sql
-- USING
(key <> 'admin_reports_cleanup_maintenance'::text)
-- WITH CHECK
(key <> 'admin_reports_cleanup_maintenance'::text)
```


### creator_events

**Admins manage creator_events** — PERMISSIVE, ALL, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
NULL
```


### event_reports

**Admins can update reports** — PERMISSIVE, UPDATE, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
NULL
```

**Admins can view reports** — PERMISSIVE, SELECT, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
NULL
```

**Anyone can submit reports** — PERMISSIVE, INSERT, roles `{public}`

```sql
-- USING
NULL
-- WITH CHECK
true
```

**event_reports_machine_tokens_block_insert** — RESTRICTIVE, INSERT, roles `{anon,authenticated}`

```sql
-- USING
NULL
-- WITH CHECK
(NOT (EXISTS ( SELECT 1
   FROM unnest(event_reports.report_types) token(value)
  WHERE ((token.value = ANY (ARRAY['scopeReviewNonJapan'::text, 'auto_security_prompt_injection'::text])) OR (token.value ~~ 'scopeDecision:%'::text) OR (token.value ~~ 'scopeRegion:%'::text) OR (token.value ~~ 'scopeHash:%'::text) OR (token.value ~~ 'securityHash:%'::text) OR (token.value ~~ 'securitySeverity:%'::text)))))
```

**event_reports_maint_block_delete** — RESTRICTIVE, DELETE, roles `{public}`

```sql
-- USING
(NOT admin_reports_maintenance_active())
-- WITH CHECK
NULL
```

**event_reports_maint_block_insert** — RESTRICTIVE, INSERT, roles `{public}`

```sql
-- USING
NULL
-- WITH CHECK
(NOT admin_reports_maintenance_active())
```

**event_reports_maint_block_update** — RESTRICTIVE, UPDATE, roles `{public}`

```sql
-- USING
(NOT admin_reports_maintenance_active())
-- WITH CHECK
(NOT admin_reports_maintenance_active())
```


### event_views

**Admins read event_views** — PERMISSIVE, SELECT, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
NULL
```

**Anyone can insert event_view** — PERMISSIVE, INSERT, roles `{public}`

```sql
-- USING
NULL
-- WITH CHECK
true
```


### field_corrections

**Admin full access on field_corrections** — PERMISSIVE, ALL, roles `{authenticated}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
```

**field_corrections_maint_block_delete** — RESTRICTIVE, DELETE, roles `{public}`

```sql
-- USING
(NOT admin_reports_maintenance_active())
-- WITH CHECK
NULL
```

**field_corrections_maint_block_insert** — RESTRICTIVE, INSERT, roles `{public}`

```sql
-- USING
NULL
-- WITH CHECK
(NOT admin_reports_maintenance_active())
```

**field_corrections_maint_block_update** — RESTRICTIVE, UPDATE, roles `{public}`

```sql
-- USING
(NOT admin_reports_maintenance_active())
-- WITH CHECK
(NOT admin_reports_maintenance_active())
```


### quota_snapshots

**Admins can view quota_snapshots** — PERMISSIVE, SELECT, roles `{authenticated}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
NULL
```


### research_reports

**Admins can update research_reports** — PERMISSIVE, UPDATE, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
NULL
```

**Admins read research_reports** — PERMISSIVE, SELECT, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
NULL
```

**Admins update research_reports** — PERMISSIVE, UPDATE, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
NULL
```


### research_sources

**Admins can read research_sources** — PERMISSIVE, SELECT, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
NULL
```

**Admins can update research_sources** — PERMISSIVE, UPDATE, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
NULL
```

**Service role can write research_sources** — PERMISSIVE, ALL, roles `{public}`

```sql
-- USING
(auth.role() = 'service_role'::text)
-- WITH CHECK
NULL
```


### scraper_runs

**Admins read scraper_runs** — PERMISSIVE, SELECT, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
NULL
```


### selection_reason_corrections

**admin_full_src** — PERMISSIVE, ALL, roles `{authenticated}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
```

**selection_reason_corrections_maint_block_delete** — RESTRICTIVE, DELETE, roles `{public}`

```sql
-- USING
(NOT admin_reports_maintenance_active())
-- WITH CHECK
NULL
```

**selection_reason_corrections_maint_block_insert** — RESTRICTIVE, INSERT, roles `{public}`

```sql
-- USING
NULL
-- WITH CHECK
(NOT admin_reports_maintenance_active())
```

**selection_reason_corrections_maint_block_update** — RESTRICTIVE, UPDATE, roles `{public}`

```sql
-- USING
(NOT admin_reports_maintenance_active())
-- WITH CHECK
(NOT admin_reports_maintenance_active())
```


### source_exclusions

**source_exclusions_admin_all** — PERMISSIVE, ALL, roles `{authenticated}`

```sql
-- USING
is_admin()
-- WITH CHECK
is_admin()
```

**source_exclusions_admin_select** — PERMISSIVE, SELECT, roles `{authenticated}`

```sql
-- USING
is_admin()
-- WITH CHECK
NULL
```


### user_roles

**Users read own role** — PERMISSIVE, SELECT, roles `{public}`

```sql
-- USING
(auth.uid() = user_id)
-- WITH CHECK
NULL
```


### works

**Admins can manage works** — PERMISSIVE, ALL, roles `{public}`

```sql
-- USING
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
-- WITH CHECK
(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))
```

**Anyone can read works** — PERMISSIVE, SELECT, roles `{public}`

```sql
-- USING
true
-- WITH CHECK
NULL
```

**works_maint_block_delete** — RESTRICTIVE, DELETE, roles `{public}`

```sql
-- USING
(NOT admin_reports_maintenance_active())
-- WITH CHECK
NULL
```

**works_maint_block_insert** — RESTRICTIVE, INSERT, roles `{public}`

```sql
-- USING
NULL
-- WITH CHECK
(NOT admin_reports_maintenance_active())
```

**works_maint_block_update** — RESTRICTIVE, UPDATE, roles `{public}`

```sql
-- USING
(NOT admin_reports_maintenance_active())
-- WITH CHECK
(NOT admin_reports_maintenance_active())
```


## Table grant 與 RLS（engineer 查詢，2026-11-10）

`has_table_privilege` 在 `anon`／`authenticated`／`service_role` 上對 S/I/U/D 的結果。沒有任何表設 FORCE RLS，所有列出的表 `relrowsecurity = t`。

| 表 | anon | authenticated | service_role |
| --- | --- | --- | --- |
| `account_usage` | 無 | SELECT | SIUD |
| `creators` | 無 | SIUD | SIUD |
| 其餘（`user_roles`、`event_reports`、`scraper_runs`、`research_*`、`event_views`、`creator_events`、`aeo_visits`、`announcements`、`announcement_events`、`field_corrections`、`selection_reason_corrections`、`quota_snapshots`、`works`、`app_settings`、`source_exclusions`、`events`、`category_corrections`、`field_corrections_audit`） | SIUD | SIUD | SIUD |

## 其他 fixture 依據（engineer 查詢，2026-11-10）

- `auth.uid()`、`auth.role()`：`LANGUAGE sql STABLE`，`coalesce(nullif(current_setting('request.jwt.claim.sub'|'request.jwt.claim.role', true), ''), (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub'|'role'))`，`::uuid`／`::text`。完整定義在 `scraper/tests/test_advisor_hardening.py` 的 `SUPER_SQL`。
- `*_updated_at` trigger 掛載：`update_announcements_updated_at` → `announcements`；`set_creators_updated_at` → `creators`；`works_set_updated_at` → `works`；`set_updated_at` → `events`、`organizers`、`sources`、`venues`。
- 函式 ACL：`admin_list_users`、`admin_reports_maintenance_active` 沒有 PUBLIC 項目（`{postgres,anon,authenticated,service_role}`）；`is_admin`、`rls_auto_enable` 與 4 個 trigger 函式有 `=X`（PUBLIC）。
- event trigger `ensure_rls`：`ddl_command_end`，tag `CREATE TABLE`／`CREATE TABLE AS`／`SELECT INTO`，enabled `O`，函式 `rls_auto_enable`（owner `postgres`）。其他 event trigger（`pgrst_ddl_watch`、`issue_pg_*`）屬於 `supabase_admin`，不受影響。
- 7 個 FK 的現有索引：無任何一個以該欄位開頭（`field_corrections` 只有 `event_id`、`report_id` 部分索引、`(event_id, field_name)`）。
- `admin_list_users()` COMMENT 逐字：`Admin-only RPC; uses auth.uid() first, then request.jwt.claim.sub fallback for SQL Editor testing.`；`is_admin()`、`admin_reports_maintenance_active()`、`rls_auto_enable()` 原本沒有 COMMENT。

## 本機 PostgreSQL 16 測試輸出（engineer，2026-11-10）

`cd scraper && python3 -m pytest tests/test_advisor_hardening.py -q`：34 passed。EXPLAIN（`costs off`，30000 列 `aeo_visits`）：


```text
=== aeo_visits (admin) :: before 107 ===
Seq Scan on aeo_visits
  Filter: ($0 AND (path = '/p5'::text))
  InitPlan 1 (returns $0)
    ->  Seq Scan on user_roles
          Filter: ((role = 'admin'::text) AND ((COALESCE(NULLIF(current_setting('request.jwt.claim.sub'::text, true), ''::text), ((NULLIF(current_setting('request.jwt.claims'::text, true), ''::text))::jsonb ->> 'sub'::text)))::uuid = user_id) AND (user_id = (COALESCE(NULLIF(current_setting('request.jwt.claim.sub'::text, true), ''::text), ((NULLIF(current_setting('request.jwt.claims'::text, true), ''::text))::jsonb ->> 'sub'::text)))::uuid))

=== aeo_visits (admin) :: after 107 ===
Seq Scan on aeo_visits
  Filter: ($2 AND (path = '/p5'::text))
  InitPlan 3 (returns $2)
    ->  Result
          One-Time Filter: ($1 = $0)
          InitPlan 1 (returns $0)
            ->  Result
          InitPlan 2 (returns $1)
            ->  Result
          ->  Seq Scan on user_roles
                Filter: ((user_id = $0) AND (role = 'admin'::text))

=== aeo_visits (anon) :: before 107 ===
Seq Scan on aeo_visits
  Filter: ($0 AND (path = '/p5'::text))
  InitPlan 1 (returns $0)
    ->  Seq Scan on user_roles
          Filter: ((role = 'admin'::text) AND ((COALESCE(NULLIF(current_setting('request.jwt.claim.sub'::text, true), ''::text), ((NULLIF(current_setting('request.jwt.claims'::text, true), ''::text))::jsonb ->> 'sub'::text)))::uuid = user_id) AND (user_id = (COALESCE(NULLIF(current_setting('request.jwt.claim.sub'::text, true), ''::text), ((NULLIF(current_setting('request.jwt.claims'::text, true), ''::text))::jsonb ->> 'sub'::text)))::uuid))

=== aeo_visits (anon) :: after 107 ===
Seq Scan on aeo_visits
  Filter: (false AND (path = '/p5'::text))

=== user_roles (user) :: before 107 ===
Seq Scan on user_roles
  Filter: ((COALESCE(NULLIF(current_setting('request.jwt.claim.sub'::text, true), ''::text), ((NULLIF(current_setting('request.jwt.claims'::text, true), ''::text))::jsonb ->> 'sub'::text)))::uuid = user_id)

=== user_roles (user) :: after 107 ===
Seq Scan on user_roles
  Filter: ($0 = user_id)
  InitPlan 1 (returns $0)
    ->  Result

=== account_usage (user) :: before 107 ===
Seq Scan on account_usage
  Filter: ((COALESCE(NULLIF(current_setting('request.jwt.claim.sub'::text, true), ''::text), ((NULLIF(current_setting('request.jwt.claims'::text, true), ''::text))::jsonb ->> 'sub'::text)))::uuid = user_id)

=== account_usage (user) :: after 107 ===
Seq Scan on account_usage
  Filter: ($0 = user_id)
  InitPlan 1 (returns $0)
    ->  Result
```


讀法：
- admin 型 policy 改前就是 `InitPlan 1`，每個語句評估一次；改後多幾層 `Result` InitPlan（`auth.uid()` 被拆成 `$0`、`$1`），每語句仍只算一次，所以 `aeo_visits` 沒有可量的效能差。
- `anon` 查 `aeo_visits`：改前要規劃並執行 admin 子查詢；改後 admin policy 不再套用，計畫變成 `Filter: (false AND …)`。
- `user_roles`、`account_usage`：改前 `Filter` 內每列呼叫 `current_setting`／`jsonb` 取值；改後 `InitPlan` 一次。這才是實際省下的部分。
