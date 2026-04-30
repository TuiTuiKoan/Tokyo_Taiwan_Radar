-- 030_announcements.sql
-- Announcements / social media posts management
-- Supports multilingual content (ja/zh/en), per-locale images,
-- event linking, social publishing status tracking

-- Main announcements table
CREATE TABLE IF NOT EXISTS announcements (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          TEXT        UNIQUE NOT NULL,
  title_ja      TEXT,
  title_zh      TEXT,
  title_en      TEXT,
  body_ja       TEXT,
  body_zh       TEXT,
  body_en       TEXT,
  cover_image_url TEXT,        -- shared fallback image (must be public URL)
  image_ja      TEXT,          -- per-locale image override
  image_zh      TEXT,
  image_en      TEXT,
  is_featured   BOOLEAN     NOT NULL DEFAULT false,
  published_at  TIMESTAMPTZ,   -- NULL = draft
  social_status JSONB       NOT NULL DEFAULT '{}',
  -- { platform: { status, published_at, post_id, locale, error } }
  -- status ∈ 'idle' | 'publishing' | 'published' | 'error'
  author_id     UUID        REFERENCES auth.users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Junction table: an announcement can highlight 0..n events
CREATE TABLE IF NOT EXISTS announcement_events (
  announcement_id UUID NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
  event_id        UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  PRIMARY KEY (announcement_id, event_id)
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_announcements_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER announcements_updated_at
  BEFORE UPDATE ON announcements
  FOR EACH ROW EXECUTE FUNCTION update_announcements_updated_at();

-- Indexes
CREATE INDEX IF NOT EXISTS announcements_published_at_idx ON announcements (published_at DESC);
CREATE INDEX IF NOT EXISTS announcements_is_featured_idx ON announcements (is_featured) WHERE is_featured = true;
CREATE INDEX IF NOT EXISTS announcement_events_event_id_idx ON announcement_events (event_id);

-- RLS
ALTER TABLE announcements ENABLE ROW LEVEL SECURITY;
ALTER TABLE announcement_events ENABLE ROW LEVEL SECURITY;

-- Public: anyone can read published announcements
CREATE POLICY "announcements_public_read"
  ON announcements FOR SELECT
  USING (published_at IS NOT NULL AND published_at <= now());

-- Admin: full access (uses existing admin_list_users / user_roles pattern)
CREATE POLICY "announcements_admin_all"
  ON announcements FOR ALL
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

-- Public: read announcement_events for published announcements
CREATE POLICY "announcement_events_public_read"
  ON announcement_events FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM announcements a
      WHERE a.id = announcement_id
        AND a.published_at IS NOT NULL
        AND a.published_at <= now()
    )
  );

-- Admin: full access on junction table
CREATE POLICY "announcement_events_admin_all"
  ON announcement_events FOR ALL
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
