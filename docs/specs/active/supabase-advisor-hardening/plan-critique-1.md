# Plan Critic 評審：supabase-advisor-hardening（plan-critique-1）

> 存檔說明：2026-11-10 由 Claude 的 `plan-critic` subagent（Opus · high）產出，以下逐字存檔。
> 注意：Architect 和這份批評都由 Claude 撰寫，不算取得不同模型家族的第二視角。這個環境沒有 Codex。

審查對象：`docs/specs/active/supabase-advisor-hardening/proposal.md`、`notes.md`、`tasks.md`（worktree `/home/claude/tokyo_taiwan_radar/ttr-supabase-advisor-hardening-worktree`）。

本次只做唯讀檢查，repo 內沒有改任何檔案。為了驗證幾個關鍵假設，我在 `/tmp` 起了一個用完即刪的 PostgreSQL 16 cluster 做實驗，下文標為「本機實測」。這個 cluster 已停止並刪除。

---

## 0. 八個指定風險點的結論

### 1. `admin_list_users()` 撤銷 anon、`rls_auto_enable()` 撤銷 EXECUTE：**OK**

- **`admin_list_users()`**
  - 兩個呼叫點（`web/app/[locale]/admin/page.tsx:146`、`admin/users/page.tsx:48`）都走 `web/lib/supabase/server.ts` 的 `createServerClient`（anon key 加 cookie session）。有登入 session 時，PostgREST 以 `authenticated` 執行，保留 `authenticated` 的 EXECUTE 就不會壞。
  - session 失效、請求以 anon 身分送出時：改前由函式本體丟 `42501 admin privileges required`，改後由權限層丟 `42501 permission denied for function admin_list_users`。SQLSTATE 相同，只有訊息文字不同。`users/page.tsx` 會把 `error.message` 顯示出來，這不算回歸。
  - notes 的 ACL 顯示 `admin_list_users` 本來就沒有 PUBLIC 項目，所以 `REVOKE … FROM PUBLIC` 是 no-op，無害。
- **`rls_auto_enable()`**
  - 本機實測：event trigger 的函式撤銷 PUBLIC 後，用一個沒有 EXECUTE 的非 owner 角色執行 `CREATE TABLE`，trigger 照常觸發，新表的 `relrowsecurity = t`。PostgreSQL 觸發 trigger 或 event trigger 時不檢查 EXECUTE。函式是 owner 為 postgres 的 SECURITY DEFINER，本體以 postgres 身分執行。
  - 補充：PostgREST 本來就無法直接呼叫回傳 `event_trigger` 的函式，所以這一條純粹是消 lint，實際曝險原本就是零。

### 2. 不撤銷 `is_admin()`、`admin_reports_maintenance_active()` 的 anon：**OK，判斷正確**

- 本機實測：`events` 有一條 `TO public USING ((select public.is_admin()))` 的 policy。撤銷 anon（含 PUBLIC）的 EXECUTE 後，anon 的 `select count(*) from events` 直接報 `ERROR: permission denied for function is_admin`。
- policy 運算式以呼叫者身分評估，函式的 EXECUTE 在 executor 初始化時檢查。即使包成 `(select …)` 的 InitPlan、或 OR 短路，也逃不掉這個檢查。
- `admin_reports_maintenance_active()` 被 `event_reports_maint_block_insert`（RESTRICTIVE、TO public）引用，撤銷會讓匿名回報（`web/app/actions/submit-report.ts:22`）壞掉。
- Non-Goals 的推理與 #628 的拆分都正確。

### 3. `ALTER FUNCTION is_admin() SET search_path = pg_catalog`：**OK，但需要補強**

- 本機實測：`ALTER FUNCTION … SET` 之後 OID 不變（16408 → 16408），依賴它的 policy 不受影響。
- 本體只用 `public.user_roles`、`auth.uid()`、`exists`，加上 uuid／text 的 `=`，全部可以在 `pg_catalog` 解析。
- `auth.uid()` 本身沒有固定 search_path，會沿用呼叫端的 `pg_catalog`。它的本體（`current_setting`、`nullif`、`::uuid`、`jsonb ->>`）都在 pg_catalog，也安全。
- 因為 SECURITY DEFINER 本來就不會被 inline，加上 SET 也不會失去 inline。

需要補強兩點：

1. migration 088 曾用 `create or replace function public.is_admin()` 重寫本體，而 `CREATE OR REPLACE` 會清掉 `proconfig`。之後任何人照 088 的寫法改 `is_admin()`，search_path 會悄悄消失。106 的 COMMENT 與 `database.instructions.md` 要寫明「改本體必須帶 `SET search_path = pg_catalog`」。
2. 帶 SET 的函式每次呼叫都會多一次 GUC 的設定與還原。仍有 policy 以裸呼叫 `public.is_admin()` 逐列評估：`004_admin_rls` 的 events insert/update/delete、`005`、`013`、`041`、`046`、`086`。每列成本會微幅上升。量級很小，但應在 #628 一併處理（全部包成 `(select public.is_admin())`），並在 proposal 註明這是已知取捨。

### 4. admin policy 從 `TO public` 改成 `TO authenticated`：**OK，但需要補強證據**

- **不受影響**：`postgres`（table owner，未 FORCE RLS）、`service_role`（BYPASSRLS）、`supabase_admin`（superuser）。它們本來就不經過這些 policy。
- **anon**：改前 policy 套用到 anon，但 `auth.uid()` 為 NULL，永遠過不了檢查；改後 policy 不再套用，結果都是看不到列。
- 有一個語意差異要寫進測試的預期值。本機實測：anon 對 `user_roles` 沒有 SELECT 權限時，`TO public` 的 inline EXISTS 會讓 anon 查詢**報錯**（`permission denied for table user_roles`）；改成 `TO authenticated` 後變成**回傳 0 列**。正式環境 anon 是否持有 `user_roles` 的 SELECT，notes 沒記錄。
- **authenticator、dashboard_user、supabase_privileged_role 等不繞過 RLS 的角色**：改前它們要通過 admin 檢查，必須在沒有 `SET ROLE authenticated` 的情況下自行把 `request.jwt.claim(s)` 設成 admin 的 sub。本機實測也確認 anon 加上 admin sub 時，在 `TO public` 下會通過檢查。改後這條路徑關閉，這是收緊，不是放寬。
- repo 內沒有任何程式走這條路徑：web 走 PostgREST 的 `authenticated`，scraper 走 `service_role`，Studio 的角色模擬也是 `set role authenticated`。
- 補強：`supabase_privileged_role` 等角色的屬性無法從 repo 驗證。before-image 應補一筆唯讀查詢：`pg_roles` 的 `rolsuper`、`rolbypassrls`、`rolinherit`，加上 `pg_auth_members` 中哪些角色是 `authenticated` 的成員。原因是 policy 的角色比對依 `has_privs_of_role` 判斷，INHERIT 成員也會命中。

### 5. 刪除三條 policy：**OK，但需要補強證據**

- **`research_reports` 的 `Admins update research_reports`**：與 #7 相同（UPDATE、PERMISSIVE、public、ADMIN、沒有 WITH CHECK），刪除後語意不變。前提是兩者的 `qual` 逐字相同；notes 只寫了縮寫 `ADMIN`，見必改 1。
- **`Service role can write research_sources`**：`service_role` 有 BYPASSRLS，這條 policy 對它無效。其他角色要讓 `auth.role() = 'service_role'` 成立，必須持有用 service-role 簽章的 JWT，而 PostgREST 收到這種 JWT 會切成 `service_role`。所以刪除不改變任何人的權限。不過 notes 沒有 `service_role` 的 `rolbypassrls` read-back，刪除理由完全建立在這個屬性上，應補一行唯讀證據。
- **`source_exclusions_admin_select`**：與 `source_exclusions_admin_all` 的 USING 都是 `is_admin()`、角色都是 authenticated，ALL 已經涵蓋 SELECT，刪除安全。

### 6. 鎖與中斷風險：**有問題**

- 本機實測鎖等級：`ALTER POLICY`／`CREATE POLICY`／`DROP POLICY` 都取 **AccessExclusiveLock**；`CREATE INDEX` 取 **ShareLock**。兩者都持有到 commit。
- 107 會改 `user_roles` 的 policy（#1）。`user_roles` 被所有 admin policy 的 inline EXISTS 和 `is_admin()` 本體讀取，`events` 的 `Admins read all events` 也會讓 anon 查詢執行 `is_admin()`。
- 107 一旦對 `user_roles` 取得 AccessExclusiveLock，**全站對 events 的公開查詢都會排隊，直到 107 commit**。
- 如果 107 接著在另一張表（例如 `aeo_visits` 上有長查詢）等鎖，網站會整個卡住。多表累積鎖還會增加和並行寫入（scraper）死鎖的機會。
- proposal 沒有 `lock_timeout`，也沒有規定語句順序，**這是阻擋項**（必改 2）。
- 外鍵索引不用 `CONCURRENTLY`：可接受。SQL Editor 是 transaction，且這些表很小。但「七張表都很小」沒有證據，notes 應補 `reltuples`。ShareLock 也會擋這七張表的寫入直到 commit，交易要保持短。

### 7. 測試計畫：**有問題**

proposal 本身沒有測試段落，只有 `tasks.md` M3 一句「改寫前後可見列數相同」。比照 `scraper/tests/test_scope_cleanup_rpc.py` 的作法有三個缺口：

1. 那支測試的 `SCHEMA` 是手寫的最小 schema。這次要驗證的是**正式環境的 policy 集合**，而正式環境已經和 migration 檔脫節：`rls_auto_enable` 和重複的 UPDATE policy 都不在 repo 裡。fixture 必須以正式環境逐字的 policy 定義為準。
2. 那支測試以 superuser `postgres` 執行 migration，Supabase 的 `postgres` 不是 superuser，ACL 與 owner 錯誤會被遮蔽。
3. 只比較「可見列數」，蓋不到 UPDATE／DELETE 影響列數、INSERT 允許或拒絕、WITH CHECK 與維護鎖。

具體要覆蓋的斷言見必改 7。

### 8. 範圍：**106 合理；107 的效能理由不成立，應縮小作法**

本機實測：notes 的 `ADMIN` 形式是不相關的 `EXISTS (SELECT 1 FROM user_roles WHERE user_id = auth.uid() AND role = 'admin')`。在 `TO public` 的 SELECT policy 下，計畫**原本就是 `InitPlan 1` 加 `Filter: $0`**，每個語句只評估一次，`auth.uid()` 只在掃描 `user_roles`（幾列）時評估。

所以 21 條裡 17 條 admin 型 policy 的實際效能收益接近零。真正逐列重算的只有：

- #1 `user_roles`：`auth.uid() = user_id`
- #2 `account_usage`：同上
- #11 `research_sources`：`auth.role()`（本來就要刪）

proposal 第 32 行「21 條 policy 每列重算 `auth.uid()`，`aeo_visits`（約 11.5 萬列）會受影響」與實測不符，必須改寫（必改 4）。17 條 admin 型的改寫仍有價值（消 advisor lint 0003、讓 anon 查詢不再規劃 admin EXISTS），但屬於 lint 清理，不是效能修復。

更簡單的作法：19 條「DROP 再 CREATE」改成 `ALTER POLICY`。本機實測 `ALTER POLICY adm ON t TO authenticated USING (…)` 可以一次改角色與 USING。`ALTER POLICY` 無法改 cmd 與 PERMISSIVE，所以「保留 cmd、PERMISSIVE、名稱」在結構上就成立，不靠人工抄寫（必改 3）。鎖等級相同，但 SQL 行數減半，也不會有 policy 名稱打錯而多出新 policy 的風險。

---

## 1. 商業主軸對齊：🟡 弱對齊

- 對應「資料正確性與安全」的防護層。106 為讀取 `auth.users` 的 RPC 加上第二道防線，屬於安全衛生；107 是 lint 與小幅效能。
- 沒有偏離全日本台灣活動聚合的使命，但不直接推進 SKILL.md 商業優先序的 1–4 項。

## 2. 複雜度與價值

- **複雜度：high。** 依 SKILL.md 啟發式：2 支 migration（+2），RLS／權限變更（+2），跨約 15 張表、6 個函式、7 個索引。
- **價值：** 106 為 medium，107 為 low（見第 8 點的實測）。
- **警示：107 的複雜度大於價值。** 改用 `ALTER POLICY` 並補齊 before-image 斷言後，複雜度可以降到 medium，比值才合理。

## 3. 優先順序提醒：🟡 可延後，但不必暫停

open issue 中有更貼近主軸的項目：

- #596：merger 同名重播未合併，被 Search Console 判為重複網頁（資料品質與 SEO）
- #603、#604：organizer 回填與空值率（資料完整性，需要人工核准）
- #590：Sentry 長期錯誤 `cinemaclair_ocr` `model_not_found`（爬蟲斷流）

這個 spec 的人類關卡都很輕（dry-run、套用、按合併），不會排擠上面的工作，可以並行。但 107 的投入應控制在 lint 清理的規模，不要擴張到 #628 的範圍。

## 4. 全站架構整合分析

- 沒有新增 table、component、i18n key 或 scraper，也沒有觸及 Category／Event Form／i18n／FC／SCRAPERS 等 Guard。
- 沿用 100／101 的 `DO` 區塊 ACL 檢查與 096 的「不 DROP 函式」原則：106 用 `ALTER FUNCTION`，正確。
- 漏掉的同步點：
  - `database.instructions.md` 第 11 行已經損壞：里程碑清單重複三次，還殘留「(next = `098`)」「(next = `104`)」。M4 應整段重寫，不要再往後追加。
  - 「Functions: revoke from anon and authenticated by name」那段應補一條規則：被 `TO public` policy 引用的函式不能撤銷 anon（106 的例外理由）。

## 5. 既有 Component 復用建議：🟢 充分復用

- 測試 harness 復用 `scraper/tests/test_scope_cleanup_rpc.py` 的 `_pg_bin()`／`cluster` fixture：正確。
- 106 的 `DO` 區塊復用 100／101 的 `has_function_privilege` 迴圈：正確。
- 107 的 before-image 檢查應復用 103 的「field-by-field before-image check」思路（見必改 1）。

## 6. 建議更新後的計畫

接受 106 的範圍；107 的範圍不變，但作法依必改 1–4 修改；proposal 補上測試段落（必改 7）與 read-back 預期值（必改 6）；dry-run 卡片依必改 5 修改。

---

## 必改清單（阻擋實作）

1. **逐字 before-image 與漂移防護。**
   - notes 的 `ADMIN` 縮寫不夠用。對 107 涉及的每張表，`pg_policies` 的**所有** policy（不只 21 條），都要記下 `policyname`、`cmd`、`permissive`、`roles`、`qual`、`with_check` 的逐字文字。
   - 107 開頭加 `DO` 區塊，逐條比對預期的改前文字，不符就 `raise exception`（比照 103）。這樣可以避免「notes 拍照後到套用前」之間的漂移被悄悄覆蓋。
   - 同時把 `rls_auto_enable()` 的 `pg_get_functiondef`、4 個 trigger 函式本體、`service_role` 的 `rolbypassrls`、anon／authenticated 對 `user_roles` 的 `has_table_privilege` 寫進 notes。第一項是本機測試重現 event trigger 所需；後兩項是第 4、5 點的證據。
2. **107 的鎖控制。**
   - 開頭 `SET LOCAL lock_timeout = '5s';`（與 103 的 `lock_timeout` 一致）。
   - `user_roles` 的 #1 放在最後一條 policy 語句，讓全站必經的表最晚上鎖、持鎖最短。
   - 卡片要寫明：逾時就整批 rollback，可以直接重跑，因為 migration 是冪等的。
3. **19 條改寫改用 `ALTER POLICY … TO … USING (…) [WITH CHECK (…)]`**，不用 DROP 再 CREATE。只有刪除的 3 條用 `DROP POLICY IF EXISTS`。原本有 WITH CHECK 的 ALL policy（#15、16、17、18、20、21）必須同時改寫 WITH CHECK；原本沒有的不要新增。
4. **修正 Why 的效能主張。** 改成：admin 型 17 條已經是 InitPlan，改寫是為了消 lint 0003 與減少 anon 的規劃成本；真正逐列重算的是 #1、#2。並用本機 PG16 的 `EXPLAIN`（`aeo_visits` 形式）佐證改前與改後的計畫。
5. **dry-run 程序。**
   - 106 與 107 依 100／103 慣例自帶 `begin; … commit;`。在 SQL Editor 外面再包一層 `BEGIN; … ROLLBACK;`，內層的 `commit;` 會**真的提交**。
   - 人類關卡卡片必須寫成：「貼上全文，把檔尾的 `commit;` 改成 `rollback;` 後執行」。或者另外提供一份檔尾是 `rollback;` 的 dry-run 版本。
6. **advisor read-back 的預期值**，套用後逐項比對：
   - 0011：0 筆
   - 0003：0 筆
   - 0001：0 筆
   - 0028：剩 2 筆（`is_admin`、`admin_reports_maintenance_active`）
   - 0029：剩 3 筆（再加 `admin_list_users`）
   - 0006：比 37 少 3 筆，以實際 lint 名稱核對
   - 0005：18 筆不變

   沒有預期值，「read-back」就沒有通過標準。
7. **proposal 補上測試段落**，至少包含下列斷言（本機 PG16；migration 以非 superuser 的 owner 角色執行，event trigger 由 superuser 建立）：
   - **fixture**：依必改 1 的逐字 policy 建出 15 張表的全部 policy 與正式環境的 table grant。`auth.uid()`／`auth.role()` 用 Supabase 的真實定義，同時讀 `request.jwt.claim.sub` 與 `request.jwt.claims->>'sub'`。`service_role` 設 BYPASSRLS。
   - **行為矩陣**：5 種身分（anon、authenticated 非 admin 且有自己的列、authenticated admin、authenticated 但 `user_roles` 沒有列、service_role）× 每張表 × 4 種操作，每一格在 107 前後各取一次快照，斷言相等。4 種操作是 SELECT 列數，以及 UPDATE／DELETE 影響列數、INSERT 允許或拒絕（後三者在 savepoint 內執行後 rollback）。唯一允許的差異是第 4 點的 anon「報錯變成 0 列」，必須在測試中明列。
   - **維護鎖**：鎖啟用時，authenticated admin 對 `works`、`field_corrections`、`event_reports` 的寫入被拒；鎖停用時允許。anon INSERT `event_reports` 在 106、107 之後仍然成功。
   - **結構斷言**：每張表的 policy 名稱集合等於預期；`cmd`、`permissive` 與改前相同；`roles` 只依計畫變動；`qual`／`with_check` 中沒有未包裝的 `auth.uid()`／`auth.role()`（以 `( SELECT auth.uid() AS uid)` 正規化後比對）。
   - **106 的權限**：`has_function_privilege` 矩陣（anon、authenticated、service_role × 6 個函式）。`admin_list_users`：anon 回 SQLSTATE 42501、非 admin 回 42501、admin 回傳列。`is_admin()` 的 OID 不變、`proconfig = {search_path=pg_catalog}`、`pg_depend` 中的 policy 依賴仍在；anon 的 `select count(*) from events` 仍然成功。
   - **event trigger**：沒有 EXECUTE 的非 owner 角色 `CREATE TABLE` 後，`relrowsecurity = t`。
   - **trigger 函式**：4 個 `*_updated_at` 在 UPDATE 後仍會更新 `updated_at`。
   - **外鍵索引**：7 個索引以 `pg_index.indkey` 對應 FK 欄位驗證，不只看名稱。
   - **冪等**：106 與 107 各跑兩次都成功。
   - **負向測試**：竄改任一條 before-image，107 的 DO 區塊要 raise，而且 `pg_policies` 完全沒有變動。

## 建議清單（不阻擋）

1. `rls_auto_enable()` 由 Dashboard 管理。在 Dashboard 切換自動 RLS 功能時，平台有機會重建這個函式並恢復預設 grant。在 COMMENT 與 `database.instructions.md` 註明這件事；advisor 的 0028／0029 若再出現它，就照 106 重跑。
2. `is_admin()` 的 COMMENT 寫明「改本體必須用 `CREATE OR REPLACE … SET search_path = pg_catalog`」，見第 3 點。在 #628 補上「把裸呼叫的 `is_admin()` 包成 `(select …)`」，抵銷 SET 帶來的每列成本。
3. `CREATE INDEX IF NOT EXISTS` 只比對名稱。結尾的 `DO` 區塊用 `pg_index` 驗證七個 FK 欄位都有前導欄位相符的索引。notes 補上七張表的 `reltuples`。
4. M4 改寫 `database.instructions.md` 時，整段修正第 11 行損壞的里程碑清單，見第 4 段。
5. notes 記下正式環境的 `select version()`。本機測試是 PG16；本評審依賴的行為（EXECUTE 檢查時機、InitPlan、`ALTER POLICY`、event trigger 不檢查 ACL）在 15–17 都相同，但應留下證據。
6. #628 的替代方案：日後可以評估把 `is_admin()` 用 `ALTER FUNCTION … SET SCHEMA` 移到不對 API 公開的 schema。OID 不變，policy 不受影響，也能讓它離開 `/rest/v1/rpc`。但所有以名稱呼叫 `public.is_admin()` 的 plpgsql 本體都要一併改。這是另案，不在本 spec 做。

## 總評：**修訂後可實作**

- 106 的判斷（撤銷 `admin_list_users` 的 anon、撤銷 `rls_auto_enable` 的 EXECUTE、保留 `is_admin`／維護鎖的 anon、`ALTER FUNCTION` 固定 search_path）經本機 PG16 實測都成立。補上 COMMENT 與 read-back 預期值就可以實作。
- 107 的語意變更（改 `TO authenticated`、刪除三條 policy）是安全的，但有四個阻擋問題：
  1. 缺少逐字 before-image 與漂移檢查；
  2. 沒有 `lock_timeout`，且 `user_roles` 持鎖會卡住全站；
  3. DROP 再 CREATE 應改成 `ALTER POLICY`；
  4. 效能理由與實測不符。
- 另外，dry-run 的 `BEGIN/ROLLBACK` 包法會被檔案內的 `commit;` 擊穿，必須修改卡片。
- 依必改 1–7 修訂後即可交給 Engineer。
