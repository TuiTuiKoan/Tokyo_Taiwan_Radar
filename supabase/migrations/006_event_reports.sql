-- 006_event_reports.sql
-- User feedback reports for events (AI accuracy issues)

CREATE TABLE IF NOT EXISTS event_reports (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id     uuid        NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  report_types text[]      NOT NULL,
  locale       text,
  status       text        NOT NULL DEFAULT 'pending',
  admin_notes  text,
  confirmed_at timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS event_reports_event_id_idx ON event_reports(event_id);
CREATE INDEX IF NOT EXISTS event_reports_status_idx   ON event_reports(status);

ALTER TABLE event_reports ENABLE ROW LEVEL SECURITY;

-- Anyone (including anonymous visitors) may submit a report
CREATE POLICY "Anyone can submit reports"
  ON event_reports FOR INSERT
  WITH CHECK (true);

-- Only admins may read reports
CREATE POLICY "Admins can view reports"
  ON event_reports FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  );

-- Only admins may update (confirm / dismiss) reports
CREATE POLICY "Admins can update reports"
  ON event_reports FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  );
