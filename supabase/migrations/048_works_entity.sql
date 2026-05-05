-- ============================================================
-- 048: works_entity
-- Add `works` table as upper entity for events that share a single
-- creative work across venues / dates (films, stage plays, tours).
-- One work → many events (1:N via events.work_id).
--
-- Coexists with parent_event_id (master ↔ sub-event split, e.g.
-- film festival → individual screenings). Both columns are
-- independent and may be set together.
--
-- Admin must run in Supabase Dashboard → SQL Editor.
-- ============================================================

CREATE TABLE IF NOT EXISTS works (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  work_type       TEXT NOT NULL CHECK (work_type IN ('film','stage','exhibition','concert_tour','other')),
  original_title  TEXT NOT NULL,
  title_ja        TEXT,
  title_zh        TEXT,
  title_en        TEXT,
  director        TEXT,
  cast_summary    TEXT,
  release_year    INT,
  country         TEXT DEFAULT 'TW',
  description     TEXT,
  poster_url      TEXT,
  external_links  JSONB,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_works_original_title ON works(original_title);
CREATE INDEX IF NOT EXISTS idx_works_work_type      ON works(work_type);

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS work_id UUID REFERENCES works(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_events_work_id
  ON events(work_id) WHERE work_id IS NOT NULL;

-- Auto-update updated_at on row change
CREATE OR REPLACE FUNCTION works_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS works_updated_at ON works;
CREATE TRIGGER works_updated_at
  BEFORE UPDATE ON works
  FOR EACH ROW EXECUTE FUNCTION works_set_updated_at();

-- RLS: anyone may SELECT, only admins may INSERT/UPDATE/DELETE
ALTER TABLE works ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anyone can read works"   ON works;
CREATE POLICY "Anyone can read works"
  ON works FOR SELECT
  USING (true);

DROP POLICY IF EXISTS "Admins can manage works" ON works;
CREATE POLICY "Admins can manage works"
  ON works FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  );
