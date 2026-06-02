-- ── Migration: 085_event_views_traffic_source ──────────────────
-- Description: Add traffic_source column to event_views table with indexing.

ALTER TABLE public.event_views
  ADD COLUMN IF NOT EXISTS traffic_source text;

CREATE INDEX IF NOT EXISTS event_views_traffic_source_idx
  ON public.event_views (traffic_source);
