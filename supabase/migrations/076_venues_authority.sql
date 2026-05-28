-- Migration 076: venues authority flags
-- Spec: /memories/session/plan.md PR-2 Phase 0

ALTER TABLE venues
  ADD COLUMN IF NOT EXISTS is_authoritative BOOL NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS is_multi_venue BOOL NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS homepage TEXT,
  ADD COLUMN IF NOT EXISTS prefectures TEXT[] DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_venues_is_authoritative
  ON venues(is_authoritative) WHERE is_authoritative = true;

COMMENT ON COLUMN venues.is_authoritative IS
  'When true, annotator uses this venue as canonical (unless field_corrections lock exists).';
COMMENT ON COLUMN venues.is_multi_venue IS
  'Multi-venue festival (for example film festivals) with no single fixed address; use prefectures list.';
