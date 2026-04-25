-- 011_event_reports_suggested_category.sql
-- Add user-suggested category to event_reports

ALTER TABLE event_reports
  ADD COLUMN IF NOT EXISTS suggested_category text[];
