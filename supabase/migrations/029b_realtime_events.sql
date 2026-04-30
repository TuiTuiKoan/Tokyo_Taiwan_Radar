-- 029b_realtime_events.sql
-- Note: numbered 029b because 029_aeo_visits.sql already took the 029 slot.
-- Enable Supabase Realtime for the events table so the admin events list
-- receives live UPDATE events when reports are confirmed or events are edited.

ALTER PUBLICATION supabase_realtime ADD TABLE events;
