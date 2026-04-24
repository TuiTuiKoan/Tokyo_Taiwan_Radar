-- Migration 009: research_sources table
-- Status flow: candidate → researched → recommended → implemented | not-viable

CREATE TABLE research_sources (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  name TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  agent_category TEXT,
  category TEXT,
  status TEXT NOT NULL DEFAULT 'candidate',
  scraping_feasibility TEXT,
  event_types TEXT,
  frequency TEXT,
  reason TEXT,
  url_verified BOOLEAN DEFAULT FALSE,
  source_profile JSONB,
  github_issue_url TEXT,
  first_seen_at TIMESTAMPTZ DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE research_sources ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can read research_sources"
  ON research_sources FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM user_roles WHERE user_id = auth.uid() AND role = 'admin'
  ));

CREATE POLICY "Service role can write research_sources"
  ON research_sources FOR ALL
  USING (auth.role() = 'service_role');