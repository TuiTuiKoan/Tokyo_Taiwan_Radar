-- ============================================================
-- 049: merged_into_event_id
-- Add `merged_into_event_id` to track when an event has been
-- absorbed as a secondary URL into a primary event.
--
-- This is a reverse-link: if event A's source_url was added to
-- event B's secondary_source_urls, then A.merged_into_event_id = B.id.
--
-- Enables admin UI to show a "merged → <primary name>" badge
-- and filter merged/non-merged events easily.
-- ============================================================

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS merged_into_event_id UUID REFERENCES events(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_events_merged_into
  ON events(merged_into_event_id) WHERE merged_into_event_id IS NOT NULL;

COMMENT ON COLUMN events.merged_into_event_id IS
  'If set, this event has been absorbed into the referenced primary event as a secondary source URL. Set by merger.py or admin manual merge.';
