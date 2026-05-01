-- Migration 032: auto-scraper run tracking on research_sources (Layer B Phase 2)
--
-- Adds status columns so `scraper/auto_scraper/generate.py` can record
-- attempt outcomes per source row without touching events / scraper_runs.
ALTER TABLE research_sources
  ADD COLUMN IF NOT EXISTS auto_scraper_status TEXT,
  ADD COLUMN IF NOT EXISTS auto_scraper_pr_url TEXT,
  ADD COLUMN IF NOT EXISTS auto_scraper_failed_reason TEXT,
  ADD COLUMN IF NOT EXISTS auto_scraper_attempted_at TIMESTAMPTZ;

COMMENT ON COLUMN research_sources.auto_scraper_status IS
  'NULL=never attempted; pending|generating|dry-run|sandbox-failed|spec-invalid|budget-exceeded|llm-error|success|pr-opened|live|broken';
