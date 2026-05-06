-- Migration 050: organizers + venues entity tables (Tier 2)
-- Spec: docs/specs/active/report-prototype-gap-fix/proposal.md § Phase 2
--
-- Purpose: normalize organizer / location_name strings so reports can aggregate
-- across spelling variants (e.g. 「日本台湾交流協会」 ≡ 「日台交流協会」 ≡
-- 「Japan-Taiwan Exchange Association」).
--
-- Original `events.organizer` and `events.location_name` are PRESERVED as
-- audit trail. Reports use `organizer_id` / `venue_id` for aggregation;
-- event detail pages still display the original raw strings.
--
-- Apply manually via Supabase Dashboard → SQL Editor.

-- ─── organizers ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organizers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_name_ja TEXT NOT NULL UNIQUE,
  canonical_name_zh TEXT,
  canonical_name_en TEXT,
  organizer_type TEXT,                -- mirrors events.organizer_type enum values
  aliases TEXT[] NOT NULL DEFAULT '{}',
  homepage TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── venues ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS venues (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_name_ja TEXT NOT NULL UNIQUE,
  canonical_name_zh TEXT,
  canonical_name_en TEXT,
  address TEXT,
  prefecture TEXT,
  city TEXT,
  latitude DECIMAL(9,6),
  longitude DECIMAL(9,6),
  aliases TEXT[] NOT NULL DEFAULT '{}',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── FK columns on events ─────────────────────────────────────────────────
ALTER TABLE events
  ADD COLUMN IF NOT EXISTS organizer_id UUID REFERENCES organizers(id) ON DELETE SET NULL;
ALTER TABLE events
  ADD COLUMN IF NOT EXISTS venue_id UUID REFERENCES venues(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_events_organizer_id ON events(organizer_id);
CREATE INDEX IF NOT EXISTS idx_events_venue_id ON events(venue_id);

-- Alias lookup: GIN indexes accelerate `aliases @> ARRAY['…']` queries used
-- by database.py upsert lookup.
CREATE INDEX IF NOT EXISTS idx_organizers_aliases ON organizers USING GIN (aliases);
CREATE INDEX IF NOT EXISTS idx_venues_aliases     ON venues     USING GIN (aliases);

-- ─── RLS: public read; writes go through service_role (bypass RLS) ────────
ALTER TABLE organizers ENABLE ROW LEVEL SECURITY;
ALTER TABLE venues     ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS organizers_read ON organizers;
CREATE POLICY organizers_read ON organizers FOR SELECT USING (true);

DROP POLICY IF EXISTS venues_read ON venues;
CREATE POLICY venues_read ON venues FOR SELECT USING (true);

-- ─── updated_at triggers ──────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS organizers_updated_at ON organizers;
CREATE TRIGGER organizers_updated_at BEFORE UPDATE ON organizers
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS venues_updated_at ON venues;
CREATE TRIGGER venues_updated_at BEFORE UPDATE ON venues
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
