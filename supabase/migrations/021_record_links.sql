-- 021_record_links.sql
-- Add record_links column to events for storing post-event coverage and documentation links.
-- Each element is a JSON object: {"title": "...", "url": "..."}
-- Managed by admins via the event edit form; displayed publicly on the event detail page.
-- Run in Supabase Dashboard → SQL Editor

ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS record_links jsonb NOT NULL DEFAULT '[]'::jsonb;

-- Verification:
-- SELECT id, record_links FROM events LIMIT 3;  -- should show '[]' for existing rows
