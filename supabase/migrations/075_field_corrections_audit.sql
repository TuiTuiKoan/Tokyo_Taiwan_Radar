-- 075_field_corrections_audit.sql
-- Audit trail for QA Heartbeat's automatic field_corrections unlock/override.
--
-- Every time qa_heartbeat.py changes an event field or its field_corrections
-- row, an audit row is written BEFORE the mutation (operation_status='started').
-- After the write completes and post-write verification passes, the audit
-- row is updated to operation_status='applied' / verified_at=now().
-- Rollback restores from event_before_value_json + fc_before_* columns.

CREATE TABLE IF NOT EXISTS public.field_corrections_audit (
  id                       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Linkage
  event_id                 uuid        NOT NULL REFERENCES public.events(id) ON DELETE CASCADE,
  field_name               text        NOT NULL,
  report_id                uuid        REFERENCES public.event_reports(id) ON DELETE SET NULL,
  field_correction_id      uuid,

  -- FC row state before the mutation (NULL if FC row did not exist)
  fc_before_original_value  text,
  fc_before_corrected_value text,
  fc_before_corrected_by    uuid,
  fc_before_report_id       uuid,

  -- Event field state — JSONB so text[] and NULL rollback correctly
  event_before_value_json   jsonb,
  event_after_value_json    jsonb,

  -- Classification context
  unlock_reason            text        NOT NULL,
  r_class                  text,
  model_used               text,
  confidence               numeric(3, 2),

  -- Write lifecycle
  operation_status         text        NOT NULL DEFAULT 'started',
  error_message            text,
  verified_at              timestamptz,

  -- Rollback bookkeeping
  rolled_back_at           timestamptz,
  rolled_back_reason       text,

  created_at               timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT field_corrections_audit_confidence_check
    CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),

  CONSTRAINT field_corrections_audit_operation_status_check
    CHECK (operation_status IN ('started', 'applied', 'verify_failed', 'rolled_back'))
);

CREATE INDEX IF NOT EXISTS field_corrections_audit_event_id_idx
  ON public.field_corrections_audit (event_id);

CREATE INDEX IF NOT EXISTS field_corrections_audit_created_at_idx
  ON public.field_corrections_audit (created_at DESC);

CREATE INDEX IF NOT EXISTS field_corrections_audit_r_class_idx
  ON public.field_corrections_audit (r_class)
  WHERE r_class IS NOT NULL;

CREATE INDEX IF NOT EXISTS field_corrections_audit_operation_status_idx
  ON public.field_corrections_audit (operation_status);

CREATE INDEX IF NOT EXISTS field_corrections_audit_active_idx
  ON public.field_corrections_audit (created_at DESC)
  WHERE rolled_back_at IS NULL;

-- Service-role only: heartbeat writes via service_role key, no public access.
ALTER TABLE public.field_corrections_audit ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.field_corrections_audit TO service_role;
