-- ============================================================
-- 094: admin_reports_maintenance_lock
-- Decision-16a — database-level maintenance lock for the Admin
-- Reports (#204) cleanup window.
--
-- APPLY POLICY (IMPORTANT — read before running):
--   This migration is applied ONLY during an approved decision-16b
--   bring-up, and ONLY AFTER the inactive lock row has been seeded:
--     python scraper/_oneoff_admin_reports_maintenance.py seed-inactive
--   (seeds app_settings['admin_reports_cleanup_maintenance'] = {"active": false})
--   At bring-up run the four-quadrant verification below both before and
--   after an acquire/release cycle. Until decision-16b is approved this
--   file is AUTHORED, NOT APPLIED. Do NOT paste it into the SQL Editor yet.
--
-- WHAT IT DOES:
--   Adds a fail-closed predicate function + per-command RESTRICTIVE RLS
--   policies on the six writer tables touched by the cleanup. RESTRICTIVE
--   policies are ANDed with the existing PERMISSIVE ones, so while the lock
--   is active (or the row is absent / malformed) every INSERT/UPDATE/DELETE
--   by anon + authenticated is DENIED. SELECT is never touched. service_role
--   bypasses RLS entirely, so the cleanup job and service-role routes keep
--   working at statement time (intended per decision-16a).
--
--   The lock key itself is made immutable to `authenticated`, so no admin
--   browser session can flip the flag; only the service-role operator CLI
--   (scraper/_oneoff_admin_reports_maintenance.py) may seed / acquire /
--   release it.
--
-- FAIL-CLOSED SEMANTICS:
--   Writes are ALLOWED only when the lock row EXISTS and value->>'active'
--   is exactly the string 'false'. A missing row, 'active' != 'false', or a
--   malformed value all evaluate to DENY.
--
-- FOUR-QUADRANT VERIFICATION (run at bring-up, once as service_role and
-- once as a normal authenticated admin):
--   1. lock inactive + service_role  -> write SUCCEEDS
--   2. lock inactive + authenticated -> write SUCCEEDS
--   3. lock active   + service_role  -> write SUCCEEDS (bypasses RLS)
--   4. lock active   + authenticated -> write DENIED  (RESTRICTIVE blocks)
--
-- Admin must run in Supabase Dashboard -> SQL Editor.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Fail-closed predicate: TRUE = DENY writes (maintenance active).
--    Returns FALSE (allow) ONLY when the row exists AND active == 'false'.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.admin_reports_maintenance_active()
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
  -- true = DENY writes. Allow (false) ONLY when the row exists AND
  -- value->>'active' is exactly the string 'false'.
  SELECT NOT EXISTS (
    SELECT 1 FROM public.app_settings
    WHERE key = 'admin_reports_cleanup_maintenance'
      AND value->>'active' = 'false'
  );
$$;

REVOKE EXECUTE ON FUNCTION public.admin_reports_maintenance_active() FROM public;
GRANT EXECUTE ON FUNCTION public.admin_reports_maintenance_active() TO anon, authenticated;

-- ------------------------------------------------------------
-- 2. Per-command RESTRICTIVE policies on the six writer tables.
--    RESTRICTIVE => ANDed with the existing PERMISSIVE policies.
--    SELECT is intentionally NOT restricted. RLS must be enabled for a
--    RESTRICTIVE policy to take effect; each ENABLE below is idempotent
--    (these tables already have RLS on from earlier migrations).
-- ------------------------------------------------------------

-- events -----------------------------------------------------
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "events_maint_block_insert" ON public.events;
CREATE POLICY "events_maint_block_insert" ON public.events
  AS RESTRICTIVE FOR INSERT TO public
  WITH CHECK (NOT public.admin_reports_maintenance_active());
DROP POLICY IF EXISTS "events_maint_block_update" ON public.events;
CREATE POLICY "events_maint_block_update" ON public.events
  AS RESTRICTIVE FOR UPDATE TO public
  USING (NOT public.admin_reports_maintenance_active())
  WITH CHECK (NOT public.admin_reports_maintenance_active());
DROP POLICY IF EXISTS "events_maint_block_delete" ON public.events;
CREATE POLICY "events_maint_block_delete" ON public.events
  AS RESTRICTIVE FOR DELETE TO public
  USING (NOT public.admin_reports_maintenance_active());

-- event_reports ----------------------------------------------
ALTER TABLE public.event_reports ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "event_reports_maint_block_insert" ON public.event_reports;
CREATE POLICY "event_reports_maint_block_insert" ON public.event_reports
  AS RESTRICTIVE FOR INSERT TO public
  WITH CHECK (NOT public.admin_reports_maintenance_active());
DROP POLICY IF EXISTS "event_reports_maint_block_update" ON public.event_reports;
CREATE POLICY "event_reports_maint_block_update" ON public.event_reports
  AS RESTRICTIVE FOR UPDATE TO public
  USING (NOT public.admin_reports_maintenance_active())
  WITH CHECK (NOT public.admin_reports_maintenance_active());
DROP POLICY IF EXISTS "event_reports_maint_block_delete" ON public.event_reports;
CREATE POLICY "event_reports_maint_block_delete" ON public.event_reports
  AS RESTRICTIVE FOR DELETE TO public
  USING (NOT public.admin_reports_maintenance_active());

-- field_corrections ------------------------------------------
ALTER TABLE public.field_corrections ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "field_corrections_maint_block_insert" ON public.field_corrections;
CREATE POLICY "field_corrections_maint_block_insert" ON public.field_corrections
  AS RESTRICTIVE FOR INSERT TO public
  WITH CHECK (NOT public.admin_reports_maintenance_active());
DROP POLICY IF EXISTS "field_corrections_maint_block_update" ON public.field_corrections;
CREATE POLICY "field_corrections_maint_block_update" ON public.field_corrections
  AS RESTRICTIVE FOR UPDATE TO public
  USING (NOT public.admin_reports_maintenance_active())
  WITH CHECK (NOT public.admin_reports_maintenance_active());
DROP POLICY IF EXISTS "field_corrections_maint_block_delete" ON public.field_corrections;
CREATE POLICY "field_corrections_maint_block_delete" ON public.field_corrections
  AS RESTRICTIVE FOR DELETE TO public
  USING (NOT public.admin_reports_maintenance_active());

-- category_corrections ---------------------------------------
ALTER TABLE public.category_corrections ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "category_corrections_maint_block_insert" ON public.category_corrections;
CREATE POLICY "category_corrections_maint_block_insert" ON public.category_corrections
  AS RESTRICTIVE FOR INSERT TO public
  WITH CHECK (NOT public.admin_reports_maintenance_active());
DROP POLICY IF EXISTS "category_corrections_maint_block_update" ON public.category_corrections;
CREATE POLICY "category_corrections_maint_block_update" ON public.category_corrections
  AS RESTRICTIVE FOR UPDATE TO public
  USING (NOT public.admin_reports_maintenance_active())
  WITH CHECK (NOT public.admin_reports_maintenance_active());
DROP POLICY IF EXISTS "category_corrections_maint_block_delete" ON public.category_corrections;
CREATE POLICY "category_corrections_maint_block_delete" ON public.category_corrections
  AS RESTRICTIVE FOR DELETE TO public
  USING (NOT public.admin_reports_maintenance_active());

-- selection_reason_corrections -------------------------------
ALTER TABLE public.selection_reason_corrections ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "selection_reason_corrections_maint_block_insert" ON public.selection_reason_corrections;
CREATE POLICY "selection_reason_corrections_maint_block_insert" ON public.selection_reason_corrections
  AS RESTRICTIVE FOR INSERT TO public
  WITH CHECK (NOT public.admin_reports_maintenance_active());
DROP POLICY IF EXISTS "selection_reason_corrections_maint_block_update" ON public.selection_reason_corrections;
CREATE POLICY "selection_reason_corrections_maint_block_update" ON public.selection_reason_corrections
  AS RESTRICTIVE FOR UPDATE TO public
  USING (NOT public.admin_reports_maintenance_active())
  WITH CHECK (NOT public.admin_reports_maintenance_active());
DROP POLICY IF EXISTS "selection_reason_corrections_maint_block_delete" ON public.selection_reason_corrections;
CREATE POLICY "selection_reason_corrections_maint_block_delete" ON public.selection_reason_corrections
  AS RESTRICTIVE FOR DELETE TO public
  USING (NOT public.admin_reports_maintenance_active());

-- works ------------------------------------------------------
ALTER TABLE public.works ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "works_maint_block_insert" ON public.works;
CREATE POLICY "works_maint_block_insert" ON public.works
  AS RESTRICTIVE FOR INSERT TO public
  WITH CHECK (NOT public.admin_reports_maintenance_active());
DROP POLICY IF EXISTS "works_maint_block_update" ON public.works;
CREATE POLICY "works_maint_block_update" ON public.works
  AS RESTRICTIVE FOR UPDATE TO public
  USING (NOT public.admin_reports_maintenance_active())
  WITH CHECK (NOT public.admin_reports_maintenance_active());
DROP POLICY IF EXISTS "works_maint_block_delete" ON public.works;
CREATE POLICY "works_maint_block_delete" ON public.works
  AS RESTRICTIVE FOR DELETE TO public
  USING (NOT public.admin_reports_maintenance_active());

-- ------------------------------------------------------------
-- 3. Protect the lock key from `authenticated` (admin browser sessions).
--    service_role bypasses RLS, so the operator CLI can still seed /
--    acquire / release. This RESTRICTIVE policy ANDs with the existing
--    PERMISSIVE "Admin full access on app_settings" policy, denying an
--    authenticated admin any write to THIS key while leaving every other
--    app_settings key fully writable.
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "app_settings_lock_key_immutable" ON public.app_settings;
CREATE POLICY "app_settings_lock_key_immutable" ON public.app_settings
  AS RESTRICTIVE FOR ALL TO authenticated
  USING (key <> 'admin_reports_cleanup_maintenance')
  WITH CHECK (key <> 'admin_reports_cleanup_maintenance');
