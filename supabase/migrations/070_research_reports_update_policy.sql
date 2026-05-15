-- 070_research_reports_update_policy.sql
-- Add admin UPDATE policy for research_reports.
-- Migration 008 only created a SELECT policy, so the "標記為已審閱" button
-- was silently blocked by RLS (no matching UPDATE policy → permission denied).
-- Run in Supabase Dashboard → SQL Editor

CREATE POLICY "Admins update research_reports"
  ON research_reports FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  );
