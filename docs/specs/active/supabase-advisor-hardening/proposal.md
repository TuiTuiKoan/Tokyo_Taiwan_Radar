---
slug: supabase-advisor-hardening
title: Supabase advisor 修復：SECURITY DEFINER 權限、search_path、RLS initplan 與重複 policy
status: active
branch: feat/supabase-advisor-hardening
created: 2026-11-10
tags: [db, security, performance]
---

## What（做什麼）

看板卡片：#627。

依 2026-11-10 的 Supabase security / performance advisor 結果，用兩支 migration 修掉可以安全修的項目：

1. `106_advisor_security_hardening.sql`（安全）
   - `admin_list_users()`：撤銷 `PUBLIC`、`anon` 的 EXECUTE；保留 `authenticated`、`service_role`。
   - `rls_auto_enable()`：撤銷 `PUBLIC`、`anon`、`authenticated` 的 EXECUTE；保留 `service_role`。
   - `is_admin()` 與 4 個 `*_updated_at` trigger 函式：`ALTER FUNCTION … SET search_path = pg_catalog`。
   - `is_admin()`、`admin_reports_maintenance_active()`：EXECUTE 權限不動，加 `COMMENT ON FUNCTION` 說明原因。
   - 結尾 `DO` 區塊檢查 ACL 與 `proconfig`，不符就讓整個 transaction 失敗（沿用 100 的做法）。
   - `is_admin()` 的 COMMENT 寫明：改本體必須用 `CREATE OR REPLACE … SET search_path = pg_catalog`，因為 `CREATE OR REPLACE` 會清掉 `proconfig`（088 的先例）。`rls_auto_enable()` 的 COMMENT 寫明它由 Dashboard 管理，Dashboard 切換自動 RLS 時可能被重建並恢復預設 grant，advisor 再列出時照 106 重跑。
2. `107_rls_initplan_policy_cleanup.sql`（lint 清理與小幅效能）
   - 開頭 `SET LOCAL lock_timeout = '5s'`，接著一個 `DO` 區塊逐條比對 17 張相關表的**全部** policy 改前逐字定義（`policyname`、`cmd`、`permissive`、`roles`、`qual`、`with_check`），不符就 `raise exception`，整批不動（比照 103 的 before-image check）。
   - advisor 0003 的 21 條中，19 條用 `ALTER POLICY … [TO …] USING (…) [WITH CHECK (…)]` 把 `auth.uid()` 包成 `(select auth.uid())`。`ALTER POLICY` 不能改 cmd 與 PERMISSIVE，名稱也不變，結構上就保留原語意。原本有 WITH CHECK 的才改寫 WITH CHECK，原本沒有的不新增。
   - 改寫的 admin 專用 policy 若原本是 `TO public`，改成 `TO authenticated`（`anon` 不可能通過 admin 檢查；其他不繞過 RLS 的角色要通過，得自己偽造 JWT claim，改後這條路徑關閉，是收緊）。
   - `DROP POLICY IF EXISTS` 刪除 3 條多餘的 policy：`research_reports` 的重複 UPDATE（`Admins update research_reports`）、`research_sources` 的 `Service role can write research_sources`（`service_role` 有 BYPASSRLS，見 notes）、`source_exclusions_admin_select`（已被 `source_exclusions_admin_all` 涵蓋）。
   - 語句順序：外鍵索引最先，其次各表 policy，`user_roles` 的 policy 最後。`user_roles` 被所有 admin 檢查與 `is_admin()` 讀取，最晚上 AccessExclusiveLock，持鎖最短。
   - 為 advisor 0001 列出的 7 個外鍵補索引（`CREATE INDEX IF NOT EXISTS`）；結尾 `DO` 區塊用 `pg_index.indkey` 驗證每個外鍵欄位都有前導欄位相符的索引，並驗證改後 policy 集合與預期相同、`qual`／`with_check` 裡沒有未包裝的 `auth.uid()`／`auth.role()`。

## Why（為什麼）

- `admin_list_users()` 是讀 `auth.users` 的 `SECURITY DEFINER` 函式，`anon` 可經 `/rest/v1/rpc/admin_list_users` 呼叫。函式內有 admin 檢查，目前不會外洩，但第二道防線不該依賴函式本體；web 只用登入者 session 呼叫（`web/app/[locale]/admin/page.tsx`、`admin/users/page.tsx`），所以 `anon` 不需要權限。
- `rls_auto_enable()` 是 Supabase Dashboard 建的 event trigger 函式，不該出現在 RPC 介面上；event trigger 觸發時不檢查呼叫者的 EXECUTE 權限。
- search_path 可變的函式在 `SECURITY DEFINER`（`is_admin`）下可能被物件遮蔽；trigger 函式只用到 `now()`，固定成 `pg_catalog` 沒有副作用。
- advisor 0003 列出 21 條 policy。Plan Critic 本機實測：17 條 admin 型（不相關的 `EXISTS (… user_roles … auth.uid() …)`）在 PostgreSQL 已經是 `InitPlan`，每個語句只評估一次，效能收益接近零，改寫是為了消 lint 0003，並讓 `anon` 查詢不再規劃 admin 子查詢。真正逐列重算的是 `user_roles`（`auth.uid() = user_id`）、`account_usage`（同上）和要刪除的 `research_sources` 那條（`auth.role()`）。107 屬於 lint 清理，投入控制在這個規模。
- 已知取捨：`is_admin()` 加上 `SET search_path` 後，每次呼叫多一次 GUC 設定與還原。仍有 policy 裸呼叫 `public.is_admin()` 逐列評估（events 的 insert/update/delete 等），每列成本微幅上升；量級很小，在 #628 一併改成 `(select public.is_admin())`。
- 證據與改前狀態見 `notes.md`。

## Non-Goals（不做什麼）

- 不撤銷 `is_admin()`、`admin_reports_maintenance_active()` 的 `anon` 權限：`events`、`event_reports`、`works` 等表有對 `public` role 的 policy 會呼叫它們（RESTRICTIVE 維護鎖、`Admins read all events`），撤銷會讓匿名讀活動與匿名回報變成 42501。兩者只回傳布林值。要撤銷得先把所有 `is_admin()` policy 改成 `TO authenticated`，追蹤於 #628。
- 不改 `is_admin()` 為基礎、advisor 沒列出的 policy（`events`、`category_corrections`、archive 表等）。
- 不刪 advisor 0005 列出的 18 個未使用索引：統計可能被重設過，刪除不可逆，追蹤於 #629。
- 不處理語意上必要的多重 permissive policy（例如 `events` 的公開讀取＋自己的投稿、`announcements` 的公開讀取＋admin）。
- 外洩密碼保護是 Auth 設定，不在 migration 裡，交使用者在 Dashboard 開啟，追蹤於 #630。
- `field_corrections_audit`、`line_subscribers`、`llm_cache` 的 `rls_enabled_no_policy` 是刻意的 service-role-only 設計，維持不變。

## 決定與理由（agent 依自主政策採建議值）

| 決定 | 理由 |
| --- | --- |
| 一個 PR、兩支 migration | 使用者一週審一次；兩支可分開套用，先安全後效能 |
| admin policy 保留 inline `EXISTS (… user_roles …)`，只把 `auth.uid()` 包成 `(select auth.uid())` | 最小語意變動；`user_roles` 的 RLS 讓 inline 子查詢只看到自己的列，結果和 `is_admin()` 相同 |
| 用 `ALTER POLICY`，不用 DROP 再 CREATE | Plan Critic 必改 3：cmd、PERMISSIVE、名稱在結構上不會變，也不會因名稱打錯多出 policy |
| 改前逐字定義由 engineer 以 Supabase MCP 唯讀查詢取得，寫進 `notes.md` 與 107 的 `DO` 區塊 | 轉錄錯誤只會讓 107 拒絕執行（fail-closed），不會悄悄覆蓋 |
| 0006 預期值是 9，不是評審寫的「少 3 筆」 | 改 `TO authenticated` 後，`anon`、`authenticator`、`dashboard_user`、`supabase_privileged_role` 不再套用 admin policy；逐表重算見下方 read-back 表 |
| 外鍵索引用一般 `CREATE INDEX IF NOT EXISTS`，不用 `CONCURRENTLY` | SQL Editor 以 transaction 執行；七張表都很小 |
| Plan Critic 用 Claude 的 `plan-critic` | 這個環境沒有 `codex`；同一模型家族，已在 critique 檔註明 |

## 模型分配

| Phase | 執行者 | 模型 · effort |
| --- | --- | --- |
| 0 spec、production before-image | 主對話 | Opus |
| 0 Plan Critic | `plan-critic` subagent（Codex 不可用） | Opus · high |
| 1–2 migration、測試、文件 | `engineer` subagent | Sonnet · medium |
| 3 本機 PostgreSQL 測試、`--check` | `tester` subagent | Haiku · low |
| 3 diff 審查 | 主對話 | Opus |
| 4 commit、push、PR | `validate-merge-deploy` subagent | Sonnet · medium |

## 測試（本機 PostgreSQL 16，`scraper/tests/test_advisor_hardening.py`）

沿用 `scraper/tests/test_scope_cleanup_rpc.py` 的 `_pg_bin()`／cluster fixture，沒有 PostgreSQL 時 skip。和那支測試不同的地方：migration 以**非 superuser** 的 owner 角色 `postgres_owner`（模擬 Supabase 的 `postgres`）執行，event trigger 由 superuser 建立。

- **Fixture**：17 張相關表依 `notes.md` 的逐字 policy 建出全部 policy 與正式環境的 table grant；`auth.uid()`、`auth.role()` 用 Supabase 的真實定義（同時讀 `request.jwt.claim.sub` 與 `request.jwt.claims`）；`service_role` 設 BYPASSRLS；`rls_auto_enable()` 與 event trigger `ensure_rls` 依 notes 重建。
- **行為矩陣**：5 種身分（anon、authenticated 非 admin 且有自己的列、authenticated admin、authenticated 但 `user_roles` 沒有列、service_role）× 每張表 × 4 種操作（SELECT 列數、UPDATE／DELETE 影響列數、INSERT 允許或拒絕；寫入在 savepoint 內執行後 rollback）。107 前後各取一次快照，斷言相等。正式環境 anon 有 `user_roles` 的 SELECT（見 notes），fixture 照做，所以矩陣必須完全相等，沒有允許的差異。
- **維護鎖**：鎖啟用時 authenticated admin 對 `works`、`field_corrections`、`event_reports` 的寫入被拒，停用時允許；anon INSERT `event_reports` 在 106、107 之後仍成功。
- **結構**：每張表的 policy 名稱集合等於預期；cmd、permissive 與改前相同；roles 只依計畫變動；`qual`／`with_check` 沒有未包裝的 `auth.uid()`／`auth.role()`。
- **106 權限**：anon、authenticated、service_role × 6 個函式的 `has_function_privilege` 矩陣；`admin_list_users()` 對 anon、非 admin 回 42501，admin 回傳列；`is_admin()` 的 OID 不變、`proconfig = {search_path=pg_catalog}`、`pg_depend` 的 policy 依賴仍在；anon `select count(*) from events` 仍成功。
- **Event trigger**：沒有 EXECUTE 的非 owner 角色 `CREATE TABLE` 後 `relrowsecurity = t`。
- **Trigger 函式**：4 個 `*_updated_at` 在 UPDATE 後仍更新 `updated_at`。
- **外鍵索引**：以 `pg_index.indkey` 對應外鍵欄位驗證。
- **EXPLAIN**：`aeo_visits` 形式的表在 107 前後各取一次 admin 查詢計畫，存進 notes 作為效能主張的證據。
- **冪等**：106、107 各跑兩次都成功。
- **負向**：竄改任一條 before-image，107 的 `DO` 區塊 raise，`pg_policies` 完全沒有變動。

## 套用程序與 read-back

106、107 依 100／103 慣例自帶 `begin; … commit;`。**在 SQL Editor 外面再包一層 `BEGIN; … ROLLBACK;` 沒有用，內層 `commit;` 會真的提交。** 所以 PR 另外附 `docs/specs/active/supabase-advisor-hardening/dryrun/106_advisor_security_hardening.dryrun.sql`、`107_rls_initplan_policy_cleanup.dryrun.sql`（放在 spec 資料夾，避免 `supabase/migrations/` 下出現非 migration 檔）：與正式檔逐字相同，只有檔尾是 `rollback;`，並由測試斷言兩者除檔尾外一致。107 若因 `lock_timeout` 失敗，整批 rollback，可直接重跑（冪等）。

套用後以 Supabase MCP 重跑 advisor，逐項比對：

| Lint | 改前 | 預期 |
| --- | --- | --- |
| 0011 search_path mutable | 5 | 0 |
| 0028 anon SECURITY DEFINER | 4 | 2（`is_admin`、`admin_reports_maintenance_active`） |
| 0029 authenticated SECURITY DEFINER | 4 | 3（再加 `admin_list_users`） |
| 0003 auth_rls_initplan | 21 | 0 |
| 0006 multiple permissive | 37 | 9：`events` 5、`announcements` 1、`announcement_events` 1、`works` 1、`creators` 1（都只剩 authenticated 或語意必要的組合） |
| 0001 unindexed FK | 7 | 0 |
| 0008 RLS 無 policy | 3 | 3（刻意） |
| 0005 unused index | 18 | 18～25（新建的 7 個外鍵索引在被使用前也會列入，屬預期） |
| leaked password protection | 1 | 1，使用者開啟後 0（#630） |

## 人類關卡

1. Supabase SQL Editor：執行 spec 資料夾裡的 `dryrun/106_advisor_security_hardening.dryrun.sql`、`dryrun/107_rls_initplan_policy_cleanup.dryrun.sql`，比對 read-back 查詢結果。
2. 正式套用 106，再套用 107（production 寫入，各一張卡片）。套用後 agent 以連接器重跑 advisor，依上表比對。
3. Auth 設定開啟外洩密碼保護（#630）。
4. 合併 PR（Tier 2）；建議在 migration 套用、advisor read-back 之後。
