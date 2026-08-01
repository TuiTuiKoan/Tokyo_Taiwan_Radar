-- ============================================================
-- 096: maintenance_lock_search_path
-- Decision-16a maintenance lock — Lane A A2 narrow-scope hardening.
--
-- WHY THIS EXISTS:
--   The 2026-08-01 live inventory of public.admin_reports_maintenance_active()
--   found exactly ONE drift from the approved contract:
--       owner            = postgres              OK
--       language         = sql                   OK
--       volatility       = s (STABLE)            OK
--       security_definer = true                  OK
--       config           = {search_path=public}  DRIFT (contract: pg_catalog)
--       acl              = no PUBLIC entry       OK (REVOKE already in force)
--   Migration 094 authored `SET search_path = public`, so tracked SQL and live
--   agree with each other but not with the approved contract. This migration
--   closes that single gap. Everything else is an idempotent re-declaration.
--
-- APPLY STATUS: APPLIED in production (confirmed 2026-08-01).
--   Post-apply verification passed: the 7-column pg_proc query now returns
--   config = {search_path=pg_catalog}, with owner postgres, language sql,
--   volatility s, security_definer true, and an ACL that still carries
--   anon / authenticated / service_role EXECUTE and NO PUBLIC entry.
--   admin_reports_maintenance_active() still returns false and the lock row
--   is unchanged, so the predicate and the six dependent RESTRICTIVE policies
--   survived the CREATE OR REPLACE intact.
--
-- CREATE OR REPLACE, NEVER DROP:
--   The six writer tables from 094 carry RESTRICTIVE RLS policies whose
--   USING / WITH CHECK expressions depend on this function. DROP FUNCTION
--   would fail on those dependencies (and CASCADE would silently delete the
--   policies). CREATE OR REPLACE keeps the SAME function OID, so every
--   dependent policy stays bound and completely unaffected.
--
-- SEARCH_PATH SAFETY:
--   With search_path = pg_catalog the body must not rely on implicit `public`
--   resolution, so app_settings is schema-qualified. The `jsonb` type, the
--   `->` operator and the `=` operator all live in pg_catalog, so the
--   predicate still resolves.
--
-- SCOPE / NON-SCOPE:
--   * Touches: the function definition + its owner + its EXECUTE ACL, only.
--   * Does NOT add, alter or drop any RLS policy, RLS flag, table grant, or
--     any other object. Policy/grant drift belongs to a separate plan and
--     must not be folded in here.
--   * No new table and no permission-model change, so no Data-API GRANT
--     block is required.
--
-- POST-APPLY VERIFICATION (re-run the same 7-column pg_proc query):
--     SELECT p.proname,
--            pg_catalog.pg_get_userbyid(p.proowner) AS owner,
--            l.lanname                              AS language,
--            p.provolatile                          AS volatility,
--            p.prosecdef                            AS security_definer,
--            p.proconfig                            AS config,
--            p.proacl                               AS acl
--       FROM pg_catalog.pg_proc p
--       JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
--       JOIN pg_catalog.pg_language  l ON l.oid = p.prolang
--      WHERE n.nspname = 'public'
--        AND p.proname = 'admin_reports_maintenance_active';
--   EXPECTED: config becomes {search_path=pg_catalog}; owner still postgres,
--   language still sql, volatility still s, security_definer still true, and
--   acl still lists anon / authenticated / service_role EXECUTE with NO
--   PUBLIC entry.
--
--   Then confirm the predicate itself is unchanged (lock is inactive):
--     SELECT public.admin_reports_maintenance_active();   -- expected: false
--
-- ROLLBACK (manual, only if ever needed after a successful apply):
--     CREATE OR REPLACE FUNCTION public.admin_reports_maintenance_active()
--     RETURNS boolean
--     LANGUAGE sql
--     SECURITY DEFINER
--     STABLE
--     SET search_path = public
--     AS $rollback$
--       SELECT NOT EXISTS (
--         SELECT 1 FROM public.app_settings
--         WHERE key = 'admin_reports_cleanup_maintenance'
--           AND value->'active' = 'false'::jsonb
--       );
--     $rollback$;
--   (Also CREATE OR REPLACE — the rollback must never DROP either.)
--
-- Admin must run in Supabase Dashboard -> SQL Editor.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Re-declare the predicate with the contract search_path.
--    Semantics are identical to 094: TRUE = DENY writes. Allow (false)
--    ONLY when the row exists AND value->'active' is exactly the JSON
--    boolean false — missing row, missing key, JSON null, string "false"
--    and any other malformed value all evaluate to DENY (fail-closed).
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.admin_reports_maintenance_active()
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = pg_catalog
AS $$
  SELECT NOT EXISTS (
    SELECT 1 FROM public.app_settings
    WHERE key = 'admin_reports_cleanup_maintenance'
      AND value->'active' = 'false'::jsonb
  );
$$;

-- ------------------------------------------------------------
-- 2. Idempotent re-declaration of owner + EXECUTE ACL.
--    Live already matches all of this; the statements are here so the file
--    is self-contained and safe to re-run.
--
--    service_role is deliberately NOT revoked: it currently holds EXECUTE,
--    and both the maintenance CLI (scraper/_oneoff_admin_reports_maintenance.py)
--    and the verification RPC call depend on it.
-- ------------------------------------------------------------
ALTER FUNCTION public.admin_reports_maintenance_active() OWNER TO postgres;
REVOKE EXECUTE ON FUNCTION public.admin_reports_maintenance_active() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.admin_reports_maintenance_active() TO anon, authenticated;
