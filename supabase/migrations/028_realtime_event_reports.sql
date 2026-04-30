-- 028_realtime_event_reports.sql
-- Enable Supabase Realtime for event_reports so the admin reports page
-- receives live INSERT and UPDATE events without manual page refresh.

ALTER PUBLICATION supabase_realtime ADD TABLE event_reports;
