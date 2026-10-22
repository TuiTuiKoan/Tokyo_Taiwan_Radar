-- ============================================================
-- 098: scope_report_transaction
-- Atomic admin confirmation for machine-owned scope reports and
-- database-level provenance enforcement for machine report tokens.
--
-- Apply through Supabase Dashboard -> SQL Editor before deploying the
-- web code that calls public.confirm_scope_report().
-- ============================================================

-- Public and authenticated callers may create ordinary reports, but only the
-- service-role annotator may mint scope/security findings and their metadata.
ALTER TABLE public.event_reports ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "event_reports_machine_tokens_block_insert"
  ON public.event_reports;
CREATE POLICY "event_reports_machine_tokens_block_insert"
  ON public.event_reports
  AS RESTRICTIVE
  FOR INSERT
  TO anon, authenticated
  WITH CHECK (
    NOT EXISTS (
      SELECT 1
      FROM pg_catalog.unnest(report_types) AS token(value)
      WHERE token.value IN (
        'scopeReviewNonJapan',
        'auto_security_prompt_injection'
      )
      OR token.value LIKE 'scopeDecision:%'
      OR token.value LIKE 'scopeRegion:%'
      OR token.value LIKE 'scopeHash:%'
      OR token.value LIKE 'securityHash:%'
      OR token.value LIKE 'securitySeverity:%'
    )
  );

CREATE OR REPLACE FUNCTION public.confirm_scope_report(
  p_report_id uuid,
  p_expected_scope_hash text,
  p_admin_notes text DEFAULT NULL
)
RETURNS TABLE(report_id uuid, event_id uuid)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog
AS $function$
DECLARE
  v_event_id uuid;
  v_report_types text[];
  v_machine_notes text;
  v_decision text;
  v_region text;
BEGIN
  IF (SELECT auth.uid()) IS NULL OR NOT EXISTS (
    SELECT 1
    FROM public.user_roles AS roles
    WHERE roles.user_id = (SELECT auth.uid())
      AND roles.role = 'admin'
  ) THEN
    RAISE EXCEPTION 'Forbidden' USING ERRCODE = '42501';
  END IF;

  IF p_expected_scope_hash IS NULL
     OR p_expected_scope_hash !~ '^[0-9a-f]{16}$' THEN
    RAISE EXCEPTION 'Invalid expected scope hash' USING ERRCODE = '22023';
  END IF;

  SELECT reports.event_id, reports.report_types, reports.admin_notes
    INTO v_event_id, v_report_types, v_machine_notes
    FROM public.event_reports AS reports
   WHERE reports.id = p_report_id
     AND reports.status = 'pending'
   FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Scope report not found or not pending'
      USING ERRCODE = 'P0002';
  END IF;

  IF pg_catalog.cardinality(v_report_types) <> 5
     OR (
       SELECT pg_catalog.count(*)
       FROM pg_catalog.unnest(v_report_types) AS token(value)
       WHERE token.value = 'irrelevant'
     ) <> 1
     OR (
       SELECT pg_catalog.count(*)
       FROM pg_catalog.unnest(v_report_types) AS token(value)
       WHERE token.value = 'scopeReviewNonJapan'
     ) <> 1
     OR (
       SELECT pg_catalog.count(*)
       FROM pg_catalog.unnest(v_report_types) AS token(value)
       WHERE token.value IN (
         'scopeDecision:out_of_scope',
         'scopeDecision:uncertain'
       )
     ) <> 1
     OR (
       SELECT pg_catalog.count(*)
       FROM pg_catalog.unnest(v_report_types) AS token(value)
       WHERE token.value IN (
         'scopeRegion:taiwan',
         'scopeRegion:other_foreign'
       )
     ) <> 1
     OR (
       SELECT pg_catalog.count(*)
       FROM pg_catalog.unnest(v_report_types) AS token(value)
       WHERE token.value = 'scopeHash:' || p_expected_scope_hash
     ) <> 1 THEN
    RAISE EXCEPTION 'Invalid or stale scope report evidence'
      USING ERRCODE = '22023';
  END IF;

  SELECT pg_catalog.substr(token.value, 15)
    INTO v_decision
    FROM pg_catalog.unnest(v_report_types) AS token(value)
   WHERE token.value LIKE 'scopeDecision:%';
  SELECT pg_catalog.substr(token.value, 13)
    INTO v_region
    FROM pg_catalog.unnest(v_report_types) AS token(value)
   WHERE token.value LIKE 'scopeRegion:%';

  PERFORM 1
    FROM public.events AS events
   WHERE events.id = v_event_id
     AND events.is_active IS TRUE
   FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Event not found or no longer active'
      USING ERRCODE = 'P0002';
  END IF;

  UPDATE public.events
     SET is_active = false,
         deactivated_at = pg_catalog.clock_timestamp(),
         deactivated_reason = 'out_of_scope: ' || v_decision ||
           ' in ' || v_region || ' - admin confirmed',
         deactivated_by_pass = 'admin_manual'
   WHERE id = v_event_id
     AND is_active IS TRUE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Event changed during scope confirmation'
      USING ERRCODE = '40001';
  END IF;

  UPDATE public.event_reports
     SET status = 'confirmed',
         confirmed_at = pg_catalog.clock_timestamp(),
         admin_notes = CASE
           WHEN NULLIF(
             pg_catalog.btrim(COALESCE(p_admin_notes, '')),
             ''
           ) IS NULL THEN v_machine_notes
           WHEN NULLIF(
             pg_catalog.btrim(COALESCE(v_machine_notes, '')),
             ''
           ) IS NULL THEN pg_catalog.btrim(p_admin_notes)
           ELSE v_machine_notes || pg_catalog.chr(10) || '---' ||
             pg_catalog.chr(10) || pg_catalog.btrim(p_admin_notes)
         END
   WHERE id = p_report_id
     AND event_id = v_event_id
     AND status = 'pending';

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Scope report changed during confirmation'
      USING ERRCODE = '40001';
  END IF;

  RETURN QUERY SELECT p_report_id, v_event_id;
END;
$function$;

ALTER FUNCTION public.confirm_scope_report(uuid, text, text) OWNER TO postgres;
REVOKE ALL ON FUNCTION public.confirm_scope_report(uuid, text, text)
  FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.confirm_scope_report(uuid, text, text)
  TO authenticated, service_role;

COMMENT ON FUNCTION public.confirm_scope_report(uuid, text, text) IS
  'Atomically validates scope evidence, deactivates its event, and confirms the pending report.';
