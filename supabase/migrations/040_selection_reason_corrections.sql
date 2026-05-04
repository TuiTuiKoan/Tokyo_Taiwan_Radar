-- 040_selection_reason_corrections.sql
-- P3.3: New table for recording admin-corrected selection_reason values.
--       Used by scraper/selection_reason_feedback.py to build few-shot examples
--       injected into annotator.py SYSTEM_PROMPT at runtime.
--
-- P4 缺口 #6: Add report_id FK to field_corrections so each field correction
--             can be traced back to the originating event_reports row.

-- ─── P3.3: selection_reason_corrections ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS selection_reason_corrections (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id        uuid        NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  raw_title       text,
  raw_description text,
  ai_sr           jsonb,                    -- original GPT output {ja, zh, en}
  corrected_sr    jsonb       NOT NULL,     -- admin-corrected version {ja, zh, en}
  corrected_by    uuid        REFERENCES auth.users(id),
  created_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT selection_reason_corrections_event_uq UNIQUE (event_id)
);

ALTER TABLE selection_reason_corrections ENABLE ROW LEVEL SECURITY;

-- Admin can read/write; service role bypasses RLS automatically.
CREATE POLICY "admin_full_src" ON selection_reason_corrections
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  );

-- ─── P4 缺口 #6: report_id on field_corrections ──────────────────────────────

ALTER TABLE field_corrections
  ADD COLUMN IF NOT EXISTS report_id uuid
    REFERENCES event_reports(id) ON DELETE SET NULL;

-- Index for reverse-lookup: given a report, which field corrections came from it?
CREATE INDEX IF NOT EXISTS field_corrections_report_id_idx
  ON field_corrections (report_id)
  WHERE report_id IS NOT NULL;
