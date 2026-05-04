-- 038_performer.sql
-- Add performer column for schema.org Event JSON-LD (Person type).
-- Stores the single primary person (not organization) who performs or presents
-- at the event in a featured role. Extracted by annotator.py via GPT.

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS performer text;
