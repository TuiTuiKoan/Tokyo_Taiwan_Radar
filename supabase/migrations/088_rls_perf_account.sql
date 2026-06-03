-- ============================================================
-- 088_rls_perf_account.sql
-- Fix: /account 頁面載入 30 秒以上、有時失敗歸零
--
-- 根因：public.is_admin() 未標記 STABLE（預設 VOLATILE），且 events /
-- saved_events / creators 的 RLS 政策以「裸呼叫」使用 is_admin() 與
-- auth.uid()。VOLATILE 函式 + 裸呼叫使 PostgreSQL 在 RLS 過濾時對
-- 每一列重新執行 user_roles 子查詢。/account 查詢自己的活動（含
-- is_active = false 的已關閉活動，無法靠 is_active = true 短路）以及
-- saved_events 嵌入 events 的 join，會觸發逐列評估 → 30 秒以上；
-- 超過 statement_timeout 時查詢失敗回傳空集 → 「失敗歸零」。
--
-- 修正（與 migration 015 既有的 (select public.is_admin()) 模式一致）：
--   1. 將 is_admin() 標記為 STABLE，使其結果可在單一語句內快取。
--   2. 將 RLS 政策內的 is_admin() / auth.uid() 包進 (select ...)，
--      讓 PostgreSQL 產生只評估一次的 InitPlan，而非逐列評估。
-- ============================================================

-- 1. is_admin() 標記 STABLE -------------------------------------------------
create or replace function public.is_admin()
returns boolean
language sql
security definer
stable
as $$
  select exists (
    select 1 from public.user_roles
    where user_id = (select auth.uid()) and role = 'admin'
  );
$$;

-- 2. events SELECT 政策：包進 (select ...) ----------------------------------
drop policy if exists "Admins read all events" on public.events;
create policy "Admins read all events"
  on public.events for select
  using ((select public.is_admin()));

drop policy if exists "Users read own submitted events" on public.events;
create policy "Users read own submitted events"
  on public.events for select
  to authenticated
  using (owner_user_id = (select auth.uid()));

-- 3. saved_events 政策：包進 (select ...) -----------------------------------
drop policy if exists "Users manage their own saved events" on public.saved_events;
create policy "Users manage their own saved events"
  on public.saved_events for all
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

-- 4. creators 政策：包進 (select ...) ---------------------------------------
drop policy if exists "Creators select own profile" on public.creators;
create policy "Creators select own profile"
  on public.creators for select
  to authenticated
  using (user_id = (select auth.uid()));

drop policy if exists "Admins manage creators" on public.creators;
create policy "Admins manage creators"
  on public.creators for all
  to authenticated
  using ((select public.is_admin()))
  with check ((select public.is_admin()));
