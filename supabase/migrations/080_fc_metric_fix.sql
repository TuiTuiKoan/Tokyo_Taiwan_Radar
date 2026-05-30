-- 080_fc_metric_fix.sql
-- Plan v7 Hotfix — fix fc_override_attempts daily metric + annotator_stage2 split columns
--
-- Root cause: field_corrections.override_attempted_at is overwritten on every B1 guard
-- trigger, so daily_quality.py counting "rows where override_attempted_at falls today"
-- only sees the most-recent-attempt date, not the first-occurrence date. Days with no
-- batch re-annotation appear as 0 even when conflicts exist.
--
-- Fix A: rename override_attempted_at → last_override_attempted_at (semantic clarity),
--        add first_override_attempted_at (write-once). daily_quality.py will query first.
--
-- Fix B: add annotator_stage2_nz_pass / annotator_stage2_ne_pass split columns so
--        per-field regression is visible without having to decode the combined sum.

-- ── Fix A ──────────────────────────────────────────────────────────────────────────────

-- 1. Rename override_attempted_at → last_override_attempted_at
--    PostgreSQL automatically updates partial index predicates on rename.
ALTER TABLE field_corrections
  RENAME COLUMN override_attempted_at TO last_override_attempted_at;

-- 2. Add first_override_attempted_at (write-once semantics enforced in application code)
ALTER TABLE field_corrections
  ADD COLUMN IF NOT EXISTS first_override_attempted_at TIMESTAMPTZ;

-- 3. Backfill: for rows that already have a last value, set first = last
--    (best available approximation; first true occurrence is not stored historically)
UPDATE field_corrections
  SET first_override_attempted_at = last_override_attempted_at
  WHERE last_override_attempted_at IS NOT NULL
    AND first_override_attempted_at IS NULL;

-- 4. Partial index on first_override_attempted_at for efficient daily_quality range queries
CREATE INDEX IF NOT EXISTS idx_fc_first_override_attempted_at
  ON field_corrections (first_override_attempted_at)
  WHERE first_override_attempted_at IS NOT NULL;

-- ── Fix B ──────────────────────────────────────────────────────────────────────────────

-- 5. Add split-field Stage 2 eval columns to daily_quality_metrics
ALTER TABLE daily_quality_metrics
  ADD COLUMN IF NOT EXISTS annotator_stage2_nz_pass INTEGER,
  ADD COLUMN IF NOT EXISTS annotator_stage2_ne_pass INTEGER;
