-- migration 074: store auto-generate run artifacts in DB
-- Allows daily_report.py to display events_found, cost, source_id stability,
-- and sample Taiwan keyword check without requiring local filesystem artifacts.

ALTER TABLE research_sources
  ADD COLUMN IF NOT EXISTS auto_scraper_artifacts JSONB;

COMMENT ON COLUMN research_sources.auto_scraper_artifacts IS
  'Snapshot of key generate.py run outputs: {events_found, cost_usd, source_id_url_pattern, sample_titles[3]}. '
  'Written on success; allows daily_report.py to display metrics without local filesystem artifacts.';
