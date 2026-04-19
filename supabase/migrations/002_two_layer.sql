-- Migration: Two-layer architecture (raw + annotated)
-- Adds raw-layer columns to store unprocessed scraper output,
-- and an annotation_status to track AI processing state.

ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS raw_title text,
  ADD COLUMN IF NOT EXISTS raw_description text,
  ADD COLUMN IF NOT EXISTS annotation_status text NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS annotated_at timestamptz;

-- Index for the annotator to efficiently find pending events
CREATE INDEX IF NOT EXISTS events_annotation_status_idx
  ON public.events (annotation_status);

-- Backfill existing events: treat current data as already annotated
UPDATE public.events
SET
  raw_title       = COALESCE(name_ja, name_zh, name_en),
  raw_description = COALESCE(description_ja, description_zh, description_en),
  annotation_status = 'annotated',
  annotated_at    = updated_at
WHERE annotation_status = 'pending';
