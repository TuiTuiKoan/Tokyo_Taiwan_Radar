-- 029_realtime_events.sql
-- Enable Supabase Realtime for the events table so the admin events list
-- receives live UPDATE events when reports are confirmed or events are edited.

ALTER PUBLICATION supabase_realtime ADD TABLE events;
