-- 060_eval_monitoring.sql
-- Plan v6 Batch A — eval framework 維運 + B1 FC 衝突監控
--
-- Adds:
--   1. daily_quality_metrics — annotator_stage1_pass / stage2_pass / eval_run_at
--      + fc_override_attempts (Phase 3 metric)
--   2. field_corrections — override_attempted_at / override_attempted_value
--      + override_attempt_count (B1 guard logs every attempted overwrite)
--
-- Read by:
--   - .github/workflows/eval-annotator.yml (Stage 1 KPI guard, upsert)
--   - .github/workflows/eval-annotator-stage2.yml (Stage 2 weekly cron)
--   - scraper/annotator.py B1 guard (writes override_attempted_* on enrich conflict)
--   - scraper/daily_quality.py compute_day() (reads fc_override_attempts)

ALTER TABLE daily_quality_metrics
  ADD COLUMN IF NOT EXISTS annotator_stage1_pass  INTEGER,
  ADD COLUMN IF NOT EXISTS annotator_stage2_pass  INTEGER,
  ADD COLUMN IF NOT EXISTS annotator_eval_run_at  TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS fc_override_attempts   INTEGER DEFAULT 0;

ALTER TABLE field_corrections
  ADD COLUMN IF NOT EXISTS override_attempted_at     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS override_attempted_value  TEXT,
  ADD COLUMN IF NOT EXISTS override_attempt_count    INTEGER DEFAULT 0;

-- Helpful index for daily_quality.py compute_day() range scan:
CREATE INDEX IF NOT EXISTS idx_field_corrections_override_attempted_at
  ON field_corrections (override_attempted_at)
  WHERE override_attempted_at IS NOT NULL;
