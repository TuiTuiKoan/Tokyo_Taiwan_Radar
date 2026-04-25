-- Migration 017: Document 'reviewed' annotation_status value
--
-- annotation_status valid values:
--   'pending'   — awaiting AI annotation
--   'annotated' — AI-annotated (may still be overwritten by annotator --all)
--   'reviewed'  — human-reviewed via admin confirm-report; equivalent to
--                 'annotated' for display purposes, but fully protected:
--                 • annotator.py skips it (even with --all flag)
--                 • upsert_events() skips it (even with force_rescrape=true)
--                 • category_corrections records are the source of truth
--
-- This migration adds a comment to the column only. No schema change is needed
-- because annotation_status is plain text with no CHECK constraint.

COMMENT ON COLUMN events.annotation_status IS
  'Annotation pipeline state. '
  'pending = awaiting AI annotation; '
  'annotated = AI-processed (normal); '
  'reviewed = human-confirmed via admin review — fully protected from AI and scraper overwrite; '
  'error = annotation failed.';
