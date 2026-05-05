-- ============================================================
-- 046: daily_quality_metrics — daily KPI for source precision
-- Admin must run in Supabase Dashboard → SQL Editor
-- ============================================================

CREATE TABLE IF NOT EXISTS daily_quality_metrics (
  metric_date         date         PRIMARY KEY,
  events_upserted     int          NOT NULL DEFAULT 0,
  events_active       int          NOT NULL DEFAULT 0,
  exclusion_hits      int          NOT NULL DEFAULT 0,
  irrelevant_reports  int          NOT NULL DEFAULT 0,
  precision_rate      numeric(5,4),
  computed_at         timestamptz  NOT NULL DEFAULT now()
);

COMMENT ON TABLE daily_quality_metrics IS
  'Daily aggregated quality KPI. Computed by scraper/daily_quality.py; '
  'recent 14 days are recomputed every run to absorb late-arriving reports.';
COMMENT ON COLUMN daily_quality_metrics.events_upserted IS
  'Count of parent events whose scraped_at falls on metric_date.';
COMMENT ON COLUMN daily_quality_metrics.precision_rate IS
  '1 - irrelevant_reports / max(events_upserted, 1). NULL when events_upserted = 0.';

ALTER TABLE daily_quality_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY daily_quality_metrics_admin_select
  ON daily_quality_metrics FOR SELECT TO authenticated
  USING (public.is_admin());

-- Service role can write (no policy needed)

CREATE INDEX IF NOT EXISTS daily_quality_metrics_date_idx
  ON daily_quality_metrics (metric_date DESC);
