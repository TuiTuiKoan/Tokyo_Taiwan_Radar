-- Migration 012: allow admins to update research_reports and research_sources
-- Without this, the "Mark as reviewed" button silently fails due to RLS blocking UPDATE.

-- research_reports: admin UPDATE policy
CREATE POLICY "Admins can update research_reports"
  ON research_reports FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  );

-- research_sources: admin UPDATE policy (e.g. changing status from admin UI)
CREATE POLICY "Admins can update research_sources"
  ON research_sources FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  );
