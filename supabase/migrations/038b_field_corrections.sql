-- 038b_field_corrections.sql
-- CONFLICT NOTE: 038_performer.sql already existed in the workspace when
-- this migration was created. This file is 038b per project convention.
--
-- P1: Persist admin field corrections so the annotator can skip AI output
-- for fields that a human has already corrected.
--
-- Each row records one corrected field value for one event.
-- The annotator loads all rows at startup and skips writing AI output
-- to any (event_id, field_name) pair that has a human correction.

CREATE TABLE IF NOT EXISTS field_corrections (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id      uuid        NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  field_name    text        NOT NULL,
  original_value text,
  corrected_value text      NOT NULL,
  corrected_by  uuid        REFERENCES auth.users(id),
  created_at    timestamptz DEFAULT now()
);

-- Unique constraint: one correction per (event, field).
-- On re-submission (admin corrects again), upsert overwrites the old value.
ALTER TABLE field_corrections
  ADD CONSTRAINT field_corrections_event_field_uq
  UNIQUE (event_id, field_name);

CREATE INDEX IF NOT EXISTS field_corrections_event_id_idx
  ON field_corrections (event_id);

ALTER TABLE field_corrections ENABLE ROW LEVEL SECURITY;

-- Admin: full access
CREATE POLICY "Admin full access on field_corrections"
  ON field_corrections
  FOR ALL
  TO authenticated
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

-- Service role (scraper/annotator): read-only via service key (bypasses RLS).
-- No additional policy needed — service role bypasses all RLS.
