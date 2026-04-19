-- Add selection_reason column to explain why the AI included each event
ALTER TABLE events
  ADD COLUMN IF NOT EXISTS selection_reason text;
