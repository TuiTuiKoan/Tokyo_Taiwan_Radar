-- ============================================================
-- 044: event_deactivation_audit
-- Add audit columns to events for tracking why/when/how an event
-- was deactivated. Enables post-hoc analysis of merger decisions.
-- Admin must run in Supabase Dashboard → SQL Editor.
-- ============================================================

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS deactivated_reason TEXT,
  ADD COLUMN IF NOT EXISTS deactivated_by_pass TEXT;

-- deactivated_by_pass values:
--   'merger_pass_0'  — gnews within-source dedup
--   'merger_pass_1'  — cross-source name similarity
--   'merger_pass_2'  — news-report date+location matching
--   'merger_pass_3'  — orphan sub-event reattach / grandchild flatten
--   'orphan_cleanup' — orphan sub-event with no surviving parent match
--   'admin_manual'   — manually deactivated by admin via UI

CREATE INDEX IF NOT EXISTS idx_events_deactivated
  ON events(is_active, deactivated_at DESC);
