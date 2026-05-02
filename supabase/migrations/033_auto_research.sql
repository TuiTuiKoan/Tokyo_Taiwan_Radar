-- Migration 033: auto_research pipeline columns
-- Run in Supabase Dashboard SQL Editor

ALTER TABLE research_sources
  ADD COLUMN IF NOT EXISTS auto_research_status       text DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS auto_research_attempted_at timestamptz,
  ADD COLUMN IF NOT EXISTS auto_research_score        numeric(3,2);

COMMENT ON COLUMN research_sources.auto_research_status IS
  'pending | assessed | not-viable | error';
COMMENT ON COLUMN research_sources.auto_research_score IS
  'Taiwan relevance score 0.00–1.00 from GPT-4o assessment';

CREATE INDEX IF NOT EXISTS idx_research_sources_auto_research_status
  ON research_sources(auto_research_status);
